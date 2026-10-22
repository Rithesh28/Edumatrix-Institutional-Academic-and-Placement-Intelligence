"""
Reminder Scheduler Service - Schedules Celery tasks when circulars are created
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
import logging

from ..models.circular import Circular
from ..models.user import User
from ..models.reminder import Reminder, ReminderType, ReminderStatus
from ..core.database import SessionLocal
from ..tasks.reminder_tasks import (
    send_7_day_reminder,
    send_3_day_reminder,
    send_1_day_reminder,
    send_deadline_day_reminder,
    send_missed_deadline_reminder,
    cancel_reminders
)

logger = logging.getLogger(__name__)


class ReminderScheduler:
    """
    Handles scheduling of all reminders for a circular
    """
    
    @staticmethod
    def schedule_reminders(circular_id: int, due_date: datetime):
        """
        Schedule 5 reminders for a circular with due date
        Only creates the 7-day reminder immediately, others are created by Celery tasks
        """
        if not due_date:
            logger.info(f"No due date for circular {circular_id}, skipping reminders")
            return False
        
        # Ensure due_date is timezone-aware UTC for consistent arithmetic
        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=timezone.utc)
        
        db = SessionLocal()
        
        try:
            # Get all students
            students = db.query(User).filter(User.role == "student", User.is_active == True).all()
            
            if not students:
                logger.info(f"No students found for circular {circular_id}")
                return False
            
            now = datetime.now(timezone.utc)
            
            # ============================================
            # IDEMPOTENCY CHECK: Do not duplicate if already scheduled
            # ============================================
            existing_count = db.query(Reminder).filter(Reminder.circular_id == circular_id).count()
            if existing_count > 0:
                logger.info(f"Reminders for circular {circular_id} already scheduled ({existing_count} existing), skipping to prevent duplicates")
                return True
            
            # ============================================
            # ONLY CREATE THE 7-DAY REMINDER IMMEDIATELY (IDEMPOTENT)
            # ============================================
            reminders_created = 0
            for student in students:
                scheduled_at = due_date - timedelta(days=7)
                
                # Only create if 7-day reminder is in the future
                if scheduled_at > now:
                    existing = db.query(Reminder).filter(
                        Reminder.circular_id == circular_id,
                        Reminder.user_id == student.id,
                        Reminder.reminder_type == ReminderType.SEVEN_DAY
                    ).first()
                    
                    if not existing:
                        reminder = Reminder(
                            circular_id=circular_id,
                            user_id=student.id,
                            reminder_type=ReminderType.SEVEN_DAY,
                            status=ReminderStatus.PENDING,
                            scheduled_at=scheduled_at
                        )
                        db.add(reminder)
                        reminders_created += 1
            
            db.commit()
            logger.info(f"Created {reminders_created} 7-day reminders for circular {circular_id} ({len(students)} students)")
            
            # ============================================
            # SCHEDULE ALL 5 CELERY TASKS
            # ============================================
            ReminderScheduler._schedule_celery_tasks(circular_id, due_date)
            return True
            
        except Exception as e:
            logger.error(f"Failed to schedule reminders for circular {circular_id}: {e}")
            db.rollback()
            raise
        finally:
            db.close()
    
    @staticmethod
    def _schedule_celery_tasks(circular_id: int, due_date: datetime):
        """
        Schedule Celery tasks for each reminder type
        Each task will create its own reminder record when triggered
        """
        now = datetime.now(timezone.utc)
        
        # Calculate ETA for each task
        eta_7_day = due_date - timedelta(days=7)
        eta_3_day = due_date - timedelta(days=3)
        eta_1_day = due_date - timedelta(days=1)
        eta_deadline = due_date
        eta_missed = due_date + timedelta(days=1)
        
        # Schedule tasks (only if ETA is in the future)
        if eta_7_day > now:
            send_7_day_reminder.apply_async(args=[circular_id], eta=eta_7_day)
            logger.info(f"Scheduled 7-day reminder for circular {circular_id} at {eta_7_day}")
        
        if eta_3_day > now:
            send_3_day_reminder.apply_async(args=[circular_id], eta=eta_3_day)
            logger.info(f"Scheduled 3-day reminder for circular {circular_id} at {eta_3_day}")
        
        if eta_1_day > now:
            send_1_day_reminder.apply_async(args=[circular_id], eta=eta_1_day)
            logger.info(f"Scheduled 1-day reminder for circular {circular_id} at {eta_1_day}")
        
        if eta_deadline > now:
            send_deadline_day_reminder.apply_async(args=[circular_id], eta=eta_deadline)
            logger.info(f"Scheduled deadline-day reminder for circular {circular_id} at {eta_deadline}")
        
        if eta_missed > now:
            send_missed_deadline_reminder.apply_async(args=[circular_id], eta=eta_missed)
            logger.info(f"Scheduled missed-deadline reminder for circular {circular_id} at {eta_missed}")
    
    @staticmethod
    def cancel_reminders_for_circular(circular_id: int):
        """Cancel all pending reminders for a circular"""
        cancel_reminders.apply_async(args=[circular_id])
        logger.info(f"Cancelled reminders for circular {circular_id}")


# Singleton instance
reminder_scheduler = ReminderScheduler()