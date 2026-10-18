"""
Student Study Documents Service (Private Ingestion and Lifecycle Engine)

Manages:
- Memory-bounded streaming upload validation (max 50 MiB)
- Format and magic signature validation for PDF, PNG, DOCX, PPTX, and TXT
- Anti-zip-bomb security checks for DOCX/PPTX
- SHA-256 content hashing during stream
- Per-student active document quota (15 docs, 200 MiB total storage)
- Same-student duplicate detection on active documents
- Optional subject department-alignment validation
- Offloaded text extraction via dedicated ThreadPoolExecutor
- Private MinIO storage in 'student-documents' bucket
- Database persistence with rollback cleanup and failure state recording
"""

import os
import re
import uuid
import hashlib
import logging
import tempfile
import asyncio
from typing import Optional, Tuple, Dict, Any, List
from datetime import datetime, timezone, timedelta

from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from ..core.config import settings
from ..models.user import User, UserRole
from ..models.study_buddy import (
    Subject,
    StudentStudyDocument,
    StudentDocProcessingStatus,
    StudentDocIndexingStatus,
)
import time
from ..core.study_buddy_timing import record_perf_metric, PerfTimer
from .file_storage.minio_client import minio_client
from .lecture_notes_service import (
    inspect_zip_safety,
    lecture_notes_service,
    extraction_executor,
    MAX_EXTRACTED_TEXT_LENGTH,
    TRUNCATION_MARKER,
)

logger = logging.getLogger(__name__)

# ============================================
# STUDENT DOCUMENT SAFETY CONSTANTS
# ============================================
MAX_STUDENT_DOC_FILE_SIZE = 50 * 1024 * 1024  # 50 MiB (52,428,800 bytes)
MAX_STUDENT_ACTIVE_DOCS = 15                  # Max 15 active documents per student
MAX_STUDENT_TOTAL_STORAGE = 200 * 1024 * 1024 # 200 MiB total active storage
ALLOWED_STUDENT_DOC_EXTENSIONS = {".pdf", ".png", ".docx", ".pptx", ".txt"}
CHUNK_SIZE = 64 * 1024                        # 64 KB streaming buffer
STUDENT_DOCS_BUCKET = "student-documents"
STUDENT_LOCK_NAMESPACE = 1398031684  # ASCII 'STUD' namespace for per-student advisory lock


def _acquire_student_advisory_lock(db: Session, student_id: int) -> None:
    """
    Acquire a PostgreSQL transaction-level advisory lock scoped to the student ID.
    Serializes quota checks and reservations for the same student while allowing
    concurrent uploads across different students.
    Automatically released on commit or rollback.
    """
    if db.bind and db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(:namespace, :student_id)"),
            {"namespace": STUDENT_LOCK_NAMESPACE, "student_id": int(student_id)}
        )


def _normalize_dept(dept: Optional[str]) -> str:
    """Normalize department strings for case-insensitive comparison."""
    return (dept or "").strip().lower()


def _get_user_department(user: User) -> Optional[str]:
    """Resolve department for user across roles (including student profile branch fallback)."""
    if user.department:
        return user.department
    if user.student_profile and user.student_profile.branch:
        return user.student_profile.branch
    return None


