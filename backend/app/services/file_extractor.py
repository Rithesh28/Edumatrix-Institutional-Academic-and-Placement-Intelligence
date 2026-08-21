"""
File Extractor Service - Extract text from various file types
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class FileExtractor:
    """
    Extract text from various file types:
    - PDF (text-based): pdfplumber
    - PDF (scanned): OCR via pdf2image + Tesseract
    - DOCX: python-docx
    - DOC: textract or antiword
    - Images (JPG, PNG, JPEG): Tesseract OCR
    - TXT: Direct read
    """

    def __init__(self):
        self.supported_types = {
            ".pdf": self._extract_pdf,
            ".docx": self._extract_docx,
            ".doc": self._extract_doc,
            ".txt": self._extract_txt,
            ".jpg": self._extract_image,
            ".jpeg": self._extract_image,
            ".png": self._extract_image,
        }
        self._init_imports()

    def _init_imports(self):
        """Initialize optional imports"""
        self.has_pdfplumber = False
        self.has_python_docx = False
        self.has_textract = False
        self.has_ocr = False

        try:
            import pdfplumber
            self.pdfplumber = pdfplumber
            self.has_pdfplumber = True
        except ImportError:
            pass

        try:
            import docx
            self.docx = docx
            self.has_python_docx = True
        except ImportError:
            pass

        try:
            import textract
            self.textract = textract
            self.has_textract = True
        except ImportError:
            pass

        # Check for OCR service
        try:
            from .ocr_service import ocr_service
            self.ocr_service = ocr_service
            self.has_ocr = True
        except ImportError:
            pass

    def extract_text(self, file_path: str) -> str:
        """
        Extract text from any supported file type

        Args:
            file_path: Path to the file

        Returns:
            Extracted text as string
        """
        if not os.path.exists(file_path):
            return f"Error: File not found - {file_path}"

        ext = os.path.splitext(file_path)[1].lower()

        if ext not in self.supported_types:
            return f"Error: Unsupported file type - {ext}"

        try:
            return self.supported_types[ext](file_path)
        except Exception as e:
            logger.error(f"Extraction failed for {file_path}: {e}")
            return f"Extraction Error: {str(e)}"

    def _extract_pdf(self, file_path: str) -> str:
        """Extract text from PDF"""
        # First try pdfplumber (for text-based PDFs)
        if self.has_pdfplumber:
            try:
                text = ""
                with self.pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                if text.strip():
                    return text.strip()
            except Exception as e:
                logger.warning(f"pdfplumber extraction failed: {e}")

        # If pdfplumber fails or returns empty, try OCR (scanned PDF)
        if self.has_ocr:
            try:
                return self.ocr_service.extract_text_from_scanned_pdf(file_path)
            except Exception as e:
                logger.warning(f"OCR PDF extraction failed: {e}")

        return "Error: Could not extract text from PDF. It may be a scanned document."

    def _extract_docx(self, file_path: str) -> str:
        """Extract text from DOCX file"""
        if not self.has_python_docx:
            return "Error: python-docx not installed. Please install: pip install python-docx"

        try:
            doc = self.docx.Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
            return text.strip() if text else "No text found in DOCX"
        except Exception as e:
            logger.error(f"DOCX extraction failed: {e}")
            return f"DOCX Error: {str(e)}"

    def _extract_doc(self, file_path: str) -> str:
        """Extract text from DOC file using textract"""
        if self.has_textract:
            try:
                text = self.textract.process(file_path).decode("utf-8")
                return text.strip() if text else "No text found in DOC"
            except Exception as e:
                logger.warning(f"textract DOC extraction failed: {e}")

        # Fallback: Try antiword if available
        try:
            import subprocess
            result = subprocess.run(
                ["antiword", file_path],
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass

        return "Error: Could not extract text from DOC file. Please convert to DOCX or PDF."

    def _extract_txt(self, file_path: str) -> str:
        """Extract text from TXT file"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except UnicodeDecodeError:
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    return f.read().strip()
            except Exception as e:
                return f"TXT Error: {str(e)}"

    def _extract_image(self, file_path: str) -> str:
        """Extract text from image using OCR"""
        if not self.has_ocr:
            return "Error: OCR service not available. Please install Tesseract and pytesseract."

        try:
            return self.ocr_service.extract_text_from_image(file_path)
        except Exception as e:
            logger.error(f"Image OCR extraction failed: {e}")
            return f"Image OCR Error: {str(e)}"


# Singleton instance
file_extractor = FileExtractor()


# Utility function for quick access
def extract_text_from_file(file_path: str) -> str:
    """
    Quick utility to extract text from any file

    Args:
        file_path: Path to the file

    Returns:
        Extracted text as string
    """
    return file_extractor.extract_text(file_path)