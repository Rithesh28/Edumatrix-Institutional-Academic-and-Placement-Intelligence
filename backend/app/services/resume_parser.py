"""
Resume Parser Service with LayoutLMv3 Lazy Loading
"""

import os
import re
import logging
import tempfile
from typing import Dict, Any, List, Optional
from io import BytesIO

# PDF processing
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

# DOCX processing
try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# OCR
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    import pdf2image
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

# NLP
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

# LayoutLMv3 - FIXED IMPORT
from ..ml.layoutlmv3.service import layoutlmv3_service

logger = logging.getLogger(__name__)


class ResumeParser:
    # ... rest of the class remains the same ...
    """
    Resume parser service with LayoutLMv3 integration.
    
    Pipeline:
    1. Extract text (pdfplumber/python-docx/Tesseract)
    2. Initial entity extraction (spaCy + regex)
    3. Layout verification (LayoutLMv3)
    4. Final entity output
    """
    
    def __init__(self):
        self.nlp = None
        self._load_spacy_model()
        ENABLE_LAYOUTLMV3 = os.getenv("ENABLE_LAYOUTLMV3", "false").lower() in ["true", "1", "yes"]
        self.layoutlmv3_available = ENABLE_LAYOUTLMV3 and layoutlmv3_service.is_available()
        
        if self.layoutlmv3_available:
            logger.info("✅ LayoutLMv3 integration enabled")
        else:
            logger.info("⚡ Fast NLP/Regex resume parsing engine active (<0.2s processing)")
    
    def _load_spacy_model(self):
        """Load spaCy model for NER."""
        if SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load("en_core_web_sm")
                logger.info("✅ spaCy model loaded successfully")
            except OSError:
                try:
                    self.nlp = spacy.load("en_core_web_trf")
                    logger.info("✅ spaCy transformer model loaded")
                except OSError:
                    logger.warning("⚠️ spaCy model not found")
                    self.nlp = None
    
    def is_available(self) -> bool:
        """Check if parser is available."""
        return self.nlp is not None
    
    def parse_resume(self, file_path: str, content: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Parse a resume file with LayoutLMv3 verification.
        
        Args:
            file_path: Path to the file
            content: Optional file content as bytes
            
        Returns:
            Dict with extracted text, entities, and metadata
        """
        result = {
            'success': False,
            'text': '',
            'entities': {},
            'error': None,
            'file_type': None,
            'extractor_used': None,
            'layoutlmv3_used': False
        }
        
        try:
            # Determine file type
            ext = os.path.splitext(file_path)[1].lower()
            
            # Extract text based on file type
            if ext == '.pdf':
                result['file_type'] = 'pdf'
                text, extractor_used, warning, extraction_status = self._extract_from_pdf(
                    file_path, content, return_metadata=True
                )
                result['extractor_used'] = extractor_used
                result['warning'] = warning
                result['extraction_status'] = extraction_status
            elif ext in ['.docx', '.doc']:
                result['file_type'] = 'docx'
                text = self._extract_from_docx(file_path, content)
                result['extractor_used'] = 'python-docx'
                result['extraction_status'] = 'SUCCESS' if (text and len(text.strip()) >= 10) else 'EMPTY_TEXT'
            elif ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
                result['file_type'] = 'image'
                text = self._extract_from_image(file_path, content)
                result['extractor_used'] = 'tesseract'
                result['extraction_status'] = 'SUCCESS' if (text and len(text.strip()) >= 10) else 'EMPTY_TEXT'
            elif ext == '.txt':
                result['file_type'] = 'text'
                text = content.decode('utf-8', errors='ignore') if content else (open(file_path, 'r', errors='ignore').read() if os.path.exists(file_path) else '')
                result['extractor_used'] = 'text'
                result['extraction_status'] = 'SUCCESS' if (text and len(text.strip()) >= 10) else 'EMPTY_TEXT'
            else:
                result['error'] = f"Unsupported file type: {ext}"
                result['extraction_status'] = 'UNSUPPORTED_FORMAT'
                return result
            
            if not text or len(text.strip()) < 10:
                result['success'] = False
                if result.get('extraction_status') == 'SCANNED_PDF_NO_TEXT':
                    result['error'] = result.get('warning') or "PDF appears to be scanned or image-based, but readable text could not be extracted (fewer than 20 characters). Please provide a text-based PDF or higher resolution document."
                elif result.get('warning'):
                    result['error'] = result['warning']
                else:
                    result['error'] = "No text could be extracted from the file"
                return result
            
            result['text'] = text
            
            # Extract entities with spaCy
            if self.is_available():
                entities = self._extract_entities(text)
            else:
                entities = self._extract_entities_regex(text)
            
            # 🔥 NEW: Verify with LayoutLMv3
            if self.layoutlmv3_available:
                logger.info("🔍 Verifying entities with LayoutLMv3...")
                
                # Save content to temp file if we have content
                temp_file_path = file_path
                if content:
                    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                        tmp.write(content)
                        temp_file_path = tmp.name
                
                try:
                    verified_entities = layoutlmv3_service.understand_resume(
                        temp_file_path, 
                        entities
                    )
                    entities = verified_entities
                    result['layoutlmv3_used'] = True
                    logger.info("✅ LayoutLMv3 verification complete")
                except Exception as e:
                    logger.error(f"❌ LayoutLMv3 verification failed: {str(e)}")
                
                # Clean up temp file
                if content and os.path.exists(temp_file_path):
                    try:
                        os.unlink(temp_file_path)
                    except:
                        pass
            
            result['entities'] = entities
            result['success'] = True
            
        except Exception as e:
            logger.error(f"❌ Resume parsing failed: {str(e)}", exc_info=True)
            result['error'] = str(e)
            result['extraction_status'] = 'FAILED'
        
        return result
    
    def _extract_from_pdf_ocr(self, file_path: str, content: Optional[bytes] = None, max_pages: int = 5) -> str:
        """
        Fallback OCR extraction for scanned or image-based PDFs.
        Converts PDF pages to images using pdf2image and performs OCR with pytesseract.
        """
        if not (OCR_AVAILABLE and PDF2IMAGE_AVAILABLE):
            logger.warning("OCR (pytesseract) or pdf2image not available for scanned PDF fallback")
            return ""
        
        try:
            if content:
                images = pdf2image.convert_from_bytes(content, first_page=1, last_page=max_pages)
            elif file_path and os.path.exists(file_path):
                images = pdf2image.convert_from_path(file_path, first_page=1, last_page=max_pages)
            else:
                return ""
            
            ocr_text_parts = []
            for img in images:
                processed = self._preprocess_image(img)
                custom_config = r'--oem 3 --psm 6'
                txt = pytesseract.image_to_string(processed, config=custom_config)
                if txt and txt.strip():
                    ocr_text_parts.append(txt.strip())
            
            return "\n\n".join(ocr_text_parts).strip()
        except Exception as e:
            logger.warning(f"Scanned PDF OCR fallback failed: {str(e)}")
            return ""

    def _extract_from_pdf(self, file_path: str, content: Optional[bytes] = None, return_metadata: bool = False):
        """
        Extract text from PDF using pdfplumber, PyPDF2, or OCR fallback for scanned PDFs.
        Returns:
            str if return_metadata=False
            (text, extractor_used, warning, extraction_status) if return_metadata=True
        """
        text_parts = []
        page_count = 0
        is_empty_or_corrupt = False
        
        try:
            # 1. Try pdfplumber
            if PDFPLUMBER_AVAILABLE:
                try:
                    pdf_input = BytesIO(content) if content else file_path
                    with pdfplumber.open(pdf_input) as pdf:
                        page_count = len(pdf.pages)
                        if page_count == 0:
                            is_empty_or_corrupt = True
                        for page in pdf.pages:
                            page_text = page.extract_text()
                            if page_text:
                                text_parts.append(page_text)
                            
                            # Extract tables too
                            tables = page.extract_tables()
                            for table in tables:
                                for row in table:
                                    row_text = ' '.join([str(cell) if cell else '' for cell in row])
                                    if row_text.strip():
                                        text_parts.append(row_text)
                except Exception as e:
                    logger.warning(f"pdfplumber extraction warning: {str(e)}")
            
            raw_text = '\n\n'.join(text_parts).strip()
            if len(raw_text) >= 20:
                if return_metadata:
                    return raw_text, 'pdfplumber', None, 'SUCCESS'
                return raw_text
            
            # 2. Fallback to PyPDF2 if fewer than 20 characters
            if PYPDF2_AVAILABLE:
                try:
                    pdf_input = BytesIO(content) if content else file_path
                    reader = PyPDF2.PdfReader(pdf_input)
                    if page_count == 0:
                        page_count = len(reader.pages)
                    for page in reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)
                except Exception as e:
                    logger.warning(f"PyPDF2 extraction warning: {str(e)}")
            
            raw_text = '\n\n'.join(text_parts).strip()
            if len(raw_text) >= 20:
                if return_metadata:
                    return raw_text, 'PyPDF2', None, 'SUCCESS'
                return raw_text

            # 3. Detect scanned / image-based PDF (< 20 characters extracted)
            logger.info("PDF yielded fewer than 20 characters from text streams; attempting OCR fallback for scanned document...")
            ocr_text = self._extract_from_pdf_ocr(file_path, content)
            if len(ocr_text.strip()) >= 20:
                warning_msg = "Scanned/image-based PDF detected; extracted text using OCR fallback."
                logger.info(f"✅ {warning_msg}")
                if return_metadata:
                    return ocr_text.strip(), 'tesseract_ocr', warning_msg, 'OCR_FALLBACK'
                return ocr_text.strip()
            
            # 4. If OCR failed or produced < 20 characters
            if is_empty_or_corrupt or (content is not None and len(content) == 0):
                err_msg = "Empty or corrupted PDF file"
                if return_metadata:
                    return '', 'none', err_msg, 'FAILED'
                return ''
            
            warning_msg = "PDF appears to be scanned or image-based, but readable text could not be extracted (fewer than 20 characters). Please provide a text-based PDF or high-resolution document."
            if return_metadata:
                return '', 'none', warning_msg, 'SCANNED_PDF_NO_TEXT'
            return ''
            
        except Exception as e:
            logger.warning(f"PDF extraction failed: {str(e)}")
            if return_metadata:
                return '', 'none', f"PDF extraction failed: {str(e)}", 'FAILED'
            return ''
    
    def _extract_from_docx(self, file_path: str, content: Optional[bytes] = None) -> str:
        """Extract text from DOCX."""
        if not DOCX_AVAILABLE:
            logger.warning("python-docx not available")
            return ''
        
        try:
            if content:
                doc = docx.Document(BytesIO(content))
            else:
                doc = docx.Document(file_path)
            
            text_parts = []
            
            # Extract paragraphs
            for para in doc.paragraphs:
                if para.text:
                    text_parts.append(para.text)
            
            # Extract tables
            for table in doc.tables:
                for row in table.rows:
                    row_text = ' '.join([cell.text for cell in row.cells if cell.text])
                    if row_text:
                        text_parts.append(row_text)
            
            return '\n'.join(text_parts)
            
        except Exception as e:
            logger.warning(f"DOCX extraction failed: {str(e)}")
            return ''
    
    def _extract_from_image(self, file_path: str, content: Optional[bytes] = None) -> str:
        """Extract text from image using OCR."""
        if not OCR_AVAILABLE:
            logger.warning("OCR not available")
            return ''
        
        try:
            if content:
                image = Image.open(BytesIO(content))
            else:
                image = Image.open(file_path)
            
            # Preprocess image for better OCR
            image = self._preprocess_image(image)
            
            # Perform OCR
            custom_config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(image, config=custom_config)
            
            return text.strip()
            
        except Exception as e:
            logger.warning(f"Image OCR failed: {str(e)}")
            return ''
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """Preprocess image for better OCR."""
        try:
            # Convert to grayscale
            if image.mode != 'L':
                image = image.convert('L')
            
            # Increase contrast
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0)
            
            return image
        except Exception:
            return image
    
    def _extract_entities(self, text: str) -> Dict[str, Any]:
        """Extract all resume entities (skills, education, experience, projects, certs)."""
        return self._extract_entities_regex(text)
    
    def _get_skill_keywords(self) -> List[str]:
        """Get list of common skill keywords."""
        return [
            'python', 'java', 'sql', 'c++', 'c#', 'javascript', 'html', 'css',
            'react', 'react native', 'angular', 'vue', 'django', 'flask', 'fastapi', 'node', 'express',
            'machine learning', 'deep learning', 'nlp', 'ai', 'tensorflow',
            'pytorch', 'scikit-learn', 'pandas', 'numpy', 'matplotlib', 'seaborn',
            'git', 'github', 'docker', 'kubernetes', 'aws', 'azure', 'gcp',
            'linux', 'bash', 'mongodb', 'postgresql', 'mysql', 'redis', 'sqlite',
            'typescript', 'go', 'rust', 'swift', 'kotlin', 'php', 'ruby',
            'rest api', 'graphql', 'tailwind', 'bootstrap', 'nextjs', 'ci/cd',
            'data structures', 'algorithms', 'agile', 'scrum', 'jira',
            'spring boot', 'kafka', 'hadoop', 'spark', 'tableau', 'power bi'
        ]
    
    def _extract_entities_regex(self, text: str) -> Dict[str, Any]:
        """Extract comprehensive entities using regex & semantic pattern matching."""
        entities = {
            'name': '',
            'email': '',
            'phone': '',
            'skills': [],
            'education': [],
            'experience': [],
            'projects': [],
            'certifications': [],
            'companies': [],
            'links': [],
            'cgpa': None
        }
        
        try:
            # 1. Extract email
            email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            if email_match:
                entities['email'] = email_match.group()
            
            # 2. Extract phone
            phone_match = re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', text)
            if phone_match:
                entities['phone'] = phone_match.group().strip()
            
            # 3. Extract candidate name (first clean line)
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            for line in lines[:6]:
                if 2 < len(line) < 35 and not re.search(r'[@\d:/\\]|resume|curriculum|vitae', line, re.IGNORECASE):
                    entities['name'] = line
                    break
            
            # 4. Extract links (GitHub / LinkedIn / Portfolio)
            github_match = re.search(r'(https?://)?(www\.)?github\.com/[a-zA-Z0-9_-]+', text, re.IGNORECASE)
            linkedin_match = re.search(r'(https?://)?(www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+', text, re.IGNORECASE)
            if github_match:
                entities['links'].append(github_match.group())
            if linkedin_match:
                entities['links'].append(linkedin_match.group())
            
            # 5. Extract CGPA / Percentage
            cgpa_match = re.search(r'(?:cgpa|gpa)[\s:]*([0-9]+\.?[0-9]*)\s*(?:/\s*10)?', text, re.IGNORECASE)
            if cgpa_match:
                try:
                    entities['cgpa'] = float(cgpa_match.group(1))
                except:
                    pass
            
            # 6. Extract skills
            skill_keywords = self._get_skill_keywords()
            found_skills = []
            text_lower = text.lower()
            for skill in skill_keywords:
                pattern = r'\b' + re.escape(skill) + r'\b'
                if re.search(pattern, text_lower):
                    found_skills.append(skill.title() if len(skill) > 3 else skill.upper())
            
            entities['skills'] = list(dict.fromkeys(found_skills))[:30]
            
            # 7. Extract education
            education_list = []
            degree_matches = re.findall(r'(B\.?Tech|B\.?E\.?|Bachelor|M\.?Tech|M\.?E\.?|Master|PhD|MCA|MBA|B\.?Sc|M\.?Sc|BCA)', text, re.IGNORECASE)
            branch_matches = re.findall(r'(Computer Science|Information Science|Information Technology|Electronics|Electrical|Mechanical|Civil|Data Science|Artificial Intelligence)', text, re.IGNORECASE)
            
            if degree_matches:
                for deg in set(degree_matches):
                    deg_name = str(deg).strip()
                    if branch_matches:
                        deg_name += f" ({branch_matches[0]})"
                    education_list.append({"degree": deg_name, "cgpa": entities.get('cgpa')})
            elif branch_matches:
                education_list.append({"degree": f"Degree in {branch_matches[0]}", "cgpa": entities.get('cgpa')})
            
            entities['education'] = education_list
            
            # 8. Extract experience / internships
            experience_list = []
            exp_patterns = [
                r'(Intern|Software Engineer|Developer|Data Analyst|Research Assistant|Trainee|Associate|Frontend Developer|Backend Developer|Full Stack Developer)',
                r'(?:at|@)\s+([A-Z][a-zA-Z0-9\s]{2,25}(?:Inc|LLC|Ltd|Technologies|Solutions|Corp|Company)?)'
            ]
            exp_matches = re.findall(r'(?:Work Experience|Experience|Internship|Professional Experience)([\s\S]{1,400}?)(?:Projects|Education|Skills|Certifications|$)', text, re.IGNORECASE)
            if exp_matches:
                exp_text = exp_matches[0]
                roles = re.findall(r'(Intern|Engineer|Developer|Analyst|Lead|Assistant)', exp_text, re.IGNORECASE)
                for r in set(roles):
                    experience_list.append({"title": r.strip() + " Role", "description": exp_text[:120].strip()})
            else:
                simple_roles = re.findall(r'(Software Engineer|Intern|Data Analyst|Web Developer|Full Stack Developer)', text, re.IGNORECASE)
                for r in set(simple_roles):
                    experience_list.append({"title": r.strip()})
            
            entities['experience'] = experience_list
            
            # 9. Extract projects
            projects_list = []
            proj_section = re.findall(r'(?:Projects|Academic Projects|Key Projects)([\s\S]{1,600}?)(?:Experience|Education|Skills|Certifications|$)', text, re.IGNORECASE)
            if proj_section:
                proj_lines = [l.strip() for l in proj_section[0].split('\n') if len(l.strip()) > 5]
                for l in proj_lines[:4]:
                    if not re.search(r'^(github|http|tech|technologies)', l, re.IGNORECASE):
                        projects_list.append({"name": l[:40], "description": l})
            else:
                proj_matches = re.findall(r'(?:Project|System|Platform|Application):\s*([^\n\.]+)', text, re.IGNORECASE)
                for m in proj_matches[:4]:
                    projects_list.append({"name": m.strip()})
            
            entities['projects'] = projects_list
            
            # 10. Extract certifications
            cert_list = []
            cert_matches = re.findall(r'(AWS|Azure|Google Cloud|Oracle|IBM|Cisco|CCNA|Certified|Coursera|HackerRank|Udemy|CompTIA|PMP|Scrum)', text, re.IGNORECASE)
            for c in set(cert_matches):
                cert_list.append({"name": f"{c.upper() if len(c) <= 4 else c.title()} Certification"})
            
            entities['certifications'] = cert_list
            
        except Exception as e:
            logger.error(f"Regex entity extraction failed: {str(e)}")
        
        return entities


# Singleton instance
resume_parser = ResumeParser()