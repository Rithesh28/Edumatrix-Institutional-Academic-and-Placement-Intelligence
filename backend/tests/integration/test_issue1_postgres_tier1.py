"""
EduMatrix Issue 1 — Tier 1 PostgreSQL Integration Test Suite
=============================================================
Target: Real PostgreSQL Staging Database (Port 5433) + Celery Eager Mode

SAFETY PROTOCOL & INVARIANTS:
1. Strict Fail-Closed Preflight: Refuses any connection pointing to port 5432,
   port 6379, or the active development database ('edumatrix').
2. Database Whitelist: Connects ONLY to 'edumatrix_staging' on loopback port 5433.
3. Broker Isolation: Uses 'memory://' broker and Celery eager mode (task_always_eager=True).
4. Five-Table Allowlist: Creates ONLY users, files, circulars, reminders, notifications.
5. In-Place Factory Reconfiguration: Safely binds SessionLocal to staging_engine,
   with guaranteed restoration in tearDownClass.
6. Scoped Table Cleanup: Cleans up only verified staging tables between tests.
7. Lightweight FastAPI App: Bypasses the global app.main lifespan.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import types
from pathlib import Path
import unittest
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse
from unittest.mock import patch, MagicMock

# Module logger for credential-safe cleanup reporting
log = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# Test-Only Package Import Isolation
# -------------------------------------------------------------------------
# 1. backend/app/api/__init__.py eagerly imports all 16 application routers
#    (including chat, ai, study_buddy), which cascades into optional ML
#    dependencies (sentence_transformers, torch, transformers) not required
#    for Tier 1 integration tests.
# 2. backend/app/tasks/__init__.py eagerly imports all task modules (including
#    file_tasks, duty_tasks, placement_tasks), which cascades into minio,
#    text_extractor, pdfplumber, and optional vector/ML dependencies.
#
# Pre-populating sys.modules["app.api"] and sys.modules["app.tasks"] as package
# modules allows direct resolution of required submodules (app.api.auth,
# app.api.reminders, app.tasks.celery_app, app.tasks.reminder_tasks) without
# executing package initializers or loading unrelated heavy dependencies.
import app

_backend_dir = Path(__file__).resolve().parents[2]
_api_dir = _backend_dir / "app" / "api"
if "app.api" not in sys.modules:
    _api_pkg = types.ModuleType("app.api")
    _api_pkg.__path__ = [str(_api_dir)]
    _api_pkg.__file__ = str(_api_dir / "__init__.py")
    _api_pkg.__package__ = "app.api"
    sys.modules["app.api"] = _api_pkg
    setattr(app, "api", _api_pkg)

_tasks_dir = _backend_dir / "app" / "tasks"
if "app.tasks" not in sys.modules:
    _tasks_pkg = types.ModuleType("app.tasks")
    _tasks_pkg.__path__ = [str(_tasks_dir)]
    _tasks_pkg.__file__ = str(_tasks_dir / "__init__.py")
    _tasks_pkg.__package__ = "app.tasks"
    sys.modules["app.tasks"] = _tasks_pkg
    setattr(app, "tasks", _tasks_pkg)

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

# Application models & core
import app.models  # Ensures mapper registry resolves all cross-model relationship strings
from app.core.database import Base, SessionLocal, get_db
from app.api.auth import get_current_user
from app.models.user import User, UserRole
from app.models.file import File, FileStatus
from app.models.circular import Circular, CircularType
from app.models.reminder import Reminder, ReminderType, ReminderStatus, ReminderChannel
from app.models.notification import Notification

# Tasks, Scheduler & API Routers
from app.tasks.celery_app import celery_app
from app.tasks.reminder_tasks import (
    _execute_reminder_stage,
    send_7_day_reminder,
    send_3_day_reminder,
    send_1_day_reminder,
    send_deadline_day_reminder,
    send_missed_deadline_reminder,
)
from app.services.reminder_scheduler import ReminderScheduler, normalize_to_utc
from app.api.reminders import router as reminders_router


# =========================================================================
# 1. FAIL-CLOSED CONNECTION GUARDS
# =========================================================================

EXPECTED_STAGING_PORT = 5433
EXPECTED_STAGING_DB = "edumatrix_staging"
EXPECTED_STAGING_USER = "edumatrix_staging_user"
EXPECTED_STAGING_CONTAINER_PORT = 5432

# Dedicated disposable integration-test PostgreSQL target.
EXPECTED_TIER1_TEST_PORT = 5434
EXPECTED_TIER1_TEST_DB = "edumatrix_tier1_test"
EXPECTED_TIER1_TEST_USER = "edumatrix_tier1_test_user"
EXPECTED_TIER1_TEST_CONTAINER_PORT = 5432

FORBIDDEN_DEV_PORT = 5432
FORBIDDEN_DEV_DB = "edumatrix"
FORBIDDEN_REDIS_PORT = 6379

APPROVED_TABLE_NAMES = [
    "users",
    "files",
    "circulars",
    "reminders",
    "notifications",
]


def assert_safe_staging_database_url(url_string: str) -> None:
    """
    Validates that the database connection string strictly targets the dedicated
    staging PostgreSQL database on port 5433 and never the active development stack.
    """
    if not url_string:
        raise RuntimeError("CRITICAL SAFETY VIOLATION: STAGING_DATABASE_URL is empty or not configured.")

    parsed = urlparse(url_string)

    # 1. Host must be strictly loopback
    if parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError(
            f"CRITICAL SAFETY VIOLATION: Host '{parsed.hostname}' is not a local loopback address."
        )

    # 2. Port must strictly be 5433 (never 5432 or unset)
    if parsed.port != EXPECTED_STAGING_PORT:
        raise RuntimeError(
            f"CRITICAL SAFETY VIOLATION: Port {parsed.port} is not the approved staging port ({EXPECTED_STAGING_PORT}). "
            f"Active development port ({FORBIDDEN_DEV_PORT}) is strictly forbidden."
        )

    # 3. Database name must strictly be 'edumatrix_staging'
    db_name = (parsed.path or "").lstrip("/")
    if db_name != EXPECTED_STAGING_DB:
        raise RuntimeError(
            f"CRITICAL SAFETY VIOLATION: Target database '{db_name}' is not '{EXPECTED_STAGING_DB}'. "
            f"Active development database ('{FORBIDDEN_DEV_DB}') is strictly forbidden."
        )

    # 4. User must strictly be 'edumatrix_staging_user'
    if parsed.username != EXPECTED_STAGING_USER:
        raise RuntimeError(
            f"CRITICAL SAFETY VIOLATION: User '{parsed.username}' is not '{EXPECTED_STAGING_USER}'."
        )


def assert_safe_tier1_test_database_url(url_string: str) -> None:
    """Allow writes only to the explicitly isolated Tier 1 test database."""
    if not url_string:
        raise RuntimeError(
            "CRITICAL SAFETY VIOLATION: TIER1_TEST_DATABASE_URL is empty or not configured."
        )

    parsed = urlparse(url_string)

    if not (parsed.scheme or "").startswith("postgresql"):
        raise RuntimeError("CRITICAL SAFETY VIOLATION: Test URL must use PostgreSQL.")

    if parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError(
            f"CRITICAL SAFETY VIOLATION: Test database host '{parsed.hostname}' is not loopback."
        )

    if parsed.port != EXPECTED_TIER1_TEST_PORT:
        raise RuntimeError(
            f"CRITICAL SAFETY VIOLATION: Test database port must be "
            f"{EXPECTED_TIER1_TEST_PORT}, got {parsed.port}."
        )

    db_name = (parsed.path or "").lstrip("/")
    if db_name != EXPECTED_TIER1_TEST_DB:
        raise RuntimeError(
            f"CRITICAL SAFETY VIOLATION: Test database must be "
            f"'{EXPECTED_TIER1_TEST_DB}', got '{db_name}'."
        )

    if parsed.username != EXPECTED_TIER1_TEST_USER:
        raise RuntimeError(
            f"CRITICAL SAFETY VIOLATION: Test database user must be "
            f"'{EXPECTED_TIER1_TEST_USER}'."
        )

    if parsed.query or parsed.fragment:
        raise RuntimeError(
            "CRITICAL SAFETY VIOLATION: Test database URL must not contain a query or fragment."
        )


def assert_safe_celery_broker() -> None:
    """
    Fail-closed safety guard:
    1. Broker: Both effective (conf.broker_url) and constructor-level (_broker_url)
       must be explicitly 'memory://'. Reject any Redis broker, port 6379, or non-memory URL.
    2. Result backend: Both effective (conf.result_backend) and constructor-level (backend_cls, _backend)
       must be None or empty string. Reject Redis, port 6379, 'disabled', and any non-empty backend.
    """
    conf_broker = celery_app.conf.broker_url
    app_broker = getattr(celery_app, "_broker_url", None)
    env_broker = os.environ.get("CELERY_BROKER_URL")
    conf_backend = celery_app.conf.result_backend
    app_backend_cls = getattr(celery_app, "backend_cls", None)
    app_backend = getattr(celery_app, "_backend", None)
    env_backend = os.environ.get("CELERY_RESULT_BACKEND")

    broker_targets = [
        ("celery_app.conf.broker_url", conf_broker),
        ("celery_app._broker_url", app_broker),
        ("os.environ['CELERY_BROKER_URL']", env_broker),
    ]
    for target_name, b_val in broker_targets:
        b_str = str(b_val or "")
        if f":{FORBIDDEN_REDIS_PORT}" in b_str or "redis" in b_str.lower():
            raise RuntimeError(
                f"CRITICAL SAFETY VIOLATION: {target_name} points to active development Redis ({FORBIDDEN_REDIS_PORT}): '{b_str}'"
            )
        if b_val != "memory://":
            raise RuntimeError(
                f"CRITICAL SAFETY VIOLATION: {target_name} is not explicitly 'memory://': '{b_val}'"
            )

    backend_targets = [
        ("celery_app.conf.result_backend", conf_backend),
        ("celery_app.backend_cls", app_backend_cls),
        ("celery_app._backend", app_backend),
        ("os.environ['CELERY_RESULT_BACKEND']", env_backend),
    ]
    for target_name, be_val in backend_targets:
        be_str = str(be_val or "")
        if f":{FORBIDDEN_REDIS_PORT}" in be_str or "redis" in be_str.lower():
            raise RuntimeError(
                f"CRITICAL SAFETY VIOLATION: {target_name} points to active development Redis ({FORBIDDEN_REDIS_PORT}): '{be_str}'"
            )
        if be_val not in (None, ""):
            raise RuntimeError(
                f"CRITICAL SAFETY VIOLATION: {target_name} must be disabled (None or '') for Tier 1 tests, but got: '{be_val}'"
            )


# =========================================================================
# 2. LIGHTWEIGHT TEST APP FACTORY
# =========================================================================

def build_lightweight_test_app() -> FastAPI:
    """
    Builds an isolated FastAPI application containing ONLY the Issue 1 reminders router
    (the only router exercised via HTTP in this test suite).
    Completely avoids app.main lifespan, unneeded model creation, and AI pre-warming.
    """
    test_app = FastAPI(title="EduMatrix Issue 1 Integration Test App")
    test_app.include_router(reminders_router)
    return test_app


# =========================================================================
# 3. TIER 1 INTEGRATION TEST SUITE
# =========================================================================

class TestIssue1PostgresTier1(unittest.TestCase):
    """
    Tier 1 Integration Tests verifying real PostgreSQL constraints, transactions,
    idempotency, scheduling cutoffs, and API visibility using Celery eager mode.
    """

    engine: Engine
    test_sessionmaker: sessionmaker
    orig_sessionmaker_bind: Optional[Engine] = None
    orig_celery_always_eager: bool = False
    orig_celery_eager_propagates: bool = False
    orig_celery_broker_url: Optional[str] = None
    orig_celery_result_backend: Optional[str] = None
    orig_celery_app_broker: Optional[str] = None
    orig_celery_backend_cls: Optional[str] = None
    orig_celery_backend_cache: Optional[object] = None
    orig_env_celery_broker_url: Optional[str] = None
    orig_env_celery_result_backend: Optional[str] = None

    test_app: FastAPI
    client: TestClient
    current_auth_user: Optional[User] = None

    @classmethod
    def setUpClass(cls):
        """Preflight guards, isolated schema creation, and in-place factory reconfiguration."""
        # Require the explicit disposable integration-test URL; never fall back to staging.
        test_url = os.environ.get("TIER1_TEST_DATABASE_URL")
        assert_safe_tier1_test_database_url(test_url)

        # Connect only to the dedicated disposable Tier 1 test PostgreSQL.
        # Use Psycopg 3 for this isolated test connection; keep the validated URL target unchanged.
        from sqlalchemy.engine import make_url
        test_url = make_url(test_url).set(drivername="postgresql+psycopg")
        cls.engine = create_engine(test_url, pool_pre_ping=True)
        # Register engine disposal immediately so partial setup failures release the pool.
        cls.addClassCleanup(cls.engine.dispose)

        # Verify live database identity before creating tables or allowing test writes.
        with cls.engine.connect() as conn:
            live_db, live_user, live_port = conn.execute(
                text("SELECT current_database(), current_user, current_setting('port')::integer;")
            ).fetchone()
            if (
                live_db != EXPECTED_TIER1_TEST_DB
                or live_user != EXPECTED_TIER1_TEST_USER
                or live_port != EXPECTED_TIER1_TEST_CONTAINER_PORT
            ):
                raise RuntimeError(
                    f"Live test database identity mismatch: got ({live_db}, {live_user}, {live_port}), "
                    f"expected ({EXPECTED_TIER1_TEST_DB}, {EXPECTED_TIER1_TEST_USER}, "
                    f"{EXPECTED_TIER1_TEST_CONTAINER_PORT})"
                )

        # Create sessionmaker bound only to the disposable test database
        cls.test_sessionmaker = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

        # Initialize ONLY the 5 approved tables in PostgreSQL
        target_tables = [
            Base.metadata.tables[name]
            for name in APPROVED_TABLE_NAMES
            if name in Base.metadata.tables
        ]
        if len(target_tables) != len(APPROVED_TABLE_NAMES):
            raise RuntimeError(f"Expected {len(APPROVED_TABLE_NAMES)} tables in metadata, resolved {len(target_tables)}")

        # Fail closed if the dedicated test database contains unexpected objects.
        # This check is read-only and runs before any schema creation.
        # Allow expected schema (5 tables + their sequences) from previous runs, reject unexpected objects.
        with cls.engine.connect() as conn:
            existing_objects = conn.execute(text("""
                SELECT n.nspname, c.relname, c.relkind
                FROM pg_catalog.pg_class AS c
                JOIN pg_catalog.pg_namespace AS n
                  ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
                ORDER BY n.nspname, c.relname;
            """)).fetchall()

            # Expected objects: 5 approved tables + their sequences
            unexpected_objects = []
            # Explicit allowlist of sequences created by SQLAlchemy for the 5 approved tables
            # users, files (UUID, no sequence), circulars, reminders, notifications
            APPROVED_SEQUENCES = {
                "users_id_seq",
                "circulars_id_seq",
                "reminders_id_seq",
                "notifications_id_seq",
            }
            for schema, name, kind in existing_objects:
                lower_name = name.lower()
                # Table objects
                if kind in ('r', 'p'):  # ordinary table, partitioned table
                    if lower_name not in [t.lower() for t in APPROVED_TABLE_NAMES]:
                        unexpected_objects.append((schema, name, kind))
                # Sequence objects
                elif kind == 'S':  # sequence
                    # Allow only the explicitly approved sequences
                    if lower_name not in APPROVED_SEQUENCES:
                        unexpected_objects.append((schema, name, kind))
                else:
                    # For views, materialized views, foreign tables, functions - skip for now
                    pass

            if unexpected_objects:
                object_summary = [
                    f"{schema}.{name} (kind={kind})"
                    for schema, name, kind in unexpected_objects
                ]
                raise RuntimeError(
                    "Refusing to initialize Tier 1 test database with unexpected objects. "
                    f"Unexpected objects: {object_summary}"
                )

        # Mutate SessionLocal in-place so all imported references in tasks & scheduler bind to staging
        cls.orig_sessionmaker_bind = SessionLocal.kw.get("bind")
        # Register SessionLocal restoration immediately to guarantee rebound on any setup failure
        cls.addClassCleanup(SessionLocal.configure, bind=cls.orig_sessionmaker_bind)
        SessionLocal.configure(bind=cls.engine)

        # Configure Celery in Eager Mode with in-memory broker and disabled result backend
        # 1. Capture all original Celery state and environment variables BEFORE any mutation
        cls.orig_env_celery_broker_url = os.environ.get("CELERY_BROKER_URL")
        cls.orig_env_celery_result_backend = os.environ.get("CELERY_RESULT_BACKEND")
        cls.orig_celery_always_eager = celery_app.conf.task_always_eager
        cls.orig_celery_eager_propagates = celery_app.conf.task_eager_propagates
        cls.orig_celery_broker_url = celery_app.conf.broker_url
        cls.orig_celery_result_backend = celery_app.conf.result_backend
        cls.orig_celery_app_broker = getattr(celery_app, "_broker_url", None)
        cls.orig_celery_backend_cls = getattr(celery_app, "backend_cls", None)
        cls.orig_celery_backend_cache = getattr(celery_app, "_backend_cache", None)

        def _restore_celery():
            # Attempt each restoration independently; log failures without
            # preventing the remaining original state from being restored.
            def _attempt_restore(label, operation):
                try:
                    operation()
                except Exception:
                    logging.getLogger(__name__).exception(
                        "Celery cleanup: failed to %s", label
                    )

            def _restore_env(name, value):
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

            _attempt_restore(
                "restore CELERY_BROKER_URL environment",
                lambda: _restore_env(
                    "CELERY_BROKER_URL", cls.orig_env_celery_broker_url
                ),
            )
            _attempt_restore(
                "restore CELERY_RESULT_BACKEND environment",
                lambda: _restore_env(
                    "CELERY_RESULT_BACKEND", cls.orig_env_celery_result_backend
                ),
            )
            _attempt_restore(
                "restore Celery configuration",
                lambda: celery_app.conf.update(
                    task_always_eager=cls.orig_celery_always_eager,
                    task_eager_propagates=cls.orig_celery_eager_propagates,
                    broker_url=cls.orig_celery_broker_url,
                    result_backend=cls.orig_celery_result_backend,
                ),
            )
            _attempt_restore(
                "restore Celery broker property",
                lambda: setattr(celery_app.conf, "broker_url", cls.orig_celery_broker_url),
            )
            _attempt_restore(
                "restore Celery result-backend property",
                lambda: setattr(
                    celery_app.conf, "result_backend", cls.orig_celery_result_backend
                ),
            )
            _attempt_restore(
                "restore Celery broker configuration entry",
                lambda: celery_app.conf.__setitem__(
                    "broker_url", cls.orig_celery_broker_url
                ),
            )
            _attempt_restore(
                "restore Celery result-backend configuration entry",
                lambda: celery_app.conf.__setitem__(
                    "result_backend", cls.orig_celery_result_backend
                ),
            )
            _attempt_restore(
                "restore Celery internal broker URL",
                lambda: setattr(celery_app, "_broker_url", cls.orig_celery_app_broker),
            )
            _attempt_restore(
                "restore Celery backend class",
                lambda: setattr(celery_app, "backend_cls", cls.orig_celery_backend_cls),
            )
            if hasattr(celery_app, "_backend_cache"):
                _attempt_restore(
                    "restore Celery backend cache",
                    lambda: setattr(
                        celery_app, "_backend_cache", cls.orig_celery_backend_cache
                    ),
                )

        # 2. Register restoration callback BEFORE the first Celery mutation
        cls.addClassCleanup(_restore_celery)

        # 3. Configure in-memory broker and disable result backend across environment, instance, and conf.
        # Celery 5.x Settings.broker_url and Settings.result_backend prioritize CELERY_BROKER_URL
        # and CELERY_RESULT_BACKEND from os.environ over conf dictionary entries. Explicitly align
        # the environment so the effective property getters resolve to in-memory broker and disabled backend.
        os.environ["CELERY_BROKER_URL"] = "memory://"
        os.environ.pop("CELERY_RESULT_BACKEND", None)

        celery_app._broker_url = "memory://"
        celery_app.backend_cls = None
        if hasattr(celery_app, "_backend_cache"):
            celery_app._backend_cache = None
        celery_app.conf.broker_url = "memory://"
        celery_app.conf.result_backend = None
        celery_app.conf["broker_url"] = "memory://"
        celery_app.conf["result_backend"] = None
        celery_app.conf.update(
            task_always_eager=True,
            task_eager_propagates=True,
            broker_url="memory://",
            result_backend=None,
        )

        # 4. Fail-closed safety assertion on effective and constructor-level Celery settings
        assert_safe_celery_broker()

        Base.metadata.create_all(bind=cls.engine, tables=target_tables)

        # Construct lightweight FastAPI test app
        cls.test_app = build_lightweight_test_app()
        cls.addClassCleanup(cls.test_app.dependency_overrides.clear)

        def _override_get_db():
            db = cls.test_sessionmaker()
            try:
                yield db
            finally:
                db.close()

        def _override_get_current_user():
            if cls.current_auth_user is None:
                raise RuntimeError("Test auth user not configured for this request.")
            return cls.current_auth_user

        cls.test_app.dependency_overrides[get_db] = _override_get_db
        cls.test_app.dependency_overrides[get_current_user] = _override_get_current_user
        cls.client = TestClient(cls.test_app)

    @classmethod
    def tearDownClass(cls):
        """All restorations are registered via addClassCleanup callbacks before mutations in setUpClass."""
        super().tearDownClass()

    def setUp(self):
        """Resets approved tables only inside the dedicated disposable test database."""
        with self.engine.connect() as conn:
            # Revalidate the live target immediately before the destructive table reset.
            live_db, live_user, live_port = conn.execute(
                text("SELECT current_database(), current_user, current_setting('port')::integer;")
            ).fetchone()
            if (
                live_db != EXPECTED_TIER1_TEST_DB
                or live_user != EXPECTED_TIER1_TEST_USER
                or live_port != EXPECTED_TIER1_TEST_CONTAINER_PORT
            ):
                raise RuntimeError(
                    f"Refusing test cleanup: connected to ({live_db}, {live_user}, {live_port}), "
                    f"expected ({EXPECTED_TIER1_TEST_DB}, {EXPECTED_TIER1_TEST_USER}, "
                    f"{EXPECTED_TIER1_TEST_CONTAINER_PORT})"
                )

            # Table-wide reset is permitted only because this target is disposable.
            conn.execute(text("DELETE FROM notifications;"))
            conn.execute(text("DELETE FROM reminders;"))
            conn.execute(text("DELETE FROM circulars;"))
            conn.execute(text("DELETE FROM files;"))
            conn.execute(text("DELETE FROM users;"))
            conn.commit()

        self.db = self.test_sessionmaker()

    def tearDown(self):
        """Closes individual test session."""
        self.db.close()
        self.__class__.current_auth_user = None

    # ---------------------------------------------------------------------
    # HELPER METHODS
    # ---------------------------------------------------------------------

    def _create_user(self, name: str, email: str, role: UserRole) -> User:
        user = User(
            name=name,
            email=email,
            password_hash="mock_hash_for_test",
            role=role,
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def _create_circular(self, lecturer_id: int, title: str, due_date: Optional[datetime]) -> Circular:
        circ = Circular(
            lecturer_id=lecturer_id,
            type=CircularType.ASSIGNMENT,
            title=title,
            content="Integration test circular content.",
            due_date=due_date,
        )
        self.db.add(circ)
        self.db.commit()
        self.db.refresh(circ)
        return circ

    # =====================================================================
    # 4. TIER 1 TEST SCENARIOS
    # =====================================================================

    def test_01_duplicate_event_key_raises_integrity_error(self):
        """PostgreSQL uniqueness: Attempting duplicate event_key raises IntegrityError."""
        student = self._create_user("Student One", "student1@edumatrix.test", UserRole.STUDENT)
        notif1 = Notification(
            user_id=student.id,
            type="reminder",
            title="Reminder 1",
            message="Message 1",
            reference_id=101,
            event_key="reminder_101_1_7_day",
        )
        self.db.add(notif1)
        self.db.commit()

        notif2 = Notification(
            user_id=student.id,
            type="reminder",
            title="Reminder 2",
            message="Message 2",
            reference_id=101,
            event_key="reminder_101_1_7_day",  # Exact duplicate
        )
        self.db.add(notif2)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_02_foreign_key_file_deletion_nulls_circular_file_id(self):
        """Foreign key ON DELETE SET NULL: Deleting a referenced File nulls circular.file_id."""
        lecturer = self._create_user("Lecturer One", "lecturer1@edumatrix.test", UserRole.LECTURER)
        file_record = File(
            filename="syllabus.pdf",
            file_size=1024,
            mime_type="application/pdf",
            bucket="circulars",
            object_key="circulars/syllabus_123.pdf",
            department="CSE",
            file_type="circular",
            uploaded_by=lecturer.id,
            status=FileStatus.ACTIVE,
        )
        self.db.add(file_record)
        self.db.commit()
        self.db.refresh(file_record)

        circular = Circular(
            lecturer_id=lecturer.id,
            type=CircularType.GENERAL,
            title="Circular with File",
            content="Content",
            file_id=file_record.id,
        )
        self.db.add(circular)
        self.db.commit()
        self.db.refresh(circular)
        self.assertEqual(circular.file_id, file_record.id)

        # Create associated reminder to verify survival
        reminder = Reminder(
            circular_id=circular.id,
            user_id=lecturer.id,  # Or any user id for FK check
            reminder_type=ReminderType.SEVEN_DAY,
            status=ReminderStatus.PENDING,
            scheduled_at=datetime.now(timezone.utc) + timedelta(days=7)
        )
        self.db.add(reminder)
        self.db.commit()
        self.db.refresh(reminder)
        rem_id = reminder.id

        # Save file id scalar before deletion
        file_id = file_record.id

        # Delete File via direct SQL session to avoid triggering FileVersion ORM cascade
        self.db.execute(text("DELETE FROM files WHERE id = :fid"), {"fid": file_id})
        self.db.commit()
        self.db.refresh(circular)

        # Verify file no longer exists, circular remains with file_id set to None, and exact reminder survives
        self.assertIsNone(circular.file_id)
        self.assertIsNone(self.db.query(File).filter(File.id == file_id).first())
        rem_check = self.db.query(Reminder).filter(Reminder.id == rem_id).first()
        self.assertIsNotNone(rem_check)
        self.assertEqual(rem_check.circular_id, circular.id)

    def test_03_foreign_key_invalid_lecturer_id_fails_closed(self):
        """Foreign key referential integrity: Referencing nonexistent lecturer fails."""
        circular = Circular(
            lecturer_id=999999,  # Nonexistent
            type=CircularType.EXAM,
            title="Exam Circular",
            content="Exam Content",
        )
        self.db.add(circular)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_04_future_only_stage_scheduling_near_deadline(self):
        """Cutoff logic: When deadline is 2 days in future, 7_day and 3_day stages are skipped."""
        lecturer = self._create_user("Lecturer Two", "lecturer2@edumatrix.test", UserRole.LECTURER)
        student = self._create_user("Student Two", "student2@edumatrix.test", UserRole.STUDENT)

        now = datetime.now(timezone.utc)
        near_due_date = now + timedelta(days=2)
        circular = self._create_circular(lecturer.id, "Short-notice Assignment", near_due_date)

        with patch.object(ReminderScheduler, "_schedule_celery_tasks") as mock_dispatch:
            success = ReminderScheduler.schedule_reminders(circular.id, near_due_date)
            self.assertTrue(success)
            mock_dispatch.assert_called_once()

        reminders = self.db.query(Reminder).filter(Reminder.circular_id == circular.id).all()
        reminder_types = {r.reminder_type for r in reminders}

        # Must schedule strictly future stages: 1_day, deadline_day, missed_deadline
        self.assertIn(ReminderType.ONE_DAY, reminder_types)
        self.assertIn(ReminderType.DEADLINE_DAY, reminder_types)
        self.assertIn(ReminderType.MISSED_DEADLINE, reminder_types)

        # Must NOT schedule stages in the past
        self.assertNotIn(ReminderType.SEVEN_DAY, reminder_types)
        self.assertNotIn(ReminderType.THREE_DAY, reminder_types)

    def test_05_five_stage_scheduling_far_deadline(self):
        """Full scheduling: When deadline is 10 days in future, all 5 stages are created as pending."""
        lecturer = self._create_user("Lecturer Three", "lecturer3@edumatrix.test", UserRole.LECTURER)
        student = self._create_user("Student Three", "student3@edumatrix.test", UserRole.STUDENT)

        now = datetime.now(timezone.utc)
        far_due_date = now + timedelta(days=10)
        circular = self._create_circular(lecturer.id, "Semester Project", far_due_date)

        with patch.object(ReminderScheduler, "_schedule_celery_tasks") as mock_dispatch:
            success = ReminderScheduler.schedule_reminders(circular.id, far_due_date)
            self.assertTrue(success)
            mock_dispatch.assert_called_once()

        reminders = self.db.query(Reminder).filter(Reminder.circular_id == circular.id).all()
        self.assertEqual(len(reminders), 5)
        for r in reminders:
            self.assertEqual(r.status, ReminderStatus.PENDING)

    def test_06_lifecycle_expiry_cutoff_rejects_past_circular(self):
        """
        Expiry cutoff: Circular lifecycle is strictly 25 hours past due date.
        Verifies exact microsecond boundary:
        - now == due_date + 25h (now >= due_date + 25h is True) -> Expired: scheduler skips, worker aborts.
        - now == due_date + 25h - 1 microsecond (now >= due_date + 25h is False) -> Active: worker delivers.
        """
        lecturer = self._create_user("Lecturer Four", "lecturer4@edumatrix.test", UserRole.LECTURER)
        student = self._create_user("Student Four", "student4@edumatrix.test", UserRole.STUDENT)

        fixed_now = datetime(2026, 10, 24, 12, 0, 0, tzinfo=timezone.utc)

        class FrozenDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed_now

        def _create_mock_task():
            task = MagicMock()
            def _fail_on_retry(exc=None, **kwargs):
                if exc is not None:
                    raise exc
                raise RuntimeError(f"Celery task retry requested unexpectedly: {kwargs}")
            task.retry.side_effect = _fail_on_retry
            return task

        # ---------------------------------------------------------------------
        # Exact Boundary Case A: Expired lifecycle (now == due_date + 25 hours)
        # Evaluates: now >= (due_utc + 25h) -> fixed_now >= fixed_now -> True.
        # ---------------------------------------------------------------------
        exact_expired_due = fixed_now - timedelta(hours=25)
        expired_circular = self._create_circular(lecturer.id, "Exact Expired Circular", exact_expired_due)
        expired_sched_at = exact_expired_due + timedelta(hours=24)

        # Scheduler must skip scheduling at exact boundary
        with patch("app.services.reminder_scheduler.datetime", FrozenDateTime):
            res = ReminderScheduler.schedule_reminders(expired_circular.id, exact_expired_due)
            self.assertTrue(res)  # Returns True (skipped cleanly)

        reminders_count = self.db.query(Reminder).filter(Reminder.circular_id == expired_circular.id).count()
        self.assertEqual(reminders_count, 0)

        # Pre-existing pending reminder must not be delivered when worker runs at exact 25h cutoff
        expired_reminder = Reminder(
            circular_id=expired_circular.id,
            user_id=student.id,
            reminder_type=ReminderType.MISSED_DEADLINE,
            status=ReminderStatus.PENDING,
            scheduled_at=expired_sched_at,
        )
        self.db.add(expired_reminder)
        self.db.commit()

        # Worker execution must abort immediately at the exact 25h boundary
        mock_task_expired = _create_mock_task()
        with patch("app.tasks.reminder_tasks.datetime", FrozenDateTime):
            _execute_reminder_stage(
                task_instance=mock_task_expired,
                circular_id=expired_circular.id,
                reminder_type=ReminderType.MISSED_DEADLINE,
                expected_due_date_iso=exact_expired_due.isoformat(),
                expected_scheduled_at_iso=expired_sched_at.isoformat(),
            )
        mock_task_expired.retry.assert_not_called()

        # Worker must have aborted without delivering or mutating the pending reminder
        self.db.refresh(expired_reminder)
        self.assertEqual(expired_reminder.status, ReminderStatus.PENDING)
        expired_notifs = self.db.query(Notification).filter(
            Notification.user_id == student.id,
            Notification.reference_id == expired_circular.id
        ).all()
        self.assertEqual(len(expired_notifs), 0)

        # ---------------------------------------------------------------------
        # Exact Boundary Case B: Active lifecycle (now == due_date + 25h - 1 microsecond)
        # Evaluates: now >= (due_utc + 25h) -> fixed_now >= fixed_now + 1us -> False.
        # Worker must NOT abort; delivery must succeed.
        # ---------------------------------------------------------------------
        exact_active_due = fixed_now - timedelta(hours=25) + timedelta(microseconds=1)
        active_circular = self._create_circular(lecturer.id, "Exact Active Circular", exact_active_due)
        active_sched_at = exact_active_due + timedelta(hours=24)

        active_reminder = Reminder(
            circular_id=active_circular.id,
            user_id=student.id,
            reminder_type=ReminderType.MISSED_DEADLINE,
            status=ReminderStatus.PENDING,
            scheduled_at=active_sched_at,
        )
        self.db.add(active_reminder)
        self.db.commit()

        mock_task_active = _create_mock_task()
        with patch("app.tasks.reminder_tasks.datetime", FrozenDateTime):
            _execute_reminder_stage(
                task_instance=mock_task_active,
                circular_id=active_circular.id,
                reminder_type=ReminderType.MISSED_DEADLINE,
                expected_due_date_iso=exact_active_due.isoformat(),
                expected_scheduled_at_iso=active_sched_at.isoformat(),
            )
        mock_task_active.retry.assert_not_called()

        # Worker must have completed delivery: reminder is SENT, exactly 1 notification delivered
        self.db.refresh(active_reminder)
        self.assertEqual(active_reminder.status, ReminderStatus.SENT)

        active_notifs = self.db.query(Notification).filter(
            Notification.user_id == student.id,
            Notification.reference_id == active_circular.id
        ).all()
        self.assertEqual(len(active_notifs), 1)

    def test_07_deadline_rescheduling_cancels_old_and_creates_new(self):
        """Rescheduling, SENT preservation, and stale task rejection workflow."""
        lecturer = self._create_user("Lecturer Five", "lecturer5@edumatrix.test", UserRole.LECTURER)
        student = self._create_user("Student Five", "student5@edumatrix.test", UserRole.STUDENT)

        now = datetime.now(timezone.utc)
        d1 = now + timedelta(days=10)
        circular = self._create_circular(lecturer.id, "Rescheduled Homework", d1)

        d1_utc = normalize_to_utc(d1)
        d1_7_day_scheduled_at = d1_utc - timedelta(days=7)

        with patch.object(ReminderScheduler, "_schedule_celery_tasks") as mock_dispatch:
            ReminderScheduler.schedule_reminders(circular.id, d1)
            mock_dispatch.assert_called_once()

        # Capture original SENT reminder's ID and scheduled_at value before reconciliation
        rem_7 = self.db.query(Reminder).filter(
            Reminder.circular_id == circular.id,
            Reminder.reminder_type == ReminderType.SEVEN_DAY
        ).first()
        rem_7.status = ReminderStatus.SENT
        self.db.commit()
        orig_sent_id = rem_7.id
        orig_sent_scheduled_at = rem_7.scheduled_at

        # Capture original PENDING reminder IDs before reconciliation
        orig_pending_ids = [
            r.id for r in self.db.query(Reminder).filter(
                Reminder.circular_id == circular.id,
                Reminder.status == ReminderStatus.PENDING
            ).all()
        ]
        self.assertEqual(
            len(orig_pending_ids),
            4,
            "Expected four original pending reminders after marking the seven-day reminder SENT"
        )

        # Reschedule from d1 to d2 using production reconciliation & mocked dispatch
        d2 = now + timedelta(days=14)
        d2_utc = normalize_to_utc(d2)
        circular.due_date = d2
        self.db.commit()

        with patch.object(ReminderScheduler, "_schedule_celery_tasks") as mock_dispatch2:
            ReminderScheduler.reconcile_reminders(circular.id, d2, db=self.db)
            ReminderScheduler.dispatch_reconciled_tasks(circular.id, d2)
            mock_dispatch2.assert_called_once()

        # Verify the exact same SENT reminder ID survives with status SENT and unchanged scheduled_at
        sent_check = self.db.query(Reminder).filter(Reminder.id == orig_sent_id).first()
        self.assertIsNotNone(sent_check)
        self.assertEqual(sent_check.status, ReminderStatus.SENT)
        self.assertEqual(sent_check.scheduled_at, orig_sent_scheduled_at)

        # Verify old pending reminders are removed and new pending reminders exist for d2 with exact stages and scheduled times
        pending_reminders = self.db.query(Reminder).filter(
            Reminder.circular_id == circular.id,
            Reminder.status == ReminderStatus.PENDING
        ).all()
        self.assertEqual(len(pending_reminders), 5)

        # Verify none of the original pending reminder IDs remain
        current_reminder_ids = {r.id for r in self.db.query(Reminder).filter(
            Reminder.circular_id == circular.id
        ).all()}
        for old_id in orig_pending_ids:
            self.assertNotIn(old_id, current_reminder_ids)

        expected_d2_stages = {
            ReminderType.SEVEN_DAY: d2_utc - timedelta(days=7),
            ReminderType.THREE_DAY: d2_utc - timedelta(days=3),
            ReminderType.ONE_DAY: d2_utc - timedelta(days=1),
            ReminderType.DEADLINE_DAY: d2_utc,
            ReminderType.MISSED_DEADLINE: d2_utc + timedelta(hours=24),
        }
        actual_d2_stages = {
            r.reminder_type: normalize_to_utc(r.scheduled_at)
            for r in pending_reminders
        }
        self.assertEqual(actual_d2_stages, expected_d2_stages)

        # Capture state immediately before executing stale task
        pre_stale_notif_count = self.db.query(Notification).filter(Notification.reference_id == circular.id).count()
        pre_stale_reminder_states = {
            r.id: (r.status, r.scheduled_at)
            for r in self.db.query(Reminder).filter(Reminder.circular_id == circular.id).all()
        }

        # Execute stale task with original D1 deadline token and original scheduled-time token (d1_7_day_scheduled_at)
        send_7_day_reminder.apply(args=[
            circular.id,
            d1_utc.isoformat(),
            d1_7_day_scheduled_at.isoformat()
        ])

        self.db.expire_all()
        # Compare states immediately after stale task execution
        post_stale_notif_count = self.db.query(Notification).filter(Notification.reference_id == circular.id).count()
        post_stale_reminder_states = {
            r.id: (r.status, r.scheduled_at)
            for r in self.db.query(Reminder).filter(Reminder.circular_id == circular.id).all()
        }

        self.assertEqual(pre_stale_notif_count, post_stale_notif_count)
        self.assertEqual(pre_stale_reminder_states, post_stale_reminder_states)

    def test_08_sequential_idempotency_second_run_is_noop(self):
        """Sequential idempotency: Consecutive executions deliver exactly 1 notification."""
        lecturer = self._create_user("Lecturer Six", "lecturer6@edumatrix.test", UserRole.LECTURER)
        student = self._create_user("Student Six", "student6@edumatrix.test", UserRole.STUDENT)

        now = datetime.now(timezone.utc)
        due_date = now + timedelta(days=8)
        circular = self._create_circular(lecturer.id, "Idempotency Test", due_date)

        with patch.object(ReminderScheduler, "_schedule_celery_tasks"):
            ReminderScheduler.schedule_reminders(circular.id, due_date)

        rem_7 = self.db.query(Reminder).filter(
            Reminder.circular_id == circular.id,
            Reminder.reminder_type == ReminderType.SEVEN_DAY
        ).first()
        self.assertIsNotNone(rem_7)

        # First execution (eager)
        send_7_day_reminder.apply(args=[
            circular.id,
            due_date.isoformat(),
            rem_7.scheduled_at.isoformat()
        ])

        self.db.refresh(rem_7)
        self.assertEqual(rem_7.status, ReminderStatus.SENT)

        notifs = self.db.query(Notification).filter(
            Notification.user_id == student.id,
            Notification.reference_id == circular.id
        ).all()
        self.assertEqual(len(notifs), 1)

        # Second execution (eager replay)
        send_7_day_reminder.apply(args=[
            circular.id,
            due_date.isoformat(),
            rem_7.scheduled_at.isoformat()
        ])

        # Notification count must strictly remain 1
        notifs_after = self.db.query(Notification).filter(
            Notification.user_id == student.id,
            Notification.reference_id == circular.id
        ).all()
        self.assertEqual(len(notifs_after), 1)

    def test_09_existing_notification_recovery(self):
        """Existing notification recovery: Pre-existing notification reconciles pending reminder."""
        lecturer = self._create_user("Lecturer Seven", "lecturer7@edumatrix.test", UserRole.LECTURER)
        student = self._create_user("Student Seven", "student7@edumatrix.test", UserRole.STUDENT)

        now = datetime.now(timezone.utc)
        due_date = now + timedelta(days=8)
        circular = self._create_circular(lecturer.id, "Pre-existing Notif", due_date)

        with patch.object(ReminderScheduler, "_schedule_celery_tasks"):
            ReminderScheduler.schedule_reminders(circular.id, due_date)

        # Pre-insert matching notification using canonical production event_key format
        circ_due_utc = normalize_to_utc(circular.due_date)
        due_token = circ_due_utc.strftime("%Y%m%dT%H%M%S.%fZ")
        expected_key = f"reminder:{circular.id}:due:{due_token}:user:{student.id}:stage:{ReminderType.SEVEN_DAY.value}"
        pre_notif = Notification(
            user_id=student.id,
            type="reminder",
            title="Manual 7 Day",
            message="Already delivered manually.",
            reference_id=circular.id,
            event_key=expected_key,
        )
        self.db.add(pre_notif)
        self.db.commit()

        rem_7 = self.db.query(Reminder).filter(
            Reminder.circular_id == circular.id,
            Reminder.reminder_type == ReminderType.SEVEN_DAY
        ).first()
        self.assertEqual(rem_7.status, ReminderStatus.PENDING)

        # Execute task
        send_7_day_reminder.apply(args=[
            circular.id,
            due_date.isoformat(),
            rem_7.scheduled_at.isoformat()
        ])

        # Reminder must reconcile to SENT without creating duplicate notification
        self.db.refresh(rem_7)
        self.assertEqual(rem_7.status, ReminderStatus.SENT)

        notifs_count = self.db.query(Notification).filter(
            Notification.user_id == student.id,
            Notification.reference_id == circular.id
        ).count()
        self.assertEqual(notifs_count, 1)

    def test_10_api_visibility_filters_future_unearned_reminders(self):
        """API Visibility: GET /reminders/ hides future pending and future sent reminders from students.

        API filter logic (reminders.py lines 43-50):
        - SENT reminders: only visible if scheduled_at <= now (actually delivered)
        - PENDING reminders: only visible if scheduled_at <= now (overdue/unread)
        - Future-scheduled reminders (SENT or PENDING) are hidden until their scheduled time.
        """
        lecturer = self._create_user("Lecturer Eight", "lecturer8@edumatrix.test", UserRole.LECTURER)
        student = self._create_user("Student Eight", "student8@edumatrix.test", UserRole.STUDENT)

        now = datetime.now(timezone.utc)

        # Create a circular with due date 10 days in future
        due_date = now + timedelta(days=10)
        circular = self._create_circular(lecturer.id, "Visibility Circular", due_date)

        with patch.object(ReminderScheduler, "_schedule_celery_tasks"):
            ReminderScheduler.schedule_reminders(circular.id, due_date)

        # Authenticate as student
        self.__class__.current_auth_user = student

        # 1. All 5 stages are in the future (> now) and PENDING → MUST NOT appear
        response = self.client.get("/reminders/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 0, "Future PENDING reminders must not be returned")

        # 2. Mark one reminder as SENT (but its scheduled_at is still in the future)
        #    → MUST STILL NOT appear (API excludes future SENT reminders)
        rem_7 = self.db.query(Reminder).filter(
            Reminder.circular_id == circular.id,
            Reminder.reminder_type == ReminderType.SEVEN_DAY
        ).first()
        rem_7.status = ReminderStatus.SENT
        self.db.commit()

        response2 = self.client.get("/reminders/")
        self.assertEqual(response2.status_code, 200)
        data2 = response2.json()
        self.assertEqual(len(data2), 0, "Future SENT reminders must not be returned (prematurely marked read)")

        # 3. Create a reminder scheduled in the past (or now) with SENT status → MUST appear
        #    Manually create a reminder with scheduled_at <= now to avoid relying on scheduler
        #    which intentionally skips past stages for past-due circulars
        past_scheduled_at = now - timedelta(hours=1)  # Explicitly past

        # Create a separate past-due circular for the manual reminder
        past_due_circular = self._create_circular(
            lecturer.id, "Past Due Circular", past_scheduled_at
        )

        # Create a reminder for the student with past scheduled_at
        past_reminder = Reminder(
            circular_id=past_due_circular.id,
            user_id=student.id,
            reminder_type=ReminderType.DEADLINE_DAY,  # Use a stage that would normally be scheduled
            status=ReminderStatus.PENDING,  # Start as PENDING, then mark as SENT
            scheduled_at=past_scheduled_at
        )
        self.db.add(past_reminder)
        self.db.commit()

        # Verify the reminder was created with correct scheduled_at
        created_reminder = self.db.query(Reminder).filter(
            Reminder.id == past_reminder.id
        ).first()
        self.assertIsNotNone(created_reminder)
        self.assertLessEqual(created_reminder.scheduled_at, now)

        # Mark the past reminder as SENT
        created_reminder.status = ReminderStatus.SENT
        self.db.commit()
        expected_sent_id = created_reminder.id

        # 4. GET /reminders/ → MUST return exactly the past SENT reminder
        response3 = self.client.get("/reminders/")
        self.assertEqual(response3.status_code, 200)
        data3 = response3.json()
        self.assertEqual(len(data3), 1, "Exactly one past SENT reminder must be returned")
        self.assertEqual(data3[0]["id"], expected_sent_id, "Returned reminder must match the past SENT reminder")

    def test_11_real_redis_eta_queue_dispatch(self):
        """Tier 2: Real asynchronous Redis broker queueing for 5 reminder stages.

        Verified Transport Behavior (Kombu 5.6.2, redis.py:1034-1039):
        - When a task is published with `eta=...`, Kombu's Redis transport stores it
          in a Redis LIST at the queue key (default 'celery' or test-specific queue).
        - The message is published IMMEDIATELY (no broker-side scheduling).
        - The ETA is carried in the message headers: headers['eta'] = ISO8601 string.
        - The body is a JSON string of [args, kwargs, embed] where args =
          [circular_id, expected_due_date_iso, expected_scheduled_at_iso].
        - No worker is started; messages remain in the LIST indefinitely until consumed.
        """
        # 1. Strict Redis URL Guard
        redis_url = os.environ.get("TIER1_TEST_REDIS_URL")
        if not redis_url:
            self.fail("TIER1_TEST_REDIS_URL not set")

        from urllib.parse import urlparse
        parsed = urlparse(redis_url)
        if parsed.scheme != "redis":
            self.fail(f"Invalid scheme '{parsed.scheme}', expected 'redis'")
        if parsed.hostname != "127.0.0.1":
            self.fail(f"Invalid host '{parsed.hostname}', expected '127.0.0.1'")
        if parsed.port != 6381:
            self.fail(f"Invalid port {parsed.port}, expected 6381")
        if (parsed.path or "/") != "/0":
            self.fail(f"Invalid database index '{parsed.path}', expected '/0'")
        if parsed.username or parsed.password:
            self.fail("Credentials not allowed in TIER1_TEST_REDIS_URL")
        if parsed.query:
            self.fail(f"Query parameters not allowed: '{parsed.query}'")
        if parsed.fragment:
            self.fail(f"Fragment not allowed: '{parsed.fragment}'")
        if "6379" in redis_url:
            self.fail("Development Redis port 6379 detected in test Redis URL")

        import redis
        r = redis.Redis.from_url(redis_url, decode_responses=False)

        # 2. Save original Celery configuration for guaranteed restoration
        original_broker_url = celery_app.conf.broker_url
        original_task_routes = celery_app.conf.task_routes
        original_router = celery_app.amqp.router
        original_task_always_eager = celery_app.conf.task_always_eager

        # Initialize cleanup identifiers safely to avoid UnboundLocalError if setup fails
        lecturer_id = None
        circular_id = None
        test_queue_name = None

        try:
            # 3. Configure Celery to point at the disposable test broker
            celery_app.conf.broker_url = redis_url
            celery_app._broker_url = redis_url

            # 3b. Disable eager mode so tasks are published to Redis, not executed locally
            celery_app.conf.task_always_eager = False

            # 4. Route reminder tasks to a unique test queue
            import uuid
            test_queue_name = f"test_t2_{uuid.uuid4().hex[:8]}"
            test_task_routes = {
                "app.tasks.reminder_tasks.send_7_day_reminder": {"queue": test_queue_name},
                "app.tasks.reminder_tasks.send_3_day_reminder": {"queue": test_queue_name},
                "app.tasks.reminder_tasks.send_1_day_reminder": {"queue": test_queue_name},
                "app.tasks.reminder_tasks.send_deadline_day_reminder": {"queue": test_queue_name},
                "app.tasks.reminder_tasks.send_missed_deadline_reminder": {"queue": test_queue_name},
            }
            celery_app.conf.update(task_routes=test_task_routes)
            # Force router refresh by creating a new router instance
            celery_app.amqp.flush_routes()

            # 5. Pre-dispatch routing verification: all five tasks must resolve to the test queue
            router = celery_app.amqp.router
            expected_task_names = {
                "app.tasks.reminder_tasks.send_7_day_reminder",
                "app.tasks.reminder_tasks.send_3_day_reminder",
                "app.tasks.reminder_tasks.send_1_day_reminder",
                "app.tasks.reminder_tasks.send_deadline_day_reminder",
                "app.tasks.reminder_tasks.send_missed_deadline_reminder",
            }
            for task_name in expected_task_names:
                resolved = router.route({}, task_name, (), {})
                resolved_queue = resolved.get('queue')
                queue_name = resolved_queue if isinstance(resolved_queue, str) else getattr(resolved_queue, 'name', None)
                self.assertEqual(queue_name, test_queue_name,
                                 msg=f"Task {task_name} did not resolve to test queue")

            # 6. Verify the connection targets the disposable test broker
            # Parse broker URL to verify connection params (avoid kombu connection inspection issues)
            from urllib.parse import urlparse
            # Use the original redis_url from test setup, not celery_app.conf which may not update
            broker_parsed = urlparse(redis_url)
            self.assertEqual(broker_parsed.hostname, '127.0.0.1')
            self.assertEqual(broker_parsed.port, 6381)
            self.assertEqual((broker_parsed.path or '/'), '/0')

            # 7. Verify Redis connectivity
            r.ping()

            # 8. Setup isolated test circular and dispatch tasks
            lecturer = self._create_user("Lecturer Nine", "lecturer9@edumatrix.test", UserRole.LECTURER)
            lecturer_id = lecturer.id
            now = datetime.now(timezone.utc)
            d = now + timedelta(days=10)
            circular = self._create_circular(lecturer.id, "Redis ETA Test", d)
            circular_id = circular.id

            ReminderScheduler.schedule_reminders(circular.id, d)

            # 9. Verify broker queue (Redis LIST) — bounded polling instead of fixed sleep
            import time
            expected_count = 5
            poll_interval = 0.1  # 100 ms
            max_wait = 5.0       # 5 seconds timeout
            deadline = time.monotonic() + max_wait
            pending = []
            while time.monotonic() < deadline:
                pending = r.lrange(test_queue_name, 0, -1)
                if len(pending) >= expected_count:
                    break
                time.sleep(poll_interval)

            self.assertEqual(
                len(pending), expected_count,
                f"Expected {expected_count} messages in Redis LIST '{test_queue_name}' "
                f"within {max_wait}s, found {len(pending)}"
            )

            found_task_names = set()

            d_utc = normalize_to_utc(d)
            expected_schedule = {
                "app.tasks.reminder_tasks.send_7_day_reminder": d_utc - timedelta(days=7),
                "app.tasks.reminder_tasks.send_3_day_reminder": d_utc - timedelta(days=3),
                "app.tasks.reminder_tasks.send_1_day_reminder": d_utc - timedelta(days=1),
                "app.tasks.reminder_tasks.send_deadline_day_reminder": d_utc,
                "app.tasks.reminder_tasks.send_missed_deadline_reminder": d_utc + timedelta(hours=24),
            }
            expected_due_iso = d_utc.isoformat()

            for raw in pending:
                envelope = json.loads(raw)
                headers = envelope.get("headers", {})
                task_name = headers.get("task")
                self.assertIn(task_name, expected_task_names, f"Unexpected task name: {task_name}")
                found_task_names.add(task_name)

                # Verify ETA header (ISO8601 string) with two-second tolerance
                eta_header = headers.get("eta")
                self.assertIsInstance(eta_header, str, "ETA header not a string")
                eta_dt = datetime.fromisoformat(eta_header.replace("Z", "+00:00"))
                self.assertIsNotNone(eta_dt.tzinfo, "ETA must be timezone-aware")
                expected_eta = expected_schedule[task_name]
                self.assertAlmostEqual(
                    eta_dt.timestamp(), expected_eta.timestamp(),
                    delta=2,
                    msg=f"ETA mismatch for {task_name}"
                )

                # Verify body payload
                body = envelope.get("body", "")
                payload = json.loads(body)
                args = payload[0] if isinstance(payload, list) else []
                self.assertEqual(len(args), 3, f"Task {task_name} should have 3 args")
                self.assertEqual(args[0], circular.id, f"Task {task_name} circular_id mismatch")
                self.assertEqual(args[1], expected_due_iso, f"Task {task_name} deadline token mismatch")
                self.assertEqual(args[2], expected_schedule[task_name].isoformat(),
                                 f"Task {task_name} scheduled-time token mismatch")

            self.assertEqual(found_task_names, expected_task_names,
                             "Not all expected reminder tasks were dispatched")

        finally:
            # 10. Redis cleanup: delete unique queue key then close client
            redis_cleanup_failures = []
            try:
                if test_queue_name:
                    r.delete(test_queue_name)
            except Exception:
                redis_cleanup_failures.append("redis_queue_delete")
            try:
                r.close()
            except Exception:
                redis_cleanup_failures.append("redis_client_close_failed")

            # 11. Restore Celery configuration — each step independently;
            #         failures are collected and visible, never masked
            restore_failures = []
            restore_failures.extend(redis_cleanup_failures)

            # Restore each Celery setting independently, even if an earlier step fails
            try:
                celery_app.conf.broker_url = original_broker_url
            except Exception:
                restore_failures.append("broker_url")

            try:
                celery_app._broker_url = original_broker_url
            except Exception:
                restore_failures.append("_broker_url")

            try:
                celery_app.conf.task_routes = original_task_routes
            except Exception:
                restore_failures.append("task_routes")

            try:
                celery_app.amqp.router = original_router
            except Exception:
                restore_failures.append("amqp.router")

            try:
                celery_app.amqp.flush_routes()
            except Exception:
                restore_failures.append("flush_routes")

            try:
                celery_app.conf.task_always_eager = original_task_always_eager
            except Exception:
                restore_failures.append("task_always_eager")

            # 12. Scoped DB cleanup for records created by this test
            db_cleanup_failures = []
            if circular_id is not None or lecturer_id is not None:
                try:
                    if circular_id is not None:
                        self.db.query(Reminder).filter(Reminder.circular_id == circular_id).delete(synchronize_session=False)
                        self.db.query(Notification).filter(
                            Notification.reference_id == circular_id,
                            Notification.type == "reminder",
                            Notification.event_key.like(f"reminder:{circular_id}:%")
                        ).delete(synchronize_session=False)
                        self.db.query(Circular).filter(Circular.id == circular_id).delete(synchronize_session=False)
                    if lecturer_id is not None:
                        self.db.query(User).filter(User.id == lecturer_id).delete(synchronize_session=False)
                    self.db.commit()
                except Exception:
                    db_cleanup_failures.append("db_cleanup_transaction")
                    try:
                        self.db.rollback()
                    except Exception:
                        db_cleanup_failures.append("db_rollback_failed")
                if db_cleanup_failures:
                    failed = ", ".join(db_cleanup_failures)
                    if sys.exc_info()[0] is not None:
                        log.warning("DB cleanup issues during test failure: %s", failed)
                    else:
                        self.fail(f"DB cleanup failed for: {failed}")

            # Report restoration failures without exposing credentials or connection URLs.
            # If the test already failed (original exception present), LOG the cleanup
            # failures using the module logger and allow the original exception to propagate.
            # If the test passed but cleanup failed, fail explicitly with the step names.
            if restore_failures:
                failed_steps = ", ".join(restore_failures)
                if sys.exc_info()[0] is not None:
                    # Test already failed — log cleanup issues but do not replace the
                    # original exception. Original exception will propagate after finally.
                    log.warning("Celery cleanup issues during test failure: %s", failed_steps)
                else:
                    # Test passed but cleanup failed — fail explicitly with step names
                    self.fail(f"Celery restoration failed for: {failed_steps}")

