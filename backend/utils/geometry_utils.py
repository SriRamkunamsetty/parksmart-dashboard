import cv2
import numpy as np

def is_point_in_polygon(point, polygon_pts):
    """
    Checks if a point (x, y) is inside a polygon using cv2.pointPolygonTest.
    """
    if polygon_pts is None or len(polygon_pts) < 3:
        return False
    poly = np.array(polygon_pts, np.int32).reshape((-1, 1, 2))
    return cv2.pointPolygonTest(poly, (float(point[0]), float(point[1])), False) >= 0

def get_centroid(bbox):
    """
    Calculates the centroid (cx, cy) of a bounding box [x1, y1, x2, y2].
    """
    x1, y1, x2, y2 = bbox
    cx = int((x1 + x2) / 2)
    cy = int((y1 + y2) / 2)
    return (cx, cy)

def calculate_iou(bbox, polygon_pts):
    """
    Calculates intersection over area for a bounding box and a polygon.
    Used as a fallback for centroid-only matching.
    """
    poly = np.array(polygon_pts, np.int32).reshape((-1, 1, 2))
    px, py, pw, ph = cv2.boundingRect(poly)
    p_area = cv2.contourArea(poly) or 1
    
    vx1, vy1, vx2, vy2 = bbox
    # Intersection
    ix1 = max(vx1, px)
    iy1 = max(vy1, py)
    ix2 = min(vx2, px + pw)
    iy2 = min(vy2, py + ph)
    
    if ix1 < ix2 and iy1 < iy2:
        intersection = (ix2 - ix1) * (iy2 - iy1)
        return intersection / p_area
    return 0.0
