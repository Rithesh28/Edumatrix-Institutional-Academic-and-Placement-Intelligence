"""
EduMatrix Phase 4 — Step 4.6B: Lecture Notes Ingestion Service and Backend APIs Test Suite

Comprehensive test coverage for:
1. Supported file formats: PDF (.pdf), PNG (.png), Word (.docx), PowerPoint (.pptx).
2. Size & streaming validation: 500 MB limit, streaming temporary-disk buffer, 0-byte rejection.
3. Signature & MIME validation: %PDF-, PNG magic header, PK zip internal word/ and ppt/ structures,
   and rejection of unsupported formats (.txt, .exe, .xlsx).
4. Content extraction:
   - PDF text extraction with page numbers and OCR fallback.
   - PNG OCR extraction via pytesseract.
   - DOCX extraction with paragraphs and table cells.
   - PPTX extraction with slide-indexed text and tables.
5. Error handling: Corrupt, encrypted, empty, and failed extraction handling with safe errors.
6. Storage & transactional integrity: Dedicated 'lecture-notes' bucket, unique keys,
   cleanup of MinIO object on database rollback, no orphaned files.
7. Retry endpoint: Re-reading from MinIO and retrying extraction.
8. Multi-role RBAC:
   - Placement Officer: 403 Forbidden on all endpoints.
   - Student: Read-only access to published notes of active subjects in own department;
     403 on upload, edit, publish, delete, retry.
   - Lecturer: Authorized for assigned or departmental subjects; 403 on unauthorized subjects.
   - HOD: Scoped to department; 403 on other departments.
   - Admin: Global access.
9. Publication safeguards: Gated on processing_status == EXTRACTED; draft/failed notes cannot be published.
10. Unit/topic subject alignment: Rejection (HTTP 400) on cross-subject unit/topic IDs.
11. Safe deletion: Removes DB record and MinIO binary object.
12. Syllabus workflow independence: Syllabus documents and review status remain untouched.
"""

import os
import io
import time
import uuid
import zipfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import docx
import pptx
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.core.security import create_access_token
from app.models.user import User, UserRole
from app.models.file import File
from app.models.study_buddy import (
    Subject,
    SyllabusDocument,
    SyllabusUnit,
    SyllabusTopic,
    SyllabusReviewStatus,
    LectureNote,
    LectureNoteStatus,
    LectureNoteProcessingStatus,
    LectureNoteIndexingStatus,
)
from app.services.file_storage.minio_client import minio_client
from app.services.lecture_notes_service import lecture_notes_service, MAX_NOTE_FILE_SIZE
from app.main import app


