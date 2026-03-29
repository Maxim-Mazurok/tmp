"""
GTA RP Fishing Minigame Automation - Phases 1 & 2
Phase 1: Screen capture + detection (blue column, white box, fishscale, progress bar)
Phase 2: Binary controller + state machine (cast → minigame → catch → repeat)

Game mechanics:
  1. Press "2" to cast the line.
  2. Wait ~2 minutes for a fish to bite.
  3. Minigame starts: a blue column appears with a black fishscale icon moving
     up/down at constant linear speed, changing direction randomly.
  4. A semi-transparent white box (player-controlled) overlays the column.
     Hold space → box accelerates up; release → box falls with gravity.
  5. An orange/red progress bar next to the column fills while the fishscale
     is inside the white box, and drains when outside.
  6. Fill the progress bar to 100% to catch the fish. There is no time limit
     and no lose condition — if the progress bar drains to 0% you just keep
     going. The only outcome is eventually catching the fish.
  7. After catching, press "2" again to cast and repeat.

Note: Game FPS may fluctuate depending on system load, so the control loop
uses wall-clock timing rather than frame counting.

Usage:
  python fish.py              # Run automation (requires admin for input injection)
  python fish.py --debug      # Run with debug visualization window
  python fish.py --test FILE  # Test detection on a single image file
"""

import sys
import time
import signal
import argparse
import numpy as np
import cv2
import mss

# Only import pydirectinput when actually controlling (not in test mode)
pydirectinput = None

# ─── Configuration ──────────────────────────────────────────────────────

# Screen resolution (used for initial bar search region)
SCREEN_W = 3840
SCREEN_H = 2400

# Search region for finding the blue column (center of screen)
SEARCH_MARGIN_X = 600  # pixels from center
SEARCH_MARGIN_Y = 500

# HSV thresholds for blue column detection
BLUE_H_MIN, BLUE_H_MAX = 85, 110
BLUE_S_MIN = 65
BLUE_V_MIN = 75

# White box detection: saturation drops below this threshold
WHITE_BOX_SAT_THRESHOLD = 55

# Fishscale detection: brightness drop from local average
FISH_BRIGHTNESS_DROP = 12  # pixels darker than row average to count
FISH_MIN_CLUSTER_SIZE = 3   # minimum rows to form a fishscale cluster

# Progress bar: red/orange fill detection
PROGRESS_H_MIN, PROGRESS_H_MAX = 0, 12
PROGRESS_S_MIN = 100
PROGRESS_V_MIN = 80

# Controller parameters
HYSTERESIS = 0.08  # normalized band (fraction of bar height)

# Game loop timing
CAST_DELAY = 3.0       # seconds to wait after catch before recasting
CAST_WAIT_POLL = 2.0   # seconds between polls while waiting for bite
CONTROL_HZ = 30        # control loop frequency during minigame

# ─── Detection ──────────────────────────────────────────────────────────

