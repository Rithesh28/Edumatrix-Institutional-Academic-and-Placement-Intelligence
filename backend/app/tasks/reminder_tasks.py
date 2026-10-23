"""
Reminder Celery Tasks - 5 types of automated reminders with strict lifecycle protection
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
from ..core.date_utils import normalize_to_utc

logger = logging.getLogger(__name__)
from .celery_app import celery_app


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def timestamps_match(dt1: Optional[datetime], dt2: Optional[datetime], tolerance_seconds: Optional[float] = None) -> bool:
    """
    Compare two datetimes normalized to UTC preserving full precision.
    If tolerance_seconds is None, requires exact equality down to the microsecond.
    """
    if dt1 is None or dt2 is None:
        return False
    u1 = normalize_to_utc(dt1)
    u2 = normalize_to_utc(dt2)
    if tolerance_seconds is None:
        return u1 == u2
    return abs((u1 - u2).total_seconds()) <= tolerance_seconds


def _is_valid_delivery_notification(
    notif: Optional[Notification],
    expected_user_id: int,
    expected_circular_id: int,
    expected_event_key: str
) -> bool:
    """
    Verify that an existing notification strictly matches the expected delivery identity:
    - user_id matches expected student
    - type is strictly 'reminder'
    - reference_id matches circular ID
    - event_key matches the canonical deadline-scoped event key
    """
    if not notif:
        return False
    return (
        notif.user_id == expected_user_id and
        notif.type == "reminder" and
        notif.reference_id == expected_circular_id and
        notif.event_key == expected_event_key
    )


def get_reminder_message(reminder_type: ReminderType, circular_title: str, due_date: datetime) -> tuple:
    """Get the reminder message and title based on reminder type."""
    due_date_str = due_date.strftime('%d %b %Y')
    messages = {
        ReminderType.SEVEN_DAY: {
            "title": f"📚 7 Days Left: {circular_title}",
            "message": f"Your assignment '{circular_title}' is due in 7 days on {due_date_str}. Start early!"
        },
        ReminderType.THREE_DAY: {
            "title": f"⏰ 3 Days Left: {circular_title}",
            "message": f"Only 3 days left for '{circular_title}'! Due on {due_date_str}."
        },
        ReminderType.ONE_DAY: {
            "title": f"🚨 1 Day Left: {circular_title}",
            "message": f"⚠️ '{circular_title}' is due TOMORROW ({due_date_str})! Submit before deadline."
        },
        ReminderType.DEADLINE_DAY: {
            "title": f"⚠️ DUE TODAY: {circular_title}",
            "message": f"🔴 '{circular_title}' is DUE TODAY ({due_date_str})! Submit before 11:59 PM."
        },
        ReminderType.MISSED_DEADLINE: {
            "title": f"❌ Missed Deadline: {circular_title}",
            "message": f"You missed the deadline for '{circular_title}' which was due on {due_date_str}. Please contact your lecturer."
        }
    }
    return messages.get(reminder_type, messages[ReminderType.SEVEN_DAY])


def _process_student_reminder(
    db: Session,
    user_id: int,
    circular: Circular,
    circ_due_utc: datetime,
    reminder_type: ReminderType,
    expected_sched_dt: Optional[datetime] = None
) -> bool:
    """
    Process reminder delivery for an individual student within a caller-managed transaction.
    Maintains row-level locks and strict status verification.
    NEVER creates a Reminder row if missing (zero worker auto-creation).
    """
    now = datetime.now(timezone.utc)

    # Re-check 25h cutoff immediately before record processing
    if now >= (circ_due_utc + timedelta(hours=25)):
        logger.info(f"Skipping student {user_id} for circular {circular.id}: circular lifecycle expired (>25h).")
        return False

    # Row-level lock on PENDING Reminder records for this user and stage
    pending_reminders = db.query(Reminder).with_for_update().filter(
        Reminder.circular_id == circular.id,
        Reminder.user_id == user_id,
        Reminder.reminder_type == reminder_type,
        Reminder.status == ReminderStatus.PENDING
    ).all()

    if not pending_reminders:
        return False

    reminder = None
    if expected_sched_dt is not None:
        for r in pending_reminders:
            r_sched_utc = normalize_to_utc(r.scheduled_at)
            if timestamps_match(r_sched_utc, expected_sched_dt):
                reminder = r
                break
    else:
        reminder = pending_reminders[0]

    # STRICT: Row MUST already exist with status PENDING and match expected target time. Zero worker auto-creation.
    if not reminder:
        logger.warning(
            f"No matching PENDING reminder found for circular {circular.id}, user {user_id}, "
            f"stage {reminder_type.value}, expected_sched_dt {expected_sched_dt}. Skipping."
        )
        return False

    # Distinguish deadline schedule using a canonical UTC deadline token preserving full microsecond precision
    # Retains the 'reminder:{circular.id}:' prefix for scoped expiry cleanup
    due_token = circ_due_utc.strftime("%Y%m%dT%H%M%S.%fZ")
    event_key = f"reminder:{circular.id}:due:{due_token}:user:{user_id}:stage:{reminder_type.value}"

    # Check existing notification by unique event_key for this exact schedule
    existing_notif = db.query(Notification).filter(Notification.event_key == event_key).first()
    if existing_notif:
        # Validate notification identity before treating as successful delivery
        if _is_valid_delivery_notification(existing_notif, user_id, circular.id, event_key):
            reminder.status = ReminderStatus.SENT
            reminder.sent_at = existing_notif.created_at or now
            reminder.channel = ReminderChannel.IN_APP
            logger.info(
                f"Reconciled reminder for circular {circular.id}, user {user_id}, "
                f"stage {reminder_type.value} with verified existing notification (id={existing_notif.id})."
            )
            return True
        else:
            logger.error(
                f"Existing notification (id={existing_notif.id}) for event_key {event_key} "
                f"is inconsistent: expected user={user_id}, type='reminder', ref={circular.id}; "
                f"found user={existing_notif.user_id}, type='{existing_notif.type}', ref={existing_notif.reference_id}. "
                "Leaving reminder PENDING for investigation."
            )
            return False

    title, message = get_reminder_message(reminder_type, circular.title, circ_due_utc)
    notification = Notification(
        user_id=user_id,
        type="reminder",
        title=title,
        message=message,
        reference_id=circular.id,
        event_key=event_key,
        is_read=False
    )
    # Use a nested transaction / savepoint to handle event_key collision safely
    sp = db.begin_nested()
    try:
        db.add(notification)
        db.flush()
        # Notification safely inserted: transition reminder to SENT in the same transaction
        reminder.status = ReminderStatus.SENT
        reminder.sent_at = now
        reminder.channel = ReminderChannel.IN_APP
        return True
    except IntegrityError:
        sp.rollback()
        # Handle concurrent insertion: verify conflicting notification belongs to this exact schedule before marking SENT
        conflicting = db.query(Notification).filter(Notification.event_key == event_key).first()
        if _is_valid_delivery_notification(conflicting, user_id, circular.id, event_key):
            reminder.status = ReminderStatus.SENT
            reminder.sent_at = conflicting.created_at or now
            reminder.channel = ReminderChannel.IN_APP
            logger.info(
                f"Reconciled reminder for circular {circular.id}, user {user_id}, "
                f"stage {reminder_type.value} with concurrently verified notification: {event_key}"
            )
            return True
        else:
            logger.error(
                f"IntegrityError on event_key {event_key}, but conflicting notification could not be verified. "
                "Leaving reminder PENDING for investigation."
            )
            return False


def _execute_reminder_stage(
    task_instance,
    circular_id: int,
    reminder_type: ReminderType,
    expected_due_date_iso: Optional[str],
    expected_scheduled_at_iso: Optional[str]
):
    """
    Standardized execution workflow for all 5 reminder stages:
    1. Rejects legacy tasks missing validation tokens without sending.
    2. Parses and normalizes validation tokens to UTC.
    3. Acquires a shared lock on Circular (FOR SHARE) to serialize against active deadline updates.
    4. Enforces the strict 25-hour lifecycle expiry cutoff.
    5. Validates expected deadline against current circular deadline.
    6. Processes active students using deterministic ordering, row locks, and event-key deduplication.
    7. Commits transaction atomically, holding the circular lock until completion.
    """
    # 1. Legacy Celery task rejection
    if not expected_due_date_iso or not expected_scheduled_at_iso:
        logger.warning(
            f"Rejecting legacy reminder task for circular {circular_id} ({reminder_type.value}): "
            "missing expected_due_date_iso or expected_scheduled_at_iso validation tokens. Not sending."
        )
        return

    # 2. Parse validation tokens to UTC
    try:
        expected_due_dt = datetime.fromisoformat(expected_due_date_iso.replace('Z', '+00:00')).astimezone(timezone.utc)
        expected_sched_dt = datetime.fromisoformat(expected_scheduled_at_iso.replace('Z', '+00:00')).astimezone(timezone.utc)
    except Exception as pe:
        logger.error(f"Failed to parse validation tokens for circular {circular_id}: {pe}. Dropping task.")
        return

    db = SessionLocal()
    try:
        # 3. Shared lock on Circular row (FOR SHARE) to serialize with any concurrent deadline update
        circular = db.query(Circular).with_for_update(read=True).filter(Circular.id == circular_id).first()
        if not circular:
            logger.error(f"Circular {circular_id} not found during {reminder_type.value} reminder task")
            return

        now = datetime.now(timezone.utc)
        circ_due_utc = normalize_to_utc(circular.due_date)

        if not circ_due_utc:
            logger.info(f"Circular {circular_id} has no due date, skipping {reminder_type.value} reminder.")
            return

        # 4. Strict 25-Hour Lifecycle Expiry Cutoff: now >= circular.due_date + 25h
        if now >= (circ_due_utc + timedelta(hours=25)):
            logger.info(
                f"Circular {circular_id} lifecycle expired (>25h past deadline). "
                f"Aborting {reminder_type.value} reminder task."
            )
            return

        # 5. Deadline Mismatch Validation (Tier 1 check):
        if not timestamps_match(circ_due_utc, expected_due_dt):
            logger.warning(
                f"Stale Celery task defused for circular {circular_id} ({reminder_type.value}): "
                f"task expected due_date {expected_due_dt} != current circular due_date {circ_due_utc}."
            )
            return

        # 6. Process students within this SAME transaction (keeping circular lock held!)
        # Use deterministic User.id.asc() ordering to prevent row-lock deadlocks
        students = db.query(User).filter(
            User.role == "student",
            User.is_active == True
        ).order_by(User.id.asc()).all()
        processed_count = 0

        for student in students:
            if _process_student_reminder(
                db=db,
                user_id=student.id,
                circular=circular,
                circ_due_utc=circ_due_utc,
                reminder_type=reminder_type,
                expected_sched_dt=expected_sched_dt
            ):
                processed_count += 1

        # Commit transaction atomically, releasing the circular lock only when finished
        db.commit()
        logger.info(f"{reminder_type.value} reminders processed for circular {circular_id} ({processed_count} delivered).")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to send {reminder_type.value} reminders for circular {circular_id}: {e}")
        raise task_instance.retry(exc=e, countdown=60)
    finally:
        db.close()


def send_reminder_to_user(
    user_id: int,
    circular_id: int,
    reminder_type: ReminderType,
    expected_due_date_iso: Optional[str] = None,
    expected_scheduled_at_iso: Optional[str] = None,
    db: Optional[Session] = None
):
    """
    Send reminder to a single user via in-app notification with strict idempotency and locking.
    Can be called standalone or within an existing transaction.
    Does NOT auto-create missing reminder rows.
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        # Acquire shared lock on circular
        circular = db.query(Circular).with_for_update(read=True).filter(Circular.id == circular_id).first()
        if not circular:
            logger.error(f"Circular {circular_id} not found")
            return

        now = datetime.now(timezone.utc)
        circ_due_utc = normalize_to_utc(circular.due_date)

        if not circ_due_utc:
            return

        # 25h Cutoff
        if now >= (circ_due_utc + timedelta(hours=25)):
            logger.info(f"Circular {circular_id} lifecycle expired (>25h), skipping user reminder.")
            return

        expected_due_dt = None
        if expected_due_date_iso:
            expected_due_dt = datetime.fromisoformat(expected_due_date_iso.replace('Z', '+00:00')).astimezone(timezone.utc)
            if not timestamps_match(circ_due_utc, expected_due_dt):
                logger.warning(f"Deadline mismatch for circular {circular_id}: {circ_due_utc} != {expected_due_dt}")
                return

        expected_sched_dt = None
        if expected_scheduled_at_iso:
            expected_sched_dt = datetime.fromisoformat(expected_scheduled_at_iso.replace('Z', '+00:00')).astimezone(timezone.utc)

        _process_student_reminder(
            db=db,
            user_id=user_id,
            circular=circular,
            circ_due_utc=circ_due_utc,
            reminder_type=reminder_type,
            expected_sched_dt=expected_sched_dt
        )

        if should_close:
            db.commit()
    except Exception as e:
        if should_close:
            db.rollback()
        logger.error(f"Failed to send reminder to user {user_id}: {e}")
        raise
    finally:
        if should_close:
            db.close()


