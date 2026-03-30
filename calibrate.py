"""
Interactive calibration tool for fishscale detection.

Steps through frames from a directory, runs detection, and lets you:
  - SPACE/s: skip (detection looks correct)
  - a/UP/DOWN: adjust — move green line with UP/DOWN arrows, ENTER to confirm
  - q: quit and save results

Saves test cases to calibration_results.json and prints code for
test_detection_regression.py.

Usage:
  python calibrate.py "2026-03-29 23-47-40"
  python calibrate.py "2026-03-29 23-47-40" --start 1190 --end 1210
  python calibrate.py "2026-03-29 23-47-40" --start 1190 --end 1210 --dir2 "2026-03-29 23-51-17"
"""
import sys
import os
import json
import glob
import argparse
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from detection import BarDetector, detect_on_frame
from config import SEARCH_MARGIN_X_FRAC, SEARCH_MARGIN_Y_FRAC

TOLERANCE = 0.035  # same as test_detection_regression.py
ZOOM = 4           # zoom factor for bar area display
RESULTS_FILE = 'calibration_results.json'
STEP_COARSE = 0.005   # ~1.5px per arrow press
STEP_FINE = 0.001     # hold Shift (not available in cv2, use pgup/pgdn)


def load_frame(fpath):
    """Load frame and run bar detection using the canonical detect_on_frame utility."""
    img = cv2.imread(fpath)
    if img is None:
        return None, None
    det, _result = detect_on_frame(img)
    if det is None:
        return None, None
    return det, img


def make_bar_crop(img, det, padding=30):
    """Crop image to just the bar area with padding, return crop and offset."""
    h, w = img.shape[:2]
    x1 = max(0, det.col_x1 - padding)
    x2 = min(w, det.prog_x2 + padding + 30)
    y1 = max(0, det.col_y1 - padding)
    y2 = min(h, det.col_y2 + padding)
    crop = img[y1:y2, x1:x2].copy()
    return crop, x1, y1


