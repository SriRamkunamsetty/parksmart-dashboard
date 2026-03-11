from fastapi import APIRouter, UploadFile, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
import uuid
import os
import shutil
import cv2
import time
from sqlalchemy.orm import Session
from database import get_db
from models import ParkingSlot, SystemState, ProcessingJob
from worker import job_manager
from websocket_manager import manager
from config import MAX_VIDEO_SIZE_MB
import logging
from datetime import datetime, timezone

router = APIRouter()

last_upload_time = 0.0
last_start_time = 0.0
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload-parking-video")
def upload_video(file: UploadFile, db: Session = Depends(get_db)):
    global last_upload_time
    
    current_time = time.time()
    if current_time - last_upload_time < 5.0:
        return {"error": "Upload cooldown active. Please wait 5 seconds between uploads."}
    
    allowed_extensions = [".mp4", ".avi", ".mov"]
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        return {"error": "Invalid file type. Only .mp4, .avi, .mov allowed"}
        
    if file.size and file.size > MAX_VIDEO_SIZE_MB * 1024 * 1024:
        return {"error": f"File too large. Maximum size is {MAX_VIDEO_SIZE_MB}MB"}
        
    job_id = str(uuid.uuid4())
    path = os.path.join(UPLOAD_DIR, f"{job_id}{ext}")
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
        
    # Metadata Extraction
    cap = cv2.VideoCapture(path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = total_frames / fps if fps > 0 else 0
    codec = "unknown"
    cap.release()
    
    new_job = ProcessingJob(
        job_id=job_id,
        video_name=file.filename,
        video_path=path,
        video_codec=codec,
        video_width=width,
        video_height=height,
        total_frames=total_frames,
        duration_seconds=duration,
        status="processing"
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
        
    last_upload_time = time.time()
    job_manager.start_job(new_job.id, job_id)
    
    return {
        "message": "Video uploaded. Analysis queued.", 
        "job_id": job_id,
        "metadata": {
            "total_frames": total_frames,
            "duration_seconds": duration,
            "fps": fps
        }
    }

@router.get("/api/jobs")
def list_jobs(db: Session = Depends(get_db)):
    jobs = db.query(ProcessingJob).order_by(ProcessingJob.created_at.desc()).all()
    return jobs

@router.post("/api/jobs/{job_id}/pause")
def pause_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == "processing":
        job.status = "paused"
        db.commit()
        job_manager.pause_job(job.id)
    return {"message": "Job paused"}

@router.post("/api/jobs/{job_id}/resume")
def resume_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == "paused":
        job.status = "processing"
        db.commit()
        job_manager.resume_job(job.id)
    return {"message": "Job resumed"}

@router.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in ["processing", "paused"]:
        job.status = "cancelled"
        db.commit()
        job_manager.cancel_job(job.id)
    return {"message": "Job cancelled"}

@router.get("/analysis-status")
def get_analysis_status(db: Session = Depends(get_db)):
    active = db.query(ProcessingJob).filter(ProcessingJob.status == "processing").first()
    status = "processing" if active else "idle"
    return {
        "running": status == "processing", 
        "status": status,
        "active_job": active.job_id if active else None
    }

def get_video_stream():
    while True:
        frame = job_manager.get_latest_frame()
        if frame is None:
            time.sleep(0.5)
            continue
            
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue
            
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        time.sleep(0.04)

@router.get("/video-feed")
def video_feed():
    return StreamingResponse(get_video_stream(), media_type="multipart/x-mixed-replace; boundary=frame")

@router.post("/start-analysis")
def start_analysis(db: Session = Depends(get_db)):
    # Look for last uploaded file or paused jobs
    job = db.query(ProcessingJob).filter(ProcessingJob.status == "paused").first()
    if job:
        return resume_job(job.job_id, db)
    return {"message": "No active tasks found."}

@router.post("/stop-analysis")
def stop_analysis(db: Session = Depends(get_db)):
    active = db.query(ProcessingJob).filter(ProcessingJob.status == "processing").all()
    for job in active:
        pause_job(job.job_id, db)
    return {"message": "Analysis stopped"}

    return {"message": "Analysis stopped"}

@router.post("/api/jobs/start-demo")
def start_demo_job(data: dict = None, db: Session = Depends(get_db)):
    # Locate parking_video.mp4 in root
    video_filename = "parking_video.mp4"
    if data and "video" in data:
        video_filename = data["video"]
        
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    video_path = os.path.join(root_dir, video_filename)
    
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail=f"Demo video {video_filename} not found in {root_dir}")
        
    # Check if a job is already processing (Prevent duplicate workers)
    existing_job = db.query(ProcessingJob).filter(
        ProcessingJob.status == "processing"
    ).first()
    if existing_job:
        return {"message": "Worker already running", "job_id": existing_job.job_id}

    job_id = f"demo-{str(uuid.uuid4())[:8]}"
    
    # Metadata Extraction
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="Could not open video file")
        
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = total_frames / fps if fps > 0 else 0
    cap.release()
    
    new_job = ProcessingJob(
        job_id=job_id,
        video_name=video_filename,
        video_path=video_path,
        video_codec="h264",
        video_width=width,
        video_height=height,
        total_frames=total_frames,
        duration_seconds=duration,
        status="processing"
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
        
    job_manager.start_job(new_job.id, job_id)
    
    return {
        "message": "Demo analysis started successfully.", 
        "job_id": job_id,
        "metadata": {
            "total_frames": total_frames,
            "duration": f"{duration:.1f}s"
        }
    }

@router.get("/slot-stats")
def slot_stats(db: Session = Depends(get_db)):
    total = db.query(ParkingSlot).count()
    available = db.query(ParkingSlot).filter(ParkingSlot.status == "available").count()
    occupied = db.query(ParkingSlot).filter(ParkingSlot.status == "occupied").count()
    reserved = db.query(ParkingSlot).filter(ParkingSlot.status == "reserved").count()
    
    return {
        "total_slots": total,
        "available": available,
        "occupied": occupied,
        "reserved": reserved
    }
