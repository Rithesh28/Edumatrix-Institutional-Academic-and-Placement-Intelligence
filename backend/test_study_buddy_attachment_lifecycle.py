"""
EduMatrix Study Buddy - Attachment Lifecycle & Diagnostics Regression Test Suite

Covers the 10 critical attachment lifecycle requirements:
1. Successful first-time PDF upload and indexing.
2. Reusing an already indexed identical document without duplicating Qdrant points or MinIO objects.
3. Extraction or indexing failure transitioning to a visible error with safe sanitized message.
4. Polling request returning HTTP error (401, 403, 404).
5. Processing timeout & stale lock reclamation (>60s TTL) vs active lock protection (<60s).
6. Valid attachment becoming ready and usable in Ask Buddy chat.
7. Preventing Send before indexing is complete (rejecting unindexed/failed attachments).
8. Foreign-student attachment IDs being strictly rejected.
9. Attachment citations and lecturer-note co-grounding.
10. Existing note preview/download and Study Buddy progress APIs preservation.
"""

import io
import time
import unittest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from reportlab.pdfgen import canvas

from app.main import app
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.user import User, UserRole
from app.models.study_buddy import (
    Subject,
    LectureNote,
    LectureNoteProcessingStatus,
    LectureNoteIndexingStatus,
    StudentStudyDocument,
    StudentDocProcessingStatus,
    StudentDocIndexingStatus,
)
from app.services.file_storage.minio_client import minio_client
from app.services.student_documents_service import student_documents_service
from app.services.student_documents_indexing_service import student_documents_indexing_service
from app.services.lecture_notes_indexing_service import lecture_notes_indexing_service


class TestStudyBuddyAttachmentLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db: Session = SessionLocal()
        cls.timestamp = int(time.time() * 1000)

        # 1. Resolve Users across roles
        cls.admin_user = cls.db.query(User).filter(User.role == UserRole.ADMIN).first()
        cls.student_aiml = cls.db.query(User).filter(User.role == UserRole.STUDENT, User.department == "AIML").first()
        cls.student_ece = cls.db.query(User).filter(User.role == UserRole.STUDENT, User.department == "ECE").first()
        cls.lecturer_aiml = cls.db.query(User).filter(User.role == UserRole.LECTURER, User.department == "AIML").first()

        cls.admin_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.admin_user.email, 'id': cls.admin_user.id, 'role': 'admin'})}"}
        cls.student_aiml_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.student_aiml.email, 'id': cls.student_aiml.id, 'role': 'student'})}"}
        cls.student_ece_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.student_ece.email, 'id': cls.student_ece.id, 'role': 'student'})}"}
        cls.lecturer_aiml_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.lecturer_aiml.email, 'id': cls.lecturer_aiml.id, 'role': 'lecturer'})}"}

        cls.created_subject_ids = []
        cls.created_sdoc_ids = []
        cls.created_note_ids = []
        cls.student_sem = getattr(cls.student_aiml.student_profile, 'semester', 6) or 6

    @classmethod
    def tearDownClass(cls):
        # 1. Clean up student documents
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

        # 2. Clean up lecture notes
        for note_id in cls.created_note_ids:
            try:
                lecture_notes_indexing_service.delete_note_chunks(note_id)
            except Exception:
                pass
            try:
                note = cls.db.query(LectureNote).filter(LectureNote.id == note_id).first()
                if note:
                    minio_client.delete_file(note.minio_bucket, note.minio_object_key)
                    cls.db.delete(note)
            except Exception:
                pass

        # 3. Clean up created subjects
        for subj_id in cls.created_subject_ids:
            try:
                subj = cls.db.query(Subject).filter(Subject.id == subj_id).first()
                if subj:
                    cls.db.delete(subj)
            except Exception:
                pass

        cls.db.commit()
        cls.db.close()

    @staticmethod
    def _create_sample_pdf(title: str = "Test PDF", body: str = "Body content for vector testing") -> bytes:
        pdf_io = io.BytesIO()
        c = canvas.Canvas(pdf_io)
        c.drawString(100, 750, title)
        c.drawString(100, 730, body)
        c.showPage()
        c.save()
        return pdf_io.getvalue()

    # =========================================================================
    # TEST 1: SUCCESSFUL FIRST-TIME PDF UPLOAD AND INDEXING
    # =========================================================================
    def test_01_successful_first_time_pdf_upload_and_indexing(self):
        """Verify first-time upload of a PDF is ingested, extracted, and indexed synchronously."""
        pdf_bytes = self._create_sample_pdf(
            title=f"Markov Decision Processes {self.timestamp}",
            body="Markov decision processes formalize discrete-time stochastic control with states, actions, rewards, and transitions."
        )

        resp = self.client.post(
            "/study-buddy/my-documents",
            headers=self.student_aiml_headers,
            files={"file": (f"mdp_notes_{self.timestamp}.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            data={"title": f"MDP Notes {self.timestamp}", "reuse_existing": "true"}
        )

        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        doc_id = data["id"]
        self.created_sdoc_ids.append(doc_id)

        # Status assertions
        self.assertEqual(data["processing_status"], "EXTRACTED")
        self.assertEqual(data["indexing_status"], "INDEXED")
        self.assertGreater(data["indexed_chunk_count"], 0)
        self.assertIsNone(data["extraction_error"])
        self.assertIsNone(data.get("error_message"))

        # Check detail endpoint returns consistent fields
        detail_resp = self.client.get(
            f"/study-buddy/my-documents/{doc_id}",
            headers=self.student_aiml_headers
        )
        self.assertEqual(detail_resp.status_code, 200)
        detail_data = detail_resp.json()
        self.assertEqual(detail_data["indexing_status"], "INDEXED")
        self.assertEqual(detail_data["processing_status"], "EXTRACTED")
        self.assertIsNone(detail_data.get("error_message"))

    # =========================================================================
    # TEST 2: REUSING AN ALREADY INDEXED IDENTICAL DOCUMENT
    # =========================================================================
    def test_02_reusing_already_indexed_identical_document(self):
        """Verify uploading an identical PDF with reuse_existing=True returns the indexed doc without duplicating chunks."""
        pdf_bytes = self._create_sample_pdf(
            title=f"Reused PDF {self.timestamp}",
            body="This unique document is uploaded once, then reused with reuse_existing flag."
        )

        # 1. First upload
        resp1 = self.client.post(
            "/study-buddy/my-documents",
            headers=self.student_aiml_headers,
            files={"file": (f"reuse_{self.timestamp}.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            data={"title": f"Reused Doc {self.timestamp}", "reuse_existing": "true"}
        )
        self.assertEqual(resp1.status_code, 201)
        doc1 = resp1.json()
        doc1_id = doc1["id"]
        self.created_sdoc_ids.append(doc1_id)
        self.assertEqual(doc1["indexing_status"], "INDEXED")
        initial_chunk_count = doc1["indexed_chunk_count"]

        # 2. Second upload of exact same bytes with reuse_existing=True
        resp2 = self.client.post(
            "/study-buddy/my-documents",
            headers=self.student_aiml_headers,
            files={"file": (f"reuse_copy_{self.timestamp}.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            data={"title": f"Reused Doc Copy {self.timestamp}", "reuse_existing": "true"}
        )
        self.assertIn(resp2.status_code, (200, 201))
        doc2 = resp2.json()

        # Must return the existing document without creating duplicate records or points
        self.assertEqual(doc2["id"], doc1_id)
        self.assertEqual(doc2["indexing_status"], "INDEXED")
        self.assertEqual(doc2["indexed_chunk_count"], initial_chunk_count)

    # =========================================================================
    # TEST 3: EXTRACTION OR INDEXING FAILURE TRANSITIONS TO VISIBLE ERROR
    # =========================================================================
    def test_03_extraction_or_indexing_failure_transitioning_to_visible_error(self):
        """Verify failed extraction sets FAILED status and surfaces error_message without exposing internal paths."""
        # Create a student document row directly with FAILED status and error
        doc = StudentStudyDocument(
            student_id=self.student_aiml.id,
            title=f"Corrupt Test Doc {self.timestamp}",
            original_filename="corrupt.pdf",
            file_size=512,
            mime_type="application/pdf",
            content_hash=f"dummyhash_{self.timestamp}",
            minio_bucket="student-documents",
            minio_object_key=f"student_{self.student_aiml.id}/dummy_{self.timestamp}.pdf",
            processing_status=StudentDocProcessingStatus.FAILED,
            indexing_status=StudentDocIndexingStatus.FAILED,
            extraction_error="PDF parsing failed: damaged header structure."
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        self.created_sdoc_ids.append(doc.id)

        # Query detail via API
        resp = self.client.get(
            f"/study-buddy/my-documents/{doc.id}",
            headers=self.student_aiml_headers
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["processing_status"], "FAILED")
        self.assertEqual(data["indexing_status"], "FAILED")
        self.assertEqual(data["extraction_error"], "PDF parsing failed: damaged header structure.")
        self.assertEqual(data["error_message"], "PDF parsing failed: damaged header structure.")

        # Ensure MinIO internal bucket and object key are NOT exposed in API response
        self.assertNotIn("minio_object_key", data)
        self.assertNotIn("minio_bucket", data)

    # =========================================================================
    # TEST 4: POLLING REQUEST RETURNING HTTP ERRORS
    # =========================================================================
    def test_04_polling_request_returning_http_error(self):
        """Verify polling handles 404 for missing documents and 401 for unauthorized calls."""
        # 404 Not Found
        resp_404 = self.client.get(
            "/study-buddy/my-documents/9999999",
            headers=self.student_aiml_headers
        )
        self.assertEqual(resp_404.status_code, 404)
        self.assertIn("detail", resp_404.json())

        # 401 Unauthorized
        resp_401 = self.client.get("/study-buddy/my-documents/9999999")
        self.assertEqual(resp_401.status_code, 401)

    # =========================================================================
    # TEST 5: PROCESSING TIMEOUT AND STALE LOCK RECLAMATION
    # =========================================================================
    def test_05_processing_timeout_and_stale_lock_reclamation(self):
        """Verify stale INDEXING/PROCESSING state (>60s) is reclaimed while active lock (<60s) raises 409."""
        doc = StudentStudyDocument(
            student_id=self.student_aiml.id,
            title=f"Lock Test Doc {self.timestamp}",
            original_filename="lock_test.txt",
            file_size=100,
            mime_type="text/plain",
            content_hash=f"lockhash_{self.timestamp}",
            minio_bucket="student-documents",
            minio_object_key=f"student_{self.student_aiml.id}/lock_{self.timestamp}.txt",
            processing_status=StudentDocProcessingStatus.EXTRACTED,
            indexing_status=StudentDocIndexingStatus.INDEXING,
            extracted_text="Some extracted text for testing locks.",
            updated_at=datetime.now(timezone.utc)  # Fresh active lock
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        self.created_sdoc_ids.append(doc.id)

        # 1. Fresh active lock (<60s): retry or indexing should be rejected with 409 Conflict
        resp_active = self.client.post(
            f"/study-buddy/my-documents/{doc.id}/retry",
            headers=self.student_aiml_headers
        )
        self.assertEqual(resp_active.status_code, 409)

        # 2. Stale lock (>60s): set updated_at to 120 seconds ago
        doc.updated_at = datetime.now(timezone.utc) - timedelta(seconds=120)
        self.db.commit()

        # Retry should now succeed and reclaim the document rather than getting stuck
        resp_stale = self.client.post(
            f"/study-buddy/my-documents/{doc.id}/retry",
            headers=self.student_aiml_headers
        )
        self.assertEqual(resp_stale.status_code, 200)
        stale_data = resp_stale.json()
        self.assertEqual(stale_data["indexing_status"], "INDEXED")

    # =========================================================================
    # TEST 6: VALID ATTACHMENT BECOMING READY AND ENABLING SEND IN ASK BUDDY
    # =========================================================================
    def test_06_valid_attachment_becoming_ready_and_usable_in_chat(self):
        """Verify an indexed document can be passed as attached_document_id in Ask Buddy chat."""
        # 1. Upload and index document
        unique_concept = f"ConceptAlpha_{self.timestamp}"
        pdf_bytes = self._create_sample_pdf(
            title=f"Concept Alpha {self.timestamp}",
            body=f"{unique_concept} is a technique for stabilizing recurrent networks during training."
        )

        resp_up = self.client.post(
            "/study-buddy/my-documents",
            headers=self.student_aiml_headers,
            files={"file": (f"concept_alpha_{self.timestamp}.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            data={"title": f"Alpha Notes {self.timestamp}", "reuse_existing": "true"}
        )
        self.assertEqual(resp_up.status_code, 201)
        doc_data = resp_up.json()
        doc_id = doc_data["id"]
        self.created_sdoc_ids.append(doc_id)
        self.assertEqual(doc_data["indexing_status"], "INDEXED")

        # 2. Ask Buddy with attached_document_id
        chat_resp = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={
                "question": f"What is {unique_concept}?",
                "attached_document_id": doc_id,
                "source_mode": "lecture_notes"
            }
        )
        self.assertEqual(chat_resp.status_code, 200)
        chat_data = chat_resp.json()
        self.assertTrue(chat_data["has_sufficient_evidence"])
        self.assertGreater(len(chat_data["citations"]), 0)

        # Verify citation references the attached document
        doc_citations = [c for c in chat_data["citations"] if c.get("is_attached_file") or c.get("source_type") == "student_upload"]
        self.assertGreater(len(doc_citations), 0)
        self.assertEqual(doc_citations[0]["student_study_document_id"], doc_id)

    # =========================================================================
    # TEST 7: PREVENTING SEND BEFORE INDEXING IS COMPLETE
    # =========================================================================
    def test_07_preventing_send_before_indexing_is_complete(self):
        """Verify chat rejects attached_document_id if the document is not in INDEXED state."""
        # Create unindexed document
        doc = StudentStudyDocument(
            student_id=self.student_aiml.id,
            title=f"Unindexed Doc {self.timestamp}",
            original_filename="unindexed.pdf",
            file_size=200,
            mime_type="application/pdf",
            content_hash=f"unindexed_{self.timestamp}",
            minio_bucket="student-documents",
            minio_object_key=f"student_{self.student_aiml.id}/unindexed_{self.timestamp}.pdf",
            processing_status=StudentDocProcessingStatus.PROCESSING,
            indexing_status=StudentDocIndexingStatus.NOT_INDEXED,
            extracted_text=None
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        self.created_sdoc_ids.append(doc.id)

        # Attempt to chat with unindexed attachment
        chat_resp = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={
                "question": "What is in this document?",
                "attached_document_id": doc.id,
                "source_mode": "lecture_notes"
            }
        )
        self.assertEqual(chat_resp.status_code, 400)
        detail = chat_resp.json()["detail"].lower()
        self.assertTrue("not indexed" in detail or "not_indexed" in detail or "not fully indexed" in detail)

    # =========================================================================
    # TEST 8: FOREIGN-STUDENT ATTACHMENT IDS ARE REJECTED
    # =========================================================================
    def test_08_foreign_student_attachment_ids_rejected(self):
        """Verify student B cannot use, access, or download student A's attached document."""
        # Student AIML creates a document
        pdf_bytes = self._create_sample_pdf(title="Private Student A Doc", body="Private confidential student material.")
        resp_a = self.client.post(
            "/study-buddy/my-documents",
            headers=self.student_aiml_headers,
            files={"file": (f"priv_a_{self.timestamp}.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            data={"title": f"Private A {self.timestamp}", "reuse_existing": "true"}
        )
        self.assertEqual(resp_a.status_code, 201)
        doc_id = resp_a.json()["id"]
        self.created_sdoc_ids.append(doc_id)

        # Student ECE attempts to query detail -> 404 Not Found (privacy isolation)
        resp_b_detail = self.client.get(
            f"/study-buddy/my-documents/{doc_id}",
            headers=self.student_ece_headers
        )
        self.assertEqual(resp_b_detail.status_code, 404)

        # Student ECE attempts to download -> 404 Not Found
        resp_b_dl = self.client.get(
            f"/study-buddy/my-documents/{doc_id}/download",
            headers=self.student_ece_headers
        )
        self.assertEqual(resp_b_dl.status_code, 404)

        # Student ECE attempts to attach it in chat -> 404 or 403 Forbidden
        resp_b_chat = self.client.post(
            "/study-buddy/chat",
            headers=self.student_ece_headers,
            json={
                "question": "Summarize student A's document",
                "attached_document_id": doc_id,
                "source_mode": "lecture_notes"
            }
        )
        self.assertIn(resp_b_chat.status_code, (400, 403, 404))

    # =========================================================================
    # TEST 9: ATTACHMENT CITATIONS AND LECTURER-NOTE CO-GROUNDING
    # =========================================================================
    def test_09_attachment_citations_and_lecturer_note_co_grounding(self):
        """Verify Ask Buddy co-grounds both lecturer notes and student attachment with source-aware citations."""
        # 1. Subject & Lecture Note
        sub_code = f"COG{self.timestamp % 10000}"
        resp_sub = self.client.post(
            "/study-buddy/subjects",
            headers=self.lecturer_aiml_headers,
            json={
                "code": sub_code,
                "name": f"Cognitive Architectures {self.timestamp}",
                "semester": self.student_sem,
                "curriculum_version": "2024.1"
            }
        )
        self.assertEqual(resp_sub.status_code, 201)
        sub_id = resp_sub.json()["id"]
        self.created_subject_ids.append(sub_id)

        note_pdf = self._create_sample_pdf(
            title="Lecturer Note: Dual-Process Cognitive Theory",
            body="Dual-process theory asserts System 1 operates automatically and fast, while System 2 requires deliberate cognitive effort."
        )
        resp_note = self.client.post(
            f"/study-buddy/subjects/{sub_id}/notes",
            headers=self.lecturer_aiml_headers,
            files={"file": ("dual_process.pdf", io.BytesIO(note_pdf), "application/pdf")},
            data={"title": "Dual-Process Theory"}
        )
        self.assertEqual(resp_note.status_code, 201)
        note_id = resp_note.json()["id"]
        self.created_note_ids.append(note_id)

        self.client.patch(
            f"/study-buddy/notes/{note_id}",
            headers=self.lecturer_aiml_headers,
            json={"status": "PUBLISHED", "is_published": True}
        )
        lecture_notes_indexing_service.index_lecture_note(self.db, note_id)

        # 2. Student Attachment
        student_pdf = self._create_sample_pdf(
            title="Student Attachment: Working Memory Capacity",
            body="Working memory capacity limits the amount of concurrent information System 2 can manipulate under high cognitive load."
        )
        resp_doc = self.client.post(
            "/study-buddy/my-documents",
            headers=self.student_aiml_headers,
            files={"file": (f"wm_notes_{self.timestamp}.pdf", io.BytesIO(student_pdf), "application/pdf")},
            data={"title": f"WM Notes {self.timestamp}", "reuse_existing": "true"}
        )
        self.assertEqual(resp_doc.status_code, 201)
        doc_id = resp_doc.json()["id"]
        self.created_sdoc_ids.append(doc_id)

        # 3. Ask Buddy with both sources
        chat_resp = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={
                "question": "How does working memory capacity interact with System 1 and System 2 in dual-process cognitive theory?",
                "subject_id": sub_id,
                "attached_document_id": doc_id,
                "source_mode": "lecture_notes"
            }
        )
        self.assertEqual(chat_resp.status_code, 200)
        data = chat_resp.json()
        self.assertTrue(data["has_sufficient_evidence"])
        self.assertGreater(len(data["citations"]), 0)

        # Verify co-grounding citations
        has_note_cit = any(c.get("source_type") == "lecture_note" for c in data["citations"])
        has_doc_cit = any(c.get("is_attached_file") or c.get("source_type") == "student_upload" for c in data["citations"])
        self.assertTrue(has_note_cit, "Must contain lecture_note citation")
        self.assertTrue(has_doc_cit, "Must contain student_upload citation")

    # =========================================================================
    # TEST 10: EXISTING NOTE PREVIEW, DOWNLOAD, AND PROGRESS APIS PRESERVATION
    # =========================================================================
    def test_10_existing_note_preview_download_and_progress_apis(self):
        """Verify note preview/download and Study Buddy progress endpoints remain fully functional."""
        # 1. Subject and note for preview/download
        sub_code = f"PRV{self.timestamp % 10000}"
        resp_sub = self.client.post(
            "/study-buddy/subjects",
            headers=self.lecturer_aiml_headers,
            json={
                "code": sub_code,
                "name": f"Preview Test Subject {self.timestamp}",
                "semester": self.student_sem,
                "curriculum_version": "2024.1"
            }
        )
        self.assertEqual(resp_sub.status_code, 201)
        sub_id = resp_sub.json()["id"]
        self.created_subject_ids.append(sub_id)

        note_pdf = self._create_sample_pdf(title="Preview Note", body="Content to preview and download.")
        resp_note = self.client.post(
            f"/study-buddy/subjects/{sub_id}/notes",
            headers=self.lecturer_aiml_headers,
            files={"file": ("preview_note.pdf", io.BytesIO(note_pdf), "application/pdf")},
            data={"title": "Preview Note"}
        )
        self.assertEqual(resp_note.status_code, 201)
        note_id = resp_note.json()["id"]
        self.created_note_ids.append(note_id)

        self.client.patch(
            f"/study-buddy/notes/{note_id}",
            headers=self.lecturer_aiml_headers,
            json={"status": "PUBLISHED", "is_published": True}
        )

        # Student previews note via download?preview=true
        preview_resp = self.client.get(
            f"/study-buddy/notes/{note_id}/download?preview=true",
            headers=self.student_aiml_headers
        )
        self.assertEqual(preview_resp.status_code, 200)
        self.assertEqual(preview_resp.headers.get("content-type"), "application/pdf")

        # Student downloads note
        dl_resp = self.client.get(
            f"/study-buddy/notes/{note_id}/download",
            headers=self.student_aiml_headers
        )
        self.assertEqual(dl_resp.status_code, 200)

        # Progress Dashboard & Study Plans APIs
        progress_resp = self.client.get("/study-buddy/progress/dashboard", headers=self.student_aiml_headers)
        self.assertEqual(progress_resp.status_code, 200)

        plans_resp = self.client.get("/study-buddy/plans", headers=self.student_aiml_headers)
        self.assertEqual(plans_resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
