"""
Physics measurement tool for the fishing minigame.

Run this while the minigame is active. It will:
1. Detect the bar
2. Record fish position at high frequency
3. Perform controlled experiments:
   - Phase A: Release space, let fish fall for N seconds (measure gravity)
   - Phase B: Hold space, let fish rise for N seconds (measure thrust)
   - Phase C: Alternate tap patterns to measure response time
4. Output a CSV of (time, fish_y, space_held) for analysis

Usage: python measure_physics.py [--phase all|fall|rise|tap]
"""
import sys
import os
import time
import csv
import argparse
import ctypes
import ctypes.wintypes
import numpy as np
import cv2
import mss

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fish import (
    BarDetector, ScreenCapture, find_game_window,
    SEARCH_MARGIN_X_FRAC, SEARCH_MARGIN_Y_FRAC
)

# DPI awareness
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass


def find_bar_live(capture):
    """Keep polling until the bar is found. Returns (detector, search_offsets)."""
    detector = BarDetector()
    print("[*] Searching for minigame bar...")
    while True:
        img, region = capture.capture_search_region()
        if detector.find_bar(img):
            detector.col_x1 += region['left']
            detector.col_x2 += region['left']
            detector.col_y1 += region['top']
            detector.col_y2 += region['top']
            detector.prog_x1 += region['left']
            detector.prog_x2 += region['left']
            print(f"[*] Bar found at x=[{detector.col_x1},{detector.col_x2}] "
                  f"y=[{detector.col_y1},{detector.col_y2}]")
            return detector
        time.sleep(0.05)


def record_phase(capture, detector, pdi, phase_name, duration, hold_space):
    """
    Record fish position for `duration` seconds.
    hold_space: True = hold space, False = release space, 'tap' = alternating
    Returns list of (elapsed_time, fish_y, box_center, space_held, progress)
    """
    print(f"\n[*] Phase '{phase_name}': duration={duration}s, space={'HOLD' if hold_space is True else 'RELEASE' if hold_space is False else 'TAP'}")
    data = []

    # Set initial space state
    if hold_space is True:
        pdi.keyDown('space')
        space_held = True
    else:
        pdi.keyUp('space')
        space_held = False

    # Tap pattern: 200ms on, 200ms off
    tap_interval = 0.20
    next_tap_toggle = time.perf_counter() + tap_interval if hold_space == 'tap' else float('inf')

    start = time.perf_counter()
    frame_count = 0
    detect_fails = 0

    while True:
        now = time.perf_counter()
        elapsed = now - start
        if elapsed >= duration:
            break

        # Tap toggle
        if hold_space == 'tap' and now >= next_tap_toggle:
            space_held = not space_held
            if space_held:
                pdi.keyDown('space')
            else:
                pdi.keyUp('space')
            next_tap_toggle = now + tap_interval

        # Capture and detect
        try:
            img, region = capture.capture_bar_region(detector)
        except Exception as e:
            detect_fails += 1
            continue

        # Detect elements in captured region
        det = BarDetector()
        det.col_x1 = detector.col_x1 - region['left']
        det.col_x2 = detector.col_x2 - region['left']
        det.col_y1 = detector.col_y1 - region['top']
        det.col_y2 = detector.col_y2 - region['top']
        det.prog_x1 = detector.prog_x1 - region['left']
        det.prog_x2 = detector.prog_x2 - region['left']
        det.bar_found = True

        result = det.detect_elements(img)
        if result is None:
            detect_fails += 1
            continue

        data.append((
            elapsed,
            result['fish_y'],
            result['box_center'],
            1 if space_held else 0,
            result['progress'],
        ))
        frame_count += 1

    # Release space
    pdi.keyUp('space')

    fps = frame_count / duration if duration > 0 else 0
    print(f"    Recorded {frame_count} frames in {duration:.1f}s ({fps:.1f} fps), {detect_fails} detect fails")
    return data


