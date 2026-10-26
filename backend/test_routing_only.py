"""
Standalone routing tests for query_router - no ML dependencies required.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import only query_router - no ML dependencies
from app.services.query_router import query_router

def test_routing():
    """Run all 8 focused routing tests."""
    print("=" * 60)
    print("ROUTING TESTS - Query Router Only (No ML Dependencies)")
    print("=" * 60)

    passed = 0
    failed = 0

    # Test 1: Deadline intent
    print("\n1. 'When is the last date to submit the DSP assignment?' -> STRATEGY_DEADLINE")
    strategy = query_router.determine_strategy("check_deadline", "When is the last date to submit the DSP assignment?")
    if strategy == query_router.STRATEGY_DEADLINE:
        print(f"   PASS: {strategy}")
        passed += 1
    else:
        print(f"   FAIL: Expected STRATEGY_DEADLINE, got {strategy}")
        failed += 1

    # Test 2: Exam intent
    print("\n2. 'When is the DSP midterm exam?' -> STRATEGY_EXAM")
    strategy = query_router.determine_strategy("ask_exam_info", "When is the DSP midterm exam?")
    if strategy == query_router.STRATEGY_EXAM:
        print(f"   PASS: {strategy}")
        passed += 1
    else:
        print(f"   FAIL: Expected STRATEGY_EXAM, got {strategy}")
        failed += 1

    # Test 3: Placement intent
    print("\n3. 'Are there any placements for CSE students?' -> STRATEGY_CAREER")
    strategy = query_router.determine_strategy("career_advice", "Are there any placements for CSE students?")
    if strategy == query_router.STRATEGY_CAREER:
        print(f"   PASS: {strategy}")
        passed += 1
    else:
        print(f"   FAIL: Expected STRATEGY_CAREER, got {strategy}")
        failed += 1

    # Test 4: General keyword fallback
    print("\n4. 'Show me the circular about exam fees' -> STRATEGY_GENERAL")
    strategy = query_router.determine_strategy("other", "Show me the circular about exam fees")
    if strategy == query_router.STRATEGY_GENERAL:
        print(f"   PASS: {strategy}")
        passed += 1
    else:
        print(f"   FAIL: Expected STRATEGY_GENERAL, got {strategy}")
        failed += 1

    # Test 5: Greet intent
    print("\n5. 'Hello' -> STRATEGY_GREET")
    strategy = query_router.determine_strategy("greet", "Hello")
    if strategy == query_router.STRATEGY_GREET:
        print(f"   PASS: {strategy}")
        passed += 1
    else:
        print(f"   FAIL: Expected STRATEGY_GREET, got {strategy}")
        failed += 1

    # Test 6: DSP test cases -> NOT exam (general)
    print("\n6. 'DSP test cases' -> STRATEGY_GENERAL (NOT exam - 'test' removed from exam keywords)")
    strategy = query_router.determine_strategy("other", "DSP test cases")
    if strategy != query_router.STRATEGY_EXAM and strategy == query_router.STRATEGY_GENERAL:
        print(f"   PASS: {strategy}")
        passed += 1
    else:
        print(f"   FAIL: Expected STRATEGY_GENERAL (not STRATEGY_EXAM), got {strategy}")
        failed += 1

    # Test 7: Explain DSP concepts -> NOT notes (general)
    print("\n7. 'Explain DSP concepts' -> STRATEGY_GENERAL (NOT notes - 'explain' removed from notes keywords)")
    strategy = query_router.determine_strategy("other", "Explain DSP concepts")
    if strategy != query_router.STRATEGY_NOTES and strategy == query_router.STRATEGY_GENERAL:
        print(f"   PASS: {strategy}")
        passed += 1
    else:
        print(f"   FAIL: Expected STRATEGY_GENERAL (not STRATEGY_NOTES), got {strategy}")
        failed += 1

    # Test 8: Confused about ML -> NOT notes (general)
    print("\n8. \"I'm confused about ML topics\" -> STRATEGY_GENERAL (NOT notes - 'confused' removed from notes keywords)")
    strategy = query_router.determine_strategy("other", "I'm confused about ML topics")
    if strategy != query_router.STRATEGY_NOTES and strategy == query_router.STRATEGY_GENERAL:
        print(f"   PASS: {strategy}")
        passed += 1
    else:
        print(f"   FAIL: Expected STRATEGY_GENERAL (not STRATEGY_NOTES), got {strategy}")
        failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0

if __name__ == "__main__":
    success = test_routing()
    sys.exit(0 if success else 1)