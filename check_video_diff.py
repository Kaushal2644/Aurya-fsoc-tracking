# check_video_diff.py — quick diagnostic, delete after
import cv2

cap1 = cv2.VideoCapture("test_videos/sample1.mp4")
cap2 = cv2.VideoCapture("test_videos/sample2_noisy.mp4")

ret1, frame1 = cap1.read()
ret2, frame2 = cap2.read()

cv2.imwrite("check_clean_frame.png", frame1)
cv2.imwrite("check_noisy_frame.png", frame2)

print("Saved check_clean_frame.png and check_noisy_frame.png — compare them visually")
print(f"Frame1 std: {frame1.std():.2f}, Frame2 std: {frame2.std():.2f}")

cap1.release()
cap2.release()