"""Apply pending edits to fish.py via direct file I/O."""
import sys

with open('fish.py', 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# Fix 1: Add minigame_frames counter and last_status_log initialization
old1 = '    topmost_set = False\n\n    control_interval = 1.0 / CONTROL_HZ\n\n    # Convert search region offset'
new1 = '    topmost_set = False\n\n    control_interval = 1.0 / CONTROL_HZ\n    last_status_log = 0.0\n    minigame_frames = 0\n\n    # Convert search region offset'
if old1 in content:
    content = content.replace(old1, new1)
    changes += 1
    print("Applied: minigame_frames + last_status_log init")
elif 'last_status_log' in content:
    print("Skip: already has last_status_log")
else:
    print("WARN: couldn't find insertion point for counters")

# Fix 2: Add status logging after controller update
old2 = """            if should_hold != was_held:
                if should_hold:
                    pydirectinput.keyDown('space')
                else:
                    pydirectinput.keyUp('space')

            # Debug visualization"""
new2 = '''            if should_hold != was_held:
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
if old2 in content:
    content = content.replace(old2, new2)
    changes += 1
    print("Applied: status logging")
elif 'minigame_frames += 1' in content:
    print("Skip: already has status logging")
else:
    print("WARN: couldn't find insertion point for status logging")

# Fix 3: Update debug display to show duty cycle 
old3 = '''                action = "SPACE DOWN" if controller.space_held else "space up"
                cv2.putText(vis, action, (5, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                            (0, 255, 255) if controller.space_held else (128, 128, 128), 1)'''
new3 = '''                duty_pct = int(controller._duty * 100)
                action = f"{'HOLD' if controller.space_held else 'off '} duty={duty_pct}%"
                color = (0, 255, 255) if controller.space_held else (128, 128, 128)
                cv2.putText(vis, action, (5, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)'''
if old3 in content:
    content = content.replace(old3, new3)
    changes += 1
    print("Applied: duty cycle display")
elif 'duty_pct' in content:
    print("Skip: already has duty display")
else:
    print("WARN: couldn't find insertion point for duty display")

with open('fish.py', 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\nDone: {changes} changes applied")
