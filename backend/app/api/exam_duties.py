from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import os
import uuid
from datetime import datetime, date, time

from ..core.database import get_db
from ..api.auth import get_current_user
from ..models.user import User, UserRole
from ..models.exam_duty import ExamDuty, DutyStatus
from ..schemas.exam_duty import ExamDutyCreate, ExamDutyUpdate, ExamDutyResponse, ExamDutyUploadResponse
from ..services.duty_extractor import duty_extractor
from ..services.duty_matcher import duty_matcher
from ..services.duty_scheduler import duty_scheduler
from ..services.exam_duty_parser.ai_parser import ai_parser
from ..services.exam_duty_parser.table_transformer_parser import table_transformer_parser
from ..tasks.duty_tasks import process_exam_duty_upload
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/exam-duties", tags=["Exam Duties"])

UPLOAD_DIR = "uploads/exam_duties"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload", response_model=ExamDutyUploadResponse)
async def upload_exam_duty(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload exam duty schedule (HOD only)"""
    
    if current_user.role not in [UserRole.HOD, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HODs can upload exam duties"
        )
    
    ext = os.path.splitext(file.filename)[1].lower()
    allowed_extensions = [".pdf", ".jpg", ".jpeg", ".png", ".docx", ".doc"]
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not supported. Allowed: {', '.join(allowed_extensions)}"
        )
    
    file_id = str(uuid.uuid4())
    file_path = f"{UPLOAD_DIR}/exam_duty_{current_user.id}_{file_id}{ext}"
    
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    extracted_duties = []
    matched_duties = []
    unmatched = []
    used_ai = False
    ai_confidence = 0.0
    parser_used = "rule-based"
    
    # ============================================
    # STEP 1: Multi-Stage Parser (Image & PDF Pipelines)
    # ============================================
    if table_transformer_parser.is_available():
        try:
            logger.info(f"🤖 Processing with Multi-Stage Parser for: {file_path}")
            tt_result = table_transformer_parser.parse(file_path)
            
            if tt_result.get('success') and tt_result.get('duties'):
                extracted_duties = tt_result.get('duties', [])
                used_ai = True
                parser_used = tt_result.get('stage_used', 'Multi-Stage Parser')
                ai_confidence = tt_result.get('confidence', 0.85)
                logger.info(f"✅ {parser_used} found {len(extracted_duties)} duties (confidence: {ai_confidence:.2f})")
            else:
                logger.info(f"ℹ️ Multi-stage parser returned no duties ({tt_result.get('error')}), trying fallback...")
        except Exception as e:
            logger.error(f"❌ Multi-stage parser error: {str(e)}")
    
    # ============================================
    # STEP 2: Try AI Parser (if Table Transformer failed)
    # ============================================
    if not extracted_duties and ai_parser.is_available():
        try:
            logger.info(f"🤖 Trying AI parser for: {file_path}")
            ai_result = ai_parser.parse(file_path)
            ai_confidence = ai_result.get('confidence', 0.0)
            
            if ai_result.get('success') and ai_result.get('table_detected'):
                if ai_confidence > 0.6:
                    extracted_duties = ai_result.get('duties', [])
                    used_ai = True
                    parser_used = "ai-parser"
                    logger.info(f"✅ AI Parser found {len(extracted_duties)} duties")
                else:
                    logger.info(f"⚠️ AI parser confidence too low ({ai_confidence:.2f}), falling back")
            else:
                logger.info("ℹ️ AI parser did not detect table, falling back")
        except Exception as e:
            logger.error(f"❌ AI parser failed: {str(e)}")
    
    # ============================================
    # STEP 3: Fallback to Rule-Based Parser
    # ============================================
    if not extracted_duties:
        logger.info("📄 Using rule-based parser (fallback)")
        parser_used = "rule-based"
        
        text = ""
        if ext == ".pdf":
            from ..services.pdf_extractor import pdf_extractor
            text = pdf_extractor.extract_text_from_upload(open(file_path, "rb"))
            if not text or len(text) < 50:
                from ..services.ocr_service import ocr_service
                text = ocr_service.extract_text_from_scanned_pdf(file_path)
        elif ext in [".jpg", ".jpeg", ".png"]:
            from ..services.ocr_service import ocr_service
            text = ocr_service.extract_text_from_image(file_path)
        elif ext in [".docx", ".doc"]:
            from ..services.file_extractor import file_extractor
            text = file_extractor.extract_text(file_path)
        
        if not text or len(text.strip()) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract text from file"
            )
        
        extracted_duties = duty_extractor.extract_duties(text)
    
    # ============================================
    # STEP 4: Match Lecturers
    # ============================================
    if extracted_duties:
        matched_duties, unmatched = duty_matcher.match_lecturers(
            extracted_duties,
            current_user.department,
            db
        )
        logger.info(f"Matched: {len(matched_duties)} lecturers, Unmatched: {len(unmatched)}")
    
    # ============================================
    # STEP 5: Create Duties
    # ============================================
    created_duties = []
    conflicts = 0
    
    for duty_data in matched_duties:
        session_val = duty_data.get("session", "Forenoon")
        raw_start_time = duty_data.get("start_time")
        raw_end_time = duty_data.get("end_time")
        
        if not raw_start_time or not raw_end_time:
            if "afternoon" in str(session_val).lower() or "an" in str(session_val).lower() or "pm" in str(session_val).lower():
                start_time_obj = time(14, 0, 0)
                end_time_obj = time(17, 0, 0)
            else:
                start_time_obj = time(9, 30, 0)
                end_time_obj = time(12, 30, 0)
        else:
            def parse_time_val(t_val, fallback):
                if isinstance(t_val, time):
                    return t_val
                if isinstance(t_val, str):
                    for fmt in ["%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M%p", "%I %p"]:
                        try:
                            return datetime.strptime(t_val.strip(), fmt).time()
                        except ValueError:
                            pass
                return fallback
            
            start_time_obj = parse_time_val(raw_start_time, time(9, 30, 0))
            end_time_obj = parse_time_val(raw_end_time, time(12, 30, 0))
        
        # Parse date
        raw_date = duty_data.get("date")
        if isinstance(raw_date, date):
            duty_date_obj = raw_date
        elif isinstance(raw_date, datetime):
            duty_date_obj = raw_date.date()
        elif isinstance(raw_date, str):
            duty_date_obj = None
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"]:
                try:
                    duty_date_obj = datetime.strptime(raw_date.strip(), fmt).date()
                    break
                except ValueError:
                    pass
            if not duty_date_obj:
                duty_date_obj = date.today()
        else:
            duty_date_obj = date.today()
        
        has_conflict = duty_scheduler.check_conflict(
            duty_data["lecturer_id"],
            duty_date_obj,
            start_time_obj,
            end_time_obj,
            db
        )
        
        if has_conflict:
            conflicts += 1
            continue
        
        new_duty = ExamDuty(
            lecturer_id=duty_data["lecturer_id"],
            hod_id=current_user.id,
            department=current_user.department,
            exam_name=duty_data.get("exam_name", "Semester Examination"),
            date=duty_date_obj,
            start_time=start_time_obj,
            end_time=end_time_obj,
            venue=duty_data.get("venue", ""),
            status=DutyStatus.PENDING
        )
        db.add(new_duty)
        db.commit()
        db.refresh(new_duty)
        created_duties.append(new_duty)
        
        duty_scheduler.create_notification_and_reminder(new_duty, db)
    
    # ============================================
    # STEP 6: Return Response
    # ============================================
    return {
        "message": "Exam duties processed",
        "total_extracted": len(extracted_duties),
        "matched": len(matched_duties),
        "created": len(created_duties),
        "conflicts": conflicts,
        "duties": created_duties,
        "unmatched_lecturers": unmatched,
        "ai_used": used_ai,
        "ai_confidence": ai_confidence if used_ai else None,
        "parser": parser_used
    }


# ... rest of existing endpoints (get_my_duties, get_hod_duties, etc.) ...


@router.post("/upload/async")
async def upload_exam_duty_async(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload exam duty schedule asynchronously (HOD only)"""
    
    if current_user.role not in [UserRole.HOD, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HODs can upload exam duties"
        )
    
    ext = os.path.splitext(file.filename)[1].lower()
    allowed_extensions = [".pdf", ".jpg", ".jpeg", ".png", ".docx", ".doc"]
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not supported. Allowed: {', '.join(allowed_extensions)}"
        )
    
    file_id = str(uuid.uuid4())
    file_path = f"{UPLOAD_DIR}/exam_duty_{current_user.id}_{file_id}{ext}"
    
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    # Trigger Celery task
    task = process_exam_duty_upload.delay(file_path, current_user.id)
    
    return {
        "message": "File upload started",
        "task_id": task.id,
        "status": "processing"
    }


