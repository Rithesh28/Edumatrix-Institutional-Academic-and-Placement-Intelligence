"""
Lecture Notes Indexing Service (Qdrant Vector RAG Foundation)

Manages vector indexing for approved and published lecture notes
in the shared Study Buddy Qdrant collection ('study_buddy_chunks').

Preserves the existing 'files' collection untouched, ensures strict vector
isolation from syllabus chunks using source_type='lecture_note', provides
deterministic UUIDv5 chunk point IDs, enforces PostgreSQL eligibility gates,
and provides atomic concurrency protection and safe lifecycle cleanup.
"""

import hashlib
import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from qdrant_client.http import models

from ..core.config import settings
from .embedding_service import embedding_service
from .file_storage.qdrant_client import qdrant_client
from ..models.study_buddy import (
    Subject,
    LectureNote,
    LectureNoteStatus,
    LectureNoteProcessingStatus,
    LectureNoteIndexingStatus,
)

logger = logging.getLogger(__name__)

STUDY_BUDDY_COLLECTION = "study_buddy_chunks"
STUDY_BUDDY_VECTOR_SIZE = 384
MAX_CHUNK_CHARS = 800
CHUNK_OVERLAP_CHARS = 120


class LectureNotesIndexingService:
    """
    Dedicated Qdrant vector indexing service for academic lecture notes.
    """

    def __init__(self):
        self.collection_name = STUDY_BUDDY_COLLECTION
        self.vector_size = STUDY_BUDDY_VECTOR_SIZE
        self._collection_verified = False

    def ensure_collection(self) -> bool:
        """
        Idempotently verify or initialize the dedicated 'study_buddy_chunks' collection.
        Never modifies, recreates, or touches the generic 'files' collection.
        """
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

            # Create payload indexes required for filtered note retrieval
            self._ensure_payload_indexes()
            self._collection_verified = True
            return True
        except Exception as e:
            logger.error(f"❌ Failed to ensure collection '{self.collection_name}': {e}")
            return False

    def _ensure_payload_indexes(self):
        """Create indexes on lecture note payload fields for high-performance filtering."""
        fields = [
            ("source_type", models.PayloadSchemaType.KEYWORD),
            ("lecture_note_id", models.PayloadSchemaType.INTEGER),
            ("subject_id", models.PayloadSchemaType.INTEGER),
            ("department", models.PayloadSchemaType.KEYWORD),
            ("chunk_index", models.PayloadSchemaType.INTEGER),
            ("is_published", models.PayloadSchemaType.KEYWORD),
            ("unit_id", models.PayloadSchemaType.INTEGER),
            ("topic_id", models.PayloadSchemaType.INTEGER),
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
                # Payload index may already exist or cannot be recreated; safe to continue
                logger.debug(f"Payload index notice for '{field_name}': {e}")

    def is_eligible_for_indexing(self, note: LectureNote) -> Tuple[bool, str]:
        """
        Verify indexing eligibility from PostgreSQL:
        Must be PUBLISHED, is_published is True, processing_status is EXTRACTED,
        subject is active, and extracted text is non-empty.
        """
        if not note:
            return False, "Lecture note record not found."
        if note.status != LectureNoteStatus.PUBLISHED or not note.is_published:
            return False, f"Note is not published (status: {note.status.value}, is_published: {note.is_published})."
        if note.processing_status != LectureNoteProcessingStatus.EXTRACTED:
            return False, f"Text extraction not completed (processing_status: {note.processing_status.value})."
        if not note.extracted_text or not note.extracted_text.strip():
            return False, "Lecture note contains no extracted text to index."
        if not note.subject or not note.subject.is_active:
            return False, "Associated subject is inactive or not found."
        return True, "Eligible"

    def create_chunks(self, note: LectureNote) -> List[Dict[str, Any]]:
        """
        Produce structured, provenance-linked chunks from a lecture note's extracted text.
        Includes subject, title, unit/topic context in each chunk header for optimal semantic search.
        Uses sliding bounded paragraphs with conservative overlap.
        """
        raw_text = (note.extracted_text or "").strip()
        if not raw_text:
            return []

        subject = note.subject
        header_parts = [
            f"{subject.code} - {subject.name}",
            f"Lecture Note: {note.title}"
        ]
        if note.unit and note.unit.title:
            header_parts.append(f"Unit: {note.unit.title}")
        if note.topic and note.topic.title:
            header_parts.append(f"Topic: {note.topic.title}")

        chunk_header = " | ".join(header_parts) + "\n"

        # Split on paragraph or slide/page double newlines
        paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [p.strip() for p in raw_text.split("\n") if p.strip()]

        chunks = []
        chunk_index = 1
        current_body = ""

        for para in paragraphs:
            # If adding this paragraph exceeds maximum chunk boundary, finalize current chunk
            if current_body and (len(current_body) + len(para) + 1 > MAX_CHUNK_CHARS):
                full_chunk_text = (chunk_header + current_body).strip()
                content_hash = hashlib.sha256(full_chunk_text.encode("utf-8")).hexdigest()
                point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"lecture_note_{note.id}_chunk_{chunk_index}"))

                chunks.append({
                    "point_id": point_uuid,
                    "text": full_chunk_text,
                    "payload": {
                        "text": full_chunk_text,
                        "source_type": "lecture_note",
                        "lecture_note_id": note.id,
                        "subject_id": subject.id,
                        "subject_code": subject.code,
                        "subject_name": subject.name,
                        "department": subject.department,
                        "title": note.title,
                        "original_filename": note.original_filename,
                        "mime_type": note.mime_type,
                        "unit_id": note.unit_id,
                        "unit_title": note.unit.title if note.unit else None,
                        "topic_id": note.topic_id,
                        "topic_title": note.topic.title if note.topic else None,
                        "chunk_index": chunk_index,
                        "content_hash": content_hash,
                        "is_published": "true",
                        "status": note.status.value,
                        "indexed_at": datetime.now(timezone.utc).isoformat()
                    }
                })
                chunk_index += 1
                # Modest overlap for continuity
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
            point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"lecture_note_{note.id}_chunk_{chunk_index}"))

            chunks.append({
                "point_id": point_uuid,
                "text": full_chunk_text,
                "payload": {
                    "text": full_chunk_text,
                    "source_type": "lecture_note",
                    "lecture_note_id": note.id,
                    "subject_id": subject.id,
                    "subject_code": subject.code,
                    "subject_name": subject.name,
                    "department": subject.department,
                    "title": note.title,
                    "original_filename": note.original_filename,
                    "mime_type": note.mime_type,
                    "unit_id": note.unit_id,
                    "unit_title": note.unit.title if note.unit else None,
                    "topic_id": note.topic_id,
                    "topic_title": note.topic.title if note.topic else None,
                    "chunk_index": chunk_index,
                    "content_hash": content_hash,
                    "is_published": "true",
                    "status": note.status.value,
                    "indexed_at": datetime.now(timezone.utc).isoformat()
                }
            })

        return chunks

    def delete_note_chunks(self, note_id: int) -> int:
        """
        Delete all indexed Qdrant points for a specific lecture note.
        Strictly isolates lecture note vectors from syllabus chunks and other lecture notes.
        Safe and idempotent.
        """
        if not qdrant_client.client:
            logger.warning("Qdrant client unavailable during note chunk deletion")
            return 0

        self.ensure_collection()
        try:
            filter_note = models.Filter(
                must=[
                    models.FieldCondition(
                        key="source_type",
                        match=models.MatchValue(value="lecture_note")
                    ),
                    models.FieldCondition(
                        key="lecture_note_id",
                        match=models.MatchValue(value=note_id)
                    )
                ]
            )

            qdrant_client.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=filter_note
                )
            )
            logger.info(f"🗑️ Deleted Qdrant points for lecture note {note_id}")
            return 1
        except Exception as e:
            logger.error(f"❌ Failed to delete Qdrant points for lecture note {note_id}: {e}")
            raise

    def index_lecture_note(self, db: Session, note_id: int) -> Dict[str, Any]:
        """
        Idempotent lecture note indexing pipeline:
        1. Checks eligibility immediately from PostgreSQL.
        2. Atomically claims the note using conditional update to prevent concurrent duplicate work.
        3. Ensures collection exists and verifies 384-dimensional embedding model.
        4. Removes obsolete points for this note from Qdrant.
        5. Generates structured chunks with stable UUIDv5 IDs and metadata.
        6. Generates embeddings and upserts points to Qdrant.
        7. Persists INDEXED status and actual chunk count in PostgreSQL.
        8. On failure, updates status to FAILED with sanitized error.
        """
        # 1. Fetch note and revalidate eligibility immediately
        note = db.query(LectureNote).filter(LectureNote.id == note_id).first()
        if not note:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lecture note with ID {note_id} not found."
            )

        eligible, reason = self.is_eligible_for_indexing(note)
        if not eligible:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Lecture note {note_id} is not eligible for indexing: {reason}"
            )

        # 2. Concurrency protection: conditional update to claim note
        rows_claimed = db.query(LectureNote).filter(
            LectureNote.id == note_id,
            LectureNote.indexing_status != LectureNoteIndexingStatus.INDEXING
        ).update({
            LectureNote.indexing_status: LectureNoteIndexingStatus.INDEXING,
            LectureNote.updated_at: datetime.now(timezone.utc)
        }, synchronize_session=False)
        db.commit()

        if rows_claimed == 0:
            current = db.query(LectureNote).filter(LectureNote.id == note_id).first()
            if current and current.indexing_status == LectureNoteIndexingStatus.INDEXING:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Lecture note {note_id} is currently being indexed by another process."
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Lecture note {note_id} cannot be claimed for indexing."
            )

        # 3. Ensure Qdrant collection is ready
        if not self.ensure_collection():
            self._set_failed_status(db, note_id, "Qdrant vector collection unavailable.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Qdrant vector collection unavailable."
            )

        # Ensure embedding service is available and dimension matches
        dim = embedding_service.get_embedding_dimension()
        if dim != self.vector_size:
            err = f"Embedding model dimension {dim} does not match collection configuration {self.vector_size}."
            self._set_failed_status(db, note_id, err)
            raise ValueError(err)

        try:
            # 4. Remove any existing chunks for this note (ensures clean replacement)
            self.delete_note_chunks(note_id)

            # Re-read fresh note data for chunking
            fresh_note = db.query(LectureNote).filter(LectureNote.id == note_id).first()
            if not fresh_note:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note was removed during indexing.")

            # 5. Generate chunks
            chunks = self.create_chunks(fresh_note)
            if not chunks:
                err_msg = "No valid text chunks generated for indexing."
                self._set_failed_status(db, note_id, err_msg)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Vector indexing aborted: {err_msg}"
                )

            # 6. Generate embeddings using shared embedding service
            texts = [c["text"] for c in chunks]
            embeddings = embedding_service.embed_texts(texts)
            if not embeddings or len(embeddings) != len(chunks):
                raise ValueError("Embedding generation returned incomplete or empty vectors.")

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
            qdrant_client.client.upsert(
                collection_name=self.collection_name,
                points=points
            )

            # 9. Update PostgreSQL metadata
            meta = dict(fresh_note.extraction_metadata or {})
            meta["indexing_error"] = None
            meta["indexed_at"] = datetime.now(timezone.utc).isoformat()

            fresh_note.indexing_status = LectureNoteIndexingStatus.INDEXED
            fresh_note.indexed_chunk_count = len(points)
            fresh_note.extraction_metadata = meta
            db.commit()
            db.refresh(fresh_note)

            logger.info(f"✅ Successfully indexed {len(points)} chunks for lecture note {note_id} in Qdrant")
            return {
                "status": "SUCCESS",
                "lecture_note_id": note_id,
                "chunks_indexed": len(points),
                "indexed_at": meta["indexed_at"]
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Indexing failed for lecture note {note_id}: {e}", exc_info=True)
            self._set_failed_status(db, note_id, str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Vector indexing failed for lecture note {note_id}: {str(e)}"
            )

    def _set_failed_status(self, db: Session, note_id: int, error_message: str):
        """Update note to FAILED indexing status with sanitized error metadata."""
        try:
            note = db.query(LectureNote).filter(LectureNote.id == note_id).first()
            if note:
                meta = dict(note.extraction_metadata or {})
                meta["indexing_error"] = error_message[:500]
                note.indexing_status = LectureNoteIndexingStatus.FAILED
                note.indexed_chunk_count = 0
                note.extraction_metadata = meta
                db.commit()
        except Exception as err:
            logger.error(f"Failed to persist FAILED indexing status for note {note_id}: {err}")
            db.rollback()


# Singleton instance
lecture_notes_indexing_service = LectureNotesIndexingService()
