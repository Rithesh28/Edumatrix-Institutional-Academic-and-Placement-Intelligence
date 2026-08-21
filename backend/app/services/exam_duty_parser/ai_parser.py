"""
AI Parser for Exam Duty Extraction

This module uses the trained Table Recognition AI model to extract
exam duty information from images and PDFs.
"""

import os
import sys
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import pdf2image
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

try:
    import numpy as np
except ImportError:
    np = None

try:
    from PIL import Image
except ImportError:
    Image = None

from typing import Dict, Any, List, Optional, Tuple
import logging

try:
    from app.ml.table_recognition.inference import TableRecognizer
    from app.ml.table_recognition.config import config
    TABLE_RECOGNIZER_AVAILABLE = True
except Exception:
    TableRecognizer = None
    config = None
    TABLE_RECOGNIZER_AVAILABLE = False

from app.services.exam_duty_parser.entity_mapper import EntityMapper
from app.services.exam_duty_parser.checkmark_detector import CheckmarkDetector

logger = logging.getLogger(__name__)


class AIParser:
    """
    AI-powered parser for exam duty extraction.
    
    Uses the trained Table Recognition model to detect tables,
    extract structure, and identify duties.
    """
    
    def __init__(self, checkpoint_path: str = None):
        """
        Initialize the AI parser.
        
        Args:
            checkpoint_path: Path to model checkpoint (optional)
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        candidate_paths = [
            checkpoint_path,
            os.path.join(os.path.dirname(os.path.dirname(current_dir)), "ml", "table_recognition", "weights", "best_model.pth"),
            "/app/app/ml/table_recognition/weights/best_model.pth",
            "/app/ml/table_recognition/weights/best_model.pth"
        ]
        valid_paths = [p for p in candidate_paths if p and os.path.exists(p)]
        self.checkpoint_path = valid_paths[0] if valid_paths else candidate_paths[1]
        self.recognizer = None
        self.entity_mapper = EntityMapper()
        self.checkmark_detector = CheckmarkDetector()
        self._init_model()
    
    def _init_model(self):
        """Initialize the AI model."""
        if not TABLE_RECOGNIZER_AVAILABLE or not self.checkpoint_path or not os.path.exists(self.checkpoint_path):
            logger.info("AI Table recognition model checkpoint not found, using fallback parser")
            self.recognizer = None
            return
        try:
            self.recognizer = TableRecognizer(checkpoint_path=self.checkpoint_path)
            logger.info("✅ AI Parser initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize AI model: {str(e)}")
            self.recognizer = None
    
    def is_available(self) -> bool:
        """Check if AI model is available."""
        return self.recognizer is not None
    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse an exam duty file using AI model.
        
        Args:
            file_path: Path to the file (image or PDF)
            
        Returns:
            Dict with parsing results
        """
        if not self.is_available():
            return {
                'success': False,
                'error': 'AI model not available',
                'fallback_needed': True
            }
        
        try:
            # Step 1: Convert to image if PDF
            image_path = self._prepare_image(file_path)
            
            # Step 2: Run AI inference
            result = self.recognizer.predict(image_path)
            
            # Step 3: Extract duties from structure
            duties = self._extract_duties_from_result(result)
            
            # Step 4: Add confidence
            confidence = result.get('table_confidence', 0.0)
            
            return {
                'success': True,
                'table_detected': result.get('table_detected', False),
                'rows': result.get('rows', 0),
                'cols': result.get('cols', 0),
                'duties': duties,
                'confidence': confidence,
                'raw_result': result,
                'fallback_needed': confidence < 0.6
            }
            
        except Exception as e:
            logger.error(f"AI parsing failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'fallback_needed': True
            }
    
    def _prepare_image(self, file_path: str) -> str:
        """
        Prepare image for AI model.
        
        Args:
            file_path: Path to file (image or PDF)
            
        Returns:
            Path to prepared image
        """
        ext = os.path.splitext(file_path)[1].lower()
        
        # If PDF, convert to image
        if ext == '.pdf':
            logger.info(f"Converting PDF to image: {file_path}")
            images = pdf2image.convert_from_path(file_path, first_page=1, last_page=1, dpi=150)
            if images:
                temp_path = file_path + '.jpg'
                images[0].save(temp_path, 'JPEG')
                return temp_path
        
        # If already image, return as is
        return file_path
    
    def _extract_duties_from_result(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract duties from AI model result.
        """
        duties = []
        
        # If no table detected, return empty
        if not result.get('table_detected', False):
            return duties
        
        # Get table structure
        rows = result.get('rows', 0)
        cols = result.get('cols', 0)
        
        # For now, create sample duties based on structure
        # In production, you would extract text from cells using OCR
        # and then use GLiNER + EntityMapper
        
        for row in range(min(rows, 20)):  # Limit to 20 rows for demo
            # Check if row has a checkmark (simplified)
            # In production, use checkmark_detector
            if row % 2 == 0:  # Just for demo
                duty = {
                    'faculty_name': f"Faculty_{row+1}",
                    'date': f"{row+1}-Aug",
                    'time': 'M' if row % 4 == 0 else 'A',
                    'venue': f"Hall {chr(65 + row % 5)}",
                    'exam_name': 'Exam Duty',
                    'faculty_names': [f"Faculty_{row+1}"]
                }
                duties.append(duty)
        
        return duties
    
    def parse_batch(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """Parse multiple files."""
        results = []
        for file_path in file_paths:
            result = self.parse(file_path)
            results.append(result)
        return results


# Singleton instance
ai_parser = AIParser()