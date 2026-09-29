"""
gui/gui_controller.py
Wraps the core tracking pipeline (frame_source, detector, tracker,
controller, logger) for tick-driven execution from the GUI's QTimer,
instead of main.py's blocking while-loop.

The GUI calls tick() once per timer interval; this returns everything
the UI panels need to redraw themselves that frame.
"""

import time
import config
from core.frame_source import SimulatorFrameSource, VideoFileFrameSource
from core.detector import BlobDetector
from core.tracker import KalmanTracker
from core.controller import TrackingController
from core.logger import PerformanceLogger


class TickResult:
    """Everything one frame's worth of GUI panels need to redraw."""

    def __init__(self):
        self.frame = None
        self.estimate = None
        self.ground_truth = None
        self.status = "SEARCHING"
        self.mode = "SEARCHING"
        self.sim_time = 0.0
        self.error_px = None
        self.fps_instant = None
        self.frame_idx = 0
        self.end_of_stream = False


class GuiController:
    """
    Owns the pipeline objects and exposes start/stop/tick/reconfigure
    methods the GUI wires to buttons and a QTimer.
    """

    def __init__(self):
        self.src = None
        self.detector = None
        self.tracker = None
        self.controller = None
        self.logger = None

        self.dt = 1.0 / config.TARGET_PROCESSING_FPS_MIN
        self.frame_idx = 0
        self.running = False

        # Current config (set via configure(), read by main_window's controls)
        self.mode = "sim"                # "sim" | "video"
        self.motion_type = config.TARGET_MOTION_DEFAULT
        self.noise_types = []
        self.atmospheric_preset = "clear"
        self.video_path = None
        self.ground_truth_path = None
        self.seed = 42

    # ------------------------------------------------------------------
    def configure(
        self,
        mode="sim",
        motion_type=config.TARGET_MOTION_DEFAULT,
        noise_types=None,
        atmospheric_preset="clear",
        video_path=None,
        ground_truth_path=None,
        seed=42,
    ):
        """Called before start() whenever the user changes config panel settings."""
        self.mode = mode
        self.motion_type = motion_type
        self.noise_types = noise_types or []
        self.atmospheric_preset = atmospheric_preset
        self.video_path = video_path
        self.ground_truth_path = ground_truth_path
        self.seed = seed

    # ------------------------------------------------------------------
    def start(self, run_name=None):
        """(Re)initializes the full pipeline fresh and begins a new run."""
        if self.mode == "sim":
            self.src = SimulatorFrameSource(
                motion_type=self.motion_type,
                noise_types=self.noise_types,
                atmospheric_preset=self.atmospheric_preset,
                fps=config.TARGET_PROCESSING_FPS_MIN,
                seed=self.seed,
            )
        else:
            if not self.video_path:
                raise ValueError("video_path is required for video mode")
            self.src = VideoFileFrameSource(
                video_path=self.video_path,
                ground_truth_path=self.ground_truth_path,
            )

        tracker_scale = getattr(self.src, "get_resolution_scale", lambda: 1.0)()

        if abs(tracker_scale - 1.0) < 0.01:
            self.detector = BlobDetector()
        else:
            self.detector = BlobDetector(
                min_area=int(50 * tracker_scale * tracker_scale),
                max_area=int(180 * tracker_scale * tracker_scale),
            )

        # Empirically-validated override for the specific 2x-resolution
        # case tested (see tracker.py's note on why this isn't a general
        # formula). Other non-640x480 resolutions would need their own
        # calibration pass — see dev_scripts/diagnostic_tracker_scale_sweep.py.
        if abs(tracker_scale - 2.0) < 0.05:
            self.tracker = KalmanTracker(process_noise=5000.0, measurement_noise=0.5, position_scale=tracker_scale)
        else:
            self.tracker = KalmanTracker(position_scale=tracker_scale)

        self.controller = TrackingController()

        run_name = run_name or f"{self.mode}_{self.motion_type if self.mode == 'sim' else 'video'}"
        self.logger = PerformanceLogger(run_name=run_name)
        self.logger.start()

        self.dt = 1.0 / self.src.get_fps()
        self.frame_idx = 0
        self.running = True

    def stop(self):
        """Ends the current run, finalizes the log, releases resources."""
        if self.logger:
            self.logger.stop()
        if self.src:
            self.src.release()
        self.running = False

    def export_log(self):
        """Manually trigger a log save (e.g. 'Export' button) without stopping."""
        if self.logger:
            return self.logger.export()
        return None, None

    def get_summary(self):
        if self.logger:
            return self.logger.compute_summary()
        return {}

    # ------------------------------------------------------------------
    def tick(self):
        """
        Advance the pipeline by exactly one frame. Called once per
        QTimer interval by the GUI. Returns a TickResult, or None if
        not currently running.
        """
        if not self.running or self.src is None:
            return None

        frame_start = time.time()
        result = TickResult()

        frame, gt, sim_t = self.src.get_frame()

        if frame is None:
            # End of video file (sim mode never naturally ends this way)
            result.end_of_stream = True
            self.running = False
            return result

        detections = self.detector.detect(frame)
        self.tracker.predict(self.dt)
        det = self.tracker.select_best_detection(detections)
        self.tracker.update(det)

        pan_cmd, tilt_cmd, mode_label = self.controller.compute(self.tracker, self.dt)
        if self.src.is_live():
            self.src.move_camera(pan_cmd, tilt_cmd)

        estimate = self.tracker.get_estimate()
        frame_proc_time = time.time() - frame_start

        self.logger.log_frame(sim_t, self.tracker.status, estimate, gt, frame_proc_time)

        error_px = None
        if estimate is not None and gt is not None and self.tracker.is_locked():
            error_px = ((estimate[0] - gt[0]) ** 2 + (estimate[1] - gt[1]) ** 2) ** 0.5

        self.frame_idx += 1

        result.frame = frame
        result.estimate = estimate
        result.ground_truth = gt
        result.status = self.tracker.status
        result.mode = mode_label
        result.sim_time = sim_t
        result.error_px = error_px
        result.fps_instant = (1.0 / frame_proc_time) if frame_proc_time > 0 else None
        result.frame_idx = self.frame_idx

        return result