# ============================================
# CELERY TASKS - 5 Reminder Stages
# ============================================

@celery_app.task(bind=True, max_retries=3)
def send_7_day_reminder(self, circular_id: int, expected_due_date_iso: Optional[str] = None, expected_scheduled_at_iso: Optional[str] = None):
    _execute_reminder_stage(self, circular_id, ReminderType.SEVEN_DAY, expected_due_date_iso, expected_scheduled_at_iso)


@celery_app.task(bind=True, max_retries=3)
def send_3_day_reminder(self, circular_id: int, expected_due_date_iso: Optional[str] = None, expected_scheduled_at_iso: Optional[str] = None):
    _execute_reminder_stage(self, circular_id, ReminderType.THREE_DAY, expected_due_date_iso, expected_scheduled_at_iso)


@celery_app.task(bind=True, max_retries=3)
def send_1_day_reminder(self, circular_id: int, expected_due_date_iso: Optional[str] = None, expected_scheduled_at_iso: Optional[str] = None):
    _execute_reminder_stage(self, circular_id, ReminderType.ONE_DAY, expected_due_date_iso, expected_scheduled_at_iso)


@celery_app.task(bind=True, max_retries=3)
def send_deadline_day_reminder(self, circular_id: int, expected_due_date_iso: Optional[str] = None, expected_scheduled_at_iso: Optional[str] = None):
    _execute_reminder_stage(self, circular_id, ReminderType.DEADLINE_DAY, expected_due_date_iso, expected_scheduled_at_iso)


