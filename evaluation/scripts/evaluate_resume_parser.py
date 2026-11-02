#!/usr/bin/env python3
"""
Resume Parser Evaluation Script
Evaluates the spaCy + LayoutLMv3 resume parser on test cases.
"""

import sys
import os
import json
import csv
import re
from datetime import datetime
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import re
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

try:
    from app.services.resume_parser import resume_parser
    from app.ml.layoutlmv3.service import layoutlmv3_service
except ImportError as e:
    print(f"Warning: Could not import resume parser: {e}")
    resume_parser = None
    layoutlmv3_service = None


def load_test_cases(csv_path):
    """Load test cases from CSV."""
    test_cases = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            test_cases.append(row)
    return test_cases


def normalize_text(text):
    """Normalize text for comparison."""
    if not text:
        return ""
    text = str(text).lower().strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def compute_field_match(parsed, expected, field):
    """Check if a field matches between parsed and expected."""
    if field not in parsed and field not in expected:
        return True  # Both missing is OK
    if field not in parsed or field not in expected:
        return False

    p_val = parsed[field]
    e_val = expected[field]

    # Handle lists
    if isinstance(p_val, list) and isinstance(e_val, list):
        p_set = set(normalize_text(v) for v in p_val)
        e_set = set(normalize_text(v) for v in e_val)
        return len(p_set & e_set) / max(len(p_set), len(e_set), 1) > 0.5

    # Handle strings
    if isinstance(p_val, str) and isinstance(e_val, str):
        return normalize_text(p_val) == normalize_text(e_val) or \
               normalize_text(p_val) in normalize_text(e_val) or \
               normalize_text(e_val) in normalize_text(p_val)

    return False


def run_evaluation(test_cases):
    """Run resume parser on test cases."""
    results = []

    for tc in test_cases:
        text = tc['input_text']
        # Parse expected entities (pipe-delimited in CSV)
        expected_str = tc.get('expected_entities', '')
        if expected_str:
            expected = {k.strip(): v.strip() for k, v in [pair.split(':') for pair in expected_str.split('|') if ':' in pair]}
        else:
            expected = {}

        if resume_parser is None:
            results.append({
                'test_case_id': tc['test_case_id'],
                'input': text[:100],
                'expected': expected,
                'predicted': {},
                'overall_score': 0.0,
                'fields_matched': 0,
                'total_fields': len(expected),
                'status': 'SKIPPED_PARSER_NOT_AVAILABLE',
                'category': tc['category'],
            })
            continue

        # Run parser
        parsed = resume_parser.parse_resume(text)

        # Compute field-level metrics
        fields_to_check = ['name', 'email', 'phone', 'skills', 'education',
                          'experience', 'projects', 'certifications',
                          'companies', 'universities', 'degrees',
                          'locations', 'dates', 'cgpa']

        fields_matched = 0
        for field in fields_to_check:
            if compute_field_match(parsed, expected, field):
                fields_matched += 1

        overall_score = fields_matched / len(fields_to_check) if fields_to_check else 0

        results.append({
            'test_case_id': tc['test_case_id'],
            'input': text[:100],
            'expected': expected,
            'predicted': {k: str(v)[:50] for k, v in parsed.items()},
            'overall_score': round(overall_score, 3),
            'fields_matched': fields_matched,
            'total_fields': len(fields_to_check),
            'status': 'PASS' if overall_score >= 0.7 else 'PARTIAL' if overall_score >= 0.5 else 'FAIL',
            'category': tc['category'],
        })

        status = '[PASS]' if overall_score >= 0.7 else ('[PARTIAL]' if overall_score >= 0.5 else '[FAIL]')
        print(f"{tc['test_case_id']}: {fields_matched}/{len(fields_to_check)} fields matched ({overall_score:.2f}) {status}")

    return results


def compute_metrics(results):
    """Compute aggregate metrics."""
    pass_count = sum(1 for r in results if r['status'] == 'PASS')
    partial_count = sum(1 for r in results if r['status'] == 'PARTIAL')
    fail_count = sum(1 for r in results if r['status'] == 'FAIL' or r['status'].startswith('SKIPPED'))

    avg_score = np.mean([r['overall_score'] for r in results]) if results else 0

    return {
        'total_cases': len(results),
        'pass_count': pass_count,
        'partial_count': partial_count,
        'fail_count': fail_count,
        'pass_rate': pass_count / len(results) if results else 0,
        'avg_field_match_score': avg_score,
        'avg_fields_matched': np.mean([r['fields_matched'] for r in results]) if results else 0,
    }


