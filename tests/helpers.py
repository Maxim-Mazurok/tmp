"""Shared helpers and constants for the fishing bot test suite."""
import sys
import os
import json
import cv2
import numpy as np

# Ensure the project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from detection import BarDetector, detect_on_frame  # noqa: F401
from control import FishingController, GameState  # noqa: F401
from config import SEARCH_MARGIN_X_FRAC, SEARCH_MARGIN_Y_FRAC  # noqa: F401

# ── Paths ──────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..')
FRAME_DIR_1 = os.path.join(PROJECT_ROOT, '2026-03-29 23-47-40')
FRAME_DIR_2 = os.path.join(PROJECT_ROOT, '2026-03-29 23-51-17')
CALIBRATION_FILE = os.path.join(PROJECT_ROOT, 'calibration_results.json')

# ── Skip conditions ────────────────────────────────────────────────────
HAS_FRAMES_1 = os.path.isdir(FRAME_DIR_1) and len(
    [f for f in os.listdir(FRAME_DIR_1) if f.endswith('.png')]
) > 0
HAS_FRAMES_2 = os.path.isdir(FRAME_DIR_2) and len(
    [f for f in os.listdir(FRAME_DIR_2) if f.endswith('.png')]
) > 0
HAS_CALIBRATION = os.path.isfile(CALIBRATION_FILE)


def load_frame(frame_dir, frame_name):
    """Load a single frame image by name (without extension)."""
    fpath = os.path.join(frame_dir, f'{frame_name}.png')
    if not os.path.exists(fpath):
        return None
    return cv2.imread(fpath)


def create_synthetic_bar_image(width=100, height=600, bar_x=40, bar_w=12,
                               fish_y_frac=0.5, box_top_frac=0.3,
                               box_bottom_frac=0.6, progress_frac=0.4):
    """Create a synthetic image with a blue bar, white box, fishscale, and progress.

    Returns a BGR image that the detector should be able to process.
    """
    img = np.zeros((height, width, 3), dtype=np.uint8)

    # Fill the bar region with bright blue (HSV: H=100, S=200, V=200)
    bar_x2 = bar_x + bar_w
    bar_hsv = np.zeros((height, bar_w, 3), dtype=np.uint8)
    bar_hsv[:, :, 0] = 100  # Hue
    bar_hsv[:, :, 1] = 200  # Saturation
    bar_hsv[:, :, 2] = 200  # Value
    bar_bgr = cv2.cvtColor(bar_hsv, cv2.COLOR_HSV2BGR)
    img[:, bar_x:bar_x2] = bar_bgr

    # White box overlay: reduce saturation in box region
    box_top_px = int(box_top_frac * height)
    box_bottom_px = int(box_bottom_frac * height)
    img[box_top_px:box_bottom_px, bar_x:bar_x2] = [200, 200, 220]  # Low sat, bright

    # Fishscale: dark spot at fish_y
    fish_y_px = int(fish_y_frac * height)
    fish_size = max(3, int(height * 0.03))
    y1 = max(0, fish_y_px - fish_size // 2)
    y2 = min(height, fish_y_px + fish_size // 2)
    # Dark blue spot (high saturation, low value)
    img[y1:y2, bar_x:bar_x2] = [40, 20, 20]

    # Progress bar: red/orange fill from bottom
    prog_x1 = bar_x2 + 1
    prog_x2 = bar_x2 + max(4, int(bar_w * 0.6))
    if prog_x2 < width:
        filled_rows = int(progress_frac * height)
        if filled_rows > 0:
            prog_hsv = np.zeros((filled_rows, prog_x2 - prog_x1, 3), dtype=np.uint8)
            prog_hsv[:, :, 0] = 5   # Red hue
            prog_hsv[:, :, 1] = 200  # High saturation
            prog_hsv[:, :, 2] = 200  # Bright
            prog_bgr = cv2.cvtColor(prog_hsv, cv2.COLOR_HSV2BGR)
            img[height - filled_rows:height, prog_x1:prog_x2] = prog_bgr

    return img
