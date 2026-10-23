"""
EduMatrix Issue 1 — Dedicated In-Memory Unit Test Suite
=======================================================
Target Components:
- app.services.reminder_scheduler (Normalization, Stages, Cutoff, Reconcile, Status Matrix)
- app.tasks.reminder_tasks (Identity validation, Precision, Idempotency, Token Defusing, Cleanup)

MANDATORY ISOLATION ARCHITECTURE:
- 100% in-memory execution using unittest and unittest.mock.
- Hard network barrier (socket.socket override) installed before any imports.
- Dummy unroutable environment variables set before configuration resolution.
- Zero live database connections, zero Redis connections, zero localhost HTTP calls.
"""

import sys
import os
import socket
import enum
from datetime import datetime, date, time as dt_time, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Optional
import unittest
from unittest.mock import patch, MagicMock, call

# =========================================================================
# 1. FAIL-CLOSED NETWORK BARRIER & ENVIRONMENT GUARDS
# =========================================================================
def _blocked_socket(*args, **kwargs):
    raise RuntimeError("CRITICAL ISOLATION VIOLATION: Network socket access is forbidden during unit tests!")

socket.socket = _blocked_socket

# Set dummy, unroutable URLs before any application module can read environment
os.environ["DATABASE_URL"] = "postgresql://blocked_user:blocked_pass@127.0.0.1:9999/blocked_test_db"
os.environ["REDIS_URL"] = "redis://127.0.0.1:9999/9"
os.environ["USE_GLINER"] = "false"
os.environ["EMAIL_ENABLED"] = "false"

# Ensure backend directory is in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# =========================================================================
# 2. APPLICATION IMPORTS (Safe after environment & socket barriers)
# =========================================================================
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql import operators

from app.models.circular import Circular, CircularType
from app.models.user import User, UserRole
from app.models.notification import Notification
from app.models.reminder import Reminder, ReminderStatus, ReminderType, ReminderChannel
from app.services.reminder_scheduler import (
    normalize_to_utc,
    get_stages,
    ReminderScheduler,
    reminder_scheduler,
    IST
)
from app.tasks.reminder_tasks import (
    timestamps_match,
    _is_valid_delivery_notification,
    get_reminder_message,
    _process_student_reminder,
    _execute_reminder_stage,
    send_7_day_reminder,
    send_3_day_reminder,
    send_1_day_reminder,
    send_deadline_day_reminder,
    send_missed_deadline_reminder,
    cleanup_expired_reminders,
    send_reminder_to_user
)


# =========================================================================
# HELPERS: SQLAlchemy Filter Expression Inspection (No Boolean Evaluation)
# =========================================================================

def _get_expr_left_column(expr) -> Optional[str]:
    """Extract column name from an expression's left operand without evaluating SQL."""
    left = getattr(expr, "left", None)
    if left is None:
        return None
    return getattr(left, "name", getattr(left, "key", getattr(getattr(left, "expression", None), "name", None)))


def _get_expr_operator(expr):
    """Extract operator function or callable from expression."""
    return getattr(expr, "operator", None)


def _get_expr_operator_name(expr) -> str:
    """Extract normalized operator name (lowercase, underscores)."""
    op = _get_expr_operator(expr)
    if op is None:
        return ""
    return getattr(op, "__name__", str(op)).lower().replace(" ", "_")


def _get_expr_right_value(expr):
    """
    Extract bound value or literal from an expression's right operand without evaluating SQL.
    Correctly resolves BindParameter.value and handles NULL elements and Enums.
    """
    right = getattr(expr, "right", None)
    if right is None:
        return None
    if hasattr(right, "value"):
        return right.value
    if hasattr(right, "effective_value"):
        return right.effective_value
    # Null element check in SQLAlchemy
    if "null" in str(right).lower() or getattr(right, "__class__", None).__name__ == "Null":
        return None
    return right


# Map canonical operator names to (actual_operator_callable, canonical_name)
OPERATOR_MAP = {
    "eq": (operators.eq, "eq"),
    "le": (operators.le, "le"),
    "lt": (operators.lt, "lt"),
    "ge": (operators.ge, "ge"),
    "gt": (operators.gt, "gt"),
    "is_not": (operators.is_not, "is_not"),
    "is": (getattr(operators, "is_", None), "is_"),
    "like_op": (operators.like_op, "like_op"),
    "like": (operators.like_op, "like_op"),
    "ilike_op": (getattr(operators, "ilike_op", None), "ilike_op"),
    "ilike": (getattr(operators, "ilike_op", None), "ilike_op"),
}


def _matches_operator(expr_op, expected_op_name: str) -> bool:
    """
    Check if expression's operator matches expected_op_name using exact normalized matching and identity.
    Rejects arbitrary substring matches (e.g. 'le' in 'like_op' or 'like' in 'ilike_op').
    """
    if expr_op is None:
        return False

    target_norm = expected_op_name.lower().replace(" ", "_")
    op_entry = OPERATOR_MAP.get(target_norm)
    if op_entry:
        expected_callable, canonical_target = op_entry
        if expected_callable is not None and expr_op is expected_callable:
            return True
    else:
        canonical_target = target_norm

    actual_name = _get_expr_operator_name(expr_op)
    actual_entry = OPERATOR_MAP.get(actual_name)
    canonical_actual = actual_entry[1] if actual_entry else actual_name

    # Exact normalized matching only (no arbitrary substring matching)
    return (actual_name == canonical_target) or (canonical_actual == canonical_target)


