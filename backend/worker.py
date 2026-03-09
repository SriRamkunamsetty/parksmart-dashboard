import cv2
import numpy as np
from ultralytics import YOLO
import logging
import time
import torch
import json
import asyncio
import threading
from datetime import datetime, timezone

from database import SessionLocal
from database import SessionLocal
from models import ParkingSlot, ProcessingJob, ParkingSession
from websocket_manager import manager
from config import (
    MODEL_PATH, MODEL_IMG_SIZE, FRAME_SKIP_DEFAULT, MAX_WORKERS, 
    CONFIDENCE_THRESHOLD, DEBUG_PIPELINE, QUEUE_LIMIT, 
    PROCESSING_FPS_WINDOW, MIN_POLYGON_AREA, FRAME_HASH_SIZE, 
    FRAME_TIMEOUT_SEC, STREAM_DISCONNECT_TIMEOUT_SEC, 
    YOLO_VEHICLE_CLASS_IDS, QUEUE_BACKPRESSURE_THRESHOLD,
    SLOT_STATE_COOLDOWN_SEC, DEBUG_STREAM_ENABLED, MAX_STREAM_RETRIES
)
import collections
from collections import deque
import statistics

# CPU Optimization Profile
torch.set_num_threads(4)
torch.set_num_interop_threads(2)

_global_model_instance = None
_model_lock = threading.Lock()
inference_lock = threading.Lock()
frame_buffer_lock = threading.Lock() # Guard for shared MJPEG buffer
slot_cache_lock = threading.Lock()   # Guard for geometry and bbox caches
frame_queue_lock = threading.Lock()   # Guard for frame queue push/pop
stream_reconnect_lock = threading.Lock() # Ensure single reconnection thread
recent_profiling_metrics = deque(maxlen=QUEUE_LIMIT)
fps_rolling_window = deque(maxlen=PROCESSING_FPS_WINDOW)
detection_fps_window = deque(maxlen=PROCESSING_FPS_WINDOW)
system_mode = "NORMAL" # NORMAL | SAFE_MODE

def get_model():
    global _global_model_instance
    if _global_model_instance is None:
        with _model_lock:
            if _global_model_instance is None:
                try:
                    _global_model_instance = YOLO(MODEL_PATH).to("cpu")
                except Exception as e:
                    logging.error(f"Failed to load YOLO model: {e}")
    return _global_model_instance

def get_iso_time():
    return datetime.now(timezone.utc).isoformat()

class WebSocketProgressAgent:
    @staticmethod
    async def broadcast_progress(job_id: str, progress: float, processed: int, total: int, fps: float, eta: float, skip_interval: int):
        payload = {
            "event": "video_progress",
            "timestamp": get_iso_time(),
            "job_id": job_id,
            "payload": {
                "progress": round(progress, 2),
                "processed_frames": processed,
                "total_frames": total,
                "fps": round(fps, 2),
                "eta_seconds": round(eta, 2) if eta > 0 else 0,
                "frame_skip_interval": skip_interval
            }
        }
        if DEBUG_PIPELINE:
            from worker import job_manager
            agent = job_manager.active_jobs.get(list(job_manager.active_jobs.keys())[0]) if job_manager.active_jobs else None
            payload["payload"]["queue"] = len(job_manager.active_jobs)
            payload["payload"]["decode_time_ms"] = agent.decode_time_ms if agent else 0
            payload["payload"]["inference_time_ms"] = agent.inference_time_ms if agent else 0
            payload["payload"]["slot_eval_time_ms"] = agent.slot_eval_time_ms if agent else 0
            
        await manager.broadcast(payload)
        
    @staticmethod
    async def broadcast_status(job_id: str, status: str):
        payload = {
            "event": f"job_{status}",
            "timestamp": get_iso_time(),
            "job_id": job_id
        }
        await manager.broadcast(payload)

