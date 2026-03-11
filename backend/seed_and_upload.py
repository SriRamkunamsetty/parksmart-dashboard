import requests
import json
import time

BASE = "http://localhost:8000"

# 1. Reseed slots S1-S7
print("=" * 50)
print("STEP 1: Seeding Slots S1-S7")
print("=" * 50)
r = requests.post(f"{BASE}/api/slots/reseed")
print(f"Reseed: {r.json()}")

# 2. Configure polygon coordinates for each slot (960x540 design space)
print("\n" + "=" * 50)
print("STEP 2: Configuring Polygon Regions")
print("=" * 50)
polygons = {
    "S1": [[50, 100], [200, 100], [200, 250], [50, 250]],
    "S2": [[220, 100], [370, 100], [370, 250], [220, 250]],
    "S3": [[390, 100], [540, 100], [540, 250], [390, 250]],
    "S4": [[560, 100], [710, 100], [710, 250], [560, 250]],
    "S5": [[50, 300], [200, 300], [200, 450], [50, 450]],
    "S6": [[220, 300], [370, 300], [370, 450], [220, 450]],
    "S7": [[390, 300], [540, 300], [540, 450], [390, 450]],
}

for slot_id, poly in polygons.items():
    r = requests.put(
        f"{BASE}/api/slots/{slot_id}",
        json={"polygon": json.dumps(poly)},
    )
    print(f"  {slot_id}: {r.json()}")

# 3. Verify slots
print("\n" + "=" * 50)
print("STEP 3: Verifying Slots")
print("=" * 50)
r = requests.get(f"{BASE}/api/slots")
for s in r.json():
    print(f"  {s['id']}: status={s['status']}, polygon_configured={s['polygon_configured']}")

# 4. Upload parking video
print("\n" + "=" * 50)
print("STEP 4: Uploading Parking Video")
print("=" * 50)
with open(r"d:\parksmart-dashboard\parking_video.mp4", "rb") as f:
    r = requests.post(
        f"{BASE}/upload-parking-video",
        files={"file": ("parking_video.mp4", f, "video/mp4")},
    )
print(f"Upload: {json.dumps(r.json(), indent=2)}")

# 5. Wait and check pipeline
print("\n" + "=" * 50)
print("STEP 5: Waiting for Pipeline (10s)...")
print("=" * 50)
time.sleep(10)

r = requests.get(f"{BASE}/api/debug/pipeline")
pipeline = r.json()
print(f"Pipeline Status:")
print(json.dumps(pipeline, indent=2))

# 6. Health check
print("\n" + "=" * 50)
print("STEP 6: System Health")
print("=" * 50)
r = requests.get(f"{BASE}/api/system/health")
health = r.json()
print(json.dumps(health, indent=2))

# 7. Slot stats
print("\n" + "=" * 50)
print("STEP 7: Slot Stats")
print("=" * 50)
r = requests.get(f"{BASE}/slot-stats")
print(json.dumps(r.json(), indent=2))

# 8. Model info
print("\n" + "=" * 50)
print("STEP 8: Model Info")
print("=" * 50)
r = requests.get(f"{BASE}/api/system/model")
print(json.dumps(r.json(), indent=2))
