#!/usr/bin/env python3
"""
Phase 6 Evaluation for AI Chat Analyzer
Evaluates intent classification and sentiment analysis with ground-truth labels.
Computes accuracy, precision, recall, F1, and confusion matrices.
"""

import sys
import os
import json
import csv
import re
from datetime import datetime
from pathlib import Path
import numpy as np
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    classification_report, confusion_matrix
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

try:
    from app.services.intent_classifier import intent_classifier
    from app.services.sentiment_analyser import sentiment_analyser
    MODELS_LOADED = True
except ImportError as e:
    print(f"Warning: Could not import models: {e}")
    MODELS_LOADED = False


# ============================================================
# Ground-truth labels (manually verified from extended test cases)
# ============================================================
GROUND_TRUTH = {
    'TC_AI_001': {'intent': 'ask_exam_info', 'sentiment': 'neutral'},
    'TC_AI_002': {'intent': 'check_deadline', 'sentiment': 'neutral'},
    'TC_AI_003': {'intent': 'career_advice', 'sentiment': 'neutral'},
    'TC_AI_004': {'intent': 'career_advice', 'sentiment': 'neutral'},
    'TC_AI_005': {'intent': 'career_advice', 'sentiment': 'neutral'},
    'TC_AI_006': {'intent': 'other', 'sentiment': 'neutral'},
    'TC_AI_007': {'intent': 'other', 'sentiment': 'negative'},
    'TC_AI_008': {'intent': 'ask_exam_info', 'sentiment': 'neutral'},
    'TC_AI_009': {'intent': 'ask_doubt', 'sentiment': 'neutral'},
    'TC_AI_010': {'intent': 'career_advice', 'sentiment': 'neutral'},
    'TC_AI_011': {'intent': 'request_notes', 'sentiment': 'neutral'},
    'TC_AI_012': {'intent': 'ask_doubt', 'sentiment': 'neutral'},
    'TC_AI_013': {'intent': 'greet', 'sentiment': 'neutral'},
    'TC_AI_014': {'intent': 'ask_exam_info', 'sentiment': 'neutral'},
    'TC_AI_015': {'intent': 'check_deadline', 'sentiment': 'neutral'},
    'TC_AI_016': {'intent': 'check_deadline', 'sentiment': 'neutral'},
    'TC_AI_017': {'intent': 'career_advice', 'sentiment': 'neutral'},
    'TC_AI_018': {'intent': 'career_advice', 'sentiment': 'neutral'},
    'TC_AI_019': {'intent': 'feedback', 'sentiment': 'positive'},
    'TC_AI_020': {'intent': 'feedback', 'sentiment': 'negative'},
    'TC_AI_021': {'intent': 'career_advice', 'sentiment': 'neutral'},
    'TC_AI_022': {'intent': 'request_notes', 'sentiment': 'neutral'},
    'TC_AI_023': {'intent': 'ask_exam_info', 'sentiment': 'neutral'},
    'TC_AI_024': {'intent': 'request_notes', 'sentiment': 'neutral'},
    'TC_AI_025': {'intent': 'ask_exam_info', 'sentiment': 'neutral'},
    'TC_AI_026': {'intent': 'ask_doubt', 'sentiment': 'neutral'},
    'TC_AI_027': {'intent': 'career_advice', 'sentiment': 'neutral'},
    'TC_AI_028': {'intent': 'ask_exam_info', 'sentiment': 'neutral'},
    'TC_AI_029': {'intent': 'career_advice', 'sentiment': 'neutral'},
    'TC_AI_030': {'intent': 'request_notes', 'sentiment': 'neutral'},
    'TC_AI_031': {'intent': 'greet', 'sentiment': 'neutral'},
    'TC_AI_032': {'intent': 'greet', 'sentiment': 'neutral'},
    'TC_AI_033': {'intent': 'ask_exam_info', 'sentiment': 'neutral'},
    'TC_AI_034': {'intent': 'career_advice', 'sentiment': 'neutral'},
    'TC_AI_035': {'intent': 'ask_doubt', 'sentiment': 'negative'},
    'TC_AI_036': {'intent': 'career_advice', 'sentiment': 'neutral'},
    'TC_AI_037': {'intent': 'ask_exam_info', 'sentiment': 'neutral'},
    'TC_AI_038': {'intent': 'other', 'sentiment': 'neutral'},
    'TC_AI_039': {'intent': 'ask_exam_info', 'sentiment': 'neutral'},
    'TC_AI_040': {'intent': 'ask_doubt', 'sentiment': 'neutral'},
    'TC_AI_041': {'intent': 'career_advice', 'sentiment': 'neutral'},
    'TC_AI_042': {'intent': 'feedback', 'sentiment': 'negative'},
    'TC_AI_043': {'intent': 'feedback', 'sentiment': 'positive'},
    'TC_AI_044': {'intent': 'check_deadline', 'sentiment': 'neutral'},
    'TC_AI_045': {'intent': 'request_notes', 'sentiment': 'neutral'},
    'TC_AI_046': {'intent': 'check_deadline', 'sentiment': 'neutral'},
    'TC_AI_047': {'intent': 'career_advice', 'sentiment': 'neutral'},
    'TC_AI_048': {'intent': 'ask_doubt', 'sentiment': 'negative'},
    'TC_AI_049': {'intent': 'ask_doubt', 'sentiment': 'neutral'},
    'TC_AI_050': {'intent': 'career_advice', 'sentiment': 'neutral'},
    'TC_AI_051': {'intent': 'check_deadline', 'sentiment': 'neutral'},
    'TC_AI_052': {'intent': 'career_advice', 'sentiment': 'neutral'},
    'TC_AI_053': {'intent': 'ask_exam_info', 'sentiment': 'neutral'},
    'TC_AI_054': {'intent': 'ask_exam_info', 'sentiment': 'neutral'},
    'TC_AI_055': {'intent': 'request_notes', 'sentiment': 'neutral'},
}


