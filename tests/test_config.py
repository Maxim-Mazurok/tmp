"""Tests for configuration constants and parameter validation.

Ensures physics constants, timing parameters, and detection thresholds
are self-consistent and within reasonable ranges.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import (
    BLUE_H_MIN, BLUE_H_MAX, BLUE_S_MIN, BLUE_V_MIN,
    WHITE_BOX_SAT_THRESHOLD,
    FISH_BRIGHTNESS_DROP,
    PROGRESS_H_MIN, PROGRESS_H_MAX, PROGRESS_S_MIN, PROGRESS_V_MIN,
    HYSTERESIS,
    CAST_DELAY, BITE_WAIT, MINIGAME_GRACE, CAST_WAIT_POLL,
    BAR_APPEAR_DELAY, BAR_REDETECT_INTERVAL,
    SEARCH_MARGIN_X_FRAC, SEARCH_MARGIN_Y_FRAC,
)
from control import FishingController
from physics_calibration import load_live_physics_profile


class TestDetectionThresholds:
    """Verify detection threshold consistency."""

    def test_blue_hue_range_valid(self):
        assert 0 <= BLUE_H_MIN < BLUE_H_MAX <= 180

    def test_blue_hue_covers_blue_spectrum(self):
        """Blue column has HSV hue ~100 (≈200° in OpenCV 0-180 scale)."""
        assert BLUE_H_MIN <= 100 <= BLUE_H_MAX

    def test_blue_saturation_positive(self):
        assert BLUE_S_MIN > 0

    def test_blue_value_allows_dark(self):
        """Bar can be dark (V=20-60 in unfilled areas)."""
        assert BLUE_V_MIN <= 30

    def test_white_box_sat_threshold_positive(self):
        assert WHITE_BOX_SAT_THRESHOLD > 0
        assert WHITE_BOX_SAT_THRESHOLD < 128  # Low saturation = white

    def test_fish_brightness_positive(self):
        assert FISH_BRIGHTNESS_DROP > 0

    def test_progress_hue_red_range(self):
        """Progress bar is red/orange (hue 0-12)."""
        assert PROGRESS_H_MIN == 0
        assert PROGRESS_H_MAX <= 20

    def test_progress_saturation_high(self):
        assert PROGRESS_S_MIN >= 50

    def test_hysteresis_positive(self):
        assert HYSTERESIS > 0
        assert HYSTERESIS < 0.5  # Should be a small fraction


class TestTimingParameters:
    """Verify timing parameters are reasonable."""

    def test_cast_delay_positive(self):
        assert CAST_DELAY > 0

    def test_bite_wait_reasonable(self):
        """Bite wait should be 30-300 seconds."""
        assert 30 <= BITE_WAIT <= 300

    def test_minigame_grace_shorter_than_bite_wait(self):
        assert MINIGAME_GRACE < BITE_WAIT

    def test_bar_redetect_interval_positive(self):
        assert BAR_REDETECT_INTERVAL > 0

    def test_cast_wait_poll_positive(self):
        assert CAST_WAIT_POLL > 0

    def test_bar_appear_delay_positive(self):
        assert BAR_APPEAR_DELAY > 0

    def test_search_margins_valid(self):
        assert 0.0 < SEARCH_MARGIN_X_FRAC < 0.5
        assert 0.0 < SEARCH_MARGIN_Y_FRAC < 0.5


class TestPhysicsConstants:
    """Verify controller physics constants are self-consistent."""

    def test_hover_duty_matches_gravity_thrust_ratio(self):
        """HOVER should match the active physics profile's neutral duty ratio."""
        c = FishingController()
        profile = load_live_physics_profile()
        expected_hover = profile.gravity / profile.thrust
        assert abs(c.HOVER - expected_hover) < 0.05, \
            f"HOVER={c.HOVER} differs from physics prediction {expected_hover:.3f}"

    def test_kp_positive(self):
        assert FishingController.Kp > 0

    def test_kd_non_negative(self):
        assert FishingController.Kd >= 0

    def test_lookahead_reasonable(self):
        """Lookahead should compensate for input lag (~100ms)."""
        assert 0.05 <= FishingController.LOOKAHEAD <= 0.30
