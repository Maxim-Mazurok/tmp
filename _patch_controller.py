"""Patch the controller in fish.py to use accumulator-based PWM with lower Kp."""
import re

with open('fish.py', 'r', encoding='utf-8') as f:
    content = f.read()

OLD = '''class FishingController:
    """PWM proportional controller - uses short taps to avoid overshooting.

    Measured physics:
      - Box rise speed (space held): ~1.3 bar/s
      - Box fall speed (space released): ~1.3 bar/s
      - Fish movement: ~0.17 bar/s (independent AI)
      - Box top limit: 0.061, bottom limit: 0.972

    The box moves ~7x faster than the fish, so continuous hold/release
    causes massive overshoot.  Instead we use a duty-cycle approach:
      - Compute error = fish_y - box_center  (positive = fish below box)
      - Negative error -> fish above box -> need to go up (hold space)
      - Map error to a duty cycle (0.0 = always release, 1.0 = always hold)
      - Use a short PWM cycle (e.g. 100ms) and hold space for duty*cycle ms
    """

    # PWM cycle length in seconds
    PWM_CYCLE = 0.10
    # Proportional gain: how aggressively to respond to error
    # duty = 0.5 + Kp * error  (clamped to 0..1)
    # At equilibrium (fish inside box), duty ~= 0.5 (counteract gravity)
    # Measured: gravity pulls box down at ~1.3/s, space pushes up at ~1.3/s
    # So duty=0.5 holds position (equal up/down forces)
    Kp = 4.0
    # Derivative gain: dampen oscillations based on velocity
    Kd = 0.8

    def __init__(self):
        self.space_held = False
        self._cycle_start = 0.0
        self._duty = 0.5  # start neutral

    def update(self, detector):
        """
        Decide whether to hold or release space using PWM duty cycle.
        Returns: True if space should be held, False if released.
        """
        fish = detector.fish_y
        box_center = detector.box_center

        # Error: positive = fish is below box -> need to go down (release space)
        #         negative = fish is above box -> need to go up (hold space)
        error = fish - box_center

        # Derivative term: use fish velocity to anticipate
        # fish_velocity > 0 means fish moving down
        d_term = detector.fish_velocity * self.Kd

        # Duty cycle: 0.5 = hover, >0.5 = more hold (go up), <0.5 = more release
        # fish above box (error < 0) -> need to hold more -> duty > 0.5
        # So duty = 0.5 - Kp * error  (negative error -> higher duty)
        self._duty = 0.5 - self.Kp * error - d_term
        self._duty = max(0.0, min(1.0, self._duty))

        # PWM: within each cycle, hold space for duty*cycle seconds
        now = time.perf_counter()
        cycle_elapsed = now - self._cycle_start
        if cycle_elapsed >= self.PWM_CYCLE:
            self._cycle_start = now
            cycle_elapsed = 0.0

        # Hold space for the first (duty * cycle) seconds of each cycle
        self.space_held = cycle_elapsed < (self._duty * self.PWM_CYCLE)

        return self.space_held

    def reset(self):
        self.space_held = False
        self._cycle_start = 0.0
        self._duty = 0.5'''

NEW = '''class FishingController:
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
    Kd = 0.5

    def __init__(self):
        self.space_held = False
        self._duty = 0.5
        self._accumulator = 0.0

    def update(self, detector):
        """
        Decide whether to hold or release space this frame.
        Uses accumulator-based PWM for even distribution of hold/release.
        """
        fish = detector.fish_y
        box_center = detector.box_center

        # Error: positive = fish below box -> release (go down)
        #        negative = fish above box -> hold (go up)
        error = fish - box_center

        # Derivative: anticipate fish direction
        d_term = detector.fish_velocity * self.Kd

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
        self._accumulator = 0.0'''

if OLD in content:
    content = content.replace(OLD, NEW)
    with open('fish.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("OK: Controller patched")
else:
    print("ERROR: Could not find old controller text")
    # Try to find what's actually there
    m = re.search(r'class FishingController:.*?def reset\(self\):.*?\n(?=\n)', content, re.DOTALL)
    if m:
        print(f"Found controller at chars {m.start()}-{m.end()}")
        print("First 200 chars:", repr(m.group()[:200]))

# Verify
with open('fish.py', 'r', encoding='utf-8') as f:
    v = f.read()
checks = [
    ('Kp = 1.5', 'Kp = 1.5' in v),
    ('Kd = 0.5', 'Kd = 0.5' in v),
    ('_accumulator', '_accumulator' in v),
    ('no PWM_CYCLE', 'PWM_CYCLE' not in v),
    ('no _cycle_start', '_cycle_start' not in v),
]
for name, ok in checks:
    print(f"  {'OK' if ok else 'FAIL'}: {name}")
