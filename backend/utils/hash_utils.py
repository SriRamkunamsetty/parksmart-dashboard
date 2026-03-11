import cv2
import numpy as np

def compute_frame_hash(frame, size=(9, 8)):
    """
    Computes a 64-bit dHash (Difference Hash) of the frame.
    dHash is robust to minor noise and compression artifacts.
    """
    if frame is None:
        return None
    
    # 1. Grayscale and resize to (9, 8) to get 8 differences per row
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, size, interpolation=cv2.INTER_AREA)
    
    # 2. Compute horizontal differences
    # resized is 8 rows of 9 pixels. 
    # Difference between pixel(x) and pixel(x+1) gives 8 bits per row.
    diff = resized[:, 1:] > resized[:, :-1]
    
    # 3. Convert boolean array to integer hash
    return diff.flatten()

def calculate_hash_distance(hash1, hash2):
    """
    Computes the Hamming distance between two hashes.
    distance = number of different bits.
    A threshold of 5-10 is typical for 'almost identical' frames.
    """
    if hash1 is None or hash2 is None:
        return 999
    return np.count_nonzero(hash1 != hash2)
