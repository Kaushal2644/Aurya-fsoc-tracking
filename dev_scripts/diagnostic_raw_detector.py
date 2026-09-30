from core.frame_source import SimulatorFrameSource
from core.detector import BlobDetector

src = SimulatorFrameSource(motion_type="circular", noise_types=[], atmospheric_preset="clear", seed=1)
detector = BlobDetector()

errors = []
for i in range(60):
    frame, gt, t = src.get_frame()
    det = detector.detect_best(frame)
    if det is not None and gt is not None:
        err = ((det.x - gt[0])**2 + (det.y - gt[1])**2) ** 0.5
        errors.append(err)
        print(f"frame {i}: det=({det.x:.1f},{det.y:.1f}) gt=({gt[0]:.1f},{gt[1]:.1f}) err={err:.1f}")
    else:
        print(f"frame {i}: det={det}, gt={gt}")

if errors:
    print(f"\nAvg raw detector error (no Kalman, no video, no noise): {sum(errors)/len(errors):.2f} px")
