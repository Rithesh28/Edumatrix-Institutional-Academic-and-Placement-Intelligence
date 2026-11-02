"""
Evaluate Skill Matching Service (Job Matching Engine)
Tests the 3-level matching hierarchy: Exact -> Synonym -> Semantic
"""

import csv
import json
import sys
import os
from typing import List, Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))


def load_test_cases(csv_path: str) -> List[Dict[str, Any]]:
    cases = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cases.append(row)
    return cases


def evaluate_skill_matches(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    from app.services.skill_normalizer import skill_normalizer
    from app.services.embedding_service import embedding_service

    SEMANTIC_THRESHOLD = 0.78

    results = []
    correct = 0
    total = len(cases)

    for case in cases:
        student_skill = case.get('student_skill', '').strip()
        job_skill = case.get('job_skill', '').strip()
        expected_match = case.get('expected_match', '').lower()
        expected_method = case.get('match_method', '').lower()

        # Level 1: Exact normalized match
        norm_student = skill_normalizer.normalize(student_skill)
        norm_job = skill_normalizer.normalize(job_skill)

        if norm_student == norm_job:
            actual_method = 'exact'
            is_match = True
        else:
            # Level 2: Synonym match
            canonical_student = skill_normalizer.get_canonical(student_skill)
            canonical_job = skill_normalizer.get_canonical(job_skill)

            if canonical_student == canonical_job:
                actual_method = 'synonym'
                is_match = True
            else:
                # Level 3: Semantic match
                sim = embedding_service.compute_similarity(student_skill, job_skill)
                if sim is not None and sim >= SEMANTIC_THRESHOLD:
                    actual_method = 'semantic'
                    is_match = True
                    similarity = round(sim, 3)
                else:
                    actual_method = 'none'
                    is_match = False
                    similarity = round(sim, 3) if sim is not None else 0.0

        match_correct = (is_match == (expected_match != 'false'))
        method_correct = (actual_method == expected_method) or (expected_method == 'none' and not is_match)

        if match_correct and method_correct:
            correct += 1

        results.append({
            'test_case_id': case.get('test_case_id', ''),
            'student_skill': student_skill,
            'job_skill': job_skill,
            'expected_match': expected_match,
            'actual_match': is_match,
            'expected_method': expected_method,
            'actual_method': actual_method,
            'similarity_score': similarity if 'similarity' in dir() else None,
            'match_correct': match_correct,
            'method_correct': method_correct,
            'category': case.get('category', '')
        })

    accuracy = correct / total if total > 0 else 0

    return {
        'total_cases': total,
        'correct_predictions': correct,
        'accuracy': accuracy,
        'exact_matches': sum(1 for r in results if r['actual_method'] == 'exact'),
        'synonym_matches': sum(1 for r in results if r['actual_method'] == 'synonym'),
        'semantic_matches': sum(1 for r in results if r['actual_method'] == 'semantic'),
        'no_matches': sum(1 for r in results if r['actual_method'] == 'none'),
        'results': results
    }


def main():
    print("=" * 70)
    print("Evaluating Skill Matching Service (3-Level Hierarchy)")
    print("=" * 70)

    test_csv = os.path.join(os.path.dirname(__file__), '..', 'test_cases', 'skill_matching_cases.csv')

    if not os.path.exists(test_csv):
        print(f"[XX] Test cases file not found: {test_csv}")
        return

    cases = load_test_cases(test_csv)
    print(f"Loaded {len(cases)} test cases")

    results = evaluate_skill_matches(cases)

    print(f"\nMatching Accuracy: {results['accuracy']:.2%}")
    print(f"Correct: {results['correct_predictions']}/{results['total_cases']}")
    print(f"\nMatch Type Distribution:")
    print(f"  - Exact: {results['exact_matches']}")
    print(f"  - Synonym: {results['synonym_matches']}")
    print(f"  - Semantic: {results['semantic_matches']}")
    print(f"  - No Match: {results['no_matches']}")

    output = {
        'model': 'JobMatchingService (3-Level Hierarchy)',
        'evaluation_date': '2026-11-03',
        'total_cases': results['total_cases'],
        'correct_predictions': results['correct_predictions'],
        'accuracy': round(results['accuracy'], 4),
        'match_distribution': {
            'exact': results['exact_matches'],
            'synonym': results['synonym_matches'],
            'semantic': results['semantic_matches'],
            'none': results['no_matches']
        },
        'results': results['results']
    }

    results_dir = os.path.join(os.path.dirname(__file__), '..', 'results')
    os.makedirs(results_dir, exist_ok=True)

    metrics_file = os.path.join(results_dir, 'skill_matching_metrics_20261103.json')
    with open(metrics_file, 'w') as f:
        json.dump(output, f, indent=2)

    report_file = os.path.join(results_dir, 'skill_matching_report_20261103.md')
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("# Skill Matching Service Evaluation Report\n\n")
        f.write(f"**Model:** 3-Level Deterministic Skill Matching\n")
        f.write(f"**Threshold:** 0.78 (semantic similarity)\n")
        f.write(f"**Evaluation Date:** 2026-11-03\n\n")
        f.write("## Results\n\n")
        f.write(f"- **Total Cases:** {results['total_cases']}\n")
        f.write(f"- **Correct Predictions:** {results['correct_predictions']}\n")
        f.write(f"- **Accuracy:** {results['accuracy']:.4f}\n\n")
        f.write("### Match Type Distribution\n\n")
        f.write(f"- Exact: {results['exact_matches']}\n")
        f.write(f"- Synonym: {results['synonym_matches']}\n")
        f.write(f"- Semantic: {results['semantic_matches']}\n")
        f.write(f"- No Match: {results['no_matches']}\n\n")
        f.write("## Per-Case Results\n\n")
        f.write("| Case ID | Student Skill | Job Skill | Expected | Actual | Method |\n")
        f.write("|---------|--------------|-----------|----------|--------|--------|\n")
        for r in results['results']:
            f.write(f"| {r['test_case_id']} | {r['student_skill']} | {r['job_skill']} | {r['expected_match']} | {r['actual_match']} | {r['actual_method']} |\n")

    print(f"\n[META] Metrics saved to: {metrics_file}")
    print(f"[META] Report saved to: {report_file}")
    print("[OK] Evaluation complete")


if __name__ == '__main__':
    main()
