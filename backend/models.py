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
    polygon_version = Column(Integer, default=1)
    last_status_change_at = Column(DateTime, default=datetime.datetime.utcnow)
    occupancy_count = Column(Integer, default=0)
    total_occupied_time = Column(Float, default=0.0) # In seconds
    occupied_start_time = Column(DateTime, nullable=True)
    heatmap_count = Column(Integer, default=0)

class ParkingSession(Base):
    __tablename__ = "parking_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    vehicle_id = Column(String(100))
    slot_id = Column(String(50))
    entry_time = Column(DateTime, default=datetime.datetime.utcnow)
    exit_time = Column(DateTime, nullable=True)
    duration = Column(Float, nullable=True) # In seconds

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
    system_mode = Column(String(50), default="NORMAL") # NORMAL | SAFE_MODE

class SystemEvent(Base):
    __tablename__ = "system_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_type = Column(String(100))
    message = Column(String(500))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    meta_data = Column(String(1000), nullable=True) # JSON string for extra context

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
