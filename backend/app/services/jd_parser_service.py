"""
Job Description (JD) Processing and Generalized Requirement Extraction Service

Robust, multi-stage hybrid extraction pipeline that extracts structured job requirements
across diverse companies, job roles, writing styles, and document formats (PDF, DOCX, TXT):
- Document ingestion (PDF, DOCX, TXT, OCR fallback) with structure preservation
- Text normalization with evidence traceability
- Multi-tier academic criteria (distinct 10th, 12th, Degree percentages, CGPA, backlogs)
- Staged compensation progression (Internship stipend -> Full-time CTC)
- Application deadlines, drive dates, joining dates with incomplete-date detection
- Degrees, graduation batches, eligible branches
- Core required skills vs preferred bonus skills vs certifications
- Workplace mode, service agreements / bonds, and selection rounds
- Actionable review warnings / flags and verbatim field evidence for auditability
"""

import re
import os
import logging
import tempfile
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime
from urllib.parse import urlparse

from .skill_normalizer import skill_normalizer
from .file_storage.text_extractor import text_extractor
from .ocr_service import OCRService
from .gliner_service import gliner_service

logger = logging.getLogger(__name__)


class JdParseResult(dict):
    """
    Dictionary subclass supporting both dict key access (result['title'])
    and attribute access (result.title) for seamless backward compatibility
    and object-like ergonomics.
    """
    def __getattr__(self, name: str) -> Any:
        if name == "min_cgpa":
            return dict.get(self, "min_cgpa", dict.get(self, "cgpa_criteria"))
        if name == "cgpa_criteria":
            return dict.get(self, "cgpa_criteria", dict.get(self, "min_cgpa"))
        if name in ("title", "job_title"):
            return dict.get(self, "title", dict.get(self, "job_title"))
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'JdParseResult' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value

    def __getitem__(self, key: str) -> Any:
        if key == "min_cgpa":
            val = dict.get(self, "min_cgpa")
            if val is not None:
                return val
            val = dict.get(self, "cgpa_criteria")
            if val is not None:
                return val
        elif key == "cgpa_criteria":
            val = dict.get(self, "cgpa_criteria")
            if val is not None:
                return val
            val = dict.get(self, "min_cgpa")
            if val is not None:
                return val
        elif key in ("title", "job_title"):
            val = dict.get(self, "title")
            if val is not None:
                return val
            val = dict.get(self, "job_title")
            if val is not None:
                return val
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> Any:
        if key == "min_cgpa":
            val = dict.get(self, "min_cgpa")
            if val is not None:
                return val
            val = dict.get(self, "cgpa_criteria")
            return val if val is not None else default
        elif key == "cgpa_criteria":
            val = dict.get(self, "cgpa_criteria")
            if val is not None:
                return val
            val = dict.get(self, "min_cgpa")
            return val if val is not None else default
        elif key in ("title", "job_title"):
            val = dict.get(self, "title")
            if val is not None:
                return val
            val = dict.get(self, "job_title")
            return val if val is not None else default
        return super().get(key, default)


