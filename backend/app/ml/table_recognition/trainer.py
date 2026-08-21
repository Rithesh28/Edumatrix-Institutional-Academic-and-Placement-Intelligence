"""
Trainer class for Table Recognition Model.

Handles:
├── Training loop
├── Validation loop
├── Checkpoint saving
├── Learning rate scheduling
├── TensorBoard logging
└── Early stopping
"""

import os
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
try:
    from torch.utils.tensorboard import SummaryWriter
except (ImportError, ModuleNotFoundError):
    class SummaryWriter:
        """Dummy SummaryWriter when tensorboard is not installed."""
        def __init__(self, *args, **kwargs):
            pass
        def add_scalar(self, *args, **kwargs):
            pass
        def add_image(self, *args, **kwargs):
            pass
        def close(self):
            pass
from tqdm import tqdm
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

from .config import config
from .model import TableRecognitionModel, create_model
from .dataset import TableRecognitionDataset, collate_fn
from .model_utils import (
    TableRecognitionLoss,
    TableRecognitionMetrics,
    AverageMeter,
    get_logger,
)

logger = get_logger(__name__)


class Trainer:
    """
    Trainer for Table Recognition Model.
    """
    
    def __init__(
        self,
        model: nn.Module,
        train_loader: DataLoader,
        val_loader: DataLoader,
        config: Any,
        device: torch.device,
    ):
        self.model = model
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.config = config
        self.device = device
        
        # Move model to device
        self.model.to(device)
        
        # Loss function
        self.criterion = TableRecognitionLoss(
            weights=config.training.LOSS_WEIGHTS
        )
        
        # Optimizer
        self.optimizer = optim.AdamW(
            self.model.parameters(),
            lr=config.training.LEARNING_RATE,
            weight_decay=config.training.WEIGHT_DECAY,
            betas=config.training.BETAS,
            eps=config.training.EPS,
        )
        
        # Learning rate scheduler
        self.scheduler = self._create_scheduler()
        
        # Metrics
        self.metrics = TableRecognitionMetrics()
        
        # Logging
        self.writer = SummaryWriter(config.paths.TENSORBOARD_DIR)
        self.best_val_loss = float('inf')
        self.best_val_f1 = 0.0
        self.epochs_no_improve = 0
        
        logger.info(f"Trainer initialized on {device}")
        logger.info(f"Total parameters: {model.count_parameters():,}")
    
    def _create_scheduler(self):
        """Create learning rate scheduler."""
        scheduler_type = self.config.training.SCHEDULER
        
        if scheduler_type == "cosine":
            return optim.lr_scheduler.CosineAnnealingLR(
                self.optimizer,
                T_max=self.config.training.EPOCHS,
                eta_min=self.config.training.MIN_LR,
            )
        elif scheduler_type == "step":
            return optim.lr_scheduler.StepLR(
                self.optimizer,
                step_size=5,
                gamma=0.5,
            )
        elif scheduler_type == "plateau":
            return optim.lr_scheduler.ReduceLROnPlateau(
                self.optimizer,
                mode='min',
                factor=0.5,
                patience=3,
                min_lr=self.config.training.MIN_LR,
            )
        else:
            return None
    
    def train_epoch(self, epoch: int) -> Dict[str, float]:
        """
        Train for one epoch.
        
        Returns:
            Dictionary of loss values
        """
        self.model.train()
        
        # Initialize meters
        loss_meter = AverageMeter()
        table_loss_meter = AverageMeter()
        structure_loss_meter = AverageMeter()
        ocr_loss_meter = AverageMeter()
        
        # Progress bar
        pbar = tqdm(
            self.train_loader,
            desc=f"Epoch {epoch+1}/{self.config.training.EPOCHS} [Train]",
            leave=False,
        )
        
        for batch_idx, batch in enumerate(pbar):
            # Move data to device
            images = batch['images'].to(self.device)
            batch_size = images.size(0)
            max_rows = self.config.model.MAX_ROWS
            
            # In train_epoch method:

            # Forward pass
            outputs = self.model(images)

            # Create dummy targets (simplified for testing)
            batch_size = images.size(0)
            max_rows = self.config.model.MAX_ROWS
            target_table = torch.randint(0, 2, (batch_size, 2)).float().to(self.device)
            target_rows = torch.randint(0, max_rows, (batch_size,)).to(self.device)
            target_text = torch.randint(0, 1000, (batch_size, 1, 1000)).float().to(self.device)  # ← FIXED: .float()

            # Calculate losses
            loss, loss_dict = self.criterion(
                outputs['table_detection'],
                target_table,
                outputs['rows'],
                target_rows,
                outputs['text'],
                target_text,
            )
            
            # Backward pass
            self.optimizer.zero_grad()
            loss.backward()
            
            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(
                self.model.parameters(),
                self.config.training.GRADIENT_CLIP
            )
            
            self.optimizer.step()
            
            # Update meters
            loss_meter.update(loss.item(), batch_size)
            table_loss_meter.update(loss_dict['table_detection'].item(), batch_size)
            structure_loss_meter.update(loss_dict['structure'].item(), batch_size)
            ocr_loss_meter.update(loss_dict['ocr'].item(), batch_size)
            
            # Update progress bar
            pbar.set_postfix({
                'loss': f"{loss_meter.avg:.4f}",
                'table': f"{table_loss_meter.avg:.4f}",
                'struct': f"{structure_loss_meter.avg:.4f}",
                'ocr': f"{ocr_loss_meter.avg:.4f}",
            })
            
            # Log batch metrics
            if batch_idx % self.config.training.LOG_INTERVAL == 0:
                step = epoch * len(self.train_loader) + batch_idx
                self.writer.add_scalar('train/loss', loss.item(), step)
                self.writer.add_scalar('train/table_loss', loss_dict['table_detection'].item(), step)
                self.writer.add_scalar('train/structure_loss', loss_dict['structure'].item(), step)
                self.writer.add_scalar('train/ocr_loss', loss_dict['ocr'].item(), step)
                self.writer.add_scalar('train/lr', self.optimizer.param_groups[0]['lr'], step)
        
        return {
            'loss': loss_meter.avg,
            'table_loss': table_loss_meter.avg,
            'structure_loss': structure_loss_meter.avg,
            'ocr_loss': ocr_loss_meter.avg,
        }
    
    @torch.no_grad()
    def validate(self, epoch: int) -> Dict[str, float]:
        """
        Validate the model.
        
        Returns:
            Dictionary of validation metrics
        """
        self.model.eval()
        
        # Initialize meters
        loss_meter = AverageMeter()
        table_loss_meter = AverageMeter()
        structure_loss_meter = AverageMeter()
        ocr_loss_meter = AverageMeter()
        
        # Progress bar
        pbar = tqdm(
            self.val_loader,
            desc=f"Epoch {epoch+1}/{self.config.training.EPOCHS} [Val]",
            leave=False,
        )
        
        for batch in pbar:
            # Move data to device
            images = batch['images'].to(self.device)
            batch_size = images.size(0)
            max_rows = self.config.model.MAX_ROWS
            
            # Forward pass
            outputs = self.model(images)
            
            # Dummy targets
            target_table = torch.randint(0, 2, (batch_size, 2)).float().to(self.device)
            target_rows = torch.randint(0, max_rows, (batch_size,)).to(self.device)
            target_text = torch.randint(0, 1000, (batch_size, 1, 1000)).float().to(self.device)
            
            # Calculate losses
            loss, loss_dict = self.criterion(
                outputs['table_detection'],
                target_table,
                outputs['rows'],
                target_rows,
                outputs['text'],
                target_text,
            )
            
            # Update meters
            loss_meter.update(loss.item(), batch_size)
            table_loss_meter.update(loss_dict['table_detection'].item(), batch_size)
            structure_loss_meter.update(loss_dict['structure'].item(), batch_size)
            ocr_loss_meter.update(loss_dict['ocr'].item(), batch_size)
            
            pbar.set_postfix({
                'val_loss': f"{loss_meter.avg:.4f}",
            })
        
        # Log validation metrics
        self.writer.add_scalar('val/loss', loss_meter.avg, epoch)
        self.writer.add_scalar('val/table_loss', table_loss_meter.avg, epoch)
        self.writer.add_scalar('val/structure_loss', structure_loss_meter.avg, epoch)
        self.writer.add_scalar('val/ocr_loss', ocr_loss_meter.avg, epoch)
        
        return {
            'loss': loss_meter.avg,
            'table_loss': table_loss_meter.avg,
            'structure_loss': structure_loss_meter.avg,
            'ocr_loss': ocr_loss_meter.avg,
        }
    
    def save_checkpoint(self, epoch: int, is_best: bool = False):
        """Save model checkpoint."""
        checkpoint = {
            'epoch': epoch,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'best_val_loss': self.best_val_loss,
            'config': self.config.get_training_config(),
        }
        
        # Save regular checkpoint
        checkpoint_path = os.path.join(
            self.config.paths.CHECKPOINT_DIR,
            f'checkpoint_epoch_{epoch+1}.pth'
        )
        torch.save(checkpoint, checkpoint_path)
        logger.info(f"Saved checkpoint: {checkpoint_path}")
        
        # Save best model
        if is_best:
            best_path = self.config.paths.BEST_MODEL_PATH
            torch.save(checkpoint, best_path)
            logger.info(f"Saved best model: {best_path}")
    
    def load_checkpoint(self, checkpoint_path: str):
        """Load model checkpoint."""
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.best_val_loss = checkpoint['best_val_loss']
        logger.info(f"Loaded checkpoint: {checkpoint_path}")
    
    def train(self):
        """Complete training loop."""
        logger.info("Starting training...")
        logger.info(f"Total epochs: {self.config.training.EPOCHS}")
        logger.info(f"Train batches: {len(self.train_loader)}")
        logger.info(f"Val batches: {len(self.val_loader)}")
        
        for epoch in range(self.config.training.EPOCHS):
            logger.info(f"\n{'='*50}")
            logger.info(f"Epoch {epoch+1}/{self.config.training.EPOCHS}")
            logger.info(f"{'='*50}")
            
            # Train
            train_metrics = self.train_epoch(epoch)
            logger.info(f"Train Loss: {train_metrics['loss']:.4f}")
            
            # Validate
            val_metrics = self.validate(epoch)
            logger.info(f"Val Loss: {val_metrics['loss']:.4f}")
            
            # Update scheduler
            if self.scheduler:
                if isinstance(self.scheduler, torch.optim.lr_scheduler.ReduceLROnPlateau):
                    self.scheduler.step(val_metrics['loss'])
                else:
                    self.scheduler.step()
            
            # Check for improvement
            is_best = False
            if val_metrics['loss'] < self.best_val_loss:
                self.best_val_loss = val_metrics['loss']
                self.epochs_no_improve = 0
                is_best = True
                logger.info(f"✅ New best model! Loss: {self.best_val_loss:.4f}")
            else:
                self.epochs_no_improve += 1
            
            # Save checkpoint
            if (epoch + 1) % self.config.training.SAVE_INTERVAL == 0:
                self.save_checkpoint(epoch, is_best)
            
            # Early stopping
            if self.epochs_no_improve >= self.config.training.EARLY_STOPPING_PATIENCE:
                logger.info(f"Early stopping triggered after {epoch+1} epochs")
                break
            
            # Log epoch summary
            self.writer.add_scalar('epoch/train_loss', train_metrics['loss'], epoch)
            self.writer.add_scalar('epoch/val_loss', val_metrics['loss'], epoch)
            self.writer.add_scalar('epoch/lr', self.optimizer.param_groups[0]['lr'], epoch)
        
        logger.info("\n" + "="*50)
        logger.info("✅ Training complete!")
        logger.info(f"Best validation loss: {self.best_val_loss:.4f}")
        logger.info(f"Best model saved at: {self.config.paths.BEST_MODEL_PATH}")
        logger.info("="*50)
        
        # Close TensorBoard writer
        self.writer.close()