"""Automation loop and test mode for the fishing minigame."""

import json
import os
import sys
import time
import signal
import queue
import threading
import traceback
import ctypes
from collections import deque
from datetime import datetime
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
from projection_calibration import (
    PROJECTION_TIMING_WINDOW_FRAMES,
    resolve_projection_outcome,
    summarize_projection_outcomes,
)

# Only import pydirectinput when actually controlling (not in test mode)
pydirectinput = None
DEBUG_WINDOW_NAME = 'Fishing Bot'
DEBUG_TARGET_WIDTH = 1280
DEBUG_TARGET_HEIGHT = 900
DEBUG_FONT = cv2.FONT_HERSHEY_SIMPLEX
DEBUG_FONT_SCALE = 0.5
DEBUG_FONT_THICKNESS = 1
DEBUG_PADDING = 10
DEBUG_PANEL_MIN_WIDTH = 420
DEBUG_PREDICTION_FRAMES = (1, 2, 3, 5, 8)
LIVE_DEBUG_BUFFER_FRAMES = 120
LIVE_DEBUG_DUMP_FRAMES = 45
LIVE_DEBUG_OVERLAP_MARGIN = 0.03
LIVE_DEBUG_JUMP_THRESHOLD = 0.05
LIVE_DEBUG_DUMP_COOLDOWN = 45
PROJECTION_SUMMARY_WRITE_INTERVAL = 25
_FILE_WRITE_SENTINEL = object()


def _ensure_parent_dir(path):
    """Create the parent directory for a file path when needed."""
    parent_dir = os.path.dirname(path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)


def _append_text_line(path, line):
    """Append a single line of UTF-8 text to a file."""
    _ensure_parent_dir(path)
    with open(path, 'a', encoding='utf-8') as handle:
        handle.write(line)


def _write_json_file(path, payload, indent=2):
    """Write a JSON payload to disk."""
    _ensure_parent_dir(path)
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle, indent=indent)


def _write_image_file(path, image, params=None):
    """Write an image to disk and raise if OpenCV cannot persist it."""
    _ensure_parent_dir(path)
    if params is None:
        ok = cv2.imwrite(path, image)
    else:
        ok = cv2.imwrite(path, image, list(params))
    if not ok:
        raise IOError(f'Could not write image to {path}')


class _AsyncFileWriter:
    """Serialize disk writes on a background thread so the control loop never waits on I/O."""

    def __init__(self, worker_name='fish-disk-writer'):
        self._queue = queue.Queue()
        self._closed = False
        self._thread = threading.Thread(target=self._run, name=worker_name, daemon=True)
        self._thread.start()

    def submit(self, func, *args, **kwargs):
        """Queue a write task for background execution."""
        if self._closed:
            raise RuntimeError('Async file writer is closed')
        self._queue.put((func, args, kwargs))

    def append_line(self, path, line):
        """Queue a text append operation."""
        self.submit(_append_text_line, path, line)

    def write_json(self, path, payload, indent=2):
        """Queue a JSON file rewrite."""
        self.submit(_write_json_file, path, payload, indent)

    def write_image(self, path, image, params=None):
        """Queue an image write using a detached copy of the frame."""
        image_copy = image.copy()
        params_copy = None if params is None else list(params)
        self.submit(_write_image_file, path, image_copy, params_copy)

    def flush(self):
        """Block until all queued writes are finished."""
        self._queue.join()

    def close(self):
        """Flush queued writes and stop the worker thread."""
        if self._closed:
            return
        self.flush()
        self._closed = True
        self._queue.put((_FILE_WRITE_SENTINEL, (), {}))
        self._thread.join()

    def _run(self):
        """Process queued disk writes until shutdown."""
        while True:
            func, args, kwargs = self._queue.get()
            try:
                if func is _FILE_WRITE_SENTINEL:
                    return
                func(*args, **kwargs)
            except Exception as exc:
                print(f"[!] Async file write failed: {type(exc).__name__}: {exc}", file=sys.stderr)
                traceback.print_exc()
            finally:
                self._queue.task_done()


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


