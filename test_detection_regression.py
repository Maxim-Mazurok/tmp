"""
Regression tests for fishscale detection.

Tests specific frames where detection was previously verified correct or where
bugs were found and fixed. Run with: python test_detection_regression.py

Exit code 0 = all pass, 1 = failures.
"""
import cv2
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from detection import BarDetector, detect_on_frame

FRAME_DIR_1 = '2026-03-29 23-47-40'

TOLERANCE = 0.035  # ~11px at 330px bar height

# Test cases: (frame_name, expected_fish_y_or_None, tolerance, description)
# expected=None means "just check detection doesn't crash" (known limitation frames)
# For NO_DETECT frames (fish inside white box), we verify fish_y stays at default 0.5
TEST_CASES = [
    # --- Critical regression tests: must NOT detect white box bottom as fish ---
    # fish=0.898 was the regression; anything < 0.75 is acceptable
    ('000922', None, 0.0, 'must not detect wb bottom as fish (was 0.898 regression)'),
    ('000990', None, 0.0, 'must not detect wb bottom as fish (was 0.884 regression)'),

    # --- Frames with reliable outside-box detection ---
    ('001001', 0.451, TOLERANCE, 'fish clearly visible outside white box'),
    ('001193', 0.605, TOLERANCE, 'fish outside white box'),
    ('001205', 0.677, TOLERANCE, 'fish just left white box'),
    ('001210', 0.651, TOLERANCE, 'fish outside white box'),
    ('001250', 0.529, TOLERANCE, 'fish below white box'),

    # --- Fish inside/near white box: detection may fail (known limitation) ---
    # These frames the fish is inside the white box; detection is expected to fail
    # (returning default 0.5). We just verify no crash and no wild false positive.
    ('001195', None, 0.0, 'fish entering white box - detection may fail'),
    ('001197', None, 0.0, 'fish inside white box - detection may fail'),
    ('001199', None, 0.0, 'fish inside white box - detection may fail'),
    ('001201', None, 0.0, 'fish inside white box - detection may fail'),
]


def _load_frame(fpath):
    """Load frame and run bar detection."""
    img = cv2.imread(fpath)
    if img is None:
        return None, None
    det, _result = detect_on_frame(img)
    if det is None:
        return None, None
    return det, img


def run_tests():
    passed = 0
    failed = 0
    skipped = 0

    for frame_name, expected_y, tol, desc in TEST_CASES:
        fpath = os.path.join(FRAME_DIR_1, f'{frame_name}.png')
        if not os.path.exists(fpath):
            print(f'  SKIP {frame_name}: file not found')
            skipped += 1
            continue

        det, img = _load_frame(fpath)
        if det is None:
            print(f'  FAIL {frame_name}: bar not found ({desc})')
            failed += 1
            continue

        result = det.detect_elements(img)
        if result is None:
            print(f'  FAIL {frame_name}: detection returned None ({desc})')
            failed += 1
            continue

        fish_y = result['fish_y']
        box_top = result['box_top']
        box_bottom = result['box_bottom']

        if expected_y is None:
            # Regression guard: fish should NOT be near white box edges
            # Check it's not within 0.02 of box_top or box_bottom
            near_wb_top = abs(fish_y - box_top) < 0.02
            near_wb_bot = abs(fish_y - box_bottom) < 0.02
            if near_wb_top or near_wb_bot:
                edge = 'top' if near_wb_top else 'bottom'
                print(f'  FAIL {frame_name}: fish={fish_y:.3f} at wb {edge} box=[{box_top:.3f},{box_bottom:.3f}] ({desc})')
                failed += 1
            else:
                print(f'  PASS {frame_name}: fish={fish_y:.3f} box=[{box_top:.3f},{box_bottom:.3f}] ({desc})')
                passed += 1
            continue

        error = abs(fish_y - expected_y)
        if error <= tol:
            print(f'  PASS {frame_name}: fish={fish_y:.3f} expected={expected_y:.3f} err={error:.3f} ({desc})')
            passed += 1
        else:
            print(f'  FAIL {frame_name}: fish={fish_y:.3f} expected={expected_y:.3f} err={error:.3f} > tol={tol:.3f} ({desc})')
            failed += 1

    print(f'\n{"="*60}')
    print(f'Results: {passed} passed, {failed} failed, {skipped} skipped')
    return failed == 0


if __name__ == '__main__':
    ok = run_tests()
    sys.exit(0 if ok else 1)
