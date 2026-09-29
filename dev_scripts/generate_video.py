import cv2
import csv
import math
import numpy as np
from pathlib import Path


WIDTH = 640
HEIGHT = 480
FPS = 30
DURATION_SECONDS = 10
TOTAL_FRAMES = FPS * DURATION_SECONDS

VIDEO_PATH = Path("test_videos/sample1.mp4")
GROUND_TRUTH_PATH = Path("test_videos/sample1_ground_truth.csv")


def main():
    VIDEO_PATH.parent.mkdir(parents=True, exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(
        str(VIDEO_PATH),
        fourcc,
        FPS,
        (WIDTH, HEIGHT),
    )

    if not writer.isOpened():
        raise RuntimeError("Could not create MP4 video.")

    with open(GROUND_TRUTH_PATH, "w", newline="") as csv_file:
        csv_writer = csv.writer(csv_file)

        csv_writer.writerow([
            "frame",
            "x",
            "y",
        ])

        for frame_number in range(TOTAL_FRAMES):
            frame = np.zeros(
                (HEIGHT, WIDTH, 3),
                dtype=np.uint8,
            )

            angle = 2 * math.pi * frame_number / TOTAL_FRAMES

            center_x = int(
                WIDTH / 2 + 180 * math.cos(angle)
            )

            center_y = int(
                HEIGHT / 2 + 130 * math.sin(angle)
            )

            beacon_size = 10

            x1 = center_x - beacon_size // 2
            y1 = center_y - beacon_size // 2
            x2 = center_x + beacon_size // 2
            y2 = center_y + beacon_size // 2

            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                (255, 255, 255),
                thickness=-1,
            )

            writer.write(frame)

            csv_writer.writerow([
                frame_number,
                center_x,
                center_y,
            ])

    writer.release()

    print(f"Video created: {VIDEO_PATH}")
    print(f"Ground truth created: {GROUND_TRUTH_PATH}")
    print(f"Total frames: {TOTAL_FRAMES}")


if __name__ == "__main__":
    main()