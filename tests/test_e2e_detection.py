"""End-to-end detection tests using real game frames.

Tests detection accuracy against human-calibrated ground truth from
calibration_results.json. Covers both single-frame (fresh detector)
and continuous-stream (shared detector with velocity history) modes.
"""
import os
import json
import numpy as np
import cv2
import pytest

from tests.helpers import (
    BarDetector, FishingController, SEARCH_MARGIN_X_FRAC, SEARCH_MARGIN_Y_FRAC,
    FRAME_DIR_1, FRAME_DIR_2, CALIBRATION_FILE,
    HAS_FRAMES_1, HAS_FRAMES_2, HAS_CALIBRATION,
    load_frame, detect_on_frame,
)

requires_frames_1 = pytest.mark.skipif(
    not HAS_FRAMES_1, reason="Recording 1 frames not available"
)
requires_frames_2 = pytest.mark.skipif(
    not HAS_FRAMES_2, reason="Recording 2 frames not available"
)
requires_calibration = pytest.mark.skipif(
    not HAS_CALIBRATION, reason="calibration_results.json not available"
)

DETECTION_TOLERANCE = 0.035  # ±0.035 normalized (≈11px at 330px bar height)
FRAME_DT = 1.0 / 60  # approximate dt between recorded frames


@requires_frames_1
@requires_calibration
class TestE2EDetectionAccuracy:
    """Verify detection accuracy against calibrated ground truth."""

    @pytest.fixture(autouse=True)
    def _load_calibration(self, calibration_data):
        self.cal = calibration_data

    def _get_outside_box_cases(self):
        """Get calibration entries where fish is outside white box."""
        return {
            k: v for k, v in self.cal.items()
            if not v['in_white_box'] and v['true_fish_y'] is not None
        }

    def _get_inside_box_cases(self):
        """Get calibration entries where fish is inside white box."""
        return {
            k: v for k, v in self.cal.items()
            if v['in_white_box'] and v['true_fish_y'] is not None
        }

    def test_outside_box_detection_rate(self):
        """At least 60% of outside-box frames should be detected within tolerance.

        Note: Single-frame fresh-detector accuracy is lower than stream mode
        because it lacks velocity history. Stream mode (test_stream_detection_accuracy)
        tests the real-world scenario more accurately.
        """
        cases = self._get_outside_box_cases()
        if not cases:
            pytest.skip("No outside-box calibration data")

        passed = 0
        total = 0
        errors = []

        for key, entry in cases.items():
            frame_dir = os.path.join(
                os.path.dirname(CALIBRATION_FILE), entry['frame_dir']
            )
            img = load_frame(frame_dir, entry['frame_name'])
            if img is None:
                continue
            total += 1
            det, result = detect_on_frame(img)
            if result is None:
                continue
            error = abs(result['fish_y'] - entry['true_fish_y'])
            errors.append(error)
            if error <= DETECTION_TOLERANCE:
                passed += 1

        assert total > 0, "No outside-box frames processed"
        rate = passed / total
        assert rate >= 0.60, \
            f"Outside-box detection rate {rate:.0%} < 60% ({passed}/{total})"

    def test_inside_box_no_catastrophic_failure(self):
        """Inside-box detection should not produce wild false positives."""
        cases = self._get_inside_box_cases()
        if not cases:
            pytest.skip("No inside-box calibration data")

        catastrophic = 0
        total = 0

        for key, entry in cases.items():
            frame_dir = os.path.join(
                os.path.dirname(CALIBRATION_FILE), entry['frame_dir']
            )
            img = load_frame(frame_dir, entry['frame_name'])
            if img is None:
                continue
            total += 1
            det, result = detect_on_frame(img)
            if result is None:
                continue
            # Check for catastrophic errors: fish detected way outside the box
            fish_y = result['fish_y']
            if fish_y < entry['box_top'] - 0.15 or fish_y > entry['box_bottom'] + 0.15:
                catastrophic += 1

        assert total > 0, "No inside-box frames processed"
        rate = catastrophic / total
        assert rate < 0.05, \
            f"Catastrophic false positive rate {rate:.0%} ≥ 5% ({catastrophic}/{total})"

    def test_overall_mean_error_acceptable(self):
        """Mean detection error across all frames should be < 0.10.

        Single-frame detection includes inside-white-box frames where the fish
        defaults to 0.5 (known limitation). The stream-mode test is the
        authoritative quality metric.
        """
        errors = []
        for key, entry in self.cal.items():
            if entry['true_fish_y'] is None:
                continue
            frame_dir = os.path.join(
                os.path.dirname(CALIBRATION_FILE), entry['frame_dir']
            )
            img = load_frame(frame_dir, entry['frame_name'])
            if img is None:
                continue
            det, result = detect_on_frame(img)
            if result is None:
                continue
            errors.append(abs(result['fish_y'] - entry['true_fish_y']))

        assert len(errors) > 10, "Not enough frames for meaningful error stats"
        mean_err = np.mean(errors)
        assert mean_err < 0.10, f"Mean error {mean_err:.4f} ≥ 0.10"

    def test_95th_percentile_error(self):
        """95th percentile error should be < 0.35.

        Higher threshold accounts for inside-white-box frames where single-frame
        detection defaults to 0.5 (no velocity history available).
        """
        errors = []
        for key, entry in self.cal.items():
            if entry['true_fish_y'] is None:
                continue
            frame_dir = os.path.join(
                os.path.dirname(CALIBRATION_FILE), entry['frame_dir']
            )
            img = load_frame(frame_dir, entry['frame_name'])
            if img is None:
                continue
            det, result = detect_on_frame(img)
            if result is None:
                continue
            errors.append(abs(result['fish_y'] - entry['true_fish_y']))

        if len(errors) < 10:
            pytest.skip("Not enough frames")
        p95 = np.percentile(errors, 95)
        assert p95 < 0.35, f"P95 error {p95:.4f} ≥ 0.35"


