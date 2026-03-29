"""Fit physics model to measured box position data."""
import csv
import numpy as np
from scipy.optimize import curve_fit

with open('box_physics_data.csv') as f:
    data = list(csv.DictReader(f))

# ─── FALL ANALYSIS (hold_then_fall, t > 2.0) ───
exp = [d for d in data if d['experiment'] == 'hold_then_fall']
times = np.array([float(d['time']) for d in exp])
positions = np.array([float(d['box_center']) for d in exp])

# Extract falling phase: t=2.0 to when it hits bottom (~2.72)
fall_mask = (times >= 2.05) & (times <= 2.68) & (positions < 0.95)
fall_t = times[fall_mask] - 2.05  # normalize to start at 0
fall_pos = positions[fall_mask]

print("=== FALLING (gravity) ===")
print(f"Data points: {len(fall_t)}")
print(f"Duration: {fall_t[-1]:.3f}s")
print(f"Position: {fall_pos[0]:.3f} -> {fall_pos[-1]:.3f}")

# Model 1: constant acceleration from initial velocity
# pos = p0 + v0*t + 0.5*a*t^2
def const_accel(t, p0, v0, a):
    return p0 + v0 * t + 0.5 * a * t**2

popt, pcov = curve_fit(const_accel, fall_t, fall_pos, p0=[0.06, 0.0, 3.0])
p0_fit, v0_fit, a_fit = popt
print(f"\nConstant acceleration fit:")
print(f"  p0 = {p0_fit:.4f}")
print(f"  v0 = {v0_fit:.4f} bar/s")
print(f"  a  = {a_fit:.4f} bar/s^2 (gravity)")
residuals = fall_pos - const_accel(fall_t, *popt)
print(f"  RMSE = {np.sqrt(np.mean(residuals**2)):.5f}")

# Model 2: exponential approach to terminal velocity
# v = v_term * (1 - exp(-t/tau))
# pos = p0 + v_term * (t + tau * (exp(-t/tau) - 1))
def terminal_vel(t, p0, v_term, tau):
    return p0 + v_term * (t + tau * (np.exp(-t/tau) - 1))

try:
    popt2, pcov2 = curve_fit(terminal_vel, fall_t, fall_pos, p0=[0.06, 2.5, 0.3])
    p0_2, vt_2, tau_2 = popt2
    print(f"\nTerminal velocity fit:")
    print(f"  p0    = {p0_2:.4f}")
    print(f"  v_term = {vt_2:.4f} bar/s")
    print(f"  tau   = {tau_2:.4f} s")
    residuals2 = fall_pos - terminal_vel(fall_t, *popt2)
    print(f"  RMSE  = {np.sqrt(np.mean(residuals2**2)):.5f}")
except:
    print("Terminal velocity fit failed")

# ─── RISE ANALYSIS (hold_up, from first actual motion to top) ───
print("\n\n=== RISING (holding space) ===")
exp_up = [d for d in data if d['experiment'] == 'hold_up']
times_up = np.array([float(d['time']) for d in exp_up])
pos_up = np.array([float(d['box_center']) for d in exp_up])

# The rise has a big rendering artifact at frame 17.
# Use data after the artifact (from ~t=0.3 when it's smoothly accelerating)
# Also use data before it hits the top (~t=0.82)
rise_mask = (times_up >= 0.30) & (times_up <= 0.82) & (pos_up > 0.07)
rise_t = times_up[rise_mask] - 0.30
rise_pos = pos_up[rise_mask]

print(f"Data points: {len(rise_t)}")
print(f"Duration: {rise_t[-1]:.3f}s")
print(f"Position: {rise_pos[0]:.3f} -> {rise_pos[-1]:.3f}")

# Fit constant deceleration (going upward = position decreasing)
popt_up, _ = curve_fit(const_accel, rise_t, rise_pos, p0=[0.79, -1.0, -2.0])
p0_up, v0_up, a_up = popt_up
print(f"\nConstant acceleration fit:")
print(f"  p0 = {p0_up:.4f}")
print(f"  v0 = {v0_up:.4f} bar/s (negative = upward)")
print(f"  a  = {a_up:.4f} bar/s^2 (should be negative = upward accel)")
residuals_up = rise_pos - const_accel(rise_t, *popt_up)
print(f"  RMSE = {np.sqrt(np.mean(residuals_up**2)):.5f}")

try:
    popt_up2, _ = curve_fit(terminal_vel, rise_t, rise_pos, p0=[0.79, -2.5, 0.3])
    p0_u2, vt_u2, tau_u2 = popt_up2
    print(f"\nTerminal velocity fit:")
    print(f"  p0    = {p0_u2:.4f}")
    print(f"  v_term = {vt_u2:.4f} bar/s")
    print(f"  tau   = {tau_u2:.4f} s")
    residuals_up2 = rise_pos - terminal_vel(rise_t, *popt_up2)
    print(f"  RMSE  = {np.sqrt(np.mean(residuals_up2**2)):.5f}")
except Exception as e:
    print(f"Terminal velocity fit failed: {e}")

# ─── TIMING SUMMARY ───
print("\n\n=== TIMING SUMMARY ===")
# Find when box starts moving after holding space
for i in range(1, len(exp_up)):
    if float(exp_up[i]['box_center']) < float(exp_up[0]['box_center']) - 0.005:
        print(f"Input delay (hold): box moves at t={float(exp_up[i]['time']):.3f}s (frame {i})")
        break

# Find when box starts falling after release
fall_exp = [d for d in data if d['experiment'] == 'hold_then_fall']
for i in range(len(fall_exp)):
    if float(fall_exp[i]['time']) >= 2.0 and float(fall_exp[i]['box_center']) > 0.065:
        print(f"Input delay (release): box falls at t={float(fall_exp[i]['time']):.3f}s (delta={float(fall_exp[i]['time'])-2.0:.3f}s from release)")
        break

# Time from bottom to top
for i in range(len(exp_up)):
    if float(exp_up[i]['box_center']) < 0.07:
        print(f"Bottom to top: ~{float(exp_up[i]['time']):.3f}s")
        break

# Time from top to bottom
fall_start = None
for i in range(len(fall_exp)):
    if float(fall_exp[i]['time']) >= 2.0 and float(fall_exp[i]['box_center']) > 0.065:
        fall_start = float(fall_exp[i]['time'])
        break
for i in range(len(fall_exp)-1, -1, -1):
    if float(fall_exp[i]['time']) > 2.0 and float(fall_exp[i]['box_center']) > 0.96:
        if fall_start:
            print(f"Top to bottom: ~{float(fall_exp[i]['time'])-fall_start:.3f}s")
        break

# Effective hover duty cycle from short_pulses
print("\n=== ASYMMETRY ANALYSIS ===")
exp_sp = [d for d in data if d['experiment'] == 'short_pulses']
pos_sp = np.array([float(d['box_center']) for d in exp_sp])
print(f"Short pulses (50% duty): {pos_sp[0]:.3f} -> {pos_sp[-1]:.3f}")
print(f"  Net drift: {pos_sp[-1] - pos_sp[0]:+.3f} (negative=upward)")
print(f"  This means 50% duty causes {'upward' if pos_sp[-1] < pos_sp[0] else 'downward'} drift")

exp_mp = [d for d in data if d['experiment'] == 'micro_pulses']
pos_mp = np.array([float(d['box_center']) for d in exp_mp])
print(f"Micro pulses (50% duty): {pos_mp[0]:.3f} -> {pos_mp[-1]:.3f}")
print(f"  Net drift: {pos_mp[-1] - pos_mp[0]:+.3f}")
