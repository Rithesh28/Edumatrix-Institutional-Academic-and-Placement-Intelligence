#!/usr/bin/env python3
"""
Resume Parser Evaluation Script (Fixed)
Evaluates the spaCy + regex resume parser on real DOCX/PDF files.

BUG-001 FIXES APPLIED:
1. Removed vacuous truth bug: missing fields no longer return True
2. Changed input method to use actual DOCX files
3. Fixed field comparison logic for complex types (lists, dicts)
4. Added proper error handling for empty/unavailable parsers
5. Added per-field accuracy tracking
"""

import sys
import os
import json
import csv
import re
from datetime import datetime
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from collections import defaultdict

# Add project root and backend directory to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
backend_path = os.path.join(project_root, 'backend')
sys.path.insert(0, project_root)
sys.path.insert(0, backend_path)

try:
    from backend.app.services.resume_parser import resume_parser
    from backend.app.ml.layoutlmv3.service import layoutlmv3_service
except ImportError:
    try:
        from app.services.resume_parser import resume_parser
        from app.ml.layoutlmv3.service import layoutlmv3_service
    except ImportError as e:
        print(f"Warning: Could not import resume parser: {e}")
        resume_parser = None
        layoutlmv3_service = None


def load_ground_truth(resume_dir):
    """Load ground truth JSON files for each resume."""
    ground_truth = {}
    gt_dir = Path(resume_dir) / 'ground_truth'
    if not gt_dir.exists():
        print(f"ERROR: Ground truth directory not found: {gt_dir}")
        return ground_truth

    for gt_file in sorted(gt_dir.glob('*.json')):
        resume_name = gt_file.stem + '.docx'
        with open(gt_file, 'r') as f:
            ground_truth[resume_name] = json.load(f)
        print(f"  Loaded ground truth: {gt_file.name}")

    return ground_truth


def find_resume_files(resume_dir):
    """Find all DOCX and PDF resume files."""
    resume_files = []
    for ext in ['.docx', '.pdf']:
        for f in Path(resume_dir).glob(f'*{ext}'):
            if 'ground_truth' not in str(f):
                resume_files.append(str(f))
    return sorted(resume_files)


def normalize_text(text):
    """Normalize text for comparison."""
    if not text:
        return ""
    text = str(text).lower().strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def compare_lists(parsed_list, expected_list):
    """Compare two lists with fuzzy matching."""
    if not parsed_list and not expected_list:
        return True, 1.0
    if not parsed_list or not expected_list:
        return False, 0.0

    parsed_set = set(normalize_text(v) for v in parsed_list if v)
    expected_set = set(normalize_text(v) for v in expected_list if v)

    if not expected_set:
        return False, 0.0

    intersection = len(parsed_set & expected_set)
    jaccard = intersection / max(len(parsed_set), len(expected_set), 1)

    return jaccard >= 0.5, jaccard


def compare_strings(parsed_str, expected_str):
    """Compare two strings with fuzzy matching."""
    if not parsed_str and not expected_str:
        return True, 1.0
    if not parsed_str or not expected_str:
        return False, 0.0

    p = normalize_text(parsed_str)
    e = normalize_text(expected_str)

    if p == e:
        return True, 1.0
    if p in e or e in p:
        return True, 0.8
    if any(word in e for word in p.split() if len(word) > 3):
        return True, 0.6

    return False, 0.0


def compare_values(parsed_val, expected_val):
    """Compare parsed and expected values with type awareness."""
    # Both missing
    if parsed_val is None and expected_val is None:
        return True, 1.0
    # One missing
    if parsed_val is None or expected_val is None:
        return False, 0.0

    # Both lists
    if isinstance(parsed_val, list) and isinstance(expected_val, list):
        return compare_lists(parsed_val, expected_val)

    # Both strings/numbers
    if isinstance(parsed_val, str) and isinstance(expected_val, str):
        return compare_strings(parsed_val, expected_val)

    # Number comparison (CGPA)
    try:
        p_num = float(parsed_val) if not isinstance(parsed_val, (int, float)) else parsed_val
        e_num = float(expected_val) if not isinstance(expected_val, (int, float)) else expected_val
        if abs(p_num - e_num) < 0.1:  # Allow 0.1 tolerance for CGPA
            return True, 0.95
        return False, max(0, 1 - abs(p_num - e_num) / 10)
    except (ValueError, TypeError):
        return compare_strings(str(parsed_val), str(expected_val))