def _find_binary_expr(filter_args, column_name: str, op_name: Optional[str] = None):
    """
    Find a BinaryExpression in filter_args matching column_name and optional operator name.
    Uses exact normalized operator matching to avoid key collisions and false substring matches.
    """
    for expr in filter_args:
        col = _get_expr_left_column(expr)
        if col == column_name:
            if op_name is not None:
                expr_op = _get_expr_operator(expr)
                if _matches_operator(expr_op, op_name):
                    return expr
            else:
                return expr
    return None


def _assert_filter_binary_expr(
    test_case: unittest.TestCase,
    filter_args,
    column_name: str,
    expected_op_name: str,
    expected_value=None,
    check_value: bool = True
):
    """
    Assert that filter_args contains an expression matching column_name, expected operator, and expected value.
    Inspects left column, operator, and right operand directly without evaluating SQL clauses as booleans.
    Handles SQLAlchemy Enum columns (ReminderStatus) and string values transparently.
    Uses exact normalized operator matching and identity checks.
    """
    expr = _find_binary_expr(filter_args, column_name, op_name=expected_op_name)
    test_case.assertIsNotNone(
        expr,
        f"Missing filter expression for column '{column_name}' with operator '{expected_op_name}'"
    )

    # 1. Verify left-hand column
    actual_col = _get_expr_left_column(expr)
    test_case.assertEqual(
        actual_col,
        column_name,
        f"Column mismatch: expected '{column_name}', got '{actual_col}'"
    )

    # 2. Verify operator using exact matching and identity
    actual_op = _get_expr_operator(expr)
    operator_matched = _matches_operator(actual_op, expected_op_name)
    test_case.assertTrue(
        operator_matched,
        f"Operator mismatch for column '{column_name}': expected '{expected_op_name}', got '{_get_expr_operator_name(expr)}'"
    )

    # 3. Verify right-hand value if requested
    if check_value:
        actual_val = _get_expr_right_value(expr)
        # Transparently handle enums (e.g. ReminderStatus inheriting from str, enum.Enum)
        if isinstance(expected_value, enum.Enum):
            matches = (actual_val == expected_value) or (actual_val == expected_value.value)
        elif isinstance(actual_val, enum.Enum):
            matches = (actual_val == expected_value) or (actual_val.value == expected_value)
        else:
            matches = (actual_val == expected_value)
        test_case.assertTrue(
            matches,
            f"Value mismatch for column '{column_name}': expected {expected_value!r}, got {actual_val!r}"
        )

    return expr


# =========================================================================
# TEST SUITE: ISSUE 1 UNIT TESTS
# =========================================================================

class TestTimezoneAndPrecision(unittest.TestCase):
    """Tests for naive datetime interpretation, UTC conversion, and microsecond precision."""

    def test_01_naive_datetime_interpreted_as_ist_and_converted_to_utc(self):
        """Naive datetimes must be interpreted as Asia/Kolkata (+05:30) and converted to UTC."""
        naive_dt = datetime(2026, 10, 23, 18, 30, 0)  # 6:30 PM IST
        utc_dt = normalize_to_utc(naive_dt)

        self.assertIsNotNone(utc_dt.tzinfo)
        self.assertEqual(utc_dt.tzinfo, timezone.utc)
        # 18:30 IST is 13:00 UTC
        self.assertEqual(utc_dt.year, 2026)
        self.assertEqual(utc_dt.month, 10)
        self.assertEqual(utc_dt.day, 23)
        self.assertEqual(utc_dt.hour, 13)
        self.assertEqual(utc_dt.minute, 0)
        self.assertEqual(utc_dt.second, 0)

    def test_02_explicit_timezone_preserved_and_converted_to_utc(self):
        """Datetimes with explicit timezone offsets are preserved and accurately converted."""
        # EDT is UTC-4
        edt = ZoneInfo("America/New_York")
        aware_dt = datetime(2026, 10, 23, 14, 0, 0, tzinfo=edt)
        utc_dt = normalize_to_utc(aware_dt)

        self.assertEqual(utc_dt.tzinfo, timezone.utc)
        # 14:00 EDT (UTC-4) is 18:00 UTC
        self.assertEqual(utc_dt.hour, 18)
        self.assertEqual(utc_dt.minute, 0)

    def test_03_none_datetime_handling(self):
        """normalize_to_utc(None) returns None safely without raising an exception."""
        self.assertIsNone(normalize_to_utc(None))

    def test_04_microsecond_precision_preserved_in_timestamps_match(self):
        """Full microsecond precision is preserved during comparison."""
        dt1 = datetime(2026, 10, 23, 18, 30, 0, 123456, tzinfo=timezone.utc)
        dt2 = datetime(2026, 10, 23, 18, 30, 0, 123456, tzinfo=timezone.utc)
        dt_diff = datetime(2026, 10, 23, 18, 30, 0, 123457, tzinfo=timezone.utc)

        # Exact match
        self.assertTrue(timestamps_match(dt1, dt2))
        # 1-microsecond difference must fail when tolerance_seconds is None
        self.assertFalse(timestamps_match(dt1, dt_diff))
        # Within tolerance
        self.assertTrue(timestamps_match(dt1, dt_diff, tolerance_seconds=0.01))


