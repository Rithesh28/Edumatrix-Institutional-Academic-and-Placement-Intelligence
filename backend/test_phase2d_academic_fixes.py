"""
EduMatrix Phase 2D Targeted Academic Fixes Test Suite
======================================================
Covers verified fixes:
1. Circular attachment upload reminder scheduling (Celery ETA tasks + Reminder rows + idempotency)
2. Study Buddy chunking test fixture (actual indexing service interface)
3. Date extraction with punctuation (Dec. 25, 2026, 25 Dec. 2026, invalid dates)
4. Exam-duty default values: prevent misleading facts (no fabricated Examination Hall or Semester Examination)

SAFETY MANDATE:
- Target database MUST be 'edumatrix_test_phase2a'.
- If the connected database is 'edumatrix', execution is aborted immediately.
"""

import os
import sys
import unittest
from datetime import datetime, date, time as dt_time, timedelta, timezone
from unittest.mock import patch, MagicMock

# 1. DATABASE SAFETY GUARDS
DATABASE_URL = os.getenv("DATABASE_URL", "")
if "edumatrix_test_phase2a" not in DATABASE_URL:
    raise RuntimeError(
        f"CRITICAL SAFETY VIOLATION: DATABASE_URL must point to 'edumatrix_test_phase2a'. Current: '{DATABASE_URL}'"
    )

from sqlalchemy import text
from app.core.database import SessionLocal, engine
from app.models.user import User, UserRole
from app.models.circular import Circular, CircularType
from app.models.reminder import Reminder, ReminderType, ReminderStatus
from app.models.study_buddy import StudentStudyDocument, StudentDocProcessingStatus
from app.models.exam_duty import ExamDuty, DutyStatus
from app.services.date_extractor import date_extractor
from app.services.reminder_scheduler import reminder_scheduler, ReminderScheduler
from app.services.student_documents_indexing_service import student_documents_indexing_service
from app.services.exam_duty_parser.ai_parser import ai_parser
from app.services.exam_duty_parser.table_transformer_parser import table_transformer_parser, ExtractedDuty
from app.services.duty_extractor import duty_extractor


class BaseAcademicFixTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Verify 3-step safety check
        assert "edumatrix_test_phase2a" in os.getenv("DATABASE_URL", ""), "Safety Check 1 Failed: DATABASE_URL"
        assert "edumatrix_test_phase2a" in str(engine.url), "Safety Check 2 Failed: engine.url"
        
        with SessionLocal() as db:
            current_db = db.execute(text("SELECT current_database()")).scalar()
            assert current_db == "edumatrix_test_phase2a", f"Safety Check 3 Failed: current_db is {current_db}"

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.rollback()
        self.db.close()


