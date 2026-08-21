from celery import Celery
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import logging

from ..core.database import SessionLocal
from ..models.exam_duty import ExamDuty
from ..models.notification import Notification
from ..models.user import User
from .celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def send_duty_reminder(self, duty_id: int):
    """Send reminder for exam duty"""
    
    db = SessionLocal()
    
    try:
        duty = db.query(ExamDuty).filter(ExamDuty.id == duty_id).first()
        if not duty:
            logger.error(f"Duty {duty_id} not found")
            return
        
        if duty.reminder_sent:
            return
        
        lecturer = db.query(User).filter(User.id == duty.lecturer_id).first()
        if not lecturer:
            return
        
        # Create reminder notification
        title = f"⏰ Reminder: Exam Duty Tomorrow"
        message = (
            f"Dear {lecturer.name},\n\n"
            f"This is a reminder that you have exam duty tomorrow:\n"
            f"📚 Subject: {duty.exam_name}\n"
            f"📅 Date: {duty.date}\n"
            f"⏰ Time: {duty.start_time} - {duty.end_time}\n"
            f"📍 Venue: {duty.venue}\n\n"
            f"Please arrive 15 minutes early."
        )
        
        notification = Notification(
            user_id=duty.lecturer_id,
            type="exam_duty_reminder",
            title=title,
            message=message,
            reference_id=duty.id,
            is_read=False
        )
        db.add(notification)
        
        duty.reminder_sent = True
        db.commit()
        
        logger.info(f"Reminder sent for duty {duty_id}")
        
    except Exception as e:
        logger.error(f"Failed to send duty reminder: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def process_exam_duty_upload(self, file_path: str, hod_id: int):
    """
    Process an exam duty file upload asynchronously.
    
    Args:
        file_path: Path to the uploaded file
        hod_id: ID of the HOD uploading the file
        
    Returns:
        Processing result dict
    """
    try:
        logger.info(f"Processing exam duty upload: {file_path}")
        
        # Initialize processor
        db = SessionLocal()
        from app.services.exam_duty_processor import ExamDutyProcessor
        processor = ExamDutyProcessor(db)
        
        # Process the file
        result = processor.process(file_path, hod_id)
        
        db.close()
        
        logger.info(f"Exam duty processing result: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error in process_exam_duty_upload: {str(e)}")
        self.retry(exc=e, countdown=60)
        return {
            'success': False,
            'error': str(e)
        }


@celery_app.task
def schedule_duty_reminders():
    """
    Schedule reminders for all upcoming exam duties.
    
    This task is run periodically (e.g., daily) to ensure
    reminders are scheduled for all duties.
    """
    try:
        db = SessionLocal()
        from app.services.duty_scheduler import DutyScheduler
        scheduler = DutyScheduler()
        
        scheduled = scheduler.schedule_reminders_for_new_duties(db)
        
        db.close()
        
        logger.info(f"Scheduled {scheduled} duty reminders")
        return scheduled
        
    except Exception as e:
        logger.error(f"Error in schedule_duty_reminders: {str(e)}")
        return 0


@celery_app.task
def detect_duty_conflicts():
    """
    Detect conflicts in exam duty assignments.
    
    Finds duties where the same lecturer is assigned to overlapping
    time slots on the same date.
    """
    try:
        db = SessionLocal()
        from app.services.duty_matcher import DutyMatcher
        matcher = DutyMatcher()
        
        conflicts = matcher.detect_all_conflicts(db)
        
        db.close()
        
        logger.info(f"Detected {len(conflicts)} duty conflicts")
        return conflicts
        
    except Exception as e:
        logger.error(f"Error in detect_duty_conflicts: {str(e)}")
        return []


@celery_app.task
def send_duty_notification(duty_id: int, days_before: int):
    """
    Send notification for an exam duty.
    
    Args:
        duty_id: ID of the exam duty
        days_before: Days before the duty (7, 3, 1, 0)
    """
    try:
        db = SessionLocal()
        
        duty = db.query(ExamDuty).filter(ExamDuty.id == duty_id).first()
        if not duty:
            logger.warning(f"Duty {duty_id} not found")
            return False
        
        lecturer = db.query(User).filter(User.id == duty.lecturer_id).first()
        if not lecturer:
            return False
        
        # Determine message based on days before
        if days_before == 7:
            title = f"📋 7-Day Reminder: {duty.exam_name}"
            message = f"Dear {lecturer.name},\n\nYou have exam duty for {duty.exam_name} in 7 days on {duty.date} at {duty.start_time}.\n\nVenue: {duty.venue}"
        elif days_before == 3:
            title = f"📋 3-Day Reminder: {duty.exam_name}"
            message = f"Dear {lecturer.name},\n\nYou have exam duty for {duty.exam_name} in 3 days on {duty.date} at {duty.start_time}.\n\nVenue: {duty.venue}"
        elif days_before == 1:
            title = f"⚠️ Tomorrow: {duty.exam_name}"
            message = f"Dear {lecturer.name},\n\nYou have exam duty for {duty.exam_name} TOMORROW at {duty.start_time}.\n\nVenue: {duty.venue}\n\nPlease arrive 15 minutes early."
        elif days_before == 0:
            title = f"🔔 Today: {duty.exam_name}"
            message = f"Dear {lecturer.name},\n\nYou have exam duty for {duty.exam_name} TODAY at {duty.start_time}.\n\nVenue: {duty.venue}\n\nPlease arrive 15 minutes early."
        else:
            title = f"📋 Reminder: {duty.exam_name}"
            message = f"Dear {lecturer.name},\n\nYou have exam duty for {duty.exam_name} on {duty.date} at {duty.start_time}.\n\nVenue: {duty.venue}"
        
        # Create notification
        notification = Notification(
            user_id=duty.lecturer_id,
            type="exam_duty_reminder",
            title=title,
            message=message,
            reference_id=duty.id,
            is_read=False
        )
        db.add(notification)
        db.commit()
        
        logger.info(f"Sent {days_before}-day notification for duty {duty_id}")
        db.close()
        return True
        
    except Exception as e:
        logger.error(f"Error in send_duty_notification: {str(e)}")
        return False