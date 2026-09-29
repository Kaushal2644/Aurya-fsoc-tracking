"""
gui/video_panel.py
Displays the live camera feed with detection/tracking overlay.
Converts numpy frames (from the pipeline) into a QPixmap for display,
drawing ground-truth and tracker-estimate markers directly on the image.
"""

import cv2
import numpy as np
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt


class VideoPanel(QWidget):
    """
    A self-contained widget: just call update_frame(...) each tick
    with the latest pipeline results, and it redraws itself.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.image_label = QLabel("Camera feed will appear here")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(640, 480)
        self.image_label.setStyleSheet(
            "background-color: #1a1a1a; color: #888; border: 1px solid #444;"
        )

        layout = QVBoxLayout()
        layout.addWidget(self.image_label)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    # ------------------------------------------------------------------
    def update_frame(self, frame, estimate=None, ground_truth=None, status="SEARCHING", mode="SEARCHING"):
        """
        Draws the overlay onto the given frame and displays it.

        frame: numpy array (grayscale or BGR), as returned by the pipeline
        estimate: (x, y) tracker estimate in camera-frame px, or None
        ground_truth: (x, y) true target position in camera-frame px, or None
        status: tracker status string ("SEARCHING" | "LOCKED" | "LOST")
        mode: controller mode string ("SEARCHING" | "CONFIRMING" | "TRACKING")
        """
        if frame is None:
            return

        vis = self._draw_overlay(frame, estimate, ground_truth, status, mode)
        pixmap = self._numpy_to_pixmap(vis)
        self.image_label.setPixmap(
            pixmap.scaled(
                self.image_label.width(),
                self.image_label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

    def clear(self):
        self.image_label.clear()
        self.image_label.setText("Camera feed will appear here")

    # ------------------------------------------------------------------
    def _draw_overlay(self, frame, estimate, ground_truth, status, mode):
        # Convert to BGR color so overlay markers (green/red) are visible
        # regardless of whether the source frame is grayscale
        if frame.ndim == 2:
            vis = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        else:
            vis = frame.copy()

        if ground_truth is not None:
            gx, gy = int(ground_truth[0]), int(ground_truth[1])
            cv2.circle(vis, (gx, gy), 12, (0, 255, 0), 2)  # green ring = ground truth

        if estimate is not None:
            ex, ey = int(estimate[0]), int(estimate[1])
            cv2.circle(vis, (ex, ey), 7, (0, 0, 255), 2)   # red ring = tracker estimate
            cv2.drawMarker(vis, (ex, ey), (0, 0, 255), cv2.MARKER_CROSS, 10, 1)

        # Status banner: color-coded by state for at-a-glance readability
        status_colors = {
            "LOCKED": (0, 200, 0),
            "SEARCHING": (0, 165, 255),
            "LOST": (0, 0, 255),
        }
        color = status_colors.get(status, (200, 200, 200))
        cv2.putText(
            vis, f"{status}  |  {mode}", (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA,
        )

        return vis

    def _numpy_to_pixmap(self, frame_bgr):
        h, w = frame_bgr.shape[:2]
        # QImage expects RGB order, OpenCV gives BGR
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgb = np.ascontiguousarray(rgb)
        qimage = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
        return QPixmap.fromImage(qimage)