from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File as FastAPIFile, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import os
import logging
from datetime import datetime, timedelta

from ..core.database import get_db
from ..api.auth import get_current_user
from ..models.user import User, UserRole
from ..models.circular import Circular, CircularType
from ..models.file import File
from ..models.notification import Notification
from ..models.reminder import Reminder, ReminderType, ReminderStatus
from ..schemas.circular import CircularCreate, CircularUpdate, CircularResponse
from ..services.reminder_scheduler import reminder_scheduler
from ..services.file_storage.file_service import file_service
from ..services.file_storage.text_extractor import text_extractor
from ..services.date_extractor import date_extractor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/circulars", tags=["Circulars"])


@router.post("/", response_model=CircularResponse)
async def create_circular(
    circular: CircularCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new circular (Lecturer only) - Notifications ONLY for STUDENTS"""
    
    if current_user.role not in [UserRole.LECTURER, UserRole.HOD, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only lecturers, HODs, and admins can create circulars"
        )
    
    # Create circular
    new_circular = Circular(
        lecturer_id=current_user.id,
        type=circular.type,
        title=circular.title,
        content=circular.content,
        due_date=circular.due_date,
        file_id=circular.file_id
    )
    
    # Get file type if file_id is provided
    if circular.file_id:
        file = db.query(File).filter(File.id == circular.file_id).first()
        if file:
            if file.mime_type.startswith('image/'):
                new_circular.file_type = 'image'
            elif file.mime_type == 'application/pdf':
                new_circular.file_type = 'pdf'
            elif file.mime_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
                new_circular.file_type = 'document'
            else:
                new_circular.file_type = 'other'
    
    db.add(new_circular)
    db.commit()
    db.refresh(new_circular)
    
    # Create notifications for students
    students = db.query(User).filter(
        User.role == UserRole.STUDENT, 
        User.is_active == True
    ).all()
    
    type_emoji = {
        "exam": "📝",
        "assignment": "📚",
        "general": "📢"
    }
    emoji = type_emoji.get(circular.type.value, "📢")
    
    notification_title = f"{emoji} New {circular.type.value.capitalize()} Circular"
    notification_message = f"{circular.title} - Posted by {current_user.name}"
    
    if circular.due_date:
        due_date_str = circular.due_date.strftime("%d %b %Y")
        notification_message += f" (Due: {due_date_str})"
    
    for student in students:
        new_notification = Notification(
            user_id=student.id,
            type="circular",
            title=notification_title,
            message=notification_message,
            reference_id=new_circular.id,
            is_read=False
        )
        db.add(new_notification)
    
    db.commit()
    
    # Schedule reminders if due date exists
    if new_circular.due_date:
        reminder_scheduler.schedule_reminders(new_circular.id, new_circular.due_date)
    
    # Build response with file details
    result = CircularResponse.model_validate(new_circular)
    result.lecturer_name = current_user.name
    
    if new_circular.file_id:
        file = db.query(File).filter(File.id == new_circular.file_id).first()
        if file:
            result.file_details = {
                "id": str(file.id),
                "filename": file.filename,
                "file_size": file.file_size,
                "mime_type": file.mime_type,
                "download_url": f"/files/{file.id}/download",
                "preview_url": f"/files/{file.id}/preview" if file.mime_type.startswith('image/') or file.mime_type == 'application/pdf' else None
            }
    
    return result


@router.post("/upload", response_model=CircularResponse)
async def create_circular_with_file(
    file: UploadFile = FastAPIFile(...),
    type: str = Form("general"),
    title: str = Form(...),
    content: str = Form(""),
    due_date: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a circular with file attachment - Auto-extracts dates from file"""
    
    if current_user.role not in [UserRole.LECTURER, UserRole.HOD, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only lecturers, HODs, and admins can create circulars"
        )
    
    try:
        # Read file content and get size
        file_content = await file.read()
        file_size = len(file_content)
        logger.info(f"📄 Received file: {file.filename} ({file_size} bytes)")
        
        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty"
            )
        
        # Extract text from file for date extraction
        extracted_text = ""
        auto_due_date = None
        all_dates = []
        
        try:
            text_result = text_extractor.extract_text(
                file_path=file.filename,
                content=file_content
            )
            if text_result['success'] and text_result['text']:
                extracted_text = text_result['text']
                logger.info(f"📝 Extracted {len(extracted_text)} characters from file")
                
                all_future_dates = date_extractor.extract_future_dates(extracted_text)
                if all_future_dates:
                    logger.info(f"📅 Found {len(all_future_dates)} future dates:")
                    for date_str, dt in all_future_dates:
                        days_until = (dt - datetime.now()).days
                        logger.info(f"   - {date_str}: {dt.strftime('%Y-%m-%d')} ({days_until} days from now)")
                        all_dates.append({
                            'date_string': date_str,
                            'date': dt,
                            'days_until': days_until
                        })
                    
                    latest_date = max(all_future_dates, key=lambda x: x[1])
                    auto_due_date = latest_date[1]
                    logger.info(f"📅 Primary due date set to: {auto_due_date}")
                else:
                    logger.info("ℹ️ No future dates found in file")
            else:
                logger.warning(f"⚠️ Text extraction failed: {text_result.get('error')}")
                
        except Exception as e:
            logger.warning(f"Could not extract text from file: {str(e)}")
        
        # Parse manual due date
        due_date_parsed = None
        if due_date:
            try:
                due_date_parsed = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                logger.info(f"📅 Manual due date: {due_date_parsed}")
            except Exception as e:
                logger.warning(f"Could not parse due date: {e}")
        
        # Use auto-extracted date if manual not provided
        if not due_date_parsed and auto_due_date:
            due_date_parsed = auto_due_date
            logger.info(f"✅ Using auto-extracted due date: {due_date_parsed}")
        
        # Reset file pointer before uploading to MinIO
        await file.seek(0)
        
        # Upload file to MinIO
        result = await file_service.upload_file(
            db=db,
            file=file,
            uploaded_by=current_user,
            title=title or file.filename,
            description=content or f"Attachment for circular: {title}",
            file_type="circular",
            department=current_user.department,
            extra_data={
                "extracted_text_length": len(extracted_text),
                "auto_extracted_date": auto_due_date.isoformat() if auto_due_date else None,
                "manual_due_date": due_date_parsed.isoformat() if due_date_parsed else None,
                "all_dates": [
                    {
                        "date_string": d['date_string'],
                        "date": d['date'].isoformat(),
                        "days_until": d['days_until']
                    } for d in all_dates
                ] if all_dates else []
            }
        )
        
        if not result['success']:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload file"
            )
        
        uploaded_file = db.query(File).filter(File.id == result['file'].id).first()
        if not uploaded_file:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File record not found after upload"
            )
        
        # Create circular with file reference
        new_circular = Circular(
            lecturer_id=current_user.id,
            type=CircularType(type) if type in ['exam', 'assignment', 'general'] else CircularType.GENERAL,
            title=title,
            content=content or "View attached file for details.",
            due_date=due_date_parsed,
            file_id=uploaded_file.id,
            file_type=uploaded_file.mime_type.split('/')[0] if '/' in uploaded_file.mime_type else 'other'
        )
        
        db.add(new_circular)
        db.commit()
        db.refresh(new_circular)
        
        # ============================================
        # CREATE NOTIFICATIONS FOR STUDENTS
        # ============================================
        students = db.query(User).filter(
            User.role == UserRole.STUDENT, 
            User.is_active == True
        ).all()
        
        type_emoji = {
            "exam": "📝",
            "assignment": "📚",
            "general": "📢"
        }
        emoji = type_emoji.get(type, "📢")
        
        notification_title = f"{emoji} New {type.capitalize()} Circular"
        notification_message = f"{title} - Posted by {current_user.name}"
        
        if due_date_parsed:
            notification_message += f" (Due: {due_date_parsed.strftime('%d %b %Y')})"
            if auto_due_date and not due_date:
                notification_message += " (Auto-detected)"
        elif auto_due_date:
            notification_message += f" (Auto-detected due: {auto_due_date.strftime('%d %b %Y')})"
        
        for student in students:
            new_notification = Notification(
                user_id=student.id,
                type="circular",
                title=notification_title,
                message=notification_message,
                reference_id=new_circular.id,
                is_read=False
            )
            db.add(new_notification)
        
        db.commit()
        
        # ============================================
        # SCHEDULE REMINDERS FOR STUDENTS
        # ============================================
        if new_circular.due_date:
            reminder_scheduler.schedule_reminders(new_circular.id, new_circular.due_date)
        
        # Build response
        response = CircularResponse.model_validate(new_circular)
        response.lecturer_name = current_user.name
        
        # Add file details to response
        file_obj = db.query(File).filter(File.id == new_circular.file_id).first()
        if file_obj:
            response.file_details = {
                "id": str(file_obj.id),
                "filename": file_obj.filename,
                "file_size": file_obj.file_size,
                "mime_type": file_obj.mime_type,
                "download_url": f"/files/{file_obj.id}/download",
                "preview_url": f"/files/{file_obj.id}/preview" if file_obj.mime_type.startswith('image/') or file_obj.mime_type == 'application/pdf' else None
            }
            logger.info(f"✅ File attached to circular: {file_obj.filename} ({file_obj.file_size} bytes)")
        
        return response
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Circular upload failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/", response_model=List[CircularResponse])
async def get_all_circulars(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all circulars (ordered by newest first)"""
    
    circulars = db.query(Circular).order_by(Circular.created_at.desc()).offset(skip).limit(limit).all()
    
    result = []
    for circ in circulars:
        lecturer = db.query(User).filter(User.id == circ.lecturer_id).first()
        circ_dict = CircularResponse.model_validate(circ)
        circ_dict.lecturer_name = lecturer.name if lecturer else None
        
        if circ.file_id:
            file = db.query(File).filter(File.id == circ.file_id).first()
            if file:
                circ_dict.file_details = {
                    "id": str(file.id),
                    "filename": file.filename,
                    "file_size": file.file_size,
                    "mime_type": file.mime_type,
                    "download_url": f"/files/{file.id}/download",
                    "preview_url": f"/files/{file.id}/preview" if file.mime_type.startswith('image/') or file.mime_type == 'application/pdf' else None
                }
        
        result.append(circ_dict)
    
    return result


@router.get("/{circular_id}", response_model=CircularResponse)
async def get_circular(
    circular_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a single circular by ID"""
    
    circular = db.query(Circular).filter(Circular.id == circular_id).first()
    if not circular:
        raise HTTPException(status_code=404, detail="Circular not found")
    
    lecturer = db.query(User).filter(User.id == circular.lecturer_id).first()
    result = CircularResponse.model_validate(circular)
    result.lecturer_name = lecturer.name if lecturer else None
    
    if circular.file_id:
        file = db.query(File).filter(File.id == circular.file_id).first()
        if file:
            result.file_details = {
                "id": str(file.id),
                "filename": file.filename,
                "file_size": file.file_size,
                "mime_type": file.mime_type,
                "download_url": f"/files/{file.id}/download",
                "preview_url": f"/files/{file.id}/preview" if file.mime_type.startswith('image/') or file.mime_type == 'application/pdf' else None
            }
    
    return result


@router.get("/type/{circular_type}", response_model=List[CircularResponse])
async def get_circulars_by_type(
    circular_type: CircularType,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get circulars filtered by type"""
    
    circulars = db.query(Circular).filter(Circular.type == circular_type).order_by(Circular.created_at.desc()).offset(skip).limit(limit).all()
    
    result = []
    for circ in circulars:
        lecturer = db.query(User).filter(User.id == circ.lecturer_id).first()
        circ_dict = CircularResponse.model_validate(circ)
        circ_dict.lecturer_name = lecturer.name if lecturer else None
        
        if circ.file_id:
            file = db.query(File).filter(File.id == circ.file_id).first()
            if file:
                circ_dict.file_details = {
                    "id": str(file.id),
                    "filename": file.filename,
                    "file_size": file.file_size,
                    "mime_type": file.mime_type,
                    "download_url": f"/files/{file.id}/download",
                    "preview_url": f"/files/{file.id}/preview" if file.mime_type.startswith('image/') or file.mime_type == 'application/pdf' else None
                }
        
        result.append(circ_dict)
    
    return result


@router.put("/{circular_id}", response_model=CircularResponse)
async def update_circular(
    circular_id: int,
    circular_update: CircularUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a circular"""
    
    circular = db.query(Circular).filter(Circular.id == circular_id).first()
    if not circular:
        raise HTTPException(status_code=404, detail="Circular not found")
    
    creator = db.query(User).filter(User.id == circular.lecturer_id).first()
    is_owner = circular.lecturer_id == current_user.id
    is_admin = current_user.role == UserRole.ADMIN
    is_hod_dept = current_user.role == UserRole.HOD and creator and creator.department == current_user.department
    
    if not (is_owner or is_admin or is_hod_dept):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own circulars or department circulars as HOD"
        )
    
    if circular_update.type is not None:
        circular.type = circular_update.type
    if circular_update.title is not None:
        circular.title = circular_update.title
    if circular_update.content is not None:
        circular.content = circular_update.content
    if circular_update.due_date is not None:
        circular.due_date = circular_update.due_date
    if circular_update.file_id is not None:
        circular.file_id = circular_update.file_id
    
    db.commit()
    db.refresh(circular)
    
    # Notify students about update
    students = db.query(User).filter(User.role == UserRole.STUDENT, User.is_active == True).all()
    
    for student in students:
        new_notification = Notification(
            user_id=student.id,
            type="circular",
            title="📝 Circular Updated",
            message=f"Circular has been updated: {circular.title}",
            reference_id=circular.id,
            is_read=False
        )
        db.add(new_notification)
    db.commit()
    
    lecturer = db.query(User).filter(User.id == circular.lecturer_id).first()
    result = CircularResponse.model_validate(circular)
    result.lecturer_name = lecturer.name if lecturer else None
    
    if circular.file_id:
        file = db.query(File).filter(File.id == circular.file_id).first()
        if file:
            result.file_details = {
                "id": str(file.id),
                "filename": file.filename,
                "file_size": file.file_size,
                "mime_type": file.mime_type,
                "download_url": f"/files/{file.id}/download",
                "preview_url": f"/files/{file.id}/preview" if file.mime_type.startswith('image/') or file.mime_type == 'application/pdf' else None
            }
    
    return result


@router.delete("/{circular_id}")
async def delete_circular(
    circular_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a circular"""
    
    circular = db.query(Circular).filter(Circular.id == circular_id).first()
    if not circular:
        raise HTTPException(status_code=404, detail="Circular not found")
    
    creator = db.query(User).filter(User.id == circular.lecturer_id).first()
    is_owner = circular.lecturer_id == current_user.id
    is_admin = current_user.role == UserRole.ADMIN
    is_hod_dept = current_user.role == UserRole.HOD and creator and creator.department == current_user.department
    
    if not (is_owner or is_admin or is_hod_dept):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own circulars or department circulars as HOD"
        )
    
    # Delete reminders
    db.query(Reminder).filter(Reminder.circular_id == circular_id).delete()
    reminder_scheduler.cancel_reminders_for_circular(circular_id)
    
    db.delete(circular)
    db.commit()
    
    return {"message": "Circular deleted successfully"}