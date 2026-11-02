#!/usr/bin/env python3
"""
Sentiment Analyser Evaluation Script
Evaluates the DistilBERT sentiment classifier on test cases.
"""

import sys
import os
import json
import csv
import torch
import numpy as np
from datetime import datetime
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    classification_report, confusion_matrix
)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from app.services.sentiment_analyser import sentiment_analyser


def load_test_cases(csv_path):
    """Load test cases from CSV."""
    test_cases = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            test_cases.append(row)
    return test_cases


def run_evaluation(test_cases):
    """Run sentiment analyser on test cases."""
    results = []
    y_true = []
    y_pred = []
    confidences = []

    sentiment_to_idx = {"negative": 0, "neutral": 1, "positive": 2}
    idx_to_sentiment = {v: k for k, v in sentiment_to_idx.items()}

    for tc in test_cases:
        text = tc['input_text']
        expected = tc['expected_sentiment']

        result = sentiment_analyser.analyse(text)
        predicted = result.get('sentiment', 'neutral')
        confidence = result.get('confidence', 0.5)
        probabilities = result.get('probabilities', {})

        y_true.append(sentiment_to_idx.get(expected, 1))
        y_pred.append(sentiment_to_idx.get(predicted, 1))
        confidences.append(confidence)

        results.append({
            'test_case_id': tc['test_case_id'],
            'input': text,
            'expected': expected,
            'predicted': predicted,
            'confidence': round(confidence, 3),
            'probabilities': probabilities,
            'correct': expected == predicted,
            'category': tc['category'],
        })

        check = '[OK]' if expected == predicted else '[XX]'
        print(f"{tc['test_case_id']}: '{text[:60]}' -> Expected: {expected}, Predicted: {predicted} ({confidence:.2f}) {check}")

    return results, y_true, y_pred, confidences, idx_to_sentiment


def compute_metrics(y_true, y_pred, idx_to_sentiment):
    """Compute comprehensive metrics."""
    labels = [0, 1, 2]
    target_names = [idx_to_sentiment[i] for i in labels]

    metrics = {
        'accuracy': accuracy_score(y_true, y_pred),
        'macro_precision': precision_score(y_true, y_pred, average='macro', zero_division=0),
        'macro_recall': recall_score(y_true, y_pred, average='macro', zero_division=0),
        'macro_f1': f1_score(y_true, y_pred, average='macro', zero_division=0),
        'weighted_precision': precision_score(y_true, y_pred, average='weighted', zero_division=0),
        'weighted_recall': recall_score(y_true, y_pred, average='weighted', zero_division=0),
        'weighted_f1': f1_score(y_true, y_pred, average='weighted', zero_division=0),
        'per_class': {}
    }

    report = classification_report(y_true, y_pred, target_names=target_names, output_dict=True, zero_division=0)
    for cls in target_names:
        if cls in report:
            metrics['per_class'][cls] = {
                'precision': report[cls]['precision'],
                'recall': report[cls]['recall'],
                'f1': report[cls]['f1-score'],
                'support': report[cls]['support']
            }

    return metrics, report


def generate_confusion_matrix(y_true, y_pred, idx_to_sentiment, output_path):
    """Generate confusion matrix heatmap."""
    labels = [0, 1, 2]
    target_names = [idx_to_sentiment[i] for i in labels]

    cm = confusion_matrix(y_true, y_pred, labels=labels)

    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=target_names, yticklabels=target_names)
    plt.title('Sentiment Analysis Confusion Matrix')
    plt.xlabel('Predicted')
    plt.ylabel('Actual')
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

    return cm


def generate_confidence_distribution(confidences, y_true, y_pred, idx_to_sentiment, output_path):
    """Generate confidence distribution chart."""
    correct = [confidences[i] for i in range(len(confidences)) if y_true[i] == y_pred[i]]
    incorrect = [confidences[i] for i in range(len(confidences)) if y_true[i] != y_pred[i]]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Histogram for correct predictions
    axes[0].hist(correct, bins=15, color='#2ecc71', alpha=0.7, edgecolor='white')
    axes[0].set_xlabel('Confidence')
    axes[0].set_ylabel('Count')
    axes[0].set_title('Confidence Distribution (Correct Predictions)')
    axes[0].axvline(x=np.mean(correct), color='darkgreen', linestyle='--', label=f'Mean: {np.mean(correct):.3f}')
    axes[0].legend()

    # Histogram for incorrect predictions
    axes[1].hist(incorrect, bins=15, color='#e74c3c', alpha=0.7, edgecolor='white')
    axes[1].set_xlabel('Confidence')
    axes[1].set_ylabel('Count')
    axes[1].set_title('Confidence Distribution (Incorrect Predictions)')
    if incorrect:
        axes[1].axvline(x=np.mean(incorrect), color='darkred', linestyle='--', label=f'Mean: {np.mean(incorrect):.3f}')
        axes[1].legend()

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()


