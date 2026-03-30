"""Debug live screenshot detection."""
import cv2
import numpy as np
import sys
sys.path.insert(0, '.')
from detection import BarDetector
from config import SEARCH_MARGIN_X_FRAC, SEARCH_MARGIN_Y_FRAC

img = cv2.imread('live_screenshot.png')
h, w = img.shape[:2]
cx, cy = w // 2, h // 2
mx = int(w * SEARCH_MARGIN_X_FRAC)
my = int(h * SEARCH_MARGIN_Y_FRAC)
roi = img[cy - my:cy + my,
          cx - mx:cx + mx]

det = BarDetector()
det.find_bar(roi)
det.col_x1 += cx - mx
det.col_x2 += cx - mx
det.col_y1 += cy - my
det.col_y2 += cy - my
det.prog_x1 += cx - mx
det.prog_x2 += cx - mx

print(f"Bar: x=[{det.col_x1},{det.col_x2}] y=[{det.col_y1},{det.col_y2}]")
print(f"Width: {det.col_x2-det.col_x1+1}, Height: {det.col_y2-det.col_y1+1}")

# Extract the column strip and analyze
col_img = img[det.col_y1:det.col_y2+1, det.col_x1:det.col_x2+1]
col_h, col_w = col_img.shape[:2]
hsv = cv2.cvtColor(col_img, cv2.COLOR_BGR2HSV)
gray = cv2.cvtColor(col_img, cv2.COLOR_BGR2GRAY)

row_sat = np.mean(hsv[:, :, 1].astype(float), axis=1)
row_brightness = np.mean(gray.astype(float), axis=1)
row_hue = np.mean(hsv[:, :, 0].astype(float), axis=1)
row_val = np.mean(hsv[:, :, 2].astype(float), axis=1)

print(f"\nRow-by-row analysis (every 10th row):")
print(f"{'row':>5} {'norm':>6} {'H':>5} {'S':>5} {'V':>5} {'bright':>7}")
for r in range(0, col_h, 10):
    norm = r / col_h
    print(f"{r:5d} {norm:6.3f} {row_hue[r]:5.1f} {row_sat[r]:5.1f} {row_val[r]:5.1f} {row_brightness[r]:7.1f}")

# Stats
print(f"\nSaturation stats:")
print(f"  min={row_sat.min():.1f} max={row_sat.max():.1f} mean={row_sat.mean():.1f}")
print(f"  Rows with sat<55: {np.sum(row_sat < 55)} / {col_h}")
print(f"  Rows with sat<40: {np.sum(row_sat < 40)} / {col_h}")
print(f"  Rows with sat<30: {np.sum(row_sat < 30)} / {col_h}")
print(f"  Rows with sat<20: {np.sum(row_sat < 20)} / {col_h}")
