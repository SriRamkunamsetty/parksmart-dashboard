import cv2
import numpy as np
import logging
import time
import os
import threading
import psutil
import asyncio
from datetime import datetime, timezone
from collections import deque
import statistics
from shapely.geometry import Polygon

from database import SessionLocal
from models import ParkingSlot, ProcessingJob, ParkingSession
from websocket_manager import manager
from config import (
    QUEUE_LIMIT, MAX_FPS_PROCESSING, MEMORY_RESTART_MB, 
    MAX_STREAM_RETRIES, HASH_DISTANCE_THRESHOLD, PROCESSING_LATENCY_WINDOW,
    MAX_HASH_SKIP_FRAMES, FPS_STABILITY_WINDOW
)

from services.detection_service import get_detection_service
from services.slot_service import slot_service, DESIGN_WIDTH, DESIGN_HEIGHT
from services.tracking_service import tracking_service
from utils.hash_utils import compute_frame_hash, calculate_hash_distance
from utils.frame_utils import encode_frame_to_mjpeg, draw_detection_overlay
from utils.logging_utils import log_event

# Project Root Detection
# worker.py is in backend/, project root is one level up
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_VIDEO = os.path.abspath(os.path.join(ROOT_DIR, "parking_video.mp4"))

log_event("startup", f"[STARTUP] default video source: {os.path.basename(DEFAULT_VIDEO)}")

DEMO_STATE_APPLIED = False

class WorkerState:
    INIT = "INIT"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RESTARTING = "RESTARTING"

