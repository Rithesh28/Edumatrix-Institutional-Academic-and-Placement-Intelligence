"""
EduMatrix Phase 4 — Step 4.6D: Dedicated Secure Lecture Note Download Endpoint Test Suite

Comprehensive test coverage for:
1. Authorized student downloads of published notes (HTTP 200, correct binary, headers).
2. Anti-enumeration: student attempts to download draft/unpublished notes return HTTP 404.
3. Anti-enumeration: student attempts to download archived notes return HTTP 404.
4. Cross-department student download rejection (HTTP 403).
5. Student department resolution via student_profile.branch when user.department is null.
6. Inactive subject protection: students receive HTTP 404 when subject is inactive.
7. Lecturer access: authorized for departmental/assigned subjects, denied on cross-department unassigned subjects.
8. Lecturer access to draft notes for own subjects (allows previewing unpublished materials).
9. HOD department restriction: access to department notes, denial on other departments (HTTP 403).
10. Admin institutional access: global download capability across departments and publication states.
11. Placement Officer strict denial (HTTP 403) across all download attempts.
12. Missing note handling: non-existent note returns HTTP 404.
13. Missing MinIO object handling: valid DB record with missing storage binary returns HTTP 404 without crashing.
14. Atomic download count increment: count increments on successful download, remains unchanged on failures.
15. Correct Content-Disposition and MIME type headers.
16. Regression protection: generic file download (/files/{file_id}/download) and syllabus endpoints unaffected.
"""

import os
import io
import time
import uuid
import unittest
from datetime import datetime, timezone
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.user import User, UserRole, LecturerProfile
from app.models.profile import StudentProfileExtended
from app.models.file import File, FileStatus
from app.models.study_buddy import (
    Subject,
    LectureNote,
    LectureNoteStatus,
    LectureNoteProcessingStatus,
    LectureNoteIndexingStatus,
)
from app.services.file_storage.minio_client import minio_client
from app.main import app


