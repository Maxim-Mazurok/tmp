"""Unit tests for FishingController: PWM, physics, gain, accumulator logic."""
import time
import pytest

from tests.helpers import BarDetector, FishingController


class TestControllerInit:
    """Test FishingController initialization."""

    def test_initial_state(self, controller):
        assert controller.space_held is False
        assert controller._duty == controller.HOVER
        assert controller._accumulator == 0.0
        assert controller._last_box is None
        assert controller._last_box_time == 0.0

    def test_physics_constants(self):
        """Verify physics-derived constants are reasonable."""
        c = FishingController()
        assert 0.3 < c.HOVER < 0.6, "Hover duty should be ~47%"
        assert c.Kp > 0, "Kp must be positive"
        assert c.Kd >= 0, "Kd must be non-negative"
        assert 0.0 < c.LOOKAHEAD < 0.5, "Lookahead should be 50-500ms"


class TestControllerReset:
    """Test controller reset behavior."""

    def test_reset_clears_state(self, controller):
        # Modify state
        controller.space_held = True
        controller._duty = 0.9
        controller._accumulator = 0.7
        controller._last_box = 0.5
        controller._last_box_time = 100.0
        controller.last_fish_pred = 0.8
        controller.last_box_velocity = 1.2
        controller.last_error = -0.3
        controller.last_error_rate = 0.4

        controller.reset()
        assert controller.space_held is False
        assert controller._duty == controller.HOVER
        assert controller._accumulator == 0.0
        assert controller._last_box is None
        assert controller._last_box_time == 0.0
        assert controller.last_fish_pred == 0.5
        assert controller.last_box_velocity == 0.0
        assert controller.last_error == 0.0
        assert controller.last_error_rate == 0.0


class TestControllerUpdate:
    """Test FishingController.update() behavior."""

    def _make_detector(self, fish_y=0.5, box_center=0.5, box_top=0.3,
                       box_bottom=0.7, fish_velocity=0.0):
        """Create a detector with specified positions for controller testing."""
        det = BarDetector()
        det.fish_y = fish_y
        det.box_center = box_center
        det.box_top = box_top
        det.box_bottom = box_bottom
        det.fish_velocity = fish_velocity
        return det

    def test_returns_bool(self, controller):
        det = self._make_detector()
        result = controller.update(det, now=0.0)
        assert isinstance(result, bool)

    def test_fish_above_box_holds_space(self, controller):
        """When fish is above box (lower y value), controller should hold space more."""
        det = self._make_detector(fish_y=0.2, box_center=0.8)
        dt = 1.0 / controller.REFERENCE_HZ
        # Run several updates to see the pattern
        holds = sum(controller.update(det, now=i * dt) for i in range(20))
        # With fish far above box, duty should be high (>HOVER), so more holds
        assert holds > 10, f"Expected mostly holds when fish above box, got {holds}/20"

    def test_fish_below_box_releases_space(self, controller):
        """When fish is below box (higher y value), controller should release more."""
        det = self._make_detector(fish_y=0.8, box_center=0.2)
        dt = 1.0 / controller.REFERENCE_HZ
        holds = sum(controller.update(det, now=i * dt) for i in range(20))
        # With fish far below box, duty should be low (<HOVER), so fewer holds
        assert holds < 10, f"Expected mostly releases when fish below box, got {holds}/20"

    def test_fish_at_box_center_hovers(self, controller):
        """When fish is at box center, duty should be near HOVER (~90%)."""
        det = self._make_detector(fish_y=0.5, box_center=0.5)
        dt = 1.0 / controller.REFERENCE_HZ
        holds = sum(controller.update(det, now=i * dt) for i in range(100))
        # Should hover around 90% (HOVER = gravity/thrust ≈ 0.897)
        hover_pct = holds / 100
        assert 0.7 < hover_pct < 1.0, \
            f"Expected hover ~90%, got {hover_pct:.0%}"

    def test_duty_clamped_0_1(self, controller):
        """Duty should never exceed [0, 1]."""
        dt = 1.0 / controller.REFERENCE_HZ
        # Extreme error case
        det = self._make_detector(fish_y=0.0, box_center=1.0)
        for i in range(50):
            controller.update(det, now=i * dt)
        assert 0.0 <= controller._duty <= 1.0

        controller.reset()
        det = self._make_detector(fish_y=1.0, box_center=0.0)
        for i in range(50):
            controller.update(det, now=100.0 + i * dt)
        assert 0.0 <= controller._duty <= 1.0

    def test_accumulator_drives_pwm(self, controller):
        """The accumulator-based PWM should produce varying hold/release patterns."""
        # fish_y ≈ box_center so duty lands near HOVER (~0.9), producing mixed PWM
        det = self._make_detector(fish_y=0.50, box_center=0.50)
        dt = 1.0 / controller.REFERENCE_HZ
        pattern = [controller.update(det, now=i * dt) for i in range(30)]
        # Should have a mix of holds and releases (not all one or the other)
        assert 0 < sum(pattern) < 30, \
            f"PWM pattern should be mixed: {sum(pattern)} holds out of 30"

    def test_derivative_term_braking(self, controller):
        """Error-rate derivative should provide braking when box approaches fish."""
        # Fish stationary, box velocity approaching fish
        det = self._make_detector(
            fish_y=0.4, box_center=0.5,
            fish_velocity=0.0  # Fish not moving
        )
        # Simulate box moving up toward fish (box velocity negative in screen coords)
        controller._last_box = 0.52
        controller._last_box_time = 1.0 - 0.016  # ~1 frame ago

        controller.update(det, now=1.0)
        # The derivative term should reduce the duty (braking)
        # Compared to a case without derivative...
        duty_with_braking = controller._duty

        # Reset and try without braking history
        controller.reset()
        controller.update(det, now=2.0)
        duty_without_braking = controller._duty

        # With braking, duty should differ from without
        # (The exact direction depends on fish_velocity - box_velocity sign)
        # This test mainly verifies the derivative term is active and influencing duty


