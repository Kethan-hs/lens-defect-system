# Optical Lens Defect Detection System

The Optical Lens Defect Detection System is a real-time, computer vision-powered QA manufacturing tool designed to identify and log surface defects on optical lenses. The application captures a live camera feed, uses classical computer vision to isolate the lens region, and then runs a trained YOLOv8m-OBB (Oriented Bounding Box) machine learning model on that cropped region to detect four specific defect classes: bubble, crack, dots, and scratch. The results, including annotated frames and Pass/Fail decisions, are streamed to a modern React dashboard while historical data is logged to a SQLite database for trend analysis and PDF/CSV reporting.

## Architecture

```text
Live Camera Feed
      │
      ▼
┌─────────────────────────────┐
│  Step 1: Lens Isolation     │  ← Classical CV (HoughCircles)
│  Detect & crop lens ROI     │
└────────────┬────────────────┘
             │ (only if lens detected)
             ▼
┌─────────────────────────────┐
│  Step 2: Defect Detection   │  ← YOLOv8m-OBB inference
│  Classify: bubble/crack/    │
│  dots/scratch               │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│  Step 3: Decision + Output  │  ← Pass/Fail logic & Annotation
│  Log to SQLite & stream     │
└─────────────────────────────┘
             │
             ▼
┌─────────────────────────────┐
│  React Dashboard            │  ← Live feed & Analytics
└─────────────────────────────┘
```

## Prerequisites
- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- Trained YOLOv8m-OBB weights file (`best.pt`)
- A connected USB camera (or virtual camera)

## Model Placement
Place your trained YOLOv8m-OBB weights file in the following directory before running:
`backend/models/best.pt`

## Quick Start (Docker)
1. Place your model at `backend/models/best.pt`.
2. Build and start the containers:
   ```bash
   cd docker
   docker-compose up --build
   ```
3. Open `http://localhost:3000` in your browser.

## Quick Start (Manual)

### Backend
```bash
cd backend
python -m venv venv
# On Windows: venv\Scripts\activate
# On macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Configuration
| Variable | Default | Description |
|---|---|---|
| `CAMERA_INDEX` | `0` | OpenCV camera index |
| `CONFIDENCE_THRESHOLD` | `0.5` | Min OBB detection confidence |
| `MODEL_PATH` | `backend/models/best.pt` | Path to YOLOv8m-OBB weights |
| `DATABASE_URL` | `sqlite:///./lens_inspections.db` | SQLite DB path |
| `VITE_API_URL` | `http://localhost:8000` | Frontend → backend URL |

## Dashboard Features
- **Live Camera Feed**: Real-time WebSocket stream displaying the annotated frame and current Pass/Fail status.
- **Current Detections**: A side panel listing all defects identified in the current frame with their confidence scores.
- **Defect Distribution**: A grid showing the total count of each defect type (bubble, crack, dots, scratch) recorded so far.
- **Yield Trend**: A line chart tracking the rolling Pass Rate % over the last 50 inspections.
- **Inspection Table**: A paginated history log of all inspections with a "Details" modal showing raw JSON defect data.
- **Export Panel**: Buttons to generate and download a CSV log or a PDF summary report.

## Pipeline Explanation
1. **Lens Isolation**: The system reads a frame from the camera, converts it to grayscale, and applies a blur. It uses OpenCV's Hough Circle Transform to find the circular shape of the lens and crops out the background, leaving a Region of Interest (ROI).
2. **Defect Detection**: The YOLOv8m-OBB model processes only the cropped ROI. It looks for oriented bounding boxes that match the patterns of bubbles, cracks, dots, or scratches.
3. **Decision & Output**: If any defects are found above the confidence threshold, the lens is marked "Fail"; otherwise "Pass". The original frame is annotated with the bounding boxes and text, saved to the database (if a lens is present), and streamed to the UI.

## Known Limitations
- **Lighting Sensitivity**: Step 1 (classical CV using HoughCircles) is highly sensitive to reflections and shadows. Consistent, diffuse lighting is required for reliable lens isolation.
- **Defect Sub-classes**: The "dots" class is generally harder to detect accurately than larger scratches or cracks due to its small pixel area.

## Future Improvements
- **GPU Acceleration**: Update the Dockerfile to support NVIDIA CUDA for faster YOLOv8 inference.
- **Multi-camera Support**: Scale the backend and frontend to handle multiple camera feeds simultaneously on different assembly lines.
- **Active Learning Loop**: Add a UI feature to flag false positives/negatives and save those frames to a dataset folder for future model retraining.
