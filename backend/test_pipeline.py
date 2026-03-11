import requests
import json
import time

BASE_URL = "http://localhost:8100"

def test_health():
    print("\n--- Testing Health API ---")
    try:
        r = requests.get(f"{BASE_URL}/api/system/health")
        print(f"Status: {r.status_code}")
        print(json.dumps(r.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

def test_debug_pipeline():
    print("\n--- Testing Debug Pipeline ---")
    try:
        r = requests.get(f"{BASE_URL}/api/debug/pipeline")
        print(f"Status: {r.status_code}")
        print(json.dumps(r.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

def test_model():
    print("\n--- Testing Model API ---")
    try:
        r = requests.get(f"{BASE_URL}/api/system/model")
        print(f"Status: {r.status_code}")
        print(json.dumps(r.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    time.sleep(5) # Give server time to warm up
    test_health()
    test_debug_pipeline()
    test_model()
