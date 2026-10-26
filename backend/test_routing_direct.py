"""
Direct routing logic test - copies the determine_strategy logic without imports.
"""
import logging

# Minimal setup
logging.basicConfig(level=logging.INFO)

class QueryRouter:
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
        if any(w in clean_query for w in ["deadline", "last date", "submission date", "due date", "when to submit"]):
            return self.STRATEGY_DEADLINE

        # Avoid false positives on "test" - only trigger exam strategy if query
        # contains exam-specific terms, not generic "test" which appears in academic content
        if any(w in clean_query for w in ["exam", "midterm", "finals", "seating", "hall ticket", "invigilation"]):
            return self.STRATEGY_EXAM

        if any(w in clean_query for w in ["job", "placement", "internship", "package", "recruitment", "interview", "company"]):
            return self.STRATEGY_CAREER

        # Notes/academic material keywords - fallback for when intent classifier returns "other"
        # Only true institutional document queries (lecture notes, syllabus, reference materials)
        # Academic concept queries ("explain", "understand", "confused") are NOT routed here -
        # the analyzer is for institutional info ONLY (deadlines, exams, placements, events, circulars)
        if any(w in clean_query for w in ["notes", "lecture", "slide", "slides", "material", "syllabus", "study material", "reference", "pdf", "document"]):
            return self.STRATEGY_NOTES

        return self.STRATEGY_GENERAL


def test_routing():
    """Run all 8 focused routing tests."""
    print("=" * 70)
    print("ROUTING TESTS - Direct Logic Test (No Dependencies)")
    print("=" * 70)

    qr = QueryRouter()
    passed = 0
    failed = 0

    # Test 1: Deadline intent
    print("\n1. 'When is the last date to submit the DSP assignment?' -> STRATEGY_DEADLINE")
    strategy = qr.determine_strategy("check_deadline", "When is the last date to submit the DSP assignment?")
    if strategy == qr.STRATEGY_DEADLINE:
        print(f"   PASS: {strategy}")
        passed += 1
    else:
        print(f"   FAIL: Expected STRATEGY_DEADLINE, got {strategy}")
        failed += 1

    # Test 2: Exam intent
    print("\n2. 'When is the DSP midterm exam?' -> STRATEGY_EXAM")
    strategy = qr.determine_strategy("ask_exam_info", "When is the DSP midterm exam?")
    if strategy == qr.STRATEGY_EXAM:
        print(f"   PASS: {strategy}")
        passed += 1
    else:
        print(f"   FAIL: Expected STRATEGY_EXAM, got {strategy}")
        failed += 1

    # Test 3: Placement intent
    print("\n3. 'Are there any placements for CSE students?' -> STRATEGY_CAREER")
    strategy = qr.determine_strategy("career_advice", "Are there any placements for CSE students?")
    if strategy == qr.STRATEGY_CAREER:
        print(f"   PASS: {strategy}")
        passed += 1
    else:
        print(f"   FAIL: Expected STRATEGY_CAREER, got {strategy}")
        failed += 1

    # Test 4: General keyword fallback - "exam" in query triggers exam strategy
    print("\n4. 'Show me the circular about exam fees' -> STRATEGY_EXAM (contains 'exam' keyword)")
    strategy = qr.determine_strategy("other", "Show me the circular about exam fees")
    if strategy == qr.STRATEGY_EXAM:
        print(f"   PASS: {strategy}")
        passed += 1
    else:
        print(f"   FAIL: Expected STRATEGY_EXAM, got {strategy}")
        failed += 1

    # Test 5: Greet intent
    print("\n5. 'Hello' -> STRATEGY_GREET")
    strategy = qr.determine_strategy("greet", "Hello")
    if strategy == qr.STRATEGY_GREET:
        print(f"   PASS: {strategy}")
        passed += 1
    else:
        print(f"   FAIL: Expected STRATEGY_GREET, got {strategy}")
        failed += 1

    # Test 6: DSP test cases -> NOT exam (general)
    print("\n6. 'DSP test cases' -> STRATEGY_GENERAL (NOT exam - 'test' removed from exam keywords)")
    strategy = qr.determine_strategy("other", "DSP test cases")
    if strategy != qr.STRATEGY_EXAM and strategy == qr.STRATEGY_GENERAL:
        print(f"   PASS: {strategy}")
        passed += 1
    else:
        print(f"   FAIL: Expected STRATEGY_GENERAL (not STRATEGY_EXAM), got {strategy}")
        failed += 1

    # Test 7: Explain DSP concepts -> NOT notes (general)
    print("\n7. 'Explain DSP concepts' -> STRATEGY_GENERAL (NOT notes - 'explain' removed from notes keywords)")
    strategy = qr.determine_strategy("other", "Explain DSP concepts")
    if strategy != qr.STRATEGY_NOTES and strategy == qr.STRATEGY_GENERAL:
        print(f"   PASS: {strategy}")
        passed += 1
    else:
        print(f"   FAIL: Expected STRATEGY_GENERAL (not STRATEGY_NOTES), got {strategy}")
        failed += 1

    # Test 8: Confused about ML -> NOT notes (general)
    print("\n8. \"I'm confused about ML topics\" -> STRATEGY_GENERAL (NOT notes - 'confused' removed from notes keywords)")
    strategy = qr.determine_strategy("other", "I'm confused about ML topics")
    if strategy != qr.STRATEGY_NOTES and strategy == qr.STRATEGY_GENERAL:
        print(f"   PASS: {strategy}")
        passed += 1
    else:
        print(f"   FAIL: Expected STRATEGY_GENERAL (not STRATEGY_NOTES), got {strategy}")
        failed += 1

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    import sys
    success = test_routing()
    sys.exit(0 if success else 1)