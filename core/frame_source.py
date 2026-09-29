"""
core/frame_source.py
Abstraction layer so the detector/tracker pipeline doesn't care whether
frames come from the live simulator (with a controllable PTZ camera) or
from a pre-recorded .mp4 file (Benchmark-2: PTZ is bypassed, video is
fed directly into the coarse-pointing pipeline).

Both classes expose the same interface:
    get_frame() -> (frame, ground_truth_pos_or_None, timestamp)
    is_live()   -> bool  (True = simulator, can accept PTZ commands)
    release()
"""

import time
import cv2
import config
from core.target import MultiTargetManager
from core.scene import Scene
from core.camera import VirtualCamera
from core.disturbance import DisturbanceEngine
import random as _random_module


class FrameSource:
    """Abstract base — defines the contract both sources must follow."""

    def get_frame(self):
        raise NotImplementedError

    def is_live(self):
        raise NotImplementedError

    def release(self):
        pass

    def get_fps(self):
        raise NotImplementedError


# ======================================================================
class SimulatorFrameSource(FrameSource):
    """
    Live simulator mode. Wraps Scene + MultiTargetManager + VirtualCamera
    + DisturbanceEngine into one frame-producing source. Since the camera
    is controllable here, the controller (PID) can call `camera.move()`
    on this object between frames.
    """

    def __init__(
        self,
        motion_type=config.TARGET_MOTION_DEFAULT,
        num_targets=config.NUM_TARGETS_DEFAULT,
        noise_types=None,
        atmospheric_preset="clear",
        fps=config.TARGET_PROCESSING_FPS_MIN,
        seed=None,
    ):
        self.scene = Scene()
        target_rng = _random_module.Random(seed)
        self.targets = MultiTargetManager(num_targets=num_targets, motion_type=motion_type, rng=target_rng)
        self.camera = VirtualCamera()
        self.disturbance = DisturbanceEngine(
            noise_types=noise_types or [],
            atmospheric_preset=atmospheric_preset,
            seed=seed,
        )
        self.dt = 1.0 / fps
        self._fps = fps

    def get_frame(self):
        """
        Advances simulation by one tick, returns:
            frame            -> degraded camera view (what detector sees)
            ground_truth_pos -> target position IN CAMERA COORDS, or None if outside FOV
            timestamp        -> simulation time (s)
        """
        self.targets.update(self.dt)
        full_scene = self.scene.render(self.targets)
        clean_view = self.camera.capture(full_scene)
        degraded_view = self.disturbance.apply(clean_view)

        # Ground truth: first target's position mapped into camera coords
        # (extend to a list if you need multi-target ground truth)
        tx, ty = self.targets.targets[0].get_position()
        gt_cam_coords = self.camera.scene_to_camera_coords(tx, ty)

        timestamp = self.targets.targets[0].t
        return degraded_view, gt_cam_coords, timestamp

    def move_camera(self, pan_cmd_deg_s, tilt_cmd_deg_s):
        """Controller calls this to steer the camera (only valid in live mode)."""
        self.camera.move(pan_cmd_deg_s, tilt_cmd_deg_s, self.dt)

    def is_live(self):
        return True

    def get_fps(self):
        return self._fps

    def reset(self):
        self.camera.reset_to_center()


# ======================================================================
class VideoFileFrameSource(FrameSource):
    """
    Benchmark-2 mode. Reads frames directly from a pre-recorded .mp4 file.
    PTZ camera is bypassed entirely — the detector/tracker must work
    directly on these frames. No ground truth available unless a
    companion annotation file is provided by the organizers.

    Hardened for unknown real-world video specs (ISRO's actual
    Benchmark-2 files aren't available to test against in advance):
    resolution, frame rate, and channel count are all detected at
    open time rather than assumed, and reported clearly so a mismatch
    is visible immediately instead of silently degrading results.
    """

    EXPECTED_WIDTH = 640
    EXPECTED_HEIGHT = 480

    def __init__(self, video_path, ground_truth_path=None, verbose=True):
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise IOError(f"Could not open video file: {video_path}")

        self._fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.total_frames_reported = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.frame_idx = 0

        # Scale factor lets the detector's area-based filters adapt if
        # this video isn't the expected 640x480 — a target's pixel
        # footprint scales with resolution, so area thresholds calibrated
        # for 640x480 would otherwise misfire on a differently-sized feed.
        self.resolution_scale = (
            (self.width * self.height) / (self.EXPECTED_WIDTH * self.EXPECTED_HEIGHT)
        ) ** 0.5

        if verbose:
            self._report_video_info()

        self.ground_truth = None
        if ground_truth_path:
            self.ground_truth = self._load_ground_truth(ground_truth_path)

    def _report_video_info(self):
        print(f"[VideoFileFrameSource] Opened video: "
              f"{self.width}x{self.height} @ {self._fps:.1f}fps, "
              f"~{self.total_frames_reported} frames")
        if self.width != self.EXPECTED_WIDTH or self.height != self.EXPECTED_HEIGHT:
            print(f"[VideoFileFrameSource] NOTE: resolution differs from the "
                  f"expected {self.EXPECTED_WIDTH}x{self.EXPECTED_HEIGHT}. "
                  f"Detector area thresholds will be scaled by "
                  f"{self.resolution_scale:.3f}x to compensate.")
        if abs(self._fps - 30.0) > 1.0:
            print(f"[VideoFileFrameSource] NOTE: frame rate ({self._fps:.1f}fps) "
                  f"differs from the spec's 30fps — dt-dependent calculations "
                  f"(Kalman prediction, PID) will use the video's actual rate.")

    def _load_ground_truth(self, path):
        import pandas as pd
        df = pd.read_csv(path)
        return {int(row.frame): (row.x, row.y) for row in df.itertuples()}

    def get_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return None, None, None  # end of video

        # Handle color, grayscale, and any unexpected channel count safely
        if frame.ndim == 3:
            if frame.shape[2] == 4:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        elif frame.ndim == 2:
            frame_gray = frame
        else:
            raise ValueError(f"Unexpected frame shape from video file: {frame.shape}")

        gt = None
        if self.ground_truth is not None:
            gt = self.ground_truth.get(self.frame_idx, None)

        timestamp = self.frame_idx / self._fps
        self.frame_idx += 1

        return frame_gray, gt, timestamp

    def move_camera(self, pan_cmd_deg_s, tilt_cmd_deg_s):
        # No-op: PTZ is bypassed in video-file mode per spec
        pass

    def is_live(self):
        return False

    def get_fps(self):
        return self._fps

    def get_resolution_scale(self):
        """Used by main.py to adapt the detector if resolution differs from 640x480."""
        return self.resolution_scale

    def release(self):
        self.cap.release()