def save_results(results, metrics, output_dir):
    """Save all results to files."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Detailed results CSV
    results_csv = os.path.join(output_dir, f'sentiment_analysis_results_{timestamp}.csv')
    with open(results_csv, 'w', newline='') as f:
        fieldnames = results[0].keys() | {'probabilities'}
        writer = csv.DictWriter(f, fieldnames=list(fieldnames))
        writer.writeheader()
        for r in results:
            row = dict(r)
            row['probabilities'] = json.dumps(r.get('probabilities', {}))
            writer.writerow(row)

    # Metrics JSON
    metrics_json = os.path.join(output_dir, f'sentiment_analysis_metrics_{timestamp}.json')
    with open(metrics_json, 'w') as f:
        json.dump(metrics, f, indent=2)

    # Report MD
    report_md = os.path.join(output_dir, f'sentiment_analysis_report_{timestamp}.md')
    with open(report_md, 'w') as f:
        f.write(f"# Sentiment Analysis Evaluation Report\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## Overall Metrics\n\n")
        f.write(f"- **Accuracy:** {metrics['accuracy']:.4f}\n")
        f.write(f"- **Macro F1:** {metrics['macro_f1']:.4f}\n")
        f.write(f"- **Weighted F1:** {metrics['weighted_f1']:.4f}\n")
        f.write(f"- **Mean Confidence:** {np.mean([r['confidence'] for r in results]):.4f}\n\n")

        f.write(f"## Per-Class Performance\n\n")
        f.write(f"| Class | Precision | Recall | F1 | Support |\n")
        f.write(f"|-------|-----------|--------|----|---------|\n")
        for cls, vals in metrics['per_class'].items():
            f.write(f"| {cls} | {vals['precision']:.4f} | {vals['recall']:.4f} | {vals['f1']:.4f} | {vals['support']} |\n")

        f.write(f"\n## Test Case Summary\n\n")
        total = len(results)
        correct = sum(1 for r in results if r['correct'])
        f.write(f"- **Total Cases:** {total}\n")
        f.write(f"- **Correct:** {correct}\n")
        f.write(f"- **Accuracy:** {correct/total:.2%}\n\n")

        f.write(f"## Notes\n\n")
        f.write(f"- Model: DistilBERT fine-tuned checkpoint (268MB)\n")
        f.write(f"- Training data: Unknown (checkpoint only)\n")
        f.write(f"- 3-class: positive, neutral, negative\n")

    return results_csv, metrics_json, report_md


def main():
    """Main evaluation function."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_cases_path = os.path.join(base_dir, 'test_cases', 'sentiment_analysis_cases.csv')
    results_dir = os.path.join(base_dir, 'results')
    graphs_dir = os.path.join(base_dir, 'graphs')

    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(graphs_dir, exist_ok=True)

    print("=" * 60)
    print("SENTIMENT ANALYSIS EVALUATION")
    print("=" * 60)

    if not os.path.exists(test_cases_path):
        print(f"ERROR: Test cases not found at {test_cases_path}")
        return 1

    test_cases = load_test_cases(test_cases_path)
    print(f"Loaded {len(test_cases)} test cases")

    print("\nRunning predictions...")
    results, y_true, y_pred, confidences, idx_to_sentiment = run_evaluation(test_cases)

    print("\nComputing metrics...")
    metrics, report = compute_metrics(y_true, y_pred, idx_to_sentiment)

    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"Accuracy:          {metrics['accuracy']:.4f}")
    print(f"Macro F1:          {metrics['macro_f1']:.4f}")
    print(f"Weighted F1:       {metrics['weighted_f1']:.4f}")
    print(f"Mean Confidence:   {np.mean(confidences):.4f}")

    print("\nGenerating graphs...")
    cm_path = os.path.join(graphs_dir, 'sentiment_confusion_matrix.png')
    generate_confusion_matrix(y_true, y_pred, idx_to_sentiment, cm_path)
    print(f"  Confusion matrix: {cm_path}")

    conf_path = os.path.join(graphs_dir, 'sentiment_confidence_distribution.png')
    generate_confidence_distribution(confidences, y_true, y_pred, idx_to_sentiment, conf_path)
    print(f"  Confidence distribution: {conf_path}")

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