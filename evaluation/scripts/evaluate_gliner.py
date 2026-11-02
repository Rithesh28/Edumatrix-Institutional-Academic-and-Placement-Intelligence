#!/usr/bin/env python3
"""
GLiNER Entity Extraction Evaluation Script
Evaluates the GLiNER zero-shot NER model on test cases.
"""

import sys
import os
import json
import csv
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from app.services.gliner_service import gliner_service


def load_test_cases(csv_path):
    """Load test cases from CSV."""
    test_cases = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            test_cases.append(row)
    return test_cases


def exact_match(entities_found, entities_expected):
    """Check exact match of entity sets."""
    if not entities_found and not entities_expected:
        return True
    found_set = set((e['text'].lower(), e['label']) for e in entities_found)
    expected_set = set((e['text'].lower(), e['label']) for e in entities_expected)
    return found_set == expected_set


def partial_match(entities_found, entities_expected):
    """Check partial match - at least one entity matches."""
    if not entities_expected:
        return len(entities_found) == 0
    found_set = set((e['text'].lower(), e['label']) for e in entities_found)
    expected_set = set((e['text'].lower(), e['label']) for e in entities_expected)
    return len(found_set & expected_set) > 0


def run_evaluation(test_cases):
    """Run GLiNER on test cases."""
    results = []

    entity_labels = ['technical skill', 'job title', 'company', 'qualification',
                     'percentage', 'CGPA', 'location', 'experience years',
                     'date range', 'selection round']

    for tc in test_cases:
        text = tc['input_text']
        expected_entities = json.loads(tc.get('expected_entities', '[]'))

        # Run GLiNER
        entities = gliner_service.predict_entities(text, entity_labels, threshold=0.5)

        # Compute metrics
        tp = len(set((e['text'].lower(), e['label']) for e in entities) &
                 set((e['text'].lower(), e['label']) for e in expected_entities))
        fp = len(set((e['text'].lower(), e['label']) for e in entities) -
                 set((e['text'].lower(), e['label']) for e in expected_entities))
        fn = len(set((e['text'].lower(), e['label']) for e in expected_entities) -
                 set((e['text'].lower(), e['label']) for e in entities))

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        results.append({
            'test_case_id': tc['test_case_id'],
            'input': text,
            'expected': expected_entities,
            'predicted': entities,
            'precision': round(precision, 3),
            'recall': round(recall, 3),
            'f1': round(f1, 3),
            'tp': tp,
            'fp': fp,
            'fn': fn,
            'exact_match': exact_match(entities, expected_entities),
            'partial_match': partial_match(entities, expected_entities),
            'category': tc['category'],
        })

        status = '[OK]' if exact_match(entities, expected_entities) else ('[PARTIAL]' if partial_match(entities, expected_entities) else '[XX]')
        print(f"{tc['test_case_id']}: {len(entities)} entities found vs {len(expected_entities)} expected {status}")

    return results


def compute_metrics(results):
    """Compute aggregate metrics."""
    total_tp = sum(r['tp'] for r in results)
    total_fp = sum(r['fp'] for r in results)
    total_fn = sum(r['fn'] for r in results)

    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    exact_matches = sum(1 for r in results if r['exact_match'])
    partial_matches = sum(1 for r in results if r['partial_match'])

    return {
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'total_tp': total_tp,
        'total_fp': total_fp,
        'total_fn': total_fn,
        'exact_match_rate': exact_matches / len(results) if results else 0,
        'partial_match_rate': partial_matches / len(results) if results else 0,
        'total_cases': len(results),
    }


def generate_extraction_chart(metrics, results, output_path):
    """Generate entity extraction performance chart."""
    case_ids = [r['test_case_id'] for r in results]
    f1_scores = [r['f1'] for r in results]

    fig, ax = plt.subplots(figsize=(14, 6))
    x = np.arange(len(case_ids))
    bars = ax.bar(x, f1_scores, color=['#2ecc71' if r['exact_match'] else '#f39c12' if r['partial_match'] else '#e74c3c' for r in results], alpha=0.8)

    ax.set_xlabel('Test Case')
    ax.set_ylabel('F1-Score')
    ax.set_title('GLiNER Entity Extraction F1 per Test Case')
    ax.set_xticks(x)
    ax.set_xticklabels(case_ids, rotation=45, ha='right', fontsize=8)
    ax.axhline(y=metrics['f1'], color='red', linestyle='--', label=f'Mean F1: {metrics["f1"]:.3f}')
    ax.legend()
    ax.set_ylim(0, 1.1)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()


