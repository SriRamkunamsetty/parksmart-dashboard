from apscheduler.schedulers.background import BackgroundScheduler
import datetime
import logging
from database import SessionLocal
from models import Booking, ParkingSlot
from websocket_manager import manager

logging.basicConfig(level=logging.INFO)

def expire_bookings():
    db = SessionLocal()
    try:
        now = datetime.datetime.utcnow()
        expired_bookings = db.query(Booking).filter(
            Booking.status == "active",
            Booking.expiry_time < now
        ).all()
        
        for booking in expired_bookings:
            booking.status = "expired"
            logging.info(f"Booking {booking.id} has expired.")
            
            slot = db.query(ParkingSlot).filter(ParkingSlot.id == booking.slot_id).first()
            if slot and slot.status == "reserved":
                slot.status = "available"
                logging.info(f"Slot {slot.id} is now available again.")
                manager.sync_broadcast({
                    "event": "slot_update",
                    "slot_id": slot.id,
                    "status": "available"
                })
                
        if expired_bookings:
            db.commit()
    except Exception as e:
        logging.error(f"Error in expire_bookings: {e}")
    finally:
        db.close()

scheduler = BackgroundScheduler()
scheduler.add_job(expire_bookings, "interval", seconds=30)
