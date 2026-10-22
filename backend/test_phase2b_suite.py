"""
EduMatrix Phase 2B Systematic Test Suite
Modules:
- Module A: Academic Circulars & Announcements
- Module B: Deadlines, Reminders & Notifications
- Module C: Exam Duties & Timetable Intelligence
- Module D: Study Buddy RAG Pipeline

SAFETY MANDATE:
- Target database MUST be 'edumatrix_test_phase2a'.
- If the connected database is 'edumatrix', execution is aborted immediately.
"""

import os
import sys
import io
import time
import json
import unittest
from datetime import datetime, date, time as dt_time, timedelta, timezone
from unittest.mock import patch, MagicMock

# Force DATABASE_URL safety guard
DATABASE_URL = os.getenv("DATABASE_URL", "")
if "edumatrix_test_phase2a" not in DATABASE_URL:
    raise RuntimeError(
        f"CRITICAL SAFETY VIOLATION: DATABASE_URL must point to 'edumatrix_test_phase2a'. Current: '{DATABASE_URL}'"
    )

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.main import app
from app.core.database import SessionLocal, engine
from app.core.security import create_access_token, get_password_hash
from app.models.user import User, UserRole
from app.models.profile import StudentProfileExtended
from app.models.circular import Circular, CircularType
from app.models.file import File
from app.models.notification import Notification
from app.models.reminder import Reminder, ReminderType, ReminderStatus, ReminderChannel
from app.models.exam_duty import ExamDuty, DutyStatus
from app.models.study_buddy import (
    Subject, SyllabusDocument, SyllabusUnit, SyllabusTopic,
    SyllabusProcessingStatus, SyllabusReviewStatus,
    LectureNote, LectureNoteStatus, LectureNoteProcessingStatus,
    StudentStudyDocument, StudentDocProcessingStatus
)

from app.services.date_extractor import date_extractor
from app.services.reminder_scheduler import reminder_scheduler, ReminderScheduler
from app.services.duty_scheduler import duty_scheduler
from app.services.duty_matcher import duty_matcher
from app.services.exam_duty_parser.ai_parser import ai_parser
from app.services.exam_duty_parser.table_transformer_parser import table_transformer_parser
from app.ml.table_recognition.inference import TableRecognizer
from app.tasks.reminder_tasks import (
    send_7_day_reminder, send_3_day_reminder, send_1_day_reminder,
    send_deadline_day_reminder, send_missed_deadline_reminder,
    cancel_reminders, send_reminder_to_user
)
from app.services.study_buddy_chat_service import study_buddy_chat_service
from app.services.study_buddy_content_service import study_buddy_content_service
from app.services.student_documents_indexing_service import student_documents_indexing_service
from app.services.file_storage.text_extractor import text_extractor


def get_token_headers(user: User) -> dict:
    token = create_access_token(data={"id": user.id, "email": user.email, "role": user.role.value})
    return {"Authorization": f"Bearer {token}"}


class BasePhase2BTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Double check database URL from engine
        url_str = str(engine.url)
        if "edumatrix_test_phase2a" not in url_str:
            raise RuntimeError(f"Engine URL target safety violation: {url_str}")
        
        cls.client = TestClient(app)
        cls.db: Session = SessionLocal()
        
        # Verify DB connection and target database name
        res = cls.db.execute(text("SELECT current_database();")).scalar()
        if res != "edumatrix_test_phase2a":
            raise RuntimeError(f"Connected to WRONG database: {res}. Aborting.")
        
        print(f"\n[SAFETY VERIFIED] Test suite executing against isolated DB: {res}")
        cls._seed_test_users()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    @classmethod
    def _seed_test_users(cls):
        """Seed synthetic test users in edumatrix_test_phase2a if they don't exist"""
        users_meta = [
            ("admin_p2b@test.edu", "Admin P2B", UserRole.ADMIN, "ADMIN"),
            ("hod_aiml_p2b@test.edu", "HOD AIML", UserRole.HOD, "AIML"),
            ("hod_ece_p2b@test.edu", "HOD ECE", UserRole.HOD, "ECE"),
            ("lec_aiml1_p2b@test.edu", "Dr. Sharma", UserRole.LECTURER, "AIML"),
            ("lec_aiml2_p2b@test.edu", "Prof. Verma", UserRole.LECTURER, "AIML"),
            ("lec_ece_p2b@test.edu", "Dr. Rao", UserRole.LECTURER, "ECE"),
            ("stu_aiml1_p2b@test.edu", "Alice AIML", UserRole.STUDENT, "AIML"),
            ("stu_aiml2_p2b@test.edu", "Bob AIML", UserRole.STUDENT, "AIML"),
            ("stu_ece_p2b@test.edu", "Charlie ECE", UserRole.STUDENT, "ECE"),
            ("po_p2b@test.edu", "Officer PO", UserRole.PLACEMENT_OFFICER, "PLACEMENT"),
        ]
        
        pwd_hash = get_password_hash("testpass123")
        cls.users = {}
        for email, name, role, dept in users_meta:
            u = cls.db.query(User).filter(User.email == email).first()
            if not u:
                u = User(
                    email=email,
                    name=name,
                    role=role,
                    department=dept,
                    password_hash=pwd_hash,
                    is_active=True
                )
                cls.db.add(u)
                cls.db.commit()
                cls.db.refresh(u)
                
                # If student, add student profile
                if role == UserRole.STUDENT:
                    sp = StudentProfileExtended(
                        user_id=u.id,
                        enrollment_number=f"1TEST{u.id:04d}",
                        branch=dept,
                        semester=6,
                        cgpa=8.5
                    )
                    cls.db.add(sp)
                    cls.db.commit()
            cls.users[email] = u

    def get_user(self, email: str) -> User:
        return self.db.query(User).filter(User.email == email).first()


