# quick_test_metrics_panel.py — sanity check, delete later
import sys
import random
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import QTimer
from gui.metrics_panel import MetricsPanel

app = QApplication(sys.argv)
window = QMainWindow()
window.setWindowTitle("Metrics Panel Test")

panel = MetricsPanel()
window.setCentralWidget(panel)
window.resize(500, 600)

frame_idx = [0]

def tick():
    frame_idx[0] += 1
    error = abs(random.gauss(5, 8))  # fake noisy error data
    panel.update_live("LOCKED", "TRACKING", error, random.uniform(25, 35), frame_idx[0])
    if frame_idx[0] % 30 == 0:
        panel.update_summary({
            "acquisition_time_s": 0.5,
            "avg_tracking_error_px": 6.2,
            "max_tracking_error_px": 15.8,
            "lock_retention_rate": 0.95,
            "target_loss_rate": 0.02,
            "num_reacquisition_events": 1,
        })

timer = QTimer()
timer.timeout.connect(tick)
timer.start(50)

window.show()
sys.exit(app.exec_())