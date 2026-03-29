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
import traceback
import ctypes
import ctypes.wintypes
import numpy as np
import cv2
import mss

# Only import pydirectinput when actually controlling (not in test mode)
pydirectinput = None

# ─── Configuration ──────────────────────────────────────────────────────

# Search region margins as fraction of game window size
SEARCH_MARGIN_X_FRAC = 0.30  # 30% of game width from center
SEARCH_MARGIN_Y_FRAC = 0.45  # 45% of game height from center

# HSV thresholds for blue column detection
BLUE_H_MIN, BLUE_H_MAX = 85, 115
BLUE_S_MIN = 25
BLUE_V_MIN = 20  # Live game bar can be very dark (V=20-60 in unfilled areas)

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
CONTROL_HZ = 60        # control loop frequency during minigame

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

        # --- Pass 1: Find columns with BRIGHT blue/cyan pixels.
        # Only the bar's bright gradient section has these; water/sky are darker.
        # Try progressively lower V thresholds until valid bar groups are found.
        # Higher V thresholds are preferred as they better separate the bar
        # from blue sky in daytime scenes.
        img_w = img.shape[1]
        min_bar_width = max(5, int(img_w * 0.003))    # ~0.3% of width
        max_bar_width = max(50, int(img_w * 0.05))     # ~5% of width

        best_group = None
        best_bright_score = 0

        for v_thresh in (200, 150, 100, 75):
            bright_mask = cv2.inRange(
                hsv,
                np.array([BLUE_H_MIN, BLUE_S_MIN, v_thresh]),
                np.array([BLUE_H_MAX, 255, 255])
            )
            bright_col_sums = np.sum(bright_mask > 0, axis=0)
            min_bright = max(5, int(img.shape[0] * 0.02))
            bright_cols = np.where(bright_col_sums > min_bright)[0]
            if len(bright_cols) < 3:
                continue

            # Group bright columns
            diffs = np.diff(bright_cols)
            splits = np.where(diffs > 5)[0]
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
                    if len(candidate_rows) < 10:
                        continue
                    cr_diffs = np.diff(candidate_rows)
                    cr_splits = np.where(cr_diffs > 20)[0]
                    cr_groups = np.split(candidate_rows, cr_splits + 1)
                    largest = max(cr_groups, key=len)
                    min_rows = max(20, int(img.shape[0] * 0.04))
                    if len(largest) >= min_rows:
                        bar_y1 = int(largest[0])
                        bar_y2 = int(largest[-1])
                        break

                if bar_y1 < 0:
                    continue
                height = bar_y2 - bar_y1
                if height < width * 3:
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
        self.prog_x1 = x2 + 1
        self.prog_x2 = x2 + 20  # approximately 16-20px wide

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

        # --- Pass 1: detect fish OUTSIDE white box (high-confidence) ---
        dark_rows = np.where(dips < -FISH_BRIGHTNESS_DROP)[0]
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

        fish_detected = False
        new_fish_y = None

        if len(dark_rows) >= FISH_MIN_CLUSTER_SIZE:
            dr_diffs = np.diff(dark_rows)
            dr_splits = np.where(dr_diffs > 5)[0]
            dr_clusters = np.split(dark_rows, dr_splits + 1)
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
                fish_detected = True

        # --- Pass 2: detect fish INSIDE white box (relaxed thresholds) ---
        if not fish_detected and len(white_rows) >= 3:
            # Inside white box: sat is low (~20-30), brightness dip is subtle.
            # Strategy: try mean-based detection first (works for moderate cases),
            # then fall back to percentile-based (catches faint fish).
            wb_start = int(self.box_top * col_h)
            wb_end = int(self.box_bottom * col_h)
            wb_margin = 3
            wb_inner_start = wb_start + wb_margin
            wb_inner_end = wb_end - wb_margin

            if wb_inner_end > wb_inner_start + 5:
                # --- Pass 2a: mean-based WB detection (moderate cases) ---
                wb_brightness = smoothed[wb_inner_start:wb_inner_end]
                wb_win = min(15, len(wb_brightness) // 2 * 2 + 1)
                wb_local_avg = uniform_filter1d(wb_brightness, size=wb_win)
                wb_dips = wb_brightness - wb_local_avg

                # Much lower threshold for white box interior
                wb_dark = np.where(wb_dips < -2.0)[0]
                if len(wb_dark) >= 2:
                    # Cluster the dark rows
                    wd_diffs = np.diff(wb_dark)
                    wd_splits = np.where(wd_diffs > 5)[0]
                    wd_clusters = np.split(wb_dark, wd_splits + 1)
                    best_wb_cluster = None
                    best_wb_dip = 0
                    for c in wd_clusters:
                        if len(c) >= 2:
                            cluster_dip = -np.min(wb_dips[c])
                            if cluster_dip > best_wb_dip:
                                best_wb_dip = cluster_dip
                                best_wb_cluster = c
                    if best_wb_cluster is not None:
                        wb_fish_center = (best_wb_cluster[0] + best_wb_cluster[-1]) / 2
                        new_fish_y = (wb_inner_start + wb_fish_center) / col_h
                        fish_detected = True

        if fish_detected and new_fish_y is not None:
            # Update velocity tracking
            self.fish_y_history.append((now, new_fish_y))
            # Keep last 20 samples for stable velocity estimation
            self.fish_y_history = self.fish_y_history[-20:]

            # Compute velocity over a wider window to avoid quantization noise.
            # Fish position is quantized (~0.006 steps), so frame-to-frame
            # velocity fluctuates wildly between 0 and ~0.36/s.
            # Using first-to-last of history gives a stable estimate.
            if len(self.fish_y_history) >= 2:
                t0, y0 = self.fish_y_history[0]
                t1, y1 = self.fish_y_history[-1]
                dt = t1 - t0
                if dt > 0.03:  # need at least ~2 frames for stable estimate
                    self.fish_velocity = (y1 - y0) / dt
                else:
                    # Very short window, use last 2
                    dt2 = t1 - self.fish_y_history[-2][0]
                    if dt2 > 0:
                        self.fish_velocity = (y1 - self.fish_y_history[-2][1]) / dt2

            self.fish_y = new_fish_y

        if not fish_detected:
            # Fish not found by either pass.
            # Use velocity prediction — fish speed is constant between direction
            # changes, so prediction stays valid for longer than 300ms.
            if len(self.fish_y_history) >= 2:
                last_t, last_y = self.fish_y_history[-1]
                dt = now - last_t
                if dt < 2.0 and abs(self.fish_velocity) > 0.001:
                    predicted = last_y + self.fish_velocity * dt
                    self.fish_y = max(0.0, min(1.0, predicted))
            # else: keep last known fish_y (stale but avoids wild jumps)

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

def find_game_window(title_part='fivem'):
    """Find the FiveM game window and return its DPI-aware screen rect."""
    # Make process DPI-aware to get correct coordinates
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

    user32 = ctypes.windll.user32
    results = []

    def callback(hwnd, _):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if title_part.lower() in buf.value.lower():
                rect = ctypes.wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                if w > 100 and h > 100:  # Skip tiny windows
                    results.append({
                        'hwnd': hwnd,
                        'title': buf.value,
                        'left': rect.left,
                        'top': rect.top,
                        'width': w,
                        'height': h,
                    })
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(callback), 0)

    if not results:
        return None
    # Pick the largest window if multiple matches
    return max(results, key=lambda r: r['width'] * r['height'])


