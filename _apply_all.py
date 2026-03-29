"""Apply ALL pending changes to fish.py - controller rewrite + logging."""
import re

with open('fish.py', 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# ─── Change 1: Replace binary controller with PWM controller ───
old_controller = '''class FishingController:
    """Binary controller: press space when fish is above box, release when below."""

    def __init__(self):
        self.space_held = False

    def update(self, detector):
        """
        Decide whether to hold or release space.
        Returns: True if space should be held, False if released.
        """
        fish = detector.fish_y
        box_center = detector.box_center

        # Hysteresis: only change state if fish is clearly above/below
        if self.space_held:
            # Currently holding space (box moving up)
            # Release if fish is below box center by hysteresis margin
            # Remember: 0.0 = top, 1.0 = bottom
            # Fish below box \xe2\x86\x92 fish_y > box_center \xe2\x86\x92 need to go down \xe2\x86\x92 release
            if fish > box_center + HYSTERESIS:
                self.space_held = False
        else:
            # Currently released (box falling)
            # Press if fish is above box center by hysteresis margin
            # Fish above box \xe2\x86\x92 fish_y < box_center \xe2\x86\x92 need to go up \xe2\x86\x92 press
            if fish < box_center - HYSTERESIS:
                self.space_held = True

        return self.space_held

    def reset(self):
        self.space_held = False'''

# Check if old controller is present (it might have unicode arrows)
# Let's be flexible with the arrow chars
if 'Binary controller' in content:
    # Find the controller class boundaries
    start = content.find('class FishingController:')
    if start >= 0:
        # Find the next class or section
        end_marker = '\n\n# '
        end = content.find(end_marker, start + 10)
        if end < 0:
            end = len(content)
        old_section = content[start:end]
        
        new_controller = '''class FishingController:
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

        content = content[:start] + new_controller + content[end:]
        changes += 1
        print("Applied: PWM controller")
elif 'PWM proportional' in content:
    print("Skip: already has PWM controller")
else:
    print("WARN: couldn't find controller class")

# ─── Change 2: Add status logging variables ───
old2 = '    topmost_set = False\n\n    control_interval = 1.0 / CONTROL_HZ\n\n    # Convert search region offset'
new2 = '    topmost_set = False\n\n    control_interval = 1.0 / CONTROL_HZ\n    last_status_log = 0.0\n    minigame_frames = 0\n\n    # Convert search region offset'
if old2 in content:
    content = content.replace(old2, new2)
    changes += 1
    print("Applied: status log variables")
elif 'last_status_log' in content:
    print("Skip: already has status log variables")
else:
    print("WARN: couldn't find status log insertion point")

# ─── Change 3: Add status logging code ───
old3 = """            if should_hold != was_held:
                if should_hold:
                    pydirectinput.keyDown('space')
                else:
                    pydirectinput.keyUp('space')

            # Debug visualization"""
new3 = '''            if should_hold != was_held:
                if should_hold:
                    pydirectinput.keyDown('space')
                else:
                    pydirectinput.keyUp('space')

            minigame_frames += 1
            if now - last_status_log >= 2.0:
                last_status_log = now
                err = detector.fish_y - detector.box_center
                print(f"  [status] fish={detector.fish_y:.2f} box={detector.box_center:.2f} "
                      f"err={err:+.2f} duty={controller._duty:.0%} prog={detector.progress:.0%} "
                      f"frames={minigame_frames}", flush=True)

            # Debug visualization'''
if old3 in content:
    content = content.replace(old3, new3)
    changes += 1
    print("Applied: status logging code")
elif 'minigame_frames += 1' in content:
    print("Skip: already has status logging code")
else:
    print("WARN: couldn't find status logging insertion point")

# ─── Change 4: Update debug display ───
old4 = '''                action = "SPACE DOWN" if controller.space_held else "space up"
                cv2.putText(vis, action, (5, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                            (0, 255, 255) if controller.space_held else (128, 128, 128), 1)'''
new4 = '''                duty_pct = int(controller._duty * 100)
                action = f"{'HOLD' if controller.space_held else 'off '} duty={duty_pct}%"
                color = (0, 255, 255) if controller.space_held else (128, 128, 128)
                cv2.putText(vis, action, (5, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)'''
if old4 in content:
    content = content.replace(old4, new4)
    changes += 1
    print("Applied: duty cycle display")
elif 'duty_pct' in content:
    print("Skip: already has duty display")
else:
    print("WARN: couldn't find duty display insertion point")

with open('fish.py', 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\nDone: {changes} changes applied")

# Verify all changes
with open('fish.py', 'r') as f:
    text = f.read()
checks = [
    ('PWM controller', 'PWM proportional' in text),
    ('_duty attribute', '_duty' in text),
    ('status logging', 'minigame_frames' in text),
    ('duty display', 'duty_pct' in text),
]
for name, ok in checks:
    print(f"  {'OK' if ok else 'MISSING'}: {name}")
