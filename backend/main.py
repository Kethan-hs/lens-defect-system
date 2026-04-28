from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db.database import engine, Base
from routes import stream, inspections, export

# Create DB tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Optical Lens Defect Detection API")

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://lens-defect-system.vercel.app",  # your Vercel URL
        "http://localhost:3000",                    # keep for local dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(stream.router)
app.include_router(inspections.router)
app.include_router(export.router)

@app.get("/")
def read_root():
    return {"message": "Lens Defect System API is running"}
