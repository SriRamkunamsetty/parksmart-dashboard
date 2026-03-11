import cv2
import numpy as np
from ultralytics import YOLO
import logging
import time
import os
import torch
import threading
from collections import deque
from database import SessionLocal
from models import ParkingSlot, SystemState

# --- Configuration & State ---
frame_lock = threading.Lock()
latest_frame = None
latest_results = None
analysis_running = False
analysis_paused = False
analysis_status = {"status": "idle"}
slot_state_cache = {}  # In-memory cache to avoid DB spam

EXIT_LINE_Y = 380
vehicle_track_y = {}
vehicle_slot_assignment = {}
vehicle_last_seen_frame = {}
slot_detection_buffers = {f"S{i}": deque(maxlen=5) for i in range(1, 8)}
slot_last_seen_time = {f"S{i}": 0.0 for i in range(1, 8)}
slot_first_seen_time = {f"S{i}": 0.0 for i in range(1, 8)}

SLOT_POLYGONS = {
    "S1": np.array([(100, 320), (220, 320), (200, 520), (50, 520)], np.int32).reshape((-1, 1, 2)),
    "S2": np.array([(240, 320), (360, 320), (340, 520), (210, 520)], np.int32).reshape((-1, 1, 2)),
    "S3": np.array([(380, 320), (500, 320), (480, 520), (350, 520)], np.int32).reshape((-1, 1, 2)),
    "S4": np.array([(520, 320), (640, 320), (620, 520), (490, 520)], np.int32).reshape((-1, 1, 2)),
    "S5": np.array([(660, 320), (780, 320), (760, 520), (630, 520)], np.int32).reshape((-1, 1, 2)),
    "S6": np.array([(800, 320), (920, 320), (900, 520), (770, 520)], np.int32).reshape((-1, 1, 2)),
    "S7": np.array([(940, 320), (1060, 320), (1040, 520), (910, 520)], np.int32).reshape((-1, 1, 2)),
}

# --- Utilities ---
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(asctime)s - %(message)s")

def update_system_status(status_str: str):
    db = SessionLocal()
    try:
        state = db.query(SystemState).first()
        if not state:
            state = SystemState(system_status=status_str)
            db.add(state)
        else:
            state.system_status = status_str
        db.commit()
        log_event("system", f"[DB] status updated: {status_str}")
    except Exception as e:
        logging.error(f"Failed to update system state: {e}")
    finally:
        db.close()

def log_event(category, message):
    logging.info(f"[{category.upper()}] {message}")

# --- AI Model Initialization ---
MODEL_PATH = os.path.join("backend", "models", "yolov8n.pt")
try:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    global_model = YOLO(MODEL_PATH).to(device)
    log_event("yolo", f"model loaded on {device}")
    # Warm-up
    dummy = np.zeros((640, 640, 3), dtype=np.uint8)
    global_model.predict(dummy, verbose=False)
except Exception as e:
    global_model = None
    log_event("yolo", f"critical error loading model: {e}")

def get_video_stream():
    global latest_frame
    while True:
        with frame_lock:
            if latest_frame is None:
                frame_to_send = None
            else:
                frame_to_send = latest_frame.copy()
        
        if frame_to_send is None:
            time.sleep(0.1)
            continue
            
        ret, buffer = cv2.imencode('.jpg', frame_to_send)
        if not ret: continue
            
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        time.sleep(0.04)

