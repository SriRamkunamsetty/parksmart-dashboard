import requests
import time
import json
import os

BASE_URL = "http://localhost:8000"

def trigger_job():
    print("Triggering test job...")
    try:
        dummy_file = "sample_video_dummy.mp4"
        with open(dummy_file, "wb") as f:
            f.write(b"dummy video content")
            
        with open(dummy_file, "rb") as f:
            files = {'file': (dummy_file, f, 'video/mp4')}
            # Correct endpoint from routes/upload_video.py
            r = requests.post(f"{BASE_URL}/upload-parking-video", files=files)
            
        print(f"Upload Status: {r.status_code}")
        data = r.json()
        print(data)
        return data.get("job_id")
    except Exception as e:
        print(f"Error: {e}")
        return None

def verify_metrics():
    print("\n--- Verifying Metrics ---")
    for i in range(12):
        try:
            r = requests.get(f"{BASE_URL}/api/system/health")
            data = r.json()
            print(f"[{i}] Worker State: {data.get('worker_state')} | Stream: {data.get('stream_state')}")
            if data.get('worker_state') in ["RUNNING", "COMPLETED"]:
                print(f"TPS: {data.get('processing_fps')} | Acc Latency: {data.get('processing_latency_ms')}ms")
                print(f"Heartbeat: {data.get('heartbeat')}")
                print("Reliability Check: OK")
            time.sleep(2)
        except Exception as e:
            print(f"Error: {e}")
            break

if __name__ == "__main__":
    jid = trigger_job()
    verify_metrics()
