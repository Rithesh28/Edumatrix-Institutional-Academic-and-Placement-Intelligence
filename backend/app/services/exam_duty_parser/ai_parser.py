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
            
            # Step 2: Run AI inference (table structure detection)
            result = self.recognizer.predict(image_path)
            confidence = float(result.get('table_confidence', 0.0))
            table_detected = bool(result.get('table_detected', False))
            
            # If AI model did not detect a table with sufficient confidence, fail safely
            has_table_structure = table_detected or (confidence >= 0.40 and result.get('rows', 0) > 0 and result.get('cols', 0) > 0)
            if not has_table_structure or confidence < 0.35:
                logger.info(f"AI model did not detect table structure with confidence (detected={table_detected}, conf={confidence:.2f})")
                return {
                    'success': False,
                    'table_detected': False,
                    'rows': result.get('rows', 0),
                    'cols': result.get('cols', 0),
                    'duties': [],
                    'confidence': confidence,
                    'raw_result': result,
                    'error': 'No table structure detected in timetable image',
                    'review_required': True,
                    'fallback_needed': True
                }
            
            # Step 3: Extract genuine duties from recognized cell regions via OCR
            duties = self._extract_duties_from_result(result, image_path=image_path)
            
            if duties:
                logger.info(f"✅ AI Parser successfully extracted {len(duties)} genuine duties via OCR")
                return {
                    'success': True,
                    'table_detected': True,
                    'rows': result.get('rows', 0),
                    'cols': result.get('cols', 0),
                    'duties': duties,
                    'total_duties': len(duties),
                    'confidence': confidence,
                    'raw_result': result,
                    'review_required': False,
                    'fallback_needed': False
                }
            else:
                # Structure detected, but text could not be reliably extracted from cells
                logger.warning("Table structure detected by AI model, but cell OCR text was unreadable or insufficient")
                return {
                    'success': False,
                    'table_detected': True,
                    'rows': result.get('rows', 0),
                    'cols': result.get('cols', 0),
                    'duties': [],
                    'total_duties': 0,
                    'confidence': confidence,
                    'raw_result': result,
                    'error': 'Table structure detected but cell text/duties could not be reliably extracted from image',
                    'review_required': True,
                    'fallback_needed': True
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
    
    def _extract_duties_from_result(
        self,
        result: Dict[str, Any],
        image_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract genuine duties from recognized table cell regions.
        Zero placeholders: If cell text is unreadable or absent, returns empty list.
        """
        duties = []
        
        # If no table structure detected, return empty
        if not result.get('table_detected', False) and result.get('table_confidence', 0.0) < 0.40:
            return duties
        
        img_target = image_path or result.get('image_path')
        if not img_target or not os.path.exists(img_target):
            # No image available to perform OCR extraction; never fabricate mock data
            return []
        
        try:
            from .table_transformer_parser import table_transformer_parser
            import pytesseract
            
            pil_img = Image.open(img_target) if Image else None
            extracted_raw_duties = []
            
            # Strategy A: Matrix timetable parser for multi-column grid timetables
            if pil_img is not None:
                try:
                    matrix_duties = table_transformer_parser._extract_matrix_duties_from_image(pil_img)
                    if matrix_duties:
                        extracted_raw_duties.extend(matrix_duties)
                except Exception as e:
                    logger.debug(f"Matrix grid parse error in AI parser: {e}")
            
            # Strategy B: Local OCR extraction across table text lines
            if not extracted_raw_duties and pil_img is not None:
                try:
                    # Preprocess for contrast enhancement
                    prep_img = pil_img.convert('L')
                    if CV2_AVAILABLE and np is not None:
                        np_img = np.array(prep_img)
                        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                        enhanced = clahe.apply(np_img)
                        prep_img = Image.fromarray(enhanced)
                    
                    ocr_text = pytesseract.image_to_string(prep_img, config='--oem 3 --psm 6')
                    if not ocr_text or len(ocr_text.strip()) < 15:
                        ocr_text = pytesseract.image_to_string(prep_img, config='--oem 3 --psm 3')
                    
                    if ocr_text and len(ocr_text.strip()) > 15:
                        line_duties = table_transformer_parser._extract_duties_from_raw_text(ocr_text)
                        if line_duties:
                            extracted_raw_duties.extend(line_duties)
                except Exception as e:
                    logger.debug(f"OCR text extraction error in AI parser: {e}")
            
            # Normalize and strictly validate extracted records
            for ed in extracted_raw_duties:
                duty_dict = ed.to_dict() if hasattr(ed, 'to_dict') else ed
                if not isinstance(duty_dict, dict):
                    continue
                
                raw_name = str(duty_dict.get('faculty_name', '')).strip()
                # Strict anti-fabrication check: reject placeholder strings and headers
                if not raw_name or raw_name.lower().startswith('faculty_') or raw_name.lower() in ['staff', 'date', 'page', 'signature', 'name']:
                    continue
                
                date_val = duty_dict.get('date')
                if not date_val:
                    continue
                
                session_val = duty_dict.get('session') or ('Forenoon' if duty_dict.get('time') == 'M' else 'Afternoon')
                time_val = duty_dict.get('time') or ('M' if session_val.lower() == 'forenoon' else 'A')
                
                duties.append({
                    'faculty_name': raw_name,
                    'date': date_val,
                    'session': session_val,
                    'time': time_val,
                    'venue': duty_dict.get('venue') or '',
                    'exam_name': duty_dict.get('exam_name') or '',
                    'confidence': float(duty_dict.get('confidence', 0.88)),
                    'faculty_names': [raw_name]
                })
                
        except Exception as e:
            logger.error(f"Error during OCR extraction from recognized cells: {e}")
            return []
        
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