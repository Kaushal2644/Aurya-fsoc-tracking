# quick_test_logger.py — sanity check, delete later
from core.frame_source import SimulatorFrameSource
from core.detector import BlobDetector
from core.tracker import KalmanTracker
from core.controller import TrackingController
from core.logger import PerformanceLogger
import time

src = SimulatorFrameSource(motion_type="circular", noise_types=["gaussian"])
detector = BlobDetector()
tracker = KalmanTracker()
controller = TrackingController()
logger = PerformanceLogger(run_name="test_circular_gaussian")

logger.start()
dt = 1.0 / 30

for i in range(150):
    frame_start = time.time()

    frame, gt, sim_t = src.get_frame()
    det = detector.detect_best(frame)
    tracker.predict(dt)
    tracker.update(det)
    pan_cmd, tilt_cmd, mode = controller.compute(tracker, dt)
    src.move_camera(pan_cmd, tilt_cmd)

    estimate = tracker.get_estimate()
    frame_proc_time = time.time() - frame_start

    logger.log_frame(sim_t, tracker.status, estimate, gt, frame_proc_time)

logger.stop()
logger.print_summary()
logger.export()