def load_test_cases(csv_path):
    """Load test cases from CSV."""
    test_cases = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            test_cases.append(row)
    return test_cases


def run_evaluation(test_cases):
    """Run AI Chat Analyzer on test cases and compare against ground truth."""
    results = []

    for tc in test_cases:
        tc_id = tc['test_case_id']
        query = tc['input_query']
        gt = GROUND_TRUTH.get(tc_id, {})

        if not MODELS_LOADED:
            results.append({
                'test_case_id': tc_id,
                'query': query[:80],
                'status': 'SKIPPED_MODELS_NOT_LOADED',
                'intent_prediction': None,
                'intent_confidence': None,
                'intent_correct': None,
                'sentiment_prediction': None,
                'sentiment_confidence': None,
                'sentiment_correct': None,
            })
            continue

        # Run intent classifier
        intent_result = intent_classifier.predict(query)
        predicted_intent = intent_result.get('intent', 'other')
        intent_confidence = intent_result.get('confidence', 0.0)

        # Run sentiment analyzer
        sentiment_result = sentiment_analyser.analyse(query)
        predicted_sentiment = sentiment_result.get('sentiment', 'neutral')
        sentiment_confidence = sentiment_result.get('confidence', 0.0)

        # Compare with ground truth
        expected_intent = gt.get('intent', 'other')
        expected_sentiment = gt.get('sentiment', 'neutral')

        intent_correct = (predicted_intent == expected_intent)
        sentiment_correct = (predicted_sentiment == expected_sentiment)

        results.append({
            'test_case_id': tc_id,
            'query': query[:80],
            'status': 'EVALUATED',
            'intent_prediction': predicted_intent,
            'intent_confidence': intent_confidence,
            'intent_expected': expected_intent,
            'intent_correct': intent_correct,
            'sentiment_prediction': predicted_sentiment,
            'sentiment_confidence': sentiment_confidence,
            'sentiment_expected': expected_sentiment,
            'sentiment_correct': sentiment_correct,
            'category': tc.get('category', ''),
        })

        status_str = '[OK]' if (intent_correct and sentiment_correct) else '[PARTIAL]'
        print(f"{tc_id}: intent={predicted_intent}({intent_correct}) sent={predicted_sentiment}({sentiment_correct}) {status_str}")

    return results


