"""
Study Buddy Content Service (Summaries & Quizzes)

Orchestrates syllabus-grounded academic study summaries and interactive quizzes:
1. Enforces institutional role and department authorization against PostgreSQL.
2. Retrieves approved, published syllabus passages with version isolation and active subject checks.
3. Generates concise revision notes or detailed breakdowns via shared Qwen singleton.
4. Generates and server-side validates multiple-choice quizzes with hidden answer keys.
5. Persists quiz attempts and evaluates student submissions strictly server-side.
6. Enforces attempt ownership so students cannot view or submit other students' quizzes.
"""

import re
import time
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from ..core.config import settings
from ..models.user import User, UserRole
from ..models.study_buddy import (
    Subject,
    SyllabusDocument,
    SyllabusUnit,
    SyllabusTopic,
    SyllabusReviewStatus,
    QuizStatus,
    StudyBuddyQuizAttempt
)
from ..schemas.study_buddy import (
    StudyBuddyCitation,
    StudyBuddySummaryResponse,
    StudyBuddyQuizPublicResponse,
    QuizQuestionPublicResponse,
    StudyBuddyQuizResultResponse,
    QuizQuestionResultResponse,
    StudyBuddyQuizAttemptSummaryResponse
)
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


class StudyBuddyContentService:
    """
    Service for generating syllabus-grounded summaries and managing quizzes.
    """

    def _validate_subject_access(
        self,
        db: Session,
        current_user: User,
        subject_id: int
    ) -> Tuple[Subject, SyllabusDocument]:
        """
        Validates caller role, department boundary, subject active state,
        and retrieves the latest approved, published syllabus document.
        """
        # 1. Placement Officer check
        if current_user.role == UserRole.PLACEMENT_OFFICER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Placement Officers do not have access to Study Buddy academic materials."
            )

        # 2. User department check
        user_dept = _get_user_department(current_user)
        if current_user.role != UserRole.ADMIN and not user_dept:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no assigned academic department."
            )

        # 3. Subject active check
        subject = db.query(Subject).filter(
            Subject.id == subject_id,
            Subject.is_active == True
        ).first()

        if not subject:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subject ID {subject_id} not found or inactive."
            )

        # 4. Department boundary check
        if current_user.role == UserRole.LECTURER:
            if _normalize_dept(user_dept) != _normalize_dept(subject.department):
                assigned_subjects = []
                if current_user.lecturer_profile and current_user.lecturer_profile.subjects:
                    assigned_subjects = [str(s).strip().upper() for s in current_user.lecturer_profile.subjects]
                if subject.code.strip().upper() not in assigned_subjects:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Access denied: Subject belongs to department '{subject.department}'."
                    )
        elif current_user.role != UserRole.ADMIN:
            if _normalize_dept(user_dept) != _normalize_dept(subject.department):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: Subject belongs to department '{subject.department}'."
                )

        # 5. Published syllabus check
        published_doc = db.query(SyllabusDocument).filter(
            SyllabusDocument.subject_id == subject.id,
            SyllabusDocument.is_published == True,
            SyllabusDocument.review_status == SyllabusReviewStatus.APPROVED
        ).order_by(SyllabusDocument.version.desc()).first()

        if not published_doc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No approved published syllabus available for subject '{subject.code}'."
            )

        return subject, published_doc

    def _collect_grounded_evidence(
        self,
        db: Session,
        current_user: User,
        subject: Subject,
        published_doc: SyllabusDocument,
        unit_id: Optional[int] = None,
        topic_id: Optional[int] = None,
        search_query: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Gathers approved syllabus passages strictly belonging to the published syllabus document.
        Combines direct structured database units/topics and indexed vector chunks.
        """
        unit_obj = None
        topic_obj = None

        if unit_id:
            unit_obj = db.query(SyllabusUnit).filter(
                SyllabusUnit.id == unit_id,
                SyllabusUnit.document_id == published_doc.id
            ).first()
            if not unit_obj:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Unit ID {unit_id} not found in published syllabus for subject '{subject.code}'."
                )

        if topic_id:
            topic_query = db.query(SyllabusTopic).join(SyllabusUnit).filter(
                SyllabusTopic.id == topic_id,
                SyllabusUnit.document_id == published_doc.id
            )
            if unit_obj:
                topic_query = topic_query.filter(SyllabusTopic.unit_id == unit_obj.id)
            topic_obj = topic_query.first()
            if not topic_obj:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Topic ID {topic_id} not found in specified syllabus unit."
                )

        evidence_sources = []
        context_blocks = []

        # 1. Gather text directly from PostgreSQL structured units/topics
        if topic_obj:
            parent_unit = topic_obj.unit
            text_val = topic_obj.extracted_text or topic_obj.source_evidence or topic_obj.title
            evidence_sources.append({
                "document_id": published_doc.id,
                "version": published_doc.version,
                "subject_id": subject.id,
                "subject_code": subject.code,
                "subject_name": subject.name,
                "department": subject.department,
                "unit_number": parent_unit.unit_number if parent_unit else None,
                "unit_title": parent_unit.title if parent_unit else None,
                "topic_title": topic_obj.title,
                "source_page": topic_obj.source_page,
                "source_evidence": topic_obj.source_evidence or text_val,
                "chunk_order": topic_obj.order,
                "text": text_val,
                "score": 1.0
            })
            context_blocks.append(
                f"[Unit {parent_unit.unit_number or 1}: {parent_unit.title if parent_unit else 'Unit'} | "
                f"Topic: {topic_obj.title} (Page {topic_obj.source_page or 1})]\n"
                f"Content: {text_val.strip()}"
            )
        elif unit_obj:
            unit_desc = unit_obj.description or unit_obj.source_evidence or ""
            if unit_desc:
                evidence_sources.append({
                    "document_id": published_doc.id,
                    "version": published_doc.version,
                    "subject_id": subject.id,
                    "subject_code": subject.code,
                    "subject_name": subject.name,
                    "department": subject.department,
                    "unit_number": unit_obj.unit_number,
                    "unit_title": unit_obj.title,
                    "topic_title": None,
                    "source_page": unit_obj.source_page_start,
                    "source_evidence": unit_desc,
                    "chunk_order": unit_obj.order,
                    "text": unit_desc,
                    "score": 1.0
                })
                context_blocks.append(
                    f"[Unit {unit_obj.unit_number or 1}: {unit_obj.title}]\n"
                    f"Content: {unit_desc.strip()}"
                )
            for t in unit_obj.topics:
                text_val = t.extracted_text or t.source_evidence or t.title
                evidence_sources.append({
                    "document_id": published_doc.id,
                    "version": published_doc.version,
                    "subject_id": subject.id,
                    "subject_code": subject.code,
                    "subject_name": subject.name,
                    "department": subject.department,
                    "unit_number": unit_obj.unit_number,
                    "unit_title": unit_obj.title,
                    "topic_title": t.title,
                    "source_page": t.source_page,
                    "source_evidence": t.source_evidence or text_val,
                    "chunk_order": t.order,
                    "text": text_val,
                    "score": 1.0
                })
                context_blocks.append(
                    f"[Unit {unit_obj.unit_number or 1}: {unit_obj.title} | Topic: {t.title}]\n"
                    f"Content: {text_val.strip()}"
                )
        else:
            # Subject-wide: collect across all units of the published document
            for u in published_doc.units:
                unit_desc = u.description or u.source_evidence or ""
                if unit_desc:
                    evidence_sources.append({
                        "document_id": published_doc.id,
                        "version": published_doc.version,
                        "subject_id": subject.id,
                        "subject_code": subject.code,
                        "subject_name": subject.name,
                        "department": subject.department,
                        "unit_number": u.unit_number,
                        "unit_title": u.title,
                        "topic_title": None,
                        "source_page": u.source_page_start,
                        "source_evidence": unit_desc,
                        "chunk_order": u.order,
                        "text": unit_desc,
                        "score": 1.0
                    })
                    context_blocks.append(
                        f"[Unit {u.unit_number or 1}: {u.title}]\n"
                        f"Content: {unit_desc.strip()}"
                    )
                for t in u.topics:
                    text_val = t.extracted_text or t.source_evidence or t.title
                    evidence_sources.append({
                        "document_id": published_doc.id,
                        "version": published_doc.version,
                        "subject_id": subject.id,
                        "subject_code": subject.code,
                        "subject_name": subject.name,
                        "department": subject.department,
                        "unit_number": u.unit_number,
                        "unit_title": u.title,
                        "topic_title": t.title,
                        "source_page": t.source_page,
                        "source_evidence": t.source_evidence or text_val,
                        "chunk_order": t.order,
                        "text": text_val,
                        "score": 1.0
                    })
                    context_blocks.append(
                        f"[Unit {u.unit_number or 1}: {u.title} | Topic: {t.title}]\n"
                        f"Content: {text_val.strip()}"
                    )

        # 2. Complement with vector retrieved chunks if search query or needed
        query_str = search_query or (topic_obj.title if topic_obj else (unit_obj.title if unit_obj else subject.name))
        try:
            chunks = syllabus_indexing_service.search_chunks(
                db=db,
                query=query_str,
                current_user=current_user,
                subject_id=subject.id,
                limit=10
            )
            # Filter strictly to current published document id
            for c in chunks:
                if c.get("document_id") == published_doc.id:
                    # Check deduplication
                    already_present = any(
                        s.get("topic_title") == c.get("topic_title") and
                        s.get("unit_number") == c.get("unit_number") and
                        s.get("text", "")[:50] == (c.get("text") or "")[:50]
                        for s in evidence_sources
                    )
                    if not already_present:
                        evidence_sources.append(c)
                        c_text = c.get("text") or c.get("source_evidence") or ""
                        context_blocks.append(
                            f"[Unit {c.get('unit_number', 1)}: {c.get('unit_title', 'Unit')} | Topic: {c.get('topic_title', 'Core')}]\n"
                            f"Content: {c_text.strip()}"
                        )
        except Exception as q_err:
            logger.warning(f"Vector chunk retrieval complement skipped: {q_err}")

        # Cap bounded context
        max_chars = settings.STUDY_BUDDY_MAX_CONTEXT_CHARS * 2
        joined_context = "\n\n".join(context_blocks)
        if len(joined_context) > max_chars:
            joined_context = joined_context[:max_chars].rsplit("\n\n", 1)[0] + "\n..."

        return evidence_sources, joined_context

    def generate_summary(
        self,
        db: Session,
        current_user: User,
        subject_id: int,
        unit_id: Optional[int] = None,
        topic_id: Optional[int] = None,
        format_type: str = "concise"
    ) -> StudyBuddySummaryResponse:
        """
        Generate a syllabus-grounded academic study summary.
        """
        start_time = time.time()
        subject, published_doc = self._validate_subject_access(db, current_user, subject_id)

        evidence_sources, context_str = self._collect_grounded_evidence(
            db=db,
            current_user=current_user,
            subject=subject,
            published_doc=published_doc,
            unit_id=unit_id,
            topic_id=topic_id
        )

        # Title assembly
        scope_parts = [f"{subject.code} {subject.name}"]
        if unit_id:
            u = db.query(SyllabusUnit).filter(SyllabusUnit.id == unit_id).first()
            if u:
                scope_parts.append(f"Unit {u.unit_number or u.order}: {u.title}")
        if topic_id:
            t = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id).first()
            if t:
                scope_parts.append(f"Topic: {t.title}")

        summary_title = " - ".join(scope_parts)

        if not evidence_sources or not context_str.strip():
            elapsed_ms = (time.time() - start_time) * 1000
            return StudyBuddySummaryResponse(
                title=summary_title,
                summary=(
                    "The approved syllabus material does not provide sufficient information to generate a study summary. "
                    "Please consult your subject lecturer or course coordinator for clarification."
                ),
                format_type=format_type,
                has_sufficient_evidence=False,
                citations=[],
                subject_id=subject.id,
                subject_code=subject.code,
                subject_name=subject.name,
                unit_id=unit_id,
                topic_id=topic_id,
                model_used="syllabus_evidence_guard",
                latency_ms=round(elapsed_ms, 2)
            )

        gen_res = ai_generator.generate_study_buddy_summary(
            title=summary_title,
            context_str=context_str,
            sources=evidence_sources,
            format_type=format_type
        )

        summary_text = gen_res.get("summary", "")
        has_evidence = gen_res.get("has_sufficient_evidence", True)
        model_used = gen_res.get("model_used", settings.AI_MODEL_NAME)

        citations = []
        if has_evidence:
            seen_cits = set()
            for s in evidence_sources:
                c_key = (s.get("document_id"), s.get("unit_number"), s.get("topic_title"), s.get("source_page"))
                if c_key in seen_cits:
                    continue
                seen_cits.add(c_key)
                citations.append(
                    StudyBuddyCitation(
                        document_id=s["document_id"],
                        version=s["version"],
                        subject_id=s["subject_id"],
                        subject_code=s["subject_code"],
                        subject_name=s["subject_name"],
                        department=s["department"],
                        unit_number=s.get("unit_number"),
                        unit_title=s.get("unit_title"),
                        topic_title=s.get("topic_title"),
                        source_page=s.get("source_page"),
                        source_evidence=s.get("source_evidence"),
                        chunk_order=s.get("chunk_order"),
                        relevance_score=round(float(s.get("score", 1.0)), 4)
                    )
                )

        elapsed_ms = (time.time() - start_time) * 1000
        return StudyBuddySummaryResponse(
            title=summary_title,
            summary=summary_text,
            format_type=format_type,
            has_sufficient_evidence=has_evidence,
            citations=citations,
            subject_id=subject.id,
            subject_code=subject.code,
            subject_name=subject.name,
            unit_id=unit_id,
            topic_id=topic_id,
            model_used=model_used,
            latency_ms=round(elapsed_ms, 2)
        )

    def generate_quiz(
        self,
        db: Session,
        current_user: User,
        subject_id: int,
        unit_id: Optional[int] = None,
        topic_id: Optional[int] = None,
        num_questions: int = 5,
        difficulty: str = "medium"
    ) -> StudyBuddyQuizPublicResponse:
        """
        Generate a syllabus-grounded multiple-choice quiz and persist the attempt.
        Answer keys and explanations are stored server-side and STRIPPED from the returned public response.
        """
        subject, published_doc = self._validate_subject_access(db, current_user, subject_id)

        evidence_sources, context_str = self._collect_grounded_evidence(
            db=db,
            current_user=current_user,
            subject=subject,
            published_doc=published_doc,
            unit_id=unit_id,
            topic_id=topic_id
        )

        title_parts = [f"{subject.code} {subject.name} Quiz ({difficulty.capitalize()})"]
        if unit_id:
            u = db.query(SyllabusUnit).filter(SyllabusUnit.id == unit_id).first()
            if u:
                title_parts.append(f"Unit {u.unit_number or u.order}")
        if topic_id:
            t = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id).first()
            if t:
                title_parts.append(f"Topic: {t.title}")

        quiz_title = " - ".join(title_parts)

        if not evidence_sources or not context_str.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient syllabus evidence to generate a grounded quiz for this selection."
            )

        gen_res = ai_generator.generate_study_buddy_quiz(
            subject_name=f"{subject.code} {subject.name}",
            context_str=context_str,
            sources=evidence_sources,
            num_questions=num_questions,
            difficulty=difficulty
        )

        candidate_questions = gen_res.get("questions", [])
        model_used = gen_res.get("model_used", "deterministic_syllabus_synthesizer")

        # 4. Strict Server-Side Question Validation against Retrieved Evidence
        raw_evidence_text = " ".join([s.get("text", "") or s.get("source_evidence", "") for s in evidence_sources]).strip()
        evidence_sentences = [
            s.strip() for s in re.split(r'(?<=[.!?])\s+', raw_evidence_text)
            if len(s.strip()) > 15
        ]
        max_supportable_questions = max(1, min(len(evidence_sentences) * 2, num_questions))

        valid_questions = []
        seen_questions = set()

        for q in candidate_questions:
            q_text = str(q.get("question", "")).strip()
            options = q.get("options", [])
            correct_idx = q.get("correct_option_index")
            explanation = str(q.get("explanation", "")).strip()

            # Question length & non-empty
            if len(q_text) < 10:
                continue

            # Exactly 4 options and all strings
            if not isinstance(options, list) or len(options) != 4:
                continue
            clean_options = [str(opt).strip() for opt in options if str(opt).strip()]
            if len(clean_options) != 4 or len(set(clean_options)) != 4:
                # Malformed options or duplicates
                continue

            # Valid correct index in range 0..3
            try:
                correct_idx = int(correct_idx)
                if correct_idx < 0 or correct_idx > 3:
                    continue
            except (TypeError, ValueError):
                continue

            # Deduplication
            q_norm = q_text.lower()
            if q_norm in seen_questions:
                continue
            seen_questions.add(q_norm)

            # Grounding check: correct option must have token support in retrieved context
            correct_opt_text = clean_options[correct_idx].lower()
            ans_tokens = [w for w in re.findall(r'[a-zA-Z0-9]{3,}', correct_opt_text)]
            stop_words = {"the", "and", "for", "with", "that", "this", "from", "are", "not", "has", "have", "can", "all", "none"}
            meaningful_ans = [w for w in ans_tokens if w not in stop_words]
            if meaningful_ans and not any(w in context_str.lower() for w in meaningful_ans):
                logger.info(f"🛡️ Question rejected: correct answer '{correct_opt_text}' not grounded in syllabus context")
                continue

            # Assign or resolve citation
            citation_data = q.get("citation")
            if not citation_data and evidence_sources:
                src = evidence_sources[0]
                citation_data = {
                    "document_id": src.get("document_id"),
                    "version": src.get("version"),
                    "subject_id": src.get("subject_id"),
                    "subject_code": src.get("subject_code"),
                    "subject_name": src.get("subject_name"),
                    "department": src.get("department"),
                    "unit_number": src.get("unit_number"),
                    "unit_title": src.get("unit_title"),
                    "topic_title": src.get("topic_title"),
                    "source_page": src.get("source_page"),
                    "source_evidence": src.get("source_evidence"),
                    "chunk_order": src.get("chunk_order"),
                    "relevance_score": float(src.get("score", 1.0))
                }

            valid_questions.append({
                "question_id": len(valid_questions) + 1,
                "question": q_text,
                "options": clean_options,
                "correct_option_index": correct_idx,
                "explanation": explanation or f"Grounded in verified syllabus material for {subject.code}.",
                "citation": citation_data
            })

            if len(valid_questions) >= min(num_questions, max_supportable_questions):
                break

        if not valid_questions:
            # Direct synthesis from verified syllabus evidence sources
            fallback_cands = ai_generator._synthesize_study_buddy_quiz(
                subject_name=f"{subject.code} {subject.name}",
                sources=evidence_sources,
                num_questions=min(num_questions, max_supportable_questions),
                difficulty=difficulty
            )
            for fq in fallback_cands:
                valid_questions.append({
                    "question_id": len(valid_questions) + 1,
                    "question": fq["question"],
                    "options": fq["options"],
                    "correct_option_index": fq["correct_option_index"],
                    "explanation": fq.get("explanation") or f"Grounded in verified syllabus material for {subject.code}.",
                    "citation": fq.get("citation") or (evidence_sources[0] if evidence_sources else None)
                })
                if len(valid_questions) >= min(num_questions, max_supportable_questions):
                    break
            if valid_questions:
                model_used = "deterministic_syllabus_synthesizer"

        if not valid_questions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to generate valid, evidence-grounded quiz questions from current syllabus passages."
            )

        shortfall_note = None
        if len(valid_questions) < num_questions:
            shortfall_note = (
                f"Requested {num_questions} questions, but approved syllabus evidence supported "
                f"{len(valid_questions)} verified questions."
            )

        # 5. Persist Quiz Attempt in PostgreSQL
        attempt = StudyBuddyQuizAttempt(
            student_id=current_user.id,
            subject_id=subject.id,
            syllabus_document_id=published_doc.id,
            syllabus_version=published_doc.version,
            unit_id=unit_id,
            topic_id=topic_id,
            title=quiz_title,
            difficulty=difficulty,
            total_questions=len(valid_questions),
            questions_data=valid_questions,
            status=QuizStatus.GENERATED
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        # 6. Build Public Response: STRIP OUT correct_option_index and explanation!
        public_questions = [
            QuizQuestionPublicResponse(
                question_id=vq["question_id"],
                question=vq["question"],
                options=vq["options"]
            )
            for vq in valid_questions
        ]

        return StudyBuddyQuizPublicResponse(
            id=attempt.id,
            subject_id=subject.id,
            subject_code=subject.code,
            subject_name=subject.name,
            syllabus_version=published_doc.version,
            unit_id=unit_id,
            topic_id=topic_id,
            title=attempt.title,
            difficulty=attempt.difficulty,
            total_questions=attempt.total_questions,
            questions=public_questions,
            status=attempt.status.value,
            created_at=attempt.created_at,
            model_used=model_used,
            shortfall_note=shortfall_note
        )

    def submit_quiz(
        self,
        db: Session,
        current_user: User,
        attempt_id: int,
        student_answers: Dict[str, int]
    ) -> StudyBuddyQuizResultResponse:
        """
        Evaluate and persist quiz submission strictly server-side.
        Enforces ownership and prevents tampering with scores or answers.
        """
        attempt = db.query(StudyBuddyQuizAttempt).filter(StudyBuddyQuizAttempt.id == attempt_id).first()
        if not attempt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz attempt not found.")

        # Ownership check
        if attempt.student_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You cannot submit answers for another student's quiz attempt."
            )

        # State check: prevent resubmission
        if attempt.status == QuizStatus.COMPLETED:
            return self.get_quiz_result(db, current_user, attempt_id)

        questions = attempt.questions_data or []
        correct_count = 0
        questions_results = []

        for q in questions:
            q_id = str(q.get("question_id"))
            chosen_idx = student_answers.get(q_id)
            correct_idx = q.get("correct_option_index")
            is_correct = (chosen_idx is not None and int(chosen_idx) == int(correct_idx))
            if is_correct:
                correct_count += 1

            citation_obj = None
            if q.get("citation"):
                c_data = q["citation"]
                citation_obj = StudyBuddyCitation(
                    document_id=c_data.get("document_id") or attempt.syllabus_document_id,
                    version=c_data.get("version") or attempt.syllabus_version,
                    subject_id=c_data.get("subject_id") or attempt.subject_id,
                    subject_code=c_data.get("subject_code") or attempt.subject.code,
                    subject_name=c_data.get("subject_name") or attempt.subject.name,
                    department=c_data.get("department") or attempt.subject.department,
                    unit_number=c_data.get("unit_number"),
                    unit_title=c_data.get("unit_title"),
                    topic_title=c_data.get("topic_title"),
                    source_page=c_data.get("source_page"),
                    source_evidence=c_data.get("source_evidence"),
                    chunk_order=c_data.get("chunk_order"),
                    relevance_score=round(float(c_data.get("relevance_score", 1.0)), 4)
                )

            questions_results.append(
                QuizQuestionResultResponse(
                    question_id=int(q_id),
                    question=q["question"],
                    options=q["options"],
                    selected_option_index=chosen_idx,
                    correct_option_index=correct_idx,
                    is_correct=is_correct,
                    explanation=q.get("explanation", ""),
                    citation=citation_obj
                )
            )

        total = len(questions)
        pct = round((correct_count / total * 100.0), 2) if total > 0 else 0.0

        # Update persisted record
        attempt.status = QuizStatus.COMPLETED
        attempt.score = float(correct_count)
        attempt.max_score = total
        attempt.percentage = pct
        attempt.student_answers = student_answers
        attempt.submitted_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(attempt)

        return StudyBuddyQuizResultResponse(
            id=attempt.id,
            student_id=attempt.student_id,
            subject_id=attempt.subject_id,
            subject_code=attempt.subject.code,
            subject_name=attempt.subject.name,
            syllabus_version=attempt.syllabus_version,
            unit_id=attempt.unit_id,
            topic_id=attempt.topic_id,
            title=attempt.title,
            difficulty=attempt.difficulty,
            status=attempt.status.value,
            score=attempt.score,
            max_score=attempt.max_score,
            percentage=attempt.percentage,
            submitted_at=attempt.submitted_at,
            questions_results=questions_results
        )

    def get_quiz_result(
        self,
        db: Session,
        current_user: User,
        attempt_id: int
    ) -> StudyBuddyQuizResultResponse:
        """
        Retrieve completed quiz results with ownership protection.
        """
        attempt = db.query(StudyBuddyQuizAttempt).filter(StudyBuddyQuizAttempt.id == attempt_id).first()
        if not attempt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz attempt not found.")

        # Ownership check
        if current_user.role != UserRole.ADMIN and attempt.student_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You cannot view results for another student's quiz attempt."
            )

        questions = attempt.questions_data or []
        student_answers = attempt.student_answers or {}
        questions_results = []

        for q in questions:
            q_id = str(q.get("question_id"))
            chosen_idx = student_answers.get(q_id)
            correct_idx = q.get("correct_option_index")
            is_correct = (chosen_idx is not None and int(chosen_idx) == int(correct_idx))

            citation_obj = None
            if q.get("citation"):
                c_data = q["citation"]
                citation_obj = StudyBuddyCitation(
                    document_id=c_data.get("document_id") or attempt.syllabus_document_id,
                    version=c_data.get("version") or attempt.syllabus_version,
                    subject_id=c_data.get("subject_id") or attempt.subject_id,
                    subject_code=c_data.get("subject_code") or attempt.subject.code,
                    subject_name=c_data.get("subject_name") or attempt.subject.name,
                    department=c_data.get("department") or attempt.subject.department,
                    unit_number=c_data.get("unit_number"),
                    unit_title=c_data.get("unit_title"),
                    topic_title=c_data.get("topic_title"),
                    source_page=c_data.get("source_page"),
                    source_evidence=c_data.get("source_evidence"),
                    chunk_order=c_data.get("chunk_order"),
                    relevance_score=round(float(c_data.get("relevance_score", 1.0)), 4)
                )

            questions_results.append(
                QuizQuestionResultResponse(
                    question_id=int(q_id),
                    question=q["question"],
                    options=q["options"],
                    selected_option_index=chosen_idx,
                    correct_option_index=correct_idx,
                    is_correct=is_correct,
                    explanation=q.get("explanation", ""),
                    citation=citation_obj
                )
            )

        return StudyBuddyQuizResultResponse(
            id=attempt.id,
            student_id=attempt.student_id,
            subject_id=attempt.subject_id,
            subject_code=attempt.subject.code,
            subject_name=attempt.subject.name,
            syllabus_version=attempt.syllabus_version,
            unit_id=attempt.unit_id,
            topic_id=attempt.topic_id,
            title=attempt.title,
            difficulty=attempt.difficulty,
            status=attempt.status.value,
            score=attempt.score or 0.0,
            max_score=attempt.max_score or len(questions),
            percentage=attempt.percentage or 0.0,
            submitted_at=attempt.submitted_at,
            questions_results=questions_results
        )

    def list_student_attempts(
        self,
        db: Session,
        current_user: User,
        subject_id: Optional[int] = None
    ) -> List[StudyBuddyQuizAttemptSummaryResponse]:
        """
        List past quiz attempts for the authenticated student.
        """
        query = db.query(StudyBuddyQuizAttempt).filter(
            StudyBuddyQuizAttempt.student_id == current_user.id
        )
        if subject_id:
            query = query.filter(StudyBuddyQuizAttempt.subject_id == subject_id)

        attempts = query.order_by(StudyBuddyQuizAttempt.created_at.desc()).all()

        return [
            StudyBuddyQuizAttemptSummaryResponse(
                id=a.id,
                subject_id=a.subject_id,
                subject_code=a.subject.code,
                subject_name=a.subject.name,
                syllabus_version=a.syllabus_version,
                title=a.title,
                difficulty=a.difficulty,
                status=a.status.value,
                score=a.score,
                max_score=a.max_score,
                percentage=a.percentage,
                total_questions=a.total_questions,
                created_at=a.created_at,
                submitted_at=a.submitted_at
            )
            for a in attempts
        ]


study_buddy_content_service = StudyBuddyContentService()