def process_video(video_path: str):
    global analysis_status, latest_frame, analysis_running, latest_results, slot_state_cache
    
    if analysis_running: return
    analysis_running = True
    update_system_status("processing")
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        log_event("stream", f"failed to open: {video_path}")
        analysis_running = False
        return

    frame_count = 0
    try:
        while analysis_running:
            if analysis_paused:
                time.sleep(0.5)
                continue
                
            ret, frame = cap.read()
            if not ret:
                log_event("job", "video ended. processing complete.")
                break
                
            # Resize once at capture scale
            frame = cv2.resize(frame, (960, 540))
            frame_count += 1
            
            # 1. YOLO Inference
            if frame_count % 3 == 0:
                if global_model:
                    results = global_model.track(frame, persist=True, tracker="bytetrack.yaml", conf=0.4, verbose=False)
                    latest_results = results
                
                detected_vehicles = []
                if latest_results:
                    for r in latest_results:
                        for box in r.boxes:
                            cls_id = int(box.cls[0])
                            track_id = int(box.id[0]) if box.id is not None else -1
                            if cls_id in [2, 3, 5, 7]: # car, motorcycle, bus, truck
                                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                                cx, cy = int((x1+x2)/2), int((y1+y2)/2)
                                detected_vehicles.append((cx, cy, track_id, (x1,y1,x2,y2)))
                                if track_id != -1:
                                    vehicle_track_y[track_id] = cy
                                    vehicle_last_seen_frame[track_id] = frame_count

                # 2. Cleanup Stale Vehicles
                stale_ids = [tid for tid, last in vehicle_last_seen_frame.items() if (frame_count - last) > 50]
                for tid in stale_ids:
                    vehicle_track_y.pop(tid, None)
                    vehicle_last_seen_frame.pop(tid, None)
                    vehicle_slot_assignment.pop(tid, None)

                # 3. Slot Occupancy Logic
                db = SessionLocal()
                try:
                    slots = db.query(ParkingSlot).all()
                    db_changed = False
                    for slot in slots:
                        # Normalize ID for lookup
                        norm_id = slot.id.split("(")[0].strip()
                        if not norm_id.startswith("S"):
                            slot_key = f"S{norm_id}"
                        else:
                            slot_key = norm_id
                            
                        # Try to use the shared Slot Service if available or local polygons
                        poly = SLOT_POLYGONS.get(slot_key)
                        if poly is None: continue

                        # ... evaluation logic ...
                        slot_x, slot_y, slot_w, slot_h = cv2.boundingRect(poly)
                        vehicle_in_poly = False
                        best_overlap = 0.0
                        
                        for (cx, cy, tid, (vx1, vy1, vx2, vy2)) in detected_vehicles:
                            # Intersection area
                            ix1, iy1 = max(vx1, slot_x), max(vy1, slot_y)
                            ix2, iy2 = min(vx2, slot_x + slot_w), min(vy2, slot_y + slot_h)
                            
                            if ix1 < ix2 and iy1 < iy2:
                                intersection = (ix2-ix1)*(iy2-iy1)
                                overlap_ratio = intersection / cv2.contourArea(poly)
                                if overlap_ratio > best_overlap:
                                    best_overlap = overlap_ratio
                                    
                                if overlap_ratio > 0.3:
                                    vehicle_in_poly = True; break

                        slot_detection_buffers[slot_key].append(1 if vehicle_in_poly else 0)
                        if len(slot_detection_buffers[slot_key]) >= 5:
                            recent = sum(slot_detection_buffers[slot_key])
                            new_status = "occupied" if recent >= 3 else "available"
                            
                            if slot.status != new_status:
                                log_event("slot", f"[DETECTION] {slot_key} change: {slot.status} -> {new_status}")
                                slot.status = new_status
                                db_changed = True
                        
                        slot_state_cache[slot_key] = slot.status

                    if db_changed: db.commit()
                except Exception as e:
                    log_event("job", f"Slot evaluation error: {e}")
                finally:
                    db.close()

            # 4. UI Drawing
            from utils.frame_utils import draw_detection_overlay
            from services.slot_service import slot_service
            
            # Prepare detections for the shared drawing utility
            drawing_detections = []
            if latest_results:
                for r in latest_results:
                    for box in r.boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                        cx, cy = int((x1+x2)/2), int((y1+y2)/2)
                        tid = int(box.id[0]) if box.id is not None else "?"
                        drawing_detections.append({"bbox": (x1,y1,x2,y2), "centroid": (cx,cy), "track_id": tid})

            draw_frame = draw_detection_overlay(frame, drawing_detections, slot_service.slot_cache.values())

            with frame_lock:
                latest_frame = draw_frame
            time.sleep(0.01)

    except Exception as e:
        log_event("job", f"processing error: {e}")
    finally:
        cap.release()
        analysis_running = False
        update_system_status("idle")
        log_event("job", "analysis thread terminated")
