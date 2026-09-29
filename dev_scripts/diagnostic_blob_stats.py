"""
diagnostic_blob_stats.py
Prints the REAL target's actual confidence math for both fog and
low-light scenarios side by side, so thresholds are set once against
real numbers for both cases together — not re-guessed one at a time.
"""

import cv2
import numpy as np
from core.frame_source import SimulatorFrameSource
from core.detector import BlobDetector

detector = BlobDetector()

scenarios = [
    ("FOG", dict(motion_type="circular", noise_types=["gaussian", "salt_pepper"], atmospheric_preset="fog", seed=1)),
    ("LOW_LIGHT", dict(motion_type="straight_line", noise_types=["poisson"], atmospheric_preset="low_light", seed=1)),
]

for label, kwargs in scenarios:
    print(f"\n===== {label} =====")
    src = SimulatorFrameSource(**kwargs)

    frame, gt, t = None, None, None
    for i in range(150):
        frame, gt, t = src.get_frame()
        if gt is not None:
            break

    if gt is None:
        print("Target never visible in 150 frames.")
        continue

    gray = detector._to_gray(frame)
    denoised = detector._denoise(gray)
    binary = detector._threshold(denoised)
    frame_max = max(int(gray.max()), 1)

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
    print(f"Frame max brightness: {frame_max}, raw blob count: {num_labels - 1}")

    for i in range(1, num_labels):
        cx, cy = centroids[i]
        if abs(cx - gt[0]) < 15 and abs(cy - gt[1]) < 15:
            area = stats[i, cv2.CC_STAT_AREA]
            x1, y1 = stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP]
            w, h = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
            x2, y2 = x1 + w, y1 + h
            mean_intensity = gray[y1:y2, x1:x2].mean()
            brightness_score = min(1.0, mean_intensity / frame_max)
            expected_area = 100.0
            size_ratio = min(area, expected_area) / max(area, expected_area)
            confidence = 0.5 * brightness_score + 0.5 * size_ratio
            print(f"REAL TARGET blob: area={area}, mean_intensity={mean_intensity:.1f}, "
                  f"brightness_score={brightness_score:.3f}, size_ratio={size_ratio:.3f}, "
                  f"confidence={confidence:.3f}")
            # Also check confidence of NOISE blobs, to see if a confidence
            # cutoff can actually separate them from the real target
            noise_confidences = []
            for i in range(1, num_labels):
                cx, cy = centroids[i]
                if abs(cx - gt[0]) < 15 and abs(cy - gt[1]) < 15:
                    continue  # skip the real target, already reported above
                area = stats[i, cv2.CC_STAT_AREA]
                if area < detector.min_area or area > detector.max_area:
                    continue  # skip blobs that area-filtering would reject anyway
                x1, y1 = stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP]
                w, h = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
                x2, y2 = x1 + w, y1 + h
                mean_intensity = gray[y1:y2, x1:x2].mean()
                brightness_score = min(1.0, mean_intensity / frame_max)
                size_ratio = min(area, 100.0) / max(area, 100.0)
                conf = 0.5 * brightness_score + 0.5 * size_ratio
                noise_confidences.append(conf)

            if noise_confidences:
                noise_confidences.sort(reverse=True)
                print(f"Noise blobs surviving area filter: {len(noise_confidences)}")
                print(f"Top 5 noise confidences: {[round(c,3) for c in noise_confidences[:5]]}")
            else:
                print("No noise blobs survived area filtering (min_area/max_area already isolates real target).")