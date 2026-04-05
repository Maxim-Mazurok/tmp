"""Projection-vs-observation calibration helpers for the live fishing bot."""

from __future__ import annotations

from statistics import mean, median


PROJECTION_TIMING_WINDOW_FRAMES = 2
LOOKAHEAD_DELTA_LIMIT = 0.15
ACCEL_DELTA_LIMIT = 8.0


def _float_list(values) -> list[float]:
    """Convert an iterable of numeric values to plain Python floats."""
    return [float(value) for value in values]


def _bool_list(values) -> list[bool]:
    """Convert an iterable of truthy values to plain Python bools."""
    return [bool(value) for value in values]


def classify_projection_mode(hold_ratio: float) -> str:
    """Classify a prediction as hold-dominant, release-dominant, or mixed."""
    if hold_ratio >= 0.6:
        return 'hold'
    if hold_ratio <= 0.4:
        return 'release'
    return 'mixed'


def resolve_projection_outcome(plan: dict, actual_frames: dict[int, dict],
                               timing_window_frames: int = PROJECTION_TIMING_WINDOW_FRAMES) -> dict | None:
    """Compare one predicted meeting plan with the actual future observations."""
    source_frame = int(plan['source_frame'])
    source_actual = actual_frames.get(source_frame)
    target_frame = int(plan['target_frame'])
    target_actual = actual_frames.get(target_frame)
    if source_actual is None or target_actual is None:
        return None

    candidates = [
        actual_frames[frame]
        for frame in range(target_frame - timing_window_frames, target_frame + timing_window_frames + 1)
        if frame in actual_frames
    ]
    if not candidates:
        return None

    best_actual = min(candidates, key=lambda item: abs(item['box_center'] - item['fish_y']))
    source_progress = float(source_actual['progress'])
    target_progress = float(target_actual['progress'])
    best_window_progress = max(float(item['progress']) for item in candidates)
    fish_error = float(target_actual['fish_y'] - plan['predicted_fish_y'])
    box_error = float(target_actual['box_center'] - plan['predicted_box_y'])
    predicted_gap = float(plan['predicted_signed_gap'])
    actual_gap = float(target_actual['box_center'] - target_actual['fish_y'])
    best_gap = float(best_actual['box_center'] - best_actual['fish_y'])
    horizon_seconds = max(float(plan['target_seconds']), 1e-6)
    mode = classify_projection_mode(float(plan['hold_ratio']))

    lookahead_delta_seconds = None
    if abs(float(plan['fish_velocity'])) >= 0.02:
        lookahead_delta_seconds = fish_error / float(plan['fish_velocity'])

    gravity_delta = None
    thrust_delta = None
    accel_delta = 2.0 * box_error / (horizon_seconds ** 2)
    if mode == 'release':
        gravity_delta = accel_delta
    elif mode == 'hold':
        thrust_delta = -accel_delta

    return {
        'source_frame': source_frame,
        'target_frame': target_frame,
        'target_seconds': horizon_seconds,
        'mode': mode,
        'first_hold': bool(plan['first_hold']),
        'hold_ratio': float(plan['hold_ratio']),
        'fish_velocity': float(plan['fish_velocity']),
        'box_velocity': float(plan['box_velocity']),
        'duty': float(plan['duty']),
        'predicted_fish_y': float(plan['predicted_fish_y']),
        'predicted_box_y': float(plan['predicted_box_y']),
        'predicted_signed_gap': predicted_gap,
        'predicted_abs_gap': float(plan['predicted_abs_gap']),
        'predicted_fish_path': _float_list(plan.get('fish_path', [])),
        'predicted_box_path': _float_list(plan.get('box_path', [])),
        'predicted_hold_path': _bool_list(plan.get('hold_path', [])),
        'source_progress': source_progress,
        'actual_target_progress': target_progress,
        'target_progress_delta': target_progress - source_progress,
        'best_window_progress': best_window_progress,
        'best_window_progress_delta': best_window_progress - source_progress,
        'reward_score': max(0.0, best_window_progress - source_progress),
        'actual_target_fish_y': float(target_actual['fish_y']),
        'actual_target_box_y': float(target_actual['box_center']),
        'actual_target_signed_gap': actual_gap,
        'best_actual_frame': int(best_actual['frame']),
        'best_actual_fish_y': float(best_actual['fish_y']),
        'best_actual_box_y': float(best_actual['box_center']),
        'best_actual_signed_gap': best_gap,
        'timing_error_frames': int(best_actual['frame'] - target_frame),
        'fish_error': fish_error,
        'box_error': box_error,
        'gap_error': float(actual_gap - predicted_gap),
        'lookahead_delta_seconds': lookahead_delta_seconds,
        'gravity_delta': gravity_delta,
        'thrust_delta': thrust_delta,
    }