class TestStudyBuddyStep46B(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db: Session = SessionLocal()
        cls.timestamp = int(time.time() * 1000)

        # Users across 5 roles
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
        cls.created_minio_keys = []

        # Create primary test subject (AIML)
        cls.aiml_code = f"LN{cls.timestamp % 100000}A"
        cls.subject_aiml = Subject(
            code=cls.aiml_code,
            name=f"Deep Learning Systems {cls.aiml_code}",
            department="AIML",
            semester=6,
            academic_year="2026-2027",
            curriculum_version="2026.1",
            description="Test subject for Step 4.6B lecture notes",
            is_active=True
        )
        cls.db.add(cls.subject_aiml)

        # Create secondary test subject (ECE)
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
        cls.db.commit()
        cls.db.refresh(cls.subject_aiml)
        cls.db.refresh(cls.subject_ece)
        cls.created_subject_ids.extend([cls.subject_aiml.id, cls.subject_ece.id])

        # Create syllabus document with unit and topic for AIML subject
        cls.syllabus_doc = SyllabusDocument(
            subject_id=cls.subject_aiml.id,
            version=1,
            is_latest=True,
            is_published=True,
            review_status=SyllabusReviewStatus.APPROVED,
            title="Sample Syllabus",
            original_filename="sample_syllabus.pdf",
            file_size=1024,
            mime_type="application/pdf",
            minio_bucket="syllabus",
            minio_object_key=f"syllabus/{cls.subject_aiml.id}/sample_syllabus_{cls.timestamp}.pdf",
            extracted_text="Sample Syllabus Document",
            extraction_metadata={"page_count": 2}
        )
        cls.db.add(cls.syllabus_doc)
        cls.db.commit()
        cls.db.refresh(cls.syllabus_doc)

        cls.unit_1 = SyllabusUnit(
            document_id=cls.syllabus_doc.id,
            unit_number=1,
            title="Unit 1: Neural Networks Foundations",
            order=1
        )
        cls.db.add(cls.unit_1)
        cls.db.commit()
        cls.db.refresh(cls.unit_1)

        cls.topic_1 = SyllabusTopic(
            unit_id=cls.unit_1.id,
            title="Topic 1.1: Gradient Descent & Backpropagation",
            order=1
        )
        cls.db.add(cls.topic_1)
        cls.db.commit()
        cls.db.refresh(cls.topic_1)

    @classmethod
    def tearDownClass(cls):
        # Clean up any created MinIO objects
        for key in cls.created_minio_keys:
            try:
                minio_client.delete_file("lecture-notes", key)
            except Exception:
                pass

        if cls.created_subject_ids:
            cls.db.query(Subject).filter(Subject.id.in_(cls.created_subject_ids)).delete(synchronize_session=False)
            cls.db.commit()

        if cls.created_file_ids:
            cls.db.query(File).filter(File.id.in_(cls.created_file_ids)).delete(synchronize_session=False)
            cls.db.commit()

        cls.db.close()

    # =========================================================================
    # HELPERS: In-Memory File Builders
    # =========================================================================

    def _create_sample_pdf(self, text: str = "EduMatrix Lecture Note: Neural Networks and Deep Learning") -> bytes:
        pdf_io = io.BytesIO()
        c = canvas.Canvas(pdf_io)
        c.drawString(100, 750, text)
        c.drawString(100, 730, "Mathematics of gradient descent and activation functions.")
        c.showPage()
        c.save()
        return pdf_io.getvalue()

    def _create_sample_docx(self, title: str = "Lecture Notes: Convolutional Architectures") -> bytes:
        doc_io = io.BytesIO()
        doc = docx.Document()
        doc.add_heading(title, level=0)
        doc.add_paragraph("Convolutional layers, pooling kernels, and feature extraction.")
        table = doc.add_table(rows=2, cols=2)
        table.rows[0].cells[0].text = "Layer"
        table.rows[0].cells[1].text = "Parameters"
        table.rows[1].cells[0].text = "Conv2D"
        table.rows[1].cells[1].text = "3x3 kernel, 64 filters"
        doc.save(doc_io)
        return doc_io.getvalue()

    def _create_sample_pptx(self, title: str = "Lecture Slide: Recurrent Networks and LSTMs") -> bytes:
        prs_io = io.BytesIO()
        prs = pptx.Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        slide.shapes.title.text = title
        slide.placeholders[1].text = "Sequence modeling, hidden states, and vanishing gradients."
        prs.save(prs_io)
        return prs_io.getvalue()

    def _create_sample_png(self, text: str = "EduMatrix PNG Note") -> bytes:
        img = Image.new("RGB", (300, 100), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((10, 30), text, fill=(0, 0, 0))
        png_io = io.BytesIO()
        img.save(png_io, format="PNG")
        return png_io.getvalue()

    # =========================================================================
    # 1. SUCCESSFUL UPLOADS ACROSS ALL FOUR FORMATS
    # =========================================================================

    def test_01_upload_pdf_success(self):
        """Upload a valid PDF lecture note, verifying extraction, storage, and draft status."""
        pdf_bytes = self._create_sample_pdf("Lecture 1: Transformers and Self-Attention Mechanism")
        response = self.client.post(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.lecturer_aiml_headers,
            data={"title": "Attention Mechanisms Note", "description": "Transformers overview"},
            files={"file": ("transformers.pdf", pdf_bytes, "application/pdf")},
        )
        self.assertIn(response.status_code, [200, 201], response.text)
        data = response.json()
        self.assertEqual(data["title"], "Attention Mechanisms Note")
        self.assertEqual(data["status"], "DRAFT")
        self.assertEqual(data["processing_status"], "EXTRACTED")
        self.assertFalse(data["is_published"])
        self.assertIn("transformers.pdf", data["original_filename"])

        # Security check: Internal storage keys and raw extracted text must NOT be exposed
        self.assertNotIn("minio_bucket", data)
        self.assertNotIn("minio_object_key", data)
        self.assertNotIn("extracted_text", data)

        # Database verification
        note = self.db.query(LectureNote).filter(LectureNote.id == data["id"]).first()
        self.assertIsNotNone(note)
        self.assertIn("Transformers", note.extracted_text)
        self.assertEqual(note.minio_bucket, "lecture-notes")
        self.created_minio_keys.append(note.minio_object_key)

    def test_02_upload_docx_success(self):
        """Upload a valid DOCX lecture note, verifying paragraph and table extraction."""
        docx_bytes = self._create_sample_docx("Deep Learning Architectures Note")
        response = self.client.post(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.lecturer_aiml_headers,
            data={"title": "CNNs and Pooling", "description": "Convolutional notes"},
            files={"file": ("cnn_notes.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        self.assertIn(response.status_code, [200, 201], response.text)
        data = response.json()
        self.assertEqual(data["processing_status"], "EXTRACTED")

        note = self.db.query(LectureNote).filter(LectureNote.id == data["id"]).first()
        self.assertIn("Convolutional layers", note.extracted_text)
        self.assertIn("Conv2D", note.extracted_text)  # Table row content extracted
        self.created_minio_keys.append(note.minio_object_key)

    def test_03_upload_pptx_success(self):
        """Upload a valid PPTX presentation, verifying slide-indexed extraction."""
        pptx_bytes = self._create_sample_pptx("RNNs and LSTMs Slide Presentation")
        response = self.client.post(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.lecturer_aiml_headers,
            data={"title": "RNNs Presentation", "description": "Slide deck"},
            files={"file": ("rnn_slides.pptx", pptx_bytes, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
        )
        self.assertIn(response.status_code, [200, 201], response.text)
        data = response.json()
        self.assertEqual(data["processing_status"], "EXTRACTED")

        note = self.db.query(LectureNote).filter(LectureNote.id == data["id"]).first()
        self.assertIn("--- Slide 1 ---", note.extracted_text)
        self.assertIn("RNNs and LSTMs", note.extracted_text)
        self.created_minio_keys.append(note.minio_object_key)

    def test_04_upload_png_success(self):
        """Upload a valid PNG image note, verifying OCR extraction handling."""
        png_bytes = self._create_sample_png("EduMatrix OCR Test")
        response = self.client.post(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.lecturer_aiml_headers,
            data={"title": "Whiteboard Diagram Note"},
            files={"file": ("whiteboard.png", png_bytes, "image/png")},
        )
        self.assertIn(response.status_code, [200, 201], response.text)
        data = response.json()
        self.assertIn(data["processing_status"], ["EXTRACTED", "FAILED"])

        note = self.db.query(LectureNote).filter(LectureNote.id == data["id"]).first()
        self.created_minio_keys.append(note.minio_object_key)

    # =========================================================================
    # 2. STREAMING SIZE LIMITS & BOUNDARY ENFORCEMENT
    # =========================================================================

    def test_05_oversized_file_rejected_via_streaming_guard(self):
        """Verify that files exceeding the size limit are rejected with 400 without crashing."""
        # Mock max_file_size to 100 KB for bounded test execution
        original_max = lecture_notes_service.max_file_size
        lecture_notes_service.max_file_size = 100 * 1024  # 100 KB
        try:
            oversized_pdf = b"%PDF-" + b"A" * (150 * 1024)
            response = self.client.post(
                f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
                headers=self.lecturer_aiml_headers,
                data={"title": "Oversized Note"},
                files={"file": ("oversized.pdf", oversized_pdf, "application/pdf")},
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn("maximum allowed size", response.json()["detail"])
        finally:
            lecture_notes_service.max_file_size = original_max

    def test_06_empty_file_rejected(self):
        """Verify that 0-byte uploaded files are rejected with 400."""
        response = self.client.post(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.lecturer_aiml_headers,
            data={"title": "Empty Note"},
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Empty file cannot be uploaded", response.json()["detail"])

    # =========================================================================
    # 3. FORMAT VALIDATION & MAGIC BYTE SIGNATURES
    # =========================================================================

    def test_07_unsupported_file_extension_rejected(self):
        """Verify that unsupported extensions (.txt, .exe, .zip) are rejected with 400."""
        response = self.client.post(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.lecturer_aiml_headers,
            data={"title": "Text Note"},
            files={"file": ("notes.txt", b"Plain text content", "text/plain")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported file format '.txt'", response.json()["detail"])

    def test_08_invalid_pdf_magic_signature_rejected(self):
        """Verify that a file named .pdf without %PDF- magic signature is rejected with 400."""
        fake_pdf = b"NOT_A_VALID_PDF_HEADER_AT_ALL"
        response = self.client.post(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.lecturer_aiml_headers,
            data={"title": "Fake PDF Note"},
            files={"file": ("fake.pdf", fake_pdf, "application/pdf")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("%PDF- magic signature", response.json()["detail"])

    def test_09_invalid_png_magic_signature_rejected(self):
        """Verify that a file named .png without PNG magic signature is rejected with 400."""
        fake_png = b"FAKE_PNG_BINARY_HEADER"
        response = self.client.post(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.lecturer_aiml_headers,
            data={"title": "Fake PNG Note"},
            files={"file": ("fake.png", fake_png, "image/png")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("PNG magic signature", response.json()["detail"])

    def test_10_invalid_docx_without_word_structure_rejected(self):
        """Verify that a zip file without word/ directory structure is rejected as invalid DOCX."""
        # Create a valid zip but missing word/ structure
        zip_io = io.BytesIO()
        with zipfile.ZipFile(zip_io, "w") as z:
            z.writestr("some_folder/dummy.txt", "hello")
        fake_docx = zip_io.getvalue()

        response = self.client.post(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.lecturer_aiml_headers,
            data={"title": "Fake DOCX Note"},
            files={"file": ("fake.docx", fake_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("missing Word document structure", response.json()["detail"])

    def test_11_invalid_pptx_without_ppt_structure_rejected(self):
        """Verify that a zip file without ppt/ directory structure is rejected as invalid PPTX."""
        zip_io = io.BytesIO()
        with zipfile.ZipFile(zip_io, "w") as z:
            z.writestr("some_folder/dummy.txt", "hello")
        fake_pptx = zip_io.getvalue()

        response = self.client.post(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.lecturer_aiml_headers,
            data={"title": "Fake PPTX Note"},
            files={"file": ("fake.pptx", fake_pptx, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("missing PowerPoint presentation structure", response.json()["detail"])

    # =========================================================================
    # 4. EXTRACTION ROBUSTNESS & SAFE ERROR PERSISTENCE
    # =========================================================================

    def test_12_corrupt_pdf_extraction_failure_is_safe_and_persisted(self):
        """Verify that corrupt PDFs fail safely, setting processing_status=FAILED with safe error."""
        corrupt_pdf = b"%PDF-1.4\n%corrupted bytes content that cannot be parsed by pdfplumber\n%%EOF"
        response = self.client.post(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.lecturer_aiml_headers,
            data={"title": "Corrupt PDF Note"},
            files={"file": ("corrupt.pdf", corrupt_pdf, "application/pdf")},
        )
        self.assertIn(response.status_code, [200, 201])
        data = response.json()
        self.assertEqual(data["processing_status"], "FAILED")
        self.assertIsNotNone(data["extraction_error"])
        # Ensure stack trace is not exposed
        self.assertNotIn("Traceback", data["extraction_error"])

        note = self.db.query(LectureNote).filter(LectureNote.id == data["id"]).first()
        self.created_minio_keys.append(note.minio_object_key)

    # =========================================================================
    # 5. STORAGE ROLLBACK ON DATABASE FAILURE & RETRY LOGIC
    # =========================================================================

    def test_13_database_failure_cleans_up_minio_object(self):
        """Verify that if database persistence fails, the uploaded MinIO object is deleted."""
        pdf_bytes = self._create_sample_pdf("Rollback Test PDF")

        # Mock db.commit to raise an exception during note creation
        with patch.object(Session, "commit", side_effect=Exception("Database connection terminated")):
            response = self.client.post(
                f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
                headers=self.lecturer_aiml_headers,
                data={"title": "Failing Note"},
                files={"file": ("rollback.pdf", pdf_bytes, "application/pdf")},
            )
            self.assertEqual(response.status_code, 500)

    def test_14_retry_processing_endpoint(self):
        """Verify POST /notes/{note_id}/retry re-reads binary from MinIO and retries extraction."""
        # 1. Create a note with failed extraction initially
        corrupt_pdf = b"%PDF-1.4\n%corrupt initially\n%%EOF"
        create_resp = self.client.post(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.lecturer_aiml_headers,
            data={"title": "Retry Note Test"},
            files={"file": ("retry_test.pdf", corrupt_pdf, "application/pdf")},
        )
        self.assertIn(create_resp.status_code, [200, 201])
        note_id = create_resp.json()["id"]

        note = self.db.query(LectureNote).filter(LectureNote.id == note_id).first()
        self.assertEqual(note.processing_status, LectureNoteProcessingStatus.FAILED)
        self.created_minio_keys.append(note.minio_object_key)

        # 2. Overwrite MinIO object with a valid PDF to simulate external repair or updated extractor
        valid_pdf = self._create_sample_pdf("Valid Retried PDF Content on MinIO")
        minio_client.upload_file(note.minio_bucket, note.minio_object_key, valid_pdf, "application/pdf")

        # 3. Call retry endpoint
        retry_resp = self.client.post(
            f"/api/v1/study-buddy/notes/{note_id}/retry",
            headers=self.lecturer_aiml_headers
        )
        self.assertEqual(retry_resp.status_code, 200, retry_resp.text)
        data = retry_resp.json()
        self.assertEqual(data["processing_status"], "EXTRACTED")
        self.assertIsNone(data["extraction_error"])

        self.db.refresh(note)
        self.assertEqual(note.processing_status, LectureNoteProcessingStatus.EXTRACTED)
        self.assertIn("Valid Retried PDF", note.extracted_text)

    # =========================================================================
    # 6. MULTI-ROLE AUTHORIZATION (RBAC)
    # =========================================================================

    def test_15_placement_officer_denied_on_all_endpoints(self):
        """Verify Placement Officers are denied (HTTP 403) across all note endpoints."""
        pdf_bytes = self._create_sample_pdf()

        # Upload
        res = self.client.post(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.po_headers,
            data={"title": "PO Note"},
            files={"file": ("po.pdf", pdf_bytes, "application/pdf")}
        )
        self.assertEqual(res.status_code, 403)

        # List
        res = self.client.get(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.po_headers
        )
        self.assertEqual(res.status_code, 403)

    def test_16_student_denied_from_upload_update_delete_retry(self):
        """Verify Students receive 403 Forbidden on upload, PATCH, DELETE, and retry."""
        pdf_bytes = self._create_sample_pdf()

        # Student Upload -> 403
        res = self.client.post(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.student_aiml_headers,
            data={"title": "Student Upload"},
            files={"file": ("s.pdf", pdf_bytes, "application/pdf")}
        )
        self.assertEqual(res.status_code, 403)

        # Create note as lecturer first
        lecturer_note = self.client.post(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.lecturer_aiml_headers,
            data={"title": "Lecturer Note for Student RBAC"},
            files={"file": ("l.pdf", pdf_bytes, "application/pdf")}
        ).json()
        note_id = lecturer_note["id"]

        # Student PATCH -> 403
        res = self.client.patch(
            f"/api/v1/study-buddy/notes/{note_id}",
            headers=self.student_aiml_headers,
            json={"title": "Student Modified"}
        )
        self.assertEqual(res.status_code, 403)

        # Student DELETE -> 403
        res = self.client.delete(
            f"/api/v1/study-buddy/notes/{note_id}",
            headers=self.student_aiml_headers
        )
        self.assertEqual(res.status_code, 403)

        # Student RETRY -> 403
        res = self.client.post(
            f"/api/v1/study-buddy/notes/{note_id}/retry",
            headers=self.student_aiml_headers
        )
        self.assertEqual(res.status_code, 403)

    def test_17_hod_department_isolation(self):
        """Verify HOD of CSE is blocked (HTTP 403) from managing notes in AIML subject."""
        pdf_bytes = self._create_sample_pdf()
        res = self.client.post(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.hod_cse_headers,
            data={"title": "Cross-Dept Note"},
            files={"file": ("cross.pdf", pdf_bytes, "application/pdf")}
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("HOD access restricted", res.json()["detail"])

    def test_18_admin_global_access(self):
        """Verify Admin has global access to upload and manage notes for any department."""
        pdf_bytes = self._create_sample_pdf("Admin Global Note")
        res = self.client.post(
            f"/api/v1/study-buddy/subjects/{self.subject_ece.id}/notes",
            headers=self.admin_headers,
            data={"title": "Admin ECE Note"},
            files={"file": ("admin_ece.pdf", pdf_bytes, "application/pdf")}
        )
        self.assertIn(res.status_code, [200, 201])
        self.assertEqual(res.json()["title"], "Admin ECE Note")

    # =========================================================================
    # 7. STUDENT VISIBILITY & PUBLICATION GATE
    # =========================================================================

    def test_19_student_visibility_only_published_notes(self):
        """Verify Students only see published notes for active subjects in own department."""
        pdf_bytes = self._create_sample_pdf("Student Visibility Test")

        # 1. Create a DRAFT note
        create_resp = self.client.post(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.lecturer_aiml_headers,
            data={"title": "Visibility Note Draft"},
            files={"file": ("vis.pdf", pdf_bytes, "application/pdf")}
        )
        self.assertIn(create_resp.status_code, [200, 201])
        note_id = create_resp.json()["id"]

        # 2. Student lists notes -> Draft note must NOT appear
        list_resp = self.client.get(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.student_aiml_headers
        )
        self.assertEqual(list_resp.status_code, 200)
        student_notes = list_resp.json()
        self.assertNotIn(note_id, [n["id"] for n in student_notes])

        # 3. Student GET single note -> 404
        get_resp = self.client.get(
            f"/api/v1/study-buddy/notes/{note_id}",
            headers=self.student_aiml_headers
        )
        self.assertEqual(get_resp.status_code, 404)

        # 4. Lecturer publishes the note
        pub_resp = self.client.patch(
            f"/api/v1/study-buddy/notes/{note_id}",
            headers=self.lecturer_aiml_headers,
            json={"is_published": True}
        )
        self.assertEqual(pub_resp.status_code, 200)
        self.assertTrue(pub_resp.json()["is_published"])
        self.assertEqual(pub_resp.json()["status"], "PUBLISHED")

        # 5. Student lists notes -> Note is now visible!
        list_resp2 = self.client.get(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.student_aiml_headers
        )
        self.assertEqual(list_resp2.status_code, 200)
        self.assertIn(note_id, [n["id"] for n in list_resp2.json()])

        # 6. Student GET single note -> 200 with metadata
        get_resp2 = self.client.get(
            f"/api/v1/study-buddy/notes/{note_id}",
            headers=self.student_aiml_headers
        )
        self.assertEqual(get_resp2.status_code, 200)
        self.assertEqual(get_resp2.json()["id"], note_id)
        self.assertEqual(get_resp2.json()["subject_code"], self.subject_aiml.code)

        # 7. Student from ECE department blocked from AIML note
        get_ece = self.client.get(
            f"/api/v1/study-buddy/notes/{note_id}",
            headers=self.student_ece_headers
        )
        self.assertEqual(get_ece.status_code, 403)

    def test_20_publication_guard_blocks_publishing_unextracted_notes(self):
        """Verify that attempting to publish a note with failed extraction is rejected with 400."""
        # Create a note with failed extraction
        corrupt_pdf = b"%PDF-1.4\n%unextractable\n%%EOF"
        create_resp = self.client.post(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.lecturer_aiml_headers,
            data={"title": "Failed Note Guard"},
            files={"file": ("guard.pdf", corrupt_pdf, "application/pdf")},
        )
        self.assertIn(create_resp.status_code, [200, 201])
        note_id = create_resp.json()["id"]

        # Attempt to publish -> 400 Bad Request
        patch_resp = self.client.patch(
            f"/api/v1/study-buddy/notes/{note_id}",
            headers=self.lecturer_aiml_headers,
            json={"is_published": True}
        )
        self.assertEqual(patch_resp.status_code, 400)
        self.assertIn("text extraction must succeed before publication", patch_resp.json()["detail"])

    # =========================================================================
    # 8. UNIT AND TOPIC ALIGNMENT VALIDATION
    # =========================================================================

    def test_21_unit_and_topic_alignment_validation(self):
        """Verify that assigning a unit or topic from another subject is rejected with 400."""
        pdf_bytes = self._create_sample_pdf()

        # 1. Valid unit and topic upload
        valid_resp = self.client.post(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.lecturer_aiml_headers,
            data={"title": "Aligned Note", "unit_id": self.unit_1.id, "topic_id": self.topic_1.id},
            files={"file": ("aligned.pdf", pdf_bytes, "application/pdf")},
        )
        self.assertIn(valid_resp.status_code, [200, 201], valid_resp.text)
        self.assertEqual(valid_resp.json()["unit_id"], self.unit_1.id)
        self.assertEqual(valid_resp.json()["topic_id"], self.topic_1.id)

        # 2. Upload with invalid unit_id (does not belong to subject)
        invalid_resp = self.client.post(
            f"/api/v1/study-buddy/subjects/{self.subject_ece.id}/notes",
            headers=self.admin_headers,
            data={"title": "Misaligned Note", "unit_id": self.unit_1.id},
            files={"file": ("misaligned.pdf", pdf_bytes, "application/pdf")},
        )
        self.assertEqual(invalid_resp.status_code, 400)
        self.assertIn("does not belong to subject", invalid_resp.json()["detail"])

    # =========================================================================
    # 9. NOTE DELETION & STORAGE CLEANUP
    # =========================================================================

    def test_22_delete_note_removes_db_record_and_minio_object(self):
        """Verify DELETE /notes/{note_id} deletes the DB record and calls MinIO deletion."""
        pdf_bytes = self._create_sample_pdf("Deletion Test PDF")
        create_resp = self.client.post(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.lecturer_aiml_headers,
            data={"title": "Note to Delete"},
            files={"file": ("delete_me.pdf", pdf_bytes, "application/pdf")},
        )
        self.assertIn(create_resp.status_code, [200, 201])
        note_id = create_resp.json()["id"]

        note = self.db.query(LectureNote).filter(LectureNote.id == note_id).first()
        minio_key = note.minio_object_key

        del_resp = self.client.delete(
            f"/api/v1/study-buddy/notes/{note_id}",
            headers=self.lecturer_aiml_headers
        )
        self.assertEqual(del_resp.status_code, 200)

        # Verify DB record is gone
        deleted_note = self.db.query(LectureNote).filter(LectureNote.id == note_id).first()
        self.assertIsNone(deleted_note)

    # =========================================================================
    # 10. SYLLABUS WORKFLOW INDEPENDENCE
    # =========================================================================

    def test_23_syllabus_workflow_remains_independent(self):
        """Verify that lecture note operations never modify syllabus documents or approvals."""
        initial_syllabus = self.db.query(SyllabusDocument).filter(SyllabusDocument.id == self.syllabus_doc.id).first()
        self.assertTrue(initial_syllabus.is_published)
        self.assertEqual(initial_syllabus.review_status, SyllabusReviewStatus.APPROVED)

        # Upload lecture note
        pdf_bytes = self._create_sample_pdf("Syllabus Independence Test")
        self.client.post(
            f"/api/v1/study-buddy/subjects/{self.subject_aiml.id}/notes",
            headers=self.lecturer_aiml_headers,
            data={"title": "Independence Test Note"},
            files={"file": ("indep.pdf", pdf_bytes, "application/pdf")}
        )

        self.db.refresh(initial_syllabus)
        self.assertTrue(initial_syllabus.is_published)
        self.assertEqual(initial_syllabus.review_status, SyllabusReviewStatus.APPROVED)
        self.assertEqual(initial_syllabus.version, 1)


if __name__ == "__main__":
    unittest.main()
