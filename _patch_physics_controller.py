"""
Patch fish.py to replace the accumulator-based PWM controller with a
physics-based bang-bang controller that uses measured acceleration constants
and stopping-distance logic.

Physics model (from measure_box_physics.py):
  - Gravity (falling when released): 3.24 bar/s^2
  - Upward thrust (net, when holding): 3.61 bar/s^2
  - Input lag: ~100ms
  - Terminal velocity: ~2.4 bar/s (upward)
"""

import re

filepath = 'fish.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Define the old controller (everything between the comment markers)
old_controller = '''class FishingController:
    """Accumulator-based proportional controller for the fishing minigame.

    Measured physics:
      - Box rise speed (space held): ~1.3 bar/s
      - Box fall speed (space released): ~1.3 bar/s
      - Fish movement: ~0.17 bar/s (independent AI)
      - Box height: ~0.12 bar-units

    Uses an accumulator (Bresenham-style) to distribute hold/release frames
    evenly.  Each frame independently decides hold or release based on the
    accumulated duty.  No fixed PWM cycle = instant reaction to error changes.
    """

    # Proportional gain: duty = 0.5 - Kp * error
    # Proportional band = +/-(0.5/Kp).  Kp=1.5 -> band +/-0.33
    # At error=0.1 -> duty offset 0.15 -> box speed 0.39 bar/s (gentle)
    # At error=0.33+ -> saturates -> box at full 1.3 bar/s (chase)
    Kp = 1.5
    # Derivative gain: anticipate fish movement
    Kd = 1.0

    def __init__(self):
        self.space_held = False
        self._duty = 0.5
        self._accumulator = 0.0
        self._last_box = None
        self._last_box_time = 0.0

    def update(self, detector):
        """
        Decide whether to hold or release space this frame.
        Uses accumulator-based PWM for even distribution of hold/release.
        """
        fish = detector.fish_y
        box_center = detector.box_center
        now = time.perf_counter()

        # Error: positive = fish below box -> release (go down)
        #        negative = fish above box -> hold (go up)
        error = fish - box_center

        # Estimate box velocity from position changes
        box_velocity = 0.0
        if self._last_box is not None:
            dt_box = now - self._last_box_time
            if dt_box > 0:
                box_velocity = (box_center - self._last_box) / dt_box
        self._last_box = box_center
        self._last_box_time = now

        # Derivative uses ERROR RATE, not just fish velocity.
        # error_rate = d(error)/dt = fish_velocity - box_velocity
        # When box is APPROACHING fish: error_rate opposes error -> brakes
        # When box is DIVERGING from fish: error_rate same as error -> boost
        error_rate = detector.fish_velocity - box_velocity
        d_term = error_rate * self.Kd

        # Duty: 0.5 = hover, >0.5 = hold more (go up), <0.5 = release more
        self._duty = 0.5 - self.Kp * error - d_term
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
        self._duty = 0.5
        self._accumulator = 0.0
        self._last_box = None
        self._last_box_time = 0.0'''