def evaluate_resume(parser, resume_path, ground_truth):
    """Evaluate a single resume against ground truth."""
    result = {
        'resume_file': os.path.basename(resume_path),
        'status': 'UNKNOWN',
        'success': False,
        'error': None,
        'fields_evaluated': 0,
        'fields_correct': 0,
        'field_scores': {},
        'parsed_entities': {},
        'expected_entities': {}
    }

    # Run parser
    if parser is None:
        result['status'] = 'PARSER_UNAVAILABLE'
        result['error'] = 'Resume parser not initialized'
        return result

    try:
        parsed = parser.parse_resume(resume_path)
        result['success'] = parsed.get('success', False)
        result['parsed_entities'] = parsed.get('entities', {})
        result['status'] = 'SUCCESS' if parsed.get('success') else 'PARSE_FAILED'
        result['error'] = parsed.get('error')

        if not parsed.get('success'):
            print(f"  [FAIL] {result['resume_file']}: {parsed.get('error', 'Unknown error')}")
            return result

        # Compare with ground truth
        gt = ground_truth.get(os.path.basename(resume_path), {})
        result['expected_entities'] = gt

        # Define fields to evaluate
        fields_to_check = [
            'name', 'email', 'phone', 'cgpa', 'skills',
            'education', 'companies', 'experience',
            'projects', 'certifications', 'location'
        ]

        for field in fields_to_check:
            parsed_val = result['parsed_entities'].get(field)
            expected_val = gt.get(field)

            # Handle special cases
            if field == 'education' and parsed_val:
                # Extract education details from parsed entities
                edu_list = result['parsed_entities'].get('education', [])
                if edu_list:
                    parsed_val = [e.get('degree', '') for e in edu_list if isinstance(e, dict)]
                else:
                    parsed_val = None

            if field == 'experience' and parsed_val:
                # Extract experience entries for comparison
                exp_list = result['parsed_entities'].get('experience', [])
                if exp_list:
                    if isinstance(exp_list[0], dict):
                        # Dict format: [{"title": ..., "company": ..., "dates": ...}]
                        parsed_val = [e.get('title', '') for e in exp_list if isinstance(e, dict) and e.get('title')]
                    else:
                        # String format: "Title at Company (dates)"
                        # Parse into comparable dict list to match expected format
                        parsed_entries = []
                        for entry in exp_list:
                            m = re.match(r'(.+?)\s+at\s+(.+?)\s*\((.+)\)', entry)
                            if m:
                                parsed_entries.append({
                                    'title': m.group(1).strip(),
                                    'company': m.group(2).strip(),
                                    'dates': m.group(3).strip()
                                })
                        parsed_val = parsed_entries
                else:
                    parsed_val = None

            if field == 'companies' and parsed_val:
                # Extract companies from parsed experience
                exp_list = result['parsed_entities'].get('experience', [])
                if exp_list:
                    if isinstance(exp_list[0], dict):
                        parsed_companies = [e.get('company', '') for e in exp_list if isinstance(e, dict) and e.get('company')]
                    else:
                        # String format: "Title at Company (dates)"
                        parsed_companies = []
                        for entry in exp_list:
                            m = re.search(r' at ([^ (]+)(?:\s*\()', entry)
                            if m:
                                parsed_companies.append(m.group(1))
                    if parsed_companies:
                        parsed_val = parsed_companies

            # Compare
            correct, score = compare_values(parsed_val, expected_val)
            result['field_scores'][field] = {
                'correct': correct,
                'score': score,
                'parsed': str(parsed_val)[:100] if parsed_val else None,
                'expected': str(expected_val)[:100] if expected_val else None
            }

            if correct:
                result['fields_correct'] += 1
            result['fields_evaluated'] += 1

        # Calculate overall score
        if result['fields_evaluated'] > 0:
            avg_score = sum(fs['score'] for fs in result['field_scores'].values()) / result['fields_evaluated']
            result['overall_score'] = avg_score
            result['pass_rate'] = result['fields_correct'] / result['fields_evaluated']
        else:
            result['overall_score'] = 0.0
            result['pass_rate'] = 0.0

    except Exception as e:
        result['status'] = 'ERROR'
        result['error'] = str(e)
        print(f"  [ERROR] {result['resume_file']}: {e}")

    return result