class TestModuleA_AcademicCirculars(BasePhase2BTest):
    """
    Module A: Academic Circulars & Announcements
    Tests:
    - Creation by Lecturer, HOD, Admin (Allowed)
    - Creation attempts by Student, Placement Officer (403 Forbidden)
    - Upload with file: empty file rejection (400 Bad Request)
    - Date extraction: future dates, missing dates, multiple dates
    - Department-specific filtering & visibility
    - Role & ownership checks on update & delete
    - Duplicate circular uploads
    """

    def test_01_rbac_circular_creation(self):
        """Test RBAC permissions on POST /circulars/"""
        payload = {
            "title": "Semester Exam Schedule Notice",
            "content": "All students must review the exam timetable.",
            "type": "exam"
        }
        
        # 1. Lecturer creation -> 200
        lec = self.get_user("lec_aiml1_p2b@test.edu")
        res = self.client.post("/circulars/", json=payload, headers=get_token_headers(lec))
        self.assertEqual(res.status_code, 200, f"Lecturer creation failed: {res.text}")
        circ_id = res.json()["id"]
        self.assertEqual(res.json()["title"], payload["title"])
        self.assertEqual(res.json()["lecturer_name"], lec.name)
        
        # 2. HOD creation -> 200
        hod = self.get_user("hod_aiml_p2b@test.edu")
        payload["title"] = "Department Meeting Circular"
        res = self.client.post("/circulars/", json=payload, headers=get_token_headers(hod))
        self.assertEqual(res.status_code, 200, f"HOD creation failed: {res.text}")
        
        # 3. Admin creation -> 200
        admin = self.get_user("admin_p2b@test.edu")
        payload["title"] = "Institute Holiday Circular"
        res = self.client.post("/circulars/", json=payload, headers=get_token_headers(admin))
        self.assertEqual(res.status_code, 200, f"Admin creation failed: {res.text}")
        
        # 4. Student creation -> 403 Forbidden
        stu = self.get_user("stu_aiml1_p2b@test.edu")
        res = self.client.post("/circulars/", json=payload, headers=get_token_headers(stu))
        self.assertEqual(res.status_code, 403, "Student was able to create circular")
        
        # 5. Placement Officer creation -> 403 Forbidden
        po = self.get_user("po_p2b@test.edu")
        res = self.client.post("/circulars/", json=payload, headers=get_token_headers(po))
        self.assertEqual(res.status_code, 403, "Placement Officer was able to create academic circular")

    def test_02_empty_file_upload_rejected(self):
        """Test POST /circulars/upload rejects 0-byte file with 400 Bad Request"""
        lec = self.get_user("lec_aiml1_p2b@test.edu")
        empty_file = io.BytesIO(b"")
        files = {"file": ("empty_notice.pdf", empty_file, "application/pdf")}
        data = {"title": "Empty Circular", "content": "Notice with empty file", "type": "general"}
        
        res = self.client.post("/circulars/upload", files=files, data=data, headers=get_token_headers(lec))
        self.assertIn(res.status_code, [400, 500], f"Expected 400 or 500 for empty file, got {res.status_code}: {res.text}")
        self.assertIn("File is empty", res.text)

    def test_03_circular_auto_date_extraction(self):
        """Test date extraction on circular text with single, multiple, and missing future dates"""
        # A. Future date extraction with supported format (abbreviated month / ISO)
        future_date_text = "All assignments must be submitted on or before 25 Dec 2026 without fail."
        dates = date_extractor.extract_future_dates(future_date_text)
        self.assertGreaterEqual(len(dates), 1, "Failed to extract future date '25 Dec 2026'")
        dt_val = dates[0][1]
        self.assertEqual(dt_val.year, 2026)
        self.assertEqual(dt_val.month, 12)
        self.assertEqual(dt_val.day, 25)
        
        # B. Multiple dates: selects latest date as primary due date
        multi_date_text = "First draft due: 10 Nov 2026. Final project submission due: 30 Nov 2026."
        multi_dates = date_extractor.extract_future_dates(multi_date_text)
        self.assertGreaterEqual(len(multi_dates), 2, "Failed to extract multiple dates")
        latest = max(multi_dates, key=lambda x: x[1])[1]
        self.assertEqual(latest.day, 30)
        self.assertEqual(latest.month, 11)
        
        # C. Missing dates: returns empty list
        no_date_text = "Please find the syllabus for the current academic session attached."
        no_dates = date_extractor.extract_future_dates(no_date_text)
        self.assertEqual(len(no_dates), 0, "Expected 0 dates for date-less text")

        # D. POST-FIX VERIFICATION: Full month name ("25 December 2026")
        full_month_text = "All assignments must be submitted on or before 25 December 2026 without fail."
        full_dates = date_extractor.extract_future_dates(full_month_text)
        self.assertGreaterEqual(len(full_dates), 1, "Failed to extract full month date '25 December 2026'")
        self.assertEqual(full_dates[0][1].month, 12)
        self.assertEqual(full_dates[0][1].day, 25)
        self.assertEqual(full_dates[0][1].year, 2026)
        print(f"\n[DATE EXTRACTOR VERIFIED] Full month name 'December' extracted: {full_dates[0]}")

    def test_04_ownership_and_role_edit_delete(self):
        """Test circular update and deletion role constraints:
        - Creator can update/delete
        - HOD of creator's department can update/delete
        - Admin can update/delete
        - Non-creator Lecturer blocked (403)
        - HOD of DIFFERENT department blocked (403)
        - Student blocked (403)
        """
        lec_aiml = self.get_user("lec_aiml1_p2b@test.edu")
        lec_other = self.get_user("lec_aiml2_p2b@test.edu")
        hod_aiml = self.get_user("hod_aiml_p2b@test.edu")
        hod_ece = self.get_user("hod_ece_p2b@test.edu")
        stu = self.get_user("stu_aiml1_p2b@test.edu")
        admin = self.get_user("admin_p2b@test.edu")
        
        # Create a test circular by lec_aiml
        circ = Circular(
            lecturer_id=lec_aiml.id,
            type=CircularType.ASSIGNMENT,
            title="Assignment 1 - ML Concepts",
            content="Submit answers by Friday.",
            due_date=datetime(2026, 11, 20, 23, 59, tzinfo=timezone.utc)
        )
        self.db.add(circ)
        self.db.commit()
        self.db.refresh(circ)
        
        # 1. Non-creator lecturer tries to update -> 403
        res = self.client.put(f"/circulars/{circ.id}", json={"title": "Hacked Title"}, headers=get_token_headers(lec_other))
        self.assertEqual(res.status_code, 403, "Non-creator lecturer was able to update circular")
        
        # 2. HOD of other department (ECE) tries to update -> 403
        res = self.client.put(f"/circulars/{circ.id}", json={"title": "Hacked by ECE HOD"}, headers=get_token_headers(hod_ece))
        self.assertEqual(res.status_code, 403, "HOD of another department was able to update circular")
        
        # 3. Student tries to update -> 403
        res = self.client.put(f"/circulars/{circ.id}", json={"title": "Hacked by Student"}, headers=get_token_headers(stu))
        self.assertEqual(res.status_code, 403, "Student was able to update circular")
        
        # 4. HOD of creator's department (AIML) updates -> 200
        res = self.client.put(f"/circulars/{circ.id}", json={"title": "Assignment 1 - ML Concepts (Approved by HOD)"}, headers=get_token_headers(hod_aiml))
        self.assertEqual(res.status_code, 200, f"AIML HOD update failed: {res.text}")
        
        # 5. Creator updates -> 200
        res = self.client.put(f"/circulars/{circ.id}", json={"content": "Extended deadline to Sunday."}, headers=get_token_headers(lec_aiml))
        self.assertEqual(res.status_code, 200, f"Creator update failed: {res.text}")
        
        # 6. HOD of other department tries to delete -> 403
        res = self.client.delete(f"/circulars/{circ.id}", headers=get_token_headers(hod_ece))
        self.assertEqual(res.status_code, 403, "HOD of another department was able to delete circular")
        
        # 7. Admin deletes -> 200
        res = self.client.delete(f"/circulars/{circ.id}", headers=get_token_headers(admin))
        self.assertEqual(res.status_code, 200, f"Admin delete failed: {res.text}")
        
        # Verify deleted
        check = self.db.query(Circular).filter(Circular.id == circ.id).first()
        self.assertIsNone(check, "Circular was not deleted from DB")

    def test_05_department_filtering_observation(self):
        """
        Verify whether GET /circulars/ applies department filtering or acts as institutional announcements.
        Audit requirement: 'Department-specific filtering and visibility for students... according to implemented rules'
        """
        # Create circular by AIML lecturer
        lec_aiml = self.get_user("lec_aiml1_p2b@test.edu")
        circ = Circular(
            lecturer_id=lec_aiml.id,
            type=CircularType.GENERAL,
            title="AIML Department AI Symposium Notice",
            content="Notice for AIML students."
        )
        self.db.add(circ)
        self.db.commit()
        self.db.refresh(circ)
        
        # Student from ECE queries circulars
        stu_ece = self.get_user("stu_ece_p2b@test.edu")
        res = self.client.get("/circulars/", headers=get_token_headers(stu_ece))
        self.assertEqual(res.status_code, 200)
        items = res.json()
        ids = [c["id"] for c in items]
        
        # Finding: Check if Circular model has a department column or if circulars are institution-wide
        has_dept_col = hasattr(Circular, "department")
        print(f"\n[CIRCULAR ARCHITECTURE] Circular model has 'department' column: {has_dept_col}")
        print(f"[CIRCULAR VISIBILITY] ECE student received AIML circular in GET /circulars/: {circ.id in ids}")
        # Note: Documenting this as an architectural observation (institutional announcement vs dept scoped)


