from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import InspectionLog
import csv
import io
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

router = APIRouter(prefix="/export", tags=["export"])

@router.get("/csv")
def export_csv(db: Session = Depends(get_db)):
    logs = db.query(InspectionLog).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Timestamp", "Result", "Defects"])
    
    for log in logs:
        writer.writerow([log.id, log.timestamp.strftime("%Y-%m-%d %H:%M:%S"), log.pass_fail, log.defects_json])
        
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inspection_log.csv"}
    )

@router.get("/pdf")
def export_pdf(db: Session = Depends(get_db)):
    total = db.query(InspectionLog).count()
    passes = db.query(InspectionLog).filter(InspectionLog.pass_fail == "Pass").count()
    fails = db.query(InspectionLog).filter(InspectionLog.pass_fail == "Fail").count()
    
    pdf_path = "/tmp/report.pdf" if os.name != 'nt' else "report.pdf" # fallback for windows
    
    c = canvas.Canvas(pdf_path, pagesize=letter)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, 750, "Optical Lens Defect Detection Report")
    
    c.setFont("Helvetica", 14)
    c.drawString(50, 700, f"Total Inspections: {total}")
    c.drawString(50, 670, f"Passed: {passes}")
    c.drawString(50, 640, f"Failed: {fails}")
    
    if total > 0:
        c.drawString(50, 610, f"Yield Rate: {(passes/total)*100:.2f}%")
        
    c.save()
    
    return FileResponse(pdf_path, filename="inspection_report.pdf", media_type="application/pdf")
