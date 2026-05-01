from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from routes.stream import router as stream_router
from routes.inspections import router as inspections_router
from routes.export import router as export_router

from db.database import engine, Base

# Create DB tables on startup
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load models on startup to avoid cold start delays."""
    try:
        from pipeline.defect_detector import _load_model as load_defect_model
        from pipeline.lens_segmentor import _load_model as load_seg_model

        print("[Startup] Pre-loading models...")
        load_defect_model()
        load_seg_model()
        print("[Startup] Models loaded successfully")
    except Exception as e:
        print(f"[Startup] Model loading failed: {e}")
    yield

app = FastAPI(title="Optical Lens Defect Detection API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stream_router)
app.include_router(inspections_router)
app.include_router(export_router)

@app.get("/")
def read_root():
    return {"message": "Lens Defect System API is running"}
