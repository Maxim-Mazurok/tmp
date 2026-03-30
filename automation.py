"""Automation loop and test mode for the fishing minigame."""

import os
import sys
import time
import signal
import traceback
import ctypes
import cv2
import numpy as np

from config import (
    BLUE_H_MIN, BLUE_H_MAX,
    SEARCH_MARGIN_X_FRAC, SEARCH_MARGIN_Y_FRAC,
    CAST_DELAY, BITE_WAIT, MINIGAME_GRACE, CAST_WAIT_POLL,
    BAR_APPEAR_DELAY, CONTROL_HZ,
)
from detection import BarDetector
from capture import ScreenCapture, find_game_window
from control import FishingController, GameState

# Only import pydirectinput when actually controlling (not in test mode)
pydirectinput = None


def _setup_topmost_window(window_name):
    """Make an OpenCV window always-on-top using Win32 API."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, window_name)
        if hwnd:
            HWND_TOPMOST = -1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
    except Exception:
        pass


def _handle_idle(state_ctx):
    """Handle IDLE state: anti-AFK movement and casting."""
    now = state_ctx['now']
    if state_ctx['reel_only']:
        state_ctx['state'] = GameState.WAITING
        state_ctx['state_start'] = now
        state_ctx['detector'].bar_found = False
        state_ctx['controller'].reset()
    else:
        pydirectinput.press('a')
        time.sleep(0.15)
        pydirectinput.press('d')
        time.sleep(0.15)
        print(f"\n[{state_ctx['catches']}] Casting...")
        pydirectinput.press('2')
        state_ctx['state'] = GameState.WAITING
        state_ctx['state_start'] = now
        state_ctx['detector'].bar_found = False
        state_ctx['controller'].reset()
        time.sleep(1.0)


def _handle_waiting(state_ctx):
    """Handle WAITING state: wait for bite and poll for minigame bar."""
    now = state_ctx['now']
    detector = state_ctx['detector']
    capture = state_ctx['capture']
    debug = state_ctx['debug']
    reel_only = state_ctx['reel_only']

    wait_elapsed = now - state_ctx['state_start']
    total_wait = BITE_WAIT if reel_only else BITE_WAIT + BAR_APPEAR_DELAY
    if not reel_only and wait_elapsed < total_wait:
        remaining = total_wait - wait_elapsed
        bite_remaining = max(0, BITE_WAIT - wait_elapsed)
        if debug:
            img, _ = capture.capture_search_region()
            vis = img.copy()
            if bite_remaining > 0:
                label = f"Waiting for bite... {bite_remaining:.0f}s"
            else:
                label = f"Bar appearing... {remaining:.0f}s"
            cv2.putText(vis, label,
                        (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            show = cv2.resize(vis, (600, 500))
            cv2.imshow('Fishing Bot', show)
            if not state_ctx['topmost_set']:
                _setup_topmost_window('Fishing Bot')
                state_ctx['topmost_set'] = True
            if cv2.waitKey(1) & 0xFF == ord('q'):
                state_ctx['running'] = False
                return
        time.sleep(min(1.0, remaining))
        return

    # Poll for the minigame bar to appear
    img, region = capture.capture_search_region()
    state_ctx['search_offset_x'] = region['left']
    state_ctx['search_offset_y'] = region['top']

    if detector.find_bar(img):
        # Validate the detected bar has sufficient bright blue
        val_strip = img[detector.col_y1:detector.col_y2 + 1,
                        detector.col_x1:detector.col_x2 + 1]
        if val_strip.size > 0:
            val_hsv = cv2.cvtColor(val_strip, cv2.COLOR_BGR2HSV)
            val_mask = cv2.inRange(
                val_hsv,
                np.array([BLUE_H_MIN, 40, 100]),
                np.array([BLUE_H_MAX, 255, 255])
            )
            val_ratio = np.sum(val_mask > 0) / max(val_mask.size, 1)
            bar_w = detector.col_x2 - detector.col_x1
            bar_h = detector.col_y2 - detector.col_y1
            if val_ratio < 0.70:
                print(f"[!] Bar rejected: blue ratio {val_ratio:.1%} too low "
                      f"(w={bar_w} h={bar_h} ratio={bar_h/max(bar_w,1):.1f})")
                detector.bar_found = False
                return

        # Convert to absolute screen coordinates
        detector.col_x1 += state_ctx['search_offset_x']
        detector.col_x2 += state_ctx['search_offset_x']
        detector.col_y1 += state_ctx['search_offset_y']
        detector.col_y2 += state_ctx['search_offset_y']
        detector.prog_x1 += state_ctx['search_offset_x']
        detector.prog_x2 += state_ctx['search_offset_x']

        bar_w = detector.col_x2 - detector.col_x1
        bar_h = detector.col_y2 - detector.col_y1
        print(f"[*] Minigame detected! Bar at x=[{detector.col_x1},{detector.col_x2}] "
              f"y=[{detector.col_y1},{detector.col_y2}] (w={bar_w} h={bar_h})")
        state_ctx['state'] = GameState.MINIGAME
        state_ctx['state_start'] = now
        state_ctx['max_blue_seen'] = 0.0
        # Start with space released, let box fall to bottom
        controller = state_ctx['controller']
        controller.reset()
        if controller.space_held:
            pydirectinput.keyUp('space')
    else:
        if debug:
            vis = img.copy()
            cv2.putText(vis, f"Looking for bar... ({now - state_ctx['state_start']:.0f}s)",
                        (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            show = cv2.resize(vis, (600, 500))
            cv2.imshow('Fishing Bot', show)
            if not state_ctx['topmost_set']:
                _setup_topmost_window('Fishing Bot')
                state_ctx['topmost_set'] = True
            if cv2.waitKey(1) & 0xFF == ord('q'):
                state_ctx['running'] = False
                return
        if reel_only:
            time.sleep(0.1)
        else:
            time.sleep(CAST_WAIT_POLL)


def _check_blue_bar_gone(state_ctx, col_strip, blue_ratio, catch_allowed):
    """Check if the blue bar has disappeared (fish caught or false detection)."""
    detector = state_ctx['detector']
    controller = state_ctx['controller']
    now = state_ctx['now']

    state_ctx['max_blue_seen'] = max(state_ctx['max_blue_seen'], blue_ratio)
    if blue_ratio < 0.10:
        state_ctx['low_blue_count'] += 1
        if state_ctx['low_blue_count'] == 1:
            diag_dir = os.path.join(os.path.dirname(__file__), 'diag_blue_gone')
            os.makedirs(diag_dir, exist_ok=True)
            cv2.imwrite(os.path.join(diag_dir, 'first_low.png'), state_ctx['img'])
            cv2.imwrite(os.path.join(diag_dir, 'first_low_strip.png'), col_strip)
            print(f"[!] First low-blue frame: ratio={blue_ratio:.1%} "
                  f"strip={col_strip.shape} region={state_ctx['region']}")
    else:
        state_ctx['low_blue_count'] = 0

    LOW_BLUE_THRESHOLD = 30
    if state_ctx['low_blue_count'] >= LOW_BLUE_THRESHOLD and catch_allowed:
        if state_ctx['max_blue_seen'] < 0.70:
            print(f"[!] False bar: blue never exceeded {state_ctx['max_blue_seen']:.1%} "
                  f"(need 70%). Returning to WAITING.")
            detector.bar_found = False
            state_ctx['state'] = GameState.WAITING
            state_ctx['state_start'] = now
            if controller.space_held:
                pydirectinput.keyUp('space')
                controller.space_held = False
            state_ctx['low_blue_count'] = 0
            return True
        print(f"[*] Blue bar gone ({state_ctx['low_blue_count']} frames, ratio={blue_ratio:.1%}). Fish caught!")
        diag_dir = os.path.join(os.path.dirname(__file__), 'diag_blue_gone')
        os.makedirs(diag_dir, exist_ok=True)
        cv2.imwrite(os.path.join(diag_dir, 'capture.png'), state_ctx['img'])
        cv2.imwrite(os.path.join(diag_dir, 'col_strip.png'), col_strip)
        print(f"[!] Diagnostic images saved to {diag_dir}/ "
              f"(capture={state_ctx['img'].shape}, strip={col_strip.shape}, "
              f"region={state_ctx['region']})")
        state_ctx['state'] = GameState.CAUGHT
        state_ctx['state_start'] = now
        if controller.space_held:
            pydirectinput.keyUp('space')
            controller.space_held = False
        state_ctx['catches'] += 1
        state_ctx['low_blue_count'] = 0
        return True
    return False


def _handle_minigame(state_ctx):
    """Handle MINIGAME state: control loop for keeping fish in box."""
    now = state_ctx['now']
    detector = state_ctx['detector']
    capture = state_ctx['capture']
    controller = state_ctx['controller']
    debug = state_ctx['debug']

    loop_start = time.perf_counter()
    minigame_elapsed = now - state_ctx['state_start']
    catch_allowed = minigame_elapsed >= MINIGAME_GRACE

    # Capture bar region
    try:
        img, region = capture.capture_bar_region(detector)
    except Exception as e:
        traceback.print_exc()
        print(f"[!] Capture failed: {type(e).__name__}: {e}")
        print(f"[!] Detector coords: col=[{detector.col_x1},{detector.col_x2}] "
              f"y=[{detector.col_y1},{detector.col_y2}] prog_x2={detector.prog_x2}")
        detector.bar_found = False
        state_ctx['state'] = GameState.WAITING
        if controller.space_held:
            pydirectinput.keyUp('space')
            controller.space_held = False
        return

    state_ctx['img'] = img
    state_ctx['region'] = region

    # Adjust detector coordinates relative to capture region
    det = BarDetector()
    det.col_x1 = detector.col_x1 - region['left']
    det.col_x2 = detector.col_x2 - region['left']
    det.col_y1 = detector.col_y1 - region['top']
    det.col_y2 = detector.col_y2 - region['top']
    det.prog_x1 = detector.prog_x1 - region['left']
    det.prog_x2 = detector.prog_x2 - region['left']
    det.bar_found = True

    # Check if blue bar is still present
    sy1 = max(0, min(det.col_y1, img.shape[0]))
    sy2 = max(0, min(det.col_y2 + 1, img.shape[0]))
    sx1 = max(0, min(det.col_x1, img.shape[1]))
    sx2 = max(0, min(det.col_x2 + 1, img.shape[1]))
    col_strip = img[sy1:sy2, sx1:sx2]
    if col_strip.size > 0:
        col_hsv = cv2.cvtColor(col_strip, cv2.COLOR_BGR2HSV)
        bright_blue_mask = cv2.inRange(
            col_hsv,
            np.array([BLUE_H_MIN, 40, 100]),
            np.array([BLUE_H_MAX, 255, 255])
        )
        blue_ratio = np.sum(bright_blue_mask > 0) / max(bright_blue_mask.size, 1)
        if _check_blue_bar_gone(state_ctx, col_strip, blue_ratio, catch_allowed):
            return
    else:
        state_ctx['low_blue_count'] += 1

    det.fish_y_history = detector.fish_y_history
    det.fish_y = detector.fish_y
    det.box_top = detector.box_top
    det.box_bottom = detector.box_bottom
    det.box_center = detector.box_center

    result = det.detect_elements(img)

    if result is None:
        return

    # Copy detection results back
    detector.fish_y = det.fish_y
    detector.box_top = det.box_top
    detector.box_bottom = det.box_bottom
    detector.box_center = det.box_center
    detector.progress = det.progress
    detector.fish_velocity = det.fish_velocity
    detector.fish_y_history = det.fish_y_history

    state_ctx['minigame_frames'] += 1
    if now - state_ctx['last_status_log'] >= 2.0:
        state_ctx['last_status_log'] = now
        err = detector.fish_y - detector.box_center
        print(f"  [status] fish={detector.fish_y:.2f} box={detector.box_center:.2f} "
              f"err={err:+.2f} duty={controller._duty:.0%} prog={detector.progress:.0%} "
              f"frames={state_ctx['minigame_frames']}", flush=True)

    # Run controller
    was_held = controller.space_held
    should_hold = controller.update(detector)
    if should_hold != was_held:
        if should_hold:
            pydirectinput.keyDown('space')
        else:
            pydirectinput.keyUp('space')

    # Debug visualization
    if debug:
        vis = det.draw_debug(img)
        state_text = f"MINIGAME | Fish={detector.fish_y:.2f} Box={detector.box_center:.2f} Prog={detector.progress:.0%}"
        cv2.putText(vis, state_text, (5, 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1)
        duty_pct = int(controller._duty * 100)
        action = f"{'HOLD' if controller.space_held else 'off '} duty={duty_pct}%"
        color = (0, 255, 255) if controller.space_held else (128, 128, 128)
        cv2.putText(vis, action, (5, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)
        scale = max(1, 400 // max(vis.shape[1], 1))
        if scale > 1:
            show = cv2.resize(vis, (vis.shape[1] * scale, vis.shape[0] * scale),
                              interpolation=cv2.INTER_NEAREST)
        else:
            show = vis
        cv2.imshow('Fishing Bot', show)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            state_ctx['running'] = False

    # Rate limit
    elapsed = time.perf_counter() - loop_start
    control_interval = 1.0 / CONTROL_HZ
    sleep_time = control_interval - elapsed
    if sleep_time > 0:
        time.sleep(sleep_time)


def _handle_caught(state_ctx):
    """Handle CAUGHT state: log catch and prepare for next cast."""
    print(f"[*] Total catches: {state_ctx['catches']}. Casting again in {CAST_DELAY}s...")
    time.sleep(CAST_DELAY)
    state_ctx['state'] = GameState.IDLE


# Map state names to handlers
_STATE_HANDLERS = {
    GameState.IDLE: _handle_idle,
    GameState.WAITING: _handle_waiting,
    GameState.MINIGAME: _handle_minigame,
    GameState.CAUGHT: _handle_caught,
}


def run_automation(debug=False, reel_only=False):
    """Main automation loop."""
    global pydirectinput
    import pydirectinput as pdi
    pydirectinput = pdi
    pydirectinput.FAILSAFE = True

    # Find FiveM game window
    game_win = find_game_window('fivem')
    if game_win:
        print(f"[*] Found game window: {game_win['title'][:60].encode('ascii', 'replace').decode()}")
        try:
            user32 = ctypes.windll.user32
            hwnd = game_win['hwnd']
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
            print("[*] Game window focused. Starting in 1s...")
            time.sleep(1.0)
        except Exception:
            print("[!] Could not focus window. Starting in 3s...")
            time.sleep(3.0)
    else:
        print("[!] FiveM window not found, using primary monitor. Starting in 3s...")
        time.sleep(3.0)

    capture = ScreenCapture(game_window=game_win)
    detector = BarDetector()
    controller = FishingController()

    # Shared state context for handler functions
    state_ctx = {
        'state': GameState.IDLE,
        'state_start': time.perf_counter(),
        'catches': 0,
        'running': True,
        'debug': debug,
        'reel_only': reel_only,
        'detector': detector,
        'controller': controller,
        'capture': capture,
        'topmost_set': False,
        'minigame_frames': 0,
        'last_status_log': 0.0,
        'low_blue_count': 0,
        'max_blue_seen': 0.0,
        'search_offset_x': 0,
        'search_offset_y': 0,
        'now': 0.0,
        'img': None,
        'region': None,
    }

    # Graceful shutdown
    def signal_handler(sig, frame):
        print("\n[!] Shutting down...")
        state_ctx['running'] = False
        if controller.space_held:
            pydirectinput.keyUp('space')
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)

    print("[*] Fishing automation started")
    if reel_only:
        print("[*] Reel-only mode: searching for minigame bar...")
    print("[*] Move mouse to top-left corner to abort (FAILSAFE)")
    if debug:
        print("[*] Debug visualization enabled - press 'q' in window to quit")
        cv2.namedWindow('Fishing Bot', cv2.WINDOW_AUTOSIZE)
        _setup_topmost_window('Fishing Bot')

    while state_ctx['running']:
        state_ctx['now'] = time.perf_counter()
        handler = _STATE_HANDLERS.get(state_ctx['state'])
        if handler:
            handler(state_ctx)

    # Cleanup
    if controller.space_held:
        pydirectinput.keyUp('space')
    if debug:
        cv2.destroyAllWindows()
    print(f"\n[*] Done. Total catches: {state_ctx['catches']}")


# ─── Test Mode ──────────────────────────────────────────────────────────

def run_test(image_path, debug=True):
    """Test detection on a single image file or directory of frames."""
    import glob

    detector = BarDetector()

    if os.path.isdir(image_path):
        frames = sorted(glob.glob(os.path.join(image_path, "*.png")))
        if not frames:
            print(f"No PNG files found in {image_path}")
            return
        print(f"Found {len(frames)} frames. Press any key to advance, 'q' to quit.")

        for fpath in frames:
            img = cv2.imread(fpath)
            if img is None:
                continue

            if not detector.bar_found:
                h, w = img.shape[:2]
                cx, cy = w // 2, h // 2
                mx = int(w * SEARCH_MARGIN_X_FRAC)
                my = int(h * SEARCH_MARGIN_Y_FRAC)
                roi = img[cy - my:cy + my,
                          cx - mx:cx + mx]
                if detector.find_bar(roi):
                    detector.col_x1 += cx - mx
                    detector.col_x2 += cx - mx
                    detector.col_y1 += cy - my
                    detector.col_y2 += cy - my
                    detector.prog_x1 += cx - mx
                    detector.prog_x2 += cx - mx
                    print(f"Bar found at x=[{detector.col_x1},{detector.col_x2}] y=[{detector.col_y1},{detector.col_y2}]")

            if detector.bar_found:
                result = detector.detect_elements(img)
                if result:
                    fname = os.path.basename(fpath)
                    print(f"{fname}: fish={result['fish_y']:.3f} box=[{result['box_top']:.3f},{result['box_bottom']:.3f}] prog={result['progress']:.1%} vel={result['fish_velocity']:+.3f}")

                if debug:
                    pad = 30
                    crop = img[
                        max(0, detector.col_y1 - pad):min(img.shape[0], detector.col_y2 + pad),
                        max(0, detector.col_x1 - pad):min(img.shape[1], detector.prog_x2 + pad + 40),
                    ]
                    vis_det = BarDetector()
                    vis_det.col_x1 = pad
                    vis_det.col_x2 = pad + (detector.col_x2 - detector.col_x1)
                    vis_det.col_y1 = pad
                    vis_det.col_y2 = pad + (detector.col_y2 - detector.col_y1)
                    vis_det.prog_x1 = vis_det.col_x2 + 1
                    vis_det.prog_x2 = vis_det.col_x2 + 20
                    vis_det.bar_found = True
                    vis_det.fish_y = detector.fish_y
                    vis_det.box_top = detector.box_top
                    vis_det.box_bottom = detector.box_bottom
                    vis_det.box_center = detector.box_center
                    vis_det.progress = detector.progress
                    vis_det.fish_velocity = detector.fish_velocity

                    vis = vis_det.draw_debug(crop)
                    scale = max(1, 400 // max(vis.shape[1], 1))
                    show = cv2.resize(vis, (vis.shape[1] * scale, vis.shape[0] * scale),
                                      interpolation=cv2.INTER_NEAREST)
                    cv2.imshow('Detection Test', show)
                    key = cv2.waitKey(0) & 0xFF
                    if key == ord('q'):
                        break
            else:
                if debug:
                    thumb = cv2.resize(img, (960, 600))
                    cv2.putText(thumb, "Bar not found", (20, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    cv2.imshow('Detection Test', thumb)
                    key = cv2.waitKey(0) & 0xFF
                    if key == ord('q'):
                        break

        cv2.destroyAllWindows()

    else:
        # Single image
        img = cv2.imread(image_path)
        if img is None:
            print(f"Could not load {image_path}")
            return

        h, w = img.shape[:2]
        print(f"Image: {w}x{h}")

        cx, cy = w // 2, h // 2
        mx = int(w * SEARCH_MARGIN_X_FRAC)
        my = int(h * SEARCH_MARGIN_Y_FRAC)
        roi = img[cy - my:cy + my,
                  cx - mx:cx + mx]
        if detector.find_bar(roi):
            detector.col_x1 += cx - mx
            detector.col_x2 += cx - mx
            detector.col_y1 += cy - my
            detector.col_y2 += cy - my
            detector.prog_x1 += cx - mx
            detector.prog_x2 += cx - mx
            print(f"Bar found at x=[{detector.col_x1},{detector.col_x2}] y=[{detector.col_y1},{detector.col_y2}]")

            result = detector.detect_elements(img)
            if result:
                print(f"  Fish Y: {result['fish_y']:.3f} (0=top, 1=bottom)")
                print(f"  Box: top={result['box_top']:.3f} bottom={result['box_bottom']:.3f} center={result['box_center']:.3f}")
                print(f"  Progress: {result['progress']:.1%}")

            if debug:
                vis = detector.draw_debug(img)
                pad = 50
                crop = vis[
                    max(0, detector.col_y1 - pad):min(h, detector.col_y2 + pad),
                    max(0, detector.col_x1 - pad):min(w, detector.prog_x2 + pad + 60),
                ]
                scale = max(1, 400 // max(crop.shape[1], 1))
                show = cv2.resize(crop, (crop.shape[1] * scale, crop.shape[0] * scale),
                                  interpolation=cv2.INTER_NEAREST)
                cv2.imshow('Detection Test', show)
                cv2.waitKey(0)
                cv2.destroyAllWindows()
        else:
            print("Bar not found in image")
            if debug:
                thumb = cv2.resize(img, (960, 600))
                cv2.putText(thumb, "Bar not found", (20, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                cv2.imshow('Detection Test', thumb)
                cv2.waitKey(0)
                cv2.destroyAllWindows()
