"""
Step 2: Defect Detection
YOLOv8m-OBB model inference on the cropped lens ROI to detect 4 defect classes.
"""
import os
from ultralytics import YOLO

# Load model globally to avoid reloading on each frame
MODEL_PATH = os.getenv("MODEL_PATH", "models/best.pt")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.3"))

try:
    model = YOLO(MODEL_PATH)
except Exception as e:
    print(f"Warning: Could not load YOLO model at {MODEL_PATH}. Error: {e}")
    model = None

def detect_defects(roi, confidence_threshold=CONFIDENCE_THRESHOLD) -> list:
    """
    Runs YOLOv8-OBB inference on the region of interest.
    Returns a list of detections: 
    [{"label": str, "class": str, "confidence": float, "obb_coords": list, "bbox": [x, y, w, h]}]
    """
    if model is None or roi is None or roi.size == 0:
        return []
        
    try:
        results = model(roi, conf=confidence_threshold, verbose=False, imgsz=640)
        detections = []
        
        for result in results:
            if result.obb is not None:
                for obb in result.obb:
                    # OBB usually has xywhr or xyxyxyxy coordinates
                    cls_id = int(obb.cls[0].item())
                    conf = float(obb.conf[0].item())
                    
                    # Extract 4 corner points
                    coords = obb.xyxyxyxy[0].cpu().numpy().tolist()
                    
                    # Calculate standard bounding box [x, y, w, h] from OBB
                    xs = [pt[0] for pt in coords]
                    ys = [pt[1] for pt in coords]
                    x_min, x_max = min(xs), max(xs)
                    y_min, y_max = min(ys), max(ys)
                    bbox = [int(x_min), int(y_min), int(x_max - x_min), int(y_max - y_min)]
                    
                    # Map to class name
                    class_name = result.names.get(cls_id, f"class_{cls_id}")
                    
                    detections.append({
                        "label": class_name,      # New format required by prompt
                        "class": class_name,      # Backward compatibility
                        "confidence": conf,
                        "obb_coords": coords,     # Kept for angled drawing
                        "bbox": bbox              # New standard bbox
                    })
                    
        return detections
    except Exception as e:
        print(f"Error during defect detection inference: {e}")
        return []
