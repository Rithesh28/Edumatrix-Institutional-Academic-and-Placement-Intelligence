from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict
import os
import uuid

from ..core.database import get_db
from ..api.auth import get_current_user
from ..models.user import User, UserRole
from ..services.pdf_extractor import pdf_extractor
from ..services.file_extractor import file_extractor
from ..services.ocr_service import ocr_service
from ..services.ner_extractor import ner_extractor
from ..services.date_extractor import date_extractor

router = APIRouter(prefix="/upload", tags=["Upload"])

UPLOAD_DIR = "/tmp/uploads"
try:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
except PermissionError:
    UPLOAD_DIR = "/tmp/uploads"
    os.makedirs(UPLOAD_DIR, exist_ok=True)

# Allowed file types
ALLOWED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png", ".docx", ".doc", ".txt"]
ALLOWED_MIME_TYPES = [
    "application/pdf",
    "image/jpeg", "image/png",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain"
]


@router.post("/syllabus")
async def upload_syllabus(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload syllabus PDF (Lecturer only) - Extracts text for study buddy"""
    
    if current_user.role not in [UserRole.LECTURER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only lecturers can upload syllabus"
        )
    
    # Check file type
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Save file
    file_id = str(uuid.uuid4())
    file_path = f"{UPLOAD_DIR}/syllabus_{current_user.id}_{file_id}{ext}"
    
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    # Extract text based on file type
    text = ""
    extracted_by = ""
    
    if ext == ".pdf":
        # Try pdfplumber first (for typed PDFs)
        text = pdf_extractor.extract_text_from_upload(open(file_path, "rb"))
        extracted_by = "pdfplumber"
        
        # If no text, try OCR (scanned PDF)
        if not text or len(text) < 50:
            text = ocr_service.extract_text_from_scanned_pdf(file_path)
            extracted_by = "ocr (scanned PDF)"
    
    elif ext in [".jpg", ".jpeg", ".png"]:
        text = ocr_service.extract_text_from_image(file_path)
        extracted_by = "ocr (image)"
    
    elif ext in [".docx", ".doc"]:
        text = file_extractor.extract_text(file_path)
        extracted_by = "file_extractor"
    
    if not text or len(text.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not extract text from file. Extracted by: {extracted_by}"
        )
    
    # Extract dates and entities
    structured_data = ner_extractor.extract_exam_circular_info(text)
    raw_dates = ner_extractor.extract_dates(text)
    entities = pdf_extractor.extract_entities_from_text(text)
    
    return {
        "message": "Syllabus uploaded successfully",
        "file_path": file_path,
        "text_length": len(text),
        "extracted_by": extracted_by,
        "preview": text[:500] + "..." if len(text) > 500 else text,
        "structured_data": structured_data,
        "extracted_dates": raw_dates,
        "extracted_entities": entities
    }


@router.post("/circular")
async def upload_circular_pdf(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload circular (PDF, Image, DOCX) - Extracts text, dates, and auto-fills fields"""
    
    if current_user.role not in [UserRole.LECTURER, UserRole.HOD, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only lecturers and HODs can upload circulars"
        )
    
    # Check file type
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Save file
    file_id = str(uuid.uuid4())
    file_path = f"{UPLOAD_DIR}/circular_{current_user.id}_{file_id}{ext}"
    
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    # Extract text based on file type
    text = ""
    extracted_by = ""
    
    if ext == ".pdf":
        # Try pdfplumber first (for typed PDFs)
        text = pdf_extractor.extract_text_from_upload(open(file_path, "rb"))
        extracted_by = "pdfplumber"
        
        # If no text, try OCR (scanned PDF)
        if not text or len(text) < 50:
            text = ocr_service.extract_text_from_scanned_pdf(file_path)
            extracted_by = "ocr (scanned PDF)"
    
    elif ext in [".jpg", ".jpeg", ".png"]:
        text = ocr_service.extract_text_from_image(file_path)
        extracted_by = "ocr (image)"
    
    elif ext in [".docx", ".doc"]:
        text = file_extractor.extract_text(file_path)
        extracted_by = "file_extractor"
    
    elif ext == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        extracted_by = "text_reader"
    
    if not text or len(text.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not extract text from file. Extracted by: {extracted_by}"
        )
    
    # Use NER & Date Extractor for structured extraction
    structured_data = ner_extractor.extract_exam_circular_info(text)
    raw_dates = ner_extractor.extract_dates(text)
    entities = pdf_extractor.extract_entities_from_text(text)
    
    # Determine future due date
    future_dates = date_extractor.extract_future_dates(text)
    suggested_due_date = None
    
    if future_dates:
        latest_dt = max(future_dates, key=lambda x: x[1])[1]
        suggested_due_date = latest_dt.strftime("%Y-%m-%dT23:59")
    elif raw_dates and len(raw_dates) > 0:
        date_item = raw_dates[0]
        raw_val = date_item.get("text") if isinstance(date_item, dict) else str(date_item)
        parsed_dt = date_extractor._parse_date(raw_val)
        if parsed_dt:
            suggested_due_date = parsed_dt.strftime("%Y-%m-%dT23:59")
    
    # Auto-detect circular type
    text_lower = text.lower()
    auto_type = "general"
    if any(k in text_lower for k in ['exam', 'test', 'cie', 'mid term', 'semester examination', 'schedule', 'timetable']):
        auto_type = "exam"
    elif any(k in text_lower for k in ['assignment', 'homework', 'submission', 'project', 'lab report']):
        auto_type = "assignment"
        
    # Suggested Title
    suggested_title = structured_data.get("title") or ""
    if not suggested_title and file.filename:
        suggested_title = file.filename.rsplit('.', 1)[0].replace('_', ' ')
    if not suggested_title:
        lines = [line.strip() for line in text.split('\n') if len(line.strip()) > 3]
        if lines:
            suggested_title = lines[0][:80]
    
    return {
        "message": "Circular extracted successfully",
        "file_path": file_path,
        "text": text,
        "extracted_text_length": len(text),
        "extracted_by": extracted_by,
        "preview": text[:500] + "..." if len(text) > 500 else text,
        "structured_data": structured_data,
        "extracted_dates": raw_dates,
        "extracted_entities": entities,
        "suggested_title": suggested_title or "Circular Announcement",
        "suggested_due_date": suggested_due_date,
        "suggested_type": auto_type
    }


@router.post("/exam-duty")
async def upload_exam_duty_pdf(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload exam duty (PDF, Image, DOCX) - Extracts duty schedule"""
    
    if current_user.role not in [UserRole.LECTURER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only lecturers and admins can upload exam duties"
        )
    
    # Check file type
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Save file
    file_id = str(uuid.uuid4())
    file_path = f"{UPLOAD_DIR}/exam_duty_{current_user.id}_{file_id}{ext}"
    
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    # Extract text based on file type
    text = ""
    extracted_by = ""
    
    if ext == ".pdf":
        text = pdf_extractor.extract_text_from_upload(open(file_path, "rb"))
        extracted_by = "pdfplumber"
        if not text or len(text) < 50:
            text = ocr_service.extract_text_from_scanned_pdf(file_path)
            extracted_by = "ocr (scanned PDF)"
    elif ext in [".jpg", ".jpeg", ".png"]:
        text = ocr_service.extract_text_from_image(file_path)
        extracted_by = "ocr (image)"
    elif ext in [".docx", ".doc"]:
        text = file_extractor.extract_text(file_path)
        extracted_by = "file_extractor"
    
    if not text or len(text.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not extract text from file. Extracted by: {extracted_by}"
        )
    
    # Extract duty schedule using NER
    structured_data = ner_extractor.extract_exam_circular_info(text)
    raw_dates = ner_extractor.extract_dates(text)
    entities = pdf_extractor.extract_entities_from_text(text)
    
    return {
        "message": "Exam duty uploaded successfully",
        "file_path": file_path,
        "extracted_text_length": len(text),
        "extracted_by": extracted_by,
        "preview": text[:500] + "..." if len(text) > 500 else text,
        "extracted_duties": structured_data,
        "extracted_dates": raw_dates,
        "extracted_entities": entities,
        "suggested_exam_dates": raw_dates[:5] if raw_dates else []
    }


@router.post("/assignment")
async def upload_assignment_pdf(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload assignment (PDF, Image, DOCX) - Extracts due dates and requirements"""
    
    if current_user.role not in [UserRole.LECTURER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only lecturers can upload assignments"
        )
    
    # Check file type
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Save file
    file_id = str(uuid.uuid4())
    file_path = f"{UPLOAD_DIR}/assignment_{current_user.id}_{file_id}{ext}"
    
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    # Extract text based on file type
    text = ""
    extracted_by = ""
    
    if ext == ".pdf":
        text = pdf_extractor.extract_text_from_upload(open(file_path, "rb"))
        extracted_by = "pdfplumber"
        if not text or len(text) < 50:
            text = ocr_service.extract_text_from_scanned_pdf(file_path)
            extracted_by = "ocr (scanned PDF)"
    elif ext in [".jpg", ".jpeg", ".png"]:
        text = ocr_service.extract_text_from_image(file_path)
        extracted_by = "ocr (image)"
    elif ext in [".docx", ".doc"]:
        text = file_extractor.extract_text(file_path)
        extracted_by = "file_extractor"
    
    if not text or len(text.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not extract text from file. Extracted by: {extracted_by}"
        )
    
    # Extract assignment info using NER
    structured_data = ner_extractor.extract_exam_circular_info(text)
    raw_dates = ner_extractor.extract_dates(text)
    
    # Extract suggested due date
    suggested_due_date = None
    if raw_dates and len(raw_dates) > 0:
        suggested_due_date = raw_dates[0].get("text") if isinstance(raw_dates[0], dict) else raw_dates[0]
    
    return {
        "message": "Assignment uploaded successfully",
        "file_path": file_path,
        "extracted_text_length": len(text),
        "extracted_by": extracted_by,
        "preview": text[:500] + "..." if len(text) > 500 else text,
        "structured_data": structured_data,
        "extracted_dates": raw_dates,
        "suggested_due_date": suggested_due_date
    }