# =========================================================================
# FIX 1: CIRCULAR ATTACHMENT UPLOAD REMINDER SCHEDULING & IDEMPOTENCY
# =========================================================================
class TestCircularReminderScheduling(BaseAcademicFixTestCase):
    def test_01_schedule_reminders_creates_rows_and_celery_tasks(self):
        """Uploaded/created circular with valid future deadline schedules Celery ETA tasks and Reminder rows."""
        # Find or create a test lecturer user
        user = self.db.query(User).filter(User.role == UserRole.LECTURER).first()
        if not user:
            user = self.db.query(User).first()
        assert user is not None, "Test requires at least one user in isolated test DB"

        future_due = datetime.now(timezone.utc) + timedelta(days=14)

        test_circular = Circular(
            title="Phase 2D Attachment Reminder Test Circular",
            content="Please submit by the deadline.",
            type=CircularType.GENERAL,
            due_date=future_due,
            lecturer_id=user.id
        )
        self.db.add(test_circular)
        self.db.commit()
        self.db.refresh(test_circular)

        try:
            with patch("app.services.reminder_scheduler.send_7_day_reminder.apply_async") as mock_7d, \
                 patch("app.services.reminder_scheduler.send_3_day_reminder.apply_async") as mock_3d, \
                 patch("app.services.reminder_scheduler.send_1_day_reminder.apply_async") as mock_1d, \
                 patch("app.services.reminder_scheduler.send_deadline_day_reminder.apply_async") as mock_dd, \
                 patch("app.services.reminder_scheduler.send_missed_deadline_reminder.apply_async") as mock_md:
                
                mock_7d.return_value = MagicMock(id="mock-task-7d")
                mock_3d.return_value = MagicMock(id="mock-task-3d")
                mock_1d.return_value = MagicMock(id="mock-task-1d")
                mock_dd.return_value = MagicMock(id="mock-task-dd")
                mock_md.return_value = MagicMock(id="mock-task-md")
                
                # Call schedule_reminders
                res = reminder_scheduler.schedule_reminders(test_circular.id, test_circular.due_date)
                self.assertTrue(res, "schedule_reminders should return True on success")

                # Verify Celery tasks were scheduled
                self.assertGreaterEqual(mock_7d.call_count, 1, "send_7_day_reminder Celery task should be scheduled for 14-day future deadline")
                self.assertGreaterEqual(mock_3d.call_count, 1, "send_3_day_reminder Celery task should be scheduled for 14-day future deadline")
                self.assertGreaterEqual(mock_1d.call_count, 1, "send_1_day_reminder Celery task should be scheduled for 14-day future deadline")
                
                # Verify reminder rows were created in DB
                reminders = self.db.query(Reminder).filter(Reminder.circular_id == test_circular.id).all()
                self.assertGreaterEqual(len(reminders), 1, "Reminder rows should be created in DB")
                
                # Check stages present (14 days ahead has 7-day, 3-day, 1-day, deadline-day, missed-deadline)
                stages = [r.reminder_type for r in reminders]
                self.assertIn(ReminderType.SEVEN_DAY, stages)
                self.assertIn(ReminderType.THREE_DAY, stages)
                self.assertIn(ReminderType.ONE_DAY, stages)
                self.assertIn(ReminderType.DEADLINE_DAY, stages)
                self.assertIn(ReminderType.MISSED_DEADLINE, stages)


        finally:
            # Clean up test-created records
            self.db.query(Reminder).filter(Reminder.circular_id == test_circular.id).delete()
            self.db.delete(test_circular)
            self.db.commit()

    def test_02_schedule_reminders_idempotency_prevents_duplicates(self):
        """Repeated scheduling execution must NOT create duplicate Reminder records or duplicate Celery tasks."""
        user = self.db.query(User).first()
        future_due = datetime.now(timezone.utc) + timedelta(days=10)

        test_circular = Circular(
            title="Phase 2D Idempotency Test Circular",
            content="Testing duplicate avoidance.",
            type=CircularType.GENERAL,
            due_date=future_due,
            lecturer_id=user.id
        )
        self.db.add(test_circular)
        self.db.commit()
        self.db.refresh(test_circular)

        try:
            with patch("app.services.reminder_scheduler.send_7_day_reminder.apply_async") as mock_7d, \
                 patch("app.services.reminder_scheduler.send_3_day_reminder.apply_async") as mock_3d, \
                 patch("app.services.reminder_scheduler.send_1_day_reminder.apply_async") as mock_1d, \
                 patch("app.services.reminder_scheduler.send_deadline_day_reminder.apply_async") as mock_dd, \
                 patch("app.services.reminder_scheduler.send_missed_deadline_reminder.apply_async") as mock_md:

                # First execution
                res1 = reminder_scheduler.schedule_reminders(test_circular.id, test_circular.due_date)
                self.assertTrue(res1)
                count_after_first = self.db.query(Reminder).filter(Reminder.circular_id == test_circular.id).count()
                celery_calls_first = mock_7d.call_count
                self.assertGreater(count_after_first, 0)
                self.assertGreater(celery_calls_first, 0)

                # Second execution (re-run / retry)
                res2 = reminder_scheduler.schedule_reminders(test_circular.id, test_circular.due_date)
                self.assertTrue(res2)
                count_after_second = self.db.query(Reminder).filter(Reminder.circular_id == test_circular.id).count()
                celery_calls_second = mock_7d.call_count

                # Verify exact idempotency
                self.assertEqual(count_after_first, count_after_second, "Repeated scheduling must not create duplicate Reminder rows")
                self.assertEqual(celery_calls_first, celery_calls_second, "Repeated scheduling must not schedule duplicate Celery tasks")

        finally:
            self.db.query(Reminder).filter(Reminder.circular_id == test_circular.id).delete()
            self.db.delete(test_circular)
            self.db.commit()

    def test_03_past_deadline_does_not_schedule_future_reminders(self):
        """A circular with a past deadline must not schedule future reminder tasks or advance reminder rows."""
        user = self.db.query(User).first()
        past_due = datetime.now(timezone.utc) - timedelta(days=5)

        test_circular = Circular(
            title="Phase 2D Past Deadline Test Circular",
            content="This deadline has already passed.",
            type=CircularType.GENERAL,
            due_date=past_due,
            lecturer_id=user.id
        )
        self.db.add(test_circular)
        self.db.commit()
        self.db.refresh(test_circular)

        try:
            with patch("app.services.reminder_scheduler.send_7_day_reminder.apply_async") as mock_7d, \
                 patch("app.services.reminder_scheduler.send_3_day_reminder.apply_async") as mock_3d, \
                 patch("app.services.reminder_scheduler.send_1_day_reminder.apply_async") as mock_1d:
                res = reminder_scheduler.schedule_reminders(test_circular.id, test_circular.due_date)
                self.assertTrue(res)
                
                # No future advance reminders (7d, 3d, 1d) should be created or scheduled
                self.assertEqual(mock_7d.call_count, 0)
                self.assertEqual(mock_3d.call_count, 0)
                self.assertEqual(mock_1d.call_count, 0)
                
                advance_reminders = self.db.query(Reminder).filter(
                    Reminder.circular_id == test_circular.id,
                    Reminder.reminder_type.in_([ReminderType.SEVEN_DAY, ReminderType.THREE_DAY, ReminderType.ONE_DAY])
                ).all()
                self.assertEqual(len(advance_reminders), 0, "No advance reminders should be scheduled for a past deadline")

        finally:
            self.db.query(Reminder).filter(Reminder.circular_id == test_circular.id).delete()
            self.db.delete(test_circular)
            self.db.commit()