class BarDetector:
    """Detects and tracks the fishing minigame bar elements."""

    def __init__(self):
        self.bar_found = False
        # Absolute pixel coordinates of the blue column
        self.col_x1 = 0
        self.col_x2 = 0
        self.col_y1 = 0
        self.col_y2 = 0
        # Progress bar x range (to the right of blue column)
        self.prog_x1 = 0
        self.prog_x2 = 0
        # Capture region for mss (during minigame, capture only bar area)
        self.capture_region = None
        # Last detected positions (normalized 0.0 = top, 1.0 = bottom)
        self.fish_y = 0.5
        self.box_top = 0.0
        self.box_bottom = 0.0
        self.box_center = 0.5
        self.progress = 0.0  # 0.0 to 1.0
        # Velocity tracking
        self.fish_y_history = []  # list of (time, y) tuples
        self.fish_velocity = 0.0  # positive = moving down

    def find_bar(self, img):
        """
        Search for the blue column in a screen capture.
        img: BGR numpy array (can be full screen or search region).
        Returns True if bar found and coordinates updated.
        """
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        blue_mask = cv2.inRange(
            hsv,
            np.array([BLUE_H_MIN, BLUE_S_MIN, BLUE_V_MIN]),
            np.array([BLUE_H_MAX, 255, 255])
        )

        # Find columns with significant blue pixel count (vertical strip)
        col_sums = np.sum(blue_mask > 0, axis=0)
        # The blue column should have many consecutive blue pixels vertically
        # Expect at least 100 blue pixels in a column (out of ~330 height)
        blue_cols = np.where(col_sums > 80)[0]
        if len(blue_cols) < 5:
            return False

        # Find the main continuous group of blue columns
        diffs = np.diff(blue_cols)
        splits = np.where(diffs > 5)[0]
        groups = np.split(blue_cols, splits + 1)
        # Pick the largest group
        main_group = max(groups, key=len)
        if len(main_group) < 10:
            return False

        x1 = main_group[0]
        x2 = main_group[-1]

        # Find vertical extent within those columns
        # Use hue-based detection (H=80-115, S>40) to include the darker bottom
        # portion of the bar (3D tube effect) that the brightness-based blue_mask misses
        col_strip_hsv = hsv[:, x1:x2 + 1]
        hue_mask = (
            (col_strip_hsv[:, :, 0] >= 80) &
            (col_strip_hsv[:, :, 0] <= 115) &
            (col_strip_hsv[:, :, 1] > 40)
        ).astype(np.uint8)
        row_sums = np.sum(hue_mask, axis=1)
        bar_rows = np.where(row_sums > (x2 - x1) * 0.3)[0]
        if len(bar_rows) < 50:
            return False

        y1 = bar_rows[0]
        y2 = bar_rows[-1]

        self.col_x1 = x1
        self.col_x2 = x2
        self.col_y1 = y1
        self.col_y2 = y2

        # Progress bar is immediately to the right of the blue column
        self.prog_x1 = x2 + 1
        self.prog_x2 = x2 + 20  # approximately 16-20px wide

        self.bar_found = True
        return True

    def detect_elements(self, img):
        """
        Detect fishscale, white box, and progress from a cropped image
        that contains the bar area.
        img: BGR numpy array of the bar region.
        Returns dict with detection results.
        """
        h, w = img.shape[:2]

        # Extract just the blue column
        cx1 = max(0, self.col_x1)
        cx2 = min(w, self.col_x2 + 1)
        cy1 = max(0, self.col_y1)
        cy2 = min(h, self.col_y2 + 1)

        if cx2 <= cx1 or cy2 <= cy1:
            return None

        col_img = img[cy1:cy2, cx1:cx2]
        col_h, col_w = col_img.shape[:2]
        if col_h < 20 or col_w < 3:
            return None

        hsv = cv2.cvtColor(col_img, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(col_img, cv2.COLOR_BGR2GRAY)

        # --- White box detection (low saturation rows) ---
        row_sat = np.mean(hsv[:, :, 1].astype(float), axis=1)
        white_rows = np.where(row_sat < WHITE_BOX_SAT_THRESHOLD)[0]

        if len(white_rows) >= 3:
            # Find the main continuous cluster
            diffs = np.diff(white_rows)
            splits = np.where(diffs > 3)[0]
            clusters = np.split(white_rows, splits + 1)
            main_cluster = max(clusters, key=len)
            if len(main_cluster) >= 3:
                self.box_top = main_cluster[0] / col_h
                self.box_bottom = main_cluster[-1] / col_h
                self.box_center = (self.box_top + self.box_bottom) / 2
            else:
                # No white box detected - might be at very edge
                pass
        else:
            # White box might not be visible (off-screen or not present)
            pass

        # --- Fishscale detection (brightness dip + high saturation) ---
        # The fishscale is a small dark icon with HIGH saturation (it's dark blue/black
        # on blue). The white box edges also create brightness dips but have LOW
        # saturation. We use both signals to distinguish them.
        row_brightness = np.mean(gray.astype(float), axis=1)
        row_sat = np.mean(hsv[:, :, 1].astype(float), axis=1)

        # Build a mask of rows that belong to the white box (low saturation)
        white_box_rows = set()
        if len(white_rows) >= 3:
            # Expand white box region by a few pixels to exclude transition edges
            wb_expand = 5
            for wr in white_rows:
                for offset in range(-wb_expand, wb_expand + 1):
                    white_box_rows.add(wr + offset)

        # Smooth brightness to reduce noise
        kernel_size = 5
        if len(row_brightness) > kernel_size:
            smoothed = np.convolve(row_brightness, np.ones(kernel_size) / kernel_size, mode='same')
        else:
            smoothed = row_brightness

        # Use a larger window to compute local average, then find dips
        window = min(41, col_h // 3)
        if window % 2 == 0:
            window += 1
        from scipy.ndimage import uniform_filter1d
        local_avg = uniform_filter1d(smoothed, size=window)
        dips = smoothed - local_avg

        # Find rows significantly darker than local average
        dark_rows = np.where(dips < -FISH_BRIGHTNESS_DROP)[0]
        # Filter out: top/bottom edges, white box rows, and low-saturation rows
        margin = max(8, int(col_h * 0.05))
        dark_rows = dark_rows[
            (dark_rows > margin) &
            (dark_rows < col_h - margin)
        ]
        # Exclude white box region and require high saturation
        dark_rows = np.array([
            r for r in dark_rows
            if r not in white_box_rows and row_sat[r] > 70
        ])

        if len(dark_rows) >= FISH_MIN_CLUSTER_SIZE:
            # Find clusters of dark rows
            dr_diffs = np.diff(dark_rows)
            dr_splits = np.where(dr_diffs > 5)[0]
            dr_clusters = np.split(dark_rows, dr_splits + 1)
            # Pick the cluster with the deepest dip
            best_cluster = None
            best_dip = 0
            for c in dr_clusters:
                if len(c) >= FISH_MIN_CLUSTER_SIZE:
                    cluster_dip = -np.min(dips[c])
                    if cluster_dip > best_dip:
                        best_dip = cluster_dip
                        best_cluster = c
            if best_cluster is not None:
                fish_center = (best_cluster[0] + best_cluster[-1]) / 2
                new_fish_y = fish_center / col_h

                # Update velocity tracking
                now = time.perf_counter()
                self.fish_y_history.append((now, new_fish_y))
                # Keep last 10 samples
                self.fish_y_history = self.fish_y_history[-10:]
                if len(self.fish_y_history) >= 2:
                    dt = self.fish_y_history[-1][0] - self.fish_y_history[-2][0]
                    if dt > 0:
                        dy = self.fish_y_history[-1][1] - self.fish_y_history[-2][1]
                        self.fish_velocity = dy / dt

                self.fish_y = new_fish_y

        # --- Progress bar detection ---
        px1 = max(0, self.prog_x1)
        px2 = min(w, self.prog_x2 + 1)
        if px2 > px1:
            prog_strip = img[cy1:cy2, px1:px2]
            prog_hsv = cv2.cvtColor(prog_strip, cv2.COLOR_BGR2HSV)
            red_mask = cv2.inRange(
                prog_hsv,
                np.array([PROGRESS_H_MIN, PROGRESS_S_MIN, PROGRESS_V_MIN]),
                np.array([PROGRESS_H_MAX, 255, 255])
            )
            # Progress fills from bottom up
            row_fill = np.sum(red_mask > 0, axis=1)
            filled_rows = np.sum(row_fill > 1)
            self.progress = filled_rows / max(col_h, 1)

        return {
            'fish_y': self.fish_y,
            'box_top': self.box_top,
            'box_bottom': self.box_bottom,
            'box_center': self.box_center,
            'progress': self.progress,
            'fish_velocity': self.fish_velocity,
        }

    def draw_debug(self, img):
        """Draw detection overlays on the image for visualization."""
        vis = img.copy()
        if not self.bar_found:
            return vis

        cy1, cy2 = self.col_y1, self.col_y2
        cx1, cx2 = self.col_x1, self.col_x2
        col_h = cy2 - cy1

        # Draw blue column bounds (green rectangle)
        cv2.rectangle(vis, (cx1, cy1), (cx2, cy2), (0, 255, 0), 1)

        # Draw white box (white rectangle)
        box_y1 = cy1 + int(self.box_top * col_h)
        box_y2 = cy1 + int(self.box_bottom * col_h)
        cv2.rectangle(vis, (cx1, box_y1), (cx2, box_y2), (255, 255, 255), 2)

        # Draw fishscale position (red horizontal line)
        fish_abs_y = cy1 + int(self.fish_y * col_h)
        cv2.line(vis, (cx1 - 5, fish_abs_y), (cx2 + 5, fish_abs_y), (0, 0, 255), 2)

        # Draw progress bar bounds
        px1, px2 = self.prog_x1, self.prog_x2
        cv2.rectangle(vis, (px1, cy1), (px2, cy2), (0, 128, 255), 1)

        # Progress fill level
        prog_y = cy2 - int(self.progress * col_h)
        cv2.line(vis, (px1, prog_y), (px2, prog_y), (0, 255, 255), 1)

        # Text overlay
        info_x = cx2 + 25
        cv2.putText(vis, f"Fish: {self.fish_y:.2f}", (info_x, cy1 + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
        cv2.putText(vis, f"Box: {self.box_top:.2f}-{self.box_bottom:.2f}", (info_x, cy1 + 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        cv2.putText(vis, f"Progress: {self.progress:.0%}", (info_x, cy1 + 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        cv2.putText(vis, f"Vel: {self.fish_velocity:+.3f}", (info_x, cy1 + 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 128, 255), 1)

        return vis


# ─── Screen Capture ─────────────────────────────────────────────────────

class ScreenCapture:
    """Fast screen capture using mss."""

    def __init__(self):
        self.sct = mss.mss()
        self._monitor = self.sct.monitors[1]  # Primary monitor

    def capture_search_region(self):
        """Capture center region for initial bar search."""
        cx = self._monitor['width'] // 2
        cy = self._monitor['height'] // 2
        region = {
            'left': cx - SEARCH_MARGIN_X,
            'top': cy - SEARCH_MARGIN_Y,
            'width': SEARCH_MARGIN_X * 2,
            'height': SEARCH_MARGIN_Y * 2,
        }
        screenshot = self.sct.grab(region)
        img = np.array(screenshot)[:, :, :3]  # BGRA → BGR
        return img, region

    def capture_bar_region(self, detector, padding=15):
        """Capture just the bar area for fast updates."""
        region = {
            'left': self._monitor['left'] + detector.col_x1 - padding,
            'top': self._monitor['top'] + detector.col_y1 - padding,
            'width': (detector.prog_x2 - detector.col_x1) + padding * 2 + 30,
            'height': (detector.col_y2 - detector.col_y1) + padding * 2,
        }
        screenshot = self.sct.grab(region)
        img = np.array(screenshot)[:, :, :3]
        return img, region


# ─── Controller ─────────────────────────────────────────────────────────

class FishingController:
    """Binary controller: press space when fish is above box, release when below."""

    def __init__(self):
        self.space_held = False

    def update(self, detector):
        """
        Decide whether to hold or release space.
        Returns: True if space should be held, False if released.
        """
        fish = detector.fish_y
        box_center = detector.box_center

        # Hysteresis: only change state if fish is clearly above/below
        if self.space_held:
            # Currently holding space (box moving up)
            # Release if fish is below box center by hysteresis margin
            # Remember: 0.0 = top, 1.0 = bottom
            # Fish below box → fish_y > box_center → need to go down → release
            if fish > box_center + HYSTERESIS:
                self.space_held = False
        else:
            # Currently released (box falling)
            # Press if fish is above box center by hysteresis margin
            # Fish above box → fish_y < box_center → need to go up → press
            if fish < box_center - HYSTERESIS:
                self.space_held = True

        return self.space_held

    def reset(self):
        self.space_held = False


# ─── State Machine ──────────────────────────────────────────────────────

class GameState:
    IDLE = 'IDLE'
    CASTING = 'CASTING'
    WAITING = 'WAITING'
    MINIGAME = 'MINIGAME'
    CAUGHT = 'CAUGHT'


def run_automation(debug=False):
    """Main automation loop."""
    global pydirectinput
    import pydirectinput as pdi
    pydirectinput = pdi
    pydirectinput.FAILSAFE = True

    capture = ScreenCapture()
    detector = BarDetector()
    controller = FishingController()

    state = GameState.IDLE
    state_start = time.perf_counter()
    catches = 0

    # Graceful shutdown
    running = True
    def signal_handler(sig, frame):
        nonlocal running
        print("\n[!] Shutting down...")
        running = False
        # Release space if held
        if controller.space_held:
            pydirectinput.keyUp('space')
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)

    print("[*] Fishing automation started")
    print("[*] Move mouse to top-left corner to abort (FAILSAFE)")
    if debug:
        print("[*] Debug visualization enabled - press 'q' in window to quit")

    control_interval = 1.0 / CONTROL_HZ

    # Convert search region offset for absolute coordinate mapping
    search_offset_x = 0
    search_offset_y = 0

    while running:
        now = time.perf_counter()

        if state == GameState.IDLE:
            print(f"\n[{catches}] Casting...")
            pydirectinput.press('2')
            state = GameState.WAITING
            state_start = now
            detector.bar_found = False
            controller.reset()
            time.sleep(1.0)

        elif state == GameState.WAITING:
            # Poll for the minigame bar to appear
            img, region = capture.capture_search_region()
            search_offset_x = region['left']
            search_offset_y = region['top']

            if detector.find_bar(img):
                # Convert to absolute screen coordinates
                detector.col_x1 += search_offset_x
                detector.col_x2 += search_offset_x
                detector.col_y1 += search_offset_y
                detector.col_y2 += search_offset_y
                detector.prog_x1 += search_offset_x
                detector.prog_x2 += search_offset_x

                print(f"[*] Minigame detected! Bar at x=[{detector.col_x1},{detector.col_x2}] y=[{detector.col_y1},{detector.col_y2}]")
                state = GameState.MINIGAME
                state_start = now
                # Start with space released, let box fall to bottom
                controller.reset()
                if controller.space_held:
                    pydirectinput.keyUp('space')
            else:
                if debug:
                    # Show search region
                    vis = img.copy()
                    cv2.putText(vis, f"Waiting for bite... ({now - state_start:.0f}s)",
                                (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    show = cv2.resize(vis, (600, 500))
                    cv2.imshow('Fishing Bot', show)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        running = False
                        break
                time.sleep(CAST_WAIT_POLL)

        elif state == GameState.MINIGAME:
            loop_start = time.perf_counter()

            # Capture bar region
            try:
                img, region = capture.capture_bar_region(detector)
            except Exception:
                # Bar might have moved or disappeared
                print("[!] Capture failed, re-searching...")
                detector.bar_found = False
                state = GameState.WAITING
                if controller.space_held:
                    pydirectinput.keyUp('space')
                    controller.space_held = False
                continue

            # Adjust detector coordinates relative to capture region
            det = BarDetector()
            det.col_x1 = detector.col_x1 - region['left']
            det.col_x2 = detector.col_x2 - region['left']
            det.col_y1 = detector.col_y1 - region['top']
            det.col_y2 = detector.col_y2 - region['top']
            det.prog_x1 = detector.prog_x1 - region['left']
            det.prog_x2 = detector.prog_x2 - region['left']
            det.bar_found = True
            det.fish_y_history = detector.fish_y_history
            det.fish_y = detector.fish_y
            det.box_top = detector.box_top
            det.box_bottom = detector.box_bottom
            det.box_center = detector.box_center

            result = det.detect_elements(img)

            if result is None:
                # Detection failed - bar might have disappeared (caught!)
                # Check if we were making good progress
                if detector.progress > 0.85:
                    print(f"[*] Fish caught! (progress was {detector.progress:.0%})")
                    state = GameState.CAUGHT
                    state_start = now
                    if controller.space_held:
                        pydirectinput.keyUp('space')
                        controller.space_held = False
                    catches += 1
                    continue
                # Otherwise might be a detection glitch, retry
                continue

            # Copy detection results back
            detector.fish_y = det.fish_y
            detector.box_top = det.box_top
            detector.box_bottom = det.box_bottom
            detector.box_center = det.box_center
            detector.progress = det.progress
            detector.fish_velocity = det.fish_velocity
            detector.fish_y_history = det.fish_y_history

            # Check if progress bar is full
            if detector.progress > 0.92:
                print(f"[*] Fish caught! (progress {detector.progress:.0%})")
                state = GameState.CAUGHT
                state_start = now
                if controller.space_held:
                    pydirectinput.keyUp('space')
                    controller.space_held = False
                catches += 1
                continue

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
                action = "SPACE DOWN" if controller.space_held else "space up"
                cv2.putText(vis, action, (5, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                            (0, 255, 255) if controller.space_held else (128, 128, 128), 1)
                # Scale up for visibility
                scale = max(1, 400 // max(vis.shape[1], 1))
                if scale > 1:
                    show = cv2.resize(vis, (vis.shape[1] * scale, vis.shape[0] * scale),
                                      interpolation=cv2.INTER_NEAREST)
                else:
                    show = vis
                cv2.imshow('Fishing Bot', show)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    running = False
                    break

            # Rate limit
            elapsed = time.perf_counter() - loop_start
            sleep_time = control_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        elif state == GameState.CAUGHT:
            print(f"[*] Total catches: {catches}. Waiting {CAST_DELAY}s before next cast...")
            time.sleep(CAST_DELAY)
            state = GameState.IDLE

    # Cleanup
    if controller.space_held:
        pydirectinput.keyUp('space')
    if debug:
        cv2.destroyAllWindows()
    print(f"\n[*] Done. Total catches: {catches}")


# ─── Test Mode ──────────────────────────────────────────────────────────

def run_test(image_path, debug=True):
    """Test detection on a single image file or directory of frames."""
    import os
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
                # Search in center region
                h, w = img.shape[:2]
                cx, cy = w // 2, h // 2
                roi = img[cy - SEARCH_MARGIN_Y:cy + SEARCH_MARGIN_Y,
                          cx - SEARCH_MARGIN_X:cx + SEARCH_MARGIN_X]
                if detector.find_bar(roi):
                    detector.col_x1 += cx - SEARCH_MARGIN_X
                    detector.col_x2 += cx - SEARCH_MARGIN_X
                    detector.col_y1 += cy - SEARCH_MARGIN_Y
                    detector.col_y2 += cy - SEARCH_MARGIN_Y
                    detector.prog_x1 += cx - SEARCH_MARGIN_X
                    detector.prog_x2 += cx - SEARCH_MARGIN_X
                    print(f"Bar found at x=[{detector.col_x1},{detector.col_x2}] y=[{detector.col_y1},{detector.col_y2}]")

            if detector.bar_found:
                result = detector.detect_elements(img)
                if result:
                    fname = os.path.basename(fpath)
                    print(f"{fname}: fish={result['fish_y']:.3f} box=[{result['box_top']:.3f},{result['box_bottom']:.3f}] prog={result['progress']:.1%} vel={result['fish_velocity']:+.3f}")

                if debug:
                    # Draw on cropped region
                    pad = 30
                    crop = img[
                        max(0, detector.col_y1 - pad):min(img.shape[0], detector.col_y2 + pad),
                        max(0, detector.col_x1 - pad):min(img.shape[1], detector.prog_x2 + pad + 40),
                    ]
                    # Need to adjust detector coords for the crop
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
                    # Show frame overview
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

        # Search center region
        cx, cy = w // 2, h // 2
        roi = img[cy - SEARCH_MARGIN_Y:cy + SEARCH_MARGIN_Y,
                  cx - SEARCH_MARGIN_X:cx + SEARCH_MARGIN_X]
        if detector.find_bar(roi):
            detector.col_x1 += cx - SEARCH_MARGIN_X
            detector.col_x2 += cx - SEARCH_MARGIN_X
            detector.col_y1 += cy - SEARCH_MARGIN_Y
            detector.col_y2 += cy - SEARCH_MARGIN_Y
            detector.prog_x1 += cx - SEARCH_MARGIN_X
            detector.prog_x2 += cx - SEARCH_MARGIN_X
            print(f"Bar found at x=[{detector.col_x1},{detector.col_x2}] y=[{detector.col_y1},{detector.col_y2}]")

            result = detector.detect_elements(img)
            if result:
                print(f"  Fish Y: {result['fish_y']:.3f} (0=top, 1=bottom)")
                print(f"  Box: top={result['box_top']:.3f} bottom={result['box_bottom']:.3f} center={result['box_center']:.3f}")
                print(f"  Progress: {result['progress']:.1%}")

            if debug:
                vis = detector.draw_debug(img)
                # Crop to bar area with padding
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


# ─── Entry Point ────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='GTA RP Fishing Bot')
    parser.add_argument('--debug', action='store_true', help='Show debug visualization')
    parser.add_argument('--test', type=str, help='Test detection on image file or frame directory')
    args = parser.parse_args()

    if args.test:
        run_test(args.test, debug=True)
    else:
        run_automation(debug=args.debug)
