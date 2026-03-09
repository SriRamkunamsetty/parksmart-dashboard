import logging
import os
import psutil
import asyncio
import numpy as np
from datetime import datetime, timedelta
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from database import engine, SessionLocal
import models
from models import ProcessingJob, ParkingSession, SystemEvent, ParkingSlot
from config import MODEL_IMG_SIZE, EVENT_LOG_RETENTION_HOURS, LIVE_API_CACHE_TTL, MIN_FORECAST_SAMPLE_SIZE, FORECAST_CACHE_TTL

logging.basicConfig(
    level=logging.INFO, 
    format="[%(levelname)s] %(asctime)s - %(message)s"
)

# Routers
from routes import slots, booking, admin, upload_video
from booking_timer import scheduler
from websocket_manager import manager
from worker import job_manager, get_model, get_system_settings, set_system_mode, get_model_metadata

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Parksmart API")
START_TIME = datetime.utcnow()
LIVE_SLOTS_CACHE = {"data": None, "timestamp": 0}
FORECAST_CACHE = {"data": None, "timestamp": 0}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(slots.router)
app.include_router(booking.router)
app.include_router(admin.router)
app.include_router(upload_video.router)

@app.get("/api/system/health")
def system_health():
    uptime = (datetime.utcnow() - START_TIME).total_seconds()
    active_job = list(job_manager.active_jobs.keys())[0] if job_manager.active_jobs else None
    
    metrics = job_manager.get_profiling_metrics()
    
    return {
        "status": "online",
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent,
        "active_workers": len(job_manager.active_jobs),
        "process_uptime": uptime,
        "active_job_id": active_job,
        "frame_queue_pressure": metrics["queue_pressure"],
        "frame_processing_time_avg": metrics["frame_processing_time_avg"],
        "frame_processing_time_max": metrics["frame_processing_time_max"],
        "detection_fps": metrics["detection_fps"],
        "frame_stats": metrics["frame_stats"],
        "detected_classes": metrics["detected_classes"],
        "stream_source": metrics["stream_source"],
        "frame_skip_interval": job_manager.get_active_skip_interval(),
        "decode_time_ms": metrics["decode_time_ms"],
        "inference_time_ms": metrics["inference_time_ms"],
        "slot_eval_time_ms": metrics["slot_eval_time_ms"],
        "gpu_usage": metrics.get("gpu_usage", "N/A"),
        "stream_status": metrics.get("stream_status", "unknown"),
        "camera_fps": metrics.get("camera_fps", 0),
        "camera_latency": metrics.get("camera_latency", 0),
        "camera_last_frame_time": metrics.get("camera_last_frame_time", 0)
    }

@app.get("/api/system/settings")
def get_settings():
    settings = get_system_settings()
    return {
        "system_status": getattr(settings, "system_status", "idle"),
        "system_mode": getattr(settings, "system_mode", "NORMAL")
    }

@app.post("/api/system/mode")
def update_system_mode(mode: str):
    if mode not in ["NORMAL", "SAFE_MODE"]:
        return {"error": "Invalid mode"}
    set_system_mode(mode)
    return {"status": "success", "mode": mode}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/api/slots/utilization")
def get_slots_utilization():
    db = SessionLocal()
    try:
        slots = db.query(models.ParkingSlot).all()
        return [
            {
                "id": s.id,
                "number": s.number,
                "occupancy_count": s.occupancy_count or 0,
                "total_occupied_time_sec": round(s.total_occupied_time or 0.0, 2),
                "heatmap_count": s.heatmap_count or 0
            }
            for s in slots
        ]
    finally:
        db.close()

