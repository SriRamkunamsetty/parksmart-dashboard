from fastapi import APIRouter, Depends
from worker import job_manager
from services.detection_service import get_detection_service

router = APIRouter(prefix="/api/system", tags=["system"])

@router.get("/health")
def get_health():
    """
    1. & 3. Exposes frames_dropped_total and stream_reconnect_count.
    """
    metrics = job_manager.get_metrics()
    return metrics

@router.get("/model")
def get_model_info():
    """
    2. Model Load Validation: Returns model_loaded, device, model_path, warmup_complete.
    """
    service = get_detection_service()
    return service.get_model_info()