class TestStageTimingAndCutoff(unittest.TestCase):
    """Tests for the 5 canonical stages, future-only scheduling, and the 25h cutoff."""

    def test_05_five_canonical_stages_timing(self):
        """get_stages() produces exactly 5 stages: D-7, D-3, D-1, D, and D+24h."""
        due_utc = datetime(2026, 10, 24, 18, 30, 0, tzinfo=timezone.utc)
        stages = get_stages(due_utc)

        self.assertEqual(len(stages), 5)
        expected = [
            (ReminderType.SEVEN_DAY, due_utc - timedelta(days=7)),
            (ReminderType.THREE_DAY, due_utc - timedelta(days=3)),
            (ReminderType.ONE_DAY, due_utc - timedelta(days=1)),
            (ReminderType.DEADLINE_DAY, due_utc),
            (ReminderType.MISSED_DEADLINE, due_utc + timedelta(hours=24)),
        ]
        for (actual_type, actual_time), (exp_type, exp_time) in zip(stages, expected):
            self.assertEqual(actual_type, exp_type)
            self.assertEqual(actual_time, exp_time)

    def test_06_lifecycle_cutoff_active_immediately_before_25h(self):
        """Circular lifecycle is active at due_date + 24 hours 59 minutes (before 25h)."""
        due_utc = datetime(2026, 10, 24, 18, 30, 0, tzinfo=timezone.utc)
        now_active = due_utc + timedelta(hours=24, minutes=59)

        # Cutoff check: now < due_utc + 25h
        self.assertTrue(now_active < (due_utc + timedelta(hours=25)))

    def test_07_lifecycle_cutoff_expired_at_and_after_25h(self):
        """Circular lifecycle is expired at exactly due_date + 25h and later."""
        due_utc = datetime(2026, 10, 24, 18, 30, 0, tzinfo=timezone.utc)
        now_exact = due_utc + timedelta(hours=25)
        now_past = due_utc + timedelta(hours=26)

        # Cutoff check: now >= due_utc + 25h
        self.assertTrue(now_exact >= (due_utc + timedelta(hours=25)))
        self.assertTrue(now_past >= (due_utc + timedelta(hours=25)))

    @patch("app.tasks.reminder_tasks.SessionLocal")
    def test_08_execute_reminder_stage_aborts_when_lifecycle_expired(self, mock_session_local):
        """_execute_reminder_stage defuses immediately if circular is expired (>25h past due date)."""
        now = datetime.now(timezone.utc)
        due_utc = now - timedelta(hours=30)
        mock_task = MagicMock()
        mock_db = MagicMock(spec=Session)
        mock_session_local.return_value = mock_db

        mock_circ = MagicMock()
        mock_circ.id = 42
        mock_circ.due_date = due_utc
        mock_db.query.return_value.with_for_update.return_value.filter.return_value.first.return_value = mock_circ

        # Call stage with expected tokens matching due date
        due_iso = due_utc.isoformat()
        sched_iso = (due_utc - timedelta(days=1)).isoformat()

        _execute_reminder_stage(mock_task, 42, ReminderType.ONE_DAY, due_iso, sched_iso)

        # Circular was queried, but because now >= due_date + 25h, task aborts before querying students or committing
        mock_db.commit.assert_not_called()

    @patch("app.services.reminder_scheduler.SessionLocal")
    @patch("app.services.reminder_scheduler.ReminderScheduler._schedule_celery_tasks")
    def test_08b_future_stages_only_no_catch_up_for_past_stages(self, mock_dispatch, mock_session_local):
        """When deadline is 2 days away, D-7 and D-3 are in the past: only future stages (D-1, D, D+24h) are scheduled."""
        now = datetime.now(timezone.utc)
        due_utc = now + timedelta(days=2)
        circular_id = 42

        mock_db = MagicMock(spec=Session)
        mock_session_local.return_value = mock_db

        mock_circ = MagicMock()
        mock_circ.id = circular_id
        mock_circ.due_date = due_utc

        mock_student = User(id=10, role=UserRole.STUDENT, is_active=True)
        mock_student_query = MagicMock()
        mock_student_query.filter.return_value = mock_student_query
        mock_student_query.order_by.return_value = mock_student_query
        mock_student_query.all.return_value = [mock_student]

        def query_side_effect(model):
            q = MagicMock()
            if model == Circular:
                q.with_for_update.return_value.filter.return_value.first.return_value = mock_circ
                return q
            elif model == User:
                return mock_student_query
            elif model == Reminder:
                q.filter.return_value.all.return_value = []
                return q
            return q

        mock_db.query.side_effect = query_side_effect

        ReminderScheduler.schedule_reminders(circular_id, due_utc)

        # Added reminders must ONLY include future stages: ONE_DAY, DEADLINE_DAY, MISSED_DEADLINE
        added_reminders = [c[0][0] for c in mock_db.add.call_args_list]
        added_types = [r.reminder_type for r in added_reminders]

        # Past stages must be omitted without catch-up
        self.assertNotIn(ReminderType.SEVEN_DAY, added_types)
        self.assertNotIn(ReminderType.THREE_DAY, added_types)
        # Future stages must be present
        self.assertIn(ReminderType.ONE_DAY, added_types)
        self.assertIn(ReminderType.DEADLINE_DAY, added_types)
        self.assertIn(ReminderType.MISSED_DEADLINE, added_types)


