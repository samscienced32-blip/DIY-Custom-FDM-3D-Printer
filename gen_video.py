#!/usr/bin/env python3

"""Generate an AVI preview from a saved capture directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2


def load_events(event_log: Path):
    events = {}
    if not event_log.exists():
        return events

    with event_log.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            events[payload["capture_index"]] = payload
    return events


def label_for_event(event):
    if not event or not event.get("triggered"):
        return None
    return event.get("reason", "Failure")


def cli():
    parser = argparse.ArgumentParser(description="Build a video from a camera or combined capture directory.")
    parser.add_argument("image_dir", help="Directory containing JPG frames")
    parser.add_argument("--event-log", default=None, help="Optional events.log path")
    parser.add_argument("--output", default="output.avi")
    parser.add_argument("--fps", type=float, default=10.0)
    args = parser.parse_args()

    image_dir = Path(args.image_dir)
    image_paths = sorted(image_dir.glob("*.jpg"))
    if not image_paths:
        raise FileNotFoundError(f"No JPG files found in {image_dir}")

    events = load_events(Path(args.event_log)) if args.event_log else {}
    first_frame = cv2.imread(str(image_paths[0]))
    height, width = first_frame.shape[:2]
    writer = cv2.VideoWriter(
        args.output,
        cv2.VideoWriter_fourcc("X", "V", "I", "D"),
        args.fps,
        (width, height),
    )

    font = cv2.FONT_HERSHEY_SIMPLEX
    red = (0, 0, 255)

    for image_path in image_paths:
        frame = cv2.imread(str(image_path))
        capture_index = int(image_path.stem.split("_")[-1]) if "_" in image_path.stem else int(image_path.stem)
        label = label_for_event(events.get(capture_index))

        if label:
            cv2.rectangle(frame, (20, 20), (width - 20, height - 20), red, 10)
            cv2.putText(frame, label, (40, height - 40), font, 1.5, red, 3)

        writer.write(frame)

    writer.release()


if __name__ == "__main__":
    cli()
