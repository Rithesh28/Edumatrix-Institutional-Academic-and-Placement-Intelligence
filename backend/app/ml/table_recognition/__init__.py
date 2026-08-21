"""
Table Recognition Module for Exam Duty AI Model
"""

from .dataset import TableRecognitionDataset, collate_fn
from .model import TableRecognitionModel, create_model
from .trainer import Trainer
from .train import main as train_model
from .evaluate import evaluate_model
from .inference import TableRecognizer
from .config import config

__all__ = [
    'TableRecognitionDataset',
    'collate_fn',
    'TableRecognitionModel',
    'create_model',
    'Trainer',
    'train_model',
    'evaluate_model',
    'TableRecognizer',
    'config',
]