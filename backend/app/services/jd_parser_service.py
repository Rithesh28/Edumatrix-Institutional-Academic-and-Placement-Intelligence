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

from .skill_normalizer import skill_normalizer
from .file_storage.text_extractor import text_extractor
from .ocr_service import OCRService

logger = logging.getLogger(__name__)


class JdParseResult(dict):
    """
    Dictionary subclass supporting both dict key access (result['title'])
    and attribute access (result.title) for seamless backward compatibility
    and object-like ergonomics.
    """
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'JdParseResult' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


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
        "sap", "sap abap", "abap", "salesforce", "embedded c", "iot", "vlsi", "matlab"
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
        "computer science": "CSE",
        "computer science engineering": "CSE",
        "computer science & engineering": "CSE",
        "it": "IT",
        "information technology": "IT",
        "information science": "IT",
        "ise": "IT",
        "aiml": "AIML",
        "ai & ml": "AIML",
        "ai/ml": "AIML",
        "artificial intelligence": "AIML",
        "aids": "AIDS",
        "ai & ds": "AIDS",
        "ai/ds": "AIDS",
        "data science": "AIDS",
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

        # 1. Image OCR handling
        if ext in [".png", ".jpg", ".jpeg"]:
            try:
                if content:
                    ocr_text = self.ocr_service.extract_text_from_image_bytes(content)
                    if ocr_text and "Error:" not in ocr_text and "OCR Error:" not in ocr_text:
                        extracted_text = ocr_text.strip()
                elif file_path and os.path.exists(file_path):
                    ocr_text = self.ocr_service.extract_text_from_image(file_path)
                    if ocr_text and "Error:" not in ocr_text and "OCR Error:" not in ocr_text:
                        extracted_text = ocr_text.strip()
            except Exception as img_err:
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
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                        tmp.write(content)
                        tmp_path = tmp.name
                    try:
                        ocr_text = self.ocr_service.extract_text_from_scanned_pdf(tmp_path)
                        if ocr_text and len(ocr_text.strip()) > 30 and "Error:" not in ocr_text:
                            extracted_text = ocr_text.strip()
                    finally:
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)
                elif file_path and os.path.exists(file_path):
                    ocr_text = self.ocr_service.extract_text_from_scanned_pdf(file_path)
                    if ocr_text and len(ocr_text.strip()) > 30 and "Error:" not in ocr_text:
                        extracted_text = ocr_text.strip()
            except Exception as ocr_err:
                logger.warning(f"OCR fallback attempt encountered an error: {ocr_err}")

        # 7. Fallback for raw text bytes (plain text files only)
        if not extracted_text and ext == ".txt" and content:
            try:
                extracted_text = content.decode("utf-8", errors="ignore").strip()
            except Exception:
                pass

        if not extracted_text or len(extracted_text.strip()) < 10:
            raise ValueError(
                "Failed to extract readable text from the document. "
                "The file may be a scanned image without readable text or contains unreadable content. "
                "Please upload a searchable text document, recruitment document, or paste the text directly."
            )

        return extracted_text


    # =========================================================================
    # STAGE B: TEXT NORMALIZATION
    # =========================================================================

    def normalize_text(self, text: str) -> str:
        """
        Normalize whitespace and bullet characters while preserving structural
        headings, bullet points, and key-value lines.
        """
        if not text:
            return ""

        # Normalize unicode line breaks
        norm = text.replace("\r\n", "\n").replace("\r", "\n")

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
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                # Clean prefix/suffix noise
                candidate = re.sub(r'^(?:is\s+|a\s+|an\s+)', '', candidate, flags=re.IGNORECASE).strip()
                candidate = re.sub(r'\s+(?:with|to|in|having|who).*$', '', candidate, flags=re.IGNORECASE).strip()
                if 3 <= len(candidate) <= 60 and not re.search(r'company|overview|eligibility|ctc|notice', candidate, re.IGNORECASE):
                    evidence["title"] = match.group(0).strip()
                    return candidate

        # 2. Heuristic search in the first 6 non-empty lines for typical engineering titles
        role_keywords = (
            r'(?:software\s+engineer|developer|consultant|full\s*stack|frontend|backend|'
            r'data\s+analyst|data\s+scientist|qa\s+engineer|devops|system\s+engineer|'
            r'graduate\s+engineer\s+trainee|associate\s+software\s+engineer|trainee|'
            r'intern|cloud\s+engineer|cyber\s+security\s+analyst)'
        )
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for line in lines[:6]:
            if re.search(role_keywords, line, re.IGNORECASE) and len(line) <= 60:
                if not re.search(r'company|welcome|campus|placement|hiring', line, re.IGNORECASE):
                    evidence["title"] = line
                    return line

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
            r'(?:cgpa|gpa|cutoff)[\s:=><]+([0-9]+(?:\.[0-9]+)?)\s*(?:/\s*10)?',
            r'([0-9]+(?:\.[0-9]+)?)\s*(?:and\s*above|or\s*above|\+)?\s*(?:cgpa|gpa)',
            r'minimum\s+([0-9]+(?:\.[0-9]+)?)\s*(?:in\s+)?cgpa'
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
        degrees = list(dict.fromkeys(degrees))
        if degrees:
            evidence["degree_eligibility"] = ", ".join(degrees)

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

        # 1. Detect Staged Compensation (Stipend + Post-conversion CTC)
        stipend_match = re.search(
            r'(?:stipend(?:\s*during\s*(?:internship|training))?|internship\s*stipend)(?:[\s:\-–—|]+|\s+of\s+)([₹Rs\.\s0-9,]+(?:\s*(?:\/|per)\s*(?:month|mo|pm))?)',
            text,
            re.IGNORECASE
        )
        ctc_match = re.search(
            r'(?:(?:full[\s\-]*time\s*)?(?:ctc|package|salary(?:\s*range)?)|post\s*(?:completion\s*of\s*)?internship|upon\s*(?:full[\s\-]*time\s*)?(?:absorption|confirmation))(?:[\s:\-–—|]+|(?:\s+(?:offered\s+)?(?:is|of)\s+))([₹Rs\.\s0-9,\-]+(?:lpa|lakhs?|lac|inr|per\s*annum|pa)?)',
            text,
            re.IGNORECASE
        )

        stipend_val = stipend_match.group(1).split("\n")[0].strip() if stipend_match else None
        ctc_val = ctc_match.group(1).split("\n")[0].strip() if ctc_match else None

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
            lpa_m = re.search(r'\b([0-9]+(?:\.[0-9]+)?\s*lpa)\b', text, re.IGNORECASE)
            if lpa_m:
                ctc_val = lpa_m.group(1).strip()

        # Check for internship duration
        intern_duration_match = re.search(r'([0-9]+)\s*[\-]?\s*months?\s*(?:internship|training)?', text, re.IGNORECASE)
        if not intern_duration_match:
            intern_duration_match = re.search(r'for\s+([0-9]+)\s*[\-]?\s*months?', text, re.IGNORECASE)
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

            compensation_details["stipend"] = stipend_formatted
            compensation_details["full_time_ctc"] = ctc_val
            compensation_details["staged_compensation"] = [
                {"stage": f"Internship ({intern_duration or 'Period'})", "amount": stipend_formatted},
                {"stage": "Full Time / Post-Conversion", "amount": ctc_val}
            ]
            salary_range = f"Stipend: {stipend_formatted} → Full Time CTC: {ctc_val}"
            evidence["salary_range"] = salary_range
            review_flags.append(
                f"Staged compensation detected ({stipend_formatted} internship stipend, followed by {ctc_val} full-time CTC). Preserved as progression stages."
            )
            return salary_range, compensation_details

        # 2. Check for numeric lakhs in rupees (e.g. ₹14,00,000 - ₹20,00,000 PA)
        num_lakhs_range = re.search(
            r'[₹Rs\.\s]*(\d{1,2})(?:,00,000|00000)\s*[\-–—to\s]+\s*[₹Rs\.\s]*(\d{1,2})(?:,00,000|00000)\s*(?:pa|per\s*annum|ctc)?',
            text,
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
            text,
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
            r'([₹Rs\.\s0-9]+(?:\.[0-9]+)?\s*[\-–—to\s]+\s*[₹Rs\.\s0-9]+(?:\.[0-9]+)?\s*(?:lpa|lakhs?|lac))',
            text,
            re.IGNORECASE
        )
        if match_lpa_range:
            salary_range = match_lpa_range.group(1).strip()
            compensation_details["full_time_ctc"] = salary_range
            evidence["salary_range"] = salary_range
            return salary_range, compensation_details

        # Single LPA value
        match_single_lpa = re.search(
            r'([₹Rs\.\s0-9]+(?:\.[0-9]+)?\s*(?:lpa|lakhs?|lac))',
            text,
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
            r'(?:application\s*closing\s*date|closing\s*date)(?:[\s:\-–—|]+|\s+is\s+)([^\n\r\.;]+)',
            r'(?:last\s*date\s*(?:to\s*(?:apply|register)|for\s*(?:student\s*)?(?:registration|applying|submission)))(?:[\s:\-–—|]+|\s+is\s+)([^\n\r\.;]+)',
            r'(?:application\s*deadline|registration\s*deadline|apply\s*on\s*or\s*before|apply\s*by|applications?\s*close(?:\s*on)?)(?:[\s:\-–—|]+|\s+is\s+)([^\n\r\.;]+)',
            r'deadline[\s:\-–—|]+([^\n\r\.;]+)'
        ]

        for p in deadline_patterns:
            dm = re.search(p, text, re.IGNORECASE)
            if dm:
                raw_snippet = dm.group(1).strip()
                evidence["application_deadline"] = dm.group(0).strip()
                # Check for year presence
                has_year = bool(re.search(r'\b202[4-9]\b', raw_snippet))
                if not has_year:
                    review_flags.append(
                        f"Incomplete date: Missing year in deadline expression '{raw_snippet}'. Placement Officer confirmation required."
                    )
                    deadline = raw_snippet  # Keep raw text for review, do not hallucinate year
                else:
                    deadline = self._format_date_iso(raw_snippet) or raw_snippet
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
                has_year = bool(re.search(r'\b202[4-9]\b', raw_snippet))
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
        clean = date_str.strip()
        # Clean ordinals: 1st, 2nd, 3rd, 15th
        clean_clean = re.sub(r'(\d+)(?:st|nd|rd|th)', r'\1', clean, flags=re.IGNORECASE)

        # Common format trials
        formats = [
            "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y",
            "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y",
            "%d %B %Y %I:%M %p", "%d %b %Y %I:%M %p",
            "%d-%m-%Y %I:%M %p", "%Y-%m-%d %H:%M"
        ]

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
            "sap": "SAP"
        }
        return special_casing.get(skill.lower(), skill.title())

    def _extract_application_url_and_instructions(
        self,
        text: str,
        evidence: Dict[str, str]
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract external company application URL (http/https) and application instructions.
        Looks for explicit links in context of application, registration, careers, portal, etc.
        """
        app_url: Optional[str] = None
        instructions: Optional[str] = None

        # 1. URL extraction
        url_matches = list(re.finditer(r'https?://[^\s<>"\'\`,;)]+', text, re.IGNORECASE))
        candidate_urls = []
        for m in url_matches:
            raw_url = m.group(0).rstrip('.,;:)]>')
            if raw_url.startswith(('http://', 'https://')):
                candidate_urls.append(raw_url)

        if candidate_urls:
            def score_url(u: str) -> int:
                score = 0
                u_lower = u.lower()
                if any(k in u_lower for k in ["apply", "career", "job", "portal", "recruit", "form", "forms.gle"]):
                    score += 10
                u_idx = text.find(u)
                if u_idx != -1:
                    window = text[max(0, u_idx - 100):min(len(text), u_idx + len(u) + 100)].lower()
                    if any(k in window for k in ["apply", "application", "register", "registration", "portal", "submit", "link", "url"]):
                        score += 5
                return score

            best_url = max(candidate_urls, key=score_url)
            app_url = best_url
            evidence["application_url"] = app_url

        # 2. Application instructions extraction
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

    def _extract_description(self, text: str, evidence: Dict[str, str]) -> str:
        """Extract a readable summary excerpt of the job description."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if paragraphs:
            summary = paragraphs[0] if len(paragraphs[0]) >= 30 else ("\n\n".join(paragraphs[:2]))
            evidence["description"] = summary[:150] + "..." if len(summary) > 150 else summary
            return summary[:800].strip()
        return text[:500].strip()

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
            "review_flags": ["No text provided for analysis."],
            "field_evidence": {}
        })


# Global singleton instance
jd_parser_service = JdParserService()