def draw_overlay(crop, det, crop_x, crop_y, true_fish_y=None):
    """Draw detection overlay on the cropped bar image."""
    vis = crop.copy()
    col_h = det.col_y2 - det.col_y1

    # Column bounds (green)
    cx1 = det.col_x1 - crop_x
    cx2 = det.col_x2 - crop_x
    cy1 = det.col_y1 - crop_y
    cy2 = det.col_y2 - crop_y
    cv2.rectangle(vis, (cx1, cy1), (cx2, cy2), (0, 255, 0), 1)

    # White box (white)
    box_y1 = cy1 + int(det.box_top * col_h)
    box_y2 = cy1 + int(det.box_bottom * col_h)
    cv2.rectangle(vis, (cx1, box_y1), (cx2, box_y2), (255, 255, 255), 2)

    # Detected fish position (red line)
    fish_abs = cy1 + int(det.fish_y * col_h)
    cv2.line(vis, (cx1 - 5, fish_abs), (cx2 + 5, fish_abs), (0, 0, 255), 2)

    # True fish position (green dashed line) if provided
    if true_fish_y is not None:
        true_abs = cy1 + int(true_fish_y * col_h)
        # Draw dashed line by drawing segments
        for x in range(cx1 - 5, cx2 + 5, 6):
            cv2.line(vis, (x, true_abs), (min(x + 3, cx2 + 5), true_abs), (0, 255, 0), 2)

    # Text info
    info_x = cx2 + 10
    cv2.putText(vis, f"Det: {det.fish_y:.3f}", (info_x, cy1 + 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
    cv2.putText(vis, f"Box: {det.box_top:.3f}-{det.box_bottom:.3f}", (info_x, cy1 + 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    if true_fish_y is not None:
        err = abs(det.fish_y - true_fish_y)
        cv2.putText(vis, f"True: {true_fish_y:.3f} err={err:.3f}", (info_x, cy1 + 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

    return vis


def load_results():
    """Load existing calibration results."""
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"WARNING: {RESULTS_FILE} is corrupt ({e}), starting fresh")
            os.rename(RESULTS_FILE, RESULTS_FILE + '.bak')
    return {}


def save_results(results):
    """Save calibration results to JSON."""
    with open(RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=2)


def print_test_cases(results):
    """Print test cases in format ready to paste into test_detection_regression.py."""
    print("\n" + "=" * 60)
    print("Test cases for test_detection_regression.py:")
    print("=" * 60)
    for key, info in sorted(results.items()):
        frame_dir = info['frame_dir']
        frame_name = info['frame_name']
        true_y = info['true_fish_y']
        det_y = info['detected_fish_y']
        err = abs(true_y - det_y)
        desc = f"calibrated: det={det_y:.3f} err={err:.3f}"
        if info.get('in_white_box'):
            desc += " (fish in white box)"
        # Use the FRAME_DIR variable if it matches, otherwise note which dir
        print(f"    ('{frame_name}', {true_y:.3f}, TOLERANCE, '{desc}'),")
    print()


def main():
    parser = argparse.ArgumentParser(description='Interactive detection calibration tool')
    parser.add_argument('frame_dir', help='Directory containing frame PNGs')
    parser.add_argument('--dir2', help='Second frame directory to also process')
    parser.add_argument('--start', type=int, default=None, help='Start frame number')
    parser.add_argument('--end', type=int, default=None, help='End frame number')
    parser.add_argument('--step', type=int, default=1, help='Step between frames (default: 1)')
    args = parser.parse_args()

    # Collect frame files from all directories
    dirs = [args.frame_dir]
    if args.dir2:
        dirs.append(args.dir2)

    frame_files = []
    for d in dirs:
        files = sorted(glob.glob(os.path.join(d, '*.png')))
        for f in files:
            name = os.path.splitext(os.path.basename(f))[0]
            try:
                num = int(name)
            except ValueError:
                continue
            if args.start is not None and num < args.start:
                continue
            if args.end is not None and num > args.end:
                continue
            frame_files.append((d, name, num, f))

    # Sort by (dir, frame_number)
    frame_files.sort(key=lambda x: (x[0], x[2]))

    # Apply step
    if args.step > 1:
        frame_files = frame_files[::args.step]

    if not frame_files:
        print("No frames found!")
        sys.exit(1)

    print(f"Found {len(frame_files)} frames to review")
    print("Controls:")
    print("  SPACE/s  = skip (detection OK)")
    print("  a/UP/DN  = adjust mode (move green line with UP/DOWN, ENTER to save, ESC to cancel)")
    print("  n        = mark as None (fish not visible/in white box)")
    print("  LEFT     = go back one frame")
    print("  q        = quit and save")
    print()

    results = load_results()
    window_name = 'Calibrate'
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    idx = 0
    while idx < len(frame_files):
        frame_dir, frame_name, frame_num, fpath = frame_files[idx]
        key_str = f"{frame_dir}/{frame_name}"

        det, img = load_frame(fpath)
        if det is None:
            print(f"  [{idx+1}/{len(frame_files)}] {key_str}: bar not found, skipping")
            idx += 1
            continue

        result = det.detect_elements(img)
        if result is None:
            print(f"  [{idx+1}/{len(frame_files)}] {key_str}: detection failed, skipping")
            idx += 1
            continue

        # Check if fish is inside white box
        in_wb = bool(det.box_top <= det.fish_y <= det.box_bottom)

        # Check if already calibrated
        prev = results.get(key_str)
        true_y = prev['true_fish_y'] if prev else None

        crop, crop_x, crop_y = make_bar_crop(img, det)
        vis = draw_overlay(crop, det, crop_x, crop_y, true_y)

        # Status text at top
        status = f"[{idx+1}/{len(frame_files)}] {key_str}  fish={det.fish_y:.3f}"
        if in_wb:
            status += " [IN WHITE BOX]"
        if prev:
            status += f"  [CALIBRATED: {true_y:.3f}]"

        # Zoom for better visibility
        zoomed = cv2.resize(vis, None, fx=ZOOM, fy=ZOOM, interpolation=cv2.INTER_NEAREST)

        # Add status bar at top
        bar_h = 30
        display = np.zeros((bar_h + zoomed.shape[0], max(zoomed.shape[1], 600), 3), dtype=np.uint8)
        display[bar_h:bar_h + zoomed.shape[0], :zoomed.shape[1]] = zoomed
        cv2.putText(display, status, (5, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        cv2.imshow(window_name, display)
        key = cv2.waitKeyEx(0)

        if key == ord('q'):
            break
        elif key == ord('s') or key == ord(' '):
            # Skip — detection is correct
            print(f"  {key_str}: SKIP (det={det.fish_y:.3f})")
            idx += 1
        elif key == ord('n'):
            # Mark as None (fish not visible / inside white box)
            results[key_str] = {
                'frame_dir': frame_dir,
                'frame_name': frame_name,
                'detected_fish_y': float(det.fish_y),
                'true_fish_y': None,
                'box_top': float(det.box_top),
                'box_bottom': float(det.box_bottom),
                'in_white_box': in_wb,
            }
            save_results(results)
            print(f"  {key_str}: NONE (fish not reliably visible)")
            idx += 1
        elif key == ord('a') or key == 2490368 or key == 2621440:  # 'a' or UP or DOWN
            # Adjust mode — use arrow keys to move green line
            cursor_y = true_y if true_y is not None else det.fish_y
            # If UP/DOWN triggered entry, apply initial nudge
            if key == 2490368:  # UP
                cursor_y = max(0.0, cursor_y - STEP_COARSE)
            elif key == 2621440:  # DOWN
                cursor_y = min(1.0, cursor_y + STEP_COARSE)

            while True:
                vis_adj = draw_overlay(crop, det, crop_x, crop_y, cursor_y)
                zoomed_adj = cv2.resize(vis_adj, None, fx=ZOOM, fy=ZOOM,
                                        interpolation=cv2.INTER_NEAREST)
                disp_adj = np.zeros((bar_h + zoomed_adj.shape[0],
                                     max(zoomed_adj.shape[1], 600), 3), dtype=np.uint8)
                disp_adj[bar_h:bar_h + zoomed_adj.shape[0], :zoomed_adj.shape[1]] = zoomed_adj
                err_now = abs(det.fish_y - cursor_y)
                adj_status = (f"ADJUST {key_str}  cursor={cursor_y:.3f} det={det.fish_y:.3f} "
                              f"err={err_now:.3f}  UP/DN=move  ENTER=save  ESC=cancel")
                cv2.putText(disp_adj, adj_status, (5, 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
                cv2.imshow(window_name, disp_adj)

                k2 = cv2.waitKeyEx(0)  # waitKeyEx for arrow key codes
                if k2 == 2490368:  # UP arrow
                    cursor_y = max(0.0, cursor_y - STEP_COARSE)
                elif k2 == 2621440:  # DOWN arrow
                    cursor_y = min(1.0, cursor_y + STEP_COARSE)
                elif k2 == 2162688:  # Page Up (fine)
                    cursor_y = max(0.0, cursor_y - STEP_FINE)
                elif k2 == 2228224:  # Page Down (fine)
                    cursor_y = min(1.0, cursor_y + STEP_FINE)
                elif k2 == 13 or k2 == ord('\r'):  # ENTER — save
                    true_fish_y = cursor_y
                    results[key_str] = {
                        'frame_dir': frame_dir,
                        'frame_name': frame_name,
                        'detected_fish_y': float(det.fish_y),
                        'true_fish_y': float(true_fish_y),
                        'box_top': float(det.box_top),
                        'box_bottom': float(det.box_bottom),
                        'in_white_box': in_wb,
                    }
                    save_results(results)
                    print(f"  {key_str}: ADJUSTED true={true_fish_y:.3f} "
                          f"det={det.fish_y:.3f} err={abs(det.fish_y - true_fish_y):.3f}")
                    idx += 1
                    break
                elif k2 == 27:  # ESC — cancel
                    print(f"  {key_str}: adjust cancelled")
                    break
        elif key == 2424832:  # LEFT arrow
            idx = max(0, idx - 1)
        else:
            idx += 1

    cv2.destroyAllWindows()

    # Print summary
    adjusted = {k: v for k, v in results.items() if v.get('true_fish_y') is not None}
    none_cases = {k: v for k, v in results.items() if v.get('true_fish_y') is None}
    print(f"\nCalibration complete: {len(adjusted)} adjusted, {len(none_cases)} marked as None")

    if adjusted:
        print_test_cases(adjusted)

    if none_cases:
        print("\nNone-type test cases (regression guards):")
        for key, info in sorted(none_cases.items()):
            print(f"    ('{info['frame_name']}', None, 0.0, "
                  f"'fish in white box - detection may fail'),")

    print(f"\nResults saved to {RESULTS_FILE}")


if __name__ == '__main__':
    main()