class ProcessingAgent(threading.Thread):
    def __init__(self, job_id: str, video_path: str, db_id: int):
        super().__init__()
        self.job_id = job_id
        
        # Fallback handling
        if not video_path or not os.path.exists(video_path) or not video_path.lower().endswith(".mp4"):
            log_event("worker", f"[WORKER] video path invalid, falling back to {os.path.basename(DEFAULT_VIDEO)}")
            self.video_path = DEFAULT_VIDEO
        else:
            self.video_path = video_path

        log_event("worker", f"[WORKER] using video source: {os.path.basename(self.video_path)}")
        self.db_id = db_id
        
        self.worker_running = False
        self.capture_finished = False
        self.latest_frame = None
        self.loop = None
        
        self.last_heartbeat_perf = time.perf_counter()
        self.last_heartbeat_ts = time.time()
        self.last_frame_perf = time.perf_counter() # For freeze detection
        
        self.frame_queue = deque(maxlen=QUEUE_LIMIT)
        self.frame_queue_lock = threading.Lock()
        
        self.state = WorkerState.INIT
        self.last_frame_hash = None
        self.last_detections = []
        self.hash_skip_counter = 0
        
        self.frames_received = 0
        self.frames_processed = 0
        self.frames_dropped = 0
        self.frames_dropped_total = 0
        self.decode_error_count = 0
        self.latest_fps = 0
        self.stream_status = "RECONNECTING"
        self.stream_retry_count = 0
        self.stream_reconnect_count = 0
        self.stream_connected_at = None
        
        self.latency_window = deque(maxlen=PROCESSING_LATENCY_WINDOW)
        self.queue_latency_window = deque(maxlen=PROCESSING_LATENCY_WINDOW)
        self.fps_window = deque(maxlen=FPS_STABILITY_WINDOW)
        self.inference_time_ms = 0
        self.slot_eval_time_ms = 0
        
        self.capture_thread = None
        self.cached_resolution = (0, 0)
        self.cached_scaled_slots = {}

    def run(self):
        self.worker_running = True
        self.state = WorkerState.RUNNING
        
        # SECTION: Emergency Demo Configuration - Force DB Sync
        global DEMO_STATE_APPLIED
        from services.slot_service import DEMO_MODE
        if DEMO_MODE and not DEMO_STATE_APPLIED:
            try:
                db = SessionLocal()
                log_event("worker", "[DEMO] Forcing deterministic slot states for demo...")
                
                # Force Available
                db.query(ParkingSlot).filter(ParkingSlot.id == "S2").update({"status": "available"})
                db.query(ParkingSlot).filter(ParkingSlot.id == "S5").update({"status": "available"})
                
                # Force Occupied
                db.query(ParkingSlot).filter(ParkingSlot.id.in_(["S1", "S3", "S4", "S6", "S7"])).update({"status": "occupied"})
                
                db.commit()
                db.close()
                
                slot_service.refresh_cache()
                
                # Clear Worker Caches
                self.cached_scaled_slots.clear()
                self.cached_resolution = (0, 0)
                
                DEMO_STATE_APPLIED = True
                log_event("worker", "[DEMO] DB sync complete: S2, S5 available; S1,S3,S4,S6,S7 occupied.")
            except Exception as e:
                log_event("worker", f"[DEMO ERROR] Failed to force demo states: {e}")

        log_event("worker", f"[WORKER] starting {self.job_id}")
        
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True, name=f"Cap-{self.job_id}")
        self.capture_thread.start()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._process_loop())
        finally:
            loop.close()

    def _capture_loop(self):
        log_event("worker", f"[WORKER] capture loop started: {self.job_id}")
        while self.worker_running:
            if self.capture_finished:
                break

            cap = cv2.VideoCapture(self.video_path)
            if cap.isOpened():
                self.stream_status = "CONNECTED"
                self.stream_connected_at = time.perf_counter()
                self.stream_reconnect_count += 1
                self.stream_retry_count = 0
                log_event("worker", "[WORKER] video capture initialized")
                log_event("stream", f"[WORKER] stream connected: {os.path.basename(self.video_path)}")
            else:
                self.stream_status = "DISCONNECTED"
                self.stream_retry_count += 1
                if self.stream_retry_count > MAX_STREAM_RETRIES:
                    log_event("worker", f"[STREAM] max retries reached: {self.job_id}", {"level": "error"})
                    self.state = WorkerState.FAILED
                    self.worker_running = False
                    break
                
                delay = min(30, self.stream_retry_count * 5)
                log_event("stream", f"[STREAM] reconnect attempt {self.stream_retry_count} in {delay}s")
                for _ in range(int(delay * 10)):
                    if not self.worker_running: break
                    time.sleep(0.1)
                continue

            while self.worker_running:
                ret, frame = cap.read()
                if not ret:
                    break
                
                capture_ts = time.perf_counter()
                self.last_frame_perf = capture_ts
                with self.frame_queue_lock:
                    if len(self.frame_queue) == QUEUE_LIMIT:
                        self.frame_queue.popleft()
                        self.frames_dropped += 1
                        self.frames_dropped_total += 1
                    self.frame_queue.append((frame, capture_ts))
                    self.frames_received += 1
                
                time.sleep(0.01) 

            cap.release()
            if not self.worker_running:
                break
            
            # Hardening: Stream Freeze Detection
            if time.perf_counter() - self.last_frame_perf > 10.0:
                log_event("worker", f"[WORKER] stream freeze detected (>10s): {self.job_id}")
                self.state = WorkerState.RESTARTING
                self.worker_running = False
                break

            if not self.capture_finished:
                log_event("worker", "[WORKER] stream ended or lost")
                self.capture_finished = True
                break

    async def _process_loop(self):
        self.loop = asyncio.get_running_loop()
        db = SessionLocal()
        detection_service = get_detection_service()
        
        try:
            while self.worker_running:
                self.last_heartbeat_perf = time.perf_counter()
                self.last_heartbeat_ts = time.time()
                
                frame_data = None
                with self.frame_queue_lock:
                    if self.frame_queue:
                        frame_data = self.frame_queue.popleft()

                if frame_data is None:
                    if self.capture_finished and not self.frame_queue:
                        log_event("job", f"[JOB] {self.job_id} processing complete")
                        break
                    await asyncio.sleep(0.01)
                    continue

                frame, capture_ts = frame_data
                process_start = time.perf_counter()
                
                queue_latency = max(0, min((process_start - capture_ts) * 1000, 5000))
                self.queue_latency_window.append(queue_latency)
                
                # Queue Backpressure Protection: Flush if backlog is too high
                if queue_latency > 2000.0:
                    with self.frame_queue_lock:
                        self.frame_queue.clear()
                        log_event("worker", f"[WORKER] queue backlog detected ({queue_latency:.0f}ms). flushing frame queue to resume real-time sync.")
                    continue
                
                if self.frames_processed % 30 == 0:
                    slot_service.verify_cache_integrity()
                
                frame_hash = compute_frame_hash(frame)
                if self.last_frame_hash is None:
                    dist = HASH_DISTANCE_THRESHOLD + 1
                else:
                    dist = calculate_hash_distance(frame_hash, self.last_frame_hash)
                
                from config import FORCE_DETECTION_INTERVAL
                force_detection = (self.frames_processed % FORCE_DETECTION_INTERVAL == 0)
                backlogged = (len(self.frame_queue) > QUEUE_LIMIT * 0.5)
                
                if (dist < HASH_DISTANCE_THRESHOLD and not force_detection and not backlogged 
                    and self.hash_skip_counter < MAX_HASH_SKIP_FRAMES):
                    detections = self.last_detections
                    self.hash_skip_counter += 1
                else:
                    inf_start = time.perf_counter()
                    results = detection_service.detect(frame)
                    vehicle_count = sum(len(r.boxes) for r in results if r.boxes is not None)
                    log_event("worker", f"[YOLO] vehicles detected: {vehicle_count}")
                    
                    detections = []
                    for r in results:
                        if r.boxes is None or len(r.boxes) == 0:
                            continue
                        
                        # Extract boxes and validate
                        for b in r.boxes:
                            try:
                                # Section 4: Detection Confidence Filtering
                                try:
                                    conf = float(b.conf[0]) if hasattr(b.conf, "__len__") else float(b.conf)
                                except (TypeError, AttributeError):
                                    conf = 0.0
                                    
                                if conf < 0.35:
                                    continue
                                    
                                x1, y1, x2, y2 = map(float, b.xyxy[0].cpu().numpy())
                                
                                # Section 3: Bounding Box Validation
                                if x2 <= x1 or y2 <= y1:
                                    continue
                                    
                                # Section 6: Centroid Precision
                                cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                                
                                # Section 5: Robust Tracker ID Extraction
                                track_id = None
                                if hasattr(b, "id") and b.id is not None and len(b.id) > 0:
                                    track_id = int(b.id[0])
                                
                                # Minimal geometry: Only bbox and float-precision centroid
                                detections.append({
                                    "bbox": (float(x1), float(y1), float(x2), float(y2)), 
                                    "centroid": (float(cx), float(cy)), 
                                    "track_id": track_id,
                                    "conf": conf
                                })
                                # High-frequency diagnostic (local only)
                                logging.debug(f"[YOLO] detected vehicle at ({cx:.1f}, {cy:.1f}) conf:{conf:.2f}")
                            except Exception as e:
                                logging.error(f"[YOLO] error parsing box: {e}")
                    
                    self.inference_time_ms = int((time.perf_counter() - inf_start) * 1000)
                    self.last_frame_hash = frame_hash
                    self.last_detections = detections
                    self.hash_skip_counter = 0

                tracking_service.update_tracks(detections, current_frame_id=self.frames_processed)
                
                # 3. Slot Evaluation
                # log_event("worker", f"[WORKER] starting evaluation for frame {self.frames_processed}")
                
                # Normalization & Scaling for evaluation
                h, w = frame.shape[:2]
                
                # SECTION 7: Slot Cache Invalidation
                # Also Performance Optimization: Only re-scale if resolution changes OR slot count changes
                slot_count = len(slot_service.slot_cache)
                needs_rescale = (w, h) != self.cached_resolution or len(self.cached_scaled_slots) != slot_count
                
                # Check for database-driven cache updates
                if slot_service.verify_cache_integrity():
                    needs_rescale = True
                    self.cached_scaled_slots.clear()
                    self.cached_resolution = (0, 0)

                if needs_rescale:
                    scale_x = w / DESIGN_WIDTH
                    scale_y = h / DESIGN_HEIGHT
                    
                    log_event("worker", f"[AGENT] building scaled cache: res={w}x{h}, scale={scale_x:.2f}x{scale_y:.2f}, slots={slot_count}")
                    
                    self.cached_scaled_slots = {}
                    for sid, s_cache in slot_service.slot_cache.items():
                        try:
                            raw_pts = s_cache["polygon_pts"]
                            scaled_pts = [[int(x * scale_x), int(y * scale_y)] for [x, y] in raw_pts]
                            
                            s_poly = Polygon(scaled_pts)
                            self.cached_scaled_slots[sid] = {
                                "poly_cv2": np.array(scaled_pts, dtype=np.int32).reshape((-1, 1, 2)),
                                "shapely_poly": s_poly,
                                "area": s_poly.area,
                                "status": s_cache.get("status", "available"),
                                "number": s_cache.get("number", "??")
                            }
                        except Exception as e:
                            logging.error(f"[WORKER] error scaling slot {sid}: {e}")
                            
                    self.cached_resolution = (w, h)

                # 3. Slot Evaluation
                updates, eval_time = slot_service.evaluate_slots(detections, self.cached_scaled_slots)
                self.slot_eval_time_ms = eval_time
                
                # Performance Monitoring (Agent Mode)
                if eval_time > 2.0 and self.frames_processed % 50 == 0:
                    log_event("system", f"[AGENT WARNING] slot evaluation performance degraded ({eval_time:.2f}ms)")

                if updates:
                    self._persist_updates(db, updates)
                
                # 4. Rendering - Pass scaled polygons directly
                self.latest_frame = draw_detection_overlay(frame, detections, self.cached_scaled_slots.values())

                if self.frames_processed % 100 == 0:
                    cpu_usage = psutil.cpu_percent()
                    log_event("worker", f"[WORKER] CPU level: {cpu_usage}%")

                mem_mb = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
                if mem_mb > MEMORY_RESTART_MB:
                    log_event("system", f"[WORKER] memory threshold hit ({mem_mb:.0f}MB). performing safe restart.")
                    self.state = WorkerState.RESTARTING
                    self.worker_running = False
                    break

                self.frames_processed += 1
                exec_time = time.perf_counter() - process_start
                fps = 1.0 / exec_time if exec_time > 0 else 0
                self.fps_window.append(fps)
                self.latest_fps = statistics.mean(self.fps_window)
                self.latency_window.append(exec_time * 1000)
                
                if self.frames_processed % 50 == 0:
                    log_event("worker", f"[WORKER] processed {self.frames_processed} frames")

                sleep_time = max(0, (1.0 / MAX_FPS_PROCESSING) - exec_time)
                await asyncio.sleep(sleep_time)

            if self.state not in [WorkerState.RESTARTING, WorkerState.FAILED]:
                self.state = WorkerState.COMPLETED
                db_job = db.query(ProcessingJob).filter(ProcessingJob.id == self.db_id).first()
                if db_job:
                    db_job.status = "completed"
                    db_job.frames_processed = self.frames_processed
                    db_job.completed_at = datetime.now(timezone.utc)
                    db.commit()

        except Exception as e:
            log_event("worker", f"[WORKER] critical error: {e}", {"level": "error"})
            self.state = WorkerState.FAILED
            db_job = db.query(ProcessingJob).filter(ProcessingJob.id == self.db_id).first()
            if db_job:
                db_job.status = "failed"
                db_job.error_message = str(e)
                db.commit()
        finally:
            db.close()

    def _persist_updates(self, db, updates):
        try:
            now_utc = datetime.now(timezone.utc)
            for u in updates:
                slot_id = u["slot_id"]
                new_status = u["status"]
                vid = u.get("vehicle_id")
                
                slot = db.query(ParkingSlot).filter(ParkingSlot.id == slot_id).first()
                if not slot: continue
                
                if new_status == "occupied":
                    session = ParkingSession(slot_id=slot.id, vehicle_id=vid, entry_time=now_utc)
                    db.add(session)
                elif new_status == "available":
                    session = db.query(ParkingSession).filter(
                        ParkingSession.slot_id == slot.id, ParkingSession.exit_time == None
                    ).first()
                    if session: session.exit_time = now_utc

                slot.status = new_status
                slot.last_status_change_at = now_utc
                
                payload = {"event": "slot_update", "slot_id": slot_id, "status": new_status}
                if self.loop and self.loop.is_running():
                    asyncio.run_coroutine_threadsafe(manager.broadcast(payload), self.loop)
                
            db.commit()
        except Exception as e:
            db.rollback()
            log_event("system", f"[DB] persistence error: {e}")

