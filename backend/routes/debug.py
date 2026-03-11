from fastapi import APIRouter, Response
from worker import job_manager
from utils.frame_utils import encode_frame_to_mjpeg

router = APIRouter(prefix="/api/debug", tags=["debug"])

@router.get("/pipeline")
def debug_pipeline():
    """
    10. Debug API: Exposes worker_state, heartbeat, queue_size, etc.
    """
    metrics = job_manager.get_metrics()
    return {
        "worker_state": metrics.get("worker_state"),
        "stream_state": metrics.get("stream_state"),
        "frames_received": metrics.get("frames_received"),
        "frames_processed": metrics.get("frames_processed"),
        "frames_dropped_total": metrics.get("frames_dropped_total"),
        "queue_size": metrics.get("queue_size"),
        "frame_queue_size": metrics.get("frame_queue_size"),
        "queue_latency_ms": metrics.get("queue_latency_ms"),
        "processing_fps": metrics.get("processing_fps"),
        "fps_stability": metrics.get("fps_stability"),
        "processing_latency_ms": metrics.get("processing_latency_ms"),
        "inference_time_ms": metrics.get("inference_time_ms"),
        "slot_eval_time_ms": metrics.get("slot_eval_time_ms"),
        "decode_time_ms": metrics.get("decode_time_ms"),
        "hash_skip_counter": metrics.get("hash_skip_counter"),
        "frame_skip_interval": metrics.get("frame_skip_interval"),
        "heartbeat": metrics.get("heartbeat"),
        "model_loaded": metrics.get("model_loaded")
    }

@router.get("/frame")
def debug_frame():
    """
    Debug API: Returns latest processed frame with overlays.
    """
    frame = job_manager.get_latest_frame()
    if frame is None:
        return Response(content=b"", media_type="image/jpeg")
    
    buffer = encode_frame_to_mjpeg(frame)
    return Response(content=buffer, media_type="image/jpeg")
