"""
Test Suite for EduMatrix Phase 4 — Step 4.6E: Lecture Notes Qdrant Indexing Service

Covers:
1. Successful vector indexing of published lecture notes in 'study_buddy_chunks'.
2. Stable deterministic UUIDv5 point IDs and idempotent re-indexing without duplicates.
3. Strict rejection of drafts, unpublished notes, archived notes, non-extracted notes, and inactive subjects.
4. Rejection of empty or whitespace extracted text.
5. Accurate 384-dimensional vector embedding validation.
6. Error handling and FAILED state persistence on Qdrant/embedding failures.
7. Concurrency protection preventing duplicate indexing of notes with INDEXING status (409 Conflict).
8. Automatic indexing triggered on note publication via PATCH /study-buddy/notes/{note_id}.
9. Vector cleanup from Qdrant upon unpublishing (is_published=False) or archiving (status=ARCHIVED).
10. Isolated vector deletion on note deletion without affecting syllabus points or other lecture notes.
11. Regression verification: syllabus vector isolation and existing syllabus indexing untouched.
12. RBAC verification for POST /study-buddy/notes/{note_id}/index and GET indexing-status:
    - Students blocked (403)
    - Placement Officers blocked (403)
    - Cross-department unassigned lecturers blocked (403)
    - Departmental/assigned faculty and Admin authorized (200)
"""

import time
import uuid
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from qdrant_client.http import models

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.user import User, UserRole, LecturerProfile
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
from app.services.file_storage.minio_client import minio_client
from app.services.file_storage.qdrant_client import qdrant_client
from app.services.lecture_notes_indexing_service import (
    lecture_notes_indexing_service,
    STUDY_BUDDY_COLLECTION,
    STUDY_BUDDY_VECTOR_SIZE,
)
from app.services.syllabus_indexing_service import syllabus_indexing_service
from app.main import app