class ScreenCapture:
    """Fast screen capture using mss, targeting the game window."""

    def __init__(self, game_window=None):
        self.sct = mss.mss()
        if game_window:
            self._region = game_window  # dict with left, top, width, height
        else:
            self._region = self.sct.monitors[1]  # Fallback to primary monitor
        print(f"[*] Capture region: {self._region['width']}x{self._region['height']} "
              f"at ({self._region['left']},{self._region['top']})")

    def capture_search_region(self):
        """Capture center region of the game window for initial bar search."""
        gw = self._region['width']
        gh = self._region['height']
        margin_x = int(gw * SEARCH_MARGIN_X_FRAC)
        margin_y = int(gh * SEARCH_MARGIN_Y_FRAC)

        cx = self._region['left'] + gw // 2
        cy = self._region['top'] + gh // 2
        region = {
            'left': cx - margin_x,
            'top': cy - margin_y,
            'width': margin_x * 2,
            'height': margin_y * 2,
        }
        screenshot = self.sct.grab(region)
        img = np.array(screenshot)[:, :, :3]  # BGRA → BGR
        return img, region

    def capture_bar_region(self, detector, padding=15):
        """Capture just the bar area for fast updates."""
        region = {
            'left': int(detector.col_x1 - padding),
            'top': int(detector.col_y1 - padding),
            'width': int((detector.prog_x2 - detector.col_x1) + padding * 2 + 30),
            'height': int((detector.col_y2 - detector.col_y1) + padding * 2),
        }
        if region['width'] <= 0 or region['height'] <= 0:
            raise ValueError(
                f"Invalid region dimensions: {region} "
                f"bar=[{detector.col_x1},{detector.col_y1}]-[{detector.col_x2},{detector.col_y2}] "
                f"prog_x2={detector.prog_x2}"
            )
        try:
            screenshot = self.sct.grab(region)
        except Exception as e:
            # Retry once with a fresh mss instance (handles stale GDI resources)
            try:
                self.sct = mss.mss()
                screenshot = self.sct.grab(region)
            except Exception as e2:
                raise RuntimeError(
                    f"mss.grab failed (2 attempts): {type(e).__name__}:{e} / "
                    f"{type(e2).__name__}:{e2} region={region} "
                    f"bar=[{detector.col_x1},{detector.col_y1}]-[{detector.col_x2},{detector.col_y2}] "
                    f"monitors={self.sct.monitors}"
                )
        img = np.array(screenshot)[:, :, :3]
        return img, region


