"""
Reminder Celery Tasks - 5 types of automated reminders
"""

from celery import Celery
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
import logging

from ..core.database import SessionLocal
from ..models.user import User
from ..models.circular import Circular
from ..models.notification import Notification
from ..models.reminder import Reminder, ReminderStatus, ReminderChannel, ReminderType

logger = logging.getLogger(__name__)
from .celery_app import celery_app


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_reminder_message(reminder_type: ReminderType, circular_title: str, due_date: datetime) -> tuple:
    """Get the reminder message and title based on reminder type"""
    
    messages = {
        ReminderType.SEVEN_DAY: {
            "title": f"📚 7 Days Left: {circular_title}",
            "message": f"Your assignment '{circular_title}' is due in 7 days on {due_date.strftime('%d %b %Y')}. Start early!"
        },
        ReminderType.THREE_DAY: {
            "title": f"⏰ 3 Days Left: {circular_title}",
            "message": f"Only 3 days left for '{circular_title}'! Due on {due_date.strftime('%d %b %Y')}."
        },
        ReminderType.ONE_DAY: {
            "title": f"🚨 1 Day Left: {circular_title}",
            "message": f"⚠️ '{circular_title}' is due TOMORROW ({due_date.strftime('%d %b %Y')})! Submit before deadline."
        },
        ReminderType.DEADLINE_DAY: {
            "title": f"⚠️ DUE TODAY: {circular_title}",
            "message": f"🔴 '{circular_title}' is DUE TODAY ({due_date.strftime('%d %b %Y')})! Submit before 11:59 PM."
        },
        ReminderType.MISSED_DEADLINE: {
            "title": f"❌ Missed Deadline: {circular_title}",
            "message": f"You missed the deadline for '{circular_title}' which was due on {due_date.strftime('%d %b %Y')}. Please contact your lecturer."
        }
    }
    
    return messages.get(reminder_type, messages[ReminderType.SEVEN_DAY])


def create_reminder_record(user_id: int, circular_id: int, reminder_type: ReminderType):
    """Create a reminder record in the database"""
    db = SessionLocal()
    try:
        scheduled_at = db.query(Reminder).filter(
            Reminder.user_id == user_id,
            Reminder.circular_id == circular_id,
            Reminder.reminder_type == reminder_type
        ).first()
        
        if scheduled_at:
            return
        
        circular = db.query(Circular).filter(Circular.id == circular_id).first()
        if not circular:
            return
        
        # Calculate scheduled time based on reminder type
        if reminder_type == ReminderType.SEVEN_DAY:
            scheduled_time = circular.due_date - timedelta(days=7)
        elif reminder_type == ReminderType.THREE_DAY:
            scheduled_time = circular.due_date - timedelta(days=3)
        elif reminder_type == ReminderType.ONE_DAY:
            scheduled_time = circular.due_date - timedelta(days=1)
        elif reminder_type == ReminderType.DEADLINE_DAY:
            scheduled_time = circular.due_date
        else:  # MISSED_DEADLINE
            scheduled_time = circular.due_date + timedelta(days=1)
        
        reminder = Reminder(
            circular_id=circular_id,
            user_id=user_id,
            reminder_type=reminder_type,
            status=ReminderStatus.PENDING,
            scheduled_at=scheduled_time
        )
        db.add(reminder)
        db.commit()
        logger.info(f"Created {reminder_type} reminder record for user {user_id}, circular {circular_id}")
    except Exception as e:
        logger.error(f"Failed to create reminder record: {e}")
        db.rollback()
    finally:
        db.close()