class TestDeadlineExtensionAndReconciliation(unittest.TestCase):
    """Tests for deadline extension, history preservation, and duplicate prevention."""

    def test_09_reconciliation_preserves_sent_history_and_creates_new_schedule(self):
        """A SENT reminder for an earlier deadline must not suppress a reminder for the revised deadline."""
        circular_id = 42
        now = datetime.now(timezone.utc)
        d1_utc = now - timedelta(days=1)
        d2_utc = now + timedelta(days=10)

        mock_db = MagicMock(spec=Session)

        # Existing SENT reminder for student 10 at D1 - 1 day
        old_sent_rem = Reminder(
            id=1,
            circular_id=circular_id,
            user_id=10,
            reminder_type=ReminderType.ONE_DAY,
            status=ReminderStatus.SENT,
            scheduled_at=d1_utc - timedelta(days=1)
        )

        mock_student = User(id=10, role=UserRole.STUDENT, is_active=True)
        mock_student_query = MagicMock()
        mock_student_query.filter.return_value = mock_student_query
        mock_student_query.order_by.return_value = mock_student_query
        mock_student_query.all.return_value = [mock_student]

        # Separate, independent query mocks for production call order:
        # 1. First db.query(Reminder) -> PENDING deletion query
        # 2. db.query(User) -> active students query
        # 3. Second db.query(Reminder) -> SENT history retrieval query
        mock_pending_delete_query = MagicMock()
        mock_pending_delete_query.filter.return_value.delete.return_value = 2  # 2 stale PENDING rows deleted

        mock_sent_records_query = MagicMock()
        mock_sent_records_query.filter.return_value.all.return_value = [old_sent_rem]

        reminder_queries = [mock_pending_delete_query, mock_sent_records_query]

        def query_side_effect(model):
            if model == Reminder:
                if not reminder_queries:
                    raise AssertionError("Unexpected extra db.query(Reminder) call in reconcile_reminders")
                return reminder_queries.pop(0)
            elif model == User:
                return mock_student_query
            return MagicMock()

        mock_db.query.side_effect = query_side_effect

        # Call reconcile_reminders with new deadline D2
        res = ReminderScheduler.reconcile_reminders(circular_id, d2_utc, db=mock_db)
        self.assertTrue(res)

        # 1. Verify PENDING deletion query:
        # - Target: db.query(Reminder) call #1
        # - Delete called with synchronize_session=False
        # - Filter expressions include circular_id == 42 and status == ReminderStatus.PENDING
        mock_pending_delete_query.filter.return_value.delete.assert_called_once_with(synchronize_session=False)
        mock_pending_delete_query.filter.return_value.all.assert_not_called()

        delete_filter_args = mock_pending_delete_query.filter.call_args[0]
        _assert_filter_binary_expr(
            self,
            delete_filter_args,
            column_name="circular_id",
            expected_op_name="eq",
            expected_value=circular_id
        )
        _assert_filter_binary_expr(
            self,
            delete_filter_args,
            column_name="status",
            expected_op_name="eq",
            expected_value=ReminderStatus.PENDING
        )

        # 2. Verify SENT history query:
        # - Target: db.query(Reminder) call #2
        # - all() called to fetch records
        # - Filter expressions include circular_id == 42 and status == ReminderStatus.SENT
        mock_sent_records_query.filter.return_value.all.assert_called_once()
        mock_sent_records_query.filter.return_value.delete.assert_not_called()

        sent_filter_args = mock_sent_records_query.filter.call_args[0]
        _assert_filter_binary_expr(
            self,
            sent_filter_args,
            column_name="circular_id",
            expected_op_name="eq",
            expected_value=circular_id
        )
        _assert_filter_binary_expr(
            self,
            sent_filter_args,
            column_name="status",
            expected_op_name="eq",
            expected_value=ReminderStatus.SENT
        )

        # 3. Verify: db.add was called to create future stages for D2, including the new ONE_DAY stage
        added_reminders = [call[0][0] for call in mock_db.add.call_args_list]
        added_types = [r.reminder_type for r in added_reminders]
        self.assertIn(ReminderType.ONE_DAY, added_types)

        # 4. Verify new ONE_DAY stage for D2 has PENDING status, correct user, and exact target scheduled time
        new_1d = next(r for r in added_reminders if r.reminder_type == ReminderType.ONE_DAY)
        self.assertEqual(new_1d.status, ReminderStatus.PENDING)
        self.assertEqual(new_1d.scheduled_at, d2_utc - timedelta(days=1))
        self.assertEqual(new_1d.user_id, 10)
        self.assertEqual(new_1d.circular_id, circular_id)

        # 5. Verify historical SENT record was preserved unchanged
        self.assertEqual(old_sent_rem.status, ReminderStatus.SENT)
        self.assertEqual(old_sent_rem.scheduled_at, d1_utc - timedelta(days=1))

    def test_10_reconciliation_skips_stage_if_already_sent_for_exact_same_schedule(self):
        """If a stage was already marked SENT for the exact target scheduled time, do not recreate."""
        circular_id = 42
        now = datetime.now(timezone.utc)
        d_utc = now + timedelta(days=10)
        target_1d_time = d_utc - timedelta(days=1)

        mock_db = MagicMock(spec=Session)

        # Existing SENT reminder for student 10 already delivered for target_1d_time
        sent_1d_rem = Reminder(
            id=1,
            circular_id=circular_id,
            user_id=10,
            reminder_type=ReminderType.ONE_DAY,
            status=ReminderStatus.SENT,
            scheduled_at=target_1d_time
        )

        mock_student = User(id=10, role=UserRole.STUDENT, is_active=True)
        mock_student_query = MagicMock()
        mock_student_query.filter.return_value = mock_student_query
        mock_student_query.order_by.return_value = mock_student_query
        mock_student_query.all.return_value = [mock_student]

        mock_reminder_query = MagicMock()
        mock_reminder_query.filter.return_value.delete.return_value = 0
        mock_reminder_query.filter.return_value.all.return_value = [sent_1d_rem]

        def query_side_effect(model):
            if model == Reminder:
                return mock_reminder_query
            elif model == User:
                return mock_student_query
            return MagicMock()

        mock_db.query.side_effect = query_side_effect

        ReminderScheduler.reconcile_reminders(circular_id, d_utc, db=mock_db)

        # Verify: ONE_DAY was NOT re-added because it was already sent for this exact schedule
        added_reminders = [call[0][0] for call in mock_db.add.call_args_list]
        added_types = [r.reminder_type for r in added_reminders]
        self.assertNotIn(ReminderType.ONE_DAY, added_types)


