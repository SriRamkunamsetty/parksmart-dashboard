import sys
import os
import time
import threading
import psutil
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from worker import job_manager
from database import SessionLocal
from models import ProcessingJob

def create_mock_job():
    db = SessionLocal()
    job_id = str(uuid.uuid4())
    job = ProcessingJob(
        job_id=job_id,
        video_name="mock.mp4",
        video_path="mock.mp4",
        total_frames=1000,
        status="processing"
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    db_id = job.id
    db.close()
    return db_id, job_id

def stress_test():
    print("Starting JobManager Stress Test...")
    jobs_to_spawn = 10
    
    print(f"Spawning {jobs_to_spawn} concurrent jobs into database...")
    
    start_time = time.time()
    
    for i in range(jobs_to_spawn):
        db_id, j_id = create_mock_job()
        job_manager.start_job(db_id, j_id)
        time.sleep(0.1)
        
    print(f"Active Workers in Manager: {len(job_manager.active_jobs)}")
    print(f"Target Max Workers Enforced: {len(job_manager.active_jobs) <= 1}")
    
    print("Monitoring CPU and Queue Latency...")
    for _ in range(5):
        time.sleep(1)
        print(f"CPU Utilization: {psutil.cpu_percent()}% | Queue Latency: {(time.time() - start_time):.2f}s")
        
    print("Stress Test Completed.")

if __name__ == "__main__":
    stress_test()
