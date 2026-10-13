"""
Study Buddy Chat Service (RAG Academic Assistant)

Orchestrates RAG-powered academic question answering for students:
1. Validates student authorization and department/subject access against PostgreSQL.
2. Embeds student query and retrieves syllabus chunks from dedicated Qdrant collection.
3. Revalidates every chunk against PostgreSQL (active, approved, published).
4. Enforces configurable minimum relevance score threshold.
5. Assembles bounded academic context with provenance.
6. Invokes shared thread-safe Qwen generator singleton.
7. Constructs verified source citations from chunk metadata (not model hallucination).
8. Handles timeouts, model fallback, and concurrent requests safely.
"""

import time
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from ..core.config import settings
from ..models.user import User, UserRole
from ..models.study_buddy import Subject, SyllabusDocument, SyllabusReviewStatus
from .syllabus_indexing_service import syllabus_indexing_service
from .ai_generator_service import ai_generator

logger = logging.getLogger(__name__)


def _normalize_dept(dept: Optional[str]) -> str:
    """Normalize department strings for case-insensitive comparison."""
    return (dept or "").strip().lower()


def _get_user_department(user: User) -> Optional[str]:
    """Resolve department for user across roles (including student profile branch)."""
    if user.department:
        return user.department
    if user.student_profile and user.student_profile.branch:
        return user.student_profile.branch
    return None


class StudyBuddyChatService:
    """
    RAG Academic Assistant question answering service.
    """

    def __init__(self):
        self.min_relevance_score = settings.STUDY_BUDDY_MIN_RELEVANCE_SCORE
        self.top_k = settings.STUDY_BUDDY_TOP_K
        self.max_context_chars = settings.STUDY_BUDDY_MAX_CONTEXT_CHARS

    def ask_question(
        self,
        db: Session,
        current_user: User,
        question: str,
        subject_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Process student academic query with strict RAG grounding and PostgreSQL authorization.
        """
        start_time = time.time()
        clean_query = (question or "").strip()
        if not clean_query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question cannot be empty."
            )

        # 1. Enforce Role & Department Authorization
        if current_user.role == UserRole.PLACEMENT_OFFICER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Placement Officers do not have access to Study Buddy academic materials."
            )

        user_dept = _get_user_department(current_user)
        if current_user.role != UserRole.ADMIN and not user_dept:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no assigned academic department."
            )

        # 2. If subject_id is specified by client, verify existence, active status, and department access
        target_subject = None
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

        # 3. Retrieve relevant syllabus chunks with PostgreSQL boundary checks
        raw_chunks = syllabus_indexing_service.search_chunks(
            db=db,
            query=clean_query,
            current_user=current_user,
            subject_id=subject_id,
            limit=self.top_k
        )

        # 4. Filter by Minimum Relevance Score Threshold
        qualifying_chunks = [
            c for c in raw_chunks
            if float(c.get("score", 0.0)) >= self.min_relevance_score
        ]

        logger.info(
            f"🔍 [STUDY-BUDDY] Query: '{clean_query[:50]}...' | "
            f"Raw Chunks: {len(raw_chunks)} | Qualifying (>= {self.min_relevance_score}): {len(qualifying_chunks)}"
        )

        # 5. Insufficient Evidence Handling
        if not qualifying_chunks:
            elapsed_ms = (time.time() - start_time) * 1000
            return {
                "answer": (
                    "The approved syllabus material does not provide sufficient information to answer this question. "
                    "Please consult your subject lecturer or course coordinator for clarification."
                ),
                "has_sufficient_evidence": False,
                "citations": [],
                "subject_id": subject_id,
                "model_used": "syllabus_evidence_guard",
                "latency_ms": round(elapsed_ms, 2)
            }

        # 6. Build Bounded Academic Context Window
        context_passages = []
        total_chars = 0
        for i, chunk in enumerate(qualifying_chunks, 1):
            passage_text = chunk.get("text") or chunk.get("source_evidence") or ""
            header = f"[Passage {i}] {chunk.get('subject_code', '')} {chunk.get('subject_name', '')}"
            if chunk.get("unit_number"):
                header += f" | Unit {chunk['unit_number']}: {chunk.get('unit_title', 'Unit')}"
            if chunk.get("topic_title"):
                header += f" | Topic: {chunk['topic_title']}"
            if chunk.get("source_page"):
                header += f" (Page {chunk['source_page']})"

            passage_block = f"{header}\nContent: {passage_text.strip()}"
            if total_chars + len(passage_block) > self.max_context_chars:
                # Add truncated passage if room allows
                remaining = self.max_context_chars - total_chars
                if remaining > 100:
                    passage_block = passage_block[:remaining].strip() + "..."
                    context_passages.append(passage_block)
                break

            context_passages.append(passage_block)
            total_chars += len(passage_block)

        context_str = "\n\n".join(context_passages)

        # 7. Grounded Answer Generation via Shared Qwen Singleton
        gen_result = ai_generator.generate_study_buddy_answer(
            query=clean_query,
            context_str=context_str,
            sources=qualifying_chunks
        )

        answer_text = gen_result.get("answer", "")
        has_evidence = gen_result.get("has_sufficient_evidence", True)
        model_used = gen_result.get("model_used", settings.AI_MODEL_NAME)

        # 8. Build Verified Source Citations
        citations = []
        if has_evidence:
            for c in qualifying_chunks:
                citations.append({
                    "document_id": c["document_id"],
                    "version": c["version"],
                    "subject_id": c["subject_id"],
                    "subject_code": c["subject_code"],
                    "subject_name": c["subject_name"],
                    "department": c["department"],
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
