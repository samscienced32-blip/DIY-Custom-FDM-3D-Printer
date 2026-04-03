#!/usr/bin/env python3

"""Image comparison helpers for per-camera failure scoring."""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

import cv2
from skimage.metrics import normalized_root_mse

from api_keys import CAMERAS, COMPARISON_DEPTH, PIXEL_DIFF_THRESHOLD

INDEX_PATTERN = re.compile(r"(\d+)(?=\.[^.]+$)")


def get_camera_settings(camera_name: str | None) -> dict:
    if not camera_name:
        return {}

    for camera in CAMERAS:
        if camera["name"] == camera_name:
            return camera
    return {}


def extract_frame_index(image_path: str | Path) -> int:
    match = INDEX_PATTERN.search(Path(image_path).name)
    if not match:
        raise ValueError(f"Could not extract a numeric frame index from {image_path}")
    return int(match.group(1))


def build_indexed_path(image_path: str | Path, index: int) -> Path:
    image_path = Path(image_path)
    match = INDEX_PATTERN.search(image_path.name)
    if not match:
        raise ValueError(f"Could not rebuild image path for {image_path}")

    padded = str(index).rjust(len(match.group(1)), "0")
    new_name = image_path.name[: match.start(1)] + padded + image_path.name[match.end(1) :]
    return image_path.with_name(new_name)


def resolve_crop_bounds(image, crop):
    height, width = image.shape[:2]
    if not crop:
        return 0, height, 0, width

    if isinstance(crop, dict):
        y_start = int(crop.get("y_start", 0))
        y_end = crop.get("y_end", height)
        x_start = int(crop.get("x_start", 0))
        x_end = crop.get("x_end", width)
    else:
        if len(crop) != 4:
            raise ValueError("Crop must contain 4 values: (y_start, y_end, x_start, x_end)")
        y_start, y_end, x_start, x_end = crop

    y_end = height if y_end is None else int(y_end)
    x_end = width if x_end is None else int(x_end)

    return max(0, y_start), min(height, y_end), max(0, x_start), min(width, x_end)


def load_grayscale(image_path: str | Path, crop=None):
    image = cv2.imread(str(image_path), 0)
    if image is None:
        raise FileNotFoundError(f"Could not read image {image_path}")

    y_start, y_end, x_start, x_end = resolve_crop_bounds(image, crop)
    return image[y_start:y_end, x_start:x_end]


def threshold_foreground(current_gray, background_gray, threshold):
    diff = cv2.absdiff(current_gray, background_gray)
    return cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)[1]


def safe_nrmse(reference, candidate):
    if cv2.countNonZero(reference) == 0 and cv2.countNonZero(candidate) == 0:
        return 0.0

    value = float(normalized_root_mse(reference, candidate))
    if math.isnan(value) or math.isinf(value):
        return 0.0
    return value


def read_previous_metrics(logfile: str | Path):
    logfile = Path(logfile)
    if not logfile.exists():
        return None

    with logfile.open("r", encoding="utf-8") as handle:
        lines = [line.strip() for line in handle.readlines() if line.strip()]

    for line in reversed(lines):
        parts = line.split()
        if len(parts) != 5:
            continue
        try:
            return {
                "index": int(parts[0]),
                "score": float(parts[1]),
                "deviance": float(parts[2]),
                "score_diff": float(parts[3]),
                "deviance_diff": float(parts[4]),
            }
        except ValueError:
            continue

    return None


def calculate_metrics(
    image_path: str | Path,
    camera_name: str | None = None,
    threshold: int = PIXEL_DIFF_THRESHOLD,
    comparison_depth: int = COMPARISON_DEPTH,
):
    image_path = Path(image_path)
    camera_settings = get_camera_settings(camera_name)
    crop = camera_settings.get("crop")

    current_index = extract_frame_index(image_path)
    result = {
        "index": current_index,
        "camera": camera_name,
        "image_path": str(image_path),
        "status": "ok",
        "score": math.nan,
        "deviance": math.nan,
        "score_diff": math.nan,
        "deviance_diff": math.nan,
    }

    if current_index == 0:
        result["status"] = "background"
        return result

    if current_index == 1:
        result["status"] = "warmup"
        return result

    previous_path = build_indexed_path(image_path, current_index - 1)
    background_path = build_indexed_path(image_path, 0)

    current_gray = load_grayscale(image_path, crop)
    previous_gray = load_grayscale(previous_path, crop)
    background_gray = load_grayscale(background_path, crop)

    thresholded_current = threshold_foreground(current_gray, background_gray, threshold)
    thresholded_previous = threshold_foreground(previous_gray, background_gray, threshold)

    result["score"] = safe_nrmse(thresholded_current, thresholded_previous)

    if current_index > comparison_depth:
        history_path = build_indexed_path(image_path, current_index - comparison_depth)
        history_gray = load_grayscale(history_path, crop)
        thresholded_history = threshold_foreground(history_gray, background_gray, threshold)

        result["deviance"] = safe_nrmse(thresholded_current, thresholded_history)

        previous_metrics = read_previous_metrics(image_path.parent / "output.log")
        if previous_metrics:
            result["score_diff"] = abs(result["score"] - previous_metrics["score"])
            result["deviance_diff"] = abs(result["deviance"] - previous_metrics["deviance"])
    else:
        result["deviance"] = 1.0
        result["score_diff"] = 0.0
        result["deviance_diff"] = 0.0

    return result


def format_metrics(metrics) -> str:
    if metrics["status"] in {"background", "warmup"}:
        return f"{metrics['index']} nan"

    return "{} {} {} {} {}".format(
        metrics["index"],
        metrics["score"],
        metrics["deviance"],
        metrics["score_diff"],
        metrics["deviance_diff"],
    )


def cli():
    parser = argparse.ArgumentParser(description="Calculate score metrics for a captured frame.")
    parser.add_argument("image_path", help="Path to the current image")
    parser.add_argument("--camera", help="Camera name from api_keys.py", default=None)
    parser.add_argument("--threshold", type=int, default=PIXEL_DIFF_THRESHOLD)
    parser.add_argument("--comparison-depth", type=int, default=COMPARISON_DEPTH)
    args = parser.parse_args()

    metrics = calculate_metrics(
        args.image_path,
        camera_name=args.camera,
        threshold=args.threshold,
        comparison_depth=args.comparison_depth,
    )

    print(format_metrics(metrics))
    print(args.image_path)


if __name__ == "__main__":
    cli()