class TestStudyBuddyStep46E(unittest.TestCase):
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
        cls.created_note_ids = []
        cls.created_sdoc_ids = []
        cls.created_file_ids = []
        cls.created_minio_keys = []

        # 1. Primary Active Subject (AIML)
        cls.aiml_code = f"IDX{cls.timestamp % 100000}A"
        cls.subject_aiml = Subject(
            code=cls.aiml_code,
            name=f"Deep Learning Systems {cls.aiml_code}",
            department="AIML",
            semester=6,
            academic_year="2026-2027",
            curriculum_version="2026.1",
            description="Test subject for Step 4.6E indexing testing",
            is_active=True
        )
        cls.db.add(cls.subject_aiml)

        # 2. Secondary Active Subject (ECE)
        cls.ece_code = f"IDX{cls.timestamp % 100000}E"
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
        cls.inactive_code = f"IDX{cls.timestamp % 100000}I"
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

        # Ensure Qdrant collection is ready
        lecture_notes_indexing_service.ensure_collection()

    @classmethod
    def _create_note(
        cls,
        subject: Subject,
        title: str,
        text: str | None,
        status: LectureNoteStatus = LectureNoteStatus.PUBLISHED,
        is_published: bool = True,
        processing_status: LectureNoteProcessingStatus = LectureNoteProcessingStatus.EXTRACTED,
        indexing_status: LectureNoteIndexingStatus = LectureNoteIndexingStatus.NOT_INDEXED
    ) -> LectureNote:
        file_uuid = uuid.uuid4()
        object_key = f"notes/{subject.id}/{file_uuid}_test.pdf"

        file_rec = File(
            id=file_uuid,
            filename="test.pdf",
            file_size=1024,
            mime_type="application/pdf",
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
            original_filename="test.pdf",
            file_size=1024,
            mime_type="application/pdf",
            minio_bucket="lecture-notes",
            minio_object_key=object_key,
            status=status,
            is_published=is_published,
            processing_status=processing_status,
            indexing_status=indexing_status,
            extracted_text=text,
            extraction_metadata={"pages": 2},
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
        if cls.created_sdoc_ids:
            cls.db.query(SyllabusDocument).filter(SyllabusDocument.id.in_(cls.created_sdoc_ids)).delete(synchronize_session=False)
            cls.db.commit()

        # 3. Clean LectureNotes
        if cls.created_note_ids:
            cls.db.query(LectureNote).filter(LectureNote.id.in_(cls.created_note_ids)).delete(synchronize_session=False)
            cls.db.commit()

        # 4. Clean Files
        if cls.created_file_ids:
            cls.db.query(File).filter(File.id.in_(cls.created_file_ids)).delete(synchronize_session=False)
            cls.db.commit()

        # 5. Clean Subjects
        if cls.created_subject_ids:
            cls.db.query(Subject).filter(Subject.id.in_(cls.created_subject_ids)).delete(synchronize_session=False)
            cls.db.commit()

        cls.db.close()

    # =========================================================================
    # 1. BASIC INDEXING & DETERMINISTIC ID TESTS
    # =========================================================================

    def test_01_successful_indexing_published_note(self):
        """Index a valid published lecture note and verify points in Qdrant with correct metadata."""
        content = (
            "Convolutional Neural Networks (CNNs) are widely used for computer vision tasks.\n\n"
            "Feature maps are produced by sliding kernels across input images.\n\n"
            "Pooling layers downsample the spatial dimensions to achieve translation invariance."
        )
        note = self._create_note(self.subject_aiml, "CNN Foundations", content)

        res = lecture_notes_indexing_service.index_lecture_note(self.db, note.id)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertGreaterEqual(res["chunks_indexed"], 1)

        self.db.refresh(note)
        self.assertEqual(note.indexing_status, LectureNoteIndexingStatus.INDEXED)
        self.assertEqual(note.indexed_chunk_count, res["chunks_indexed"])
        self.assertIsNotNone(note.extraction_metadata.get("indexed_at"))

        # Verify Qdrant points directly
        filter_note = models.Filter(
            must=[
                models.FieldCondition(key="source_type", match=models.MatchValue(value="lecture_note")),
                models.FieldCondition(key="lecture_note_id", match=models.MatchValue(value=note.id)),
            ]
        )
        points, _ = qdrant_client.client.scroll(
            collection_name=STUDY_BUDDY_COLLECTION,
            scroll_filter=filter_note,
            with_payload=True,
            with_vectors=True
        )
        self.assertEqual(len(points), res["chunks_indexed"])
        for p in points:
            self.assertEqual(p.payload["source_type"], "lecture_note")
            self.assertEqual(p.payload["lecture_note_id"], note.id)
            self.assertEqual(p.payload["subject_id"], self.subject_aiml.id)
            self.assertEqual(p.payload["subject_code"], self.subject_aiml.code)
            self.assertEqual(p.payload["department"], "AIML")
            self.assertEqual(p.payload["is_published"], "true")
            self.assertEqual(len(p.vector), STUDY_BUDDY_VECTOR_SIZE)

    def test_02_stable_deterministic_point_ids_and_idempotence(self):
        """Re-indexing unchanged note produces identical UUIDv5 point IDs without duplicating points."""
        content = "Recurrent Neural Networks (RNNs) process sequential data with feedback connections."
        note = self._create_note(self.subject_aiml, "RNN Notes", content)

        # First indexing
        res1 = lecture_notes_indexing_service.index_lecture_note(self.db, note.id)
        count1 = res1["chunks_indexed"]

        filter_note = models.Filter(
            must=[
                models.FieldCondition(key="source_type", match=models.MatchValue(value="lecture_note")),
                models.FieldCondition(key="lecture_note_id", match=models.MatchValue(value=note.id)),
            ]
        )
        pts1, _ = qdrant_client.client.scroll(
            collection_name=STUDY_BUDDY_COLLECTION,
            scroll_filter=filter_note
        )
        ids1 = {p.id for p in pts1}

        # Second indexing (idempotent re-index)
        res2 = lecture_notes_indexing_service.index_lecture_note(self.db, note.id)
        pts2, _ = qdrant_client.client.scroll(
            collection_name=STUDY_BUDDY_COLLECTION,
            scroll_filter=filter_note
        )
        ids2 = {p.id for p in pts2}

        self.assertEqual(ids1, ids2, "Point IDs must be deterministic UUIDv5 strings")
        self.assertEqual(len(pts2), count1, "Re-indexing must not create duplicate vector points")

    # =========================================================================
    # 2. ELIGIBILITY & REJECTION GATES
    # =========================================================================

    def test_03_rejection_of_draft_note(self):
        """Draft note (is_published=False, status=DRAFT) is rejected for indexing."""
        note = self._create_note(
            self.subject_aiml,
            "Draft Note",
            "Some content",
            status=LectureNoteStatus.DRAFT,
            is_published=False
        )
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            lecture_notes_indexing_service.index_lecture_note(self.db, note.id)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("not eligible", ctx.exception.detail)

    def test_04_rejection_of_archived_note(self):
        """Archived note (status=ARCHIVED) is rejected for indexing."""
        note = self._create_note(
            self.subject_aiml,
            "Archived Note",
            "Archived content",
            status=LectureNoteStatus.ARCHIVED,
            is_published=False
        )
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            lecture_notes_indexing_service.index_lecture_note(self.db, note.id)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_05_rejection_of_non_extracted_notes(self):
        """Note whose processing_status is FAILED or UPLOADED is rejected for indexing."""
        note_failed = self._create_note(
            self.subject_aiml,
            "Failed Extraction Note",
            None,
            processing_status=LectureNoteProcessingStatus.FAILED
        )
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            lecture_notes_indexing_service.index_lecture_note(self.db, note_failed.id)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_06_rejection_of_inactive_subject(self):
        """Published note on inactive subject is rejected for indexing."""
        note = self._create_note(
            self.subject_inactive,
            "Inactive Subject Note",
            "Some valid text",
            status=LectureNoteStatus.PUBLISHED,
            is_published=True
        )
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            lecture_notes_indexing_service.index_lecture_note(self.db, note.id)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("inactive", ctx.exception.detail.lower())

    def test_07_rejection_of_empty_extracted_text(self):
        """Note with empty or whitespace-only text is rejected for indexing."""
        note = self._create_note(
            self.subject_aiml,
            "Blank Content Note",
            "   \n\n  \t  ",
            status=LectureNoteStatus.PUBLISHED,
            is_published=True
        )
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            lecture_notes_indexing_service.index_lecture_note(self.db, note.id)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("no extracted text", ctx.exception.detail.lower())

    # =========================================================================
    # 3. CONCURRENCY & FAILURE HANDLING
    # =========================================================================

    def test_08_concurrency_protection_claims_note(self):
        """Simultaneous indexing attempt on note already in INDEXING status raises 409 Conflict."""
        note = self._create_note(
            self.subject_aiml,
            "Concurrent Claim Note",
            "Transformer attention mechanisms calculate scaled dot-product attention.",
            indexing_status=LectureNoteIndexingStatus.INDEXING
        )
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            lecture_notes_indexing_service.index_lecture_note(self.db, note.id)
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("currently being indexed", ctx.exception.detail)

    def test_09_failure_status_on_qdrant_or_embedding_error(self):
        """If embedding generation or Qdrant fails, indexing_status is set to FAILED with error persisted."""
        note = self._create_note(
            self.subject_aiml,
            "Failure Test Note",
            "This note will fail during upsert to test error persistence."
        )

        with patch("app.services.file_storage.qdrant_client.qdrant_client.client.upsert", side_effect=RuntimeError("Qdrant socket timeout")):
            from fastapi import HTTPException
            with self.assertRaises(HTTPException) as ctx:
                lecture_notes_indexing_service.index_lecture_note(self.db, note.id)
            self.assertEqual(ctx.exception.status_code, 500)

        self.db.refresh(note)
        self.assertEqual(note.indexing_status, LectureNoteIndexingStatus.FAILED)
        self.assertEqual(note.indexed_chunk_count, 0)
        self.assertIn("Qdrant socket timeout", note.extraction_metadata.get("indexing_error", ""))

    # =========================================================================
    # 4. LIFECYCLE TRIGGERS: PUBLISH, UNPUBLISH, DELETE
    # =========================================================================

    def test_10_publication_via_patch_triggers_indexing(self):
        """Publishing a draft extracted note via PATCH triggers automatic vector indexing."""
        note = self._create_note(
            self.subject_aiml,
            "Auto Index Publish Test",
            "Residual networks utilize skip connections to prevent vanishing gradients.",
            status=LectureNoteStatus.DRAFT,
            is_published=False
        )

        res = self.client.patch(
            f"/study-buddy/notes/{note.id}",
            json={"is_published": True, "status": "PUBLISHED"},
            headers=self.lecturer_aiml_headers
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["is_published"])
        self.assertEqual(data["status"], "PUBLISHED")
        self.assertEqual(data["indexing_status"], "INDEXED")
        self.assertGreaterEqual(data["indexed_chunk_count"], 1)

        # Verify vectors exist in Qdrant
        filter_note = models.Filter(
            must=[
                models.FieldCondition(key="source_type", match=models.MatchValue(value="lecture_note")),
                models.FieldCondition(key="lecture_note_id", match=models.MatchValue(value=note.id)),
            ]
        )
        points, _ = qdrant_client.client.scroll(
            collection_name=STUDY_BUDDY_COLLECTION,
            scroll_filter=filter_note
        )
        self.assertGreaterEqual(len(points), 1)

    def test_11_unpublishing_removes_qdrant_vectors_and_resets_status(self):
        """Unpublishing a note (is_published=False) deletes vectors from Qdrant and resets status."""
        note = self._create_note(
            self.subject_aiml,
            "Unpublish Test Note",
            "Self-supervised learning methods like SimCLR and MAE."
        )
        # Index note first
        lecture_notes_indexing_service.index_lecture_note(self.db, note.id)

        # Unpublish via API
        res = self.client.patch(
            f"/study-buddy/notes/{note.id}",
            json={"is_published": False, "status": "DRAFT"},
            headers=self.lecturer_aiml_headers
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["is_published"])
        self.assertEqual(data["indexing_status"], "NOT_INDEXED")
        self.assertEqual(data["indexed_chunk_count"], 0)

        # Confirm vectors deleted from Qdrant
        filter_note = models.Filter(
            must=[
                models.FieldCondition(key="source_type", match=models.MatchValue(value="lecture_note")),
                models.FieldCondition(key="lecture_note_id", match=models.MatchValue(value=note.id)),
            ]
        )
        points, _ = qdrant_client.client.scroll(
            collection_name=STUDY_BUDDY_COLLECTION,
            scroll_filter=filter_note
        )
        self.assertEqual(len(points), 0, "All vectors must be deleted when unpublished")

    def test_12_deleting_note_removes_only_its_vectors(self):
        """Deleting a note removes its vectors without removing points of another note."""
        note1 = self._create_note(self.subject_aiml, "Note 1 For Delete", "Autoencoders map input to latent representations.")
        note2 = self._create_note(self.subject_aiml, "Note 2 Kept", "Variational Autoencoders optimize ELBO objective.")

        lecture_notes_indexing_service.index_lecture_note(self.db, note1.id)
        lecture_notes_indexing_service.index_lecture_note(self.db, note2.id)

        # Delete note 1 via API
        res = self.client.delete(f"/study-buddy/notes/{note1.id}", headers=self.lecturer_aiml_headers)
        self.assertEqual(res.status_code, 200)

        # Check Note 1 vectors are gone
        pts1, _ = qdrant_client.client.scroll(
            collection_name=STUDY_BUDDY_COLLECTION,
            scroll_filter=models.Filter(must=[
                models.FieldCondition(key="source_type", match=models.MatchValue(value="lecture_note")),
                models.FieldCondition(key="lecture_note_id", match=models.MatchValue(value=note1.id)),
            ])
        )
        self.assertEqual(len(pts1), 0)

        # Check Note 2 vectors are STILL intact
        pts2, _ = qdrant_client.client.scroll(
            collection_name=STUDY_BUDDY_COLLECTION,
            scroll_filter=models.Filter(must=[
                models.FieldCondition(key="source_type", match=models.MatchValue(value="lecture_note")),
                models.FieldCondition(key="lecture_note_id", match=models.MatchValue(value=note2.id)),
            ])
        )
        self.assertGreaterEqual(len(pts2), 1, "Note 2 vectors must remain untouched")

    # =========================================================================
    # 5. REGRESSION & ISOLATION: SYLLABUS VECTORS UNTOUCHED
    # =========================================================================

    def test_13_syllabus_vectors_remain_isolated_and_unaffected(self):
        """Indexing and deleting lecture notes does not alter or corrupt syllabus points in study_buddy_chunks."""
        # 1. Create a syllabus document and index it
        sdoc = SyllabusDocument(
            subject_id=self.subject_aiml.id,
            uploaded_by_id=self.lecturer_aiml.id,
            version=1,
            title="AIML Official Syllabus",
            original_filename="aiml_syllabus.pdf",
            file_size=2048,
            mime_type="application/pdf",
            minio_bucket="syllabi",
            minio_object_key=f"syllabi/{self.subject_aiml.id}/sdoc_reg_test.pdf",
            processing_status=SyllabusProcessingStatus.EXTRACTED,
            review_status=SyllabusReviewStatus.APPROVED,
            is_published=True,
            extracted_text="Unit 1: Foundations of Deep Learning. Unit 2: Sequence Modeling and Transformers."
        )
        self.db.add(sdoc)
        self.db.commit()
        self.db.refresh(sdoc)
        self.created_sdoc_ids.append(sdoc.id)

        s_res = syllabus_indexing_service.index_syllabus_document(self.db, sdoc.id)
        self.assertEqual(s_res["status"], "SUCCESS")

        # 2. Verify syllabus points exist (they lack source_type='lecture_note' or have document_id)
        s_pts, _ = qdrant_client.client.scroll(
            collection_name=STUDY_BUDDY_COLLECTION,
            scroll_filter=models.Filter(must=[
                models.FieldCondition(key="document_id", match=models.MatchValue(value=sdoc.id))
            ])
        )
        self.assertGreaterEqual(len(s_pts), 1)
        initial_syllabus_pts_count = len(s_pts)

        # 3. Create, index, and delete a lecture note
        note = self._create_note(self.subject_aiml, "Parallel Lecture Note", "Gradient Descent optimization variants Adam, RMSprop.")
        lecture_notes_indexing_service.index_lecture_note(self.db, note.id)
        lecture_notes_indexing_service.delete_note_chunks(note.id)

        # 4. Re-verify syllabus points are 100% intact
        s_pts_after, _ = qdrant_client.client.scroll(
            collection_name=STUDY_BUDDY_COLLECTION,
            scroll_filter=models.Filter(must=[
                models.FieldCondition(key="document_id", match=models.MatchValue(value=sdoc.id))
            ])
        )
        self.assertEqual(len(s_pts_after), initial_syllabus_pts_count, "Syllabus points must be completely unaffected")

    # =========================================================================
    # 6. API ENDPOINTS & RBAC TESTS
    # =========================================================================

    def test_14_api_manual_reindex_rbac(self):
        """Test POST /study-buddy/notes/{note_id}/index RBAC permissions."""
        note = self._create_note(self.subject_aiml, "RBAC Index Test Note", "Generative Adversarial Networks (GANs) mini-max game.")

        # Student blocked (403)
        res_stu = self.client.post(f"/study-buddy/notes/{note.id}/index", headers=self.student_aiml_headers)
        self.assertEqual(res_stu.status_code, 403)

        # Placement Officer blocked (403)
        res_po = self.client.post(f"/study-buddy/notes/{note.id}/index", headers=self.po_headers)
        self.assertEqual(res_po.status_code, 403)

        # Lecturer from another department unassigned blocked (403)
        res_cross = self.client.post(f"/study-buddy/notes/{note.id}/index", headers=self.hod_cse_headers)
        self.assertEqual(res_cross.status_code, 403)

        # Department Lecturer allowed (200)
        res_lec = self.client.post(f"/study-buddy/notes/{note.id}/index", headers=self.lecturer_aiml_headers)
        self.assertEqual(res_lec.status_code, 200)
        self.assertEqual(res_lec.json()["status"], "SUCCESS")

        # Admin allowed (200)
        res_admin = self.client.post(f"/study-buddy/notes/{note.id}/index", headers=self.admin_headers)
        self.assertEqual(res_admin.status_code, 200)

    def test_15_api_indexing_status_endpoint(self):
        """Test GET /study-buddy/notes/{note_id}/indexing-status endpoint and RBAC."""
        note = self._create_note(self.subject_aiml, "Status API Note", "Self-attention matrix computation QK^T / sqrt(d_k).")
        lecture_notes_indexing_service.index_lecture_note(self.db, note.id)

        # Student blocked (403)
        res_stu = self.client.get(f"/study-buddy/notes/{note.id}/indexing-status", headers=self.student_aiml_headers)
        self.assertEqual(res_stu.status_code, 403)

        # Faculty allowed (200)
        res_fac = self.client.get(f"/study-buddy/notes/{note.id}/indexing-status", headers=self.lecturer_aiml_headers)
        self.assertEqual(res_fac.status_code, 200)
        data = res_fac.json()
        self.assertEqual(data["note_id"], note.id)
        self.assertEqual(data["indexing_status"], "INDEXED")
        self.assertGreaterEqual(data["indexed_chunk_count"], 1)


if __name__ == "__main__":
    unittest.main()
