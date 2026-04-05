"""Controller and game state for the fishing minigame automation."""

import time

from physics_calibration import load_live_physics_profile


PHYSICS_PROFILE = load_live_physics_profile()


class GameState:
    IDLE = 'IDLE'
    CASTING = 'CASTING'
    WAITING = 'WAITING'
    MINIGAME = 'MINIGAME'
    CAUGHT = 'CAUGHT'


class FishingController:
    """Accumulator controller with physics-informed braking.

        Physics are loaded from the aggregated live white-box calibration runs
        when available, falling back to the legacy defaults otherwise.

    Strategy: proportional control with error-rate derivative for
    natural braking, plus accumulator for smooth PWM output.
    """

    REFERENCE_HZ = 60  # PWM normalization rate (physics calibrated at 60 Hz)
    Kp = 1.5   # proportional gain
    Kd = 1.0   # derivative gain (on error rate)
    GRAVITY = PHYSICS_PROFILE.gravity
    THRUST = PHYSICS_PROFILE.thrust
    HOVER = PHYSICS_PROFILE.hover
    HOVER_BIAS = 0.05  # upward bias to compensate systematic box-below-fish drift
    LOOKAHEAD = 0.095  # seconds to predict fish position ahead (~input lag)
    PROJECTION_HORIZON_SECONDS = 0.2  # ~12 frames at 60 Hz
    TRACKING_PROGRESS_THRESHOLD = 0.003
    TRACKING_KP_SCALE = 0.45
    TRACKING_KD_SCALE = 1.20
    TRACKING_DEADZONE_FRAC = 0.30
    MISSING_FISH_KP_SCALE = 0.70
    INSIDE_BOX_SPEED_SCALE = 0.85  # fish slows ~15% when inside white box

    def __init__(self):
        self.space_held = False
        self._duty = self.HOVER
        self._accumulator = 0.0
        self._last_box = None
        self._last_box_time = 0.0
        self._last_update_time = None
        self.last_fish_pred = 0.5
        self.last_box_velocity = 0.0
        self.last_error = 0.0
        self.last_error_rate = 0.0
        self.last_intercept_plan = None
        self.last_tracking_mode = 'normal'
        self.last_dt = 1.0 / self.REFERENCE_HZ

    @staticmethod
    def _prediction_velocity(detector):
        """Use the freshest measured fish velocity for prediction when available."""
        virtual_velocity = getattr(detector, 'virtual_fish_velocity', None)
        if virtual_velocity is not None and abs(virtual_velocity) > 1e-9:
            return virtual_velocity

        raw_velocity = getattr(detector, 'raw_fish_velocity', None)
        confirmed_velocity = detector.fish_velocity
        if raw_velocity is None:
            return detector.fish_velocity
        if abs(raw_velocity) <= 1e-9 and abs(confirmed_velocity) > 1e-9:
            return confirmed_velocity
        return raw_velocity

    @classmethod
    def _tracking_adjustment(cls, detector, fish_pred, box_center):
        """Dampen position chasing while overlap is already producing reward."""
        error = fish_pred - box_center
        kp_scale = 1.0
        kd_scale = 1.0
        mode = 'normal'

        progress_delta = float(getattr(detector, 'progress_delta', 0.0) or 0.0)
        detected_fish_y = getattr(detector, 'detected_fish_y', None)
        inside_box = detector.box_top <= detector.fish_y <= detector.box_bottom
        if progress_delta > cls.TRACKING_PROGRESS_THRESHOLD and inside_box:
            box_height = max(detector.box_bottom - detector.box_top, 0.0)
            deadzone = max(0.02, box_height * cls.TRACKING_DEADZONE_FRAC)
            if abs(error) <= deadzone:
                error *= 0.30
            else:
                sign = -1.0 if error < 0.0 else 1.0
                error = sign * ((abs(error) - deadzone) + deadzone * 0.30)
            kp_scale *= cls.TRACKING_KP_SCALE
            kd_scale *= cls.TRACKING_KD_SCALE
            mode = 'tracking'

        if detected_fish_y is None:
            kp_scale *= cls.MISSING_FISH_KP_SCALE
            if mode == 'normal':
                mode = 'virtual'
            else:
                mode = 'tracking-virtual'

        return error, kp_scale, kd_scale, mode

    def update(self, detector, now=None):
        """Accumulator-based PWM with error-rate braking and fish prediction."""
        fish = detector.fish_y
        box_center = detector.box_center
        if now is None:
            now = time.perf_counter()

        # Compute actual dt from last update
        if self._last_update_time is not None:
            dt = min(now - self._last_update_time, 0.1)  # cap at 100ms to prevent stutter issues
        else:
            dt = 1.0 / self.REFERENCE_HZ  # first call fallback
        self._last_update_time = now
        self.last_dt = dt

        # Predict where the fish WILL BE, not where it is now.
        # Accounts for input lag (~100ms) + box acceleration time.
        prediction_velocity = self._prediction_velocity(detector)

        # Fish slows down when inside the white box (progress rising)
        progress_delta = float(getattr(detector, 'progress_delta', 0.0) or 0.0)
        inside_box = detector.box_top <= detector.fish_y <= detector.box_bottom
        if progress_delta > self.TRACKING_PROGRESS_THRESHOLD and inside_box:
            prediction_velocity *= self.INSIDE_BOX_SPEED_SCALE

        fish_pred = fish + prediction_velocity * self.LOOKAHEAD
        fish_pred = max(0.0, min(1.0, fish_pred))
        self.last_fish_pred = fish_pred

        # Error against predicted fish position, softened when overlap is already rewarding.
        error, kp_scale, kd_scale, tracking_mode = self._tracking_adjustment(detector, fish_pred, box_center)
        self.last_error = error
        self.last_tracking_mode = tracking_mode

        # Estimate box velocity for error-rate derivative
        box_velocity = 0.0
        if self._last_box is not None:
            dt_box = now - self._last_box_time
            if dt_box > 0.001:
                box_velocity = (box_center - self._last_box) / dt_box
        self.last_box_velocity = box_velocity
        self._last_box = box_center
        self._last_box_time = now

        # error_rate = fish_velocity - box_velocity
        # Provides natural braking: when box approaches fish, error_rate
        # opposes the error, automatically reducing duty.
        error_rate = prediction_velocity - box_velocity
        self.last_error_rate = error_rate
        d_term = error_rate * self.Kd * kd_scale

        # Duty: HOVER = neutral, >HOVER = hold more (go up), <HOVER = release
        effective_hover = self.HOVER + self.HOVER_BIAS
        self._duty = effective_hover - self.Kp * kp_scale * error - d_term
        self._duty = max(0.0, min(1.0, self._duty))

        # Accumulator-based PWM: scale by actual dt so duty ratio
        # is time-averaged rather than frame-averaged.
        self._accumulator += self._duty * dt * self.REFERENCE_HZ
        # Epsilon handles floating-point rounding when dt comes from
        # accumulated timestamps (e.g. dt*60 = 0.99999999… instead of 1.0).
        if self._accumulator >= 1.0 - 1e-9:
            self._accumulator -= 1.0
            self._accumulator = max(self._accumulator, 0.0)
            self.space_held = True
        else:
            self.space_held = False
        # Clamp to prevent runaway accumulation during stutters
        self._accumulator = min(self._accumulator, 1.0)

        return self.space_held

    def reset(self):
        self.space_held = False
        self._duty = self.HOVER
        self._accumulator = 0.0
        self._last_box = None
        self._last_box_time = 0.0
        self._last_update_time = None
        self.last_fish_pred = 0.5
        self.last_box_velocity = 0.0
        self.last_error = 0.0
        self.last_error_rate = 0.0
        self.last_intercept_plan = None
        self.last_tracking_mode = 'normal'
        self.last_dt = 1.0 / self.REFERENCE_HZ

    def predict_fish_positions(self, detector, time_offsets):
        """Project future fish positions assuming current velocity persists briefly.

        Args:
            detector: Current bar detector state.
            time_offsets: Sequence of future time offsets in seconds.
        """
        predictions = []
        prediction_velocity = self._prediction_velocity(detector)
        for time_offset in sorted(time_offsets):
            predicted = detector.fish_y + prediction_velocity * time_offset
            predictions.append((time_offset, max(0.0, min(1.0, predicted))))
        return predictions

    def _simulate_box_path(self, detector, time_horizon):
        """Simulate future box centers using the current PWM duty and physics.

        Internally steps at REFERENCE_HZ for consistency with calibrated physics.

        Args:
            detector: Current bar detector state.
            time_horizon: Duration in seconds to simulate ahead.
        """
        dt = 1.0 / self.REFERENCE_HZ
        step_count = max(1, round(time_horizon * self.REFERENCE_HZ))
        accumulator = self._accumulator
        box_center = detector.box_center
        box_velocity = self.last_box_velocity
        positions = []
        hold_path = []
        timestamps = []

        for step in range(step_count):
            accumulator += self._duty * dt * self.REFERENCE_HZ
            hold = accumulator >= 1.0
            if hold:
                accumulator -= 1.0

            acceleration = self.GRAVITY - self.THRUST if hold else self.GRAVITY
            box_velocity += acceleration * dt
            box_center += box_velocity * dt

            if box_center <= 0.0:
                box_center = 0.0
                box_velocity = 0.0
            elif box_center >= 1.0:
                box_center = 1.0
                box_velocity = 0.0

            positions.append(box_center)
            hold_path.append(hold)
            timestamps.append((step + 1) * dt)

        return positions, hold_path, timestamps

    def predict_box_positions(self, detector, time_offsets):
        """Project future white-box center positions using current PWM state and physics.

        Args:
            detector: Current bar detector state.
            time_offsets: Sequence of future time offsets in seconds.
        """
        if not time_offsets:
            return []

        max_time = max(time_offsets)
        path, _, timestamps = self._simulate_box_path(detector, max_time)
        results = []
        for target_time in sorted(time_offsets):
            # Find the closest simulated step to the requested time offset
            best_index = min(range(len(timestamps)),
                             key=lambda idx: abs(timestamps[idx] - target_time))
            results.append((target_time, path[best_index]))
        return results

    def predict_intercept_plan(self, detector, source_frame=0, horizon_seconds=None):
        """Predict when the current box and fish trajectories should meet next."""
        horizon = horizon_seconds if horizon_seconds is not None else self.PROJECTION_HORIZON_SECONDS
        if horizon <= 0:
            return None

        # Simulate box path at reference rate
        box_positions, hold_path, timestamps = self._simulate_box_path(detector, horizon)
        step_count = len(box_positions)
        if step_count == 0:
            return None

        # Predict fish at the same time offsets
        fish_positions = []
        prediction_velocity = self._prediction_velocity(detector)
        for timestamp in timestamps:
            predicted = detector.fish_y + prediction_velocity * timestamp
            fish_positions.append(max(0.0, min(1.0, predicted)))

        best_index = min(range(step_count), key=lambda idx: abs(box_positions[idx] - fish_positions[idx]))
        target_seconds = timestamps[best_index]
        steps_ahead = best_index + 1
        hold_ratio = sum(hold_path[:steps_ahead]) / steps_ahead

        plan = {
            'source_frame': int(source_frame),
            'target_frame': int(source_frame + steps_ahead),
            'frames_ahead': steps_ahead,
            'target_seconds': target_seconds,
            'predicted_fish_y': fish_positions[best_index],
            'predicted_box_y': box_positions[best_index],
            'predicted_signed_gap': box_positions[best_index] - fish_positions[best_index],
            'predicted_abs_gap': abs(box_positions[best_index] - fish_positions[best_index]),
            'fish_path': fish_positions,
            'box_path': box_positions,
            'hold_path': hold_path,
            'hold_ratio': hold_ratio,
            'first_hold': bool(hold_path[0]) if hold_path else False,
            'fish_velocity': self._prediction_velocity(detector),
            'confirmed_fish_velocity': detector.fish_velocity,
            'box_velocity': self.last_box_velocity,
            'duty': self._duty,
            'tracking_mode': self.last_tracking_mode,
        }
        self.last_intercept_plan = plan
        return plan
