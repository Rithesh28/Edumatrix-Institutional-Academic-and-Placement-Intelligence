"""
Institutional Retrieval Service

Retrieves factual institutional information from:
- PostgreSQL: Circulars, Deadlines, Reminders, Exam Schedules, Job Postings
- Qdrant & MinIO: Academic Documents, Files, Notes
"""

import re
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from ..models.circular import Circular, CircularType
from ..models.reminder import Reminder
from ..models.job_posting import JobPosting
from ..models.company import Company
from ..models.exam_duty import ExamDuty
from ..models.file import File, FileStatus
from .file_storage.search_service import search_service
from .file_storage.text_extractor import text_extractor
from .file_storage.minio_client import minio_client

logger = logging.getLogger(__name__)


class InstitutionalRetrievalService:
    """
    Retrieves grounded institutional data from PostgreSQL and Qdrant.
    """

    # Comprehensive vocabulary of generic question tokens, pronouns, prepositions,
    # and generic institutional workflow/academic terms (NOT specific subject entities).
    GENERIC_QUERY_TERMS = {
        # Question words, pronouns, prepositions, determiners, auxiliary verbs
        "what", "when", "where", "which", "who", "whom", "whose", "why", "how",
        "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
        "do", "does", "did", "the", "a", "an", "and", "or", "but", "if", "then",
        "else", "at", "by", "for", "with", "about", "against", "between", "into",
        "through", "during", "before", "after", "above", "below", "to", "from",
        "up", "down", "in", "out", "on", "off", "over", "under", "all", "any",
        "both", "each", "few", "more", "most", "other", "some", "such", "no",
        "nor", "not", "only", "own", "same", "so", "than", "too", "very", "can",
        "could", "will", "would", "should", "just", "now", "tell", "give", "show",
        "know", "please", "me", "my", "our", "your", "i", "we", "you", "he", "she",
        "it", "they", "this", "that", "these", "those", "of", "there", "their",
        "want", "need", "check", "find", "get", "uploaded", "upload", "doc", "document",
        "today", "tomorrow", "yesterday",
        # Generic academic & workflow terms (must NOT be treated as subject entities)
        "date", "dates", "deadline", "deadlines", "last", "day", "days", "time", "times",
        "submission", "submissions", "submit", "submitting", "submitted", "due",
        "due_date", "duedate",
        "assignment", "assignments", "homework", "task", "tasks", "project", "projects",
        "exam", "exams", "examination", "examinations", "test", "tests", "midterm", "finals",
        "schedule", "schedules", "circular", "circulars", "notice", "notices",
        "info", "information", "detail", "details", "update", "updates", "status"
    }

    def extract_specific_entities(self, query_text: str) -> List[str]:
        """
        Extracts subject, course, acronym, or unique entity tokens from the query,
        strictly filtering out all generic academic workflow words and stopwords.
        Preserves 2+ character acronyms/identifiers (e.g., 'dsp', 'ml', 'os', 'cn', 'dbms').
        """
        tokens = re.findall(r'\b[a-zA-Z0-9_-]{2,}\b', (query_text or "").lower())
        return [t for t in tokens if t not in self.GENERIC_QUERY_TERMS]

    def detect_ambiguity(
        self,
        query_text: str,
        sources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Determines whether the query contains enough information to identify a unique
        assignment or exam. If the query is generic and multiple matching items exist,
        returns ambiguity details so the system can ask for clarification rather than
        arbitrarily selecting one.
        """
        clean_query = (query_text or "").lower()
        specific_entities = self.extract_specific_entities(clean_query)
        is_assignment_query = any(w in clean_query for w in ["assignment", "homework", "task", "project", "submission", "submit"])
        is_exam_query = any(w in clean_query for w in ["exam", "examination", "test", "midterm", "finals"])

        # If a specific subject entity was identified (e.g. 'DSP', 'ML'), query is specific
        if specific_entities:
            return {
                "is_ambiguous": False,
                "category": "assignment" if is_assignment_query else ("exam" if is_exam_query else "general"),
                "candidates": sources,
                "candidate_count": len(sources)
            }

        # 1. Check for ambiguous assignments
        if is_assignment_query:
            assignment_sources = [
                s for s in sources
                if (s.get("category") == "assignment" or "assignment" in (s.get("title") or "").lower())
                and s.get("due_date")
            ]
            # Deduplicate by normalized title
            unique_assignments: List[Dict[str, Any]] = []
            seen_titles = set()
            for src in assignment_sources:
                norm_title = (src.get("title") or "").strip().lower()
                if norm_title and norm_title not in seen_titles:
                    seen_titles.add(norm_title)
                    unique_assignments.append(src)

            if len(unique_assignments) > 1:
                return {
                    "is_ambiguous": True,
                    "category": "assignment",
                    "candidates": unique_assignments,
                    "candidate_count": len(unique_assignments)
                }

        # 2. Check for ambiguous exams
        if is_exam_query:
            exam_sources = [
                s for s in sources
                if (s.get("category") == "exam" or "exam" in (s.get("title") or "").lower() or s.get("source_type") == "exam_duty")
            ]
            unique_exams: List[Dict[str, Any]] = []
            seen_titles = set()
            for src in exam_sources:
                norm_title = (src.get("title") or "").strip().lower()
                if norm_title and norm_title not in seen_titles:
                    seen_titles.add(norm_title)
                    unique_exams.append(src)

            if len(unique_exams) > 1:
                return {
                    "is_ambiguous": True,
                    "category": "exam",
                    "candidates": unique_exams,
                    "candidate_count": len(unique_exams)
                }

        return {
            "is_ambiguous": False,
            "category": "assignment" if is_assignment_query else ("exam" if is_exam_query else "general"),
            "candidates": sources,
            "candidate_count": len(sources)
        }

    def retrieve_deadlines(
        self,
        db: Session,
        query_text: str,
        department: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve structured deadline information from circulars and job postings.
        Ensures specific query entities dominate over generic academic keywords.
        """
        results: List[Dict[str, Any]] = []
        now = datetime.utcnow()
        clean_query = query_text.lower()

        try:
            specific_entities = self.extract_specific_entities(clean_query)
            is_assignment_query = any(w in clean_query for w in ["assignment", "homework", "task", "project", "submission", "submit"])
            is_exam_query = any(w in clean_query for w in ["exam", "test", "midterm", "finals"])

            # 1. Query circulars with due dates
            circular_query = db.query(Circular).filter(Circular.due_date.isnot(None))

            # Build SQL pre-filters for specific entity queries to avoid loading all circulars
            if specific_entities:
                # Escape SQL wildcard characters and build OR conditions for each entity
                # We search both title and content. Use ILIKE for case-insensitive matching.
                entity_conditions = []
                for e in specific_entities:
                    # Escape SQL wildcards in the entity
                    escaped = e.replace('%', r'\%').replace('_', r'\_')
                    # Match entity as word boundary using ILIKE with spaces/punctuation
                    # Note: word boundaries in ILIKE are not perfect, but this provides
                    # a safe pre-filter; exact boundaries are verified in Python below.
                    entity_conditions.append(Circular.title.ilike(f"% {escaped} %"))
                    entity_conditions.append(Circular.title.ilike(f"{escaped} %"))
                    entity_conditions.append(Circular.title.ilike(f"% {escaped}"))
                    entity_conditions.append(Circular.content.ilike(f"% {escaped} %"))
                    entity_conditions.append(Circular.content.ilike(f"{escaped} %"))
                    entity_conditions.append(Circular.content.ilike(f"% {escaped}"))

                if entity_conditions:
                    circular_query = circular_query.filter(or_(*entity_conditions))

                # Fetch a bounded set of candidates, sorted by due date (most relevant first)
                # Use a generous limit (100) to avoid excluding the correct assignment
                # while still bounding data transfer.
                candidate_circulars = circular_query.order_by(Circular.due_date.asc()).limit(100).all()
            else:
                # Generic query: fetch only assignment/exam type circulars
                # to reduce Python-side filtering workload
                if is_assignment_query:
                    circular_query = circular_query.filter(
                        or_(
                            Circular.type == CircularType.ASSIGNMENT,
                            Circular.title.ilike("%assignment%"),
                            Circular.content.ilike("%assignment%")
                        )
                    )
                elif is_exam_query:
                    circular_query = circular_query.filter(
                        or_(
                            Circular.type == CircularType.EXAM,
                            Circular.title.ilike("%exam%"),
                            Circular.content.ilike("%exam%")
                        )
                    )
                candidate_circulars = circular_query.order_by(Circular.due_date.asc()).limit(100).all()

            for circ in candidate_circulars:
                title_lower = (circ.title or "").lower()
                content_lower = (circ.content or "").lower()
                circ_type = circ.type.value if hasattr(circ.type, 'value') else str(circ.type).lower()

                # A. Specific Entity Filtering:
                # If the user specified a subject/topic entity (e.g. 'DSP', 'ML', 'Python'),
                # require that the circular explicitly matches that entity.
                # Unrelated circulars (e.g. 'ML' when querying 'DSP') MUST be filtered out completely.
                if specific_entities:
                    matched_title_entities = [
                        e for e in specific_entities
                        if re.search(rf'\b{re.escape(e)}\b', title_lower)
                    ]
                    matched_content_entities = [
                        e for e in specific_entities
                        if re.search(rf'\b{re.escape(e)}\b', content_lower)
                    ]

                    if not matched_title_entities and not matched_content_entities:
                        # Unrelated document: does not contain requested entity
                        continue

                    # Exact entity match scoring
                    score = 1.0
                    if matched_title_entities:
                        # Entity in title has highest importance
                        score += 1.0 * len(matched_title_entities)
                    if matched_content_entities:
                        score += 0.5 * len(matched_content_entities)
                    if is_assignment_query and (circ_type == "assignment" or "assignment" in title_lower):
                        score += 0.3
                else:
                    # B. Generic Query (e.g. 'last date for assignment submission'):
                    # Only match circulars of relevant category
                    if is_assignment_query:
                        if circ_type != "assignment" and "assignment" not in title_lower and "assignment" not in content_lower:
                            continue
                    elif is_exam_query:
                        if circ_type != "exam" and "exam" not in title_lower and "exam" not in content_lower:
                            continue
                    score = 0.8

                due_dt = circ.due_date.replace(tzinfo=None) if circ.due_date else None
                days_until = (due_dt - now).days if due_dt else None

                results.append({
                    "source_type": "circular",
                    "source_id": circ.id,
                    "title": circ.title,
                    "category": circ_type,
                    "due_date": circ.due_date.strftime("%Y-%m-%d %H:%M") if circ.due_date else None,
                    "due_date_iso": circ.due_date.isoformat() if circ.due_date else None,
                    "days_remaining": days_until,
                    "is_upcoming": days_until is not None and days_until >= 0,
                    "content": circ.content,
                    "score": round(score, 2),
                    "has_verified_text": True
                })

            # 2. If query explicitly mentions placement/job/drive/application, check job postings
            if any(term in clean_query for term in ["job", "placement", "drive", "internship", "company", "apply", "application"]):
                jobs = db.query(JobPosting).filter(
                    JobPosting.application_deadline.isnot(None),
                    JobPosting.status == "open"
                ).order_by(JobPosting.application_deadline.asc()).limit(limit).all()

                for job in jobs:
                    company_name = job.company.name if job.company else "Campus Placement"
                    deadline_dt = job.application_deadline.replace(tzinfo=None) if job.application_deadline else None
                    days_until = (deadline_dt - now).days if deadline_dt else None

                    results.append({
                        "source_type": "job_posting",
                        "source_id": job.id,
                        "title": f"{job.title} ({company_name})",
                        "category": "placement",
                        "due_date": job.application_deadline.strftime("%Y-%m-%d") if job.application_deadline else None,
                        "due_date_iso": job.application_deadline.isoformat() if job.application_deadline else None,
                        "days_remaining": days_until,
                        "is_upcoming": days_until is not None and days_until >= 0,
                        "content": job.description or f"Position: {job.title} at {company_name}",
                        "score": 0.85,
                        "has_verified_text": True
                    })

            # Sort by score descending, then upcoming deadlines
            results.sort(key=lambda r: (r["score"], r.get("is_upcoming", False)), reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error(f"❌ Failed to retrieve deadlines: {e}", exc_info=True)
            return []

    def retrieve_exam_information(
        self,
        db: Session,
        query_text: str,
        department: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve exam schedules, exam circulars, and duty information.
        """
        results: List[Dict[str, Any]] = []
        clean_query = query_text.lower()

        try:
            specific_entities = self.extract_specific_entities(clean_query)

            # 1. Circulars of type EXAM or with 'exam' in title/content
            exam_circulars = db.query(Circular).filter(
                or_(
                    Circular.type == CircularType.EXAM,
                    Circular.title.ilike("%exam%"),
                    Circular.content.ilike("%exam%")
                )
            ).order_by(desc(Circular.created_at)).all()

            for circ in exam_circulars:
                title_lower = (circ.title or "").lower()
                content_lower = (circ.content or "").lower()
                circ_type = circ.type.value if hasattr(circ.type, 'value') else str(circ.type)

                if specific_entities:
                    matched = [
                        e for e in specific_entities
                        if re.search(rf'\b{re.escape(e)}\b', title_lower) or re.search(rf'\b{re.escape(e)}\b', content_lower)
                    ]
                    if not matched:
                        continue
                    score = 1.0 + 0.5 * len(matched)
                else:
                    score = 0.8 if "exam" in title_lower else 0.6

                results.append({
                    "source_type": "circular",
                    "source_id": circ.id,
                    "title": circ.title,
                    "category": circ_type,
                    "due_date": circ.due_date.strftime("%Y-%m-%d") if circ.due_date else None,
                    "content": circ.content,
                    "score": round(score, 2),
                    "has_verified_text": True
                })

            # 2. Check exam duties for scheduled dates/venues if relevant
            duties = db.query(ExamDuty).order_by(desc(ExamDuty.date)).all()
            for duty in duties:
                exam_name_lower = (duty.exam_name or "").lower()
                dept_lower = (duty.department or "").lower()

                if specific_entities:
                    matched = [
                        e for e in specific_entities
                        if re.search(rf'\b{re.escape(e)}\b', exam_name_lower) or re.search(rf'\b{re.escape(e)}\b', dept_lower)
                    ]
                    if not matched:
                        continue
                    score = 0.9 + 0.3 * len(matched)
                else:
                    score = 0.5

                results.append({
                    "source_type": "exam_duty",
                    "source_id": duty.id,
                    "title": f"Exam Duty: {duty.exam_name} ({duty.department})",
                    "category": "exam_duty",
                    "date": duty.date.strftime("%Y-%m-%d") if duty.date else None,
                    "venue": duty.venue,
                    "content": f"Exam: {duty.exam_name}, Date: {duty.date}, Time: {duty.start_time} - {duty.end_time}, Venue: {duty.venue or 'TBD'}, Department: {duty.department}",
                    "score": round(score, 2),
                    "has_verified_text": True
                })

            results.sort(key=lambda r: r["score"], reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error(f"❌ Failed to retrieve exam information: {e}", exc_info=True)
            return []

    def retrieve_placement_information(
        self,
        db: Session,
        query_text: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve placement drives, companies, and job postings.
        """
        results: List[Dict[str, Any]] = []
        clean_query = query_text.lower()

        try:
            jobs = db.query(JobPosting).filter(JobPosting.status == "open").all()
            for job in jobs:
                company_name = job.company.name if job.company else "Unknown Company"
                title_match = (job.title or "").lower()
                skills_match = str(job.required_skills or "").lower()

                score = 0.5
                if any(w in title_match or w in skills_match for w in clean_query.split() if len(w) > 3):
                    score += 0.4

                results.append({
                    "source_type": "job_posting",
                    "source_id": job.id,
                    "title": f"{job.title} at {company_name}",
                    "category": "placement",
                    "company": company_name,
                    "skills": job.required_skills,
                    "deadline": job.application_deadline.strftime("%Y-%m-%d") if job.application_deadline else None,
                    "salary": job.salary_range,
                    "content": f"Company: {company_name}. Title: {job.title}. Requirements: {job.required_skills}. Deadline: {job.application_deadline}.",
                    "score": round(score, 2),
                    "has_verified_text": True
                })

            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error(f"❌ Failed to retrieve placement info: {e}", exc_info=True)
            return []



    def _extract_best_passage(
        self,
        full_text: str,
        query: str,
        chunk_size: int = 500,
        overlap: int = 100
    ) -> Optional[str]:
        """
        Splits extracted document text into chunks and returns the passage
        most relevant to the user query based on keyword overlap.
        """
        if not full_text or not full_text.strip():
            return None

        # Split by paragraph breaks first
        raw_paragraphs = [p.strip() for p in full_text.split("\n\n") if len(p.strip()) > 20]
        chunks: List[str] = []

        if raw_paragraphs:
            current_chunk = ""
            for p in raw_paragraphs:
                if len(current_chunk) + len(p) <= chunk_size:
                    current_chunk += ("\n" + p if current_chunk else p)
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = p[:chunk_size]
            if current_chunk:
                chunks.append(current_chunk)
        else:
            # Sliding window over character stream
            start = 0
            while start < len(full_text):
                end = min(start + chunk_size, len(full_text))
                chunks.append(full_text[start:end].strip())
                if end == len(full_text):
                    break
                start += (chunk_size - overlap)

        if not chunks:
            return full_text[:chunk_size].strip()

        # Score chunks against query keywords
        query_terms = [w.lower() for w in re.findall(r'\b[a-zA-Z0-9_-]{3,}\b', query)]
        if not query_terms:
            return chunks[0]

        best_chunk = chunks[0]
        max_score = -1
        for chunk in chunks:
            chunk_lower = chunk.lower()
            score = sum(1 for term in query_terms if term in chunk_lower)
            if score > max_score:
                max_score = score
                best_chunk = chunk

        return best_chunk

    def retrieve_academic_documents(
        self,
        db: Session,
        query_text: str,
        department: Optional[str] = None,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Retrieve academic files from Qdrant semantic search.
        Clearly separates file metadata from actual retrieved text passages.
        """
        results: List[Dict[str, Any]] = []

        try:
            from ..schemas.file import FileSearchQuery
            search_query = FileSearchQuery(
                query=query_text,
                department=department,
                limit=limit,
                offset=0
            )

            search_response = search_service.search(db, search_query)

            for item in search_response.results:
                # Check if we can get actual text content from file
                text_snippet = None
                has_text = False

                file_record = db.query(File).filter(File.id == item.file_id).first()
                if file_record and file_record.status == FileStatus.ACTIVE:
                    try:
                        content_bytes = minio_client.download_file(file_record.bucket, file_record.object_key)
                        extracted = text_extractor.extract_text(file_record.filename, content_bytes)
                        if extracted.get("success") and extracted.get("text"):
                            full_text = extracted["text"]
                            best_passage = self._extract_best_passage(full_text, query_text)
                            if best_passage:
                                text_snippet = best_passage
                                has_text = True
                    except Exception as extract_err:
                        logger.warning(f"⚠️ Could not extract text from file {item.file_id}: {extract_err}")

                results.append({
                    "source_type": "academic_document" if has_text else "file_metadata",
                    "source_id": str(item.file_id),
                    "title": item.title or item.filename,
                    "filename": item.filename,
                    "file_type": item.file_type,
                    "department": item.department,
                    "score": round(item.score, 3),
                    "has_verified_text": has_text,
                    "text": text_snippet,
                    "text_passage": text_snippet,
                    "metadata_only": not has_text,
                    "content": text_snippet if has_text else f"File: {item.title or item.filename} ({item.file_type}) - Department: {item.department}"
                })

            return results

        except Exception as e:
            logger.error(f"❌ Failed to retrieve academic documents from Qdrant: {e}", exc_info=True)
            return []

    def retrieve_general(
        self,
        db: Session,
        query_text: str,
        department: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        General hybrid retrieval combining circulars and documents.
        """
        # Circulars
        circular_matches = db.query(Circular).filter(
            or_(
                Circular.title.ilike(f"%{query_text[:30]}%"),
                Circular.content.ilike(f"%{query_text[:30]}%")
            )
        ).order_by(desc(Circular.created_at)).limit(limit).all()

        results = []
        for circ in circular_matches:
            results.append({
                "source_type": "circular",
                "source_id": circ.id,
                "title": circ.title,
                "category": circ.type.value if hasattr(circ.type, 'value') else str(circ.type),
                "due_date": circ.due_date.strftime("%Y-%m-%d") if circ.due_date else None,
                "content": circ.content,
                "score": 0.75,
                "has_verified_text": True
            })

        # Academic files
        docs = self.retrieve_academic_documents(db, query_text, department, limit=2)
        results.extend(docs)

        return results[:limit]


institutional_retrieval_service = InstitutionalRetrievalService()
