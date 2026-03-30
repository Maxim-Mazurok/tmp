"""Screen capture utilities for the fishing minigame automation."""

import ctypes
import ctypes.wintypes
import numpy as np
import mss

from config import SEARCH_MARGIN_X_FRAC, SEARCH_MARGIN_Y_FRAC


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

    def capture_bar_region(self, detector, padding=None):
        """Capture just the bar area for fast updates."""
        bar_h = detector.col_y2 - detector.col_y1
        bar_w = detector.col_x2 - detector.col_x1
        if padding is None:
            padding = max(4, int(bar_h * 0.05))  # ~5% of bar height
        prog_extra = max(4, int(bar_w * 0.8))  # extra width for progress bar
        region = {
            'left': int(detector.col_x1 - padding),
            'top': int(detector.col_y1 - padding),
            'width': int((detector.prog_x2 - detector.col_x1) + padding * 2 + prog_extra),
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
