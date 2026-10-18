"""
Student Documents Indexing Service (Qdrant Vector RAG Engine)

Manages vector indexing for private student study documents
in the shared Study Buddy Qdrant collection ('study_buddy_chunks').

Core Guarantees:
- Strict vector isolation using source_type='student_upload' and student_id payload filter
- Reuses 384-dimensional 'all-MiniLM-L6-v2' vector embedding model
- Deterministic UUIDv5 chunk point IDs for idempotent upserts
- Enforces strict PostgreSQL eligibility gates (owner, is_active, EXTRACTED)
- Atomic concurrency protection preventing duplicate indexing processes
- Safe chunk replacement: removes obsolete vectors upon reindexing or deletion
- Zero modification to existing syllabus or lecturer-note points
"""

import hashlib
import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from qdrant_client.http import models

import time
from ..core.study_buddy_timing import record_perf_metric
from ..core.config import settings
from .embedding_service import embedding_service
from .file_storage.qdrant_client import qdrant_client
from ..models.study_buddy import (
    Subject,
    StudentStudyDocument,
    StudentDocProcessingStatus,
    StudentDocIndexingStatus,
)

logger = logging.getLogger(__name__)

STUDY_BUDDY_COLLECTION = "study_buddy_chunks"
STUDY_BUDDY_VECTOR_SIZE = 384
MAX_CHUNK_CHARS = 800
CHUNK_OVERLAP_CHARS = 120


