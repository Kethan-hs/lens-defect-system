from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from db.database import Base

class InspectionLog(Base):
    __tablename__ = "inspections"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    pass_fail = Column(String, index=True)
    defects_json = Column(String) # Store JSON string of detections
    frame_path = Column(String, nullable=True) # Optional path to saved frame
