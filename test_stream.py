"""
Stream-based test: processes calibration frames sequentially through BarDetector,
simulating the real game loop with velocity tracking and prediction.
Compares detected fish_y with human-calibrated ground truth.

Usage:
  python test_stream.py                    # run test
  python test_stream.py --verbose          # show every frame
  python test_stream.py --plot             # show error plot (requires matplotlib)
"""
import sys
import os
import json
import argparse
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from detection import BarDetector
from config import SEARCH_MARGIN_X_FRAC, SEARCH_MARGIN_Y_FRAC

RESULTS_FILE = 'calibration_results.json'
FRAME_DT = 1.0 / 60  # approximate dt between recorded frames


def load_frame_and_detect(fpath, det, fake_time):
    """Load frame, find bar if needed, run detection with fake timestamp."""
    img = cv2.imread(fpath)
    if img is None:
        return None, None

    if not det.bar_found:
        h, w = img.shape[:2]
        cx, cy = w // 2, h // 2
        mx = int(w * SEARCH_MARGIN_X_FRAC)
        my = int(h * SEARCH_MARGIN_Y_FRAC)
        roi = img[cy - my:cy + my, cx - mx:cx + mx]
        if not det.find_bar(roi):
            return None, None
        det.col_x1 += cx - mx
        det.col_x2 += cx - mx
        det.col_y1 += cy - my
        det.col_y2 += cy - my
        det.prog_x1 += cx - mx
        det.prog_x2 += cx - mx

    result = det.detect_elements(img, now=fake_time)
    return result, img


def run_stream_test(verbose=False, do_plot=False):
    if not os.path.exists(RESULTS_FILE):
        print(f"ERROR: {RESULTS_FILE} not found")
        return False

    cal = json.load(open(RESULTS_FILE))
    if not cal:
        print("No calibration data found")
        return False

    # Group by frame_dir and sort by frame number
    items = sorted(cal.values(), key=lambda v: (v['frame_dir'], v['frame_name']))

    # Find contiguous runs for stream processing
    runs = []
    current_run = [items[0]]
    for i in range(1, len(items)):
        prev_num = int(items[i-1]['frame_name'])
        curr_num = int(items[i]['frame_name'])
        same_dir = items[i]['frame_dir'] == items[i-1]['frame_dir']
        if same_dir and curr_num - prev_num <= 5:  # gap of 5 or less = same run
            current_run.append(items[i])
        else:
            runs.append(current_run)
            current_run = [items[i]]
    runs.append(current_run)

    print(f"Calibration data: {len(items)} frames in {len(runs)} contiguous runs")
    for i, run in enumerate(runs):
        names = [v['frame_name'] for v in run]
        print(f"  Run {i+1}: frames {names[0]}-{names[-1]} ({len(run)} frames)")

    all_errors = []
    all_frames = []
    total_pass = 0
    total_fail = 0
    tolerance = 0.035

    # Use a single continuous detector across ALL runs (like the real game loop).
    # Process all frames from before the first calibrated frame to after the last,
    # giving the detector velocity history that carries across runs.
    frame_dir = runs[0][0]['frame_dir']
    global_first = int(runs[0][0]['frame_name'])
    global_last = int(runs[-1][-1]['frame_name'])

    # Build combined ground-truth lookup and run boundaries
    gt = {}
    run_boundaries = []  # (first_num, last_num, run_idx)
    for run_idx, run in enumerate(runs):
        first_num = int(run[0]['frame_name'])
        last_num = int(run[-1]['frame_name'])
        run_boundaries.append((first_num, last_num, run_idx))
        for v in run:
            gt[v['frame_name']] = (v, run_idx)

    # Warm up: start 200 frames before first calibrated frame
    WARMUP = 200
    start_frame = max(0, global_first - WARMUP)

    det = BarDetector()
    frame_time = 0.0
    current_run_idx = -1

    for frame_num in range(start_frame, global_last + 1):
        fname = f"{frame_num:06d}"
        fpath = os.path.join(frame_dir, f"{fname}.png")

        if not os.path.exists(fpath):
            continue

        frame_time += FRAME_DT
        result, img = load_frame_and_detect(fpath, det, frame_time)
        if result is None:
            continue

        # Print run header when entering a new run
        for first_num, last_num, ridx in run_boundaries:
            if frame_num == first_num and ridx != current_run_idx:
                current_run_idx = ridx
                print(f"\n--- Run {ridx+1}: {frame_dir} frames {first_num}-{last_num} ---")
                break

        # Check against ground truth if this is a calibrated frame
        if fname in gt:
            truth, ridx = gt[fname]
            true_y = truth['true_fish_y']
            if true_y is None:
                continue  # skip None-expected frames

            det_y = det.fish_y
            err = abs(det_y - true_y)
            passed = err <= tolerance
            all_errors.append(err)
            all_frames.append(frame_num)

            if passed:
                total_pass += 1
            else:
                total_fail += 1

            if verbose or not passed:
                status = "PASS" if passed else "FAIL"
                wb = " [WB]" if truth['in_white_box'] else ""
                print(f"  {status} {fname}: det={det_y:.3f} true={true_y:.3f} "
                      f"err={err:.3f} vel={det.fish_velocity:+.3f}{wb}")

    # Summary
    print(f"\n{'='*60}")
    print(f"Results: {total_pass} passed, {total_fail} failed out of {total_pass + total_fail}")
    if all_errors:
        errs = np.array(all_errors)
        print(f"Error stats: mean={errs.mean():.4f} median={np.median(errs):.4f} "
              f"max={errs.max():.4f} p95={np.percentile(errs, 95):.4f}")
        within_tol = np.sum(errs <= tolerance) / len(errs) * 100
        within_2tol = np.sum(errs <= tolerance * 2) / len(errs) * 100
        print(f"Within tolerance ({tolerance}): {within_tol:.1f}%")
        print(f"Within 2x tolerance ({tolerance*2}): {within_2tol:.1f}%")

    if do_plot and all_errors:
        try:
            import matplotlib.pyplot as plt
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6))
            ax1.bar(all_frames, all_errors, width=1)
            ax1.axhline(y=tolerance, color='r', linestyle='--', label=f'tolerance={tolerance}')
            ax1.set_ylabel('Error')
            ax1.set_xlabel('Frame')
            ax1.set_title('Detection Error vs Ground Truth')
            ax1.legend()

            ax2.hist(all_errors, bins=50)
            ax2.axvline(x=tolerance, color='r', linestyle='--', label=f'tolerance={tolerance}')
            ax2.set_xlabel('Error')
            ax2.set_ylabel('Count')
            ax2.set_title('Error Distribution')
            ax2.legend()

            plt.tight_layout()
            plt.savefig('stream_test_errors.png', dpi=100)
            print("\nPlot saved to stream_test_errors.png")
            plt.show()
        except ImportError:
            print("\nmatplotlib not available, skipping plot")

    return total_fail == 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--plot', action='store_true')
    args = parser.parse_args()
    ok = run_stream_test(verbose=args.verbose, do_plot=args.plot)
    sys.exit(0 if ok else 1)
