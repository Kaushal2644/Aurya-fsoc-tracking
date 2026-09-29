"""
core/camera.py
Virtual pan-tilt camera. Crops a small FOV window out of the large
scene canvas, and moves that window based on pan/tilt commands,
respecting max slew-rate constraints (per ISRO spec: 5-10 deg/s).

We work in pixel-space for simplicity, with a configurable
deg-to-pixel conversion derived from the camera FOV spec.
"""

import numpy as np
import config


class VirtualCamera:
    """
    Represents the mobile terminal's camera. Views a cropped window
    of the larger scene. Pan/tilt commands move this window's center,
    limited by max angular slew speed.
    """

    def __init__(
        self,
        scene_width=config.SCENE_WIDTH,
        scene_height=config.SCENE_HEIGHT,
        cam_width=config.CAMERA_WIDTH,
        cam_height=config.CAMERA_HEIGHT,
        fov_deg=config.CAMERA_FOV_DEG,
        max_pan_speed=config.MAX_PAN_SPEED_DEG_S,
        max_tilt_speed=config.MAX_TILT_SPEED_DEG_S,
    ):
        self.scene_w = scene_width
        self.scene_h = scene_height
        self.cam_w = cam_width
        self.cam_h = cam_height
        self.fov_h_deg, self.fov_v_deg = fov_deg

        self.max_pan_speed = max_pan_speed     # deg/s
        self.max_tilt_speed = max_tilt_speed   # deg/s

        # Degrees-per-pixel conversion (scene-space), derived so that
        # the camera's FOV window in pixels corresponds to its angular FOV.
        # We assume the "lens" maps cam_width pixels -> fov_h_deg degrees.
        self.deg_per_px_h = self.fov_h_deg / self.cam_w
        self.deg_per_px_v = self.fov_v_deg / self.cam_h

        # Camera center starts at the center of the scene (per spec)
        self.center_x = self.scene_w / 2
        self.center_y = self.scene_h / 2

        # Pan/tilt angular position (relative, degrees) — optional bookkeeping
        self.pan_angle = 0.0
        self.tilt_angle = 0.0

    # ------------------------------------------------------------------
    def move(self, pan_cmd_deg_s, tilt_cmd_deg_s, dt):
        """
        Move the camera center based on commanded angular velocities,
        clipped to max slew speed. Called every control-loop tick.

        pan_cmd_deg_s / tilt_cmd_deg_s: desired angular velocity (deg/s),
        typically output by the PID controller.
        """
        # Clip commands to max slew rate
        pan_cmd = np.clip(pan_cmd_deg_s, -self.max_pan_speed, self.max_pan_speed)
        tilt_cmd = np.clip(tilt_cmd_deg_s, -self.max_tilt_speed, self.max_tilt_speed)

        # Integrate angle
        self.pan_angle += pan_cmd * dt
        self.tilt_angle += tilt_cmd * dt

        # Convert angular movement to pixel movement in scene-space
        dx_px = (pan_cmd * dt) / self.deg_per_px_h
        dy_px = (tilt_cmd * dt) / self.deg_per_px_v

        self.center_x += dx_px
        self.center_y += dy_px

        self._clamp_to_scene()

    def _clamp_to_scene(self):
        half_w = self.cam_w / 2
        half_h = self.cam_h / 2
        self.center_x = np.clip(self.center_x, half_w, self.scene_w - half_w)
        self.center_y = np.clip(self.center_y, half_h, self.scene_h - half_h)

    # ------------------------------------------------------------------
    def get_fov_bbox(self):
        """Returns (x1, y1, x2, y2) of the current camera window in scene coords."""
        half_w = self.cam_w / 2
        half_h = self.cam_h / 2
        x1 = int(self.center_x - half_w)
        y1 = int(self.center_y - half_h)
        x2 = x1 + self.cam_w
        y2 = y1 + self.cam_h
        return x1, y1, x2, y2

    def capture(self, scene_frame):
        """
        Crop the current FOV window out of the full scene frame.
        Returns the camera-view image (cam_width x cam_height).
        """
        x1, y1, x2, y2 = self.get_fov_bbox()
        view = scene_frame[y1:y2, x1:x2]

        # Safety: pad if crop is smaller than expected (edge case at boundaries)
        if view.shape[0] != self.cam_h or view.shape[1] != self.cam_w:
            view = self._pad_to_size(view)

        return view

    def _pad_to_size(self, view):
        import cv2
        h, w = view.shape[:2]
        pad_h = self.cam_h - h
        pad_w = self.cam_w - w
        if view.ndim == 3:
            return cv2.copyMakeBorder(view, 0, max(0, pad_h), 0, max(0, pad_w),
                                       cv2.BORDER_CONSTANT, value=(0, 0, 0))
        else:
            return cv2.copyMakeBorder(view, 0, max(0, pad_h), 0, max(0, pad_w),
                                       cv2.BORDER_CONSTANT, value=0)

    # ------------------------------------------------------------------
    def scene_to_camera_coords(self, scene_x, scene_y):
        """
        Convert a ground-truth scene-space point into camera-frame pixel
        coordinates (for computing tracking error against detections).
        Returns None if point is outside current FOV.
        """
        x1, y1, x2, y2 = self.get_fov_bbox()
        if x1 <= scene_x <= x2 and y1 <= scene_y <= y2:
            return scene_x - x1, scene_y - y1
        return None  # target not visible in current FOV

    def reset_to_center(self):
        self.center_x = self.scene_w / 2
        self.center_y = self.scene_h / 2
        self.pan_angle = 0.0
        self.tilt_angle = 0.0