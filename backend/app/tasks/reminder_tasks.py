"""
Reminder Celery Tasks - 5 types of automated reminders
"""

from celery import Celery
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
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


def create_reminder_record(user_id: int, circular_id: int, reminder_type: ReminderType, db: Optional[Session] = None):
    """Create a reminder record in the database idempotently"""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True
        
    try:
        existing = db.query(Reminder).filter(
            Reminder.user_id == user_id,
            Reminder.circular_id == circular_id,
            Reminder.reminder_type == reminder_type
        ).first()
        
        if existing:
            return existing
        
        circular = db.query(Circular).filter(Circular.id == circular_id).first()
        if not circular:
            return None
        
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
        if should_close:
            db.commit()
            db.refresh(reminder)
        else:
            db.flush()
        logger.info(f"Created {reminder_type} reminder record for user {user_id}, circular {circular_id}")
        return reminder
    except Exception as e:
        logger.error(f"Failed to create reminder record: {e}")
        if should_close:
            db.rollback()
        return None
    finally:
        if should_close:
            db.close()


def send_reminder_to_user(user_id: int, circular_id: int, reminder_type: ReminderType):
    """Send reminder to a single user via in-app notification with strict idempotency"""
    event_key = f"reminder:{circular_id}:user:{user_id}:stage:{reminder_type.value}"
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.id == user_id).first()
        circular = db.query(Circular).filter(Circular.id == circular_id).first()

        if not user or not circular:
            logger.error(f"User {user_id} or Circular {circular_id} not found")
            return

        # GUARD: Verify this stage is still valid
        now = datetime.now(timezone.utc)
        due_date = circular.due_date
        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=timezone.utc)

        # Calculate target time for this stage
        if reminder_type == ReminderType.SEVEN_DAY: target = due_date - timedelta(days=7)
        elif reminder_type == ReminderType.THREE_DAY: target = due_date - timedelta(days=3)
        elif reminder_type == ReminderType.ONE_DAY: target = due_date - timedelta(days=1)
        elif reminder_type == ReminderType.DEADLINE_DAY: target = due_date
        else: target = due_date + timedelta(days=1) # MISSED_DEADLINE

        # If task is significantly delayed (e.g. deadline has passed for 7-day reminder), do not proceed
        # For non-missed-deadline, target should not be in the past beyond a small drift (e.g. 5 mins)
        if reminder_type != ReminderType.MISSED_DEADLINE and target < (now - timedelta(minutes=5)):
             logger.warning(f"Reminder task for circular {circular_id} ({reminder_type.value}) is stale (target: {target}). Skipping.")
             return

        # 1. Fast idempotency check: Has this notification already been generated?
        existing_notif = db.query(Notification).filter(Notification.event_key == event_key).first()
        existing_reminder = db.query(Reminder).filter(
            Reminder.user_id == user_id,
            Reminder.circular_id == circular_id,
            Reminder.reminder_type == reminder_type
        ).first()

        if existing_notif and existing_reminder and existing_reminder.status == ReminderStatus.SENT:
            logger.info(
                f"Reminder already processed and sent for user {user_id}, "
                f"circular {circular_id} ({reminder_type.value}) [event_key: {event_key}] - skipping"
            )
            return

        # 2. Ensure Reminder record exists in current transaction
        if not existing_reminder:
            existing_reminder = create_reminder_record(user_id, circular_id, reminder_type, db=db)

        # 3. Create In-App Notification with unique event_key if not already created
        if not existing_notif:
            title, message = get_reminder_message(reminder_type, circular.title, circular.due_date)
            notification = Notification(
                user_id=user_id,
                type="reminder",
                title=title,
                message=message,
                reference_id=circular_id,
                event_key=event_key,
                is_read=False
            )
            db.add(notification)

        # 4. Mark reminder as SENT in the same transaction
        if existing_reminder:
            existing_reminder.status = ReminderStatus.SENT
            existing_reminder.sent_at = datetime.now(timezone.utc)
            existing_reminder.channel = ReminderChannel.IN_APP

        # 5. Commit atomically with unique constraint conflict handling
        try:
            db.commit()
            logger.info(f"Reminder sent to user {user_id} for circular {circular_id} ({reminder_type.value})")
        except IntegrityError as ie:
            # Concurrent worker or retry attempt inserted the notification concurrently
            db.rollback()
            logger.warning(
                f"Concurrent reminder delivery detected for {event_key}; unique constraint prevented duplicate. ({ie})"
            )
            # Ensure the reminder status is reconciled to SENT in a clean session
            with SessionLocal() as recovery_db:
                rem = recovery_db.query(Reminder).filter(
                    Reminder.user_id == user_id,
                    Reminder.circular_id == circular_id,
                    Reminder.reminder_type == reminder_type
                ).first()
                if rem and rem.status != ReminderStatus.SENT:
                    rem.status = ReminderStatus.SENT
                    rem.sent_at = datetime.now(timezone.utc)
                    recovery_db.commit()

    except Exception as e:
        logger.error(f"Failed to send reminder to user {user_id}: {e}")
        db.rollback()
        raise
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


@celery_app.task
def cleanup_expired_reminders():
    """
    Periodic cleanup task: Removes expired reminder records and their associated
    notifications once the deadline + missed deadline window has passed.
    Safe and idempotent.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        # Expired window: reminders whose scheduled_at is older than 2 days (past missed deadline)
        # or where circular due_date is passed by > 2 days and status is PENDING / CANCELLED.
        cutoff = now - timedelta(days=2)

        expired_reminders = db.query(Reminder).filter(
            (Reminder.scheduled_at < cutoff) | (Reminder.status == ReminderStatus.CANCELLED)
        ).all()

        reminders_deleted = 0
        notifications_deleted = 0

        for rem in expired_reminders:
            # Delete associated notification by event_key if exists
            event_key = f"reminder:{rem.circular_id}:user:{rem.user_id}:stage:{rem.reminder_type.value}"
            notif = db.query(Notification).filter(Notification.event_key == event_key).first()
            if notif:
                db.delete(notif)
                notifications_deleted += 1

            db.delete(rem)
            reminders_deleted += 1

        db.commit()
        if reminders_deleted > 0 or notifications_deleted > 0:
            logger.info(f"🧹 Cleaned up {reminders_deleted} expired reminders and {notifications_deleted} associated notifications.")
    except Exception as e:
        logger.error(f"Failed to cleanup expired reminders: {e}")
        db.rollback()
    finally:
        db.close()
