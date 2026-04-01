"""Tests for annotated live-run fish crop exports."""

import numpy as np

import export_live_run_fish_crops as exporter


def test_annotate_frame_adds_label_panel_and_red_line():
    """Annotated crops should widen to fit the label and show both fused and raw fish lines."""
    image = np.zeros((40, 20, 3), dtype=np.uint8)
    entry = {
        'fish_y': 0.5,
        'detected_fish_y': 0.5,
        'method': 'inside-legacy',
    }

    annotated = exporter._annotate_frame(image, entry, frame_number=12)

    assert annotated.shape[0] == image.shape[0]
    assert annotated.shape[1] > image.shape[1]
    assert np.any(annotated[:, image.shape[1]:] != 0)
    # Green fused line (thickness 2, drawn first — visible on adjacent rows)
    assert annotated[19, 0, 1] == 200
    # Red raw line (thickness 1, drawn on top at exact y)
    assert annotated[20, 0, 2] == 255