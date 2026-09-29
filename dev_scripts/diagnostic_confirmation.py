"""
diagnostic_confirmation.py
Prints raw detector output and confirmation-counter state, frame by
frame, under the failing fog+salt-pepper scenario — so we can see
exactly why confirmation never completes, instead of guessing.
"""

from core.frame_source import SimulatorFrameSource
from core.detector import BlobDetector
from core.tracker import KalmanTracker

src = SimulatorFrameSource(
    motion_type="circular",
    noise_types=["gaussian", "salt_pepper"],
    atmospheric_preset="fog",
    seed=1,
)
detector = BlobDetector()
tracker = KalmanTracker()

dt = 1.0 / 30
for i in range(40):
    frame, gt, t = src.get_frame()
    detections = detector.detect(frame)

    tracker.predict(dt)
    det = tracker.select_best_detection(detections)
    tracker.update(det)

    num_raw = len(detections)
    best = detections[0] if detections else None

    print(f"frame {i}: raw_count={num_raw} "
          f"best_raw={'None' if best is None else (round(best.x,1), round(best.y,1), round(best.confidence,2))} "
          f"gated_det={'None' if det is None else (round(det.x,1), round(det.y,1))} "
          f"status={tracker.status} pending_count={tracker._pending_count} pending_gap={tracker._pending_gap} "
          f"gt={gt}")