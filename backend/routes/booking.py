from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import ParkingSlot, Booking
from websocket_manager import manager
import datetime

router = APIRouter()

@router.post("/book-slot")
def book_slot(data: dict, db: Session = Depends(get_db)):
    slot = db.query(ParkingSlot).filter(ParkingSlot.id == data.get("slot_id")).first()
    if not slot:
        return {"error": "Slot not found"}
    # Section 5: Booking Validation - Demo Requirement
    if slot.status != "available":
        return {"error": "Slot not available"}
        
    now = datetime.datetime.utcnow()
    expiry = now + datetime.timedelta(minutes=10)
    
    new_booking = Booking(
        name=data.get("name"),
        phone=data.get("phone"),
        vehicle_number=data.get("vehicle_number"),
        slot_id=data.get("slot_id"),
        booking_time=now,
        expiry_time=expiry,
        status="active"
    )
    
    db.add(new_booking)
    slot.status = "reserved"
    db.commit()
    
    manager.sync_broadcast({
        "event": "slot_update",
        "slot_id": slot.id,
        "status": "reserved"
    })
    
    return {"message": "Slot booked successfully"}

@router.post("/cancel-booking/{booking_id}")
def cancel_booking(booking_id: int, db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        return {"error": "Booking not found"}
        
    if booking.status != "active":
        return {"error": "Booking is not active"}
        
    booking.status = "cancelled"
    slot = db.query(ParkingSlot).filter(ParkingSlot.id == booking.slot_id).first()
    
    if slot and slot.status == "reserved":
        slot.status = "available"
        manager.sync_broadcast({
            "event": "slot_update",
            "slot_id": slot.id,
            "status": "available"
        })
        
    db.commit()
    return {"message": "Booking cancelled"}

@router.get("/booking-history")
def booking_history(phone: str, db: Session = Depends(get_db)):
    bookings = db.query(Booking).filter(Booking.phone == phone).all()
    return bookings
