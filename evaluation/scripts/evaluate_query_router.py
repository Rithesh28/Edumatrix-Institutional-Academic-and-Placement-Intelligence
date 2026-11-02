"""
Evaluate Query Router (Strategy Selection)
Tests routing accuracy to appropriate strategies
"""

import csv
import json
import sys
import os
from typing import List, Dict, Any


def load_test_cases(csv_path: str) -> List[Dict[str, Any]]:
    cases = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cases.append(row)
    return cases


def evaluate_routing(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluate routing based on intent + keyword matching logic.
    This mirrors the query_router.py logic.
    """
    results = []
    correct = 0

    for case in cases:
        query = case.get('query', '')
        intent = case.get('intent', 'other')
        expected_strategy = case.get('expected_strategy', 'general_knowledge')

        # Replicate routing logic from query_router.py
        strategy = determine_strategy(query, intent)

        is_correct = (strategy == expected_strategy)
        if is_correct:
            correct += 1

        results.append({
            'test_case_id': case.get('test_case_id', ''),
            'query': query,
            'intent': intent,
            'expected_strategy': expected_strategy,
            'actual_strategy': strategy,
            'is_correct': is_correct,
            'notes': case.get('notes', '')
        })

    accuracy = correct / len(cases) if cases else 0

    return {
        'total_cases': len(cases),
        'correct_predictions': correct,
        'accuracy': accuracy,
        'results': results
    }


def determine_strategy(query: str, intent: str) -> str:
    """Replicate query routing logic."""
    query_lower = query.lower()

    # Check conversation retrieval keywords
    conv_keywords = ['who said', 'my friend', 'what did', 'show my', 'friend said', 'message about']
    if any(kw in query_lower for kw in conv_keywords):
        return 'conversation_retrieval'

    # Check study buddy keywords
    study_keywords = ['study', 'notes', 'syllabus', 'lecture', 'course', 'subject', 'learn', 'explain']
    if any(kw in query_lower for kw in study_keywords):
        return 'study_buddy_rag'

    # Intent-based routing
    if intent == 'check_deadline':
        return 'institutional_rag'
    if intent == 'ask_exam_info':
        return 'institutional_rag'
    if intent == 'ask_doubt':
        return 'study_buddy_rag'
    if intent == 'request_notes':
        return 'study_buddy_rag'
    if intent in ('greet', 'feedback'):
        return 'general_knowledge'

    # Keyword overrides
    institutional_keywords = ['deadline', 'due date', 'exam', 'circular', 'placement', 'drive', 'company']
    if any(kw in query_lower for kw in institutional_keywords):
        return 'institutional_rag'

    return 'general_knowledge'


def main():
    print("=" * 70)
    print("Evaluating Query Router (Strategy Selection)")
    print("=" * 70)

    test_csv = os.path.join(os.path.dirname(__file__), '..', 'test_cases', 'query_router_cases.csv')

    if not os.path.exists(test_csv):
        print(f"[XX] Test cases file not found: {test_csv}")
        return

    cases = load_test_cases(test_csv)
    print(f"Loaded {len(cases)} test cases")

    results = evaluate_routing(cases)

    print(f"\nRouting Accuracy: {results['accuracy']:.2%}")
    print(f"Correct: {results['correct_predictions']}/{results['total_cases']}")

    output = {
        'model': 'QueryRouter (Rule-based)',
        'evaluation_date': '2026-11-03',
        'total_cases': results['total_cases'],
        'correct_predictions': results['correct_predictions'],
        'accuracy': round(results['accuracy'], 4),
        'results': results['results']
    }

    results_dir = os.path.join(os.path.dirname(__file__), '..', 'results')
    os.makedirs(results_dir, exist_ok=True)

    metrics_file = os.path.join(results_dir, 'query_router_metrics_20261103.json')
    with open(metrics_file, 'w') as f:
        json.dump(output, f, indent=2)

    report_file = os.path.join(results_dir, 'query_router_report_20261103.md')
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("# Query Router Evaluation Report\n\n")
        f.write(f"**Model:** Rule-based Query Router\n")
        f.write(f"**Evaluation Date:** 2026-11-03\n\n")
        f.write("## Results\n\n")
        f.write(f"- **Total Cases:** {results['total_cases']}\n")
        f.write(f"- **Correct Predictions:** {results['correct_predictions']}\n")
        f.write(f"- **Accuracy:** {results['accuracy']:.4f}\n\n")
        f.write("## Per-Case Results\n\n")
        f.write("| Case ID | Query | Expected | Actual | Correct |\n")
        f.write("|---------|-------|----------|--------|---------|\n")
        for r in results['results']:
            f.write(f"| {r['test_case_id']} | {r['query'][:30]}... | {r['expected_strategy']} | {r['actual_strategy']} | {'Yes' if r['is_correct'] else 'No'} |\n")

    print(f"\n[META] Metrics saved to: {metrics_file}")
    print(f"[META] Report saved to: {report_file}")
    print("[OK] Evaluation complete")


if __name__ == '__main__':
    main()
