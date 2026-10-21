"""
Recruitment Result Extractor Service

Extracts structured tabular candidate records from uploaded company result files:
- CSV (.csv)
- Excel (.xlsx, .xls)
- PDF Tables (.pdf via pdfplumber)
- Text/OCR fallback for image scans

Preserves exact raw row values in raw_data, maps common column header synonyms,
and normalizes initial result terms safely.
"""

import os
import io
import re
import csv
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Column Header Synonym Mappings (normalized lower-case trimmed keys)
HEADER_SYNONYMS = {
    "usn": [
        "usn", "usn no", "usn no.", "usn_no", "roll no", "roll no.", "roll_no", "rollno",
        "reg no", "reg no.", "reg_no", "regno", "register no", "register number",
        "registration no", "registration number", "enrollment no", "enrollment number",
        "univ seat no", "university seat number", "seat no", "student id", "candidate id"
    ],
    "name": [
        "candidate name", "candidate_name", "student name", "student_name", "name",
        "full name", "full_name", "applicant name", "name of candidate", "name of student"
    ],
    "email": [
        "email", "email id", "email_id", "emailid", "e-mail", "e-mail id", "mail",
        "college email", "student email", "personal email", "email address"
    ],
    "status": [
        "status", "result", "selection status", "selection_status", "round result",
        "round status", "shortlist status", "interview status", "final status",
        "outcome", "decision", "final result", "round 1 result", "round 2 result"
    ],
    "branch": [
        "branch", "department", "dept", "stream", "course", "discipline"
    ],
    "remarks": [
        "remarks", "comments", "feedback", "notes", "reason", "extra info"
    ],
    "sl_no": [
        "sl no", "sl no.", "sl. no.", "sl.no", "sl_no", "s no", "s. no.", "s.no",
        "serial no", "serial no.", "serial number", "sr no", "sr. no.", "sr_no",
        "sino", "slno", "si no", "si. no.", "si.no"
    ]
}

# Non-candidate document titles, announcements, exam duty banners, and page headings
BANNER_PATTERNS = [
    r"campus\s+(?:recruitment|placement|hiring)",
    r"recruitment\s+drive",
    r"shortlist(?:ed)?\s+candidates?",
    r"selection\s+list",
    r"final\s+(?:results?|selection|offers?)",
    r"examination\s+duty",
    r"exam\s+duty",
    r"duty\s+chart",
    r"vtu\s+(?:theory\s+)?exam",
    r"college\s+of\s+engineering",
    r"department\s+of\s+",
    r"training\s+(?:&|and)\s+placement",
    r"coordinator\s+signature",
    r"signature\s+of\s+(?:hod|principal|coordinator|officer)",
    r"page\s+\d+\s+(?:of|/)\s+\d+",
    r"date\s*:\s*\d+",
    r"venue\s*:\s*",
    r"time\s*:\s*\d+",
    r"semester\s*:\s*",
    r"session\s*:\s*",
    r"room\s+no\b",
    r"total\s+candidates?",
    r"sl\s*no\b|serial\s*no\b|si\s*no\b",
    # Notice phrases and explanatory sentences
    r"\bwe\s+(?:are\s+)?(?:kindly\s+)?(?:request|inform|advise|pleased|glad|delighted|announce)\b",
    r"\bpleased\s+to\s+inform\b",
    r"\bplease\s+(?:find|inform|note|report|contact|ensure|advise)\b",
    r"\bkindly\s+(?:request|inform|confirm|advise|note|find)\b",
    r"\brespective\s+students?\b",
    r"\babout\s+their\s+interview\b",
    r"\binterview\s+(?:schedule|process|dates?|timings?|venue|location|details)\b",
    r"\bshortlisted\s+for\s+(?:the\s+)?interview\b",
    r"\breport\s+to\s+(?:the\s+)?.*office\b",
    r"\bconfirm\s+(?:the\s+)?availability\b",
    r"\bfinalize\s+(?:the\s+)?interview\b",
    r"\bnecessary\s+arrangements\b",
    r"\bselection\s+process\b",
    r"\bapplication[-\s]level\s+screening\b",
    r"\bpre[-\s]placement\s+talk\b",
    r"\bgroup\s+discussion\s+round\b",
    r"\bpersonal\s+interview\b",
    r"\bregistration\s+link\b",
    r"\blast\s+date\s+of\b",
    r"\bcompany\s+profile\b",
    r"\bjob\s+description\b",
    r"\bworking\s+(?:days|hours)\b",
    r"\brequired\s+skills\b",
    r"\beducational\s+qualification\b",
    r"\bcompensation\b",
    r"\bannual\s+ctc\b",
    r"\bstipend\s+is\b",
    r"\bwork\s+mode\b",
    r"\bon\s*site\b",
    r"\bhead\s+office\b",
    r"\bregistered\s+office\b",
    r"\borganized\s+&\s+coordinated\b",
    r"\ball\s+other\s+details\b",
    r"\bmentioned\s+in\s+the\s+attachment\b",
    r"\bgraduating\s+batch\b",
    r"\bhiring\s+students\b",
    r"\binterested\s+candidates\b",
    r"\bnot\s+supposed\s+to\s+pay\b",
    r"\bpay\s+any\s+amount\b",
    r"\brecruitment\s+partners?\b",
    r"\bjoining\s+date\b",
    r"\bfor\s+your\s+reference\b",
    r"\bdear\s+(?:sir|madam)\b",
]

# Words that indicate sentence structure or non-name text
SENTENCE_STOPWORDS = {
    "we", "you", "they", "them", "their", "our", "us", "he", "she", "him", "her",
    "this", "that", "these", "those", "which", "what", "who", "whom", "whose",
    "the", "an",
    "and", "or", "but", "if", "because", "as", "until", "while", "of", "at", "by",
    "for", "with", "about", "against", "between", "into", "through", "during",
    "before", "after", "above", "below", "to", "from", "up", "down", "in", "out",
    "on", "off", "over", "under", "again", "further", "then", "once",
    "is", "am", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "having", "do", "does", "did", "doing",
    "would", "should", "could", "ought", "shall", "will", "can", "may", "might", "must",
    "please", "kindly", "request", "inform", "advise", "report", "confirm", "finalize",
    "students", "interview", "schedule", "availability", "attending", "arrangements",
    "timings", "dates", "office", "process", "details", "qualification", "attachment",
    "eligible", "stream", "batch", "annual", "ctc", "stipend", "lakhs", "per", "month",
    "mode", "site", "company", "requirements", "guidelines", "criteria"
}