# ─── Controller ─────────────────────────────────────────────────────────

class FishingController:
    """Accumulator controller with physics-informed braking.

    Measured physics (from measure_box_physics.py):
      - Gravity: 3.24 bar/s^2, Thrust: 3.61 bar/s^2
      - Bottom-to-top: ~0.85s, Top-to-bottom: ~0.72s
      - 50% duty drifts upward (thrust > gravity)
      - Hover duty: ~47% (gravity/thrust ratio)

    Strategy: proportional control with error-rate derivative for
    natural braking, plus accumulator for smooth PWM output.
    """

    Kp = 1.5   # proportional gain
    Kd = 1.0   # derivative gain (on error rate)
    HOVER = 0.47  # duty for neutral hover (gravity/thrust ≈ 3.24/3.61 ≈ 0.47)
    LOOKAHEAD = 0.10  # seconds to predict fish position ahead (~input lag)

    def __init__(self):
        self.space_held = False
        self._duty = self.HOVER
        self._accumulator = 0.0
        self._last_box = None
        self._last_box_time = 0.0

    def update(self, detector):
        """Accumulator-based PWM with error-rate braking and fish prediction."""
        fish = detector.fish_y
        box_center = detector.box_center
        now = time.perf_counter()

        # Predict where the fish WILL BE, not where it is now.
        # Accounts for input lag (~100ms) + box acceleration time.
        fish_pred = fish + detector.fish_velocity * self.LOOKAHEAD
        fish_pred = max(0.0, min(1.0, fish_pred))

        # Error against predicted fish position
        error = fish_pred - box_center

        # Estimate box velocity for error-rate derivative
        box_velocity = 0.0
        if self._last_box is not None:
            dt_box = now - self._last_box_time
            if dt_box > 0.001:
                box_velocity = (box_center - self._last_box) / dt_box
        self._last_box = box_center
        self._last_box_time = now

        # error_rate = fish_velocity - box_velocity
        # Provides natural braking: when box approaches fish, error_rate
        # opposes the error, automatically reducing duty.
        error_rate = detector.fish_velocity - box_velocity
        d_term = error_rate * self.Kd

        # Duty: HOVER = neutral, >HOVER = hold more (go up), <HOVER = release
        self._duty = self.HOVER - self.Kp * error - d_term
        self._duty = max(0.0, min(1.0, self._duty))

        # Accumulator-based PWM: evenly spreads hold frames
        self._accumulator += self._duty
        if self._accumulator >= 1.0:
            self._accumulator -= 1.0
            self.space_held = True
        else:
            self.space_held = False

        return self.space_held

    def reset(self):
        self.space_held = False
        self._duty = self.HOVER
        self._accumulator = 0.0
        self._last_box = None
        self._last_box_time = 0.0


