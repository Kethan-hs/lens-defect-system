"""
WebSocket stream endpoint.

Pipeline timing:
  - Lens segmentation  → every SEG_INTERVAL seconds (default 3s)
  - Defect detection   → every frame on cached ROI
  - DB write           → every DB_WRITE_INTERVAL seconds (default 5s)

Thread-safety:
  - PipelineState is mutated only inside asyncio.to_thread() — one frame
    processed at a time (process_loop awaits each result before continuing),
    so there is no concurrent mutation.
  - _save_to_db runs in a thread via asyncio.to_thread() to avoid blocking
    the event loop with synchronous SQLAlchemy.

JSON safety:
  - All floats/ints from numpy are cast to Python native types before
    json.dumps() to prevent "Object of type float32 is not serializable".
"""

import asyncio
import json
import os
import time
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from db.database              import SessionLocal
from db.models                import InspectionLog
from pipeline.decision        import make_decision_and_annotate
from pipeline.defect_detector import detect_defects
from pipeline.lens_segmentor  import segment_lens

router = APIRouter()

SEG_INTERVAL      = float(os.getenv("SEG_INTERVAL",      "3.0"))
DB_WRITE_INTERVAL = float(os.getenv("DB_WRITE_INTERVAL", "5.0"))

# Railway / cloud proxies close idle WebSocket connections after ~30s.
# We send a ping every 20s to keep the connection alive.
WS_PING_INTERVAL  = float(os.getenv("WS_PING_INTERVAL",  "20.0"))


# ── JSON-safe serializer ──────────────────────────────────────────────────────
def _to_json_safe(obj):
    """
    Recursively convert numpy scalars / arrays to native Python types so
    json.dumps() never crashes with "float32 is not JSON serializable".
    """
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_json_safe(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


# ── Per-connection pipeline state ─────────────────────────────────────────────
class PipelineState:
    def __init__(self):
        self.last_seg_time : float              = 0.0
        self.cached_roi    : Optional[np.ndarray] = None
        self.cached_bbox   : list               = []
        self.cached_mask   : Optional[np.ndarray] = None
        self.cached_polygon: list               = []
        self.is_lens_found : bool               = False
        self.last_db_write : float              = 0.0   # per-connection, reset on reconnect


# ── Synchronous pipeline (runs in thread pool) ────────────────────────────────
def _run_pipeline(frame_bytes: bytes, state: PipelineState):
    try:
        nparr = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            return None, None, "No Lens", []

        now = time.monotonic()

        # Stage 1 — lens segmentation (throttled)
        if now - state.last_seg_time >= SEG_INTERVAL:
            found, roi, bbox, mask, poly = segment_lens(frame)
            state.last_seg_time  = now
            state.is_lens_found  = found
            state.cached_roi     = roi
            state.cached_bbox    = bbox
            state.cached_mask    = mask
            state.cached_polygon = poly

        # Stage 2 — defect detection (every frame)
        detections = []
        if state.is_lens_found and state.cached_roi is not None:
            detections = detect_defects(state.cached_roi)

    # Stage 3 — annotate + decide
    annotated, pass_fail, mapped = make_decision_and_annotate(
        frame,
        state.is_lens_found,
        detections,
        state.cached_bbox,
        state.cached_mask,
        state.cached_polygon,
    )

    # Seg-refresh countdown overlay
    age  = now - state.last_seg_time
    till = max(0.0, SEG_INTERVAL - age)
    cv2.putText(
        annotated,
        f"Seg refresh: {till:.1f}s",
        (10, annotated.shape[0] - 12),
        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1,
    )

    _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])

    # Build metadata — ensure all values are JSON-serialisable
    metadata = _to_json_safe({
        "lens_detected": state.is_lens_found,
        "is_lens_found": state.is_lens_found,
        "lens_bbox":     state.cached_bbox,
        "pass_fail":     pass_fail,
        "detections":    mapped,
        "defects":       mapped,
        "seg_age_s":     round(age, 1),
    })

    return buf.tobytes(), metadata, pass_fail, mapped
    except Exception as e:
        print(f"[Pipeline] Error: {e}")
        import traceback
        traceback.print_exc()
        return None, None, "Error", []


# ── Blocking DB write (called via asyncio.to_thread) ─────────────────────────
def _write_db(pass_fail: str, detections: list):
    """Synchronous DB write — always called in a thread, never on event loop."""
    db = SessionLocal()
    try:
        db.add(InspectionLog(
            pass_fail    = pass_fail,
            defects_json = json.dumps(_to_json_safe(detections)),
        ))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[DB] Write error: {e}")
    finally:
        db.close()


# ── WebSocket endpoint ────────────────────────────────────────────────────────
@router.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[WS] Client connected")

    latest_frame: Optional[bytes] = None
    frame_lock   = asyncio.Lock()
    frame_event  = asyncio.Event()
    should_run   = True
    state        = PipelineState()

    # ── Receive loop ──────────────────────────────────────────────────────────
    async def receive_loop():
        nonlocal latest_frame, should_run
        try:
            while should_run:
                data = await websocket.receive_bytes()
                async with frame_lock:
                    latest_frame = data
                frame_event.set()
        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"[WS] Receive error: {e}")
        finally:
            should_run = False
            frame_event.set()

    # ── Ping loop — keeps Railway proxy alive ─────────────────────────────────
    async def ping_loop():
        nonlocal should_run
        try:
            while should_run:
                await asyncio.sleep(WS_PING_INTERVAL)
                if should_run:
                    await websocket.send_text(json.dumps({"type": "ping"}))
        except Exception:
            pass

# ── Process loop ──────────────────────────────────────────────────────────
    async def process_loop():
        nonlocal latest_frame, should_run
        try:
            while should_run:
                await frame_event.wait()
                if not should_run:
                    break

                async with frame_lock:
                    current      = latest_frame
                    latest_frame = None
                frame_event.clear()

                if current is None:
                    continue

                # Run blocking pipeline in thread pool
                try:
                    out_bytes, metadata, pass_fail, dets = await asyncio.to_thread(
                        _run_pipeline, current, state
                    )
                except Exception as e:
                    print(f"[WS] Pipeline error: {e}")
                    continue

                if out_bytes is None or not should_run:
                    continue

                try:
                    await websocket.send_text(json.dumps(metadata))
                    await websocket.send_bytes(out_bytes)
                except Exception as e:
                    print(f"[WS] Send error: {e}")
                    continue

                # Throttled DB write (also in thread pool — non-blocking)
                now = time.monotonic()
                if (state.is_lens_found
                        and now - state.last_db_write >= DB_WRITE_INTERVAL):
                    state.last_db_write = now
                    asyncio.create_task(
                        asyncio.to_thread(_write_db, pass_fail, dets)
                    )

        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"[WS] Process error: {e}")
        finally:
            should_run = False

    try:
        await asyncio.gather(receive_loop(), process_loop(), ping_loop())
    except Exception as e:
        print(f"[WS] Fatal: {e}")
    finally:
        print("[WS] Client disconnected")
