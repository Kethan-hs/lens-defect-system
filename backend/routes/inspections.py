from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from db.database import get_db
from db.models import InspectionLog
import json

router = APIRouter(prefix="/inspections", tags=["inspections"])

@router.get("/")
def get_inspections(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    logs = db.query(InspectionLog).order_by(InspectionLog.timestamp.desc()).offset(skip).limit(limit).all()
    return logs

@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    # Total Pass/Fail
    total_logs = db.query(InspectionLog).count()
    pass_count = db.query(InspectionLog).filter(InspectionLog.pass_fail == "Pass").count()
    fail_count = db.query(InspectionLog).filter(InspectionLog.pass_fail == "Fail").count()
    
    # Class counts
    class_counts = {
        "bubble": 0,
        "crack": 0,
        "dots": 0,
        "scratch": 0
    }
    
    logs = db.query(InspectionLog.defects_json).filter(InspectionLog.pass_fail == "Fail").all()
    for log in logs:
        try:
            defects = json.loads(log[0])
            for d in defects:
                cls = d.get("class")
                if cls in class_counts:
                    class_counts[cls] += 1
                else:
                    class_counts[cls] = 1
        except json.JSONDecodeError:
            pass
            
    return {
        "total": total_logs,
        "pass": pass_count,
        "fail": fail_count,
        "defect_counts": class_counts
    }