class StudentDocumentsIndexingService:
    """Dedicated Qdrant vector indexing service for private student study documents."""

    def __init__(self):
        self.collection_name = STUDY_BUDDY_COLLECTION
        self.vector_size = STUDY_BUDDY_VECTOR_SIZE
        self._collection_verified = False

    def ensure_collection(self) -> bool:
        """
        Idempotently verify or initialize the dedicated 'study_buddy_chunks' collection.
        Creates payload indexes needed for private student document filtering.
        """
        if self._collection_verified:
            return True

        if not qdrant_client.client:
            logger.error("Qdrant client is not available")
            return False

        try:
            collections = qdrant_client.client.get_collections().collections
            existing_names = [c.name for c in collections]

            if self.collection_name not in existing_names:
                qdrant_client.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=self.vector_size,
                        distance=models.Distance.COSINE
                    ),
                    optimizers_config=models.OptimizersConfigDiff(
                        default_segment_number=2,
                        indexing_threshold=10000,
                        flush_interval_sec=5
                    ),
                    hnsw_config=models.HnswConfigDiff(
                        m=16,
                        ef_construct=100,
                        full_scan_threshold=10000
                    )
                )
                logger.info(f"✅ Created dedicated Qdrant collection: '{self.collection_name}' ({self.vector_size}-dim COSINE)")
            else:
                info = qdrant_client.client.get_collection(self.collection_name)
                current_size = info.config.params.vectors.size
                if current_size != self.vector_size:
                    raise ValueError(
                        f"Collection '{self.collection_name}' vector dimension is {current_size}, "
                        f"expected {self.vector_size}."
                    )
                logger.debug(f"📁 Qdrant collection '{self.collection_name}' verified ({current_size}-dim)")

            self._ensure_payload_indexes()
            self._collection_verified = True
            return True
        except Exception as e:
            logger.error(f"❌ Failed to ensure collection '{self.collection_name}': {e}")
            return False

    def _ensure_payload_indexes(self):
        """Create indexes on student document payload fields for high-performance filtering."""
        fields = [
            ("source_type", models.PayloadSchemaType.KEYWORD),
            ("student_study_document_id", models.PayloadSchemaType.INTEGER),
            ("student_id", models.PayloadSchemaType.INTEGER),
            ("subject_id", models.PayloadSchemaType.INTEGER),
            ("chunk_index", models.PayloadSchemaType.INTEGER),
            ("content_hash", models.PayloadSchemaType.KEYWORD),
        ]
        for field_name, field_type in fields:
            try:
                qdrant_client.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=field_type
                )
                logger.debug(f"Created payload index for '{field_name}' in '{self.collection_name}'")
            except Exception as e:
                logger.debug(f"Payload index notice for '{field_name}': {e}")

    def is_eligible_for_indexing(self, doc: StudentStudyDocument) -> Tuple[bool, str]:
        """
        Verify indexing eligibility from PostgreSQL:
        Must be active (is_active is True), processing_status is EXTRACTED,
        extracted text is non-empty, and subject is active if associated.
        """
        if not doc:
            return False, "Student study document record not found."
        if not doc.is_active:
            return False, "Document is inactive or deleted."
        if doc.processing_status != StudentDocProcessingStatus.EXTRACTED:
            return False, f"Text extraction not completed (processing_status: {doc.processing_status.value})."
        if not doc.extracted_text or not doc.extracted_text.strip():
            return False, "Document contains no extracted text to index."
        if doc.subject_id and (not doc.subject or not doc.subject.is_active):
            return False, "Associated academic subject is inactive or not found."
        return True, "Eligible"

    def create_chunks(self, doc: StudentStudyDocument) -> List[Dict[str, Any]]:
        """
        Produce structured, provenance-linked chunks from a student document's extracted text.
        Includes title and optional subject context in each chunk header for optimal semantic search.
        Uses sliding bounded paragraphs with conservative overlap.
        """
        raw_text = (doc.extracted_text or "").strip()
        if not raw_text:
            return []

        header_parts = ["[Student Document]"]
        if doc.subject:
            header_parts.append(f"{doc.subject.code} - {doc.subject.name}")
        header_parts.append(f"Title: {doc.title}")

        chunk_header = " | ".join(header_parts) + "\n"

        # Split on paragraph or slide/page double newlines
        paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [p.strip() for p in raw_text.split("\n") if p.strip()]

        chunks = []
        chunk_index = 1
        current_body = ""

        for para in paragraphs:
            if current_body and (len(current_body) + len(para) + 1 > MAX_CHUNK_CHARS):
                full_chunk_text = (chunk_header + current_body).strip()
                content_hash = hashlib.sha256(full_chunk_text.encode("utf-8")).hexdigest()
                point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"student_study_doc_{doc.id}_chunk_{chunk_index}"))

                chunks.append({
                    "point_id": point_uuid,
                    "text": full_chunk_text,
                    "payload": {
                        "text": full_chunk_text,
                        "source_type": "student_upload",
                        "student_study_document_id": doc.id,
                        "student_id": doc.student_id,
                        "subject_id": doc.subject_id,
                        "subject_code": doc.subject.code if doc.subject else None,
                        "subject_name": doc.subject.name if doc.subject else None,
                        "department": doc.subject.department if doc.subject else None,
                        "title": doc.title,
                        "original_filename": doc.original_filename,
                        "mime_type": doc.mime_type,
                        "chunk_index": chunk_index,
                        "content_hash": content_hash,
                        "source_page": None,
                        "indexed_at": datetime.now(timezone.utc).isoformat()
                    }
                })
                chunk_index += 1
                overlap_text = current_body[-CHUNK_OVERLAP_CHARS:].strip() if len(current_body) > CHUNK_OVERLAP_CHARS else ""
                current_body = (overlap_text + " " + para).strip() if overlap_text else para
            else:
                if current_body:
                    current_body += "\n" + para
                else:
                    current_body = para

        # Final trailing chunk
        if current_body.strip():
            full_chunk_text = (chunk_header + current_body).strip()
            content_hash = hashlib.sha256(full_chunk_text.encode("utf-8")).hexdigest()
            point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"student_study_doc_{doc.id}_chunk_{chunk_index}"))

            chunks.append({
                "point_id": point_uuid,
                "text": full_chunk_text,
                "payload": {
                    "text": full_chunk_text,
                    "source_type": "student_upload",
                    "student_study_document_id": doc.id,
                    "student_id": doc.student_id,
                    "subject_id": doc.subject_id,
                    "subject_code": doc.subject.code if doc.subject else None,
                    "subject_name": doc.subject.name if doc.subject else None,
                    "department": doc.subject.department if doc.subject else None,
                    "title": doc.title,
                    "original_filename": doc.original_filename,
                    "mime_type": doc.mime_type,
                    "chunk_index": chunk_index,
                    "content_hash": content_hash,
                    "source_page": None,
                    "indexed_at": datetime.now(timezone.utc).isoformat()
                }
            })

        return chunks

    def delete_document_chunks(self, document_id: int) -> int:
        """
        Safely delete all Qdrant vector points for a given student study document.
        Uses scoped filter: source_type='student_upload' AND student_study_document_id=document_id.
        Never affects syllabus chunks or lecture notes.
        """
        if not self.ensure_collection():
            return 0

        try:
            filter_doc = models.Filter(
                must=[
                    models.FieldCondition(
                        key="source_type",
                        match=models.MatchValue(value="student_upload")
                    ),
                    models.FieldCondition(
                        key="student_study_document_id",
                        match=models.MatchValue(value=document_id)
                    )
                ]
            )

            qdrant_client.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=filter_doc
                )
            )
            logger.info(f"🗑️ Deleted Qdrant points for student study document {document_id}")
            return 1
        except Exception as e:
            logger.error(f"❌ Failed to delete Qdrant points for student study document {document_id}: {e}")
            raise

    def index_student_document(self, db: Session, document_id: int, student_id: int) -> Dict[str, Any]:
        """
        Idempotent student document indexing pipeline:
        1. Checks eligibility immediately from PostgreSQL.
        2. Atomically claims the document using conditional update.
        3. Ensures collection exists and verifies 384-dimensional embedding model.
        4. Removes obsolete points for this document from Qdrant.
        5. Generates structured chunks with stable UUIDv5 IDs and metadata.
        6. Generates embeddings and upserts points to Qdrant.
        7. Persists INDEXED status and actual chunk count in PostgreSQL.
        8. On failure, cleans up partial points and updates status to FAILED with sanitized error.
        """
        # 1. Fetch document and revalidate eligibility immediately
        doc = db.query(StudentStudyDocument).filter(
            StudentStudyDocument.id == document_id,
            StudentStudyDocument.student_id == student_id
        ).first()

        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student study document with ID {document_id} not found."
            )

        eligible, reason = self.is_eligible_for_indexing(doc)
        if not eligible:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document {document_id} is not eligible for indexing: {reason}"
            )

        # 2. Concurrency protection: conditional update to claim document
        rows_claimed = db.query(StudentStudyDocument).filter(
            StudentStudyDocument.id == document_id,
            StudentStudyDocument.student_id == student_id,
            StudentStudyDocument.is_active == True,
            StudentStudyDocument.processing_status == StudentDocProcessingStatus.EXTRACTED,
            StudentStudyDocument.indexing_status != StudentDocIndexingStatus.INDEXING
        ).update({
            StudentStudyDocument.indexing_status: StudentDocIndexingStatus.INDEXING,
            StudentStudyDocument.updated_at: datetime.now(timezone.utc)
        }, synchronize_session=False)
        db.commit()

        if rows_claimed == 0:
            current = db.query(StudentStudyDocument).filter(StudentStudyDocument.id == document_id).first()
            if current and current.indexing_status == StudentDocIndexingStatus.INDEXING:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Document {document_id} is currently being indexed by another process."
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document {document_id} cannot be claimed for indexing."
            )

        # 3. Ensure Qdrant collection is ready
        t0_indexing = time.perf_counter()
        t0_ensure = time.perf_counter()
        if not self.ensure_collection():
            self._set_failed_status(db, document_id, "Qdrant vector collection unavailable.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Qdrant vector collection unavailable."
            )
        ensure_col_ms = (time.perf_counter() - t0_ensure) * 1000.0

        dim = embedding_service.get_embedding_dimension()
        if dim != self.vector_size:
            err = f"Embedding model dimension {dim} does not match collection configuration {self.vector_size}."
            self._set_failed_status(db, document_id, err)
            raise ValueError(err)

        try:
            # 4. Remove any existing chunks for this document (ensures clean replacement)
            self.delete_document_chunks(document_id)

            # Re-read fresh document data for chunking
            fresh_doc = db.query(StudentStudyDocument).filter(StudentStudyDocument.id == document_id).first()
            if not fresh_doc:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document removed during indexing.")

            # 5. Generate chunks
            t0_chunk = time.perf_counter()
            chunks = self.create_chunks(fresh_doc)
            chunk_ms = (time.perf_counter() - t0_chunk) * 1000.0
            if not chunks:
                err_msg = "No valid text chunks generated for indexing."
                self._set_failed_status(db, document_id, err_msg)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Vector indexing aborted: {err_msg}"
                )

            # 6. Generate embeddings using shared embedding service
            t0_embed = time.perf_counter()
            texts = [c["text"] for c in chunks]
            embeddings = embedding_service.embed_texts(texts)
            embed_ms = (time.perf_counter() - t0_embed) * 1000.0
            if not embeddings or len(embeddings) != len(chunks):
                raise ValueError("Embedding generation returned incomplete or empty vectors.")

            record_perf_metric(
                stage="chunking_and_embedding",
                duration_ms=chunk_ms + embed_ms,
                chunk_count=len(chunks),
                chunking_ms=round(chunk_ms, 2),
                embedding_ms=round(embed_ms, 2)
            )

            # 7. Construct Qdrant points
            points = []
            for i, chunk in enumerate(chunks):
                emb = embeddings[i]
                if not emb or len(emb) != self.vector_size:
                    raise ValueError(f"Embedding generation failed for chunk {i}: invalid vector dimension ({len(emb) if emb else 0}).")

                points.append(
                    models.PointStruct(
                        id=chunk["point_id"],
                        vector=emb,
                        payload=chunk["payload"]
                    )
                )

            # 8. Upsert points into Qdrant
            t0_upsert = time.perf_counter()
            qdrant_client.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            upsert_ms = (time.perf_counter() - t0_upsert) * 1000.0

            # 9. Update PostgreSQL metadata
            t0_db = time.perf_counter()
            meta = dict(fresh_doc.extraction_metadata or {})
            meta["indexing_error"] = None
            meta["indexed_at"] = datetime.now(timezone.utc).isoformat()

            fresh_doc.indexing_status = StudentDocIndexingStatus.INDEXED
            fresh_doc.indexed_chunk_count = len(points)
            fresh_doc.extraction_metadata = meta
            db.commit()
            db.refresh(fresh_doc)
            db_ms = (time.perf_counter() - t0_db) * 1000.0

            total_idx_ms = (time.perf_counter() - t0_indexing) * 1000.0
            record_perf_metric(
                stage="qdrant_indexing",
                duration_ms=total_idx_ms,
                chunks_indexed=len(points),
                collection_ensure_ms=round(ensure_col_ms, 2),
                upsert_ms=round(upsert_ms, 2),
                db_commit_ms=round(db_ms, 2)
            )

            logger.info(f"✅ Successfully indexed {len(points)} chunks for student document {document_id} in Qdrant")
            return {
                "status": "SUCCESS",
                "student_study_document_id": document_id,
                "chunks_indexed": len(points),
                "indexed_at": meta["indexed_at"]
            }

        except HTTPException:
            self._cleanup_partial_vectors(document_id)
            raise
        except Exception as e:
            logger.error(f"❌ Indexing failed for student document {document_id}: {e}", exc_info=True)
            self._cleanup_partial_vectors(document_id)
            self._set_failed_status(db, document_id, str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Vector indexing failed for student document {document_id}: {str(e)}"
            )

    def _cleanup_partial_vectors(self, document_id: int):
        """Clean up partial vectors on indexing abort or failure."""
        try:
            self.delete_document_chunks(document_id)
        except Exception as e:
            logger.warning(f"Failed to cleanup partial Qdrant points for student doc {document_id}: {e}")

    def _set_failed_status(self, db: Session, document_id: int, error_message: str):
        """Update document to FAILED indexing status with sanitized error metadata."""
        try:
            doc = db.query(StudentStudyDocument).filter(StudentStudyDocument.id == document_id).first()
            if doc:
                meta = dict(doc.extraction_metadata or {})
                meta["indexing_error"] = error_message[:500]
                doc.indexing_status = StudentDocIndexingStatus.FAILED
                doc.indexed_chunk_count = 0
                doc.extraction_metadata = meta
                db.commit()
        except Exception as err:
            logger.error(f"Failed to persist FAILED indexing status for student doc {document_id}: {err}")
            db.rollback()


# Singleton instance
student_documents_indexing_service = StudentDocumentsIndexingService()
