#!/usr/bin/env python3
"""
Table Recognition Model Evaluation Script
Evaluates the custom CNN+Transformer table recognition model.
"""

import sys
import os
import json
import torch
import numpy as np
from datetime import datetime
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from app.ml.table_recognition.config import config
from app.ml.table_recognition.model import TableRecognitionModel
from app.ml.table_recognition.dataset import TableRecognitionDataset, collate_fn
from app.ml.table_recognition.model_utils import TableRecognitionMetrics, get_logger
from torch.utils.data import DataLoader, Subset

logger = get_logger(__name__)


def load_model(checkpoint_path, device):
    """Load trained model from checkpoint."""
    model = TableRecognitionModel(
        backbone_name=config.model.CNN_BACKBONE,
        pretrained=False,
        freeze_backbone=False,
        transformer_layers=config.model.TRANSFORMER_LAYERS,
        attention_heads=config.model.ATTENTION_HEADS,
        hidden_dim=config.model.HIDDEN_DIM,
        ffn_dim=config.model.FFN_DIM,
        dropout=config.model.DROPOUT,
        max_rows=config.model.MAX_ROWS,
        max_cols=config.model.MAX_COLS,
    )

    checkpoint = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.to(device)
    model.eval()

    epoch = checkpoint.get('epoch', 'unknown')
    print(f"Loaded model from epoch {epoch + 1}")

    return model, epoch


def evaluate_model(model, test_loader, device):
    """Evaluate model on test set."""
    model.eval()

    metrics_calculator = TableRecognitionMetrics()
    all_preds = []
    all_targets = []
    losses = []

    print("Running evaluation...")
    with torch.no_grad():
        for batch in test_loader:
            images = batch['images'].to(device)

            # Forward pass
            outputs = model(images)

            # Table detection predictions
            pred_table = torch.argmax(outputs['table_detection'], dim=1)

            # For evaluation, we need actual targets from dataset
            # The dataset should provide targets; here we use what's available
            if 'table_detection_target' in batch:
                target_table = batch['table_detection_target'].to(device)
            else:
                # Fallback: create dummy targets (this needs proper dataset implementation)
                target_table = torch.zeros(images.size(0), dtype=torch.long).to(device)

            all_preds.extend(pred_table.cpu().numpy())
            all_targets.extend(target_table.cpu().numpy())

    # Compute metrics
    accuracy = accuracy_score(all_targets, all_preds)

    # Per-class metrics
    report = classification_report(all_targets, all_preds,
                                   target_names=['No Table', 'Table'],
                                   output_dict=True, zero_division=0)

    cm = confusion_matrix(all_targets, all_preds)

    return {
        'accuracy': accuracy,
        'per_class': report,
        'confusion_matrix': cm.tolist(),
        'total_samples': len(all_targets)
    }, all_preds, all_targets


def generate_confusion_matrix(cm, output_path):
    """Generate confusion matrix heatmap."""
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=['No Table', 'Table'],
                yticklabels=['No Table', 'Table'])
    plt.title('Table Detection Confusion Matrix')
    plt.xlabel('Predicted')
    plt.ylabel('Actual')
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()


def generate_metrics_chart(metrics, output_path):
    """Generate per-class metrics chart."""
    classes = ['No Table', 'Table']
    precision = [metrics['per_class'][c]['precision'] for c in classes]
    recall = [metrics['per_class'][c]['recall'] for c in classes]
    f1 = [metrics['per_class'][c]['f1-score'] for c in classes]

    x = np.arange(len(classes))
    width = 0.25

    fig, ax = plt.subplots(figsize=(10, 6))
    bars1 = ax.bar(x - width, precision, width, label='Precision', color='#2ecc71', alpha=0.8)
    bars2 = ax.bar(x, recall, width, label='Recall', color='#3498db', alpha=0.8)
    bars3 = ax.bar(x + width, f1, width, label='F1-Score', color='#e74c3c', alpha=0.8)

    ax.set_xlabel('Class')
    ax.set_ylabel('Score')
    ax.set_title('Table Detection Per-Class Metrics')
    ax.set_xticks(x)
    ax.set_xticklabels(classes)
    ax.legend()
    ax.set_ylim(0, 1.1)

    for bars in [bars1, bars2, bars3]:
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height:.3f}',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3), textcoords="offset points",
                       ha='center', va='bottom', fontsize=10)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()


