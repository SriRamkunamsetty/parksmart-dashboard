import requests
import time
import sys

BASE_URL = "http://localhost:8000"

def check_health():
    try:
        r = requests.get(f"{BASE_URL}/api/system/health", timeout=2)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

def check_pipeline():
    try:
        r = requests.get(f"{BASE_URL}/api/debug/pipeline", timeout=2)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

def wait_for_system(timeout=60):
    start_time = time.time()
    print(f"Waiting for backend to be ready (timeout {timeout}s)...")
    while time.time() - start_time < timeout:
        health = check_health()
        if health:
            print("Backend is UP.")
            print(f"Active Workers: {health.get('active_workers', 0)}")
            return True
        time.sleep(2)
    return False

if __name__ == "__main__":
    if wait_for_system():
        print("System verified successfully.")
        sys.exit(0)
    else:
        print("System verification failed (timeout).")
        sys.exit(1)