class JdParserService:
    """General-purpose service for extracting structured requirements from Job Descriptions."""

    # Comprehensive technical & domain skill vocabulary
    KNOWN_SKILL_KEYWORDS: List[str] = [
        # Languages
        "python", "java", "c++", "c#", "c", "javascript", "typescript", "golang", "go",
        "rust", "ruby", "php", "swift", "kotlin", "scala", "dart", "r", "matlab",
        # Web Frameworks
        "react", "react.js", "reactjs", "angular", "angularjs", "vue", "vuejs",
        "node", "nodejs", "node.js", "express", "express.js", "django", "flask", "fastapi",
        "spring", "spring boot", "springboot", "nextjs", "next.js", "nest.js", "laravel",
        "asp.net", "dotnet", ".net", "ruby on rails", "rails",
        # UI & Frontend
        "html", "html5", "css", "css3", "tailwind", "tailwind css", "bootstrap", "sass", "redux",
        # Databases
        "sql", "mysql", "postgresql", "postgres", "psql", "sqlite", "mongodb", "mongo",
        "redis", "cassandra", "dynamodb", "elasticsearch", "oracle", "mariadb", "neo4j",
        # Cloud, DevOps & Monitoring
        "docker", "kubernetes", "k8s", "aws", "azure", "gcp", "linux", "bash", "shell",
        "git", "github", "gitlab", "ci/cd", "cicd", "terraform", "jenkins", "ansible",
        "helm", "prometheus", "grafana",
        # Mobile & Cross-Platform
        "flutter", "dart", "firebase", "react native", "android", "ios",
        # AI / ML / Data
        "machine learning", "deep learning", "ai", "artificial intelligence", "nlp", "computer vision",
        "tensorflow", "pytorch", "keras", "scikit-learn", "pandas", "numpy", "opencv",
        "data science", "data analysis", "power bi", "tableau", "spark", "hadoop", "kafka",
        # Core Architecture & Concepts
        "rest api", "rest", "restful api", "graphql", "microservices", "grpc",
        "data structures", "algorithms", "dsa", "oop", "oops", "object oriented programming",
        "system design", "operating systems", "dbms", "computer networks",
        # Testing & Tooling
        "selenium", "junit", "pytest", "cypress", "postman", "agile", "scrum", "jira",
        # Enterprise / ERP / Specialized
        "sap", "sap abap", "abap", "salesforce", "embedded c", "iot", "vlsi", "matlab",
        # Functional, Support, Operations & Management
        "customer support", "technical support", "troubleshooting", "crm", "helpdesk",
        "ticketing", "incident management", "communication", "client communication",
        "problem solving", "erp", "enterprise resource planning", "client relationship",
        "documentation", "product support", "software support", "customer service",
        "networking", "hardware support", "desktop support", "database administration"
    ]

    # Academic degree standardization
    DEGREE_PATTERNS: List[Tuple[str, str]] = [
        (r'\b(?:b\.?e\.?|bachelor\s+of\s+engineering)\b', "B.E"),
        (r'\b(?:b\.?tech\.?|bachelor\s+of\s+technology)\b', "B.Tech"),
        (r'\b(?:m\.?e\.?|master\s+of\s+engineering)\b', "M.E"),
        (r'\b(?:m\.?tech\.?|master\s+of\s+technology)\b', "M.Tech"),
        (r'\b(?:mca|master\s+of\s+computer\s+applications)\b', "MCA"),
        (r'\b(?:bca|bachelor\s+of\s+computer\s+applications)\b', "BCA"),
        (r'\b(?:b\.?sc\.?|bachelor\s+of\s+science)\b', "B.Sc"),
        (r'\b(?:m\.?sc\.?|master\s+of\s+science)\b', "M.Sc"),
        (r'\b(?:mba)\b', "MBA"),
        (r'\b(?:diploma)\b', "Diploma"),
    ]

    # Branch mapping
    BRANCH_MAP: Dict[str, str] = {
        "cse": "CSE",
        "cs": "CSE",
        "computer science": "CSE",
        "computer science engineering": "CSE",
        "computer science & engineering": "CSE",
        "cd": "CSE/Design",
        "cse/design": "CSE/Design",
        "cs & design": "CSE/Design",
        "computer science & design": "CSE/Design",
        "computer science and design": "CSE/Design",
        "it": "IT",
        "information technology": "IT",
        "information science": "IT",
        "ise": "IT",
        "aiml": "AIML",
        "ai & ml": "AIML",
        "ai/ml": "AIML",
        "artificial intelligence": "AIML",
        "artificial intelligence & machine learning": "AIML",
        "artificial intelligence and machine learning": "AIML",
        "aids": "AIDS",
        "ai & ds": "AIDS",
        "ai/ds": "AIDS",
        "data science": "AIDS",
        "artificial intelligence & data science": "AIDS",
        "artificial intelligence and data science": "AIDS",
        "cyber security": "CYBER_SECURITY",
        "cybersecurity": "CYBER_SECURITY",
        "ece": "ECE",
        "electronics": "ECE",
        "electronics and communication": "ECE",
        "electronics & communication": "ECE",
        "eee": "EEE",
        "electrical": "EEE",
        "electrical and electronics": "EEE",
        "electrical & electronics": "EEE",
        "mech": "MECH",
        "mechanical": "MECH",
        "mechanical engineering": "MECH",
        "civil": "CIVIL",
        "civil engineering": "CIVIL",
    }

    def __init__(self):
        self.ocr_service = OCRService()

    # =========================================================================
    # STAGE A: DOCUMENT INGESTION
    # =========================================================================

    def parse_file(
        self,
        file_path: Optional[Union[str, bytes]] = None,
        content: Optional[Union[bytes, str]] = None,
        target_name: Optional[str] = None
    ) -> JdParseResult:
        """Convenience method to extract text and parse structured requirements from a file."""
        text = self.extract_text_from_file(file_path=file_path, content=content, filename=target_name)
        return self.parse_jd_text(text)

    def extract_text_from_file(
        self,
        file_path: Optional[Union[str, bytes]] = None,
        content: Optional[Union[bytes, str]] = None,
        filename: Optional[str] = None
    ) -> str:
        """
        Extract text from PDF, DOCX, or TXT file with fallback handling for
        scanned or unreadable documents.
        """
        # Flexible positional argument handling:
        # e.g., extract_text_from_file(raw_bytes, "notice.pdf")
        if isinstance(file_path, (bytes, bytearray)):
            raw_bytes = bytes(file_path)
            if isinstance(content, str) and filename is None:
                filename = content
                content = raw_bytes
            else:
                content = raw_bytes
            file_path = None

        # Check for empty content
        if content is not None and isinstance(content, (bytes, bytearray)) and len(content) == 0:
            raise ValueError("Uploaded file is empty (0 bytes).")
        if file_path and isinstance(file_path, str) and os.path.exists(file_path) and os.path.getsize(file_path) == 0:
            raise ValueError("Uploaded file is empty (0 bytes).")

        target_name = filename or (os.path.basename(file_path) if file_path and isinstance(file_path, str) else "document.txt")
        ext = os.path.splitext(target_name)[1].lower()

        # Allowed extensions
        allowed_extensions = [".pdf", ".docx", ".doc", ".txt", ".png", ".jpg", ".jpeg", ".xlsx", ".xls", ".csv"]
        if ext not in allowed_extensions:
            raise ValueError(
                f"Unsupported file format '{ext}'. Please upload a PDF (.pdf), Word document (.docx), plain text (.txt), "
                f"recruitment image (.png, .jpg, .jpeg), or spreadsheet (.xlsx, .csv)."
            )

        extracted_text = ""
        last_ocr_err: Optional[str] = None

        # 1. Image OCR handling
        if ext in [".png", ".jpg", ".jpeg"]:
            try:
                if content:
                    ocr_text = self.ocr_service.extract_text_from_image_bytes(content)
                    if ocr_text and "Error:" not in ocr_text and "OCR Error:" not in ocr_text:
                        extracted_text = ocr_text.strip()
                    elif ocr_text and ("Error:" in ocr_text or "OCR Error:" in ocr_text):
                        last_ocr_err = ocr_text
                elif file_path and os.path.exists(file_path):
                    ocr_text = self.ocr_service.extract_text_from_image(file_path)
                    if ocr_text and "Error:" not in ocr_text and "OCR Error:" not in ocr_text:
                        extracted_text = ocr_text.strip()
                    elif ocr_text and ("Error:" in ocr_text or "OCR Error:" in ocr_text):
                        last_ocr_err = ocr_text
            except Exception as img_err:
                last_ocr_err = str(img_err)
                logger.warning(f"Image OCR extraction failed for {target_name}: {img_err}")

        # 2. Primary extraction using text_extractor (for docs, pdfs, sheets, text)
        if not extracted_text:
            try:
                target_path = file_path or target_name
                extracted = text_extractor.extract_text(target_path, content=content)
                if extracted and extracted.get("success") and extracted.get("text"):
                    extracted_text = extracted.get("text", "").strip()
            except Exception as e:
                logger.warning(f"Primary text_extractor failed for {target_name}: {e}")

        # 3. PDF direct fallback if needed
        if not extracted_text and ext == ".pdf" and content:
            try:
                import pdfplumber
                from io import BytesIO
                with pdfplumber.open(BytesIO(content)) as pdf:
                    pages = []
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            pages.append(page_text)
                    if pages:
                        extracted_text = "\n".join(pages).strip()
            except Exception as e:
                logger.warning(f"Direct pdfplumber fallback failed: {e}")

        # 4. DOCX direct fallback if needed
        if not extracted_text and ext in [".docx", ".doc"] and content:
            try:
                import docx
                from io import BytesIO
                doc = docx.Document(BytesIO(content))
                parts = [p.text for p in doc.paragraphs if p.text]
                for table in doc.tables:
                    for row in table.rows:
                        row_vals = [c.text.strip() for c in row.cells if c.text.strip()]
                        if row_vals:
                            parts.append(" | ".join(row_vals))
                extracted_text = "\n".join(parts).strip()
            except Exception as e:
                logger.warning(f"Direct docx fallback failed: {e}")

        # 5. Spreadsheet direct fallback if needed
        if not extracted_text and ext in [".xlsx", ".xls", ".csv"] and content:
            try:
                from io import BytesIO
                if ext == ".csv":
                    import pandas as pd
                    df = pd.read_csv(BytesIO(content))
                    extracted_text = df.to_string(index=False)
                elif ext in [".xlsx", ".xls"]:
                    import pandas as pd
                    dfs = pd.read_excel(BytesIO(content), sheet_name=None)
                    sheet_texts = []
                    for sheet_name, df in dfs.items():
                        sheet_texts.append(f"Sheet: {sheet_name}\n" + df.to_string(index=False))
                    extracted_text = "\n\n".join(sheet_texts)
            except Exception as xl_err:
                logger.warning(f"Spreadsheet fallback failed: {xl_err}")

        # 6. PDF scanned document detection and OCR fallback
        if ext == ".pdf" and (not extracted_text or len(extracted_text.strip()) < 20):
            logger.info("PDF has insufficient selectable text; attempting OCR extraction...")
            try:
                if content:
                    ocr_text = self.ocr_service.extract_text_from_scanned_pdf_bytes(content)
                    if ocr_text and len(ocr_text.strip()) > 30 and "Error:" not in ocr_text and "Scanned PDF Error:" not in ocr_text:
                        extracted_text = ocr_text.strip()
                    elif ocr_text and ("Error:" in ocr_text or "Scanned PDF Error:" in ocr_text):
                        last_ocr_err = ocr_text
                elif file_path and os.path.exists(file_path):
                    ocr_text = self.ocr_service.extract_text_from_scanned_pdf(file_path)
                    if ocr_text and len(ocr_text.strip()) > 30 and "Error:" not in ocr_text and "Scanned PDF Error:" not in ocr_text:
                        extracted_text = ocr_text.strip()
                    elif ocr_text and ("Error:" in ocr_text or "Scanned PDF Error:" in ocr_text):
                        last_ocr_err = ocr_text
            except Exception as ocr_err:
                last_ocr_err = str(ocr_err)
                logger.warning(f"OCR fallback attempt encountered an error: {ocr_err}")

        # 7. Fallback for raw text bytes (plain text files or mock content)
        if not extracted_text and content:
            try:
                decoded = content.decode("utf-8", errors="ignore").strip()
                if len(decoded) >= 10 and (ext == ".txt" or any(w in decoded.lower() for w in ["job", "drive", "eligibility", "criteria", "apply", "company", "campus", "title", "salary", "recruitment", "support", "executive"])):
                    extracted_text = decoded
            except Exception:
                pass

        if not extracted_text or len(extracted_text.strip()) < 10:
            err_msg = (
                f"Failed to extract readable text from '{target_name}'. "
                + (f"OCR failure details: {last_ocr_err}. " if last_ocr_err else "")
                + "The file may be a scanned image without readable text or contains unreadable content. "
                "Please upload a searchable text document, recruitment document, or paste the text directly."
            )
            raise ValueError(err_msg)

        return extracted_text


    # =========================================================================
    # STAGE B: TEXT NORMALIZATION
    # =========================================================================

    @staticmethod
    def _clean_ocr_word_splits(text: str) -> str:
        """Fix OCR-split words frequently found in job descriptions and recruitment notices."""
        if not text:
            return ""
        fixes = [
            (r'\b(supp)\s+(ort)\b', 'support'),
            (r'\b(technic)\s+(al)\b', 'technical'),
            (r'\b(execut)\s+(ive)\b', 'executive'),
            (r'\b(soft)\s+(ware)\b', 'software'),
            (r'\b(engine)\s+(er)\b', 'engineer'),
            (r'\b(devel)\s+(oper)\b', 'developer'),
            (r'\b(gradu)\s+(ate)\b', 'graduate'),
            (r'\b(trai)\s+(nee)\b', 'trainee'),
            (r'\b(consult)\s+(ant)\b', 'consultant'),
            (r'\b(applic)\s+(ation)\b', 'application'),
            (r'\b(registr)\s+(ation)\b', 'registration'),
            (r'\b(dead)\s+(line)\b', 'deadline'),
            (r'\b(eligib)\s+(ility)\b', 'eligibility'),
            (r'\b(require)\s+(ments?)\b', 'requirements'),
            (r'\b(qualific)\s+(ations?)\b', 'qualifications'),
            (r'\b(descrip)\s+(tion)\b', 'description'),
        ]
        res = text
        for pat, word in fixes:
            def _repl(m, target_word=word):
                raw = m.group(0)
                if raw.isupper():
                    return target_word.upper()
                if raw[0].isupper():
                    return target_word.capitalize()
                return target_word.lower()
            res = re.sub(pat, _repl, res, flags=re.IGNORECASE)
        return res

    def normalize_text(self, text: str) -> str:
        """
        Normalize whitespace and bullet characters while preserving structural
        headings, bullet points, and key-value lines.
        """
        if not text:
            return ""

        # Normalize unicode line breaks
        norm = text.replace("\r\n", "\n").replace("\r", "\n")

        # Repair known OCR-split words
        norm = self._clean_ocr_word_splits(norm)

        # Normalize non-breaking spaces and tabs
        norm = norm.replace("\xa0", " ").replace("\t", "    ")

        # Normalize non-standard bullet characters to standard '- '
        bullet_pattern = r'^[ \t]*[•▪▫➢✦★\*\-–—][ \t]+'
        lines = []
        for line in norm.split("\n"):
            cleaned_line = re.sub(bullet_pattern, '- ', line.strip())
            lines.append(cleaned_line)

        norm = "\n".join(lines)

        # Collapse excess empty lines (max 2 consecutive)
        norm = re.sub(r'\n{3,}', '\n\n', norm)
        return norm.strip()

    # =========================================================================
    # STAGE C: FIELD EXTRACTION PIPELINE
    # =========================================================================

    def parse_jd_text(self, text: str) -> Dict[str, Any]:
        """
        Execute the full hybrid extraction pipeline on raw Job Description text.
        Extracts both core job-posting fields and general-purpose placement metadata,
        accompanied by review flags and source evidence.
        """
        raw_text = text.strip() if text else ""
        if not raw_text:
            return self._empty_result()

        norm_text = self.normalize_text(raw_text)

        evidence: Dict[str, str] = {}
        review_flags: List[str] = []

        # 1. Title / Role
        title = self._extract_title(norm_text, evidence)

        # 2. Company Name
        company_name = self._extract_company(norm_text, evidence)

        # 3. Academic Criteria: CGPA, Percentages across tiers, Backlogs
        cgpa_criteria, academic_percentages, backlog_criteria = self._extract_academic_criteria(
            norm_text, evidence, review_flags
        )

        # 4. Degree & Branch Eligibility, Batch Years
        degree_eligibility, branch_eligibility, graduation_years = self._extract_education(
            norm_text, evidence
        )

        # 5. Experience Level & Job Type
        experience_level, job_type = self._extract_employment_type(norm_text, evidence)

        # 6. Workplace Mode & Location
        location, work_mode = self._extract_location_and_mode(norm_text, evidence)

        # 7. Compensation & Staged Progression
        salary_range, compensation_details = self._extract_compensation(
            norm_text, evidence, review_flags
        )

        # 8. Deadlines & Important Dates
        application_deadline, drive_date, joining_date = self._extract_dates_and_deadlines(
            norm_text, evidence, review_flags
        )

        # 9. Service Agreement / Bond
        bond_details = self._extract_bond(norm_text, evidence, review_flags)

        # 10. Selection / Interview Process
        selection_rounds = self._extract_selection_process(norm_text, evidence)

        # 11. Technical & Preferred Skills, Certifications
        required_skills, preferred_skills, certifications = self._extract_skills_and_certifications(
            norm_text, evidence, review_flags
        )

        # 12. Description summary
        description = self._extract_description(norm_text, evidence)

        # 13. External Application URL & Instructions
        application_url, application_instructions = self._extract_application_url_and_instructions(
            norm_text, evidence
        )

        return JdParseResult({
            # Standard legacy & DB-compatible fields
            "title": title,
            "description": description,
            "required_skills": required_skills,
            "preferred_skills": preferred_skills,
            "experience_level": experience_level,
            "cgpa_criteria": cgpa_criteria,
            "branch_eligibility": branch_eligibility,
            "location": location,
            "salary_range": salary_range,
            "raw_text_length": len(raw_text),

            # Extended General-Purpose Fields (Step C Improvement)
            "company_name": company_name,
            "job_type": job_type,
            "degree_eligibility": degree_eligibility,
            "graduation_years": graduation_years,
            "academic_percentages": academic_percentages,
            "backlog_criteria": backlog_criteria,
            "certifications": certifications,
            "compensation_details": compensation_details,
            "application_deadline": application_deadline,
            "drive_date": drive_date,
            "joining_date": joining_date,
            "work_mode": work_mode,
            "bond_details": bond_details,
            "selection_rounds": selection_rounds,
            "application_instructions": application_instructions,
            "application_url": application_url,
            "application_url_candidates": [{"url": u} for u in evidence.get("application_url_candidates", [])],

            # Traceability & Verification
            "review_flags": review_flags,
            "field_evidence": evidence
        })

    # =========================================================================
    # FIELD-SPECIFIC EXTRACTORS
    # =========================================================================

    def _extract_title(self, text: str, evidence: Dict[str, str]) -> Optional[str]:
        """Extract job designation / role title."""
        # 1. Label-based regex patterns
        patterns = [
            r'(?:job\s*title|designation|position|role|profile|hiring\s*for|opening\s*for)[\s:\-–—|]+([^\n\r,;|\t]+)',
            r'(?:recruitment\s*of|inviting\s*applications\s*for)[\s:\-–—|]+([^\n\r,;|\t]+)',
            r'(?:looking\s*for|seeking)(?:\s*(?:a|an))?[\s:\-–—|]+([^\n\r,;|\t]+?)(?:\s+(?:with|to|in|having|who)|\.|\n|$)'
        ]
        non_title_words = r'(?:bright\s+and\s+motivated|candidates?|freshers?|individuals?|talented|dynamic|eligible|graduates?|students?|overview|criteria|eligibility|notice|company|welcome|campus|our|team|office|locations?)'
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                # Clean prefix/suffix noise
                candidate = re.sub(r'^(?:is\s+|a\s+|an\s+)', '', candidate, flags=re.IGNORECASE).strip()
                candidate = re.sub(r'\s+(?:with|to|in|having|who).*$', '', candidate, flags=re.IGNORECASE).strip()
                if 3 <= len(candidate) <= 60 and not re.search(r'^(?:' + non_title_words + r')\b', candidate, re.IGNORECASE):
                    if not re.search(r'company|overview|eligibility|ctc|notice', candidate, re.IGNORECASE):
                        evidence["title"] = match.group(0).strip()
                        return candidate

        # 2. Heuristic search in the first 8 non-empty lines for typical engineering & operational titles
        role_keywords = (
            r'(?:technical\s+support(?:\s+executive)?|support\s+executive|support\s+engineer|'
            r'software\s+engineer|developer|consultant|full\s*stack|frontend|backend|'
            r'data\s+analyst|data\s+scientist|qa\s+engineer|devops|system\s+engineer|'
            r'graduate\s+engineer\s+trainee|associate\s+software\s+engineer|trainee|'
            r'intern|cloud\s+engineer|cyber\s+security\s+analyst|customer\s+support(?:\s+executive)?|'
            r'business\s+analyst|technical\s+consultant)'
        )
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for line in lines[:8]:
            if re.search(role_keywords, line, re.IGNORECASE) and len(line) <= 60:
                if not re.search(r'company|welcome|campus|placement|hiring|seeking|looking\s+for', line, re.IGNORECASE):
                    evidence["title"] = line
                    return line

        # 3. GLiNER zero-shot entity fallback if semantic model is available and deterministic methods found no title
        if gliner_service.is_available():
            try:
                intro_text = text[:1200]
                preds = gliner_service.predict_entities(
                    intro_text,
                    labels=["job title", "designation", "role"],
                    threshold=0.55
                )
                valid_gliner_titles = []
                known_tech_or_skills = {
                    "docker", "kubernetes", "linux", "python", "java", "react", "angular", "vue",
                    "aws", "azure", "gcp", "sql", "git", "c++", "c#", "html", "css", "javascript",
                    "typescript", "nosql", "node", "express", "fastify", "spring", "django"
                }
                title_role_pattern = r'\b(?:engineer|developer|architect|consultant|specialist|analyst|intern|lead|manager|administrator|executive|trainee|officer|associate|coordinator|scientist|designer|tester|programmer|sre|chaos|director|head)\b'

                for p in preds:
                    cand = re.sub(r'^(?:is\s+|a\s+|an\s+|the\s+|role\s+of\s+)', '', p["text"].strip(), flags=re.IGNORECASE).strip(" :,.-")
                    cand_lower = cand.lower()
                    if 4 <= len(cand) <= 60 and not re.search(r'^(?:' + non_title_words + r')\b', cand, re.IGNORECASE):
                        if not re.search(r'company|overview|eligibility|ctc|notice|salary|drive|campus|welcome|placement|opening|criteria|requirement', cand, re.IGNORECASE):
                            if cand_lower in self.KNOWN_SKILL_KEYWORDS or cand_lower in known_tech_or_skills:
                                continue
                            is_recognized_role = bool(re.search(title_role_pattern, cand, re.IGNORECASE))
                            is_multi_word_high_conf = len(cand.split()) >= 2 and p["score"] >= 0.70
                            if is_recognized_role or is_multi_word_high_conf:
                                valid_gliner_titles.append((cand, p["score"]))
                if valid_gliner_titles:
                    valid_gliner_titles.sort(key=lambda x: (x[1], len(x[0])), reverse=True)
                    best_title, best_score = valid_gliner_titles[0]
                    evidence["title"] = f"{best_title} [GLiNER: {best_score:.2f}]"
                    return best_title
            except Exception as e:
                logger.warning(f"GLiNER title extraction fallback error: {e}")

        return None

    def _extract_company(self, text: str, evidence: Dict[str, str]) -> Optional[str]:
        """Extract hiring company name."""
        patterns = [
            r'(?:company(?:\s*name)?|client|organization|recruiter)[\s:\-–—|]+([A-Za-z0-9\s\.\,\&\'\-]+)',
            r'About\s+([A-Z][A-Za-z0-9\s\.\&]+?)(?:\s*:|\n|—|–|\sis\s+)',
            r'(?:^|\n)\s*([A-Za-z0-9\.\& ]{2,50})\s+is\s+(?:visiting|hiring|recruiting|conducting)',
            r'(?:^|\n)\s*([A-Za-z0-9\.\& ]{2,50})\s+(?:campus\s+placement|recruitment\s+drive)'
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                cand = match.group(1).split("\n")[0].strip()
                # Clean trailing punctuation
                cand = cand.strip(" .,:-")
                if 2 <= len(cand) <= 50 and not re.search(r'placement|cell|notice|department|edumatrix|overview|criteria', cand, re.IGNORECASE):
                    evidence["company_name"] = match.group(0).strip()
                    return cand

        return None

    def _extract_academic_criteria(
        self,
        text: str,
        evidence: Dict[str, str],
        review_flags: List[str]
    ) -> Tuple[Optional[float], Optional[Dict[str, Optional[float]]], Optional[str]]:
        """
        Extract academic criteria:
        - CGPA criteria (strictly on 0-10 scale)
        - Academic percentages across tiers (10th, 12th, Diploma, Degree, PG)
        - Backlog / arrear restrictions
        Ensures percentages are NEVER falsely converted to CGPA.
        """
        cgpa_val: Optional[float] = None
        percentages: Dict[str, Optional[float]] = {
            "10th": None,
            "tenth": None,
            "12th": None,
            "twelfth": None,
            "diploma": None,
            "degree": None,
            "postgraduate": None
        }
        backlog_criteria: Optional[str] = None

        # 1. CGPA Extraction (Explicit CGPA/GPA context only)
        cgpa_patterns = [
            r'(?:minimum\s+|min\s+)?(?:cgpa|gpa|cutoff)[\s:=><\-–—]+([0-9]+(?:\.[0-9]+)?)(?:\s*(?:and\s*above|or\s*above|\+|/\s*10))?',
            r'(?:cgpa|gpa)\s+(?:of\s+|is\s+|>=|≥)?\s*([0-9]+(?:\.[0-9]+)?)(?:\s*(?:and\s*above|or\s*above|\+|/\s*10))?',
            r'([0-9]+(?:\.[0-9]+)?)\s*(?:and\s*above|or\s*above|\+)?\s*(?:cgpa|gpa)',
            r'minimum\s+([0-9]+(?:\.[0-9]+)?)\s*(?:in\s+)?(?:cgpa|gpa)',
            r'(?:minimum|min)\s+(?:cgpa|gpa)[\s:=><\-–—]+([0-9]+(?:\.[0-9]+)?)',
            r'\b([0-9]+(?:\.[0-9]+)?)\s*cgpa\s*required\b',
            r'\bcgpa\s*(?:>=|≥|:|is|=)\s*([0-9]+(?:\.[0-9]+)?)\b',
            r'\b([0-9]+(?:\.[0-9]+)?)\s*(?:&|and)\s*above\s*(?:in\s+)?(?:cgpa|gpa)\b',
            r'(?:cgpa|gpa)[\s:=]+([0-9]+(?:\.[0-9]+)?)\s*/\s*10',
        ]
        for p in cgpa_patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                try:
                    val = float(m.group(1))
                    if 4.0 <= val <= 10.0:
                        cgpa_val = val
                        evidence["cgpa_criteria"] = m.group(0).strip()
                        break
                except ValueError:
                    pass

        # 2. Percentage across academic levels
        # 10th & 12th combined (e.g. "Minimum 60% in 10th and 12th")
        tenth_twelfth_match = re.search(
            r'([0-9]{2}(?:\.[0-9]+)?)\s*%\s*(?:in|for)?\s*(?:both\s+)?(?:10th|class\s*10|sslc)\s*(?:and|&)\s*(?:12th|class\s*12|puc|hsc)',
            text,
            re.IGNORECASE
        )
        if not tenth_twelfth_match:
            tenth_twelfth_match = re.search(
                r'(?:10th|class\s*10|sslc)\s*(?:and|&)\s*(?:12th|class\s*12|puc|hsc)[^\n\r\d]{0,25}?([0-9]{2}(?:\.[0-9]+)?)\s*%',
                text,
                re.IGNORECASE
            )
        if tenth_twelfth_match:
            try:
                v = float(tenth_twelfth_match.group(1))
                if 40.0 <= v <= 100.0:
                    percentages["10th"] = v
                    percentages["tenth"] = v
                    percentages["12th"] = v
                    percentages["twelfth"] = v
                    evidence["academic_percentage_10th_12th"] = tenth_twelfth_match.group(0).strip()
            except ValueError:
                pass
        # 10th / SSLC / Class X
        tenth_patterns = [
            r'(?:10th(?:\s*(?:std|standard))?|sslc|class\s*(?:x|10)|matric(?:ulation)?)[^\n\r\d]{0,40}?([0-9]{2}(?:\.[0-9]+)?)\s*%',
            r'(?:10th|sslc|class\s*x|matric)[\s:=><\-–—|]+([0-9]{2}(?:\.[0-9]+)?)'
        ]
        for p in tenth_patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                try:
                    v = float(m.group(1))
                    if 40.0 <= v <= 100.0:
                        percentages["10th"] = v
                        percentages["tenth"] = v
                        evidence["academic_percentage_tenth"] = m.group(0).strip()
                        break
                except ValueError:
                    pass

        # 12th / PUC / HSC / Class XII
        twelfth_patterns = [
            r'(?:12th(?:\s*(?:std|standard))?|puc|hsc|class\s*(?:xii|12)|intermediate|\+2)[^\n\r\d]{0,40}?([0-9]{2}(?:\.[0-9]+)?)\s*%',
            r'(?:12th|puc|hsc|class\s*xii)[\s:=><\-–—|]+([0-9]{2}(?:\.[0-9]+)?)'
        ]
        for p in twelfth_patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                try:
                    v = float(m.group(1))
                    if 40.0 <= v <= 100.0:
                        percentages["12th"] = v
                        percentages["twelfth"] = v
                        evidence["academic_percentage_twelfth"] = m.group(0).strip()
                        break
                except ValueError:
                    pass

        # Diploma
        diploma_patterns = [
            r'(?:diploma)[^\n\r\d]{0,40}?([0-9]{2}(?:\.[0-9]+)?)\s*%',
            r'(?:diploma)[\s:=><\-–—|]+([0-9]{2}(?:\.[0-9]+)?)'
        ]
        for p in diploma_patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                try:
                    v = float(m.group(1))
                    if 40.0 <= v <= 100.0:
                        percentages["diploma"] = v
                        evidence["academic_percentage_diploma"] = m.group(0).strip()
                        break
                except ValueError:
                    pass

        # Degree / Graduation
        degree_patterns = [
            r'(?:degree|graduation|b\.?e|b\.?tech|ug|undergraduate|engineering\s*degree)[^\n\r\d]{0,40}?([0-9]{2}(?:\.[0-9]+)?)\s*%',
            r'([0-9]{2}(?:\.[0-9]+)?)\s*%\s*(?:(?:or|and)\s+[0-9\.]+\s*(?:cgpa|gpa)\s*)?(?:in|for)?\s*(?:graduation|degree|b\.?e|b\.?tech)',
            r'([0-9]{2}(?:\.[0-9]+)?)\s*%\s*(?:in|for|and\s+above\s+in|aggregate\s+in|or\s+above\s+in)?[^\n\r\d]{0,35}?(?:degree|graduation|b\.?e|b\.?tech)',
            r'minimum[^\n\r\d]{0,25}?([0-9]{2}(?:\.[0-9]+)?)\s*%[^\n\r\d]{0,25}?(?:graduation|degree)',
            r'(?:graduation\s+percentage|degree\s+percentage)[\s:=><\-–—|]+([0-9]{2}(?:\.[0-9]+)?)'
        ]
        for p in degree_patterns:
            deg_m = re.search(p, text, re.IGNORECASE)
            if deg_m:
                try:
                    v = float(deg_m.group(1))
                    if 40.0 <= v <= 100.0:
                        percentages["degree"] = v
                        evidence["academic_percentage_degree"] = deg_m.group(0).strip()
                        break
                except ValueError:
                    pass

        # Postgraduate
        pg_patterns = [
            r'(?:post[\s\-]*graduation|pg|m\.?e|m\.?tech|mca)[^\n\r\d]{0,40}?([0-9]{2}(?:\.[0-9]+)?)\s*%',
        ]
        for p in pg_patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                try:
                    v = float(m.group(1))
                    if 40.0 <= v <= 100.0:
                        percentages["postgraduate"] = v
                        evidence["academic_percentage_postgraduate"] = m.group(0).strip()
                        break
                except ValueError:
                    pass

        # Throughout academics rule (e.g., "60% throughout academics (10th, 12th, B.Tech)")
        throughout_match = re.search(
            r'([0-9]{2}(?:\.[0-9]+)?)\s*%\s*(?:throughout|across|aggregate\s*in\s*all|in\s*all\s*semesters|through\s*out)',
            text,
            re.IGNORECASE
        )
        if throughout_match:
            try:
                tv = float(throughout_match.group(1))
                if 40.0 <= tv <= 100.0:
                    evidence["academic_percentage_throughout"] = throughout_match.group(0).strip()
                    if percentages["10th"] is None:
                        percentages["10th"] = tv
                        percentages["tenth"] = tv
                    if percentages["12th"] is None:
                        percentages["12th"] = tv
                        percentages["twelfth"] = tv
                    if percentages["degree"] is None:
                        percentages["degree"] = tv
            except ValueError:
                pass

        # Check for review warning when percentage is specified but no CGPA
        if percentages["degree"] is not None and cgpa_val is None:
            review_flags.append(
                f"Degree requirement specified as percentage ({percentages['degree']}%) rather than CGPA cutoff. "
                "Do not convert automatically. Placement Officer should confirm institutional conversion."
            )

        # 3. Backlog Criteria
        backlog_patterns = [
            r'(?:no|zero|0)\s*(?:(?:active|standing|current)\s*)*(?:arrears?|backlogs?)(?:\s*allowed)?',
            r'(?:up\s*to|maximum|max)\s*([0-9]+)\s*(?:(?:active|standing|current)\s*)*(?:arrears?|backlogs?)(?:\s*allowed)?',
            r'([0-9]+)\s*(?:(?:active|standing|current)\s*)*(?:arrears?|backlogs?)(?:\s*allowed)?',
            r'(?:no\s*history\s*of\s*(?:arrears|backlogs))',
            r'(?:backlogs?|arrears?)[\s:\-–—|]+([^\n\r,;]+)'
        ]
        for bp in backlog_patterns:
            bm = re.search(bp, text, re.IGNORECASE)
            if bp_m := bm:
                matched_snippet = bp_m.group(0).strip()
                backlog_criteria = matched_snippet
                evidence["backlog_criteria"] = matched_snippet
                break

        # Only return dictionary if at least one academic percentage was extracted
        result_percentages = percentages if any(v is not None for v in percentages.values()) else None
        if result_percentages:
            pct_evidence = []
            for k in ["10th", "12th", "diploma", "degree", "postgraduate"]:
                if percentages[k] is not None:
                    ev_key = f"academic_percentage_{k}"
                    if ev_key in evidence:
                        pct_evidence.append(evidence[ev_key])
                    else:
                        pct_evidence.append(f"{k}: {percentages[k]}%")
            if pct_evidence:
                evidence["academic_percentages"] = pct_evidence

        return cgpa_val, result_percentages, backlog_criteria

    def _extract_education(
        self,
        text: str,
        evidence: Dict[str, str]
    ) -> Tuple[List[str], List[str], List[int]]:
        """Extract eligible degrees, branches, and graduation batches."""
        degrees: List[str] = []
        branches: List[str] = []
        batch_years: List[int] = []

        # 1. Degrees
        for pat, deg_code in self.DEGREE_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                degrees.append(deg_code)

        # 2. Branches
        text_lower = text.lower()
        found_branches = set()
        for term, standard_code in self.BRANCH_MAP.items():
            pattern = r'\b' + re.escape(term) + r'\b'
            if re.search(pattern, text_lower):
                found_branches.add(standard_code)

        # Check for circuital branches
        if re.search(r'\bcircuital\s*branches\b', text_lower):
            found_branches.update(["CSE", "IT", "ECE", "EEE"])

        # GLiNER semantic degree and branch enrichment
        if gliner_service.is_available():
            try:
                edu_preds = gliner_service.predict_entities(
                    text[:2500],
                    labels=["academic degree", "educational qualification", "academic branch", "engineering discipline"],
                    threshold=0.55
                )
                for ep in edu_preds:
                    lbl = ep["label"].lower()
                    ent_str = ep["text"].strip(" \t\n\r\"'()[]{}.,;:*•▪-–—")
                    if "degree" in lbl or "qualification" in lbl:
                        for pat, deg_code in self.DEGREE_PATTERNS:
                            if re.search(pat, ent_str, re.IGNORECASE):
                                if deg_code not in degrees:
                                    degrees.append(deg_code)
                                    evidence[f"gliner_degree_{deg_code}"] = f"{ent_str} [GLiNER: {ep['score']:.2f}]"
                    elif "branch" in lbl or "discipline" in lbl:
                        clean_b = ent_str.lower()
                        clean_b = re.sub(r'^(?:branch(?:es)?\s*(?:of|in)?|discipline\s*(?:of|in)?)\s*', '', clean_b).strip()
                        if clean_b in self.BRANCH_MAP:
                            b_code = self.BRANCH_MAP[clean_b]
                            if b_code not in found_branches:
                                found_branches.add(b_code)
                                evidence[f"gliner_branch_{b_code}"] = f"{ent_str} [GLiNER: {ep['score']:.2f}]"
                        else:
                            for term, b_code in self.BRANCH_MAP.items():
                                if len(term) >= 3 and term in clean_b:
                                    if b_code not in found_branches:
                                        found_branches.add(b_code)
                                        evidence[f"gliner_branch_{b_code}"] = f"{ent_str} [GLiNER: {ep['score']:.2f}]"
            except Exception as e:
                logger.warning(f"GLiNER education enrichment warning: {e}")

        degrees = list(dict.fromkeys(degrees))
        if degrees:
            evidence["degree_eligibility"] = ", ".join(degrees)

        branches = sorted(list(found_branches))
        if branches:
            evidence["branch_eligibility"] = ", ".join(branches)

        # 3. Graduation batch years (e.g. "2025", "2026")
        batch_years: List[str] = []
        batch_lines = [
            line for line in text.split("\n")
            if re.search(r'\b(?:batch|passout|passing\s*out|graduating|class\s*of)\b', line, re.IGNORECASE)
        ]
        for line in batch_lines:
            for y in re.findall(r'\b(202[3-9])\b', line):
                batch_years.append(y)

        # Standalone patterns
        for y in re.findall(r'\b(202[3-9])\s*batch\b', text, re.IGNORECASE):
            batch_years.append(y)

        batch_matches = re.finditer(
            r'(?:batch|passout|passing\s*out|class\s*of|graduates?|eligible\s*batch)[\s:\-–—]+([0-9\s,\/&and]+)',
            text,
            re.IGNORECASE
        )
        for bm in batch_matches:
            for y in re.findall(r'\b(202[3-9])\b', bm.group(1)):
                batch_years.append(y)

        batch_years = sorted(list(dict.fromkeys(batch_years)))
        if batch_years:
            evidence["graduation_years"] = ", ".join(batch_years)

        return degrees, branches, batch_years

    def _extract_employment_type(
        self,
        text: str,
        evidence: Dict[str, str]
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extract experience requirement and job/employment type."""
        exp_level: Optional[str] = None
        job_type: Optional[str] = None

        # Experience
        if re.search(r'\b(fresher|freshers|entry\s*level|graduate\s*trainee|0\s*years?)\b', text, re.IGNORECASE):
            exp_level = "fresher"
            evidence["experience_level"] = "fresher"
        else:
            match_range = re.search(r'([0-9]+\s*-\s*[0-9]+\s*(?:years?|yrs?))', text, re.IGNORECASE)
            if match_range:
                exp_level = match_range.group(1).strip()
                evidence["experience_level"] = exp_level
            else:
                match_plus = re.search(r'([0-9]+\+?\s*(?:years?|yrs?)\s*(?:of)?\s*experience)', text, re.IGNORECASE)
                if match_plus:
                    exp_level = match_plus.group(1).strip()
                    evidence["experience_level"] = exp_level

        # Fallback to GLiNER for experience requirements if not found
        if not exp_level and gliner_service.is_available():
            try:
                exp_preds = gliner_service.predict_entities(
                    text[:1500],
                    labels=["experience requirement", "internship prerequisite"],
                    threshold=0.55
                )
                for ep in exp_preds:
                    txt = ep["text"].lower()
                    if "intern" in txt:
                        exp_level = "internship"
                        evidence["experience_level"] = f"{ep['text']} [GLiNER: {ep['score']:.2f}]"
                        break
                    elif "fresher" in txt or "entry" in txt:
                        exp_level = "fresher"
                        evidence["experience_level"] = f"{ep['text']} [GLiNER: {ep['score']:.2f}]"
                        break
                    else:
                        ym = re.search(r'([0-9]+\s*-\s*[0-9]+\s*(?:years?|yrs?))', ep["text"], re.IGNORECASE)
                        if ym:
                            exp_level = ym.group(1).strip()
                            evidence["experience_level"] = f"{exp_level} [GLiNER: {ep['score']:.2f}]"
                            break
            except Exception as e:
                logger.warning(f"GLiNER experience extraction warning: {e}")

        # Job / Employment Type
        if re.search(r'\binternship\s*(?:cum|\+)\s*(?:placement|full\s*time|fte|job)\b', text, re.IGNORECASE):
            job_type = "Internship + Full-time"
        elif re.search(r'\binternship\b', text, re.IGNORECASE) and not re.search(r'\bfull\s*time\b', text, re.IGNORECASE):
            job_type = "Internship"
        elif re.search(r'\bfull\s*time\b', text, re.IGNORECASE):
            job_type = "Full-time"

        if job_type:
            evidence["job_type"] = job_type

        return exp_level, job_type

    def _extract_location_and_mode(
        self,
        text: str,
        evidence: Dict[str, str]
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extract job work location and work mode."""
        location: Optional[str] = None
        work_mode: Optional[str] = None

        # Work mode
        if re.search(r'\b(remote|work\s*from\s*home|wfh)\b', text, re.IGNORECASE):
            work_mode = "Remote"
        elif re.search(r'\bhybrid\b', text, re.IGNORECASE):
            work_mode = "Hybrid"
        elif re.search(r'\b(on-?site|in-?office|office)\b', text, re.IGNORECASE):
            work_mode = "On-site"

        if work_mode:
            evidence["work_mode"] = work_mode

        # Location
        loc_match = re.search(r'(?:job\s*location|location|work\s*location)[\s:\-–—|]+([A-Za-z\s,/\-]+)', text, re.IGNORECASE)
        if loc_match:
            cand = loc_match.group(1).split("\n")[0].strip()
            # Clean trailing noise
            cand = re.sub(r'[\r\n].*', '', cand).strip(" ,.-")
            if 2 <= len(cand) <= 45 and not re.search(r'qualification|experience|salary|mode', cand, re.IGNORECASE):
                location = cand
                evidence["location"] = loc_match.group(0).strip()

        if not location:
            common_cities = [
                "Bangalore", "Bengaluru", "Hyderabad", "Pune", "Mumbai", "Chennai",
                "Delhi", "Noida", "Gurugram", "Gurgaon", "Kolkata", "Mysore", "Mangalore", "Coimbatore"
            ]
            for city in common_cities:
                if re.search(r'\b' + re.escape(city) + r'\b', text, re.IGNORECASE):
                    location = city
                    evidence["location"] = city
                    break

        return location, work_mode

    def _extract_compensation(
        self,
        text: str,
        evidence: Dict[str, str],
        review_flags: List[str]
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Extract compensation:
        - Normalizes OCR artifacts such as commas in decimals (e.g. 2,40 -> 2.40)
        - Detects staged compensation (e.g. Internship stipend followed by Full-time CTC)
        - Prevents invalid min/max salary range conflation (e.g. 25k to 6.5 LPA)
        - Extracts flat/ranged annual CTC and stipend
        """
        salary_range: Optional[str] = None
        compensation_details: Dict[str, Any] = {
            "currency": "INR",
            "stipend": None,
            "full_time_ctc": None,
            "staged_compensation": []
        }

        # Normalize OCR comma in decimals for compensation (e.g., 'INR 2,40 - 3.60 Lakhs' -> 'INR 2.40 - 3.60 Lakhs')
        # Do not alter thousands separators like 1,00,000 or 25,000
        comp_text = re.sub(r'(\bINR|\bRs|₹|\bCTC|\bPackage|\bsalary|\bto|[–—-]|[\-–—])\s*(\d+),(\d{1,2})\b(?!\s*,?\d{3})', r'\1 \2.\3', text, flags=re.IGNORECASE)
        comp_text = re.sub(r'(\d+),(\d{1,2})\s*(?:-|–|—|to)\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?|lac)', r'\1.\2 - \3 Lakhs', comp_text, flags=re.IGNORECASE)

        # 1. Detect Staged Compensation (Stipend + Post-conversion / Annual CTC)
        stipend_match = re.search(
            r'(?:stipend(?:\s*(?:during|for)\s*(?:[0-9]+[\s\-]*months?\s*)?(?:internship|training|probation))?|internship\s*stipend)(?:[\s:\-–—|]+|\s+of\s+)([₹RsINR\.\s0-9,]+(?:\s*(?:\/|per)\s*(?:month|mo|pm))?)',
            comp_text,
            re.IGNORECASE
        )
        ctc_match = re.search(
            r'(?:(?:annual|full[\s\-]*time)\s+)?(?:ctc|package|salary(?:\s*range)?|gross|fixed|remuneration)(?:\s*(?:upon|after|post)\s*(?:full[\s\-]*time\s*)?(?:absorption|confirmation|completion))?(?:[\s:\-–—|]+|(?:\s+(?:offered\s+)?(?:is|of)\s+))([₹RsINR\.\s0-9,\-–—to]+?(?:lpa|lakhs?(?:\s*(?:per\s*annum|pa))?|lac|inr|per\s*annum|pa)\b)',
            comp_text,
            re.IGNORECASE
        )

        stipend_val = stipend_match.group(1).split("\n")[0].strip() if stipend_match else None
        ctc_val = ctc_match.group(1).split("\n")[0].strip() if ctc_match else None

        # Dedicated fallback for explicit CTC range with INR / Lakhs per annum
        if not ctc_val:
            ctc_range_fallback = re.search(
                r'(?:(?:annual\s+)?(?:ctc|package|salary)[\s:\-–—|]*)?(?:inr|rs\.?|₹)?\s*([0-9]+(?:\.[0-9]+)?)\s*[\-–—to\s]+\s*(?:inr|rs\.?|₹)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:lpa|lakhs?(?:\s*(?:per\s*annum|pa))?|lac)',
                comp_text,
                re.IGNORECASE
            )
            if ctc_range_fallback:
                low_c, high_c = ctc_range_fallback.group(1), ctc_range_fallback.group(2)
                ctc_val = f"INR {low_c} - {high_c} Lakhs per annum"

        # Clean trailing punctuation
        if stipend_val:
            stipend_val = stipend_val.strip(" .,:-")
            if not re.search(r'\d', stipend_val):
                stipend_val = None
        if ctc_val:
            ctc_val = ctc_val.strip(" .,:-")
            if not re.search(r'\d', ctc_val):
                ctc_val = None

        if stipend_val and not ctc_val:
            lpa_m = re.search(r'\b([0-9]+(?:\.[0-9]+)?\s*lpa)\b', comp_text, re.IGNORECASE)
            if lpa_m:
                ctc_val = lpa_m.group(1).strip()

        # Check for internship duration
        intern_duration_match = re.search(r'([0-9]+)\s*[\-]?\s*months?\s*(?:internship|training)?', comp_text, re.IGNORECASE)
        if not intern_duration_match:
            intern_duration_match = re.search(r'for\s+([0-9]+)\s*[\-]?\s*months?', comp_text, re.IGNORECASE)
        if intern_duration_match:
            n_months = int(intern_duration_match.group(1))
            intern_duration = f"{n_months} months" if n_months > 1 else f"{n_months} month"
        else:
            intern_duration = None

        if stipend_val and ctc_val and (stipend_val.lower() != ctc_val.lower()):
            clean_amt = re.search(r'([0-9,]+)', stipend_val)
            amt = clean_amt.group(1) if clean_amt else stipend_val
            stipend_formatted = f"₹{amt}/month"
            if intern_duration:
                stipend_formatted += f" ({intern_duration})"

            stipend_display = stipend_val if "month" in stipend_val.lower() else stipend_formatted
            compensation_details["stipend"] = stipend_display
            compensation_details["full_time_ctc"] = ctc_val
            compensation_details["annual_ctc"] = ctc_val
            compensation_details["staged_compensation"] = [
                {"stage": f"Internship ({intern_duration or 'Period'})", "amount": stipend_display},
                {"stage": "Full Time / Post-Conversion", "amount": ctc_val}
            ]
            salary_range = ctc_val
            evidence["salary_range"] = ctc_val
            evidence["stipend"] = stipend_display
            review_flags.append(
                f"Staged compensation detected ({stipend_display} internship stipend, followed by {ctc_val} full-time CTC). Preserved as distinct compensation details."
            )
            return salary_range, compensation_details

        # 2. Check for numeric lakhs in rupees (e.g. ₹14,00,000 - ₹20,00,000 PA)
        num_lakhs_range = re.search(
            r'[₹Rs\.\s]*(\d{1,2})(?:,00,000|00000)\s*[\-–—to\s]+\s*[₹Rs\.\s]*(\d{1,2})(?:,00,000|00000)\s*(?:pa|per\s*annum|ctc)?',
            comp_text,
            re.IGNORECASE
        )
        if num_lakhs_range:
            low_l, high_l = num_lakhs_range.group(1), num_lakhs_range.group(2)
            salary_range = f"{low_l} - {high_l} LPA"
            compensation_details["full_time_ctc"] = salary_range
            evidence["salary_range"] = num_lakhs_range.group(0).strip()
            return salary_range, compensation_details

        num_lakh_single = re.search(
            r'[₹Rs\.\s]*(\d{1,2})(?:,00,000|00000)\s*(?:pa|per\s*annum|ctc)?\b',
            comp_text,
            re.IGNORECASE
        )
        if num_lakh_single:
            single_l = num_lakh_single.group(1)
            salary_range = f"{single_l} LPA"
            compensation_details["full_time_ctc"] = salary_range
            evidence["salary_range"] = num_lakh_single.group(0).strip()
            return salary_range, compensation_details

        # 3. Standard CTC / Salary Range (e.g. ₹8-12 LPA, 6.5 LPA)
        match_lpa_range = re.search(
            r'([₹RsINR\.\s0-9]+(?:\.[0-9]+)?\s*[\-–—to\s]+\s*[₹RsINR\.\s0-9]+(?:\.[0-9]+)?\s*(?:lpa|lakhs?(?:\s*(?:per\s*annum|pa))?|lac))',
            comp_text,
            re.IGNORECASE
        )
        if match_lpa_range:
            salary_range = match_lpa_range.group(1).strip()
            compensation_details["full_time_ctc"] = salary_range
            evidence["salary_range"] = salary_range
            return salary_range, compensation_details

        # Single LPA value
        match_single_lpa = re.search(
            r'([₹RsINR\.\s0-9]+(?:\.[0-9]+)?\s*(?:lpa|lakhs?(?:\s*(?:per\s*annum|pa))?|lac))',
            comp_text,
            re.IGNORECASE
        )
        if match_single_lpa:
            salary_range = match_single_lpa.group(1).strip()
            compensation_details["full_time_ctc"] = salary_range
            evidence["salary_range"] = salary_range
            return salary_range, compensation_details

        # General CTC label match
        if ctc_val and len(ctc_val) <= 30 and re.search(r'\d', ctc_val):
            salary_range = ctc_val
            compensation_details["full_time_ctc"] = ctc_val
            evidence["salary_range"] = ctc_val
            return salary_range, compensation_details

        if stipend_val and len(stipend_val) <= 30 and re.search(r'\d', stipend_val):
            salary_range = f"Stipend: {stipend_val}"
            compensation_details["stipend"] = stipend_val
            evidence["salary_range"] = stipend_val
            return salary_range, compensation_details

        return None, compensation_details

    def _extract_dates_and_deadlines(
        self,
        text: str,
        evidence: Dict[str, str],
        review_flags: List[str]
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extract application deadline, placement drive date, and joining date.
        Flags incomplete dates (missing year) without fabricating calendar years.
        """
        deadline: Optional[str] = None
        drive_date: Optional[str] = None
        joining_date: Optional[str] = None

        # 1. Application Deadline Patterns
        deadline_patterns = [
            r'(?:last\s*date\s*(?:of|for)?\s*(?:online\s*)?(?:application|registration|applying|submission))[\s:\-–—|]+([^\n\r\.;]+)',
            r'(?:application\s*closing\s*date|closing\s*date)(?:[\s:\-–—|]+|\s+is\s+)([^\n\r\.;]+)',
            r'(?:last\s*date\s*(?:to\s*(?:apply|register)|for\s*(?:student\s*)?(?:registration|applying|submission)))(?:[\s:\-–—|]+|\s+is\s+)([^\n\r\.;]+)',
            r'(?:application\s*deadline|registration\s*deadline|apply\s*on\s*or\s*before|apply\s*by|apply\s*before|(?:applications?|registrations?)\s*closes?(?:\s*on)?)(?:[\s:\-–—|]+|\s+is\s+)([^\n\r\.;]+)',
            r'(?:deadline\s*for\s*(?:online\s*)?(?:application|registration|submission))[\s:\-–—|]+([^\n\r\.;]+)',
            r'deadline[\s:\-–—|]+([^\n\r\.;]+)'
        ]

        for p in deadline_patterns:
            dm = re.search(p, text, re.IGNORECASE)
            if dm:
                raw_snippet = dm.group(1).strip()
                evidence["application_deadline"] = dm.group(0).strip()
                # Check for year presence
                has_year = bool(re.search(r'\b20[2-9][0-9]\b', raw_snippet))
                if not has_year:
                    review_flags.append(
                        f"Incomplete date: Missing year in deadline expression '{raw_snippet}'. Placement Officer confirmation required."
                    )
                    deadline = raw_snippet  # Keep raw text for review, do not hallucinate year
                else:
                    # Isolate date submatch from snippet to ignore extraneous trailing notes
                    date_submatch = re.search(
                        r'(\d{1,2}(?:st|nd|rd|th|["\'“”‘’`]+)?[\s\/\-\.]+(?:[A-Za-z]{3,9}|\d{1,2})[\s\/\-\.]+\d{4}(?:\s*(?:,|at|@)?\s*\d{1,2}(?::\d{2})?\s*(?:am|pm))?)',
                        raw_snippet,
                        re.IGNORECASE
                    )
                    if not date_submatch:
                        date_submatch = re.search(
                            r'([A-Za-z]{3,9}\s+\d{1,2}(?:st|nd|rd|th|["\'“”‘’`]+)?\s*,?\s*\d{4}(?:\s*(?:,|at|@)?\s*\d{1,2}(?::\d{2})?\s*(?:am|pm))?)',
                            raw_snippet,
                            re.IGNORECASE
                        )
                    date_target = date_submatch.group(1).strip() if date_submatch else raw_snippet
                    deadline = self._format_date_iso(date_target) or raw_snippet
                break

        # 2. Drive Date
        drive_patterns = [
            r'(?:campus\s*drive\s*date|drive\s*date|interview\s*date|test\s*date|date\s*of\s*drive)[\s:\-–—|]+([^\n\r,\.;]+)',
            r'(?:drive\s*on|interviews?\s*on)[\s:\-–—|]+([^\n\r,\.;]+)'
        ]
        for dp in drive_patterns:
            drm = re.search(dp, text, re.IGNORECASE)
            if drm:
                raw_snippet = drm.group(1).strip()
                evidence["drive_date"] = drm.group(0).strip()
                has_year = bool(re.search(r'\b20[2-9][0-9]\b', raw_snippet))
                if not has_year:
                    review_flags.append(
                        f"Incomplete date: Missing year in placement drive date '{raw_snippet}'."
                    )
                    drive_date = raw_snippet
                else:
                    drive_date = self._format_date_iso(raw_snippet) or raw_snippet
                break

        # 3. Joining Date
        join_patterns = [
            r'(?:date\s*of\s*joining|joining\s*date|joining)[\s:\-–—|]+([^\n\r,\.;]+)'
        ]
        for jp in join_patterns:
            jm = re.search(jp, text, re.IGNORECASE)
            if jm:
                raw_snippet = jm.group(1).strip()
                evidence["joining_date"] = jm.group(0).strip()
                if re.search(r'\b202[4-9]\b', raw_snippet):
                    joining_date = self._format_date_iso(raw_snippet) or raw_snippet
                else:
                    joining_date = raw_snippet
                break

        return deadline, drive_date, joining_date

    def _format_date_iso(self, date_str: str) -> Optional[str]:
        """Convert varied natural language date strings into ISO format (YYYY-MM-DDTHH:MM)."""
        if not date_str:
            return None
        clean = date_str.strip()

        # 1. Clean OCR quote noise on ordinals: e.g. 19" October, 19' October, 19” October, 19’ October
        clean = re.sub(r'(\d{1,2})\s*["\'“”‘’`]+', r'\1', clean)
        # 2. Clean standard ordinals: 1st, 2nd, 3rd, 19th
        clean_clean = re.sub(r'(\d+)(?:st|nd|rd|th)', r'\1', clean, flags=re.IGNORECASE)
        clean_clean = clean_clean.strip(" .,;:-|–—")

        # Extract time if present
        time_part = "00:00"
        time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))', clean, re.IGNORECASE)
        if time_match:
            try:
                t_str = time_match.group(1).upper()
                if ":" not in t_str:
                    t_str = t_str.replace(" AM", ":00 AM").replace(" PM", ":00 PM")
                    t_str = t_str.replace("AM", ":00 AM").replace("PM", ":00 PM")
                parsed_time = datetime.strptime(t_str.strip(), "%I:%M %p")
                time_part = parsed_time.strftime("%H:%M")
            except Exception:
                pass

        # Try dateparser if available (handles natural language dates)
        try:
            import dateparser
            parsed_dp = dateparser.parse(
                clean_clean,
                settings={
                    'PREFER_DAY_OF_MONTH': 'first',
                    'DATE_ORDER': 'DMY',
                    'STRICT_PARSING': False
                }
            )
            if parsed_dp and 2020 <= parsed_dp.year <= 2035:
                final_time = parsed_dp.strftime("%H:%M") if (parsed_dp.hour != 0 or parsed_dp.minute != 0) else time_part
                return parsed_dp.strftime(f"%Y-%m-%dT{final_time}")
        except Exception as dp_err:
            logger.debug(f"dateparser parsing skipped: {dp_err}")

        # Common format trials
        formats = [
            "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y",
            "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y",
            "%d %B %Y %I:%M %p", "%d %b %Y %I:%M %p",
            "%d-%m-%Y %I:%M %p", "%Y-%m-%d %H:%M"
        ]

        # Try parsing date component
        for fmt in formats:
            try:
                dt = datetime.strptime(clean_clean.strip(), fmt)
                return dt.strftime(f"%Y-%m-%dT{time_part}")
            except ValueError:
                pass

        # Regex fallback: Day Month Year (e.g. 15 Oct 2026 or 15/10/2026)
        day_month_year = re.search(
            r'(\d{1,2})[\s\/\-\.]([A-Za-z]{3,9}|\d{1,2})[\s\/\-\.](\d{4})',
            clean_clean
        )
        if day_month_year:
            day, month_str, year = day_month_year.groups()
            try:
                # Numeric month
                if month_str.isdigit():
                    dt = datetime(int(year), int(month_str), int(day))
                else:
                    dt = datetime.strptime(f"{day} {month_str[:3]} {year}", "%d %b %Y")
                return dt.strftime(f"%Y-%m-%dT{time_part}")
            except Exception:
                pass

        # Regex fallback: Year Month Day (e.g. 2026-11-30)
        year_month_day = re.search(
            r'(\d{4})[\s\/\-\.](\d{1,2}|[A-Za-z]{3,9})[\s\/\-\.](\d{1,2})',
            clean_clean
        )
        if year_month_day:
            year, month_str, day = year_month_day.groups()
            try:
                if month_str.isdigit():
                    dt = datetime(int(year), int(month_str), int(day))
                else:
                    dt = datetime.strptime(f"{year} {month_str[:3]} {day}", "%Y %b %d")
                return dt.strftime(f"%Y-%m-%dT{time_part}")
            except Exception:
                pass

        return None

    def _extract_bond(
        self,
        text: str,
        evidence: Dict[str, str],
        review_flags: List[str]
    ) -> Optional[str]:
        """Extract service agreement or bond terms."""
        bond_patterns = [
            r'((?:service\s*agreement|bond)(?:[\s:\-–—|]+|\s+(?:of|for)\s+)[0-9]+\s*(?:years?|months?)[^\n\r\.;]*)',
            r'([0-9]+\s*(?:years?|months?)\s*(?:service\s*agreement|bond))',
            r'(?:execute|sign)\s+(?:a\s+)?service\s+agreement\s+(?:of|for)\s+([0-9]+\s*(?:years?|months?)(?:\s*\([^\)]+\))?[^\n\r\.;]*)',
            r'(?:bond\s*period|service\s*commitment)[\s:\-–—|]+([^\n\r\.;]+)'
        ]
        for bp in bond_patterns:
            bm = re.search(bp, text, re.IGNORECASE)
            if bm:
                bond_str = bm.group(0).strip()
                evidence["bond_details"] = bond_str
                review_flags.append(f"Service agreement / bond requirement detected: '{bond_str}'.")
                return bond_str

        return None

    def _extract_selection_process(
        self,
        text: str,
        evidence: Dict[str, str]
    ) -> List[str]:
        """Extract recruitment selection rounds."""
        rounds: List[str] = []
        round_matches = re.finditer(
            r'(?:round\s*[0-9]+|step\s*[0-9]+)[\s:\-–—|]+([^\n\r;,]+)',
            text,
            re.IGNORECASE
        )
        for rm in round_matches:
            r_text = rm.group(0).strip()
            if 4 <= len(r_text) <= 60:
                rounds.append(r_text)

        if not rounds:
            # Look for general selection process section
            sp_match = re.search(
                r'(?:selection\s*process|recruitment\s*process|rounds\s*of\s*interview)[\s:\-–—]+([^\n\n]+)',
                text,
                re.IGNORECASE
            )
            if sp_match:
                section = sp_match.group(1).strip()
                split_rounds = [s.strip(" -•") for s in re.split(r'[,;]|\n', section) if len(s.strip()) > 3]
                rounds.extend(split_rounds[:5])

        if rounds:
            evidence["selection_rounds"] = " -> ".join(rounds)

        return rounds

    def _extract_skills_and_certifications(
        self,
        text: str,
        evidence: Dict[str, str],
        review_flags: List[str]
    ) -> Tuple[List[str], List[str], List[str]]:
        """
        Segment text into required vs preferred skills and professional certifications.
        Prevents overlapping classifications.
        """
        # Section demarcation headers
        req_headers = r'(?:required\s*skills|technical\s*requirements|must[\s\-]*have(?:\s*skills)?|mandatory\s*skills|core\s*competencies|eligibility\s*skills)'
        pref_headers = r'(?:preferred\s*skills|nice[\s\-]*to[\s\-]*have|good[\s\-]*to[\s\-]*have|bonus\s*points|desired\s*skills)'
        cert_headers = r'(?:certifications?|certified\s*in)'

        cert_match = re.search(cert_headers, text, re.IGNORECASE)
        req_match = re.search(req_headers, text, re.IGNORECASE)
        pref_match = re.search(pref_headers, text, re.IGNORECASE)

        required_text = ""
        preferred_text = ""

        if req_match and pref_match:
            if req_match.start() < pref_match.start():
                required_text = text[req_match.start():pref_match.start()]
                end_pos = cert_match.start() if cert_match and cert_match.start() > pref_match.start() else len(text)
                preferred_text = text[pref_match.start():end_pos]
            else:
                end_pos = cert_match.start() if cert_match and cert_match.start() > req_match.start() else len(text)
                preferred_text = text[pref_match.start():req_match.start()]
                required_text = text[req_match.start():end_pos]
        elif req_match:
            end_pos = cert_match.start() if cert_match and cert_match.start() > req_match.start() else len(text)
            required_text = text[req_match.start():end_pos]
        elif pref_match:
            end_pos = cert_match.start() if cert_match and cert_match.start() > pref_match.start() else len(text)
            preferred_text = text[pref_match.start():end_pos]
            required_text = text[:pref_match.start()]
        else:
            required_text = text

        # Extract skills using vocabulary and regex
        req_raw = self._find_skills_in_segment(required_text)
        pref_raw = self._find_skills_in_segment(preferred_text)

        # Deduplicate: Required takes precedence
        req_set = set(req_raw)
        pref_raw = [s for s in pref_raw if s not in req_set]

        # Format skill names
        req_skills = [self._format_skill_name(s) for s in req_raw]
        pref_skills = [self._format_skill_name(s) for s in pref_raw]

        # Additive GLiNER entity enrichment (captures unlisted frameworks, modern libraries, soft skills)
        if gliner_service.is_available():
            self._enrich_skills_with_gliner(
                required_text=required_text,
                preferred_text=preferred_text,
                req_skills=req_skills,
                pref_skills=pref_skills,
                evidence=evidence
            )

        # Extract certifications
        certifications: List[str] = []
        cert_patterns = [
            r'\b(aws\s+certified[^\n,;]*)',
            r'\b(azure\s+certified[^\n,;]*)',
            r'\b(ccna|ccnp)\b',
            r'\b(red\s*hat\s+certified[^\n,;]*)',
            r'\b(ocpjp|oracle\s+certified[^\n,;]*)',
            r'\b(certified\s+kubernetes\s+administrator|cka|ckad)\b'
        ]
        for cp in cert_patterns:
            cm = re.search(cp, text, re.IGNORECASE)
            if cm:
                certifications.append(cm.group(0).strip().title())

        certifications = list(dict.fromkeys(certifications))

        if req_skills:
            evidence["required_skills"] = ", ".join(req_skills)
        if pref_skills:
            evidence["preferred_skills"] = ", ".join(pref_skills)
        if certifications:
            evidence["certifications"] = ", ".join(certifications)

        if not req_skills and not pref_skills:
            review_flags.append(
                "No technical skills identified automatically from the text. Placement Officer should review and add required skills."
            )

        return req_skills, pref_skills, certifications

    def _find_skills_in_segment(self, segment: str) -> List[str]:
        """Scan segment for known technical skills."""
        if not segment:
            return []
        found: List[str] = []
        seg_lower = segment.lower()
        for skill in self.KNOWN_SKILL_KEYWORDS:
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, seg_lower):
                found.append(skill)
        return list(dict.fromkeys(found))

    def _format_skill_name(self, skill: str) -> str:
        """Format skill names with standard industry casing."""
        special_casing = {
            "python": "Python",
            "java": "Java",
            "c++": "C++",
            "c#": "C#",
            "c": "C",
            "javascript": "JavaScript",
            "typescript": "TypeScript",
            "golang": "Golang",
            "go": "Go",
            "flutter": "Flutter",
            "dart": "Dart",
            "firebase": "Firebase",
            "helm": "Helm",
            "prometheus": "Prometheus",
            "grafana": "Grafana",
            "terraform": "Terraform",
            "linux": "Linux",
            "rust": "Rust",
            "ruby": "Ruby",
            "php": "PHP",
            "swift": "Swift",
            "kotlin": "Kotlin",
            "react": "React",
            "angular": "Angular",
            "vue": "Vue",
            "node": "Node.js",
            "nodejs": "Node.js",
            "node.js": "Node.js",
            "express": "Express",
            "django": "Django",
            "flask": "Flask",
            "fastapi": "FastAPI",
            "spring boot": "Spring Boot",
            "nextjs": "Next.js",
            "sql": "SQL",
            "mysql": "MySQL",
            "postgresql": "PostgreSQL",
            "postgres": "PostgreSQL",
            "mongodb": "MongoDB",
            "redis": "Redis",
            "docker": "Docker",
            "kubernetes": "Kubernetes",
            "k8s": "Kubernetes",
            "aws": "AWS",
            "gcp": "GCP",
            "azure": "Azure",
            "git": "Git",
            "ci/cd": "CI/CD",
            "machine learning": "Machine Learning",
            "deep learning": "Deep Learning",
            "ai": "AI",
            "nlp": "NLP",
            "data structures": "Data Structures",
            "algorithms": "Algorithms",
            "dsa": "DSA",
            "rest api": "REST API",
            "power bi": "Power BI",
            "sap abap": "SAP ABAP",
            "sap": "SAP",
            "customer support": "Customer Support",
            "technical support": "Technical Support",
            "troubleshooting": "Troubleshooting",
            "crm": "CRM",
            "helpdesk": "Helpdesk",
            "problem solving": "Problem Solving",
            "communication": "Communication",
            "client communication": "Client Communication",
            "erp": "ERP",
            "incident management": "Incident Management",
            "ticketing": "Ticketing"
        }
        return special_casing.get(skill.lower(), skill.title())

    def _clean_and_validate_skill_entity(self, ent_text: str) -> Optional[str]:
        """Validate and clean a candidate skill entity from GLiNER."""
        if not ent_text:
            return None
        clean = ent_text.strip(" \t\n\r\"'()[]{}.,;:*•▪-–—")
        # Strip common leading noise
        clean = re.sub(
            r'^(?:experience\s+(?:in|with)|knowledge\s+of|proficiency\s+in|familiarity\s+with|understanding\s+of|hands[\s\-]*on\s+with|skills?\s+in)\s+',
            '',
            clean,
            flags=re.IGNORECASE
        ).strip(" \t\n\r\"'()[]{}.,;:*•▪-–—")
        # Strip common trailing generic descriptors (e.g. "Qdrant vector database" -> "Qdrant", "Agile environments" -> "Agile")
        clean = re.sub(r'\s+(?:vector\s+)?databases?$', '', clean, flags=re.IGNORECASE)
        clean = re.sub(r'\s+environments?$', '', clean, flags=re.IGNORECASE)
        clean = re.sub(r'\s+frameworks?$', '', clean, flags=re.IGNORECASE)
        clean = re.sub(r'\s+platforms?$', '', clean, flags=re.IGNORECASE)
        clean = re.sub(r'\s+technolog(?:y|ies)$', '', clean, flags=re.IGNORECASE)
        clean = re.sub(r'\s+tools?$', '', clean, flags=re.IGNORECASE)
        clean = clean.strip(" \t\n\r\"'()[]{}.,;:*•▪-–—")
        if len(clean) < 2 or len(clean) > 40:
            return None
        # Disallow pure numbers, percentages, or punctuation
        if re.match(r'^[\d\.\%\s\-\/\:]+$', clean):
            return None
        # Disallow blacklisted stop words and non-skill entities
        stop_words = {
            "skill", "skills", "requirement", "requirements", "qualification", "qualifications",
            "responsibilities", "experience", "candidate", "candidates", "team", "work", "role",
            "job", "company", "degree", "branch", "engineering", "b.tech", "m.tech", "knowledge",
            "ability", "proficient", "familiar", "hands-on", "understanding", "good", "strong",
            "excellent", "basic", "advanced", "etc", "years", "fresher", "freshers", "students",
            "graduates", "notice", "criteria", "eligibility", "overview", "drive", "interview",
            "process", "location", "salary", "stipend", "package", "ctc", "lpa", "inr", "per annum",
            "written", "verbal", "communication", "opportunity", "profile", "discipline", "applicant"
        }
        if clean.lower() in stop_words:
            return None
        # Formatting casing
        low = clean.lower()
        if low in self.KNOWN_SKILL_KEYWORDS:
            return self._format_skill_name(low)
        # If all lowercase or all uppercase (and > 4 chars), titlecase; else preserve exact casing
        if clean.islower():
            return clean.title() if len(clean) > 4 else clean.upper()
        if clean.isupper() and len(clean) > 5:
            return clean.title()
        return clean

    def _chunk_text_for_gliner(self, text: str, max_chars: int = 750) -> List[str]:
        """
        Split text into bounded chunks below GLiNER's 384-token limit (~750 chars / ~150 words),
        preserving sentence and bullet boundaries without dropping text.
        """
        if not text or not text.strip():
            return []

        raw_lines = text.splitlines()
        segments: List[str] = []
        for line in raw_lines:
            line = line.strip()
            if not line:
                continue
            sentences = re.split(r'(?<=[.!?])\s+', line)
            for s in sentences:
                s = s.strip()
                if s:
                    segments.append(s)

        chunks: List[str] = []
        current_chunk = ""

        for seg in segments:
            if len(current_chunk) + (1 if current_chunk else 0) + len(seg) <= max_chars:
                current_chunk = (current_chunk + " " + seg).strip() if current_chunk else seg
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                
                if len(seg) > max_chars:
                    words = seg.split()
                    sub_chunk = ""
                    for w in words:
                        if len(sub_chunk) + (1 if sub_chunk else 0) + len(w) <= max_chars:
                            sub_chunk = (sub_chunk + " " + w).strip() if sub_chunk else w
                        else:
                            if sub_chunk:
                                chunks.append(sub_chunk)
                            sub_chunk = w
                    current_chunk = sub_chunk
                else:
                    current_chunk = seg

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _enrich_skills_with_gliner(
        self,
        required_text: str,
        preferred_text: str,
        req_skills: List[str],
        pref_skills: List[str],
        evidence: Dict[str, str]
    ) -> None:
        """Enrich required and preferred skill lists using bounded chunked GLiNER zero-shot entity extraction."""
        target_labels = ["technical skill", "software tool", "soft skill"]
        req_keys = {skill_normalizer.clean_text(s) for s in req_skills}
        req_canon_keys = {skill_normalizer.get_canonical(s) for s in req_skills}
        pref_keys = {skill_normalizer.clean_text(s) for s in pref_skills}
        pref_canon_keys = {skill_normalizer.get_canonical(s) for s in pref_skills}

        gliner_added_req: List[Tuple[str, float]] = []
        gliner_added_pref: List[Tuple[str, float]] = []

        # 1. Required skills segment (chunked to ensure every chunk < 384 tokens)
        if required_text and required_text.strip():
            req_chunks = self._chunk_text_for_gliner(required_text, max_chars=750)
            for chunk in req_chunks:
                try:
                    req_preds = gliner_service.predict_entities(
                        chunk,
                        labels=target_labels,
                        threshold=0.50
                    )
                except Exception as e:
                    logger.warning(f"GLiNER inference error on required skills chunk: {e}")
                    continue
                for rp in req_preds:
                    c_skill = self._clean_and_validate_skill_entity(rp["text"])
                    if not c_skill:
                        continue
                    k_clean = skill_normalizer.clean_text(c_skill)
                    k_canon = skill_normalizer.get_canonical(c_skill)
                    if k_clean not in req_keys and k_canon not in req_canon_keys:
                        req_skills.append(c_skill)
                        req_keys.add(k_clean)
                        req_canon_keys.add(k_canon)
                        gliner_added_req.append((c_skill, rp["score"]))

        # 2. Preferred skills segment (chunked to ensure every chunk < 384 tokens)
        if preferred_text and preferred_text.strip():
            pref_chunks = self._chunk_text_for_gliner(preferred_text, max_chars=750)
            for chunk in pref_chunks:
                try:
                    pref_preds = gliner_service.predict_entities(
                        chunk,
                        labels=target_labels,
                        threshold=0.50
                    )
                except Exception as e:
                    logger.warning(f"GLiNER inference error on preferred skills chunk: {e}")
                    continue
                for pp in pref_preds:
                    c_skill = self._clean_and_validate_skill_entity(pp["text"])
                    if not c_skill:
                        continue
                    k_clean = skill_normalizer.clean_text(c_skill)
                    k_canon = skill_normalizer.get_canonical(c_skill)
                    if (k_clean not in req_keys and k_canon not in req_canon_keys and
                        k_clean not in pref_keys and k_canon not in pref_canon_keys):
                        pref_skills.append(c_skill)
                        pref_keys.add(k_clean)
                        pref_canon_keys.add(k_canon)
                        gliner_added_pref.append((c_skill, pp["score"]))

        # Record GLiNER evidence
        if gliner_added_req:
            evidence["gliner_required_skills"] = ", ".join([f"{s} ({sc:.2f})" for s, sc in gliner_added_req])
            evidence["required_skills"] = ", ".join(req_skills)
        if gliner_added_pref:
            evidence["gliner_preferred_skills"] = ", ".join([f"{s} ({sc:.2f})" for s, sc in gliner_added_pref])
            evidence["preferred_skills"] = ", ".join(pref_skills)

    IGNORED_URL_HOSTS = {
        "schemas.openxmlformats.org",
        "schemas.microsoft.com",
        "www.w3.org",
        "w3.org",
        "purl.org",
        "xml.org",
        "localhost",
        "127.0.0.1",
        "schema.org",
    }

    def _preprocess_text_for_urls(self, text: str) -> str:
        """
        Generic preprocessor to repair OCR and PDF layout artifacts in URLs:
        - Accidental whitespace in protocol (e.g. 'http : //', 'https ://', 'https : / /')
        - Accidental whitespace in domain (e.g. 'forms . gle /', 'docs . google . com / forms /', 'www . ')
        - Single OCR space after slash or inside path/form IDs (e.g. 'forms.gle/ yP4tpWtmk9VdFFBU8' -> 'forms.gle/yP4tpWtmk9VdFFBU8')
        - PDF layout line-wrapping of URLs across newlines
        """
        if not text:
            return ""

        t = text
        # 1. Normalize protocol spacing: "https : / /" or "http ://" -> "https://" / "http://"
        t = re.sub(r'\b(https?)\s*:\s*/\s*/\s*', r'\1://', t, flags=re.IGNORECASE)
        t = re.sub(r'\b(https?)\s*:\s*/\s*(?!/)', r'\1://', t, flags=re.IGNORECASE)

        # 2. Normalize common domain spacing around dots:
        t = re.sub(r'(https?://[a-zA-Z0-9_-]+)\s*\.\s*([a-zA-Z0-9_-]+)\s*\.\s*([a-zA-Z]{2,})\s*/\s*', r'\1.\2.\3/', t, flags=re.IGNORECASE)
        t = re.sub(r'(https?://[a-zA-Z0-9_-]+)\s*\.\s*([a-zA-Z]{2,})\s*/\s*', r'\1.\2/', t, flags=re.IGNORECASE)
        t = re.sub(r'\b(forms|docs|bit)\s*\.\s*(gle|google|ly)\s*/\s*', r'\1.\2/', t, flags=re.IGNORECASE)
        t = re.sub(r'\b(docs)\s*\.\s*(google)\s*\.\s*(com)\s*/\s*', r'\1.\2.\3/', t, flags=re.IGNORECASE)
        t = re.sub(r'\b(forms)\s*\.\s*(office)\s*\.\s*(com)\s*/\s*', r'\1.\2.\3/', t, flags=re.IGNORECASE)
        t = re.sub(r'\b([a-zA-Z0-9_-]+)\s*\.\s*(com|org|in|edu|io|co|net|ai)\s*/\s*', r'\1.\2/', t, flags=re.IGNORECASE)
        t = re.sub(r'\b(www)\s*\.\s*', r'www.', t, flags=re.IGNORECASE)

        # 3. Reconstruct URLs split across line breaks (PDF hard wrap)
        # Case A: URL ending with hyphen at line break
        t = re.sub(r'(\bhttps?://[^\s<>"\'`]+)-\s*[\r\n]+\s*([a-zA-Z0-9_/?&=#%~+.-]+)', r'\1\2', t)

        # Case B: URL ending with delimiter or slash before line break
        t = re.sub(r'(\bhttps?://[^\s<>"\'`]+[/=?&_])\s*[\r\n]+\s*([a-zA-Z0-9_/?&=#%~+.-]+)', r'\1\2', t)

        # Case C: Google forms or Microsoft forms or short links split across newline
        t = re.sub(r'(\b(?:https?://)?forms\.gle/)\s*[\r\n]+\s*([a-zA-Z0-9_-]+)', r'\1\2', t)
        t = re.sub(r'(\bhttps?://forms\.office\.com/r/)\s*[\r\n]+\s*([a-zA-Z0-9_-]+)', r'\1\2', t)
        t = re.sub(r'(\bhttps?://docs\.google\.com/forms/[^\s]+/)\s*[\r\n]+\s*([a-zA-Z0-9_-]+)', r'\1\2', t)

        # Case D: Generic URL where line break splits a query string or path segment starting with delimiter
        t = re.sub(r'(\bhttps?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?::\d+)?/[^\s<>"\'`]*)\s*[\r\n]+\s*([/?&=#%][a-zA-Z0-9_/?&=#%~+.-]*)', r'\1\2', t)

        # 4. OCR spacing repairs inside paths:
        t = re.sub(r'(\b(?:https?://)?forms\.gle/)\s+([a-zA-Z0-9_-]+)', r'\1\2', t)
        t = re.sub(r'(\bhttps?://docs\.google\.com/forms/[^\s]+/)\s+([a-zA-Z0-9_-]+)', r'\1\2', t)
        t = re.sub(r'(\bhttps?://forms\.office\.com/r/)\s+([a-zA-Z0-9_-]+)', r'\1\2', t)

        # Collapse spaces around slashes and hyphens in URLs without gobbling adjacent words
        for _ in range(4):
            t = re.sub(r'(\bhttps?://[a-zA-Z0-9_.\-]+(?::\d+)?(?:/[a-zA-Z0-9_.~%+\-]*)*)\s+/\s*([a-zA-Z0-9_.~%+\-]+)', r'\1/\2', t)
            t = re.sub(r'(\bhttps?://[^\s<>"\'`]+/[a-zA-Z0-9_.~%+/]*[a-zA-Z0-9_.~%+])\s+-\s+([a-zA-Z0-9_.~%+\-]+)', r'\1-\2', t)

        return t

    def _clean_and_validate_candidate_url(self, raw_url: str) -> Optional[str]:
        """
        Clean surrounding brackets and trailing sentence punctuation from candidate URL
        while strictly preserving valid query parameters, fragments, encoded chars, etc.
        """
        if not raw_url:
            return None

        u = raw_url.strip()

        # Strip surrounding enclosure quotes or angle brackets
        if (u.startswith('"') and u.endswith('"')) or (u.startswith("'") and u.endswith("'")):
            u = u[1:-1].strip()
        if u.startswith('<') and u.endswith('>'):
            u = u[1:-1].strip()
        if u.startswith('[') and u.endswith(']'):
            u = u[1:-1].strip()
        if u.startswith('(') and u.endswith(')'):
            u = u[1:-1].strip()

        # Handle scheme prefixes
        if u.lower().startswith('www.'):
            u = 'https://' + u
        elif u.lower().startswith('forms.gle/'):
            u = 'https://' + u
        elif u.lower().startswith('bit.ly/'):
            u = 'https://' + u
        elif u.lower().startswith('tinyurl.com/'):
            u = 'https://' + u
        elif not re.match(r'^https?://', u, re.IGNORECASE):
            return None

        # Clean trailing sentence punctuation (dots, commas, semicolons, colons)
        while len(u) > 10:
            last_char = u[-1]
            if last_char in ('.', ',', ';', ':', '!', '"', "'", '`', '>', '}'):
                u = u[:-1]
            elif last_char == ')':
                if u.count('(') < u.count(')'):
                    u = u[:-1]
                else:
                    break
            elif last_char == ']':
                if u.count('[') < u.count(']'):
                    u = u[:-1]
                else:
                    break
            elif last_char == '?':
                if len(u) > 1 and u[-2] in ('/', '.'):
                    u = u[:-1]
                else:
                    break
            else:
                break

        # Validate URL structure
        try:
            parsed = urlparse(u)
            if parsed.scheme.lower() not in ('http', 'https'):
                return None
            netloc = parsed.netloc.lower().split(':')[0]
            if not netloc or '.' not in netloc:
                return None
            if netloc in self.IGNORED_URL_HOSTS or any(netloc.endswith('.' + ign) for ign in self.IGNORED_URL_HOSTS):
                return None
            path_lower = parsed.path.lower()
            if any(path_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.css', '.js', '.woff', '.ico', '.mp4']):
                return None
            return u
        except Exception:
            return None

    def _score_url_context(self, url: str, text: str) -> Tuple[int, str]:
        """
        Score a URL candidate based on its structure and surrounding text context.
        Returns (score, context_snippet).
        Higher score indicates strong evidence of being the external application/registration link.
        """
        u_lower = url.lower()
        score = 0

        # Form provider intrinsic weight
        if any(f in u_lower for f in [
            "forms.gle", "docs.google.com/forms", "forms.office.com", "typeform.com",
            "jotform.com", "surveymonkey.com", "airtable.com", "greenhouse.io",
            "lever.co", "smartrecruiters.com", "myworkdayjobs.com", "pod.ai", "supersets.com"
        ]):
            score += 35
        # Portal / career path intrinsic weight
        if any(k in u_lower for k in ["/apply", "/application", "/register", "/registration", "/careers", "/career", "/jobs", "/job/", "/openings", "/recruitment"]):
            score += 25
        if any(s in u_lower for s in ["bit.ly/", "tinyurl.com/"]):
            score += 15

        # Check if URL is just a bare company root homepage (e.g., https://company.com or https://www.company.com/)
        try:
            parsed = urlparse(url)
            path = parsed.path.strip('/')
            if not path and not parsed.query:
                score -= 15
        except Exception:
            pass

        # Context window signals
        context_snippet = ""
        u_idx = text.find(url)
        if u_idx == -1:
            try:
                parsed = urlparse(url)
                if parsed.path and len(parsed.path) > 3:
                    u_idx = text.find(parsed.path)
            except Exception:
                pass

        if u_idx != -1:
            start = max(0, u_idx - 250)
            end = min(len(text), u_idx + len(url) + 150)
            window = text[start:end]
            context_snippet = window.replace('\n', ' ').strip()
            w_lower = window.lower()

            # Strong explicit application/registration phrases
            if any(p in w_lower for p in [
                "registration link", "application link", "apply link", "registration url",
                "application url", "link to apply", "link to register", "link for registration", "form link",
                "apply here", "register here", "interested candidates register", "google form link",
                "google form", "registration form", "application form", "official application link", "online application"
            ]):
                score += 40
            elif any(p in w_lower for p in [
                "register", "registration", "apply", "application", "how to apply",
                "interested candidates", "apply online", "submit application", "fill the form"
            ]):
                score += 25
            elif any(p in w_lower for p in ["career", "portal", "recruitment", "submission", "shortlist"]):
                score += 10

            # Negative signals (informational / corporate / contact)
            if any(p in w_lower for p in ["company website", "visit our website", "about us", "official website", "web:"]):
                score -= 20
            if any(p in w_lower for p in ["privacy policy", "terms of service", "unsubscribe", "contact us at", "terms and conditions"]):
                score -= 30

        return score, context_snippet

    def _extract_all_application_urls(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract, reconstruct, score, and rank all valid candidate URLs from text.
        Eliminates truncated prefixes and returns list sorted by score descending.
        """
        prep_text = self._preprocess_text_for_urls(text)
        
        # Regex matching generic URLs across text
        raw_matches = re.findall(
            r'(?<![a-zA-Z0-9])(?:https?://|www\.|forms\.gle/|docs\.google\.com/forms/|forms\.office\.com/|bit\.ly/|tinyurl\.com/)[^\s<>"\'`]+',
            prep_text,
            re.IGNORECASE
        )

        candidates_map = {}
        for rm in raw_matches:
            cleaned = self._clean_and_validate_candidate_url(rm)
            if cleaned and cleaned not in candidates_map:
                score, snippet = self._score_url_context(cleaned, prep_text)
                candidates_map[cleaned] = {
                    "url": cleaned,
                    "score": score,
                    "context": snippet
                }

        candidates = list(candidates_map.values())

        # Discard truncated prefixes:
        # If url A is a strict prefix of url B (e.g. 'https://forms.gle/yP4tp' vs 'https://forms.gle/yP4tpWtmk9VdFFBU8'),
        # discard the truncated prefix.
        filtered = []
        for c in candidates:
            url_c = c["url"]
            is_prefix = any(
                other["url"] != url_c and other["url"].startswith(url_c)
                for other in candidates
            )
            if not is_prefix:
                filtered.append(c)

        # Sort by score descending, then length descending
        filtered.sort(key=lambda x: (x["score"], len(x["url"])), reverse=True)
        return filtered

    def _extract_application_url_and_instructions(
        self,
        text: str,
        evidence: Dict[str, str]
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract external company application URL (http/https) and application instructions.
        Looks for explicit links in context of application, registration, careers, portal, etc.
        Validates URL structure and rejects invalid formats and metadata/schema URLs.
        """
        app_url: Optional[str] = None
        instructions: Optional[str] = None

        candidates = self._extract_all_application_urls(text)
        valid_app_candidates = [c for c in candidates if c["score"] > 0]
        evidence["application_url_candidates"] = [c["url"] for c in valid_app_candidates]

        if valid_app_candidates:
            app_url = valid_app_candidates[0]["url"]
            evidence["application_url"] = app_url

        # Application instructions extraction
        instruction_patterns = [
            r'(?:how\s*to\s*apply|application\s*(?:process|procedure|instructions?|steps?|method)|mode\s*of\s*application)[\s:\-–—|]+([^\n\r]+(?:\n[^\n\r]+){0,2})',
            r'(?:apply\s*(?:online|at|via|through)[\s:\-–—]+[^\n\r]+)',
            r'(?:(?:interested\s*)?candidates?\s*(?:must|should|may|can|are\s*required\s*to)\s*apply[^\n\r]+)'
        ]
        for ip in instruction_patterns:
            im = re.search(ip, text, re.IGNORECASE)
            if im:
                snippet = im.group(0).strip()
                if len(snippet) > 10:
                    instructions = snippet[:300].strip()
                    evidence["application_instructions"] = instructions
                    break

        return app_url, instructions

    def _extract_application_url(self, text: str) -> Optional[str]:
        """Extract application URL from text using the URL extraction and validation logic."""
        app_url, _ = self._extract_application_url_and_instructions(text, {})
        return app_url

    def _extract_description(self, text: str, evidence: Dict[str, str]) -> str:
        """Extract a readable summary excerpt of the job description."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if paragraphs:
            summary = paragraphs[0] if len(paragraphs[0]) >= 30 else ("\n\n".join(paragraphs[:2]))
            evidence["description"] = summary[:150] + "..." if len(summary) > 150 else summary
            return summary[:800].strip()
        return text[:500].strip()

    def parse_multiple_files(self, files_data: List[Dict[str, Any]]) -> JdParseResult:
        """
        Extract and parse requirements across multiple uploaded Job Description documents.
        Intelligently merges fields, identifies conflicts between documents, tags source evidence,
        and distinguishes between success, partial, and failed extractions.
        
        Args:
            files_data: List of dicts with keys:
                - filename: str
                - content: bytes
                - file_id: Optional[UUID]
                
        Returns:
            JdParseResult with merged requirements, review flags for conflicts,
            per-file extraction details, and overall extraction status.
        """
        if not files_data:
            return self._empty_result()

        extracted_files_summary: List[Dict[str, Any]] = []
        per_file_results: List[Dict[str, Any]] = []

        for item in files_data:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                fn = item[0]
                content = item[1]
                fid = item[2] if len(item) > 2 else None
            elif isinstance(item, dict):
                fn = item.get("filename", "unknown")
                content = item.get("content", b"")
                fid = item.get("file_id")
            else:
                continue

            if isinstance(content, str):
                content = content.encode("utf-8")

            try:
                text = self.extract_text_from_file(content=content, filename=fn)
                parsed = self.parse_jd_text(text)
                per_file_results.append({
                    "filename": fn,
                    "file_id": fid,
                    "parsed": parsed,
                    "text": text
                })
                extracted_files_summary.append({
                    "filename": fn,
                    "file_id": str(fid) if fid else None,
                    "size": len(content),
                    "text_length": len(text),
                    "status": "success" if len(text) >= 20 else "partial"
                })
            except Exception as err:
                logger.warning(f"Text extraction failed for {fn}: {err}")
                extracted_files_summary.append({
                    "filename": fn,
                    "file_id": str(fid) if fid else None,
                    "size": len(content),
                    "text_length": 0,
                    "status": "failed",
                    "error": str(err)
                })

        # If all failed
        if not per_file_results:
            empty = self._empty_result()
            empty["extracted_files"] = extracted_files_summary
            empty["extraction_status"] = "failed"
            empty["review_flags"] = ["Failed to extract readable text from uploaded documents."]
            empty["file_ids"] = [item["file_id"] for item in files_data if isinstance(item, dict) and item.get("file_id")]
            empty["file_names"] = [item["filename"] if isinstance(item, dict) else item[0] for item in files_data if (isinstance(item, dict) and item.get("filename")) or isinstance(item, (list, tuple))]
            if empty["file_ids"]:
                empty["file_id"] = empty["file_ids"][0]
                empty["file_name"] = empty["file_names"][0]
            return empty

        # If single file succeeded
        if len(per_file_results) == 1:
            res = per_file_results[0]["parsed"]
            fn = per_file_results[0]["filename"]
            fid = per_file_results[0]["file_id"]
            res["file_id"] = fid
            res["file_name"] = fn
            res["file_ids"] = [fid] if fid else []
            res["file_names"] = [fn]
            res["extracted_files"] = extracted_files_summary
            
            # Determine extraction status
            has_failed_other = any(f["status"] == "failed" for f in extracted_files_summary)
            if has_failed_other or len(res.get("review_flags", [])) > 0 or not res.get("title") or not res.get("required_skills"):
                res["extraction_status"] = "partial"
            else:
                res["extraction_status"] = "success"
            return res

        # Multi-file merge logic
        merged_review_flags: List[str] = []
        merged_evidence: Dict[str, Any] = {}

        # 1. Job Title selection and conflict detection
        titles = [(r["filename"], r["parsed"].get("title")) for r in per_file_results if r["parsed"].get("title")]
        chosen_title = None
        if titles:
            unique_titles = {t[1].strip().lower(): t for t in titles}
            if len(unique_titles) > 1:
                t1 = titles[0]
                t2 = titles[1]
                chosen_title = t1[1]
                merged_review_flags.append(
                    f"Document conflict on Job Title: '{t1[1]}' ({t1[0]}) vs '{t2[1]}' ({t2[0]}). Defaulted to '{chosen_title}'. Please verify."
                )
            else:
                chosen_title = titles[0][1]
            merged_evidence["title"] = f"[{titles[0][0]}] {chosen_title}"

        # 2. Company Name
        companies = [(r["filename"], r["parsed"].get("company_name")) for r in per_file_results if r["parsed"].get("company_name")]
        chosen_company = None
        if companies:
            unique_companies = {c[1].strip().lower(): c for c in companies}
            if len(unique_companies) > 1:
                c1 = companies[0]
                c2 = companies[1]
                chosen_company = c1[1]
                merged_review_flags.append(
                    f"Document conflict on Company Name: '{c1[1]}' ({c1[0]}) vs '{c2[1]}' ({c2[0]}). Defaulted to '{chosen_company}'."
                )
            else:
                chosen_company = companies[0][1]
            merged_evidence["company_name"] = f"[{companies[0][0]}] {chosen_company}"

        # 3. CGPA Criteria
        cgpa_vals = [(r["filename"], r["parsed"].get("cgpa_criteria")) for r in per_file_results if r["parsed"].get("cgpa_criteria") is not None]
        chosen_cgpa = None
        if cgpa_vals:
            unique_cgpas = {c[1]: c for c in cgpa_vals}
            if len(unique_cgpas) > 1:
                cg1 = cgpa_vals[0]
                cg2 = cgpa_vals[1]
                chosen_cgpa = max(c[1] for c in cgpa_vals)
                merged_review_flags.append(
                    f"Conflicting Minimum CGPA criteria: {cg1[1]} ({cg1[0]}) vs {cg2[1]} ({cg2[0]}). Selected higher value ({chosen_cgpa}). Please verify."
                )
            else:
                chosen_cgpa = cgpa_vals[0][1]
            merged_evidence["cgpa_criteria"] = f"[{cgpa_vals[0][0]}] Minimum CGPA: {chosen_cgpa}"

        # 4. Location and Workplace Mode
        loc_vals = [(r["filename"], r["parsed"].get("location")) for r in per_file_results if r["parsed"].get("location")]
        chosen_location = None
        if loc_vals:
            unique_locs = {l[1].strip().lower(): l for l in loc_vals}
            if len(unique_locs) > 1:
                l1 = loc_vals[0]
                l2 = loc_vals[1]
                chosen_location = l1[1]
                merged_review_flags.append(
                    f"Conflicting Job Location: '{l1[1]}' ({l1[0]}) vs '{l2[1]}' ({l2[0]}). Please confirm."
                )
            else:
                chosen_location = loc_vals[0][1]
            merged_evidence["location"] = f"[{loc_vals[0][0]}] {chosen_location}"

        work_modes = [r["parsed"].get("work_mode") for r in per_file_results if r["parsed"].get("work_mode")]
        chosen_work_mode = work_modes[0] if work_modes else None

        # 5. Salary Range & Compensation Details across multiple files
        stipend_entries = []
        ctc_entries = []
        for r in per_file_results:
            fn = r["filename"]
            cd = r["parsed"].get("compensation_details") or {}
            stip = cd.get("stipend")
            ctc = cd.get("full_time_ctc")
            if stip:
                stipend_entries.append((fn, stip))
            if ctc:
                ctc_entries.append((fn, ctc))

        chosen_salary = None
        comp_details = {
            "currency": "INR",
            "stipend": None,
            "full_time_ctc": None,
            "staged_compensation": []
        }

        # Check for conflicts among distinct CTC values
        if ctc_entries:
            unique_ctcs = {c[1].strip().lower(): c for c in ctc_entries}
            if len(unique_ctcs) > 1:
                c1, c2 = ctc_entries[0], ctc_entries[1]
                merged_review_flags.append(
                    f"Conflicting full-time CTC/salary: '{c1[1]}' ({c1[0]}) vs '{c2[1]}' ({c2[0]}). Defaulted to '{c1[1]}'. Please verify."
                )
            comp_details["full_time_ctc"] = ctc_entries[0][1]
            comp_details["annual_ctc"] = ctc_entries[0][1]

        # Check for conflicts among distinct Stipend values
        if stipend_entries:
            unique_stipends = {s[1].strip().lower(): s for s in stipend_entries}
            if len(unique_stipends) > 1:
                s1, s2 = stipend_entries[0], stipend_entries[1]
                merged_review_flags.append(
                    f"Conflicting stipend details: '{s1[1]}' ({s1[0]}) vs '{s2[1]}' ({s2[0]}). Defaulted to '{s1[1]}'. Please verify."
                )
            comp_details["stipend"] = stipend_entries[0][1]

        if comp_details["stipend"] and comp_details["full_time_ctc"]:
            comp_details["staged_compensation"] = [
                {"stage": "Internship Period", "amount": comp_details["stipend"]},
                {"stage": "Full Time / Post-Conversion", "amount": comp_details["full_time_ctc"]}
            ]
            chosen_salary = comp_details["full_time_ctc"]
            merged_evidence["salary_range"] = f"Full Time CTC: {chosen_salary}"
            merged_evidence["stipend"] = comp_details["stipend"]
        elif comp_details["full_time_ctc"]:
            chosen_salary = comp_details["full_time_ctc"]
            merged_evidence["salary_range"] = f"Full Time CTC: {chosen_salary}"
        elif comp_details["stipend"]:
            chosen_salary = f"Stipend: {comp_details['stipend']}"
            merged_evidence["salary_range"] = chosen_salary
        else:
            salary_vals = [(r["filename"], r["parsed"].get("salary_range")) for r in per_file_results if r["parsed"].get("salary_range")]
            if salary_vals:
                chosen_salary = salary_vals[0][1]
                merged_evidence["salary_range"] = f"[{salary_vals[0][0]}] {chosen_salary}"

        # 6. Deadlines & Important Dates
        deadlines = [(r["filename"], r["parsed"].get("application_deadline")) for r in per_file_results if r["parsed"].get("application_deadline")]
        chosen_deadline = None
        if deadlines:
            unique_deadlines = {d[1].strip(): d for d in deadlines}
            if len(unique_deadlines) > 1:
                d1, d2 = deadlines[0], deadlines[1]
                chosen_deadline = d1[1]
                merged_review_flags.append(
                    f"Conflicting application_deadline: '{d1[1]}' ({d1[0]}) vs '{d2[1]}' ({d2[0]}). Selected '{chosen_deadline}'. Please verify."
                )
            else:
                chosen_deadline = deadlines[0][1]
            merged_evidence["application_deadline"] = f"[{deadlines[0][0]}] {chosen_deadline}"

        drive_dates = [(r["filename"], r["parsed"].get("drive_date")) for r in per_file_results if r["parsed"].get("drive_date")]
        chosen_drive_date = None
        if drive_dates:
            unique_drive_dates = {d[1].strip(): d for d in drive_dates}
            if len(unique_drive_dates) > 1:
                dd1, dd2 = drive_dates[0], drive_dates[1]
                chosen_drive_date = dd1[1]
                merged_review_flags.append(
                    f"Conflicting drive dates: '{dd1[1]}' ({dd1[0]}) vs '{dd2[1]}' ({dd2[0]}). Selected '{chosen_drive_date}'. Please verify."
                )
            else:
                chosen_drive_date = drive_dates[0][1]
            merged_evidence["drive_date"] = f"[{drive_dates[0][0]}] {chosen_drive_date}"

        joining_dates = [r["parsed"].get("joining_date") for r in per_file_results if r["parsed"].get("joining_date")]
        chosen_joining_date = joining_dates[0] if joining_dates else None

        # 7. Skills Union (Required and Preferred)
        all_req_skills: List[str] = []
        all_pref_skills: List[str] = []
        for r in per_file_results:
            fn = r["filename"]
            reqs = r["parsed"].get("required_skills") or []
            prefs = r["parsed"].get("preferred_skills") or []
            all_req_skills.extend(reqs)
            all_pref_skills.extend(prefs)
            if reqs:
                merged_evidence[f"required_skills_{fn}"] = f"[{fn}] {', '.join(reqs)}"

        merged_req_skills = list(dict.fromkeys(all_req_skills))
        merged_pref_skills = [s for s in list(dict.fromkeys(all_pref_skills)) if s not in merged_req_skills]

        # 8. Branch Eligibility Union
        all_branches: List[str] = []
        for r in per_file_results:
            b_list = r["parsed"].get("branch_eligibility") or []
            all_branches.extend(b_list)
        merged_branches = list(dict.fromkeys(all_branches))

        # 9. Degrees and Graduation Batches
        all_degrees: List[str] = []
        all_batches: List[Any] = []
        for r in per_file_results:
            all_degrees.extend(r["parsed"].get("degree_eligibility") or [])
            all_batches.extend(r["parsed"].get("graduation_years") or [])
        merged_degrees = list(dict.fromkeys(all_degrees))
        merged_batches = list(dict.fromkeys(all_batches))

        # 10. Application URL and Multi-Document Candidate Aggregation
        all_url_candidates: List[Dict[str, Any]] = []
        seen_candidate_urls = set()

        for r in per_file_results:
            fn = r["filename"]
            file_candidates = r["parsed"].get("application_url_candidates") or []
            file_app_url = r["parsed"].get("application_url")
            if file_app_url and not any(fc.get("url") == file_app_url for fc in file_candidates if isinstance(fc, dict)):
                file_candidates.append({
                    "url": file_app_url,
                    "source_file": fn,
                    "score": 30,
                    "context": r["parsed"].get("field_evidence", {}).get("application_url", "")
                })

            for fc in file_candidates:
                u = fc.get("url", "").strip() if isinstance(fc, dict) else str(fc).strip()
                if u and u not in seen_candidate_urls:
                    seen_candidate_urls.add(u)
                    all_url_candidates.append({
                        "url": u,
                        "source_file": fc.get("source_file") or fn if isinstance(fc, dict) else fn,
                        "score": fc.get("score", 30) if isinstance(fc, dict) else 30,
                        "context": fc.get("context", "") if isinstance(fc, dict) else ""
                    })

        # Discard truncated prefixes across multiple files:
        # If url A is a strict prefix of url B, discard the incomplete prefix
        filtered_url_candidates = []
        for c in all_url_candidates:
            u = c["url"]
            is_prefix = any(
                other["url"] != u and other["url"].startswith(u)
                for other in all_url_candidates
            )
            if not is_prefix:
                filtered_url_candidates.append(c)

        # Sort candidates by score descending, then length descending
        filtered_url_candidates.sort(key=lambda x: (x["score"], len(x["url"])), reverse=True)

        chosen_url = None
        if filtered_url_candidates:
            top_cand = filtered_url_candidates[0]
            if top_cand["score"] > 0:
                chosen_url = top_cand["url"]
                merged_evidence["application_url"] = f"[{top_cand['source_file']}] {chosen_url}"

            valid_candidates = [c for c in filtered_url_candidates if c["score"] > 0]
            if len(valid_candidates) > 1:
                top1 = valid_candidates[0]
                top2 = valid_candidates[1]
                if abs(top1["score"] - top2["score"]) < 15 and top1["url"] != top2["url"]:
                    merged_review_flags.append(
                        f"Multiple plausible application URLs detected: '{top1['url']}' ({top1['source_file']}) vs '{top2['url']}' ({top2['source_file']}). Pre-selected '{chosen_url}'. Please confirm the correct link."
                    )
        else:
            merged_review_flags.append(
                "No external application URL detected in the uploaded documents. If students must apply externally, please enter the link manually."
            )

        instructions_list = [r["parsed"].get("application_instructions") for r in per_file_results if r["parsed"].get("application_instructions")]
        chosen_instructions = instructions_list[0] if instructions_list else None

        # 11. Description combining without duplicate paragraphs
        descriptions = []
        for r in per_file_results:
            desc = (r["parsed"].get("description") or "").strip()
            if desc and desc not in descriptions:
                descriptions.append(desc)
        chosen_description = "\n\n".join(descriptions) if descriptions else ""

        # 12. Aggregate Review Flags
        for r in per_file_results:
            fn = r["filename"]
            for flag in r["parsed"].get("review_flags", []):
                merged_review_flags.append(f"[{fn}] {flag}")

        # 13. Academic Percentages across multiple documents
        merged_percentages: Dict[str, Optional[float]] = {
            "tenth": None,
            "10th": None,
            "twelfth": None,
            "12th": None,
            "diploma": None,
            "degree": None,
            "postgraduate": None
        }
        for r in per_file_results:
            ap = r["parsed"].get("academic_percentages")
            if isinstance(ap, dict):
                for k, v in ap.items():
                    if v is not None and merged_percentages.get(k) is None:
                        merged_percentages[k] = v
        has_any_pct = any(v is not None for v in merged_percentages.values())
        chosen_percentages = merged_percentages if has_any_pct else None

        chosen_exp = next((r["parsed"].get("experience_level") for r in per_file_results if r["parsed"].get("experience_level")), None)
        chosen_job_type = next((r["parsed"].get("job_type") for r in per_file_results if r["parsed"].get("job_type")), None)
        chosen_backlogs = next((r["parsed"].get("backlog_criteria") for r in per_file_results if r["parsed"].get("backlog_criteria")), None)

        # Determine extraction status
        any_failed = any(f["status"] == "failed" for f in extracted_files_summary)
        if any_failed or merged_review_flags or not chosen_title or not merged_req_skills:
            extraction_status = "partial"
        else:
            extraction_status = "success"

        all_file_ids = [item["file_id"] for item in files_data if isinstance(item, dict) and item.get("file_id")]
        all_file_names = [item["filename"] if isinstance(item, dict) else item[0] for item in files_data if (isinstance(item, dict) and item.get("filename")) or isinstance(item, (list, tuple))]

        return JdParseResult({
            "title": chosen_title,
            "description": chosen_description,
            "required_skills": merged_req_skills,
            "preferred_skills": merged_pref_skills,
            "experience_level": chosen_exp,
            "cgpa_criteria": chosen_cgpa,
            "min_cgpa": chosen_cgpa,
            "branch_eligibility": merged_branches,
            "location": chosen_location,
            "salary_range": chosen_salary,
            "raw_text_length": sum(r.get("text_length", 0) for r in extracted_files_summary),

            "company_name": chosen_company,
            "job_type": chosen_job_type,
            "degree_eligibility": merged_degrees,
            "graduation_years": merged_batches,
            "academic_percentages": chosen_percentages,
            "backlog_criteria": chosen_backlogs,
            "certifications": list(dict.fromkeys(sum([r["parsed"].get("certifications") or [] for r in per_file_results], []))),
            "compensation_details": comp_details,
            "application_deadline": chosen_deadline,
            "drive_date": chosen_drive_date,
            "joining_date": chosen_joining_date,
            "work_mode": chosen_work_mode,
            "bond_details": next((r["parsed"].get("bond_details") for r in per_file_results if r["parsed"].get("bond_details")), None),
            "selection_rounds": list(dict.fromkeys(sum([r["parsed"].get("selection_rounds") or [] for r in per_file_results], []))),
            "application_instructions": chosen_instructions,
            "application_url": chosen_url,
            "application_url_candidates": filtered_url_candidates,

            # File persistence and multi-document tracking
            "file_id": all_file_ids[0] if all_file_ids else None,
            "file_name": all_file_names[0] if all_file_names else None,
            "file_ids": all_file_ids,
            "file_names": all_file_names,
            "extracted_files": extracted_files_summary,
            "extraction_status": extraction_status,

            "review_flags": merged_review_flags,
            "field_evidence": merged_evidence
        })

    def _empty_result(self) -> Dict[str, Any]:
        """Return standardized empty extraction result."""
        return JdParseResult({
            "title": None,
            "description": "",
            "required_skills": [],
            "preferred_skills": [],
            "experience_level": None,
            "cgpa_criteria": None,
            "branch_eligibility": [],
            "location": None,
            "salary_range": None,
            "raw_text_length": 0,
            "company_name": None,
            "job_type": None,
            "degree_eligibility": [],
            "graduation_years": [],
            "academic_percentages": {
                "tenth": None,
                "twelfth": None,
                "diploma": None,
                "degree": None,
                "postgraduate": None
            },
            "backlog_criteria": None,
            "certifications": [],
            "compensation_details": {
                "currency": "INR",
                "stipend": None,
                "full_time_ctc": None,
                "staged_compensation": []
            },
            "application_deadline": None,
            "drive_date": None,
            "joining_date": None,
            "work_mode": None,
            "bond_details": None,
            "selection_rounds": [],
            "application_instructions": None,
            "application_url": None,
            "application_url_candidates": [],
            "file_id": None,
            "file_name": None,
            "file_ids": [],
            "file_names": [],
            "extracted_files": [],
            "extraction_status": "failed",
            "review_flags": ["No text provided for analysis."],
            "field_evidence": {}
        })

    # Alias for convenience
    parse = parse_jd_text


# Global singleton instance
jd_parser_service = JdParserService()

