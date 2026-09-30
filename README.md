# Aurya — FSOC Virtual Camera Tracking System

**Smart India Hackathon 2026 — Problem Statement SIH26169**

**Development of an AI-Based Virtual Camera Tracking System for Coarse Alignment of Mobile Free Space Optical Communication (FSOC) Terminals**

**Organization:** Indian Space Research Organisation (ISRO) — Department of Space  
**Theme:** Smart Automation  
**Category:** Software

---

## Team

**Team Name:** Aurya  
**Team ID:** 129418  
**Institution:** Shri S'ad Vidya Mandal Institute of Technology  
**Location:** Bharuch, Gujarat

| Member | Role |
|---|---|
| Parth Ravriya | Team Leader |
| Kaushal Patel | Software & System Integration |
| Ravindra Arethiya | Computer Vision & Estimation Engineer |
| Nitin Gami | Testing & Validation |
| Manav Surti | Software Engineer |
| Hiya Modi | Testing & Validation |

---

## Overview

This project implements a software-only virtual camera tracking system for the **coarse alignment** stage of Pointing, Acquisition, and Tracking (PAT) in Free Space Optical Communication.

It simulates a moving optical beacon in a configurable virtual environment, detects and tracks it using computer vision and state estimation, and controls a virtual pan-tilt camera to keep the beacon centered — without requiring any physical camera or gimbal hardware.

The system supports two input modes through a single, identical processing pipeline:

- **Simulator mode** — a fully virtual scene with configurable target motion, noise, and atmospheric disturbance
- **Video-file mode (Benchmark-2 style)** — ingests a pre-recorded `.mp4` file directly, bypassing the virtual PTZ camera

---

## Key Features

- Configurable 2000×2000 virtual scene, 640×480 camera, and 4°×3° field of view
- Four required target motion models:
  - Straight line
  - Circular
  - Figure-8
  - Random
- Optional motion models:
  - Spiral
  - Sinusoidal
- Three noise types:
  - Salt & Pepper
  - Gaussian
  - Poisson
- Independently combinable disturbance conditions
- Five atmospheric presets:
  - Clear
  - Haze
  - Fog
  - Rain
  - Low-light
- Adaptive computer-vision beacon detection using thresholding, connected-component blob analysis, and confidence scoring
- Beacon detection covering the 5–20 px beacon-size range specified by the problem statement
- Kalman filter state estimation
- M-of-N confirmation-lock logic to reduce false lock-on under noise
- PID pan/tilt camera control
- Scan-and-freeze acquisition behaviour
- Real-time PyQt5 GUI
- Live tracking overlay
- Tracking error visualization
- Configuration controls
- Automatic performance logs in CSV and JSON formats
- Resolution-aware detector and tracker scaling for video files at non-standard resolutions
- Standalone Windows executable using PyInstaller
- Docker support for reproducible CLI-based evaluation

---

## Architecture

```text
Virtual Scene / MP4 Input
          │
          ▼
   Disturbance Engine
          │
          ▼
     Blob Detector
          │
          ▼
   Kalman Tracker
   + Confirmation Lock
          │
          ▼
    PID Controller
          │
          ▼
 Virtual PTZ Camera
          │
          ▼
 Live GUI + Performance Logger
```

A single `FrameSource` abstraction (`core/frame_source.py`) provides both
`SimulatorFrameSource` and `VideoFileFrameSource`, so the detector, tracker,
and logger behave identically regardless of input source. This was validated
directly by comparing tracking accuracy on live simulation against a
noise-and-fog stress-test video, with results matching to within a fraction
of a pixel.

## Project Structure
```
Aurya-fsoc-tracking/
│
├── core/
│   ├── __init__.py
│   ├── target.py
│   ├── scene.py
│   ├── camera.py
│   ├── disturbance.py
│   ├── frame_source.py
│   ├── detector.py
│   ├── tracker.py
│   ├── controller.py
│   └── logger.py
│
├── gui/
│   ├── __init__.py
│   ├── main_window.py
│   ├── video_panel.py
│   ├── control_panel.py
│   ├── metrics_panel.py
│   └── gui_controller.py
│
├── dev_scripts/
│   ├── diagnostic_*.py
│   ├── quick_test_*.py
│   ├── generate_video.py
│   ├── generate_video_noisy.py
│   ├── generate_video_stress.py
│   └── generate_video_diffres.py
│
├── test_videos/
│   ├── sample1.mp4
│   ├── sample1_ground_truth.csv
│   ├── sample2_noisy.mp4
│   ├── sample2_noisy_ground_truth.csv
│   ├── sample3_stress.mp4
│   ├── sample3_stress_ground_truth.csv
│   ├── sample4_diffres.mp4
│   └── sample4_diffres_ground_truth.csv
│
├── docs/
│
├── config.py
├── main.py
├── main_gui.py
├── requirements.txt
├── fsoc_tracker.spec
├── .dockerignore
└── .gitignore
```
## Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| Computer Vision | OpenCV |
| Numerical Processing | NumPy |
| Data processing | Pandas |
| State Estimation | Custom Kalman Filtter |
| Camera Control | PID Controller |
| GUI | PyQt5 |
| Visualization | PyQtGraph |
| Video Processing | OpenCV |
| Packaging | PyInstaller |
| Containerization | Docker |
| Version Control | Git/Github |


