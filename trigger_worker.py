import requests
import os
import sys

BASE_URL = "http://localhost:8000"
VIDEO_FILE = "parking_video.mp4"

def trigger_worker():
    if not os.path.exists(VIDEO_FILE):
        # Try finding it in parent dir if run from backend/
        if os.path.exists("../" + VIDEO_FILE):
            video_path = "../" + VIDEO_FILE
        else:
            print(f"Error: {VIDEO_FILE} not found in root or parent.")
            return False
    else:
        video_path = VIDEO_FILE
        
    print(f"Uploading {video_path} to trigger analysis...")
    with open(video_path, "rb") as f:
        try:
            r = requests.post(
                f"{BASE_URL}/upload-parking-video",
                files={"file": (VIDEO_FILE, f, "video/mp4")},
                timeout=30
            )
            if r.status_code == 200:
                print(f"Success: {r.json().get('message')}")
                print(f"Job ID: {r.json().get('job_id')}")
                return True
            else:
                print(f"Failed: {r.status_code} - {r.text}")
        except Exception as e:
            print(f"Error connecting to backend: {e}")
    return False

if __name__ == "__main__":
    if trigger_worker():
        sys.exit(0)
    else:
        sys.exit(1)
