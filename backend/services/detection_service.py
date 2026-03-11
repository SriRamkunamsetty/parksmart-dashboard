import torch
from ultralytics import YOLO
import os
import threading
import numpy as np
from config import MODEL_PATH, YOLO_VEHICLE_CLASS_IDS, CONFIDENCE_THRESHOLD, MODEL_IMG_SIZE, YOLO_WARMUP_FRAMES
from utils.logging_utils import log_event

class DetectionService:
    def __init__(self):
        self.model = None
        self.model_lock = threading.Lock()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.warmup_complete = False
        self.load_model()

    def load_model(self):
        if not os.path.exists(MODEL_PATH):
            log_event("startup", f"YOLO model not found at {MODEL_PATH}", {"status": "failed"})
            raise RuntimeError(f"YOLO model not found at {MODEL_PATH}")
        
        log_event("startup", f"Loading YOLO model on {self.device}...")
        self.model = YOLO(MODEL_PATH)
        self.model.to(self.device)
        
        # 2. Model Load Validation Logging
        log_event("startup", "[STARTUP] YOLO model loaded")
        log_event("startup", f"device = {self.device}")
        log_event("startup", "model_loaded = true")
        
        # Warm-up (5 frames per requirement)
        self.warmup(frames=YOLO_WARMUP_FRAMES)
        self.warmup_complete = True

    def warmup(self, frames=5):
        log_event("startup", f"Warming up YOLO model with {frames} dummy frames...")
        dummy_frame = np.zeros((MODEL_IMG_SIZE, MODEL_IMG_SIZE, 3), dtype=np.uint8)
        for _ in range(frames):
            with self.model_lock:
                self.model.predict(dummy_frame, verbose=False, imgsz=MODEL_IMG_SIZE)
        log_event("startup", f"YOLO Model Warmed Up ({frames} frames)")

    def detect(self, frame):
        if self.model is None:
            return []
        
        with self.model_lock:
            results = self.model.track(
                frame, 
                persist=True, 
                imgsz=MODEL_IMG_SIZE, 
                verbose=False, 
                classes=YOLO_VEHICLE_CLASS_IDS, 
                conf=CONFIDENCE_THRESHOLD,
                tracker="bytetrack.yaml"
            )
        return results

    def get_model_info(self):
        """
        2. Model Load Validation API Data
        """
        return {
            "model_loaded": self.model is not None,
            "device": self.device,
            "model_path": MODEL_PATH,
            "warmup_complete": self.warmup_complete
        }

# Singleton management
detection_service = None

def get_detection_service():
    global detection_service
    if detection_service is None:
        detection_service = DetectionService()
    return detection_service