## Installation (local, without Docker)

**Requirements:** Python 3.10 or newer

```bash
git clone https://github.com/Kaushal2644/Aurya-fsoc-tracking.git
cd fsoc-tracker

python -m venv venv
# Windows:
venv\Scripts\activate
# Linux / macOS:
source venv/bin/activate

pip install -r requirements.txt
```

## Usage

**GUI (recommended for demonstration):**
```bash
python main_gui.py
```

**CLI — simulator mode:**
```bash
python main.py --mode sim --motion circular --noise gaussian salt_pepper --atmosphere fog --frames 300
```

**CLI — video-file mode (Benchmark-2 style):**
```bash
python main.py --mode video --video_path path/to/video.mp4 --ground_truth_path path/to/ground_truth.csv
```

All CLI options:
```bash
python main.py --help
```

Performance reports are written to `logs/` as paired `.csv` (per-frame data)
and `.json` (run summary) files after every run.

---

## Docker Setup

Docker is provided for reproducible evaluation on any machine without a local
Python environment. The container runs the **CLI pipeline** — this is the
mode relevant to Benchmark-1 and Benchmark-2 style evaluation, where scenario
execution and the generated performance log are what's being assessed.

### 1. Build the image

From the project root, where the `Dockerfile` is located:

```bash
docker build -t fsoc-tracker .
```

### 2. Run a scenario

**Simulator mode**, with logs written back to your local machine:

```bash
docker run --rm -v "$(pwd)/logs:/app/logs" fsoc-tracker \
  --mode sim --motion circular --noise gaussian salt_pepper --atmosphere fog --frames 300
```

On Windows PowerShell, replace `$(pwd)` with `${PWD}`:

```powershell
docker run --rm -v ${PWD}/logs:/app/logs fsoc-tracker `
  --mode sim --motion circular --noise gaussian salt_pepper --atmosphere fog --frames 300
```

**Video-file mode** (mount a folder containing your `.mp4` and ground truth
CSV, then reference it inside the container):

```bash
docker run --rm \
  -v "$(pwd)/test_videos:/app/test_videos" \
  -v "$(pwd)/logs:/app/logs" \
  fsoc-tracker \
  --mode video --video_path test_videos/sample1.mp4 \
  --ground_truth_path test_videos/sample1_ground_truth.csv --frames 300
```

### 3. Check results

After the run finishes, the performance summary prints to the console, and
`logs/` on your host machine will contain the generated `_frames.csv` and
`_summary.json` files.

### Notes for evaluators

- The container does not include a GUI. This is intentional — the GUI
  requires a display server, which adds setup burden with no benefit for
  scenario-based evaluation. The GUI can be run directly via
  `python main_gui.py` after the local installation steps above, on any
  machine with a desktop environment.
- The image is based on `python:3.11-slim` with only the OpenCV system
  dependencies added, to keep the build small and the evaluation environment
  minimal and auditable.

---

## Performance (measured, not projected)

| Metric | ISRO Spec | Measured |
|---|---|---|
| Acquisition Time | ≤ 2 s | 0.07–0.10 s (beacon starting in camera view) |
| Tracking Error (avg) | ≤ 10 px | 2.2–7.3 px across tested scenarios |
| Target Loss Rate | < 5% | 0.0% (post-lock) |
| Processing Speed | ≥ 20 FPS | 65–240 FPS (video mode) |

Full test methodology, scenario coverage, and results are documented in the
Technical Report.

## Known Limitations

These are documented honestly rather than omitted, per our own testing
process:

- Kalman tracker noise parameters are empirically calibrated for 640×480 and
  one validated 2× resolution case; other resolutions require a separate
  calibration pass (see `dev_scripts/diagnostic_tracker_scale_sweep.py`)
- Haze and Rain atmospheric presets are implemented but not yet
  systematically stress-tested
- Re-acquisition timing (post-loss recovery) has not been measured in a
  dedicated test scenario
- Poisson noise generation has a measured performance cost in low-light
  scenarios, root-caused to `numpy.random.Generator.poisson` call overhead;
  not yet optimized, no correctness impact

## License

This project was developed as a submission for Smart India Hackathon 2026,
under Problem Statement SIH26169 (Department of Space / ISRO). Intellectual
property arising from SIH submissions may be subject to the terms of the
Smart India Hackathon participation agreement and the sponsoring
organization's policies, which take precedence over any license stated here.

Subject to those terms, the source code in this repository is made available
for educational and evaluation purposes. Contact the team for reuse beyond
that scope.
