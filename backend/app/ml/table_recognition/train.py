"""
Training script for Table Recognition Model.

Usage:
    python -m app.ml.table_recognition.train

Options:
    --config     Path to config file (optional)
    --resume     Path to checkpoint to resume from (optional)
    --debug      Run in debug mode (small dataset)
"""

import os
import sys
import argparse
import torch
from torch.utils.data import DataLoader, Subset
import random
import numpy as np

# Add parent directory to path
sys.path.append('/app')

from app.ml.table_recognition.config import config
from app.ml.table_recognition.model import create_model
from app.ml.table_recognition.dataset import TableRecognitionDataset, collate_fn
from app.ml.table_recognition.trainer import Trainer
from app.ml.table_recognition.model_utils import get_logger

logger = get_logger(__name__)


def set_seed(seed: int = 42):
    """Set random seed for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


def create_loaders(debug: bool = False):
    """
    Create dataloaders for training and validation.
    
    Args:
        debug: If True, use smaller dataset for testing
        
    Returns:
        train_loader, val_loader
    """
    logger.info("Creating dataloaders...")
    
    # Create datasets
    train_dataset = TableRecognitionDataset(
        data_dir=config.paths.DATA_DIR,
        split='train',
        target_size=config.dataset.IMAGE_SIZE,
        use_all_styles=config.dataset.USE_ALL_STYLES,
    )
    
    val_dataset = TableRecognitionDataset(
        data_dir=config.paths.DATA_DIR,
        split='val',
        target_size=config.dataset.IMAGE_SIZE,
        use_all_styles=config.dataset.USE_ALL_STYLES,
    )
    
    # Debug mode: use smaller datasets
    if debug:
        logger.warning("⚠️ Running in debug mode with small datasets")
        train_dataset = Subset(train_dataset, range(min(100, len(train_dataset))))
        val_dataset = Subset(val_dataset, range(min(20, len(val_dataset))))
    
    # Create dataloaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=config.dataset.BATCH_SIZE,
        shuffle=True,
        num_workers=config.dataset.NUM_WORKERS,
        collate_fn=collate_fn,
        pin_memory=True,
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=config.dataset.BATCH_SIZE,
        shuffle=False,
        num_workers=config.dataset.NUM_WORKERS,
        collate_fn=collate_fn,
        pin_memory=True,
    )
    
    logger.info(f"Train samples: {len(train_dataset)}")
    logger.info(f"Val samples: {len(val_dataset)}")
    logger.info(f"Train batches: {len(train_loader)}")
    logger.info(f"Val batches: {len(val_loader)}")
    
    return train_loader, val_loader


def main():
    """Main training function."""
    # Parse arguments
    parser = argparse.ArgumentParser(description='Train Table Recognition Model')
    parser.add_argument('--resume', type=str, help='Path to checkpoint to resume from')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    args = parser.parse_args()
    
    # Set seed
    set_seed(42)
    
    # Get device
    device = config.device.get_device()
    logger.info(f"Device: {device}")
    
    # Create dataloaders
    train_loader, val_loader = create_loaders(debug=args.debug)
    
    # Create model
    logger.info("Creating model...")
    model = create_model(use_pretrained=True)
    
    # Create trainer
    trainer = Trainer(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        config=config,
        device=device,
    )
    
    # Resume from checkpoint if specified
    if args.resume:
        logger.info(f"Resuming from checkpoint: {args.resume}")
        trainer.load_checkpoint(args.resume)
    
    # Start training
    trainer.train()


if __name__ == "__main__":
    main()