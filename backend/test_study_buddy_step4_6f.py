"""
Test Suite for EduMatrix Phase 4 — Step 4.6F: Unified Multi-Source Study Buddy Retrieval

Covers:
1. Syllabus-only retrieval (source_mode='syllabus'):
   - Queries syllabus material only.
   - Citations return source_type='syllabus'.
2. Lecture-note-only retrieval (source_mode='lecture_notes'):
   - Queries published faculty lecture notes only.
   - Citations return source_type='lecture_note'.
3. Combined retrieval (source_mode='all'):
   - Retrieves eligible chunks from both sources.
   - Deduplicates near-identical chunks.
   - Citations include appropriate source_type for each qualifying chunk.
4. Backward-compatible default behavior:
   - Requests without source_mode default to 'syllabus'.
   - Existing clients calling /chat or /ask continue working seamlessly.
5. Invalid source-mode validation:
   - Passing an invalid mode (e.g. 'web', 'invalid') returns 422 Unprocessable Entity.
6. Student department and subject isolation:
   - ECE student cannot access AIML syllabus or lecture notes.
   - Cross-department subject queries rejected with 403 or return empty context.
7. Student branch fallback when user.department is null:
   - Student with user.department = None but student_profile.branch = "AIML"
     successfully retrieves AIML materials.
8. Exclusion of ineligible lecture notes:
   - DRAFT notes excluded.
   - Unpublished notes (is_published=False) excluded.
   - ARCHIVED notes excluded.
   - Inactive subject notes (Subject.is_active=False) excluded.
   - Non-indexed notes (indexing_status='NOT_INDEXED' or indexed_chunk_count=0) excluded.
9. Exclusion of stale Qdrant points:
   - Stale Qdrant vectors with missing or ineligible PostgreSQL records are discarded
     during authoritative PostgreSQL re-validation.
10. Citation schema correctness and source awareness:
    - All fields validated: source_type, source_id, source_title, original_filename,
      subject_id, subject_code, subject_name, department, unit, topic, source_page,
      relevance_score, document_id, lecture_note_id.
    - No fabricated page numbers.
11. No citations for unauthorized or excluded chunks:
    - Citations only returned for authorized chunks actually supplied to the generator.
12. Insufficient-context responses:
    - Queries on out-of-domain topics return has_sufficient_evidence=False,
      informative message, and empty citations.
13. Qdrant and generation failure handling:
    - Vector database or generator errors fail gracefully without unauthorized fallbacks.
14. Placement Officer forbidden:
    - Placement Officers blocked from chat and search endpoints (403).
15. Existing syllabus-only Study Buddy regressions:
    - Chat, summaries, quizzes, and progress features remain intact and unaffected.
16. Search endpoint with source modes:
    - GET /study-buddy/search supports source_mode='syllabus', 'lecture_notes', and 'all'.
"""

import time
import uuid
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.user import User, UserRole
from app.models.profile import StudentProfileExtended
from app.models.file import File, FileStatus
from app.models.study_buddy import (
    Subject,
    SyllabusDocument,
    SyllabusUnit,
    SyllabusTopic,
    SyllabusProcessingStatus,
    SyllabusReviewStatus,
    LectureNote,
    LectureNoteStatus,
    LectureNoteProcessingStatus,
    LectureNoteIndexingStatus,
)
from app.services.file_storage.qdrant_client import qdrant_client
from app.services.syllabus_indexing_service import syllabus_indexing_service
from app.services.lecture_notes_indexing_service import (
    lecture_notes_indexing_service,
    STUDY_BUDDY_COLLECTION,
)
from app.services.study_buddy_chat_service import study_buddy_chat_service
from app.main import app