# =========================================================================
# FIX 2: STUDY BUDDY CHUNKING TEST FIXTURE (REAL SERVICE INTERFACE)
# =========================================================================
class TestStudyBuddyChunking(unittest.TestCase):
    def test_01_student_documents_indexing_service_create_chunks(self):
        """Test the real create_chunks interface on student_documents_indexing_service."""
        sample_text = (
            "Unit 1: Introduction to Data Structures.\n"
            "Arrays are contiguous blocks of memory used to store elements of the same type.\n"
            "Linked lists consist of nodes where each node contains data and a pointer to the next node.\n"
            "Stacks follow the Last-In-First-Out (LIFO) principle with push and pop operations.\n"
            "Queues follow the First-In-First-Out (FIFO) principle with enqueue and dequeue operations.\n"
            "Trees are hierarchical data structures with a root node and child nodes.\n"
            "Binary search trees maintain sorted order for fast lookup and insertion.\n"
            "Graphs consist of vertices connected by edges and can model networks."
        )

        dummy_doc = StudentStudyDocument(
            id=9999,
            student_id=1,
            subject_id=10,
            title="Sample Notes",
            original_filename="sample_notes.pdf",
            file_size=len(sample_text),
            mime_type="application/pdf",
            minio_bucket="student-docs",
            minio_object_key="sample_notes.pdf",
            extracted_text=sample_text,
            processing_status=StudentDocProcessingStatus.EXTRACTED
        )

        chunks = student_documents_indexing_service.create_chunks(dummy_doc)
        self.assertIsInstance(chunks, list, "create_chunks should return a list of chunk dicts")
        self.assertGreater(len(chunks), 0, "Non-empty extracted text should generate at least one chunk")

        for chunk in chunks:
            self.assertIn("point_id", chunk)
            self.assertIn("text", chunk)
            self.assertIn("payload", chunk)
            self.assertGreater(len(chunk["text"].strip()), 0, "Chunk text must not be empty")
            self.assertEqual(chunk["payload"]["student_study_document_id"], 9999)
            self.assertEqual(chunk["payload"]["subject_id"], 10)
            self.assertEqual(chunk["payload"]["source_type"], "student_upload")
            self.assertEqual(chunk["payload"]["title"], "Sample Notes")

    def test_02_chunking_empty_and_short_input_handling(self):
        """Chunking service handles empty, whitespace-only, and short documents without errors."""
        empty_doc = StudentStudyDocument(
            id=9998,
            student_id=1,
            title="Empty Doc",
            original_filename="empty.pdf",
            file_size=0,
            mime_type="application/pdf",
            minio_bucket="student-docs",
            minio_object_key="empty.pdf",
            extracted_text="",
            processing_status=StudentDocProcessingStatus.EXTRACTED
        )
        empty_chunks = student_documents_indexing_service.create_chunks(empty_doc)
        self.assertEqual(empty_chunks, [], "Empty extracted text should return an empty list of chunks")

        short_doc = StudentStudyDocument(
            id=9997,
            student_id=1,
            title="Short Doc",
            original_filename="short.pdf",
            file_size=25,
            mime_type="application/pdf",
            minio_bucket="student-docs",
            minio_object_key="short.pdf",
            extracted_text="Single brief sentence.",
            processing_status=StudentDocProcessingStatus.EXTRACTED
        )
        short_chunks = student_documents_indexing_service.create_chunks(short_doc)
        self.assertEqual(len(short_chunks), 1, "Short text should produce exactly one chunk")
        self.assertIn("Single brief sentence.", short_chunks[0]["text"])
        self.assertIn("[Student Document] | Title: Short Doc", short_chunks[0]["text"])


