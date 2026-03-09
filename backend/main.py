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
from models import ProcessingJob
from config import MODEL_IMG_SIZE

logging.basicConfig(
    level=logging.INFO, 
    format="[%(levelname)s] %(asctime)s - %(message)s"
)

# Routers
from routes import slots, booking, admin, upload_video
from booking_timer import scheduler
from websocket_manager import manager
from worker import job_manager, get_model

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Parksmart API")
START_TIME = datetime.utcnow()

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
        "frame_queue_size": len(job_manager.active_jobs) * 50, # In a pure queue system this is the length
        "frame_skip_interval": job_manager.get_active_skip_interval(),
        "decode_time_ms": metrics["decode_time_ms"],
        "inference_time_ms": metrics["inference_time_ms"],
        "slot_eval_time_ms": metrics["slot_eval_time_ms"],
        "recent_metrics": job_manager.get_recent_metrics()
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

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