# Words that are known non-candidate tokens or noise fragments
NOISE_NAME_WORDS = {
    "non", "none", "nil", "na", "null", "not", "no", "yes", "ok",
    "total", "page", "date", "time", "venue", "sl", "serial", "sr",
    "usn", "name", "email", "status", "branch", "dept", "department",
    "round", "result", "remarks", "gender", "male", "female", "cgpa",
    "oct", "nov", "dec", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep",
    "october", "november", "december", "january", "february", "march", "april",
    "june", "july", "august", "september", "am", "pm"
}


class RecruitmentResultExtractionError(ValueError):
    """Raised when recruitment result extraction fails."""
    pass


class RecruitmentResultExtractor:
    """Service for extracting structured candidate rows from recruitment result documents."""

    def extract(self, file_bytes: bytes, filename: str, mime_type: Optional[str] = None) -> Dict[str, Any]:
        """Convenience alias for extract_candidates_from_bytes."""
        return self.extract_candidates_from_bytes(file_bytes, filename)

    def extract_candidates_from_bytes(
        self, file_bytes: bytes, filename: str
    ) -> Dict[str, Any]:
        """
        Extract structured candidate records from file bytes based on file extension.
        """
        if not file_bytes or len(file_bytes) == 0:
            raise RecruitmentResultExtractionError("The uploaded result file is empty.")

        ext = os.path.splitext(filename or "")[1].lower()

        if ext in [".csv", ".txt"]:
            return self._extract_csv(file_bytes)
        elif ext in [".xlsx", ".xls"]:
            return self._extract_excel(file_bytes, ext)
        elif ext == ".pdf":
            return self._extract_pdf(file_bytes)
        elif ext in [".docx", ".doc"]:
            return self._extract_docx(file_bytes)
        elif ext in [".png", ".jpg", ".jpeg"]:
            return self._extract_image(file_bytes)
        else:
            raise RecruitmentResultExtractionError(f"Unsupported result file format: '{ext}'. Supported formats: .csv, .xlsx, .xls, .pdf, .docx, .txt, .png, .jpg, .jpeg")

    # =========================================================================
    # IMAGE OCR EXTRACTION (SPATIAL TABLE RECONSTRUCTION)
    # =========================================================================
    def _extract_image(self, file_bytes: bytes) -> Dict[str, Any]:
        """Extract candidate rows from image files using spatial OCR with fallback."""
        # 1. Attempt spatial image_to_data extraction (preserves row/column alignment)
        try:
            from app.services.ocr_service import ocr_service
            ocr_data = ocr_service.extract_ocr_data_from_image_bytes(file_bytes)
            if ocr_data and any(str(t).strip() for t in ocr_data.get("text", [])):
                res = self._parse_candidates_from_ocr_data(ocr_data, source_type="image", source_page=1)
                if res and res.get("total_rows", 0) > 0:
                    return res
        except RecruitmentResultExtractionError:
            raise
        except Exception as spatial_err:
            logger.warning(f"Spatial OCR table parsing failed on image: {spatial_err}; trying text fallback...")

        # 2. Fallback to image_to_string text extraction
        try:
            from app.services.ocr_service import ocr_service
            text = ocr_service.extract_text_from_image_bytes(file_bytes)
        except Exception as e:
            raise RecruitmentResultExtractionError(f"OCR service failed on image: {str(e)}")

        if not text or text.startswith("OCR Error:") or text.startswith("Error:"):
            raise RecruitmentResultExtractionError(f"Could not extract readable text from image: {text}")

        return self._parse_candidates_from_ocr_text(text, source_type="image")

    def _is_title_banner(self, text: str) -> bool:
        """Identify non-candidate document titles, announcements, exam duty banners, or labels (excluding column header rows)."""
        if not text:
            return True
        t = str(text).strip().lower()
        if len(t) < 3:
            return True
        for pat in BANNER_PATTERNS:
            if re.search(pat, t, re.IGNORECASE):
                return True
        return False

    def _is_banner_text(self, text: str) -> bool:
        """Identify non-candidate document titles, announcements, exam duty banners, or labels."""
        if not text:
            return True
        t = str(text).strip().lower()
        if len(t) < 3:
            return True
        for pat in BANNER_PATTERNS:
            if re.search(pat, t, re.IGNORECASE):
                return True

        # Reject pure table header lines (e.g. "USN / Register Number Name Email Status")
        header_kw = [
            "usn", "register number", "reg no", "roll no", "candidate name", "student name",
            "email", "status", "department", "branch", "discipline", "remarks", "selection status"
        ]
        matches = sum(1 for kw in header_kw if kw in t)
        if matches >= 2 and "@" not in t and not re.search(r"\b[0-9][a-zA-Z]{2}[0-9]{2}[a-zA-Z0-9]{2,5}\b", t, re.IGNORECASE):
            return True

        return False

    def _detect_header_row(self, row_tokens: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Tuple[int, int]]]:
        """
        Check if a visual row represents a table column header.
        Returns (is_header, mapping of canonical_col -> (left_x, right_x)).
        """
        row_text = " ".join(t["text"] for t in row_tokens).lower()
        norm_row = self._normalize_key(row_text)

        detected_cols: Dict[str, Tuple[int, int]] = {}
        for canon_field, syns in HEADER_SYNONYMS.items():
            for syn in syns:
                norm_syn = self._normalize_key(syn)
                if norm_syn in norm_row:
                    matched_tokens = [
                        t for t in row_tokens
                        if self._normalize_key(t["text"]) in norm_syn or norm_syn in self._normalize_key(t["text"])
                    ]
                    if matched_tokens:
                        col_left = min(t["left"] for t in matched_tokens)
                        col_right = max(t["right"] for t in matched_tokens)
                        detected_cols[canon_field] = (col_left, col_right)
                        break

        # A table header row requires at least 2 detected distinct column headers
        is_header = len(detected_cols) >= 2
        return is_header, detected_cols

    def _classify_row_tokens(self, tokens: List[Dict[str, Any]]) -> Tuple[str, str, str, str, str]:
        """
        Classify row tokens into (usn, name, email, status, branch) when column headers are absent.
        """
        usn_parts = []
        name_parts = []
        email_parts = []
        status_parts = []
        branch_parts = []

        for t in tokens:
            w = t["text"]
            w_clean = re.sub(r"[\s\-\/\.]+", "", w).upper()
            if re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", w):
                email_parts.append(w)
            elif re.search(r"\b[4A0-9][a-zA-Z]{2}[0-9]{2}[a-zA-Z0-9]{2,5}\b", w_clean):
                usn_parts.append(w)
            elif w.lower() in ["selected", "rejected", "shortlisted", "absent", "cleared", "placed", "hired", "offer"]:
                status_parts.append(w)
            elif w.upper() in ["CSE", "ISE", "AIML", "AIDS", "ECE", "EEE", "ME", "CV", "MCA", "MBA"]:
                branch_parts.append(w)
            else:
                name_parts.append(w)

        return (
            " ".join(usn_parts).strip(),
            " ".join(name_parts).strip(),
            " ".join(email_parts).strip(),
            " ".join(status_parts).strip(),
            " ".join(branch_parts).strip()
        )

    def _is_valid_usn_format(self, usn: Optional[str]) -> bool:
        """Verify if a string matches valid institutional candidate identifier formats."""
        if not usn:
            return False
        u = re.sub(r"[\s\-\.]+", "", str(usn)).upper()
        # VTU format: 1-digit region, 2-letter college, 2-digit year, 2-3 letter branch, 2-4 digit roll
        if re.match(r"^[0-9][A-Z]{2}[0-9]{2}[A-Z0-9]{2,3}[0-9]{2,4}$", u):
            return True
        # Standard institutional roll format: e.g. TEST36419, CS20210045
        if re.match(r"^[A-Z]{2,6}[0-9]{4,10}$", u):
            return True
        # Numeric / college year roll format: e.g. 21CSE0045
        if re.match(r"^[0-9]{2}[A-Z]{2,4}[0-9]{3,6}$", u):
            return True
        # General candidate alphanumeric ID (6-14 chars, alphanumeric only, with digits and letters)
        if 6 <= len(u) <= 14 and u.isalnum() and any(c.isdigit() for c in u) and any(c.isalpha() for c in u):
            if not any(w in u.lower() for w in ["the", "students", "interview", "schedule", "office", "about", "dates"]):
                return True
        return False

    def _is_plausible_candidate_name(self, name: Optional[str]) -> bool:
        """Validate if extracted candidate name is genuine rather than arbitrary OCR text or sentences."""
        if not name:
            return False
        clean = re.sub(r"[^a-zA-Z\s\.\-]", " ", str(name)).strip()
        clean = re.sub(r"\s+", " ", clean)
        tokens = clean.split()
        if not tokens or len(tokens) > 5:
            return False
        if len(tokens) == 1:
            tok_lower = tokens[0].lower()
            if tok_lower in NOISE_NAME_WORDS or tok_lower in SENTENCE_STOPWORDS:
                return False
            if len(tokens[0]) < 2:
                return False
            return True
        # Multi-token: check stopwords (single letter tokens are initials, not articles)
        real_words = [t.lower() for t in tokens if len(t) > 1]
        stopwords_count = sum(1 for w in real_words if w in SENTENCE_STOPWORDS or w in NOISE_NAME_WORDS)
        if stopwords_count > 0:
            return False
        alpha_chars = sum(len(t) for t in tokens if t.isalpha())
        return alpha_chars >= 3

    def _normalize_candidate_fields(
        self, raw_usn: str, raw_name: str, raw_email: str, raw_status: str, full_row_text: str = ""
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        Conservatively normalize fields, resolve accidental column merges, and clean noise.
        """
        usn = str(raw_usn or "").strip("‘'\"-–—.:;| \t")
        name = str(raw_name or "").strip("‘'\"-–—.:;|•*▪ \t")
        email = str(raw_email or "").strip("‘'\"-–—.:;| \t")
        status = str(raw_status or "").strip()
        full_text = str(full_row_text or "").strip()

        # 1. Email extraction & dot-correction
        email_clean = ""
        email_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-.]+", full_text or email)
        if email_match:
            extracted = email_match.group(0).lower()
            if not re.search(r"\.[a-zA-Z]{2,4}$", extracted):
                extracted = re.sub(r"(gmail|yahoo|hotmail|outlook|vcet|edu)(com|in|org|net)$", r"\1.\2", extracted)
            email_clean = extracted
        elif "@" in email:
            email_clean = email.lower()

        # 2. Status extraction and normalization
        status_clean = "shortlisted"
        for term in ["selected", "rejected", "shortlisted", "absent", "cleared", "not selected", "placed", "hired", "offer"]:
            if re.search(r"\b" + term + r"\b", status, re.IGNORECASE) or re.search(r"\b" + term + r"\b", full_text, re.IGNORECASE):
                status_clean = self._normalize_status(term)
                break

        # 3. USN extraction & common OCR misreadings
        usn_clean = None
        usn_raw_match = None
        usn_match = re.search(r"\b([4AH0-9])([A-Za-z0-9]{2})\s*([0-9]{2})\s*([A-Za-z0-9]{1,3})\s*([0-9]{2,4})\b", usn or full_text)
        if not usn_match and full_text:
            usn_match = re.search(r"\b([4AH0-9])([A-Za-z0-9]{2})\s*([0-9]{2})\s*([A-Za-z0-9]{1,3})\s*([0-9]{2,4})\b", full_text)

        if usn_match:
            usn_raw_match = usn_match.group(0)
            c1, c2, yr, br, num = usn_match.groups()
            c2_clean = c2.upper()
            c1 = "4" if c1[0].upper() in ["A", "H"] and c2_clean == "VP" else c1[0].upper()
            c2 = c2_clean
            if len(br) == 1 and len(num) == 4 and num[0] in ["9", "5", "8", "S"]:
                br = br + "S"
                num = num[1:]
            br_fixed = br.upper().replace("1", "I").replace("L", "I").replace("9", "S").replace("5", "S")
            usn_clean = f"{c1}{c2}{yr}{br_fixed}{num}"
        elif usn:
            merged_match = re.match(r"^([0-9][a-zA-Z]{2}[0-9]{2}[a-zA-Z0-9]{2,5}[0-9]{2,4})([a-zA-Z].*)$", usn.strip())
            if merged_match:
                cand_usn = merged_match.group(1).upper()
                if self._is_valid_usn_format(cand_usn):
                    usn_clean = cand_usn
                    spilled = merged_match.group(2)
                    name = (spilled + " " + name).strip()
            elif self._is_valid_usn_format(usn.strip()):
                usn_clean = usn.strip().upper()
            else:
                usn_clean = None

        # 4. Name extraction & isolation
        rem = name or ""
        if not rem or not re.search(r"[a-zA-Z]{2,}", rem) or (usn_raw_match and usn_raw_match in rem):
            rem = full_text or ""

        if usn_raw_match:
            rem = re.sub(re.escape(usn_raw_match), "", rem, flags=re.IGNORECASE)
        if usn_clean:
            rem = re.sub(re.escape(usn_clean), "", rem, flags=re.IGNORECASE)
        if usn:
            rem = re.sub(re.escape(usn), "", rem, flags=re.IGNORECASE)
        # Remove standalone digits from split USN tokens
        rem = re.sub(r"\b\d{3,5}\b", "", rem)
        rem = re.sub(r"[a-zA-Z0-9_.+-]*@[a-zA-Z0-9-.]*", "", rem)
        for term in ["selected", "rejected", "shortlisted", "absent", "cleared", "not selected", "placed", "hired", "offer"]:
            rem = re.sub(r"\b" + term + r"\b", "", rem, flags=re.IGNORECASE)

        rem = re.sub(r"^\d+[\.\)\-\s]+\s*", "", rem)
        rem = re.sub(r"[—\-–_.:;|~^`=]+", " ", rem)
        rem = re.sub(r"\s+", " ", rem).strip()
        rem = re.sub(r"([a-z])([A-Z])", r"\1 \2", rem)

        # Defensive cleanup: strip leading serial tokens / noise (e.g. DBD, WwW, bt, Oo)
        toks = rem.split()
        if len(toks) >= 2:
            first_tok_lower = toks[0].lower()
            if first_tok_lower in NOISE_NAME_WORDS or (len(toks[0]) in (2, 3) and toks[0].isupper() and all(c not in 'AEIOU' for c in toks[0])):
                rem = " ".join(toks[1:])

        name_clean = rem if len(rem) >= 2 else (name or None)

        return (usn_clean or None, name_clean or None, email_clean or None, status_clean or "shortlisted")

    def _is_valid_candidate_row(
        self, usn: Optional[str], name: Optional[str], email: Optional[str], status: Optional[str], full_row_text: str
    ) -> bool:
        """
        Structural validation to reject false candidate records:
        - Document titles, banners, date labels, exam duties, and table headers are rejected.
        - Notice paragraphs, instructions, and announcement sentences are rejected.
        - Rows without USN or email must have a valid student name and non-banner structure.
        """
        if self._is_banner_text(full_row_text):
            return False

        # Reject if all/majority of tokens in the row match column header synonyms
        tokens = [self._normalize_key(w) for w in full_row_text.split() if self._normalize_key(w)]
        if tokens:
            header_count = 0
            for t in tokens:
                for syns in HEADER_SYNONYMS.values():
                    if any(self._normalize_key(s) == t for s in syns):
                        header_count += 1
                        break
            if header_count >= len(tokens) * 0.7:
                return False

        # Reject if row contains notice or announcement language
        if any(re.search(pat, full_row_text, re.IGNORECASE) for pat in BANNER_PATTERNS):
            return False

        # Validate name plausibility
        name_is_plausible = self._is_plausible_candidate_name(name)
        if name and not name_is_plausible:
            # If name is clearly a sentence/notice phrase or has > 5 words, reject row entirely
            if any(re.search(pat, name, re.IGNORECASE) for pat in BANNER_PATTERNS) or len(name.split()) > 5:
                return False
            name = None

        # Candidate validity tiers:
        # 1. Valid USN
        if usn and self._is_valid_usn_format(usn):
            return True

        # 2. Valid Email
        if email and re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email):
            return True

        # 3. Plausible Name without USN or email (must be a genuine name with proper structure)
        if name and name_is_plausible:
            tokens = name.split()
            # Must have at least 2 tokens with proper capitalized structure (e.g. "Adithya CS")
            # or a single valid name
            if len(tokens) >= 2 and all(t[0].isupper() for t in tokens if t[0].isalpha()):
                return True

        return False

    def _parse_candidates_from_ocr_data(
        self, ocr_data: Dict[str, Any], source_type: str = "document", source_page: int = 1
    ) -> Dict[str, Any]:
        """
        Parse structured candidate records using spatial bounding boxes from Tesseract image_to_data.
        - Clusters words into horizontal rows using vertical coordinates.
        - Identifies table header row and establishes column horizontal boundaries.
        - Rejects document titles, announcement banners, table headers, and unrelated fragments.
        - Slots words into detected columns (USN, Name, Email, Status, Branch) without shifting.
        - Conservatively normalizes noisy USNs.
        """
        import statistics

        texts = ocr_data.get("text", [])
        lefts = ocr_data.get("left", [])
        tops = ocr_data.get("top", [])
        widths = ocr_data.get("width", [])
        heights = ocr_data.get("height", [])
        confs = ocr_data.get("conf", [])

        tokens: List[Dict[str, Any]] = []
        for i in range(len(texts)):
            w_text = str(texts[i]).strip()
            if not w_text or w_text in ["|", "~", "^", "—", "_", "`"]:
                continue
            left = int(lefts[i])
            top = int(tops[i])
            w = int(widths[i])
            h = int(heights[i])
            conf = float(confs[i]) if i < len(confs) and confs[i] != -1 else 50.0
            tokens.append({
                "text": w_text,
                "left": left,
                "top": top,
                "right": left + w,
                "bottom": top + h,
                "width": w,
                "height": h,
                "center_x": left + w / 2,
                "center_y": top + h / 2,
                "conf": conf,
            })

        if not tokens:
            raise RecruitmentResultExtractionError(f"{source_type.capitalize()} OCR extracted no readable text tokens.")

        # Vertical clustering into visual rows
        med_h = statistics.median([t["height"] for t in tokens]) if tokens else 10
        y_tol = max(8, int(med_h * 0.6))
        tokens.sort(key=lambda t: (t["top"], t["left"]))

        v_rows: List[Dict[str, Any]] = []
        for t in tokens:
            matched_row = None
            for r in v_rows:
                if abs(t["center_y"] - r["avg_y"]) <= y_tol:
                    matched_row = r
                    break
            if matched_row:
                matched_row["tokens"].append(t)
                matched_row["min_top"] = min(matched_row["min_top"], t["top"])
                matched_row["max_bottom"] = max(matched_row["max_bottom"], t["bottom"])
                matched_row["avg_y"] = sum(tok["center_y"] for tok in matched_row["tokens"]) / len(matched_row["tokens"])
            else:
                v_rows.append({
                    "tokens": [t],
                    "min_top": t["top"],
                    "max_bottom": t["bottom"],
                    "avg_y": t["center_y"],
                })

        for r in v_rows:
            r["tokens"].sort(key=lambda t: t["left"])
            r["text"] = " ".join(t["text"] for t in r["tokens"])

        # Detect Header Row and Column Boundaries
        header_row_idx: Optional[int] = None
        detected_col_spans: Dict[str, Tuple[int, int]] = {}

        for r_idx, r in enumerate(v_rows):
            is_hdr, col_spans = self._detect_header_row(r["tokens"])
            if is_hdr:
                header_row_idx = r_idx
                detected_col_spans = col_spans
                break
            if self._is_banner_text(r["text"]):
                continue

        # Compute horizontal boundary cutoffs if header row was detected
        col_zones: List[Tuple[str, float, float]] = []
        canonical_headers: List[str] = ["USN", "Name", "Email", "Status"]

        if header_row_idx is not None and detected_col_spans:
            sorted_cols = sorted(detected_col_spans.items(), key=lambda x: x[1][0])
            first_col_left = sorted_cols[0][1][0]
            if first_col_left > 180 and sorted_cols[0][0] != "sl_no":
                sorted_cols.insert(0, ("sl_no", (0, int(first_col_left - 30))))

            canonical_headers = [col_name.upper() for col_name, _ in sorted_cols]
            
            cutoffs = [0.0]
            for i in range(len(sorted_cols) - 1):
                mid = (sorted_cols[i][1][1] + sorted_cols[i + 1][1][0]) / 2.0
                cutoffs.append(mid)
            cutoffs.append(float("inf"))

            for i, (col_name, _) in enumerate(sorted_cols):
                col_zones.append((col_name, cutoffs[i], cutoffs[i + 1]))

        # Data rows extraction
        start_row_idx = (header_row_idx + 1) if header_row_idx is not None else 0
        data_rows: List[List[str]] = []

        extra_data: List[Dict[str, Any]] = []
        for r_idx in range(start_row_idx, len(v_rows)):
            r = v_rows[r_idx]
            row_text = r["text"]

            if self._is_banner_text(row_text):
                continue

            is_rep_hdr, _ = self._detect_header_row(r["tokens"])
            if is_rep_hdr:
                continue

            usn_val = ""
            name_val = ""
            email_val = ""
            status_val = ""
            branch_val = ""

            if col_zones:
                cells: Dict[str, List[str]] = {col_name: [] for col_name, _, _ in col_zones}
                for t in r["tokens"]:
                    cx = t["center_x"]
                    assigned_col = None
                    for col_name, left_bound, right_bound in col_zones:
                        if left_bound <= cx < right_bound:
                            assigned_col = col_name
                            break
                    if not assigned_col:
                        assigned_col = col_zones[-1][0]
                    cells[assigned_col].append(t["text"])

                usn_val = " ".join(cells.get("usn", [])).strip()
                name_val = " ".join(cells.get("name", [])).strip()
                email_val = " ".join(cells.get("email", [])).strip()
                status_val = " ".join(cells.get("status", [])).strip()
                branch_val = " ".join(cells.get("branch", [])).strip()
            else:
                usn_val, name_val, email_val, status_val, branch_val = self._classify_row_tokens(r["tokens"])

            usn_clean, name_clean, email_clean, status_clean = self._normalize_candidate_fields(
                usn_val, name_val, email_val, status_val, row_text
            )

            if not self._is_valid_candidate_row(usn_clean, name_clean, email_clean, status_clean, row_text):
                logger.debug(
                    f"Excluding non-candidate OCR row {r_idx}: text={row_text[:60]!r}, "
                    f"usn={usn_clean!r}, name={name_clean!r}"
                )
                continue

            extra_data.append({"raw_usn": usn_val or usn_clean or ""})

            if col_zones:
                row_items = []
                for h in canonical_headers:
                    h_lower = h.lower()
                    if h_lower == "usn":
                        row_items.append(usn_clean or "")
                    elif h_lower == "name":
                        row_items.append(name_clean or "")
                    elif h_lower == "email":
                        row_items.append(email_clean or "")
                    elif h_lower == "status":
                        row_items.append(status_clean or "shortlisted")
                    elif h_lower == "branch":
                        row_items.append(branch_val or "")
                    else:
                        row_items.append("")
                data_rows.append(row_items)
            else:
                data_rows.append([usn_clean or "", name_clean or "", email_clean or "", status_clean or "shortlisted"])

        if not data_rows:
            raise RecruitmentResultExtractionError(
                f"Could not extract any candidate records from the {source_type} OCR output. "
                "Please verify that the document contains recognizable student USNs, names, or emails."
            )

        return self._build_extracted_result(canonical_headers, data_rows, source_page=source_page, extra_row_data=extra_data)

    def _parse_candidates_from_ocr_text(
        self, text: str, source_type: str = "document", source_page: int = 1
    ) -> Dict[str, Any]:
        """
        Parse structured candidate records from OCR text output.
        Handles delimited text, aligned column text, and free-form pattern matching.
        Enforces rejection of document banners, examination duties, and table headers.
        """
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            raise RecruitmentResultExtractionError(f"{source_type.capitalize()} OCR extracted no readable text lines.")

        clean_lines = [l for l in lines if not re.match(r"^---\s*Page\s*\d+\s*---$", l, re.IGNORECASE)]
        if not clean_lines:
            raise RecruitmentResultExtractionError(f"{source_type.capitalize()} OCR extracted no readable data lines.")

        # Filter out document title and announcement banners (preserving table header lines for structural parsing)
        clean_lines = [l for l in clean_lines if not self._is_title_banner(l)]
        if not clean_lines:
            raise RecruitmentResultExtractionError(f"{source_type.capitalize()} OCR extracted no readable data lines.")

        # Attempt structured delimiter-based parsing (e.g. CSV-like text inside image/scan)
        for candidate_delim in [",", "\t", ";", "|"]:
            if candidate_delim in clean_lines[0] and clean_lines[0].count(candidate_delim) >= 1:
                reader = csv.reader(clean_lines, delimiter=candidate_delim)
                raw_rows = [row for row in reader if any(cell.strip() for cell in row)]
                if len(raw_rows) >= 2:
                    row_0_text = " ".join(raw_rows[0]).lower()
                    if any(k in row_0_text for k in ["usn", "roll", "reg", "name", "email", "status", "branch"]):
                        header_row = raw_rows[0]
                        data_rows = [r for r in raw_rows[1:] if not self._is_banner_text(" ".join(r))]
                    else:
                        header_row = ["USN", "Name", "Email", "Status"]
                        data_rows = [r for r in raw_rows if not self._is_banner_text(" ".join(r))]
                    if data_rows:
                        return self._build_extracted_result(header_row, data_rows, source_page=source_page)

        # Tabular whitespace check: if header line has 2+ columns separated by 2+ spaces
        tokens_line_0 = re.split(r"\s{2,}|\t", clean_lines[0])
        if len(tokens_line_0) >= 2 and any(k in clean_lines[0].lower() for k in ["usn", "roll", "reg", "name", "email", "status", "candidate", "branch"]):
            headers = [t.strip() for t in tokens_line_0 if t.strip()]
            data_rows = []
            for line in clean_lines[1:]:
                if self._is_banner_text(line):
                    continue
                parts = [p.strip() for p in re.split(r"\s{2,}|\t", line) if p.strip()]
                if parts:
                    data_rows.append(parts)
            if data_rows:
                return self._build_extracted_result(headers, data_rows, source_page=source_page)

        # Free-form line pattern matching for USN / Name / Email / Status
        headers = ["USN", "Name", "Email", "Status"]
        data_rows = []
        for line in clean_lines:
            if self._is_banner_text(line):
                continue

            email_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", line)
            email = email_match.group(0).lower() if email_match else ""

            usn_match = re.search(r"\b[0-9][a-zA-Z]{2}[0-9]{2}[a-zA-Z]{0,3}[0-9]{2,4}\b|\b[a-zA-Z]{2,4}[0-9]{5,10}\b", line, re.IGNORECASE)
            usn = usn_match.group(0).upper() if usn_match else ""

            rem = line
            if email:
                rem = rem.replace(email, "")
            if usn:
                rem = re.sub(re.escape(usn), "", rem, flags=re.IGNORECASE)
            rem = rem.strip(" ,-|:\t")

            status = "shortlisted"
            for term in ["selected", "rejected", "shortlisted", "absent", "cleared", "placed", "hired", "offer"]:
                if re.search(r"\b" + term + r"\b", rem, re.IGNORECASE):
                    status = term
                    rem = re.sub(r"\b" + term + r"\b", "", rem, flags=re.IGNORECASE).strip(" ,-|:\t")
                    break

            name = rem
            name = re.sub(r"^\d+[\.\)\-\s]+\s*", "", name).strip("‘'\"-–—.:;|•*▪ \t")

            usn_clean, name_clean, email_clean, status_clean = self._normalize_candidate_fields(
                usn, name, email, status, line
            )

            # Validate before adding
            if not self._is_valid_candidate_row(usn_clean, name_clean, email_clean, status_clean, line):
                logger.debug(f"Excluding non-candidate OCR text line: {line[:60]!r}")
                continue

            data_rows.append([usn_clean or "", name_clean or "", email_clean or "", status_clean or "shortlisted"])

        if not data_rows:
            raise RecruitmentResultExtractionError(
                f"Could not extract any candidate records from the {source_type} OCR output. "
                "Please verify that the document contains recognizable student USNs, names, or emails."
            )

        return self._build_extracted_result(headers, data_rows, source_page=source_page)


    # =========================================================================
    # DOCX TABLE EXTRACTION
    # =========================================================================
    def _extract_docx(self, file_bytes: bytes) -> Dict[str, Any]:
        """Extract candidate rows from tables inside a DOCX document."""
        try:
            import docx
        except ImportError:
            raise RuntimeError("python-docx is required for DOCX table extraction.")

        try:
            doc = docx.Document(io.BytesIO(file_bytes))
        except Exception as e:
            raise ValueError(f"Failed to open Word document: {str(e)}")

        all_headers: Optional[List[str]] = None
        data_rows: List[List[str]] = []

        for table in doc.tables:
            table_rows = []
            for row in table.rows:
                row_cells = [cell.text.strip() for cell in row.cells]
                if any(row_cells):
                    table_rows.append(row_cells)

            if not table_rows:
                continue

            if all_headers is None:
                all_headers = table_rows[0]
                data_rows.extend(table_rows[1:])
            else:
                # If subsequent table repeats header, skip header row
                if [c.lower() for c in table_rows[0]] == [c.lower() for c in all_headers]:
                    data_rows.extend(table_rows[1:])
                else:
                    data_rows.extend(table_rows)

        if not all_headers or not data_rows:
            raise ValueError(
                "Could not extract a candidate table from this Word document. "
                "Ensure the document contains a table with candidate column headers (e.g., USN, Name, Status)."
            )

        return self._build_extracted_result(all_headers, data_rows, source_page=1)

    # =========================================================================
    # CSV EXTRACTION
    # =========================================================================
    def _extract_csv(self, file_bytes: bytes) -> Dict[str, Any]:
        """Parse CSV with robust encoding and delimiter detection."""
        # Try multiple encodings
        text = None
        for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
            try:
                text = file_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if text is None:
            raise ValueError("Failed to decode CSV file: unsupported character encoding.")

        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            raise ValueError("CSV file contains no readable data rows.")

        # Try sniffing delimiter, fallback to comma
        first_few = "\n".join(lines[:10])
        delimiter = ","
        try:
            dialect = csv.Sniffer().sniff(first_few, delimiters=",;\t|")
            delimiter = dialect.delimiter
        except Exception:
            if "\t" in lines[0] and lines[0].count("\t") > lines[0].count(","):
                delimiter = "\t"
            elif ";" in lines[0] and lines[0].count(";") > lines[0].count(","):
                delimiter = ";"

        reader = csv.reader(lines, delimiter=delimiter)
        raw_rows = [row for row in reader if any(cell.strip() for cell in row)]
        if not raw_rows:
            raise ValueError("CSV contains no rows.")

        header_row = raw_rows[0]
        data_rows = raw_rows[1:]

        return self._build_extracted_result(header_row, data_rows, source_page=1)

    # =========================================================================
    # EXCEL EXTRACTION
    # =========================================================================
    def _extract_excel(self, file_bytes: bytes, ext: str) -> Dict[str, Any]:
        """Parse Excel spreadsheets via pandas/openpyxl."""
        try:
            import pandas as pd
        except ImportError:
            raise RuntimeError("pandas / openpyxl is not installed for Excel extraction.")

        try:
            bio = io.BytesIO(file_bytes)
            # Read first sheet
            engine = "openpyxl" if ext == ".xlsx" else None
            df = pd.read_excel(bio, sheet_name=0, engine=engine)
        except Exception as e:
            raise ValueError(f"Failed to read Excel workbook: {str(e)}")

        if df.empty or len(df.columns) == 0:
            raise ValueError("Excel sheet is empty or contains no valid columns.")

        # Clean columns
        headers = [str(col).strip() for col in df.columns]
        data_rows = []
        for _, row in df.iterrows():
            row_vals = [
                str(val).strip() if pd.notna(val) else ""
                for val in row
            ]
            if any(row_vals):
                data_rows.append(row_vals)

        if not data_rows:
            raise ValueError("Excel sheet contains column headers but zero candidate data rows.")

        return self._build_extracted_result(headers, data_rows, source_page=1)

    # =========================================================================
    # PDF EXTRACTION
    # =========================================================================
    def _extract_pdf(self, file_bytes: bytes) -> Dict[str, Any]:
        """Extract tabular rows from PDF using pdfplumber."""
        try:
            import pdfplumber
        except ImportError:
            raise RuntimeError("pdfplumber is required for PDF table extraction.")

        all_headers: Optional[List[str]] = None
        extracted_rows: List[Tuple[List[str], int]] = []  # (row_cells, page_num)

        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                if len(pdf.pages) == 0:
                    raise ValueError("PDF file has 0 pages.")

                for page_idx, page in enumerate(pdf.pages, start=1):
                    tables = page.extract_tables()
                    if not tables:
                        # Fallback for tables without explicit graphic grid lines
                        try:
                            tables = page.extract_tables(table_settings={
                                "vertical_strategy": "text",
                                "horizontal_strategy": "text",
                            })
                        except Exception:
                            tables = []

                    for table in tables:
                        if not table or len(table) == 0:
                            continue

                        # Clean table cells
                        clean_table = [
                            [str(cell).strip() if cell is not None else "" for cell in row]
                            for row in table
                            if any(cell and str(cell).strip() for cell in row)
                        ]
                        if not clean_table:
                            continue

                        # Determine if first row is header
                        if all_headers is None:
                            all_headers = clean_table[0]
                            data_part = clean_table[1:]
                        else:
                            # If header repeated on page, skip it
                            if [c.lower() for c in clean_table[0]] == [c.lower() for c in all_headers]:
                                data_part = clean_table[1:]
                            else:
                                data_part = clean_table

                        for r in data_part:
                            extracted_rows.append((r, page_idx))

        except Exception as e:
            logger.error(f"Error opening or reading PDF tables: {e}", exc_info=True)
            raise ValueError(f"Failed to read PDF table: {str(e)}")

        if not all_headers or not extracted_rows:
            # Fallback: Attempt OCR extraction on scanned PDF
            logger.info("PDF contained no selectable tables; attempting scanned PDF OCR extraction...")
            try:
                from app.services.ocr_service import ocr_service
                # 1. Attempt spatial page OCR extraction
                try:
                    ocr_pages = ocr_service.extract_ocr_data_pages_from_scanned_pdf_bytes(file_bytes)
                    if ocr_pages:
                        all_page_rows: List[Tuple[List[str], int]] = []
                        all_extra_rows: List[Dict[str, Any]] = []
                        canonical_hdrs: Optional[List[str]] = None
                        for p_idx, p_data in enumerate(ocr_pages, start=1):
                            if not p_data or not any(str(t).strip() for t in p_data.get("text", [])):
                                continue
                            try:
                                p_res = self._parse_candidates_from_ocr_data(p_data, source_type="scanned_pdf", source_page=p_idx)
                                if p_res and p_res.get("rows"):
                                    if canonical_hdrs is None:
                                        canonical_hdrs = p_res.get("headers", ["USN", "Name", "Email", "Status"])
                                    for r in p_res["rows"]:
                                        row_cells = [
                                            r.get(h.lower()) or r.get("raw_data", {}).get(h, "")
                                            for h in canonical_hdrs
                                        ]
                                        all_page_rows.append((row_cells, p_idx))
                                        all_extra_rows.append({"raw_usn": r.get("raw_usn") or r.get("extracted_usn") or ""})
                            except Exception as page_e:
                                logger.debug(f"Page {p_idx} spatial OCR extraction skipped: {page_e}")
                        if canonical_hdrs and all_page_rows:
                            return self._build_extracted_result_with_pages(canonical_hdrs, all_page_rows, extra_row_data=all_extra_rows)
                except Exception as spatial_pdf_err:
                    logger.warning(f"Spatial OCR table parsing on scanned PDF failed: {spatial_pdf_err}; falling back to text OCR...")

                # 2. Text OCR fallback
                ocr_text = ocr_service.extract_text_from_scanned_pdf_bytes(file_bytes)
                if ocr_text and not ocr_text.startswith("Error:") and not ocr_text.startswith("Scanned PDF Error:"):
                    return self._parse_candidates_from_ocr_text(ocr_text, source_type="scanned_pdf")
                elif ocr_text and (ocr_text.startswith("Error:") or ocr_text.startswith("Scanned PDF Error:")):
                    raise RecruitmentResultExtractionError(f"Scanned PDF OCR failed: {ocr_text}")
            except RecruitmentResultExtractionError:
                raise
            except Exception as ocr_err:
                logger.error(f"OCR fallback on PDF failed: {ocr_err}")
                raise RecruitmentResultExtractionError(f"Scanned PDF OCR failed: {str(ocr_err)}")

            raise RecruitmentResultExtractionError(
                "Could not extract candidate records from this PDF. "
                "The PDF might contain scanned images without recognizable text or complex non-tabular layouts. "
                "Please upload a searchable text document, spreadsheet (.xlsx, .csv), or clear recruitment scan."
            )

        # Build extracted result with page tracking
        return self._build_extracted_result_with_pages(all_headers, extracted_rows)

    # =========================================================================
    # HEADER MAPPING & ROW NORMALIZATION
    # =========================================================================
    def _normalize_key(self, text: str) -> str:
        """Strip punctuation and whitespace for fuzzy synonym matching."""
        return re.sub(r"[^a-zA-Z0-9]", "", str(text).lower().strip())

    def _map_columns(self, headers: List[str]) -> Dict[str, Optional[int]]:
        """Map canonical attributes (usn, name, email, status, branch, remarks) to column indices."""
        mapping: Dict[str, Optional[int]] = {k: None for k in HEADER_SYNONYMS.keys()}

        normalized_headers = [self._normalize_key(h) for h in headers]

        for canon_field, synonyms in HEADER_SYNONYMS.items():
            norm_synonyms = [self._normalize_key(s) for s in synonyms]
            for idx, h_norm in enumerate(normalized_headers):
                if not h_norm:
                    continue
                # Exact synonym match
                if h_norm in norm_synonyms:
                    mapping[canon_field] = idx
                    break
                # Substring match if not found
                if mapping[canon_field] is None:
                    for s_norm in norm_synonyms:
                        if len(s_norm) >= 3 and (s_norm in h_norm or h_norm in s_norm):
                            mapping[canon_field] = idx
                            break

        return mapping

    def _normalize_status(self, raw_status: Optional[str]) -> str:
        """
        Conservatively normalize candidate result terms into canonical categories:
        shortlisted, selected, rejected, absent, on_hold.
        """
        if not raw_status:
            return "shortlisted"

        s = str(raw_status).strip().lower()

        # Final offer / Selected
        if any(term in s for term in [
            "final offer", "selected", "offer", "offered", "placed", "hired", "accepted"
        ]) and "not" not in s and "reject" not in s:
            return "selected"

        # Rejected / Not Selected
        if any(term in s for term in [
            "reject", "not selected", "fail", "eliminated", "unsuccessful", "dropped"
        ]):
            return "rejected"

        # Absent
        if any(term in s for term in ["absent", "not attended", "no show", "na"]):
            return "absent"

        # Shortlisted / Cleared / Next Round
        if any(term in s for term in [
            "shortlisted", "cleared", "pass", "qualified", "eligible",
            "round 1", "round 2", "round 3", "l1", "l2", "next round"
        ]):
            return "shortlisted"

        # Default fallback is shortlisted for officer review
        return "shortlisted"

    def _build_extracted_result(
        self,
        headers: List[str],
        data_rows: List[List[str]],
        source_page: int = 1,
        extra_row_data: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Convert tabular rows into structured JSON format."""
        rows_with_pages = [(row, source_page) for row in data_rows]
        return self._build_extracted_result_with_pages(headers, rows_with_pages, extra_row_data=extra_row_data)

    def _build_extracted_result_with_pages(
        self,
        headers: List[str],
        rows_with_pages: List[Tuple[List[str], int]],
        extra_row_data: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Build full structured extraction response."""
        col_map = self._map_columns(headers)

        items: List[Dict[str, Any]] = []
        for row_idx, (row_cells, page_num) in enumerate(rows_with_pages, start=1):
            extra = extra_row_data[row_idx - 1] if extra_row_data and (row_idx - 1) < len(extra_row_data) else {}

            # Pad row cells if length less than headers
            padded_cells = list(row_cells) + [""] * max(0, len(headers) - len(row_cells))

            # Raw data JSON dictionary
            raw_dict = {}
            for col_idx, h_name in enumerate(headers):
                cell_val = padded_cells[col_idx] if col_idx < len(padded_cells) else ""
                raw_dict[h_name] = cell_val

            # Extract canonical fields
            extracted_usn = padded_cells[col_map["usn"]].strip() if col_map["usn"] is not None and col_map["usn"] < len(padded_cells) else None
            extracted_name = padded_cells[col_map["name"]].strip() if col_map["name"] is not None and col_map["name"] < len(padded_cells) else None
            extracted_email = padded_cells[col_map["email"]].strip() if col_map["email"] is not None and col_map["email"] < len(padded_cells) else None
            extracted_status_raw = padded_cells[col_map["status"]].strip() if col_map["status"] is not None and col_map["status"] < len(padded_cells) else None
            extracted_branch = padded_cells[col_map["branch"]].strip() if col_map["branch"] is not None and col_map["branch"] < len(padded_cells) else None
            extracted_remarks = padded_cells[col_map["remarks"]].strip() if col_map["remarks"] is not None and col_map["remarks"] < len(padded_cells) else None

            # Skip completely empty extracted rows
            if not any([extracted_usn, extracted_name, extracted_email, extracted_status_raw]):
                # If cells contain some text, retain it using raw values
                if not any(padded_cells):
                    continue

            normalized_status = self._normalize_status(extracted_status_raw)

            raw_usn = extra.get("raw_usn") or extracted_usn or None
            if raw_usn:
                raw_dict["raw_usn"] = raw_usn

            items.append({
                "row_index": row_idx,
                "source_page": page_num,
                "raw_data": raw_dict,
                "extracted_usn": extracted_usn or None,
                "raw_usn": raw_usn,
                "extracted_name": extracted_name or None,
                "extracted_email": extracted_email or None,
                "extracted_branch": extracted_branch or None,
                "extracted_status_raw": extracted_status_raw or None,
                "extracted_remarks": extracted_remarks or None,
                "normalized_status": normalized_status,
                "usn": extracted_usn or None,
                "name": extracted_name or None,
                "email": extracted_email or None,
                "branch": extracted_branch or None,
                "status": normalized_status,
            })

        if not items:
            raise ValueError("No valid candidate rows could be parsed from the file.")

        return {
            "success": True,
            "total_rows": len(items),
            "headers": headers,
            "column_mapping": col_map,
            "rows": items,
        }


# Global singleton instance
recruitment_result_extractor = RecruitmentResultExtractor()
