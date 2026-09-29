# quick_test_video_panel.py — sanity check, delete later
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import QTimer
from gui.video_panel import VideoPanel
from gui.gui_controller import GuiController

app = QApplication(sys.argv)

window = QMainWindow()
window.setWindowTitle("Video Panel Test")
panel = VideoPanel()
window.setCentralWidget(panel)
window.resize(700, 550)

ctrl = GuiController()
ctrl.configure(mode="sim", motion_type="circular", noise_types=["gaussian"], atmospheric_preset="clear")
ctrl.start()

def tick():
    result = ctrl.tick()
    if result:
        panel.update_frame(result.frame, result.estimate, result.ground_truth, result.status, result.mode)

timer = QTimer()
timer.timeout.connect(tick)
timer.start(33)  # ~30 fps

window.show()
sys.exit(app.exec_())