import cv2
from ultralytics import YOLO
import os

MODEL_PATH = "models/yolov8n.pt"
VIDEO_PATH = "uploads/parking_video.mp4"

if not os.path.exists(MODEL_PATH):
    print(f"Model not found: {MODEL_PATH}")
    exit(1)

if not os.path.exists(VIDEO_PATH):
    print(f"Video not found: {VIDEO_PATH}")
    exit(1)

model = YOLO(MODEL_PATH)
cap = cv2.VideoCapture(VIDEO_PATH)
ret, frame = cap.read()
if ret:
    results = model.track(frame, persist=True, conf=0.15)
    for r in results:
        print(f"Detected {len(r.boxes)} objects")
        for box in r.boxes:
            print(f"Class: {int(box.cls[0])}, Conf: {float(box.conf[0]):.2f}")
else:
    print("Could not read frame from video")
cap.release()