def compute_metrics(results):
    """Compute aggregate metrics."""
    evaluated = [r for r in results if r['status'] == 'EVALUATED']

    if not evaluated:
        return {
            'total_cases': len(results),
            'evaluated': 0,
            'intent_accuracy': 0.0,
            'sentiment_accuracy': 0.0,
            'intent_classification_report': '',
            'sentiment_classification_report': '',
            'intent_confusion_matrix': [],
            'sentiment_confusion_matrix': [],
            'avg_intent_confidence': 0.0,
            'avg_sentiment_confidence': 0.0,
        }

    # Intent metrics
    intent_true = [r['intent_expected'] for r in evaluated]
    intent_pred = [r['intent_prediction'] for r in evaluated]
    intent_correct_count = sum(1 for t, p in zip(intent_true, intent_pred) if t == p)
    intent_accuracy = intent_correct_count / len(evaluated) if evaluated else 0.0

    # Sentiment metrics
    sent_true = [r['sentiment_expected'] for r in evaluated]
    sent_pred = [r['sentiment_prediction'] for r in evaluated]
    sent_correct_count = sum(1 for t, p in zip(sent_true, sent_pred) if t == p)
    sent_accuracy = sent_correct_count / len(evaluated) if evaluated else 0.0

    # Classification reports
    intent_report = classification_report(intent_true, intent_pred, digits=4, zero_division=0)
    sent_report = classification_report(sent_true, sent_pred, digits=4, zero_division=0)

    # Confusion matrices
    all_intent_labels = sorted(set(intent_true) | set(intent_pred))
    all_sent_labels = sorted(set(sent_true) | set(sent_pred))

    intent_cm = confusion_matrix(intent_true, intent_pred, labels=all_intent_labels)
    sent_cm = confusion_matrix(sent_true, sent_pred, labels=all_sent_labels)

    # Average confidences
    avg_intent_conf = np.mean([r['intent_confidence'] for r in evaluated if r['intent_confidence'] is not None]) if evaluated else 0.0
    avg_sent_conf = np.mean([r['sentiment_confidence'] for r in evaluated if r['sentiment_confidence'] is not None]) if evaluated else 0.0

    # Macro F1
    intent_macro_f1 = f1_score(intent_true, intent_pred, average='macro', zero_division=0)
    sent_macro_f1 = f1_score(sent_true, sent_pred, average='macro', zero_division=0)

    # Weighted F1
    intent_weighted_f1 = f1_score(intent_true, intent_pred, average='weighted', zero_division=0)
    sent_weighted_f1 = f1_score(sent_true, sent_pred, average='weighted', zero_division=0)

    return {
        'total_cases': len(results),
        'evaluated': len(evaluated),
        'intent_accuracy': intent_accuracy,
        'intent_macro_f1': intent_macro_f1,
        'intent_weighted_f1': intent_weighted_f1,
        'intent_avg_confidence': avg_intent_conf,
        'sentiment_accuracy': sent_accuracy,
        'sentiment_macro_f1': sent_macro_f1,
        'sentiment_weighted_f1': sent_weighted_f1,
        'sentiment_avg_confidence': avg_sent_conf,
        'intent_classification_report': intent_report,
        'sentiment_classification_report': sent_report,
        'intent_confusion_matrix': intent_cm.tolist(),
        'sentiment_confusion_matrix': sent_cm.tolist(),
        'intent_labels': all_intent_labels,
        'sentiment_labels': all_sent_labels,
        'per_case_results': evaluated,
    }


