"""Patch: add box velocity tracking and use error-rate for derivative term.

The current Kd term uses fish_velocity, but what we really need is the RATE
of error change (= fish_velocity - box_velocity).  This provides natural
braking: when the box approaches the fish, error_rate goes opposite to error,
reducing duty and slowing the box before it overshoots.
"""

with open('fish.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add box tracking state to __init__
OLD_INIT = '''    def __init__(self):
        self.space_held = False
        self._duty = 0.5
        self._accumulator = 0.0'''

NEW_INIT = '''    def __init__(self):
        self.space_held = False
        self._duty = 0.5
        self._accumulator = 0.0
        self._last_box = None
        self._last_box_time = 0.0'''

# 2. Replace update method with velocity-aware version
OLD_UPDATE = '''    def update(self, detector):
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
        self._duty = max(0.0, min(1.0, self._duty))'''

NEW_UPDATE = '''    def update(self, detector):
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
        self._duty = max(0.0, min(1.0, self._duty))'''

# 3. Reset box tracking state
OLD_RESET = '''    def reset(self):
        self.space_held = False
        self._duty = 0.5
        self._accumulator = 0.0'''

NEW_RESET = '''    def reset(self):
        self.space_held = False
        self._duty = 0.5
        self._accumulator = 0.0
        self._last_box = None
        self._last_box_time = 0.0'''

changes = 0
for label, old, new in [
    ('init', OLD_INIT, NEW_INIT),
    ('update', OLD_UPDATE, NEW_UPDATE),
    ('reset', OLD_RESET, NEW_RESET),
]:
    if old in content:
        content = content.replace(old, new)
        changes += 1
        print(f"OK: {label}")
    else:
        print(f"ERROR: {label} not found")

with open('fish.py', 'w', encoding='utf-8') as f:
    f.write(content)
print(f"Applied {changes} changes")

# Verify
with open('fish.py', 'r', encoding='utf-8') as f:
    v = f.read()
for check in ['_last_box', 'box_velocity', 'error_rate', '_last_box_time']:
    print(f"  {'OK' if check in v else 'FAIL'}: {check}")
