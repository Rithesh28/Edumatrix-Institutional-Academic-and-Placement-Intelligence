"""
Evaluation script for Table Recognition Model.

Usage:
    python -m app.ml.table_recognition.evaluate --checkpoint <path>

Options:
    --checkpoint    Path to model checkpoint (required)
    --batch_size    Batch size for evaluation (optional)
    --debug         Run in debug mode
"""

import os
import sys
import argparse
import torch
from torch.utils.data import DataLoader, Subset
import json
import numpy as np
from tqdm import tqdm

# Add parent directory to path
sys.path.append('/app')

from app.ml.table_recognition.config import config
from app.ml.table_recognition.model import TableRecognitionModel
from app.ml.table_recognition.dataset import TableRecognitionDataset, collate_fn
from app.ml.table_recognition.model_utils import TableRecognitionMetrics, get_logger

logger = get_logger(__name__)


def evaluate_model(
    model: TableRecognitionModel,
    test_loader: DataLoader,
    device: torch.device,
) -> dict:
    """
    Evaluate model on test set.
    
    Returns:
        Dictionary of metrics
    """
    model.eval()
    model.to(device)
    
    # Initialize metrics
    metrics = TableRecognitionMetrics()
    loss_total = 0.0
    correct_table = 0
    total_samples = 0
    
    logger.info("Running evaluation...")
    
    with torch.no_grad():
        pbar = tqdm(test_loader, desc="Evaluating")
        
        for batch in pbar:
            # Move data to device
            images = batch['images'].to(device)
            
            # Forward pass
            outputs = model(images)
            
            # Table detection accuracy
            pred_table = torch.argmax(outputs['table_detection'], dim=1)
            # Dummy target for testing
            target_table = torch.zeros(images.size(0), dtype=torch.long).to(device)
            
            correct_table += (pred_table == target_table).sum().item()
            total_samples += images.size(0)
            
            # Update progress bar
            pbar.set_postfix({
                'acc': f"{correct_table/total_samples:.4f}",
            })
    
    # Calculate metrics
    table_accuracy = correct_table / total_samples if total_samples > 0 else 0.0
    
    metrics = {
        'table_accuracy': table_accuracy,
        'total_samples': total_samples,
    }
    
    return metrics


def create_test_loader(debug: bool = False):
    """Create dataloader for test set."""
    logger.info("Creating test dataloader...")
    
    test_dataset = TableRecognitionDataset(
        data_dir=config.paths.DATA_DIR,
        split='test',
        target_size=config.dataset.IMAGE_SIZE,
        use_all_styles=config.dataset.USE_ALL_STYLES,
    )
    
    if debug:
        logger.warning("⚠️ Running in debug mode with small dataset")
        test_dataset = Subset(test_dataset, range(min(50, len(test_dataset))))
    
    test_loader = DataLoader(
        test_dataset,
        batch_size=config.dataset.BATCH_SIZE,
        shuffle=False,
        num_workers=config.dataset.NUM_WORKERS,
        collate_fn=collate_fn,
        pin_memory=True,
    )
    
    logger.info(f"Test samples: {len(test_dataset)}")
    logger.info(f"Test batches: {len(test_loader)}")
    
    return test_loader


def main():
    """Main evaluation function."""
    parser = argparse.ArgumentParser(description='Evaluate Table Recognition Model')
    parser.add_argument('--checkpoint', type=str, required=True, help='Path to model checkpoint')
    parser.add_argument('--batch_size', type=int, default=16, help='Batch size for evaluation')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    args = parser.parse_args()
    
    # Get device
    device = config.device.get_device()
    logger.info(f"Device: {device}")
    
    # Create model
    logger.info("Creating model...")
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
    
    # Load checkpoint
    logger.info(f"Loading checkpoint: {args.checkpoint}")
    checkpoint = torch.load(args.checkpoint, map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    logger.info(f"Loaded checkpoint from epoch {checkpoint['epoch'] + 1}")
    
    # Update batch size if provided
    if args.batch_size:
        config.dataset.BATCH_SIZE = args.batch_size
    
    # Create test loader
    test_loader = create_test_loader(debug=args.debug)
    
    # Evaluate
    metrics = evaluate_model(
        model=model,
        test_loader=test_loader,
        device=device,
    )
    
    # Print results
    logger.info("\n" + "="*50)
    logger.info("Evaluation Results")
    logger.info("="*50)
    for key, value in metrics.items():
        if isinstance(value, float):
            logger.info(f"  {key}: {value:.4f}")
        else:
            logger.info(f"  {key}: {value}")
    logger.info("="*50)
    
    # Save results
    results_path = os.path.join(config.paths.LOGS_DIR, 'eval_results.json')
    with open(results_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    logger.info(f"Results saved to: {results_path}")


if __name__ == "__main__":
    main()