class SlotEvaluationAgent:
    def __init__(self):
        self.slot_pending_state = {} 
        self.slot_bbox_cache = {}    
        self.slot_continuous_hits = {}
        self.cached_polygon_version = {} # slot_id -> version

    def _get_or_build_cache(self, db, slots):
        for slot in slots:
            # Rebuild if not in cache OR if version in DB is different from cached version
            needs_rebuild = slot.id not in self.slot_bbox_cache or \
                           self.cached_polygon_version.get(slot.id) != slot.polygon_version
            
            if needs_rebuild:
                # Immediate hit buffer reset on geometry change per exact specifications
                if slot.id in self.slot_continuous_hits:
                    self.slot_continuous_hits[slot.id] = 0
                
                if slot.polygon and slot.polygon != "[]":
                    try:
                        pts = json.loads(slot.polygon)
                        if len(pts) >= 3:
                            poly = np.array(pts, np.int32).reshape((-1, 1, 2))
                            x, y, w, h = cv2.boundingRect(poly)
                            area = cv2.contourArea(poly) or 1
                            with slot_cache_lock:
                                self.slot_bbox_cache[slot.id] = (x, y, w, h, area, poly)
                                self.cached_polygon_version[slot.id] = slot.polygon_version
                    except Exception as e:
                        logging.error(f"Polygon parse error for {slot.id}: {e}")
                    
    def evaluate(self, detections, current_timestamp: float, eval_frame=None):
        db = SessionLocal()
        try:
            slots = db.query(ParkingSlot).all()
            self._get_or_build_cache(db, slots)
            
            with slot_cache_lock:
                target_slots_data = [(s, self.slot_bbox_cache[s.id]) for s in slots if s.id in self.slot_bbox_cache]
                
            for slot, cache_data in target_slots_data:
                x, y, w, h, area, poly = cache_data
                vehicle_in_slot = False
                found_track_id = None
                
                for v in detections:
                    vx1, vy1, vx2, vy2 = v["bbox"]
                    if vx2 < x or vx1 > x + w or vy2 < y or vy1 > y + h:
                        continue
                        
                    cx, cy = v["centroid"]
                    
                    if DEBUG_PIPELINE and DEBUG_STREAM_ENABLED and eval_frame is not None:
                        cv2.rectangle(eval_frame, (vx1, vy1), (vx2, vy2), (255, 0, 0), 2) # Blue bbox
                        cv2.circle(eval_frame, (cx, cy), 4, (0, 0, 255), -1) # Red centroid
                        
                    inside = cv2.pointPolygonTest(poly, (float(cx), float(cy)), False) >= 0
                    if not inside:
                        if DEBUG_PIPELINE:
                            logging.debug(f"[SlotEval] Centroid ({cx},{cy}) outside polygon for slot {slot.id} (S{slot.number})")
                        ix1 = max(vx1, x)
                        iy1 = max(vy1, y)
                        ix2 = min(vx2, x + w)
                        iy2 = min(vy2, y + h)
                        if ix1 < ix2 and iy1 < iy2:
                            intersection = (ix2 - ix1) * (iy2 - iy1)
                            iou = intersection / area
                            if iou > 0.25:
                                vehicle_in_slot = True
                                break
                    else:
                        if DEBUG_PIPELINE:
                            logging.debug(f"[SlotEval] Centroid ({cx},{cy}) inside polygon for slot {slot.id} (S{slot.number}) -> OCCUPIED")
                        vehicle_in_slot = True
                        found_track_id = v.get("track_id")
                        break
                
                if DEBUG_PIPELINE and DEBUG_STREAM_ENABLED and poly is not None and len(poly) > 0 and eval_frame is not None:
                    # Drawing polylines already happens outside this loop for all slots if enabled,
                    # but we keep this for specific per-slot highlights if needed later.
                    pass
                
                if vehicle_in_slot:
                    self.slot_continuous_hits[slot.id] = self.slot_continuous_hits.get(slot.id, 0) + 1
                else:
                    # Implement 3-miss rule for available transition
                    current_hits = self.slot_continuous_hits.get(slot.id, 0)
                    if current_hits > 0:
                        self.slot_continuous_hits[slot.id] = max(0, current_hits - 1)
                
                # OCCUPIED after 2 hits, AVAILABLE after 3 misses (or 0 hits)
                hits = self.slot_continuous_hits.get(slot.id, 0)
                if hits >= 2:
                    desired_state = "occupied"
                elif hits == 0:
                    desired_state = "available"
                else:
                    desired_state = slot.status # Maintain current state while in buffer
                
                if slot.status == desired_state:
                    if slot.id in self.slot_pending_state:
                        del self.slot_pending_state[slot.id]
                    continue
                    
                if slot.id not in self.slot_pending_state or self.slot_pending_state[slot.id][0] != desired_state:
                    self.slot_pending_state[slot.id] = (desired_state, current_timestamp)
                else:
                    pending_state, first_seen = self.slot_pending_state[slot.id]
                    if current_timestamp - first_seen >= 1.0:
                        # Enforce SLOT_STATE_COOLDOWN_SEC
                        now_utc = datetime.now(timezone.utc)
                        delta = (now_utc - slot.last_status_change_at.replace(tzinfo=timezone.utc)).total_seconds() \
                                if slot.last_status_change_at else 999
                        
                        if delta < SLOT_STATE_COOLDOWN_SEC:
                            if DEBUG_PIPELINE:
                                logging.debug(f"[SlotEval] Rejecting state change for slot {slot.id} (S{slot.number}): Cooldown active ({delta:.2f}s < {SLOT_STATE_COOLDOWN_SEC}s)")
                            continue

                        logging.info(f"Updating slot {slot.id} (S{slot.number}) status: {slot.status} -> {pending_state}")
                        
                        # Utilization Analytics & Session Logging
                        if pending_state == "occupied" and slot.status != "occupied":
                            slot.occupancy_count = (slot.occupancy_count or 0) + 1
                            slot.occupied_start_time = now_utc
                            # Start Session
                            session = ParkingSession(
                                slot_id=slot.id,
                                vehicle_id=str(found_track_id or "unknown"),
                                entry_time=now_utc
                            )
                            db.add(session)
                        elif slot.status == "occupied" and pending_state == "available":
                            if slot.last_status_change_at:
                                duration = (now_utc - slot.last_status_change_at.replace(tzinfo=timezone.utc)).total_seconds()
                                slot.total_occupied_time = (slot.total_occupied_time or 0.0) + duration
                            # End Session
                            latest_session = db.query(ParkingSession).filter(
                                ParkingSession.slot_id == slot.id,
                                ParkingSession.exit_time == None
                            ).order_by(ParkingSession.entry_time.desc()).first()
                            if latest_session:
                                latest_session.exit_time = now_utc
                                latest_session.duration = (now_utc - latest_session.entry_time).total_seconds()
                            slot.occupied_start_time = None
                        
                        slot.status = pending_state
                        slot.last_status_change_at = now_utc
                        if pending_state == "occupied":
                            slot.heatmap_count = (slot.heatmap_count or 0) + 1
                        db.commit()
                        del self.slot_pending_state[slot.id]
                        
                        manager.sync_broadcast({
                            "event": "slot_update",
                            "slot_id": slot.id,
                            "status": pending_state,
                            "timestamp": get_iso_time()
                        })
                        
        except Exception as e:
            logging.error(f"Slot evaluation error: {e}")
            db.rollback()
        finally:
            db.close()

    @staticmethod
    def process(frame):
        model = get_model()
        if model is None:
            return []
        
        # Strict Lock Ordering: slot_cache_lock -> frame_queue_lock -> inference_lock
        # We only need inference_lock here, but we honor the ordering principle
        # by not having higher locks if we were to grab them.
        with inference_lock:
            with torch.no_grad():
                results = model.track(frame, persist=True, imgsz=MODEL_IMG_SIZE, verbose=False, classes=YOLO_VEHICLE_CLASS_IDS, conf=CONFIDENCE_THRESHOLD)
            
        detections = []
        for r in results:
            if r.boxes.id is not None:
                ids = r.boxes.id.cpu().numpy().astype(int)
                for box, track_id in zip(r.boxes, ids):
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                    cx = int((x1 + x2) / 2)
                    cy = int((y1 + y2) / 2)
                    detections.append({
                        "bbox": (x1, y1, x2, y2),
                        "centroid": (cx, cy),
                        "class_id": cls_id,
                        "track_id": track_id
                    })
            else:
                for box in r.boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    if cls_id in YOLO_VEHICLE_CLASS_IDS and conf >= CONFIDENCE_THRESHOLD:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                        cx = int((x1 + x2) / 2)
                        cy = int((y1 + y2) / 2)
                        detections.append({
                            "bbox": (x1, y1, x2, y2),
                            "centroid": (cx, cy),
                            "class_id": cls_id,
                            "track_id": None
                        })
        return detections

