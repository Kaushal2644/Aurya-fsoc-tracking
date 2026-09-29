"""
gui/main_window.py
Top-level window wiring VideoPanel + ControlPanel + MetricsPanel
together with GuiController, driven by a QTimer.

This is the main entry point for the GUI application.
"""

import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QMessageBox, QStatusBar,
)
from PyQt5.QtCore import Qt, QTimer

from gui.video_panel import VideoPanel
from gui.control_panel import ControlPanel
from gui.metrics_panel import MetricsPanel
from gui.gui_controller import GuiController


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIH26169 — FSOC Virtual Camera Tracking System")
        self.resize(1200, 750)

        self.controller = GuiController()
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_tick)

        self._summary_counter = 0
        self._summary_update_interval = 15  # refresh stats grid every N ticks (not every frame — keeps UI light)

        self._build_ui()
        self._wire_signals()

    # ------------------------------------------------------------------
    def _build_ui(self):
        self.video_panel = VideoPanel()
        self.control_panel = ControlPanel()
        self.metrics_panel = MetricsPanel()

        # Left: video feed (large). Right: controls stacked above metrics.
        right_column = QWidget()
        right_layout = QVBoxLayout()
        right_layout.addWidget(self.control_panel)
        right_layout.addWidget(self.metrics_panel)
        right_column.setLayout(right_layout)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.video_panel)
        splitter.addWidget(right_column)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        central = QWidget()
        layout = QHBoxLayout()
        layout.addWidget(splitter)
        layout.setContentsMargins(6, 6, 6, 6)
        central.setLayout(layout)
        self.setCentralWidget(central)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready. Configure settings and click Start.")

    def _wire_signals(self):
        self.control_panel.start_requested.connect(self._on_start)
        self.control_panel.stop_requested.connect(self._on_stop)
        self.control_panel.reset_requested.connect(self._on_reset)
        self.control_panel.export_requested.connect(self._on_export)

    # ------------------------------------------------------------------
    def _on_start(self, cfg):
        if cfg["mode"] == "video" and not cfg["video_path"]:
            QMessageBox.warning(self, "Missing Video File", "Please select a video file before starting video mode.")
            return

        try:
            self.controller.configure(
                mode=cfg["mode"],
                motion_type=cfg["motion_type"],
                noise_types=cfg["noise_types"],
                atmospheric_preset=cfg["atmospheric_preset"],
                video_path=cfg["video_path"],
                ground_truth_path=cfg["ground_truth_path"],
                seed=cfg["seed"],
            )
            self.controller.start()
        except (IOError, ValueError) as e:
            QMessageBox.critical(self, "Failed to Start", str(e))
            return

        self.metrics_panel.reset()
        self._summary_counter = 0

        interval_ms = int(1000 / self.controller.src.get_fps())
        self.timer.start(max(interval_ms, 1))

        self.control_panel.set_running_state(True)
        self.statusBar().showMessage(f"Running: {cfg['mode']} mode...")

    def _on_stop(self):
        self.timer.stop()
        self.controller.stop()
        self.control_panel.set_running_state(False)
        summary = self.controller.get_summary()
        self.metrics_panel.update_summary(summary)
        self.statusBar().showMessage("Stopped. Summary updated.")

    def _on_reset(self):
        self.timer.stop()
        if self.controller.running:
            self.controller.stop()
        self.video_panel.clear()
        self.metrics_panel.reset()
        self.control_panel.set_running_state(False)
        self.statusBar().showMessage("Reset. Ready to configure a new run.")

    def _on_export(self):
        if self.controller.logger is None:
            QMessageBox.information(self, "Nothing to Export", "Start a run first before exporting a log.")
            return
        csv_path, json_path = self.controller.export_log()
        self.statusBar().showMessage(f"Exported: {csv_path}")
        QMessageBox.information(
            self, "Export Complete",
            f"Performance log saved:\n\nCSV: {csv_path}\nJSON: {json_path}"
        )

    # ------------------------------------------------------------------
    def _on_tick(self):
        result = self.controller.tick()

        if result is None:
            return

        if result.end_of_stream:
            self.timer.stop()
            self.control_panel.set_running_state(False)
            summary = self.controller.get_summary()
            self.metrics_panel.update_summary(summary)
            self.statusBar().showMessage("End of video reached. Run complete.")
            return

        self.video_panel.update_frame(
            result.frame, result.estimate, result.ground_truth, result.status, result.mode
        )
        self.metrics_panel.update_live(
            result.status, result.mode, result.error_px, result.fps_instant, result.frame_idx
        )

        self._summary_counter += 1
        if self._summary_counter >= self._summary_update_interval:
            self._summary_counter = 0
            summary = self.controller.get_summary()
            self.metrics_panel.update_summary(summary)

    # ------------------------------------------------------------------
    def closeEvent(self, event):
        self.timer.stop()
        if self.controller.running:
            self.controller.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()