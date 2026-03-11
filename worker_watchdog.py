import requests
import time
import sys

BASE_URL = "http://localhost:8000"
DEBUG_URL = f"{BASE_URL}/api/debug/pipeline"
TRIGGER_URL = f"{BASE_URL}/api/jobs/start-demo"

def monitor_worker():
    print("Starting Worker Watchdog...")
    while True:
        try:
            r = requests.get(DEBUG_URL, timeout=5)
            if r.status_code == 200:
                data = r.json()
                worker_state = data.get("worker_state")
                
                if worker_state == "FAILED":
                    print("[WATCHDOG] Worker state is FAILED. Restarting...")
                    requests.post(TRIGGER_URL, json={"video": "parking_video.mp4"})
                elif worker_state == "IDLE":
                    # Optionally start if idle and not just finished
                    pass
                else:
                    # Healthy
                    pass
            else:
                print(f"[WATCHDOG] Backend returned {r.status_code}")
        except Exception as e:
            print(f"[WATCHDOG] Error: {e}")
            
        time.sleep(10)

if __name__ == "__main__":
    monitor_worker()
