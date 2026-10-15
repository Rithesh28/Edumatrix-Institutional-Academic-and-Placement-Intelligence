"""
Study Buddy Chat Service (Unified Multi-Source RAG Academic Assistant)

Orchestrates RAG-powered academic question answering across multiple knowledge sources:
1. Syllabus documents ('syllabus')
2. Faculty lecture notes ('lecture_notes')
3. Unified multi-source retrieval ('all')

Core Guarantees:
- Validates caller authorization and department boundaries against PostgreSQL.
- Resolves student department accurately (including student_profile.branch fallback).
- Performs dual-stage retrieval: Qdrant semantic search + strict PostgreSQL revalidation.
- Stale, unpublished, draft, archived, non-indexed, or cross-department records are excluded.
- Source-aware citation building with complete provenance and stable identifiers.
- Bounded academic context window preventing CPU saturation on local neural generation.
- Graceful insufficient-evidence guards and honest non-hallucinatory fallbacks.
"""

import time
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from qdrant_client.http import models

from ..core.config import settings
from ..models.user import User, UserRole
from ..models.study_buddy import (
    Subject,
    SyllabusDocument,
    SyllabusReviewStatus,
    LectureNote,
    LectureNoteStatus,
    LectureNoteProcessingStatus,
    LectureNoteIndexingStatus,
    StudentStudyDocument,
    StudentDocProcessingStatus,
    StudentDocIndexingStatus,
)
from .embedding_service import embedding_service
from .file_storage.qdrant_client import qdrant_client
from .syllabus_indexing_service import syllabus_indexing_service
from .lecture_notes_indexing_service import (
    lecture_notes_indexing_service,
    STUDY_BUDDY_COLLECTION,
)
from .student_documents_indexing_service import student_documents_indexing_service
from .ai_generator_service import ai_generator

logger = logging.getLogger(__name__)


def _normalize_dept(dept: Optional[str]) -> str:
    """Normalize department strings for case-insensitive comparison."""
    return (dept or "").strip().lower()


def _get_user_department(user: User) -> Optional[str]:
    """Resolve department for user across roles (including student profile branch fallback)."""
    if user.role == UserRole.STUDENT and user.student_profile and user.student_profile.branch:
        return user.student_profile.branch
    if user.department:
        return user.department
    if user.student_profile and user.student_profile.branch:
        return user.student_profile.branch
    return None


