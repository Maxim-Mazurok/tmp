"""Controller and game state for the fishing minigame automation."""

import time


class GameState:
    IDLE = 'IDLE'
    CASTING = 'CASTING'
    WAITING = 'WAITING'
    MINIGAME = 'MINIGAME'
    CAUGHT = 'CAUGHT'


class FishingController:
    """Accumulator controller with physics-informed braking.

    Measured physics (from measure_box_physics.py):
      - Gravity: 3.24 bar/s^2, Thrust: 3.61 bar/s^2
      - Bottom-to-top: ~0.85s, Top-to-bottom: ~0.72s
      - 50% duty drifts upward (thrust > gravity)
      - Hover duty: ~47% (gravity/thrust ratio)

    Strategy: proportional control with error-rate derivative for
    natural braking, plus accumulator for smooth PWM output.
    """

    Kp = 1.5   # proportional gain
    Kd = 1.0   # derivative gain (on error rate)
    HOVER = 0.47  # duty for neutral hover (gravity/thrust ≈ 3.24/3.61 ≈ 0.47)
    LOOKAHEAD = 0.10  # seconds to predict fish position ahead (~input lag)

    def __init__(self):
        self.space_held = False
        self._duty = self.HOVER
        self._accumulator = 0.0
        self._last_box = None
        self._last_box_time = 0.0

    def update(self, detector):
        """Accumulator-based PWM with error-rate braking and fish prediction."""
        fish = detector.fish_y
        box_center = detector.box_center
        now = time.perf_counter()

        # Predict where the fish WILL BE, not where it is now.
        # Accounts for input lag (~100ms) + box acceleration time.
        fish_pred = fish + detector.fish_velocity * self.LOOKAHEAD
        fish_pred = max(0.0, min(1.0, fish_pred))

        # Error against predicted fish position
        error = fish_pred - box_center

        # Estimate box velocity for error-rate derivative
        box_velocity = 0.0
        if self._last_box is not None:
            dt_box = now - self._last_box_time
            if dt_box > 0.001:
                box_velocity = (box_center - self._last_box) / dt_box
        self._last_box = box_center
        self._last_box_time = now

        # error_rate = fish_velocity - box_velocity
        # Provides natural braking: when box approaches fish, error_rate
        # opposes the error, automatically reducing duty.
        error_rate = detector.fish_velocity - box_velocity
        d_term = error_rate * self.Kd

        # Duty: HOVER = neutral, >HOVER = hold more (go up), <HOVER = release
        self._duty = self.HOVER - self.Kp * error - d_term
        self._duty = max(0.0, min(1.0, self._duty))

        # Accumulator-based PWM: evenly spreads hold frames
        self._accumulator += self._duty
        if self._accumulator >= 1.0:
            self._accumulator -= 1.0
            self.space_held = True
        else:
            self.space_held = False

        return self.space_held

    def reset(self):
        self.space_held = False
        self._duty = self.HOVER
        self._accumulator = 0.0
        self._last_box = None
        self._last_box_time = 0.0