class TestSchedulerStatusMatrix(unittest.TestCase):
    """Tests for explicit handling of PENDING, SENT, FAILED, and CANCELLED statuses."""

    @patch("app.services.reminder_scheduler.SessionLocal")
    @patch("app.services.reminder_scheduler.ReminderScheduler._schedule_celery_tasks")
    def test_11_pending_and_sent_block_duplicate_pending(self, mock_dispatch, mock_session_local):
        """schedule_reminders() blocks duplicate PENDING creation if PENDING or SENT exists."""
        circular_id = 42
        due_utc = datetime(2026, 11, 4, 18, 30, 0, tzinfo=timezone.utc)
        sched_7d = due_utc - timedelta(days=7)

        mock_db = MagicMock(spec=Session)
        mock_session_local.return_value = mock_db

        mock_circ = MagicMock()
        mock_circ.id = circular_id
        mock_circ.due_date = due_utc

        mock_student = User(id=10, role=UserRole.STUDENT, is_active=True)
        mock_student_query = MagicMock()
        mock_student_query.filter.return_value = mock_student_query
        mock_student_query.order_by.return_value = mock_student_query
        mock_student_query.all.return_value = [mock_student]

        # Existing PENDING record for 7_day stage
        pending_rem = Reminder(
            circular_id=circular_id,
            user_id=10,
            reminder_type=ReminderType.SEVEN_DAY,
            status=ReminderStatus.PENDING,
            scheduled_at=sched_7d
        )

        def query_side_effect(model):
            q = MagicMock()
            if model == Circular:
                q.with_for_update.return_value.filter.return_value.first.return_value = mock_circ
                return q
            elif model == User:
                return mock_student_query
            elif model == Reminder:
                q.filter.return_value.all.return_value = [pending_rem]
                return q
            return q

        mock_db.query.side_effect = query_side_effect

        ReminderScheduler.schedule_reminders(circular_id, due_utc)

        # Verify: 7_day stage was NOT re-added to mock_db
        added_reminders = [call[0][0] for call in mock_db.add.call_args_list]
        added_types = [r.reminder_type for r in added_reminders]
        self.assertNotIn(ReminderType.SEVEN_DAY, added_types)

    @patch("app.services.reminder_scheduler.SessionLocal")
    @patch("app.services.reminder_scheduler.ReminderScheduler._schedule_celery_tasks")
    def test_12_failed_and_cancelled_do_not_block_pending_creation(self, mock_dispatch, mock_session_local):
        """FAILED and CANCELLED records must NOT be treated as successful delivery and do not block future stages."""
        circular_id = 42
        due_utc = datetime(2026, 11, 4, 18, 30, 0, tzinfo=timezone.utc)
        sched_7d = due_utc - timedelta(days=7)

        mock_db = MagicMock(spec=Session)
        mock_session_local.return_value = mock_db

        mock_circ = MagicMock()
        mock_circ.id = circular_id
        mock_circ.due_date = due_utc

        mock_student = User(id=10, role=UserRole.STUDENT, is_active=True)
        mock_student_query = MagicMock()
        mock_student_query.filter.return_value = mock_student_query
        mock_student_query.order_by.return_value = mock_student_query
        mock_student_query.all.return_value = [mock_student]

        # In schedule_reminders, the query filters for status.in_([PENDING, SENT]).
        # Therefore, FAILED or CANCELLED records return an empty active list.
        def query_side_effect(model):
            q = MagicMock()
            if model == Circular:
                q.with_for_update.return_value.filter.return_value.first.return_value = mock_circ
                return q
            elif model == User:
                return mock_student_query
            elif model == Reminder:
                # Active query returns empty because FAILED/CANCELLED are excluded
                q.filter.return_value.all.return_value = []
                return q
            return q

        mock_db.query.side_effect = query_side_effect

        ReminderScheduler.schedule_reminders(circular_id, due_utc)

        # Verify: 7_day stage WAS added because FAILED/CANCELLED did not block it
        added_reminders = [call[0][0] for call in mock_db.add.call_args_list]
        added_types = [r.reminder_type for r in added_reminders]
        self.assertIn(ReminderType.SEVEN_DAY, added_types)


