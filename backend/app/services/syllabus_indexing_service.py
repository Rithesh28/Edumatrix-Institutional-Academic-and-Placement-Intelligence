"""
Syllabus Indexing Service (RAG Foundation)

Manages vector indexing for approved and published syllabus documents
in a dedicated Qdrant collection ('study_buddy_chunks').

Preserves the existing 'files' collection untouched, provides deterministic
chunking with provenance, enforces PostgreSQL-backed eligibility gates,
and ensures idempotent chunk replacement and cleanup.
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
    SyllabusDocument,
    SyllabusUnit,
    SyllabusTopic,
    SyllabusProcessingStatus,
    SyllabusReviewStatus
)
from ..models.user import User, UserRole

logger = logging.getLogger(__name__)

STUDY_BUDDY_COLLECTION = "study_buddy_chunks"
STUDY_BUDDY_VECTOR_SIZE = 384


class SyllabusIndexingService:
    """
    Dedicated RAG indexing service for academic syllabus documents.
    """

    def __init__(self):
        self.collection_name = STUDY_BUDDY_COLLECTION
        self.vector_size = STUDY_BUDDY_VECTOR_SIZE
        self._collection_verified = False

    def ensure_collection(self) -> bool:
        """
        Idempotently initialize the dedicated 'study_buddy_chunks' collection.
        Never modifies, recreates, or touches the existing 'files' collection.
        """
        if not qdrant_client.client:
            logger.error("Qdrant client unavailable")
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

                # Create payload indexes for fast filtering
                self._create_payload_indexes()
            else:
                info = qdrant_client.client.get_collection(self.collection_name)
                current_size = info.config.params.vectors.size
                if current_size != self.vector_size:
                    raise ValueError(
                        f"Collection '{self.collection_name}' has vector dimension {current_size}, "
                        f"expected {self.vector_size}."
                    )
                logger.info(f"📁 Qdrant collection '{self.collection_name}' verified ({current_size}-dim)")

            self._collection_verified = True
            return True
        except Exception as e:
            logger.error(f"❌ Failed to ensure collection '{self.collection_name}': {e}")
            return False

    def _create_payload_indexes(self):
        """Create indexes on payload fields for high-performance filtering."""
        fields = [
            ("document_id", models.PayloadSchemaType.INTEGER),
            ("subject_id", models.PayloadSchemaType.INTEGER),
            ("department", models.PayloadSchemaType.KEYWORD),
            ("version", models.PayloadSchemaType.INTEGER),
            ("is_published", models.PayloadSchemaType.KEYWORD),
            ("unit_number", models.PayloadSchemaType.INTEGER),
        ]
        for field_name, field_type in fields:
            try:
                qdrant_client.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=field_type
                )
                logger.debug(f"Created payload index for '{field_name}'")
            except Exception as e:
                logger.warning(f"Failed to create index for '{field_name}': {e}")

    def create_chunks(self, doc: SyllabusDocument) -> List[Dict[str, Any]]:
        """
        Produce structured, provenance-linked chunks from a syllabus document.
        Prefers Unit and Topic boundaries. If units are not available, breaks
        on paragraph boundaries with conservative overlap.
        """
        chunks = []
        subject = doc.subject

        # Strategy A: Use segmented units & topics if available
        if doc.units and len(doc.units) > 0:
            chunk_order = 1
            for unit in doc.units:
                u_header = f"{subject.code} {subject.name} - {unit.title}"
                if unit.description:
                    u_header += f"\nDescription: {unit.description}"

                # If unit has topics, create chunks per topic or topic group
                if unit.topics and len(unit.topics) > 0:
                    for topic in unit.topics:
                        content_lines = [u_header, f"Topic: {topic.title}"]
                        if topic.extracted_text and topic.extracted_text.strip() != topic.title.strip():
                            content_lines.append(f"Content: {topic.extracted_text}")

                        chunk_text = "\n".join(content_lines).strip()
                        content_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()

                        # Deterministic point ID based on doc, version, and chunk order
                        point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"syllabus_{doc.id}_v{doc.version}_chunk_{chunk_order}"))

                        chunks.append({
                            "point_id": point_uuid,
                            "text": chunk_text,
                            "payload": {
                                "text": chunk_text,
                                "document_id": doc.id,
                                "version": doc.version,
                                "subject_id": subject.id,
                                "subject_code": subject.code,
                                "subject_name": subject.name,
                                "department": subject.department,
                                "unit_number": unit.unit_number,
                                "unit_title": unit.title,
                                "topic_title": topic.title,
                                "source_page": topic.source_page or unit.source_page_start,
                                "source_evidence": topic.source_evidence or unit.source_evidence,
                                "chunk_order": chunk_order,
                                "content_hash": content_hash,
                                "is_published": str(doc.is_published).lower(),
                                "review_status": doc.review_status.value if hasattr(doc.review_status, "value") else str(doc.review_status),
                                "chunk_type": "unit_topic",
                                "indexed_at": datetime.now(timezone.utc).isoformat()
                            }
                        })
                        chunk_order += 1
                else:
                    # Unit without specific subtopics
                    chunk_text = u_header
                    content_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
                    point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"syllabus_{doc.id}_v{doc.version}_chunk_{chunk_order}"))

                    chunks.append({
                        "point_id": point_uuid,
                        "text": chunk_text,
                        "payload": {
                            "text": chunk_text,
                            "document_id": doc.id,
                            "version": doc.version,
                            "subject_id": subject.id,
                            "subject_code": subject.code,
                            "subject_name": subject.name,
                            "department": subject.department,
                            "unit_number": unit.unit_number,
                            "unit_title": unit.title,
                            "topic_title": None,
                            "source_page": unit.source_page_start,
                            "source_evidence": unit.source_evidence,
                            "chunk_order": chunk_order,
                            "content_hash": content_hash,
                            "is_published": str(doc.is_published).lower(),
                            "review_status": doc.review_status.value if hasattr(doc.review_status, "value") else str(doc.review_status),
                            "chunk_type": "unit_only",
                            "indexed_at": datetime.now(timezone.utc).isoformat()
                        }
                    })
                    chunk_order += 1

            return chunks

        # Strategy B: Fallback to paragraph chunking with conservative size & overlap
        raw_text = doc.extracted_text or ""
        if not raw_text.strip():
            return []

        paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
        chunks = []
        chunk_order = 1
        current_chunk = f"{subject.code} - {subject.name}:\n"
        max_chunk_chars = 600
        overlap_chars = 100

        for para in paragraphs:
            if len(current_chunk) + len(para) > max_chunk_chars:
                chunk_text = current_chunk.strip()
                content_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
                point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"syllabus_{doc.id}_v{doc.version}_chunk_{chunk_order}"))

                chunks.append({
                    "point_id": point_uuid,
                    "text": chunk_text,
                    "payload": {
                        "text": chunk_text,
                        "document_id": doc.id,
                        "version": doc.version,
                        "subject_id": subject.id,
                        "subject_code": subject.code,
                        "subject_name": subject.name,
                        "department": subject.department,
                        "unit_number": None,
                        "unit_title": None,
                        "topic_title": None,
                        "source_page": None,
                        "source_evidence": None,
                        "chunk_order": chunk_order,
                        "content_hash": content_hash,
                        "is_published": str(doc.is_published).lower(),
                        "review_status": doc.review_status.value if hasattr(doc.review_status, "value") else str(doc.review_status),
                        "chunk_type": "paragraph_fallback",
                        "indexed_at": datetime.now(timezone.utc).isoformat()
                    }
                })
                chunk_order += 1
                current_chunk = current_chunk[-overlap_chars:] + " " + para
            else:
                current_chunk += "\n" + para

        if current_chunk.strip():
            chunk_text = current_chunk.strip()
            content_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
            point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"syllabus_{doc.id}_v{doc.version}_chunk_{chunk_order}"))

            chunks.append({
                "point_id": point_uuid,
                "text": chunk_text,
                "payload": {
                    "text": chunk_text,
                    "document_id": doc.id,
                    "version": doc.version,
                    "subject_id": subject.id,
                    "subject_code": subject.code,
                    "subject_name": subject.name,
                    "department": subject.department,
                    "unit_number": None,
                    "unit_title": None,
                    "topic_title": None,
                    "source_page": None,
                    "source_evidence": None,
                    "chunk_order": chunk_order,
                    "content_hash": content_hash,
                    "is_published": str(doc.is_published).lower(),
                    "review_status": doc.review_status.value if hasattr(doc.review_status, "value") else str(doc.review_status),
                    "chunk_type": "paragraph_fallback",
                    "indexed_at": datetime.now(timezone.utc).isoformat()
                }
            })

        return chunks

    def is_eligible_for_indexing(self, doc: SyllabusDocument) -> Tuple[bool, str]:
        """
        Verify indexing eligibility from PostgreSQL:
        Must be approved, published, subject active, with non-empty content.
        """
        if not doc:
            return False, "Document does not exist."
        if doc.review_status != SyllabusReviewStatus.APPROVED:
            return False, f"Document is not approved (current status: {doc.review_status})."
        if not doc.is_published:
            return False, "Document is not published."
        if not doc.subject or not doc.subject.is_active:
            return False, "Subject is inactive or deleted."
        if not doc.extracted_text and not doc.units:
            return False, "Document has no extracted content to index."
        return True, "Eligible"

    def delete_document_chunks(self, document_id: int) -> int:
        """
        Delete all indexed chunks for a specific document version.
        Does not delete other versions or other documents.
        """
        if not qdrant_client.client:
            return 0

        self.ensure_collection()
        try:
            # Count points before deletion
            filter_doc = models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
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
            logger.info(f"🗑️ Deleted Qdrant points for syllabus document {document_id}")
            return 1
        except Exception as e:
            logger.error(f"Failed to delete points for document {document_id}: {e}")
            return 0

    def index_syllabus_document(self, db: Session, document_id: int) -> Dict[str, Any]:
        """
        Idempotent indexing pipeline:
        1. Verifies eligibility from PostgreSQL.
        2. Ensures collection exists with 384 dimensions.
        3. Cleans up any existing points for this document_id.
        4. Generates chunks and verifies 384-dimensional embeddings.
        5. Upserts points into Qdrant.
        6. Persists indexing metadata and timestamp in PostgreSQL.
        """
        doc = db.query(SyllabusDocument).filter(SyllabusDocument.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Syllabus document not found.")

        # Re-verify eligibility from PostgreSQL
        eligible, reason = self.is_eligible_for_indexing(doc)
        if not eligible:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Syllabus document {document_id} is not eligible for indexing: {reason}"
            )

        if not self.ensure_collection():
            doc_meta = doc.extraction_metadata or {}
            doc_meta["indexing_status"] = "FAILED"
            doc_meta["indexing_error"] = "Vector database unavailable."
            doc.extraction_metadata = doc_meta
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Qdrant vector collection unavailable."
            )

        # Ensure embedding service is available and dimension matches
        dim = embedding_service.get_embedding_dimension()
        if dim != self.vector_size:
            raise ValueError(f"Embedding model dimension {dim} does not match collection configuration {self.vector_size}.")

        try:
            # 1. Remove existing chunks for this document version
            self.delete_document_chunks(doc.id)

            # 2. Generate chunks
            chunks = self.create_chunks(doc)
            if not chunks:
                doc_meta = doc.extraction_metadata or {}
                doc_meta["indexing_status"] = "INDEXED"
                doc_meta["indexed_chunks_count"] = 0
                doc_meta["indexed_at"] = datetime.now(timezone.utc).isoformat()
                doc.extraction_metadata = doc_meta
                db.commit()
                return {"status": "SUCCESS", "chunks_indexed": 0, "message": "No text content to index."}

            # 3. Generate embeddings
            texts = [c["text"] for c in chunks]
            if hasattr(embedding_service, "embed_texts"):
                embeddings = embedding_service.embed_texts(texts)
            elif hasattr(embedding_service, "embed_batch"):
                embeddings = embedding_service.embed_batch(texts)
            else:
                embeddings = [embedding_service.embed_text(t) for t in texts]

            # 4. Construct Qdrant points
            points = []
            for i, chunk in enumerate(chunks):
                emb = embeddings[i]
                if not emb or len(emb) != self.vector_size:
                    raise ValueError(f"Embedding generation failed for chunk {i}: invalid vector dimension.")

                points.append(
                    models.PointStruct(
                        id=chunk["point_id"],
                        vector=emb,
                        payload=chunk["payload"]
                    )
                )

            # 5. Upsert points into Qdrant
            qdrant_client.client.upsert(
                collection_name=self.collection_name,
                points=points
            )

            # 6. Update PostgreSQL metadata
            doc_meta = doc.extraction_metadata or {}
            doc_meta["indexing_status"] = "INDEXED"
            doc_meta["indexed_chunks_count"] = len(points)
            doc_meta["indexed_at"] = datetime.now(timezone.utc).isoformat()
            doc_meta["indexing_error"] = None
            doc.extraction_metadata = doc_meta
            db.commit()
            db.refresh(doc)

            logger.info(f"✅ Successfully indexed {len(points)} chunks for syllabus {doc.id} (v{doc.version}) in Qdrant")
            return {
                "status": "SUCCESS",
                "document_id": doc.id,
                "version": doc.version,
                "chunks_indexed": len(points),
                "indexed_at": doc_meta["indexed_at"]
            }

        except Exception as e:
            logger.error(f"❌ Indexing failed for syllabus {doc.id}: {e}", exc_info=True)
            doc_meta = doc.extraction_metadata or {}
            doc_meta["indexing_status"] = "FAILED"
            doc_meta["indexing_error"] = str(e)
            doc.extraction_metadata = doc_meta
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Vector indexing failed: {str(e)}"
            )

    def search_chunks(
        self,
        db: Session,
        query: str,
        current_user: User,
        subject_id: Optional[int] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Authorized semantic retrieval across syllabus chunks.
        Never relies on Qdrant filters alone: enforces PostgreSQL
        authorization boundary before and after retrieval.
        """
        if not query or not query.strip():
            return []

        # 1. Authorization check
        if current_user.role == UserRole.PLACEMENT_OFFICER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Placement Officers do not have syllabus retrieval access.")

        # Resolve department for caller
        user_dept = current_user.department
        if current_user.student_profile and current_user.student_profile.branch:
            user_dept = current_user.student_profile.branch

        # 2. Ensure collection
        if not self.ensure_collection():
            return []

        # 3. Generate query embedding
        query_vector = embedding_service.embed_text(query)
        if not query_vector:
            return []

        # 4. Construct Qdrant filter
        must_conditions = [
            models.FieldCondition(
                key="is_published",
                match=models.MatchValue(value="true")
            )
        ]

        if current_user.role != UserRole.ADMIN and user_dept:
            must_conditions.append(
                models.FieldCondition(
                    key="department",
                    match=models.MatchValue(value=user_dept)
                )
            )

        if subject_id:
            must_conditions.append(
                models.FieldCondition(
                    key="subject_id",
                    match=models.MatchValue(value=subject_id)
                )
            )

        qdrant_filter = models.Filter(must=must_conditions)

        # 5. Execute search (supports modern QdrantClient query_points and legacy search)
        if hasattr(qdrant_client.client, "query_points"):
            response = qdrant_client.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=limit,
                query_filter=qdrant_filter,
                score_threshold=0.2
            )
            results = response.points
        else:
            results = qdrant_client.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                query_filter=qdrant_filter,
                score_threshold=0.2
            )

        # 6. Secondary validation against PostgreSQL (authoritative store)
        formatted = []
        for r in results:
            doc_id = r.payload.get("document_id")
            # Verify that document is still active, approved, published, and belongs to an active subject in PostgreSQL
            doc_query = db.query(SyllabusDocument).join(Subject).filter(
                SyllabusDocument.id == doc_id,
                SyllabusDocument.is_published == True,
                SyllabusDocument.review_status == SyllabusReviewStatus.APPROVED,
                Subject.is_active == True
            )

            if current_user.role != UserRole.ADMIN and user_dept:
                doc_query = doc_query.filter(Subject.department.ilike(user_dept))

            if current_user.role == UserRole.STUDENT:
                user_sem = current_user.student_profile.semester if current_user.student_profile else getattr(current_user, "semester", None)
                if user_sem is not None:
                    doc_query = doc_query.filter(Subject.semester == user_sem)

            doc = doc_query.first()

            if doc:
                formatted.append({
                    "score": r.score,
                    "document_id": doc_id,
                    "version": r.payload.get("version"),
                    "subject_id": r.payload.get("subject_id"),
                    "subject_code": r.payload.get("subject_code"),
                    "subject_name": r.payload.get("subject_name"),
                    "department": r.payload.get("department"),
                    "unit_number": r.payload.get("unit_number"),
                    "unit_title": r.payload.get("unit_title"),
                    "topic_title": r.payload.get("topic_title"),
                    "source_page": r.payload.get("source_page"),
                    "source_evidence": r.payload.get("source_evidence"),
                    "chunk_order": r.payload.get("chunk_order"),
                    "text": r.payload.get("text")
                })

        return formatted


syllabus_indexing_service = SyllabusIndexingService()
