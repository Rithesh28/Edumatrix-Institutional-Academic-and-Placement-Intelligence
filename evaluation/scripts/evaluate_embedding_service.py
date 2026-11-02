"""
Evaluate Embedding Service (SBERT all-MiniLM-L6-v2)
Tests similarity accuracy and semantic matching performance
"""

import csv
import json
import sys
import os
from typing import List, Dict, Any, Tuple

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

def load_test_cases(csv_path: str) -> List[Dict[str, Any]]:
    cases = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cases.append(row)
    return cases


def evaluate_similarities(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    from app.services.embedding_service import embedding_service

    results = []
    correct = 0
    total = len(cases)

    for case in cases:
        text1 = case.get('text1', '')
        text2 = case.get('text2', '')
        expected_sim = float(case.get('expected_similarity', 0))
        expected_match = case.get('is_semantic_match', '').lower() == 'true'

        actual_sim = embedding_service.compute_similarity(text1, text2)
        if actual_sim is None:
            actual_sim = 0.0

        # Determine match based on threshold
        actual_match = actual_sim >= 0.65  # reasonable threshold

        is_correct = (actual_match == expected_match)
        if is_correct:
            correct += 1

        results.append({
            'test_case_id': case.get('test_case_id', ''),
            'text1': text1,
            'text2': text2,
            'expected_similarity': round(expected_sim, 3),
            'actual_similarity': round(actual_sim, 3),
            'similarity_diff': round(abs(expected_sim - actual_sim), 3),
            'expected_match': expected_match,
            'actual_match': actual_match,
            'is_correct': is_correct,
            'category': case.get('category', '')
        })

    accuracy = correct / total if total > 0 else 0
    avg_similarity_diff = sum(abs(r['actual_similarity'] - r['expected_similarity']) for r in results) / total if total > 0 else 0

    return {
        'total_cases': total,
        'correct_predictions': correct,
        'accuracy': accuracy,
        'avg_similarity_diff': avg_similarity_diff,
        'results': results
    }


def generate_confusion_matrix(results: List[Dict[str, Any]]):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    cm = np.zeros((2, 2), dtype=int)
    for r in results:
        actual = r['expected_match']
        predicted = r['actual_match']
        if actual and predicted:
            cm[1, 1] += 1  # True Positive
        elif actual and not predicted:
            cm[1, 0] += 1  # False Negative
        elif not actual and predicted:
            cm[0, 1] += 1  # False Positive
        else:
            cm[0, 0] += 1  # True Negative

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
    ax.set_title('Embedding Service Similarity Confusion Matrix', fontsize=14, fontweight='bold')
    ax.set_xlabel('Predicted Match', fontsize=12)
    ax.set_ylabel('Actual Match', fontsize=12)
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(['No Match', 'Match'], fontsize=11)
    ax.set_yticklabels(['No Match', 'Match'], fontsize=11)

    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i, j]), ha='center', va='center', fontsize=14, fontweight='bold')

    plt.tight_layout()
    graphs_dir = os.path.join(os.path.dirname(__file__), '..', 'graphs')
    os.makedirs(graphs_dir, exist_ok=True)
    plt.savefig(os.path.join(graphs_dir, 'embedding_similarity_confusion.png'), dpi=300)
    plt.close()


def main():
    print("=" * 70)
    print("Evaluating Embedding Service (SBERT all-MiniLM-L6-v2)")
    print("=" * 70)

    test_csv = os.path.join(os.path.dirname(__file__), '..', 'test_cases', 'embedding_service_cases.csv')

    if not os.path.exists(test_csv):
        print(f"[XX] Test cases file not found: {test_csv}")
        return

    cases = load_test_cases(test_csv)
    print(f"Loaded {len(cases)} test cases")

    print("\nRunning similarity evaluations...")
    results = evaluate_similarities(cases)

    print(f"\nAccuracy: {results['accuracy']:.2%}")
    print(f"Correct: {results['correct_predictions']}/{results['total_cases']}")
    print(f"Average similarity difference: {results['avg_similarity_diff']:.3f}")

    generate_confusion_matrix(results['results'])

    output = {
        'model': 'SBERT all-MiniLM-L6-v2',
        'evaluation_date': '2026-11-03',
        'total_cases': results['total_cases'],
        'correct_predictions': results['correct_predictions'],
        'accuracy': round(results['accuracy'], 4),
        'avg_similarity_diff': round(results['avg_similarity_diff'], 4),
        'results': results['results']
    }

    results_dir = os.path.join(os.path.dirname(__file__), '..', 'results')
    os.makedirs(results_dir, exist_ok=True)

    metrics_file = os.path.join(results_dir, 'embedding_service_metrics_20261103.json')
    with open(metrics_file, 'w') as f:
        json.dump(output, f, indent=2)

    report_file = os.path.join(results_dir, 'embedding_service_report_20261103.md')
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("# Embedding Service Evaluation Report\n\n")
        f.write(f"**Model:** SBERT all-MiniLM-L6-v2\n")
        f.write(f"**Evaluation Date:** 2026-11-03\n\n")
        f.write("## Results\n\n")
        f.write(f"- **Total Cases:** {results['total_cases']}\n")
        f.write(f"- **Correct Predictions:** {results['correct_predictions']}\n")
        f.write(f"- **Accuracy:** {results['accuracy']:.4f} ({results['correct_predictions']}/{results['total_cases']})\n")
        f.write(f"- **Average Similarity Difference:** {results['avg_similarity_diff']:.4f}\n\n")
        f.write("## Per-Case Results\n\n")
        f.write("| Case ID | Text 1 | Text 2 | Expected Sim | Actual Sim | Correct |\n")
        f.write("|---------|--------|--------|--------------|------------|---------|\n")
        for r in results['results']:
            f.write(f"| {r['test_case_id']} | {r['text1'][:20]}... | {r['text2'][:20]}... | {r['expected_similarity']} | {r['actual_similarity']} | {'Yes' if r['is_correct'] else 'No'} |\n")

    print(f"\n[META] Metrics saved to: {metrics_file}")
    print(f"[META] Report saved to: {report_file}")
    print("[OK] Evaluation complete")


if __name__ == '__main__':
    main()
