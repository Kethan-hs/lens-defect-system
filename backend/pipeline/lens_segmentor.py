"""
Lens Segmentation — Step 1 of the inspection pipeline.

Detection priority:
  1. Fine-tuned YOLOv8n-seg  (lens_seg.pt — trained specifically on lens/eyewear images)
  2. Smart CV fallback        (GrabCut + ellipse fitting — works in clean lab setups)

The trained model (lens_seg.pt) is built by running:
  scripts/train_lens_segmentation.py

Until that model is available the CV fallback handles clean lab frames reliably.
"""

import cv2
import numpy as np
import os
import threading

# ── Model paths & thresholds ──────────────────────────────────────────────────
# Primary: custom-trained lens segmentation model
LENS_SEG_MODEL_PATH = os.getenv("LENS_SEG_MODEL_PATH", "models/lens_seg.pt")
# Fallback: legacy custom model path for backwards compatibility
LENS_SEG_LEGACY_PATH = "models/lens_seg.pt"
# Fallback: generic nano-seg model (optional, only used if custom model is absent)
GENERIC_SEG_MODEL_PATH = os.getenv("SEG_MODEL_PATH", "models/yolov8n-seg.pt")

SEG_CONF   = float(os.getenv("SEG_CONFIDENCE", "0.35"))
MIN_AREA_F = float(os.getenv("LENS_MIN_AREA_FRAC", "0.005"))   # 0.5% of frame
MAX_AREA_F = float(os.getenv("LENS_MAX_AREA_FRAC", "0.92"))    # 92% of frame

# ── Lazy model loader (thread-safe) ──────────────────────────────────────────
_model      = None
_model_path = None
_model_lock = threading.Lock()


def _load_model():
    """Load best available segmentation model, thread-safe."""
    global _model, _model_path

    with _model_lock:
        if _model is not None:
            return _model

        try:
            from ultralytics import YOLO
        except ImportError:
            print("[LensSeg] ultralytics not installed — CV fallback only")
            return None

        for path in [LENS_SEG_MODEL_PATH, LENS_SEG_LEGACY_PATH, GENERIC_SEG_MODEL_PATH]:
            if os.path.exists(path):
                try:
                    _model = YOLO(path)
                    _model_path = path
                    print(f"[LensSeg] Loaded model: {path}")
                    return _model
                except Exception as e:
                    print(f"[LensSeg] Failed to load {path}: {e}")

        print("[LensSeg] No model file found — CV fallback only")
        return None


# ── YOLO segmentation ─────────────────────────────────────────────────────────
def _yolo_segment(frame: np.ndarray):
    """
    Run YOLOv8-seg on the frame.

    For the fine-tuned lens_seg model  → accept class 0 ('lens') only.
    For the generic yolov8n-seg model  → accept any class (since lens was
      trained as a single-class model we can't predict COCO IDs).

    Returns (mask_uint8, bbox, polygon_pts) or (None, None, None).
    """
    model = _load_model()
    if model is None:
        return None, None, None

    h, w = frame.shape[:2]
    min_area = h * w * MIN_AREA_F
    max_area = h * w * MAX_AREA_F
    is_custom = (_model_path == LENS_SEG_MODEL_PATH)

    try:
        results = model(frame, conf=SEG_CONF, verbose=False, imgsz=640)
    except Exception as e:
        print(f"[LensSeg] Inference error: {e}")
        return None, None, None

    best_mask   = None
    best_area   = 0

    for result in results:
        if result.masks is None:
            continue

        for i, seg_mask in enumerate(result.masks.data):
            cls_id = int(result.boxes.cls[i].item())
            conf   = float(result.boxes.conf[i].item())

            # Custom model: only class 0 = lens
            # Generic model: accept class 0 (person — may have glasses), or skip
            if is_custom and cls_id != 0:
                continue
            if not is_custom and cls_id not in {0, 29, 32, 37, 46}:
                continue

            mask_np = seg_mask.cpu().numpy().astype(np.uint8) * 255
            mask_resized = cv2.resize(mask_np, (w, h), interpolation=cv2.INTER_NEAREST)
            area = float(mask_resized.sum()) / 255.0

            if area < min_area or area > max_area:
                continue

            if area > best_area:
                best_area  = area
                best_mask  = mask_resized

    if best_mask is None:
        return None, None, None

    return _mask_to_output(best_mask)