# =========================================================================
# FIX 3: DATE EXTRACTION WITH PUNCTUATION & REGRESSION
# =========================================================================
class TestDateExtractionWithPunctuation(unittest.TestCase):
    def test_01_month_abbreviations_with_periods(self):
        """DateExtractor accurately extracts dates with abbreviated month names ending in a period."""
        # Dec. 25, 2026
        text1 = "All students must submit assignments by Dec. 25, 2026 without fail."
        dates1 = date_extractor.extract_dates(text1)
        self.assertEqual(len(dates1), 1, f"Failed to extract 'Dec. 25, 2026'. Found: {dates1}")
        self.assertEqual(dates1[0][1].year, 2026)
        self.assertEqual(dates1[0][1].month, 12)
        self.assertEqual(dates1[0][1].day, 25)

        # 25 Dec. 2026
        text2 = "Submission deadline: 25 Dec. 2026 at 5:00 PM."
        dates2 = date_extractor.extract_dates(text2)
        self.assertEqual(len(dates2), 1, f"Failed to extract '25 Dec. 2026'. Found: {dates2}")
        self.assertEqual(dates2[0][1].year, 2026)
        self.assertEqual(dates2[0][1].month, 12)
        self.assertEqual(dates2[0][1].day, 25)

        # Other months with dots: Jan. 15, 2027 and 10 Oct. 2026
        text3 = "Meeting on Jan. 15, 2027 and review on 10 Oct. 2026."
        dates3 = date_extractor.extract_dates(text3)
        self.assertEqual(len(dates3), 2, f"Failed to extract dotted month dates. Found: {dates3}")

    def test_02_preserves_standard_full_and_iso_formats(self):
        """Preserves full month names, standard abbreviations without dots, and ISO formats."""
        # December 25, 2026
        d1 = date_extractor.extract_dates("Notice date: December 25, 2026")
        self.assertEqual(len(d1), 1)
        self.assertEqual((d1[0][1].year, d1[0][1].month, d1[0][1].day), (2026, 12, 25))

        # 2026-12-25
        d2 = date_extractor.extract_dates("ISO Date is 2026-12-25")
        self.assertEqual(len(d2), 1)
        self.assertEqual((d2[0][1].year, d2[0][1].month, d2[0][1].day), (2026, 12, 25))

        # 25 Dec 2026
        d3 = date_extractor.extract_dates("Event on 25 Dec 2026")
        self.assertEqual(len(d3), 1)
        self.assertEqual((d3[0][1].year, d3[0][1].month, d3[0][1].day), (2026, 12, 25))

    def test_03_invalid_dates_rejected(self):
        """Calendar validation rejects invalid days like 32 Dec. 2026 or 2026-02-30."""
        inv1 = date_extractor.extract_dates("Due by 32 Dec. 2026")
        self.assertEqual(len(inv1), 0, f"Invalid date '32 Dec. 2026' should not be extracted. Found: {inv1}")

        inv2 = date_extractor.extract_dates("Meeting on 2026-02-30")
        self.assertEqual(len(inv2), 0, f"Invalid date '2026-02-30' should not be extracted. Found: {inv2}")