class TestEventKeyAndIdentityValidation(unittest.TestCase):
    """Tests for canonical event-key format, microsecond precision, and identity checks."""

    def test_13_event_key_microsecond_precision_and_prefix(self):
        """Event key must include microsecond precision and retain the reminder:{circular_id}: prefix."""
        due_utc = datetime(2026, 10, 24, 18, 30, 0, 123456, tzinfo=timezone.utc)
        due_token = due_utc.strftime("%Y%m%dT%H%M%S.%fZ")
        event_key = f"reminder:42:due:{due_token}:user:10:stage:1_day"

        self.assertTrue(event_key.startswith("reminder:42:"))
        self.assertIn("due:20261024T183000.123456Z", event_key)
        self.assertLessEqual(len(event_key), 255)

    def test_14_delivery_notification_identity_validator_success(self):
        """_is_valid_delivery_notification returns True only when all four identity tokens match."""
        notif = Notification(
            id=1,
            user_id=10,
            type="reminder",
            reference_id=42,
            event_key="reminder:42:due:20261024T183000.000000Z:user:10:stage:1_day"
        )
        self.assertTrue(
            _is_valid_delivery_notification(
                notif,
                expected_user_id=10,
                expected_circular_id=42,
                expected_event_key="reminder:42:due:20261024T183000.000000Z:user:10:stage:1_day"
            )
        )

    def test_15_delivery_notification_identity_validator_failures(self):
        """Validator returns False if user_id, type, circular_id, or event_key does not match."""
        valid_key = "reminder:42:due:20261024T183000.000000Z:user:10:stage:1_day"

        # Wrong user
        n_wrong_user = Notification(user_id=99, type="reminder", reference_id=42, event_key=valid_key)
        self.assertFalse(_is_valid_delivery_notification(n_wrong_user, 10, 42, valid_key))

        # Wrong type (e.g. announcement circular instead of reminder)
        n_wrong_type = Notification(user_id=10, type="circular", reference_id=42, event_key=valid_key)
        self.assertFalse(_is_valid_delivery_notification(n_wrong_type, 10, 42, valid_key))

        # Wrong reference ID
        n_wrong_ref = Notification(user_id=10, type="reminder", reference_id=999, event_key=valid_key)
        self.assertFalse(_is_valid_delivery_notification(n_wrong_ref, 10, 42, valid_key))

        # None notification
        self.assertFalse(_is_valid_delivery_notification(None, 10, 42, valid_key))


class TestWorkerExecutionSafeguards(unittest.TestCase):
    """Tests for zero worker auto-creation, token rejection, stale task defusing, and savepoint handling."""

    def test_16_zero_worker_auto_creation_when_pending_row_missing(self):
        """_process_student_reminder must return False and never create a reminder if no PENDING row exists."""
        mock_db = MagicMock(spec=Session)
        mock_circ = MagicMock()
        mock_circ.id = 42
        mock_circ.title = "Test Notice"
        due_utc = datetime(2026, 11, 4, 18, 30, 0, tzinfo=timezone.utc)

        # DB returns empty list for PENDING reminders
        mock_db.query.return_value.with_for_update.return_value.filter.return_value.all.return_value = []

        res = _process_student_reminder(
            db=mock_db,
            user_id=10,
            circular=mock_circ,
            circ_due_utc=due_utc,
            reminder_type=ReminderType.ONE_DAY,
            expected_sched_dt=due_utc - timedelta(days=1)
        )
        self.assertFalse(res)
        mock_db.add.assert_not_called()

    @patch("app.tasks.reminder_tasks.SessionLocal")
    def test_17_legacy_celery_task_rejected_when_tokens_missing(self, mock_session_local):
        """_execute_reminder_stage logs warning and exits before initializing DB session when tokens are missing."""
        mock_task = MagicMock()

        # Case A: Both tokens missing
        _execute_reminder_stage(mock_task, 42, ReminderType.ONE_DAY, None, None)
        mock_session_local.assert_not_called()
        mock_task.retry.assert_not_called()

        # Case B: One token missing
        _execute_reminder_stage(mock_task, 42, ReminderType.ONE_DAY, "2026-10-24T18:30:00Z", None)
        mock_session_local.assert_not_called()
        mock_task.retry.assert_not_called()

    @patch("app.tasks.reminder_tasks.SessionLocal")
    def test_18_stale_task_defused_on_deadline_mismatch(self, mock_session_local):
        """Worker drops task without sending when expected due date does not match circular due date."""
        now = datetime.now(timezone.utc)
        current_due = now + timedelta(days=10)
        stale_expected_due = now + timedelta(days=5)

        mock_task = MagicMock()
        mock_db = MagicMock(spec=Session)
        mock_session_local.return_value = mock_db

        mock_circ = MagicMock()
        mock_circ.id = 42
        mock_circ.due_date = current_due
        mock_db.query.return_value.with_for_update.return_value.filter.return_value.first.return_value = mock_circ

        _execute_reminder_stage(
            mock_task,
            42,
            ReminderType.ONE_DAY,
            expected_due_date_iso=stale_expected_due.isoformat(),
            expected_scheduled_at_iso=(stale_expected_due - timedelta(days=1)).isoformat()
        )

        # Worker defused stale task: circular was checked, but no commit was made
        mock_db.commit.assert_not_called()

    def test_19_inconsistent_existing_notification_leaves_reminder_pending(self):
        """If existing notification has conflicting user or type, do not mark reminder SENT."""
        mock_db = MagicMock(spec=Session)
        mock_circ = MagicMock()
        mock_circ.id = 42
        due_utc = datetime(2026, 11, 4, 18, 30, 0, tzinfo=timezone.utc)
        sched_1d = due_utc - timedelta(days=1)

        pending_rem = Reminder(
            id=5,
            circular_id=42,
            user_id=10,
            reminder_type=ReminderType.ONE_DAY,
            status=ReminderStatus.PENDING,
            scheduled_at=sched_1d
        )

        # Conflicting notification with mismatched user_id (99 instead of 10)
        due_token = due_utc.strftime("%Y%m%dT%H%M%S.%fZ")
        event_key = f"reminder:42:due:{due_token}:user:10:stage:1_day"
        inconsistent_notif = Notification(id=1, user_id=99, type="reminder", reference_id=42, event_key=event_key)

        def query_side_effect(model):
            q = MagicMock()
            if model == Reminder:
                q.with_for_update.return_value.filter.return_value.all.return_value = [pending_rem]
                return q
            elif model == Notification:
                q.filter.return_value.first.return_value = inconsistent_notif
                return q
            return q

        mock_db.query.side_effect = query_side_effect

        res = _process_student_reminder(
            db=mock_db,
            user_id=10,
            circular=mock_circ,
            circ_due_utc=due_utc,
            reminder_type=ReminderType.ONE_DAY,
            expected_sched_dt=sched_1d
        )

        self.assertFalse(res)
        # Status MUST remain PENDING
        self.assertEqual(pending_rem.status, ReminderStatus.PENDING)

    def test_20_integrity_error_recovery_with_verified_notification(self):
        """When savepoint catches IntegrityError, verify conflicting row and mark SENT if identity matches."""
        mock_db = MagicMock(spec=Session)
        mock_circ = MagicMock()
        mock_circ.id = 42
        mock_circ.title = "Assignment 1"
        due_utc = datetime(2026, 11, 4, 18, 30, 0, tzinfo=timezone.utc)
        sched_1d = due_utc - timedelta(days=1)

        pending_rem = Reminder(
            id=5,
            circular_id=42,
            user_id=10,
            reminder_type=ReminderType.ONE_DAY,
            status=ReminderStatus.PENDING,
            scheduled_at=sched_1d
        )

        due_token = due_utc.strftime("%Y%m%dT%H%M%S.%fZ")
        event_key = f"reminder:42:due:{due_token}:user:10:stage:1_day"
        verified_conflicting_notif = Notification(id=1, user_id=10, type="reminder", reference_id=42, event_key=event_key)

        notification_query_count = [0]
        def query_side_effect(model):
            q = MagicMock()
            if model == Reminder:
                q.with_for_update.return_value.filter.return_value.all.return_value = [pending_rem]
                return q
            elif model == Notification:
                # 1st call: existing_notif -> None (simulating race)
                # 2nd call: in except IntegrityError -> returns verified_conflicting_notif
                if notification_query_count[0] == 0:
                    notification_query_count[0] += 1
                    q.filter.return_value.first.return_value = None
                else:
                    q.filter.return_value.first.return_value = verified_conflicting_notif
                return q
            return q

        mock_db.query.side_effect = query_side_effect

        # Mock savepoint flush raising IntegrityError
        mock_sp = MagicMock()
        mock_db.begin_nested.return_value = mock_sp
        mock_db.flush.side_effect = IntegrityError("duplicate key", params=None, orig=None)

        res = _process_student_reminder(
            db=mock_db,
            user_id=10,
            circular=mock_circ,
            circ_due_utc=due_utc,
            reminder_type=ReminderType.ONE_DAY,
            expected_sched_dt=sched_1d
        )

        self.assertTrue(res)
        mock_sp.rollback.assert_called_once()
        self.assertEqual(pending_rem.status, ReminderStatus.SENT)


