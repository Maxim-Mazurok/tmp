"""Tests for live projection calibration helpers."""

import json

import numpy as np
import pytest

from projection_calibration import resolve_projection_outcome, summarize_projection_outcomes


def test_resolve_projection_outcome_computes_target_and_timing_errors():
    plan = {
        'source_frame': 100,
        'target_frame': 104,
        'target_seconds': 4 / 60,
        'predicted_fish_y': 0.45,
        'predicted_box_y': 0.43,
        'predicted_signed_gap': -0.02,
        'predicted_abs_gap': 0.02,
        'fish_path': [0.40, 0.42, 0.44, 0.45],
        'box_path': [0.50, 0.48, 0.45, 0.43],
        'hold_path': [True, True, False, False],
        'hold_ratio': 0.5,
        'first_hold': True,
        'fish_velocity': 0.30,
        'box_velocity': -0.20,
        'duty': 0.6,
    }
    actual_frames = {
        100: {'frame': 100, 'fish_y': 0.40, 'box_center': 0.50, 'time': 0.0, 'progress': 0.10},
        102: {'frame': 102, 'fish_y': 0.43, 'box_center': 0.46, 'time': 0.0, 'progress': 0.0},
        103: {'frame': 103, 'fish_y': 0.44, 'box_center': 0.445, 'time': 0.0, 'progress': 0.0},
        104: {'frame': 104, 'fish_y': 0.47, 'box_center': 0.44, 'time': 0.0, 'progress': 0.0},
        105: {'frame': 105, 'fish_y': 0.48, 'box_center': 0.455, 'time': 0.0, 'progress': 0.0},
        106: {'frame': 106, 'fish_y': 0.49, 'box_center': 0.48, 'time': 0.0, 'progress': 0.0},
    }

    outcome = resolve_projection_outcome(plan, actual_frames, timing_window_frames=2)

    assert outcome is not None
    assert outcome['actual_target_fish_y'] == 0.47
    assert outcome['actual_target_box_y'] == 0.44
    assert outcome['fish_error'] == pytest.approx(0.02)
    assert outcome['box_error'] == pytest.approx(0.01)
    assert outcome['best_actual_frame'] == 103
    assert outcome['timing_error_frames'] == -1


def test_summarize_projection_outcomes_returns_adjustment_hints():
    outcomes = [
        {
            'timing_error_frames': 1,
            'target_seconds': 0.2,
            'fish_error': 0.03,
            'box_error': 0.02,
            'gap_error': 0.01,
            'lookahead_delta_seconds': 0.04,
            'gravity_delta': 0.5,
            'thrust_delta': None,
            'target_progress_delta': 0.01,
            'best_window_progress_delta': 0.03,
            'actual_target_signed_gap': 0.08,
            'mode': 'release',
        },
        {
            'timing_error_frames': -1,
            'target_seconds': 0.15,
            'fish_error': -0.01,
            'box_error': -0.03,
            'gap_error': -0.02,
            'lookahead_delta_seconds': 0.02,
            'gravity_delta': None,
            'thrust_delta': 0.4,
            'target_progress_delta': -0.01,
            'best_window_progress_delta': 0.0,
            'actual_target_signed_gap': 0.15,
            'mode': 'hold',
        },
    ]

    summary = summarize_projection_outcomes(
        outcomes,
        current_lookahead=0.10,
        current_gravity=3.1,
        current_thrust=5.9,
    )

    assert summary['samples'] == 2
    assert summary['timing']['mean_seconds'] > 0.0
    assert summary['errors']['mean_abs_box_error'] > 0.0
    assert summary['reward']['positive_samples'] == 1
    assert summary['reward']['effective_overlap_gap'] == pytest.approx(0.08)
    assert summary['suggestions']['lookahead']['suggested'] > 0.10
    assert summary['suggestions']['gravity']['suggested'] > 3.1
    assert summary['suggestions']['thrust']['suggested'] == pytest.approx(5.9)


def test_projection_outcome_is_json_serializable_with_numpy_bool_path():
    plan = {
        'source_frame': 1,
        'target_frame': 2,
        'target_seconds': 1 / 60,
        'predicted_fish_y': 0.4,
        'predicted_box_y': 0.45,
        'predicted_signed_gap': 0.05,
        'predicted_abs_gap': 0.05,
        'fish_path': [np.float32(0.4), np.float32(0.41)],
        'box_path': [np.float32(0.5), np.float32(0.45)],
        'hold_path': [np.bool_(True), np.bool_(False)],
        'hold_ratio': np.float32(0.5),
        'first_hold': np.bool_(True),
        'fish_velocity': np.float32(0.2),
        'box_velocity': np.float32(-0.1),
        'duty': np.float32(0.6),
    }
    actual_frames = {
        1: {'frame': 1, 'fish_y': 0.40, 'box_center': 0.50, 'time': 0.0, 'progress': 0.05},
        2: {'frame': 2, 'fish_y': 0.41, 'box_center': 0.44, 'time': 0.0, 'progress': 0.0},
    }

    outcome = resolve_projection_outcome(plan, actual_frames)

    assert outcome is not None
    json.dumps(outcome)