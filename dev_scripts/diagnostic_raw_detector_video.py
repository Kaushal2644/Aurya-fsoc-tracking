"""
diagnostic_raw_detector_video.py
Checks raw detector accuracy directly against ground truth CSV,
on the video file, with NO Kalman filter involved.
"""

from core.frame_source import VideoFileFrameSource
from core.detector import BlobDetector

src = VideoFileFrameSource(
    video_path="test_videos/sample1.mp4",
    ground_truth_path="test_videos/sample1_ground_truth.csv",
)
detector = BlobDetector()

errors = []
count = 0
while count < 30:
    frame, gt, t = src.get_frame()
    if frame is None:
        print("End of video reached early.")
        break

    det = detector.detect_best(frame)
    if det is not None and gt is not None:
        err = ((det.x - gt[0]) ** 2 + (det.y - gt[1]) ** 2) ** 0.5
        errors.append(err)
        print(f"frame {count}: det=({det.x:.1f},{det.y:.1f}) gt=({gt[0]:.1f},{gt[1]:.1f}) err={err:.1f}")
    else:
        print(f"frame {count}: det={det}, gt={gt}")

    count += 1

if errors:
    print(f"\nAvg raw detector error on video (no Kalman): {sum(errors)/len(errors):.2f} px")

src.release()