class JobManager:
    def __init__(self):
        self.active_agents = {}
        self.worker_restart_count = 0
        self.watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True, name="WorkerWatchdog")
        self.watchdog_thread.start()

    def start_job(self, db_id: int, job_id: str):
        db = SessionLocal()
        try:
            job = db.query(ProcessingJob).filter(ProcessingJob.id == db_id).first()
            if job: self.start_worker(db_id, job_id, job.video_path)
        finally:
            db.close()

    def start_worker(self, db_id: int, job_id: str, video_path: str):
        if db_id in self.active_agents:
            log_event("worker", f"[WORKER] duplicate skip: {job_id}")
            return
        
        agent = ProcessingAgent(job_id, video_path, db_id)
        agent.start()
        self.active_agents[db_id] = agent

    def stop_worker(self, db_id: int):
        if db_id in self.active_agents:
            agent = self.active_agents[db_id]
            agent.worker_running = False
            if agent.capture_thread and agent.capture_thread.is_alive():
                agent.capture_thread.join(timeout=5)
            if agent.is_alive():
                agent.join(timeout=5)
            with agent.frame_queue_lock:
                agent.frame_queue.clear()
            del self.active_agents[db_id]
            log_event("worker", f"[WORKER] stopped {agent.job_id}")

    def _watchdog_loop(self):
        while True:
            time.sleep(5)
            now = time.perf_counter()
            for db_id, agent in list(self.active_agents.items()):
                if agent.worker_running and (now - agent.last_heartbeat_perf) > 10.0:
                    log_event("system", f"[WATCHDOG] worker restart triggered: {agent.job_id}")
                    self.worker_restart_count += 1
                    j_id, v_path = agent.job_id, agent.video_path
                    self.stop_worker(db_id)
                    self.start_worker(db_id, j_id, v_path)
                elif not agent.worker_running and agent.state == WorkerState.RESTARTING:
                    log_event("system", f"[WATCHDOG] performing memory restart: {agent.job_id}")
                    self.worker_restart_count += 1
                    j_id, v_path = agent.job_id, agent.video_path
                    self.stop_worker(db_id)
                    self.start_worker(db_id, j_id, v_path)

    def get_metrics(self):
        # Global System Stats
        try:
            svmem = psutil.virtual_memory()
            system_mem_percent = svmem.percent
            system_cpu_percent = psutil.cpu_percent(interval=None)
            disk_usage = psutil.disk_usage('/')
            system_disk_percent = disk_usage.percent
            process_uptime = time.time() - psutil.Process(os.getpid()).create_time()
        except:
            system_mem_percent = 0
            system_cpu_percent = 0
            system_disk_percent = 0
            process_uptime = 0

        for agent in self.active_agents.values():
            fps_stability = statistics.stdev(agent.fps_window) if len(agent.fps_window) > 1 else 0
            uptime = int(time.perf_counter() - agent.stream_connected_at) if agent.stream_connected_at else 0
            
            from config import MAX_HASH_SKIP_FRAMES
            return {
                "worker_state": agent.state,
                "stream_state": agent.stream_status,
                "stream_uptime": uptime,
                "stream_reconnects": agent.stream_reconnect_count,
                "worker_restarts": self.worker_restart_count,
                "processing_fps": round(agent.latest_fps, 2),
                "fps_stability": round(fps_stability, 3),
                "processing_latency_ms": round(statistics.mean(agent.latency_window) if agent.latency_window else 0, 2),
                "queue_latency_ms": round(statistics.mean(agent.queue_latency_window) if agent.queue_latency_window else 0, 2),
                "inference_time_ms": agent.inference_time_ms,
                "slot_eval_time_ms": agent.slot_eval_time_ms,
                "decode_time_ms": 0, # Placeholder for now
                "hash_skip_counter": agent.hash_skip_counter,
                "frame_skip_interval": MAX_HASH_SKIP_FRAMES,
                "queue_size": len(agent.frame_queue),
                "frame_queue_size": len(agent.frame_queue),
                "heartbeat": datetime.fromtimestamp(agent.last_heartbeat_ts, timezone.utc).isoformat(),
                "active_job_id": agent.job_id,
                "frames_processed": agent.frames_processed,
                "frames_received": agent.frames_received,
                "cpu_percent": system_cpu_percent,
                "memory_percent": system_mem_percent,
                "disk_percent": system_disk_percent,
                "process_uptime": process_uptime,
                "active_workers": len(self.active_agents),
                "model_loaded": True
            }
        
        return {
            "worker_state": "IDLE", 
            "active_workers": 0,
            "cpu_percent": system_cpu_percent,
            "memory_percent": system_mem_percent,
            "disk_percent": system_disk_percent,
            "process_uptime": process_uptime,
            "frame_queue_size": 0,
            "inference_time_ms": 0,
            "slot_eval_time_ms": 0,
            "decode_time_ms": 0
        }

    def get_latest_frame(self):
        for agent in self.active_agents.values():
            if agent.latest_frame is not None: return agent.latest_frame
        return None

job_manager = JobManager()
