#!/usr/bin/env python3
"""
Intent Classifier Evaluation Script
Evaluates the SBERT + Logistic Regression intent classifier on test cases.
"""

import sys
import os
import json
import csv
import numpy as np
from datetime import datetime
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    classification_report, confusion_matrix, ConfusionMatrixDisplay
)
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from app.services.intent_classifier import intent_classifier


def load_test_cases(csv_path):
    """Load test cases from CSV."""
    test_cases = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            test_cases.append(row)
    return test_cases


def run_evaluation(test_cases):
    """Run intent classifier on test cases."""
    results = []
    y_true = []
    y_pred = []
    confidences = []

    intent_to_idx = {
        "ask_doubt": 0, "greet": 1, "request_notes": 2, "check_deadline": 3,
        "ask_exam_info": 4, "career_advice": 5, "feedback": 6, "other": 7
    }
    idx_to_intent = {v: k for k, v in intent_to_idx.items()}

    for tc in test_cases:
        text = tc['input_text']
        expected = tc['expected_intent']

        # Get prediction
        pred_result = intent_classifier.predict(text)
        predicted = pred_result.get('intent', 'other')
        confidence = pred_result.get('confidence', 0.0)

        y_true.append(intent_to_idx.get(expected, 7))
        y_pred.append(intent_to_idx.get(predicted, 7))
        confidences.append(confidence)

        results.append({
            'test_case_id': tc['test_case_id'],
            'input': text,
            'expected': expected,
            'predicted': predicted,
            'confidence': round(confidence, 3),
            'correct': expected == predicted,
            'category': tc['category'],
            'notes': tc.get('notes', '')
        })

        checkmark = '[OK]' if expected == predicted else '[XX]'
        print(f"{tc['test_case_id']}: '{text[:50]}' -> Expected: {expected}, Predicted: {predicted} ({confidence:.2f}) {checkmark}")

    return results, y_true, y_pred, confidences, idx_to_intent


def compute_metrics(y_true, y_pred, idx_to_intent):
    """Compute comprehensive metrics."""
    labels = list(range(8))
    target_names = [idx_to_intent[i] for i in labels]

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

    # Per-class metrics
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


def generate_confusion_matrix(y_true, y_pred, idx_to_intent, output_path):
    """Generate and save confusion matrix heatmap."""
    labels = list(range(8))
    target_names = [idx_to_intent[i] for i in labels]

    cm = confusion_matrix(y_true, y_pred, labels=labels)

    plt.figure(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=target_names, yticklabels=target_names)
    plt.title('Intent Classification Confusion Matrix')
    plt.xlabel('Predicted')
    plt.ylabel('Actual')
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

    return cm


def generate_per_class_chart(metrics, output_path):
    """Generate per-class precision/recall/F1 chart."""
    classes = list(metrics['per_class'].keys())
    precision = [metrics['per_class'][c]['precision'] for c in classes]
    recall = [metrics['per_class'][c]['recall'] for c in classes]
    f1 = [metrics['per_class'][c]['f1'] for c in classes]

    x = np.arange(len(classes))
    width = 0.25

    fig, ax = plt.subplots(figsize=(12, 6))
    bars1 = ax.bar(x - width, precision, width, label='Precision', color='#2ecc71', alpha=0.8)
    bars2 = ax.bar(x, recall, width, label='Recall', color='#3498db', alpha=0.8)
    bars3 = ax.bar(x + width, f1, width, label='F1-Score', color='#e74c3c', alpha=0.8)

    ax.set_xlabel('Intent Class')
    ax.set_ylabel('Score')
    ax.set_title('Per-Class Precision, Recall, and F1-Score')
    ax.set_xticks(x)
    ax.set_xticklabels(classes, rotation=45, ha='right')
    ax.legend()
    ax.set_ylim(0, 1.1)

    # Add value labels on bars
    for bars in [bars1, bars2, bars3]:
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height:.2f}',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3), textcoords="offset points",
                       ha='center', va='bottom', fontsize=8)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()