@app.get("/api/slots/live")
def get_slots_live():
    global LIVE_SLOTS_CACHE
    import time
    now_ts = time.time()
    if LIVE_SLOTS_CACHE["data"] and (now_ts - LIVE_SLOTS_CACHE["timestamp"] < LIVE_API_CACHE_TTL):
        return LIVE_SLOTS_CACHE["data"]
    db = SessionLocal()
    try:
        slots = db.query(ParkingSlot).all()
        result = []
        now_utc = datetime.utcnow()
        for s in slots:
            session_duration = 0
            vehicle_id = "unknown"
            if s.status == "occupied":
                active_session = db.query(ParkingSession).filter(
                    ParkingSession.slot_id == s.id,
                    ParkingSession.exit_time == None
                ).first()
                if active_session:
                    vehicle_id = active_session.vehicle_id
                    session_duration = (now_utc - active_session.entry_time).total_seconds()
            # Improvement 1 — Add Slot Visualization Metadata
            uptime = (datetime.utcnow() - START_TIME).total_seconds()
            rate = min(1.0, s.total_occupied_time / uptime) if uptime > 0 else 0
            
            result.append({
                "slot_id": s.id,
                "status": s.status,
                "vehicle_id": vehicle_id,
                "session_duration_sec": round(session_duration, 2),
                "occupancy_rate": round(rate, 2),
                "last_updated": s.last_status_change_at.isoformat() if s.last_status_change_at else None
            })
        LIVE_SLOTS_CACHE = {"data": result, "timestamp": now_ts}
        return result
    finally:
        db.close()

@app.get("/api/slots/heatmap")
def get_slots_heatmap():
    db = SessionLocal()
    try:
        slots = db.query(models.ParkingSlot).all()
        result = []
        for s in slots:
            uptime = (datetime.utcnow() - START_TIME).total_seconds()
            rate = min(1.0, s.total_occupied_time / uptime) if uptime > 0 else 0
            avg_duration = s.total_occupied_time / s.occupancy_count if (s.occupancy_count and s.occupancy_count > 0) else 0
            result.append({
                "slot_id": s.id,
                "occupancy_rate": round(rate, 2),
                "average_duration_sec": round(avg_duration, 2)
            })
        return result
    finally:
        db.close()

@app.get("/api/analytics/vehicle-types")
def get_vehicle_analytics():
    metrics = job_manager.get_profiling_metrics()
    return metrics["detected_classes"]

@app.get("/api/analytics/occupancy-forecast")
def get_occupancy_forecast():
    """Simple rolling average forecast with safety guard and caching"""
    global FORECAST_CACHE
    import time
    now_ts = time.time()
    
    if FORECAST_CACHE["data"] and (now_ts - FORECAST_CACHE["timestamp"] < FORECAST_CACHE_TTL):
        return FORECAST_CACHE["data"]
        
    db = SessionLocal()
    try:
        # Correction 2 — Forecast Model Protection
        total_sessions = db.query(ParkingSession).count()
        if total_sessions < MIN_FORECAST_SAMPLE_SIZE:
            return {
                "predicted_occupancy": None,
                "status": "insufficient_data",
                "sample_size": total_sessions,
                "required": MIN_FORECAST_SAMPLE_SIZE
            }

        slots = db.query(ParkingSlot).all()
        current_occupied = sum(1 for s in slots if s.status == "occupied")
        
        three_hours_ago = datetime.utcnow() - timedelta(hours=3)
        recent_sessions = db.query(ParkingSession).filter(
            (ParkingSession.entry_time >= three_hours_ago) | (ParkingSession.exit_time == None)
        ).count()
        
        forecast_val = round((recent_sessions + current_occupied) / 2, 1)
        
        res = {
            "predicted_occupancy": min(len(slots), forecast_val),
            "confidence": 0.75,
            "period": "next_1_hour",
            "status": "success",
            "sample_size": total_sessions
        }
        FORECAST_CACHE = {"data": res, "timestamp": now_ts}
        return res
    finally:
        db.close()

@app.get("/api/system/model")
def get_model_info():
    """Improvement 2 — Add Model Metadata Endpoint"""
    return get_model_metadata()

@app.get("/api/events")
def get_events(limit: int = 50):
    db = SessionLocal()
    try:
        import json
        events = db.query(models.SystemEvent).order_by(models.SystemEvent.timestamp.desc()).limit(limit).all()
        return [
            {
                "id": e.id,
                "event_type": e.event_type,
                "message": e.message,
                "timestamp": e.timestamp.isoformat(),
                "meta_data": json.loads(e.meta_data) if e.meta_data else {}
            }
            for e in events
        ]
    finally:
        db.close()