class StudyBuddyChatService:
    """
    Unified RAG Academic Assistant question answering service.
    Supports 'syllabus', 'lecture_notes', and 'all' retrieval modes.
    """

    def __init__(self):
        self.min_relevance_score = settings.STUDY_BUDDY_MIN_RELEVANCE_SCORE
        self.top_k = settings.STUDY_BUDDY_TOP_K
        self.max_context_chars = settings.STUDY_BUDDY_MAX_CONTEXT_CHARS

    def search_syllabus_chunks(
        self,
        db: Session,
        query: str,
        current_user: User,
        subject_id: Optional[int] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve authorized syllabus chunks with PostgreSQL boundary checks.
        """
        raw = syllabus_indexing_service.search_chunks(
            db=db,
            query=query,
            current_user=current_user,
            subject_id=subject_id,
            limit=limit
        )
        formatted = []
        for c in raw:
            item = dict(c)
            doc_id = item.get("document_id")
            doc = None
            if doc_id:
                doc = db.query(SyllabusDocument.title, SyllabusDocument.original_filename).filter(
                    SyllabusDocument.id == doc_id
                ).first()

            item["source_type"] = "syllabus"
            item["source_id"] = doc_id
            item["source_title"] = (doc.title if doc and doc.title else None) or item.get("subject_name") or item.get("subject_code") or "Official Syllabus"
            item["original_filename"] = (doc.original_filename if doc and doc.original_filename else None) or item.get("original_filename")
            item["lecture_note_id"] = None
            formatted.append(item)
        return formatted

    def search_lecture_note_chunks(
        self,
        db: Session,
        query: str,
        current_user: User,
        subject_id: Optional[int] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve authorized lecture note chunks with strict PostgreSQL boundary checks.
        Re-validates that the note is published, extracted, indexed, and active in DB.
        """
        if not query or not query.strip():
            return []

        if current_user.role == UserRole.PLACEMENT_OFFICER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Placement Officers do not have lecture note retrieval access."
            )

        user_dept = _get_user_department(current_user)

        # Ensure collection
        if not lecture_notes_indexing_service.ensure_collection():
            return []

        # Generate query vector
        query_vector = embedding_service.embed_text(query)
        if not query_vector:
            return []

        # Filter by source_type='lecture_note' and is_published='true'
        must_conditions = [
            models.FieldCondition(
                key="source_type",
                match=models.MatchValue(value="lecture_note")
            ),
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

        try:
            if hasattr(qdrant_client.client, "query_points"):
                response = qdrant_client.client.query_points(
                    collection_name=STUDY_BUDDY_COLLECTION,
                    query=query_vector,
                    limit=limit,
                    query_filter=qdrant_filter,
                    score_threshold=0.2
                )
                results = response.points
            else:
                results = qdrant_client.client.search(
                    collection_name=STUDY_BUDDY_COLLECTION,
                    query_vector=query_vector,
                    limit=limit,
                    query_filter=qdrant_filter,
                    score_threshold=0.2
                )
        except Exception as qd_err:
            logger.error(f"Qdrant query failed for lecture notes: {qd_err}")
            return []

        # Authoritative secondary validation against PostgreSQL
        formatted = []
        for r in results:
            note_id = r.payload.get("lecture_note_id")
            if not note_id:
                continue

            note = db.query(LectureNote).join(Subject).filter(
                LectureNote.id == note_id,
                LectureNote.is_published == True,
                LectureNote.status == LectureNoteStatus.PUBLISHED,
                LectureNote.processing_status == LectureNoteProcessingStatus.EXTRACTED,
                LectureNote.indexing_status == LectureNoteIndexingStatus.INDEXED,
                LectureNote.indexed_chunk_count > 0,
                Subject.is_active == True
            ).first()

            if not note:
                # Discard stale or invalidated Qdrant point
                continue

            if subject_id is not None and note.subject_id != subject_id:
                continue

            # Check role-based department and subject permissions
            if current_user.role == UserRole.STUDENT:
                if _normalize_dept(user_dept) != _normalize_dept(note.subject.department):
                    continue
            elif current_user.role == UserRole.LECTURER:
                if _normalize_dept(user_dept) != _normalize_dept(note.subject.department):
                    assigned = []
                    if current_user.lecturer_profile and current_user.lecturer_profile.subjects:
                        assigned = [str(s).strip().upper() for s in current_user.lecturer_profile.subjects]
                    if note.subject.code.strip().upper() not in assigned:
                        continue
            elif current_user.role == UserRole.HOD:
                if _normalize_dept(user_dept) != _normalize_dept(note.subject.department):
                    continue
            elif current_user.role != UserRole.ADMIN:
                if _normalize_dept(user_dept) != _normalize_dept(note.subject.department):
                    continue

            formatted.append({
                "score": r.score,
                "source_type": "lecture_note",
                "source_id": note.id,
                "source_title": note.title,
                "original_filename": note.original_filename,
                "document_id": None,
                "version": None,
                "lecture_note_id": note.id,
                "subject_id": note.subject_id,
                "subject_code": note.subject.code,
                "subject_name": note.subject.name,
                "department": note.subject.department,
                "unit_number": note.unit.unit_number if note.unit else r.payload.get("unit_number"),
                "unit_title": note.unit.title if note.unit else r.payload.get("unit_title"),
                "topic_title": note.topic.title if note.topic else r.payload.get("topic_title"),
                "source_page": r.payload.get("source_page"),
                "source_evidence": None,
                "chunk_order": r.payload.get("chunk_index"),
                "text": r.payload.get("text")
            })

        return formatted

    def search_student_document_chunks(
        self,
        db: Session,
        query: str,
        current_user: User,
        subject_id: Optional[int] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve authorized student study document chunks with strict PostgreSQL boundary checks.
        Filters Qdrant by source_type='student_upload' and student_id=current_user.id,
        then strictly validates each candidate point against PostgreSQL:
        - Document exists
        - student_id == current_user.id
        - is_active is True
        - processing_status == EXTRACTED
        - indexing_status == INDEXED
        - indexed_chunk_count > 0
        - If subject_id is linked: Subject.is_active is True and department-accessible
        """
        if not query or not query.strip():
            return []

        if current_user.role == UserRole.PLACEMENT_OFFICER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Placement Officers do not have study document retrieval access."
            )

        # Ensure collection
        if not student_documents_indexing_service.ensure_collection():
            return []

        # Generate query vector
        query_vector = embedding_service.embed_text(query)
        if not query_vector:
            return []

        # Vector filter: scope strictly to source_type="student_upload" and student_id=current_user.id
        must_conditions = [
            models.FieldCondition(
                key="source_type",
                match=models.MatchValue(value="student_upload")
            ),
            models.FieldCondition(
                key="student_id",
                match=models.MatchValue(value=current_user.id)
            )
        ]

        if subject_id is not None:
            must_conditions.append(
                models.FieldCondition(
                    key="subject_id",
                    match=models.MatchValue(value=subject_id)
                )
            )

        qdrant_filter = models.Filter(must=must_conditions)

        try:
            if hasattr(qdrant_client.client, "query_points"):
                response = qdrant_client.client.query_points(
                    collection_name=STUDY_BUDDY_COLLECTION,
                    query=query_vector,
                    limit=limit,
                    query_filter=qdrant_filter,
                    score_threshold=0.2
                )
                results = response.points
            else:
                results = qdrant_client.client.search(
                    collection_name=STUDY_BUDDY_COLLECTION,
                    query_vector=query_vector,
                    limit=limit,
                    query_filter=qdrant_filter,
                    score_threshold=0.2
                )
        except Exception as qd_err:
            logger.error(f"Qdrant query failed for student documents: {qd_err}")
            return []

        user_dept = _get_user_department(current_user)

        # Authoritative secondary validation against PostgreSQL
        # NEVER rely on Qdrant filters as the authorization boundary!
        formatted = []
        for r in results:
            doc_id = r.payload.get("student_study_document_id")
            if not doc_id:
                continue

            doc = db.query(StudentStudyDocument).filter(
                StudentStudyDocument.id == doc_id,
                StudentStudyDocument.student_id == current_user.id,
                StudentStudyDocument.is_active == True,
                StudentStudyDocument.processing_status == StudentDocProcessingStatus.EXTRACTED,
                StudentStudyDocument.indexing_status == StudentDocIndexingStatus.INDEXED,
                StudentStudyDocument.indexed_chunk_count > 0
            ).first()

            if not doc:
                # Discard stale, deleted, deactivated, failed, non-indexed, or foreign-owner chunks
                continue

            if subject_id is not None and doc.subject_id != subject_id:
                continue

            # If subject is associated, verify subject is active and department-accessible
            if doc.subject_id is not None:
                if not doc.subject or not doc.subject.is_active:
                    continue

                if current_user.role != UserRole.ADMIN:
                    if not user_dept or _normalize_dept(user_dept) != _normalize_dept(doc.subject.department):
                        continue

            formatted.append({
                "score": r.score,
                "source_type": "student_upload",
                "source_id": doc.id,
                "source_title": doc.title,
                "original_filename": doc.original_filename,
                "document_id": None,
                "version": None,
                "lecture_note_id": None,
                "student_study_document_id": doc.id,
                "subject_id": doc.subject_id,
                "subject_code": doc.subject.code if doc.subject else None,
                "subject_name": doc.subject.name if doc.subject else None,
                "department": doc.subject.department if doc.subject else None,
                "unit_number": None,
                "unit_title": None,
                "topic_title": None,
                "source_page": r.payload.get("source_page"),
                "source_evidence": None,
                "chunk_order": r.payload.get("chunk_index"),
                "text": r.payload.get("text")
            })

        return formatted

    def search_unified_chunks(
        self,
        db: Session,
        query: str,
        current_user: User,
        subject_id: Optional[int] = None,
        source_mode: str = "syllabus",
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Unified search router dispatching to syllabus, lecture_notes, my_documents, or combinations.
        """
        mode = str(source_mode.value if hasattr(source_mode, "value") else source_mode).lower().strip()
        valid_modes = ("syllabus", "lecture_notes", "all", "my_documents", "all_my_sources")
        if mode not in valid_modes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid source_mode '{source_mode}'. Must be one of: {', '.join(valid_modes)}."
            )

        if mode == "syllabus":
            return self.search_syllabus_chunks(db, query, current_user, subject_id, limit)
        elif mode == "lecture_notes":
            return self.search_lecture_note_chunks(db, query, current_user, subject_id, limit)
        elif mode == "my_documents":
            return self.search_student_document_chunks(db, query, current_user, subject_id, limit)
        elif mode == "all":
            # Existing combined syllabus + lecture_notes behavior, unchanged
            s_chunks = self.search_syllabus_chunks(db, query, current_user, subject_id, limit)
            l_chunks = self.search_lecture_note_chunks(db, query, current_user, subject_id, limit)
            combined = s_chunks + l_chunks
            combined.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)

            # Deduplicate near-identical chunks based on snippet prefix
            deduped = []
            seen_snippets = set()
            for c in combined:
                snippet = (c.get("text") or "").strip()[:80].lower()
                if snippet and snippet in seen_snippets:
                    continue
                seen_snippets.add(snippet)
                deduped.append(c)
                if len(deduped) >= limit:
                    break
            return deduped
        elif mode == "all_my_sources":
            s_chunks = self.search_syllabus_chunks(db, query, current_user, subject_id, limit)
            l_chunks = self.search_lecture_note_chunks(db, query, current_user, subject_id, limit)
            m_chunks = self.search_student_document_chunks(db, query, current_user, subject_id, limit)
            combined = s_chunks + l_chunks + m_chunks
            combined.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)

            deduped = []
            seen_snippets = set()
            for c in combined:
                snippet = (c.get("text") or "").strip()[:80].lower()
                if snippet and snippet in seen_snippets:
                    continue
                seen_snippets.add(snippet)
                deduped.append(c)
                if len(deduped) >= limit:
                    break
            return deduped

        return []

    def ask_question(
        self,
        db: Session,
        current_user: User,
        question: str,
        subject_id: Optional[int] = None,
        source_mode: str = "syllabus"
    ) -> Dict[str, Any]:
        """
        Process student academic query with strict RAG grounding across requested knowledge sources.
        """
        start_time = time.time()
        clean_query = (question or "").strip()
        if not clean_query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question cannot be empty."
            )

        # Validate source_mode
        mode = str(source_mode.value if hasattr(source_mode, "value") else source_mode).lower().strip()
        valid_modes = ("syllabus", "lecture_notes", "all", "my_documents", "all_my_sources")
        if mode not in valid_modes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid source_mode '{source_mode}'. Must be one of: {', '.join(valid_modes)}."
            )

        # 1. Enforce Role & Department Authorization
        if current_user.role == UserRole.PLACEMENT_OFFICER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Placement Officers do not have access to Study Buddy academic materials."
            )

        user_dept = _get_user_department(current_user)
        if mode in ("syllabus", "lecture_notes", "all", "all_my_sources") or subject_id is not None:
            if current_user.role != UserRole.ADMIN and not user_dept:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User has no assigned academic department."
                )

        # 2. If subject_id is specified, verify existence, active status, and department access
        if subject_id is not None:
            target_subject = db.query(Subject).filter(
                Subject.id == subject_id,
                Subject.is_active == True
            ).first()

            if not target_subject:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Subject ID {subject_id} not found or inactive."
                )

            # Department match check for non-admin
            if current_user.role == UserRole.LECTURER:
                if _normalize_dept(user_dept) != _normalize_dept(target_subject.department):
                    assigned_subjects = []
                    if current_user.lecturer_profile and current_user.lecturer_profile.subjects:
                        assigned_subjects = [str(s).strip().upper() for s in current_user.lecturer_profile.subjects]
                    if target_subject.code.strip().upper() not in assigned_subjects:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Access denied: Subject belongs to department '{target_subject.department}'."
                        )
            elif current_user.role != UserRole.ADMIN:
                if _normalize_dept(user_dept) != _normalize_dept(target_subject.department):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Access denied: Subject belongs to department '{target_subject.department}'."
                    )

        # 3. Retrieve relevant chunks according to source_mode
        raw_chunks = self.search_unified_chunks(
            db=db,
            query=clean_query,
            current_user=current_user,
            subject_id=subject_id,
            source_mode=mode,
            limit=self.top_k
        )

        # 4. Filter by Minimum Relevance Score Threshold
        qualifying_chunks = [
            c for c in raw_chunks
            if float(c.get("score", 0.0)) >= self.min_relevance_score
        ]

        logger.info(
            f"🔍 [STUDY-BUDDY] Mode: '{mode}' | Query: '{clean_query[:50]}...' | "
            f"Raw: {len(raw_chunks)} | Qualifying (>= {self.min_relevance_score}): {len(qualifying_chunks)}"
        )

        # 5. Insufficient Evidence Handling
        if not qualifying_chunks:
            elapsed_ms = (time.time() - start_time) * 1000
            if mode == "my_documents":
                source_desc = "uploaded personal study documents"
            elif mode == "lecture_notes":
                source_desc = "lecture notes"
            elif mode in ("all", "all_my_sources"):
                source_desc = "academic materials"
            else:
                source_desc = "syllabus material"

            return {
                "answer": (
                    f"The selected {source_desc} do not provide sufficient information to answer this question. "
                    "Please check your uploaded files or consult your subject lecturer for clarification."
                ) if mode == "my_documents" else (
                    f"The approved {source_desc} do not provide sufficient information to answer this question. "
                    "Please consult your subject lecturer or course coordinator for clarification."
                ),
                "has_sufficient_evidence": False,
                "citations": [],
                "subject_id": subject_id,
                "model_used": "evidence_guard",
                "latency_ms": round(elapsed_ms, 2)
            }

        # 6. Build Bounded Academic Context Window
        context_passages = []
        supplied_chunks = []
        total_chars = 0
        for i, chunk in enumerate(qualifying_chunks, 1):
            passage_text = chunk.get("text") or chunk.get("source_evidence") or ""
            source_type = chunk.get("source_type", "syllabus")
            if source_type == "student_upload":
                source_label = "Student Document"
            elif source_type == "lecture_note":
                source_label = "Lecture Note"
            else:
                source_label = "Syllabus"

            title_label = chunk.get("source_title") or chunk.get("original_filename") or ""
            subj_desc = f"{chunk.get('subject_code', '')} {chunk.get('subject_name', '')}".strip()

            header = f"[Passage {i} - {source_label}]"
            if subj_desc:
                header += f" {subj_desc}"
            if title_label and title_label != chunk.get('subject_name'):
                header += f" | {title_label}"
            if chunk.get("unit_number"):
                header += f" | Unit {chunk['unit_number']}: {chunk.get('unit_title', 'Unit')}"
            elif chunk.get("unit_title"):
                header += f" | Unit: {chunk['unit_title']}"
            if chunk.get("topic_title"):
                header += f" | Topic: {chunk['topic_title']}"
            if chunk.get("source_page"):
                header += f" (Page {chunk['source_page']})"

            passage_block = f"{header}\nContent: {passage_text.strip()}"
            if total_chars + len(passage_block) > self.max_context_chars:
                remaining = self.max_context_chars - total_chars
                if remaining > 100:
                    passage_block = passage_block[:remaining].strip() + "..."
                    context_passages.append(passage_block)
                    supplied_chunks.append(chunk)
                break

            context_passages.append(passage_block)
            supplied_chunks.append(chunk)
            total_chars += len(passage_block)

        context_str = "\n\n".join(context_passages)

        # 7. Grounded Answer Generation via Shared Qwen Singleton
        gen_result = ai_generator.generate_study_buddy_answer(
            query=clean_query,
            context_str=context_str,
            sources=supplied_chunks
        )

        answer_text = gen_result.get("answer", "")
        has_evidence = gen_result.get("has_sufficient_evidence", True)
        model_used = gen_result.get("model_used", settings.AI_MODEL_NAME)

        # 8. Build Verified Source Citations
        citations = []
        if has_evidence:
            for c in supplied_chunks:
                citations.append({
                    "source_type": c.get("source_type", "syllabus"),
                    "source_id": c.get("source_id") or c.get("document_id") or c.get("lecture_note_id") or c.get("student_study_document_id"),
                    "source_title": c.get("source_title"),
                    "original_filename": c.get("original_filename"),
                    "document_id": c.get("document_id"),
                    "version": c.get("version"),
                    "lecture_note_id": c.get("lecture_note_id"),
                    "student_study_document_id": c.get("student_study_document_id"),
                    "subject_id": c.get("subject_id"),
                    "subject_code": c.get("subject_code"),
                    "subject_name": c.get("subject_name"),
                    "department": c.get("department"),
                    "unit_number": c.get("unit_number"),
                    "unit_title": c.get("unit_title"),
                    "topic_title": c.get("topic_title"),
                    "source_page": c.get("source_page"),
                    "source_evidence": c.get("source_evidence"),
                    "chunk_order": c.get("chunk_order"),
                    "relevance_score": round(float(c.get("score", 0.0)), 4)
                })

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "answer": answer_text,
            "has_sufficient_evidence": has_evidence,
            "citations": citations,
            "subject_id": subject_id,
            "model_used": model_used,
            "latency_ms": round(elapsed_ms, 2)
        }


study_buddy_chat_service = StudyBuddyChatService()
