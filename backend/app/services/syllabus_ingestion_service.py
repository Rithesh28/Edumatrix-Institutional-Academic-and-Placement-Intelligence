"""
Syllabus Ingestion Service

Handles secure ingestion, validation, MinIO storage, text extraction,
OCR fallback, and conservative unit/topic segmentation for academic syllabi.
"""

import os
import re
import uuid
import logging
import tempfile
from io import BytesIO
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import UploadFile, HTTPException, status

from ..core.config import settings
from ..models.user import User
from ..models.file import File, FileStatus
from ..models.study_buddy import (
    Subject,
    SyllabusDocument,
    SyllabusUnit,
    SyllabusTopic,
    SyllabusProcessingStatus,
    SyllabusReviewStatus
)
from .file_storage.minio_client import minio_client
from .ocr_service import ocr_service

logger = logging.getLogger(__name__)

# Maximum file size: 25 MB
MAX_SYLLABUS_FILE_SIZE = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "application/octet-stream"
}


class SyllabusIngestionService:
    """
    Dedicated service for syllabus document ingestion, extraction, and segmentation.
    """

    def __init__(self):
        self.bucket = "syllabi"

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal or unsafe characters."""
        base = os.path.basename(filename)
        cleaned = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", base)
        return cleaned or f"syllabus_{uuid.uuid4().hex[:8]}.pdf"

    def _validate_file(self, filename: str, content: bytes, content_type: Optional[str]) -> str:
        """
        Validate file extension, size, and magic bytes.
        Returns the sanitized filename.
        """
        if not content or len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty. Uploaded file contains 0 bytes."
            )

        if len(content) > MAX_SYLLABUS_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size of {MAX_SYLLABUS_FILE_SIZE // (1024 * 1024)}MB."
            )

        sanitized_filename = self._sanitize_filename(filename)
        ext = os.path.splitext(sanitized_filename)[1].lower()

        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{ext}'. Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
            )

        # Magic bytes validation
        if ext == ".pdf":
            if not content.startswith(b"%PDF-"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Corrupt or invalid PDF file: missing %PDF- magic signature."
                )
        elif ext == ".docx":
            # DOCX is a zip archive starting with PK\x03\x04
            if not content.startswith(b"PK\x03\x04"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Corrupt or invalid DOCX file: missing PK zip header."
                )
        elif ext == ".txt":
            # Must be decodable text without NUL bytes
            if b"\x00" in content:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid plain text file: binary NUL bytes detected."
                )

        return sanitized_filename

    def _extract_pdf(self, content: bytes) -> Tuple[str, List[Dict[str, Any]], str, Optional[str]]:
        """
        Extract text from PDF page by page with OCR fallback.
        Returns (full_text, pages_data, extractor_used, error_msg).
        """
        pages_data = []
        extractor_used = "pdfplumber"
        error_msg = None

        try:
            import pdfplumber
            with pdfplumber.open(BytesIO(content)) as pdf:
                for idx, page in enumerate(pdf.pages):
                    page_text = page.extract_text() or ""
                    pages_data.append({
                        "page_number": idx + 1,
                        "text": page_text.strip()
                    })
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {e}")
            extractor_used = "PyPDF2"

        full_text = "\n\n".join([p["text"] for p in pages_data if p.get("text")]).strip()

        # Fallback to PyPDF2 if pdfplumber extracted nothing or failed
        if not full_text or len(full_text) < 50:
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(BytesIO(content))
                py_pages = []
                for idx, page in enumerate(reader.pages):
                    pt = page.extract_text() or ""
                    py_pages.append({
                        "page_number": idx + 1,
                        "text": pt.strip()
                    })
                candidate_text = "\n\n".join([p["text"] for p in py_pages if p.get("text")]).strip()
                if len(candidate_text) > len(full_text):
                    pages_data = py_pages
                    full_text = candidate_text
                    extractor_used = "PyPDF2"
            except Exception as e:
                logger.warning(f"PyPDF2 fallback failed: {e}")

        # If still empty or very short, attempt OCR on scanned pages
        if not full_text or len(full_text) < 50:
            logger.info("PDF has minimal text. Attempting OCR on scanned pages...")
            ocr_text = self._ocr_pdf(content)
            if ocr_text and len(ocr_text.strip()) > 30:
                full_text = ocr_text.strip()
                extractor_used = "tesseract_ocr"
                pages_data = [{
                    "page_number": 1,
                    "text": full_text
                }]
            else:
                error_msg = "Scanned/image-based PDF detected with insufficient readable text. OCR did not extract structured content."
                extractor_used = "unreadable_scanned"

        return full_text, pages_data, extractor_used, error_msg

    def _ocr_pdf(self, content: bytes) -> Optional[str]:
        """Perform OCR on a PDF using temporary file and ocr_service."""
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            ocr_result = ocr_service.extract_text_from_scanned_pdf(tmp_path)
            if ocr_result and not ocr_result.startswith("Error:"):
                return ocr_result
        except Exception as e:
            logger.warning(f"PDF OCR failed: {e}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
        return None

    def _extract_docx(self, content: bytes) -> Tuple[str, List[Dict[str, Any]], str, Optional[str]]:
        """
        Extract text from DOCX file.
        Returns (full_text, pages_data, extractor_used, error_msg).
        """
        try:
            import docx
            doc = docx.Document(BytesIO(content))
            sections = []
            para_num = 1
            for p in doc.paragraphs:
                text = p.text.strip()
                if text:
                    sections.append({
                        "section_number": para_num,
                        "text": text
                    })
                    para_num += 1

            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join([c.text.strip() for c in row.cells if c.text.strip()])
                    if row_text:
                        sections.append({
                            "section_number": para_num,
                            "text": row_text
                        })
                        para_num += 1

            full_text = "\n\n".join([s["text"] for s in sections]).strip()
            if not full_text:
                return "", [], "python_docx", "DOCX contains no readable text."
            return full_text, sections, "python_docx", None
        except Exception as e:
            logger.error(f"DOCX extraction failed: {e}")
            return "", [], "python_docx", f"DOCX extraction error: {str(e)}"

    def _extract_txt(self, content: bytes) -> Tuple[str, List[Dict[str, Any]], str, Optional[str]]:
        """
        Extract text from TXT file.
        Returns (full_text, pages_data, extractor_used, error_msg).
        """
        text = None
        for enc in ["utf-8", "utf-8-sig", "latin-1"]:
            try:
                text = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue

        if text is None:
            return "", [], "text", "Unable to decode text file with standard encodings."

        cleaned = text.strip()
        if not cleaned:
            return "", [], "text", "TXT file is empty."

        return cleaned, [{"section_number": 1, "text": cleaned}], "text", None

    def extract_content(self, filename: str, content: bytes) -> Tuple[str, List[Dict[str, Any]], str, Optional[str]]:
        """
        Route file content to appropriate extractor based on extension.
        """
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".pdf":
            return self._extract_pdf(content)
        elif ext == ".docx":
            return self._extract_docx(content)
        elif ext == ".txt":
            return self._extract_txt(content)
        else:
            return "", [], "unknown", f"Unsupported file extension: {ext}"

    def _segment_units_and_topics(
        self,
        full_text: str,
        pages_data: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Conservatively segment text into Units and Topics.
        Recognizes headings such as:
          - Unit 1: / Unit I: / UNIT - 1
          - Module 1 / Module I
          - Chapter 1
        Returns (units_list, is_high_confidence).
        """
        if not full_text or len(full_text.strip()) < 20:
            return [], False

        lines = [line.strip() for line in full_text.splitlines() if line.strip()]

        # Regex for unit headings
        unit_regex = re.compile(
            r"^(?:unit|module|chapter|part)\s*[-:]?\s*([0-9IVXLCDM]+|[A-Z])\s*[:\-\.]?\s*(.*?)$",
            re.IGNORECASE
        )

        detected_units: List[Dict[str, Any]] = []
        current_unit: Optional[Dict[str, Any]] = None
        current_topics: List[Dict[str, Any]] = []

        def _find_page_for_text(snippet: str) -> Optional[int]:
            if not pages_data:
                return None
            snippet_lower = snippet[:40].lower()
            for p in pages_data:
                if snippet_lower in p.get("text", "").lower():
                    return p.get("page_number")
            return None

        for line in lines:
            match = unit_regex.match(line)
            if match:
                # Close previous unit
                if current_unit:
                    current_unit["topics"] = current_topics
                    detected_units.append(current_unit)

                raw_num = match.group(1).strip()
                unit_num = None
                # Try parsing arabic number
                try:
                    unit_num = int(raw_num)
                except ValueError:
                    # Map roman numerals if possible
                    roman_map = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8}
                    unit_num = roman_map.get(raw_num.upper())

                sub_title = match.group(2).strip()
                unit_title = line
                if sub_title:
                    unit_title = f"Unit {raw_num}: {sub_title}"
                else:
                    unit_title = f"Unit {raw_num}"

                page_num = _find_page_for_text(line)

                current_unit = {
                    "unit_number": unit_num,
                    "title": unit_title[:255],
                    "order": len(detected_units) + 1,
                    "description": "",
                    "source_page_start": page_num,
                    "source_page_end": page_num,
                    "source_evidence": line[:500],
                    "topics": []
                }
                current_topics = []
                continue

            # If inside a unit, identify topics or append description
            if current_unit:
                # Check if line looks like a subtopic (numbered, bulleted, or semicolon separated)
                topic_bullet_match = re.match(r"^(?:[0-9]+\.[0-9]+|\([a-z0-9]+\)|[•\-\*])\s*(.*)$", line)
                if topic_bullet_match:
                    t_text = topic_bullet_match.group(1).strip()
                    if t_text:
                        p_num = _find_page_for_text(t_text)
                        current_topics.append({
                            "title": t_text[:255],
                            "order": len(current_topics) + 1,
                            "extracted_text": t_text,
                            "source_page": p_num,
                            "source_evidence": line[:300]
                        })
                else:
                    # Non-bulleted line within unit: either a topic or unit description
                    if len(line) < 120 and not line.endswith("."):
                        p_num = _find_page_for_text(line)
                        current_topics.append({
                            "title": line[:255],
                            "order": len(current_topics) + 1,
                            "extracted_text": line,
                            "source_page": p_num,
                            "source_evidence": line[:300]
                        })
                    else:
                        if current_unit["description"]:
                            current_unit["description"] += " " + line
                        else:
                            current_unit["description"] = line

        # Flush the last unit
        if current_unit:
            current_unit["topics"] = current_topics
            detected_units.append(current_unit)

        # High confidence if at least 1 explicit unit was detected with headings
        if detected_units:
            return detected_units, True

        # Fallback: Conservative unsegmented unit (do not hallucinate fake units!)
        fallback_topics = []
        # Create topics from non-empty lines (up to 15 key points)
        for idx, line in enumerate(lines[:30]):
            if len(line) > 5 and len(line) < 150:
                p_num = _find_page_for_text(line)
                fallback_topics.append({
                    "title": line[:255],
                    "order": len(fallback_topics) + 1,
                    "extracted_text": line,
                    "source_page": p_num,
                    "source_evidence": line[:300]
                })

        unsegmented_unit = [{
            "unit_number": 1,
            "title": "General Syllabus Content",
            "order": 1,
            "description": "Automatic unit segmentation did not identify explicit Unit/Module headings. Content retained in a unified section for manual review.",
            "source_page_start": 1 if pages_data else None,
            "source_page_end": len(pages_data) if pages_data else None,
            "source_evidence": lines[0][:300] if lines else "Unsegmented syllabus text",
            "topics": fallback_topics
        }]
        return unsegmented_unit, False

    async def ingest_syllabus(
        self,
        db: Session,
        subject_id: int,
        file: UploadFile,
        current_user: User,
        title: Optional[str] = None
    ) -> SyllabusDocument:
        """
        End-to-end ingestion pipeline:
        1. Validates subject existence.
        2. Validates file integrity, extension, and magic bytes.
        3. Uploads binary to MinIO.
        4. Extracts text and page provenance.
        5. Conservatively segments into units and topics.
        6. Persists SyllabusDocument, SyllabusUnit, and SyllabusTopic records.
        7. Automatically cleans up MinIO binary if unhandled failure occurs.
        """
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        if not subject:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subject with ID {subject_id} not found."
            )

        # Read content
        content = await file.read()
        sanitized_filename = self._validate_file(file.filename, content, file.content_type)
        mime_type = file.content_type or "application/octet-stream"

        doc_uuid = uuid.uuid4()
        object_key = f"syllabi/{subject.id}/{doc_uuid}_{sanitized_filename}"

        # 1. Upload to MinIO
        uploaded_key = None
        try:
            uploaded_key = minio_client.upload_file(
                bucket=self.bucket,
                object_key=object_key,
                file_data=content,
                content_type=mime_type
            )
        except Exception as e:
            logger.error(f"MinIO syllabus upload failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Storage service unavailable: failed to store syllabus file."
            )

        try:
            # 2. Institutional File tracking record
            file_record = File(
                id=doc_uuid,
                filename=sanitized_filename,
                file_size=len(content),
                mime_type=mime_type,
                bucket=self.bucket,
                object_key=uploaded_key,
                title=title or sanitized_filename,
                description=f"Syllabus document for {subject.code} - {subject.name}",
                department=subject.department,
                file_type="syllabus",
                uploaded_by=current_user.id,
                status=FileStatus.ACTIVE
            )
            db.add(file_record)

            # 3. Determine versioning (preserve historical versions)
            existing_docs = db.query(SyllabusDocument).filter(
                SyllabusDocument.subject_id == subject.id
            ).all()

            version = 1
            if existing_docs:
                version = max(d.version for d in existing_docs) + 1
                for d in existing_docs:
                    d.is_latest = False

            # 4. Extract text
            full_text, pages_data, extractor_used, error_msg = self.extract_content(sanitized_filename, content)

            # 5. Segment units and topics
            units_data, is_high_confidence = self._segment_units_and_topics(full_text, pages_data)

            # Determine statuses
            if error_msg or not full_text or len(full_text.strip()) < 20:
                processing_status = SyllabusProcessingStatus.REVIEW_REQUIRED if full_text else SyllabusProcessingStatus.FAILED
                review_status = SyllabusReviewStatus.DRAFT
                safe_error = error_msg or "Extraction yielded empty or unparseable text."
            elif not is_high_confidence:
                processing_status = SyllabusProcessingStatus.REVIEW_REQUIRED
                review_status = SyllabusReviewStatus.DRAFT
                safe_error = "Syllabus text extracted successfully, but formal unit headings were not detected. Please verify units manually."
            else:
                processing_status = SyllabusProcessingStatus.EXTRACTED
                review_status = SyllabusReviewStatus.PENDING_REVIEW
                safe_error = None

            # 6. Create SyllabusDocument
            syllabus_doc = SyllabusDocument(
                subject_id=subject.id,
                file_id=file_record.id,
                version=version,
                is_latest=True,
                title=title or f"{subject.code} Syllabus v{version}",
                original_filename=sanitized_filename,
                file_size=len(content),
                mime_type=mime_type,
                minio_bucket=self.bucket,
                minio_object_key=uploaded_key,
                uploaded_by_id=current_user.id,
                processing_status=processing_status,
                review_status=review_status,
                is_published=False,  # Must never be visible to students until explicit approval & publish
                extracted_text=full_text if full_text else None,
                extraction_error=safe_error,
                extraction_metadata={
                    "extractor_used": extractor_used,
                    "pages_count": len(pages_data),
                    "is_high_confidence": is_high_confidence,
                    "character_count": len(full_text)
                }
            )
            db.add(syllabus_doc)
            db.flush()  # populate syllabus_doc.id

            # 7. Persist units and topics
            for u_data in units_data:
                unit = SyllabusUnit(
                    document_id=syllabus_doc.id,
                    unit_number=u_data.get("unit_number"),
                    title=u_data.get("title"),
                    order=u_data.get("order", 1),
                    description=u_data.get("description"),
                    source_page_start=u_data.get("source_page_start"),
                    source_page_end=u_data.get("source_page_end"),
                    source_evidence=u_data.get("source_evidence")
                )
                db.add(unit)
                db.flush()

                for t_data in u_data.get("topics", []):
                    topic = SyllabusTopic(
                        unit_id=unit.id,
                        title=t_data.get("title"),
                        order=t_data.get("order", 1),
                        extracted_text=t_data.get("extracted_text"),
                        source_page=t_data.get("source_page"),
                        source_evidence=t_data.get("source_evidence")
                    )
                    db.add(topic)

            db.commit()
            db.refresh(syllabus_doc)
            logger.info(f"✅ Ingested syllabus document {syllabus_doc.id} (v{version}) for subject {subject.code}")
            return syllabus_doc

        except Exception as e:
            db.rollback()
            # Clean up newly uploaded MinIO object on ingestion failure
            if uploaded_key:
                try:
                    minio_client.delete_file(self.bucket, uploaded_key)
                    logger.info(f"🧹 Cleaned up orphaned MinIO object {uploaded_key} after ingestion failure")
                except Exception as cleanup_err:
                    logger.warning(f"Failed to cleanup MinIO object {uploaded_key}: {cleanup_err}")

            if isinstance(e, HTTPException):
                raise e
            logger.error(f"Syllabus ingestion failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Syllabus ingestion encountered an internal processing error: {str(e)}"
            )

    def retry_processing(self, db: Session, document_id: int) -> SyllabusDocument:
        """
        Retry extraction and segmentation on an existing syllabus document
        using the stored binary in MinIO.
        """
        doc = db.query(SyllabusDocument).filter(SyllabusDocument.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Syllabus document not found.")

        try:
            # Download from MinIO
            content = minio_client.download_file(doc.minio_bucket, doc.minio_object_key)
            if not content or len(content) == 0:
                raise ValueError("Downloaded syllabus binary is empty.")

            # Clear existing units (cascades topics)
            db.query(SyllabusUnit).filter(SyllabusUnit.document_id == doc.id).delete()

            # Re-extract
            full_text, pages_data, extractor_used, error_msg = self.extract_content(doc.original_filename, content)
            units_data, is_high_confidence = self._segment_units_and_topics(full_text, pages_data)

            if error_msg or not full_text:
                doc.processing_status = SyllabusProcessingStatus.REVIEW_REQUIRED if full_text else SyllabusProcessingStatus.FAILED
                doc.extraction_error = error_msg or "Retry extraction yielded empty content."
            elif not is_high_confidence:
                doc.processing_status = SyllabusProcessingStatus.REVIEW_REQUIRED
                doc.extraction_error = "Syllabus text re-extracted, but unit headings remain unverified."
            else:
                doc.processing_status = SyllabusProcessingStatus.EXTRACTED
                doc.extraction_error = None

            doc.extracted_text = full_text if full_text else None
            doc.extraction_metadata = {
                "extractor_used": extractor_used,
                "pages_count": len(pages_data),
                "is_high_confidence": is_high_confidence,
                "character_count": len(full_text),
                "retried_at": datetime.now(timezone.utc).isoformat()
            }

            for u_data in units_data:
                unit = SyllabusUnit(
                    document_id=doc.id,
                    unit_number=u_data.get("unit_number"),
                    title=u_data.get("title"),
                    order=u_data.get("order", 1),
                    description=u_data.get("description"),
                    source_page_start=u_data.get("source_page_start"),
                    source_page_end=u_data.get("source_page_end"),
                    source_evidence=u_data.get("source_evidence")
                )
                db.add(unit)
                db.flush()

                for t_data in u_data.get("topics", []):
                    topic = SyllabusTopic(
                        unit_id=unit.id,
                        title=t_data.get("title"),
                        order=t_data.get("order", 1),
                        extracted_text=t_data.get("extracted_text"),
                        source_page=t_data.get("source_page"),
                        source_evidence=t_data.get("source_evidence")
                    )
                    db.add(topic)

            db.commit()
            db.refresh(doc)
            return doc
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Retry processing failed for syllabus doc {document_id}: {e}", exc_info=True)
            # Record failed processing status safely
            try:
                doc.processing_status = SyllabusProcessingStatus.FAILED
                doc.extraction_error = f"Retry extraction encountered an error: {str(e)}"
                db.commit()
            except Exception:
                db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unable to re-process syllabus file: {str(e)}"
            )


syllabus_ingestion_service = SyllabusIngestionService()
