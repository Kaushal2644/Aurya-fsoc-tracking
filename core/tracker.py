"""
core/tracker.py
Kalman-filter-based tracker sitting on top of the raw detector output.

Model: constant-velocity in 2D image-plane coordinates.
State vector: [x, y, vx, vy]

Responsibilities:
  - Smooth noisy detections
  - Predict position when detector misses a frame (noise/occlusion)
  - Track "lock" status: LOCKED / SEARCHING / LOST
  - Support re-acquisition after a bounded number of missed frames
"""

import numpy as np
import time


class KalmanTracker:
    """
    Simple constant-velocity Kalman filter for 2D point tracking,
    implemented directly with NumPy (no external dependency required,
    though `filterpy` could replace this if preferred).
    """

    def __init__(
        self,
        process_noise=25.0,         # calibrated for 640x480-scale pixel motion
        measurement_noise=0.5,      # calibrated for 640x480-scale pixel motion
        max_missed_frames=15,       # ~0.5-1 sec at 20-30fps before declaring LOST
        position_scale=1.0,         # kept for API compatibility; no longer auto-derives noise
    ):
        self.max_missed_frames = max_missed_frames
        self.position_scale = position_scale

        # NOTE on resolution scaling: an earlier attempt scaled
        # process_noise/measurement_noise by position_scale^2 (a
        # quadratic pixel-displacement argument), but empirical testing
        # against a real 2x-resolution video showed that assumption was
        # wrong — quadratic scaling barely improved tracking error
        # (47.5px -> 48.5px), while process_noise=5000 (a ~200x increase,
        # not 4x) actually worked, dropping error to ~4px avg / 9.6px max.
        # No clean formula reliably predicts the right constant from one
        # data point, so this is intentionally NOT auto-scaled. If you
        # run against a video at a resolution other than 640x480, pass
        # process_noise/measurement_noise explicitly, re-tuned for that
        # resolution using the same empirical sweep method documented in
        # dev_scripts/diagnostic_tracker_scale_sweep.py.

        # State: [x, y, vx, vy]
        self.x = np.zeros((4, 1))
        self.P = np.eye(4) * 500.0   # initial uncertainty (large = not yet initialized)

        # State transition matrix (updated with dt each step, dt filled at runtime)
        self.F = np.eye(4)

        # Measurement matrix: we observe x, y only
        self.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
        ])

        self.Q_scale = process_noise
        self.R = np.eye(2) * measurement_noise

        # Tracking state machine
        self.status = "SEARCHING"    # SEARCHING | LOCKED | LOST
        self.missed_frames = 0
        self.initialized = False

        # Lock confirmation: requires N consecutive, spatially-consistent
        # detections before committing to a lock. Prevents a single noise
        # blob (common under heavy fog/salt-pepper) from being mistaken
        # for the real target.
        self.confirm_required = 3
        self.confirm_radius = 25.0          # widened: tolerates noise-driven centroid jitter
        self.confirm_max_gap = 3            # NEW: allow brief detection dropouts during confirmation
        self._pending_candidate = None
        self._pending_count = 0
        self._pending_gap = 0
        self._unconfirmed_frames = 0
        self.max_unconfirmed_frames = 10     # NEW: hard cap — give up and resume scanning if stuck this long                # NEW: counts consecutive misses during confirmation

        # Timing bookkeeping for acquisition/re-acquisition metrics
        self.lock_start_time = None
        self.lost_since_time = None

    # ------------------------------------------------------------------
    def _build_F(self, dt):
        F = np.eye(4)
        F[0, 2] = dt
        F[1, 3] = dt
        return F

    def _build_Q(self, dt):
        """Process noise covariance, scaled by dt (discretized white-noise-acceleration model)."""
        q = self.Q_scale
        Q = np.array([
            [dt**4/4, 0, dt**3/2, 0],
            [0, dt**4/4, 0, dt**3/2],
            [dt**3/2, 0, dt**2, 0],
            [0, dt**3/2, 0, dt**2],
        ]) * q
        return Q

    # ------------------------------------------------------------------
    def init(self, x, y):
        """Called on first successful detection to seed the filter."""
        self.x = np.array([[x], [y], [0.0], [0.0]])
        self.P = np.eye(4) * 50.0
        self.initialized = True
        self.status = "LOCKED"
        self.missed_frames = 0
        self.lock_start_time = time.time()
        self.lost_since_time = None

    def predict(self, dt):
        """Prediction step — call every frame regardless of detection."""
        if not self.initialized:
            return None

        F = self._build_F(dt)
        Q = self._build_Q(dt)

        self.x = F @ self.x
        self.P = F @ self.P @ F.T + Q

        return self.x[0, 0], self.x[1, 0]

    def update(self, detection):
        """
        Correction step. Call with a Detection object (from detector.py)
        or None if no detection this frame.
        """
        if detection is None:
            self._handle_missed_frame()
            if self.status != "LOCKED":
                # Tolerate brief gaps in an otherwise-good confirmation
                # sequence (expected under heavy noise) instead of
                # discarding all progress on a single missed frame.
                self._pending_gap += 1
                if self._pending_gap > self.confirm_max_gap:
                    self._pending_candidate = None
                    self._pending_count = 0
                    self._pending_gap = 0
                    self._unconfirmed_frames = 0
            return self.get_estimate()

        # --- Not yet locked: require confirmation before committing ---
                # --- Not yet locked: require confirmation before committing ---
        if self.status != "LOCKED":
            self._unconfirmed_frames += 1
            if self._unconfirmed_frames > self.max_unconfirmed_frames:
                # Stuck too long without confirming — likely noise churn.
                # Give up this attempt so the scanner can resume searching
                # instead of freezing the camera forever.
                self._pending_candidate = None
                self._pending_count = 0
                self._pending_gap = 0
                self._unconfirmed_frames = 0
                return self.get_estimate()

            if self._pending_candidate is not None:
                dist = np.hypot(
                    detection.x - self._pending_candidate[0],
                    detection.y - self._pending_candidate[1],
                )
            else:
                dist = None

            if dist is None or dist > self.confirm_radius:
                self._pending_candidate = (detection.x, detection.y)
                self._pending_count = 1
            else:
                self._pending_count += 1
                self._pending_candidate = (detection.x, detection.y)

            self._pending_gap = 0  # reset gap counter on any successful detection

            if self._pending_count >= self.confirm_required:
                self.init(detection.x, detection.y)
                self._pending_candidate = None
                self._pending_count = 0
                self._pending_gap = 0
                self._unconfirmed_frames = 0

            return self.get_estimate()

        # --- Already locked: standard Kalman correction ---
        z = np.array([[detection.x], [detection.y]])

        y_residual = z - (self.H @ self.x)
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)

        self.x = self.x + K @ y_residual
        self.P = (np.eye(4) - K @ self.H) @ self.P

        self.missed_frames = 0
        self.lost_since_time = None

        return self.get_estimate()

    def select_best_detection(self, detections, gating_radius=90.0):
        """
        Chooses the most trustworthy detection among candidates.

        If not yet locked: trust the detector's own confidence ranking
        (list is pre-sorted, highest confidence first).

        If locked: only accept a detection if it's spatially close to
        where the Kalman filter predicts the target should be. This
        rejects noise blobs that happen to look bright/round but are
        physically implausible given recent motion — instead of
        jumping to them, the tracker coasts on its prediction.
        """
        if not detections:
            return None

        if self.status != "LOCKED":
            return detections[0]

        predicted = self.get_estimate()
        if predicted is None:
            return detections[0]

        px, py = predicted
        gated = [
            d for d in detections
            if ((d.x - px) ** 2 + (d.y - py) ** 2) ** 0.5 <= gating_radius
        ]

        if gated:
            return min(gated, key=lambda d: (d.x - px) ** 2 + (d.y - py) ** 2)

        return None  # nothing trustworthy this frame — let the filter coast

    def _handle_missed_frame(self):
        self.missed_frames += 1

        if self.missed_frames > self.max_missed_frames:
            if self.status != "LOST":
                self.status = "LOST"
                self.lost_since_time = time.time()
        elif self.initialized:
            # Still within tolerance: coast on prediction, remain "LOCKED"
            # (this is what lets you survive brief noise dropout/occlusion)
            self.status = "LOCKED"

    # ------------------------------------------------------------------
    def get_estimate(self):
        """Returns current best (x, y) estimate, or None if never initialized."""
        if not self.initialized:
            return None
        return self.x[0, 0], self.x[1, 0]

    def get_velocity(self):
        if not self.initialized:
            return None
        return self.x[2, 0], self.x[3, 0]

    def is_locked(self):
        return self.status == "LOCKED"

    def is_confirming(self):
        """True as soon as any candidate is being tracked toward
        confirmation. Freezing on the very first detection (not the
        second) is necessary because the acquisition scanner moves the
        target enough between frames that two detections would never
        land within confirm_radius of each other otherwise."""
        return self.status != "LOCKED" and self._pending_count >= 1

    def is_lost(self):
        return self.status == "LOST"

    def reset(self):
        """Full reset — call when re-initiating acquisition from scratch."""
        self.__init__(
            process_noise=self.Q_scale,
            measurement_noise=self.R[0, 0],
            max_missed_frames=self.max_missed_frames,
        )