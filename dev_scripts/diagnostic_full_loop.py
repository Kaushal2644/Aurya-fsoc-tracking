"""
diagnostic_full_loop.py
Mirrors main.py's exact loop (detector + tracker + controller +
camera movement) so we can see confirmation state alongside real
camera motion — diagnostic_confirmation.py never moved the camera,
so it couldn't reveal this interaction.
"""

from core.frame_source import SimulatorFrameSource
from core.detector import BlobDetector
from core.tracker import KalmanTracker
from core.controller import TrackingController

src = SimulatorFrameSource(
    motion_type="circular",
    noise_types=["gaussian", "salt_pepper"],
    atmospheric_preset="fog",
    seed=1,
)
detector = BlobDetector()
tracker = KalmanTracker()
controller = TrackingController()

dt = 1.0 / 30
for i in range(40):
    frame, gt, t = src.get_frame()
    detections = detector.detect(frame)

    tracker.predict(dt)
    det = tracker.select_best_detection(detections)
    tracker.update(det)

    pan_cmd, tilt_cmd, mode = controller.compute(tracker, dt)
    src.move_camera(pan_cmd, tilt_cmd)

    print(f"frame {i}: status={tracker.status} mode={mode} "
          f"pending_count={tracker._pending_count} pending_gap={tracker._pending_gap} "
          f"pan_cmd={pan_cmd:.2f} tilt_cmd={tilt_cmd:.2f} "
          f"raw_det={'None' if det is None else (round(det.x,1), round(det.y,1))} "
          f"gt={gt}")