@requires_frames_1
@requires_calibration
class TestE2EStreamDetection:
    """E2E stream detection: process frames sequentially with a shared detector.

    This simulates the real game loop where the detector maintains velocity
    history across frames, testing that the continuous pipeline works correctly.
    """

    @pytest.fixture(autouse=True)
    def _load_calibration(self, calibration_data):
        self.cal = calibration_data

    def _build_runs(self):
        """Group calibration entries into contiguous runs."""
        items = sorted(self.cal.values(),
                       key=lambda v: (v['frame_dir'], v['frame_name']))
        runs = []
        current_run = [items[0]]
        for i in range(1, len(items)):
            prev_num = int(items[i - 1]['frame_name'])
            curr_num = int(items[i]['frame_name'])
            same_dir = items[i]['frame_dir'] == items[i - 1]['frame_dir']
            if same_dir and curr_num - prev_num <= 5:
                current_run.append(items[i])
            else:
                runs.append(current_run)
                current_run = [items[i]]
        runs.append(current_run)
        return runs

    def test_stream_detection_accuracy(self):
        """Stream detection should match ground truth within tolerance.

        Achievement target: >= 75% of calibrated frames within tolerance.
        """
        runs = self._build_runs()
        frame_dir = runs[0][0]['frame_dir']
        frame_dir_path = os.path.join(os.path.dirname(CALIBRATION_FILE), frame_dir)

        global_first = int(runs[0][0]['frame_name'])
        global_last = int(runs[-1][-1]['frame_name'])

        # Build ground truth lookup
        gt = {}
        for run in runs:
            for v in run:
                gt[v['frame_name']] = v

        WARMUP = 200
        start_frame = max(0, global_first - WARMUP)

        det = BarDetector()
        frame_time = 0.0

        passed = 0
        failed = 0
        errors = []

        for frame_num in range(start_frame, global_last + 1):
            fname = f"{frame_num:06d}"
            fpath = os.path.join(frame_dir_path, f"{fname}.png")
            if not os.path.exists(fpath):
                continue

            frame_time += FRAME_DT
            img = cv2.imread(fpath)
            if img is None:
                continue

            if not det.bar_found:
                h, w = img.shape[:2]
                cx, cy = w // 2, h // 2
                mx = int(w * SEARCH_MARGIN_X_FRAC)
                my = int(h * SEARCH_MARGIN_Y_FRAC)
                roi = img[cy - my:cy + my, cx - mx:cx + mx]
                if det.find_bar(roi):
                    det.col_x1 += cx - mx
                    det.col_x2 += cx - mx
                    det.col_y1 += cy - my
                    det.col_y2 += cy - my
                    det.prog_x1 += cx - mx
                    det.prog_x2 += cx - mx

            if not det.bar_found:
                continue

            result = det.detect_elements(img, now=frame_time)
            if result is None:
                continue

            if fname in gt:
                truth = gt[fname]
                true_y = truth['true_fish_y']
                if true_y is None:
                    continue
                err = abs(det.fish_y - true_y)
                errors.append(err)
                if err <= DETECTION_TOLERANCE:
                    passed += 1
                else:
                    failed += 1

        total = passed + failed
        assert total > 10, f"Only {total} frames tested"
        rate = passed / total
        assert rate >= 0.75, \
            f"Stream detection rate {rate:.0%} < 75% ({passed}/{total})"

    def test_stream_velocity_consistent(self):
        """During stream processing, velocity should be smooth and consistent."""
        frame_dir_path = os.path.join(os.path.dirname(CALIBRATION_FILE),
                                      '2026-03-29 23-47-40')
        det = BarDetector()
        frame_time = 0.0

        velocities = []
        for i in range(1001, 1100):
            fpath = os.path.join(frame_dir_path, f"{i:06d}.png")
            if not os.path.exists(fpath):
                continue
            img = cv2.imread(fpath)
            if img is None:
                continue
            frame_time += FRAME_DT

            if not det.bar_found:
                h, w = img.shape[:2]
                cx, cy = w // 2, h // 2
                mx = int(w * SEARCH_MARGIN_X_FRAC)
                my = int(h * SEARCH_MARGIN_Y_FRAC)
                roi = img[cy - my:cy + my, cx - mx:cx + mx]
                if det.find_bar(roi):
                    det.col_x1 += cx - mx
                    det.col_x2 += cx - mx
                    det.col_y1 += cy - my
                    det.col_y2 += cy - my
                    det.prog_x1 += cx - mx
                    det.prog_x2 += cx - mx

            if det.bar_found:
                det.detect_elements(img, now=frame_time)
                velocities.append(det.fish_velocity)

        assert len(velocities) >= 20, "Not enough frames with velocity data"
        # Velocity should not have wild jumps (>2.0 bar/s change between frames)
        vel_diffs = [abs(velocities[i] - velocities[i - 1])
                     for i in range(1, len(velocities))]
        max_jump = max(vel_diffs)
        assert max_jump < 2.0, f"Velocity jump {max_jump:.3f} ≥ 2.0"

    def test_stream_detection_on_relative_bar_crops_preserves_state(self):
        """Automation-style cropped bar captures should preserve detector state across frames."""
        frame_dir_path = os.path.join(os.path.dirname(CALIBRATION_FILE),
                                      '2026-03-29 23-47-40')
        det = BarDetector(use_advanced_inside_box=True)
        frame_time = 0.0
        methods = []

        for i in range(1188, 1203):
            fpath = os.path.join(frame_dir_path, f"{i:06d}.png")
            if not os.path.exists(fpath):
                continue
            img = cv2.imread(fpath)
            if img is None:
                continue
            frame_time += FRAME_DT

            if not det.bar_found:
                h, w = img.shape[:2]
                cx, cy = w // 2, h // 2
                mx = int(w * SEARCH_MARGIN_X_FRAC)
                my = int(h * SEARCH_MARGIN_Y_FRAC)
                roi = img[cy - my:cy + my, cx - mx:cx + mx]
                if det.find_bar(roi):
                    det.col_x1 += cx - mx
                    det.col_x2 += cx - mx
                    det.col_y1 += cy - my
                    det.col_y2 += cy - my
                    det.prog_x1 += cx - mx
                    det.prog_x2 += cx - mx

            if not det.bar_found:
                continue

            bar_h = det.col_y2 - det.col_y1
            bar_w = det.col_x2 - det.col_x1
            padding = max(4, int(bar_h * 0.05))
            prog_extra = max(4, int(bar_w * 0.8))
            region = {
                'left': int(det.col_x1 - padding),
                'top': int(det.col_y1 - padding),
                'width': int((det.prog_x2 - det.col_x1) + padding * 2 + prog_extra),
                'height': int((det.col_y2 - det.col_y1) + padding * 2),
            }
            crop = img[
                region['top']:region['top'] + region['height'],
                region['left']:region['left'] + region['width'],
            ]
            if crop.size == 0:
                continue

            abs_coords = (
                det.col_x1,
                det.col_x2,
                det.col_y1,
                det.col_y2,
                det.prog_x1,
                det.prog_x2,
            )
            det.col_x1 -= region['left']
            det.col_x2 -= region['left']
            det.col_y1 -= region['top']
            det.col_y2 -= region['top']
            det.prog_x1 -= region['left']
            det.prog_x2 -= region['left']

            result = det.detect_elements(crop, now=frame_time)
            det.col_x1, det.col_x2, det.col_y1, det.col_y2, det.prog_x1, det.prog_x2 = abs_coords
            if result is None:
                continue
            methods.append(result['fish_detect_method'])

        assert methods, "No cropped frames were processed"
        assert det.prev_col_gray is not None, "Detector should retain previous column state across cropped frames"
        assert det.fish_template_grad is not None, "Detector should keep a fish template across cropped frames"
        assert 'inside-template' in methods or 'outside-dip' in methods, \
            f"Expected tracked/template detections in cropped stream, got {methods}"


