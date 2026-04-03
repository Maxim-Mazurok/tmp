"""Bar detection for the fishing minigame: find bar, detect elements, draw debug."""

import os
import time
import numpy as np
import cv2
from scipy.ndimage import uniform_filter1d

from config import (
    BLUE_H_MIN, BLUE_H_MAX, BLUE_S_MIN,
    WHITE_BOX_SAT_THRESHOLD, FISH_BRIGHTNESS_DROP,
    PROGRESS_H_MIN, PROGRESS_H_MAX, PROGRESS_S_MIN, PROGRESS_V_MIN,
    SEARCH_MARGIN_X_FRAC, SEARCH_MARGIN_Y_FRAC,
    ADVANCED_INSIDE_BOX_DETECTION,
)


class BarDetector:
    """Detects and tracks the fishing minigame bar elements."""

    TEMPLATE_HALF_HEIGHT_FRAC = 0.04
    TEMPLATE_SEARCH_RADIUS_FRAC = 0.12
    TEMPLATE_MIN_SCORE = 0.12
    TRACK_MIN_CONFIDENCE = 0.75
    TRACK_MAX_MISSES = 4
    SHAPE_MATCH_MAX = 1.2
    TEMPLATE_COMPONENT_MIN_AREA = 6
    LK_WINDOW = (9, 9)
    LK_CRITERIA = (
        cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
        10,
        0.03,
    )
    BOOTSTRAP_TEMPLATE = ('2026-03-29 23-47-40', '001205', 0.6772727272727272)
    _BOOTSTRAP_CACHE = None

    VELOCITY_HISTORY_MAX = 20
    VELOCITY_LOOKBACK = 0.10
    DIRECTION_EPSILON = 0.02
    DIRECTION_CONFIRM_FRAMES = 3
    SPEED_BANDS = (0.18, 0.30, 0.60)
    SPEED_BAND_TOLERANCE = 0.12
    SPEED_ESTIMATE_MIN = 0.05
    OBSERVATION_JUMP_LIMIT = 0.08
    OBSERVATION_BLEND_LIMIT = 0.14
    VIRTUAL_FISH_MAX_DT = 0.20
    VIRTUAL_TRACK_MIN_STEP = 0.002
    VIRTUAL_TRACK_CORRECTION_RATE = 0.16
    VIRTUAL_TRACK_CONFIDENT_RATE = 0.28
    VIRTUAL_TRACK_INSIDE_BOX_RATE = 0.10
    VIRTUAL_TRACK_PROGRESS_RATE = 0.08
    VIRTUAL_TRACK_REENTRY_RATE = 1.10
    BOX_INFERENCE_MARGIN_FRAC = 0.18
    BOX_INFERENCE_BIAS = 0.55
    BOX_PROGRESS_BIAS = 0.82
    PROGRESS_RISE_THRESHOLD = 0.003

    def __init__(self, use_advanced_inside_box=ADVANCED_INSIDE_BOX_DETECTION, bootstrap_template=True):
        self.use_advanced_inside_box = use_advanced_inside_box
        self.bootstrap_template = bootstrap_template
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
        self.progress_delta = 0.0
        # Velocity tracking
        self.fish_y_history = []  # list of (time, y) tuples
        self.fish_velocity = 0.0  # positive = moving down
        self.raw_fish_velocity = 0.0
        self.virtual_fish_velocity = 0.0
        self.fish_speed = 0.0
        self.fish_speed_band = 0.0
        self.fish_direction = 0
        self.pending_fish_direction = 0
        self.pending_direction_frames = 0
        self.detected_fish_y = None
        self.inferred_fish_y = 0.5
        self.virtual_fish_source = 'init'
        self.fish_missing_frames = 0
        self.last_fish_update_time = None
        self.fish_template_gray = None
        self.fish_template_grad = None
        self.fish_template_mask = None
        self.fish_template_contour = None
        self.fish_template_x1 = 0
        self.fish_template_x2 = 0
        self.fish_template_center_offset = 0.0
        self.template_source = 'none'
        self.prev_col_gray = None
        self.tracker_points = None
        self.tracker_confidence = 0.0
        self.tracker_misses = 0
        self.last_detection_method = 'none'
        self.last_match_score = 0.0
        self.last_shape_score = 0.0
        self._outside_dip_strength = 0.0
        self.last_tracker_y = None
        self.last_detection_confident = False
        self._last_find_bar_diag = ''
        self._load_bootstrap_template()

    def find_bar(self, img):
        """
        Search for the blue column in a screen capture.
        img: BGR numpy array (can be full screen or search region).
        Returns True if bar found and coordinates updated.
        """
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # --- Pass 1: Find columns with BRIGHT blue/cyan pixels.
        # Only the bar's bright gradient section has these; water/sky are darker.
        # Try progressively lower V thresholds until valid bar groups are found.
        # Higher V thresholds are preferred as they better separate the bar
        # from blue sky in daytime scenes.
        img_h, img_w = img.shape[:2]
        min_bar_width = max(2, int(img_w * 0.01))     # ~1.0% of width
        max_bar_width = max(10, int(img_w * 0.08))     # ~8% of width (bar is wider at low res)

        best_group = None
        best_bright_score = 0

        # Track best candidate for diagnostic logging on failure
        _diag_best_width = 0
        _diag_best_height = 0
        _diag_best_rows = 0
        _diag_fail_reason = 'no-bright-cols'

        for v_thresh in (200, 150, 100, 75, 50):
            bright_mask = cv2.inRange(
                hsv,
                np.array([BLUE_H_MIN, BLUE_S_MIN, v_thresh]),
                np.array([BLUE_H_MAX, 255, 255])
            )
            bright_col_sums = np.sum(bright_mask > 0, axis=0)
            min_bright = max(2, int(img_h * 0.02))
            bright_cols = np.where(bright_col_sums > min_bright)[0]
            if len(bright_cols) < max(2, int(img_w * 0.002)):
                continue

            # Group bright columns
            diffs = np.diff(bright_cols)
            col_gap = max(2, int(img_w * 0.004))  # ~0.4% of width
            splits = np.where(diffs > col_gap)[0]
            groups = np.split(bright_cols, splits + 1)

            for grp in groups:
                width = grp[-1] - grp[0] + 1
                if width < min_bar_width or width > max_bar_width:
                    continue
                bright_score = int(bright_col_sums[grp].sum())

                # Find vertical extent: contiguous rows where >50% of bar
                # columns are bright. Try progressively lower V for row extent.
                strip_hsv = hsv[:, grp[0]:grp[-1] + 1]
                bar_y1 = bar_y2 = -1
                for v_min_row in (150, 100, 75, 50):
                    row_mask = (
                        (strip_hsv[:, :, 0] >= 80) &
                        (strip_hsv[:, :, 0] <= 120) &
                        (strip_hsv[:, :, 1] >= 20) &
                        (strip_hsv[:, :, 2] >= v_min_row)
                    )
                    row_counts = np.sum(row_mask, axis=1)
                    candidate_rows = np.where(row_counts > width * 0.5)[0]
                    if len(candidate_rows) < max(4, int(img_h * 0.01)):
                        continue
                    cr_diffs = np.diff(candidate_rows)
                    row_gap = max(4, int(img_h * 0.02))  # ~2% of height
                    cr_splits = np.where(cr_diffs > row_gap)[0]
                    cr_groups = np.split(candidate_rows, cr_splits + 1)
                    largest = max(cr_groups, key=len)
                    min_rows = max(8, int(img_h * 0.08))
                    if len(largest) >= min_rows:
                        bar_y1 = int(largest[0])
                        bar_y2 = int(largest[-1])
                        break
                    # Track best candidate for diagnostics
                    if len(largest) > _diag_best_rows:
                        _diag_best_rows = len(largest)
                        _diag_best_width = width
                        _diag_best_height = int(largest[-1]) - int(largest[0])
                        _diag_fail_reason = f'rows={len(largest)}<{min_rows}'

                if bar_y1 < 0:
                    if _diag_best_width == 0 and width > 0:
                        _diag_fail_reason = 'no-row-groups'
                    continue
                height = bar_y2 - bar_y1
                if height < width * 5:
                    if height > _diag_best_height:
                        _diag_best_height = height
                        _diag_best_width = width
                        _diag_fail_reason = f'aspect={height}/{width*5}'
                    continue
                if bright_score > best_bright_score:
                    best_bright_score = bright_score
                    all_rows = np.arange(bar_y1, bar_y2 + 1)
                    best_group = (grp, all_rows)

            # If we found a valid group at this V threshold, use it
            # (prefer higher V thresholds)
            if best_group is not None:
                break

        if best_group is None:
            self._last_find_bar_diag = (
                f'img={img_w}x{img_h} '
                f'best_candidate=w{_diag_best_width}/h{_diag_best_height}/rows{_diag_best_rows} '
                f'fail={_diag_fail_reason}'
            )
            return False

        main_group, bar_rows = best_group
        x1 = main_group[0]
        x2 = main_group[-1]
        y1 = bar_rows[0]
        y2 = bar_rows[-1]

        self.col_x1 = x1
        self.col_x2 = x2
        self.col_y1 = y1
        self.col_y2 = y2

        # Progress bar is immediately to the right of the blue column
        bar_width = x2 - x1 + 1
        self.prog_x1 = x2 + 1
        self.prog_x2 = x2 + max(4, int(bar_width * 0.6))  # ~60% of bar width

        self.bar_found = True
        return True

    def detect_elements(self, img, now=None):
        """
        Detect fishscale, white box, and progress from a cropped image
        that contains the bar area.
        img: BGR numpy array of the bar region.
        now: optional timestamp (for testing with fake clocks).
        Returns dict with detection results.
        """
        if now is None:
            now = time.perf_counter()
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
        if col_h < max(8, int(h * 0.02)) or col_w < max(2, int(w * 0.001)):
            return None

        hsv = cv2.cvtColor(col_img, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(col_img, cv2.COLOR_BGR2GRAY)

        white_rows = self._detect_white_box(hsv, col_h)
        new_fish_y = self._detect_fishscale(hsv, gray, white_rows, col_h)
        self._detect_progress(img, w, cy1, cy2, col_h)
        self._update_velocity_tracking(new_fish_y, now, col_h)
        self.prev_col_gray = gray.copy()

        return {
            'fish_y': self.fish_y,
            'detected_fish_y': self.detected_fish_y,
            'inferred_fish_y': self.inferred_fish_y,
            'box_top': self.box_top,
            'box_bottom': self.box_bottom,
            'box_center': self.box_center,
            'progress': self.progress,
            'progress_delta': self.progress_delta,
            'fish_velocity': self.fish_velocity,
            'virtual_fish_velocity': self.virtual_fish_velocity,
            'fish_speed_band': self.fish_speed_band,
            'fish_detect_method': self.last_detection_method,
            'fish_match_score': self.last_match_score,
            'fish_shape_score': self.last_shape_score,
            'tracker_confidence': self.tracker_confidence,
        }

    def _detect_white_box(self, hsv, col_h):
        """Detect the white box region by finding low-saturation rows.

        Returns the array of white row indices.
        """
        row_sat = np.mean(hsv[:, :, 1].astype(float), axis=1)
        white_rows = np.where(row_sat < WHITE_BOX_SAT_THRESHOLD)[0]

        min_wb_rows = max(2, int(col_h * 0.01))
        if len(white_rows) >= min_wb_rows:
            diffs = np.diff(white_rows)
            wb_gap = max(2, int(col_h * 0.015))
            splits = np.where(diffs > wb_gap)[0]
            clusters = np.split(white_rows, splits + 1)
            main_cluster = max(clusters, key=len)
            if len(main_cluster) >= min_wb_rows:
                self.box_top = main_cluster[0] / col_h
                self.box_bottom = main_cluster[-1] / col_h
                self.box_center = (self.box_top + self.box_bottom) / 2

        return white_rows

    def _detect_fishscale(self, hsv, gray, white_rows, col_h):
        """Detect the fishscale icon position using brightness dips.

        Returns the new fish_y value if detected, else None.
        """
        row_brightness = np.mean(gray.astype(float), axis=1)
        row_sat = np.mean(hsv[:, :, 1].astype(float), axis=1)
        tracking_y = self._track_fish(gray, col_h)
        self.last_tracker_y = tracking_y

        min_wb_rows = max(2, int(col_h * 0.01))

        # Build white box row exclusion set
        white_box_rows = set()
        if len(white_rows) >= min_wb_rows:
            wb_expand = max(2, int(col_h * 0.02))
            for wr in white_rows:
                for offset in range(-wb_expand, wb_expand + 1):
                    white_box_rows.add(wr + offset)

        # Smooth brightness to reduce noise
        kernel_size = max(3, int(col_h * 0.02))
        if kernel_size % 2 == 0:
            kernel_size += 1
        if len(row_brightness) > kernel_size:
            smoothed = np.convolve(row_brightness, np.ones(kernel_size) / kernel_size, mode='same')
        else:
            smoothed = row_brightness

        # Local average for dip detection
        window = max(5, col_h // 3)
        if window % 2 == 0:
            window += 1
        local_avg = uniform_filter1d(smoothed, size=window)
        dips = smoothed - local_avg

        fish_min_cluster = max(2, int(col_h * 0.01))
        fish_gap = max(2, int(col_h * 0.02))

        # Pass 1: detect fish OUTSIDE white box (high-confidence)
        new_fish_y = self._detect_fish_outside_box(
            smoothed, row_sat, white_box_rows, col_h, fish_min_cluster, fish_gap
        )
        if new_fish_y is not None:
            self.last_detection_method = 'outside-dip'
            self.last_match_score = min(1.0, 0.5 + 0.5 * self._outside_dip_strength / (2 * FISH_BRIGHTNESS_DROP))
            self.last_shape_score = 0.0
            self.last_detection_confident = True
            self._update_fish_template(gray, new_fish_y, col_h, source='outside-dip')
            self._refresh_tracker(gray, new_fish_y, col_h)
            return new_fish_y

        # Pass 2: prefer tracking + template matching when fish is under the white box.
        if len(white_rows) >= min_wb_rows:
            if self.use_advanced_inside_box:
                template_y, match_score, shape_score = self._detect_fish_inside_box_template(
                    gray, col_h, tracking_y
                )
                if template_y is not None:
                    self.last_detection_method = 'inside-template'
                    self.last_match_score = match_score
                    self.last_shape_score = shape_score
                    self.last_detection_confident = True
                    self._update_fish_template(gray, template_y, col_h, source='inside-template')
                    self._refresh_tracker(gray, template_y, col_h)
                    return template_y

            new_fish_y = self._detect_fish_inside_box_legacy(
                smoothed, col_h, fish_gap
            )
            if new_fish_y is not None:
                self.last_detection_method = 'inside-legacy'
                self.last_match_score = 0.0
                self.last_shape_score = 0.0
                self.last_detection_confident = False
                self._refresh_tracker(gray, new_fish_y, col_h)
                return new_fish_y

        if tracking_y is not None and self.tracker_confidence >= self.TRACK_MIN_CONFIDENCE:
            self.last_detection_method = 'tracker-flow'
            self.last_match_score = self.tracker_confidence
            self.last_shape_score = 0.0
            self.last_detection_confident = False
            return tracking_y

        return new_fish_y

    def _detect_fish_outside_box(self, smoothed, row_sat, white_box_rows, col_h,
                                 fish_min_cluster, fish_gap):
        """Pass 1: Detect fishscale outside the white box using brightness dips + high saturation."""
        # Compute box-corrected dips.  The global baseline (uniform_filter1d
        # with a large window) bleeds the bright white-box signal many rows
        # beyond the box edges, creating strong false dip artifacts.  We
        # replace the box region with a linear interpolation before computing
        # the baseline so dip values near the box reflect the real background.
        has_box = self.box_bottom > self.box_top and bool(white_box_rows)
        window = max(5, col_h // 3)
        if window % 2 == 0:
            window += 1
        if has_box:
            # Extend interpolation beyond box boundaries to cover the full
            # brightness transition zone.  The smoothing kernel spreads the
            # box-edge step over several additional rows, so anchors must
            # sit at true background level.
            transition_margin = max(6, int(col_h * 0.03))
            interp_start = max(1, int(self.box_top * col_h) - transition_margin)
            interp_end = min(col_h - 2, int(self.box_bottom * col_h) + transition_margin)
            corrected = smoothed.copy()
            corrected[interp_start:interp_end + 1] = np.linspace(
                corrected[interp_start - 1], corrected[interp_end + 1],
                interp_end - interp_start + 1
            )
            local_avg = uniform_filter1d(corrected, size=window)
        else:
            local_avg = uniform_filter1d(smoothed, size=window)
        dips = smoothed - local_avg

        dark_rows = np.where(dips < -FISH_BRIGHTNESS_DROP)[0]
        margin = max(3, int(col_h * 0.05))
        dark_rows = dark_rows[
            (dark_rows > margin) &
            (dark_rows < col_h - margin)
        ]
        dark_rows = np.array([
            r for r in dark_rows
            if r not in white_box_rows and row_sat[r] > 70
        ])

        if len(dark_rows) < fish_min_cluster:
            return None

        dr_diffs = np.diff(dark_rows)
        dr_splits = np.where(dr_diffs > fish_gap)[0]
        dr_clusters = np.split(dark_rows, dr_splits + 1)

        best_cluster = None
        best_dip = 0
        for c in dr_clusters:
            if len(c) >= fish_min_cluster:
                cluster_dip = -np.min(dips[c])
                if cluster_dip > best_dip:
                    best_dip = cluster_dip
                    best_cluster = c
        if best_cluster is not None:
            fish_center = (best_cluster[0] + best_cluster[-1]) / 2
            self._outside_dip_strength = best_dip
            return fish_center / col_h
        self._outside_dip_strength = 0.0
        return None

    def _detect_fish_inside_box_legacy(self, smoothed, col_h, fish_gap):
        """Legacy inside-white-box detector using relaxed row-dip thresholds."""
        wb_start = int(self.box_top * col_h)
        wb_end = int(self.box_bottom * col_h)
        wb_margin = max(2, int(col_h * 0.01))
        wb_inner_start = wb_start + wb_margin
        wb_inner_end = wb_end - wb_margin
        wb_min_interior = max(3, int(col_h * 0.02))

        if wb_inner_end <= wb_inner_start + wb_min_interior:
            return None

        wb_brightness = smoothed[wb_inner_start:wb_inner_end]
        wb_win_size = max(5, int(col_h * 0.06))
        wb_win = min(wb_win_size, len(wb_brightness) // 2 * 2 + 1)
        wb_local_avg = uniform_filter1d(wb_brightness, size=wb_win)
        wb_dips = wb_brightness - wb_local_avg

        wb_min_dark = max(2, int(col_h * 0.008))
        wb_dark = np.where(wb_dips < -2.0)[0]
        if len(wb_dark) < wb_min_dark:
            return None

        wd_diffs = np.diff(wb_dark)
        wd_splits = np.where(wd_diffs > fish_gap)[0]
        wd_clusters = np.split(wb_dark, wd_splits + 1)
        best_wb_cluster = None
        best_wb_dip = 0
        for c in wd_clusters:
            if len(c) >= wb_min_dark:
                cluster_dip = -np.min(wb_dips[c])
                if cluster_dip > best_wb_dip:
                    best_wb_dip = cluster_dip
                    best_wb_cluster = c
        if best_wb_cluster is not None:
            wb_fish_center = (best_wb_cluster[0] + best_wb_cluster[-1]) / 2
            return (int(self.box_top * col_h) + max(2, int(col_h * 0.01)) + wb_fish_center) / col_h
        return None

    def _detect_fish_inside_box_template(self, gray, col_h, tracking_y=None):
        """Detect fish under the white box via masked gradient template matching."""
        if self.fish_template_grad is None or self.fish_template_mask is None:
            return None, 0.0, 0.0

        template_h, template_w = self.fish_template_grad.shape[:2]
        if template_h < 3 or template_w < 2:
            return None, 0.0, 0.0

        x1 = max(0, min(self.fish_template_x1, gray.shape[1] - 1))
        x2 = max(x1 + 1, min(self.fish_template_x2, gray.shape[1]))

        predicted_y = self._predict_fish_y()
        target_y = tracking_y if tracking_y is not None else predicted_y
        target_px = int(round(target_y * col_h))
        search_radius = max(template_h, int(col_h * self.TEMPLATE_SEARCH_RADIUS_FRAC))
        wb_start = int(self.box_top * col_h)
        wb_end = int(self.box_bottom * col_h)
        search_top = max(wb_start, target_px - search_radius - template_h // 2)
        search_bottom = min(wb_end, target_px + search_radius + template_h // 2)
        if search_bottom - search_top < template_h:
            return None, 0.0, 0.0

        search_strip = gray[search_top:search_bottom, x1:x2]
        if search_strip.shape[0] < template_h or search_strip.shape[1] != template_w:
            return None, 0.0, 0.0

        search_grad = self._compute_structure_response(search_strip)
        best_score = -1.0
        best_top = None
        for top in range(0, search_grad.shape[0] - template_h + 1):
            candidate_grad = search_grad[top:top + template_h, :]
            score = self._masked_ncc(candidate_grad, self.fish_template_grad, self.fish_template_mask)
            if score > best_score:
                best_score = score
                best_top = top

        if best_top is None or best_score < self.TEMPLATE_MIN_SCORE:
            return None, best_score, 0.0

        candidate_gray = search_strip[best_top:best_top + template_h, :]
        shape_score = self._shape_verify_candidate(candidate_gray)
        if shape_score > self.SHAPE_MATCH_MAX:
            return None, best_score, shape_score

        fish_center = search_top + best_top + self.fish_template_center_offset
        return fish_center / col_h, best_score, shape_score

    def _compute_gradient(self, gray):
        """Compute a gradient-magnitude image for structure-based matching."""
        grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        grad = cv2.magnitude(grad_x, grad_y)
        return grad

    def _compute_structure_response(self, gray):
        """Combine local dark-response and gradient magnitude to emphasize the fish shape."""
        grad = self._compute_gradient(gray)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        dark = np.maximum(blur.astype(np.float32) - gray.astype(np.float32), 0.0)
        return grad + 1.5 * dark

    def _masked_ncc(self, candidate_grad, template_grad, mask):
        """Compute masked normalized cross-correlation for a candidate patch."""
        mask_f = mask.astype(np.float32)
        weight = float(mask_f.sum())
        if weight <= 1.0:
            return -1.0

        candidate = candidate_grad.astype(np.float32)
        template = template_grad.astype(np.float32)
        cand_mean = float((candidate * mask_f).sum() / weight)
        templ_mean = float((template * mask_f).sum() / weight)
        cand_centered = (candidate - cand_mean) * mask_f
        templ_centered = (template - templ_mean) * mask_f
        denom = float(np.linalg.norm(cand_centered) * np.linalg.norm(templ_centered))
        if denom <= 1e-6:
            return -1.0
        return float((cand_centered * templ_centered).sum() / denom)

    def _shape_verify_candidate(self, candidate_gray):
        """Reject template matches whose connected shape differs too much from the fish silhouette."""
        if self.fish_template_contour is None:
            return 0.0

        candidate_mask, _ = self._build_fish_mask(candidate_gray)
        contour = self._largest_contour(candidate_mask)
        if contour is None:
            return 0.0
        return float(cv2.matchShapes(self.fish_template_contour, contour, cv2.CONTOURS_MATCH_I1, 0.0))

    def _build_fish_mask(self, patch_gray):
        """Build a binary fish-shape mask from local dark-response and gradient."""
        blur = cv2.GaussianBlur(patch_gray, (5, 5), 0)
        dark_response = blur.astype(np.float32) - patch_gray.astype(np.float32)
        grad = self._compute_gradient(patch_gray)

        dark_thresh = max(4.0, float(np.percentile(dark_response, 82)))
        grad_thresh = max(6.0, float(np.percentile(grad, 75)))
        dark_mask = (dark_response > dark_thresh).astype(np.uint8) * 255
        grad_mask = (grad > grad_thresh).astype(np.uint8) * 255
        mask = cv2.bitwise_or(dark_mask, grad_mask)
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        border_x = max(2, patch_gray.shape[1] // 8)
        border_y = max(1, patch_gray.shape[0] // 10)
        mask[:, :border_x] = 0
        mask[:, -border_x:] = 0
        mask[:border_y, :] = 0
        mask[-border_y:, :] = 0
        return mask, dark_response

    def _largest_contour(self, binary_mask):
        """Return the largest contour in a binary mask, if any."""
        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        return max(contours, key=cv2.contourArea)

    def _update_fish_template(self, gray, fish_y, col_h, source='dynamic'):
        """Refresh the fish template from a confident detection."""
        template = self._extract_template(gray, fish_y, col_h)
        if template is None:
            return

        self.fish_template_gray = template['gray']
        self.fish_template_grad = template['grad']
        self.fish_template_mask = template['mask']
        self.fish_template_contour = template['contour']
        self.fish_template_x1 = template['x1']
        self.fish_template_x2 = template['x2']
        self.fish_template_center_offset = template['center_offset']
        self.template_source = source

    def _extract_template(self, gray, fish_y, col_h):
        """Extract a fish-centric patch, gradient template, and mask from a confident frame."""
        center_y = int(round(fish_y * col_h))
        half_h = max(5, int(col_h * self.TEMPLATE_HALF_HEIGHT_FRAC))
        y1 = max(0, center_y - half_h)
        y2 = min(gray.shape[0], center_y + half_h + 1)
        patch = gray[y1:y2, :]
        if patch.shape[0] < 5 or patch.shape[1] < 4:
            return None

        mask, dark_response = self._build_fish_mask(patch)
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        best_label = None
        best_score = None
        patch_center_y = patch.shape[0] / 2.0
        for label in range(1, num_labels):
            area = stats[label, cv2.CC_STAT_AREA]
            if area < self.TEMPLATE_COMPONENT_MIN_AREA:
                continue
            top = stats[label, cv2.CC_STAT_TOP]
            height = stats[label, cv2.CC_STAT_HEIGHT]
            center = top + height / 2.0
            score = abs(center - patch_center_y)
            if best_score is None or score < best_score:
                best_score = score
                best_label = label

        if best_label is None:
            return None

        ys, xs = np.where(labels == best_label)
        if xs.size == 0 or ys.size == 0:
            return None
        x1 = max(0, int(xs.min()) - 2)
        x2 = min(gray.shape[1], int(xs.max()) + 3)
        y1_local = max(0, int(ys.min()) - 2)
        y2_local = min(patch.shape[0], int(ys.max()) + 3)
        fish_patch = patch[y1_local:y2_local, x1:x2]
        if fish_patch.shape[0] < 5 or fish_patch.shape[1] < 2:
            return None

        fish_mask = (labels[y1_local:y2_local, x1:x2] == best_label).astype(np.uint8) * 255
        contour = self._largest_contour(fish_mask)
        if contour is None:
            return None
        center_offset = float(np.where(fish_mask > 0)[0].mean())

        return {
            'gray': fish_patch,
            'grad': self._compute_structure_response(fish_patch),
            'mask': fish_mask,
            'contour': contour,
            'x1': x1,
            'x2': x2,
            'center_offset': center_offset,
        }

    def _predict_fish_y(self):
        """Predict fish position from recent motion history."""
        velocity = self._virtual_prediction_velocity()
        return max(0.0, min(1.0, self.fish_y + velocity * self.VELOCITY_LOOKBACK))

    def _load_bootstrap_template(self):
        """Load a starter template from a known-good calibration frame when available."""
        if not self.bootstrap_template:
            return
        if BarDetector._BOOTSTRAP_CACHE is None:
            BarDetector._BOOTSTRAP_CACHE = self._build_bootstrap_template()
        cache = BarDetector._BOOTSTRAP_CACHE
        if cache is None:
            return
        self.fish_template_gray = cache['gray'].copy()
        self.fish_template_grad = cache['grad'].copy()
        self.fish_template_mask = cache['mask'].copy()
        self.fish_template_contour = cache['contour'].copy()
        self.fish_template_x1 = cache['x1']
        self.fish_template_x2 = cache['x2']
        self.fish_template_center_offset = cache['center_offset']
        self.template_source = 'bootstrap'

    def _build_bootstrap_template(self):
        """Build a fish template from a known-good calibration frame if it exists in the repo."""
        frame_dir, frame_name, fish_y = self.BOOTSTRAP_TEMPLATE
        root = os.path.dirname(__file__)
        frame_path = os.path.join(root, frame_dir, f'{frame_name}.png')
        if not os.path.exists(frame_path):
            return None

        img = cv2.imread(frame_path)
        if img is None:
            return None

        temp_detector = BarDetector(use_advanced_inside_box=False, bootstrap_template=False)
        h, w = img.shape[:2]
        cx, cy = w // 2, h // 2
        mx = int(w * SEARCH_MARGIN_X_FRAC)
        my = int(h * SEARCH_MARGIN_Y_FRAC)
        roi = img[cy - my:cy + my, cx - mx:cx + mx]
        if not temp_detector.find_bar(roi):
            return None
        temp_detector.col_x1 += cx - mx
        temp_detector.col_x2 += cx - mx
        temp_detector.col_y1 += cy - my
        temp_detector.col_y2 += cy - my

        col_img = img[temp_detector.col_y1:temp_detector.col_y2 + 1,
                      temp_detector.col_x1:temp_detector.col_x2 + 1]
        gray = cv2.cvtColor(col_img, cv2.COLOR_BGR2GRAY)
        col_h = gray.shape[0]
        return temp_detector._extract_template(gray, fish_y, col_h)

    def _refresh_tracker(self, gray, fish_y, col_h):
        """(Re)initialize LK tracking features around the latest confident fish position."""
        center_y = int(round(fish_y * col_h))
        half_h = max(5, int(col_h * self.TEMPLATE_HALF_HEIGHT_FRAC))
        y1 = max(0, center_y - half_h)
        y2 = min(gray.shape[0], center_y + half_h + 1)
        if y2 - y1 < 5:
            return

        mask = np.zeros_like(gray, dtype=np.uint8)
        x1 = max(0, self.fish_template_x1)
        x2 = min(gray.shape[1], max(x1 + 1, self.fish_template_x2))
        mask[y1:y2, x1:x2] = 255
        points = cv2.goodFeaturesToTrack(gray, maxCorners=6, qualityLevel=0.01, minDistance=2, mask=mask)
        if points is None:
            points = np.array([[[float((x1 + x2) / 2.0), float(center_y)]]], dtype=np.float32)
        self.tracker_points = points.astype(np.float32)
        self.tracker_confidence = min(1.0, len(self.tracker_points) / 3.0)
        self.tracker_misses = 0

    def _track_fish(self, gray, col_h):
        """Track the fish vertically through ambiguous frames with Lucas-Kanade optical flow."""
        if self.prev_col_gray is None or self.tracker_points is None or not self.last_detection_confident:
            return None

        next_points, status, _err = cv2.calcOpticalFlowPyrLK(
            self.prev_col_gray,
            gray,
            self.tracker_points,
            None,
            winSize=self.LK_WINDOW,
            maxLevel=1,
            criteria=self.LK_CRITERIA,
        )
        if next_points is None or status is None:
            self.tracker_misses += 1
            return None

        good_new = next_points[status.flatten() == 1]
        if good_new.size == 0:
            self.tracker_misses += 1
            if self.tracker_misses >= self.TRACK_MAX_MISSES:
                self.tracker_points = None
            return None

        good_new = good_new.reshape(-1, 2)
        in_bounds = (
            (good_new[:, 0] >= 0) & (good_new[:, 0] < gray.shape[1]) &
            (good_new[:, 1] >= 0) & (good_new[:, 1] < gray.shape[0])
        )
        good_new = good_new[in_bounds]
        if good_new.size == 0:
            self.tracker_misses += 1
            return None

        self.tracker_points = good_new.reshape(-1, 1, 2).astype(np.float32)
        self.tracker_confidence = min(1.0, len(good_new) / 3.0)
        self.tracker_misses = 0
        return float(np.median(good_new[:, 1]) / max(col_h, 1))

    def _update_velocity_tracking(self, new_fish_y, now, col_h):
        """Update observed and inferred fish motion state."""
        dt = 0.0
        predicted_y = self.fish_y
        if self.last_fish_update_time is not None:
            dt = max(0.0, min(now - self.last_fish_update_time, self.VIRTUAL_FISH_MAX_DT))
            predicted_y = self._predict_virtual_position(dt)
        self.inferred_fish_y = predicted_y

        if new_fish_y is not None:
            self.fish_y_history.append((now, new_fish_y))
            self.fish_y_history = self.fish_y_history[-self.VELOCITY_HISTORY_MAX:]

            recent_velocity = self._estimate_recent_velocity(now)
            if recent_velocity is not None:
                self.raw_fish_velocity = recent_velocity
                self.fish_velocity = self._confirm_direction_change(recent_velocity)
                self._update_speed_model(recent_velocity)

            self.detected_fish_y = new_fish_y
            self.fish_missing_frames = 0
            self.fish_y = self._resolve_virtual_observation(new_fish_y, predicted_y, dt)
            if abs(self.fish_y - new_fish_y) <= 0.01:
                self.virtual_fish_source = self.last_detection_method
            else:
                self.virtual_fish_source = f'blend-{self.last_detection_method}'
        else:
            self.last_detection_confident = False
            self.detected_fish_y = None
            self.fish_missing_frames += 1
            self.fish_y = self._infer_missing_fish(predicted_y)

        self.virtual_fish_velocity = self._virtual_prediction_velocity()
        self.last_fish_update_time = now

    def _classify_direction(self, velocity):
        """Classify a velocity into up/down/steady buckets."""
        if velocity > self.DIRECTION_EPSILON:
            return 1
        if velocity < -self.DIRECTION_EPSILON:
            return -1
        return 0

    def _confirm_direction_change(self, recent_velocity):
        """Require several consecutive frames before accepting a fish direction flip."""
        candidate_direction = self._classify_direction(recent_velocity)

        if self.fish_direction == 0 or candidate_direction == 0:
            self.fish_direction = candidate_direction
            self.pending_fish_direction = 0
            self.pending_direction_frames = 0
            return recent_velocity

        if candidate_direction == self.fish_direction:
            self.pending_fish_direction = 0
            self.pending_direction_frames = 0
            return recent_velocity

        if candidate_direction == self.pending_fish_direction:
            self.pending_direction_frames += 1
        else:
            self.pending_fish_direction = candidate_direction
            self.pending_direction_frames = 1

        if self.pending_direction_frames >= self.DIRECTION_CONFIRM_FRAMES:
            self.fish_direction = candidate_direction
            self.pending_fish_direction = 0
            self.pending_direction_frames = 0
            return recent_velocity

        # Keep the last confirmed direction until the flip is stable.
        return abs(recent_velocity) * self.fish_direction

    def _estimate_recent_velocity(self, now):
        """Estimate fish velocity from the most recent stable motion window."""
        if len(self.fish_y_history) < 2:
            return None

        latest_t, latest_y = self.fish_y_history[-1]
        anchor = None
        for sample_t, sample_y in reversed(self.fish_y_history[:-1]):
            if now - sample_t >= self.VELOCITY_LOOKBACK:
                anchor = (sample_t, sample_y)
                break

        if anchor is None:
            anchor = self.fish_y_history[-2]

        dt = latest_t - anchor[0]
        if dt <= 0:
            return None

        return (latest_y - anchor[1]) / dt

    def _snap_speed_band(self, speed):
        """Snap stable fish speeds to the dominant bands seen in recordings when close enough."""
        if speed < self.SPEED_ESTIMATE_MIN:
            return 0.0

        nearest = min(self.SPEED_BANDS, key=lambda band: abs(band - speed))
        if abs(nearest - speed) <= self.SPEED_BAND_TOLERANCE:
            return nearest
        return speed

    def _update_speed_model(self, velocity):
        """Keep a stable speed estimate for virtual fish carry-forward."""
        speed = abs(velocity)
        if speed < self.SPEED_ESTIMATE_MIN:
            return

        snapped_speed = self._snap_speed_band(speed)
        if self.fish_speed <= 0.0:
            self.fish_speed = snapped_speed
        else:
            self.fish_speed = 0.65 * self.fish_speed + 0.35 * snapped_speed
        self.fish_speed_band = self._snap_speed_band(self.fish_speed)

    def _virtual_motion_direction(self):
        """Prefer the freshest raw direction, then fall back to confirmed direction."""
        raw_direction = self._classify_direction(self.raw_fish_velocity)
        if raw_direction != 0:
            return raw_direction
        if self.fish_direction != 0:
            return self.fish_direction
        return self._classify_direction(self.fish_velocity)

    def _virtual_prediction_velocity(self):
        """Predict fish motion using stable speed with the freshest plausible direction."""
        direction = self._virtual_motion_direction()
        raw_speed = abs(self.raw_fish_velocity)
        confirmed_speed = abs(self.fish_velocity)
        speed = self.fish_speed_band or self.fish_speed
        if speed < self.SPEED_ESTIMATE_MIN:
            if raw_speed >= self.SPEED_ESTIMATE_MIN:
                speed = raw_speed
            elif confirmed_speed >= self.SPEED_ESTIMATE_MIN:
                speed = confirmed_speed
            else:
                speed = 0.0

        if direction == 0:
            if raw_speed >= self.SPEED_ESTIMATE_MIN:
                return self.raw_fish_velocity
            if confirmed_speed >= self.SPEED_ESTIMATE_MIN:
                return self.fish_velocity
            return 0.0

        return direction * speed

    def _predict_virtual_position(self, dt):
        """Advance the virtual fish position using the stable motion model."""
        predicted = self.fish_y + self._virtual_prediction_velocity() * dt
        return max(0.0, min(1.0, predicted))

    def _observation_confidence(self, method):
        """Map fish detection methods to how much we should trust them against the prior track."""
        if method == 'outside-dip':
            return 1.0
        if method == 'inside-template':
            return 0.85
        if method == 'tracker-flow':
            return 0.70
        if method == 'inside-legacy':
            return 0.45
        return 0.0

    def _box_target(self, y_value):
        """Return a conservative in-box target for inferred fish positions."""
        if self.box_bottom <= self.box_top:
            return None

        box_height = self.box_bottom - self.box_top
        inner_margin = min(0.02, box_height * self.BOX_INFERENCE_MARGIN_FRAC)
        inner_top = self.box_top + inner_margin
        inner_bottom = self.box_bottom - inner_margin
        if inner_bottom <= inner_top:
            return self.box_center
        return max(inner_top, min(inner_bottom, y_value))

    def _near_or_inside_box(self, y_value, margin=0.04):
        """Check whether a position is plausibly inside the white box region."""
        return self.box_top - margin <= y_value <= self.box_bottom + margin

    def _observation_correction_rate(self, observed_y):
        """Return how quickly the virtual fish may be pulled toward an observation."""
        method = self.last_detection_method
        if method == 'outside-dip':
            rate = self.VIRTUAL_TRACK_CONFIDENT_RATE
        elif method == 'inside-template':
            rate = 0.18
        elif method == 'tracker-flow':
            rate = 0.14
        elif method == 'inside-legacy':
            rate = 0.10
        else:
            rate = self.VIRTUAL_TRACK_CORRECTION_RATE

        if self._near_or_inside_box(observed_y, margin=0.02):
            rate = min(rate, self.VIRTUAL_TRACK_INSIDE_BOX_RATE)
        if self.progress_delta > self.PROGRESS_RISE_THRESHOLD:
            rate = min(rate, self.VIRTUAL_TRACK_PROGRESS_RATE)
        return rate

    def _bounded_virtual_correction(self, predicted_y, observed_y, dt):
        """Nudge the virtual fish toward an observation without letting it mirror frame noise."""
        delta = observed_y - predicted_y
        if abs(delta) <= 1e-6:
            return max(0.0, min(1.0, observed_y))

        rate = self._observation_correction_rate(observed_y)
        if self._near_or_inside_box(observed_y, margin=0.0) and not self._near_or_inside_box(predicted_y, margin=0.0):
            rate = max(rate, self.VIRTUAL_TRACK_REENTRY_RATE)
        max_step = max(self.VIRTUAL_TRACK_MIN_STEP, rate * max(dt, 1.0 / 60.0))
        correction = np.sign(delta) * min(abs(delta), max_step)
        return max(0.0, min(1.0, predicted_y + correction))

    def _resolve_virtual_observation(self, observed_y, predicted_y, dt):
        """Blend weak detections with the prior virtual track instead of hard-snapping."""
        confidence = self._observation_confidence(self.last_detection_method)
        if self.last_fish_update_time is None:
            return max(0.0, min(1.0, observed_y))

        if confidence >= 0.95:
            return self._bounded_virtual_correction(predicted_y, observed_y, dt)

        if self._near_or_inside_box(observed_y, margin=0.0) and not self._near_or_inside_box(predicted_y, margin=0.0):
            return self._bounded_virtual_correction(predicted_y, observed_y, dt)

        delta = observed_y - predicted_y
        if abs(delta) <= self.OBSERVATION_JUMP_LIMIT:
            return self._bounded_virtual_correction(predicted_y, observed_y, dt)

        if abs(delta) <= self.OBSERVATION_BLEND_LIMIT:
            blend = 0.35 + 0.5 * confidence
            resolved = predicted_y + delta * blend
        else:
            resolved = predicted_y + np.sign(delta) * self.OBSERVATION_JUMP_LIMIT

        if confidence < 0.9 and self.progress_delta > self.PROGRESS_RISE_THRESHOLD:
            box_target = self._box_target(resolved)
            if box_target is not None:
                resolved = 0.4 * resolved + 0.6 * box_target

        return self._bounded_virtual_correction(predicted_y, resolved, dt)

    def _infer_missing_fish(self, predicted_y):
        """Infer the fish position across ambiguous frames without letting it teleport."""
        inferred = predicted_y
        box_target = self._box_target(predicted_y)

        assume_in_box = False
        if box_target is not None:
            assume_in_box = (
                self.progress_delta > self.PROGRESS_RISE_THRESHOLD or
                self._near_or_inside_box(self.fish_y) or
                self._near_or_inside_box(predicted_y) or
                self.virtual_fish_source.startswith('inside') or
                self.virtual_fish_source.startswith('box-assume')
            )

        if box_target is not None and assume_in_box:
            bias = self.BOX_PROGRESS_BIAS if self.progress_delta > self.PROGRESS_RISE_THRESHOLD else self.BOX_INFERENCE_BIAS
            inferred = (1.0 - bias) * predicted_y + bias * box_target
            self.last_detection_method = 'box-assume-progress' if self.progress_delta > self.PROGRESS_RISE_THRESHOLD else 'box-assume'
            self.virtual_fish_source = self.last_detection_method
        else:
            self.last_detection_method = 'velocity-predict'
            self.virtual_fish_source = 'velocity-predict'

        return max(0.0, min(1.0, inferred))

    def _detect_progress(self, img, w, cy1, cy2, col_h):
        """Detect progress bar fill level from red/orange pixels."""
        previous_progress = self.progress
        new_progress = previous_progress
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
            row_fill = np.sum(red_mask > 0, axis=1)
            prog_w = px2 - px1
            filled_rows = np.sum(row_fill > max(1, prog_w * 0.1))
            new_progress = filled_rows / max(col_h, 1)

        self.progress_delta = new_progress - previous_progress
        self.progress = new_progress

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

        # Draw the controller-facing virtual fish track on the right half of the bar.
        virtual_abs_y = cy1 + int(self.fish_y * col_h)
        cv2.line(vis, (cx1, virtual_abs_y), (cx2 + 8, virtual_abs_y), (0, 255, 0), 3)

        # Draw the carry-forward inference from prior speed and direction (orange).
        inferred_abs_y = cy1 + int(self.inferred_fish_y * col_h)
        cv2.line(vis, (cx1 - 3, inferred_abs_y), (cx2 + 3, inferred_abs_y), (0, 165, 255), 1)

        # Draw the directly observed fish position on the left half of the bar.
        if self.detected_fish_y is not None:
            observed_abs_y = cy1 + int(self.detected_fish_y * col_h)
            cv2.line(vis, (cx1 - 8, observed_abs_y), (cx2, observed_abs_y), (0, 0, 255), 3)

        # Draw progress bar bounds
        px1, px2 = self.prog_x1, self.prog_x2
        cv2.rectangle(vis, (px1, cy1), (px2, cy2), (0, 128, 255), 1)

        # Progress fill level
        prog_y = cy2 - int(self.progress * col_h)
        cv2.line(vis, (px1, prog_y), (px2, prog_y), (0, 255, 255), 1)

        # Text overlay
        info_x = cx2 + 25
        observed_text = 'n/a' if self.detected_fish_y is None else f'{self.detected_fish_y:.2f}'
        cv2.putText(vis, f"Obs: {observed_text}", (info_x, cy1 + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
        cv2.putText(vis, f"Inf: {self.inferred_fish_y:.2f}", (info_x, cy1 + 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 165, 255), 1)
        cv2.putText(vis, f"Use: {self.fish_y:.2f}", (info_x, cy1 + 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
        cv2.putText(vis, f"Box: {self.box_top:.2f}-{self.box_bottom:.2f}", (info_x, cy1 + 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        cv2.putText(vis, f"Progress: {self.progress:.0%}", (info_x, cy1 + 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        cv2.putText(vis, f"Vel: {self.fish_velocity:+.3f} / {self.virtual_fish_velocity:+.3f}", (info_x, cy1 + 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 128, 255), 1)

        return vis


def detect_on_frame(img, detector=None):
    """Run full detection pipeline on an image: find_bar in center ROI + detect_elements.

    This is the canonical DRY utility for frame-based detection used by tests,
    calibration tools, and standalone scripts.

    Returns (detector, result) or (None, None) if bar not found.
    """
    if detector is None:
        detector = BarDetector()
    h, w = img.shape[:2]
    cx, cy = w // 2, h // 2
    mx = int(w * SEARCH_MARGIN_X_FRAC)
    my = int(h * SEARCH_MARGIN_Y_FRAC)
    roi = img[cy - my:cy + my, cx - mx:cx + mx]
    if not detector.find_bar(roi):
        return None, None
    detector.col_x1 += cx - mx
    detector.col_x2 += cx - mx
    detector.col_y1 += cy - my
    detector.col_y2 += cy - my
    detector.prog_x1 += cx - mx
    detector.prog_x2 += cx - mx
    result = detector.detect_elements(img)
    return detector, result
