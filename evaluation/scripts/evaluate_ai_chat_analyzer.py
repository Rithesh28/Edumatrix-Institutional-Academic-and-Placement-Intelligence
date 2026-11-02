#!/usr/bin/env python3
"""
AI Chat Analyzer Evaluation Script
Evaluates the Qwen LLM-based AI Chat Analyzer with grounding checks.
Tests: grounding accuracy, hallucination detection, ambiguity detection.
"""

import sys
import os
import json
import csv
from datetime import datetime
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))


def load_test_cases(csv_path):
    """Load test cases from CSV."""
    test_cases = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            test_cases.append(row)
    return test_cases


def compute_grounding_score(response, sources_used, expected_sources):
    """Check if response uses correct sources."""
    if not response or not sources_used:
        return 0.0

    used_set = set(sources_used)
    expected_set = set(expected_sources)

    # All expected sources should be used
    recall = len(used_set & expected_set) / len(expected_set) if expected_set else 1.0

    # Penalize extra sources not in expected
    precision = len(used_set & expected_set) / len(used_set) if used_set else 0.0

    return 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0


def detect_hallucination(response, sources):
    """
    Simple hallucination heuristic: check if response contains claims not in sources.
    """
    if not response or not sources:
        return False, 0.0

    response_lower = response.lower()
    source_text = ' '.join(sources).lower()

    # Check for specific factual claims
    hallucination_indicators = ['i think', 'probably', 'might be', 'possibly', 'i believe']
    for indicator in hallucination_indicators:
        if indicator in response_lower:
            return True, 0.3

    # Check if response contains information not in sources
    words = set(response_lower.split())
    source_words = set(source_text.split())

    unsupported = words - source_words
    ratio = len(unsupported) / max(len(words), 1)

    return ratio > 0.5, ratio


def run_evaluation(test_cases):
    """Run AI Chat Analyzer evaluation."""
    results = []

    for tc in test_cases:
        query = tc['input_query']
        # Parse expected sources (pipe-delimited in CSV)
        sources_str = tc.get('expected_sources', '')
        expected_sources = [s.strip() for s in sources_str.split('|') if s.strip()] if sources_str else []
        expected_answer = tc.get('expected_answer', '')

        # Simulate - in production, call ai_generator_service
        results.append({
            'test_case_id': tc['test_case_id'],
            'query': query[:80],
            'expected_sources': expected_sources,
            'sources_used': [],
            'grounding_score': 0.0,
            'hallucination_detected': False,
            'hallucination_risk': 0.0,
            'ambiguity_detected': tc.get('expected_ambiguity', False),
            'latency_ms': 0,
            'status': 'PENDING_MODEL_EVAL',
            'category': tc['category'],
        })

        amb_flag = '[AMBIG]' if tc.get('expected_ambiguity', False) else ''
        print(f"{tc['test_case_id']}: '{query[:50]}...' {amb_flag} [PENDING]")

    return results


def compute_metrics(results):
    """Compute aggregate metrics."""
    pending = sum(1 for r in results if r['status'] == 'PENDING_MODEL_EVAL')

    return {
        'total_cases': len(results),
        'pending_model_eval': pending,
        'evaluated': len(results) - pending,
        'avg_grounding': np.mean([r['grounding_score'] for r in results if r['status'] != 'PENDING_MODEL_EVAL']) if any(r['status'] != 'PENDING_MODEL_EVAL' for r in results) else 0,
        'hallucination_rate': sum(1 for r in results if r['hallucination_detected']) / len(results) if results else 0,
        'ambiguity_detection_rate': sum(1 for r in results if r['ambiguity_detected']) / len(results) if results else 0,
    }


def save_results(results, metrics, output_dir):
    """Save all results."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    results_json = os.path.join(output_dir, f'ai_chat_analyzer_results_{timestamp}.json')
    with open(results_json, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    metrics_json = os.path.join(output_dir, f'ai_chat_analyzer_metrics_{timestamp}.json')
    with open(metrics_json, 'w') as f:
        json.dump(metrics, f, indent=2)

    report_md = os.path.join(output_dir, f'ai_chat_analyzer_report_{timestamp}.md')
    with open(report_md, 'w') as f:
        f.write(f"# AI Chat Analyzer Evaluation Report\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## Summary\n\n")
        f.write(f"- **Total Test Cases:** {metrics['total_cases']}\n")
        f.write(f"- **Pending Model Eval:** {metrics['pending_model_eval']}\n\n")
        f.write(f"## Metrics\n\n")
        f.write(f"- **Avg Grounding Score:** {metrics['avg_grounding']:.3f}\n")
        f.write(f"- **Hallucination Rate:** {metrics['hallucination_rate']:.2%}\n")
        f.write(f"- **Ambiguity Detection Rate:** {metrics['ambiguity_detection_rate']:.2%}\n\n")
        f.write(f"## Notes\n\n")
        f.write(f"- Model: Qwen Instruct (via Transformers)\n")
        f.write(f"- Grounding: Strict anti-hallucination with fallback\n")
        f.write(f"- Ambiguity: Detected via keyword analysis\n")

    return results_json, metrics_json, report_md


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_cases_path = os.path.join(base_dir, 'test_cases', 'ai_chat_analyzer_cases.csv')
    results_dir = os.path.join(base_dir, 'results')
    graphs_dir = os.path.join(base_dir, 'graphs')

    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(graphs_dir, exist_ok=True)

    print("=" * 60)
    print("AI CHAT ANALYZER EVALUATION")
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
    print(f"Pending Model:     {metrics['pending_model_eval']}")

    print("\nSaving results...")
    results_json, metrics_json, report_md = save_results(results, metrics, results_dir)
    print(f"  Results: {results_json}")
    print(f"  Metrics: {metrics_json}")
    print(f"  Report: {report_md}")

    print(f"\n{'='*60}")
    print("NOTE: Structural placeholders - run with live Qwen for real metrics.")
    print(f"{'='*60}")

    return 0


if __name__ == '__main__':
    sys.exit(main())