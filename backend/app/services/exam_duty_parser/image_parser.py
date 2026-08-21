"""
Image Parser for Exam Duty Extraction

This module handles parsing of images and scanned documents for exam duty schedules.
Supports multiple OCR backends:
1. OCR.space (Free, 500/day) - DEFAULT
2. Tesseract (Local, 100% free) - FALLBACK

Features:
- OpenCV-based image preprocessing (if available)
- CLAHE contrast enhancement for complex tables
- Adaptive thresholding for better text detection
- Multiple OCR engine fallbacks
- Table detection from OCR text
- Timeout protection
"""
from __future__ import annotations

import os
import io
import logging
import time
import re
from typing import Dict, Any, List, Optional
try:
    from PIL import Image, ImageEnhance
    PIL_AVAILABLE = True
except ImportError:
    Image = None
    ImageEnhance = None
    PIL_AVAILABLE = False

try:
    import pdf2image
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    requests = None
    REQUESTS_AVAILABLE = False

from .base_parser import BaseParser

logger = logging.getLogger(__name__)

# Check if OpenCV is available
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
    logger.info("OpenCV (cv2) is available")
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("OpenCV (cv2) is not available. Install opencv-python-headless for better image preprocessing.")


class ImageParser(BaseParser):
    """
    Parser for images and scanned documents with multiple OCR backends.
    
    Features:
    - OpenCV-based image preprocessing (if available)
    - OCR.space API (free, 500 requests/day)
    - Tesseract fallback (local, 100% free)
    - Table detection from OCR text
    - Timeout protection
    """
    
    # OCR.space API Key (FREE, 500/day)
    OCR_SPACE_API_KEY = "K82855031688957"
    
    def __init__(self, file_path: str):
        super().__init__(file_path)
        self._image = None
        self._ocr_text = ""
        self._preprocessed_image = None
        self._processing_time = 0
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse the image and return structured data.
        
        Returns:
            Dict containing parsed data
        """
        start_time = time.time()
        logger.info(f"Starting parse for: {self.file_path}")
        
        try:
            # Step 1: Load image
            logger.info("Loading image...")
            image = self._load_image()
            
            # Step 2: Preprocess image for better OCR
            logger.info("Preprocessing image...")
            processed_image = self._preprocess_image(image)
            self._preprocessed_image = processed_image
            
            # Step 3: Convert to bytes
            image_bytes = self._image_to_bytes(processed_image)
            logger.info(f"Image size: {len(image_bytes)} bytes")
            
            # Step 4: Try OCR.space with multiple engines
            logger.info("Trying OCR.space API...")
            ocr_text = self._perform_ocr_space(image_bytes)
            
            # Step 5: If OCR.space fails or returns garbage, fallback to Tesseract
            if not ocr_text or len(ocr_text.strip()) < 20:
                logger.warning("OCR.space returned insufficient text, falling back to Tesseract...")
                ocr_text = self._perform_tesseract_ocr(processed_image)
            
            self._ocr_text = ocr_text
            logger.info(f"OCR text extracted: {len(ocr_text)} characters")
            
            # Step 6: Detect tables from OCR text
            tables = self._detect_tables(ocr_text)
            logger.info(f"Detected {len(tables)} tables")
            
            self._processing_time = time.time() - start_time
            logger.info(f"Parse completed in {self._processing_time:.2f} seconds")
            
            return {
                'raw_text': ocr_text,
                'tables': tables,
                'metadata': self.get_metadata(),
                'file_type': 'image',
                'ocr_source': 'ocr.space' if ocr_text and len(ocr_text) > 50 else 'tesseract',
                'processing_time': self._processing_time
            }
            
        except Exception as e:
            logger.error(f"Image parsing failed: {str(e)}")
            return self._fallback_ocr()
    
    # In image_parser.py, improve preprocessing

    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """Preprocess image for better OCR with VTU tables."""
        import cv2
        import numpy as np
        
        # Convert to grayscale
        if image.mode != 'L':
            image = image.convert('L')
        
        # Resize for better OCR
        if max(image.size) < 1500:
            ratio = 2500 / max(image.size)
            new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Convert to numpy
        img_np = np.array(image)
        
        # Apply CLAHE (contrast enhancement)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        img_np = clahe.apply(img_np)
        
        # Apply adaptive thresholding
        img_np = cv2.adaptiveThreshold(
            img_np, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 15, 3
        )
        
        return Image.fromarray(img_np)
    
    def _perform_ocr_space(self, image_bytes: bytes) -> str:
        """
        Use OCR.space API with multiple engine fallbacks.
        """
        try:
            files = {
                'file': ('image.png', image_bytes, 'image/png')
            }
            
            # Try multiple OCR engines
            engines = [3, 1, 2]  # 3 = Best for complex layouts, 1 = Fast, 2 = Standard
            
            for engine in engines:
                try:
                    data = {
                        'apikey': self.OCR_SPACE_API_KEY,
                        'language': 'eng',
                        'isTable': True,
                        'detectOrientation': True,
                        'scale': True,
                        'OCREngine': engine,
                        'filetype': 'PNG',
                    }
                    
                    logger.info(f"Trying OCR.space with Engine {engine}...")
                    
                    response = requests.post(
                        'https://api.ocr.space/parse/image',
                        files=files,
                        data=data,
                        timeout=30
                    )
                    
                    logger.info(f"Response status code: {response.status_code}")
                    
                    if response.status_code == 200:
                        result = response.json()
                        
                        if result.get('IsErroredOnProcessing'):
                            error_msg = result.get('ErrorMessage', ['Unknown error'])[0]
                            logger.warning(f"Engine {engine} error: {error_msg}")
                            continue
                        
                        if result.get('ParsedResults'):
                            text = result['ParsedResults'][0].get('ParsedText', '')
                            if text and len(text.strip()) > 50:
                                logger.info(f"OCR.space Engine {engine} extracted {len(text)} characters")
                                return text.strip()
                            elif text:
                                logger.info(f"OCR.space Engine {engine} extracted {len(text)} characters (short)")
                                return text.strip()
                except Exception as e:
                    logger.warning(f"Engine {engine} failed: {str(e)}")
                    continue
            
            return ""
            
        except Exception as e:
            logger.error(f"OCR.space failed: {str(e)}")
            return ""
    
    def _perform_tesseract_ocr(self, image: Image.Image) -> str:
        """Fallback to Tesseract OCR."""
        logger.info("Using Tesseract OCR fallback...")
        
        try:
            import pytesseract
            
            # Tesseract config optimized for tables
            config = '--psm 6 --oem 3 -c tessedit_do_invert=0'
            
            # If OpenCV is available, use it for preprocessing
            if CV2_AVAILABLE:
                try:
                    img_np = np.array(image)
                    img_np = cv2.adaptiveThreshold(
                        img_np, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                        cv2.THRESH_BINARY, 15, 3
                    )
                    image = Image.fromarray(img_np)
                except Exception as e:
                    logger.warning(f"OpenCV preprocessing for Tesseract failed: {str(e)}")
            
            text = pytesseract.image_to_string(image, config=config)
            logger.info(f"Tesseract extracted {len(text)} characters")
            return text.strip()
            
        except ImportError:
            logger.error("Tesseract (pytesseract) not installed")
            return ""
        except Exception as e:
            logger.error(f"Tesseract failed: {str(e)}")
            return ""
    
    def _fallback_ocr(self) -> Dict[str, Any]:
        """Fallback when all OCR methods fail."""
        logger.warning("All OCR methods failed, returning empty result")
        return {
            'raw_text': '',
            'tables': [],
            'metadata': self.get_metadata(),
            'file_type': 'image',
            'ocr_source': 'failed',
            'error': 'OCR failed'
        }
    
    def _load_image(self) -> Image.Image:
        """Load image from file path."""
        ext = self.get_file_extension().lower()
        logger.info(f"Loading file with extension: {ext}")
        
        if ext == '.pdf':
            logger.info("Converting PDF to image...")
            try:
                images = pdf2image.convert_from_path(
                    self.file_path,
                    first_page=1,
                    last_page=1,
                    dpi=150
                )
                if images:
                    logger.info("PDF converted successfully")
                    return images[0]
                raise Exception("Failed to convert PDF to image")
            except Exception as e:
                raise Exception(f"PDF to image conversion failed: {str(e)}")
        
        try:
            return Image.open(self.file_path)
        except Exception as e:
            raise Exception(f"Failed to load image: {str(e)}")
    
    def _image_to_bytes(self, image: Image.Image) -> bytes:
        """Convert PIL Image to bytes for API."""
        img_bytes = io.BytesIO()
        
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize if too large
        if image.size[0] > 3000 or image.size[1] > 3000:
            ratio = min(3000 / image.size[0], 3000 / image.size[1])
            new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            logger.info(f"Image resized to: {new_size}")
        
        image.save(img_bytes, format='PNG', optimize=True)
        return img_bytes.getvalue()
    
    def extract_text(self) -> str:
        """Extract text using available OCR."""
        try:
            image = self._load_image()
            processed = self._preprocess_image(image)
            image_bytes = self._image_to_bytes(processed)
            
            # Try OCR.space first
            text = self._perform_ocr_space(image_bytes)
            if text and len(text.strip()) > 50:
                return text
            
            # Fallback to Tesseract
            return self._perform_tesseract_ocr(processed)
            
        except Exception as e:
            logger.error(f"Text extraction failed: {str(e)}")
            return ""
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get image metadata."""
        try:
            image = self._load_image()
            return {
                'file_name': os.path.basename(self.file_path),
                'file_size': self.get_file_size(),
                'file_type': 'image',
                'width': image.width,
                'height': image.height,
                'mode': image.mode,
                'format': image.format
            }
        except Exception:
            return {
                'file_name': os.path.basename(self.file_path),
                'file_size': self.get_file_size(),
                'file_type': 'image',
                'error': 'Could not read metadata'
            }
    
    def _detect_tables(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect tables in OCR text.
        
        Returns:
            List of detected tables with structure
        """
        tables = []
        
        if not text:
            return tables
        
        lines = text.split('\n')
        lines = [line.strip() for line in lines if line.strip()]
        
        if len(lines) < 3:
            return tables
        
        current_table = []
        in_table = False
        
        for line in lines:
            # Check for table indicators
            has_pipe = '|' in line
            has_multiple_spaces = len(line.split()) > 3 and '  ' in line
            has_tabs = '\t' in line
            
            if has_pipe or has_multiple_spaces or has_tabs:
                in_table = True
                cells = self._parse_table_row(line)
                if cells and len(cells) > 1:
                    current_table.append(cells)
            else:
                if in_table and len(current_table) > 1:
                    tables.append({
                        'rows': current_table,
                        'row_count': len(current_table),
                        'col_count': max(len(row) for row in current_table) if current_table else 0
                    })
                current_table = []
                in_table = False
        
        if in_table and len(current_table) > 1:
            tables.append({
                'rows': current_table,
                'row_count': len(current_table),
                'col_count': max(len(row) for row in current_table) if current_table else 0
            })
        
        return tables
    
    def _parse_table_row(self, row: str) -> List[str]:
        """Parse a table row into cells."""
        if '|' in row:
            cells = [cell.strip() for cell in row.split('|')]
            if cells and not cells[0]:
                cells = cells[1:]
            if cells and not cells[-1]:
                cells = cells[:-1]
            return cells
        
        if '\t' in row:
            return [cell.strip() for cell in row.split('\t')]
        
        if re.search(r' {3,}', row):
            cells = re.split(r' {2,}', row)
            return [cell.strip() for cell in cells if cell.strip()]
        
        return [row]