"""Project configuration for a Marlin-based dual-camera monitor.

Keep this file simple so it can be edited directly for a specific printer.
"""

# Serial connection to the Marlin controller board.
SERIAL_PORT = "COM5"
SERIAL_BAUDRATE = 250000
SERIAL_TIMEOUT = 1.0
SERIAL_READY_DELAY_SECONDS = 2.0
DISABLE_DTR_ON_CONNECT = True

# Commands sent when a failure is confirmed.
# `M25` pauses SD-card prints, while `M0` is a generic stop/pause command.
# Adjust these to match how your printer is driven.
PAUSE_COMMANDS = [
    "M400",
    "M25",
    "M0 Failure detected",
]

STOP_COMMANDS = [
    "M400",
    "M112",
]

# How capture events are triggered.
# - "layer": only react to serial layer markers such as `M118 LAYER:12`
# - "timer": capture at a fixed interval
# - "hybrid": listen for layer markers, but fall back to timed capture until
#   they appear
TRIGGER_MODE = "hybrid"
CAPTURE_INTERVAL_SECONDS = 8.0
SERIAL_LAYER_PATTERNS = (
    "LAYER:",
    "layer:",
)

# Capture frames from both cameras before starting the print so index 0 can be
# used as the empty-bed background reference.
CAPTURE_ROOT = "captures"
CAPTURE_WARMUP_FRAMES = 8
CAPTURE_FRAME_DELAY_SECONDS = 0.05
JPEG_QUALITY = 95
SAVE_COMPOSITE_FRAMES = True

# Detection starts only after a few comparable frames exist.
MIN_ANALYSIS_INDEX = 7
COMPARISON_DEPTH = 5
PIXEL_DIFF_THRESHOLD = 20
FAILURE_CONFIRMATION_MODE = "any"
ENABLE_SPAGHETTI_DETECTION = True
SPAGHETTI_THRESHOLD = 0.3

# Thresholds inherited from the original project and kept configurable.
DETACHMENT_SCORE_THRESHOLD = 1.0
DETACHMENT_DEVIANCE_THRESHOLD = 1.0
BREAKAGE_SCORE_DIFF_THRESHOLD = 0.2
BREAKAGE_DEVIANCE_DIFF_THRESHOLD = 0.2
FILAMENT_SCORE_THRESHOLD = 0.2
FILAMENT_DEVIANCE_THRESHOLD = 0.2

# Configure both cameras here. `source` can be an integer device index or a
# stream URL. `crop` is optional and uses:
# (y_start, y_end, x_start, x_end)
CAMERAS = [
    {
        "name": "cam0_top",
        "source": 0,
        "rotate": 0,
        "mirror": False,
        "crop": None,
    },
    {
        "name": "cam1_side",
        "source": 1,
        "rotate": 0,
        "mirror": False,
        "crop": None,
    },
]
