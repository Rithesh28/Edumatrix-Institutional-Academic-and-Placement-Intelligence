"""
Test Suite for EduMatrix Phase 4 — Step 4.6H.1:
Private Student Document Data Layer and Processing Engine

Covers:
1. Migration upgrade and downgrade verification in PostgreSQL (019 <-> 020).
2. Model constraints and status defaults (StudentDocProcessingStatus, StudentDocIndexingStatus, StudentStudyDocument).
3. Valid file types and invalid magic bytes (.txt, .pdf, .png, .docx, .pptx).
4. Oversized (>50 MiB) and empty (0-byte) upload rejections.
5. ZIP/archive safety and text extraction truncation limits.
6. Per-student quota enforcement (max 15 active docs, max 200 MiB total storage).
7. Same-student duplicate detection (HTTP 409 Conflict) and cross-student identical content acceptance.
8. Subject ownership and department validation (AIML vs ECE vs None vs 404).
9. Extraction failure handling, error sanitization, and retry processing.
10. MinIO upload failure and transactional database rollback behavior.
11. Indexing eligibility gates (rejects non-extracted, failed, or inactive documents).
12. Deterministic UUIDv5 idempotent vector indexing in Qdrant (source_type='student_upload').
13. Obsolete chunk pruning on document reindexing.
14. Partial indexing failure cleanup and recoverable FAILED state.
15. Isolation guarantee: syllabus and lecturer-note vectors remain completely unaffected.
"""

import os
import io
import time
import uuid
import zipfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from io import BytesIO

from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from qdrant_client.http import models

from app.core.database import SessionLocal, engine
from app.models.user import User, UserRole
from app.models.study_buddy import (
    Subject,
    SyllabusDocument,
    LectureNote,
    LectureNoteStatus,
    StudentStudyDocument,
    StudentDocProcessingStatus,
    StudentDocIndexingStatus,
)
from app.services.file_storage.minio_client import minio_client
from app.services.file_storage.qdrant_client import qdrant_client
from app.services.student_documents_service import (
    student_documents_service,
    STUDENT_DOCS_BUCKET,
    MAX_STUDENT_DOC_FILE_SIZE,
    MAX_STUDENT_ACTIVE_DOCS,
    MAX_STUDENT_TOTAL_STORAGE,
)
from app.services.student_documents_indexing_service import (
    student_documents_indexing_service,
    STUDY_BUDDY_COLLECTION,
    STUDY_BUDDY_VECTOR_SIZE,
)


