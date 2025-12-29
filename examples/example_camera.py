import cv2
import time

print("Opening Camera...")
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

if not cap.isOpened():
    print("Error: Could not open camera.")
    exit()

print("Warming up camera (30 frames)...")
# 露出安定のため空読み
for _ in range(30):
    cap.read()
    time.sleep(0.05)

print("Capturing...")
ret, frame = cap.read()

if ret:
    cv2.imwrite("test_capture.jpg", frame)
    print("Image saved to test_capture.jpg")
else:
    print("Error: Could not read frame.")

cap.release()