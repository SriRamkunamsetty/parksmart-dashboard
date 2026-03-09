from sqlalchemy import Column, String, Integer, DateTime, Float
from database import Base
import datetime

class ParkingSlot(Base):
    __tablename__ = "parking_slots"

    id = Column(String(50), primary_key=True, index=True)
    number = Column(String(50))
    floor = Column(String(50))
    status = Column(String(50), default="available")
    polygon = Column(String(500), default="[]")
    polygon_configured = Column(Integer, default=0) # Using Integer as boolean for SQLite compatibility
    heatmap_count = Column(Integer, default=0)

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100))
    phone = Column(String(20))
    vehicle_number = Column(String(50))
    slot_id = Column(String(50))
    booking_time = Column(DateTime, default=datetime.datetime.utcnow)
    expiry_time = Column(DateTime)
    status = Column(String(50), default="active")

class SystemState(Base):
    __tablename__ = "system_state"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    system_status = Column(String(50), default="idle")

class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(String(100), unique=True, index=True)
    video_name = Column(String(255))
    video_path = Column(String(500))
    video_codec = Column(String(50))
    video_width = Column(Integer)
    video_height = Column(Integer)
    total_frames = Column(Integer, default=0)
    processed_frames = Column(Integer, default=0)
    progress_percentage = Column(Float, default=0.0)
    fps = Column(Float, default=0.0)
    duration_seconds = Column(Float, default=0.0)
    status = Column(String(50), default="processing")  # processing, paused, completed, error, cancelled
    error_message = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
