import time
import logging

class TrackingService:
    def __init__(self, ttl=300):
        self.tracker_vehicle_map = {} # track_id -> vehicle_id
        self.last_seen_time = {}      # track_id -> timestamp
        self.last_seen_frame = {}     # track_id -> frame_id
        self.ttl = ttl               # seconds

    def update_tracks(self, detections, current_frame_id=None):
        """
        Maintains consistent vehicle identity.
        In this blueprint, we use YOLO's track_id as vehicle_id.
        """
        now = time.time()
        for d in detections:
            tid = d.get("track_id")
            if tid is not None:
                self.last_seen_time[tid] = now
                if current_frame_id is not None:
                    self.last_seen_frame[tid] = current_frame_id
        
        # Cleanup stale tracks
        if current_frame_id is not None:
            # Hardening: Remove if not seen for > 50 frames
            stale_ids = [tid for tid, f_id in self.last_seen_frame.items() if (current_frame_id - f_id) > 50]
        else:
            # Fallback to time-based TTL
            stale_ids = [tid for tid, ts in self.last_seen_time.items() if now - ts > self.ttl]
            
        for tid in stale_ids:
            self.last_seen_time.pop(tid, None)
            self.last_seen_frame.pop(tid, None)
            self.tracker_vehicle_map.pop(tid, None)

# Global instance
tracking_service = TrackingService()
