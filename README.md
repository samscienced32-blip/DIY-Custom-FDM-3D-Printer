# 3DPrintSaviour for Marlin + Dual Cameras

## Objective
This fork adapts the original OctoPrint/Octolapse workflow to a custom Marlin-based printer that is connected directly over USB serial and monitored with two cameras.

The new workflow is:

1. `run` opens two cameras and captures a background frame for each one.
2. It listens to the Marlin serial console for layer markers such as `M118 LAYER:12`.
3. On every trigger, it captures frames from both cameras, computes the original NRMSE-based metrics per camera, and optionally runs spaghetti detection.
4. If either camera reports a configured failure condition, `printcontrol.py` sends Marlin pause G-code over serial.

If layer messages are not available yet, `run` can also fall back to timed captures.


- `SERIAL_PORT` to the printer port, for example `COM5`
- `PAUSE_COMMANDS` to the pause/stop G-code that matches the printer workflow
- `CAMERAS` so both camera sources, crop areas, rotation, and mirroring are correct
- `TRIGGER_MODE` to `layer`, `timer`, or `hybrid`

## Recommended Marlin trigger setup
For best results, make your slicer emit a serial message at every layer change (didn't work well without this). A simple pattern is:

```gcode
M118 LAYER:[layer_num]
```

That lets `run` capture images at repeatable layer boundaries instead of arbitrary time intervals.

## Installation
Create a Python environment and install the runtime dependencies:

```bash
pip install numpy scipy scikit-image opencv-python pyserial matplotlib
```

For spaghetti detection, also download the Darknet weights file into `ml_api/model/model.weights` using the URL in `ml_api/model/model.weights.url`.

## Running the monitor
The monitor needs to be started before beginning the print so capture index `000000.jpg` becomes the empty-bed background reference:

```bash
python run --job-name test_part
```

Useful options:

```bash
python run --trigger-mode layer
python run --trigger-mode timer --capture-interval 10
python run --background-only --job-name calibration
```

Captured sessions are written under `captures/<job-name>/` with this layout:

```text
captures/
  test_part/
    cam0_top/
      000000.jpg
      000001.jpg
      output.log
    cam1_side/
      000000.jpg
      000001.jpg
      output.log
    combined/
      000000.jpg
      000001.jpg
    events.log
```

## Detection logic
The score rules run per camera:

- Detachment: `score > 1.0` and `deviance > 1.0`
- Breakage: `score_diff > 0.2` and `deviance_diff > 0.2`
- Filament runout/clog: `score < 0.2` and `deviance < 0.2`
- Spaghetti: Darknet model reports one or more spaghetti detections

The confirmation mode is controlled by `FAILURE_CONFIRMATION_MODE` in [`api_keys.py`](/C:/Users/sagar/OneDrive/Desktop/Applications/Criss/3DPrintSaviour-marlin/api_keys.py):

- `any`: pause when one camera confirms a failure
- `all`: pause only when both cameras confirm a failure

## Utility scripts
- [`get_score.py`](/C:/Users/sagar/OneDrive/Desktop/Applications/Criss/3DPrintSaviour-marlin/get_score.py) calculates metrics for one saved frame
- [`data_visualisation.py`](/C:/Users/sagar/OneDrive/Desktop/Applications/Criss/3DPrintSaviour-marlin/data_visualisation.py) plots one camera `output.log`
- [`gen_video.py`](/C:/Users/sagar/OneDrive/Desktop/Applications/Criss/3DPrintSaviour-marlin/gen_video.py) builds a preview video from a camera or combined capture folder

## Notes for custom printers
- Some Arduino-style boards reset when a serial connection opens. `DISABLE_DTR_ON_CONNECT` is included to reduce that risk, but behaviour still depends on your USB interface and firmware board.
- `M25` is mainly for SD-card prints. If your printer is driven differently, adjust `PAUSE_COMMANDS` to match your Marlin setup.
- For the most reliable image comparison, park the toolhead out of frame at each trigger point or choose camera angles where the nozzle does not hide the part.


