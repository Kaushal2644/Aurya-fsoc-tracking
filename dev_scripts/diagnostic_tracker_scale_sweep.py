# dev_scripts/diagnostic_tracker_scale_sweep.py
"""
Sweeps several process_noise/measurement_noise scaling strategies
against the real 2x-resolution test video, to find what actually
works — rather than guessing another formula.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.frame_source import VideoFileFrameSource
from core.detector import BlobDetector
from core.tracker import KalmanTracker

def run_trial(process_noise, measurement_noise, label):
    src = VideoFileFrameSource(
        "test_videos/sample4_diffres.mp4",
        "test_videos/sample4_diffres_ground_truth.csv",
        verbose=False,
    )
    detector = BlobDetector(min_area=200, max_area=720)
    tracker = KalmanTracker(process_noise=process_noise, measurement_noise=measurement_noise)

    dt = 1.0 / 30
    errors = []
    for i in range(120):
        frame, gt, t = src.get_frame()
        if frame is None:
            break
        det = detector.detect_best(frame)
        tracker.predict(dt)
        tracker.update(det)
        est = tracker.get_estimate()
        if est and gt:
            err = ((est[0] - gt[0]) ** 2 + (est[1] - gt[1]) ** 2) ** 0.5
            errors.append(err)

    avg_err = sum(errors) / len(errors) if errors else None
    max_err = max(errors) if errors else None
    print(f"{label}: process_noise={process_noise}, measurement_noise={measurement_noise} "
          f"-> avg_err={avg_err:.2f}px, max_err={max_err:.2f}px" if avg_err else f"{label}: no data")

# Baseline (unscaled, known to fail at 2x resolution)
run_trial(25.0, 0.5, "baseline (unscaled)")

# Our attempted fix (quadratic scale, proven insufficient)
run_trial(100.0, 2.0, "quadratic x2 scale")

# Progressively stronger process_noise (let the filter trust detections more)
run_trial(300.0, 2.0, "process_noise x12")
run_trial(600.0, 2.0, "process_noise x24")
run_trial(1000.0, 2.0, "process_noise x40")
run_trial(2000.0, 1.0, "process_noise x80, R back to baseline")

# Continuing the trend that's working — push further
run_trial(3000.0, 1.0, "process_noise x120, R=1.0")
run_trial(4000.0, 0.5, "process_noise x160, R back to original 0.5")
run_trial(5000.0, 0.5, "process_noise x200, R=0.5")
run_trial(3000.0, 0.5, "process_noise x120, R=0.5")