new_controller = '''class FishingController:
    """Physics-based bang-bang controller using measured acceleration constants.

    Measured physics (from measure_box_physics.py):
      - Gravity (falling, space released): 3.24 bar/s^2 downward
      - Upward thrust (space held, net): 3.61 bar/s^2 upward
      - Input lag: ~100ms
      - Terminal velocity (upward): ~2.4 bar/s
      - Fish movement: ~0.17 bar/s (independent AI, constant speed)

    Strategy: bang-bang control with phase-plane switching curve.
      1. Estimate box velocity from position changes (smoothed).
      2. Predict where the box will be after input lag.
      3. Compute stopping distance from current velocity.
      4. If box can overshoot fish: brake (apply opposite force).
         Otherwise: accelerate toward fish.
    """

    GRAVITY = 3.24       # bar/s^2 (falling acceleration when released)
    THRUST = 3.61        # bar/s^2 (net upward acceleration when holding)
    INPUT_LAG = 0.10     # seconds before input takes effect
    DEADZONE = 0.03      # bar-units: if |error| < this, coast

    def __init__(self):
        self.space_held = False
        self._duty = 0.5   # for status display compatibility
        self._box_vel = 0.0  # estimated box velocity (positive = downward)
        self._last_box = None
        self._last_box_time = 0.0
        # Smoothing: exponential moving average of velocity
        self._vel_alpha = 0.3  # weight for new samples

    def update(self, detector):
        """
        Decide whether to hold or release space this frame.
        Uses phase-plane switching: accelerate toward fish, then brake
        so we stop at the fish position.
        """
        fish = detector.fish_y
        box_center = detector.box_center
        now = time.perf_counter()

        # ── Estimate box velocity (positive = downward) ──
        if self._last_box is not None:
            dt = now - self._last_box_time
            if dt > 0.001:
                raw_vel = (box_center - self._last_box) / dt
                self._box_vel = (self._vel_alpha * raw_vel +
                                 (1 - self._vel_alpha) * self._box_vel)
        self._last_box = box_center
        self._last_box_time = now

        v = self._box_vel  # current velocity (positive=down, negative=up)

        # ── Predict box state after input lag ──
        # During lag, current physics continues
        # If currently holding: acceleration is -THRUST (upward)
        # If currently released: acceleration is +GRAVITY (falling)
        lag = self.INPUT_LAG
        if self.space_held:
            a_during_lag = -self.THRUST
        else:
            a_during_lag = self.GRAVITY
        # Predicted position and velocity after lag
        box_pred = box_center + v * lag + 0.5 * a_during_lag * lag**2
        v_pred = v + a_during_lag * lag

        # ── Compute error from predicted position ──
        # Also predict fish position (constant velocity)
        fish_pred = fish + detector.fish_velocity * lag
        error = fish_pred - box_pred  # positive = fish below, negative = fish above

        # ── Stopping distance calculation ──
        # If going down (v_pred > 0) and need to stop: hold space (decel = THRUST)
        #   stopping_dist = v_pred^2 / (2 * THRUST)
        # If going up (v_pred < 0) and need to stop: release (decel = GRAVITY)
        #   stopping_dist = v_pred^2 / (2 * GRAVITY)

        if v_pred > 0:
            # Moving downward - would need to hold (thrust up) to stop
            stop_dist = v_pred**2 / (2 * self.THRUST)
            # Will overshoot fish if error < stop_dist (fish is closer than
            # we can stop in, or above us)
            overshoot = error < stop_dist
        elif v_pred < 0:
            # Moving upward - would need to release (gravity) to stop
            stop_dist = v_pred**2 / (2 * self.GRAVITY)
            # Will overshoot if error > -stop_dist (fish is closer or below)
            overshoot = error > -stop_dist
        else:
            stop_dist = 0
            overshoot = False

        # ── Decision ──
        if abs(error) < self.DEADZONE and abs(v_pred) < 0.3:
            # Close enough and slow: maintain gentle hover
            # Hold ~48% to counteract slightly-stronger thrust vs gravity
            # Use a simple rule: hold if below fish, release if above
            should_hold = error < 0
        elif error > 0:
            # Fish is below us: we want to go DOWN
            if overshoot:
                # Moving down too fast, will overshoot: BRAKE (hold/thrust up)
                should_hold = True
            else:
                # Need to go further down: ACCELERATE down (release)
                should_hold = False
        else:
            # Fish is above us: we want to go UP
            if overshoot:
                # Moving up too fast, will overshoot: BRAKE (release/gravity)
                should_hold = False
            else:
                # Need to go further up: ACCELERATE up (hold)
                should_hold = True

        self.space_held = should_hold
        # Update _duty for display (1=hold, 0=release, smooth for readability)
        target_duty = 1.0 if should_hold else 0.0
        self._duty = 0.7 * self._duty + 0.3 * target_duty

        return self.space_held

    def reset(self):
        self.space_held = False
        self._duty = 0.5
        self._box_vel = 0.0
        self._last_box = None
        self._last_box_time = 0.0'''

if old_controller in content:
    content = content.replace(old_controller, new_controller)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("OK: Controller replaced successfully")
else:
    print("ERROR: Could not find old controller text")
    # Try to find it with a shorter match
    if 'Accumulator-based proportional controller' in content:
        print("  Found docstring but full match failed - checking for whitespace issues")
    elif 'FishingController' in content:
        print("  Found class name but content differs")
    else:
        print("  Class not found at all!")

# Verify
with open(filepath, 'r', encoding='utf-8') as f:
    final = f.read()

checks = [
    ('GRAVITY = 3.24', 'gravity constant'),
    ('THRUST = 3.61', 'thrust constant'),
    ('INPUT_LAG = 0.10', 'input lag'),
    ('stop_dist = v_pred**2', 'stopping distance'),
    ('_box_vel', 'velocity tracking'),
    ('box_pred = box_center', 'position prediction'),
    ('fish_pred = fish', 'fish prediction'),
]
for pattern, desc in checks:
    if pattern in final:
        print(f"  OK: {desc}")
    else:
        print(f"  MISSING: {desc}")