def compute_metrics(results):
    """Compute aggregate metrics."""
    total_resumes = len(results)
    successful_parses = sum(1 for r in results if r['success'])
    failed_parses = total_resumes - successful_parses

    total_fields = sum(r['fields_evaluated'] for r in results)
    correct_fields = sum(r['fields_correct'] for r in results)
    skipped = sum(1 for r in results if r['status'] == 'PARSER_UNAVAILABLE')

    field_accuracy = correct_fields / total_fields if total_fields > 0 else 0.0

    # Per-field accuracy
    per_field_stats = defaultdict(lambda: {'correct': 0, 'total': 0})
    for r in results:
        if r['status'] == 'PARSER_UNAVAILABLE':
            continue
        for field, scores in r['field_scores'].items():
            per_field_stats[field]['total'] += 1
            if scores['correct']:
                per_field_stats[field]['correct'] += 1

    per_field_accuracy = {}
    for field, stats in per_field_stats.items():
        per_field_accuracy[field] = {
            'accuracy': stats['correct'] / stats['total'] if stats['total'] > 0 else 0.0,
            'correct': stats['correct'],
            'total': stats['total']
        }

    # Average scores
    scores = [r['overall_score'] for r in results if r['status'] != 'PARSER_UNAVAILABLE']
    avg_score = np.mean(scores) if scores else 0.0

    # Pass/fail distribution (threshold: 0.7 = pass)
    passed = sum(1 for r in results if r.get('pass_rate', 0) >= 0.7 and r['status'] != 'PARSER_UNAVAILABLE')
    partial = sum(1 for r in results if 0.5 <= r.get('pass_rate', 0) < 0.7)
    failed = sum(1 for r in results if r.get('pass_rate', 0) < 0.7 and r['status'] != 'PARSER_UNAVAILABLE')

    return {
        'total_resumes': total_resumes,
        'successful_parses': successful_parses,
        'failed_parses': failed_parses,
        'parser_unavailable': skipped,
        'total_fields_evaluated': total_fields,
        'correct_fields': correct_fields,
        'field_accuracy': field_accuracy,
        'per_field_accuracy': per_field_accuracy,
        'avg_overall_score': avg_score,
        'pass_count': passed,
        'partial_count': partial,
        'fail_count': failed,
        'pass_rate': passed / len(results) if results else 0.0,
        'results': results
    }


def generate_field_accuracy_chart(metrics, output_path):
    """Generate field-wise accuracy chart."""
    per_field = metrics.get('per_field_accuracy', {})
    if not per_field:
        print("  No field data to plot")
        return

    fields = sorted(per_field.keys(), key=lambda x: per_field[x]['accuracy'], reverse=True)
    accuracies = [per_field[f]['accuracy'] for f in fields]
    labels = [f'{f}\n({per_field[f]["correct"]}/{per_field[f]["total"]})' for f in fields]

    fig, ax = plt.subplots(figsize=(12, 6))

    colors = ['#2ecc71' if acc >= 0.7 else '#f39c12' if acc >= 0.5 else '#e74c3c' for acc in accuracies]
    bars = ax.barh(labels, accuracies, color=colors, alpha=0.8, edgecolor='black', linewidth=0.5)

    # Add value labels
    for bar, acc in zip(bars, accuracies):
        width = bar.get_width()
        ax.text(width + 0.02, bar.get_y() + bar.get_height()/2, f'{acc:.1%}',
                ha='left', va='center', fontsize=9, fontweight='bold')

    ax.set_xlabel('Field Accuracy', fontsize=11)
    ax.set_title('Resume Parser: Field-wise Extraction Accuracy', fontsize=13, fontweight='bold')
    ax.set_xlim(0, 1.1)
    ax.axvline(x=0.7, color='green', linestyle='--', alpha=0.5, label='Pass Threshold (70%)')
    ax.axvline(x=0.5, color='orange', linestyle='--', alpha=0.5, label='Partial Threshold (50%)')
    ax.legend(loc='lower right')

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {output_path}")


def generate_extraction_performance_chart(metrics, output_path):
    """Generate per-resume performance chart."""
    results = metrics.get('results', [])
    if not results:
        print("  No results to plot")
        return

    resumes = [r['resume_file'] for r in results if r['status'] != 'PARSER_UNAVAILABLE']
    scores = [r.get('overall_score', 0) for r in results if r['status'] != 'PARSER_UNAVAILABLE']
    pass_rates = [r.get('pass_rate', 0) for r in results if r['status'] != 'PARSER_UNAVAILABLE']

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Overall score distribution
    colors = ['#2ecc71' if s >= 0.7 else '#f39c12' if s >= 0.5 else '#e74c3c' for s in scores]
    bars1 = axes[0].bar(resumes, scores, color=colors, alpha=0.8, edgecolor='black', linewidth=0.5)
    axes[0].axhline(y=metrics['avg_overall_score'], color='blue', linestyle='--',
                    label=f'Average: {metrics["avg_overall_score"]:.2%}')
    axes[0].axhline(y=0.7, color='green', linestyle=':', alpha=0.5, label='Pass Threshold')
    axes[0].set_ylabel('Overall Score', fontsize=10)
    axes[0].set_title('Resume Parser: Overall Performance per Resume', fontsize=12, fontweight='bold')
    axes[0].set_xticks(range(len(resumes)))
    axes[0].set_xticklabels(resumes, rotation=45, ha='right', fontsize=8)
    axes[0].legend(fontsize=8)
    axes[0].set_ylim(0, 1.1)

    # Add value labels
    for bar, score in zip(bars1, scores):
        axes[0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                     f'{score:.2f}', ha='center', va='bottom', fontsize=8, fontweight='bold')

    # Pass rate distribution
    colors2 = ['#2ecc71' if p >= 0.7 else '#f39c12' if p >= 0.5 else '#e74c3c' for p in pass_rates]
    bars2 = axes[1].bar(resumes, pass_rates, color=colors2, alpha=0.8, edgecolor='black', linewidth=0.5)
    axes[1].axhline(y=0.7, color='green', linestyle='--', alpha=0.5, label='Pass Threshold')
    axes[1].set_ylabel('Field Pass Rate', fontsize=10)
    axes[1].set_title('Resume Parser: Field-level Pass Rate per Resume', fontsize=12, fontweight='bold')
    axes[1].set_xticks(range(len(resumes)))
    axes[1].set_xticklabels(resumes, rotation=45, ha='right', fontsize=8)
    axes[1].legend(fontsize=8)
    axes[1].set_ylim(0, 1.1)

    # Add value labels
    for bar, pr in zip(bars2, pass_rates):
        axes[1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                     f'{pr:.0%}', ha='center', va='bottom', fontsize=8, fontweight='bold')

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {output_path}")


