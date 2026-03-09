import sys
import os
import time
import cv2
import psutil

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from worker import get_model, SlotEvaluationAgent
from database import SessionLocal

def benchmark(video_path):
    print(f"Starting Benchmark on {video_path}...")
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Error: Could not open video file.")
        return
        
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
    model = get_model()
    evaluator = SlotEvaluationAgent()
    
    decode_times = []
    infer_times = []
    eval_times = []
    
    start_time = time.time()
    frames_processed = 0
    
    while True:
        d_start = time.time()
        ret, frame = cap.read()
        if not ret:
            break
        decode_times.append((time.time() - d_start) * 1000)
        
        i_start = time.time()
        # Mock inference for benchmark
        results = model.predict(frame, imgsz=416, verbose=False)
        infer_times.append((time.time() - i_start) * 1000)
        
        e_start = time.time()
        # Mock eval
        evaluator.evaluate([], time.time())
        eval_times.append((time.time() - e_start) * 1000)
        
        frames_processed += 1
        
        if frames_processed >= 100: # Limit to 100 frames to get a solid average without waiting forever
            break
            
    total_time = time.time() - start_time
    cap.release()
    
    avg_fps = frames_processed / total_time if total_time > 0 else 0
    avg_dec = sum(decode_times) / len(decode_times) if decode_times else 0
    avg_inf = sum(infer_times) / len(infer_times) if infer_times else 0
    avg_eval = sum(eval_times) / len(eval_times) if eval_times else 0
    
    print("\nPipeline Benchmark Results")
    print("--------------------------")
    print(f"Average FPS: {avg_fps:.1f}")
    print(f"Average Inference Time: {avg_inf:.0f} ms")
    print(f"Average Decode Time: {avg_dec:.0f} ms")
    print(f"Slot Evaluation Time: {avg_eval:.0f} ms")
    print(f"Total Runtime: {total_time:.1f} seconds")

if __name__ == "__main__":
    if len(sys.path) > 1 and len(sys.argv) > 1:
        benchmark(sys.argv[1])
    else:
        print("Usage: python benchmark_pipeline.py <video_path>")
