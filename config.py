"""Configuration constants for the GTA RP Fishing Minigame Automation."""

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

# Experimental CV pipeline for fish detection under the semi-transparent white box.
# Keep this disabled by default until the evaluator shows a clear aggregate win.
ADVANCED_INSIDE_BOX_DETECTION = True

# Progress bar: red/orange fill detection
PROGRESS_H_MIN, PROGRESS_H_MAX = 0, 12
PROGRESS_S_MIN = 100
PROGRESS_V_MIN = 80

# Controller parameters
HYSTERESIS = 0.08  # normalized band (fraction of bar height)

# Game loop timing
CAST_DELAY = 3.0       # seconds to wait after catch before recasting
BITE_WAIT = 120.0      # seconds to wait for bite before starting to look for minigame
MINIGAME_GRACE = 5.0   # seconds after minigame start before allowing catch detection
CAST_WAIT_POLL = 2.0   # seconds between polls while waiting for bite
BAR_APPEAR_DELAY = 5.0 # extra seconds after BITE_WAIT for bar to fully appear
BAR_REDETECT_INTERVAL = 3.0  # seconds between bar position re-detection
