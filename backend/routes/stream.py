from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
import cv2
import asyncio
import json
import os
from pipeline.lens_detector import detect_lens
from pipeline.defect_detector import detect_defects
from pipeline.decision import make_decision_and_annotate
from db.database import SessionLocal
from db.models import InspectionLog

import numpy as np

router = APIRouter()


# ─── Synchronous pipeline function (runs in thread pool) ───────────────
def _run_pipeline(frame_bytes: bytes) -> tuple:
    """
    Runs the full detection pipeline on raw JPEG bytes.
    This is a BLOCKING function — must be called via asyncio.to_thread().
    Returns (out_frame_bytes, metadata_dict, is_lens_found, pass_fail, final_detections)
    """
    # Decode bytes to OpenCV image
    nparr = np.frombuffer(frame_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is None:
        return None, None, False, "No Lens", []

    # Stage 1: Lens detection (HoughCircles — fast, ~5-10ms)
    is_lens_found, roi, lens_bbox, circle_coords = detect_lens(frame)

    # Stage 2: Defect detection (YOLO — slow, ~100-200ms) — only on ROI
    detections = []
    if is_lens_found:
        detections = detect_defects(roi)

    # Stage 3: Decision + annotation
    annotated_frame, pass_fail, final_detections = make_decision_and_annotate(
        frame, is_lens_found, circle_coords, detections, lens_bbox
    )

    # Encode annotated frame to JPEG
    _, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    out_frame_bytes = buffer.tobytes()

    metadata = {
        # New spec format
        "lens_detected": bool(is_lens_found),
        "lens_bbox": lens_bbox if is_lens_found else [],
        "defects": final_detections,

        # Backward compatibility for existing React frontend
        "pass_fail": pass_fail,
        "detections": final_detections,
        "is_lens_found": bool(is_lens_found)
    }

    return out_frame_bytes, metadata, is_lens_found, pass_fail, final_detections


# ─── Background DB write (non-blocking) ───────────────────────────────
async def _save_to_db(pass_fail: str, final_detections: list):
    """Writes inspection result to DB in a background task."""
    try:
        db = SessionLocal()
        log = InspectionLog(
            pass_fail=pass_fail,
            defects_json=json.dumps(final_detections)
        )
        db.add(log)
        db.commit()
        db.close()
    except Exception as e:
        print(f"Background DB write error: {e}")


@router.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    # Shared state for latest-frame buffer
    latest_frame = None
    frame_lock = asyncio.Lock()
    frame_event = asyncio.Event()
    should_run = True

    async def receive_loop():
        """Continuously receives frames, keeping only the latest one."""
        nonlocal latest_frame, should_run
        try:
            while should_run:
                frame_bytes = await websocket.receive_bytes()
                async with frame_lock:
                    latest_frame = frame_bytes
                frame_event.set()  # Signal that a new frame is available
        except WebSocketDisconnect:
            should_run = False
            frame_event.set()  # Unblock process loop
        except Exception:
            should_run = False
            frame_event.set()

    async def process_loop():
        """Grabs the latest frame, runs pipeline in thread, sends result."""
        nonlocal latest_frame, should_run
        frame_count = 0
        try:
            while should_run:
                # Wait for a frame to be available
                await frame_event.wait()
                if not should_run:
                    break

                # Grab the latest frame and clear the buffer
                async with frame_lock:
                    current_frame = latest_frame
                    latest_frame = None
                frame_event.clear()

                if current_frame is None:
                    continue

                # Run pipeline in thread pool (NON-BLOCKING to event loop)
                result = await asyncio.to_thread(_run_pipeline, current_frame)
                out_frame_bytes, metadata, is_lens_found, pass_fail, final_detections = result

                if out_frame_bytes is None:
                    continue

                # Check connection is still alive before sending
                if not should_run:
                    break

                # Send metadata as JSON, then frame as bytes
                await websocket.send_text(json.dumps(metadata))
                await websocket.send_bytes(out_frame_bytes)

                # Background DB write every 30 frames (non-blocking)
                if is_lens_found and frame_count % 30 == 0:
                    asyncio.create_task(_save_to_db(pass_fail, final_detections))

                frame_count += 1

        except WebSocketDisconnect:
            should_run = False
        except Exception as e:
            print(f"Process loop error: {e}")
            should_run = False

    try:
        # Run receive and process loops concurrently
        await asyncio.gather(
            receive_loop(),
            process_loop()
        )
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        print("Client disconnected")