def analyze_data(data, phase_name):
    """Analyze recorded data and print physics parameters."""
    if len(data) < 10:
        print(f"  Not enough data for analysis ({len(data)} frames)")
        return

    times = np.array([d[0] for d in data])
    positions = np.array([d[1] for d in data])

    # Compute velocities (units: fraction_of_bar / second)
    dt = np.diff(times)
    dy = np.diff(positions)
    velocities = np.where(dt > 0, dy / dt, 0)

    # Compute accelerations
    if len(velocities) > 1:
        dt2 = (dt[:-1] + dt[1:]) / 2
        dv = np.diff(velocities)
        accelerations = np.where(dt2 > 0, dv / dt2, 0)
    else:
        accelerations = np.array([])

    print(f"\n=== Analysis: {phase_name} ===")
    print(f"  Duration: {times[-1] - times[0]:.3f}s")
    print(f"  Frames: {len(data)}")
    print(f"  Position: start={positions[0]:.3f} end={positions[-1]:.3f} "
          f"delta={positions[-1]-positions[0]:.3f}")

    # Filter out extreme velocity spikes (detection glitches)
    v_filtered = velocities[np.abs(velocities) < 5.0]
    if len(v_filtered) > 0:
        print(f"  Velocity: mean={np.mean(v_filtered):.4f} "
              f"median={np.median(v_filtered):.4f} "
              f"std={np.std(v_filtered):.4f} "
              f"min={np.min(v_filtered):.4f} max={np.max(v_filtered):.4f}")

    if len(accelerations) > 0:
        a_filtered = accelerations[np.abs(accelerations) < 50.0]
        if len(a_filtered) > 0:
            print(f"  Accel: mean={np.mean(a_filtered):.4f} "
                  f"median={np.median(a_filtered):.4f} "
                  f"std={np.std(a_filtered):.4f}")

    # Estimate terminal velocity (last 30% of data)
    n_tail = max(5, len(v_filtered) // 3)
    tail_v = v_filtered[-n_tail:]
    print(f"  Terminal velocity (last {n_tail} samples): "
          f"mean={np.mean(tail_v):.4f} std={np.std(tail_v):.4f}")


def main():
    parser = argparse.ArgumentParser(description='Measure fishing minigame physics')
    parser.add_argument('--phase', default='all', choices=['all', 'fall', 'rise', 'tap'],
                        help='Which experiment phase to run')
    parser.add_argument('--duration', type=float, default=3.0,
                        help='Duration per phase in seconds')
    parser.add_argument('--output', default='physics_data.csv',
                        help='Output CSV file')
    args = parser.parse_args()

    import pydirectinput as pdi
    pdi.FAILSAFE = True

    # Find game
    game_win = find_game_window('fivem')
    if not game_win:
        print("[!] FiveM window not found")
        sys.exit(1)
    print(f"[*] Game window: {game_win['width']}x{game_win['height']}")

    capture = ScreenCapture(game_window=game_win)
    detector = find_bar_live(capture)

    all_data = []

    print("\n[*] Starting in 1 second... (move mouse to top-left to abort)")
    time.sleep(1.0)

    phases = {
        'fall': ('fall', False),
        'rise': ('rise', True),
        'tap': ('tap', 'tap'),
    }

    if args.phase == 'all':
        run_phases = ['fall', 'rise', 'tap']
    else:
        run_phases = [args.phase]

    for phase_name in run_phases:
        label, space = phases[phase_name]
        data = record_phase(capture, detector, pdi, label, args.duration, space)
        for row in data:
            all_data.append((label,) + row)
        analyze_data(data, label)

        # Brief pause between phases
        if phase_name != run_phases[-1]:
            time.sleep(0.5)

    # Save CSV
    with open(args.output, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['phase', 'time', 'fish_y', 'box_center', 'space_held', 'progress'])
        writer.writerows(all_data)
    print(f"\n[*] Data saved to {args.output} ({len(all_data)} rows)")


if __name__ == '__main__':
    main()
