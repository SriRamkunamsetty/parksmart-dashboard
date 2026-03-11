import requests
import json
import time

BASE = "http://localhost:8000"

print("=" * 50)
print("FINAL PIPELINE VERIFICATION")
print("=" * 50)

# 1. Pipeline Metrics
r = requests.get(f"{BASE}/api/debug/pipeline")
p = r.json()
print(f"Worker State: {p.get('worker_state')}")
print(f"Slot Eval Time: {p.get('slot_eval_time_ms')} ms")
print(f"Inference Time: {p.get('inference_time_ms')} ms")

# 2. Slot Status
r = requests.get(f"{BASE}/api/slots")
slots = r.json()
print("\nSlot Occupancy Status:")
for s in slots:
    print(f"  {s['id']}: {s['status'].upper()} (Poly Configured: {s['polygon_configured']})")

# 3. Stats
r = requests.get(f"{BASE}/slot-stats")
stats = r.json()
print(f"\nStats: {stats}")

# 4. Check for log messages in health (if any)
r = requests.get(f"{BASE}/api/system/health")
h = r.json()
print(f"\nSystem Health: {h}")

print("=" * 50)
