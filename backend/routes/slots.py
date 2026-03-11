import math
import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import ParkingSlot, SlotGeometryHistory, SystemEvent
from websocket_manager import manager
from datetime import datetime
from config import START_TIME
import time
from utils.logging_utils import log_event
from services.slot_service import slot_service

router = APIRouter(prefix="/api/slots", tags=["slots"])

def sort_clockwise(points):
    """Sort points in clockwise order."""
    if not points:
        return []
    # Calculate centroid
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    # Sort by angle from centroid
    return sorted(points, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))

@router.get("")
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
            "heatmap_count": s.heatmap_count,
            "last_updated": s.last_status_change_at.isoformat() if s.last_status_change_at else None
        }
        for s in slots
    ]

@router.put("/{slot_id}")
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
            slot.polygon_version = (slot.polygon_version or 0) + 1
            
            # Track History
            from models import SlotGeometryHistory
            history = SlotGeometryHistory(
                slot_id=slot.id,
                polygon=slot.polygon,
                version=slot.polygon_version
            )
            db.add(history)
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
    slot_service.refresh_cache()
    return {"message": "Slot updated successfully"}

@router.delete("/{slot_id}")
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
    slot_service.refresh_cache()
    return {"message": "Slot polygon reset successfully"}

@router.post("/reseed")
def reseed_slots(db: Session = Depends(get_db)):
    """Reseed slots S1-S7 and reset all existing slots to available in a single transaction."""
    try:
        # 1. Reset all existing slots
        all_slots = db.query(ParkingSlot).all()
        for s in all_slots:
            s.polygon = None
            s.polygon_configured = 0
            s.status = "available"
            s.occupancy_count = 0
            s.total_occupied_time = 0.0
            s.occupied_start_time = None
            s.heatmap_count = 0
        
        # 2. Ensure S1-S7 exist
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
                    occupied_start_time=None,
                    heatmap_count=0
                )
                db.add(new_slot)
                
                # Track Initial History
                from models import SlotGeometryHistory
                history = SlotGeometryHistory(
                    slot_id=s_id,
                    polygon=None,
                    version=1
                )
                db.add(history)
        
        db.commit()
        slot_service.refresh_cache()
        
        # Reload all slots in memory if they changed
        manager.sync_broadcast({"event": "reload_slots"})
        
        return {
            "message": "Slots reseeded",
            "slot_count": db.query(ParkingSlot).count()
        }
    except Exception as e:
        db.rollback()
        raise e

@router.post("")
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
    slot_service.refresh_cache()
    manager.sync_broadcast({
        "event": "slot_created",
        "slot_id": new_slot.id,
        "status": new_slot.status
    })
    return {"message": "Slot created successfully"}

@router.get("/stats")
def get_slot_stats(db: Session = Depends(get_db)):
    total = db.query(ParkingSlot).count()
    available = db.query(ParkingSlot).filter(ParkingSlot.status == "available").count()
    occupied = db.query(ParkingSlot).filter(ParkingSlot.status == "occupied").count()
    reserved = db.query(ParkingSlot).filter(ParkingSlot.status == "reserved").count()
    
    return {
        "total_slots": total,
        "available": available,
        "occupied": occupied,
        "reserved": reserved
    }

@router.get("/live")
def get_slots_live(db: Session = Depends(get_db)):
    """Live status API with slot occupancy details."""
    slots = db.query(ParkingSlot).all()
    result = []
    for s in slots:
        session = db.query(ParkingSession).filter(
            ParkingSession.slot_id == s.id,
            ParkingSession.exit_time == None
        ).first()
        
        vehicle_id = session.vehicle_id if session else None
        session_duration = (datetime.utcnow() - session.entry_time).total_seconds() if session else 0
        
        uptime = (datetime.utcnow() - START_TIME).total_seconds()
        rate = min(1.0, s.total_occupied_time / uptime) if uptime > 0 else 0
        
        result.append({
            "slot_id": s.id,
            "status": s.status,
            "vehicle_id": vehicle_id,
            "session_duration_sec": round(session_duration, 2),
            "occupancy_rate": round(rate, 2),
            "last_updated": s.last_status_change_at.isoformat() if s.last_status_change_at else None
        })
    return result

@router.get("/heatmap")
def get_slots_heatmap(db: Session = Depends(get_db)):
    slots = db.query(ParkingSlot).all()
    result = []
    for s in slots:
        uptime = (datetime.utcnow() - START_TIME).total_seconds()
        rate = min(1.0, s.total_occupied_time / uptime) if uptime > 0 else 0
        avg_duration = s.total_occupied_time / s.occupancy_count if (s.occupancy_count and s.occupancy_count > 0) else 0
        result.append({
            "slot_id": s.id,
            "occupancy_rate": round(rate, 2),
            "average_duration_sec": round(avg_duration, 2)
        })
    return result
