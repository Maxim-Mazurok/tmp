"""Bar detection for the fishing minigame: find bar, detect elements, draw debug."""

import time
import numpy as np
import cv2
from scipy.ndimage import uniform_filter1d

from config import (
    BLUE_H_MIN, BLUE_H_MAX, BLUE_S_MIN,
    WHITE_BOX_SAT_THRESHOLD, FISH_BRIGHTNESS_DROP,
    PROGRESS_H_MIN, PROGRESS_H_MAX, PROGRESS_S_MIN, PROGRESS_V_MIN,
    SEARCH_MARGIN_X_FRAC, SEARCH_MARGIN_Y_FRAC,
)


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

        # --- Pass 1: Find columns with BRIGHT blue/cyan pixels.
        # Only the bar's bright gradient section has these; water/sky are darker.
        # Try progressively lower V thresholds until valid bar groups are found.
        # Higher V thresholds are preferred as they better separate the bar
        # from blue sky in daytime scenes.
        img_h, img_w = img.shape[:2]
        min_bar_width = max(2, int(img_w * 0.01))     # ~1.0% of width
        max_bar_width = max(10, int(img_w * 0.05))     # ~5% of width

        best_group = None
        best_bright_score = 0

        for v_thresh in (200, 150, 100, 75):
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
                for v_min_row in (150, 100, 75):
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
                    row_gap = max(4, int(img_h * 0.015))  # ~1.5% of height
                    cr_splits = np.where(cr_diffs > row_gap)[0]
                    cr_groups = np.split(candidate_rows, cr_splits + 1)
                    largest = max(cr_groups, key=len)
                    min_rows = max(8, int(img_h * 0.12))
                    if len(largest) >= min_rows:
                        bar_y1 = int(largest[0])
                        bar_y2 = int(largest[-1])
                        break

                if bar_y1 < 0:
                    continue
                height = bar_y2 - bar_y1
                if height < width * 8:
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
        self._update_velocity_tracking(new_fish_y, now, col_h)
        self._detect_progress(img, w, cy1, cy2, col_h)

        return {
            'fish_y': self.fish_y,
            'box_top': self.box_top,
            'box_bottom': self.box_bottom,
            'box_center': self.box_center,
            'progress': self.progress,
            'fish_velocity': self.fish_velocity,
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
            dips, row_sat, white_box_rows, col_h, fish_min_cluster, fish_gap
        )

        # Pass 2: detect fish INSIDE white box (relaxed thresholds)
        if new_fish_y is None and len(white_rows) >= min_wb_rows:
            new_fish_y = self._detect_fish_inside_box(
                smoothed, col_h, fish_gap
            )

        return new_fish_y

    def _detect_fish_outside_box(self, dips, row_sat, white_box_rows, col_h,
                                 fish_min_cluster, fish_gap):
        """Pass 1: Detect fishscale outside the white box using brightness dips + high saturation."""
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
            return fish_center / col_h
        return None

    def _detect_fish_inside_box(self, smoothed, col_h, fish_gap):
        """Pass 2: Detect fishscale inside the white box using relaxed thresholds."""
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

    def _update_velocity_tracking(self, new_fish_y, now, col_h):
        """Update fish position and velocity from detection result or prediction."""
        if new_fish_y is not None:
            self.fish_y_history.append((now, new_fish_y))
            self.fish_y_history = self.fish_y_history[-20:]

            if len(self.fish_y_history) >= 2:
                t0, y0 = self.fish_y_history[0]
                t1, y1 = self.fish_y_history[-1]
                dt = t1 - t0
                if dt > 0.03:
                    self.fish_velocity = (y1 - y0) / dt
                else:
                    dt2 = t1 - self.fish_y_history[-2][0]
                    if dt2 > 0:
                        self.fish_velocity = (y1 - self.fish_y_history[-2][1]) / dt2

            self.fish_y = new_fish_y
        else:
            # Fish not found — use velocity prediction
            if len(self.fish_y_history) >= 2:
                last_t, last_y = self.fish_y_history[-1]
                dt = now - last_t
                if dt < 2.0 and abs(self.fish_velocity) > 0.001:
                    predicted = last_y + self.fish_velocity * dt
                    self.fish_y = max(0.0, min(1.0, predicted))

    def _detect_progress(self, img, w, cy1, cy2, col_h):
        """Detect progress bar fill level from red/orange pixels."""
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
            self.progress = filled_rows / max(col_h, 1)

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
