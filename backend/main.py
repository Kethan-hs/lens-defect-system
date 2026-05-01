from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.stream import router as stream_router
from routes.inspections import router as inspections_router
from routes.export import router as export_router

from db.database import engine, Base

# Create DB tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Optical Lens Defect Detection API")

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
