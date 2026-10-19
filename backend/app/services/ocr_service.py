"""
OCR Service - Extract text from images using Tesseract
"""

import os
import pytesseract
from PIL import Image
import logging

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
            image = Image.open(BytesIO(image_bytes))
            text = pytesseract.image_to_string(image)
            return text.strip()
        except Exception as e:
            logger.error(f"OCR extraction from bytes failed: {e}")
            return f"OCR Error: {str(e)}"

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
        Extract text from scanned PDF bytes using pdf2image and Tesseract

        Args:
            pdf_bytes: Raw bytes of the scanned PDF

        Returns:
            Extracted text as string, or error string starting with 'Scanned PDF Error:'
        """
        try:
            from pdf2image import convert_from_bytes

            if not pdf_bytes:
                return "Error: Empty PDF bytes"

            images = convert_from_bytes(pdf_bytes)
            if not images:
                return "Error: No pages could be converted from PDF"

            all_text = []
            for i, image in enumerate(images):
                text = pytesseract.image_to_string(image)
                if text and text.strip():
                    all_text.append(f"--- Page {i+1} ---\n{text.strip()}")

            return "\n\n".join(all_text).strip()
        except ImportError:
            return "Error: pdf2image not installed. Please install: pip install pdf2image"
        except Exception as e:
            logger.error(f"Scanned PDF extraction from bytes failed: {e}")
            return f"Scanned PDF Error: {str(e)}"



# Singleton instance
ocr_service = OCRService()