"""
Test script for Table Recognition Model.

This script tests:
├── Model forward pass
├── Dataset integration
└── Basic training loop
"""

import sys
import os
import torch
import logging

# Add parent directory to path
sys.path.append('/app')

from app.ml.table_recognition.dataset import TableRecognitionDataset
from app.ml.table_recognition.model import TableRecognitionModel, create_model
from app.ml.table_recognition.config import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_dataset():
    """Test dataset loading."""
    logger.info("=== Testing Dataset ===")
    
    dataset = TableRecognitionDataset(
        data_dir=config.paths.DATA_DIR,
        split='train',
        target_size=config.dataset.IMAGE_SIZE,
        use_all_styles=config.dataset.USE_ALL_STYLES,
    )
    
    logger.info(f"Dataset size: {len(dataset)}")
    
    if len(dataset) > 0:
        sample = dataset[0]
        logger.info(f"Sample keys: {list(sample.keys())}")
        logger.info(f"Image shape: {sample['image'].shape}")
        logger.info(f"Table bbox: {sample['table_bbox']}")
        logger.info(f"Structure: {sample['structure']}")
        logger.info(f"Cells: {len(sample['cells'])}")
        logger.info(f"Text: {len(sample['text'])}")
    
    return dataset


def test_model():
    """Test model forward pass."""
    logger.info("\n=== Testing Model ===")
    
    # Create model
    model = create_model(use_pretrained=True)
    
    # Move to device
    device = config.device.get_device()
    model = model.to(device)
    logger.info(f"Model on device: {device}")
    
    # Create dummy input
    batch_size = 2
    channels = 9  # 3 styles × 3 RGB
    height, width = config.dataset.IMAGE_SIZE
    
    dummy_input = torch.randn(batch_size, channels, height, width).to(device)
    logger.info(f"Dummy input shape: {dummy_input.shape}")
    
    # Forward pass
    with torch.no_grad():
        outputs = model(dummy_input)
    
    logger.info("Output shapes:")
    for key, value in outputs.items():
        if isinstance(value, torch.Tensor):
            logger.info(f"  {key}: {value.shape}")
    
    logger.info("✅ Model forward pass successful!")
    return model


def test_training_step():
    """Test a single training step."""
    logger.info("\n=== Testing Training Step ===")
    
    # Create dataset
    dataset = TableRecognitionDataset(
        data_dir=config.paths.DATA_DIR,
        split='train',
        target_size=config.dataset.IMAGE_SIZE,
        use_all_styles=config.dataset.USE_ALL_STYLES,
    )
    
    if len(dataset) == 0:
        logger.warning("Dataset is empty, skipping training step test")
        return
    
    # Get a sample
    sample = dataset[0]
    image = sample['image'].unsqueeze(0)  # Add batch dimension
    
    # Create model
    model = create_model(use_pretrained=True)
    device = config.device.get_device()
    model = model.to(device)
    image = image.to(device)
    
    # Forward pass
    outputs = model(image)
    
    # Check outputs
    for key, value in outputs.items():
        if isinstance(value, torch.Tensor):
            logger.info(f"{key}: {value.shape}")
    
    # Create dummy targets (for testing)
    target_table = torch.tensor([[1.0, 0.0]], dtype=torch.float32).to(device)
    target_rows = torch.randint(0, 10, (1, 50)).to(device)
    target_cols = torch.randint(0, 6, (1, 30)).to(device)
    target_text = torch.randint(0, 1000, (1, 100)).to(device)
    
    # Calculate loss (simplified)
    loss_table = torch.nn.functional.binary_cross_entropy_with_logits(
        outputs['table_detection'], target_table
    )
    
    logger.info(f"Table Detection Loss: {loss_table.item():.4f}")
    logger.info("✅ Training step test successful!")


def main():
    """Run all tests."""
    logger.info("=" * 50)
    logger.info("Table Recognition Model Tests")
    logger.info("=" * 50)
    
    # Check CUDA availability
    if torch.cuda.is_available():
        logger.info(f"CUDA available: {torch.cuda.get_device_name(0)}")
    else:
        logger.info("CUDA not available, using CPU")
    
    try:
        # Test 1: Dataset
        dataset = test_dataset()
        
        # Test 2: Model
        model = test_model()
        
        # Test 3: Training step
        test_training_step()
        
        logger.info("\n" + "=" * 50)
        logger.info("✅ All tests passed!")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}")
        raise


if __name__ == "__main__":
    main()