# ─── State Machine ──────────────────────────────────────────────────────

class GameState:
    IDLE = 'IDLE'
    CASTING = 'CASTING'
    WAITING = 'WAITING'
    MINIGAME = 'MINIGAME'
    CAUGHT = 'CAUGHT'


def _setup_topmost_window(window_name):
    """Make an OpenCV window always-on-top using Win32 API."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, window_name)
        if hwnd:
            HWND_TOPMOST = -1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
    except Exception:
        pass


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
    else:
        print("[!] FiveM window not found, using primary monitor")

    capture = ScreenCapture(game_window=game_win)
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
    if reel_only:
        print("[*] Reel-only mode: searching for minigame bar...")
    print("[*] Move mouse to top-left corner to abort (FAILSAFE)")
    if debug:
        print("[*] Debug visualization enabled - press 'q' in window to quit")
        cv2.namedWindow('Fishing Bot', cv2.WINDOW_AUTOSIZE)
        _setup_topmost_window('Fishing Bot')

    topmost_set = False

    control_interval = 1.0 / CONTROL_HZ
    last_status_log = 0.0
    minigame_frames = 0

    # Convert search region offset for absolute coordinate mapping
    search_offset_x = 0
    search_offset_y = 0

    while running:
        now = time.perf_counter()

        if state == GameState.IDLE:
            if reel_only:
                # Skip casting, go straight to searching for the bar
                state = GameState.WAITING
                state_start = now
                detector.bar_found = False
                controller.reset()
            else:
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
                    if not topmost_set:
                        _setup_topmost_window('Fishing Bot')
                        topmost_set = True
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        running = False
                        break
                if reel_only:
                    time.sleep(0.1)  # Fast poll in reel mode
                else:
                    time.sleep(CAST_WAIT_POLL)

        elif state == GameState.MINIGAME:
            loop_start = time.perf_counter()

            # Capture bar region
            try:
                img, region = capture.capture_bar_region(detector)
            except Exception as e:
                traceback.print_exc()
                print(f"[!] Capture failed: {type(e).__name__}: {e}")
                print(f"[!] Detector coords: col=[{detector.col_x1},{detector.col_x2}] "
                      f"y=[{detector.col_y1},{detector.col_y2}] prog_x2={detector.prog_x2}")
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

            minigame_frames += 1
            if now - last_status_log >= 2.0:
                last_status_log = now
                err = detector.fish_y - detector.box_center
                print(f"  [status] fish={detector.fish_y:.2f} box={detector.box_center:.2f} "
                      f"err={err:+.2f} duty={controller._duty:.0%} prog={detector.progress:.0%} "
                      f"frames={minigame_frames}", flush=True)

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
                duty_pct = int(controller._duty * 100)
                action = f"{'HOLD' if controller.space_held else 'off '} duty={duty_pct}%"
                color = (0, 255, 255) if controller.space_held else (128, 128, 128)
                cv2.putText(vis, action, (5, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)
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
            if reel_only:
                print(f"[*] Total catches: {catches}. Reel-only mode, returning to search...")
                state = GameState.IDLE
            else:
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
    parser.add_argument('--reel', action='store_true', help='Reel-only mode: skip casting, just search for minigame and play it')
    parser.add_argument('--test', type=str, help='Test detection on image file or frame directory')
    args = parser.parse_args()

    if args.test:
        run_test(args.test, debug=True)
    else:
        run_automation(debug=args.debug, reel_only=args.reel)
