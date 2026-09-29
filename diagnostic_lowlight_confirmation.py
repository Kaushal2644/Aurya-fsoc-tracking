"""
diagnostic_lowlight_confirmation.py
Tracks confirmation-state and detection hit/miss pattern frame-by-frame
under low_light+poisson, to see whether detection is truly flickering
and whether confirmation attempts are repeatedly failing to complete.
"""

from core.frame_source import SimulatorFrameSource
from core.detector import BlobDetector
from core.tracker import KalmanTracker
from core.controller import TrackingController

src = SimulatorFrameSource(
    motion_type="straight_line",
    noise_types=["poisson"],
    atmospheric_preset="low_light",
    seed=42,   # known to bring the target into view reasonably (per earlier main.py test)
)
detector = BlobDetector()
tracker = KalmanTracker()
controller = TrackingController()

dt = 1.0 / 30
hit_count = 0
miss_count = 0
lock_events = 0
prev_status = "SEARCHING"

for i in range(600):  # longer run, since target takes time to appear
    frame, gt, t = src.get_frame()
    detections = detector.detect(frame)

    tracker.predict(dt)
    det = tracker.select_best_detection(detections)
    tracker.update(det)

    pan_cmd, tilt_cmd, mode = controller.compute(tracker, dt)
    src.move_camera(pan_cmd, tilt_cmd)

    if gt is not None:  # only count hit/miss once target is actually visible
        if det is not None:
            hit_count += 1
        else:
            miss_count += 1

    if tracker.status == "LOCKED" and prev_status != "LOCKED":
        lock_events += 1
    prev_status = tracker.status

    if i % 20 == 0:
        print(f"frame {i}: status={tracker.status} pending_count={tracker._pending_count} "
              f"unconfirmed_frames={tracker._unconfirmed_frames} det={'hit' if det else 'miss'} gt_visible={gt is not None}")

print(f"\nTotal hits: {hit_count}, misses: {miss_count} (while target visible)")
print(f"Lock events (SEARCHING/LOST -> LOCKED transitions): {lock_events}")