def main():
    """Main evaluation entry point."""
    print("=" * 70)
    print("AI CHAT ANALYZER EVALUATION (PHASE 6 - GROUNDED)")
    print("=" * 70)
    print()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Prefer extended dataset, fall back to original
    test_cases_path = os.path.join(base_dir, 'test_cases', 'ai_chat_analyzer_extended_test_cases.csv')
    if not os.path.exists(test_cases_path):
        test_cases_path = os.path.join(base_dir, 'test_cases', 'ai_chat_analyzer_cases.csv')
    results_dir = os.path.join(base_dir, 'results')
    os.makedirs(results_dir, exist_ok=True)

    if not os.path.exists(test_cases_path):
        print(f"ERROR: Test cases not found at {test_cases_path}")
        return 1

    test_cases = load_test_cases(test_cases_path)
    print(f"Loaded {len(test_cases)} test cases")
    print()

    print("Running evaluation...")
    print("-" * 70)
    results = run_evaluation(test_cases)
    print()

    print("Computing metrics...")
    metrics = compute_metrics(results)
    print()

    print("=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)
    print()
    print(f"Total Cases:         {metrics['total_cases']}")
    print(f"Evaluated:           {metrics['evaluated']}")
    print()
    print("Intent Classification:")
    print(f"  Accuracy:          {metrics['intent_accuracy']*100:.2f}%")
    print(f"  Macro F1:          {metrics['intent_macro_f1']*100:.2f}%")
    print(f"  Weighted F1:       {metrics['intent_weighted_f1']*100:.2f}%")
    print(f"  Avg Confidence:    {metrics['intent_avg_confidence']*100:.2f}%")
    print()
    print("Sentiment Analysis:")
    print(f"  Accuracy:          {metrics['sentiment_accuracy']*100:.2f}%")
    print(f"  Macro F1:          {metrics['sentiment_macro_f1']*100:.2f}%")
    print(f"  Weighted F1:       {metrics['sentiment_weighted_f1']*100:.2f}%")
    print(f"  Avg Confidence:    {metrics['sentiment_avg_confidence']*100:.2f}%")
    print()

    print("Intent Classification Report:")
    print(metrics['intent_classification_report'])
    print("Sentiment Classification Report:")
    print(metrics['sentiment_classification_report'])

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    results_file = os.path.join(results_dir, f'ai_chat_analyzer_results_v2_{timestamp}.json')
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=2, default=str)

    metrics_file = os.path.join(results_dir, f'ai_chat_analyzer_metrics_v2_{timestamp}.json')
    with open(metrics_file, 'w', encoding='utf-8') as f:
        json.dump({
            'total_cases': metrics['total_cases'],
            'evaluated': metrics['evaluated'],
            'intent_accuracy': metrics['intent_accuracy'],
            'intent_macro_f1': metrics['intent_macro_f1'],
            'intent_weighted_f1': metrics['intent_weighted_f1'],
            'sentiment_accuracy': metrics['sentiment_accuracy'],
            'sentiment_macro_f1': metrics['sentiment_macro_f1'],
            'sentiment_weighted_f1': metrics['sentiment_weighted_f1'],
        }, f, indent=2)

    report_file = os.path.join(results_dir, f'ai_chat_analyzer_report_v2_{timestamp}.md')
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("# AI Chat Analyzer Evaluation Report (Phase 6)\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Summary\n\n")
        f.write(f"- **Total Test Cases:** {metrics['total_cases']}\n")
        f.write(f"- **Evaluated:** {metrics['evaluated']}\n")
        f.write(f"- **Intent Accuracy:** {metrics['intent_accuracy']*100:.2f}%\n")
        f.write(f"- **Intent Macro F1:** {metrics['intent_macro_f1']*100:.2f}%\n")
        f.write(f"- **Sentiment Accuracy:** {metrics['sentiment_accuracy']*100:.2f}%\n\n")
        f.write("## Intent Classification Report\n\n")
        f.write("```\n")
        f.write(metrics['intent_classification_report'])
        f.write("```\n\n")
        f.write("## Sentiment Classification Report\n\n")
        f.write("```\n")
        f.write(metrics['sentiment_classification_report'])
        f.write("```\n\n")
        f.write("## Per-Case Results\n\n")
        f.write("| Test Case | Intent (Pred/Exp) | Sentiment (Pred/Exp) | Status |\n")
        f.write("|-----------|-------------------|----------------------|--------|\n")
        for r in metrics['per_case_results']:
            intent_status = '✓' if r['intent_correct'] else '✗'
            sent_status = '✓' if r['sentiment_correct'] else '✗'
            overall = 'PASS' if (r['intent_correct'] and r['sentiment_correct']) else 'FAIL'
            f.write(f"| {r['test_case_id']} | {r['intent_prediction']}/{r['intent_expected']} {intent_status} | {r['sentiment_prediction']}/{r['sentiment_expected']} {sent_status} | {overall} |\n")

    print(f"  Saved: {results_file}")
    print(f"  Saved: {metrics_file}")
    print(f"  Saved: {report_file}")
    print()
    print("=" * 70)
    print("EVALUATION COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    sys.exit(main())
