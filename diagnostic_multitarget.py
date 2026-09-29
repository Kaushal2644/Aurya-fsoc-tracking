"""
diagnostic_multitarget.py
Checks whether multi-target scenes render correctly, whether the
detector finds multiple blobs, and whether ground truth reporting
(which only tracks targets[0]) creates a mismatch with what the
detector/tracker actually locks onto.
"""

from core.frame_source import SimulatorFrameSource
from core.detector import BlobDetector

src = SimulatorFrameSource(
    motion_type="circular",
    num_targets=2,
    noise_types=[],
    atmospheric_preset="clear",
    seed=1,
)
detector = BlobDetector()

for i in range(10):
    frame, gt, t = src.get_frame()
    detections = detector.detect(frame)

    all_target_positions = [t.get_position() for t in src.targets.targets]

    print(f"frame {i}:")
    print(f"  ground_truth (targets[0] only): {gt}")
    print(f"  ALL target scene positions: {[(round(x,1), round(y,1)) for x,y in all_target_positions]}")
    print(f"  detections found: {len(detections)}")
    for d in detections:
        print(f"    {d}")
    print()