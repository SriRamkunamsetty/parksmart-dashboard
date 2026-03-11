import cv2
import json
import numpy as np

def encode_frame_to_mjpeg(frame, quality=70):
    """
    Encodes a BGR frame to MJPEG JPEG byte buffer.
    """
    if frame is None:
        return None
    _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return buffer.tobytes()

def draw_detection_overlay(frame, detections, scaled_slots):
    """
    SECTION 12-15: Rendering Pipeline Audit - Clean Demo Mode
    - ONLY Green slot polygons
    - NO labels, boxes, or centroids
    """
    if frame is None:
        return None
    
    # SECTION 15: Rendering Safety
    if not scaled_slots:
        return frame
        
    overlay = frame.copy()
    
    # SECTION 14: Slot Visualization (Clean Look)
    for slot in scaled_slots:
        # Constant Green for all slots in Demo Mode
        color = (0, 255, 0)
        
        poly_cv2 = slot.get("poly_cv2")
        if poly_cv2 is not None:
            try:
                cv2.polylines(overlay, [poly_cv2], True, color, 2)
            except Exception:
                pass
        
    return overlay