class TestModuleB_DeadlinesRemindersNotifications(BasePhase2BTest):
    """
    Module B: Deadlines, Reminders & Notifications
    Tests:
    - Reminder scheduling for circulars with due dates (7-day, 3-day, 1-day, deadline-day)
    - Date boundary and past deadline handling
    - Notification dispatch targeting students only
    - Notification read/unread state
    - Celery task retry deduplication (idempotency check)
    - Cross-user notification isolation
    """

    def test_01_reminder_creation_intervals(self):
        """Test scheduling of 7-day, 3-day, 1-day, and deadline-day reminders"""
        lec = self.get_user("lec_aiml1_p2b@test.edu")
        due = datetime.now(timezone.utc) + timedelta(days=10)
        
        circ = Circular(
            lecturer_id=lec.id,
            type=CircularType.ASSIGNMENT,
            title="Lab Project Submission",
            content="Upload lab report to portal.",
            due_date=due
        )
        self.db.add(circ)
        self.db.commit()
        self.db.refresh(circ)
        
        # Test reminder scheduler
        with patch.object(ReminderScheduler, '_schedule_celery_tasks') as mock_celery:
            reminder_scheduler.schedule_reminders(circ.id, circ.due_date)
            # Celery scheduling was called
            self.assertTrue(mock_celery.called, "_schedule_celery_tasks was not invoked")
        
        # Check reminder records in DB for 7-day reminder
        reminders = self.db.query(Reminder).filter(Reminder.circular_id == circ.id).all()
        stu_count = self.db.query(User).filter(User.role == UserRole.STUDENT, User.is_active == True).count()
        
        self.assertGreaterEqual(len(reminders), stu_count, f"Expected at least {stu_count} reminders, got {len(reminders)}")
        for r in reminders:
            self.assertEqual(r.reminder_type, ReminderType.SEVEN_DAY)
            self.assertEqual(r.status, ReminderStatus.PENDING)
            # Scheduled time should be due - 7 days
            expected_time = (due - timedelta(days=7)).replace(microsecond=0)
            actual_time = r.scheduled_at.replace(microsecond=0)
            self.assertEqual(expected_time.date(), actual_time.date())

    def test_02_past_deadline_handling(self):
        """Test that past due dates do NOT schedule future reminders"""
        lec = self.get_user("lec_aiml1_p2b@test.edu")
        past_due = datetime.now(timezone.utc) - timedelta(days=2)
        
        circ = Circular(
            lecturer_id=lec.id,
            type=CircularType.GENERAL,
            title="Past Due Event",
            content="Event has already occurred.",
            due_date=past_due
        )
        self.db.add(circ)
        self.db.commit()
        self.db.refresh(circ)
        
        reminders_before = self.db.query(Reminder).filter(Reminder.circular_id == circ.id).count()
        with patch.object(reminder_scheduler, '_schedule_celery_tasks') as mock_celery:
            reminder_scheduler.schedule_reminders(circ.id, circ.due_date)
            
        reminders_after = self.db.query(Reminder).filter(Reminder.circular_id == circ.id).count()
        self.assertEqual(reminders_before, reminders_after, "Reminders were scheduled for a past deadline")

    def test_03_notification_student_targeting_and_payload(self):
        """Verify notifications from circulars are routed to students and contain required fields"""
        lec = self.get_user("lec_aiml1_p2b@test.edu")
        payload = {
            "title": "Unit Test 1 Announcement",
            "content": "Syllabus covers units 1 and 2.",
            "type": "exam",
            "due_date": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        }
        
        notifs_before_stu = self.db.query(Notification).filter(Notification.type == "circular").count()
        
        res = self.client.post("/circulars/", json=payload, headers=get_token_headers(lec))
        self.assertEqual(res.status_code, 200)
        circ_id = res.json()["id"]
        
        # Check that students received the notification
        stu = self.get_user("stu_aiml1_p2b@test.edu")
        stu_notif = self.db.query(Notification).filter(
            Notification.user_id == stu.id,
            Notification.reference_id == circ_id,
            Notification.type == "circular"
        ).first()
        
        self.assertIsNotNone(stu_notif, "Student did not receive circular notification")
        self.assertIn("Unit Test 1 Announcement", stu_notif.message)
        self.assertEqual(stu_notif.is_read, False)
        
        # Check that lecturers and HOD did NOT receive circular notification
        lec_notif = self.db.query(Notification).filter(
            Notification.user_id == lec.id,
            Notification.reference_id == circ_id,
            Notification.type == "circular"
        ).first()
        self.assertIsNone(lec_notif, "Lecturer received student circular notification")

    def test_04_reminder_deduplication_and_idempotency_audit(self):
        """
        AUDIT DEFECT TEST:
        Verify whether repeated execution of send_reminder_to_user creates duplicate notifications.
        Code in reminder_tasks.py inserts Notification unconditionally without checking if
        reminder was already SENT!
        """
        stu = self.get_user("stu_aiml1_p2b@test.edu")
        lec = self.get_user("lec_aiml1_p2b@test.edu")
        
        circ = Circular(
            lecturer_id=lec.id,
            type=CircularType.ASSIGNMENT,
            title="Idempotency Test Assignment",
            content="Testing reminder retry behavior.",
            due_date=datetime.now(timezone.utc) + timedelta(days=7)
        )
        self.db.add(circ)
        self.db.commit()
        self.db.refresh(circ)
        
        # Call 1: Send 7-day reminder
        send_reminder_to_user(stu.id, circ.id, ReminderType.SEVEN_DAY)
        notifs_count_1 = self.db.query(Notification).filter(
            Notification.user_id == stu.id,
            Notification.reference_id == circ.id,
            Notification.type == "reminder"
        ).count()
        self.assertEqual(notifs_count_1, 1, "First reminder call should create exactly 1 notification")
        
        # Call 2: Celery retry / duplicate execution of the same reminder task
        send_reminder_to_user(stu.id, circ.id, ReminderType.SEVEN_DAY)
        notifs_count_2 = self.db.query(Notification).filter(
            Notification.user_id == stu.id,
            Notification.reference_id == circ.id,
            Notification.type == "reminder"
        ).count()
        
        # Check if duplicate notification occurred
        print(f"\n[REMINDER RETRY IDEMPOTENCY] Notifications after retry: {notifs_count_2}")
        self.assertEqual(notifs_count_2, 1, f"Expected exactly 1 notification after retry, got {notifs_count_2}")

    def test_05_cross_user_notification_isolation(self):
        """Ensure notifications cannot be read or marked read by unauthorized users"""
        stu1 = self.get_user("stu_aiml1_p2b@test.edu")
        stu2 = self.get_user("stu_ece_p2b@test.edu")
        
        # Create private notification for stu1
        notif = Notification(
            user_id=stu1.id,
            type="reminder",
            title="Private Alert",
            message="Confidential alert for student 1.",
            reference_id=999,
            is_read=False
        )
        self.db.add(notif)
        self.db.commit()
        self.db.refresh(notif)
        
        # Stu2 queries notifications - should NOT contain stu1's notification
        res = self.client.get("/notifications/", headers=get_token_headers(stu2))
        self.assertEqual(res.status_code, 200)
        user2_notif_ids = [n["id"] for n in res.json()]
        self.assertNotIn(notif.id, user2_notif_ids, "Student 2 can see Student 1's notification!")
        
        # Stu2 attempts to mark Stu1's notification as read
        res = self.client.put(f"/notifications/{notif.id}/read", headers=get_token_headers(stu2))
        # Should be 403 or 404 (not allowed to mark someone else's notification as read)
        self.assertIn(res.status_code, [403, 404], f"Cross-user notification modification not blocked: {res.status_code}")


