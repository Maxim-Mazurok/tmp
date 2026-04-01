"""Export annotated raw crops from a recorded live debug event."""

import argparse
import json
import os

import cv2


LABEL_FONT = cv2.FONT_HERSHEY_SIMPLEX
LABEL_FONT_SCALE = 0.45
LABEL_FONT_THICKNESS = 1
LABEL_PADDING = 6
LABEL_LINE_EXTENSION = 12
LABEL_PANEL_COLOR = (18, 18, 18)


def _load_telemetry_index(telemetry_path):
    """Load telemetry rows keyed by frame number."""
    telemetry_by_frame = {}
    with open(telemetry_path, encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            telemetry_by_frame[int(payload['frame'])] = payload
    return telemetry_by_frame


def _frame_confidence(entry):
    """Reduce method-specific scores to one display confidence for inspection."""
    method = entry.get('method', 'none')
    if entry.get('detected_fish_y') is None:
        return 0.0
    if method == 'outside-dip':
        return max(0.0, min(1.0, float(entry.get('match_score', 1.0))))
    if method == 'inside-template':
        match_score = max(0.0, min(1.0, float(entry.get('match_score', 0.0))))
        shape_score = max(0.0, min(1.0, float(entry.get('shape_score', 1.0))))
        return max(0.0, min(1.0, 0.75 * match_score + 0.25 * (1.0 - shape_score)))
    if method == 'tracker-flow':
        return max(0.0, min(1.0, float(entry.get('tracker_confidence', 0.0))))
    if method == 'inside-legacy':
        return 0.45
    return 0.0


def _line_y(entry):
    """Choose the directly observed fish location when available."""
    detected = entry.get('detected_fish_y')
    if detected is not None:
        return float(detected)
    return float(entry['fish_y'])


def _annotate_frame(image, entry, frame_number):
    """Draw fish location and confidence label on a crop.

    Green line = fused fish_y (what the controller used).
    Red line   = raw detected_fish_y (what the detector reported).
    """
    img_h, img_w = image.shape[:2]

    fused_y = float(entry['fish_y'])
    fused_px = max(0, min(img_h - 1, int(round(fused_y * (img_h - 1)))))

    detected_y = entry.get('detected_fish_y')
    raw_px = None
    if detected_y is not None:
        raw_px = max(0, min(img_h - 1, int(round(float(detected_y) * (img_h - 1)))))

    confidence = _frame_confidence(entry)
    method = entry.get('method', 'none')

    line1 = f"frame={frame_number:05d} conf={confidence:.2f} method={method}"
    raw_str = f"{float(detected_y):.3f}" if detected_y is not None else "n/a"
    line2 = f"raw={raw_str} fused={fused_y:.3f}"
    labels = [line1, line2]

    label_sizes = [cv2.getTextSize(l, LABEL_FONT, LABEL_FONT_SCALE, LABEL_FONT_THICKNESS)[0]
                   for l in labels]
    max_label_w = max(s[0] for s in label_sizes)
    line_height = label_sizes[0][1] + 8

    panel_width = LABEL_LINE_EXTENSION + max_label_w + LABEL_PADDING * 2
    annotated = cv2.copyMakeBorder(
        image,
        0,
        0,
        0,
        panel_width,
        cv2.BORDER_CONSTANT,
        value=LABEL_PANEL_COLOR,
    )

    # Green line — fused position the controller acted on
    cv2.line(annotated, (0, fused_px), (img_w + LABEL_LINE_EXTENSION, fused_px), (0, 200, 0), 2)

    # Red line — raw detector observation
    if raw_px is not None:
        cv2.line(annotated, (0, raw_px), (img_w + LABEL_LINE_EXTENSION, raw_px), (0, 0, 255), 1)

    text_x = img_w + LABEL_LINE_EXTENSION + LABEL_PADDING
    text_y = fused_px - 8
    min_text_y = label_sizes[0][1] + 6
    max_text_y = img_h - line_height * len(labels) - 6
    text_y = max(min_text_y, min(max_text_y, text_y))

    for i, label in enumerate(labels):
        ly = text_y + i * line_height
        lsz = label_sizes[i]
        box_tl = (max(0, text_x - 4), max(0, ly - lsz[1] - 4))
        box_br = (
            min(annotated.shape[1] - 1, text_x + lsz[0] + 4),
            min(img_h - 1, ly + 6),
        )
        cv2.rectangle(annotated, box_tl, box_br, (0, 0, 0), -1)
        cv2.putText(
            annotated,
            label,
            (text_x, ly),
            LABEL_FONT,
            LABEL_FONT_SCALE,
            (255, 255, 255),
            LABEL_FONT_THICKNESS,
            cv2.LINE_AA,
        )

    return annotated


def export_event(session_dir, event_name, output_dir):
    """Export annotated raw crops for one live-debug event."""
    telemetry_path = os.path.join(session_dir, 'telemetry.jsonl')
    event_dir = os.path.join(session_dir, 'events', event_name)
    telemetry_by_frame = _load_telemetry_index(telemetry_path)

    os.makedirs(output_dir, exist_ok=True)
    exported = 0
    missing = []

    for name in sorted(os.listdir(event_dir)):
        if not name.endswith('_raw.png'):
            continue
        frame_number = int(name.split('_', 1)[0])
        entry = telemetry_by_frame.get(frame_number)
        if entry is None:
            missing.append(frame_number)
            continue

        raw_path = os.path.join(event_dir, name)
        image = cv2.imread(raw_path)
        if image is None:
            missing.append(frame_number)
            continue

        annotated = _annotate_frame(image, entry, frame_number)
        out_name = f"{frame_number:05d}_annotated.png"
        out_path = os.path.join(output_dir, out_name)
        if not cv2.imwrite(out_path, annotated):
            raise IOError(f'Could not write {out_path}')
        exported += 1

    return exported, missing


def main():
    parser = argparse.ArgumentParser(description='Export annotated live-run fish crops')
    parser.add_argument('--session', required=True, help='Path to the live_debug_runs session directory')
    parser.add_argument('--event', required=True, help='Event folder name inside the session events directory')
    parser.add_argument('--output-dir', required=True, help='Directory for annotated image exports')
    args = parser.parse_args()

    exported, missing = export_event(args.session, args.event, args.output_dir)
    print(json.dumps({
        'session': args.session,
        'event': args.event,
        'output_dir': args.output_dir,
        'exported': exported,
        'missing_frames': missing,
    }, indent=2))


if __name__ == '__main__':
    main()