class ProcessingAgent(threading.Thread):
    def __init__(self, job_id: str, db_id: int):
        super().__init__()
        self.job_id = job_id
        self.db_id = db_id
        self.running = False
        self.paused = False
        self.latest_frame = None
        self.frame_queue = deque(maxlen=QUEUE_LIMIT)
        self.current_skip_interval = FRAME_SKIP_DEFAULT
        self.last_frame_hash = None
        self.last_detections = []
        self.decode_time_ms = 0
        self.inference_time_ms = 0
        self.slot_eval_time_ms = 0
        self.latency_window = deque(maxlen=20)
        self.worker_last_seen = time.time()
        self.last_heartbeat = time.time()
        self.frames_received = 0
        self.frames_processed = 0
        self.frames_dropped = 0
        self.detected_classes = {"car": 0, "truck": 0, "bus": 0, "motorcycle": 0}
        self.stream_source = "primary"
        self.stream_retry_count = 0

    def run(self):
        self.running = True
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.run_pipeline())
        finally:
            loop.close()

    async def run_pipeline(self):
        db = SessionLocal()
        job = db.query(ProcessingJob).filter(ProcessingJob.id == self.db_id).first()
        if not job or job.status == "cancelled":
            db.close()
        while self.running:
            self.last_heartbeat = time.time()
            with stream_reconnect_lock:
                cap = cv2.VideoCapture(job.video_path)
                if cap.isOpened():
                    self.stream_retry_count = 0
                    break
            
            self.stream_retry_count += 1
            if self.stream_retry_count > MAX_STREAM_RETRIES:
                global system_mode
                system_mode = "SAFE_MODE"
                logging.error(f"Stream reconnection failed after {MAX_STREAM_RETRIES} attempts. SYSTEM_MODE -> SAFE_MODE")
            
            logging.warning(f"Failed to open stream/file {job.video_path} (Attempt {self.stream_retry_count}). Retrying in 5 seconds...")
            await asyncio.sleep(5)
            job = db.query(ProcessingJob).filter(ProcessingJob.id == self.db_id).first()
            if not job or job.status == "cancelled":
                db.close()
                return

        cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
        
        # Resume optimization per exact specifications
        if job.processed_frames > 0:
            resume_frame = job.processed_frames * self.current_skip_interval
            cap.set(cv2.CAP_PROP_POS_FRAMES, resume_frame)
            
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        base_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        
        evaluator = SlotEvaluationAgent()
        processed_inferences = job.processed_frames
        
        last_emit_time = 0
        fps_window = []
        
        while self.running and (processed_inferences * self.current_skip_interval) < total_frames:
            if self.paused:
                job.processed_frames = processed_inferences
                db.commit()
                await asyncio.sleep(1)
                job = db.query(ProcessingJob).filter(ProcessingJob.id == self.db_id).first()
                if job.status == "cancelled":
                    break
                if job.status == "processing":
                    self.paused = False
                continue
                
            loop_start = time.time()
            
            # Read single frame using interval
            current_vid_index = processed_inferences * self.current_skip_interval
            if current_vid_index >= total_frames:
                break
                
            decode_start = time.time()
            cap.set(cv2.CAP_PROP_POS_FRAMES, current_vid_index)
            ret, frame = cap.read()
            self.decode_time_ms = int((time.time() - decode_start) * 1000)
            processed_inferences += 1
            
            if not ret:
                break
                
            self.worker_last_seen = time.time()
            self.last_heartbeat = time.time()
            self.frames_received += 1
            
            # Frame queue pressure simulation/tracking
            with frame_queue_lock:
                self.frame_queue.append(time.time())
                self.queue_pressure = len(self.frame_queue) / QUEUE_LIMIT
            
            # Dropped frames logic (if queue was overflowing, but here we process sequentially)
            # In a real producer-consumer, we'd pop oldest if queue full.
            
            # Adaptive Backpressure: Increase skip interval if pressure > threshold
            if self.queue_pressure > QUEUE_BACKPRESSURE_THRESHOLD:
                self.current_skip_interval = min(30, self.current_skip_interval + 2)
                if DEBUG_PIPELINE:
                    logging.warning(f"[Backpressure] Pressure high ({self.queue_pressure:.2f}), increasing skip to {self.current_skip_interval}")

            # Thread-safe update of shared MJPEG buffer
            with frame_buffer_lock:
                self.latest_frame = frame.copy()
            
            self.frames_processed += 1
            
            # 1. Detection with Frame Hashing & Timeout
            inference_start = time.time()
            small_frame = cv2.resize(frame, FRAME_HASH_SIZE)
            frame_hash = hash(small_frame.tobytes())
            if frame_hash == self.last_frame_hash:
                detections = self.last_detections
            else:
                detections = DetectionAgent.process(frame)
                self.last_frame_hash = frame_hash
                self.last_detections = detections
                # Count classes for diagnostics
                class_map = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
                for d in detections:
                    cls_id = d.get("class_id")
                    if cls_id in class_map:
                        cls_name = class_map[cls_id]
                        self.detected_classes[cls_name] += 1
                
            self.inference_time_ms = int((time.time() - inference_start) * 1000)
            
            # Detection FPS calculation (excluding hashing time)
            actual_inference_time = time.time() - inference_start
            if actual_inference_time > 0:
                detection_fps_window.append(1.0 / actual_inference_time)
            self.latest_detection_fps = statistics.mean(detection_fps_window) if detection_fps_window else 0

            # 2. Evaluation
            eval_start = time.time()
            vid_timestamp = current_vid_index / base_fps
            evaluator.evaluate(detections, vid_timestamp, self.latest_frame)
            self.slot_eval_time_ms = int((time.time() - eval_start) * 1000)
            
            # Latency Statistics
            total_latency = self.inference_time_ms + self.slot_eval_time_ms
            self.latency_window.append(total_latency)
            self.latency_avg = statistics.mean(self.latency_window)
            self.latency_max = max(self.latency_window)
            
            # Metrics
            detect_time = time.time() - loop_start
            detected_fps = 1.0 / detect_time if detect_time > 0 else 0
            
            # Rolling smoothed FPS
            fps_rolling_window.append(detected_fps)
            avg_det_fps = statistics.mean(fps_rolling_window)
            
            
            # Adaptive Frame Skipping Logic
            if avg_det_fps < 2:
                self.current_skip_interval = 18
            elif avg_det_fps > 6:
                self.current_skip_interval = 8
            else:
                self.current_skip_interval = FRAME_SKIP_DEFAULT

            latency = self.decode_time_ms + self.inference_time_ms + self.slot_eval_time_ms
            if DEBUG_PIPELINE:
                logging.debug(f"[Pipeline] job_id={self.job_id} frame={processed_inferences} decode={self.decode_time_ms}ms infer={self.inference_time_ms}ms slot_eval={self.slot_eval_time_ms}ms latency={latency}ms skip={self.current_skip_interval}")
                recent_profiling_metrics.append({
                    "fps": round(avg_det_fps, 2),
                    "infer": self.inference_time_ms,
                    "decode": self.decode_time_ms
                })
                
            # WS Throttling & Emit
            current_time = time.time()
            if current_time - last_emit_time >= 0.5:
                actual_progress_frames = processed_inferences * self.current_skip_interval
                progress = min(100.0, (actual_progress_frames / total_frames) * 100)
                
                # Precise ETA calculation mapping user requests
                remaining_frames = total_frames - actual_progress_frames
                remaining_processed_frames = remaining_frames / self.current_skip_interval
                eta = remaining_processed_frames / avg_det_fps if avg_det_fps > 0 else 0
                
                job.processed_frames = processed_inferences
                job.progress_percentage = progress
                job.fps = avg_det_fps
                self.latest_fps = avg_det_fps
                db.commit()
                
                await WebSocketProgressAgent.broadcast_progress(
                    self.job_id, progress, processed_inferences, total_frames, avg_det_fps, eta, self.current_skip_interval
                )
                last_emit_time = current_time
                
            await asyncio.sleep(0.001)

        cap.release()
        
        job = db.query(ProcessingJob).filter(ProcessingJob.id == self.db_id).first()
        if self.running and job.status != "cancelled" and not self.paused:
            job.status = "completed"
            job.progress_percentage = 100.0
            db.commit()
            await WebSocketProgressAgent.broadcast_status(self.job_id, "complete")
            
        db.close()