def initialize_db():
    db = SessionLocal()
    try:
        count = db.query(models.ParkingSlot).count()
        if count < 7:
            for i in range(1, 8):
                s_id = f"S{i}"
                if not db.query(models.ParkingSlot).filter(models.ParkingSlot.id == s_id).first():
                    new_slot = models.ParkingSlot(
                        id=s_id, number=f"S-0{i}", floor="S", status="available", polygon="[]"
                    )
                    db.add(new_slot)
            db.commit()
    except Exception as e:
        logging.error(f"DB Init Error: {e}")
    finally:
        db.close()

def recover_jobs():
    db = SessionLocal()
    try:
        threshold = datetime.utcnow() - timedelta(minutes=5)
        stuck_jobs = db.query(ProcessingJob).filter(
            ProcessingJob.status == "processing",
            ProcessingJob.updated_at < threshold
        ).all()
        
        for job in stuck_jobs:
            logging.info(f"Recovering orphaned job {job.job_id}")
            job.status = "paused" # Soft-pause so admin can intentionally resume
        if stuck_jobs:
            db.commit()
    except Exception as e:
        logging.error(f"Job Recovery Error: {e}")
    finally:
        db.close()

def cleanup_storage():
    import shutil
    upload_dir = "uploads"
    if not os.path.exists(upload_dir):
        return
        
    disk_percent = psutil.disk_usage('/').percent
    is_critical_disk = disk_percent > 80.0
    
    import time
    now = time.time()
    for filename in os.listdir(upload_dir):
        fp = os.path.join(upload_dir, filename)
        if os.path.isfile(fp):
            age_days = (now - os.path.getmtime(fp)) / (86400)
            if age_days > 7 or (is_critical_disk and age_days > 1):
                try:
                    os.remove(fp)
                    logging.info(f"Cleaned up {filename} (Disk: {disk_percent}%)")
                except:
                    pass
    
    # Event Log Retention
    db = SessionLocal()
    try:
        retention_limit = datetime.utcnow() - timedelta(hours=EVENT_LOG_RETENTION_HOURS)
        deleted = db.query(SystemEvent).filter(SystemEvent.timestamp < retention_limit).delete()
        if deleted > 0:
            db.commit()
            logging.info(f"Purged {deleted} old system events.")
    except Exception as e:
        logging.error(f"Event Log Cleanup Error: {e}")
        db.rollback()
    finally:
        db.close()

@app.on_event("startup")
async def startup_event():
    manager.loop = asyncio.get_running_loop()

    os.makedirs("uploads", exist_ok=True)
    initialize_db()
    
    # 1. Job Recovery
    recover_jobs()
    
    # 2. YOLO Warmup Singleton (Bypass PyTorch Lazy Load)
    model = get_model()
    if model is not None:
        try:
            dummy_frame = np.zeros((MODEL_IMG_SIZE, MODEL_IMG_SIZE, 3), dtype=np.uint8)
            model.predict(dummy_frame, imgsz=MODEL_IMG_SIZE, verbose=False)
            logging.info("YOLO Model Warmed Up.")
        except Exception as e:
            logging.error(f"Warmup Failed: {e}")
            
    # 3. Schedule Cleanup Cron
    scheduler.add_job(cleanup_storage, 'interval', hours=1, id='storage_cleanup', replace_existing=True)
    scheduler.start()
    logging.info("Backend Systems Online.")

@app.on_event("shutdown")
def shutdown_event():
    logging.info("Shutting down... saving active jobs state.")
    try:
        scheduler.shutdown()
    except Exception:
        pass
    
    # Gracefully save running processes into paused state for recovery
    db = SessionLocal()
    try:
        active_jobs = db.query(ProcessingJob).filter(ProcessingJob.status == "processing").all()
        for job in active_jobs:
            logging.info(f"Gracefully pausing job {job.job_id} before exit")
            job.status = "paused"
        db.commit()
    finally:
        db.close()