def _setup_debug_window(window_name):
    """Create a resizable debug window with enough room for telemetry."""
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, DEBUG_TARGET_WIDTH, DEBUG_TARGET_HEIGHT)


def _format_direction(velocity, threshold=0.02):
    """Convert velocity sign into a readable direction label."""
    if velocity > threshold:
        return 'down'
    if velocity < -threshold:
        return 'up'
    return 'steady'


def _format_direction_code(direction_code):
    """Convert a direction code (-1, 0, +1) to a readable label."""
    if direction_code > 0:
        return 'down'
    if direction_code < 0:
        return 'up'
    return 'steady'


def _predict_fish_positions(detector):
    """Predict fish positions for the next few control frames."""
    predictions = []
    velocity = getattr(detector, 'virtual_fish_velocity', detector.fish_velocity)
    for frames_ahead in DEBUG_PREDICTION_FRAMES:
        dt = frames_ahead / CONTROL_HZ
        predicted = detector.fish_y + velocity * dt
        predictions.append((frames_ahead, max(0.0, min(1.0, predicted))))
    return predictions


def _draw_prediction_markers(vis, detector, fish_predictions, box_predictions):
    """Draw future fish and white-box position estimates without overlap."""
    if not detector.bar_found:
        return vis

    cy1, cy2 = detector.col_y1, detector.col_y2
    cx1, cx2 = detector.col_x1, detector.col_x2
    col_h = max(cy2 - cy1, 1)

    for idx, (frames_ahead, predicted) in enumerate(fish_predictions):
        pred_y = cy1 + int(predicted * col_h)
        shade = max(80, 255 - idx * 30)
        color = (shade, 180, 255 - idx * 20)
        cv2.line(vis, (max(0, cx1 - 16), pred_y), (max(0, cx1 - 2), pred_y), color, 1)
        cv2.putText(vis, f'F+{frames_ahead}', (max(0, cx1 - 46), pred_y - 2),
                    DEBUG_FONT, 0.35, color, 1)

    for idx, (frames_ahead, predicted) in enumerate(box_predictions):
        pred_y = cy1 + int(predicted * col_h)
        shade = max(80, 255 - idx * 30)
        color = (255 - idx * 20, shade, shade)
        cv2.line(vis, (cx2 + 2, pred_y), (min(vis.shape[1] - 1, cx2 + 16), pred_y), color, 1)
        cv2.putText(vis, f'B+{frames_ahead}', (min(vis.shape[1] - 40, cx2 + 18), pred_y - 2),
                    DEBUG_FONT, 0.35, color, 1)
    return vis