def save_results(metrics, output_dir):
    """Save all results to files."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Results CSV
    results_csv = os.path.join(output_dir, f'resume_parser_results_fixed_{timestamp}.csv')
    with open(results_csv, 'w', newline='') as f:
        fieldnames = ['resume_file', 'status', 'success', 'fields_evaluated', 'fields_correct',
                     'pass_rate', 'overall_score', 'error']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in metrics['results']:
            writer.writerow({
                'resume_file': r['resume_file'],
                'status': r['status'],
                'success': r['success'],
                'fields_evaluated': r['fields_evaluated'],
                'fields_correct': r['fields_correct'],
                'pass_rate': r.get('pass_rate', 0),
                'overall_score': r.get('overall_score', 0),
                'error': r.get('error', '')
            })
    print(f"  Saved: {results_csv}")

    # Metrics JSON
    metrics_json = os.path.join(output_dir, f'resume_parser_metrics_fixed_{timestamp}.json')
    # Convert defaultdict to regular dict for JSON serialization
    metrics_serializable = dict(metrics)
    metrics_serializable['per_field_accuracy'] = dict(metrics_serializable.get('per_field_accuracy', {}))
    with open(metrics_json, 'w') as f:
        json.dump(metrics_serializable, f, indent=2, default=str)
    print(f"  Saved: {metrics_json}")

    # Report MD
    report_md = os.path.join(output_dir, f'resume_parser_report_fixed_{timestamp}.md')
    with open(report_md, 'w') as f:
        f.write(f"# Resume Parser Evaluation Report (Fixed)\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Fix Applied:** BUG-001 - Removed vacuous truth, using real DOCX files\n\n")
        f.write(f"## Overall Metrics\n\n")
        f.write(f"- **Total Resumes:** {metrics['total_resumes']}\n")
        f.write(f"- **Successful Parses:** {metrics['successful_parses']}\n")
        f.write(f"- **Failed Parses:** {metrics['failed_parses']}\n")
        f.write(f"- **Parser Unavailable:** {metrics['parser_unavailable']}\n")
        f.write(f"- **Total Fields Evaluated:** {metrics['total_fields_evaluated']}\n")
        f.write(f"- **Correct Fields:** {metrics['correct_fields']}\n")
        f.write(f"- **Field Accuracy:** {metrics['field_accuracy']:.2%}\n")
        f.write(f"- **Average Overall Score:** {metrics['avg_overall_score']:.2%}\n")
        f.write(f"- **Pass Rate (>=70%):** {metrics['pass_rate']:.2%}\n\n")

        f.write(f"## Per-Field Accuracy\n\n")
        f.write(f"| Field | Correct | Total | Accuracy |\n")
        f.write(f"|-------|---------|-------|----------|\n")
        for field, stats in sorted(metrics['per_field_accuracy'].items(),
                                    key=lambda x: x[1]['accuracy'], reverse=True):
            f.write(f"| {field} | {stats['correct']} | {stats['total']} | {stats['accuracy']:.2%} |\n")

        f.write(f"\n## Detailed Results\n\n")
        for r in metrics['results']:
            f.write(f"### {r['resume_file']}\n\n")
            f.write(f"- Status: {r['status']}\n")
            f.write(f"- Success: {r['success']}\n")
            f.write(f"- Fields: {r['fields_correct']}/{r['fields_evaluated']}\n")
            f.write(f"- Pass Rate: {r.get('pass_rate', 0):.2%}\n")
            f.write(f"- Overall Score: {r.get('overall_score', 0):.2f}\n")
            if r.get('error'):
                f.write(f"- Error: {r['error']}\n")
            f.write("\n")

            # Field details
            if r['field_scores']:
                f.write(f"| Field | Correct | Score | Parsed | Expected |\n")
                f.write(f"|-------|---------|-------|--------|----------|\n")
                for field, scores in r['field_scores'].items():
                    parsed_preview = str(scores.get('parsed', ''))[:50]
                    expected_preview = str(scores.get('expected', ''))[:50]
                    f.write(f"| {field} | {'[PASS]' if scores['correct'] else '[FAIL]'} | {scores['score']:.2f} | {parsed_preview} | {expected_preview} |\n")
                f.write("\n")

    print(f"  Saved: {report_md}")

    return results_csv, metrics_json, report_md


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    evaluation_dir = os.path.dirname(base_dir)
    resume_dir = os.path.join(evaluation_dir, 'test_cases', 'resumes')
    results_dir = os.path.join(evaluation_dir, 'results')
    graphs_dir = os.path.join(evaluation_dir, 'graphs', 'all_models')

    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(graphs_dir, exist_ok=True)

    print("=" * 70)
    print("RESUME PARSER EVALUATION (BUG-001 FIXED)")
    print("=" * 70)
    print()

    # Check parser availability
    if resume_parser is None:
        print("ERROR: Resume parser not available")
        print("  - Ensure spacy model 'en_core_web_sm' is installed")
        print("  - Run: python -m spacy download en_core_web_sm")
        return 1

    # Load ground truth
    print("Loading ground truth...")
    ground_truth = load_ground_truth(resume_dir)
    if not ground_truth:
        print("ERROR: No ground truth files found")
        return 1
    print(f"  Found {len(ground_truth)} ground truth files")
    print()

    # Find resume files
    print("Finding resume files...")
    resume_files = find_resume_files(resume_dir)
    if not resume_files:
        print("ERROR: No DOCX/PDF files found in", resume_dir)
        return 1
    print(f"  Found {len(resume_files)} resume files:")
    for rf in resume_files:
        print(f"    - {os.path.basename(rf)}")
    print()

    # Evaluate each resume
    print("Running evaluation...")
    print("-" * 70)
    results = []
    for resume_path in resume_files:
        resume_name = os.path.basename(resume_path)
        print(f"\nEvaluating: {resume_name}")

        result = evaluate_resume(resume_parser, resume_path, ground_truth)
        results.append(result)

        if result['success']:
            print(f"  [OK] Status: {result['status']}")
            print(f"  [OK] Fields: {result['fields_correct']}/{result['fields_evaluated']}")
            print(f"  [OK] Pass Rate: {result.get('pass_rate', 0):.2%}")
            print(f"  [OK] Overall Score: {result.get('overall_score', 0):.2f}")
        else:
            print(f"  [FAIL] Status: {result['status']}")
            if result.get('error'):
                print(f"  [FAIL] Error: {result['error']}")

        # Print field details
        if result['field_scores']:
            print(f"  Field Details:")
            for field, scores in result['field_scores'].items():
                status = '[PASS]' if scores['correct'] else '[FAIL]'
                print(f"    {status} {field}: {scores['score']:.2f}")

    print()
    print("-" * 70)

    # Compute metrics
    print("Computing metrics...")
    metrics = compute_metrics(results)

    print(f"\n{'='*70}")
    print("EVALUATION SUMMARY")
    print(f"{'='*70}")
    print(f"Total Resumes Evaluated: {metrics['total_resumes']}")
    print(f"Successful Parses:       {metrics['successful_parses']}")
    print(f"Failed Parses:           {metrics['failed_parses']}")
    print(f"Parser Unavailable:      {metrics['parser_unavailable']}")
    print(f"Total Fields Evaluated:  {metrics['total_fields_evaluated']}")
    print(f"Correct Fields:          {metrics['correct_fields']}")
    print(f"Field Accuracy:          {metrics['field_accuracy']:.2%}")
    print(f"Average Overall Score:   {metrics['avg_overall_score']:.2%}")
    print(f"Pass Rate (>=70%):        {metrics['pass_rate']:.2%}")

    print(f"\nPer-Field Accuracy:")
    for field, stats in sorted(metrics['per_field_accuracy'].items(),
                                key=lambda x: x[1]['accuracy'], reverse=True):
        print(f"  {field:15s}: {stats['correct']:2d}/{stats['total']:2d} = {stats['accuracy']:.2%}")

    print(f"\nSaving results...")
    results_csv, metrics_json, report_md = save_results(metrics, results_dir)
    print(f"  Results:   {results_csv}")
    print(f"  Metrics:   {metrics_json}")
    print(f"  Report:    {report_md}")

    # Generate graphs
    print(f"\nGenerating graphs...")
    field_chart = os.path.join(graphs_dir, 'resume_parser_field_accuracy.png')
    perf_chart = os.path.join(graphs_dir, 'resume_parser_extraction_performance.png')
    generate_field_accuracy_chart(metrics, field_chart)
    generate_extraction_performance_chart(metrics, perf_chart)

    print(f"\n{'='*70}")
    print("EVALUATION COMPLETE")
    print(f"{'='*70}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
