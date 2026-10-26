"""
Direct routing logic test for critical queries from the verification list.
"""
import logging

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
        clean_query = query_text.lower().strip()

        if intent == "greet":
            return self.STRATEGY_GREET
        if intent == "feedback":
            return self.STRATEGY_FEEDBACK

        if intent == "check_deadline":
            return self.STRATEGY_DEADLINE
        elif intent == "ask_exam_info":
            return self.STRATEGY_EXAM
        elif intent == "career_advice":
            return self.STRATEGY_CAREER
        elif intent in ["request_notes", "ask_doubt"]:
            return self.STRATEGY_NOTES

        if any(w in clean_query for w in ["deadline", "last date", "submission date", "due date", "when to submit"]):
            return self.STRATEGY_DEADLINE

        if any(w in clean_query for w in ["exam", "midterm", "finals", "seating", "hall ticket", "invigilation"]):
            return self.STRATEGY_EXAM

        if any(w in clean_query for w in ["job", "placement", "internship", "package", "recruitment", "interview", "company"]):
            return self.STRATEGY_CAREER

        if any(w in clean_query for w in ["notes", "lecture", "slide", "slides", "material", "syllabus", "study material", "reference", "pdf", "document"]):
            return self.STRATEGY_NOTES

        return self.STRATEGY_GENERAL


def test_critical_routing():
    """Test critical routing behaviors from verification list."""
    print("=" * 70)
    print("CRITICAL ROUTING VERIFICATION")
    print("=" * 70)

    qr = QueryRouter()
    passed = 0
    failed = 0

    test_cases = [
        # (query, expected_strategy, description)
        ("When is the assignment submission deadline?", "structured_deadline", "Deadline keyword"),
        ("When is the next internal examination?", "exam_information", "Exam keyword 'examination'"),
        ("When is the placement drive for TCS?", "career_placement", "Placement drive"),
        ("What is the last date to apply for TCS?", "career_placement", "Placement apply deadline"),
        ("What are the upcoming college events?", "general_institutional", "Events - general"),
        ("Show me DSP test cases.", "general_institutional", "DSP test cases - NOT exam"),
        ("Explain the DSP concept from my lecture slides.", "general_institutional", "Explain from slides - NOT notes"),
    ]

    for query, expected, desc in test_cases:
        print(f"\nQuery: '{query}'")
        print(f"  Expected: {expected} ({desc})")
        strategy = qr.determine_strategy("other", query)
        if strategy == expected:
            print(f"  PASS: {strategy}")
            passed += 1
        else:
            print(f"  FAIL: Got {strategy}")
            failed += 1

    # Also verify explicit intent-based routing works
    print("\n" + "=" * 70)
    print("INTENT-BASED ROUTING (should override keywords)")
    print("=" * 70)

    intent_tests = [
        ("check_deadline", "When is the test submission?", "structured_deadline", "Intent overrides 'test'"),
        ("ask_exam_info", "When is the test?", "exam_information", "Intent overrides 'test'"),
    ]

    for intent, query, expected, desc in intent_tests:
        print(f"\nIntent: {intent}, Query: '{query}'")
        print(f"  Expected: {expected} ({desc})")
        strategy = qr.determine_strategy(intent, query)
        if strategy == expected:
            print(f"  PASS: {strategy}")
            passed += 1
        else:
            print(f"  FAIL: Got {strategy}")
            failed += 1

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    import sys
    success = test_critical_routing()
    sys.exit(0 if success else 1)