def _compose_debug_display(vis, detector, controller, state_ctx):
    """Compose the bar visualization with a side telemetry panel."""
    fish_predictions = _predict_fish_positions(detector)
    box_predictions = controller.predict_box_positions(detector, DEBUG_PREDICTION_FRAMES, CONTROL_HZ)
    vis = _draw_prediction_markers(vis, detector, fish_predictions, box_predictions)
    intercept_plan = controller.last_intercept_plan

    minigame_elapsed = state_ctx['now'] - state_ctx['state_start']
    grace_remaining = max(0.0, MINIGAME_GRACE - minigame_elapsed)
    region = state_ctx.get('region') or {}
    region_w = region.get('width', vis.shape[1])
    region_h = region.get('height', vis.shape[0])

    lines = [
        f"STATE     {state_ctx['state']}  t={minigame_elapsed:5.2f}s  frame={state_ctx['minigame_frames']}",
        f"ACTION    {'HOLD' if controller.space_held else 'RELEASE'}  duty={controller._duty:6.1%}  acc={controller._accumulator:5.2f}",
        f"PROGRESS  {detector.progress:6.1%}  d={detector.progress_delta:+6.3f}  grace={grace_remaining:4.1f}s  catches={state_ctx['catches']}",
        f"FISH OBS  y={detector.detected_fish_y if detector.detected_fish_y is not None else float('nan'):6.3f}  mode={detector.last_detection_method:>14}",
        f"FISH INF  y={detector.inferred_fish_y:6.3f}  src={detector.virtual_fish_source:>14}",
        f"FISH USE  y={detector.fish_y:6.3f}  dir={_format_direction_code(detector.fish_direction):>6}  vel={detector.virtual_fish_velocity:+7.3f}",
        f"FISH RAW  dir={_format_direction(detector.raw_fish_velocity):>6}  vel={detector.raw_fish_velocity:+7.3f}",
        f"FISH SPD  est={detector.fish_speed:6.3f}  band={detector.fish_speed_band:6.3f}",
        f"CV SCORE  score={detector.last_match_score:6.3f}  shape={detector.last_shape_score:6.3f}",
        f"TRACKER   y={detector.last_tracker_y if detector.last_tracker_y is not None else float('nan'):6.3f}  conf={detector.tracker_confidence:5.2f}",
        f"TURN      pending={_format_direction_code(detector.pending_fish_direction):>6}  frames={detector.pending_direction_frames}/{detector.DIRECTION_CONFIRM_FRAMES}",
        f"LOOKAHEAD y={controller.last_fish_pred:6.3f}  dt={controller.LOOKAHEAD * 1000:4.0f}ms  mode={controller.last_tracking_mode}",
        f"BOX       top={detector.box_top:6.3f}  ctr={detector.box_center:6.3f}  bot={detector.box_bottom:6.3f}",
        f"BOX VEL   dir={_format_direction(controller.last_box_velocity):>6}  vel={controller.last_box_velocity:+7.3f}",
        f"CONTROL   err={controller.last_error:+7.3f}  rate={controller.last_error_rate:+7.3f}",
        f"ERR RATE  {controller.last_error_rate:+7.3f}  history={len(detector.fish_y_history):2d}",
        f"MEET      +{intercept_plan['frames_ahead']:2d}f  t={intercept_plan['target_seconds'] * 1000:5.0f}ms  gap={intercept_plan['predicted_abs_gap']:6.3f}" if intercept_plan else 'MEET      n/a',
        f"MEET POS  fish={intercept_plan['predicted_fish_y']:6.3f}  box={intercept_plan['predicted_box_y']:6.3f}  hold={intercept_plan['hold_ratio']:5.1%}" if intercept_plan else 'MEET POS  n/a',
        f"BAR       blue_max={state_ctx['max_blue_seen']:6.1%}  low_blue={state_ctx['low_blue_count']:2d}",
        f"CAPTURE   {region_w}x{region_h}  strip={vis.shape[1]}x{vis.shape[0]}",
        "NEXT FISH " + '  '.join(f"+{frames}:{value:0.3f}" for frames, value in fish_predictions[:3]),
        "NEXT FISH " + '  '.join(f"+{frames}:{value:0.3f}" for frames, value in fish_predictions[3:]),
        "NEXT BOX  " + '  '.join(f"+{frames}:{value:0.3f}" for frames, value in box_predictions[:3]),
        "NEXT BOX  " + '  '.join(f"+{frames}:{value:0.3f}" for frames, value in box_predictions[3:]),
    ]

    text_sizes = [cv2.getTextSize(line, DEBUG_FONT, DEBUG_FONT_SCALE, DEBUG_FONT_THICKNESS)[0]
                  for line in lines]
    line_height = max(size[1] for size in text_sizes) + 8
    panel_width = max(DEBUG_PANEL_MIN_WIDTH, max(size[0] for size in text_sizes) + DEBUG_PADDING * 2)
    panel_height = max(vis.shape[0], DEBUG_PADDING * 2 + line_height * len(lines))
    display_height = max(vis.shape[0], panel_height)
    display_width = vis.shape[1] + panel_width

    canvas = np.zeros((display_height, display_width, 3), dtype=np.uint8)
    canvas[:, :] = (18, 18, 18)
    canvas[0:vis.shape[0], 0:vis.shape[1]] = vis

    panel_x = vis.shape[1]
    cv2.rectangle(canvas, (panel_x, 0), (display_width - 1, display_height - 1), (45, 45, 45), -1)
    cv2.line(canvas, (panel_x, 0), (panel_x, display_height - 1), (80, 80, 80), 1)

    for idx, line in enumerate(lines):
        baseline_y = DEBUG_PADDING + (idx + 1) * line_height - 4
        cv2.putText(canvas, line, (panel_x + DEBUG_PADDING, baseline_y),
                    DEBUG_FONT, DEBUG_FONT_SCALE, (235, 235, 235), DEBUG_FONT_THICKNESS)

    scale = min(DEBUG_TARGET_WIDTH / max(display_width, 1),
                DEBUG_TARGET_HEIGHT / max(display_height, 1))
    if scale > 0 and abs(scale - 1.0) > 0.01:
        return cv2.resize(canvas, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    return canvas


def _create_live_debug_recorder(enabled):
    """Create an on-disk recorder for live minigame debug traces."""
    if not enabled:
        return None

    root_dir = os.path.join(os.path.dirname(__file__), 'live_debug_runs')
    os.makedirs(root_dir, exist_ok=True)
    session_name = datetime.now().strftime('%Y%m%d_%H%M%S')
    session_dir = os.path.join(root_dir, session_name)
    os.makedirs(session_dir, exist_ok=True)
    events_dir = os.path.join(session_dir, 'events')
    os.makedirs(events_dir, exist_ok=True)
    telemetry_path = os.path.join(session_dir, 'telemetry.jsonl')
    projection_path = os.path.join(session_dir, 'projection_calibration.jsonl')
    projection_summary_path = os.path.join(session_dir, 'projection_summary.json')
    return {
        'session_dir': session_dir,
        'events_dir': events_dir,
        'telemetry_path': telemetry_path,
        'projection_path': projection_path,
        'projection_summary_path': projection_summary_path,
        'buffer': deque(maxlen=LIVE_DEBUG_BUFFER_FRAMES),
        'last_dump_frame': -LIVE_DEBUG_DUMP_COOLDOWN,
        'dump_count': 0,
        'last_note': None,
        'projection_pending': [],
        'projection_frames': {},
        'projection_outcomes': [],
        'writer': _AsyncFileWriter(),
        'closed': False,
    }


def _finalize_live_debug_recorder(recorder, controller):
    """Flush queued debug writes and stop the background writer."""
    if recorder is None or recorder.get('closed'):
        return
    _write_projection_summary(recorder, controller)
    recorder['writer'].close()
    recorder['closed'] = True


def _build_projection_actual_frame(state_ctx, detector):
    """Build the observed state used to validate earlier intercept plans."""
    return {
        'frame': int(state_ctx['minigame_frames']),
        'time': float(state_ctx['now']),
        'fish_y': float(detector.fish_y),
        'box_center': float(detector.box_center),
        'progress': float(detector.progress),
    }


def _write_projection_summary(recorder, controller):
    """Persist a per-session summary of projection calibration outcomes."""
    summary = summarize_projection_outcomes(
        recorder['projection_outcomes'],
        current_lookahead=controller.LOOKAHEAD,
        current_gravity=controller.GRAVITY,
        current_thrust=controller.THRUST,
        control_hz=CONTROL_HZ,
    )
    summary['session_dir'] = recorder['session_dir']
    recorder['writer'].write_json(recorder['projection_summary_path'], summary, indent=2)


def _update_projection_calibration(state_ctx, detector, controller):
    """Resolve projected fish/box meeting plans against actual future frames."""
    recorder = state_ctx.get('debug_recorder')
    if recorder is None:
        return

    current_frame = int(state_ctx['minigame_frames'])
    recorder['projection_frames'][current_frame] = _build_projection_actual_frame(state_ctx, detector)

    min_frame = current_frame - (controller.PROJECTION_HORIZON_FRAMES + PROJECTION_TIMING_WINDOW_FRAMES + 5)
    stale_frames = [frame for frame in recorder['projection_frames'] if frame < min_frame]
    for frame in stale_frames:
        recorder['projection_frames'].pop(frame, None)

    plan = controller.last_intercept_plan
    if plan is not None:
        recorder['projection_pending'].append(plan)

    unresolved = []
    for pending in recorder['projection_pending']:
        if pending['target_frame'] + PROJECTION_TIMING_WINDOW_FRAMES > current_frame:
            unresolved.append(pending)
            continue

        outcome = resolve_projection_outcome(
            pending,
            recorder['projection_frames'],
            timing_window_frames=PROJECTION_TIMING_WINDOW_FRAMES,
        )
        if outcome is None:
            continue

        recorder['projection_outcomes'].append(outcome)
        recorder['writer'].append_line(recorder['projection_path'], json.dumps(outcome) + '\n')

        if len(recorder['projection_outcomes']) % PROJECTION_SUMMARY_WRITE_INTERVAL == 0:
            _write_projection_summary(recorder, controller)

    recorder['projection_pending'] = unresolved


def _record_live_debug_frame(state_ctx, detector, controller, raw_img, debug_img=None):
    """Append telemetry for the current minigame frame and keep an in-memory frame buffer."""
    recorder = state_ctx.get('debug_recorder')
    if recorder is None:
        return

    intercept_plan = controller.last_intercept_plan

    telemetry = {
        'frame': int(state_ctx['minigame_frames']),
        'time': float(state_ctx['now']),
        'state': state_ctx['state'],
        'fish_y': float(detector.fish_y),
        'detected_fish_y': None if detector.detected_fish_y is None else float(detector.detected_fish_y),
        'inferred_fish_y': float(detector.inferred_fish_y),
        'box_top': float(detector.box_top),
        'box_bottom': float(detector.box_bottom),
        'box_center': float(detector.box_center),
        'progress': float(detector.progress),
        'progress_delta': float(detector.progress_delta),
        'fish_velocity': float(detector.fish_velocity),
        'raw_fish_velocity': float(detector.raw_fish_velocity),
        'virtual_fish_velocity': float(detector.virtual_fish_velocity),
        'fish_speed_band': float(detector.fish_speed_band),
        'fish_speed': float(detector.fish_speed),
        'fish_direction': int(detector.fish_direction),
        'method': detector.last_detection_method,
        'virtual_source': detector.virtual_fish_source,
        'match_score': float(detector.last_match_score),
        'shape_score': float(detector.last_shape_score),
        'tracker_confidence': float(detector.tracker_confidence),
        'tracker_y': None if detector.last_tracker_y is None else float(detector.last_tracker_y),
        'template_source': detector.template_source,
        'controller_error': float(controller.last_error),
        'controller_error_rate': float(controller.last_error_rate),
        'controller_duty': float(controller._duty),
        'controller_tracking_mode': controller.last_tracking_mode,
        'space_held': bool(controller.space_held),
        'intercept_target_frame': None if intercept_plan is None else int(intercept_plan['target_frame']),
        'intercept_frames_ahead': None if intercept_plan is None else int(intercept_plan['frames_ahead']),
        'intercept_target_seconds': None if intercept_plan is None else float(intercept_plan['target_seconds']),
        'intercept_predicted_fish_y': None if intercept_plan is None else float(intercept_plan['predicted_fish_y']),
        'intercept_predicted_box_y': None if intercept_plan is None else float(intercept_plan['predicted_box_y']),
        'intercept_predicted_gap': None if intercept_plan is None else float(intercept_plan['predicted_signed_gap']),
        'intercept_hold_ratio': None if intercept_plan is None else float(intercept_plan['hold_ratio']),
        'region': state_ctx.get('region'),
        'note': recorder.get('last_note'),
    }
    recorder['last_note'] = None

    recorder['writer'].append_line(recorder['telemetry_path'], json.dumps(telemetry) + '\n')

    recorder['buffer'].append({
        'frame': telemetry['frame'],
        'telemetry': telemetry,
        'raw_img': raw_img.copy(),
        'debug_img': None if debug_img is None else debug_img.copy(),
    })


def _detect_overlap_jump(detector, prev_fish_y):
    """Return a dump reason when fish tracking jumps while the white box overlaps the fish."""
    if prev_fish_y is None:
        return None

    near_box = (
        detector.box_top - LIVE_DEBUG_OVERLAP_MARGIN <= detector.fish_y <=
        detector.box_bottom + LIVE_DEBUG_OVERLAP_MARGIN
    )
    if not near_box:
        return None

    jump = detector.fish_y - prev_fish_y
    if abs(jump) < LIVE_DEBUG_JUMP_THRESHOLD:
        return None

    prev_side = np.sign(prev_fish_y - detector.box_center)
    curr_side = np.sign(detector.fish_y - detector.box_center)
    if prev_side == 0:
        prev_side = curr_side

    if prev_side != curr_side:
        side_text = 'above' if curr_side < 0 else 'below'
        return f'fish_jumped_{side_text}_box'

    return f'fish_jump_{jump:+.3f}'


def _dump_live_debug_buffer(state_ctx, reason):
    """Persist recent buffered frames around a suspicious live event."""
    recorder = state_ctx.get('debug_recorder')
    if recorder is None or not recorder['buffer']:
        return

    frame_index = state_ctx['minigame_frames']
    if frame_index - recorder['last_dump_frame'] < LIVE_DEBUG_DUMP_COOLDOWN:
        return

    recorder['last_dump_frame'] = frame_index
    recorder['dump_count'] += 1
    dump_name = f"{recorder['dump_count']:03d}_{frame_index:05d}_{reason}"
    dump_dir = os.path.join(recorder['events_dir'], dump_name)

    frames = list(recorder['buffer'])[-LIVE_DEBUG_DUMP_FRAMES:]
    for item in frames:
        stem = f"{item['frame']:05d}"
        recorder['writer'].write_image(os.path.join(dump_dir, f'{stem}_raw.png'), item['raw_img'])
        if item['debug_img'] is not None:
            recorder['writer'].write_image(os.path.join(dump_dir, f'{stem}_debug.png'), item['debug_img'])

    summary = {
        'reason': reason,
        'frame': frame_index,
        'saved_frames': len(frames),
        'session_dir': recorder['session_dir'],
        'telemetry_tail': [item['telemetry'] for item in frames[-10:]],
    }
    recorder['writer'].write_json(os.path.join(dump_dir, 'summary.json'), summary, indent=2)

    print(f"[!] Live debug dump queued: {dump_dir}")


def _set_detector_note(state_ctx, note):
    """Attach a note to the next recorder telemetry entry."""
    recorder = state_ctx.get('debug_recorder')
    if recorder is not None:
        recorder['last_note'] = note


def _handle_idle(state_ctx):
    """Handle IDLE state: anti-AFK movement and casting."""
    now = state_ctx['now']
    if state_ctx['reel_only']:
        state_ctx['state'] = GameState.WAITING
        state_ctx['state_start'] = now
        state_ctx['detector'].bar_found = False
        state_ctx['controller'].reset()
        state_ctx['prev_debug_fish_y'] = None
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
        state_ctx['prev_debug_fish_y'] = None
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
            cv2.imshow(DEBUG_WINDOW_NAME, show)
            if not state_ctx['topmost_set']:
                _setup_topmost_window(DEBUG_WINDOW_NAME)
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
        _set_detector_note(state_ctx, 'minigame-detected')
        state_ctx['state'] = GameState.MINIGAME
        state_ctx['state_start'] = now
        state_ctx['max_blue_seen'] = 0.0
        state_ctx['minigame_frames'] = 0
        state_ctx['prev_debug_fish_y'] = None
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
            cv2.imshow(DEBUG_WINDOW_NAME, show)
            if not state_ctx['topmost_set']:
                _setup_topmost_window(DEBUG_WINDOW_NAME)
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
            recorder = state_ctx.get('debug_recorder')
            if recorder is not None:
                recorder['writer'].write_image(os.path.join(diag_dir, 'first_low.png'), state_ctx['img'])
                recorder['writer'].write_image(os.path.join(diag_dir, 'first_low_strip.png'), col_strip)
            else:
                _write_image_file(os.path.join(diag_dir, 'first_low.png'), state_ctx['img'])
                _write_image_file(os.path.join(diag_dir, 'first_low_strip.png'), col_strip)
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
        recorder = state_ctx.get('debug_recorder')
        if recorder is not None:
            recorder['writer'].write_image(os.path.join(diag_dir, 'capture.png'), state_ctx['img'])
            recorder['writer'].write_image(os.path.join(diag_dir, 'col_strip.png'), col_strip)
        else:
            _write_image_file(os.path.join(diag_dir, 'capture.png'), state_ctx['img'])
            _write_image_file(os.path.join(diag_dir, 'col_strip.png'), col_strip)
        print(f"[!] Diagnostic images queued to {diag_dir}/ "
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

    # Adjust detector coordinates relative to capture region while preserving
    # tracker/template state across frames.
    abs_coords = (
        detector.col_x1,
        detector.col_x2,
        detector.col_y1,
        detector.col_y2,
        detector.prog_x1,
        detector.prog_x2,
    )
    detector.col_x1 -= region['left']
    detector.col_x2 -= region['left']
    detector.col_y1 -= region['top']
    detector.col_y2 -= region['top']
    detector.prog_x1 -= region['left']
    detector.prog_x2 -= region['left']
    detector.bar_found = True

    # Check if blue bar is still present
    sy1 = max(0, min(detector.col_y1, img.shape[0]))
    sy2 = max(0, min(detector.col_y2 + 1, img.shape[0]))
    sx1 = max(0, min(detector.col_x1, img.shape[1]))
    sx2 = max(0, min(detector.col_x2 + 1, img.shape[1]))
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
            detector.col_x1, detector.col_x2, detector.col_y1, detector.col_y2, detector.prog_x1, detector.prog_x2 = abs_coords
            return
    else:
        state_ctx['low_blue_count'] += 1

    result = detector.detect_elements(img)

    if result is None:
        detector.col_x1, detector.col_x2, detector.col_y1, detector.col_y2, detector.prog_x1, detector.prog_x2 = abs_coords
        return

    state_ctx['minigame_frames'] += 1
    if now - state_ctx['last_status_log'] >= 2.0:
        state_ctx['last_status_log'] = now
        err = detector.fish_y - detector.box_center
        print(f"  [status] fish={detector.fish_y:.2f} box={detector.box_center:.2f} "
              f"err={err:+.2f} duty={controller._duty:.0%} prog={detector.progress:.0%} "
              f"method={detector.last_detection_method} score={detector.last_match_score:.2f} "
              f"frames={state_ctx['minigame_frames']}", flush=True)

    # Run controller
    was_held = controller.space_held
    should_hold = controller.update(detector)
    controller.predict_intercept_plan(detector, CONTROL_HZ, source_frame=state_ctx['minigame_frames'])
    if should_hold != was_held:
        if should_hold:
            pydirectinput.keyDown('space')
        else:
            pydirectinput.keyUp('space')

    # Debug visualization
    show = None
    if debug:
        vis = detector.draw_debug(img)
        show = _compose_debug_display(vis, detector, controller, state_ctx)
        cv2.imshow(DEBUG_WINDOW_NAME, show)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            state_ctx['running'] = False

    _record_live_debug_frame(state_ctx, detector, controller, img, show)
    _update_projection_calibration(state_ctx, detector, controller)
    overlap_reason = _detect_overlap_jump(detector, state_ctx.get('prev_debug_fish_y'))
    if overlap_reason is not None:
        _dump_live_debug_buffer(state_ctx, overlap_reason)
    state_ctx['prev_debug_fish_y'] = detector.fish_y

    detector.col_x1, detector.col_x2, detector.col_y1, detector.col_y2, detector.prog_x1, detector.prog_x2 = abs_coords

    # Rate limit
    elapsed = time.perf_counter() - loop_start
    control_interval = 1.0 / CONTROL_HZ
    sleep_time = control_interval - elapsed
    if sleep_time > 0:
        time.sleep(sleep_time)


def _handle_caught(state_ctx):
    """Handle CAUGHT state: log catch and prepare for next cast."""
    print(f"[*] Total catches: {state_ctx['catches']}. Casting again in {CAST_DELAY}s...")
    _set_detector_note(state_ctx, 'fish-caught')
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
        'debug_recorder': _create_live_debug_recorder(debug),
        'prev_debug_fish_y': None,
    }

    # Graceful shutdown
    def signal_handler(sig, frame):
        print("\n[!] Shutting down...")
        state_ctx['running'] = False
        if controller.space_held:
            pydirectinput.keyUp('space')
        _finalize_live_debug_recorder(state_ctx['debug_recorder'], controller)
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)

    print("[*] Fishing automation started")
    if reel_only:
        print("[*] Reel-only mode: searching for minigame bar...")
    print("[*] Move mouse to top-left corner to abort (FAILSAFE)")
    if debug:
        print("[*] Debug visualization enabled - press 'q' in window to quit")
        _setup_debug_window(DEBUG_WINDOW_NAME)
        _setup_topmost_window(DEBUG_WINDOW_NAME)
        if state_ctx['debug_recorder'] is not None:
            print(f"[*] Live debug capture: {state_ctx['debug_recorder']['session_dir']}")

    while state_ctx['running']:
        state_ctx['now'] = time.perf_counter()
        handler = _STATE_HANDLERS.get(state_ctx['state'])
        if handler:
            handler(state_ctx)

    # Cleanup
    if controller.space_held:
        pydirectinput.keyUp('space')
    if state_ctx['debug_recorder'] is not None:
        _finalize_live_debug_recorder(state_ctx['debug_recorder'], controller)
        print(f"[*] Projection calibration summary: {state_ctx['debug_recorder']['projection_summary_path']}")
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
                    dummy_state = {
                        'state': 'TEST',
                        'state_start': 0.0,
                        'now': 0.0,
                        'minigame_frames': 0,
                        'catches': 0,
                        'max_blue_seen': 0.0,
                        'low_blue_count': 0,
                        'region': {'width': crop.shape[1], 'height': crop.shape[0]},
                    }
                    dummy_controller = FishingController()
                    show = _compose_debug_display(vis, vis_det, dummy_controller, dummy_state)
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
                dummy_controller = FishingController()
                dummy_state = {
                    'state': 'TEST',
                    'state_start': 0.0,
                    'now': 0.0,
                    'minigame_frames': 0,
                    'catches': 0,
                    'max_blue_seen': 0.0,
                    'low_blue_count': 0,
                    'region': {'width': img.shape[1], 'height': img.shape[0]},
                }
                vis = detector.draw_debug(img)
                pad = 50
                crop = vis[
                    max(0, detector.col_y1 - pad):min(h, detector.col_y2 + pad),
                    max(0, detector.col_x1 - pad):min(w, detector.prog_x2 + pad + 60),
                ]
                vis_det = BarDetector()
                vis_det.col_x1 = pad
                vis_det.col_x2 = pad + (detector.col_x2 - detector.col_x1)
                vis_det.col_y1 = pad
                vis_det.col_y2 = pad + (detector.col_y2 - detector.col_y1)
                vis_det.prog_x1 = vis_det.col_x2 + 1
                vis_det.prog_x2 = vis_det.col_x2 + (detector.prog_x2 - detector.prog_x1)
                vis_det.bar_found = True
                vis_det.fish_y = detector.fish_y
                vis_det.box_top = detector.box_top
                vis_det.box_bottom = detector.box_bottom
                vis_det.box_center = detector.box_center
                vis_det.progress = detector.progress
                vis_det.fish_velocity = detector.fish_velocity
                vis_det.fish_y_history = detector.fish_y_history
                show = _compose_debug_display(crop, vis_det, dummy_controller, dummy_state)
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
