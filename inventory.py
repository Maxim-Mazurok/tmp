"""Inventory detection and auto shift+click for the fishing bot.

Monitors the screen for the inventory UI (detected via OCR for "YOUR INVENTORY"
text), locates the grid slots, and shift+clicks the second row first column
to move items. Rate-limited to at most once every 26 seconds.
"""

import os
import time
import cv2
import numpy as np
import pytesseract
from dotenv import load_dotenv

load_dotenv()

# Point pytesseract at the installed Tesseract binary
pytesseract.pytesseract.tesseract_cmd = (
    r'C:\Users\Maxim.Mazurok\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
)

# Rate limit: minimum seconds between shift+clicks
INVENTORY_ACTION_COOLDOWN = 26.0

# Set to false to disable inventory shift+click entirely. Configure via .env file.
INVENTORY_ENABLED = os.environ.get('INVENTORY_ENABLED', 'true').lower() in ('1', 'true', 'yes')

# Grid slot to shift+click (1-indexed). Configure via .env file.
INVENTORY_ROW = int(os.environ.get('INVENTORY_ROW', '1')) - 1
INVENTORY_COL = int(os.environ.get('INVENTORY_COL', '4')) - 1


class InventoryHandler:
    """Detects the inventory UI and shift+clicks grid slots."""

    def __init__(self):
        self._last_action_time = 0.0
        self._cached_slot = None        # (x, y) image-relative coords
        self._cached_window_size = None  # (width, height) when slot was detected

    def _is_on_cooldown(self):
        return (time.perf_counter() - self._last_action_time) < INVENTORY_ACTION_COOLDOWN

    def check_and_act(self, capture, pydirectinput):
        """Check if inventory is open and shift+click second row, first column.

        Args:
            capture: ScreenCapture instance (has ._region for game window).
            pydirectinput: The pydirectinput module for sending input.

        Returns:
            True if an action was performed, False otherwise.
        """
        if not INVENTORY_ENABLED:
            return False

        if self._is_on_cooldown():
            return False

        region = capture._region
        # Capture the full game window
        grab_region = {
            'left': region['left'],
            'top': region['top'],
            'width': region['width'],
            'height': region['height'],
        }
        try:
            screenshot = capture.sct.grab(grab_region)
        except Exception:
            try:
                capture.sct = __import__('mss').mss()
                screenshot = capture.sct.grab(grab_region)
            except Exception:
                return False

        img = np.array(screenshot)[:, :, :3]  # BGRA -> BGR

        # --- Step 1: OCR to detect "YOUR INVENTORY" text ---
        if not self._detect_inventory_text(img):
            return False

        # --- Step 2: Find the grid slot (use cache if window size unchanged) ---
        current_size = (region['width'], region['height'])
        if self._cached_slot is not None and self._cached_window_size == current_size:
            slot_center = self._cached_slot
        else:
            slot_center = self._find_grid_slot(img, row=INVENTORY_ROW, col=INVENTORY_COL)
            if slot_center is None:
                return False
            self._cached_slot = slot_center
            self._cached_window_size = current_size
            print(f"[INV] Cached grid slot at {slot_center} for window size {current_size}")

        # Convert to absolute screen coordinates
        abs_x = region['left'] + slot_center[0]
        abs_y = region['top'] + slot_center[1]

        # --- Step 3: Shift+click ---
        print(f"[INV] Shift+clicking inventory slot at ({abs_x}, {abs_y})")
        pydirectinput.keyDown('shift')
        time.sleep(0.05)
        pydirectinput.click(abs_x, abs_y)
        time.sleep(0.05)
        pydirectinput.keyUp('shift')
        self._last_action_time = time.perf_counter()
        return True

    def _detect_inventory_text(self, img):
        """Use OCR to check if 'YOUR INVENTORY' text is visible on screen."""
        h, w = img.shape[:2]

        # The "YOUR INVENTORY" text is in the upper portion of the screen,
        # roughly in the left-center area. Scan top 40%, middle 60% horizontally.
        roi_top = int(h * 0.15)
        roi_bottom = int(h * 0.45)
        roi_left = int(w * 0.15)
        roi_right = int(w * 0.65)
        roi = img[roi_top:roi_bottom, roi_left:roi_right]

        # Convert to grayscale and threshold to isolate white/light text
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)

        # Run OCR with fast config
        try:
            text = pytesseract.image_to_string(
                thresh,
                config='--psm 6 --oem 3',
            )
        except Exception as e:
            print(f"[INV] OCR error: {e}")
            return False

        text_upper = text.upper()
        if 'YOUR INVENTORY' in text_upper or 'INVENTORY' in text_upper:
            return True
        return False

    def _find_grid_slot(self, img, row=1, col=0):
        """Find the pixel center of a specific grid slot (0-indexed row/col).

        Detects the semi-transparent grid boxes by looking for their rectangular
        edges using contour detection.

        Returns (x, y) in image coordinates, or None if not found.
        """
        h, w = img.shape[:2]

        # The inventory grid is in the left-center area of the screen
        # Based on the screenshot: roughly x=17%-52%, y=32%-78%
        roi_left = int(w * 0.17)
        roi_right = int(w * 0.52)
        roi_top = int(h * 0.32)
        roi_bottom = int(h * 0.78)
        roi = img[roi_top:roi_bottom, roi_left:roi_right]

        # Detect grid cell edges: the cells have a slightly lighter border
        # on a dark semi-transparent background
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        # Edge detection to find grid lines
        edges = cv2.Canny(gray, 30, 100)

        # Dilate to connect nearby edges
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated = cv2.dilate(edges, kernel, iterations=2)

        # Find contours
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        roi_h, roi_w = roi.shape[:2]
        # Expected cell size: roughly 1/9 to 1/6 of the grid width
        min_cell = int(roi_w * 0.06)
        max_cell = int(roi_w * 0.25)

        # Filter for rectangular contours that look like grid cells
        cells = []
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            # Grid cells are roughly square
            aspect = cw / max(ch, 1)
            if 0.6 < aspect < 1.6 and min_cell < cw < max_cell and min_cell < ch < max_cell:
                cells.append((x, y, cw, ch))

        if len(cells) < 3:
            # Fallback: use a fixed grid layout based on screen proportions
            return self._fixed_grid_slot(img, row, col)

        # Sort cells by y then x to organize into rows
        cells.sort(key=lambda c: (c[1], c[0]))

        # Group into rows: cells within similar y positions
        rows = []
        current_row = [cells[0]]
        for cell in cells[1:]:
            if abs(cell[1] - current_row[0][1]) < current_row[0][3] * 0.5:
                current_row.append(cell)
            else:
                rows.append(sorted(current_row, key=lambda c: c[0]))
                current_row = [cell]
        rows.append(sorted(current_row, key=lambda c: c[0]))

        if row >= len(rows) or col >= len(rows[row]):
            # Not enough rows/cols detected, use fallback
            return self._fixed_grid_slot(img, row, col)

        # Get the target cell
        cell = rows[row][col]
        cx = roi_left + cell[0] + cell[2] // 2
        cy = roi_top + cell[1] + cell[3] // 2
        return (cx, cy)

    def _fixed_grid_slot(self, img, row=1, col=0):
        """Fallback: estimate grid slot position from screen proportions.

        Based on the inventory UI layout observed in the screenshot:
        - Grid starts at roughly x=20%, y=36% of the game window
        - Each cell is about 5.3% wide and 8.5% tall
        - Gap between cells is about 0.3%
        """
        h, w = img.shape[:2]

        # Grid origin (top-left of first cell)
        grid_x0 = int(w * 0.198)
        grid_y0 = int(h * 0.355)

        # Cell dimensions (including gap)
        cell_w = int(w * 0.056)
        cell_h = int(h * 0.088)

        # Target cell center
        cx = grid_x0 + col * cell_w + cell_w // 2
        cy = grid_y0 + row * cell_h + cell_h // 2

        # Sanity check: should be within screen bounds
        if 0 < cx < w and 0 < cy < h:
            return (cx, cy)
        return None