def generate_category_analysis(results, output_path):
    """Generate accuracy by test category chart."""
    categories = {}
    for r in results:
        cat = r['category']
        if cat not in categories:
            categories[cat] = {'correct': 0, 'total': 0}
        categories[cat]['total'] += 1
        if r['correct']:
            categories[cat]['correct'] += 1

    cat_names = list(categories.keys())
    accuracies = [categories[c]['correct'] / categories[c]['total'] for c in cat_names]
    totals = [categories[c]['total'] for c in cat_names]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(cat_names, accuracies, color='#9b59b6', alpha=0.8)

    ax.set_xlabel('Test Category')
    ax.set_ylabel('Accuracy')
    ax.set_title('Accuracy by Test Category')
    ax.set_ylim(0, 1.1)
    plt.xticks(rotation=45, ha='right')

    for i, (bar, total) in enumerate(zip(bars, totals)):
        height = bar.get_height()
        ax.annotate(f'{height:.2f} (n={total})',
                   xy=(bar.get_x() + bar.get_width() / 2, height),
                   xytext=(0, 3), textcoords="offset points",
                   ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()


def save_results(results, metrics, output_dir):
    """Save all results to files."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Detailed results CSV
    results_csv = os.path.join(output_dir, f'intent_classification_results_{timestamp}.csv')
    with open(results_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    # Metrics JSON
    metrics_json = os.path.join(output_dir, f'intent_classification_metrics_{timestamp}.json')
    with open(metrics_json, 'w') as f:
        json.dump(metrics, f, indent=2)

    # Summary report
    report_md = os.path.join(output_dir, f'intent_classification_report_{timestamp}.md')
    with open(report_md, 'w') as f:
        f.write(f"# Intent Classifier Evaluation Report\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## Overall Metrics\n\n")
        f.write(f"- **Accuracy:** {metrics['accuracy']:.4f}\n")
        f.write(f"- **Macro Precision:** {metrics['macro_precision']:.4f}\n")
        f.write(f"- **Macro Recall:** {metrics['macro_recall']:.4f}\n")
        f.write(f"- **Macro F1:** {metrics['macro_f1']:.4f}\n")
        f.write(f"- **Weighted Precision:** {metrics['weighted_precision']:.4f}\n")
        f.write(f"- **Weighted Recall:** {metrics['weighted_recall']:.4f}\n")
        f.write(f"- **Weighted F1:** {metrics['weighted_f1']:.4f}\n\n")

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

        f.write(f"## By Category\n\n")
        categories = {}
        for r in results:
            cat = r['category']
            if cat not in categories:
                categories[cat] = {'correct': 0, 'total': 0}
            categories[cat]['total'] += 1
            if r['correct']:
                categories[cat]['correct'] += 1

        f.write(f"| Category | Correct | Total | Accuracy |\n")
        f.write(f"|----------|---------|-------|----------|\n")
        for cat, vals in categories.items():
            f.write(f"| {cat} | {vals['correct']} | {vals['total']} | {vals['correct']/vals['total']:.2%} |\n")

    return results_csv, metrics_json, report_md


def main():
    """Main evaluation function."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_cases_path = os.path.join(base_dir, 'test_cases', 'intent_classification_cases.csv')
    results_dir = os.path.join(base_dir, 'results')
    graphs_dir = os.path.join(base_dir, 'graphs')

    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(graphs_dir, exist_ok=True)

    print("=" * 60)
    print("INTENT CLASSIFIER EVALUATION")
    print("=" * 60)

    # Load test cases
    if not os.path.exists(test_cases_path):
        print(f"ERROR: Test cases not found at {test_cases_path}")
        return 1

    test_cases = load_test_cases(test_cases_path)
    print(f"Loaded {len(test_cases)} test cases")

    # Run evaluation
    print("\nRunning predictions...")
    results, y_true, y_pred, confidences, idx_to_intent = run_evaluation(test_cases)

    # Compute metrics
    print("\nComputing metrics...")
    metrics, report = compute_metrics(y_true, y_pred, idx_to_intent)

    # Print summary
    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"Accuracy:          {metrics['accuracy']:.4f}")
    print(f"Macro F1:          {metrics['macro_f1']:.4f}")
    print(f"Weighted F1:       {metrics['weighted_f1']:.4f}")
    print(f"Mean Confidence:   {np.mean(confidences):.4f}")

    # Generate visualizations
    print("\nGenerating graphs...")
    cm_path = os.path.join(graphs_dir, 'intent_confusion_matrix.png')
    generate_confusion_matrix(y_true, y_pred, idx_to_intent, cm_path)
    print(f"  Confusion matrix: {cm_path}")

    per_class_path = os.path.join(graphs_dir, 'intent_per_class_metrics.png')
    generate_per_class_chart(metrics, per_class_path)
    print(f"  Per-class metrics: {per_class_path}")

    cat_path = os.path.join(graphs_dir, 'intent_category_accuracy.png')
    generate_category_analysis(results, cat_path)
    print(f"  Category accuracy: {cat_path}")

    # Save results
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