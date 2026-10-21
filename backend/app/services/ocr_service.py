"""
OCR Service - Extract text from images using Tesseract
"""

import os
import pytesseract
from PIL import Image
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class OCRService:
    """Service for extracting text from images using Tesseract OCR"""

    def __init__(self):
        # Try to set Tesseract path for Windows
        possible_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                logger.info(f"Tesseract found at: {path}")
                break
        else:
            logger.warning("Tesseract not found. OCR will not work.")

    def extract_text_from_image(self, image_path: str) -> str:
        """
        Extract text from an image file
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Extracted text as string
        """
        try:
            if not os.path.exists(image_path):
                return f"Error: File not found - {image_path}"
            
            # Open image
            image = Image.open(image_path)
            
            # Extract text using Tesseract
            text = pytesseract.image_to_string(image)
            
            return text.strip()
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return f"OCR Error: {str(e)}"

    def extract_text_from_image_bytes(self, image_bytes: bytes) -> str:
        """
        Extract text from image bytes
        
        Args:
            image_bytes: Bytes of the image
            
        Returns:
            Extracted text as string
        """
        try:
            from io import BytesIO
            from PIL import ImageEnhance
            image = Image.open(BytesIO(image_bytes))
            
            # Preprocess if in color
            if image.mode not in ('L', '1'):
                image = image.convert('L')
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(1.8)
            
            # Upscale low-resolution images for optimal OCR character clarity
            w, h = image.size
            if w < 1600 or h < 1200:
                scale_factor = 2 if (w < 900 or h < 700) else 1.5
                image = image.resize((int(w * scale_factor), int(h * scale_factor)), Image.Resampling.LANCZOS)

            text = pytesseract.image_to_string(image)
            return text.strip()
        except Exception as e:
            logger.error(f"OCR extraction from bytes failed: {e}")
            return f"OCR Error: {str(e)}"

    def extract_ocr_data_from_image(self, image: Image.Image) -> Dict[str, Any]:
        """
        Extract detailed OCR data with bounding box coordinates and confidence
        using Tesseract image_to_data.
        """
        from pytesseract import Output
        from PIL import ImageEnhance

        processed = image
        if processed.mode not in ('L', '1'):
            processed = processed.convert('L')
            enhancer = ImageEnhance.Contrast(processed)
            processed = enhancer.enhance(1.8)

        # Upscale low-resolution images for optimal character clarity
        w, h = processed.size
        if w < 1600 or h < 1200:
            scale_factor = 2 if (w < 900 or h < 700) else 1.5
            processed = processed.resize((int(w * scale_factor), int(h * scale_factor)), Image.Resampling.LANCZOS)

        return pytesseract.image_to_data(processed, output_type=Output.DICT)

    def extract_ocr_data_from_image_bytes(self, image_bytes: bytes) -> Dict[str, Any]:
        """Extract Tesseract image_to_data dict from image bytes."""
        from io import BytesIO
        image = Image.open(BytesIO(image_bytes))
        return self.extract_ocr_data_from_image(image)

    def extract_ocr_data_pages_from_scanned_pdf_bytes(self, pdf_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Extract Tesseract image_to_data per page from scanned PDF bytes using pdf2image.
        """
        from pdf2image import convert_from_bytes
        if not pdf_bytes or len(pdf_bytes) == 0:
            return []
        images = convert_from_bytes(pdf_bytes)
        return [self.extract_ocr_data_from_image(img) for img in images]

    def extract_text_from_scanned_pdf(self, pdf_path: str) -> str:
        """
        Extract text from a scanned PDF (requires pdf2image)
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text as string
        """
        try:
            from pdf2image import convert_from_path
            
            if not os.path.exists(pdf_path):
                return f"Error: File not found - {pdf_path}"
            
            # Convert PDF pages to images
            images = convert_from_path(pdf_path)
            
            all_text = []
            for i, image in enumerate(images):
                text = pytesseract.image_to_string(image)
                all_text.append(f"--- Page {i+1} ---\n{text}")
            
            return "\n\n".join(all_text).strip()
        except ImportError:
            return "Error: pdf2image not installed. Please install: pip install pdf2image"
        except Exception as e:
            logger.error(f"Scanned PDF extraction failed: {e}")
            return f"Scanned PDF Error: {str(e)}"

    def extract_text_from_scanned_pdf_bytes(self, pdf_bytes: bytes) -> str:
        """
        Extract text from scanned PDF bytes using pdf2image and Tesseract OCR
        
        Args:
            pdf_bytes: Raw bytes of the PDF file
            
        Returns:
            Extracted text as string
        """
        try:
            from pdf2image import convert_from_bytes
            
            if not pdf_bytes or len(pdf_bytes) == 0:
                return "Error: PDF file bytes are empty."
            
            images = convert_from_bytes(pdf_bytes)
            if not images:
                return "Error: No rendered pages generated from PDF bytes."
            
            all_text = []
            for i, image in enumerate(images):
                text = pytesseract.image_to_string(image)
                all_text.append(f"--- Page {i+1} ---\n{text}")
            
            return "\n\n".join(all_text).strip()
        except ImportError:
            return "Error: pdf2image not installed. Please install: pip install pdf2image"
        except Exception as e:
            logger.error(f"Scanned PDF bytes extraction failed: {e}")
            return f"Scanned PDF Error: {str(e)}"


# Singleton instance
ocr_service = OCRService()