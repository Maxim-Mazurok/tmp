"""Automation loop smoke tests and live-debug helpers."""

import json
from types import SimpleNamespace

import numpy as np

import automation


class _FakeWriter:
    """Capture queued writes without touching disk."""

    def __init__(self):
        self.json_writes = []
        self.image_writes = []

    def write_json(self, path, payload, indent=2):
        self.json_writes.append((path, payload, indent))

    def write_image(self, path, image, params=None):
        self.image_writes.append((path, image.copy(), params))


def test_detect_overlap_jump_when_fish_crosses_box():
    """Large fish jumps across the box center should trigger a debug dump reason."""
    detector = SimpleNamespace(
        fish_y=0.66,
        box_top=0.54,
        box_bottom=0.64,
        box_center=0.59,
    )

    reason = automation._detect_overlap_jump(detector, prev_fish_y=0.52)

    assert reason == 'fish_jumped_below_box'


def test_detect_overlap_jump_ignores_small_motion():
    """Normal in-box motion should not be treated as a suspicious jump."""
    detector = SimpleNamespace(
        fish_y=0.602,
        box_top=0.55,
        box_bottom=0.65,
        box_center=0.60,
    )

    reason = automation._detect_overlap_jump(detector, prev_fish_y=0.58)

    assert reason is None


def test_async_file_writer_flushes_queued_writes(tmp_path):
    """Background writes should be persisted once the writer is finalized."""
    writer = automation._AsyncFileWriter(worker_name='test-fish-writer')
    json_path = tmp_path / 'summary.json'
    jsonl_path = tmp_path / 'telemetry.jsonl'
    image_path = tmp_path / 'frame.png'
    payload = {'frame': 12, 'status': 'ok'}

    writer.write_json(str(json_path), payload, indent=2)
    writer.append_line(str(jsonl_path), '{"frame": 12}\n')
    writer.write_image(str(image_path), np.full((4, 4, 3), 255, dtype=np.uint8))
    writer.close()

    assert json.loads(json_path.read_text(encoding='utf-8')) == payload
    assert jsonl_path.read_text(encoding='utf-8') == '{"frame": 12}\n'
    assert image_path.exists()


def test_dump_live_debug_buffer_queues_images_and_summary(tmp_path):
    """Suspicious live events should enqueue image and JSON writes instead of writing inline."""
    writer = _FakeWriter()
    recorder = {
        'buffer': [
            {
                'frame': 7,
                'telemetry': {'frame': 7},
                'raw_img': np.zeros((3, 3, 3), dtype=np.uint8),
                'debug_img': np.ones((3, 3, 3), dtype=np.uint8),
            },
            {
                'frame': 8,
                'telemetry': {'frame': 8},
                'raw_img': np.full((3, 3, 3), 2, dtype=np.uint8),
                'debug_img': None,
            },
        ],
        'last_dump_frame': -automation.LIVE_DEBUG_DUMP_COOLDOWN,
        'dump_count': 0,
        'events_dir': str(tmp_path / 'events'),
        'session_dir': str(tmp_path),
        'writer': writer,
    }
    state_ctx = {
        'debug_recorder': recorder,
        'minigame_frames': 42,
    }

    automation._dump_live_debug_buffer(state_ctx, 'fish_jump')

    assert recorder['dump_count'] == 1
    assert recorder['last_dump_frame'] == 42
    assert len(writer.image_writes) == 3
    assert len(writer.json_writes) == 1
    summary_path, summary_payload, indent = writer.json_writes[0]
    assert summary_path.endswith('summary.json')
    assert summary_payload['reason'] == 'fish_jump'
    assert summary_payload['frame'] == 42
    assert summary_payload['saved_frames'] == 2
    assert indent == 2