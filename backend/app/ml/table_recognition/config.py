"""
Configuration for Table Recognition Model
"""

import os
from typing import Dict, Any, Tuple


class Paths:
    """All file paths for the project."""
    
    # Base data directory (inside Docker)
    DATA_DIR = "/app/data"
    
    # TabRecSet paths
    TABRECSET_IMAGES = {
        "all_line": os.path.join(DATA_DIR, "tabrecset/image/english_all-line"),
        "no_line": os.path.join(DATA_DIR, "tabrecset/image/english_no-line"),
        "three_line": os.path.join(DATA_DIR, "tabrecset/image/english_three-line"),
    }
    TABRECSET_TD = os.path.join(DATA_DIR, "tabrecset/TD annotation/english")
    TABRECSET_TSR_TCR = os.path.join(DATA_DIR, "tabrecset/TSR_TCR_annotation/english")
    
    # Tencent OCR path
    TENCENT_OCR = os.path.join(DATA_DIR, "tencent_ocr/english")
    
    # Model weights
    WEIGHTS_DIR = os.path.join(os.path.dirname(__file__), "weights")
    CHECKPOINT_DIR = os.path.join(WEIGHTS_DIR, "checkpoints")
    BEST_MODEL_PATH = os.path.join(WEIGHTS_DIR, "best_model.pth")
    
    # Logs
    LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")
    TENSORBOARD_DIR = os.path.join(LOGS_DIR, "tensorboard")
    
    @classmethod
    def create_dirs(cls):
        """Create all necessary directories."""
        os.makedirs(cls.WEIGHTS_DIR, exist_ok=True)
        os.makedirs(cls.CHECKPOINT_DIR, exist_ok=True)
        os.makedirs(cls.LOGS_DIR, exist_ok=True)
        os.makedirs(cls.TENSORBOARD_DIR, exist_ok=True)


class DatasetConfig:
    """Dataset loading and preprocessing settings."""
    
    # Image settings
    IMAGE_SIZE = (128, 128)  # (height, width) - reduced for CPU
    USE_ALL_STYLES = True
    NORMALIZE = True
    
    # Split ratios
    TRAIN_RATIO = 0.8
    VAL_RATIO = 0.1
    TEST_RATIO = 0.1
    
    # Batch size (reduced for CPU)
    BATCH_SIZE = 2
    NUM_WORKERS = 0
    
    # Augmentation settings
    AUGMENTATION = {
        "rotation": 15,
        "scale": (0.8, 1.2),
        "brightness": 0.2,
        "contrast": 0.2,
    }


class ModelConfig:
    """Model architecture settings."""
    
    # CNN Backbone (smaller for CPU)
    CNN_BACKBONE = "resnet18"
    CNN_PRETRAINED = True
    
    # Transformer (smaller for CPU)
    TRANSFORMER_LAYERS = 2
    ATTENTION_HEADS = 4
    HIDDEN_DIM = 128
    FFN_DIM = 256
    DROPOUT = 0.1
    
    # Decoder Heads
    TABLE_DETECTION_CLASSES = 2
    MAX_ROWS = 50
    MAX_COLS = 30
    MAX_CELLS = 500
    
    # Embedding
    EMBEDDING_DIM = 384


class TrainingConfig:
    """Training hyperparameters."""
    
    # Optimization
    LEARNING_RATE = 1e-4
    WEIGHT_DECAY = 1e-5
    BETAS = (0.9, 0.999)
    EPS = 1e-8
    
    # Learning rate scheduler
    SCHEDULER = "cosine"
    WARMUP_EPOCHS = 2
    MIN_LR = 1e-6
    
    # Loss weights
    LOSS_WEIGHTS = {
        "table_detection": 1.0,
        "structure": 1.0,
        "ocr": 0.5,
    }
    
    # Training (reduced for CPU)
    EPOCHS = 3
    GRADIENT_CLIP = 1.0
    EARLY_STOPPING_PATIENCE = 5
    
    # Logging
    LOG_INTERVAL = 10
    SAVE_INTERVAL = 1
    VAL_INTERVAL = 1


class InferenceConfig:
    """Inference settings."""
    
    CONFIDENCE_THRESHOLD = 0.5
    IOU_THRESHOLD = 0.5
    MAX_DETECTIONS = 100
    OUTPUT_FORMAT = "json"
    DEVICE = "cpu"


class DeviceConfig:
    """Device settings."""
    
    @staticmethod
    def get_device():
        """Get the appropriate device."""
        import torch
        return torch.device("cpu")


class Config:
    """Master configuration."""
    
    def __init__(self):
        self.paths = Paths()
        self.dataset = DatasetConfig()
        self.model = ModelConfig()
        self.training = TrainingConfig()
        self.inference = InferenceConfig()
        self.device = DeviceConfig()
        
        # Create directories
        self.paths.create_dirs()
    
    def get_training_config(self) -> Dict[str, Any]:
        """Get all training parameters as a dictionary."""
        return {
            "batch_size": self.dataset.BATCH_SIZE,
            "learning_rate": self.training.LEARNING_RATE,
            "weight_decay": self.training.WEIGHT_DECAY,
            "epochs": self.training.EPOCHS,
            "image_size": self.dataset.IMAGE_SIZE,
            "model": {
                "backbone": self.model.CNN_BACKBONE,
                "transformer_layers": self.model.TRANSFORMER_LAYERS,
                "attention_heads": self.model.ATTENTION_HEADS,
                "hidden_dim": self.model.HIDDEN_DIM,
            },
            "loss_weights": self.training.LOSS_WEIGHTS,
        }
    
    def __repr__(self) -> str:
        return (
            f"Config(\n"
            f"  dataset={self.dataset.__class__.__name__},\n"
            f"  model={self.model.__class__.__name__},\n"
            f"  training={self.training.__class__.__name__},\n"
            f"  device={self.device.get_device()}\n"
            f")"
        )


# ============================================
# SINGLETON INSTANCE
# ============================================
config = Config()


# ============================================
# TEST CONFIGURATION
# ============================================
if __name__ == "__main__":
    print("=== Configuration ===")
    print(config)
    print("\n=== Training Config ===")
    print(config.get_training_config())
    print("\n=== Paths ===")
    print(f"  WEIGHTS_DIR: {config.paths.WEIGHTS_DIR}")
    print(f"  LOGS_DIR: {config.paths.LOGS_DIR}")
    print(f"  DATA_DIR: {config.paths.DATA_DIR}")