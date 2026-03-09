import math
import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import ParkingSlot
from websocket_manager import manager

router = APIRouter()

def sort_clockwise(points):
    """Sort points in clockwise order."""
    if not points:
        return []
    # Calculate centroid
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    # Sort by angle from centroid
    return sorted(points, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))

@router.get("/slots")
def get_slots(db: Session = Depends(get_db)):
    slots = db.query(ParkingSlot).all()
    
    return [
        {
            "id": s.id,
            "number": s.number,
            "floor": s.floor,
            "status": s.status,
            "polygon": s.polygon,
            "polygon_configured": bool(s.polygon_configured),
            "heatmap_count": s.heatmap_count
        }
        for s in slots
    ]

@router.put("/slots/{slot_id}")
def update_slot(slot_id: str, data: dict, db: Session = Depends(get_db)):
    slot = db.query(ParkingSlot).filter(ParkingSlot.id == slot_id).first()
    if not slot:
        return {"error": "Slot not found"}
        
    if "polygon" in data:
        try:
            points = json.loads(data["polygon"])
            # 1. Reorder clockwise
            points = sort_clockwise(points)
            
            # 2. Validation: prevent saving polygons outside parking region (0-1920, 0-1080)
            for p in points:
                if not (0 <= p[0] <= 1920 and 0 <= p[1] <= 1080):
                    return {"error": f"Point {p} is outside valid parking region (1920x1080)"}
            
            slot.polygon = json.dumps(points)
            slot.polygon_configured = 1
        except Exception as e:
            return {"error": f"Invalid polygon data: {str(e)}"}

    if "status" in data:
        slot.status = data["status"]
        manager.sync_broadcast({
            "event": "slot_update",
            "slot_id": slot.id,
            "status": slot.status
        })
        
    db.commit()
    return {"message": "Slot updated successfully"}

@router.delete("/slots/{slot_id}")
def delete_slot(slot_id: str, db: Session = Depends(get_db)):
    slot = db.query(ParkingSlot).filter(ParkingSlot.id == slot_id).first()
    if not slot:
        return {"error": "Slot not found"}
        
    # Reset polygon and state properly
    slot.polygon = None
    slot.polygon_configured = 0
    slot.status = "available"
    slot.occupancy_count = 0
    slot.total_occupied_time = 0.0
    slot.occupied_start_time = None
    db.commit()
    
    manager.sync_broadcast({
        "event": "slot_update",
        "slot_id": slot_id,
        "status": "available"
    })
    return {"message": "Slot polygon reset successfully"}

@router.post("/reseed-slots")
def reseed_slots(db: Session = Depends(get_db)):
    """Reseed slots S1-S7 if entries are missing."""
    count = 0
    for i in range(1, 8):
        s_id = f"S{i}"
        slot = db.query(ParkingSlot).filter(ParkingSlot.id == s_id).first()
        if not slot:
            new_slot = ParkingSlot(
                id=s_id, 
                number=f"S-0{i}", 
                floor="S", 
                status="available", 
                polygon=None,
                polygon_configured=0,
                occupancy_count=0,
                total_occupied_time=0.0,
                occupied_start_time=None
            )
            db.add(new_slot)
            count += 1
    
    db.commit()
    if count > 0:
        manager.sync_broadcast({"event": "reload_slots"})
    return {"message": f"Reseeded {count} missing slots (S1-S7)"}

@router.post("/slots")
def create_slot(data: dict, db: Session = Depends(get_db)):
    new_slot = ParkingSlot(
        id=data.get("id"),
        number=data.get("number"),
        floor=data.get("floor", "S"),
        status=data.get("status", "available"),
        polygon=data.get("polygon", "[]"),
        polygon_configured=1 if data.get("polygon") and data.get("polygon") != "[]" else 0
    )
    db.add(new_slot)
    db.commit()
    manager.sync_broadcast({
        "event": "slot_created",
        "slot_id": new_slot.id,
        "status": new_slot.status
    })
    return {"message": "Slot created successfully"}
