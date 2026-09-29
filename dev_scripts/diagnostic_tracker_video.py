"""
diagnostic_tracker_video.py
Runs detector + Kalman tracker together (like main.py does),
but computes tracking error directly here — bypassing logger.py
entirely — to check if the Kalman filter itself is the problem.
"""

from core.frame_source import VideoFileFrameSource
from core.detector import BlobDetector
from core.tracker import KalmanTracker

src = VideoFileFrameSource(
    video_path="test_videos/sample1.mp4",
    ground_truth_path="test_videos/sample1_ground_truth.csv",
)
detector = BlobDetector()
tracker = KalmanTracker()

dt = 1.0 / 30
errors = []
count = 0

while count < 60:
    frame, gt, t = src.get_frame()
    if frame is None:
        break

    det = detector.detect_best(frame)
    tracker.predict(dt)
    tracker.update(det)
    estimate = tracker.get_estimate()

    if estimate is not None and gt is not None:
        err = ((estimate[0] - gt[0]) ** 2 + (estimate[1] - gt[1]) ** 2) ** 0.5
        errors.append(err)
        print(f"frame {count}: status={tracker.status} estimate=({estimate[0]:.1f},{estimate[1]:.1f}) "
              f"gt=({gt[0]:.1f},{gt[1]:.1f}) err={err:.1f}")
    else:
        print(f"frame {count}: status={tracker.status} estimate={estimate}, gt={gt}")

    count += 1

if errors:
    print(f"\nAvg tracker error (detector+Kalman, bypassing logger.py): {sum(errors)/len(errors):.2f} px")

src.release()