"""
Reminder Scheduler Service - Schedules Celery tasks when circulars are created or updated
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
import logging

from ..models.circular import Circular
from ..models.user import User
from ..models.reminder import Reminder, ReminderType, ReminderStatus
from ..core.database import SessionLocal
from ..core.date_utils import IST, normalize_to_utc
from ..tasks.reminder_tasks import (
    send_7_day_reminder,
    send_3_day_reminder,
    send_1_day_reminder,
    send_deadline_day_reminder,
    send_missed_deadline_reminder,
    cancel_reminders
)

logger = logging.getLogger(__name__)


def get_stages(due_date_utc: datetime) -> List[Tuple[ReminderType, datetime]]:
    """Get the 5 canonical reminder stages and their target scheduled times."""
    return [
        (ReminderType.SEVEN_DAY, due_date_utc - timedelta(days=7)),
        (ReminderType.THREE_DAY, due_date_utc - timedelta(days=3)),
        (ReminderType.ONE_DAY, due_date_utc - timedelta(days=1)),
        (ReminderType.DEADLINE_DAY, due_date_utc),
        (ReminderType.MISSED_DEADLINE, due_date_utc + timedelta(hours=24)),
    ]


class ReminderScheduler:
    """
    Handles scheduling, reconciliation, and Celery dispatch for all circular reminders.
    """

    @staticmethod
    def schedule_reminders(circular_id: int, due_date: datetime) -> bool:
        """
        Schedule reminders for a circular with a due date.
        Only creates reminder stages whose scheduled times are strictly in the future.
        """
        if not due_date:
            logger.info(f"No due date for circular {circular_id}, skipping reminders")
            return False

        due_utc = normalize_to_utc(due_date)
        db = SessionLocal()

        try:
            # Re-lock circular to ensure consistency during scheduling
            circular = db.query(Circular).with_for_update().filter(Circular.id == circular_id).first()
            if not circular:
                logger.error(f"Circular {circular_id} not found during scheduling")
                return False

            now = datetime.now(timezone.utc)

            # Prevent scheduling if circular lifecycle is already closed (>= 25 hours past due date)
            if now >= (due_utc + timedelta(hours=25)):
                logger.info(f"Circular {circular_id} lifecycle expired (now >= due_date + 25h), skipping scheduling.")
                return True

            students = db.query(User).filter(
                User.role == "student",
                User.is_active == True
            ).order_by(User.id.asc()).all()
            if not students:
                logger.info(f"No active students found for circular {circular_id}")
                return False

            stages = get_stages(due_utc)
            reminders_created = 0

            # Explicit status handling:
            # - PENDING: Prevents duplicate pending rows for the exact same schedule.
            # - SENT: Preserves delivery history and prevents duplicate sending.
            # - FAILED / CANCELLED: Not treated as successful delivery; does NOT block scheduling future stages.
            existing_active_records = db.query(Reminder).filter(
                Reminder.circular_id == circular_id,
                Reminder.status.in_([ReminderStatus.PENDING, ReminderStatus.SENT])
            ).all()
            existing_schedule_set = set()
            for er in existing_active_records:
                er_utc = normalize_to_utc(er.scheduled_at)
                if er_utc:
                    existing_schedule_set.add((er.user_id, er.reminder_type, er_utc))

            for student in students:
                for r_type, scheduled_at in stages:
                    if scheduled_at > now:
                        # Exact normalized UTC datetime comparison preserving full precision
                        if (student.id, r_type, scheduled_at) not in existing_schedule_set:
                            reminder = Reminder(
                                circular_id=circular_id,
                                user_id=student.id,
                                reminder_type=r_type,
                                status=ReminderStatus.PENDING,
                                scheduled_at=scheduled_at
                            )
                            db.add(reminder)
                            reminders_created += 1

            db.commit()
            logger.info(f"Created {reminders_created} future reminder records for circular {circular_id}")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create reminder records for circular {circular_id}: {e}")
            raise
        finally:
            db.close()

        # Schedule Celery tasks post-commit outside the DB session
        ReminderScheduler._schedule_celery_tasks(circular_id, due_utc)
        return True

    @staticmethod
    def reconcile_reminders(circular_id: int, new_due_date: datetime, db: Optional[Session] = None) -> bool:
        """
        Reconcile reminder records after a deadline update:
        - Deletes all PENDING reminders for the circular.
        - Preserves SENT reminder history.
        - FAILED and CANCELLED records are preserved but not treated as successful delivery.
        - Pre-creates PENDING reminder rows for future stages relative to new_due_date.
        - Deadline-aware: an existing SENT reminder for an earlier scheduled time does
          NOT prevent creation of a future reminder for the revised deadline.
        - Compares exact target scheduled time in UTC to avoid duplicate reminders for the same schedule.
        Can run within an existing caller transaction (holding circular lock).
        """
        if not new_due_date:
            return False

        new_due_utc = normalize_to_utc(new_due_date)
        should_close = False
        if db is None:
            db = SessionLocal()
            should_close = True

        try:
            now = datetime.now(timezone.utc)

            # Delete pending reminders only (SENT history is strictly preserved)
            db.query(Reminder).filter(
                Reminder.circular_id == circular_id,
                Reminder.status == ReminderStatus.PENDING
            ).delete(synchronize_session=False)

            # If new deadline lifecycle is still active (< 25h past deadline), pre-create future stages
            if now < (new_due_utc + timedelta(hours=25)):
                students = db.query(User).filter(
                    User.role == "student",
                    User.is_active == True
                ).order_by(User.id.asc()).all()
                stages = get_stages(new_due_utc)

                # Fetch all existing SENT reminders for this circular to inspect scheduled times in UTC
                # FAILED and CANCELLED records are NOT treated as successful delivery and do not block revised future stages
                sent_records = db.query(Reminder).filter(
                    Reminder.circular_id == circular_id,
                    Reminder.status == ReminderStatus.SENT
                ).all()

                # Build a set of (user_id, reminder_type, scheduled_at_utc) with full microsecond precision
                sent_schedule_set = set()
                for sr in sent_records:
                    sr_utc = normalize_to_utc(sr.scheduled_at)
                    if sr_utc:
                        sent_schedule_set.add((sr.user_id, sr.reminder_type, sr_utc))

                for student in students:
                    for r_type, scheduled_at in stages:
                        if scheduled_at > now:
                            # Only skip if this stage was ALREADY sent for this exact schedule (preserving full precision)
                            if (student.id, r_type, scheduled_at) not in sent_schedule_set:
                                rem = Reminder(
                                    circular_id=circular_id,
                                    user_id=student.id,
                                    reminder_type=r_type,
                                    status=ReminderStatus.PENDING,
                                    scheduled_at=scheduled_at
                                )
                                db.add(rem)

            if should_close:
                db.commit()
                ReminderScheduler._schedule_celery_tasks(circular_id, new_due_utc)
            else:
                db.flush()

            return True
        except Exception as e:
            if should_close:
                db.rollback()
            logger.error(f"Failed to reconcile reminders for circular {circular_id}: {e}")
            raise
        finally:
            if should_close:
                db.close()

    @staticmethod
    def dispatch_reconciled_tasks(circular_id: int, new_due_date: datetime):
        """Dispatch Celery tasks for a reconciled schedule post-commit."""
        new_due_utc = normalize_to_utc(new_due_date)
        ReminderScheduler._schedule_celery_tasks(circular_id, new_due_utc)

    @staticmethod
    def _schedule_celery_tasks(circular_id: int, due_date: datetime):
        """
        Schedule Celery tasks for each reminder stage whose scheduled ETA is in the future.
        Passes (circular_id, expected_due_date_iso, expected_scheduled_at_iso) for validation.
        """
        now = datetime.now(timezone.utc)
        due_utc = normalize_to_utc(due_date)

        # Enforce 25-hour cutoff: no task dispatched if circular is expired
        if now >= (due_utc + timedelta(hours=25)):
            logger.info(f"Circular {circular_id} expired (>25h), skipping Celery task dispatch.")
            return

        stages = [
            (send_7_day_reminder, due_utc - timedelta(days=7)),
            (send_3_day_reminder, due_utc - timedelta(days=3)),
            (send_1_day_reminder, due_utc - timedelta(days=1)),
            (send_deadline_day_reminder, due_utc),
            (send_missed_deadline_reminder, due_utc + timedelta(hours=24)),
        ]

        due_iso = due_utc.isoformat()

        for task_fn, eta in stages:
            if eta > now:
                task_fn.apply_async(
                    args=[circular_id, due_iso, eta.isoformat()],
                    eta=eta
                )
                logger.info(f"Scheduled {task_fn.name} for circular {circular_id} at {eta}")

    @staticmethod
    def cancel_reminders_for_circular(circular_id: int):
        """Cancel all pending reminders for a circular."""
        cancel_reminders.apply_async(args=[circular_id])
        logger.info(f"Cancelled reminders for circular {circular_id}")


# Singleton instance
reminder_scheduler = ReminderScheduler()