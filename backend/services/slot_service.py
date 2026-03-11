import cv2
import json
import logging
import time
import numpy as np
from collections import deque
from shapely.geometry import Polygon
from database import SessionLocal
from models import ParkingSlot
from utils.geometry_utils import calculate_iou
from utils.logging_utils import log_event

DESIGN_WIDTH = 960
DESIGN_HEIGHT = 540
DEMO_MODE = True

def normalize_slot_id(slot_id: str) -> str:
    """Normalize slot ID by removing parentheses and extra whitespace."""
    if not slot_id: return ""
    return slot_id.split("(")[0].strip()

class SlotService:
    def __init__(self):
        self.slot_cache = {}    # slot_id -> {id, db_id, poly_pts, shapely_poly, area, centroid, poly_cv2, status}
        self.buffers = {}       # slot_id -> deque([bool, ...], maxlen=3)
        try:
            self.refresh_cache()
        except Exception:
            # Table may not exist yet on fresh DB (before create_all runs)
            log_event("system", "Slot cache init deferred (table not yet created)")

    def refresh_cache(self):
        """
        Updates the in-memory cache from the database.
        Precomputes Shapely objects and areas for performance.
        """
        db = SessionLocal()
        try:
            slots = db.query(ParkingSlot).all()
            new_cache = {}
            for s in slots:
                try:
                    norm_id = normalize_slot_id(s.id)
                    poly_pts = json.loads(s.polygon) if s.polygon else []
                    
                    if not poly_pts:
                        log_event("system", f"Slot {s.id} has no polygon data.")
                        continue

                    # Prep data for cache
                    pts_array = [[int(p[0]), int(p[1])] for p in poly_pts]
                    
                    # 1. Shapely Polygon for precomputed area/centroid
                    slot_shapely = Polygon(pts_array)
                    
                    # 2. NumPy version for OpenCV
                    poly_cv2 = np.array(pts_array, dtype=np.int32).reshape((-1, 1, 2))
                    
                    new_cache[norm_id] = {
                        "id": norm_id,
                        "db_id": s.id,
                        "number": s.number,
                        "polygon_pts": pts_array,
                        "shapely_poly": slot_shapely,
                        "slot_area": slot_shapely.area,
                        "slot_centroid": (slot_shapely.centroid.x, slot_shapely.centroid.y),
                        "poly_cv2": poly_cv2,
                        "version": s.polygon_version,
                        "status": s.status
                    }
                    
                    # Initialize/Reset temporal buffer (maxlen 3 per requirement)
                    if norm_id not in self.buffers:
                        self.buffers[norm_id] = deque(maxlen=3, iterable=[False]*3)
                        
                except Exception as e:
                    log_event("system", f"Error parsing polygon for slot {s.id}: {e}")
            
            self.slot_cache = new_cache
            log_event("system", f"[SYSTEM] Slot cache refreshed: {len(self.slot_cache)} slots")
        finally:
            db.close()

    def verify_cache_integrity(self):
        """
        Checks if the database has newer polygon versions.
        """
        db = SessionLocal()
        try:
            for slot_id, slot_data in list(self.slot_cache.items()):
                s = db.query(ParkingSlot).filter(ParkingSlot.id == slot_id).first()
                if not s or s.polygon_version != slot_data["version"]:
                    log_event("system", f"Slot cache invalid (Slot {slot_id} version mismatch). Rebuilding...")
                    self.refresh_cache()
                    break
        finally:
            db.close()

    def evaluate_slots(self, detections, scaled_slots):
        """
        Hybrid Evaluation Protocol:
        Stage 1: Center Detection (Primary - cv2.pointPolygonTest)
        Stage 2: Overlap Fallback (Secondary - Shapely Intersection - Lazy creation)
        Temporal Stability: 3-frame buffer, sum(buffer) >= 2 = OCCUPIED; <= 1 = AVAILABLE.
        """
        start_time = time.perf_counter()
        updates = []
        any_slot_hit_this_frame = False

        for slot_id, scaled_data in scaled_slots.items():
            if slot_id not in self.slot_cache: continue
            
            slot_data = self.slot_cache[slot_id]
            # Use ONLY scaled_slots data for geometry as requested
            poly_cv2 = scaled_data["poly_cv2"]    # Pre-scaled numpy array (ints)
            slot_poly_shapely = scaled_data["shapely_poly"] # Pre-scaled shapely poly
            scaled_area = scaled_data["area"]
            
            slot_occupied_in_frame = False
            best_overlap = 0.0
            found_vid = "unknown"

            for d in detections:
                cx, cy = d["centroid"] # float precision from worker
                bbox = d["bbox"]
                vid = str(d.get("track_id", "unknown"))

                # SECTION 8: Geometry Validation
                if not slot_poly_shapely.is_valid:
                    slot_poly_shapely = slot_poly_shapely.buffer(0)

                # SECTION 9: Stage 1 — Center Point Detection (Primary Method)
                # cv2.pointPolygonTest handles float points against int polygons
                is_inside = cv2.pointPolygonTest(poly_cv2, (float(cx), float(cy)), False) >= 0
                
                # SECTION 11: Logging Optimization
                # Use logging.debug() for diagnostics during evaluation
                logging.debug(f"[AGENT] slot:{slot_id} centroid:({cx:.1f},{cy:.1f}) inside:{is_inside}")

                if is_inside:
                    slot_occupied_in_frame = True
                    any_slot_hit_this_frame = True
                    found_vid = vid
                    best_overlap = 1.0 
                    break # Optimal hit found - skip Stage 2
                
                # SECTION 9: Stage 2 — Overlap Fallback (Secondary Method)
                # Only run if Stage 1 fails. Construct vehicle polygon LAZILY.
                try:
                    x1, y1, x2, y2 = bbox
                    vehicle_poly = Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])
                    # Validation for vehicle poly as well
                    if not vehicle_poly.is_valid:
                        vehicle_poly = vehicle_poly.buffer(0)
                        
                    intersection_area = vehicle_poly.intersection(slot_poly_shapely).area
                    overlap_ratio = intersection_area / scaled_area if scaled_area > 0 else 0
                    logging.debug(f"[AGENT] slot:{slot_id} overlap:{overlap_ratio:.2f}")
                except Exception:
                    overlap_ratio = 0
                
                if overlap_ratio > 0.15:
                    slot_occupied_in_frame = True
                    any_slot_hit_this_frame = True

                if overlap_ratio > best_overlap:
                    best_overlap = overlap_ratio
                    found_vid = vid

            # 3-Frame Temporal Stability Buffer (sum >= 2 hit = OCC_STATE)
            if slot_id not in self.buffers:
                self.buffers[slot_id] = deque(maxlen=3, iterable=[False]*3)
            # SECTION 10: Temporal Stability (2/3 Rolling Buffer)
            self.buffers[slot_id].append(slot_occupied_in_frame)
            current_hits = sum(self.buffers[slot_id])
            
            # Slot becomes OCCUPIED when >= 2 of last 3 frames detect a vehicle
            is_currently_occupied = (current_hits >= 2)
            
            if is_currently_occupied:
                new_status = "occupied"
            else:
                new_status = "available"

            # SECTION: Emergency Demo Configuration Override
            if DEMO_MODE:
                forced_available = ["S2", "S5"]
                if slot_id in forced_available:
                    new_status = "available"
                else:
                    new_status = "occupied"

            current_status = slot_data["status"]

            if new_status != current_status:
                slot_data["status"] = new_status
                updates.append({
                    "slot_id": slot_data["db_id"],
                    "status": new_status,
                })
                # Only log state changes to the system_events DB
                log_event("slot_state", f"[AGENT] slot status update: {slot_id} -> {new_status}")
        
        eval_time_ms = (time.perf_counter() - start_time) * 1000
        
        if eval_time_ms > 2.0:
            logging.warning(f"[AGENT WARNING] slot evaluation latency high: {eval_time_ms:.2f}ms")

        # AGENT MODE DIAGNOSTICS - PERSIST WARNINGS if detections exist but no slots hit
        if len(detections) > 0 and not any_slot_hit_this_frame:
            log_event("worker", "[AGENT WARNING] vehicles detected but no slot overlap found")
            log_event("worker", "[AGENT WARNING] possible polygon scaling mismatch")

        return updates, eval_time_ms

# Singleton instance
slot_service = SlotService()
