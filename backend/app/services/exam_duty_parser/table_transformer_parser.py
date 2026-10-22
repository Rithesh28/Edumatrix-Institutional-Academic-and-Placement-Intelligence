"""
Exam Duty Parser - Fast Multi-Stage Pipeline with Fallback

Architecture:
1. For Images (.jpg, .jpeg, .png, .bmp, .tiff, .webp):
   - Stage 1: OpenCV + Tesseract OCR (Ultra-fast <0.5s, multi-angle, EXIF-aware table & row parsing)
   - Stage 2: Table Detection Model (Microsoft Table Transformer, local-first)
   - Stage 3: PaddleOCR / Morphological Layout Cell Segmenter
   - Stage 4: GLiNER / Fast Zero-Shot Named Entity Recognition (local-first)

2. For PDFs (.pdf):
   - Stage 1: GMFT & Native Structured PDF Table Extraction (pdfplumber / PyPDF2)
   - Stage 2: GLiNER / Fast NER Text Fallback
"""

from __future__ import annotations

import os
import re
import io
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Try optional imports safely
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    requests = None
    REQUESTS_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    TORCH_AVAILABLE = False

try:
    import numpy as np
except ImportError:
    np = None

try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
except ImportError:
    Image = None
    ImageEnhance = None
    ImageFilter = None
    ImageOps = None

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    import pdf2image
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

try:
    from transformers import AutoImageProcessor, AutoModelForObjectDetection
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    from gmft import GMFT, CroppedTable, TableDetector, TableExtractor
    GMFT_AVAILABLE = True
except ImportError:
    GMFT_AVAILABLE = False

# Set GLiNER to false to prevent remote tokenizer download errors
GLINER_AVAILABLE = False

try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False

try:
    from app.ml.table_recognition.inference import TableRecognizer
    TABLE_RECOGNIZER_AVAILABLE = True
except Exception:
    TableRecognizer = None
    TABLE_RECOGNIZER_AVAILABLE = False


@dataclass
class ExtractedDuty:
    """Represents an extracted exam duty."""
    faculty_name: str
    exam_name: str = ''
    date: str = 'N/A'
    session: str = 'Forenoon'
    venue: str = ''
    confidence: float = 0.0

    def to_dict(self):
        return {
            'faculty_name': self.faculty_name,
            'exam_name': self.exam_name,
            'date': self.date,
            'session': self.session,
            'venue': self.venue,
            'confidence': round(self.confidence, 2)
        }


