import csv
import numpy as np

with open('box_physics_data.csv') as f:
    data = list(csv.DictReader(f))

# hold_up: look at individual frames
print('=== HOLD_UP: Frame-by-frame positions (first 80 frames) ===')
exp = [d for d in data if d['experiment'] == 'hold_up']
for i in range(min(80, len(exp))):
    d = exp[i]
    t = float(d['time'])
    pos = float(d['box_center'])
    hold = d['holding_space']
    print(f'f={i:3d} t={t:.3f}s pos={pos:.4f} hold={hold}')

print()
print('=== HOLD_THEN_FALL: Frame-by-frame around transition (frames 100-175) ===')
exp2 = [d for d in data if d['experiment'] == 'hold_then_fall']
for i in range(100, min(175, len(exp2))):
    d = exp2[i]
    t = float(d['time'])
    pos = float(d['box_center'])
    hold = d['holding_space']
    print(f'f={i:3d} t={t:.3f}s pos={pos:.4f} hold={hold}')

# Also analyze position changes per frame
print()
print('=== HOLD_UP: Position changes (delta per frame) ===')
for i in range(1, min(80, len(exp))):
    t0 = float(exp[i-1]['time'])
    t1 = float(exp[i]['time'])
    p0 = float(exp[i-1]['box_center'])
    p1 = float(exp[i]['box_center'])
    dt = t1 - t0
    dp = p1 - p0
    v = dp / dt if dt > 0 else 0
    print(f'f={i:3d} dt={dt:.4f}s dp={dp:+.4f} v={v:+.3f} bar/s')
