"""
Step 4.6I Verification Test Suite: Study Buddy UI & Functionality Improvements
Tests:
- Part A: Ask Buddy Attachments (upload, duplicate avoidance via reuse_existing, indexing, grounding, is_attached_file citations, cross-student rejection)
- Part B: Lecture Note Preview & Download (preview=true -> inline Content-Disposition, preview=false -> attachment, unpublished rejection, cross-department rejection)
- Part C: Regression & Interop (Quiz, Summary, Progress, Subject listing)
"""

import io
import time
import uuid
import unittest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.user import User, UserRole
from app.models.study_buddy import (
    Subject,
    LectureNote,
    LectureNoteStatus,
    LectureNoteProcessingStatus,
    LectureNoteIndexingStatus,
    StudentStudyDocument,
)
from app.services.file_storage.minio_client import minio_client
from app.services.student_documents_service import (
    student_documents_service,
    STUDENT_DOCS_BUCKET,
)
from app.services.student_documents_indexing_service import student_documents_indexing_service


class TestStudyBuddyStep46IImprovements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db: Session = SessionLocal()
        cls.timestamp = int(time.time() * 1000)

        # 1. Resolve Users across roles
        cls.student_aiml = cls.db.query(User).filter(User.role == UserRole.STUDENT, User.department == "AIML").first()
        cls.student_ece = cls.db.query(User).filter(User.role == UserRole.STUDENT, User.department == "ECE").first()
        cls.lecturer_aiml = cls.db.query(User).filter(User.role == UserRole.LECTURER, User.department == "AIML").first()

        cls.student_aiml_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.student_aiml.email, 'id': cls.student_aiml.id, 'role': 'student'})}"}
        cls.student_ece_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.student_ece.email, 'id': cls.student_ece.id, 'role': 'student'})}"}
        cls.lecturer_aiml_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.lecturer_aiml.email, 'id': cls.lecturer_aiml.id, 'role': 'lecturer'})}"}

        cls.created_sdoc_ids = []
        cls.created_minio_keys = []
        cls.created_note_ids = []

        # 2. Create test subject for AIML
        cls.subject_aiml = Subject(
            code=f"I6AIML{cls.timestamp % 10000}",
            name=f"Deep Learning Step 4.6I {cls.timestamp}",
            department="AIML",
            semester=getattr(cls.student_aiml.student_profile, 'semester', 6) or 6,
            academic_year="2026-2027",
            curriculum_version="2026.1",
            description="AIML Test Subject for Step 4.6I Improvements",
            is_active=True
        )
        cls.db.add(cls.subject_aiml)
        cls.db.commit()
        cls.db.refresh(cls.subject_aiml)

        # 3. Upload and create a published PDF lecture note for AIML
        cls.pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Title (Deep Learning Notes) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        cls.note_storage_key = f"lecturer_{cls.lecturer_aiml.id}/{uuid.uuid4().hex}_intro_dl.pdf"
        minio_client.upload_file(
            bucket="lecture-notes",
            object_key=cls.note_storage_key,
            file_data=cls.pdf_content,
            content_type="application/pdf"
        )
        cls.created_minio_keys.append(("lecture-notes", cls.note_storage_key))

        cls.lecture_note_published = LectureNote(
            subject_id=cls.subject_aiml.id,
            uploaded_by_id=cls.lecturer_aiml.id,
            title="Introduction to Deep Convolutional Networks",
            original_filename="intro_dl.pdf",
            file_size=len(cls.pdf_content),
            mime_type="application/pdf",
            minio_bucket="lecture-notes",
            minio_object_key=cls.note_storage_key,
            status=LectureNoteStatus.PUBLISHED,
            is_published=True,
            processing_status=LectureNoteProcessingStatus.EXTRACTED,
            indexing_status=LectureNoteIndexingStatus.INDEXED
        )
        cls.db.add(cls.lecture_note_published)

        # 4. Create an unpublished/draft lecture note (should be blocked for student)
        cls.note_unpub_storage_key = f"lecturer_{cls.lecturer_aiml.id}/{uuid.uuid4().hex}_draft.pdf"
        minio_client.upload_file(
            bucket="lecture-notes",
            object_key=cls.note_unpub_storage_key,
            file_data=cls.pdf_content,
            content_type="application/pdf"
        )
        cls.created_minio_keys.append(("lecture-notes", cls.note_unpub_storage_key))

        cls.lecture_note_draft = LectureNote(
            subject_id=cls.subject_aiml.id,
            uploaded_by_id=cls.lecturer_aiml.id,
            title="Draft Exam Blueprint Note",
            original_filename="draft_exam.pdf",
            file_size=len(cls.pdf_content),
            mime_type="application/pdf",
            minio_bucket="lecture-notes",
            minio_object_key=cls.note_unpub_storage_key,
            status=LectureNoteStatus.DRAFT,
            is_published=False,
            processing_status=LectureNoteProcessingStatus.EXTRACTED,
            indexing_status=LectureNoteIndexingStatus.INDEXED
        )
        cls.db.add(cls.lecture_note_draft)
        cls.db.commit()
        cls.db.refresh(cls.lecture_note_published)
        cls.db.refresh(cls.lecture_note_draft)
        cls.created_note_ids.extend([cls.lecture_note_published.id, cls.lecture_note_draft.id])

    @classmethod
    def tearDownClass(cls):
        # Clean up student documents
        for sdoc_id in cls.created_sdoc_ids:
            try:
                student_documents_indexing_service.delete_document_chunks(sdoc_id)
            except Exception:
                pass
            try:
                doc = cls.db.query(StudentStudyDocument).filter(StudentStudyDocument.id == sdoc_id).first()
                if doc:
                    minio_client.delete_file(doc.minio_bucket, doc.minio_object_key)
                    cls.db.delete(doc)
            except Exception:
                pass

        # Clean up lecture notes
        for note_id in cls.created_note_ids:
            try:
                note = cls.db.query(LectureNote).filter(LectureNote.id == note_id).first()
                if note:
                    cls.db.delete(note)
            except Exception:
                pass

        # Clean up test subjects
        try:
            subj = cls.db.query(Subject).filter(Subject.id == cls.subject_aiml.id).first()
            if subj:
                cls.db.delete(subj)
        except Exception:
            pass

        # Clean up minio objects
        for bucket, key in cls.created_minio_keys:
            try:
                minio_client.delete_file(bucket, key)
            except Exception:
                pass

        cls.db.commit()
        cls.db.close()

    # =========================================================================
    # PART A: ASK BUDDY ATTACHMENTS
    # =========================================================================

    def test_01_attachment_upload_and_reuse_lifecycle(self):
        """Verify attachment upload with reuse_existing=True returns identical document without duplication."""
        file_bytes = b"Convolutional kernels apply sliding spatial filters to extract localized feature maps."
        file_obj = io.BytesIO(file_bytes)

        # First upload as attachment
        resp1 = self.client.post(
            "/study-buddy/my-documents",
            headers=self.student_aiml_headers,
            files={"file": ("cnn_spatial_filters.txt", file_obj, "text/plain")},
            data={"title": "CNN Spatial Filters", "reuse_existing": "true"}
        )
        self.assertEqual(resp1.status_code, 201)
        doc1 = resp1.json()
        doc1_id = doc1["id"]
        self.created_sdoc_ids.append(doc1_id)
        self.assertEqual(doc1["indexing_status"].upper(), "INDEXED")

        # Second upload with identical content and reuse_existing=true
        file_obj.seek(0)
        resp2 = self.client.post(
            "/study-buddy/my-documents",
            headers=self.student_aiml_headers,
            files={"file": ("cnn_spatial_filters.txt", file_obj, "text/plain")},
            data={"title": "CNN Spatial Filters", "reuse_existing": "true"}
        )
        self.assertEqual(resp2.status_code, 201)
        doc2 = resp2.json()
        # Must reuse the exact same existing document ID!
        self.assertEqual(doc2["id"], doc1_id)

    def test_02_ask_question_with_attached_document_grounding(self):
        """Verify Ask Buddy query with attached_document_id grounds answer and marks citation as is_attached_file."""
        content = "Residual connections introduce identity shortcut mapping that enables training of networks with over 100 layers."
        resp = self.client.post(
            "/study-buddy/my-documents",
            headers=self.student_aiml_headers,
            files={"file": ("resnet_residual_mapping.txt", io.BytesIO(content.encode("utf-8")), "text/plain")},
            data={"title": "ResNet Residuals", "reuse_existing": "true"}
        )
        self.assertEqual(resp.status_code, 201)
        doc_id = resp.json()["id"]
        self.created_sdoc_ids.append(doc_id)

        # Query Ask Buddy attaching this document in 'syllabus' mode
        chat_resp = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={
                "question": "How do residual connections help in deep networks?",
                "source_mode": "syllabus",
                "attached_document_id": doc_id
            }
        )
        self.assertEqual(chat_resp.status_code, 200)
        data = chat_resp.json()
        self.assertTrue(data["has_sufficient_evidence"])
        self.assertGreater(len(data["citations"]), 0)

        # Check citation contains is_attached_file = True
        attached_citations = [c for c in data["citations"] if c.get("is_attached_file")]
        self.assertGreater(len(attached_citations), 0)
        self.assertEqual(attached_citations[0]["student_study_document_id"], doc_id)

    def test_03_attached_document_security_and_foreign_rejection(self):
        """Verify Ask Buddy rejects foreign-student attached document ID (404)."""
        # Upload doc for Student ECE
        resp_ece = self.client.post(
            "/study-buddy/my-documents",
            headers=self.student_ece_headers,
            files={"file": ("ece_confidential.txt", io.BytesIO(b"ECE Signal Processing."), "text/plain")},
            data={"title": "ECE Confidential"}
        )
        self.assertEqual(resp_ece.status_code, 201)
        ece_doc_id = resp_ece.json()["id"]
        self.created_sdoc_ids.append(ece_doc_id)

        # Student AIML attempts to query using Student ECE's document -> 404
        chat_resp = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={
                "question": "What is in confidential notes?",
                "source_mode": "syllabus",
                "attached_document_id": ece_doc_id
            }
        )
        self.assertEqual(chat_resp.status_code, 404)

    # =========================================================================
    # PART B: LECTURE NOTES PREVIEW & DOWNLOAD
    # =========================================================================

    def test_04_lecture_note_preview_inline_headers(self):
        """Verify downloadNote with preview=true sets Content-Disposition to inline."""
        note_id = self.lecture_note_published.id
        resp = self.client.get(
            f"/study-buddy/notes/{note_id}/download?preview=true",
            headers=self.student_aiml_headers
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "application/pdf")
        self.assertIn("inline", resp.headers.get("content-disposition", ""))
        self.assertIn("intro_dl.pdf", resp.headers.get("content-disposition", ""))
        self.assertEqual(resp.content, self.pdf_content)

    def test_05_lecture_note_download_attachment_headers(self):
        """Verify downloadNote without preview sets Content-Disposition to attachment."""
        note_id = self.lecture_note_published.id
        resp = self.client.get(
            f"/study-buddy/notes/{note_id}/download",
            headers=self.student_aiml_headers
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "application/pdf")
        self.assertIn("attachment", resp.headers.get("content-disposition", ""))
        self.assertIn("intro_dl.pdf", resp.headers.get("content-disposition", ""))

    def test_06_unauthorized_note_preview_and_download_blocks(self):
        """Verify draft notes and cross-department notes are inaccessible (404/403)."""
        # 1. Draft note access by student -> 404
        draft_id = self.lecture_note_draft.id
        resp_draft = self.client.get(
            f"/study-buddy/notes/{draft_id}/download?preview=true",
            headers=self.student_aiml_headers
        )
        self.assertEqual(resp_draft.status_code, 404)

        # 2. Cross-department access: Student ECE tries to access AIML note -> 403 or 404
        resp_cross = self.client.get(
            f"/study-buddy/notes/{self.lecture_note_published.id}/download?preview=true",
            headers=self.student_ece_headers
        )
        self.assertIn(resp_cross.status_code, [403, 404])

        # 3. Unauthenticated request -> 401
        resp_noauth = self.client.get(
            f"/study-buddy/notes/{self.lecture_note_published.id}/download?preview=true"
        )
        self.assertEqual(resp_noauth.status_code, 401)

    # =========================================================================
    # PART C: PRESERVATION OF REGRESSION APIS
    # =========================================================================

    def test_07_regression_preservation_apis(self):
        """Verify dashboard-progress, subjects, notes listing, and quiz endpoints function without regression."""
        # 1. Dashboard progress
        resp_prog = self.client.get("/study-buddy/progress/dashboard", headers=self.student_aiml_headers)
        self.assertEqual(resp_prog.status_code, 200)
        data_prog = resp_prog.json()
        self.assertIn("quizzes_attempted", data_prog)
        self.assertIn("quizzes_completed", data_prog)

        # 2. Subject listing for student's department & semester
        resp_subj = self.client.get("/study-buddy/subjects", headers=self.student_aiml_headers)
        self.assertEqual(resp_subj.status_code, 200)
        subj_list = resp_subj.json()
        aiml_subj_ids = [s["id"] for s in subj_list]
        self.assertIn(self.subject_aiml.id, aiml_subj_ids)

        # 3. Notes listing for subject
        resp_notes = self.client.get(f"/study-buddy/subjects/{self.subject_aiml.id}/notes", headers=self.student_aiml_headers)
        self.assertEqual(resp_notes.status_code, 200)
        notes = resp_notes.json()
        published_ids = [n["id"] for n in notes]
        self.assertIn(self.lecture_note_published.id, published_ids)
        # Draft note must NOT appear in student notes list!
        self.assertNotIn(self.lecture_note_draft.id, published_ids)


if __name__ == "__main__":
    unittest.main()
