"""Fix the corrupted controller section in fish.py."""
import re

with open('fish.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the corrupted controller section - everything between the section header
# and the State Machine header
pattern = r'(# ─── Controller ─+\n\n)class FishingController:.*?(?=# ─── State Machine ─)'
match = re.search(pattern, content, re.DOTALL)
if not match:
    print("ERROR: Could not find controller section")
    exit(1)

print(f"Found controller section at chars {match.start()}-{match.end()}")
print(f"Length: {match.end() - match.start()} chars")

# Replace with clean controller
CLEAN_CONTROLLER = '''# ─── Controller ─────────────────────────────────────────────────────────

class FishingController:
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
        self._accumulator = 0.0

'''

content = content[:match.start()] + CLEAN_CONTROLLER + content[match.end():]

# Also fix line 294 if corrupted
content = content.replace('and and row_sat', 'and row_sat')
content = content.replace('and row and row_sat', 'and row_sat')

with open('fish.py', 'w', encoding='utf-8') as f:
    f.write(content)

# Verify
with open('fish.py', 'r', encoding='utf-8') as f:
    v = f.read()

checks = [
    ('Kp = 1.5', 'Kp = 1.5' in v),
    ('Kd = 0.5', 'Kd = 0.5' in v),
    ('_accumulator', '_accumulator' in v),
    ('no PWM_CYCLE', 'PWM_CYCLE' not in v),
    ('no _cycle_start', '_cycle_start' not in v),
    ('single class def', v.count('class FishingController:') == 1),
    ('single reset def', v.count('def reset(self):') == 1),
    ('single update def', v.count('def update(self, detector):') == 1),
    ('correct line 294', 'and row_sat[r] > 70' in v),
    ('no double and', 'and and' not in v),
]
all_ok = True
for name, ok in checks:
    print(f"  {'OK' if ok else 'FAIL'}: {name}")
    if not ok:
        all_ok = False

if all_ok:
    print("\nAll checks passed!")
else:
    print("\nSome checks FAILED!")