def save_results(results, metrics, output_dir):
    """Save all results."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    results_csv = os.path.join(output_dir, f'gliner_results_{timestamp}.csv')
    with open(results_csv, 'w', newline='') as f:
        fieldnames = ['test_case_id', 'input', 'expected', 'predicted', 'precision', 'recall', 'f1', 'tp', 'fp', 'fn', 'exact_match', 'partial_match', 'category']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            row = dict(r)
            row['expected'] = json.dumps(r['expected'])
            row['predicted'] = json.dumps(r['predicted'])
            writer.writerow(row)

    metrics_json = os.path.join(output_dir, f'gliner_metrics_{timestamp}.json')
    with open(metrics_json, 'w') as f:
        json.dump(metrics, f, indent=2)

    report_md = os.path.join(output_dir, f'gliner_report_{timestamp}.md')
    with open(report_md, 'w') as f:
        f.write(f"# GLiNER Entity Extraction Evaluation Report\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## Overall Metrics\n\n")
        f.write(f"- **Precision:** {metrics['precision']:.4f}\n")
        f.write(f"- **Recall:** {metrics['recall']:.4f}\n")
        f.write(f"- **F1-Score:** {metrics['f1']:.4f}\n")
        f.write(f"- **Exact Match Rate:** {metrics['exact_match_rate']:.2%}\n")
        f.write(f"- **Partial Match Rate:** {metrics['partial_match_rate']:.2%}\n")
        f.write(f"- **Total Cases:** {metrics['total_cases']}\n\n")
        f.write(f"## Notes\n\n")
        f.write(f"- Model: urchade/gliner_base (zero-shot)\n")
        f.write(f"- NOT fine-tuned on project data\n")
        f.write(f"- Threshold: 0.5\n")

    return results_csv, metrics_json, report_md


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_cases_path = os.path.join(base_dir, 'test_cases', 'gliner_extraction_cases.csv')
    results_dir = os.path.join(base_dir, 'results')
    graphs_dir = os.path.join(base_dir, 'graphs')

    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(graphs_dir, exist_ok=True)

    print("=" * 60)
    print("GLiNER ENTITY EXTRACTION EVALUATION")
    print("=" * 60)

    if not os.path.exists(test_cases_path):
        print(f"ERROR: Test cases not found at {test_cases_path}")
        return 1

    test_cases = load_test_cases(test_cases_path)
    print(f"Loaded {len(test_cases)} test cases")

    print("\nRunning predictions...")
    results = run_evaluation(test_cases)

    metrics = compute_metrics(results)

    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"Precision:       {metrics['precision']:.4f}")
    print(f"Recall:          {metrics['recall']:.4f}")
    print(f"F1-Score:        {metrics['f1']:.4f}")
    print(f"Exact Match:     {metrics['exact_match_rate']:.2%}")
    print(f"Partial Match:   {metrics['partial_match_rate']:.2%}")

    print("\nGenerating graphs...")
    chart_path = os.path.join(graphs_dir, 'gliner_extraction_f1.png')
    generate_extraction_chart(metrics, results, chart_path)
    print(f"  F1 chart: {chart_path}")

    print("\nSaving results...")
    results_csv, metrics_json, report_md = save_results(results, metrics, results_dir)
    print(f"  Results CSV: {results_csv}")
    print(f"  Metrics JSON: {metrics_json}")
    print(f"  Report MD: {report_md}")

    print(f"\n{'='*60}")
    print("EVALUATION COMPLETE")
    print(f"{'='*60}")

    return 0


if __name__ == '__main__':
    sys.exit(main())