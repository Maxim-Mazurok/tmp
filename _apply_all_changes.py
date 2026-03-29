"""Apply ALL changes to clean fish.py from commit 98d2db1.

Changes:
1. CONTROL_HZ 30 -> 60
2. Accumulator-based controller (replaces binary controller)
3. Fish-in-white-box detection: snap to box_center when fish not found
4. Status logging every 2s
5. Debug display: show duty%
"""

with open('fish.py', 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# --- 1. CONTROL_HZ 30 -> 60 ---
old = 'CONTROL_HZ = 30        # control loop frequency during minigame'
new = 'CONTROL_HZ = 60        # control loop frequency during minigame'
if old in content:
    content = content.replace(old, new)
    changes += 1
    print("1. CONTROL_HZ: 30 -> 60")
else:
    print("1. SKIP: CONTROL_HZ already changed or not found")

# --- 2. Fish-in-white-box: add fallback to box_center ---
# The clean version has no fallback at all - fish_y just stays at default 0.5
# when detection fails. We add: short-term velocity interpolation, then box_center.
old_detect = '''                self.fish_y = new_fish_y

        # --- Progress bar detection ---'''
new_detect = '''                self.fish_y = new_fish_y
                fish_detected = True

        if not fish_detected:
            # Fish not found — most likely inside the white box.
            # Short-term: interpolate from last known velocity (smooth transition).
            # Long-term: snap to box_center (fish IS in the box, so hover there).
            now = time.perf_counter()
            used_interpolation = False
            if len(self.fish_y_history) >= 2:
                last_t, last_y = self.fish_y_history[-1]
                dt = now - last_t
                if dt < 0.2:  # Short-term: velocity interpolation
                    predicted = last_y + self.fish_velocity * dt
                    self.fish_y = max(0.0, min(1.0, predicted))
                    used_interpolation = True
            if not used_interpolation and len(white_rows) >= 3:
                # Fish is inside white box — assume at box center.
                # Controller will hover (duty~0.5), which is optimal since
                # the progress bar fills while fish overlaps the box.
                self.fish_y = self.box_center

        # --- Progress bar detection ---'''
if old_detect in content:
    # Also need to add fish_detected flag before the cluster search
    content = content.replace(old_detect, new_detect)
    # Add fish_detected = False before the cluster search
    content = content.replace(
        '        if len(dark_rows) >= FISH_MIN_CLUSTER_SIZE:',
        '        fish_detected = False\n        if len(dark_rows) >= FISH_MIN_CLUSTER_SIZE:'
    )
    changes += 1
    print("2. Fish-in-white-box: box_center fallback added")
else:
    print("2. SKIP or ERROR: detect code not found")

# --- 3. Replace binary controller with accumulator-based ---
old_ctrl = '''class FishingController:
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
            # Fish below box → fish_y > box_center → need to go down → release
            if fish > box_center + HYSTERESIS:
                self.space_held = False
        else:
            # Currently released (box falling)
            # Press if fish is above box center by hysteresis margin
            # Fish above box → fish_y < box_center → need to go up → press
            if fish < box_center - HYSTERESIS:
                self.space_held = True

        return self.space_held

    def reset(self):
        self.space_held = False'''

new_ctrl = '''class FishingController:
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

if old_ctrl in content:
    content = content.replace(old_ctrl, new_ctrl)
    changes += 1
    print("3. Controller: binary -> accumulator-based (Kp=1.5, Kd=0.5)")
else:
    print("3. SKIP or ERROR: old controller not found")

# --- 4. Status logging: add counters before main loop ---
old_counters = '''    control_interval = 1.0 / CONTROL_HZ

    # Convert search region offset'''
new_counters = '''    control_interval = 1.0 / CONTROL_HZ
    last_status_log = 0.0
    minigame_frames = 0

    # Convert search region offset'''
if old_counters in content:
    content = content.replace(old_counters, new_counters)
    changes += 1
    print("4. Status logging: counters added")
else:
    print("4. SKIP or ERROR: counter insertion point not found")

# --- 5. Status logging: add log output in MINIGAME loop ---
old_log = '''            # Run controller
            was_held = controller.space_held
            should_hold = controller.update(detector)'''
new_log = '''            minigame_frames += 1
            if now - last_status_log >= 2.0:
                last_status_log = now
                err = detector.fish_y - detector.box_center
                print(f"  [status] fish={detector.fish_y:.2f} box={detector.box_center:.2f} "
                      f"err={err:+.2f} duty={controller._duty:.0%} prog={detector.progress:.0%} "
                      f"frames={minigame_frames}", flush=True)

            # Run controller
            was_held = controller.space_held
            should_hold = controller.update(detector)'''
if old_log in content:
    content = content.replace(old_log, new_log)
    changes += 1
    print("5. Status logging: output added")
else:
    print("5. SKIP or ERROR: log insertion point not found")

# --- 6. Debug display: show duty% ---
old_debug = '''                action = "SPACE DOWN" if controller.space_held else "space up"
                cv2.putText(vis, action, (5, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                            (0, 255, 255) if controller.space_held else (128, 128, 128), 1)'''
new_debug = '''                duty_pct = int(controller._duty * 100)
                action = f"{'HOLD' if controller.space_held else 'off '} duty={duty_pct}%"
                color = (0, 255, 255) if controller.space_held else (128, 128, 128)
                cv2.putText(vis, action, (5, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)'''
if old_debug in content:
    content = content.replace(old_debug, new_debug)
    changes += 1
    print("6. Debug display: duty% shown")
else:
    print("6. SKIP or ERROR: debug display not found")

# Write result
with open('fish.py', 'w', encoding='utf-8') as f:
    f.write(content)
print(f"\nDone: {changes} changes applied")

# Verify all changes
with open('fish.py', 'r', encoding='utf-8') as f:
    v = f.read()

checks = [
    ('CONTROL_HZ = 60', 'CONTROL_HZ = 60' in v),
    ('box_center fallback', 'self.fish_y = self.box_center' in v),
    ('fish_detected flag', 'fish_detected = False' in v),
    ('accumulator controller', '_accumulator' in v),
    ('Kp = 1.5', 'Kp = 1.5' in v),
    ('Kd = 0.5', 'Kd = 0.5' in v),
    ('status logging', 'last_status_log' in v),
    ('duty display', "duty={duty_pct}%" in v),
    ('no binary controller', 'HYSTERESIS' not in v.split('class FishingController')[1] if 'class FishingController' in v else False),
    ('single controller class', v.count('class FishingController:') == 1),
    ('correct line 294-area', 'and row_sat[r] > 70' in v),
]
all_ok = True
for name, ok in checks:
    status = 'OK' if ok else 'FAIL'
    print(f"  {status}: {name}")
    if not ok:
        all_ok = False

lines = v.count('\n') + 1
print(f"\nfish.py: {lines} lines")
print("ALL CHECKS PASSED!" if all_ok else "SOME CHECKS FAILED!")