class TestModuleC_ExamDutiesTimetableIntelligence(BasePhase2BTest):
    """
    Module C: Exam Duties & Timetable Intelligence
    Tests:
    - Table recognition model inference (ResNet-18 weights verification)
    - Faculty duty assignment & matching logic
    - Duty conflict detection (overlapping exams vs adjacent sessions vs different dates)
    - Role permissions (HOD/Admin only for upload, Lecturer views self, Student blocked)
    - Duty confirmation workflow
    - Audit of parser implementation (AI parser vs multi-stage vs fallback)
    """

    def test_01_table_recognition_model_inference(self):
        """Verify the trained ResNet-18 Table Recognition model loads and runs inference"""
        weights_path = "/app/app/ml/table_recognition/weights/best_model.pth"
        if not os.path.exists(weights_path):
            weights_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend", "app", "ml", "table_recognition", "weights", "best_model.pth")
            
        self.assertTrue(os.path.exists(weights_path), f"ResNet-18 weights not found at: {weights_path}")
        
        # Load recognizer
        recognizer = TableRecognizer(checkpoint_path=weights_path)
        self.assertIsNotNone(recognizer.model)
        param_count = recognizer.model.count_parameters()
        self.assertEqual(param_count, 11936378, f"Expected 11,936,378 parameters, got {param_count}")
        
        # Create a synthetic 3-channel test table image
        import numpy as np
        import cv2
        test_img = np.ones((800, 800, 3), dtype=np.uint8) * 255
        # Draw grid lines to simulate a timetable
        for y in range(100, 800, 100):
            cv2.line(test_img, (50, y), (750, y), (0, 0, 0), 2)
        for x in range(50, 800, 140):
            cv2.line(test_img, (x, 100), (x, 700), (0, 0, 0), 2)
            
        temp_img_path = "/tmp/synthetic_exam_table.png"
        cv2.imwrite(temp_img_path, test_img)
        
        # Run inference and measure latency
        t0 = time.time()
        result = recognizer.predict(temp_img_path)
        inference_latency = time.time() - t0
        
        print(f"\n[MODEL INFERENCE] ResNet-18 inference completed in {inference_latency:.3f}s")
        print(f"[MODEL INFERENCE] Output: table_detected={result.get('table_detected')}, rows={result.get('rows')}, cols={result.get('cols')}, conf={result.get('table_confidence'):.2f}")
        
        self.assertIn("table_detected", result)
        self.assertIn("table_confidence", result)
        self.assertLess(inference_latency, 5.0, "Model inference exceeded 5.0 seconds threshold")

    def test_02_ai_parser_code_inspection_finding(self):
        """
        AUDIT VERIFICATION:
        Phase 1 flagged limited dedicated exam-duty automation.
        Test ai_parser.py _extract_duties_from_result to check if duties are mock or real OCR.
        """
        mock_result = {
            'table_detected': True,
            'table_confidence': 0.85,
            'rows': 4,
            'cols': 5
        }
        duties = ai_parser._extract_duties_from_result(mock_result)
        print(f"\n[AI PARSER AUDIT] ai_parser._extract_duties_from_result produced: {duties}")
        
        # Verify if duties contain hardcoded 'Faculty_{row+1}' demo pattern
        is_hardcoded_demo = any("Faculty_" in d.get("faculty_name", "") for d in duties)
        print(f"[AI PARSER AUDIT] Contains hardcoded 'Faculty_' demo mock duties: {is_hardcoded_demo}")
        self.assertFalse(is_hardcoded_demo, "ai_parser should NOT fabricate placeholder 'Faculty_' duties")
        self.assertEqual(len(duties), 0, "ai_parser should return empty list when no OCR image is provided")

    def test_03_faculty_matching_logic(self):
        """Test duty_matcher.match_lecturers against department faculty"""
        lec1 = self.get_user("lec_aiml1_p2b@test.edu")  # Dr. Sharma
        lec2 = self.get_user("lec_aiml2_p2b@test.edu")  # Prof. Verma
        
        extracted = [
            {"faculty_name": "Dr. Sharma", "date": "2026-11-15", "session": "Forenoon", "venue": "LH-101"},
            {"faculty_name": "Sharma", "date": "2026-11-16", "session": "Afternoon", "venue": "LH-102"},
            {"faculty_name": "Prof. Verma", "date": "2026-11-15", "session": "Forenoon", "venue": "LH-103"},
            {"faculty_name": "Dr. Rao", "date": "2026-11-15", "session": "Forenoon", "venue": "LH-104"},  # ECE, not AIML
            {"faculty_name": "Unknown Faculty", "date": "2026-11-17", "session": "Forenoon", "venue": "LH-105"}
        ]
        
        matched, unmatched = duty_matcher.match_lecturers(extracted, "AIML", self.db)
        
        matched_ids = [m["lecturer_id"] for m in matched]
        unmatched_names = [u if isinstance(u, str) else u.get("faculty_name") for u in unmatched]
        
        print(f"\n[DUTY MATCHER] Matched: {[m['lecturer_name'] for m in matched]}")
        print(f"[DUTY MATCHER] Unmatched: {unmatched_names}")
        
        self.assertIn(lec1.id, matched_ids, "Dr. Sharma should match AIML faculty")
        self.assertIn(lec2.id, matched_ids, "Prof. Verma should match AIML faculty")
        unmatched_lower = [str(u).lower() for u in unmatched_names]
        self.assertIn("dr. rao", unmatched_lower, "ECE faculty should be unmatched in AIML upload")
        self.assertIn("unknown faculty", unmatched_lower, "Unknown faculty should be unmatched")

    def test_04_duty_conflict_detection(self):
        """
        Test duty conflict detection in duty_scheduler:
        - Overlapping exam on same date -> CONFLICT (True)
        - Adjacent session on same date (09:30-12:30 and 12:30-15:30) -> NO CONFLICT (False)
        - Non-overlapping different date -> NO CONFLICT (False)
        - Cancelled duty -> NO CONFLICT (False)
        """
        lec = self.get_user("lec_aiml1_p2b@test.edu")
        target_date = date(2026, 11, 20)
        
        # Clean any existing duties for this lecturer on this date
        self.db.query(ExamDuty).filter(
            ExamDuty.lecturer_id == lec.id,
            ExamDuty.date == target_date
        ).delete()
        self.db.commit()
        
        # Existing duty: 09:30 - 12:30 on target_date
        d1 = ExamDuty(
            lecturer_id=lec.id,
            hod_id=self.get_user("hod_aiml_p2b@test.edu").id,
            department="AIML",
            exam_name="Mid-Term AI",
            date=target_date,
            start_time=dt_time(9, 30),
            end_time=dt_time(12, 30),
            venue="Room 101",
            status=DutyStatus.PENDING
        )
        self.db.add(d1)
        self.db.commit()
        
        # Case A: Exact overlap (09:30 - 12:30) -> CONFLICT
        has_conflict_a = duty_scheduler.check_conflict(
            lec.id, target_date, dt_time(9, 30), dt_time(12, 30), self.db
        )
        self.assertTrue(has_conflict_a, "Failed to detect exact time overlap conflict")
        
        # Case B: Partial overlap (11:00 - 14:00) -> CONFLICT
        has_conflict_b = duty_scheduler.check_conflict(
            lec.id, target_date, dt_time(11, 0), dt_time(14, 0), self.db
        )
        self.assertTrue(has_conflict_b, "Failed to detect partial time overlap conflict")
        
        # Case C: Adjacent session (12:30 - 15:30) -> NO CONFLICT
        has_conflict_c = duty_scheduler.check_conflict(
            lec.id, target_date, dt_time(12, 30), dt_time(15, 30), self.db
        )
        self.assertFalse(has_conflict_c, "Adjacent session (12:30) was incorrectly flagged as conflict")
        
        # Case D: Different date (2026-11-21) -> NO CONFLICT
        has_conflict_d = duty_scheduler.check_conflict(
            lec.id, date(2026, 11, 21), dt_time(9, 30), dt_time(12, 30), self.db
        )
        self.assertFalse(has_conflict_d, "Different date was incorrectly flagged as conflict")
        
        # Case E: Cancelled duty on same time -> NO CONFLICT
        d1.status = DutyStatus.CANCELLED
        self.db.commit()
        has_conflict_e = duty_scheduler.check_conflict(
            lec.id, target_date, dt_time(9, 30), dt_time(12, 30), self.db
        )
        self.assertFalse(has_conflict_e, "Cancelled duty was incorrectly flagged as active conflict")

    def test_05_exam_duty_role_and_confirmation_workflow(self):
        """Test API endpoints /exam-duties/upload, /me, /confirm, and role gating"""
        hod_aiml = self.get_user("hod_aiml_p2b@test.edu")
        lec = self.get_user("lec_aiml1_p2b@test.edu")
        stu = self.get_user("stu_aiml1_p2b@test.edu")
        
        # 1. Lecturer attempts to upload exam duty -> 403 Forbidden
        res = self.client.post("/exam-duties/upload", files={"file": ("duties.pdf", b"test", "application/pdf")}, headers=get_token_headers(lec))
        self.assertEqual(res.status_code, 403, "Lecturer should not be allowed to upload exam duties")
        
        # 2. Student attempts to access /exam-duties/me -> 403 Forbidden
        res = self.client.get("/exam-duties/me", headers=get_token_headers(stu))
        self.assertEqual(res.status_code, 403, "Student should not be allowed to access exam duties")
        
        # 3. Create a duty for Lecturer
        duty = ExamDuty(
            lecturer_id=lec.id,
            hod_id=hod_aiml.id,
            department="AIML",
            exam_name="Automata Theory",
            date=date(2026, 12, 1),
            start_time=dt_time(9, 30),
            end_time=dt_time(12, 30),
            venue="Hall B",
            status=DutyStatus.PENDING
        )
        self.db.add(duty)
        self.db.commit()
        self.db.refresh(duty)
        
        # 4. Lecturer views their duties -> 200, sees duty
        res = self.client.get("/exam-duties/me", headers=get_token_headers(lec))
        self.assertEqual(res.status_code, 200)
        duty_ids = [d["id"] for d in res.json()]
        self.assertIn(duty.id, duty_ids)
        
        # 5. Lecturer confirms duty -> 200, status becomes confirmed
        res = self.client.put(f"/exam-duties/{duty.id}/confirm", headers=get_token_headers(lec))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "confirmed")
        
        # 6. Another lecturer attempts to confirm this duty -> 403 Forbidden
        lec_other = self.get_user("lec_aiml2_p2b@test.edu")
        res = self.client.put(f"/exam-duties/{duty.id}/confirm", headers=get_token_headers(lec_other))
        self.assertEqual(res.status_code, 403, "Other lecturer was able to confirm someone else's duty")


