"""Test capture_bar_region with the coordinates that failed."""
import ctypes
import ctypes.wintypes
import mss
import numpy as np

# Make DPI-aware
ctypes.windll.shcore.SetProcessDpiAwareness(2)

sct = mss.mss()
print(f"Monitors: {sct.monitors}")

# Simulate what the code does
# The bar was found at x=[1905,1938] y=[3163,3507]
# prog_x2 = 1938 + 20 = 1958
col_x1, col_x2 = 1905, 1938
col_y1, col_y2 = 3163, 3507
prog_x2 = col_x2 + 20
padding = 15

region = {
    'left': col_x1 - padding,
    'top': col_y1 - padding,
    'width': (prog_x2 - col_x1) + padding * 2 + 30,
    'height': (col_y2 - col_y1) + padding * 2,
}
print(f"Region: {region}")
print(f"  right edge: {region['left'] + region['width']}")
print(f"  bottom edge: {region['top'] + region['height']}")

# Check if region is within any monitor
for i, m in enumerate(sct.monitors):
    m_right = m['left'] + m['width']
    m_bottom = m['top'] + m['height']
    r_right = region['left'] + region['width']
    r_bottom = region['top'] + region['height']
    fits = (region['left'] >= m['left'] and region['top'] >= m['top'] and
            r_right <= m_right and r_bottom <= m_bottom)
    print(f"  Monitor {i}: ({m['left']},{m['top']})-({m_right},{m_bottom}) fits={fits}")

# Try to grab
try:
    screenshot = sct.grab(region)
    print(f"SUCCESS: {screenshot.size}")
    img = np.array(screenshot)[:, :, :3]
    print(f"Image shape: {img.shape}")
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")
    
    # Try without DPI awareness by re-creating sct
    print("\nRetrying with adjusted region...")
    # Maybe DPI awareness was set after mss was created?
    sct2 = mss.mss()
    print(f"Monitors (new sct): {sct2.monitors}")
    try:
        screenshot = sct2.grab(region)
        print(f"SUCCESS with new sct: {screenshot.size}")
    except Exception as e2:
        print(f"FAILED again: {type(e2).__name__}: {e2}")
