"""
core/controller.py
Closed-loop pointing controller.

Two modes:
  1. TRACKING  — PID loop centers the camera on the tracked target
  2. SEARCHING — no lock yet (or lost); executes a raster/spiral scan
                 pattern to re-acquire the target within the FOV

Outputs pan/tilt angular velocity commands (deg/s), consumed by
VirtualCamera.move() (via SimulatorFrameSource.move_camera()).
Note: in VideoFileFrameSource mode, these commands are simply no-ops
(PTZ is bypassed per Benchmark-2), but the controller still runs so
its internal state/logging stays consistent across both modes.
"""

import numpy as np
import config


class PIDController:
    """Simple PID for a single axis (used twice: pan axis, tilt axis)."""

    def __init__(self, kp=config.PID_KP, ki=config.PID_KI, kd=config.PID_KD,
                 output_limit=None):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_limit = output_limit

        self._integral = 0.0
        self._prev_error = 0.0
        self._initialized = False

    def reset(self):
        self._integral = 0.0
        self._prev_error = 0.0
        self._initialized = False

    def update(self, error, dt):
        self._integral += error * dt
        # Anti-windup: clamp integral term
        self._integral = np.clip(self._integral, -1000, 1000)

        derivative = 0.0
        if self._initialized and dt > 0:
            derivative = (error - self._prev_error) / dt

        output = self.kp * error + self.ki * self._integral + self.kd * derivative

        if self.output_limit is not None:
            output = np.clip(output, -self.output_limit, self.output_limit)

        self._prev_error = error
        self._initialized = True
        return output


class AcquisitionScanner:
    """
    Generates a raster scan pattern for the SEARCHING state, sweeping
    the camera across the scene to re-locate the target when lost.
    """

    def __init__(self, scan_speed_deg_s=4.0, pattern="raster"):
        self.scan_speed = scan_speed_deg_s
        self.pattern = pattern
        self.t = 0.0
        self.direction = 1

    def reset(self):
        self.t = 0.0
        self.direction = 1

    def get_scan_command(self, dt):
        """
        Returns (pan_cmd_deg_s, tilt_cmd_deg_s) for this tick.
        Raster: sweep pan back and forth, step tilt periodically.
        """
        self.t += dt

        if self.pattern == "raster":
            pan_cmd = self.scan_speed * self.direction
            # Flip direction periodically to create a sweeping motion
            if int(self.t) % 4 == 0 and self.t % 1.0 < dt:
                self.direction *= -1
            tilt_cmd = 0.3 * np.sin(self.t * 0.5)  # slow drift in tilt
            return pan_cmd, tilt_cmd

        elif self.pattern == "spiral":
            radius_growth = 0.5
            pan_cmd = self.scan_speed * np.cos(self.t * 2.0) * (1 + radius_growth * self.t)
            tilt_cmd = self.scan_speed * np.sin(self.t * 2.0) * (1 + radius_growth * self.t)
            return pan_cmd, tilt_cmd

        return 0.0, 0.0


class TrackingController:
    """
    Top-level controller combining PID (tracking mode) and
    AcquisitionScanner (searching mode) based on tracker lock status.
    """

    def __init__(
        self,
        frame_width=config.CAMERA_WIDTH,
        frame_height=config.CAMERA_HEIGHT,
        max_pan_speed=config.MAX_PAN_SPEED_DEG_S,
        max_tilt_speed=config.MAX_TILT_SPEED_DEG_S,
    ):
        self.frame_center_x = frame_width / 2
        self.frame_center_y = frame_height / 2

        self.pan_pid = PIDController(output_limit=max_pan_speed)
        self.tilt_pid = PIDController(output_limit=max_tilt_speed)
        self.scanner = AcquisitionScanner(scan_speed_deg_s=max_pan_speed * 0.8)

        self.mode = "SEARCHING"   # SEARCHING | TRACKING

    def reset(self):
        self.pan_pid.reset()
        self.tilt_pid.reset()
        self.scanner.reset()
        self.mode = "SEARCHING"

    # ------------------------------------------------------------------
    def compute(self, tracker, dt):
        """
        tracker: a KalmanTracker instance (already predict()+update() called this frame)
        Returns (pan_cmd_deg_s, tilt_cmd_deg_s, mode)
        """
        if tracker.is_locked():
            self.mode = "TRACKING"
            estimate = tracker.get_estimate()
            ex = estimate[0] - self.frame_center_x
            ey = estimate[1] - self.frame_center_y

            pan_cmd = self.pan_pid.update(ex, dt)
            tilt_cmd = self.tilt_pid.update(ey, dt)

            return pan_cmd, tilt_cmd, self.mode

        elif tracker.is_confirming():
            # A plausible candidate is being confirmed (tracker.py requires
            # a few consistent detections in a row before committing to a
            # lock). Hold the camera still so the confirmation isn't
            # disrupted by the scanner sweeping the target out from under it.
            self.mode = "CONFIRMING"
            self.pan_pid.reset()
            self.tilt_pid.reset()
            return 0.0, 0.0, self.mode

        else:
            self.mode = "SEARCHING"
            self.pan_pid.reset()
            self.tilt_pid.reset()
            pan_cmd, tilt_cmd = self.scanner.get_scan_command(dt)
            return pan_cmd, tilt_cmd, self.mode