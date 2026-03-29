"""
Measure white box position frame-by-frame to characterize acceleration physics.

Protocol:
  1. Find the minigame bar
  2. Run several experiments:
     a) Let box fall freely (release space) - measure gravity/deceleration
     b) Hold space continuously - measure upward acceleration
     c) Alternating hold/release patterns at various frequencies
  3. Log every frame: timestamp, box_center, fish_y, input_state
  4. Save to CSV for plotting

Usage: python measure_box_physics.py
  Game must be running with fishing minigame active.
"""

import sys
import time
import ctypes
import ctypes.wintypes
import numpy as np
import cv2
import mss
import csv

# DPI awareness
ctypes.windll.shcore.SetProcessDpiAwareness(2)

# Import fish.py detection components
sys.path.insert(0, '.')
from fish import BarDetector, ScreenCapture, find_game_window, CONTROL_HZ

import pydirectinput
pydirectinput.PAUSE = 0.0
pydirectinput.FAILSAFE = True

def run_measurement():
    game_win = find_game_window('fivem')
    if not game_win:
        print("[!] FiveM window not found")
        return

    print(f"[*] Found game window: {game_win['title'][:60]}")
    capture = ScreenCapture(game_window=game_win)
    detector = BarDetector()

    # Step 1: Find the bar
    print("[*] Searching for minigame bar...")
    for attempt in range(100):
        img, region = capture.capture_search_region()
        search_offset_x = region['left']
        search_offset_y = region['top']
        if detector.find_bar(img):
            detector.col_x1 += search_offset_x
            detector.col_x2 += search_offset_x
            detector.col_y1 += search_offset_y
            detector.col_y2 += search_offset_y
            detector.prog_x1 += search_offset_x
            detector.prog_x2 += search_offset_x
            print(f"[*] Bar found at x=[{detector.col_x1},{detector.col_x2}] y=[{detector.col_y1},{detector.col_y2}]")
            break
        time.sleep(0.1)
    else:
        print("[!] Could not find bar after 100 attempts")
        return

    # Step 2: Capture function that returns detection results
    def detect_frame():
        """Capture and detect, return (box_center, fish_y, progress) or None."""
        try:
            img, region = capture.capture_bar_region(detector)
        except Exception:
            return None

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
            return None

        # Copy state back
        detector.fish_y = det.fish_y
        detector.box_top = det.box_top
        detector.box_bottom = det.box_bottom
        detector.box_center = det.box_center
        detector.progress = det.progress
        detector.fish_velocity = det.fish_velocity
        detector.fish_y_history = det.fish_y_history

        return (det.box_center, det.fish_y, det.progress, det.box_top, det.box_bottom)

    # Step 3: Run experiments
    experiments = [
        # (name, sequence of (input_state, duration_seconds))
        # input_state: True=hold space, False=release space
        ("free_fall", [(False, 4.0)]),  # Let box fall freely for 4s
        ("hold_up", [(True, 4.0)]),     # Hold space for 4s (box goes up)
        ("fall_then_hold", [(False, 2.0), (True, 2.0)]),  # Fall 2s then hold 2s
        ("hold_then_fall", [(True, 2.0), (False, 2.0)]),  # Hold 2s then fall 2s
        ("short_pulses", [(True, 0.5), (False, 0.5)] * 4),  # 0.5s pulses x4
        ("medium_pulses", [(True, 1.0), (False, 1.0)] * 2),  # 1s pulses x2
        ("micro_pulses", [(True, 0.2), (False, 0.2)] * 10),  # 0.2s pulses x10
    ]

    all_data = []
    control_interval = 1.0 / CONTROL_HZ

    for exp_name, sequence in experiments:
        print(f"\n[*] Experiment: {exp_name}")
        print(f"    Sequence: {sequence}")

        # Ensure we start with space released
        pydirectinput.keyUp('space')
        time.sleep(0.5)

        # Pre-measure: get current box position
        result = detect_frame()
        if result is None:
            print(f"    [!] Detection failed, skipping")
            continue
        print(f"    Starting box={result[0]:.3f}")

        exp_start = time.perf_counter()
        frame_num = 0
        seq_idx = 0
        seq_time = 0.0  # time into current sequence phase
        current_holding = False

        # Execute the sequence
        total_duration = sum(d for _, d in sequence)
        phase_start = exp_start

        while True:
            loop_start = time.perf_counter()
            elapsed_total = loop_start - exp_start

            if elapsed_total >= total_duration:
                break

            # Determine current phase
            phase_elapsed = loop_start - phase_start
            if seq_idx < len(sequence) and phase_elapsed >= sequence[seq_idx][1]:
                phase_start = loop_start
                seq_idx += 1
                if seq_idx >= len(sequence):
                    break

            # Set input
            target_hold = sequence[seq_idx][0]
            if target_hold != current_holding:
                if target_hold:
                    pydirectinput.keyDown('space')
                else:
                    pydirectinput.keyUp('space')
                current_holding = target_hold

            # Detect
            result = detect_frame()
            if result is None:
                frame_num += 1
                continue

            box_center, fish_y, progress, box_top, box_bottom = result

            all_data.append({
                'experiment': exp_name,
                'frame': frame_num,
                'time': elapsed_total,
                'time_abs': loop_start,
                'holding_space': int(current_holding),
                'box_center': box_center,
                'box_top': box_top,
                'box_bottom': box_bottom,
                'fish_y': fish_y,
                'progress': progress,
            })

            frame_num += 1

            # Rate limit
            elapsed_frame = time.perf_counter() - loop_start
            sleep_time = control_interval - elapsed_frame
            if sleep_time > 0:
                time.sleep(sleep_time)

        # Release space at end
        pydirectinput.keyUp('space')
        current_holding = False
        print(f"    Captured {frame_num} frames in {elapsed_total:.2f}s")

        # Brief pause between experiments
        time.sleep(1.0)

    # Step 4: Save to CSV
    csv_path = 'box_physics_data.csv'
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'experiment', 'frame', 'time', 'time_abs',
            'holding_space', 'box_center', 'box_top', 'box_bottom',
            'fish_y', 'progress'
        ])
        writer.writeheader()
        writer.writerows(all_data)

    print(f"\n[*] Saved {len(all_data)} data points to {csv_path}")

    # Step 5: Quick analysis - compute velocities and accelerations
    print("\n[*] Quick analysis:")
    for exp_name in dict.fromkeys(d['experiment'] for d in all_data):
        exp_data = [d for d in all_data if d['experiment'] == exp_name]
        if len(exp_data) < 3:
            continue

        times = [d['time'] for d in exp_data]
        positions = [d['box_center'] for d in exp_data]

        # Compute velocities (bar-units per second)
        velocities = []
        for i in range(1, len(times)):
            dt = times[i] - times[i-1]
            if dt > 0:
                v = (positions[i] - positions[i-1]) / dt
                velocities.append(v)

        # Compute accelerations
        accels = []
        for i in range(1, len(velocities)):
            dt = times[i+1] - times[i]
            if dt > 0:
                a = (velocities[i] - velocities[i-1]) / dt
                accels.append(a)

        if velocities:
            print(f"\n  {exp_name}:")
            print(f"    Frames: {len(exp_data)}")
            print(f"    Position: {positions[0]:.3f} -> {positions[-1]:.3f}")
            print(f"    Velocity (bar/s): min={min(velocities):.3f} max={max(velocities):.3f} mean={np.mean(velocities):.3f}")
            if accels:
                print(f"    Accel (bar/s²):   min={min(accels):.3f} max={max(accels):.3f} mean={np.mean(accels):.3f}")

    # Release space just in case
    pydirectinput.keyUp('space')

if __name__ == '__main__':
    run_measurement()