@router.get("/upload-status/{task_id}")
async def get_upload_status(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get status of async upload"""
    
    from ..tasks.duty_tasks import process_exam_duty_upload
    
    result = process_exam_duty_upload.AsyncResult(task_id)
    
    if result.pending:
        return {"status": "pending", "message": "Processing..."}
    elif result.failed():
        return {"status": "failed", "message": str(result.info)}
    else:
        return {"status": "completed", "result": result.result}


@router.get("/me", response_model=List[ExamDutyResponse])
async def get_my_duties(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get duties for current lecturer"""
    
    if current_user.role not in [UserRole.LECTURER, UserRole.HOD, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only lecturers can view duties"
        )
    
    duties = db.query(ExamDuty).filter(
        ExamDuty.lecturer_id == current_user.id
    ).order_by(ExamDuty.date.asc()).all()
    
    # Add lecturer and hod names
    result = []
    for duty in duties:
        response = ExamDutyResponse.model_validate(duty)
        lecturer = db.query(User).filter(User.id == duty.lecturer_id).first()
        hod = db.query(User).filter(User.id == duty.hod_id).first()
        response.lecturer_name = lecturer.name if lecturer else None
        response.hod_name = hod.name if hod else None
        result.append(response)
    
    return result


@router.get("/hod", response_model=List[ExamDutyResponse])
async def get_hod_duties(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get duties uploaded by HOD"""
    
    if current_user.role not in [UserRole.HOD, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HODs can view this"
        )
    
    duties = db.query(ExamDuty).filter(
        ExamDuty.hod_id == current_user.id
    ).order_by(ExamDuty.date.desc()).all()
    
    result = []
    for duty in duties:
        response = ExamDutyResponse.model_validate(duty)
        lecturer = db.query(User).filter(User.id == duty.lecturer_id).first()
        hod = db.query(User).filter(User.id == duty.hod_id).first()
        response.lecturer_name = lecturer.name if lecturer else None
        response.hod_name = hod.name if hod else None
        result.append(response)
    
    return result


@router.get("/department", response_model=List[ExamDutyResponse])
async def get_department_duties(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all duties for current user's department"""
    
    if current_user.role not in [UserRole.HOD, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HODs and Admins can view this"
        )
    
    duties = db.query(ExamDuty).filter(
        ExamDuty.department == current_user.department
    ).order_by(ExamDuty.date.desc()).all()
    
    result = []
    for duty in duties:
        response = ExamDutyResponse.model_validate(duty)
        lecturer = db.query(User).filter(User.id == duty.lecturer_id).first()
        hod = db.query(User).filter(User.id == duty.hod_id).first()
        response.lecturer_name = lecturer.name if lecturer else None
        response.hod_name = hod.name if hod else None
        result.append(response)
    
    return result


@router.put("/{duty_id}/confirm", response_model=ExamDutyResponse)
async def confirm_duty(
    duty_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Confirm a duty"""
    
    duty = db.query(ExamDuty).filter(ExamDuty.id == duty_id).first()
    if not duty:
        raise HTTPException(status_code=404, detail="Duty not found")
    
    if duty.lecturer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only confirm your own duties"
        )
    
    duty.status = DutyStatus.CONFIRMED
    db.commit()
    db.refresh(duty)
    
    return duty


@router.get("/upcoming", response_model=List[ExamDutyResponse])
async def get_upcoming_duties(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get upcoming duties for current user"""
    
    from datetime import date
    today = date.today()
    
    duties = db.query(ExamDuty).filter(
        ExamDuty.lecturer_id == current_user.id,
        ExamDuty.date >= today
    ).order_by(ExamDuty.date.asc()).all()
    
    result = []
    for duty in duties:
        response = ExamDutyResponse.model_validate(duty)
        lecturer = db.query(User).filter(User.id == duty.lecturer_id).first()
        hod = db.query(User).filter(User.id == duty.hod_id).first()
        response.lecturer_name = lecturer.name if lecturer else None
        response.hod_name = hod.name if hod else None
        result.append(response)
    
    return result


@router.get("/{duty_id}")
async def get_duty_details(
    duty_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get details of a specific duty"""
    
    duty = db.query(ExamDuty).filter(ExamDuty.id == duty_id).first()
    if not duty:
        raise HTTPException(status_code=404, detail="Duty not found")
    
    # Check permissions
    if current_user.role not in [UserRole.HOD, UserRole.ADMIN]:
        if duty.lecturer_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own duties"
            )
    
    response = ExamDutyResponse.model_validate(duty)
    lecturer = db.query(User).filter(User.id == duty.lecturer_id).first()
    hod = db.query(User).filter(User.id == duty.hod_id).first()
    response.lecturer_name = lecturer.name if lecturer else None
    response.hod_name = hod.name if hod else None
    
    return response


@router.delete("/{duty_id}")
async def delete_duty(
    duty_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a duty (HOD only)"""
    
    if current_user.role not in [UserRole.HOD, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HODs can delete duties"
        )
    
    duty = db.query(ExamDuty).filter(ExamDuty.id == duty_id).first()
    if not duty:
        raise HTTPException(status_code=404, detail="Duty not found")
    
    if duty.hod_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own duties"
        )
    
    db.delete(duty)
    db.commit()
    
    return {"message": "Duty deleted successfully"}