@requires_frames_1
class TestE2EBarFinding:
    """Test bar finding across multiple frames and recordings."""

    def test_bar_found_on_minigame_frames(self):
        """Bar should be found on all minigame frames (900+)."""
        found_count = 0
        checked = 0
        for i in range(1000, 3000, 100):
            img = load_frame(FRAME_DIR_1, f'{i:06d}')
            if img is None:
                continue
            checked += 1
            det, result = detect_on_frame(img)
            if det is not None:
                found_count += 1

        assert checked > 5, "Not enough frames checked"
        rate = found_count / checked
        assert rate >= 0.90, \
            f"Bar find rate {rate:.0%} < 90% ({found_count}/{checked})"

    @requires_frames_2
    def test_bar_found_on_recording_2(self):
        """Bar should also be found on recording 2 frames."""
        found_count = 0
        checked = 0
        frame_dir = FRAME_DIR_2
        for fname in os.listdir(frame_dir):
            if not fname.endswith('.png'):
                continue
            num = int(fname.replace('.png', ''))
            if num % 200 != 0:  # Sample every 200 frames
                continue
            img = load_frame(frame_dir, fname.replace('.png', ''))
            if img is None:
                continue
            checked += 1
            det, result = detect_on_frame(img)
            if det is not None:
                found_count += 1

        if checked < 3:
            pytest.skip("Not enough frames in recording 2")
        rate = found_count / checked
        assert rate >= 0.80, \
            f"Bar find rate on recording 2: {rate:.0%} < 80%"

    def test_white_box_always_detected_with_bar(self):
        """When bar is found, white box should also be detected."""
        wb_detected = 0
        bar_found = 0
        for i in range(1000, 2500, 50):
            img = load_frame(FRAME_DIR_1, f'{i:06d}')
            if img is None:
                continue
            det, result = detect_on_frame(img)
            if det is None:
                continue
            bar_found += 1
            if result and result['box_bottom'] - result['box_top'] > 0.05:
                wb_detected += 1

        assert bar_found > 5
        rate = wb_detected / bar_found
        assert rate >= 0.95, \
            f"White box detection rate {rate:.0%} < 95% ({wb_detected}/{bar_found})"

    def test_progress_bar_changes_over_game(self):
        """Progress bar should change as the game progresses."""
        progress_values = []
        det = BarDetector()
        for i in range(1000, 4500, 100):
            img = load_frame(FRAME_DIR_1, f'{i:06d}')
            if img is None:
                continue
            if not det.bar_found:
                h, w = img.shape[:2]
                cx, cy = w // 2, h // 2
                mx = int(w * SEARCH_MARGIN_X_FRAC)
                my = int(h * SEARCH_MARGIN_Y_FRAC)
                roi = img[cy - my:cy + my, cx - mx:cx + mx]
                if det.find_bar(roi):
                    det.col_x1 += cx - mx
                    det.col_x2 += cx - mx
                    det.col_y1 += cy - my
                    det.col_y2 += cy - my
                    det.prog_x1 += cx - mx
                    det.prog_x2 += cx - mx
            if det.bar_found:
                result = det.detect_elements(img)
                if result:
                    progress_values.append(result['progress'])

        assert len(progress_values) > 10, "Not enough progress readings"
        # Progress should vary over the game
        assert max(progress_values) - min(progress_values) > 0.1, \
            "Progress bar didn't change significantly"