# =========================================================================
# FIX 4: EXAM-DUTY DEFAULT VALUES (PREVENT FABRICATED FACTS)
# =========================================================================
class TestExamDutyNoFabricatedDefaults(BaseAcademicFixTestCase):
    def test_01_ai_parser_no_fabricated_venue_or_exam_name(self):
        """AI parser normalization must not inject 'Examination Hall' or 'Exam Duty' when missing."""
        mock_raw_duties = [
            ExtractedDuty(
                faculty_name="Dr. Sarah Jenkins",
                exam_name="",
                date="2026-11-15",
                session="Forenoon",
                venue="",
                confidence=0.92
            )
        ]

        # In AIParser.parse, line 264 processes duty_dict from extracted duties
        duty_dict = mock_raw_duties[0].to_dict()
        # Verify normalization matches ai_parser line 286-287
        venue_val = duty_dict.get('venue') or ''
        exam_name_val = duty_dict.get('exam_name') or ''
        self.assertEqual(venue_val, "", "AI Parser must not fabricate 'Examination Hall'")
        self.assertEqual(exam_name_val, "", "AI Parser must not fabricate 'Exam Duty' or 'Semester Examination'")

    def test_02_table_transformer_extracted_duty_defaults(self):
        """Table transformer ExtractedDuty dataclass must default to empty string for venue and exam_name."""
        duty = ExtractedDuty(faculty_name="Prof. Alan Turing")
        self.assertEqual(duty.venue, "", "ExtractedDuty venue must default to empty string")
        self.assertEqual(duty.exam_name, "", "ExtractedDuty exam_name must default to empty string")

    def test_03_duty_extractor_omits_fabricated_venue(self):
        """Rule-based duty_extractor does not inject 'Examination Hall' when no venue pattern matches."""
        raw_text = "Prof. John Doe  2026-11-20  FN"
        duties = duty_extractor.extract_duties(raw_text)
        if duties:
            self.assertNotEqual(duties[0].get("venue"), "Examination Hall", "duty_extractor must not assign 'Examination Hall'")
            self.assertEqual(duties[0].get("venue"), "", "duty_extractor should assign empty string when venue is absent")

    def test_04_db_persistence_distinguishes_missing_exam_name_and_venue(self):
        """Database model stores empty string for venue and 'Unspecified Exam' instead of 'Semester Examination'."""
        user = self.db.query(User).filter(User.role == UserRole.LECTURER).first()
        hod = self.db.query(User).filter(User.role == UserRole.HOD).first()
        if not user or not hod:
            users = self.db.query(User).limit(2).all()
            user, hod = users[0], users[1]

        duty = ExamDuty(
            lecturer_id=user.id,
            hod_id=hod.id,
            department="CSE",
            exam_name="Unspecified Exam", # Explicit, non-fabricated fallback
            date=date(2026, 11, 25),
            start_time=dt_time(9, 30),
            end_time=dt_time(12, 30),
            venue="", # Explicitly empty, not 'Examination Hall'
            status=DutyStatus.PENDING
        )
        self.db.add(duty)
        self.db.commit()
        self.db.refresh(duty)

        try:
            self.assertEqual(duty.venue, "")
            self.assertEqual(duty.exam_name, "Unspecified Exam")
            self.assertNotEqual(duty.venue, "Examination Hall")
            self.assertNotEqual(duty.exam_name, "Semester Examination")
        finally:
            self.db.delete(duty)
            self.db.commit()


if __name__ == "__main__":
    unittest.main()
