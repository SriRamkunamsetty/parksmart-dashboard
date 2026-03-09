import os

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Global Configurations
MODEL_PATH = os.getenv("MODEL_PATH", os.path.join(BASE_DIR, "models", "yolov8n.pt"))
MODEL_IMG_SIZE = 416
FRAME_SKIP_DEFAULT = 12
MAX_WORKERS = 1
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", 0.4))
MAX_VIDEO_SIZE_MB = 500
DEBUG_PIPELINE = os.getenv("DEBUG_PIPELINE", "True").lower() == "true"