# ── CV fallback — GrabCut + ellipse fitting ───────────────────────────────────
def _cv_segment(frame: np.ndarray):
    """
    Pure-CV lens isolation using:
      1. Adaptive threshold + morphological cleaning to find circular regions
      2. Ellipse fitting with aspect-ratio, solidity, and size filters
      3. GrabCut refinement of the best ellipse candidate

    Works well for clean lab setups (lens on flat surface, neutral background).
    Returns (mask_uint8, bbox, polygon_pts) or (None, None, None).
    """
    h, w = frame.shape[:2]
    min_area = h * w * MIN_AREA_F
    max_area = h * w * MAX_AREA_F

    gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (9, 9), 0)

    # ── Step 1: Multi-scale edge map ──────────────────────────────────────────
    edges_low  = cv2.Canny(blurred, 20, 60)
    edges_high = cv2.Canny(blurred, 50, 150)
    edges      = cv2.addWeighted(edges_low, 0.5, edges_high, 0.5, 0)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    edges  = cv2.dilate(edges, kernel, iterations=2)
    edges  = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=3)

    # ── Step 2: Find and score contours ──────────────────────────────────────
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best_contour  = None
    best_score    = -1

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area or area > max_area:
            continue
        if len(cnt) < 5:
            continue   # need at least 5 points for ellipse fitting

        peri = cv2.arcLength(cnt, True)
        if peri < 1:
            continue

        # Circularity (1.0 = perfect circle)
        circularity = (4.0 * np.pi * area) / (peri * peri)
        if circularity < 0.25:
            continue    # too elongated or jagged

        # Fit ellipse and check axis ratio
        ellipse = cv2.fitEllipse(cnt)
        (_, _), (ma, Mi), _ = ellipse
        if Mi < 1:
            continue
        axis_ratio = ma / Mi
        if axis_ratio < 0.3 or axis_ratio > 3.0:
            continue    # lens can't be that elongated

        # Convex hull solidity
        hull  = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        solidity  = area / hull_area if hull_area > 0 else 0
        if solidity < 0.55:
            continue

        score = circularity * solidity * area
        if score > best_score:
            best_score   = score
            best_contour = cnt

    if best_contour is None:
        return None, None, None

    # ── Step 3: GrabCut refinement ────────────────────────────────────────────
    rx, ry, rw, rh = cv2.boundingRect(best_contour)
    # Pad bounding box by 10% for GrabCut
    pad_x = max(4, int(rw * 0.10))
    pad_y = max(4, int(rh * 0.10))
    gx    = max(0, rx - pad_x)
    gy    = max(0, ry - pad_y)
    gw    = min(w - gx, rw + 2 * pad_x)
    gh    = min(h - gy, rh + 2 * pad_y)

    if gw < 8 or gh < 8:
        # Skip GrabCut, use contour directly
        mask_final = np.zeros((h, w), np.uint8)
        cv2.fillPoly(mask_final, [best_contour], 255)
        return _mask_to_output(mask_final)

    try:
        gc_mask  = np.zeros((h, w), np.uint8)
        bgd_model = np.zeros((1, 65), np.float64)
        fgd_model = np.zeros((1, 65), np.float64)
        rect      = (gx, gy, gw, gh)
        cv2.grabCut(frame, gc_mask, rect, bgd_model, fgd_model, 4, cv2.GC_INIT_WITH_RECT)
        gc_result = np.where((gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

        # Intersect GrabCut result with convex hull of best contour
        hull_mask = np.zeros((h, w), np.uint8)
        cv2.fillConvexPoly(hull_mask, cv2.convexHull(best_contour), 255)
        mask_final = cv2.bitwise_and(gc_result, hull_mask)

        # If GrabCut returned nearly nothing, fall back to contour mask
        if float(mask_final.sum()) / 255 < min_area:
            mask_final = hull_mask

    except cv2.error:
        # GrabCut can fail on tiny/edge frames
        mask_final = np.zeros((h, w), np.uint8)
        cv2.fillPoly(mask_final, [best_contour], 255)

    # Clean up
    kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask_final   = cv2.morphologyEx(mask_final, cv2.MORPH_CLOSE, kernel_small, iterations=2)
    mask_final   = cv2.morphologyEx(mask_final, cv2.MORPH_OPEN,  kernel_small, iterations=1)

    return _mask_to_output(mask_final)


# ── Shared mask → polygon/bbox helper ────────────────────────────────────────
def _mask_to_output(mask: np.ndarray):
    """Convert a binary mask to (mask, bbox, polygon_pts)."""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, None, None

    largest = max(contours, key=cv2.contourArea)
    epsilon  = 0.008 * cv2.arcLength(largest, True)
    approx   = cv2.approxPolyDP(largest, epsilon, True)

    x, y, bw, bh = cv2.boundingRect(largest)
    bbox         = [int(x), int(y), int(bw), int(bh)]
    polygon_pts  = approx.reshape(-1, 2).tolist()

    return mask, bbox, polygon_pts


# ── Public API ────────────────────────────────────────────────────────────────
def segment_lens(frame: np.ndarray):
    """
    Detect and segment the lens in a camera frame.

    Returns:
        is_found    (bool)
        roi         (np.ndarray) — cropped, masked lens region (BGR, background = black)
        bbox        (list[int])  — [x, y, w, h] in original frame coords
        mask        (np.ndarray) — full-frame binary mask, dtype uint8 (0 / 255)
        polygon_pts (list)       — outline polygon [[x,y], ...] for drawing
    """
    if frame is None or frame.size == 0:
        return False, frame, [], None, []

    h, w = frame.shape[:2]

    # Try ML model first, then CV fallback
    mask, bbox, polygon_pts = _yolo_segment(frame)
    if mask is None:
        mask, bbox, polygon_pts = _cv_segment(frame)

    if mask is None or bbox is None:
        return False, frame, [], None, []

    x, y, bw, bh = bbox
    if bw < 20 or bh < 20:
        return False, frame, [], None, []

    # Crop and mask the ROI
    roi_raw   = frame[y : y + bh, x : x + bw]
    mask_crop = mask[y : y + bh, x : x + bw]

    if roi_raw.size == 0 or mask_crop.size == 0:
        return False, frame, [], None, []

    mask_3ch  = cv2.merge([mask_crop, mask_crop, mask_crop])
    roi_clean = cv2.bitwise_and(roi_raw, mask_3ch)

    return True, roi_clean, bbox, mask, polygon_pts