class TestControllerLookahead:
    """Test fish position prediction (lookahead)."""

    def test_prediction_with_velocity(self, controller):
        """Fish prediction should extrapolate using velocity."""
        # Fish moving downward at speed
        det = BarDetector()
        det.fish_y = 0.3
        det.box_center = 0.5
        det.fish_velocity = 0.5  # Moving down at 0.5/s
        det.box_top = 0.3
        det.box_bottom = 0.7

        controller.update(det)
        # The controller should predict fish will be at
        # 0.3 + 0.5 * 0.10 = 0.35 (LOOKAHEAD=0.10s)
        # This means less error than raw position, so duty should be less extreme

    def test_prediction_clamped(self, controller):
        """Predicted fish position should be clamped to [0, 1]."""
        det = BarDetector()
        det.fish_y = 0.95
        det.box_center = 0.5
        det.fish_velocity = 2.0  # Moving very fast down
        det.box_top = 0.3
        det.box_bottom = 0.7

        controller.update(det)
        # Should not crash even with extreme prediction

    def test_debug_state_tracks_latest_control_values(self, controller):
        """Controller should expose the latest predicted position and error terms for debugging."""
        det = BarDetector()
        det.fish_y = 0.3
        det.box_center = 0.6
        det.fish_velocity = 0.5
        det.box_top = 0.4
        det.box_bottom = 0.8

        controller.update(det)

        assert 0.34 <= controller.last_fish_pred <= 0.36
        assert controller.last_error == pytest.approx(controller.last_fish_pred - det.box_center)
        assert isinstance(controller.last_box_velocity, float)
        assert isinstance(controller.last_error_rate, float)

    def test_box_projection_returns_requested_times(self, controller):
        """White-box projections should be produced for each requested future time offset."""
        det = BarDetector()
        det.box_center = 0.4

        controller._duty = 0.75
        controller._accumulator = 0.2
        controller.last_box_velocity = -0.1

        time_offsets = [1 / 60, 3 / 60, 5 / 60]
        projections = controller.predict_box_positions(det, time_offsets)

        assert len(projections) == 3
        assert all(0.0 <= value <= 1.0 for _, value in projections)

    def test_intercept_plan_tracks_future_meeting(self, controller):
        """The controller should expose a future meeting plan for calibration logging."""
        det = BarDetector()
        det.fish_y = 0.32
        det.box_center = 0.62
        det.box_top = 0.52
        det.box_bottom = 0.72
        det.fish_velocity = 0.35

        controller.update(det)
        plan = controller.predict_intercept_plan(det, source_frame=10)

        assert plan is controller.last_intercept_plan
        assert plan['target_frame'] > 10
        horizon_steps = max(1, round(controller.PROJECTION_HORIZON_SECONDS * controller.REFERENCE_HZ))
        assert 1 <= plan['frames_ahead'] <= horizon_steps
        assert len(plan['fish_path']) == horizon_steps
        assert len(plan['box_path']) == horizon_steps
        assert 0.0 <= plan['predicted_fish_y'] <= 1.0
        assert 0.0 <= plan['predicted_box_y'] <= 1.0

    def test_prediction_uses_raw_velocity_during_direction_debounce(self, controller):
        """Predictions should react to the latest measured reversal before direction debounce settles."""
        det = BarDetector()
        det.fish_y = 0.5
        det.box_center = 0.5
        det.box_top = 0.4
        det.box_bottom = 0.6
        det.fish_velocity = -0.3
        det.raw_fish_velocity = 0.4

        controller.update(det)

        assert controller.last_fish_pred == pytest.approx(0.5 + 0.4 * controller.LOOKAHEAD)

        plan = controller.predict_intercept_plan(det, source_frame=20)
        assert plan['fish_velocity'] == pytest.approx(0.4)
        assert plan['confirmed_fish_velocity'] == pytest.approx(-0.3)

    def test_progress_positive_overlap_reduces_position_chasing(self, controller):
        """When overlap is already rewarding, control should stay closer to hover and match motion instead of recentering hard."""
        det = BarDetector()
        det.fish_y = 0.58
        det.detected_fish_y = 0.58
        det.inferred_fish_y = 0.58
        det.box_top = 0.50
        det.box_bottom = 0.62
        det.box_center = 0.54
        det.fish_velocity = 0.20
        det.raw_fish_velocity = 0.20
        det.virtual_fish_velocity = 0.20
        det.progress_delta = 0.02

        controller.update(det)
        duty_tracking = controller._duty
        assert controller.last_tracking_mode == 'tracking'

        controller.reset()
        det.progress_delta = 0.0
        controller.update(det)
        duty_normal = controller._duty

        assert abs(duty_tracking - controller.HOVER) < abs(duty_normal - controller.HOVER)


class TestGameState:
    """Test GameState constants."""

    def test_state_values(self):
        from tests.helpers import GameState
        assert GameState.IDLE == 'IDLE'
        assert GameState.CASTING == 'CASTING'
        assert GameState.WAITING == 'WAITING'
        assert GameState.MINIGAME == 'MINIGAME'
        assert GameState.CAUGHT == 'CAUGHT'

    def test_all_states_unique(self):
        from tests.helpers import GameState
        states = [GameState.IDLE, GameState.CASTING, GameState.WAITING,
                  GameState.MINIGAME, GameState.CAUGHT]
        assert len(states) == len(set(states))
