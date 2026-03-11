import sys
import os
import json

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from services.slot_service import slot_service, DEMO_MODE
from database import SessionLocal
from models import ParkingSlot

def verify_demo_config():
    print(f"--- Verification: Emergency Demo Configuration ---")
    print(f"DEMO_MODE: {DEMO_MODE}")
    if not DEMO_MODE:
        print("ERROR: DEMO_MODE is False")
        return False

    # 1. Test Slot Evaluation Override
    dummy_detections = [] # No detections
    dummy_scaled_slots = {
        "S1": {"poly_cv2": None, "shapely_poly": None, "area": 0, "status": "available"},
        "S2": {"poly_cv2": None, "shapely_poly": None, "area": 0, "status": "occupied"},
    }
    
    # We need to mock the cache since we might not have a DB connection or the DB might be empty
    slot_service.slot_cache = {
        "S1": {"db_id": "S1", "status": "available"},
        "S2": {"db_id": "S2", "status": "occupied"},
    }
    
    updates, _ = slot_service.evaluate_slots(dummy_detections, dummy_scaled_slots)
    
    # S1 should become occupied (forced)
    # S2 should become available (forced)
    s1_update = next((u for u in updates if u["slot_id"] == "S1"), None)
    s2_update = next((u for u in updates if u["slot_id"] == "S2"), None)
    
    print(f"S1 Update: {s1_update}")
    print(f"S2 Update: {s2_update}")
    
    if s1_update and s1_update["status"] == "occupied" and s2_update and s2_update["status"] == "available":
        print("SUCCESS: Slot evaluation forcing works correctly.")
    else:
        print("FAILED: Slot evaluation forcing mismatch.")
        print(f"Expected S1: occupied, got {s1_update['status'] if s1_update else 'No Update'}")
        print(f"Expected S2: available, got {s2_update['status'] if s2_update else 'No Update'}")
        return False

    # 2. Test redundant update prevention
    # If we call it again with the same IDs, and cache is updated, updates should be empty
    slot_service.slot_cache["S1"]["status"] = "occupied"
    slot_service.slot_cache["S2"]["status"] = "available"
    
    updates2, _ = slot_service.evaluate_slots(dummy_detections, dummy_scaled_slots)
    print(f"Redundant updates count: {len(updates2)}")
    if len(updates2) == 0:
        print("SUCCESS: Redundant update prevention works.")
    else:
        print("FAILED: Redundant updates were generated.")
        return False

    return True

if __name__ == "__main__":
    if verify_demo_config():
        print("\nOVERALL VERIFICATION SUCCESSFUL")
        sys.exit(0)
    else:
        print("\nOVERALL VERIFICATION FAILED")
        sys.exit(1)