def summarize_projection_outcomes(outcomes: list[dict], *, current_lookahead: float,
                                  current_gravity: float, current_thrust: float) -> dict:
    """Summarize resolved projection outcomes into calibration hints."""
    if not outcomes:
        return {
            'samples': 0,
            'timing': {'mean_seconds': 0.0, 'median_seconds': 0.0, 'mean_ms': 0.0},
            'errors': {'mean_abs_fish_error': 0.0, 'mean_abs_box_error': 0.0, 'mean_abs_gap_error': 0.0},
            'reward': {
                'positive_samples': 0,
                'mean_positive_delta': 0.0,
                'mean_target_delta': 0.0,
                'effective_overlap_gap': 0.0,
            },
            'suggestions': {
                'lookahead': {'current': current_lookahead, 'suggested': current_lookahead, 'delta': 0.0, 'samples': 0},
                'gravity': {'current': current_gravity, 'suggested': current_gravity, 'delta': 0.0, 'samples': 0},
                'thrust': {'current': current_thrust, 'suggested': current_thrust, 'delta': 0.0, 'samples': 0},
            },
            'modes': {},
        }

    fish_abs_errors = [abs(outcome['fish_error']) for outcome in outcomes]
    box_abs_errors = [abs(outcome['box_error']) for outcome in outcomes]
    gap_abs_errors = [abs(outcome['gap_error']) for outcome in outcomes]
    reward_positive = [outcome for outcome in outcomes if float(outcome.get('best_window_progress_delta', 0.0)) > 0.0]
    suggestion_source = reward_positive or outcomes

    lookahead_deltas = [
        float(outcome['lookahead_delta_seconds'])
        for outcome in suggestion_source
        if outcome['lookahead_delta_seconds'] is not None and abs(float(outcome['lookahead_delta_seconds'])) <= LOOKAHEAD_DELTA_LIMIT
    ]
    gravity_deltas = [
        float(outcome['gravity_delta'])
        for outcome in suggestion_source
        if outcome['gravity_delta'] is not None and abs(float(outcome['gravity_delta'])) <= ACCEL_DELTA_LIMIT
    ]
    thrust_deltas = [
        float(outcome['thrust_delta'])
        for outcome in suggestion_source
        if outcome['thrust_delta'] is not None and abs(float(outcome['thrust_delta'])) <= ACCEL_DELTA_LIMIT
    ]

    lookahead_delta = median(lookahead_deltas) if lookahead_deltas else 0.0
    gravity_delta = median(gravity_deltas) if gravity_deltas else 0.0
    thrust_delta = median(thrust_deltas) if thrust_deltas else 0.0

    suggested_lookahead = max(0.02, min(0.30, current_lookahead + lookahead_delta))
    suggested_gravity = max(0.5, current_gravity + gravity_delta)
    suggested_thrust = max(suggested_gravity + 0.1, current_thrust + thrust_delta)

    modes = {}
    for mode in ('hold', 'release', 'mixed'):
        subset = [outcome for outcome in suggestion_source if outcome['mode'] == mode]
        if not subset:
            continue
        modes[mode] = {
            'samples': len(subset),
            'mean_abs_box_error': mean(abs(outcome['box_error']) for outcome in subset),
            'mean_abs_gap_error': mean(abs(outcome['gap_error']) for outcome in subset),
            'mean_timing_error_frames': mean(float(outcome['timing_error_frames']) for outcome in subset),
        }

    reward_deltas = [float(outcome['best_window_progress_delta']) for outcome in reward_positive]
    target_reward_deltas = [float(outcome.get('target_progress_delta', 0.0)) for outcome in outcomes]
    rewarded_gaps = [abs(float(outcome['actual_target_signed_gap'])) for outcome in reward_positive]

    timing_errors_seconds = [float(outcome['target_seconds']) for outcome in outcomes if 'target_seconds' in outcome]

    return {
        'samples': len(outcomes),
        'timing': {
            'mean_seconds': mean(timing_errors_seconds) if timing_errors_seconds else 0.0,
            'median_seconds': median(timing_errors_seconds) if timing_errors_seconds else 0.0,
            'mean_ms': mean(timing_errors_seconds) * 1000.0 if timing_errors_seconds else 0.0,
        },
        'errors': {
            'mean_abs_fish_error': mean(fish_abs_errors),
            'mean_abs_box_error': mean(box_abs_errors),
            'mean_abs_gap_error': mean(gap_abs_errors),
        },
        'reward': {
            'positive_samples': len(reward_positive),
            'mean_positive_delta': mean(reward_deltas) if reward_deltas else 0.0,
            'mean_target_delta': mean(target_reward_deltas) if target_reward_deltas else 0.0,
            'effective_overlap_gap': median(rewarded_gaps) if rewarded_gaps else 0.0,
        },
        'suggestions': {
            'lookahead': {
                'current': current_lookahead,
                'suggested': suggested_lookahead,
                'delta': suggested_lookahead - current_lookahead,
                'samples': len(lookahead_deltas),
            },
            'gravity': {
                'current': current_gravity,
                'suggested': suggested_gravity,
                'delta': suggested_gravity - current_gravity,
                'samples': len(gravity_deltas),
            },
            'thrust': {
                'current': current_thrust,
                'suggested': suggested_thrust,
                'delta': suggested_thrust - current_thrust,
                'samples': len(thrust_deltas),
            },
        },
        'modes': modes,
    }