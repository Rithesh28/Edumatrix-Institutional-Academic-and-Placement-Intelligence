"""
Inference pipeline for Table Recognition Model.

Usage:
    python -m app.ml.table_recognition.inference --image /path/to/image.jpg
"""

import os
import sys
import argparse
import torch
import cv2
import numpy as np
from PIL import Image
import json
from typing import Dict, Any, List, Tuple

sys.path.append('/app')

from app.ml.table_recognition.model import TableRecognitionModel
from app.ml.table_recognition.config import config
from app.ml.table_recognition.model_utils import get_logger

logger = get_logger(__name__)


class TableRecognizer:
    """
    Inference class for Table Recognition Model.
    """
    
    def __init__(self, checkpoint_path: str = None):
        """
        Initialize the recognizer.
        
        Args:
            checkpoint_path: Path to model checkpoint
        """
        self.device = torch.device('cpu')
        self.model = None
        self.checkpoint_path = checkpoint_path or config.paths.BEST_MODEL_PATH
        self._load_model()
    
    def _load_model(self):
        """Load the trained model."""
        logger.info(f"Loading model from: {self.checkpoint_path}")
        
        # Create model
        self.model = TableRecognitionModel(
            backbone_name=config.model.CNN_BACKBONE,
            pretrained=False,
            transformer_layers=config.model.TRANSFORMER_LAYERS,
            attention_heads=config.model.ATTENTION_HEADS,
            hidden_dim=config.model.HIDDEN_DIM,
            ffn_dim=config.model.FFN_DIM,
            max_rows=config.model.MAX_ROWS,
            max_cols=config.model.MAX_COLS,
        )
        
        # Load weights
        checkpoint = torch.load(self.checkpoint_path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()
        self.model.to(self.device)
        
        logger.info(f"✅ Model loaded successfully from epoch {checkpoint.get('epoch', 'unknown') + 1}")
        logger.info(f"   Total parameters: {self.model.count_parameters():,}")
    
    def preprocess_image(self, image_path: str) -> torch.Tensor:
        """
        Preprocess image for model input.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Preprocessed image tensor
        """
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not load image: {image_path}")
        
        # Convert BGR to RGB
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Resize
        target_size = config.dataset.IMAGE_SIZE
        image = cv2.resize(image, target_size)
        
        # Normalize
        image = image.astype(np.float32) / 255.0
        
        # Convert to tensor and add batch dimension
        # Shape: (H, W, C) -> (C, H, W) -> (1, C, H, W)
        image = torch.from_numpy(image).permute(2, 0, 1).unsqueeze(0)
        
        # Expand to 9 channels (3 styles × 3 RGB)
        # For inference, we use the same image for all 3 styles
        image = image.repeat(1, 3, 1, 1)  # (1, 9, H, W)
        
        return image
    
    def predict(self, image_path: str) -> Dict[str, Any]:
        """
        Run inference on a single image.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Dictionary with predictions
        """
        # Preprocess
        image_tensor = self.preprocess_image(image_path)
        image_tensor = image_tensor.to(self.device)
        
        # Run inference
        with torch.no_grad():
            outputs = self.model(image_tensor)
        
        # Post-process
        result = self._postprocess_outputs(outputs)
        result['image_path'] = image_path
        
        return result
    
    def _postprocess_outputs(self, outputs: Dict[str, torch.Tensor]) -> Dict[str, Any]:
        """
        Post-process model outputs.
        
        Returns:
            Dictionary with human-readable results
        """
        # Table detection
        table_logits = outputs['table_detection']
        table_prob = torch.softmax(table_logits, dim=1)
        table_detected = table_prob[0, 1].item() > 0.5
        
        # Structure (rows and columns)
        rows_logits = outputs['rows']
        cols_logits = outputs['cols']
        
        # Get predicted row and column counts
        rows = torch.argmax(rows_logits, dim=1).item()
        cols = torch.argmax(cols_logits, dim=1).item()
        
        # Content (text) - simplified
        text_logits = outputs['text']
        # text_logits shape: (batch, seq_len, vocab_size) -> (batch, vocab_size)
        text_pred = torch.argmax(text_logits, dim=2)  # (batch, seq_len)
        
        # Convert to list for JSON serialization
        if text_pred.dim() == 2:
            text_pred_list = text_pred[0].tolist()[:10]  # First 10 tokens of first batch
        else:
            text_pred_list = text_pred.tolist()[:10]
        
        result = {
            'table_detected': table_detected,
            'table_confidence': table_prob[0, 1].item(),
            'rows': rows + 1,  # Convert to 1-indexed
            'cols': cols + 1,
            'text_predictions': text_pred_list,
        }
        
        return result
    
    def predict_batch(self, image_paths: List[str]) -> List[Dict[str, Any]]:
        """Run inference on multiple images."""
        results = []
        for image_path in image_paths:
            try:
                result = self.predict(image_path)
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing {image_path}: {str(e)}")
                results.append({'error': str(e), 'image_path': image_path})
        return results


def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description='Table Recognition Inference')
    parser.add_argument('--image', type=str, help='Path to image file')
    parser.add_argument('--checkpoint', type=str, help='Path to checkpoint file')
    parser.add_argument('--output', type=str, help='Output file path (JSON)')
    args = parser.parse_args()
    
    if not args.image:
        logger.error("Please provide an image path with --image")
        sys.exit(1)
    
    # Initialize recognizer
    recognizer = TableRecognizer(checkpoint_path=args.checkpoint)
    
    # Run inference
    logger.info(f"Processing image: {args.image}")
    result = recognizer.predict(args.image)
    
    # Print results
    logger.info("\n" + "=" * 50)
    logger.info("Inference Results")
    logger.info("=" * 50)
    logger.info(f"  Table Detected: {result['table_detected']}")
    logger.info(f"  Table Confidence: {result['table_confidence']:.4f}")
    logger.info(f"  Rows: {result['rows']}")
    logger.info(f"  Columns: {result['cols']}")
    logger.info("=" * 50)
    
    # Save results
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        logger.info(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()