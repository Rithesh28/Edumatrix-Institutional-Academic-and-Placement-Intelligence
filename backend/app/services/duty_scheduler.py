from sqlalchemy.orm import Session
from datetime import datetime, date, time, timedelta
import logging

from ..models.exam_duty import ExamDuty, DutyStatus
from ..models.duty_conflict import DutyConflict, ConflictType
from ..models.notification import Notification
from ..models.reminder import Reminder, ReminderType, ReminderStatus
from ..models.user import User, UserRole

logger = logging.getLogger(__name__)


class DutyScheduler:
    """Schedule duties, notifications, and reminders"""
    
    def __init__(self, db: Session = None):
        self.db = db
    
    def _to_time_obj(self, val) -> time:
        if isinstance(val, time):
            return val
        if isinstance(val, str):
            val_str = val.strip()
            for fmt in ["%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M%p", "%I %p"]:
                try:
                    return datetime.strptime(val_str, fmt).time()
                except ValueError:
                    pass
        return time(9, 30)

    def _to_date_obj(self, val) -> date:
        if isinstance(val, date):
            return val
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, str):
            val_str = val.strip()
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"]:
                try:
                    return datetime.strptime(val_str, fmt).date()
                except ValueError:
                    pass
        return date.today()

    def check_conflict(self, lecturer_id: int, duty_date, start_time, end_time, db: Session = None) -> bool:
        if db is None:
            db = self.db
        
        if db is None:
            logger.error("No database session provided")
            return False
        
        target_date = self._to_date_obj(duty_date)
        s_time = self._to_time_obj(start_time)
        e_time = self._to_time_obj(end_time)
        
        existing_duties = db.query(ExamDuty).filter(
            ExamDuty.lecturer_id == lecturer_id,
            ExamDuty.date == target_date,
            ExamDuty.status != DutyStatus.CANCELLED
        ).all()
        
        for existing in existing_duties:
            ex_start = self._to_time_obj(existing.start_time)
            ex_end = self._to_time_obj(existing.end_time)
            if s_time < ex_end and e_time > ex_start:
                logger.info(f"Conflict found for lecturer {lecturer_id} on {target_date}")
                return True
        
        return False
    
    def create_notification_and_reminder(self, duty: ExamDuty, db: Session = None):
        if db is None:
            db = self.db
        
        if db is None:
            logger.error("No database session provided")
            return
        
        lecturer = db.query(User).filter(User.id == duty.lecturer_id).first()
        if not lecturer:
            logger.error(f"Lecturer {duty.lecturer_id} not found")
            return
        
        # ✅ FIXED: Removed venue reference
        notification_title = f"📅 New Exam Duty: {duty.exam_name}"
        notification_message = (
            f"Dear {lecturer.name},\n\n"
            f"You have been assigned exam duty for:\n"
            f"📚 Subject: {duty.exam_name}\n"
            f"📅 Date: {duty.date}\n"
            f"⏰ Time: {duty.start_time} - {duty.end_time}\n\n"
            f"Please confirm your availability."
        )
        
        lecturer_notification = Notification(
            user_id=duty.lecturer_id,
            type="exam_duty",
            title=notification_title,
            message=notification_message,
            reference_id=duty.id,
            is_read=False
        )
        db.add(lecturer_notification)
        
        # Notification for HOD
        hod = db.query(User).filter(User.id == duty.hod_id).first()
        if hod:
            hod_notification = Notification(
                user_id=duty.hod_id,
                type="exam_duty_hod",
                title=f"📤 Exam Duty Uploaded: {duty.exam_name}",
                message=f"Assigned to {lecturer.name} on {duty.date} at {duty.start_time}",
                reference_id=duty.id,
                is_read=False
            )
            db.add(hod_notification)
        
        # Schedule reminder (1 day before)
        reminder_date = duty.date - timedelta(days=1)
        scheduled_at = datetime.combine(reminder_date, duty.start_time)
        
        if scheduled_at > datetime.now():
            reminder = Reminder(
                circular_id=None,
                user_id=duty.lecturer_id,
                reminder_type=ReminderType.ONE_DAY,
                status=ReminderStatus.PENDING,
                scheduled_at=scheduled_at
            )
            db.add(reminder)
            logger.info(f"Scheduled reminder for duty {duty.id} at {scheduled_at}")
        
        db.commit()
        logger.info(f"Notification and reminder created for lecturer {duty.lecturer_id}")
    
    def schedule_reminders_for_new_duties(self, db: Session = None) -> int:
        if db is None:
            db = self.db
        
        if db is None:
            logger.error("No database session provided")
            return 0
        
        duties = db.query(ExamDuty).filter(
            ExamDuty.reminder_sent == False,
            ExamDuty.status != DutyStatus.CANCELLED
        ).all()
        
        scheduled = 0
        
        for duty in duties:
            try:
                self.create_notification_and_reminder(duty, db)
                duty.reminder_sent = True
                scheduled += 1
            except Exception as e:
                logger.error(f"Failed to schedule reminder for duty {duty.id}: {str(e)}")
        
        try:
            db.commit()
            logger.info(f"Scheduled reminders for {scheduled} new duties")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to commit reminders: {str(e)}")
        
        return scheduled


duty_scheduler = DutyScheduler()