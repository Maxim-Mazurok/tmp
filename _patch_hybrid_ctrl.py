"""
Replace bang-bang controller with hybrid accumulator + stopping-distance braking.
"""

filepath = 'fish.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

old = '''class FishingController:
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
        self._vel_alpha = 0.3  # EMA weight for velocity smoothing

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

        v = self._box_vel  # positive=down, negative=up

        # ── Predict box state after input lag ──
        lag = self.INPUT_LAG
        if self.space_held:
            a_lag = -self.THRUST  # currently holding: accelerating up
        else:
            a_lag = self.GRAVITY  # currently released: falling
        box_pred = box_center + v * lag + 0.5 * a_lag * lag**2
        v_pred = v + a_lag * lag

        # ── Predict fish position after lag ──
        fish_pred = fish + detector.fish_velocity * lag
        error = fish_pred - box_pred  # positive = fish below, negative = above

        # ── Stopping distance ──
        if v_pred > 0.05:
            # Moving downward: need thrust (hold) to stop
            stop_dist = v_pred**2 / (2 * self.THRUST)
            overshoot = error < stop_dist
        elif v_pred < -0.05:
            # Moving upward: need gravity (release) to stop
            stop_dist = v_pred**2 / (2 * self.GRAVITY)
            overshoot = error > -stop_dist
        else:
            stop_dist = 0
            overshoot = False

        # ── Decision ──
        if abs(error) < self.DEADZONE and abs(v_pred) < 0.3:
            # Close and slow: gentle hover toward fish
            should_hold = error < 0
        elif error > 0:
            # Fish is below: want to go DOWN
            if overshoot:
                should_hold = True   # brake (thrust up)
            else:
                should_hold = False  # accelerate down (release)
        else:
            # Fish is above: want to go UP
            if overshoot:
                should_hold = False  # brake (gravity)
            else:
                should_hold = True   # accelerate up (hold)

        self.space_held = should_hold
        # Smooth _duty for display
        target = 1.0 if should_hold else 0.0
        self._duty = 0.7 * self._duty + 0.3 * target

        return self.space_held

    def reset(self):
        self.space_held = False
        self._duty = 0.5
        self._box_vel = 0.0
        self._last_box = None
        self._last_box_time = 0.0'''

new = '''class FishingController:
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

    def __init__(self):
        self.space_held = False
        self._duty = self.HOVER
        self._accumulator = 0.0
        self._last_box = None
        self._last_box_time = 0.0

    def update(self, detector):
        """Accumulator-based PWM with error-rate braking."""
        fish = detector.fish_y
        box_center = detector.box_center
        now = time.perf_counter()

        # Error: positive = fish below box -> release, negative = above -> hold
        error = fish - box_center

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
        self._last_box_time = 0.0'''

if old in content:
    content = content.replace(old, new)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("OK: Controller replaced")
else:
    print("ERROR: Old controller not found")

# Verify
with open(filepath, 'r', encoding='utf-8') as f:
    final = f.read()

for pat, desc in [
    ('HOVER = 0.47', 'hover duty'),
    ('Kp = 1.5', 'Kp'),
    ('Kd = 1.0', 'Kd'),
    ('error_rate = detector.fish_velocity - box_velocity', 'error rate braking'),
    ('_accumulator', 'accumulator'),
    ('_last_box', 'box velocity tracking'),
]:
    print(f"  {'OK' if pat in final else 'MISSING'}: {desc}")

print(f"\nfish.py: {len(final.splitlines())} lines")
