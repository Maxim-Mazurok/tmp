import json

d = json.load(open('calibration_results.json'))
items = sorted(d.values(), key=lambda v: v['frame_name'])

out = [v for v in items if not v['in_white_box']]
wb = [v for v in items if v['in_white_box']]

print('=== OUTSIDE WHITE BOX ===')
for v in out:
    err = abs(v['detected_fish_y'] - v['true_fish_y'])
    bias = v['detected_fish_y'] - v['true_fish_y']
    print(f"  {v['frame_name']}: det={v['detected_fish_y']:.3f} true={v['true_fish_y']:.3f} err={err:.3f} bias={bias:+.3f}")
errs_out = [abs(v['detected_fish_y'] - v['true_fish_y']) for v in out]
print(f"  Avg err: {sum(errs_out)/len(errs_out):.4f}")

print()
print('=== INSIDE WHITE BOX ===')
for v in wb:
    err = abs(v['detected_fish_y'] - v['true_fish_y'])
    bias = v['detected_fish_y'] - v['true_fish_y']
    print(f"  {v['frame_name']}: det={v['detected_fish_y']:.3f} true={v['true_fish_y']:.3f} err={err:.3f} bias={bias:+.3f}")
errs_wb = [abs(v['detected_fish_y'] - v['true_fish_y']) for v in wb]
print(f"  Avg err: {sum(errs_wb)/len(errs_wb):.4f}")

# Look at fish velocity (constant speed)
print()
print('=== FISH VELOCITY (true positions) ===')
for i in range(1, len(items)):
    prev = items[i-1]
    curr = items[i]
    fn_prev = int(prev['frame_name'])
    fn_curr = int(curr['frame_name'])
    gap = fn_curr - fn_prev
    if gap <= 3:  # consecutive or near-consecutive
        dy = curr['true_fish_y'] - prev['true_fish_y']
        vel = dy / gap  # per-frame velocity
        print(f"  {prev['frame_name']}->{curr['frame_name']} (gap={gap}): dy={dy:+.4f} vel={vel:+.4f}/frame")