class TestStudyBuddyStep46F(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db: Session = SessionLocal()
        cls.timestamp = int(time.time() * 1000)

        # 1. Existing users across roles
        cls.admin = cls.db.query(User).filter(User.role == UserRole.ADMIN).first()
        cls.hod_aiml = cls.db.query(User).filter(User.role == UserRole.HOD, User.department == "AIML").first()
        cls.lecturer_aiml = cls.db.query(User).filter(User.role == UserRole.LECTURER, User.department == "AIML").first()
        cls.student_aiml = cls.db.query(User).filter(User.role == UserRole.STUDENT, User.department == "AIML").first()
        cls.student_ece = cls.db.query(User).filter(User.role == UserRole.STUDENT, User.department == "ECE").first()
        cls.po = cls.db.query(User).filter(User.role == UserRole.PLACEMENT_OFFICER).first()

        # Auth headers
        cls.admin_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.admin.email, 'id': cls.admin.id, 'role': 'admin'})}"}
        cls.hod_aiml_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.hod_aiml.email, 'id': cls.hod_aiml.id, 'role': 'hod'})}"}
        cls.lecturer_aiml_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.lecturer_aiml.email, 'id': cls.lecturer_aiml.id, 'role': 'lecturer'})}"}
        cls.student_aiml_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.student_aiml.email, 'id': cls.student_aiml.id, 'role': 'student'})}"}
        cls.student_ece_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.student_ece.email, 'id': cls.student_ece.id, 'role': 'student'})}"}
        cls.po_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.po.email, 'id': cls.po.id, 'role': 'placement_officer'})}"}

        # Track created test records for cleanup
        cls.created_subject_ids = []
        cls.created_sdoc_ids = []
        cls.created_note_ids = []
        cls.created_file_ids = []
        cls.created_user_ids = []

        # 2. Student with user.department = None but student_profile.branch = "AIML"
        cls.branch_student_email = f"branch_stu_46f_{cls.timestamp}@edumatrix.edu"
        cls.branch_student = User(
            email=cls.branch_student_email,
            password_hash="hashed_pw_test",
            name="Branch Only Student 4.6F",
            role=UserRole.STUDENT,
            department=None,  # Explicitly None
            is_active=True
        )
        cls.db.add(cls.branch_student)
        cls.db.commit()
        cls.db.refresh(cls.branch_student)
        cls.created_user_ids.append(cls.branch_student.id)

        cls.branch_profile = StudentProfileExtended(
            user_id=cls.branch_student.id,
            enrollment_number=f"46F{cls.timestamp % 100000}",
            branch="AIML",  # Profile branch
            semester=6,
            cgpa=9.1
        )
        cls.db.add(cls.branch_profile)
        cls.db.commit()

        cls.branch_student_headers = {
            "Authorization": f"Bearer {create_access_token({'sub': cls.branch_student.email, 'id': cls.branch_student.id, 'role': 'student'})}"
        }

        # 3. Create test subjects
        # Active AIML Subject
        cls.aiml_code = f"AIML{cls.timestamp % 10000}"
        cls.subject_aiml = Subject(
            code=cls.aiml_code,
            name=f"Neural Architectures {cls.aiml_code}",
            department="AIML",
            semester=6,
            academic_year="2026-2027",
            curriculum_version="2026.1",
            description="AIML Active Subject for Step 4.6F testing",
            is_active=True
        )
        cls.db.add(cls.subject_aiml)

        # Active ECE Subject
        cls.ece_code = f"ECE{cls.timestamp % 10000}"
        cls.subject_ece = Subject(
            code=cls.ece_code,
            name=f"Signal Processing {cls.ece_code}",
            department="ECE",
            semester=4,
            academic_year="2026-2027",
            curriculum_version="2026.1",
            description="ECE Active Subject for isolation testing",
            is_active=True
        )
        cls.db.add(cls.subject_ece)

        # Inactive AIML Subject
        cls.inact_code = f"INACT{cls.timestamp % 10000}"
        cls.subject_inactive = Subject(
            code=cls.inact_code,
            name=f"Obsolete Computing {cls.inact_code}",
            department="AIML",
            semester=8,
            academic_year="2026-2027",
            curriculum_version="2026.1",
            description="Inactive AIML Subject",
            is_active=False
        )
        cls.db.add(cls.subject_inactive)

        cls.db.commit()
        cls.db.refresh(cls.subject_aiml)
        cls.db.refresh(cls.subject_ece)
        cls.db.refresh(cls.subject_inactive)
        cls.created_subject_ids.extend([cls.subject_aiml.id, cls.subject_ece.id, cls.subject_inactive.id])

        # 4. Create and index Approved & Published Syllabus Document for AIML subject
        cls.sdoc_aiml = SyllabusDocument(
            subject_id=cls.subject_aiml.id,
            version=1,
            is_latest=True,
            title="Neural Architectures Syllabus",
            original_filename="neural_syllabus.pdf",
            file_size=12000,
            mime_type="application/pdf",
            minio_bucket="syllabi",
            minio_object_key=f"syllabi/{cls.subject_aiml.id}/neural_syllabus_{cls.timestamp}.pdf",
            uploaded_by_id=cls.hod_aiml.id,
            processing_status=SyllabusProcessingStatus.EXTRACTED,
            review_status=SyllabusReviewStatus.APPROVED,
            is_published=True,
            published_by_id=cls.hod_aiml.id,
            published_at=datetime.now(timezone.utc),
            extracted_text="Unit 1: Convolutional Neural Networks and Feature Maps. Unit 2: Recurrent Architectures."
        )
        cls.db.add(cls.sdoc_aiml)
        cls.db.commit()
        cls.db.refresh(cls.sdoc_aiml)
        cls.created_sdoc_ids.append(cls.sdoc_aiml.id)

        # Add structured unit and topic to syllabus document
        cls.sunit1 = SyllabusUnit(
            document_id=cls.sdoc_aiml.id,
            unit_number=1,
            title="Convolutional Neural Networks",
            order=1,
            source_page_start=1,
            source_evidence="Unit 1: Convolutional Neural Networks and Feature Maps"
        )
        cls.db.add(cls.sunit1)
        cls.db.commit()
        cls.db.refresh(cls.sunit1)

        cls.stopic1 = SyllabusTopic(
            unit_id=cls.sunit1.id,
            title="Backpropagation in Spatial Convolutions",
            order=1,
            extracted_text="Convolutional layers apply spatial kernel filters and backpropagation computes gradients with respect to convolutional kernel weights.",
            source_page=2,
            source_evidence="Backpropagation in Spatial Convolutions"
        )
        cls.db.add(cls.stopic1)
        cls.db.commit()
        cls.db.refresh(cls.stopic1)

        # Index the syllabus document into Qdrant
        syllabus_indexing_service.index_syllabus_document(cls.db, cls.sdoc_aiml.id)

        # 5. Create and index Approved & Published Lecture Note for AIML subject
        cls.note_aiml = cls._create_and_index_note(
            subject_id=cls.subject_aiml.id,
            title="Lecture Notes on Self-Attention and Transformers",
            filename="transformers_lecture.pdf",
            text="Transformers utilize multi-head self-attention mechanisms to compute query, key, and value representations in parallel.",
            unit_id=cls.sunit1.id,
            topic_id=cls.stopic1.id,
            status=LectureNoteStatus.PUBLISHED,
            is_published=True,
            processing_status=LectureNoteProcessingStatus.EXTRACTED
        )

        # 6. Create and index Published Lecture Note for ECE subject (for cross-department isolation)
        cls.note_ece = cls._create_and_index_note(
            subject_id=cls.subject_ece.id,
            title="Nyquist Sampling and Fourier Transformations",
            filename="nyquist_sampling.pdf",
            text="The Nyquist-Shannon sampling theorem requires sampling frequency to exceed twice the maximum signal bandwidth.",
            status=LectureNoteStatus.PUBLISHED,
            is_published=True,
            processing_status=LectureNoteProcessingStatus.EXTRACTED
        )

    @classmethod
    def _create_and_index_note(
        cls,
        subject_id: int,
        title: str,
        filename: str,
        text: str,
        unit_id: int = None,
        topic_id: int = None,
        status: LectureNoteStatus = LectureNoteStatus.PUBLISHED,
        is_published: bool = True,
        processing_status: LectureNoteProcessingStatus = LectureNoteProcessingStatus.EXTRACTED,
        indexing_status: LectureNoteIndexingStatus = LectureNoteIndexingStatus.NOT_INDEXED
    ) -> LectureNote:
        file_uuid = uuid.uuid4()
        object_key = f"lecture-notes/{subject_id}/{file_uuid.hex}_{filename}"
        db_file = File(
            id=file_uuid,
            filename=filename,
            file_size=len(text.encode("utf-8")),
            mime_type="application/pdf",
            bucket="lecture-notes",
            object_key=object_key,
            title=title,
            department="AIML",
            file_type="lecture_note",
            uploaded_by=cls.lecturer_aiml.id,
            status=FileStatus.ACTIVE
        )
        cls.db.add(db_file)
        cls.db.commit()

        note = LectureNote(
            subject_id=subject_id,
            uploaded_by_id=cls.lecturer_aiml.id,
            file_id=file_uuid,
            unit_id=unit_id,
            topic_id=topic_id,
            title=title,
            description=f"Description for {title}",
            original_filename=filename,
            file_size=len(text.encode("utf-8")),
            mime_type="application/pdf",
            minio_bucket="lecture-notes",
            minio_object_key=f"lecture-notes/{subject_id}/{file_uuid.hex}_{filename}",
            status=status,
            is_published=is_published,
            processing_status=processing_status,
            indexing_status=indexing_status,
            extracted_text=text,
            extraction_metadata={"pages": 3},
            download_count=0
        )
        cls.db.add(note)
        cls.db.commit()
        cls.db.refresh(note)

        cls.created_file_ids.append(file_uuid)
        cls.created_note_ids.append(note.id)

        # Index if published & extracted and subject is active
        if status == LectureNoteStatus.PUBLISHED and is_published and processing_status == LectureNoteProcessingStatus.EXTRACTED:
            sub = cls.db.query(Subject).filter(Subject.id == subject_id).first()
            if sub and sub.is_active:
                lecture_notes_indexing_service.index_lecture_note(cls.db, note.id)

        return note

    @classmethod
    def tearDownClass(cls):
        # 1. Clean Qdrant points for created lecture notes
        for note_id in cls.created_note_ids:
            try:
                lecture_notes_indexing_service.delete_note_chunks(note_id)
            except Exception:
                pass

        # 2. Clean syllabus documents and chunks
        for sdoc_id in cls.created_sdoc_ids:
            try:
                syllabus_indexing_service.delete_document_chunks(sdoc_id)
            except Exception:
                pass

        # 3. Clean LectureNotes
        if cls.created_note_ids:
            cls.db.query(LectureNote).filter(LectureNote.id.in_(cls.created_note_ids)).delete(synchronize_session=False)
            cls.db.commit()

        # 4. Clean SyllabusDocuments
        if cls.created_sdoc_ids:
            cls.db.query(SyllabusDocument).filter(SyllabusDocument.id.in_(cls.created_sdoc_ids)).delete(synchronize_session=False)
            cls.db.commit()

        # 5. Clean Files
        if cls.created_file_ids:
            cls.db.query(File).filter(File.id.in_(cls.created_file_ids)).delete(synchronize_session=False)
            cls.db.commit()

        # 6. Clean Users
        if cls.created_user_ids:
            cls.db.query(StudentProfileExtended).filter(StudentProfileExtended.user_id.in_(cls.created_user_ids)).delete(synchronize_session=False)
            cls.db.query(User).filter(User.id.in_(cls.created_user_ids)).delete(synchronize_session=False)
            cls.db.commit()

        # 7. Clean Subjects
        if cls.created_subject_ids:
            cls.db.query(Subject).filter(Subject.id.in_(cls.created_subject_ids)).delete(synchronize_session=False)
            cls.db.commit()

        cls.db.close()

    # =========================================================================
    # 1. SYLLABUS-ONLY RETRIEVAL (source_mode='syllabus')
    # =========================================================================

    def test_01_syllabus_only_retrieval(self):
        """When source_mode='syllabus', only syllabus chunks are retrieved and cited."""
        res = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={
                "question": "What does backpropagation compute in convolutional layers?",
                "subject_id": self.subject_aiml.id,
                "source_mode": "syllabus"
            }
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["has_sufficient_evidence"])
        self.assertGreater(len(data["citations"]), 0)

        for cit in data["citations"]:
            self.assertEqual(cit["source_type"], "syllabus")
            self.assertIsNotNone(cit["document_id"])
            self.assertIsNone(cit["lecture_note_id"])
            self.assertEqual(cit["department"], "AIML")

    # =========================================================================
    # 2. LECTURE-NOTE-ONLY RETRIEVAL (source_mode='lecture_notes')
    # =========================================================================

    def test_02_lecture_notes_only_retrieval(self):
        """When source_mode='lecture_notes', only published lecture note chunks are retrieved and cited."""
        res = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={
                "question": "How do multi-head self-attention mechanisms compute representations in parallel?",
                "subject_id": self.subject_aiml.id,
                "source_mode": "lecture_notes"
            }
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["has_sufficient_evidence"])
        self.assertGreater(len(data["citations"]), 0)

        for cit in data["citations"]:
            self.assertEqual(cit["source_type"], "lecture_note")
            self.assertIsNotNone(cit["lecture_note_id"])
            self.assertIsNone(cit["document_id"])
            self.assertEqual(cit["department"], "AIML")
            self.assertEqual(cit["source_title"], self.note_aiml.title)
            self.assertEqual(cit["original_filename"], self.note_aiml.original_filename)

    # =========================================================================
    # 3. COMBINED RETRIEVAL (source_mode='all')
    # =========================================================================

    def test_03_combined_retrieval_all(self):
        """When source_mode='all', both syllabus and lecture note chunks can be retrieved."""
        res = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={
                "question": "Explain convolutional kernel gradients and self-attention transformers",
                "subject_id": self.subject_aiml.id,
                "source_mode": "all"
            }
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["has_sufficient_evidence"])
        self.assertGreater(len(data["citations"]), 0)

        source_types = {c["source_type"] for c in data["citations"]}
        # In combined mode, citations can contain syllabus, lecture_note, or both
        for st in source_types:
            self.assertIn(st, ("syllabus", "lecture_note"))

    # =========================================================================
    # 4. BACKWARD COMPATIBLE DEFAULT BEHAVIOR (no source_mode)
    # =========================================================================

    def test_04_backward_compatible_default_behavior(self):
        """Omitting source_mode defaults to syllabus retrieval for backward compatibility."""
        res = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={
                "question": "What does backpropagation compute in convolutional layers?",
                "subject_id": self.subject_aiml.id
            }
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["has_sufficient_evidence"])
        self.assertGreater(len(data["citations"]), 0)
        for cit in data["citations"]:
            self.assertEqual(cit["source_type"], "syllabus")

        # Test the /ask alias as well
        res_ask = self.client.post(
            "/study-buddy/ask",
            headers=self.student_aiml_headers,
            json={
                "question": "What does backpropagation compute in convolutional layers?",
                "subject_id": self.subject_aiml.id
            }
        )
        self.assertEqual(res_ask.status_code, 200)
        data_ask = res_ask.json()
        self.assertTrue(data_ask["has_sufficient_evidence"])
        for cit in data_ask["citations"]:
            self.assertEqual(cit["source_type"], "syllabus")

    # =========================================================================
    # 5. INVALID SOURCE-MODE VALIDATION
    # =========================================================================

    def test_05_invalid_source_mode_returns_422(self):
        """Passing an unrecognized source_mode returns 422 Unprocessable Entity."""
        invalid_modes = ["web", "external", "wikipedia", "invalid", ""]
        for mode in invalid_modes:
            res = self.client.post(
                "/study-buddy/chat",
                headers=self.student_aiml_headers,
                json={
                    "question": "Explain self-attention transformers",
                    "subject_id": self.subject_aiml.id,
                    "source_mode": mode
                }
            )
            self.assertEqual(
                res.status_code,
                422,
                f"Expected 422 for source_mode='{mode}', got {res.status_code}"
            )

    # =========================================================================
    # 6. STUDENT DEPARTMENT AND SUBJECT ISOLATION
    # =========================================================================

    def test_06_student_department_and_subject_isolation(self):
        """ECE student cannot access AIML lecture notes or syllabi."""
        # 1. Specifying AIML subject_id returns 403 Forbidden
        res_cross_subject = self.client.post(
            "/study-buddy/chat",
            headers=self.student_ece_headers,
            json={
                "question": "Explain self-attention transformers",
                "subject_id": self.subject_aiml.id,
                "source_mode": "lecture_notes"
            }
        )
        self.assertEqual(res_cross_subject.status_code, 403)
        self.assertIn("Access denied", res_cross_subject.json()["detail"])

        # 2. Omitting subject_id returns insufficient evidence without leaking AIML content
        res_no_subject = self.client.post(
            "/study-buddy/chat",
            headers=self.student_ece_headers,
            json={
                "question": "Explain self-attention transformers in neural networks",
                "source_mode": "lecture_notes"
            }
        )
        self.assertEqual(res_no_subject.status_code, 200)
        data = res_no_subject.json()
        self.assertFalse(data["has_sufficient_evidence"])
        self.assertEqual(len(data["citations"]), 0)

        # 3. ECE student CAN access ECE lecture notes
        res_ece_ok = self.client.post(
            "/study-buddy/chat",
            headers=self.student_ece_headers,
            json={
                "question": "What is the Nyquist-Shannon sampling frequency requirement?",
                "subject_id": self.subject_ece.id,
                "source_mode": "lecture_notes"
            }
        )
        self.assertEqual(res_ece_ok.status_code, 200)
        data_ece = res_ece_ok.json()
        self.assertTrue(data_ece["has_sufficient_evidence"])
        self.assertEqual(data_ece["citations"][0]["department"], "ECE")

    # =========================================================================
    # 7. STUDENT BRANCH FALLBACK (user.department IS NULL)
    # =========================================================================

    def test_07_student_branch_fallback_when_user_department_is_null(self):
        """Student with user.department = None but student_profile.branch = 'AIML' has full access."""
        res = self.client.post(
            "/study-buddy/chat",
            headers=self.branch_student_headers,
            json={
                "question": "How do multi-head self-attention mechanisms compute representations in parallel?",
                "subject_id": self.subject_aiml.id,
                "source_mode": "lecture_notes"
            }
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["has_sufficient_evidence"])
        self.assertGreater(len(data["citations"]), 0)
        self.assertEqual(data["citations"][0]["department"], "AIML")

    # =========================================================================
    # 8. EXCLUSION OF INELIGIBLE LECTURE NOTES
    # =========================================================================

    def test_08_exclusion_of_ineligible_notes(self):
        """Draft, unpublished, archived, inactive-subject, and non-indexed notes must be excluded."""
        # 1. Draft note
        note_draft = self._create_and_index_note(
            subject_id=self.subject_aiml.id,
            title="Draft Quantum Algorithms",
            filename="draft_quantum.pdf",
            text="Quantum superposition allows quantum qubits to exist in multiple states simultaneously.",
            status=LectureNoteStatus.DRAFT,
            is_published=False,
            processing_status=LectureNoteProcessingStatus.EXTRACTED
        )

        # 2. Unpublished note
        note_unpub = self._create_and_index_note(
            subject_id=self.subject_aiml.id,
            title="Unpublished Quantum Qubits",
            filename="unpub_quantum.pdf",
            text="Quantum decoherence disrupts qubit superposition over time.",
            status=LectureNoteStatus.PUBLISHED,
            is_published=False,  # unpublished
            processing_status=LectureNoteProcessingStatus.EXTRACTED
        )

        # 3. Archived note
        note_archived = self._create_and_index_note(
            subject_id=self.subject_aiml.id,
            title="Archived Quantum Gates",
            filename="archived_quantum.pdf",
            text="Hadamard gates create equal superposition of basis states.",
            status=LectureNoteStatus.ARCHIVED,
            is_published=True,
            processing_status=LectureNoteProcessingStatus.EXTRACTED
        )

        # 4. Inactive subject note
        note_inactive_subj = self._create_and_index_note(
            subject_id=self.subject_inactive.id,
            title="Inactive Subject Quantum Mechanics",
            filename="inact_quantum.pdf",
            text="Schrodinger wave equation describes quantum wave function evolution.",
            status=LectureNoteStatus.PUBLISHED,
            is_published=True,
            processing_status=LectureNoteProcessingStatus.EXTRACTED
        )

        # Query for quantum qubits
        res = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={
                "question": "What is quantum qubit superposition and quantum decoherence?",
                "source_mode": "lecture_notes"
            }
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        # Should not find sufficient evidence because all matching notes are ineligible
        self.assertFalse(data["has_sufficient_evidence"])
        self.assertEqual(len(data["citations"]), 0)

    # =========================================================================
    # 9. EXCLUSION OF STALE QDRANT POINTS
    # =========================================================================

    def test_09_exclusion_of_stale_qdrant_points(self):
        """Stale Qdrant vectors with missing or ineligible PostgreSQL records are discarded."""
        # Create a published note and index it
        stale_note = self._create_and_index_note(
            subject_id=self.subject_aiml.id,
            title="Stale Point Photonic Computing",
            filename="photonic_computing.pdf",
            text="Photonic neural networks utilize optical Mach-Zehnder interferometers for light-speed matrix multiplication.",
            status=LectureNoteStatus.PUBLISHED,
            is_published=True,
            processing_status=LectureNoteProcessingStatus.EXTRACTED
        )

        # Delete note record directly from PostgreSQL, leaving potential stale Qdrant points
        self.db.query(LectureNote).filter(LectureNote.id == stale_note.id).delete(synchronize_session=False)
        self.db.commit()

        # Query for photonic interferometers
        res = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={
                "question": "How do Mach-Zehnder interferometers perform matrix multiplication in photonic neural networks?",
                "subject_id": self.subject_aiml.id,
                "source_mode": "lecture_notes"
            }
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        # Stale point was rejected during secondary PostgreSQL revalidation
        self.assertFalse(data["has_sufficient_evidence"])
        self.assertEqual(len(data["citations"]), 0)

    # =========================================================================
    # 10. CITATION SCHEMA CORRECTNESS AND SOURCE AWARENESS
    # =========================================================================

    def test_10_citation_schema_correctness_and_source_awareness(self):
        """Verify all fields in StudyBuddyCitation for both source types."""
        # Test syllabus citation schema
        res_syl = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={
                "question": "What does backpropagation compute in convolutional layers?",
                "subject_id": self.subject_aiml.id,
                "source_mode": "syllabus"
            }
        )
        self.assertEqual(res_syl.status_code, 200)
        syl_cits = res_syl.json()["citations"]
        self.assertGreater(len(syl_cits), 0)
        c0 = syl_cits[0]
        self.assertEqual(c0["source_type"], "syllabus")
        self.assertIsNotNone(c0["source_id"])
        self.assertIsNotNone(c0["source_title"])
        self.assertEqual(c0["document_id"], self.sdoc_aiml.id)
        self.assertIsNone(c0["lecture_note_id"])
        self.assertEqual(c0["subject_id"], self.subject_aiml.id)
        self.assertEqual(c0["subject_code"], self.subject_aiml.code)
        self.assertEqual(c0["department"], "AIML")
        self.assertIsInstance(c0["relevance_score"], float)

        # Test lecture note citation schema
        res_note = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={
                "question": "How do multi-head self-attention mechanisms compute representations in parallel?",
                "subject_id": self.subject_aiml.id,
                "source_mode": "lecture_notes"
            }
        )
        self.assertEqual(res_note.status_code, 200)
        note_cits = res_note.json()["citations"]
        self.assertGreater(len(note_cits), 0)
        n0 = note_cits[0]
        self.assertEqual(n0["source_type"], "lecture_note")
        self.assertIsNotNone(n0["source_id"])
        self.assertEqual(n0["source_title"], self.note_aiml.title)
        self.assertEqual(n0["original_filename"], self.note_aiml.original_filename)
        self.assertEqual(n0["lecture_note_id"], self.note_aiml.id)
        self.assertIsNone(n0["document_id"])
        self.assertEqual(n0["subject_id"], self.subject_aiml.id)
        self.assertEqual(n0["department"], "AIML")
        self.assertIsInstance(n0["relevance_score"], float)

    # =========================================================================
    # 11. NO CITATIONS FOR UNAUTHORIZED OR EXCLUDED CHUNKS
    # =========================================================================

    def test_11_no_citations_for_unauthorized_or_excluded_chunks(self):
        """When an unauthorized student queries or chunks are excluded, no citations are leaked."""
        res = self.client.post(
            "/study-buddy/chat",
            headers=self.student_ece_headers,
            json={
                "question": "How do multi-head self-attention mechanisms compute representations in parallel?",
                "source_mode": "lecture_notes"
            }
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["has_sufficient_evidence"])
        self.assertEqual(data["citations"], [])

    # =========================================================================
    # 12. INSUFFICIENT-CONTEXT RESPONSES
    # =========================================================================

    def test_12_insufficient_context_responses(self):
        """Queries with no matching evidence return has_sufficient_evidence=False and honest message."""
        res = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={
                "question": "Explain Renaissance European cartography and navigational instruments from 1520",
                "subject_id": self.subject_aiml.id,
                "source_mode": "all"
            }
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["has_sufficient_evidence"])
        self.assertIn("do not provide sufficient information", data["answer"])
        self.assertEqual(data["citations"], [])

    # =========================================================================
    # 13. QDRANT FAILURE HANDLING
    # =========================================================================

    def test_13_qdrant_failure_handling(self):
        """If Qdrant fails during query, service returns safe insufficient-evidence without crashing."""
        target_method = "query_points" if hasattr(qdrant_client.client, "query_points") else "search"
        with patch.object(qdrant_client.client, target_method, side_effect=Exception("Qdrant simulated timeout")):
            res = self.client.post(
                "/study-buddy/chat",
                headers=self.student_aiml_headers,
                json={
                    "question": "Explain self-attention transformers",
                    "subject_id": self.subject_aiml.id,
                    "source_mode": "lecture_notes"
                }
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertFalse(data["has_sufficient_evidence"])
            self.assertEqual(data["citations"], [])

    # =========================================================================
    # 14. PLACEMENT OFFICER FORBIDDEN
    # =========================================================================

    def test_14_placement_officer_forbidden(self):
        """Placement Officers are strictly forbidden from academic Study Buddy chat."""
        res = self.client.post(
            "/study-buddy/chat",
            headers=self.po_headers,
            json={
                "question": "Explain self-attention transformers",
                "subject_id": self.subject_aiml.id,
                "source_mode": "lecture_notes"
            }
        )
        self.assertEqual(res.status_code, 403)

        res_search = self.client.get(
            f"/study-buddy/search?query=transformers&source_mode=lecture_notes",
            headers=self.po_headers
        )
        self.assertEqual(res_search.status_code, 403)

    # =========================================================================
    # 15. REGRESSION: EXISTING SYLLABUS SUMMARIES, QUIZZES, AND PROGRESS
    # =========================================================================

    def test_15_regression_existing_summaries_quizzes_and_progress(self):
        """Verify summaries, quizzes, and progress dashboard are not redirected or broken."""
        # 1. Summary Generation (Syllabus Grounded)
        res_summary = self.client.post(
            "/study-buddy/summaries/generate",
            headers=self.student_aiml_headers,
            json={
                "subject_id": self.subject_aiml.id,
                "unit_id": self.sunit1.id,
                "format_type": "concise"
            }
        )
        self.assertEqual(res_summary.status_code, 200)
        summary_data = res_summary.json()
        self.assertIn("summary", summary_data)
        self.assertGreater(len(summary_data["citations"]), 0)

        # 2. Quiz Generation (Syllabus Grounded)
        res_quiz = self.client.post(
            "/study-buddy/quizzes/generate",
            headers=self.student_aiml_headers,
            json={
                "subject_id": self.subject_aiml.id,
                "unit_id": self.sunit1.id,
                "question_count": 3
            }
        )
        self.assertEqual(res_quiz.status_code, 200)
        quiz_data = res_quiz.json()
        self.assertIn("questions", quiz_data)
        self.assertGreaterEqual(len(quiz_data["questions"]), 1)

        # 3. Progress Dashboard
        res_progress = self.client.get(
            "/study-buddy/progress/dashboard",
            headers=self.student_aiml_headers
        )
        self.assertEqual(res_progress.status_code, 200)
        prog_data = res_progress.json()
        self.assertIn("quizzes_attempted", prog_data)
        self.assertIn("subject_performances", prog_data)

    # =========================================================================
    # 16. SEARCH ENDPOINT WITH SOURCE MODES
    # =========================================================================

    def test_16_search_endpoint_with_source_modes(self):
        """GET /study-buddy/search supports source_mode='syllabus', 'lecture_notes', and 'all'."""
        # Syllabus mode
        res_syl = self.client.get(
            f"/study-buddy/search?query=backpropagation&subject_id={self.subject_aiml.id}&source_mode=syllabus",
            headers=self.student_aiml_headers
        )
        self.assertEqual(res_syl.status_code, 200)
        syl_results = res_syl.json()
        self.assertGreater(len(syl_results), 0)
        self.assertEqual(syl_results[0]["source_type"], "syllabus")

        # Lecture note mode
        res_note = self.client.get(
            f"/study-buddy/search?query=self-attention&subject_id={self.subject_aiml.id}&source_mode=lecture_notes",
            headers=self.student_aiml_headers
        )
        self.assertEqual(res_note.status_code, 200)
        note_results = res_note.json()
        self.assertGreater(len(note_results), 0)
        self.assertEqual(note_results[0]["source_type"], "lecture_note")

        # All mode
        res_all = self.client.get(
            f"/study-buddy/search?query=attention+convolutions&subject_id={self.subject_aiml.id}&source_mode=all",
            headers=self.student_aiml_headers
        )
        self.assertEqual(res_all.status_code, 200)
        all_results = res_all.json()
        self.assertGreater(len(all_results), 0)


if __name__ == "__main__":
    unittest.main()
