# quick_test_gui_controller.py — sanity check, delete later
from gui.gui_controller import GuiController

ctrl = GuiController()
ctrl.configure(mode="sim", motion_type="circular", noise_types=["gaussian"], atmospheric_preset="clear")
ctrl.start()

for i in range(20):
    result = ctrl.tick()
    fps_str = f"{result.fps_instant:.1f}" if result.fps_instant else "0"
    print(f"frame {result.frame_idx}: status={result.status}, error={result.error_px}, fps={fps_str}")

ctrl.stop()
summary = ctrl.get_summary()
print("\nSummary:", summary.get("avg_tracking_error_px"), "px avg error")