def send_reminder_to_user(user_id: int, circular_id: int, reminder_type: ReminderType):
    """Send reminder to a single user via all channels"""
    db = SessionLocal()
    
    try:
        user = db.query(User).filter(User.id == user_id).first()
        circular = db.query(Circular).filter(Circular.id == circular_id).first()
        
        if not user or not circular:
            logger.error(f"User {user_id} or Circular {circular_id} not found")
            return
        
        # Create reminder record (if not exists)
        create_reminder_record(user_id, circular_id, reminder_type)
        
        # Get message
        title, message = get_reminder_message(reminder_type, circular.title, circular.due_date)
        
        # Create In-App Notification
        notification = Notification(
            user_id=user_id,
            type="reminder",
            title=title,
            message=message,
            reference_id=circular_id,
            is_read=False
        )
        db.add(notification)
        
        # Update reminder record
        reminder = db.query(Reminder).filter(
            Reminder.user_id == user_id,
            Reminder.circular_id == circular_id,
            Reminder.reminder_type == reminder_type
        ).first()
        
        if reminder:
            reminder.status = ReminderStatus.SENT
            reminder.sent_at = datetime.now(timezone.utc)
            reminder.channel = ReminderChannel.IN_APP
        
        db.commit()
        logger.info(f"Reminder sent to user {user_id} for circular {circular_id} ({reminder_type})")
        
    except Exception as e:
        logger.error(f"Failed to send reminder to user {user_id}: {e}")
        db.rollback()
    finally:
        db.close()


# ============================================
# CELERY TASKS - Each creates its own reminder
# ============================================

@celery_app.task(bind=True, max_retries=3)
def send_7_day_reminder(self, circular_id: int):
    db = SessionLocal()
    try:
        circular = db.query(Circular).filter(Circular.id == circular_id).first()
        if not circular:
            logger.error(f"Circular {circular_id} not found")
            return
        
        students = db.query(User).filter(User.role == "student").all()
        for student in students:
            send_reminder_to_user(student.id, circular_id, ReminderType.SEVEN_DAY)
        logger.info(f"7-day reminder sent for circular {circular_id}")
    except Exception as e:
        logger.error(f"Failed to send 7-day reminders: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def send_3_day_reminder(self, circular_id: int):
    db = SessionLocal()
    try:
        circular = db.query(Circular).filter(Circular.id == circular_id).first()
        if not circular:
            logger.error(f"Circular {circular_id} not found")
            return
        
        students = db.query(User).filter(User.role == "student").all()
        for student in students:
            send_reminder_to_user(student.id, circular_id, ReminderType.THREE_DAY)
        logger.info(f"3-day reminder sent for circular {circular_id}")
    except Exception as e:
        logger.error(f"Failed to send 3-day reminders: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def send_1_day_reminder(self, circular_id: int):
    db = SessionLocal()
    try:
        circular = db.query(Circular).filter(Circular.id == circular_id).first()
        if not circular:
            logger.error(f"Circular {circular_id} not found")
            return
        
        students = db.query(User).filter(User.role == "student").all()
        for student in students:
            send_reminder_to_user(student.id, circular_id, ReminderType.ONE_DAY)
        logger.info(f"1-day reminder sent for circular {circular_id}")
    except Exception as e:
        logger.error(f"Failed to send 1-day reminders: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def send_deadline_day_reminder(self, circular_id: int):
    db = SessionLocal()
    try:
        circular = db.query(Circular).filter(Circular.id == circular_id).first()
        if not circular:
            logger.error(f"Circular {circular_id} not found")
            return
        
        students = db.query(User).filter(User.role == "student").all()
        for student in students:
            send_reminder_to_user(student.id, circular_id, ReminderType.DEADLINE_DAY)
        logger.info(f"Deadline-day reminder sent for circular {circular_id}")
    except Exception as e:
        logger.error(f"Failed to send deadline-day reminders: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def send_missed_deadline_reminder(self, circular_id: int):
    db = SessionLocal()
    try:
        circular = db.query(Circular).filter(Circular.id == circular_id).first()
        if not circular:
            logger.error(f"Circular {circular_id} not found")
            return
        
        students = db.query(User).filter(User.role == "student").all()
        for student in students:
            send_reminder_to_user(student.id, circular_id, ReminderType.MISSED_DEADLINE)
        logger.info(f"Missed deadline reminder sent for circular {circular_id}")
    except Exception as e:
        logger.error(f"Failed to send missed deadline reminders: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@celery_app.task
def cancel_reminders(circular_id: int):
    db = SessionLocal()
    try:
        reminders = db.query(Reminder).filter(
            Reminder.circular_id == circular_id,
            Reminder.status == ReminderStatus.PENDING
        ).update({Reminder.status: ReminderStatus.CANCELLED})
        db.commit()
        logger.info(f"Cancelled {reminders} pending reminders for circular {circular_id}")
    except Exception as e:
        logger.error(f"Failed to cancel reminders: {e}")
        db.rollback()
    finally:
        db.close()