class StudentDocumentsService:
    """Service managing private student study documents ingestion, extraction, and lifecycle."""

    def __init__(self):
        self.bucket = STUDENT_DOCS_BUCKET
        self.max_file_size = MAX_STUDENT_DOC_FILE_SIZE
        self.allowed_extensions = ALLOWED_STUDENT_DOC_EXTENSIONS
        self.executor = extraction_executor

    def ensure_bucket(self):
        """Ensure the dedicated 'student-documents' bucket exists in MinIO."""
        try:
            minio_client._create_bucket_if_not_exists(self.bucket)
        except Exception as e:
            logger.warning(f"⚠️ Failed to ensure student documents bucket '{self.bucket}': {e}")

    def _sanitize_filename(self, filename: Optional[str]) -> str:
        """Sanitize filename to prevent directory traversal and special character injection."""
        if not filename:
            return "unnamed_document"
        name = os.path.basename(filename)
        clean = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", name)
        return clean[:200]

    async def _stream_and_validate_upload(
        self,
        file: UploadFile
    ) -> Tuple[str, str, int, str, str]:
        """
        Streams uploaded file to a temporary file on disk with strict 50 MiB bounding.
        Calculates SHA-256 while streaming.
        Validates extension, binary magic signatures, archive safety, and plain text encoding.
        Returns: (temp_path, sanitized_filename, total_bytes, mime_type, content_hash)
        """
        raw_filename = file.filename or "upload"
        sanitized_filename = self._sanitize_filename(raw_filename)
        _, ext = os.path.splitext(sanitized_filename)
        ext = ext.lower()

        if ext not in self.allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{ext}'. Allowed formats: {', '.join(sorted(self.allowed_extensions))}."
            )

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        temp_path = temp_file.name
        total_bytes = 0
        header_bytes = b""
        hasher = hashlib.sha256()

        t0_stream = time.perf_counter()
        try:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > self.max_file_size:
                    temp_file.close()
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="File exceeds the maximum allowed size of 50 MB."
                    )
                if len(header_bytes) < 32:
                    header_bytes += chunk[: 32 - len(header_bytes)]
                hasher.update(chunk)
                temp_file.write(chunk)

            temp_file.flush()
            temp_file.close()

            if total_bytes == 0:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Empty file cannot be uploaded."
                )

            # Validate binary magic signatures & structure
            if ext == ".pdf":
                if not header_bytes.startswith(b"%PDF-"):
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Corrupt or invalid PDF file: missing %PDF- magic signature."
                    )
            elif ext == ".png":
                if not header_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Corrupt or invalid PNG file: missing PNG magic signature."
                    )
            elif ext in {".docx", ".pptx"}:
                if not header_bytes.startswith(b"PK\x03\x04"):
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Corrupt or invalid {ext.upper()[1:]} file: missing PK zip header signature."
                    )
                zip_err = inspect_zip_safety(temp_path, ext)
                if zip_err:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=zip_err
                    )
            elif ext == ".txt":
                # Verify plain text doesn't contain null bytes and is decodable
                if b"\x00" in header_bytes:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Corrupt or invalid text file: binary content detected in .txt file."
                    )

            mime_type = file.content_type or "application/octet-stream"
            content_hash = hasher.hexdigest()

            upload_hash_ms = (time.perf_counter() - t0_stream) * 1000.0
            record_perf_metric(
                stage="attachment_upload_and_hash",
                duration_ms=upload_hash_ms,
                file_size_bytes=total_bytes,
                filename_sanitized=sanitized_filename,
                mime_type=mime_type
            )

            return temp_path, sanitized_filename, total_bytes, mime_type, content_hash

        except HTTPException:
            raise
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
            logger.error(f"Error during streaming upload validation: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to stream and validate uploaded file."
            )

    def _extract_plain_text(self, file_path: str) -> Tuple[Optional[str], Dict[str, Any], Optional[str]]:
        """Extract text from plain text (.txt) files with UTF-8 / latin-1 fallback."""
        try:
            with open(file_path, "rb") as f:
                raw_bytes = f.read()

            try:
                text = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = raw_bytes.decode("latin-1", errors="replace")

            text = text.strip()
            if not text or len(text) < 5:
                return None, {}, "Plain text file is empty or contains insufficient text."

            metadata = {
                "char_count": len(text),
                "extractor": "text_plain"
            }

            if len(text) > MAX_EXTRACTED_TEXT_LENGTH:
                metadata["truncated"] = True
                metadata["original_char_count"] = len(text)
                metadata["truncated_char_count"] = MAX_EXTRACTED_TEXT_LENGTH
                keep_len = MAX_EXTRACTED_TEXT_LENGTH - len(TRUNCATION_MARKER)
                text = text[:keep_len] + TRUNCATION_MARKER
            else:
                metadata["truncated"] = False
                metadata["original_char_count"] = len(text)

            return text, metadata, None
        except Exception as e:
            logger.error(f"Failed to read text file: {e}")
            return None, {}, f"Extraction failed: {str(e)}"

    def extract_content(
        self,
        file_path: str,
        ext: str
    ) -> Tuple[Optional[str], Dict[str, Any], Optional[str]]:
        """
        Extract readable textual content from the document file on disk.
        Delegates .pdf, .png, .docx, .pptx to lecture_notes_service.extract_content.
        Handles .txt directly.
        Returns: (extracted_text, metadata, error_msg)
        """
        ext = ext.lower()
        if ext == ".txt":
            return self._extract_plain_text(file_path)
        else:
            return lecture_notes_service.extract_content(file_path, ext)

    async def extract_content_async(
        self,
        file_path: str,
        ext: str
    ) -> Tuple[Optional[str], Dict[str, Any], Optional[str]]:
        """Run blocking extraction off the main asyncio event loop using ThreadPoolExecutor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.executor,
            self.extract_content,
            file_path,
            ext
        )

    def validate_subject_association(
        self,
        db: Session,
        subject_id: Optional[int],
        student: User
    ) -> Optional[Subject]:
        """
        Validates optional subject alignment.
        Ensures the subject exists, is active, and belongs to the student's authorized department.
        """
        if subject_id is None:
            return None

        subject = db.query(Subject).filter(
            Subject.id == subject_id,
            Subject.is_active == True
        ).first()

        if not subject:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subject with ID {subject_id} not found or inactive."
            )

        student_dept = _get_user_department(student)
        if not student_dept or _normalize_dept(student_dept) != _normalize_dept(subject.department):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Subject belongs to department '{subject.department}'."
            )

        return subject

    def check_student_quotas(
        self,
        db: Session,
        student_id: int,
        new_file_size: int
    ) -> None:
        """
        Enforce per-student quota:
        - Max 15 active documents
        - Max 200 MiB total active storage
        """
        stats = db.query(
            func.count(StudentStudyDocument.id).label("doc_count"),
            func.coalesce(func.sum(StudentStudyDocument.file_size), 0).label("total_storage")
        ).filter(
            StudentStudyDocument.student_id == student_id,
            StudentStudyDocument.is_active == True
        ).first()

        doc_count = stats.doc_count if stats else 0
        total_storage = stats.total_storage if stats else 0

        if doc_count >= MAX_STUDENT_ACTIVE_DOCS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document quota exceeded: Students may keep up to {MAX_STUDENT_ACTIVE_DOCS} active study documents."
            )

        if total_storage + new_file_size > MAX_STUDENT_TOTAL_STORAGE:
            max_mb = MAX_STUDENT_TOTAL_STORAGE // (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Storage quota exceeded: Total active documents cannot exceed {max_mb} MB."
            )

    def check_duplicate(
        self,
        db: Session,
        student_id: int,
        content_hash: str
    ) -> None:
        """
        Detect identical file uploads by the same student among active documents.
        Identical files uploaded by different students are permitted.
        """
        existing = db.query(StudentStudyDocument).filter(
            StudentStudyDocument.student_id == student_id,
            StudentStudyDocument.content_hash == content_hash,
            StudentStudyDocument.is_active == True
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"You have already uploaded this document as '{existing.title}'."
            )

    async def upload_and_ingest_document(
        self,
        db: Session,
        file: UploadFile,
        student: User,
        title: str,
        description: Optional[str] = None,
        subject_id: Optional[int] = None,
        reuse_existing: bool = False
    ) -> StudentStudyDocument:
        """
        Stream upload, validate, check quotas & duplicates under advisory lock,
        extract, and persist a private student document.
        Supports reuse_existing to avoid duplicate records when attaching existing files.
        Uses a short atomic reservation transaction to serialize quota checks for the same student
        without holding the database transaction open during MinIO I/O or text extraction.
        Cleans up temporary disk files and MinIO storage if a failure occurs.
        """
        if not title or not title.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Title is required and cannot be empty."
            )

        # 1. Validate subject association if supplied
        subject = self.validate_subject_association(db, subject_id, student)

        # 2. Stream and validate upload to temporary disk (50 MiB limit, magic bytes, archive safety)
        temp_path, sanitized_filename, file_size, mime_type, content_hash = await self._stream_and_validate_upload(file)
        _, ext = os.path.splitext(sanitized_filename)

        doc_uuid = uuid.uuid4().hex
        object_key = f"student_{student.id}/{doc_uuid}_{sanitized_filename}"

        # 3. Short atomic reservation transaction under per-student advisory lock
        # Serializes quota checks for the SAME student while different students run concurrently
        try:
            _acquire_student_advisory_lock(db, student.id)
            if reuse_existing:
                existing = db.query(StudentStudyDocument).filter(
                    StudentStudyDocument.student_id == student.id,
                    StudentStudyDocument.content_hash == content_hash,
                    StudentStudyDocument.is_active == True
                ).first()
                if existing:
                    if os.path.exists(temp_path):
                        try:
                            os.unlink(temp_path)
                        except Exception:
                            pass
                    logger.info(f"♻️ Reusing existing active student study document {existing.id} for student {student.id}")
                    return existing
            else:
                self.check_duplicate(db, student.id, content_hash)

            self.check_student_quotas(db, student.id, file_size)

            student_doc = StudentStudyDocument(
                student_id=student.id,
                subject_id=subject.id if subject else None,
                title=title.strip(),
                description=description.strip() if description else None,
                original_filename=sanitized_filename,
                file_size=file_size,
                mime_type=mime_type,
                content_hash=content_hash,
                minio_bucket=self.bucket,
                minio_object_key=object_key,
                is_active=True,
                processing_status=StudentDocProcessingStatus.PROCESSING,
                indexing_status=StudentDocIndexingStatus.NOT_INDEXED,
                extracted_text=None,
                extraction_error=None,
                extraction_metadata={},
                indexed_chunk_count=0
            )
            db.add(student_doc)
            db.commit()
            db.refresh(student_doc)
        except Exception:
            db.rollback()
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
            raise

        # 4. External operations executed outside the database transaction:
        # A. Upload to MinIO
        minio_uploaded = False
        try:
            self.ensure_bucket()
            minio_client.upload_file_from_path(
                bucket=self.bucket,
                object_key=object_key,
                file_path=temp_path,
                content_type=mime_type
            )
            minio_uploaded = True
        except Exception as minio_err:
            logger.error(f"MinIO upload failed for student doc {student_doc.id}: {minio_err}")
            try:
                db.delete(student_doc)
                db.commit()
            except Exception:
                db.rollback()
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Storage error occurred while creating student study document."
            )

        # B. Text extraction in thread pool (outside event loop)
        try:
            t0_extract = time.perf_counter()
            extracted_text, metadata, error_msg = await self.extract_content_async(temp_path, ext)
            extract_duration_ms = (time.perf_counter() - t0_extract) * 1000.0

            record_perf_metric(
                stage="text_extraction",
                duration_ms=extract_duration_ms,
                file_ext=ext,
                extracted_char_count=len(extracted_text or "") if extracted_text else 0,
                page_count=metadata.get("page_count", 1) if isinstance(metadata, dict) else 1,
                ocr_triggered=bool(isinstance(metadata, dict) and metadata.get("ocr_pages_used", 0) > 0),
                ocr_pages_count=metadata.get("ocr_pages_used", 0) if isinstance(metadata, dict) else 0,
                ocr_duration_ms=metadata.get("ocr_duration_ms", 0.0) if isinstance(metadata, dict) else 0.0
            )

            # Re-fetch fresh doc instance in case session state changed
            fresh_doc = db.query(StudentStudyDocument).filter(StudentStudyDocument.id == student_doc.id).first()
            if not fresh_doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document record missing after extraction."
                )

            if error_msg or not extracted_text:
                fresh_doc.processing_status = StudentDocProcessingStatus.FAILED
                fresh_doc.extraction_error = (error_msg or "Extraction yielded empty or unparseable text.")[:500]
                fresh_doc.extracted_text = None
                fresh_doc.extraction_metadata = metadata or {}
            else:
                fresh_doc.processing_status = StudentDocProcessingStatus.EXTRACTED
                fresh_doc.extraction_error = None
                fresh_doc.extracted_text = extracted_text
                fresh_doc.extraction_metadata = metadata or {}

            fresh_doc.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(fresh_doc)

            logger.info(
                f"✅ Student document {fresh_doc.id} ('{fresh_doc.title}') ingested "
                f"for student {student.id} (status: {fresh_doc.processing_status.value})"
            )
            return fresh_doc

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error finalizing student document {student_doc.id}: {e}", exc_info=True)
            try:
                fresh_doc = db.query(StudentStudyDocument).filter(StudentStudyDocument.id == student_doc.id).first()
                if fresh_doc:
                    fresh_doc.processing_status = StudentDocProcessingStatus.FAILED
                    fresh_doc.extraction_error = f"Finalization error: {str(e)[:400]}"
                    db.commit()
            except Exception:
                db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while finalizing student study document."
            )
        finally:
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

    async def retry_document_processing(
        self,
        db: Session,
        document_id: int,
        student_id: int
    ) -> StudentStudyDocument:
        """
        Retry text extraction for an eligible failed document by downloading original binary from MinIO.
        Atomically claims the document via conditional update to prevent concurrent duplicate extractions.
        """
        doc = db.query(StudentStudyDocument).filter(
            StudentStudyDocument.id == document_id,
            StudentStudyDocument.student_id == student_id,
            StudentStudyDocument.is_active == True
        ).first()

        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student study document with ID {document_id} not found."
            )

        now = datetime.now(timezone.utc)
        stale_cutoff = now - timedelta(seconds=60)
        is_stale = (doc.updated_at is None) or (
            doc.updated_at.replace(tzinfo=timezone.utc) if doc.updated_at.tzinfo is None else doc.updated_at
        ) < stale_cutoff

        if doc.processing_status == StudentDocProcessingStatus.PROCESSING and not is_stale:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Document {document_id} is currently being processed by another task."
            )

        # Atomic claim (allow claiming if not PROCESSING or if stale)
        claim_filter = [
            StudentStudyDocument.id == document_id,
            StudentStudyDocument.student_id == student_id,
        ]
        if not is_stale:
            claim_filter.append(StudentStudyDocument.processing_status != StudentDocProcessingStatus.PROCESSING)

        rows_claimed = db.query(StudentStudyDocument).filter(*claim_filter).update({
            StudentStudyDocument.processing_status: StudentDocProcessingStatus.PROCESSING,
            StudentStudyDocument.updated_at: now
        }, synchronize_session=False)
        db.commit()

        if rows_claimed == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Document {document_id} cannot be claimed for retry processing."
            )

        temp_path = None
        try:
            _, ext = os.path.splitext(doc.original_filename)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            temp_path = temp_file.name
            temp_file.close()

            minio_client.download_file_to_path(doc.minio_bucket, doc.minio_object_key, temp_path)

            extracted_text, metadata, error_msg = await self.extract_content_async(temp_path, ext)

            fresh_doc = db.query(StudentStudyDocument).filter(StudentStudyDocument.id == document_id).first()
            if not fresh_doc:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document removed during retry.")

            if error_msg or not extracted_text:
                fresh_doc.processing_status = StudentDocProcessingStatus.FAILED
                fresh_doc.extraction_error = (error_msg or "Extraction yielded empty or unparseable text.")[:500]
                fresh_doc.extracted_text = None
            else:
                fresh_doc.processing_status = StudentDocProcessingStatus.EXTRACTED
                fresh_doc.extracted_text = extracted_text
                fresh_doc.extraction_error = None
                fresh_doc.extraction_metadata = metadata

            fresh_doc.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(fresh_doc)
            return fresh_doc

        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to retry extraction for student document {document_id}: {e}")
            try:
                db.query(StudentStudyDocument).filter(StudentStudyDocument.id == document_id).update({
                    StudentStudyDocument.processing_status: StudentDocProcessingStatus.FAILED,
                    StudentStudyDocument.extraction_error: f"Retry extraction error: {str(e)[:400]}",
                    StudentStudyDocument.updated_at: datetime.now(timezone.utc)
                }, synchronize_session=False)
                db.commit()
            except Exception:
                db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retry processing for document {document_id}: {str(e)}"
            )
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

    def delete_document(
        self,
        db: Session,
        document_id: int,
        student_id: int
    ) -> bool:
        """
        Safely delete a private student study document:
        1. Verifies ownership (student_id == student_id).
        2. Immediately deactivates the document (is_active = False) to block retrieval,
           free quota, and release duplicate-content partial unique constraint.
        3. Deletes Qdrant vector chunks (scoped by source_type='student_upload' and student_study_document_id).
        4. Deletes original binary object from MinIO.
        5. If BOTH external cleanups succeed, permanently deletes the database record.
        6. If external cleanup fails (Qdrant or MinIO outage), preserves the database row
           with is_active=False and records cleanup errors in extraction_metadata so
           cleanup can be safely retried without losing the storage key or document provenance.
        """
        doc = db.query(StudentStudyDocument).filter(
            StudentStudyDocument.id == document_id,
            StudentStudyDocument.student_id == student_id
        ).first()

        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student study document with ID {document_id} not found."
            )

        # 1. Immediate cut-off: mark inactive to block retrieval and release quota/hash immediately
        if doc.is_active:
            doc.is_active = False
            doc.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(doc)

        bucket = doc.minio_bucket
        object_key = doc.minio_object_key
        qdrant_cleaned = False
        minio_cleaned = False
        cleanup_errors = []

        # 2. Delete Qdrant vector chunks (scoped to source_type='student_upload' and student_study_document_id)
        try:
            from .student_documents_indexing_service import student_documents_indexing_service
            student_documents_indexing_service.delete_document_chunks(doc.id)
            qdrant_cleaned = True
        except Exception as q_err:
            logger.error(f"Failed to delete Qdrant points for student doc {doc.id}: {q_err}")
            cleanup_errors.append(f"Qdrant: {str(q_err)[:200]}")

        # 3. Delete binary object from MinIO
        try:
            minio_client.delete_file(bucket, object_key)
            minio_cleaned = True
        except Exception as m_err:
            logger.error(f"Failed to delete MinIO object {bucket}/{object_key}: {m_err}")
            cleanup_errors.append(f"MinIO: {str(m_err)[:200]}")

        # 4. Handle cleanup outcome
        if qdrant_cleaned and minio_cleaned:
            # Both external resources successfully cleaned up: permanently remove DB row
            db.delete(doc)
            db.commit()
            logger.info(f"🗑️ Fully deleted student study document {document_id} (DB, MinIO, and Qdrant purged)")
            return True
        else:
            # External cleanup failed: preserve DB row with is_active=False and record error details
            meta = dict(doc.extraction_metadata or {})
            meta["cleanup_pending"] = True
            meta["cleanup_errors"] = cleanup_errors
            meta["cleanup_attempted_at"] = datetime.now(timezone.utc).isoformat()
            meta["qdrant_cleaned"] = qdrant_cleaned
            meta["minio_cleaned"] = minio_cleaned
            doc.extraction_metadata = meta
            db.commit()

            err_summary = "; ".join(cleanup_errors)
            logger.warning(
                f"⚠️ Student doc {document_id} deactivated but external cleanup incomplete ({err_summary}). "
                f"Record preserved for retry."
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    f"Document {document_id} deactivated, but external resource cleanup failed: "
                    f"{err_summary}. Record preserved for cleanup retry."
                )
            )

    def retry_document_cleanup(
        self,
        db: Session,
        document_id: int,
        student_id: int
    ) -> bool:
        """
        Retry external cleanup for a deactivated document whose initial cleanup failed.
        Invokes delete_document to re-attempt Qdrant and MinIO deletion and permanently purge the row.
        """
        return self.delete_document(db, document_id, student_id)


# Singleton instance
student_documents_service = StudentDocumentsService()