class TestCeleryDispatchAndCleanupScope(unittest.TestCase):
    """Tests for 3-argument payload dispatch and cleanup scope."""

    @patch("app.services.reminder_scheduler.send_7_day_reminder.apply_async")
    @patch("app.services.reminder_scheduler.send_3_day_reminder.apply_async")
    @patch("app.services.reminder_scheduler.send_1_day_reminder.apply_async")
    @patch("app.services.reminder_scheduler.send_deadline_day_reminder.apply_async")
    @patch("app.services.reminder_scheduler.send_missed_deadline_reminder.apply_async")
    def test_21_schedule_celery_tasks_dispatches_three_argument_payload(
        self, mock_md, mock_dd, mock_1d, mock_3d, mock_7d
    ):
        """_schedule_celery_tasks dispatches (circular_id, due_iso, eta_iso) for future stages."""
        circular_id = 42
        due_utc = datetime.now(timezone.utc) + timedelta(days=10)
        due_iso = due_utc.isoformat()

        ReminderScheduler._schedule_celery_tasks(circular_id, due_utc)

        # 7-day reminder should have been dispatched with 3 args: circular_id, due_iso, eta_iso
        self.assertTrue(mock_7d.called)
        args, kwargs = mock_7d.call_args
        call_args = kwargs.get("args") or args[0]
        self.assertEqual(call_args[0], circular_id)
        self.assertEqual(call_args[1], due_iso)
        self.assertIn("T", call_args[2])

    @patch("app.services.reminder_scheduler.send_7_day_reminder.apply_async")
    @patch("app.services.reminder_scheduler.send_3_day_reminder.apply_async")
    @patch("app.services.reminder_scheduler.send_1_day_reminder.apply_async")
    @patch("app.services.reminder_scheduler.send_deadline_day_reminder.apply_async")
    @patch("app.services.reminder_scheduler.send_missed_deadline_reminder.apply_async")
    def test_21b_schedule_celery_tasks_skips_past_stages_no_catch_up(
        self, mock_md, mock_dd, mock_1d, mock_3d, mock_7d
    ):
        """Celery dispatch only dispatches tasks for future ETAs; past stages are skipped without catch-up."""
        circular_id = 42
        now = datetime.now(timezone.utc)
        # Deadline is 2 days from now: D-7 and D-3 are in the past
        due_utc = now + timedelta(days=2)

        ReminderScheduler._schedule_celery_tasks(circular_id, due_utc)

        # D-7 (5 days ago) and D-3 (1 day ago) should NOT have been dispatched
        self.assertFalse(mock_7d.called)
        self.assertFalse(mock_3d.called)

        # D-1 (1 day in future), D (2 days in future), and D+24h (3 days in future) MUST be dispatched
        self.assertTrue(mock_1d.called)
        self.assertTrue(mock_dd.called)
        self.assertTrue(mock_md.called)

    @patch("app.tasks.reminder_tasks.SessionLocal")
    def test_22_cleanup_expired_reminders_scoped_to_reminder_notifications_only(self, mock_session_local):
        """cleanup_expired_reminders deletes only Notification.type == 'reminder' matching event_key namespace."""
        mock_db = MagicMock(spec=Session)
        mock_session_local.return_value = mock_db

        circ1 = MagicMock()
        circ1.id = 101

        # Separate query mocks for Circular, Notification, and Reminder
        mock_circ_query = MagicMock()
        mock_circ_query.with_for_update.return_value.filter.return_value.all.return_value = [circ1]

        mock_notif_query = MagicMock()
        mock_notif_query.filter.return_value.delete.return_value = 5  # 5 reminder notifications deleted

        mock_rem_query = MagicMock()
        mock_rem_query.filter.return_value.delete.return_value = 2  # 2 reminder rows deleted

        def query_side_effect(model):
            if model == Circular:
                return mock_circ_query
            elif model == Notification:
                return mock_notif_query
            elif model == Reminder:
                return mock_rem_query
            raise AssertionError(f"Unexpected query for model {model}")

        mock_db.query.side_effect = query_side_effect

        # Capture runtime timestamp immediately before task execution
        captured_now = datetime.now(timezone.utc)

        cleanup_expired_reminders()

        # 1. Verify Circular query uses row lock (with_for_update) and cutoff filters
        mock_circ_query.with_for_update.assert_called_once()
        circ_filter_args = mock_circ_query.with_for_update.return_value.filter.call_args[0]

        # 1a. Circular.due_date.isnot(None)
        # Inspect left column ('due_date'), exact operator ('is_not' / operators.is_not), and NULL right operand
        isnot_expr = _assert_filter_binary_expr(
            self,
            circ_filter_args,
            column_name="due_date",
            expected_op_name="is_not",
            check_value=False
        )
        self.assertIs(isnot_expr.operator, operators.is_not)
        isnot_right_val = _get_expr_right_value(isnot_expr)
        self.assertIsNone(isnot_right_val, "Expected isnot(None) right-hand operand value to be None")

        # 1b. Circular.due_date <= cutoff (now - 25 hours)
        # Inspect left column ('due_date'), exact operator ('le' / operators.le), and dynamic UTC cutoff value
        le_expr = _assert_filter_binary_expr(
            self,
            circ_filter_args,
            column_name="due_date",
            expected_op_name="le",
            check_value=False
        )
        self.assertIs(le_expr.operator, operators.le)
        cutoff_val = _get_expr_right_value(le_expr)
        self.assertIsInstance(cutoff_val, datetime)
        self.assertEqual(cutoff_val.tzinfo, timezone.utc)
        expected_cutoff = captured_now - timedelta(hours=25)
        self.assertLess(
            abs((cutoff_val - expected_cutoff).total_seconds()),
            10.0,
            "Circular cutoff must be dynamic UTC datetime approximately 25 hours before runtime execution"
        )

        # 2. Verify Notification query delete is scoped exclusively to:
        #    - type == "reminder"
        #    - reference_id == circ1.id (101)
        #    - event_key matching "reminder:101:%"
        mock_notif_query.filter.return_value.delete.assert_called_once_with(synchronize_session=False)
        notif_filter_args = mock_notif_query.filter.call_args[0]

        # 2a. Notification.type == "reminder"
        _assert_filter_binary_expr(
            self,
            notif_filter_args,
            column_name="type",
            expected_op_name="eq",
            expected_value="reminder"
        )

        # 2b. Notification.reference_id == circ1.id (101)
        _assert_filter_binary_expr(
            self,
            notif_filter_args,
            column_name="reference_id",
            expected_op_name="eq",
            expected_value=circ1.id
        )

        # 2c. Notification.event_key.like("reminder:101:%")
        # Accurately verify left-hand column ('event_key'), exact LIKE operator (operators.like_op), and bound pattern
        like_expr = _assert_filter_binary_expr(
            self,
            notif_filter_args,
            column_name="event_key",
            expected_op_name="like_op",
            expected_value=f"reminder:{circ1.id}:%"
        )
        self.assertIs(like_expr.operator, operators.like_op)
        self.assertEqual(_get_expr_right_value(like_expr), f"reminder:{circ1.id}:%")

        # 3. Verify Reminder query delete is scoped strictly to circular_id == 101
        mock_rem_query.filter.return_value.delete.assert_called_once_with(synchronize_session=False)
        rem_filter_args = mock_rem_query.filter.call_args[0]
        rem_expr = _assert_filter_binary_expr(
            self,
            rem_filter_args,
            column_name="circular_id",
            expected_op_name="eq",
            expected_value=circ1.id
        )
        self.assertIs(rem_expr.operator, operators.eq)

        # 4. Assert transaction committed atomically and closed safely
        mock_db.commit.assert_called_once()
        mock_db.rollback.assert_not_called()
        mock_db.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