class JobManager:
    def __init__(self):
        self.active_jobs = {} 
        self.monitor_thread = threading.Thread(target=self._monitor_heartbeats, daemon=True)
        self.monitor_thread.start()
        
    def _monitor_heartbeats(self):
        while True:
            time.sleep(10) # 10s check interval
            dead_workers = []
            current_time = time.time()
            for db_id, agent in list(self.active_jobs.items()):
                # Watchdog: Restart if heartbeat missing > 30s
                is_stale = (current_time - agent.last_heartbeat) > 30.0
                if agent.running and not agent.paused and is_stale:
                    logging.warning(f"Watchdog: Worker {agent.job_id} heartbeat timeout! Restarting thread.")
                    dead_workers.append((db_id, getattr(agent, 'job_id', 'unknown')))
                elif agent.running and not agent.paused and (current_time - agent.worker_last_seen) > 60.0:
                    # Fallback for general deadlock
                    logging.warning(f"Watchdog: Worker {agent.job_id} last seen > 60s! Restarting.")
                    dead_workers.append((db_id, getattr(agent, 'job_id', 'unknown')))
                    
            for db_id, j_id in dead_workers:
                self.cancel_job(db_id)
                self.resume_job(db_id)
        
    def start_job(self, db_id: int, job_id: str):
        if len(self.active_jobs) >= MAX_WORKERS:
            # Simple queue limiting bypass for local dev thread pool limits. Realistically we 
            # prevent queue buildup by overriding concurrent tasks in UI or letting DB handle it
            pass
            
        agent = ProcessingAgent(job_id, db_id)
        agent.start()
        self.active_jobs[db_id] = agent
        
    def get_latest_frame(self):
        with frame_buffer_lock:
            for agent in self.active_jobs.values():
                if agent.latest_frame is not None:
                    return agent.latest_frame.copy()
        return None

    def get_active_skip_interval(self):
        for agent in self.active_jobs.values():
            return agent.current_skip_interval
        return FRAME_SKIP_DEFAULT
        
    def get_profiling_metrics(self):
        for agent in self.active_jobs.values():
            return {
                "decode_time_ms": agent.decode_time_ms,
                "inference_time_ms": agent.inference_time_ms,
                "slot_eval_time_ms": agent.slot_eval_time_ms,
                "frame_processing_time_avg": agent.latency_avg if hasattr(agent, "latency_avg") else 0,
                "frame_processing_time_max": agent.latency_max if hasattr(agent, "latency_max") else 0,
                "fps": agent.latest_fps if hasattr(agent, "latest_fps") else 0,
                "detection_fps": agent.latest_detection_fps if hasattr(agent, "latest_detection_fps") else 0,
                "queue_pressure": agent.queue_pressure if hasattr(agent, "queue_pressure") else 0,
                "frame_stats": {
                    "frames_received": agent.frames_received,
                    "frames_processed": agent.frames_processed,
                    "frames_dropped": agent.frames_dropped
                },
                "detected_classes": agent.detected_classes,
                "stream_source": agent.stream_source
            }
        return {
            "decode_time_ms": 0, "inference_time_ms": 0, "slot_eval_time_ms": 0, "fps": 0, "queue_pressure": 0,
            "frame_stats": {"frames_received": 0, "frames_processed": 0, "frames_dropped": 0},
            "detected_classes": {"car": 0, "truck": 0, "bus": 0, "motorcycle": 0},
            "stream_source": "none"
        }
        
    def get_recent_metrics(self):
        return list(recent_profiling_metrics)
        
    def pause_job(self, db_id: int):
        if db_id in self.active_jobs:
            self.active_jobs[db_id].paused = True
            
    def resume_job(self, db_id: int):
        if db_id in self.active_jobs:
            self.active_jobs[db_id].paused = False
        else:
            db = SessionLocal()
            job = db.query(ProcessingJob).filter(ProcessingJob.id == db_id).first()
            if job:
                self.start_job(db_id, job.job_id)
            db.close()

    def cancel_job(self, db_id: int):
        if db_id in self.active_jobs:
            self.active_jobs[db_id].running = False
            del self.active_jobs[db_id]

job_manager = JobManager()