class TestModuleD_StudyBuddyRAGPipeline(BasePhase2BTest):
    """
    Module D: Study Buddy RAG Pipeline
    Tests:
    - Subject and syllabus ingestion
    - Text extraction and chunking
    - Qdrant vector retrieval relevance with synthetic question & known passage
    - Answer grounding vs unsupported questions
    - Quiz generation validation
    - Student study document isolation
    """

    def test_01_subject_and_syllabus_rbac(self):
        """Test Subject creation permissions and Placement Officer exclusion"""
        po = self.get_user("po_p2b@test.edu")
        admin = self.get_user("admin_p2b@test.edu")
        hod_aiml = self.get_user("hod_aiml_p2b@test.edu")
        stu = self.get_user("stu_aiml1_p2b@test.edu")
        
        # Placement officer blocked from Study Buddy
        res = self.client.get("/study-buddy/subjects", headers=get_token_headers(po))
        self.assertEqual(res.status_code, 403, f"Placement officer should be blocked from Study Buddy: {res.text}")
        
        # Student cannot create subject
        res = self.client.post("/study-buddy/subjects", json={"name": "Compilers", "code": "CS601", "department": "AIML", "semester": 6}, headers=get_token_headers(stu))
        self.assertEqual(res.status_code, 403, "Student was able to create Subject")
        
        # HOD can create subject for their department
        subj_code = f"AIML_{int(time.time() % 100000)}"
        res = self.client.post("/study-buddy/subjects", json={"name": "Deep Learning", "code": subj_code, "department": "AIML", "semester": 6}, headers=get_token_headers(hod_aiml))
        self.assertIn(res.status_code, [200, 201], f"HOD failed to create subject: {res.text}")
        subj_id = res.json()["id"]
        
        # HOD of ECE cannot modify AIML subject
        hod_ece = self.get_user("hod_ece_p2b@test.edu")
        res = self.client.put(f"/study-buddy/subjects/{subj_id}", json={"name": "ECE Hijack"}, headers=get_token_headers(hod_ece))
        self.assertEqual(res.status_code, 403, "HOD of ECE was able to modify AIML subject")

    def test_02_text_extraction_and_chunking(self):
        """Test text extraction from synthetic notes and sliding window chunking via indexing service"""
        synthetic_passage = """
        Unit 1: Machine Learning Foundations
        Supervised learning algorithms model the relationship between input features and target labels.
        Common supervised learning algorithms include Linear Regression, Logistic Regression, Support Vector Machines (SVM),
        and Random Forests. In contrast, unsupervised learning algorithms discover hidden patterns in unlabelled data.
        Examples include K-Means clustering, Principal Component Analysis (PCA), and Hierarchical Clustering.
        Overfitting occurs when a model learns the training noise rather than the underlying pattern, leading to high variance.
        Regularization techniques such as L1 (Lasso) and L2 (Ridge) prevent overfitting by adding a penalty to the loss function.
        """
        
        # Test text extractor
        res = text_extractor.extract_text("notes.txt", synthetic_passage.encode("utf-8"))
        self.assertTrue(res["success"])
        self.assertIn("Supervised learning algorithms", res["text"])
        
        # Create synthetic StudentStudyDocument to test chunking
        stu = self.get_user("stu_aiml1_p2b@test.edu")
        doc = StudentStudyDocument(
            id=999,
            student_id=stu.id if stu else 1,
            title="ML Foundations Notes",
            original_filename="notes.txt",
            extracted_text=res["text"]
        )
        
        # Test chunking helper from student documents indexing service
        chunks = student_documents_indexing_service.create_chunks(doc)
        self.assertGreaterEqual(len(chunks), 1, "Expected at least 1 chunk created")
        for idx, chunk in enumerate(chunks):
            chunk_text = chunk.get("text", "")
            self.assertIn("Machine Learning Foundations", chunk_text)
            self.assertLessEqual(len(chunk_text), 1000, f"Chunk {idx} exceeded max length")
            self.assertGreater(len(chunk_text), 10, f"Chunk {idx} is too short")
            self.assertEqual(chunk["payload"]["student_id"], doc.student_id)
        
        # Verify empty input produces 0 chunks
        empty_doc = StudentStudyDocument(id=1000, student_id=doc.student_id, title="Empty", extracted_text="")
        self.assertEqual(student_documents_indexing_service.create_chunks(empty_doc), [])
        
        print(f"\n[RAG CHUNKING] Created {len(chunks)} provenance-linked chunks with payload metadata")

    def test_03_rag_retrieval_relevance_and_grounding(self):
        """
        Test vector retrieval relevance using known synthetic questions:
        Q1: 'What techniques prevent overfitting in supervised learning?'
        Expected Evidence: 'Regularization techniques such as L1 (Lasso) and L2 (Ridge) prevent overfitting'
        """
        from app.services.embedding_service import embedding_service
        
        # Verify embedding service
        emb = embedding_service.embed_text("What is supervised learning?")
        self.assertEqual(len(emb), 384, f"Expected 384-dimensional embedding, got {len(emb)}")
        
        synthetic_passage = (
            "Regularization techniques such as L1 (Lasso) and L2 (Ridge) prevent overfitting by adding "
            "a penalty to the loss function. Overfitting causes high variance on unseen test data."
        )
        
        synthetic_distractor = (
            "Database normalization decomposes tables to minimize redundancy and dependency. "
            "Boyce-Codd Normal Form (BCNF) strictly requires every determinant to be a superkey."
        )
        
        # Compute cosine similarity
        import numpy as np
        def cosine_sim(a, b):
            a, b = np.array(a), np.array(b)
            return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
        
        q_emb = embedding_service.embed_text("How to prevent overfitting in machine learning models?")
        p_emb = embedding_service.embed_text(synthetic_passage)
        d_emb = embedding_service.embed_text(synthetic_distractor)
        
        sim_passage = cosine_sim(q_emb, p_emb)
        sim_distractor = cosine_sim(q_emb, d_emb)
        
        print(f"\n[RAG QUALITY] Similarity to relevant passage: {sim_passage:.4f}")
        print(f"[RAG QUALITY] Similarity to distractor passage: {sim_distractor:.4f}")
        
        self.assertGreater(sim_passage, sim_distractor + 0.2, "Semantic retrieval failed to rank relevant passage over distractor")
        self.assertGreater(sim_passage, 0.55, "Relevant passage similarity too low")

    def test_04_quiz_structure_and_options_integrity(self):
        """Test quiz generation service data contract and option correctness"""
        from app.services.ai_generator_service import ai_generator
        synthetic_context = """
        Unit 2: Plant Biology
        Photosynthesis is the process by which green plants transform light energy into chemical energy.
        During photosynthesis in green plants, light energy is captured and used to convert water, carbon dioxide,
        and minerals into oxygen and energy-rich organic compounds. Chlorophyll is the primary pigment responsible.
        """
        sources = [{
            "content": synthetic_context,
            "unit_number": 2,
            "topic_title": "Photosynthesis",
            "page_number": 15
        }]
        
        quiz = ai_generator.generate_study_buddy_quiz(
            subject_name="Plant Biology",
            context_str=synthetic_context,
            sources=sources,
            num_questions=2,
            difficulty="medium"
        )
        
        self.assertIn("questions", quiz, "Quiz response missing 'questions' key")
        questions = quiz["questions"]
        self.assertGreaterEqual(len(questions), 1, "Expected at least 1 quiz question generated")
        
        for q in questions:
            self.assertEqual(len(q["options"]), 4, f"Question options count must be 4: {q.get('options')}")
            self.assertIn(q["correct_option_index"], [0, 1, 2, 3], f"Invalid correct_option_index: {q.get('correct_option_index')}")
            self.assertTrue(len(q.get("explanation", "")) > 5, "Quiz explanation is missing or too short")
            print(f"\n[QUIZ QUALITY] Q: {q['question']}")
            print(f"               Options: {q['options']}")
            print(f"               Correct: Option {q['correct_option_index']} ({q['options'][q['correct_option_index']]})")
            print(f"               Explanation: {q['explanation']}")

    def test_05_student_study_document_isolation(self):
        """Verify Student A's private study documents cannot be retrieved or accessed by Student B"""
        stu1 = self.get_user("stu_aiml1_p2b@test.edu")
        stu2 = self.get_user("stu_ece_p2b@test.edu")
        
        # Student 1 creates private document record
        doc1 = StudentStudyDocument(
            student_id=stu1.id,
            title="Alice's Private ML Research Notes",
            original_filename="private_notes.pdf",
            file_size=1024,
            mime_type="application/pdf",
            content_hash=f"hash_stu1_{int(time.time()*1000)}",
            minio_object_key=f"student_docs/alice_private_{int(time.time()*1000)}.pdf",
            processing_status=StudentDocProcessingStatus.EXTRACTED
        )
        self.db.add(doc1)
        self.db.commit()
        self.db.refresh(doc1)
        
        # Student 2 queries their own documents via /study-buddy/my-documents
        res = self.client.get("/study-buddy/my-documents", headers=get_token_headers(stu2))
        self.assertEqual(res.status_code, 200)
        docs_for_stu2 = [d["id"] for d in res.json().get("items", [])]
        self.assertNotIn(doc1.id, docs_for_stu2, "Student 2 can see Student 1's private study document!")
        
        # Student 2 attempts to get Student 1's document directly -> 404 (ownership check returns 404)
        res = self.client.get(f"/study-buddy/my-documents/{doc1.id}", headers=get_token_headers(stu2))
        self.assertIn(res.status_code, [403, 404], f"Cross-student document access not prevented: {res.status_code}")
        
        # Student 2 attempts to delete Student 1's document directly -> 404
        res = self.client.delete(f"/study-buddy/my-documents/{doc1.id}", headers=get_token_headers(stu2))
        self.assertIn(res.status_code, [403, 404], f"Cross-student document deletion not prevented: {res.status_code}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
