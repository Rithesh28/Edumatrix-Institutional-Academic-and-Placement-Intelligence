#!/usr/bin/env python3
"""
JD Parser Evaluation Script
Evaluates the hybrid regex + GLiNER JD parser on test cases.
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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from app.services.jd_parser_service import jd_parser_service as jd_parser


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
        return True
    if field not in parsed or field not in expected:
        return False

    p_val = parsed[field]
    e_val = expected[field]

    if isinstance(p_val, list) and isinstance(e_val, list):
        p_set = set(normalize_text(v) for v in p_val if v)
        e_set = set(normalize_text(v) for v in e_val if v)
        return len(p_set & e_set) / max(len(p_set), len(e_set), 1) > 0.5

    if isinstance(p_val, str) and isinstance(e_val, str):
        return normalize_text(p_val) == normalize_text(e_val) or \
               normalize_text(p_val) in normalize_text(e_val) or \
               normalize_text(e_val) in normalize_text(p_val)

    return False


def run_evaluation(test_cases):
    """Run JD parser on test cases."""
    results = []

    for tc in test_cases:
        text = tc['input_text']
        # Parse expected fields (pipe-delimited in CSV)
        expected_str = tc.get('expected_fields', '')
        if expected_str:
            expected = {k.strip(): v.strip() for k, v in [pair.split(':') for pair in expected_str.split('|') if ':' in pair]}
        else:
            expected = {}

        # Run parser
        parsed = jd_parser.parse(text)

        # Compute field-level metrics
        fields_to_check = ['company', 'job_title', 'skills', 'experience_years',
                          'academic_requirements', 'cgpa_requirement', 'percentage_10th',
                          'percentage_12th', 'percentage_degree', 'location',
                          'compensation', 'selection_rounds', 'date',
                          'has_bond', 'qualification_required']

        fields_matched = 0
        for field in fields_to_check:
            if compute_field_match(parsed, expected, field):
                fields_matched += 1

        overall_score = fields_matched / len(fields_to_check) if fields_to_check else 0

        results.append({
            'test_case_id': tc['test_case_id'],
            'input': text[:100],
            'expected': expected,
            'predicted': {k: str(v)[:80] for k, v in parsed.items()},
            'overall_score': round(overall_score, 3),
            'fields_matched': fields_matched,
            'total_fields': len(fields_to_check),
            'status': 'PASS' if overall_score >= 0.7 else 'PARTIAL' if overall_score >= 0.5 else 'FAIL',
            'category': tc['category'],
        })

        status = '[PASS]' if overall_score >= 0.7 else ('[PARTIAL]' if overall_score >= 0.5 else '[FAIL]')
        print(f"{tc['test_case_id']}: {fields_matched}/{len(fields_to_check)} fields ({overall_score:.2f}) {status}")

    return results


def compute_metrics(results):
    """Compute aggregate metrics."""
    pass_count = sum(1 for r in results if r['status'] == 'PASS')
    partial_count = sum(1 for r in results if r['status'] == 'PARTIAL')
    fail_count = sum(1 for r in results if r['status'] == 'FAIL')

    return {
        'total_cases': len(results),
        'pass_count': pass_count,
        'partial_count': partial_count,
        'fail_count': fail_count,
        'pass_rate': pass_count / len(results) if results else 0,
        'avg_field_match_score': np.mean([r['overall_score'] for r in results]) if results else 0,
        'avg_fields_matched': np.mean([r['fields_matched'] for r in results]) if results else 0,
    }


def save_results(results, metrics, output_dir):
    """Save all results."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    results_csv = os.path.join(output_dir, f'jd_parser_results_{timestamp}.csv')
    with open(results_csv, 'w', newline='') as f:
        fieldnames = ['test_case_id', 'input', 'expected', 'predicted', 'overall_score',
                     'fields_matched', 'total_fields', 'status', 'category']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({k: json.dumps(v) if isinstance(v, dict) else v for k, v in r.items()})

    metrics_json = os.path.join(output_dir, f'jd_parser_metrics_{timestamp}.json')
    with open(metrics_json, 'w') as f:
        json.dump(metrics, f, indent=2)

    report_md = os.path.join(output_dir, f'jd_parser_report_{timestamp}.md')
    with open(report_md, 'w') as f:
        f.write(f"# JD Parser Evaluation Report\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## Overall Metrics\n\n")
        f.write(f"- **Total Cases:** {metrics['total_cases']}\n")
        f.write(f"- **Pass (>=70%):** {metrics['pass_count']}\n")
        f.write(f"- **Partial (50-70%):** {metrics['partial_count']}\n")
        f.write(f"- **Fail (<50%):** {metrics['fail_count']}\n")
        f.write(f"- **Pass Rate:** {metrics['pass_rate']:.2%}\n")
        f.write(f"- **Avg Field Match:** {metrics['avg_field_match_score']:.3f}\n\n")
        f.write(f"## Notes\n\n")
        f.write(f"- Parser: Hybrid (regex + GLiNER)\n")
        f.write(f"- 14 fields evaluated\n")

    return results_csv, metrics_json, report_md


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_cases_path = os.path.join(base_dir, 'test_cases', 'jd_parser_cases.csv')
    results_dir = os.path.join(base_dir, 'results')
    graphs_dir = os.path.join(base_dir, 'graphs')

    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(graphs_dir, exist_ok=True)

    print("=" * 60)
    print("JD PARSER EVALUATION")
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