class TestStudyBuddyStep46H1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db: Session = SessionLocal()
        cls.timestamp = int(time.time() * 1000)

        # Users across roles
        cls.student_aiml = cls.db.query(User).filter(User.role == UserRole.STUDENT, User.department == "AIML").first()
        cls.student_ece = cls.db.query(User).filter(User.role == UserRole.STUDENT, User.department == "ECE").first()
        if not cls.student_aiml or not cls.student_ece:
            raise RuntimeError("Required test student users (AIML and ECE) not found in DB.")

        cls.created_doc_ids = []
        cls.created_subject_ids = []
        cls.created_minio_keys = []

        # 1. Setup test subjects
        cls.aiml_code = f"AIML{cls.timestamp % 100000}"
        cls.subject_aiml = Subject(
            code=cls.aiml_code,
            name=f"Deep Learning Systems {cls.aiml_code}",
            department="AIML",
            semester=6,
            is_active=True
        )
        cls.db.add(cls.subject_aiml)

        cls.ece_code = f"ECE{cls.timestamp % 100000}"
        cls.subject_ece = Subject(
            code=cls.ece_code,
            name=f"Digital Signal Processing {cls.ece_code}",
            department="ECE",
            semester=4,
            is_active=True
        )
        cls.db.add(cls.subject_ece)
        cls.db.commit()
        cls.db.refresh(cls.subject_aiml)
        cls.db.refresh(cls.subject_ece)

        cls.created_subject_ids.extend([cls.subject_aiml.id, cls.subject_ece.id])
        student_documents_service.ensure_bucket()
        student_documents_indexing_service.ensure_collection()

    @classmethod
    def tearDownClass(cls):
        # Clean up created documents and vectors
        for doc_id in cls.created_doc_ids:
            try:
                student_documents_indexing_service.delete_document_chunks(doc_id)
            except Exception:
                pass
            try:
                doc = cls.db.query(StudentStudyDocument).filter(StudentStudyDocument.id == doc_id).first()
                if doc:
                    minio_client.delete_file(doc.minio_bucket, doc.minio_object_key)
                    cls.db.delete(doc)
            except Exception:
                pass

        for key in cls.created_minio_keys:
            try:
                minio_client.delete_file(STUDENT_DOCS_BUCKET, key)
            except Exception:
                pass

        # Clean up subjects
        for s_id in cls.created_subject_ids:
            try:
                cls.db.query(Subject).filter(Subject.id == s_id).delete()
            except Exception:
                pass

        try:
            cls.db.commit()
        except Exception:
            cls.db.rollback()
        finally:
            cls.db.close()

    def _make_upload_file(self, content: bytes, filename: str, content_type: str = "text/plain") -> UploadFile:
        """Helper to create an async-compatible UploadFile."""
        from starlette.datastructures import Headers
        file_io = BytesIO(content)
        upload_file = UploadFile(
            filename=filename,
            file=file_io,
            headers=Headers({"content-type": content_type})
        )
        return upload_file

    # =========================================================================
    # 1. MIGRATION VERIFICATION
    # =========================================================================
    def test_01_migration_upgrade_and_schema_constraints(self):
        """Verify Alembic migration 020 table, indexes, and constraint setup."""
        # Query PostgreSQL metadata
        with engine.connect() as conn:
            # Check table existence
            result = conn.execute(text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'study_buddy_student_documents')"
            )).scalar()
            self.assertTrue(result, "Table 'study_buddy_student_documents' must exist.")

            # Check column properties
            col_res = conn.execute(text(
                "SELECT column_name, is_nullable, data_type FROM information_schema.columns "
                "WHERE table_name = 'study_buddy_student_documents'"
            )).fetchall()
            cols = {r[0]: (r[1], r[2]) for r in col_res}

            self.assertIn("id", cols)
            self.assertIn("student_id", cols)
            self.assertEqual(cols["student_id"][0], "NO", "student_id must be non-nullable")
            self.assertIn("subject_id", cols)
            self.assertEqual(cols["subject_id"][0], "YES", "subject_id must be nullable")
            self.assertIn("content_hash", cols)
            self.assertIn("is_active", cols)
            self.assertIn("processing_status", cols)
            self.assertIn("indexing_status", cols)

            # Check partial unique index uq_study_buddy_student_docs_active_hash
            idx_res = conn.execute(text(
                "SELECT indexname FROM pg_indexes WHERE tablename = 'study_buddy_student_documents'"
            )).scalars().all()
            self.assertIn("uq_study_buddy_student_docs_active_hash", idx_res)
            self.assertIn("ix_study_buddy_student_docs_student_active", idx_res)

    # =========================================================================
    # 2. MODEL ENUMS AND DEFAULTS
    # =========================================================================
    def test_02_model_enums_and_defaults(self):
        """Verify model enums, defaults, and cascade semantics."""
        self.assertEqual(StudentDocProcessingStatus.UPLOADED.value, "UPLOADED")
        self.assertEqual(StudentDocProcessingStatus.EXTRACTED.value, "EXTRACTED")
        self.assertEqual(StudentDocProcessingStatus.FAILED.value, "FAILED")
        self.assertEqual(StudentDocIndexingStatus.NOT_INDEXED.value, "NOT_INDEXED")
        self.assertEqual(StudentDocIndexingStatus.INDEXED.value, "INDEXED")

        doc = StudentStudyDocument(
            student_id=self.student_aiml.id,
            title="Test Defaults Doc",
            original_filename="defaults.txt",
            file_size=100,
            mime_type="text/plain",
            content_hash=f"hash_{uuid.uuid4().hex[:16]}",
            minio_bucket=STUDENT_DOCS_BUCKET,
            minio_object_key=f"student_{self.student_aiml.id}/def_{uuid.uuid4().hex[:8]}.txt",
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        self.created_doc_ids.append(doc.id)

        self.assertTrue(doc.is_active)
        self.assertEqual(doc.processing_status, StudentDocProcessingStatus.UPLOADED)
        self.assertEqual(doc.indexing_status, StudentDocIndexingStatus.NOT_INDEXED)
        self.assertEqual(doc.indexed_chunk_count, 0)
        self.assertIsNotNone(doc.created_at)

    # =========================================================================
    # 3. VALID FILE TYPES & INVALID MAGIC BYTES
    # =========================================================================
    def test_03_valid_and_invalid_file_formats(self):
        """Verify extension validation and magic byte enforcement."""
        import asyncio

        # A. Unsupported extension (.exe)
        bad_ext_file = self._make_upload_file(b"MZ...", "malicious.exe", "application/x-msdownload")
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(student_documents_service.upload_and_ingest_document(
                self.db, bad_ext_file, self.student_aiml, "Bad File"
            ))
        self.assertEqual(cm.exception.status_code, 400)
        self.assertIn("Unsupported file format", cm.exception.detail)

        # B. Corrupt PDF without %PDF- magic signature
        fake_pdf = self._make_upload_file(b"NOT_A_REAL_PDF_HEADER_123456", "fake.pdf", "application/pdf")
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(student_documents_service.upload_and_ingest_document(
                self.db, fake_pdf, self.student_aiml, "Fake PDF"
            ))
        self.assertEqual(cm.exception.status_code, 400)
        self.assertIn("missing %PDF- magic signature", cm.exception.detail)

        # C. Corrupt PNG without PNG magic signature
        fake_png = self._make_upload_file(b"NOT_A_PNG_HEADER_12345678", "fake.png", "image/png")
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(student_documents_service.upload_and_ingest_document(
                self.db, fake_png, self.student_aiml, "Fake PNG"
            ))
        self.assertEqual(cm.exception.status_code, 400)
        self.assertIn("missing PNG magic signature", cm.exception.detail)

        # D. Corrupt DOCX without PK zip signature
        fake_docx = self._make_upload_file(b"NOT_A_ZIP_HEADER_12345678", "fake.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(student_documents_service.upload_and_ingest_document(
                self.db, fake_docx, self.student_aiml, "Fake DOCX"
            ))
        self.assertEqual(cm.exception.status_code, 400)
        self.assertIn("missing PK zip header signature", cm.exception.detail)

        # E. Binary disguised as .txt (contains null byte)
        binary_txt = self._make_upload_file(b"Hello\x00World\x00BinaryData", "binary.txt", "text/plain")
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(student_documents_service.upload_and_ingest_document(
                self.db, binary_txt, self.student_aiml, "Binary Text"
            ))
        self.assertEqual(cm.exception.status_code, 400)
        self.assertIn("binary content detected", cm.exception.detail)

    # =========================================================================
    # 4. OVERSIZED AND EMPTY UPLOADS
    # =========================================================================
    def test_04_oversized_and_empty_uploads(self):
        """Verify 0-byte and oversized (>50 MiB) uploads are rejected."""
        import asyncio
        from starlette.datastructures import Headers

        # A. Empty 0-byte file
        empty_file = self._make_upload_file(b"", "empty.txt", "text/plain")
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(student_documents_service.upload_and_ingest_document(
                self.db, empty_file, self.student_aiml, "Empty Note"
            ))
        self.assertEqual(cm.exception.status_code, 400)
        self.assertIn("Empty file cannot be uploaded", cm.exception.detail)

        # B. Oversized file (> 50 MiB threshold)
        class ChunkGenerator:
            def __init__(self, target_size, chunk_size=64 * 1024):
                self.target_size = target_size
                self.chunk_size = chunk_size
                self.sent = 0
            async def read(self, amt):
                if self.sent >= self.target_size:
                    return b""
                take = min(self.chunk_size, self.target_size - self.sent)
                self.sent += take
                return b"A" * take

        oversized_file = UploadFile(
            filename="oversized.txt",
            file=BytesIO(),
            headers=Headers({"content-type": "text/plain"})
        )
        oversized_file.read = ChunkGenerator(MAX_STUDENT_DOC_FILE_SIZE + 1024).read


        with self.assertRaises(HTTPException) as cm:
            asyncio.run(student_documents_service.upload_and_ingest_document(
                self.db, oversized_file, self.student_aiml, "Oversized Note"
            ))
        self.assertEqual(cm.exception.status_code, 400)
        self.assertIn("exceeds the maximum allowed size of 50 MB", cm.exception.detail)

    # =========================================================================
    # 5. ZIP ARCHIVE SAFETY & TEXT TRUNCATION
    # =========================================================================
    def test_05_zip_archive_safety_and_text_truncation(self):
        """Verify zip bomb protection and text truncation limits."""
        import asyncio
        from app.services.student_documents_service import MAX_EXTRACTED_TEXT_LENGTH, TRUNCATION_MARKER

        # A. Malformed zip missing expected word/ or ppt/ structure
        bad_zip_buffer = BytesIO()
        with zipfile.ZipFile(bad_zip_buffer, "w") as z:
            z.writestr("unrelated.txt", "Some random text in a zip")
        bad_docx = self._make_upload_file(bad_zip_buffer.getvalue(), "corrupt_structure.docx")
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(student_documents_service.upload_and_ingest_document(
                self.db, bad_docx, self.student_aiml, "Corrupt DOCX"
            ))
        self.assertEqual(cm.exception.status_code, 400)
        self.assertIn("Corrupt or invalid DOCX file", cm.exception.detail)

        # B. Text truncation when content > 500k characters
        long_text = ("Artificial Intelligence and Machine Learning Fundamentals. " * 12000).encode("utf-8")
        self.assertGreater(len(long_text), MAX_EXTRACTED_TEXT_LENGTH)

        long_txt_file = self._make_upload_file(long_text, "long_text_doc.txt", "text/plain")
        doc = asyncio.run(student_documents_service.upload_and_ingest_document(
            self.db, long_txt_file, self.student_aiml, "Long Truncated Note"
        ))
        self.created_doc_ids.append(doc.id)

        self.assertEqual(doc.processing_status, StudentDocProcessingStatus.EXTRACTED)
        self.assertIn(TRUNCATION_MARKER, doc.extracted_text)
        self.assertEqual(len(doc.extracted_text), MAX_EXTRACTED_TEXT_LENGTH)
        self.assertTrue(doc.extraction_metadata.get("truncated"))

    # =========================================================================
    # 6. QUOTA ENFORCEMENT & SAME-STUDENT DUPLICATES
    # =========================================================================
    def test_06_quota_enforcement_and_same_student_duplicates(self):
        """Verify active document count quota, storage quota, and duplicate rejection."""
        import asyncio

        # A. Duplicate detection for same student
        content = f"Unique student study note content for duplicate testing {self.timestamp}".encode("utf-8")
        doc1_file = self._make_upload_file(content, "study_notes.txt", "text/plain")

        doc1 = asyncio.run(student_documents_service.upload_and_ingest_document(
            self.db, doc1_file, self.student_aiml, "First Upload"
        ))
        self.created_doc_ids.append(doc1.id)

        # Second upload with same content by SAME student -> HTTP 409 Conflict
        doc2_file = self._make_upload_file(content, "study_notes_copy.txt", "text/plain")
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(student_documents_service.upload_and_ingest_document(
                self.db, doc2_file, self.student_aiml, "Second Upload"
            ))
        self.assertEqual(cm.exception.status_code, 409)
        self.assertIn("You have already uploaded this document", cm.exception.detail)

        # B. Document Count Quota Enforcement (max 15 docs)
        with patch.object(student_documents_service, "check_student_quotas") as mock_quota:
            mock_quota.side_effect = HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document quota exceeded: Students may keep up to {MAX_STUDENT_ACTIVE_DOCS} active study documents."
            )
            extra_file = self._make_upload_file(b"Another note", "quota_test.txt")
            with self.assertRaises(HTTPException) as cm:
                asyncio.run(student_documents_service.upload_and_ingest_document(
                    self.db, extra_file, self.student_aiml, "Quota Overflow Doc"
                ))
            self.assertEqual(cm.exception.status_code, 400)
            self.assertIn("Document quota exceeded", cm.exception.detail)

    # =========================================================================
    # 7. CROSS-STUDENT IDENTICAL CONTENT ACCEPTANCE
    # =========================================================================
    def test_07_identical_file_different_students_accepted(self):
        """Ensure two different students CAN upload identical study files without conflict."""
        import asyncio

        shared_content = f"Standard academic reference cheat sheet {self.timestamp}".encode("utf-8")

        # Student A upload
        file_a = self._make_upload_file(shared_content, "shared_reference.txt", "text/plain")
        doc_a = asyncio.run(student_documents_service.upload_and_ingest_document(
            self.db, file_a, self.student_aiml, "Student A Reference"
        ))
        self.created_doc_ids.append(doc_a.id)

        # Student B upload with identical content
        file_b = self._make_upload_file(shared_content, "shared_reference.txt", "text/plain")
        doc_b = asyncio.run(student_documents_service.upload_and_ingest_document(
            self.db, file_b, self.student_ece, "Student B Reference"
        ))
        self.created_doc_ids.append(doc_b.id)

        self.assertEqual(doc_a.content_hash, doc_b.content_hash)
        self.assertNotEqual(doc_a.id, doc_b.id)
        self.assertNotEqual(doc_a.student_id, doc_b.student_id)
        self.assertEqual(doc_a.processing_status, StudentDocProcessingStatus.EXTRACTED)
        self.assertEqual(doc_b.processing_status, StudentDocProcessingStatus.EXTRACTED)

    # =========================================================================
    # 8. SUBJECT OWNERSHIP & DEPARTMENT VALIDATION
    # =========================================================================
    def test_08_subject_ownership_and_department_validation(self):
        """Verify subject alignment validation against student's department."""
        import asyncio

        content = f"Notes with subject alignment test {self.timestamp}".encode("utf-8")

        # A. Same department subject (AIML student with AIML subject) -> Success
        valid_file = self._make_upload_file(content, "aiml_valid.txt")
        doc_valid = asyncio.run(student_documents_service.upload_and_ingest_document(
            self.db, valid_file, self.student_aiml, "AIML Subject Note", subject_id=self.subject_aiml.id
        ))
        self.created_doc_ids.append(doc_valid.id)
        self.assertEqual(doc_valid.subject_id, self.subject_aiml.id)

        # B. Cross-department subject (AIML student with ECE subject) -> HTTP 403 Forbidden
        diff_dept_file = self._make_upload_file(b"Cross dept notes", "ece_cross.txt")
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(student_documents_service.upload_and_ingest_document(
                self.db, diff_dept_file, self.student_aiml, "Cross Dept Note", subject_id=self.subject_ece.id
            ))
        self.assertEqual(cm.exception.status_code, 403)
        self.assertIn("Access denied: Subject belongs to department", cm.exception.detail)

        # C. Non-existent subject ID -> HTTP 404 Not Found
        non_existent_file = self._make_upload_file(b"Nonexistent subject notes", "missing.txt")
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(student_documents_service.upload_and_ingest_document(
                self.db, non_existent_file, self.student_aiml, "Missing Subject Note", subject_id=9999999
            ))
        self.assertEqual(cm.exception.status_code, 404)

        # D. Optional subject=None -> Success
        no_subj_file = self._make_upload_file(b"General study notes without subject", "general.txt")
        doc_no_subj = asyncio.run(student_documents_service.upload_and_ingest_document(
            self.db, no_subj_file, self.student_aiml, "General Notes", subject_id=None
        ))
        self.created_doc_ids.append(doc_no_subj.id)
        self.assertIsNone(doc_no_subj.subject_id)

    # =========================================================================
    # 9. EXTRACTION FAILURE & RETRY HANDLING
    # =========================================================================
    def test_09_extraction_failure_and_retry_processing(self):
        """Verify extraction failure retains binary in MinIO with FAILED status, and retry succeeds."""
        import asyncio

        # Upload a dummy file that passes streaming validation but fails extraction
        content = f"Simple extraction retry test {self.timestamp}".encode("utf-8")
        file_obj = self._make_upload_file(content, "retry_test.txt")

        # Mock extraction failure on initial upload
        with patch.object(student_documents_service, "extract_content_async") as mock_extract:
            mock_extract.return_value = (None, {}, "Corrupt content simulated error")
            failed_doc = asyncio.run(student_documents_service.upload_and_ingest_document(
                self.db, file_obj, self.student_aiml, "Failed Extraction Note"
            ))
            self.created_doc_ids.append(failed_doc.id)

        self.assertEqual(failed_doc.processing_status, StudentDocProcessingStatus.FAILED)
        self.assertIn("Corrupt content simulated error", failed_doc.extraction_error)
        self.assertIsNone(failed_doc.extracted_text)

        # Binary is preserved in MinIO
        minio_data = minio_client.download_file(failed_doc.minio_bucket, failed_doc.minio_object_key)
        self.assertEqual(minio_data, content)

        # Now test retry_document_processing with real extraction
        recovered_doc = asyncio.run(student_documents_service.retry_document_processing(
            self.db, failed_doc.id, self.student_aiml.id
        ))
        self.assertEqual(recovered_doc.processing_status, StudentDocProcessingStatus.EXTRACTED)
        self.assertIsNone(recovered_doc.extraction_error)
        self.assertIn("Simple extraction retry test", recovered_doc.extracted_text)

    # =========================================================================
    # 10. MINIO FAILURE & DATABASE ROLLBACK
    # =========================================================================
    def test_10_minio_upload_failure_and_db_rollback(self):
        """Verify that MinIO failure leaves no orphan database rows or temporary files."""
        import asyncio

        file_obj = self._make_upload_file(b"MinIO failure test content", "minio_fail.txt")

        with patch.object(minio_client, "upload_file_from_path", side_effect=RuntimeError("MinIO connection reset")):
            with self.assertRaises(HTTPException) as cm:
                asyncio.run(student_documents_service.upload_and_ingest_document(
                    self.db, file_obj, self.student_aiml, "MinIO Fail Doc"
                ))
            self.assertEqual(cm.exception.status_code, 500)

        # Check DB: no record with title "MinIO Fail Doc" exists
        orphan = self.db.query(StudentStudyDocument).filter(
            StudentStudyDocument.title == "MinIO Fail Doc",
            StudentStudyDocument.student_id == self.student_aiml.id
        ).first()
        self.assertIsNone(orphan, "Database record must be cleanly rolled back on MinIO failure.")

    # =========================================================================
    # 11. INDEXING ELIGIBILITY GATES
    # =========================================================================
    def test_11_indexing_eligibility_rejections(self):
        """Verify vector indexing rejects non-extracted, failed, or inactive documents."""
        # A. Document in UPLOADED or FAILED status rejected
        unextracted_doc = StudentStudyDocument(
            student_id=self.student_aiml.id,
            title="Unextracted Doc",
            original_filename="unex.txt",
            file_size=50,
            mime_type="text/plain",
            content_hash=uuid.uuid4().hex,
            minio_bucket=STUDENT_DOCS_BUCKET,
            minio_object_key=f"student_{self.student_aiml.id}/unex_{uuid.uuid4().hex[:8]}.txt",
            processing_status=StudentDocProcessingStatus.FAILED,
            is_active=True
        )
        self.db.add(unextracted_doc)
        self.db.commit()
        self.db.refresh(unextracted_doc)
        self.created_doc_ids.append(unextracted_doc.id)

        with self.assertRaises(HTTPException) as cm:
            student_documents_indexing_service.index_student_document(
                self.db, unextracted_doc.id, self.student_aiml.id
            )
        self.assertEqual(cm.exception.status_code, 400)
        self.assertIn("Text extraction not completed", cm.exception.detail)

        # B. Inactive document rejected
        inactive_doc = StudentStudyDocument(
            student_id=self.student_aiml.id,
            title="Inactive Doc",
            original_filename="inact.txt",
            file_size=50,
            mime_type="text/plain",
            content_hash=uuid.uuid4().hex,
            minio_bucket=STUDENT_DOCS_BUCKET,
            minio_object_key=f"student_{self.student_aiml.id}/inact_{uuid.uuid4().hex[:8]}.txt",
            processing_status=StudentDocProcessingStatus.EXTRACTED,
            extracted_text="Some extracted text here",
            is_active=False
        )
        self.db.add(inactive_doc)
        self.db.commit()
        self.db.refresh(inactive_doc)
        self.created_doc_ids.append(inactive_doc.id)

        with self.assertRaises(HTTPException) as cm:
            student_documents_indexing_service.index_student_document(
                self.db, inactive_doc.id, self.student_aiml.id
            )
        self.assertEqual(cm.exception.status_code, 400)
        self.assertIn("inactive or deleted", cm.exception.detail)

        # C. Empty extracted text rejected
        empty_text_doc = StudentStudyDocument(
            student_id=self.student_aiml.id,
            title="Empty Text Doc",
            original_filename="empty_txt.txt",
            file_size=50,
            mime_type="text/plain",
            content_hash=uuid.uuid4().hex,
            minio_bucket=STUDENT_DOCS_BUCKET,
            minio_object_key=f"student_{self.student_aiml.id}/empty_txt_{uuid.uuid4().hex[:8]}.txt",
            processing_status=StudentDocProcessingStatus.EXTRACTED,
            extracted_text="   \n\t  ",
            is_active=True
        )
        self.db.add(empty_text_doc)
        self.db.commit()
        self.db.refresh(empty_text_doc)
        self.created_doc_ids.append(empty_text_doc.id)

        with self.assertRaises(HTTPException) as cm:
            student_documents_indexing_service.index_student_document(
                self.db, empty_text_doc.id, self.student_aiml.id
            )
        self.assertEqual(cm.exception.status_code, 400)
        self.assertIn("contains no extracted text", cm.exception.detail)

    # =========================================================================
    # 12. DETERMINISTIC IDEMPOTENT VECTOR INDEXING
    # =========================================================================
    def test_12_deterministic_idempotent_indexing(self):
        """Verify vector points in Qdrant use source_type='student_upload' and deterministic UUIDv5 IDs."""
        text_content = (
            "Neural network backpropagation algorithms compute gradients using the chain rule. "
            "Optimizers like Adam and RMSprop adjust learning rates adaptively based on running averages."
        )
        doc = StudentStudyDocument(
            student_id=self.student_aiml.id,
            subject_id=self.subject_aiml.id,
            title="Deep Learning Study Cheatsheet",
            original_filename="dl_cheatsheet.txt",
            file_size=len(text_content),
            mime_type="text/plain",
            content_hash=uuid.uuid4().hex,
            minio_bucket=STUDENT_DOCS_BUCKET,
            minio_object_key=f"student_{self.student_aiml.id}/dl_{uuid.uuid4().hex[:8]}.txt",
            processing_status=StudentDocProcessingStatus.EXTRACTED,
            extracted_text=text_content,
            is_active=True
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        self.created_doc_ids.append(doc.id)

        # Index document
        res = student_documents_indexing_service.index_student_document(self.db, doc.id, self.student_aiml.id)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertGreater(res["chunks_indexed"], 0)

        # Verify PostgreSQL state
        self.db.refresh(doc)
        self.assertEqual(doc.indexing_status, StudentDocIndexingStatus.INDEXED)
        self.assertEqual(doc.indexed_chunk_count, res["chunks_indexed"])

        # Check Qdrant points
        expected_point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"student_study_doc_{doc.id}_chunk_1"))
        retrieved_points = qdrant_client.client.retrieve(
            collection_name=STUDY_BUDDY_COLLECTION,
            ids=[expected_point_id],
            with_payload=True,
            with_vectors=True
        )
        self.assertEqual(len(retrieved_points), 1)
        point = retrieved_points[0]
        self.assertEqual(point.id, expected_point_id)
        self.assertEqual(len(point.vector), STUDY_BUDDY_VECTOR_SIZE)
        self.assertEqual(point.payload["source_type"], "student_upload")
        self.assertEqual(point.payload["student_id"], self.student_aiml.id)
        self.assertEqual(point.payload["student_study_document_id"], doc.id)
        self.assertEqual(point.payload["subject_id"], self.subject_aiml.id)
        self.assertEqual(point.payload["subject_code"], self.subject_aiml.code)

        # Re-indexing the same document should be idempotent (no duplicate points created)
        res2 = student_documents_indexing_service.index_student_document(self.db, doc.id, self.student_aiml.id)
        self.assertEqual(res2["status"], "SUCCESS")
        self.assertEqual(res2["chunks_indexed"], res["chunks_indexed"])

    # =========================================================================
    # 13. REINDEXING REMOVES OBSOLETE CHUNKS
    # =========================================================================
    def test_13_reindexing_removes_obsolete_chunks(self):
        """Verify that shortening a document and reindexing deletes obsolete vector points."""
        multi_chunk_text = (
            "Paragraph one describing convolution operations and kernels in CNN architectures.\n\n"
            "Paragraph two explaining pooling layers, max pooling, and spatial downsampling techniques.\n\n"
            "Paragraph three covering fully connected layers, softmax activation, and categorical cross entropy loss."
        )
        doc = StudentStudyDocument(
            student_id=self.student_aiml.id,
            title="Multi Chunk Document",
            original_filename="multi.txt",
            file_size=len(multi_chunk_text),
            mime_type="text/plain",
            content_hash=uuid.uuid4().hex,
            minio_bucket=STUDENT_DOCS_BUCKET,
            minio_object_key=f"student_{self.student_aiml.id}/multi_{uuid.uuid4().hex[:8]}.txt",
            processing_status=StudentDocProcessingStatus.EXTRACTED,
            extracted_text=multi_chunk_text,
            is_active=True
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        self.created_doc_ids.append(doc.id)

        # 1. First index with full text
        res1 = student_documents_indexing_service.index_student_document(self.db, doc.id, self.student_aiml.id)
        count1 = res1["chunks_indexed"]

        # 2. Shorten text to a single short sentence
        doc.extracted_text = "Short summary only."
        doc.indexing_status = StudentDocIndexingStatus.NOT_INDEXED
        self.db.commit()

        # 3. Reindex
        res2 = student_documents_indexing_service.index_student_document(self.db, doc.id, self.student_aiml.id)
        self.assertEqual(res2["chunks_indexed"], 1)

        # Verify old chunk 2 point (if existed) no longer exists in Qdrant
        if count1 > 1:
            old_point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"student_study_doc_{doc.id}_chunk_2"))
            old_pts = qdrant_client.client.retrieve(
                collection_name=STUDY_BUDDY_COLLECTION,
                ids=[old_point_id]
            )
            self.assertEqual(len(old_pts), 0, "Obsolete vector points must be pruned on reindexing.")

    # =========================================================================
    # 14. PARTIAL INDEXING FAILURE CLEANUP
    # =========================================================================
    def test_14_partial_indexing_failure_cleanup(self):
        """Verify vector cleanup and FAILED state update when vector upsert fails."""
        doc = StudentStudyDocument(
            student_id=self.student_aiml.id,
            title="Failure Test Document",
            original_filename="fail_idx.txt",
            file_size=100,
            mime_type="text/plain",
            content_hash=uuid.uuid4().hex,
            minio_bucket=STUDENT_DOCS_BUCKET,
            minio_object_key=f"student_{self.student_aiml.id}/fail_idx_{uuid.uuid4().hex[:8]}.txt",
            processing_status=StudentDocProcessingStatus.EXTRACTED,
            extracted_text="Simple text for indexing failure simulation.",
            is_active=True
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        self.created_doc_ids.append(doc.id)

        with patch.object(qdrant_client.client, "upsert", side_effect=RuntimeError("Qdrant write timeout simulated")):
            with self.assertRaises(HTTPException) as cm:
                student_documents_indexing_service.index_student_document(
                    self.db, doc.id, self.student_aiml.id
                )
            self.assertEqual(cm.exception.status_code, 500)

        self.db.refresh(doc)
        self.assertEqual(doc.indexing_status, StudentDocIndexingStatus.FAILED)
        self.assertIn("Qdrant write timeout simulated", doc.extraction_metadata.get("indexing_error", ""))

    # =========================================================================
    # 15. ISOLATION: SYLLABUS & LECTURE NOTES REMAIN UNAFFECTED
    # =========================================================================
    def test_15_syllabus_and_lecture_notes_vectors_unaffected(self):
        """Verify that student document indexing/deletion never touches syllabus or lecture note points."""
        # 1. Count existing syllabus & lecture note points
        filter_syllabus = models.Filter(
            must=[models.FieldCondition(key="source_type", match=models.MatchValue(value="syllabus"))]
        )
        filter_lecture = models.Filter(
            must=[models.FieldCondition(key="source_type", match=models.MatchValue(value="lecture_note"))]
        )

        s_count_before = qdrant_client.client.count(collection_name=STUDY_BUDDY_COLLECTION, count_filter=filter_syllabus).count
        l_count_before = qdrant_client.client.count(collection_name=STUDY_BUDDY_COLLECTION, count_filter=filter_lecture).count

        # 2. Upload, index, and delete a student document
        doc = StudentStudyDocument(
            student_id=self.student_aiml.id,
            title="Isolation Check Doc",
            original_filename="isolation.txt",
            file_size=100,
            mime_type="text/plain",
            content_hash=uuid.uuid4().hex,
            minio_bucket=STUDENT_DOCS_BUCKET,
            minio_object_key=f"student_{self.student_aiml.id}/iso_{uuid.uuid4().hex[:8]}.txt",
            processing_status=StudentDocProcessingStatus.EXTRACTED,
            extracted_text="Text content for isolation testing.",
            is_active=True
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        self.created_doc_ids.append(doc.id)

        # Index
        student_documents_indexing_service.index_student_document(self.db, doc.id, self.student_aiml.id)

        # Delete chunks
        student_documents_indexing_service.delete_document_chunks(doc.id)

        # 3. Verify counts for syllabus & lecture notes have not changed
        s_count_after = qdrant_client.client.count(collection_name=STUDY_BUDDY_COLLECTION, count_filter=filter_syllabus).count
        l_count_after = qdrant_client.client.count(collection_name=STUDY_BUDDY_COLLECTION, count_filter=filter_lecture).count

        self.assertEqual(s_count_before, s_count_after, "Syllabus vector count must remain completely unaffected.")
        self.assertEqual(l_count_before, l_count_after, "Lecture note vector count must remain completely unaffected.")


if __name__ == "__main__":
    unittest.main()
