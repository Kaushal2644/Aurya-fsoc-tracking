"""
gui/control_panel.py
Configuration controls: motion type, noise types, atmospheric preset,
mode switch (sim/video), and Start/Stop/Reset buttons.

Emits Qt signals when the user wants to start/stop/reset, so
main_window.py can wire this panel to the GuiController without
this panel needing to know about the pipeline directly.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QCheckBox, QPushButton, QFileDialog, QLineEdit,
)
from PyQt5.QtCore import pyqtSignal

import config


class ControlPanel(QWidget):
    # Emitted when Start is clicked; carries the full config dict
    start_requested = pyqtSignal(dict)
    stop_requested = pyqtSignal()
    reset_requested = pyqtSignal()
    export_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout()

        layout.addWidget(self._build_mode_group())
        layout.addWidget(self._build_sim_config_group())
        layout.addWidget(self._build_video_config_group())
        layout.addWidget(self._build_action_buttons())
        layout.addStretch()

        self.setLayout(layout)
        self._on_mode_changed()  # set initial visibility

    # ------------------------------------------------------------------
    def _build_mode_group(self):
        box = QGroupBox("Input Mode")
        row = QHBoxLayout()

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Simulator", "Video File (Benchmark-2)"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        row.addWidget(QLabel("Mode:"))
        row.addWidget(self.mode_combo)
        box.setLayout(row)
        return box

    def _build_sim_config_group(self):
        self.sim_group = QGroupBox("Simulator Configuration")
        layout = QVBoxLayout()

        # Motion type
        motion_row = QHBoxLayout()
        motion_row.addWidget(QLabel("Target Motion:"))
        self.motion_combo = QComboBox()
        self.motion_combo.addItems(
            config.TARGET_MOTION_TYPES + ["spiral", "sinusoidal"]
        )
        motion_row.addWidget(self.motion_combo)
        layout.addLayout(motion_row)

        # Atmospheric preset
        atmo_row = QHBoxLayout()
        atmo_row.addWidget(QLabel("Atmosphere:"))
        self.atmo_combo = QComboBox()
        self.atmo_combo.addItems(config.ATMOSPHERIC_PRESETS)
        atmo_row.addWidget(self.atmo_combo)
        layout.addLayout(atmo_row)

        # Noise types (multi-select via checkboxes — spec allows combining)
        layout.addWidget(QLabel("Noise Types:"))
        self.noise_checkboxes = {}
        for noise_name in config.NOISE_TYPES:
            cb = QCheckBox(noise_name.replace("_", " ").title())
            self.noise_checkboxes[noise_name] = cb
            layout.addWidget(cb)

        # Seed (for reproducibility)
        seed_row = QHBoxLayout()
        seed_row.addWidget(QLabel("Seed:"))
        self.seed_input = QLineEdit("42")
        self.seed_input.setFixedWidth(80)
        seed_row.addWidget(self.seed_input)
        seed_row.addStretch()
        layout.addLayout(seed_row)

        self.sim_group.setLayout(layout)
        return self.sim_group

    def _build_video_config_group(self):
        self.video_group = QGroupBox("Video File Configuration")
        layout = QVBoxLayout()

        video_row = QHBoxLayout()
        self.video_path_display = QLineEdit()
        self.video_path_display.setReadOnly(True)
        self.video_path_display.setPlaceholderText("No file selected")
        browse_video_btn = QPushButton("Browse Video...")
        browse_video_btn.clicked.connect(self._browse_video)
        video_row.addWidget(self.video_path_display)
        video_row.addWidget(browse_video_btn)
        layout.addLayout(video_row)

        gt_row = QHBoxLayout()
        self.gt_path_display = QLineEdit()
        self.gt_path_display.setReadOnly(True)
        self.gt_path_display.setPlaceholderText("No ground truth CSV (optional)")
        browse_gt_btn = QPushButton("Browse Ground Truth...")
        browse_gt_btn.clicked.connect(self._browse_ground_truth)
        gt_row.addWidget(self.gt_path_display)
        gt_row.addWidget(browse_gt_btn)
        layout.addLayout(gt_row)

        self.video_group.setLayout(layout)
        return self.video_group

    def _build_action_buttons(self):
        box = QGroupBox("Controls")
        layout = QHBoxLayout()

        self.start_btn = QPushButton("▶ Start")
        self.start_btn.setStyleSheet("font-weight: bold; padding: 6px;")
        self.start_btn.clicked.connect(self._on_start_clicked)

        self.stop_btn = QPushButton("■ Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_requested.emit)

        self.reset_btn = QPushButton("↺ Reset")
        self.reset_btn.clicked.connect(self.reset_requested.emit)

        self.export_btn = QPushButton("⤓ Export Log")
        self.export_btn.clicked.connect(self.export_requested.emit)

        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.reset_btn)
        layout.addWidget(self.export_btn)

        box.setLayout(layout)
        return box

    # ------------------------------------------------------------------
    def _on_mode_changed(self):
        is_sim = self.mode_combo.currentIndex() == 0
        self.sim_group.setVisible(is_sim)
        self.video_group.setVisible(not is_sim)

    def _browse_video(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Video File", "", "Video Files (*.mp4 *.avi)")
        if path:
            self.video_path_display.setText(path)

    def _browse_ground_truth(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Ground Truth CSV", "", "CSV Files (*.csv)")
        if path:
            self.gt_path_display.setText(path)

    def _on_start_clicked(self):
        cfg = self.get_config()
        self.start_requested.emit(cfg)

    # ------------------------------------------------------------------
    def get_config(self):
        """Reads current UI state into a plain dict for GuiController.configure()."""
        is_sim = self.mode_combo.currentIndex() == 0
        selected_noise = [name for name, cb in self.noise_checkboxes.items() if cb.isChecked()]

        try:
            seed = int(self.seed_input.text())
        except ValueError:
            seed = 42

        return {
            "mode": "sim" if is_sim else "video",
            "motion_type": self.motion_combo.currentText(),
            "noise_types": selected_noise,
            "atmospheric_preset": self.atmo_combo.currentText(),
            "video_path": self.video_path_display.text() or None,
            "ground_truth_path": self.gt_path_display.text() or None,
            "seed": seed,
        }

    # ------------------------------------------------------------------
    def set_running_state(self, is_running):
        """Called by main_window to enable/disable controls appropriately."""
        self.start_btn.setEnabled(not is_running)
        self.stop_btn.setEnabled(is_running)
        self.mode_combo.setEnabled(not is_running)
        self.sim_group.setEnabled(not is_running)
        self.video_group.setEnabled(not is_running)