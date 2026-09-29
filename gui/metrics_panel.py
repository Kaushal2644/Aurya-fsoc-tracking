"""
gui/metrics_panel.py
Live performance display: tracking-error plot over time, FPS counter,
lock-status indicator, and running summary stats.

Uses pyqtgraph for the live plot (much faster than matplotlib for
real-time updates at 20-30+ fps).
"""

from collections import deque

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QGridLayout,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
import pyqtgraph as pg


class MetricsPanel(QWidget):
    """
    Call update(...) once per tick with the latest TickResult-derived
    values; call reset() when a new run starts.
    """

    MAX_POINTS = 300  # rolling window for the live plot (avoids unbounded memory growth)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._error_history = deque(maxlen=self.MAX_POINTS)
        self._frame_history = deque(maxlen=self.MAX_POINTS)
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout()

        layout.addWidget(self._build_status_row())
        layout.addWidget(self._build_plot())
        layout.addWidget(self._build_stats_grid())

        self.setLayout(layout)

    def _build_status_row(self):
        box = QGroupBox("Live Status")
        row = QHBoxLayout()

        self.status_label = QLabel("STATUS: —")
        self.status_label.setFont(QFont("Arial", 12, QFont.Bold))

        self.fps_label = QLabel("FPS: —")
        self.fps_label.setFont(QFont("Arial", 12))

        self.error_label = QLabel("Error: — px")
        self.error_label.setFont(QFont("Arial", 12))

        row.addWidget(self.status_label)
        row.addStretch()
        row.addWidget(self.error_label)
        row.addStretch()
        row.addWidget(self.fps_label)

        box.setLayout(row)
        return box

    def _build_plot(self):
        box = QGroupBox("Tracking Error Over Time (px)")
        layout = QVBoxLayout()

        pg.setConfigOption("background", "#1a1a1a")
        pg.setConfigOption("foreground", "#ccc")

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel("left", "Error (px)")
        self.plot_widget.setLabel("bottom", "Frame")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setMinimumHeight(200)

        # Reference line at the 10px spec threshold, for at-a-glance pass/fail
        self.spec_line = pg.InfiniteLine(
            pos=10, angle=0, pen=pg.mkPen("#ff5555", width=1, style=Qt.DashLine)
        )
        self.plot_widget.addItem(self.spec_line)

        self.error_curve = self.plot_widget.plot(
            [], [], pen=pg.mkPen("#00cc66", width=2)
        )

        layout.addWidget(self.plot_widget)
        box.setLayout(layout)
        return box

    def _build_stats_grid(self):
        box = QGroupBox("Run Statistics")
        grid = QGridLayout()

        self.stat_labels = {}
        stat_fields = [
            ("acquisition_time_s", "Acquisition Time (s)"),
            ("avg_tracking_error_px", "Avg Error (px)"),
            ("max_tracking_error_px", "Max Error (px)"),
            ("lock_retention_rate", "Lock Retention"),
            ("target_loss_rate", "Target Loss Rate"),
            ("num_reacquisition_events", "Re-acquisitions"),
        ]

        for i, (key, display_name) in enumerate(stat_fields):
            row, col = divmod(i, 2)
            name_label = QLabel(f"{display_name}:")
            value_label = QLabel("—")
            value_label.setFont(QFont("Arial", 10, QFont.Bold))
            grid.addWidget(name_label, row, col * 2)
            grid.addWidget(value_label, row, col * 2 + 1)
            self.stat_labels[key] = value_label

        box.setLayout(grid)
        return box

    # ------------------------------------------------------------------
    def update_live(self, status, mode, error_px, fps_instant, frame_idx):
        """Call once per tick."""
        status_colors = {"LOCKED": "#00cc66", "SEARCHING": "#ffaa00", "LOST": "#ff4444"}
        color = status_colors.get(status, "#ccc")
        self.status_label.setText(f"STATUS: {status} ({mode})")
        self.status_label.setStyleSheet(f"color: {color};")

        if fps_instant is not None:
            self.fps_label.setText(f"FPS: {fps_instant:.1f}")

        if error_px is not None:
            self.error_label.setText(f"Error: {error_px:.2f} px")
            self._error_history.append(error_px)
            self._frame_history.append(frame_idx)
            self.error_curve.setData(list(self._frame_history), list(self._error_history))
        else:
            self.error_label.setText("Error: — px")

    def update_summary(self, summary):
        """Call periodically (e.g. every N ticks, or on stop) with logger.compute_summary()."""
        for key, label in self.stat_labels.items():
            value = summary.get(key)
            if value is None:
                label.setText("—")
            elif isinstance(value, float):
                if "rate" in key:
                    label.setText(f"{value * 100:.1f}%")
                else:
                    label.setText(f"{value:.2f}")
            else:
                label.setText(str(value))

    def reset(self):
        self._error_history.clear()
        self._frame_history.clear()
        self.error_curve.setData([], [])
        self.status_label.setText("STATUS: —")
        self.status_label.setStyleSheet("")
        self.fps_label.setText("FPS: —")
        self.error_label.setText("Error: — px")
        for label in self.stat_labels.values():
            label.setText("—")