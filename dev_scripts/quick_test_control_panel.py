# quick_test_control_panel.py — sanity check, delete later
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow
from gui.control_panel import ControlPanel

app = QApplication(sys.argv)
window = QMainWindow()
window.setWindowTitle("Control Panel Test")

panel = ControlPanel()
panel.start_requested.connect(lambda cfg: print("START:", cfg))
panel.stop_requested.connect(lambda: print("STOP"))
panel.reset_requested.connect(lambda: print("RESET"))
panel.export_requested.connect(lambda: print("EXPORT"))

window.setCentralWidget(panel)
window.resize(420, 500)
window.show()
sys.exit(app.exec_())