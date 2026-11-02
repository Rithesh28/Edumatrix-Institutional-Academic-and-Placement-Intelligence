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
    STRATEGY_GENERAL_KNOWLEDGE = "general_knowledge"

    def determine_strategy(self, intent: str, query_text: str, intent_confidence: float = 1.0) -> str:
        """
        Determine retrieval strategy based on intent and query tokens.
        Intent classification takes priority over keyword heuristics to avoid
        misrouting (e.g., "test" in "DSP test cases" should not trigger exam strategy).

        If intent_confidence is below 0.5, intent is treated as "other" to allow
        keyword-based routing instead of trusting low-confidence classifier output.
        """
        # Low confidence intent fallback: treat as "other" for keyword-based routing
        INTENT_CONFIDENCE_THRESHOLD = 0.5
        if intent_confidence < INTENT_CONFIDENCE_THRESHOLD:
            intent = "other"

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
            # Keyword-based override: "circular/notice", "explain/confused", "test" queries
            # should route to GENERAL even if misclassified as ask_exam_info
            if any(w in clean_query for w in ["circular", "notice", "notification", "document", "pdf", "file"]):
                return self.STRATEGY_GENERAL
            # "explain", "confused", "test" are tutoring/academic content patterns, not exam queries
            # "test" alone (without exam/midterm/finals) appears in academic content like "DSP test cases"
            if any(w in clean_query for w in ["explain", "confused", "test cases", "test case"]):
                return self.STRATEGY_GENERAL
            return self.STRATEGY_EXAM
        elif intent == "career_advice":
            # Keyword-based override: "confused" and tutoring patterns
            if any(w in clean_query for w in ["explain", "understand", "confused", "doubt", "clarify", "how to", "define", "meaning of", "concept"]):
                institutional_keywords = ["deadline", "last date", "submission date", "due date", "when to submit",
                                         "job", "placement", "internship", "package", "recruitment", "interview",
                                         "company", "apply", "application", "exam", "midterm", "finals",
                                         "seating", "hall ticket", "invigilation", "event", "circular", "notice"]
                if not any(kw in clean_query for kw in institutional_keywords):
                    return self.STRATEGY_GENERAL
            return self.STRATEGY_CAREER
        elif intent in ["request_notes", "ask_doubt"]:
            # Keyword-based override: tutoring patterns should route to GENERAL
            tutoring_patterns = [
                "explain", "understand", "confused", "doubt", "clarify",
                "how to", "define", "meaning of", "concept"
            ]
            if any(w in clean_query for w in tutoring_patterns):
                institutional_keywords = ["deadline", "last date", "submission date", "due date", "when to submit",
                                         "job", "placement", "internship", "package", "recruitment", "interview",
                                         "company", "apply", "application", "exam", "midterm", "finals",
                                         "seating", "hall ticket", "invigilation", "event", "circular", "notice"]
                if not any(kw in clean_query for kw in institutional_keywords):
                    return self.STRATEGY_GENERAL
            return self.STRATEGY_NOTES

        # Keyword checks for high-priority routing (fallback when intent is "other")

        # 1. GENERAL KNOWLEDGE DETECTION - explicit check before other routing
        # Questions about world facts, general knowledge, or non-institutional topics
        # These should NOT trigger any institutional retrieval
        general_knowledge_patterns = [
            "who is the president", "who is the prime minister", "who is the",
            "what is the capital", "capital of", "population of",
            "when was", "where is", "how many", "what does", "meaning of life",
            "who won", "which country", "tell me about"
        ]
        # Check if query is asking for general knowledge (not institutional info)
        if any(pattern in clean_query for pattern in general_knowledge_patterns):
            # Ensure it's not also an institutional query
            institutional_keywords = ["deadline", "last date", "submission date", "due date", "when to submit",
                                         "job", "placement", "internship", "package", "recruitment", "interview",
                                         "company", "apply", "application", "exam", "midterm", "finals",
                                         "seating", "hall ticket", "invigilation", "event", "circular", "notice",
                                         "assignment", "circular", "timetable", "schedule", "cie", "exam"]
            if not any(kw in clean_query for kw in institutional_keywords):
                return self.STRATEGY_GENERAL_KNOWLEDGE

        # Academic tutoring queries - explicitly route to GENERAL before other keyword checks
        # The analyzer is for institutional info ONLY (deadlines, exams, placements, events, circulars)
        # NOT a study tutor. These patterns indicate academic help requests.
        # Use more specific patterns to avoid catching generic institutional queries like "what is the deadline"
        tutoring_patterns = [
            "explain", "understand", "confused", "doubt", "clarify",
            "how to", "define", "meaning of", "concept"
        ]
        # "what is" only triggers tutoring if followed by a concept-like word
        # Not when followed by institutional keywords like "deadline", "date", "last", "apply", etc.
        if any(w in clean_query for w in tutoring_patterns):
            # Additional check: don't flag as tutoring if query contains institutional keywords
            institutional_keywords = ["deadline", "last date", "submission date", "due date", "when to submit",
                                     "job", "placement", "internship", "package", "recruitment", "interview",
                                     "company", "apply", "application", "exam", "midterm", "finals",
                                     "seating", "hall ticket", "invigilation", "event", "circular", "notice"]
            if not any(kw in clean_query for kw in institutional_keywords):
                return self.STRATEGY_GENERAL

        # Document/circular request keywords - these should route to GENERAL (not notes/exam)
        # The analyzer provides institutional info; document requests are handled elsewhere
        if any(w in clean_query for w in ["circular", "notice", "notification", "document", "pdf", "file"]):
            return self.STRATEGY_GENERAL

        # "what is" specific check - only tutoring if asking about a concept, not institutional info
        if "what is" in clean_query or "what are" in clean_query:
            concept_indicators = ["concept", "topic", "subject", "chapter", "module", "theory", "principle"]
            institutional_indicators = ["deadline", "date", "last", "apply", "exam", "placement", "job",
                                        "event", "circular", "notice", "schedule", "drive", "company"]
            if any(ci in clean_query for ci in concept_indicators) and not any(ii in clean_query for ii in institutional_indicators):
                return self.STRATEGY_GENERAL

        # Placement/career keywords first - before deadline to handle "last date to apply for [company]"
        # "apply" is a strong signal for placement applications
        if any(w in clean_query for w in ["job", "placement", "internship", "package", "recruitment", "interview", "company", "apply", "application"]):
            return self.STRATEGY_CAREER

        # CIE/Exam schedule keywords - must come before general deadline to catch specific CIE queries
        # These are exam schedule queries that should route to exam_information, not deadline
        if any(w in clean_query for w in ["cie", "continuous internal evaluation", "internal exam", "internal assessment"]):
            return self.STRATEGY_EXAM

        # Deadline keywords
        if any(w in clean_query for w in ["deadline", "last date", "submission date", "due date", "when to submit", "when does", "when is the"]):
            # If the query mentions specific exam/CIE terms, route to exam instead
            if any(w in clean_query for w in ["cie", "exam", "test", "midterm", "finals", "continuous internal", "internal evaluation"]):
                return self.STRATEGY_EXAM
            return self.STRATEGY_DEADLINE

        # Avoid false positives on "test" - only trigger exam strategy if query
        # contains exam-specific terms, not generic "test" which appears in academic content
        if any(w in clean_query for w in ["exam", "midterm", "finals", "seating", "hall ticket", "invigilation"]):
            return self.STRATEGY_EXAM

        # Notes/academic material keywords - fallback for when intent classifier returns "other"
        # Only true institutional document queries (lecture notes, syllabus, reference materials)
        # "lecture", "slide", "slides" moved after academic tutoring check so
        # "explain from lecture slides" routes to general, not notes
        if any(w in clean_query for w in ["notes", "lecture", "slide", "slides", "material", "syllabus", "study material", "reference", "pdf", "document"]):
            return self.STRATEGY_NOTES

        return self.STRATEGY_GENERAL

    def execute_routing(
        self,
        db: Session,
        intent: str,
        query_text: str,
        department: Optional[str] = None,
        intent_confidence: float = 1.0
    ) -> Dict[str, Any]:
        """
        Determines strategy, runs targeted retrieval, and returns sources.
        """
        strategy = self.determine_strategy(intent, query_text, intent_confidence=intent_confidence)
        logger.info(f"🧭 Routed query '{query_text[:40]}...' [Intent: {intent}] -> Strategy: {strategy}")

        sources: List[Dict[str, Any]] = []
        requires_retrieval = True

        if strategy == self.STRATEGY_GREET:
            requires_retrieval = False
            sources = []

        elif strategy == self.STRATEGY_FEEDBACK:
            requires_retrieval = False
            sources = []

        elif strategy == self.STRATEGY_GENERAL_KNOWLEDGE:
            # General knowledge queries: NO institutional retrieval
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