@requires_frames_1
@requires_calibration
class TestE2EAchievements:
    """Achievement-based tests: high-level success criteria for the system."""

    @pytest.fixture(autouse=True)
    def _load_calibration(self, calibration_data):
        self.cal = calibration_data

    def test_achievement_detection_accuracy_50_percent(self):
        """ACHIEVEMENT: >= 50% of calibrated frames detected within tolerance.

        Single-frame accuracy. Many calibrated frames have the fish inside
        the white box where detection defaults to 0.5. Stream-mode detection
        (with velocity tracking) achieves higher accuracy.
        """
        passed = 0
        total = 0
        for key, entry in self.cal.items():
            if entry['true_fish_y'] is None:
                continue
            frame_dir = os.path.join(
                os.path.dirname(CALIBRATION_FILE), entry['frame_dir']
            )
            img = load_frame(frame_dir, entry['frame_name'])
            if img is None:
                continue
            total += 1
            det, result = detect_on_frame(img)
            if result is None:
                continue
            if abs(result['fish_y'] - entry['true_fish_y']) <= DETECTION_TOLERANCE:
                passed += 1

        assert total > 50, "Need at least 50 calibrated frames"
        rate = passed / total
        assert rate >= 0.50, \
            f"ACHIEVEMENT FAILED: Detection accuracy {rate:.0%} < 50%"

    def test_achievement_no_crashes_across_full_recording(self):
        """ACHIEVEMENT: Zero crashes processing the entire recording."""
        crashes = 0
        processed = 0
        for i in range(900, 4522, 10):
            img = load_frame(FRAME_DIR_1, f'{i:06d}')
            if img is None:
                continue
            processed += 1
            try:
                det, result = detect_on_frame(img)
            except Exception:
                crashes += 1

        assert processed > 100
        assert crashes == 0, f"ACHIEVEMENT FAILED: {crashes} crashes in {processed} frames"

    def test_achievement_bar_finding_95_percent(self):
        """ACHIEVEMENT: Bar should be found in >= 95% of minigame frames."""
        found = 0
        checked = 0
        for i in range(1000, 4000, 25):
            img = load_frame(FRAME_DIR_1, f'{i:06d}')
            if img is None:
                continue
            checked += 1
            det, result = detect_on_frame(img)
            if det is not None:
                found += 1

        assert checked > 50
        rate = found / checked
        assert rate >= 0.95, \
            f"ACHIEVEMENT FAILED: Bar found in {rate:.0%} < 95%"

    def test_achievement_controller_stable_output(self):
        """ACHIEVEMENT: Controller produces table (non-stuck) output
        when fish and box are aligned.

        At ~47% duty cycle, the accumulator-based PWM naturally produces
        frequent transitions (roughly alternating 47/53). This test verifies
        the controller doesn't get stuck in a single state.
        """
        controller = FishingController()
        det = BarDetector()
        det.fish_y = 0.5
        det.box_center = 0.5
        det.box_top = 0.3
        det.box_bottom = 0.7
        det.fish_velocity = 0.0

        outputs = [controller.update(det) for _ in range(100)]
        holds = sum(outputs)
        # Should have a mix of holds and releases (not stuck)
        assert 20 < holds < 80, \
            f"ACHIEVEMENT FAILED: Controller stuck ({holds} holds/100 frames)"
        # Hold ratio should be close to HOVER (~47%)
        assert abs(holds / 100 - controller.HOVER) < 0.15, \
            f"ACHIEVEMENT FAILED: Hold ratio {holds}% far from HOVER {controller.HOVER:.0%}"
