"""
Reminder API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone

from ..core.database import get_db
from ..api.auth import get_current_user
from ..models.user import User
from ..models.reminder import Reminder, ReminderStatus
from ..schemas.reminder import (
    ReminderResponse,
    ReminderUpdate,
    ReminderCountResponse,
    UnreadReminderCountResponse
)

router = APIRouter(prefix="/reminders", tags=["Reminders"])


@router.get("/", response_model=List[ReminderResponse])
async def get_reminders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get reminders for current user - ONLY shows:
    1. Reminders that have been SENT (read)
    2. Reminders that are PENDING but SCHEDULED for now or earlier (overdue/unread)
    """
    
    now = datetime.now(timezone.utc)
    
    # Show sent reminders OR pending reminders that are due now or earlier
    reminders = db.query(Reminder).filter(
        Reminder.user_id == current_user.id,
        (Reminder.status == ReminderStatus.SENT) | (Reminder.scheduled_at <= now)
    ).order_by(Reminder.scheduled_at.asc()).all()
    
    result = []
    for reminder in reminders:
        response = ReminderResponse.model_validate(reminder)
        if reminder.circular:
            response.circular_title = reminder.circular.title
            response.circular_content = reminder.circular.content
            response.circular_due_date = reminder.circular.due_date
        result.append(response)
    
    return result


@router.get("/unread/count", response_model=UnreadReminderCountResponse)
async def get_unread_reminder_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get count of unread reminders (pending and overdue)
    """
    
    try:
        now = datetime.now(timezone.utc)
        
        count = db.query(Reminder).filter(
            Reminder.user_id == current_user.id,
            Reminder.status == ReminderStatus.PENDING,
            Reminder.scheduled_at <= now
        ).count()
        
        return {"count": count}
    except Exception as e:
        print(f"Error in get_unread_reminder_count: {e}")
        return {"count": 0}


@router.put("/{reminder_id}/read", response_model=ReminderResponse)
async def mark_reminder_as_read(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a reminder as read"""
    
    reminder = db.query(Reminder).filter(
        Reminder.id == reminder_id,
        Reminder.user_id == current_user.id
    ).first()
    
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    
    reminder.status = ReminderStatus.SENT
    reminder.sent_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(reminder)
    
    response = ReminderResponse.model_validate(reminder)
    if reminder.circular:
        response.circular_title = reminder.circular.title
        response.circular_content = reminder.circular.content
        response.circular_due_date = reminder.circular.due_date
    
    return response


@router.put("/read-all")
async def mark_all_reminders_as_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark all reminders as read"""
    
    db.query(Reminder).filter(
        Reminder.user_id == current_user.id,
        Reminder.status == ReminderStatus.PENDING
    ).update({Reminder.status: ReminderStatus.SENT})
    
    db.commit()
    
    return {"message": "All reminders marked as read"}


@router.delete("/{reminder_id}")
async def delete_reminder(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a reminder"""
    
    reminder = db.query(Reminder).filter(
        Reminder.id == reminder_id,
        Reminder.user_id == current_user.id
    ).first()
    
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    
    db.delete(reminder)
    db.commit()
    
    return {"message": "Reminder deleted successfully"}


@router.get("/stats", response_model=ReminderCountResponse)
async def get_reminder_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get reminder statistics for current user"""
    
    try:
        now = datetime.now(timezone.utc)
        
        total = db.query(Reminder).filter(Reminder.user_id == current_user.id).count()
        pending = db.query(Reminder).filter(
            Reminder.user_id == current_user.id,
            Reminder.status == ReminderStatus.PENDING
        ).count()
        sent = db.query(Reminder).filter(
            Reminder.user_id == current_user.id,
            Reminder.status == ReminderStatus.SENT
        ).count()
        failed = db.query(Reminder).filter(
            Reminder.user_id == current_user.id,
            Reminder.status == ReminderStatus.FAILED
        ).count()
        
        overdue = db.query(Reminder).filter(
            Reminder.user_id == current_user.id,
            Reminder.status == ReminderStatus.PENDING,
            Reminder.scheduled_at <= now
        ).count()
        
        return {
            "total": total,
            "pending": pending,
            "sent": sent,
            "failed": failed,
            "overdue": overdue
        }
    except Exception as e:
        print(f"Error in get_reminder_stats: {e}")
        return {
            "total": 0,
            "pending": 0,
            "sent": 0,
            "failed": 0,
            "overdue": 0
        }