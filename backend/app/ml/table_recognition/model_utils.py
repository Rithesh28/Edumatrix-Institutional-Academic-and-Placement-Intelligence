"""
Utility functions for the Table Recognition Model.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Tuple, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class TableRecognitionLoss(nn.Module):
    """Multi-task loss for table recognition."""
    
    def __init__(self, weights: Dict[str, float] = None):
        super().__init__()
        self.weights = weights or {
            "table_detection": 1.0,
            "structure": 1.0,
            "ocr": 0.5,
        }
        self.bce_loss = nn.BCEWithLogitsLoss()
        self.ce_loss = nn.CrossEntropyLoss()
        self.mse_loss = nn.MSELoss()
    
    def forward(
        self,
        pred_table: torch.Tensor,
        target_table: torch.Tensor,
        pred_structure: torch.Tensor,
        target_structure: torch.Tensor,
        pred_text: torch.Tensor,
        target_text: torch.Tensor,
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """Calculate multi-task loss."""
        # Table Detection Loss
        loss_table = self.bce_loss(pred_table, target_table)
        
        # Structure Recognition Loss
        # pred_structure: (batch, max_rows)
        # target_structure: (batch,)
        loss_structure = self.ce_loss(pred_structure, target_structure)
        
        # Content Recognition Loss
        # pred_text: (batch, seq_len, vocab_size) -> (batch, vocab_size)
        # target_text: (batch, seq_len, vocab_size) -> (batch, vocab_size)
        # Squeeze seq_len dimension if it's 1
        if pred_text.dim() == 3 and pred_text.size(1) == 1:
            pred_text = pred_text.squeeze(1)  # (batch, vocab_size)
        if target_text.dim() == 3 and target_text.size(1) == 1:
            target_text = target_text.squeeze(1)  # (batch, vocab_size)
        
        loss_ocr = self.mse_loss(pred_text, target_text)
        
        # Weighted total loss
        total_loss = (
            self.weights["table_detection"] * loss_table +
            self.weights["structure"] * loss_structure +
            self.weights["ocr"] * loss_ocr
        )
        
        loss_dict = {
            "table_detection": loss_table,
            "structure": loss_structure,
            "ocr": loss_ocr,
            "total": total_loss,
        }
        
        return total_loss, loss_dict


class TableRecognitionMetrics:
    """Metrics for table recognition evaluation."""
    
    @staticmethod
    def calculate_iou(box1: List[float], box2: List[float]) -> float:
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        if x2 < x1 or y2 < y1:
            return 0.0
        intersection = (x2 - x1) * (y2 - y1)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - intersection
        return intersection / union if union > 0 else 0.0
    
    @staticmethod
    def calculate_accuracy(pred: torch.Tensor, target: torch.Tensor) -> float:
        pred_class = torch.argmax(pred, dim=1)
        correct = (pred_class == target).sum().item()
        total = target.size(0)
        return correct / total if total > 0 else 0.0


def normalize_bbox(bbox: List[float], img_width: int, img_height: int) -> List[float]:
    return [
        bbox[0] / img_width,
        bbox[1] / img_height,
        bbox[2] / img_width,
        bbox[3] / img_height,
    ]


def denormalize_bbox(bbox: List[float], img_width: int, img_height: int) -> List[float]:
    return [
        bbox[0] * img_width,
        bbox[1] * img_height,
        bbox[2] * img_width,
        bbox[3] * img_height,
    ]


def iou_matrix(boxes1: torch.Tensor, boxes2: torch.Tensor) -> torch.Tensor:
    """Calculate IoU matrix between two sets of boxes."""
    N = boxes1.size(0)
    M = boxes2.size(0)
    boxes1_exp = boxes1.unsqueeze(1).expand(N, M, 4)
    boxes2_exp = boxes2.unsqueeze(0).expand(N, M, 4)
    x1 = torch.max(boxes1_exp[..., 0], boxes2_exp[..., 0])
    y1 = torch.max(boxes1_exp[..., 1], boxes2_exp[..., 1])
    x2 = torch.min(boxes1_exp[..., 2], boxes2_exp[..., 2])
    y2 = torch.min(boxes1_exp[..., 3], boxes2_exp[..., 3])
    intersection = (x2 - x1).clamp(min=0) * (y2 - y1).clamp(min=0)
    area1 = (boxes1_exp[..., 2] - boxes1_exp[..., 0]) * (boxes1_exp[..., 3] - boxes1_exp[..., 1])
    area2 = (boxes2_exp[..., 2] - boxes2_exp[..., 0]) * (boxes2_exp[..., 3] - boxes2_exp[..., 1])
    union = area1 + area2 - intersection
    return intersection / (union + 1e-6)


class AverageMeter:
    """Computes and stores the average and current value."""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0
    
    def update(self, val: float, n: int = 1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Get a configured logger."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger