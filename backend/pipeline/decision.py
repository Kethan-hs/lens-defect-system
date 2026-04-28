"""
Step 3: Decision + Output
Pass/Fail logic, bounding box annotation, and returning the annotated frame.
"""
import cv2
import numpy as np

def make_decision_and_annotate(frame, is_lens_found, circle_coords, detections, lens_bbox=None):
    """
    Annotates the frame and makes a Pass/Fail decision.
    Maps defect coordinates back to the original frame.
    """
    annotated_frame = frame.copy()
    
    if not is_lens_found:
        cv2.putText(annotated_frame, "NO LENS DETECTED", (30, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        return annotated_frame, "No Lens", detections
        
    x, y, r = circle_coords
    
    # Draw lens outline and bounding box
    cv2.circle(annotated_frame, (x, y), r, (255, 255, 0), 2)
    cv2.circle(annotated_frame, (x, y), 2, (0, 0, 255), 3) # center
    
    if lens_bbox is not None and len(lens_bbox) == 4:
        lx, ly, lw, lh = lens_bbox
        cv2.rectangle(annotated_frame, (lx, ly), (lx + lw, ly + lh), (255, 255, 0), 1)
    
    # Determine pass/fail
    pass_fail = "Fail" if len(detections) > 0 else "Pass"
    
    # Coordinates offset
    x_min = max(0, x - r)
    y_min = max(0, y - r)
    
    colors = {
        "bubble": (255, 0, 0),    # Blue
        "crack": (0, 0, 255),     # Red
        "dots": (0, 255, 255),    # Yellow
        "scratch": (0, 165, 255)  # Orange
    }
    
    mapped_detections = []
    
    for det in detections:
        cls_name = det["label"] # Use the new format label
        conf = det["confidence"]
        
        # Map OBB coords
        coords = np.array(det["obb_coords"], dtype=np.int32)
        coords[:, 0] += int(x_min)
        coords[:, 1] += int(y_min)
        
        # Map standard bbox coords [x, y, w, h]
        bx, by, bw, bh = det["bbox"]
        mapped_bbox = [int(bx + x_min), int(by + y_min), int(bw), int(bh)]
        
        color = colors.get(cls_name, (255, 255, 255))
        
        # Draw polygon for OBB
        cv2.polylines(annotated_frame, [coords], isClosed=True, color=color, thickness=2)
        
        # Label
        label = f"{cls_name} {conf:.2f}"
        pt1 = tuple(coords[0])
        cv2.putText(annotated_frame, label, (pt1[0], pt1[1] - 5), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                    
        # Construct updated detection dict
        mapped_det = det.copy()
        mapped_det["obb_coords"] = coords.tolist()
        mapped_det["bbox"] = mapped_bbox
        mapped_detections.append(mapped_det)
                    
    # Draw Pass/Fail text
    result_color = (0, 255, 0) if pass_fail == "Pass" else (0, 0, 255)
    cv2.putText(annotated_frame, f"RESULT: {pass_fail}", (30, 50), 
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, result_color, 3)
                
    return annotated_frame, pass_fail, mapped_detections
