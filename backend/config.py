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

# Stabilization & Performance
QUEUE_LIMIT = 50
PROCESSING_FPS_WINDOW = 10
MIN_POLYGON_AREA = 500
FRAME_HASH_SIZE = (64, 64)
FRAME_TIMEOUT_SEC = 2
STREAM_DISCONNECT_TIMEOUT_SEC = 10
QUEUE_BACKPRESSURE_THRESHOLD = 0.8
SLOT_STATE_COOLDOWN_SEC = 1
MAX_STREAM_RETRIES = 5
TRACK_LOST_TIMEOUT = 3
EVENT_LOG_RETENTION_HOURS = 24
TRACKER_MAP_DISTANCE_THRESHOLD = 50 # Pixels

# Stream Sources
PRIMARY_STREAM_URL = os.getenv("PRIMARY_STREAM_URL", "")
FALLBACK_STREAM_URL = os.getenv("FALLBACK_STREAM_URL", "")
DEBUG_STREAM_ENABLED = os.getenv("DEBUG_STREAM_ENABLED", "True").lower() == "true"

ALLOWED_VEHICLE_CLASSES = ["car", "truck", "bus", "motorcycle"]
YOLO_VEHICLE_CLASS_IDS = [2, 3, 5, 7] # COCO: car, motorcycle, bus, truck
