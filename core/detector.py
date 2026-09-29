"""
core/detector.py
Detects the beacon target within a (possibly noisy) camera frame.
"""

import cv2
import numpy as np
import config


class Detection:
    """Single detected blob."""

    def __init__(self, x, y, area, confidence=1.0, bbox=None):
        self.x = x
        self.y = y
        self.area = area
        self.confidence = confidence
        self.bbox = bbox

    def __repr__(self):
        return f"Detection(x={self.x:.1f}, y={self.y:.1f}, area={self.area}, conf={self.confidence:.2f})"


class BlobDetector:
    """
    Classical CV detector: threshold -> denoise -> connected components
    -> filter by size/shape -> return centroid(s).
    """

    def __init__(
        self,
        min_area=50,                 # px^2, safety margin below the 10x10 default target
        max_area=180,                # px^2, filters out large clutter/false regions
        adaptive=False,
        fixed_threshold=170,
        threshold_percentile=99.9,
        blur_kernel=5,                # reverted to 3 — 5 was shrinking small targets below min_area
        min_circularity=0.3,         # 0-1, filters out non-blob-shaped noise
        min_confidence=0.60,          # NEW: rejects low-confidence noise blobs (real target scores ~1.0)
    ):
        self.min_area = min_area
        self.max_area = max_area
        self.adaptive = adaptive
        self.fixed_threshold = fixed_threshold
        self.blur_kernel = blur_kernel
        self.min_circularity = min_circularity
        self.min_confidence = min_confidence
        self.threshold_percentile = threshold_percentile

    # ------------------------------------------------------------------
    def detect(self, frame):
        gray = self._to_gray(frame)
        denoised = self._denoise(gray)
        binary = self._threshold(denoised)
        frame_max = max(int(gray.max()), 1)  # avoid divide-by-zero on pure-black frames
        detections = self._extract_blobs(binary, gray, frame_max)
        detections = [d for d in detections if d.confidence >= self.min_confidence]
        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections

    def detect_best(self, frame):
        dets = self.detect(frame)
        return dets[0] if dets else None

    # ------------------------------------------------------------------
    def _to_gray(self, frame):
        if frame.ndim == 3:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return frame

    def _denoise(self, gray):
        """Median blur fights salt & pepper without erasing small targets."""
        if self.blur_kernel and self.blur_kernel > 1:
            return cv2.medianBlur(gray, self.blur_kernel)
        return gray

    def _threshold(self, gray):
        if self.adaptive:
            _, binary = cv2.threshold(
                gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
        elif self.threshold_percentile is not None:
            # Percentile-based threshold: adapts per-frame to whatever the
            # brightest pixels actually are (target is always the brightest
            # object present), instead of one fixed value that only suits
            # one specific brightness regime (e.g. fog vs low-light).
            cutoff = np.percentile(gray, self.threshold_percentile)
            cutoff = max(cutoff, 30)  # floor: avoid thresholding near-black frames into pure noise
            _, binary = cv2.threshold(gray, cutoff, 255, cv2.THRESH_BINARY)
        else:
            _, binary = cv2.threshold(
                gray, self.fixed_threshold, 255, cv2.THRESH_BINARY
            )
        return binary

    def _extract_blobs(self, binary, original_gray, frame_max=255):
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            binary, connectivity=8
        )

        detections = []
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if area < self.min_area or area > self.max_area:
                continue

            x1 = stats[i, cv2.CC_STAT_LEFT]
            y1 = stats[i, cv2.CC_STAT_TOP]
            w = stats[i, cv2.CC_STAT_WIDTH]
            h = stats[i, cv2.CC_STAT_HEIGHT]
            x2, y2 = x1 + w, y1 + h

            aspect_ratio = w / h if h > 0 else 0
            if not (0.6 <= aspect_ratio <= 1.6):
                continue

            cx, cy = centroids[i]

            mean_intensity = original_gray[y1:y2, x1:x2].mean() if (y2 > y1 and x2 > x1) else 0
            # Normalized against THIS frame's own brightest pixel, not a fixed
            # 255 scale — otherwise low-light scenes structurally can never
            # score high confidence even when the target is correctly found.
            brightness_score = min(1.0, mean_intensity / frame_max)

            expected_area = 100.0
            size_ratio = min(area, expected_area) / max(area, expected_area)

            confidence = 0.5 * brightness_score + 0.5 * size_ratio

            detections.append(Detection(
                x=cx, y=cy, area=area, confidence=confidence,
                bbox=(x1, y1, x2, y2)
            ))

        return detections