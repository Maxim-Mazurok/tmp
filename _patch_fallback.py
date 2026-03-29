"""Patch fish.py: smarter fishscale fallback.

Only use box_center fallback when the last detected fish position was near/inside 
the white box (within 1 box-height). Otherwise keep the last known position.
"""

with open('fish.py', 'r', encoding='utf-8') as f:
    content = f.read()

OLD = '''        if not fish_detected:
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
                self.fish_y = self.box_center'''

NEW = '''        if not fish_detected:
            # Fish not found. Could be: (a) inside white box, or (b) detection glitch.
            # Strategy: use velocity interpolation short-term, then box_center ONLY
            # if we believe the fish is actually inside the white box.
            now = time.perf_counter()
            used_interpolation = False
            if len(self.fish_y_history) >= 2:
                last_t, last_y = self.fish_y_history[-1]
                dt = now - last_t
                if dt < 0.3:  # Short-term: velocity interpolation
                    predicted = last_y + self.fish_velocity * dt
                    self.fish_y = max(0.0, min(1.0, predicted))
                    used_interpolation = True
            if not used_interpolation and len(white_rows) >= 3:
                # Only snap to box_center if last known fish was near the box.
                # This prevents false snapping when detection fails for other reasons.
                box_height = self.box_bottom - self.box_top
                fish_near_box = abs(self.fish_y - self.box_center) < box_height * 1.5
                if fish_near_box:
                    self.fish_y = self.box_center
            # else: keep last known fish_y (stale but avoids wild jumps)'''

if OLD in content:
    content = content.replace(OLD, NEW)
    with open('fish.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("OK: Smarter fallback applied")
else:
    print("ERROR: Could not find old fallback code")

# Verify
with open('fish.py', 'r', encoding='utf-8') as f:
    v = f.read()
checks = [
    ('fish_near_box guard', 'fish_near_box' in v),
    ('box_height calc', 'box_height = self.box_bottom - self.box_top' in v),
    ('300ms interpolation', 'dt < 0.3' in v),
]
for name, ok in checks:
    print(f"  {'OK' if ok else 'FAIL'}: {name}")
