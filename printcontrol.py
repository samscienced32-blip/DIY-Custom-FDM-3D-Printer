#!/usr/bin/env python3

"""Failure classification and Marlin serial printer control."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2

from api_keys import (
    BREAKAGE_DEVIANCE_DIFF_THRESHOLD,
    BREAKAGE_SCORE_DIFF_THRESHOLD,
    DETACHMENT_DEVIANCE_THRESHOLD,
    DETACHMENT_SCORE_THRESHOLD,
    DISABLE_DTR_ON_CONNECT,
    ENABLE_SPAGHETTI_DETECTION,
    FAILURE_CONFIRMATION_MODE,
    FILAMENT_DEVIANCE_THRESHOLD,
    FILAMENT_SCORE_THRESHOLD,
    MIN_ANALYSIS_INDEX,
    PAUSE_COMMANDS,
    SERIAL_BAUDRATE,
    SERIAL_PORT,
    SERIAL_READY_DELAY_SECONDS,
    SERIAL_TIMEOUT,
    SPAGHETTI_THRESHOLD,
    STOP_COMMANDS,
)

try:
    import serial
except ImportError:  # pragma: no cover - depends on local environment
    serial = None


MODEL_DIR = Path(__file__).resolve().parent / "ml_api" / "model"
_NET_BUNDLE = None


def _load_spaghetti_model():
    global _NET_BUNDLE
    if _NET_BUNDLE is not None:
        return _NET_BUNDLE

    from ml_api.lib.detection_model import detect, load_net

    net, meta = load_net(
        str(MODEL_DIR / "model.cfg"),
        str(MODEL_DIR / "model.weights"),
        str(MODEL_DIR / "model.meta"),
    )
    _NET_BUNDLE = (detect, net, meta)
    return _NET_BUNDLE


class MarlinPrinterController:
    def __init__(
        self,
        port: str = SERIAL_PORT,
        baudrate: int = SERIAL_BAUDRATE,
        timeout: float = SERIAL_TIMEOUT,
        ready_delay: float = SERIAL_READY_DELAY_SECONDS,
    ):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ready_delay = ready_delay
        self.connection = None

    def connect(self):
        if self.connection and self.connection.is_open:
            return self.connection

        if serial is None:
            raise RuntimeError("pyserial is required for Marlin printer control")

        connection = serial.Serial()
        connection.port = self.port
        connection.baudrate = self.baudrate
        connection.timeout = self.timeout
        connection.write_timeout = self.timeout
        connection.rtscts = False
        connection.dsrdtr = False
        connection.open()

        if DISABLE_DTR_ON_CONNECT:
            try:
                connection.dtr = False
                connection.rts = False
            except (AttributeError, OSError):
                pass

        self.connection = connection
        time.sleep(self.ready_delay)
        self.flush_input()
        return self.connection

    def flush_input(self):
        if not self.connection:
            return

        try:
            self.connection.reset_input_buffer()
        except (OSError, AttributeError):
            pass

    def read_line(self) -> str:
        self.connect()
        try:
            line = self.connection.readline()
        except OSError:
            return ""
        return line.decode("utf-8", errors="ignore").strip()

    def send_command(self, command: str):
        self.connect()
        payload = (command.strip() + "\n").encode("ascii", errors="ignore")
        self.connection.write(payload)
        self.connection.flush()
        time.sleep(0.15)

    def pause_print(self, reason: str, reported_layer=None, reports=None):
        summary = summarise_reports(reports or [])
        message = reason if reported_layer is None else f"{reason} @ {reported_layer}"
        try:
            self.send_command(f"M118 E1 FAILURE:{message}")
        except OSError:
            pass

        for command in PAUSE_COMMANDS:
            self.send_command(command)

        return {
            "action": "pause",
            "reason": reason,
            "reported_layer": reported_layer,
            "summary": summary,
        }

    def emergency_stop(self, reason: str = "Manual stop requested"):
        try:
            self.send_command(f"M118 E1 STOP:{reason}")
        except OSError:
            pass

        for command in STOP_COMMANDS:
            self.send_command(command)

    def close(self):
        if self.connection and self.connection.is_open:
            self.connection.close()


def analyse_camera_frame(camera_name, metrics, image_path, reported_layer=None):
    report = {
        "camera": camera_name,
        "reported_layer": reported_layer,
        "index": metrics["index"],
        "reason": None,
        "triggered": False,
        "status": metrics["status"],
        "metrics": metrics,
        "image_path": str(image_path),
    }

    if metrics["status"] in {"background", "warmup"}:
        return report

    if metrics["index"] < MIN_ANALYSIS_INDEX:
        report["status"] = "waiting"
        return report

    score = metrics["score"]
    deviance = metrics["deviance"]
    score_diff = metrics["score_diff"]
    deviance_diff = metrics["deviance_diff"]

    if score > DETACHMENT_SCORE_THRESHOLD and deviance > DETACHMENT_DEVIANCE_THRESHOLD:
        report["triggered"] = True
        report["reason"] = "Print detached from bed"
        return report

    if score_diff > BREAKAGE_SCORE_DIFF_THRESHOLD and deviance_diff > BREAKAGE_DEVIANCE_DIFF_THRESHOLD:
        report["triggered"] = True
        report["reason"] = "Potential partial breakage"
        return report

    if score < FILAMENT_SCORE_THRESHOLD and deviance < FILAMENT_DEVIANCE_THRESHOLD:
        report["triggered"] = True
        report["reason"] = "Filament runout or nozzle clog"
        return report

    if ENABLE_SPAGHETTI_DETECTION:
        detections = detect_spaghetti(image_path)
        if detections:
            report["triggered"] = True
            report["reason"] = "Spaghetti detected"
            report["spaghetti_detections"] = len(detections)

    return report


def detect_spaghetti(image_path):
    if not ENABLE_SPAGHETTI_DETECTION:
        return []

    image = cv2.imread(str(image_path))
    if image is None:
        return []

    try:
        detect, net, meta = _load_spaghetti_model()
        return detect(net, meta, image, thresh=SPAGHETTI_THRESHOLD)
    except Exception:
        return []


def decide_failure(camera_reports, confirmation_mode: str = FAILURE_CONFIRMATION_MODE):
    actionable = [report for report in camera_reports if report["status"] not in {"background", "warmup"}]
    triggered = [report for report in actionable if report["triggered"]]

    if not actionable:
        return {"triggered": False, "reason": None, "reports": camera_reports}

    if confirmation_mode == "all":
        decision = len(triggered) == len(actionable)
    else:
        decision = len(triggered) >= 1

    if not decision:
        return {"triggered": False, "reason": None, "reports": camera_reports}

    reasons = []
    for report in triggered:
        label = report["reason"]
        if label not in reasons:
            reasons.append(label)

    return {
        "triggered": True,
        "reason": " / ".join(reasons),
        "reports": camera_reports,
    }


def summarise_reports(camera_reports):
    summary = []
    for report in camera_reports:
        metrics = report.get("metrics", {})
        summary.append(
            {
                "camera": report.get("camera"),
                "status": report.get("status"),
                "triggered": report.get("triggered"),
                "reason": report.get("reason"),
                "index": report.get("index"),
                "reported_layer": report.get("reported_layer"),
                "score": metrics.get("score"),
                "deviance": metrics.get("deviance"),
                "score_diff": metrics.get("score_diff"),
                "deviance_diff": metrics.get("deviance_diff"),
                "image_path": report.get("image_path"),
            }
        )
    return summary


def cli():
    parser = argparse.ArgumentParser(description="Evaluate a saved frame and optionally emit a pause command.")
    parser.add_argument("--camera", required=True)
    parser.add_argument("--metrics", required=True, help="JSON metrics payload from get_score.py")
    parser.add_argument("--image", required=True)
    parser.add_argument("--reported-layer", default=None)
    parser.add_argument("--pause", action="store_true", help="Send configured pause G-code if a failure is triggered")
    args = parser.parse_args()

    metrics = json.loads(args.metrics)
    report = analyse_camera_frame(args.camera, metrics, args.image, args.reported_layer)
    decision = decide_failure([report])
    print(json.dumps(decision, indent=2))

    if args.pause and decision["triggered"]:
        controller = MarlinPrinterController()
        try:
            controller.pause_print(decision["reason"], args.reported_layer, decision["reports"])
        finally:
            controller.close()


if __name__ == "__main__":
    cli()
