"""Analyze fishscale vs white box border characteristics.

Look at frames where the fish is inside/near the white box to understand 
how to differentiate the fishscale (broken dark pixels) from the white box 
border (continuous dark line).
"""
import cv2
import numpy as np
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fish import BarDetector, SEARCH_MARGIN_X_FRAC, SEARCH_MARGIN_Y_FRAC


def load_frame(fpath):
    img = cv2.imread(fpath)
    if img is None:
        return None, None, None
    det = BarDetector()
    h, w = img.shape[:2]
    cx, cy = w // 2, h // 2
    mx = int(w * SEARCH_MARGIN_X_FRAC)
    my = int(h * SEARCH_MARGIN_Y_FRAC)
    roi = img[cy - my:cy + my, cx - mx:cx + mx]
    if not det.find_bar(roi):
        return None, None, None
    det.col_x1 += cx - mx
    det.col_x2 += cx - mx
    det.col_y1 += cy - my
    det.col_y2 += cy - my
    det.prog_x1 += cx - mx
    det.prog_x2 += cx - mx
    return det, img, roi


def analyze_row_continuity(gray_row, threshold=128):
    """Analyze how continuous the dark pixels are in a row.
    Returns: (num_dark_pixels, num_dark_runs, max_run_length, total_dark)
    A white box border will have: many dark pixels, 1-2 runs, long max run
    A fishscale will have: fewer dark pixels, multiple runs, shorter max run
    """
    dark = gray_row < threshold
    total_dark = np.sum(dark)
    if total_dark == 0:
        return 0, 0, 0, len(gray_row)
    
    # Count runs of dark pixels
    runs = []
    in_run = False
    run_len = 0
    for px in dark:
        if px:
            if not in_run:
                in_run = True
                run_len = 1
            else:
                run_len += 1
        else:
            if in_run:
                runs.append(run_len)
                in_run = False
                run_len = 0
    if in_run:
        runs.append(run_len)
    
    return total_dark, len(runs), max(runs) if runs else 0, len(gray_row)


def analyze_frame(frame_name, det, img):
    """Analyze a frame for fishscale vs border characteristics."""
    cx1 = max(0, det.col_x1)
    cx2 = min(img.shape[1], det.col_x2 + 1)
    cy1 = max(0, det.col_y1)
    cy2 = min(img.shape[0], det.col_y2 + 1)
    
    col_img = img[cy1:cy2, cx1:cx2]
    col_h, col_w = col_img.shape[:2]
    
    hsv = cv2.cvtColor(col_img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(col_img, cv2.COLOR_BGR2GRAY)
    
    # White box detection
    row_sat = np.mean(hsv[:, :, 1].astype(float), axis=1)
    white_rows = np.where(row_sat < 55)[0]
    
    if len(white_rows) < 3:
        print(f"  {frame_name}: No white box detected")
        return
    
    diffs = np.diff(white_rows)
    splits = np.where(diffs > 3)[0]
    clusters = np.split(white_rows, splits + 1)
    main_cluster = max(clusters, key=len)
    wb_top = main_cluster[0]
    wb_bottom = main_cluster[-1]
    
    print(f"\n{'='*70}")
    print(f"Frame {frame_name}: white box rows {wb_top}-{wb_bottom} ({wb_bottom-wb_top+1} rows)")
    print(f"  Column width: {col_w}px, column height: {col_h}px")
    
    # Analyze brightness dips in the white box region and surroundings
    row_brightness = np.mean(gray.astype(float), axis=1)
    
    # Look at a wider region: wb_top-20 to wb_bottom+20
    start_r = max(0, wb_top - 20)
    end_r = min(col_h, wb_bottom + 20)
    
    print(f"\n  Row analysis (brightness, sat, continuity) around white box:")
    print(f"  {'Row':>5} {'Bright':>7} {'Sat':>5} {'InWB':>5} {'DarkPx':>7} {'Runs':>5} {'MaxRun':>7} {'Width':>6} {'DarkFrac':>9} {'Type':>10}")
    
    for r in range(start_r, end_r):
        bright = row_brightness[r]
        sat = row_sat[r]
        in_wb = wb_top <= r <= wb_bottom
        
        # Analyze row continuity
        row_gray = gray[r, :]
        total_dark, num_runs, max_run, row_width = analyze_row_continuity(row_gray, threshold=int(bright * 0.7))
        dark_frac = total_dark / row_width if row_width > 0 else 0
        
        # Classify based on characteristics
        row_type = ""
        if r in (wb_top, wb_top+1, wb_bottom, wb_bottom-1):
            row_type = "WB_EDGE"
        elif in_wb:
            row_type = "WB_INTERIOR"
        else:
            row_type = "OUTSIDE"
        
        # Only print interesting rows (edges, or rows with significant darkness)
        is_edge = abs(r - wb_top) <= 3 or abs(r - wb_bottom) <= 3
        is_dark = bright < row_brightness[max(0,r-5):min(col_h,r+5)].mean() - 10
        
        if is_edge or is_dark or r % 5 == 0:
            print(f"  {r:5d} {bright:7.1f} {sat:5.1f} {str(in_wb):>5} {total_dark:7d} {num_runs:5d} {max_run:7d} {row_width:6d} {dark_frac:9.3f} {row_type:>10}")
    
    # Now specifically look at the white box border rows in detail
    print(f"\n  Detailed pixel analysis of border rows:")
    for label, r in [("TOP-2", wb_top-2), ("TOP-1", wb_top-1), ("TOP", wb_top), 
                      ("TOP+1", wb_top+1), ("TOP+2", wb_top+2),
                      ("BOT-2", wb_bottom-2), ("BOT-1", wb_bottom-1), 
                      ("BOT", wb_bottom), ("BOT+1", wb_bottom+1), ("BOT+2", wb_bottom+2)]:
        if 0 <= r < col_h:
            row_gray_vals = gray[r, :]
            row_sat_vals = hsv[r, :, 1]
            row_val_vals = hsv[r, :, 2]
            
            # Show pixel values
            print(f"  {label:>6} (r={r:3d}): gray=[{' '.join(f'{v:3d}' for v in row_gray_vals)}]")
            print(f"         sat =[{' '.join(f'{v:3d}' for v in row_sat_vals)}]")


# Frames to analyze
FRAME_DIR = '2026-03-29 23-47-40'
# Fish entering/inside/exiting white box
FRAMES = ['001193', '001195', '001197', '001199', '001201', '001203', '001205',
          # Also check frames where no fish is near white box (for comparison)
          '000922', '000990', '001001']

for fname in FRAMES:
    fpath = os.path.join(FRAME_DIR, f'{fname}.png')
    if not os.path.exists(fpath):
        print(f"SKIP: {fpath} not found")
        continue
    det, img, roi = load_frame(fpath)
    if det is None:
        print(f"SKIP: {fname} - bar not found")
        continue
    analyze_frame(fname, det, img)
