"""
diagnostic_visibility.py
Checks whether/when the target enters the camera's FOV at all,
independent of noise or detection — pure geometry check.
"""

from core.frame_source import SimulatorFrameSource

src = SimulatorFrameSource(
    motion_type="straight_line",
    noise_types=["poisson"],
    atmospheric_preset="low_light",
    seed=1,
)

print(f"Camera center: ({src.camera.center_x}, {src.camera.center_y})")
print(f"Camera FOV bbox: {src.camera.get_fov_bbox()}")
print(f"Target initial pos: ({src.targets.targets[0].x:.1f}, {src.targets.targets[0].y:.1f})")
print(f"Target direction: {src.targets.targets[0].direction}")
print(f"Target speed: {src.targets.targets[0].speed}\n")

for i in range(60):
    frame, gt, t = src.get_frame()
    tx, ty = src.targets.targets[0].get_position()
    print(f"frame {i}: target_scene_pos=({tx:.1f},{ty:.1f}) gt_camera_coords={gt}")