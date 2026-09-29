"""
main.py
End-to-end CLI runner for the FSOC Virtual Camera Tracking System.

Two modes:
  --mode sim     : run the live simulator (scene + PTZ camera + controller loop)
  --mode video    : run Benchmark-2 style ingestion from a .mp4 file
                    (PTZ bypassed, detector/tracker still run on each frame)

Usage:
  python main.py --mode sim --motion circular --noise gaussian salt_pepper --atmosphere fog --frames 300
  python main.py --mode video --video_path test_videos/sample1.mp4
"""

import argparse
import time
import cv2

import config
from core.frame_source import SimulatorFrameSource, VideoFileFrameSource
from core.detector import BlobDetector
from core.tracker import KalmanTracker
from core.controller import TrackingController
from core.logger import PerformanceLogger


def parse_args():
    parser = argparse.ArgumentParser(description="FSOC Virtual Camera Tracking System")
    parser.add_argument("--mode", choices=["sim", "video"], default="sim")
    parser.add_argument("--motion", choices=config.TARGET_MOTION_TYPES + ["spiral", "sinusoidal"],
                         default="random")
    parser.add_argument("--noise", nargs="*", choices=config.NOISE_TYPES, default=[])
    parser.add_argument("--atmosphere", choices=config.ATMOSPHERIC_PRESETS, default="clear")
    parser.add_argument("--frames", type=int, default=300, help="number of frames to run (sim mode)")
    parser.add_argument("--video_path", type=str, default=None, help="path to .mp4 (video mode)")
    parser.add_argument("--ground_truth_path", type=str, default=None,
                         help="optional CSV of ground truth for video mode")
    parser.add_argument("--run_name", type=str, default=None)
    parser.add_argument("--display", action="store_true", help="show live OpenCV window while running")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def build_frame_source(args):
    if args.mode == "sim":
        return SimulatorFrameSource(
            motion_type=args.motion,
            noise_types=args.noise,
            atmospheric_preset=args.atmosphere,
            fps=config.TARGET_PROCESSING_FPS_MIN,
            seed=args.seed,
        )
    else:
        if not args.video_path:
            raise ValueError("--video_path is required when --mode video")
        return VideoFileFrameSource(
            video_path=args.video_path,
            ground_truth_path=args.ground_truth_path,
        )


def build_detector(src):
    """
    Builds a BlobDetector, auto-scaling area thresholds if the frame
    source's resolution differs from the 640x480 the defaults assume
    (video-file mode only; sim mode is always exactly 640x480).
    """
    scale = getattr(src, "get_resolution_scale", lambda: 1.0)()
    if abs(scale - 1.0) < 0.01:
        return BlobDetector()

    return BlobDetector(
        min_area=int(50 * scale * scale),
        max_area=int(180 * scale * scale),
    )


def draw_overlay(frame, estimate, gt, status, mode_label):
    """Draws detection/tracking overlay for --display visualization."""
    vis = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR) if frame.ndim == 2 else frame.copy()

    if gt is not None:
        cv2.circle(vis, (int(gt[0]), int(gt[1])), 10, (0, 255, 0), 1)   # green = ground truth
    if estimate is not None:
        cv2.circle(vis, (int(estimate[0]), int(estimate[1])), 6, (0, 0, 255), 2)  # red = tracker estimate

    cv2.putText(vis, f"status={status} mode={mode_label}", (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    return vis


def main():
    args = parse_args()

    run_name = args.run_name or f"{args.mode}_{args.motion if args.mode=='sim' else 'video'}"

    src = build_frame_source(args)
    detector = build_detector(src)
    tracker_scale = getattr(src, "get_resolution_scale", lambda: 1.0)()
    # Empirically-tuned override for the specific 2x-resolution case
    # we've validated (see tracker.py's note on why this isn't a
    # general formula). Any other non-640x480 resolution would need
    # its own calibration pass before being trusted.
    if abs(tracker_scale - 2.0) < 0.05:
        tracker = KalmanTracker(process_noise=5000.0, measurement_noise=0.5, position_scale=tracker_scale)
    else:
        tracker = KalmanTracker(position_scale=tracker_scale)
    controller = TrackingController()
    logger = PerformanceLogger(run_name=run_name)

    dt = 1.0 / src.get_fps()

    logger.start()
    frame_count = 0

    print(f"[main] Starting run: mode={args.mode}, run_name={run_name}")

    try:
        while True:
            if args.mode == "sim" and frame_count >= args.frames:
                break

            frame_start = time.time()
            frame, gt, sim_t = src.get_frame()

            if frame is None:  # end of video file
                print("[main] End of video reached.")
                break

            detections = detector.detect(frame)
            tracker.predict(dt)
            det = tracker.select_best_detection(detections)
            tracker.update(det)

            pan_cmd, tilt_cmd, mode_label = controller.compute(tracker, dt)
            if src.is_live():
                src.move_camera(pan_cmd, tilt_cmd)

            estimate = tracker.get_estimate()
            frame_proc_time = time.time() - frame_start

            logger.log_frame(sim_t, tracker.status, estimate, gt, frame_proc_time)

            if args.display:
                vis = draw_overlay(frame, estimate, gt, tracker.status, mode_label)
                cv2.imshow("FSOC Tracking System", vis)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("[main] Quit requested by user.")
                    break

            frame_count += 1

    except KeyboardInterrupt:
        print("[main] Interrupted by user.")

    finally:
        logger.stop()
        src.release()
        if args.display:
            cv2.destroyAllWindows()

        logger.print_summary()
        logger.export()


if __name__ == "__main__":
    main()