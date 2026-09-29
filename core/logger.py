# core/logger.py
"""
Auto-generates the mandatory Performance Log deliverable.

Tracks, per run:
    - Simulation duration
    - FPS (processing speed)
    - Acquisition time
    - Average / max tracking error
    - Lock retention rate
    - Re-acquisition times
    - Target loss rate
    - Per-frame processing time

Exports:
    - CSV per-frame log
    - JSON summary report
"""

import time
import json
import csv
import os

import numpy as np
import config


class PerformanceLogger:
    def __init__(self, run_name="run", log_dir="logs"):
        self.run_name = run_name
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

        self.frame_records = []

        self.start_time = None
        self.end_time = None
        self.run_start_wallclock = None

        self.first_lock_time = None       # sim-clock time of first lock (the metric ISRO actually means)
        self.first_lock_wallclock = None  # real CPU time (kept for reference/debugging only)
        self._run_start_sim_time = None

        self._was_locked_prev = False
        self._lost_since_wallclock = None
        self.reacquisition_times = []

        self._locked_frame_count = 0
        self._lost_frame_count = 0
        self._total_frame_count = 0

        self._errors_px = []

    def start(self):
        self.start_time = time.time()
        self.run_start_wallclock = self.start_time

    def stop(self):
        self.end_time = time.time()

    @staticmethod
    def _normalize_point(point):
        """
        Converts a point-like value into an (x, y) tuple.

        Supports:
            - tuple/list: (x, y)
            - NumPy array: [x, y]
            - None

        Returns None for invalid points.
        """
        if point is None:
            return None

        try:
            if len(point) < 2:
                return None

            x = float(point[0])
            y = float(point[1])

            if not (np.isfinite(x) and np.isfinite(y)):
                return None

            return x, y

        except (TypeError, ValueError, IndexError):
            return None

    def log_frame(
        self,
        sim_time,
        tracker_status,
        estimate,
        ground_truth,
        frame_processing_time_s,
    ):
        """
        Logs one processed frame.

        estimate:
            Tracker estimate in camera-frame pixels.

        ground_truth:
            True target position in camera-frame pixels.
        """

        now = time.time()
        self._total_frame_count += 1

        if self._run_start_sim_time is None:
            self._run_start_sim_time = sim_time

        is_locked = tracker_status == "LOCKED"
        is_lost = tracker_status == "LOST"

        if is_locked:
            self._locked_frame_count += 1
            self._has_ever_locked = True

        # Only count LOST frames toward the loss-rate metric after the
        # system has achieved its first lock — being unable to find a
        # target that hasn't appeared in the camera's FOV yet is not a
        # "target loss" event, it's pre-acquisition search time.
        if is_lost and getattr(self, "_has_ever_locked", False):
            self._lost_frame_count += 1
            self._post_lock_frame_count = getattr(self, "_post_lock_frame_count", 0) + 1
        if is_locked:
            self._post_lock_frame_count = getattr(self, "_post_lock_frame_count", 0) + 1

        # First acquisition
        if is_locked and self.first_lock_wallclock is None:
            self.first_lock_wallclock = now
            self.first_lock_time = sim_time

        # Re-acquisition tracking, measured on the sim-clock (same
        # reasoning as acquisition_time above)
        if self._was_locked_prev and is_lost:
            self._lost_since_sim_time = sim_time

        if (
            not self._was_locked_prev
            and is_locked
            and getattr(self, "_lost_since_sim_time", None) is not None
        ):
            reacq_duration = sim_time - self._lost_since_sim_time
            self.reacquisition_times.append(reacq_duration)
            self._lost_since_sim_time = None

        self._was_locked_prev = is_locked

        # Normalize coordinates before calculating error
        estimate_xy = self._normalize_point(estimate)
        ground_truth_xy = self._normalize_point(ground_truth)

        error_px = None

        if is_locked and estimate_xy is not None and ground_truth_xy is not None:
            dx = estimate_xy[0] - ground_truth_xy[0]
            dy = estimate_xy[1] - ground_truth_xy[1]

            error_px = float(np.hypot(dx, dy))
            self._errors_px.append(error_px)

        self.frame_records.append(
            {
                "frame_idx": self._total_frame_count,
                "sim_time": round(float(sim_time), 5),
                "status": tracker_status,
                "est_x": (
                    None if estimate_xy is None else round(estimate_xy[0], 2)
                ),
                "est_y": (
                    None if estimate_xy is None else round(estimate_xy[1], 2)
                ),
                "gt_x": (
                    None
                    if ground_truth_xy is None
                    else round(ground_truth_xy[0], 2)
                ),
                "gt_y": (
                    None
                    if ground_truth_xy is None
                    else round(ground_truth_xy[1], 2)
                ),
                "error_px": (
                    None if error_px is None else round(error_px, 3)
                ),
                "processing_time_s": round(
                    float(frame_processing_time_s), 5
                ),
            }
        )

    def compute_summary(self):
        duration = (
            (self.end_time or time.time())
            - (self.start_time or time.time())
        )

        # Acquisition time is measured on the SIMULATED camera-feed clock
        # (frames x dt), not real CPU wall-clock time. Wall-clock time
        # depends on processing speed (a faster machine processes more
        # simulated frames per real second), which would make this metric
        # meaningless/inconsistent across hardware. The spec's "2 second"
        # threshold refers to seconds of camera footage, matching how a
        # real PAT system's acquisition time would be measured.
        acquisition_time = None

        if self.first_lock_time is not None and self._run_start_sim_time is not None:
            acquisition_time = self.first_lock_time - self._run_start_sim_time

        proc_times = [
            record["processing_time_s"]
            for record in self.frame_records
            if record["processing_time_s"] is not None
        ]

        avg_proc_time = (
            float(np.mean(proc_times)) if proc_times else None
        )

        fps = 1.0 / avg_proc_time if avg_proc_time else None

        lock_retention_rate = (
            self._locked_frame_count / self._total_frame_count
            if self._total_frame_count
            else 0.0
        )

        post_lock_frames = getattr(self, "_post_lock_frame_count", 0)
        target_loss_rate = (
            self._lost_frame_count / post_lock_frames
            if post_lock_frames
            else 0.0
        )

        avg_error = (
            float(np.mean(self._errors_px))
            if self._errors_px
            else None
        )

        max_error = (
            float(np.max(self._errors_px))
            if self._errors_px
            else None
        )

        rmse = (
            float(np.sqrt(np.mean(np.square(self._errors_px))))
            if self._errors_px
            else None
        )

        avg_reacq_time = (
            float(np.mean(self.reacquisition_times))
            if self.reacquisition_times
            else None
        )

        max_reacq_time = (
            float(np.max(self.reacquisition_times))
            if self.reacquisition_times
            else None
        )

        return {
            "run_name": self.run_name,
            "simulation_duration_s": round(duration, 3),
            "total_frames": self._total_frame_count,
            "fps": round(fps, 2) if fps is not None else None,
            "avg_processing_time_ms": (
                round(avg_proc_time * 1000, 3)
                if avg_proc_time is not None
                else None
            ),
            "acquisition_time_s": (
                round(acquisition_time, 3)
                if acquisition_time is not None
                else None
            ),
            "acquisition_spec_met": (
                acquisition_time is not None
                and acquisition_time <= config.TARGET_ACQUISITION_TIME_S
            ),
            "avg_tracking_error_px": (
                round(avg_error, 3)
                if avg_error is not None
                else None
            ),
            "max_tracking_error_px": (
                round(max_error, 3)
                if max_error is not None
                else None
            ),
            "rmse_px": (
                round(rmse, 3)
                if rmse is not None
                else None
            ),
            "tracking_error_spec_met": (
                avg_error is not None
                and avg_error <= config.TARGET_TRACKING_ERROR_PX
            ),
            "lock_retention_rate": round(lock_retention_rate, 4),
            "target_loss_rate": round(target_loss_rate, 4),
            "target_loss_spec_met": (
                target_loss_rate <= config.TARGET_LOSS_RATE_MAX
            ),
            "num_reacquisition_events": len(self.reacquisition_times),
            "avg_reacquisition_time_s": (
                round(avg_reacq_time, 3)
                if avg_reacq_time is not None
                else None
            ),
            "max_reacquisition_time_s": (
                round(max_reacq_time, 3)
                if max_reacq_time is not None
                else None
            ),
            "reacquisition_spec_met": (
                max_reacq_time is None
                or max_reacq_time <= config.TARGET_REACQUISITION_TIME_S
            ),
            "processing_speed_spec_met": (
                fps is not None
                and fps >= config.TARGET_PROCESSING_FPS_MIN
            ),
        }

    def export(self):
        """Write the per-frame CSV and summary JSON report."""

        timestamp_str = time.strftime("%Y%m%d_%H%M%S")

        csv_path = os.path.join(
            self.log_dir,
            f"{self.run_name}_{timestamp_str}_frames.csv",
        )

        json_path = os.path.join(
            self.log_dir,
            f"{self.run_name}_{timestamp_str}_summary.json",
        )

        if self.frame_records:
            keys = self.frame_records[0].keys()

            with open(csv_path, "w", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=keys)
                writer.writeheader()
                writer.writerows(self.frame_records)

        summary = self.compute_summary()

        with open(json_path, "w") as file:
            json.dump(summary, file, indent=2)

        print(f"[Logger] Per-frame log saved: {csv_path}")
        print(f"[Logger] Summary report saved: {json_path}")

        return csv_path, json_path

    def print_summary(self):
        summary = self.compute_summary()

        print("\n===== PERFORMANCE SUMMARY =====")

        for key, value in summary.items():
            print(f"{key:35s}: {value}")

        print("================================\n")