@celery_app.task(bind=True, max_retries=3)
def send_missed_deadline_reminder(self, circular_id: int, expected_due_date_iso: Optional[str] = None, expected_scheduled_at_iso: Optional[str] = None):
    _execute_reminder_stage(self, circular_id, ReminderType.MISSED_DEADLINE, expected_due_date_iso, expected_scheduled_at_iso)


@celery_app.task
def cancel_reminders(circular_id: int):
    """Cancel all pending reminders for a circular in the database."""
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
    notifications once the deadline + 25 hours lifecycle cutoff has passed.
    Safe, scoped, and idempotent:
    - Filters circulars where Circular.due_date <= now - 25 hours.
    - Deletes ONLY reminder notifications (type == 'reminder', matching event_key namespace).
    - Preserves circular announcements (type == 'circular'), files, and circulars.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        # Circular lifecycle cutoff is strictly 25 hours past due date
        cutoff = now - timedelta(hours=25)

        # Acquire lock on expired circulars to serialize with any active operations
        expired_circulars = db.query(Circular).with_for_update().filter(
            Circular.due_date.isnot(None),
            Circular.due_date <= cutoff
        ).all()

        total_reminders_deleted = 0
        total_notifications_deleted = 0

        for circ in expired_circulars:
            # Delete ONLY reminder notifications belonging to this expired circular namespace
            deleted_notifs = db.query(Notification).filter(
                Notification.type == "reminder",
                Notification.reference_id == circ.id,
                Notification.event_key.like(f"reminder:{circ.id}:%")
            ).delete(synchronize_session=False)
            total_notifications_deleted += deleted_notifs

            # Delete reminder records for this expired circular
            deleted_rems = db.query(Reminder).filter(
                Reminder.circular_id == circ.id
            ).delete(synchronize_session=False)
            total_reminders_deleted += deleted_rems

        db.commit()
        if total_reminders_deleted > 0 or total_notifications_deleted > 0:
            logger.info(
                f"Cleaned up {total_reminders_deleted} expired reminders and "
                f"{total_notifications_deleted} associated notifications across "
                f"{len(expired_circulars)} expired circulars."
            )
    except Exception as e:
        logger.error(f"Failed to cleanup expired reminders: {e}")
        db.rollback()
    finally:
        db.close()
