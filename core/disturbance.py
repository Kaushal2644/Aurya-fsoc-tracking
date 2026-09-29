"""
core/disturbance.py
Applies noise, jitter, and atmospheric disturbances to the camera view.
Per ISRO spec:
  - Image noise: Salt & Pepper (~10%), Gaussian, Poisson (user-selectable, combinable)
  - Max camera jitter: ±20 px/frame
  - Max platform motion: ±20 px/frame
  - Atmospheric presets: Clear, Haze, Fog, Rain, Low-light
    (implemented as contrast/brightness reduction, kept simple by design)
"""

import numpy as np
import cv2
import config


class DisturbanceEngine:
    """
    Applies a configurable pipeline of disturbances to a camera frame.
    Call apply() once per frame after camera.capture().
    """

    def __init__(
        self,
        noise_types=None,
        salt_pepper_amount=config.SALT_PEPPER_AMOUNT,
        gaussian_std=10.0,
        camera_jitter_max_px=config.CAMERA_JITTER_MAX_PX,
        platform_motion_max_px=config.PLATFORM_MOTION_MAX_PX,
        atmospheric_preset="clear",
        enable_jitter=False,
        enable_platform_motion=False,
        seed=None,
    ):
        self.noise_types = noise_types or []
        self.salt_pepper_amount = salt_pepper_amount
        self.gaussian_std = gaussian_std
        self.camera_jitter_max_px = camera_jitter_max_px
        self.platform_motion_max_px = platform_motion_max_px
        self.atmospheric_preset = atmospheric_preset
        self.enable_jitter = enable_jitter
        self.enable_platform_motion = enable_platform_motion
        self.rng = np.random.default_rng(seed)

        self._platform_offset = np.array([0.0, 0.0])

    # ------------------------------------------------------------------
    def apply(self, frame):
        """
        Full disturbance pipeline. Returns the degraded frame.
        Order: platform motion shift -> jitter -> atmospheric -> noise
        """
        if self.enable_platform_motion:
            frame = self._apply_platform_motion(frame)
        if self.enable_jitter:
            frame = self._apply_camera_jitter(frame)
        frame = self._apply_atmospheric(frame)
        frame = self._apply_noise(frame)
        return frame

    # ------------------------------------------------------------------
    def _apply_camera_jitter(self, frame):
        """
        Random per-frame pixel shift simulating platform/camera vibration.
        ±20 px max per frame (spec).
        """
        dx = int(self.rng.integers(-self.camera_jitter_max_px, self.camera_jitter_max_px + 1))
        dy = int(self.rng.integers(-self.camera_jitter_max_px, self.camera_jitter_max_px + 1))

        M = np.float32([[1, 0, dx], [0, 1, dy]])
        h, w = frame.shape[:2]
        jittered = cv2.warpAffine(frame, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
        return jittered

    def _apply_platform_motion(self, frame, mode="linear"):
        """
        Slower, persistent drift (mount instability), distinct from jitter.
        Default: linear drift. Magnitude capped at platform_motion_max_px/frame.
        """
        step = self.rng.uniform(-self.platform_motion_max_px, self.platform_motion_max_px, size=2)
        # Smooth it slightly so it drifts rather than jumps every frame
        self._platform_offset = 0.9 * self._platform_offset + 0.1 * step

        dx, dy = self._platform_offset
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        h, w = frame.shape[:2]
        shifted = cv2.warpAffine(frame, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
        return shifted

    # ------------------------------------------------------------------
    def _apply_atmospheric(self, frame):
        """
        Simple contrast/brightness transforms per preset.
        Kept intentionally simple per spec ('reduction in contrast and brightness'),
        not full physical turbulence modeling.
        """
        preset = self.atmospheric_preset

        if preset == "clear":
            return frame

        elif preset == "haze":
            # slight brightness lift, contrast reduction
            return cv2.convertScaleAbs(frame, alpha=0.85, beta=25)

        elif preset == "fog":
            # stronger whitening, heavy contrast loss
            fog_layer = np.full_like(frame, 180)
            return cv2.addWeighted(frame, 0.5, fog_layer, 0.5, 0)

        elif preset == "rain":
            # darker, add streak-like noise texture
            darker = cv2.convertScaleAbs(frame, alpha=0.8, beta=-10)
            streaks = self._generate_rain_streaks(darker.shape)
            return cv2.addWeighted(darker, 0.9, streaks, 0.1, 0)

        elif preset == "low_light":
            # significant brightness reduction
            return cv2.convertScaleAbs(frame, alpha=0.4, beta=-20)

        else:
            return frame

    def _generate_rain_streaks(self, shape, num_streaks=200):
        streak_layer = np.zeros(shape, dtype=np.uint8)
        h, w = shape[:2]
        for _ in range(num_streaks):
            x = self.rng.integers(0, w)
            y = self.rng.integers(0, h)
            length = self.rng.integers(5, 15)
            color = 200
            cv2.line(streak_layer, (x, y), (x, y + length), color, 1)
        return streak_layer

    # ------------------------------------------------------------------
    def _apply_noise(self, frame):
        """Apply all selected noise types in sequence."""
        out = frame.copy()
        if "salt_pepper" in self.noise_types:
            out = self._salt_pepper_noise(out)
        if "gaussian" in self.noise_types:
            out = self._gaussian_noise(out)
        if "poisson" in self.noise_types:
            out = self._poisson_noise(out)
        return out

    def _salt_pepper_noise(self, frame):
        out = frame.copy()
        prob = self.salt_pepper_amount
        mask = self.rng.random(frame.shape[:2])

        salt_mask = mask < (prob / 2)
        pepper_mask = mask > (1 - prob / 2)

        if out.ndim == 3:
            out[salt_mask] = 255
            out[pepper_mask] = 0
        else:
            out[salt_mask] = 255
            out[pepper_mask] = 0
        return out

    def _gaussian_noise(self, frame):
        noise = self.rng.normal(0, self.gaussian_std, frame.shape)
        noisy = frame.astype(np.float32) + noise
        return np.clip(noisy, 0, 255).astype(np.uint8)

    def _poisson_noise(self, frame):
        # Poisson noise scales with signal intensity (shot noise)
        vals = len(np.unique(frame))
        vals = 2 ** np.ceil(np.log2(vals))
        noisy = self.rng.poisson(frame.astype(np.float32) * vals) / float(vals)
        return np.clip(noisy, 0, 255).astype(np.uint8)