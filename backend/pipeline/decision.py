"""
Step 3: Decision + Annotation
Pass/Fail logic, polygon mask overlay, defect bounding boxes on the original frame.
Works with the new segmentation-based lens detector (polygon outline instead of circle).
"""
import cv2
import numpy as np

# Defect class → BGR color
DEFECT_COLORS = {
    "bubble":  (255, 100,   0),   # Blue-orange
    "crack":   (0,     0, 255),   # Red
    "dots":    (0,   230, 230),   # Yellow-cyan
    "scratch": (0,   165, 255),   # Orange
}
DEFAULT_COLOR = (200, 200, 200)   # Light grey for unknown classes


def make_decision_and_annotate(
    frame: np.ndarray,
    is_lens_found: bool,
    detections: list,
    bbox: list,                    # [x, y, w, h] of the lens ROI in the original frame
    mask: np.ndarray | None,       # full-frame binary mask (0/255), or None
    polygon_pts: list,             # outline polygon [[x,y], ...] for drawing
) -> tuple:
    """
    Draws the lens segmentation outline + defect boxes on the original frame.
    Maps all coordinates from ROI-space back to full-frame space.

    Returns:
        annotated_frame  (np.ndarray)
        pass_fail        (str)  "Pass" | "Fail" | "No Lens"
        mapped_detections (list) — detections with coords mapped to full frame
    """
    annotated_frame = frame.copy()

    # ── No lens ───────────────────────────────────────────────────────────────
    if not is_lens_found:
        cv2.putText(
            annotated_frame, "NO LENS DETECTED",
            (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3
        )
        return annotated_frame, "No Lens", []

    x_off, y_off = int(bbox[0]), int(bbox[1])

    # ── Segmentation overlay (semi-transparent teal fill) ────────────────────
    if mask is not None:
        overlay = annotated_frame.copy()
        teal_layer = np.zeros_like(annotated_frame)
        teal_layer[mask > 0] = (180, 220, 0)   # BGR: yellow-green tint
        cv2.addWeighted(teal_layer, 0.15, overlay, 0.85, 0, annotated_frame)

    # ── Lens outline polygon ──────────────────────────────────────────────────
    if polygon_pts and len(polygon_pts) >= 3:
        pts = np.array(polygon_pts, dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(annotated_frame, [pts], isClosed=True, color=(0, 230, 200), thickness=2)

    # ── Bounding rect of lens ─────────────────────────────────────────────────
    lx, ly, lw, lh = [int(v) for v in bbox]
    cv2.rectangle(annotated_frame, (lx, ly), (lx + lw, ly + lh), (0, 200, 180), 1)

    # ── Pass / Fail decision ──────────────────────────────────────────────────
    pass_fail = "Fail" if detections else "Pass"

    # ── Map & draw defect detections ──────────────────────────────────────────
    mapped_detections = []

    for det in detections:
        cls_name = det["label"]
        conf     = det["confidence"]
        color    = DEFECT_COLORS.get(cls_name, DEFAULT_COLOR)

        # OBB polygon — copy before mutating
        coords = np.array(det["obb_coords"], dtype=np.int32).copy()
        coords[:, 0] += x_off
        coords[:, 1] += y_off

        # Axis-aligned bbox
        bx, by, bw, bh = det["bbox"]
        mapped_bbox = [int(bx + x_off), int(by + y_off), int(bw), int(bh)]

        # Draw OBB polygon
        cv2.polylines(annotated_frame, [coords], isClosed=True, color=color, thickness=2)

        # Label — clamp so it never goes above the frame top
        label = f"{cls_name} {conf:.0%}"
        pt1   = tuple(coords[0])
        label_y = max(pt1[1] - 6, 18)
        cv2.putText(
            annotated_frame, label,
            (pt1[0], label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2
        )

        mapped_det = det.copy()
        mapped_det["obb_coords"] = coords.tolist()
        mapped_det["bbox"] = mapped_bbox
        mapped_detections.append(mapped_det)

    # ── Result banner ─────────────────────────────────────────────────────────
    result_color = (0, 220, 80) if pass_fail == "Pass" else (0, 60, 255)
    cv2.putText(
        annotated_frame, f"  {pass_fail.upper()}  ",
        (30, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.6, result_color, 4
    )

    return annotated_frame, pass_fail, mapped_detections
