"""
Query Router Service

Inspects classified intent and query text to determine the optimal
institutional retrieval strategy without blindly querying every data source.
"""

import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from .institutional_retrieval_service import institutional_retrieval_service

logger = logging.getLogger(__name__)


class QueryRouter:
    """
    Routes queries to appropriate retrieval strategies based on intent and content.
    """

    STRATEGY_DEADLINE = "structured_deadline"
    STRATEGY_EXAM = "exam_information"
    STRATEGY_NOTES = "semantic_notes"
    STRATEGY_CAREER = "career_placement"
    STRATEGY_GREET = "conversational_greet"
    STRATEGY_FEEDBACK = "feedback"
    STRATEGY_GENERAL = "general_institutional"

    def determine_strategy(self, intent: str, query_text: str) -> str:
        """
        Determine retrieval strategy based on intent and query tokens.
        Intent classification takes priority over keyword heuristics to avoid
        misrouting (e.g., "test" in "DSP test cases" should not trigger exam strategy).
        """
        clean_query = query_text.lower().strip()

        # Direct conversational intents - highest priority
        if intent == "greet":
            return self.STRATEGY_GREET
        if intent == "feedback":
            return self.STRATEGY_FEEDBACK

        # Intent-based routing takes priority over keyword heuristics
        if intent == "check_deadline":
            return self.STRATEGY_DEADLINE
        elif intent == "ask_exam_info":
            return self.STRATEGY_EXAM
        elif intent == "career_advice":
            return self.STRATEGY_CAREER
        elif intent in ["request_notes", "ask_doubt"]:
            return self.STRATEGY_NOTES

        # Keyword checks for high-priority routing (fallback when intent is "other")

        # Placement/career keywords first - before deadline to handle "last date to apply for [company]"
        if any(w in clean_query for w in ["job", "placement", "internship", "package", "recruitment", "interview", "company"]):
            return self.STRATEGY_CAREER

        # Deadline keywords
        if any(w in clean_query for w in ["deadline", "last date", "submission date", "due date", "when to submit"]):
            return self.STRATEGY_DEADLINE

        # Avoid false positives on "test" - only trigger exam strategy if query
        # contains exam-specific terms, not generic "test" which appears in academic content
        if any(w in clean_query for w in ["exam", "midterm", "finals", "seating", "hall ticket", "invigilation"]):
            return self.STRATEGY_EXAM

        # Notes/academic material keywords - fallback for when intent classifier returns "other"
        # Only true institutional document queries (lecture notes, syllabus, reference materials)
        # Academic concept queries ("explain", "understand", "confused") are NOT routed here -
        # the analyzer is for institutional info ONLY (deadlines, exams, placements, events, circulars)
        # NOTE: "explain", "understand", "confused", "doubt" have been REMOVED per corrected requirements -
        # the analyzer is NOT a study tutor, only handles institutional info
        if any(w in clean_query for w in ["notes", "lecture", "slide", "slides", "material", "syllabus", "study material", "reference", "pdf", "document"]):
            return self.STRATEGY_NOTES

        return self.STRATEGY_GENERAL

    def execute_routing(
        self,
        db: Session,
        intent: str,
        query_text: str,
        department: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Determines strategy, runs targeted retrieval, and returns sources.
        """
        strategy = self.determine_strategy(intent, query_text)
        logger.info(f"🧭 Routed query '{query_text[:40]}...' [Intent: {intent}] -> Strategy: {strategy}")

        sources: List[Dict[str, Any]] = []
        requires_retrieval = True

        if strategy == self.STRATEGY_GREET:
            requires_retrieval = False
            sources = []

        elif strategy == self.STRATEGY_FEEDBACK:
            requires_retrieval = False
            sources = []

        elif strategy == self.STRATEGY_DEADLINE:
            # PostgreSQL circulars & deadlines first, then academic files if needed
            sources = institutional_retrieval_service.retrieve_deadlines(
                db, query_text, department=department, limit=5
            )

        elif strategy == self.STRATEGY_EXAM:
            sources = institutional_retrieval_service.retrieve_exam_information(
                db, query_text, department=department, limit=5
            )

        elif strategy == self.STRATEGY_CAREER:
            sources = institutional_retrieval_service.retrieve_placement_information(
                db, query_text, limit=5
            )

        elif strategy == self.STRATEGY_NOTES:
            # Qdrant document retrieval + circulars
            sources = institutional_retrieval_service.retrieve_academic_documents(
                db, query_text, department=department, limit=3
            )

        else:  # GENERAL
            sources = institutional_retrieval_service.retrieve_general(
                db, query_text, department=department, limit=4
            )

        ambiguity_info = {"is_ambiguous": False, "category": "general", "candidates": []}
        if requires_retrieval and sources:
            ambiguity_info = institutional_retrieval_service.detect_ambiguity(query_text, sources)

        return {
            "strategy": strategy,
            "requires_retrieval": requires_retrieval,
            "sources": sources,
            "source_count": len(sources),
            "is_ambiguous": ambiguity_info.get("is_ambiguous", False),
            "ambiguity_category": ambiguity_info.get("category", "general"),
            "ambiguous_candidates": ambiguity_info.get("candidates", [])
        }


query_router = QueryRouter()