def generate_parser_chart(metrics, results, output_path):
    """Generate parser performance chart."""
    case_ids = [r['test_case_id'] for r in results]
    scores = [r['overall_score'] for r in results]

    fig, ax = plt.subplots(figsize=(14, 6))
    colors = ['#2ecc71' if r['overall_score'] >= 0.7 else '#f39c12' if r['overall_score'] >= 0.5 else '#e74c3c' for r in results]
    bars = ax.bar(case_ids, scores, color=colors, alpha=0.8)

    ax.set_xlabel('Test Case')
    ax.set_ylabel('Field Match Score')
    ax.set_title('Resume Parser Field Match Score per Test Case')
    ax.set_xticks(range(len(case_ids)))
    ax.set_xticklabels(case_ids, rotation=45, ha='right', fontsize=8)
    ax.axhline(y=metrics['avg_field_match_score'], color='blue', linestyle='--',
               label=f'Mean: {metrics["avg_field_match_score"]:.3f}')
    ax.axhline(y=0.7, color='green', linestyle=':', alpha=0.5, label='Pass Threshold (0.7)')
    ax.legend()
    ax.set_ylim(0, 1.1)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()


def save_results(results, metrics, output_dir):
    """Save all results."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    results_csv = os.path.join(output_dir, f'resume_parser_results_{timestamp}.csv')
    with open(results_csv, 'w', newline='') as f:
        fieldnames = ['test_case_id', 'input', 'expected', 'predicted', 'overall_score',
                     'fields_matched', 'total_fields', 'status', 'category']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({k: json.dumps(v) if isinstance(v, dict) else v for k, v in r.items()})

    metrics_json = os.path.join(output_dir, f'resume_parser_metrics_{timestamp}.json')
    with open(metrics_json, 'w') as f:
        json.dump(metrics, f, indent=2)

    report_md = os.path.join(output_dir, f'resume_parser_report_{timestamp}.md')
    with open(report_md, 'w') as f:
        f.write(f"# Resume Parser Evaluation Report\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## Overall Metrics\n\n")
        f.write(f"- **Total Cases:** {metrics['total_cases']}\n")
        f.write(f"- **Pass (>=70%):** {metrics['pass_count']}\n")
        f.write(f"- **Partial (50-70%):** {metrics['partial_count']}\n")
        f.write(f"- **Fail (<50%):** {metrics['fail_count']}\n")
        f.write(f"- **Pass Rate:** {metrics['pass_rate']:.2%}\n")
        f.write(f"- **Avg Field Match Score:** {metrics['avg_field_match_score']:.3f}\n\n")
        f.write(f"## Notes\n\n")
        f.write(f"- Parser: spaCy NER + regex + LayoutLMv3 verification\n")
        f.write(f"- 14 entity fields evaluated\n")
        f.write(f"- Field match: normalized text comparison (50% overlap threshold)\n")

    return results_csv, metrics_json, report_md


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_cases_path = os.path.join(base_dir, 'test_cases', 'resume_parser_cases.csv')
    results_dir = os.path.join(base_dir, 'results')
    graphs_dir = os.path.join(base_dir, 'graphs')

    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(graphs_dir, exist_ok=True)

    print("=" * 60)
    print("RESUME PARSER EVALUATION")
    print("=" * 60)

    if not os.path.exists(test_cases_path):
        print(f"ERROR: Test cases not found at {test_cases_path}")
        return 1

    test_cases = load_test_cases(test_cases_path)
    print(f"Loaded {len(test_cases)} test cases")

    print("\nRunning evaluation...")
    results = run_evaluation(test_cases)

    metrics = compute_metrics(results)

    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"Total Cases:       {metrics['total_cases']}")
    print(f"Pass Rate:         {metrics['pass_rate']:.2%}")
    print(f"Avg Field Match:   {metrics['avg_field_match_score']:.3f}")

    print("\nSaving results...")
    results_csv, metrics_json, report_md = save_results(results, metrics, results_dir)
    print(f"  Results: {results_csv}")
    print(f"  Metrics: {metrics_json}")
    print(f"  Report: {report_md}")

    print(f"\n{'='*60}")
    print("EVALUATION COMPLETE")
    print(f"{'='*60}")

    return 0


if __name__ == '__main__':
    sys.exit(main())