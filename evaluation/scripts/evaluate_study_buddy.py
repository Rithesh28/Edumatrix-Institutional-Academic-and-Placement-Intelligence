#!/usr/bin/env python3
"""
Study Buddy RAG Evaluation Script
Evaluates the Ollama Phi-4-mini RAG-based Study Buddy assistant.
Tests: answer correctness, grounding, citation accuracy, latency.
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


def compute_faithfulness(response, context):
    """
    Simple faithfulness heuristic: check if response contains key facts from context.
    In production, this would use a cross-encoder or LLM-as-judge.
    """
    if not response or not context:
        return 0.5

    response_lower = response.lower()
    context_lower = context.lower()

    # Check for key term overlap
    context_words = set(context_lower.split())
    response_words = set(response_lower.split())

    overlap = len(context_words & response_words)
    total = len(context_words | response_words)

    return overlap / total if total > 0 else 0.0


def compute_grounding(response, expected_answer):
    """
    Check if response aligns with expected answer.
    """
    if not response or not expected_answer:
        return 0.0

    response_lower = response.lower().strip()
    expected_lower = expected_answer.lower().strip()

    # Exact match
    if response_lower == expected_lower:
        return 1.0

    # Contains expected answer
    if expected_lower in response_lower:
        return 0.8

    # Partial match
    resp_words = set(response_lower.split())
    exp_words = set(expected_lower.split())

    overlap = len(resp_words & exp_words)
    total = len(exp_words)

    return overlap / total if total > 0 else 0.0


def run_evaluation(test_cases):
    """Run Study Buddy evaluation on test cases."""
    results = []

    for tc in test_cases:
        query = tc['input_query']
        expected_answer = tc.get('expected_answer', '')
        context = tc.get('context', '')
        mode = tc.get('mode', 'rag')

        # Simulate evaluation - in production, call study_buddy_chat_service
        # Here we compute metrics based on test case properties
        results.append({
            'test_case_id': tc['test_case_id'],
            'query': query[:80],
            'mode': mode,
            'expected': expected_answer[:100],
            'faithfulness_score': 0.0,  # Would need actual model response
            'grounding_score': 0.0,
            'citation_present': False,
            'latency_ms': 0,
            'status': 'PENDING_MODEL_EVAL',
            'category': tc['category'],
        })

        print(f"{tc['test_case_id']}: '{query[:50]}...' -> Mode: {mode} [PENDING]")

    return results


def compute_metrics(results):
    """Compute aggregate metrics."""
    pending = sum(1 for r in results if r['status'] == 'PENDING_MODEL_EVAL')
    evaluated = len(results) - pending

    return {
        'total_cases': len(results),
        'pending_model_eval': pending,
        'evaluated': evaluated,
        'avg_faithfulness': np.mean([r['faithfulness_score'] for r in results]) if evaluated > 0 else 0,
        'avg_grounding': np.mean([r['grounding_score'] for r in results]) if evaluated > 0 else 0,
        'citation_rate': sum(1 for r in results if r['citation_present']) / evaluated if evaluated > 0 else 0,
        'avg_latency_ms': np.mean([r['latency_ms'] for r in results]) if evaluated > 0 else 0,
    }


def save_results(results, metrics, output_dir):
    """Save all results."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    results_json = os.path.join(output_dir, f'study_buddy_results_{timestamp}.json')
    with open(results_json, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    metrics_json = os.path.join(output_dir, f'study_buddy_metrics_{timestamp}.json')
    with open(metrics_json, 'w') as f:
        json.dump(metrics, f, indent=2)

    report_md = os.path.join(output_dir, f'study_buddy_report_{timestamp}.md')
    with open(report_md, 'w') as f:
        f.write(f"# Study Buddy RAG Evaluation Report\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## Summary\n\n")
        f.write(f"- **Total Test Cases:** {metrics['total_cases']}\n")
        f.write(f"- **Evaluated:** {metrics['evaluated']}\n")
        f.write(f"- **Pending Model Eval:** {metrics['pending_model_eval']}\n\n")
        f.write(f"## RAG Metrics\n\n")
        f.write(f"- **Avg Faithfulness:** {metrics['avg_faithfulness']:.3f}\n")
        f.write(f"- **Avg Grounding:** {metrics['avg_grounding']:.3f}\n")
        f.write(f"- **Citation Rate:** {metrics['citation_rate']:.2%}\n")
        f.write(f"- **Avg Latency:** {metrics['avg_latency_ms']:.0f} ms\n\n")
        f.write(f"## Notes\n\n")
        f.write(f"- Model: Ollama Phi-4-mini (local)\n")
        f.write(f"- Mode: RAG-grounded Q&A\n")
        f.write(f"- Temperature: 0.1\n")
        f.write(f"- These are placeholder metrics - run with live model for real results\n")

    return results_json, metrics_json, report_md


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_cases_path = os.path.join(base_dir, 'test_cases', 'study_buddy_cases.csv')
    results_dir = os.path.join(base_dir, 'results')
    graphs_dir = os.path.join(base_dir, 'graphs')

    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(graphs_dir, exist_ok=True)

    print("=" * 60)
    print("STUDY BUDDY RAG EVALUATION")
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
    print(f"Evaluated:         {metrics['evaluated']}")
    print(f"Pending Model:     {metrics['pending_model_eval']}")

    print("\nSaving results...")
    results_json, metrics_json, report_md = save_results(results, metrics, results_dir)
    print(f"  Results: {results_json}")
    print(f"  Metrics: {metrics_json}")
    print(f"  Report: {report_md}")

    print(f"\n{'='*60}")
    print("NOTE: These are structural placeholders.")
    print("Run with live Ollama for actual RAG metrics.")
    print(f"{'='*60}")

    return 0


if __name__ == '__main__':
    sys.exit(main())