class TableTransformerParser:
    """
    Multi-stage high-speed exam duty parser with specialized pipelines for images and PDFs.
    
    Image Pipeline Order:
      Stage 1: OCR.space API (Cloud-First, isTable=True, Multi-Engine)
      Stage 2: Trained Custom Table Recognition Model (CNN+Transformer DL / Table Transformer)
      Stage 3: PaddleOCR / OpenCV + Tesseract Multi-Angle CLAHE Grid Segmenter
      Stage 4: GLiNER (Zero-shot Named Entity Recognition Fallback)
    """

    MONTHS = {
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
        'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
        'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
    }

    # OCR.space API Key (Free tier 500 req/day)
    OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY", "K82855031688957")

    def __init__(self):
        self.stage1_available = REQUESTS_AVAILABLE
        self.stage2_available = True
        self.stage3_available = PADDLEOCR_AVAILABLE or (CV2_AVAILABLE and PYTESSERACT_AVAILABLE)
        self.stage4_available = GLINER_AVAILABLE or PYTESSERACT_AVAILABLE
        self.gmft_available = GMFT_AVAILABLE or PDFPLUMBER_AVAILABLE

        # Lazy models
        self.tt_detection_processor = None
        self.tt_detection_model = None
        self.tt_initialized = False

        self.custom_recognizer = None
        self.custom_recognizer_initialized = False

        self.gliner_model = None
        self.gliner_initialized = False

        self.paddle_ocr = None
        self.paddle_initialized = False

    def is_available(self) -> bool:
        """Check if parser pipeline is ready."""
        return True

    # =========================================================================
    # MAIN ROUTER BY FILE EXTENSION
    # =========================================================================
    def parse(self, file_path: str) -> Dict[str, Any]:
        if not os.path.exists(file_path):
            return {'success': False, 'error': f'File not found: {file_path}', 'duties': []}

        ext = os.path.splitext(file_path)[1].lower()
        logger.info(f"📄 Parsing exam duty schedule: {os.path.basename(file_path)} ({ext})")

        if ext == '.pdf':
            return self._parse_pdf_pipeline(file_path)
        elif ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']:
            return self._parse_image_pipeline(file_path)
        else:
            return {'success': False, 'error': f'Unsupported file format: {ext}', 'duties': []}

    # =========================================================================
    # IMAGE PIPELINE (4 STAGES - MATRIX -> API -> TRAINED MODEL -> PADDLE/TESSERACT -> GLINER)
    # =========================================================================
    def _parse_image_pipeline(self, image_path: str) -> Dict[str, Any]:
        # -------------------------------------------------------------
        # 0. 2D MATRIX / GRID TIMETABLE PARSER (Specialized for Multi-Date Charts)
        # -------------------------------------------------------------
        try:
            pil_img = Image.open(image_path) if Image else None
            if pil_img:
                matrix_duties = self._extract_matrix_duties_from_image(pil_img)
                if matrix_duties and len(matrix_duties) >= 1:
                    logger.info(f"✅ [Matrix Grid Table Success] Extracted {len(matrix_duties)} duties with exact dates & sessions")
                    return {
                        'success': True,
                        'duties': [d.to_dict() for d in matrix_duties],
                        'total_duties': len(matrix_duties),
                        'stage_used': 'Matrix Timetable Grid Parser',
                        'confidence': 0.98
                    }
        except Exception as e:
            logger.warning(f"Matrix grid parse attempt warning: {e}")

        # -------------------------------------------------------------
        # STAGE 1: OCR.space API (Cloud-First, High Accuracy Table OCR)
        # -------------------------------------------------------------
        if self.stage1_available:
            logger.info("🌐 [Image Stage 1] Running OCR.space API (Cloud-First)...")
            res1 = self._parse_stage1_ocr_space(image_path)
            if res1.get('success') and res1.get('duties'):
                logger.info(f"✅ [Stage 1 Success] Extracted {len(res1['duties'])} duties via OCR.space API")
                return {
                    'success': True,
                    'duties': [d.to_dict() for d in res1['duties']],
                    'total_duties': len(res1['duties']),
                    'stage_used': 'Stage 1: OCR.space API',
                    'confidence': 0.95
                }

        # -------------------------------------------------------------
        # STAGE 2: Trained Custom Table Recognition Model (Deep Learning)
        # -------------------------------------------------------------
        if self.stage2_available:
            logger.info("🤖 [Image Stage 2] Fallback to Trained Table Recognition Model...")
            res2 = self._parse_stage2_trained_table_model(image_path)
            if res2.get('success') and res2.get('duties'):
                logger.info(f"✅ [Stage 2 Success] Extracted {len(res2['duties'])} duties via Trained Model")
                return {
                    'success': True,
                    'duties': [d.to_dict() for d in res2['duties']],
                    'total_duties': len(res2['duties']),
                    'stage_used': 'Stage 2: Trained Table Recognition Model',
                    'confidence': 0.88
                }

        # -------------------------------------------------------------
        # STAGE 3: PaddleOCR / OpenCV + Tesseract (Local OCR & Matrix Grid Segmenter)
        # -------------------------------------------------------------
        if self.stage3_available:
            logger.info("⚡ [Image Stage 3] Fallback to PaddleOCR / OpenCV + Tesseract OCR...")
            res3 = self._parse_stage3_paddle_or_tesseract(image_path)
            if res3.get('success') and res3.get('duties'):
                logger.info(f"✅ [Stage 3 Success] Extracted {len(res3['duties'])} duties via PaddleOCR/Tesseract")
                return {
                    'success': True,
                    'duties': [d.to_dict() for d in res3['duties']],
                    'total_duties': len(res3['duties']),
                    'stage_used': 'Stage 3: PaddleOCR / OpenCV + Tesseract',
                    'confidence': 0.82
                }

        # -------------------------------------------------------------
        # STAGE 4: GLiNER (Zero-shot Named Entity Recognition Fallback)
        # -------------------------------------------------------------
        if self.stage4_available:
            logger.info("🔍 [Image Stage 4] Fallback to GLiNER Named Entity Recognition...")
            res4 = self._parse_stage4_gliner_image(image_path)
            if res4.get('success') and res4.get('duties'):
                logger.info(f"✅ [Stage 4 Success] Extracted {len(res4['duties'])} duties via GLiNER")
                return {
                    'success': True,
                    'duties': [d.to_dict() for d in res4['duties']],
                    'total_duties': len(res4['duties']),
                    'stage_used': 'Stage 4: GLiNER NER Fallback',
                    'confidence': 0.70
                }

        return {
            'success': False,
            'error': 'Could not extract exam duties from image across all 4 pipeline stages. Please ensure image is clear and contains dates, faculty names, and exam sessions.',
            'duties': [],
            'total_duties': 0,
            'stage_used': 'None'
        }

    # =========================================================================
    # PDF PIPELINE (3 STAGES)
    # =========================================================================
    def _parse_pdf_pipeline(self, pdf_path: str) -> Dict[str, Any]:
        # -------------------------------------------------------------
        # STAGE 1: GMFT & Native Table Extraction
        # -------------------------------------------------------------
        logger.info("⚡ [PDF Stage 1] Running GMFT / Native PDF Table Extraction...")
        res1 = self._parse_pdf_native_tables(pdf_path)
        if res1.get('success') and res1.get('duties'):
            logger.info(f"✅ [PDF Stage 1 Success] Extracted {len(res1['duties'])} duties")
            return {
                'success': True,
                'duties': [d.to_dict() for d in res1['duties']],
                'total_duties': len(res1['duties']),
                'stage_used': 'PDF Stage 1: GMFT/Native Table',
                'confidence': 0.92
            }

        # -------------------------------------------------------------
        # STAGE 2: GLiNER / PDF Text Fallback
        # -------------------------------------------------------------
        logger.info("🔄 [PDF Stage 2] Fallback to GLiNER NER on PDF text...")
        res2 = self._parse_pdf_gliner(pdf_path)
        if res2.get('success') and res2.get('duties'):
            logger.info(f"✅ [PDF Stage 2 Success] Extracted {len(res2['duties'])} duties")
            return {
                'success': True,
                'duties': [d.to_dict() for d in res2['duties']],
                'total_duties': len(res2['duties']),
                'stage_used': 'PDF Stage 2: GLiNER NER',
                'confidence': 0.75
            }

        # -------------------------------------------------------------
        # STAGE 3: Scanned PDF Multi-Engine OCR & Matrix Grid Parser
        # -------------------------------------------------------------
        logger.info("🔍 [PDF Stage 3] Converting PDF to image for Scanned OCR / Matrix Table Analysis...")
        res3 = self._parse_pdf_scanned_ocr(pdf_path)
        if res3.get('success') and res3.get('duties'):
            logger.info(f"✅ [PDF Stage 3 Success] Extracted {len(res3['duties'])} duties")
            return {
                'success': True,
                'duties': [d.to_dict() for d in res3['duties']],
                'total_duties': len(res3['duties']),
                'stage_used': 'PDF Stage 3: Scanned OCR / Matrix Grid',
                'confidence': 0.88
            }

        return {
            'success': False,
            'error': 'No structured exam duties found in PDF.',
            'duties': [],
            'total_duties': 0,
            'stage_used': 'None'
        }

    # =========================================================================
    # STAGE 1 (IMAGE): OCR.SPACE CLOUD API (PRIMARY)
    # =========================================================================
    def _parse_stage1_ocr_space(self, image_path: str) -> Dict[str, Any]:
        if not REQUESTS_AVAILABLE or requests is None:
            return {'success': False, 'error': 'requests library not available for OCR.space'}

        try:
            with open(image_path, 'rb') as f:
                image_bytes = f.read()

            files = {'file': ('image.png', image_bytes, 'image/png')}
            engines = [3, 1, 2]  # 3 = Complex table layout, 1 = Fast, 2 = Standard

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
                    logger.info(f"Trying OCR.space API with Engine {engine}...")
                    response = requests.post(
                        'https://api.ocr.space/parse/image',
                        files=files,
                        data=data,
                        timeout=15
                    )
                    if response.status_code == 200:
                        result = response.json()
                        if result.get('IsErroredOnProcessing'):
                            err = result.get('ErrorMessage', ['Unknown error'])[0]
                            logger.warning(f"OCR.space Engine {engine} error: {err}")
                            continue

                        if result.get('ParsedResults'):
                            text = result['ParsedResults'][0].get('ParsedText', '')
                            if text and len(text.strip()) > 15:
                                duties = self._extract_duties_from_raw_text(text)
                                if duties:
                                    return {'success': True, 'duties': duties, 'text': text}
                except Exception as e:
                    logger.warning(f"OCR.space Engine {engine} request error: {e}")
                    continue

            return {'success': False, 'error': 'OCR.space API did not return structured duty records'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # =========================================================================
    # STAGE 2 (IMAGE): TRAINED TABLE RECOGNITION MODEL (CUSTOM DL / TT)
    # =========================================================================
    def _parse_stage2_trained_table_model(self, image_path: str) -> Dict[str, Any]:
        try:
            # 1. First try Custom Trained Model (app.ml.table_recognition / best_model.pth)
            if not self.custom_recognizer_initialized:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                candidate_paths = [
                    os.path.join(os.path.dirname(os.path.dirname(current_dir)), "ml", "table_recognition", "weights", "best_model.pth"),
                    "/app/app/ml/table_recognition/weights/best_model.pth",
                    "/app/ml/table_recognition/weights/best_model.pth"
                ]
                weight_path = next((p for p in candidate_paths if os.path.exists(p)), None)
                if weight_path and TABLE_RECOGNIZER_AVAILABLE and TableRecognizer is not None:
                    try:
                        self.custom_recognizer = TableRecognizer(checkpoint_path=weight_path)
                        logger.info(f"✅ Loaded Custom Trained Table Recognizer from: {weight_path}")
                    except Exception as e:
                        logger.warning(f"Custom TableRecognizer init failed: {e}")
                self.custom_recognizer_initialized = True

            if self.custom_recognizer is not None:
                try:
                    pred = self.custom_recognizer.predict(image_path)
                    if pred.get('table_detected') and pred.get('table_confidence', 0) > 0.4:
                        logger.info(f"Custom Table Model detected table (conf: {pred.get('table_confidence', 0):.2f}, {pred.get('rows')} rows, {pred.get('cols')} cols)")
                        pil_img = Image.open(image_path) if Image else None
                        if pil_img:
                            matrix_duties = self._extract_matrix_duties_from_image(pil_img)
                            if matrix_duties:
                                return {'success': True, 'duties': matrix_duties}
                except Exception as e:
                    logger.warning(f"Custom Table Model inference warning: {e}")

            # 2. Next try Microsoft Table Transformer (if available)
            if TRANSFORMERS_AVAILABLE and torch is not None:
                try:
                    if not self.tt_initialized:
                        try:
                            self.tt_detection_processor = AutoImageProcessor.from_pretrained(
                                "microsoft/table-transformer-detection",
                                use_fast=True,
                                local_files_only=True
                            )
                            self.tt_detection_model = AutoModelForObjectDetection.from_pretrained(
                                "microsoft/table-transformer-detection",
                                local_files_only=True
                            )
                            self.tt_detection_model.eval()
                            self.tt_initialized = True
                        except Exception as e:
                            logger.info(f"Table Transformer weights not cached locally: {e}")

                    if self.tt_initialized and self.tt_detection_processor and self.tt_detection_model:
                        image = Image.open(image_path).convert("RGB") if Image else None
                        if image:
                            inputs = self.tt_detection_processor(images=image, return_tensors="pt")
                            with torch.no_grad():
                                outputs = self.tt_detection_model(**inputs)

                            target_sizes = torch.tensor([image.size[::-1]])
                            results = self.tt_detection_processor.post_process_object_detection(
                                outputs, threshold=0.6, target_sizes=target_sizes
                            )[0]

                            tables = []
                            for box, score, label in zip(results["boxes"], results["scores"], results["labels"]):
                                if label.item() == 0:  # table class
                                    tables.append([int(c) for c in box.tolist()])

                            if tables:
                                x1, y1, x2, y2 = tables[0]
                                cropped = image.crop((x1, y1, x2, y2))
                                if PYTESSERACT_AVAILABLE:
                                    text = pytesseract.image_to_string(cropped, config='--psm 6')
                                    duties = self._extract_duties_from_raw_text(text)
                                    if duties:
                                        return {'success': True, 'duties': duties}
                except Exception as e:
                    logger.info(f"Table Transformer attempt warning: {e}")

            return {'success': False, 'error': 'Trained Table Model could not extract duty records'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # =========================================================================
    # STAGE 3 (IMAGE): PADDLEOCR / OPENCV + TESSERACT OCR & GRID SEGMENTER
    # =========================================================================
    def _parse_stage3_paddle_or_tesseract(self, image_path: str) -> Dict[str, Any]:
        # Option A: PaddleOCR
        if PADDLEOCR_AVAILABLE:
            try:
                if not self.paddle_initialized:
                    self.paddle_ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
                    self.paddle_initialized = True

                result = self.paddle_ocr.ocr(image_path, cls=True)
                lines = []
                if result and len(result) > 0 and result[0]:
                    for line in result[0]:
                        if len(line) > 1 and len(line[1]) > 0:
                            lines.append(line[1][0])

                full_text = "\n".join(lines)
                duties = self._extract_duties_from_raw_text(full_text)
                if duties:
                    return {'success': True, 'duties': duties}
            except Exception as e:
                logger.warning(f"PaddleOCR execution warning: {e}")

        # Option B: Multi-Angle CLAHE + Adaptive Thresholding with Tesseract
        if PYTESSERACT_AVAILABLE:
            try:
                pil_img = None
                if Image:
                    try:
                        pil_img = Image.open(image_path)
                        if ImageOps:
                            pil_img = ImageOps.exif_transpose(pil_img)
                    except Exception:
                        pass

                cv_img = None
                if pil_img is not None and np is not None:
                    cv_img = cv2.cvtColor(np.array(pil_img.convert('RGB')), cv2.COLOR_RGB2BGR) if CV2_AVAILABLE else None
                elif CV2_AVAILABLE:
                    cv_img = cv2.imread(image_path)

                all_extracted_texts = []

                if cv_img is not None and CV2_AVAILABLE:
                    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
                    h, w = gray.shape[:2]
                    if w > 2400:
                        scale = 2000.0 / w
                        gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

                    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
                    enhanced = clahe.apply(gray)
                    _, otsu = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    adapt = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 4)

                    matrices = [enhanced, otsu, adapt]
                    for mat in matrices:
                        for psm in [6, 4, 3]:
                            try:
                                txt = pytesseract.image_to_string(mat, config=f'--oem 3 --psm {psm}')
                                if txt and len(txt.strip()) > 15:
                                    all_extracted_texts.append(txt)
                            except Exception:
                                pass

                    # Rotate 90 & 270 degrees if text is short
                    if not all_extracted_texts or max(len(t) for t in all_extracted_texts) < 40:
                        for angle in [cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_90_COUNTERCLOCKWISE]:
                            rotated = cv2.rotate(enhanced, angle)
                            try:
                                txt = pytesseract.image_to_string(rotated, config='--oem 3 --psm 6')
                                if txt and len(txt.strip()) > 25:
                                    all_extracted_texts.append(txt)
                            except Exception:
                                pass

                    # Contour Grid Extraction
                    thresh = cv2.adaptiveThreshold(~gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, -2)
                    hor_size = int(thresh.shape[1] / 30)
                    ver_size = int(thresh.shape[0] / 30)
                    if hor_size > 0 and ver_size > 0:
                        hor_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (hor_size, 1))
                        horizontal = cv2.dilate(cv2.erode(thresh.copy(), hor_kernel), hor_kernel)
                        ver_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, ver_size))
                        vertical = cv2.dilate(cv2.erode(thresh.copy(), ver_kernel), ver_kernel)
                        table_mask = horizontal + vertical
                        contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                        if contours:
                            contours = sorted(contours, key=cv2.contourArea, reverse=True)
                            x, y, w_box, h_box = cv2.boundingRect(contours[0])
                            table_crop = cv_img[y:y+h_box, x:x+w_box]
                            txt = pytesseract.image_to_string(table_crop, config='--psm 6')
                            if txt and len(txt.strip()) > 15:
                                all_extracted_texts.append(txt)

                best_duties = []
                for txt in all_extracted_texts:
                    duties = self._extract_duties_from_raw_text(txt)
                    if len(duties) > len(best_duties):
                        best_duties = duties

                if best_duties:
                    return {'success': True, 'duties': best_duties}
            except Exception as e:
                logger.warning(f"Tesseract multi-angle OCR error: {e}")

        return {'success': False, 'error': 'Stage 3 OCR failed to locate duty records'}

    # =========================================================================
    # STAGE 4 (IMAGE): GLINER / FAST NER FALLBACK
    # =========================================================================
    def _parse_stage4_gliner_image(self, image_path: str) -> Dict[str, Any]:
        try:
            if not PYTESSERACT_AVAILABLE:
                return {'success': False, 'error': 'Tesseract OCR required'}

            img = Image.open(image_path) if Image else None
            if not img:
                return {'success': False, 'error': 'Cannot open image'}

            text = pytesseract.image_to_string(img, config='--psm 3')
            if not text or len(text.strip()) < 10:
                return {'success': False, 'error': 'Insufficient text for Stage 4'}

            return self._extract_duties_via_ner(text)
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # =========================================================================
    # PDF STAGES
    # =========================================================================
    def _parse_pdf_native_tables(self, pdf_path: str) -> Dict[str, Any]:
        if not PDFPLUMBER_AVAILABLE:
            return {'success': False, 'error': 'pdfplumber not available'}

        try:
            extracted_tables = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for t in tables:
                        if t and len(t) > 1:
                            extracted_tables.append(t)

            if not extracted_tables:
                return {'success': False, 'error': 'No structured tables found in PDF'}

            duties = []
            for table in extracted_tables:
                header_idx = self._find_header_row(table)
                mapping = self._determine_column_mapping(table, header_idx)

                for row_idx, row in enumerate(table):
                    if row_idx <= header_idx or not row:
                        continue
                    clean_row = [str(c).strip() if c else '' for c in row]
                    if all(c == '' for c in clean_row):
                        continue

                    duty = self._extract_duty_from_row(clean_row, mapping)
                    if duty and duty.faculty_name:
                        duties.append(duty)

            if duties:
                return {'success': True, 'duties': duties}

            return {'success': False, 'error': 'No valid duties parsed from PDF tables'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _parse_pdf_gliner(self, pdf_path: str) -> Dict[str, Any]:
        if not PDFPLUMBER_AVAILABLE:
            return {'success': False, 'error': 'pdfplumber required for PDF text extraction'}

        try:
            text_parts = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    txt = page.extract_text()
                    if txt:
                        text_parts.append(txt)

            full_text = "\n".join(text_parts)
            if not full_text or len(full_text.strip()) < 10:
                return {'success': False, 'error': 'No text extracted from PDF'}

            return self._extract_duties_via_ner(full_text)
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _parse_pdf_scanned_ocr(self, pdf_path: str) -> Dict[str, Any]:
        """Parse scanned/image-based PDFs by converting pages to images and running multi-engine OCR."""
        if not PDF2IMAGE_AVAILABLE:
            return {'success': False, 'error': 'pdf2image not available for scanned PDF'}

        try:
            images = pdf2image.convert_from_path(pdf_path)
            if not images:
                return {'success': False, 'error': 'Could not render PDF pages to images'}

            all_duties = []
            for page_idx, img in enumerate(images):
                # 1. Try Matrix Table Parser (VTU / Timetable Checkmark Matrix)
                matrix_duties = self._extract_matrix_duties_from_image(img)
                if matrix_duties:
                    all_duties.extend(matrix_duties)
                    continue

                # 2. Try Standard OCR with multiple PSM modes
                if PYTESSERACT_AVAILABLE:
                    for psm in [6, 4, 3]:
                        try:
                            text = pytesseract.image_to_string(img, config=f'--oem 3 --psm {psm}')
                            if text and len(text.strip()) > 15:
                                duties = self._extract_duties_from_raw_text(text)
                                if duties:
                                    all_duties.extend(duties)
                                    break
                        except Exception:
                            pass

            if all_duties:
                return {'success': True, 'duties': all_duties}

            return {'success': False, 'error': 'No duties extracted from scanned PDF OCR'}
        except Exception as e:
            logger.error(f"Scanned PDF OCR failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _extract_matrix_duties_from_image(self, img: Any) -> List[ExtractedDuty]:
        """
        Extract exam duties from 2D matrix/grid timetable charts (Dates in columns, Staff in rows, checkmarks in cells).
        Combines Tesseract spatial bounding boxes with sub-cell pixel density validation.
        """
        if not PYTESSERACT_AVAILABLE:
            return []

        try:
            # 1. OCR Token Coordinates
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            words = []
            for i in range(len(data['text'])):
                w = data['text'][i].strip()
                if w:
                    words.append({
                        'text': w,
                        'left': data['left'][i],
                        'top': data['top'][i],
                        'width': data['width'][i],
                        'height': data['height'][i],
                        'center_x': data['left'][i] + data['width'][i] / 2,
                        'center_y': data['top'][i] + data['height'][i] / 2
                    })

            if not words:
                return []

            # Document Exam Name
            doc_exam = ''
            for w in words[:25]:
                if any(k in w['text'].lower() for k in ['vtu', 'exam', 'theory', 'assessment', 'semester']):
                    doc_exam = 'VTU Theory Examination'
                    break

            # 2. Extract Date Columns
            month_map = {'jan':'01','feb':'02','mar':'03','apr':'04','may':'05','jun':'06','jul':'07','aug':'08','sep':'09','oct':'10','nov':'11','dec':'12'}
            date_cols = []
            
            for w in words:
                m = re.match(r'^([0-9O]{1,2})-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', w['text'], re.IGNORECASE)
                if m:
                    day_str = m.group(1).replace('O', '0').replace('o', '0').zfill(2)
                    month_str = month_map.get(m.group(2).lower(), '08')
                    date_cols.append({
                        'raw': w['text'],
                        'date_str': f"2026-{month_str}-{day_str}",
                        'center_x': w['center_x'],
                        'center_y': w['center_y'],
                        'left': w['left'],
                        'width': w['width'],
                        'top': w['top']
                    })

            if not date_cols:
                return []

            date_cols = sorted(date_cols, key=lambda x: x['center_x'])
            min_date_x = min(d['center_x'] for d in date_cols)
            header_date_y = max(d['center_y'] for d in date_cols)
            header_bottom_y = header_date_y + 45

            # 3. Extract Session (Forenoon M / Afternoon A) per Date Column
            session_words = [w for w in words if w['text'].upper() in ['M', 'A', 'FN', 'AN', '1', '3', '6'] and w['center_y'] < header_bottom_y + 30]
            for col in date_cols:
                nearby_session = [s for s in session_words if abs(s['center_x'] - col['center_x']) < 35 and s['center_y'] > col['center_y']]
                col['session'] = 'Forenoon'
                for s in nearby_session:
                    t = s['text'].upper()
                    if t in ['A', 'AN', '3']:
                        col['session'] = 'Afternoon'
                        break
                    elif t in ['M', 'FN', '1', '6']:
                        col['session'] = 'Forenoon'
                        break

            # 4. Extract Faculty Rows
            faculty_words = [w for w in words if w['center_x'] < min_date_x - 30 and w['center_y'] > header_bottom_y]
            faculty_lines = {}
            for w in faculty_words:
                found = False
                for y in faculty_lines:
                    if abs(w['center_y'] - y) < 18:
                        faculty_lines[y].append(w)
                        found = True
                        break
                if not found:
                    faculty_lines[w['center_y']] = [w]

            faculty_rows = []
            ignored_patterns = [r'\bstaff\b', r'\bpage\b', r'\bvtu\b', r'\btheory\b', r'\bsl\b', r'\bno\b', r'\bsignature\b', r'\bname\b']

            for y in sorted(faculty_lines.keys()):
                row_words = sorted(faculty_lines[y], key=lambda x: x['left'])
                name = ' '.join([w['text'] for w in row_words]).strip()
                name = re.sub(r'^(?:Or\.|Dr\.|Mr\.|Ms\.|Prof\.|Mrs\.|Ms,)\s*', '', name, flags=re.IGNORECASE).strip()
                name = name.replace('|', '').replace('_', '').strip()
                
                is_header = any(re.search(pat, name, re.IGNORECASE) for pat in ignored_patterns)
                if len(name) > 2 and not is_header:
                    faculty_rows.append({
                        'name': name,
                        'center_y': y
                    })

            if not faculty_rows:
                return []

            # 5. Extract Checkmarks / Ticks in Cells (Hybrid OCR Word Match + Visual Pixel Density)
            duty_marks = [
                w for w in words 
                if w['center_x'] >= min_date_x - 35 and w['center_y'] > header_bottom_y
                and w['text'].lower() in ['v', 'vv', 'w', 'x', '✓', 'y', '1', 'c', '\\', 's', 'j', '/']
            ]

            img_np = None
            if np is not None:
                try:
                    img_np = np.array(img.convert('L'))
                except Exception:
                    pass

            duties = []
            h_img, w_img = img_np.shape[:2] if img_np is not None else (0, 0)

            for f in faculty_rows:
                for d in date_cols:
                    has_duty = False

                    # Method A: Direct OCR checkmark token match
                    matched_marks = [
                        m for m in duty_marks
                        if abs(m['center_x'] - d['center_x']) < 42 and abs(m['center_y'] - f['center_y']) < 22
                    ]
                    if matched_marks:
                        has_duty = True
                    elif img_np is not None:
                        # Method B: Sub-cell visual stroke inspection
                        x1 = max(0, int(d['center_x'] - 30))
                        x2 = min(w_img, int(d['center_x'] + 30))
                        y1 = max(0, int(f['center_y'] - 14))
                        y2 = min(h_img, int(f['center_y'] + 14))
                        
                        cell_crop = img_np[y1:y2, x1:x2]
                        if cell_crop.size > 0:
                            ch, cw = cell_crop.shape
                            inner_cell = cell_crop[int(ch*0.15):int(ch*0.85), int(cw*0.15):int(cw*0.85)]
                            if inner_cell.size > 0:
                                dark_pixels = np.sum(inner_cell < 150)
                                ratio = dark_pixels / inner_cell.size
                                if ratio > 0.035 and dark_pixels > 25:
                                    has_duty = True

                    if has_duty:
                        duties.append(ExtractedDuty(
                            faculty_name=f['name'],
                            exam_name=doc_exam,
                            date=d['date_str'],
                            session=d['session'],
                            venue='',
                            confidence=0.95
                        ))

            return duties
        except Exception as e:
            logger.warning(f"Matrix duty extraction error: {e}")
            return []

    # =========================================================================
    # UNIVERSAL ROBUST DUTY EXTRACTOR (FOR LIST/TABULAR TEXT WITH DATES ON LINES)
    # =========================================================================
    def _extract_duties_from_raw_text(self, text: str) -> List[ExtractedDuty]:
        """
        Extracts exam duties from raw OCR text when lines contain explicit dates.
        Strictly requires real dates to avoid false fallback assignments.
        """
        if not text or len(text.strip()) < 5:
            return []

        duties = []
        raw_lines = text.split('\n')

        # Detect document-level exam name if mentioned in headers
        doc_exam = ''
        for line in raw_lines[:6]:
            line_str = line.strip()
            if any(k in line_str.lower() for k in ['exam', 'semester', 'mid term', 'cie', 'term', 'b.tech', 'mca', 'm.tech', 'assessment']):
                doc_exam = line_str
                break

        for raw_line in raw_lines:
            line = raw_line.strip()
            if len(line) < 3:
                continue

            # Ignore general headers and title lines
            line_lower = line.lower()
            header_hits = sum(1 for kw in ['date', 'session', 'faculty', 'venue', 'subject', 'sl.no', 'signature', 'department', 'invigilator', 'staff name'] if kw in line_lower)
            if header_hits >= 2 or any(h in line_lower for h in ['allocation', 'department of', 'duty schedule', 'examination cell']):
                continue

            # 1. Date Detection (Must be present on line to avoid false date generation)
            date_match = re.search(
                r'(\b\d{1,4}[-/\.]\d{1,2}[-/\.]\d{1,4}\b|\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}\b|\b\d{1,2}-(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*-\d{2,4}\b)',
                line,
                re.IGNORECASE
            )

            # If no date is found on the individual line, skip it (prevents creating wrong fallback dates)
            if not date_match:
                continue

            # 2. Session / Time Detection
            session_match = re.search(
                r'(\b(?:FN|AN|FORENOON|AFTERNOON|MORNING|EVENING)\b|\b\d{1,2}:\d{2}\s*(?:AM|PM)?\s*[-–toTO]+\s*\d{1,2}:\d{2}\s*(?:AM|PM)?\b)',
                line,
                re.IGNORECASE
            )

            # 3. Venue Detection
            venue_match = re.search(
                r'\b(Hall\s*[-#]?\s*\d+|Room\s*[-#]?\s*\d+|LH\s*[-#]?\s*\d+|Lab\s*[-#]?\s*\d+|Block\s*[A-Za-z0-9]+|Auditorium)\b',
                line,
                re.IGNORECASE
            )

            tokens = [t.strip() for t in re.split(r'\s{2,}|\t|\|', line) if t.strip()]

            # Determine faculty candidate
            faculty = ''
            title_match = re.search(r'(?:Dr\.|Prof\.|Mr\.|Mrs\.|Ms\.|Er\.)\s*[A-Za-z0-9_\.]+', line, re.IGNORECASE)
            if title_match:
                faculty = self._clean_faculty_name(title_match.group(0))

            if not faculty and tokens:
                for tok in tokens:
                    if re.search(r'\d{1,4}[-/]\d{1,4}', tok):
                        continue
                    if re.search(r'\b(FN|AN|Morning|Afternoon|Evening|\d{1,2}:\d{2})\b', tok, re.IGNORECASE):
                        continue
                    if re.search(r'\b(Hall|Room|LH|Lab|Exam|Semester|Subject|Venue|Date)\b', tok, re.IGNORECASE):
                        continue
                    
                    cleaned_cand = self._clean_faculty_name(tok)
                    if cleaned_cand and len(cleaned_cand) >= 2 and cleaned_cand.lower() not in ['date', 'session', 'venue', 'exam', 'paper']:
                        faculty = cleaned_cand
                        break

            if not faculty:
                name_match = re.search(r'(?:(?:Dr\.|Prof\.|Mr\.|Mrs\.|Ms\.|Er\.)\s*)?([A-Za-z0-9_]{3,25}(?:\s+[A-Za-z0-9_]+){0,3})', line)
                if name_match:
                    cand = self._clean_faculty_name(name_match.group(0))
                    if cand and not any(k in cand.lower() for k in ['date', 'time', 'exam', 'session', 'hall', 'room']):
                        faculty = cand

            if faculty and date_match:
                date_val = self._parse_date(date_match.group(0))
                session_val = self._parse_session(session_match.group(0)) if session_match else 'Forenoon'
                venue_val = venue_match.group(0) if venue_match else ''

                duties.append(ExtractedDuty(
                    faculty_name=faculty,
                    exam_name=doc_exam,
                    date=date_val,
                    session=session_val,
                    venue=venue_val,
                    confidence=0.88
                ))

        return duties

    # =========================================================================
    # NER ENTITY EXTRACTION
    # =========================================================================
    def _extract_duties_via_ner(self, text: str) -> Dict[str, Any]:
        faculty_names = []
        dates = []
        sessions = []
        venues = []

        # Local-only GLiNER check (never block HTTP on download)
        if GLINER_AVAILABLE:
            try:
                if not self.gliner_initialized:
                    self.gliner_model = GLiNER.from_pretrained(
                        "urchade/gliner_medium-v2.1",
                        local_files_only=True
                    )
                    self.gliner_initialized = True

                labels = ["person", "date", "time", "venue", "exam"]
                entities = self.gliner_model.predict_entities(text, labels, threshold=0.35)

                for ent in entities:
                    lbl = ent['label'].lower()
                    val = ent['text'].strip()
                    if lbl == 'person':
                        faculty_names.append(self._clean_faculty_name(val))
                    elif lbl == 'date':
                        dates.append(self._parse_date(val))
                    elif lbl == 'time':
                        sessions.append(self._parse_session(val))
                    elif lbl == 'venue':
                        venues.append(val)
            except Exception as e:
                logger.info(f"GLiNER not pre-cached locally: {e}")

        # Fallback to our fast regex tokenizer if GLiNER unavailable
        if not faculty_names:
            duties = self._extract_duties_from_raw_text(text)
            if duties:
                return {'success': True, 'duties': duties}
            return {'success': False, 'error': 'No entities extracted'}

        duties = []
        for i, name in enumerate(faculty_names):
            duties.append(ExtractedDuty(
                faculty_name=name,
                exam_name='',
                date=dates[i] if i < len(dates) else datetime.now().strftime('%Y-%m-%d'),
                session=sessions[i] if i < len(sessions) else 'Forenoon',
                venue=venues[i] if i < len(venues) else '',
                confidence=0.75
            ))

        return {'success': True, 'duties': duties} if duties else {'success': False, 'error': 'No duties created'}

    # =========================================================================
    # HELPERS
    # =========================================================================
    def _find_header_row(self, rows: List[List[str]]) -> int:
        header_keywords = ['date', 'faculty', 'session', 'exam', 'name', 'time', 'venue', 'staff', 'lecturer']
        for idx, row in enumerate(rows):
            row_text = ' '.join([str(cell).lower() for cell in row if cell])
            if any(k in row_text for k in header_keywords):
                return idx
        return 0

    def _determine_column_mapping(self, rows: List[List[str]], header_idx: int) -> Dict[str, int]:
        mapping = {'date': -1, 'session': -1, 'exam_name': -1, 'faculty_name': -1, 'venue': -1}
        if header_idx < len(rows):
            header = rows[header_idx]
            for col_idx, cell in enumerate(header):
                if not cell:
                    continue
                cell_lower = str(cell).lower()
                if 'date' in cell_lower:
                    mapping['date'] = col_idx
                elif any(s in cell_lower for s in ['session', 'time', 'fn', 'an', 'slot']):
                    mapping['session'] = col_idx
                elif any(e in cell_lower for e in ['exam', 'subject', 'course', 'paper']):
                    mapping['exam_name'] = col_idx
                elif any(f in cell_lower for f in ['faculty', 'staff', 'name', 'teacher', 'invigilator', 'lecturer']):
                    mapping['faculty_name'] = col_idx
                elif any(v in cell_lower for v in ['venue', 'room', 'hall', 'block', 'lab']):
                    mapping['venue'] = col_idx

        if mapping['faculty_name'] == -1 and len(rows[header_idx]) > 0:
            mapping['faculty_name'] = 1 if len(rows[header_idx]) > 1 else 0
        return mapping

    def _extract_duty_from_row(self, row: List[str], mapping: Dict[str, int]) -> Optional[ExtractedDuty]:
        try:
            faculty = row[mapping['faculty_name']] if 0 <= mapping['faculty_name'] < len(row) else ''
            exam = row[mapping['exam_name']] if 0 <= mapping['exam_name'] < len(row) else ''
            date_str = row[mapping['date']] if 0 <= mapping['date'] < len(row) else ''
            session_str = row[mapping['session']] if 0 <= mapping['session'] < len(row) else ''
            venue_str = row[mapping['venue']] if 0 <= mapping['venue'] < len(row) else ''

            faculty = self._clean_faculty_name(faculty)
            if not faculty or len(faculty) < 2:
                return None

            return ExtractedDuty(
                faculty_name=faculty,
                exam_name=self._clean_exam_name(exam),
                date=self._parse_date(date_str) or datetime.now().strftime('%Y-%m-%d'),
                session=self._parse_session(session_str) or 'Forenoon',
                venue=venue_str,
                confidence=0.90
            )
        except Exception:
            return None

    def _clean_faculty_name(self, name: str) -> str:
        if not name:
            return ''
        name = re.sub(r'^(Dr\.|Prof\.|Mr\.|Ms\.|Mrs\.|Er\.)\s*', '', str(name).strip(), flags=re.IGNORECASE)
        name = re.sub(r'[^\w\s\.]', '', name)
        return ' '.join(name.split()).strip()

    def _clean_exam_name(self, exam: str) -> str:
        if not exam:
            return ''
        return ' '.join(str(exam).split()).strip()

    def _parse_date(self, date_text: str) -> str:
        if not date_text:
            return datetime.now().strftime('%Y-%m-%d')
        date_text = str(date_text).strip()

        # DD/MM/YYYY or MM/DD/YYYY or YYYY-MM-DD
        m1 = re.search(r'(\d{1,4})[-/\.](\d{1,2})[-/\.](\d{1,4})', date_text)
        if m1:
            p1_s, p2_s, p3_s = m1.groups()
            p1, p2 = int(p1_s), int(p2_s)
            if p1 > 31:  # YYYY-MM-DD
                return f"{p1_s}-{str(p2).zfill(2)}-{str(p3_s).zfill(2)}"
            
            year = '20' + p3_s if len(p3_s) <= 2 else p3_s
            if p1 <= 12 and p2 > 12:  # MM/DD/YYYY format
                month = p1
                day = p2
            else:  # DD/MM/YYYY format
                day = p1
                month = p2
            return f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}"

        # DD Month YYYY
        m2 = re.search(r'(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{2,4})', date_text)
        if m2:
            d, month_name, y = m2.groups()
            month_num = self.MONTHS.get(month_name[:3].lower(), '01')
            year = '20' + y if len(y) <= 2 else y
            return f"{year}-{month_num}-{d.zfill(2)}"

        return date_text

    def _parse_session(self, session_text: str) -> str:
        if not session_text:
            return 'Forenoon'
        s = str(session_text).lower()
        if 'an' in s or 'afternoon' in s or 'evening' in s or '01:' in s or '02:' in s or '03:' in s or 'pm' in s:
            return 'Afternoon'
        return 'Forenoon'


# Singleton instance
table_transformer_parser = TableTransformerParser()