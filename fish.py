"""
GTA RP Fishing Minigame Automation - Phases 1 & 2

This module is a backward-compatible facade. All functionality has been
decomposed into focused modules:

  config.py     - Configuration constants
  detection.py  - BarDetector class and detect_on_frame utility
  capture.py    - ScreenCapture class and find_game_window
  control.py    - FishingController and GameState
  automation.py - run_automation and run_test entry points

Existing imports like `from fish import BarDetector` continue to work.
"""

# Re-export everything for backward compatibility
from config import (  # noqa: F401
    SEARCH_MARGIN_X_FRAC,
    SEARCH_MARGIN_Y_FRAC,
    BLUE_H_MIN,
    BLUE_H_MAX,
    BLUE_S_MIN,
    BLUE_V_MIN,
    WHITE_BOX_SAT_THRESHOLD,
    FISH_BRIGHTNESS_DROP,
    PROGRESS_H_MIN,
    PROGRESS_H_MAX,
    PROGRESS_S_MIN,
    PROGRESS_V_MIN,
    HYSTERESIS,
    CAST_DELAY,
    BITE_WAIT,
    MINIGAME_GRACE,
    CAST_WAIT_POLL,
    BAR_APPEAR_DELAY,
    BAR_REDETECT_INTERVAL,
)
from detection import BarDetector, detect_on_frame  # noqa: F401
from capture import ScreenCapture, find_game_window  # noqa: F401
from control import FishingController, GameState  # noqa: F401
from automation import run_automation, run_test  # noqa: F401
from simulation import FishingSimulator, evaluate_controller, run_controller_episode  # noqa: F401

import argparse

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