def save_results(metrics, epoch, output_dir):
    """Save evaluation results."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Metrics JSON
    metrics_json = os.path.join(output_dir, f'table_recognition_metrics_{timestamp}.json')
    with open(metrics_json, 'w') as f:
        json.dump({
            'epoch': epoch,
            'timestamp': timestamp,
            'metrics': metrics
        }, f, indent=2)

    # Report MD
    report_md = os.path.join(output_dir, f'table_recognition_report_{timestamp}.md')
    with open(report_md, 'w') as f:
        f.write(f"# Table Recognition Model Evaluation Report\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Model Epoch:** {epoch}\n")
        f.write(f"**Configuration:** {config.model.CNN_BACKBONE} + {config.model.TRANSFORMER_LAYERS}-layer Transformer\n\n")

        f.write(f"## Overall Metrics\n\n")
        f.write(f"- **Accuracy:** {metrics['accuracy']:.4f}\n")
        f.write(f"- **Total Test Samples:** {metrics['total_samples']}\n\n")

        f.write(f"## Per-Class Performance\n\n")
        f.write(f"| Class | Precision | Recall | F1-Score | Support |\n")
        f.write(f"|-------|-----------|--------|----------|---------|\n")
        for cls in ['No Table', 'Table']:
            m = metrics['per_class'][cls]
            f.write(f"| {cls} | {m['precision']:.4f} | {m['recall']:.4f} | {m['f1-score']:.4f} | {m['support']} |\n")

        f.write(f"\n## Confusion Matrix\n\n")
        cm = metrics['confusion_matrix']
        f.write(f"| | Predicted: No Table | Predicted: Table |\n")
        f.write(f"|---|---|---|\n")
        f.write(f"| Actual: No Table | {cm[0][0]} | {cm[0][1]} |\n")
        f.write(f"| Actual: Table | {cm[1][0]} | {cm[1][1]} |\n")

        f.write(f"\n## Notes\n\n")
        f.write(f"- Model trained in **debug mode** with only 100 train / 20 val samples\n")
        f.write(f"- Only **3 epochs** completed (config: 20 epochs)\n")
        f.write(f"- **NOT production-ready** - needs full dataset training\n")
        f.write(f"- Evaluation uses dummy targets; real evaluation needs proper test set\n")

    return metrics_json, report_md


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    checkpoint_path = os.path.join(base_dir, '..', '..', 'backend', 'app', 'ml', 'table_recognition', 'weights', 'best_model.pth')
    results_dir = os.path.join(base_dir, 'results')
    graphs_dir = os.path.join(base_dir, 'graphs')

    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(graphs_dir, exist_ok=True)

    print("=" * 60)
    print("TABLE RECOGNITION MODEL EVALUATION")
    print("=" * 60)

    if not os.path.exists(checkpoint_path):
        print(f"ERROR: Checkpoint not found at {checkpoint_path}")
        return 1

    device = config.device.get_device()
    print(f"Device: {device}")

    # Load model
    model, epoch = load_model(checkpoint_path, device)

    # Create test loader (using validation split as test since no separate test)
    print("Creating test dataloader...")
    test_dataset = TableRecognitionDataset(
        data_dir=config.paths.DATA_DIR,
        split='val',  # Use validation as test (no separate test in debug)
        target_size=config.dataset.IMAGE_SIZE,
        use_all_styles=config.dataset.USE_ALL_STYLES,
    )

    # In debug mode, dataset is small
    if len(test_dataset) > 50:
        test_dataset = Subset(test_dataset, range(50))

    test_loader = DataLoader(
        test_dataset,
        batch_size=config.dataset.BATCH_SIZE,
        shuffle=False,
        num_workers=config.dataset.NUM_WORKERS,
        collate_fn=collate_fn,
        pin_memory=True,
    )

    print(f"Test samples: {len(test_dataset)}")
    print(f"Test batches: {len(test_loader)}")

    # Evaluate
    metrics, preds, targets = evaluate_model(model, test_loader, device)

    # Print summary
    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"Accuracy: {metrics['accuracy']:.4f}")
    print(f"Total Samples: {metrics['total_samples']}")

    # Generate visualizations
    print("\nGenerating graphs...")
    cm_path = os.path.join(graphs_dir, 'table_recognition_confusion_matrix.png')
    generate_confusion_matrix(np.array(metrics['confusion_matrix']), cm_path)
    print(f"  Confusion matrix: {cm_path}")

    metrics_path = os.path.join(graphs_dir, 'table_recognition_metrics.png')
    generate_metrics_chart(metrics, metrics_path)
    print(f"  Metrics chart: {metrics_path}")

    # Save results
    print("\nSaving results...")
    metrics_json, report_md = save_results(metrics, epoch, results_dir)
    print(f"  Metrics JSON: {metrics_json}")
    print(f"  Report MD: {report_md}")

    print(f"\n{'='*60}")
    print("EVALUATION COMPLETE")
    print(f"{'='*60}")
    print("WARNING: This was a DEBUG evaluation with minimal data.")
    print("Full training and evaluation on complete TabRecSet is required.")

    return 0


if __name__ == '__main__':
    sys.exit(main())