class TestStudyBuddyStep46D(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db: Session = SessionLocal()
        cls.timestamp = int(time.time() * 1000)

        # Users across roles
        cls.admin = cls.db.query(User).filter(User.role == UserRole.ADMIN).first()
        cls.hod_aiml = cls.db.query(User).filter(User.role == UserRole.HOD, User.department == "AIML").first()
        cls.hod_cse = cls.db.query(User).filter(User.role == UserRole.HOD, User.department == "CSE").first()
        cls.lecturer_aiml = cls.db.query(User).filter(User.role == UserRole.LECTURER, User.department == "AIML").first()
        cls.student_aiml = cls.db.query(User).filter(User.role == UserRole.STUDENT, User.department == "AIML").first()
        cls.student_ece = cls.db.query(User).filter(User.role == UserRole.STUDENT, User.department == "ECE").first()
        cls.po = cls.db.query(User).filter(User.role == UserRole.PLACEMENT_OFFICER).first()

        # Auth headers
        cls.admin_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.admin.email, 'id': cls.admin.id, 'role': 'admin'})}"}
        cls.hod_aiml_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.hod_aiml.email, 'id': cls.hod_aiml.id, 'role': 'hod'})}"}
        cls.hod_cse_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.hod_cse.email, 'id': cls.hod_cse.id, 'role': 'hod'})}"}
        cls.lecturer_aiml_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.lecturer_aiml.email, 'id': cls.lecturer_aiml.id, 'role': 'lecturer'})}"}
        cls.student_aiml_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.student_aiml.email, 'id': cls.student_aiml.id, 'role': 'student'})}"}
        cls.student_ece_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.student_ece.email, 'id': cls.student_ece.id, 'role': 'student'})}"}
        cls.po_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.po.email, 'id': cls.po.id, 'role': 'placement_officer'})}"}

        cls.created_subject_ids = []
        cls.created_file_ids = []
        cls.created_note_ids = []
        cls.created_minio_keys = []
        cls.created_user_ids = []

        # 1. Primary Active Subject (AIML)
        cls.aiml_code = f"LN{cls.timestamp % 100000}A"
        cls.subject_aiml = Subject(
            code=cls.aiml_code,
            name=f"Deep Learning Systems {cls.aiml_code}",
            department="AIML",
            semester=6,
            academic_year="2026-2027",
            curriculum_version="2026.1",
            description="Test subject for Step 4.6D download testing",
            is_active=True
        )
        cls.db.add(cls.subject_aiml)

        # 2. Secondary Subject (ECE)
        cls.ece_code = f"LN{cls.timestamp % 100000}E"
        cls.subject_ece = Subject(
            code=cls.ece_code,
            name=f"Signals & Systems {cls.ece_code}",
            department="ECE",
            semester=4,
            academic_year="2026-2027",
            curriculum_version="2026.1",
            description="ECE test subject for isolation testing",
            is_active=True
        )
        cls.db.add(cls.subject_ece)

        # 3. Inactive Subject (AIML)
        cls.inactive_code = f"LN{cls.timestamp % 100000}I"
        cls.subject_inactive = Subject(
            code=cls.inactive_code,
            name=f"Legacy AI {cls.inactive_code}",
            department="AIML",
            semester=8,
            academic_year="2024-2025",
            curriculum_version="2024.1",
            description="Inactive subject for access testing",
            is_active=False
        )
        cls.db.add(cls.subject_inactive)

        cls.db.commit()
        cls.db.refresh(cls.subject_aiml)
        cls.db.refresh(cls.subject_ece)
        cls.db.refresh(cls.subject_inactive)
        cls.created_subject_ids.extend([cls.subject_aiml.id, cls.subject_ece.id, cls.subject_inactive.id])

        # Create test student with user.department = None but student_profile.branch = "AIML"
        cls.branch_student_email = f"branch_stu_{cls.timestamp}@edumatrix.edu"
        cls.branch_student = User(
            email=cls.branch_student_email,
            password_hash="hashed_pw_test",
            name="Branch Only Student",
            role=UserRole.STUDENT,
            department=None,  # Null department on User model!
            is_active=True
        )
        cls.db.add(cls.branch_student)
        cls.db.commit()
        cls.db.refresh(cls.branch_student)
        cls.created_user_ids.append(cls.branch_student.id)

        cls.branch_profile = StudentProfileExtended(
            user_id=cls.branch_student.id,
            enrollment_number=f"1EM{cls.timestamp % 100000}",
            branch="AIML",  # Department stored in profile branch!
            semester=6,
            cgpa=9.1
        )
        cls.db.add(cls.branch_profile)
        cls.db.commit()
        cls.branch_student_headers = {
            "Authorization": f"Bearer {create_access_token({'sub': cls.branch_student.email, 'id': cls.branch_student.id, 'role': 'student'})}"
        }

        # 4. Upload sample binaries to MinIO and create note records
        cls.sample_pdf_content = cls._generate_pdf_bytes("Unit 1: Foundations of Deep Learning and Neural Architectures.")
        cls.sample_docx_content = b"PK\x03\x04\x14\x00\x00\x00\x08\x00Dummy DOCX binary content for Step 4.6D download test."

        # Note 1: Published AIML Note
        cls.note_published = cls._create_persisted_note(
            subject=cls.subject_aiml,
            title="Published Deep Learning Notes",
            filename="deep_learning_u1.pdf",
            content=cls.sample_pdf_content,
            mime_type="application/pdf",
            status=LectureNoteStatus.PUBLISHED,
            is_published=True,
            processing_status=LectureNoteProcessingStatus.EXTRACTED
        )

        # Note 2: Draft AIML Note (Extracted but unapproved/draft)
        cls.note_draft = cls._create_persisted_note(
            subject=cls.subject_aiml,
            title="Draft Neural Network Tutorial",
            filename="nn_tutorial_draft.pdf",
            content=cls.sample_pdf_content,
            mime_type="application/pdf",
            status=LectureNoteStatus.DRAFT,
            is_published=False,
            processing_status=LectureNoteProcessingStatus.EXTRACTED
        )

        # Note 3: Archived AIML Note
        cls.note_archived = cls._create_persisted_note(
            subject=cls.subject_aiml,
            title="Archived Optimization Notes",
            filename="optimization_old.docx",
            content=cls.sample_docx_content,
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            status=LectureNoteStatus.ARCHIVED,
            is_published=False,
            processing_status=LectureNoteProcessingStatus.EXTRACTED
        )

        # Note 4: Published ECE Note (for cross-department testing)
        cls.note_ece_published = cls._create_persisted_note(
            subject=cls.subject_ece,
            title="Published Signals Notes",
            filename="signals_u1.pdf",
            content=cls.sample_pdf_content,
            mime_type="application/pdf",
            status=LectureNoteStatus.PUBLISHED,
            is_published=True,
            processing_status=LectureNoteProcessingStatus.EXTRACTED
        )

        # Note 5: Published Note on Inactive Subject
        cls.note_inactive = cls._create_persisted_note(
            subject=cls.subject_inactive,
            title="Inactive Subject Notes",
            filename="legacy_ai.pdf",
            content=cls.sample_pdf_content,
            mime_type="application/pdf",
            status=LectureNoteStatus.PUBLISHED,
            is_published=True,
            processing_status=LectureNoteProcessingStatus.EXTRACTED
        )

        # Note 6: Missing MinIO Object Note (DB record exists, but MinIO key does not exist)
        cls.note_missing_blob = cls._create_persisted_note(
            subject=cls.subject_aiml,
            title="Missing Storage Note",
            filename="ghost_file.pdf",
            content=None,  # Do not upload to MinIO!
            mime_type="application/pdf",
            status=LectureNoteStatus.PUBLISHED,
            is_published=True,
            processing_status=LectureNoteProcessingStatus.EXTRACTED
        )

    @classmethod
    def _generate_pdf_bytes(cls, text: str) -> bytes:
        pdf_io = io.BytesIO()
        c = canvas.Canvas(pdf_io)
        c.drawString(100, 750, text)
        c.save()
        pdf_io.seek(0)
        return pdf_io.read()

    @classmethod
    def _create_persisted_note(
        cls,
        subject: Subject,
        title: str,
        filename: str,
        content: bytes | None,
        mime_type: str,
        status: LectureNoteStatus,
        is_published: bool,
        processing_status: LectureNoteProcessingStatus
    ) -> LectureNote:
        file_uuid = uuid.uuid4()
        object_key = f"notes/{subject.id}/{file_uuid}_{filename}"
        file_size = len(content) if content else 1024

        if content:
            minio_client.upload_file(
                bucket="lecture-notes",
                object_key=object_key,
                file_data=content,
                content_type=mime_type
            )
            cls.created_minio_keys.append(object_key)

        file_rec = File(
            id=file_uuid,
            filename=filename,
            file_size=file_size,
            mime_type=mime_type,
            bucket="lecture-notes",
            object_key=object_key,
            title=title,
            department=subject.department,
            file_type="lecture_note",
            uploaded_by=cls.lecturer_aiml.id,
            status=FileStatus.ACTIVE
        )
        cls.db.add(file_rec)

        note = LectureNote(
            subject_id=subject.id,
            uploaded_by_id=cls.lecturer_aiml.id,
            file_id=file_uuid,
            title=title,
            original_filename=filename,
            file_size=file_size,
            mime_type=mime_type,
            minio_bucket="lecture-notes",
            minio_object_key=object_key,
            status=status,
            is_published=is_published,
            processing_status=processing_status,
            indexing_status=LectureNoteIndexingStatus.NOT_INDEXED,
            download_count=0
        )
        cls.db.add(note)
        cls.db.commit()
        cls.db.refresh(note)
        cls.created_file_ids.append(file_uuid)
        cls.created_note_ids.append(note.id)
        return note

    @classmethod
    def tearDownClass(cls):
        # 1. Clean MinIO objects
        for key in cls.created_minio_keys:
            try:
                minio_client.delete_file("lecture-notes", key)
            except Exception:
                pass

        # 2. Clean LectureNotes
        if cls.created_note_ids:
            cls.db.query(LectureNote).filter(LectureNote.id.in_(cls.created_note_ids)).delete(synchronize_session=False)
            cls.db.commit()

        # 3. Clean Files
        if cls.created_file_ids:
            cls.db.query(File).filter(File.id.in_(cls.created_file_ids)).delete(synchronize_session=False)
            cls.db.commit()

        # 4. Clean Subjects
        if cls.created_subject_ids:
            cls.db.query(Subject).filter(Subject.id.in_(cls.created_subject_ids)).delete(synchronize_session=False)
            cls.db.commit()

        # 5. Clean Test Users
        if cls.created_user_ids:
            cls.db.query(StudentProfileExtended).filter(StudentProfileExtended.user_id.in_(cls.created_user_ids)).delete(synchronize_session=False)
            cls.db.query(User).filter(User.id.in_(cls.created_user_ids)).delete(synchronize_session=False)
            cls.db.commit()

        cls.db.close()

    # =========================================================================
    # 1. STUDENT ACCESS TESTS
    # =========================================================================

    def test_01_authorized_student_download_published_note(self):
        """Student in AIML can successfully download published AIML lecture note."""
        initial_note = self.db.query(LectureNote).filter(LectureNote.id == self.note_published.id).first()
        initial_count = initial_note.download_count

        res = self.client.get(
            f"/study-buddy/notes/{self.note_published.id}/download",
            headers=self.student_aiml_headers
        )
        self.assertEqual(res.status_code, 200, f"Expected 200, got: {res.text}")
        self.assertEqual(res.content, self.sample_pdf_content)
        self.assertIn("application/pdf", res.headers.get("Content-Type", ""))
        self.assertIn('filename="deep_learning_u1.pdf"', res.headers.get("Content-Disposition", ""))

        # Check atomic counter increment
        self.db.refresh(initial_note)
        self.assertEqual(initial_note.download_count, initial_count + 1)

    def test_02_student_attempt_download_draft_note_returns_404(self):
        """Student receives 404 (anti-enumeration) when attempting to download draft note."""
        initial_note = self.db.query(LectureNote).filter(LectureNote.id == self.note_draft.id).first()
        initial_count = initial_note.download_count

        res = self.client.get(
            f"/study-buddy/notes/{self.note_draft.id}/download",
            headers=self.student_aiml_headers
        )
        self.assertEqual(res.status_code, 404, "Draft note must return 404 for students")

        # Counter must NOT increment on 404
        self.db.refresh(initial_note)
        self.assertEqual(initial_note.download_count, initial_count)

    def test_03_student_attempt_download_archived_note_returns_404(self):
        """Student receives 404 (anti-enumeration) when attempting to download archived note."""
        initial_note = self.db.query(LectureNote).filter(LectureNote.id == self.note_archived.id).first()
        initial_count = initial_note.download_count

        res = self.client.get(
            f"/study-buddy/notes/{self.note_archived.id}/download",
            headers=self.student_aiml_headers
        )
        self.assertEqual(res.status_code, 404, "Archived note must return 404 for students")

        self.db.refresh(initial_note)
        self.assertEqual(initial_note.download_count, initial_count)

    def test_04_cross_department_student_denied(self):
        """Student in ECE cannot download published AIML note (cross-department isolation)."""
        res = self.client.get(
            f"/study-buddy/notes/{self.note_published.id}/download",
            headers=self.student_ece_headers
        )
        self.assertEqual(res.status_code, 403, "Cross-department student must be denied with 403")

    def test_05_student_department_resolved_via_profile_branch(self):
        """Student whose user.department is None but student_profile.branch is 'AIML' can download."""
        res = self.client.get(
            f"/study-buddy/notes/{self.note_published.id}/download",
            headers=self.branch_student_headers
        )
        self.assertEqual(res.status_code, 200, f"Expected 200 via profile branch, got: {res.text}")
        self.assertEqual(res.content, self.sample_pdf_content)

    def test_06_student_denied_on_inactive_subject_returns_404(self):
        """Student cannot download note from inactive subject (returns 404)."""
        res = self.client.get(
            f"/study-buddy/notes/{self.note_inactive.id}/download",
            headers=self.student_aiml_headers
        )
        self.assertEqual(res.status_code, 404, "Inactive subject note must return 404 for student")

    # =========================================================================
    # 2. FACULTY & STAFF ACCESS TESTS
    # =========================================================================

    def test_07_lecturer_can_download_published_and_draft_notes_for_own_subject(self):
        """Lecturer can download both published and draft notes for their department subject."""
        # 1. Published note
        res_pub = self.client.get(
            f"/study-buddy/notes/{self.note_published.id}/download",
            headers=self.lecturer_aiml_headers
        )
        self.assertEqual(res_pub.status_code, 200)

        # 2. Draft note (lecturer needs to preview their draft uploads)
        res_draft = self.client.get(
            f"/study-buddy/notes/{self.note_draft.id}/download",
            headers=self.lecturer_aiml_headers
        )
        self.assertEqual(res_draft.status_code, 200, "Lecturer must be able to download draft notes for review")

    def test_08_lecturer_denied_on_unassigned_cross_department_subject(self):
        """Lecturer in AIML cannot download notes for ECE subject unless assigned."""
        res = self.client.get(
            f"/study-buddy/notes/{self.note_ece_published.id}/download",
            headers=self.lecturer_aiml_headers
        )
        self.assertEqual(res.status_code, 403, "Lecturer must be denied on cross-department subject")

    def test_09_hod_access_and_department_boundary(self):
        """HOD of AIML can download departmental notes; HOD of CSE is denied."""
        # HOD AIML -> AIML note (allowed)
        res_aiml = self.client.get(
            f"/study-buddy/notes/{self.note_published.id}/download",
            headers=self.hod_aiml_headers
        )
        self.assertEqual(res_aiml.status_code, 200)

        # HOD CSE -> AIML note (denied with 403)
        res_cse = self.client.get(
            f"/study-buddy/notes/{self.note_published.id}/download",
            headers=self.hod_cse_headers
        )
        self.assertEqual(res_cse.status_code, 403, "HOD CSE must be denied for AIML note")

    def test_10_admin_global_access(self):
        """Admin can download notes across departments and publication statuses."""
        # Published AIML
        res1 = self.client.get(
            f"/study-buddy/notes/{self.note_published.id}/download",
            headers=self.admin_headers
        )
        self.assertEqual(res1.status_code, 200)

        # Draft AIML
        res2 = self.client.get(
            f"/study-buddy/notes/{self.note_draft.id}/download",
            headers=self.admin_headers
        )
        self.assertEqual(res2.status_code, 200)

        # ECE note
        res3 = self.client.get(
            f"/study-buddy/notes/{self.note_ece_published.id}/download",
            headers=self.admin_headers
        )
        self.assertEqual(res3.status_code, 200)

    def test_11_placement_officer_denied(self):
        """Placement Officers are strictly blocked from downloading lecture notes."""
        res = self.client.get(
            f"/study-buddy/notes/{self.note_published.id}/download",
            headers=self.po_headers
        )
        self.assertEqual(res.status_code, 403, "Placement Officer must be denied with 403")

    # =========================================================================
    # 3. EDGE CASES: MISSING NOTE, MISSING MINIO BLOB, ATOMICITY
    # =========================================================================

    def test_12_missing_note_id_returns_404(self):
        """Non-existent note_id returns 404."""
        res = self.client.get(
            "/study-buddy/notes/9999999/download",
            headers=self.admin_headers
        )
        self.assertEqual(res.status_code, 404)

    def test_13_missing_minio_blob_returns_404_without_counter_increment(self):
        """Note record exists in DB, but binary object is missing in MinIO returns 404."""
        initial_note = self.db.query(LectureNote).filter(LectureNote.id == self.note_missing_blob.id).first()
        initial_count = initial_note.download_count

        res = self.client.get(
            f"/study-buddy/notes/{self.note_missing_blob.id}/download",
            headers=self.admin_headers
        )
        self.assertEqual(res.status_code, 404, "Missing MinIO binary must return 404")
        self.assertIn("not found in storage", res.json().get("detail", ""))

        self.db.refresh(initial_note)
        self.assertEqual(initial_note.download_count, initial_count, "Counter must not increment when blob is missing")

    def test_14_atomic_download_count_increments_consecutively(self):
        """Consecutive successful downloads increment download_count accurately without lost updates."""
        note = self.db.query(LectureNote).filter(LectureNote.id == self.note_published.id).first()
        self.db.refresh(note)
        start_count = note.download_count

        for i in range(1, 4):
            res = self.client.get(
                f"/study-buddy/notes/{self.note_published.id}/download",
                headers=self.admin_headers
            )
            self.assertEqual(res.status_code, 200)
            self.db.refresh(note)
            self.assertEqual(note.download_count, start_count + i)

    # =========================================================================
    # 4. REGRESSION VERIFICATIONS
    # =========================================================================

    def test_15_regression_generic_file_download_endpoint_still_operates(self):
        """Generic /files/{file_id}/download endpoint continues to operate normally."""
        res = self.client.get(
            f"/files/{self.note_published.file_id}/download",
            headers=self.admin_headers
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content, self.sample_pdf_content)

    def test_16_regression_study_buddy_subjects_and_notes_list_operates(self):
        """Study Buddy subject listing and note metadata listing remain functional."""
        res_sub = self.client.get(
            "/study-buddy/subjects",
            headers=self.admin_headers
        )
        self.assertEqual(res_sub.status_code, 200)

        res_notes = self.client.get(
            f"/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.admin_headers
        )
        self.assertEqual(res_notes.status_code, 200)
        self.assertGreaterEqual(len(res_notes.json()), 1)


if __name__ == "__main__":
    unittest.main()
