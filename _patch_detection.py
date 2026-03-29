"""Patch fish.py: improve fishscale-in-white-box handling.

When fish detection fails, use velocity interpolation for short-term (< 200ms),
then snap to box_center. This is correct because the only time detection fails
is when the fish overlaps the white box, so box_center ≈ fish position.
"""

with open('fish.py', 'r', encoding='utf-8') as f:
    content = f.read()

OLD = '''        if not fish_detected and len(self.fish_y_history) >= 2:
            # Fish is probably inside the white box — interpolate from velocity
            now = time.perf_counter()
            last_t, last_y = self.fish_y_history[-1]
            dt = now - last_t
            if dt < 0.5:  # Only interpolate for up to 500ms
                predicted = last_y + self.fish_velocity * dt
                self.fish_y = max(0.0, min(1.0, predicted))'''

NEW = '''        if not fish_detected:
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
                # Controller will hover (duty≈0.5), which is optimal since
                # the progress bar fills while fish overlaps the box.
                self.fish_y = self.box_center'''

if OLD in content:
    content = content.replace(OLD, NEW)
    with open('fish.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("OK: Patched fishscale-in-white-box handling")
else:
    print("ERROR: Could not find old interpolation code")
    # Debug: show what's around "fish_detected"
    idx = content.find('if not fish_detected')
    if idx >= 0:
        print(f"Found 'if not fish_detected' at char {idx}")
        print("Context:", repr(content[idx:idx+300]))
    else:
        print("'if not fish_detected' not found at all")

# Also fix line 294 if corrupted
content2 = open('fish.py', 'r', encoding='utf-8').read()
if 'and and row_sat' in content2 or 'and row and row_sat' in content2:
    content2 = content2.replace('and and row_sat', 'and row_sat')
    content2 = content2.replace('and row and row_sat', 'and row_sat')
    with open('fish.py', 'w', encoding='utf-8') as f:
        f.write(content2)
    print("OK: Fixed line 294")

# Verify
with open('fish.py', 'r', encoding='utf-8') as f:
    v = f.read()
checks = [
    ('box_center fallback', 'self.fish_y = self.box_center' in v),
    ('short interpolation', 'dt < 0.2' in v),
    ('no old 500ms', 'dt < 0.5' not in v),
    ('correct line 294', 'and row_sat[r] > 70' in v),
    ('no double and', 'and and' not in v),
]
for name, ok in checks:
    print(f"  {'OK' if ok else 'FAIL'}: {name}")
