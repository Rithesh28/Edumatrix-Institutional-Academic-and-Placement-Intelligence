"""
Text Extractor Service

Extracts text from various file types for embedding generation.
Supports: PDF, DOCX, DOC, PPTX, PPT, XLSX, XLS, TXT, Images (OCR)
"""

import os
import logging
import tempfile
from typing import Optional, Dict, Any, List
from io import BytesIO

# PDF
import pdfplumber
import PyPDF2

# Word
try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# PowerPoint
try:
    from pptx import Presentation
    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False

# Excel
try:
    import openpyxl
    import pandas as pd
    XLSX_AVAILABLE = True
except ImportError:
    XLSX_AVAILABLE = False

# OCR
try:
    import pytesseract
    from PIL import Image
    import cv2
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

logger = logging.getLogger(__name__)


class TextExtractor:
    """
    Extract text from various file types.
    
    Supported formats:
    - PDF: pdfplumber, PyPDF2
    - DOCX: python-docx
    - PPTX: python-pptx
    - XLSX: openpyxl, pandas
    - Images: pytesseract (OCR)
    - TXT: Direct read
    """
    
    def __init__(self):
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Check which extractors are available."""
        self.available = {
            'pdf': True,  # pdfplumber is always available
            'docx': DOCX_AVAILABLE,
            'pptx': PPTX_AVAILABLE,
            'xlsx': XLSX_AVAILABLE,
            'ocr': OCR_AVAILABLE
        }
        logger.info(f"📋 Text extractor dependencies: {self.available}")
    
    def extract_text(self, file_path: str, content: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Extract text from a file.
        
        Args:
            file_path: Path to the file
            content: Optional file content as bytes (if file_path is not accessible)
            
        Returns:
            Dict with extracted text and metadata
        """
        ext = os.path.splitext(file_path)[1].lower()
        
        result = {
            'success': False,
            'text': '',
            'error': None,
            'extractor_used': None,
            'metadata': {}
        }
        
        try:
            if ext == '.pdf':
                return self._extract_pdf(file_path, content)
            elif ext in ['.docx', '.doc']:
                return self._extract_docx(file_path, content)
            elif ext in ['.pptx', '.ppt']:
                return self._extract_pptx(file_path, content)
            elif ext in ['.xlsx', '.xls']:
                return self._extract_xlsx(file_path, content)
            elif ext in ['.csv']:
                return self._extract_csv(file_path, content)
            elif ext in ['.txt']:
                return self._extract_txt(file_path, content)
            elif ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
                return self._extract_image(file_path, content)
            else:
                result['error'] = f"Unsupported file type: {ext}"
                return result
                
        except Exception as e:
            logger.error(f"❌ Text extraction failed for {file_path}: {str(e)}")
            result['error'] = str(e)
            return result
    
    def _get_content_bytes(self, file_path: str, content: Optional[bytes] = None) -> bytes:
        """Get file content as bytes."""
        if content is not None:
            return content
        with open(file_path, 'rb') as f:
            return f.read()
    
    def _extract_pdf(self, file_path: str, content: Optional[bytes] = None) -> Dict[str, Any]:
        """Extract text from PDF using pdfplumber (preferred) or PyPDF2."""
        result = {
            'success': False,
            'text': '',
            'error': None,
            'extractor_used': 'pdfplumber',
            'metadata': {'page_count': 0, 'hyperlinks': []}
        }
        
        try:
            # Try pdfplumber first (better for tables and text layout)
            if content:
                pdf_target = BytesIO(content)
            else:
                pdf_target = file_path
            
            with pdfplumber.open(pdf_target) as pdf:
                text_parts = []
                hyperlinks = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                    # Extract embedded PDF link annotations
                    if hasattr(page, 'hyperlinks') and page.hyperlinks:
                        for hl in page.hyperlinks:
                            if isinstance(hl, dict) and hl.get('uri'):
                                uri = str(hl['uri']).strip()
                                if uri.startswith(('http://', 'https://')):
                                    hyperlinks.append(uri)
                
                # Deduplicate hyperlinks
                hyperlinks = list(dict.fromkeys(hyperlinks))
                if hyperlinks:
                    text_parts.append("\n\n--- Document Hyperlinks ---\n" + "\n".join(hyperlinks))
                    result['metadata']['hyperlinks'] = hyperlinks

                result['text'] = '\n\n'.join(text_parts)
                result['metadata']['page_count'] = len(pdf.pages)
                result['success'] = True
                
                if result['text'].strip():
                    logger.info(f"📄 Extracted {len(result['text'])} chars and {len(hyperlinks)} hyperlinks from PDF (pdfplumber)")
                    return result
                else:
                    # Fallback to PyPDF2 if pdfplumber returns empty
                    logger.warning("pdfplumber returned empty text, trying PyPDF2...")
                    result = self._extract_pdf_pypdf2(file_path, content)
                    result['extractor_used'] = 'PyPDF2 (fallback)'
                    return result
                
        except Exception as e:
            logger.warning(f"pdfplumber failed: {str(e)}, trying PyPDF2...")
            return self._extract_pdf_pypdf2(file_path, content)
    
    def _extract_pdf_pypdf2(self, file_path: str, content: Optional[bytes] = None) -> Dict[str, Any]:
        """Extract text from PDF using PyPDF2 (fallback)."""
        result = {
            'success': False,
            'text': '',
            'error': None,
            'extractor_used': 'PyPDF2',
            'metadata': {'page_count': 0, 'hyperlinks': []}
        }
        
        try:
            if content:
                from io import BytesIO
                reader = PyPDF2.PdfReader(BytesIO(content))
            else:
                reader = PyPDF2.PdfReader(file_path)
            
            text_parts = []
            hyperlinks = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
                # Extract embedded link annotations in PyPDF2
                try:
                    if "/Annots" in page:
                        for annot in page["/Annots"]:
                            annot_obj = annot.get_object()
                            if "/A" in annot_obj and "/URI" in annot_obj["/A"]:
                                uri = str(annot_obj["/A"]["/URI"]).strip()
                                if uri.startswith(('http://', 'https://')):
                                    hyperlinks.append(uri)
                except Exception:
                    pass
            
            hyperlinks = list(dict.fromkeys(hyperlinks))
            if hyperlinks:
                text_parts.append("\n\n--- Document Hyperlinks ---\n" + "\n".join(hyperlinks))
                result['metadata']['hyperlinks'] = hyperlinks

            result['text'] = '\n\n'.join(text_parts)
            result['metadata']['page_count'] = len(reader.pages)
            result['success'] = True
            
            logger.info(f"📄 Extracted {len(result['text'])} chars and {len(hyperlinks)} hyperlinks from PDF (PyPDF2)")
            return result
            
        except Exception as e:
            result['error'] = str(e)
            return result
    
    def _extract_docx(self, file_path: str, content: Optional[bytes] = None) -> Dict[str, Any]:
        """Extract text from DOCX including tables and embedded hyperlinks."""
        result = {
            'success': False,
            'text': '',
            'error': None,
            'extractor_used': 'python-docx',
            'metadata': {'paragraph_count': 0, 'table_count': 0, 'hyperlinks': []}
        }
        
        if not DOCX_AVAILABLE:
            result['error'] = 'python-docx not available'
            return result
        
        try:
            if content:
                from io import BytesIO
                doc = docx.Document(BytesIO(content))
            else:
                doc = docx.Document(file_path)
            
            text_parts = []
            for paragraph in doc.paragraphs:
                if paragraph.text:
                    text_parts.append(paragraph.text)
            
            # Extract text from tables
            for table in doc.tables:
                for row in table.rows:
                    row_text = ' '.join([cell.text.strip() for cell in row.cells if cell.text.strip()])
                    if row_text:
                        text_parts.append(row_text)
            
            # Extract embedded hyperlinks from document relationships
            docx_links = []
            try:
                for rel in doc.part.rels.values():
                    rel_type = getattr(rel, 'reltype', '')
                    if rel_type and 'hyperlink' in rel_type.lower():
                        target = getattr(rel, 'target_ref', '')
                        if target and str(target).startswith(('http://', 'https://')):
                            docx_links.append(str(target).strip())
            except Exception as hl_err:
                logger.debug(f"DOCX hyperlink extraction notice: {hl_err}")

            docx_links = list(dict.fromkeys(docx_links))
            if docx_links:
                text_parts.append("\n\n--- Document Hyperlinks ---\n" + "\n".join(docx_links))
                result['metadata']['hyperlinks'] = docx_links

            result['text'] = '\n'.join(text_parts)
            result['metadata']['paragraph_count'] = len(doc.paragraphs)
            result['metadata']['table_count'] = len(doc.tables)
            result['success'] = True
            
            logger.info(f"📄 Extracted {len(result['text'])} chars and {len(docx_links)} hyperlinks from DOCX")
            return result
            
        except Exception as e:
            result['error'] = str(e)
            return result

    def _extract_csv(self, file_path: str, content: Optional[bytes] = None) -> Dict[str, Any]:
        """Extract text from CSV files."""
        result = {
            'success': False,
            'text': '',
            'error': None,
            'extractor_used': 'pandas/csv',
            'metadata': {'row_count': 0, 'columns': []}
        }
        
        try:
            import pandas as pd
            if content:
                from io import BytesIO
                df = pd.read_csv(BytesIO(content))
            else:
                df = pd.read_csv(file_path)
            
            headers = ' | '.join([str(col) for col in df.columns])
            lines = [f"Columns: {headers}"]
            for _, row in df.head(1000).iterrows():
                row_text = ' | '.join([str(val) if pd.notna(val) else '' for val in row])
                if row_text.strip():
                    lines.append(row_text)
            
            result['text'] = '\n'.join(lines)
            result['metadata']['row_count'] = len(df)
            result['metadata']['columns'] = [str(c) for c in df.columns]
            result['success'] = True
            logger.info(f"📄 Extracted {len(result['text'])} chars from CSV ({len(df)} rows)")
            return result
        except Exception as e:
            result['error'] = str(e)
            return result
    
    def _extract_pptx(self, file_path: str, content: Optional[bytes] = None) -> Dict[str, Any]:
        """Extract text from PPTX."""
        result = {
            'success': False,
            'text': '',
            'error': None,
            'extractor_used': 'python-pptx',
            'metadata': {'slide_count': 0}
        }
        
        if not PPTX_AVAILABLE:
            result['error'] = 'python-pptx not available'
            return result
        
        try:
            if content:
                from io import BytesIO
                prs = Presentation(BytesIO(content))
            else:
                prs = Presentation(file_path)
            
            text_parts = []
            for slide_num, slide in enumerate(prs.slides, 1):
                slide_text_parts = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text:
                        slide_text_parts.append(shape.text)
                    # Handle tables in slides
                    if hasattr(shape, "table"):
                        for row in shape.table.rows:
                            row_text = ' '.join([cell.text for cell in row.cells if cell.text])
                            if row_text:
                                slide_text_parts.append(row_text)
                
                if slide_text_parts:
                    slide_text = ' '.join(slide_text_parts)
                    text_parts.append(f"Slide {slide_num}: {slide_text}")
            
            result['text'] = '\n'.join(text_parts)
            result['metadata']['slide_count'] = len(prs.slides)
            result['success'] = True
            
            logger.info(f"📄 Extracted {len(result['text'])} chars from PPTX")
            return result
            
        except Exception as e:
            result['error'] = str(e)
            return result
    
    def _extract_xlsx(self, file_path: str, content: Optional[bytes] = None) -> Dict[str, Any]:
        """Extract text from XLSX."""
        result = {
            'success': False,
            'text': '',
            'error': None,
            'extractor_used': 'pandas/openpyxl',
            'metadata': {'sheet_count': 0}
        }
        
        if not XLSX_AVAILABLE:
            result['error'] = 'openpyxl/pandas not available'
            return result
        
        try:
            if content:
                from io import BytesIO
                df_dict = pd.read_excel(BytesIO(content), sheet_name=None, engine='openpyxl')
            else:
                df_dict = pd.read_excel(file_path, sheet_name=None, engine='openpyxl')
            
            text_parts = []
            for sheet_name, df in df_dict.items():
                # Convert to text representation
                sheet_text_parts = []
                
                # Add column headers
                headers = ' | '.join([str(col) for col in df.columns])
                sheet_text_parts.append(f"Sheet: {sheet_name}")
                sheet_text_parts.append(f"Columns: {headers}")
                
                # Add rows (limit to 1000 rows to avoid memory issues)
                for _, row in df.head(1000).iterrows():
                    row_text = ' | '.join([str(val) if pd.notna(val) else '' for val in row])
                    if row_text.strip():
                        sheet_text_parts.append(row_text)
                
                text_parts.append('\n'.join(sheet_text_parts))
            
            result['text'] = '\n\n'.join(text_parts)
            result['metadata']['sheet_count'] = len(df_dict)
            result['success'] = True
            
            logger.info(f"📄 Extracted {len(result['text'])} chars from XLSX")
            return result
            
        except Exception as e:
            result['error'] = str(e)
            return result
    
    def _extract_txt(self, file_path: str, content: Optional[bytes] = None) -> Dict[str, Any]:
        """Extract text from TXT."""
        result = {
            'success': False,
            'text': '',
            'error': None,
            'extractor_used': 'txt',
            'metadata': {}
        }
        
        try:
            if content:
                text = content.decode('utf-8', errors='ignore')
            else:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
            
            result['text'] = text
            result['success'] = True
            logger.info(f"📄 Extracted {len(result['text'])} chars from TXT")
            return result
            
        except Exception as e:
            result['error'] = str(e)
            return result
    
    def _extract_image(self, file_path: str, content: Optional[bytes] = None) -> Dict[str, Any]:
        """Extract text from image using OCR."""
        result = {
            'success': False,
            'text': '',
            'error': None,
            'extractor_used': 'pytesseract',
            'metadata': {}
        }
        
        if not OCR_AVAILABLE:
            result['error'] = 'OCR (pytesseract) not available'
            return result
        
        try:
            # Load image
            if content:
                from io import BytesIO
                image = Image.open(BytesIO(content))
            else:
                image = Image.open(file_path)
            
            # Preprocess image for better OCR
            image = self._preprocess_image(image)
            
            # Perform OCR
            custom_config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(image, config=custom_config)
            
            result['text'] = text.strip()
            result['metadata']['image_size'] = image.size
            result['success'] = True
            
            logger.info(f"📄 Extracted {len(result['text'])} chars from image")
            return result
            
        except Exception as e:
            result['error'] = str(e)
            return result
    
    def _preprocess_image(self, image):
        """Preprocess image for better OCR."""
        try:
            # Convert to grayscale
            if image.mode != 'L':
                image = image.convert('L')
            
            # Increase contrast
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0)
            
            # Apply threshold
            image = image.point(lambda x: 0 if x < 128 else 255, '1')
            
            return image
            
        except Exception as e:
            logger.warning(f"Image preprocessing failed: {str(e)}")
            return image
    
    def extract_text_for_embedding(self, file_path: str, content: Optional[bytes] = None) -> Optional[str]:
        """
        Extract text and clean it for embedding generation.
        
        Args:
            file_path: Path to the file
            content: Optional file content as bytes
            
        Returns:
            Cleaned text string or None if extraction failed
        """
        result = self.extract_text(file_path, content)
        
        if not result['success'] or not result['text']:
            return None
        
        # Clean text
        text = result['text']
        
        # Remove excessive whitespace
        import re
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Remove very short texts (likely garbage)
        if len(text) < 20:
            return None
        
        return text
    
    def extract_metadata(self, file_path: str, content: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Extract file metadata for search.
        
        Args:
            file_path: Path to the file
            content: Optional file content as bytes
            
        Returns:
            Dictionary with file metadata
        """
        ext = os.path.splitext(file_path)[1].lower()
        metadata = {
            'extension': ext,
            'extractor_used': None,
            'has_text': False
        }
        
        result = self.extract_text(file_path, content)
        if result['success']:
            metadata['extractor_used'] = result.get('extractor_used')
            metadata['has_text'] = bool(result.get('text', ''))
            metadata.update(result.get('metadata', {}))
        
        return metadata


# Singleton instance
text_extractor = TextExtractor()