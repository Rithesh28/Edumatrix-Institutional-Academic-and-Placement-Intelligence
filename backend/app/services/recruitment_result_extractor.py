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
    ]
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
    # IMAGE OCR EXTRACTION
    # =========================================================================
    def _extract_image(self, file_bytes: bytes) -> Dict[str, Any]:
        """Extract candidate rows from image files using OCR."""
        try:
            from app.services.ocr_service import ocr_service
            text = ocr_service.extract_text_from_image_bytes(file_bytes)
        except Exception as e:
            raise RecruitmentResultExtractionError(f"OCR service failed on image: {str(e)}")

        if not text or text.startswith("OCR Error:") or text.startswith("Error:"):
            raise RecruitmentResultExtractionError(f"Could not extract readable text from image: {text}")

        return self._parse_candidates_from_ocr_text(text, source_type="image")

    def _parse_candidates_from_ocr_text(
        self, text: str, source_type: str = "document", source_page: int = 1
    ) -> Dict[str, Any]:
        """
        Parse structured candidate records from OCR text output.
        Handles delimited text, aligned column text, and free-form pattern matching.
        """
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            raise RecruitmentResultExtractionError(f"{source_type.capitalize()} OCR extracted no readable text lines.")

        # Filter out generic header/banner lines like "--- Page 1 ---"
        clean_lines = [l for l in lines if not re.match(r"^---\s*Page\s*\d+\s*---$", l, re.IGNORECASE)]
        if not clean_lines:
            raise RecruitmentResultExtractionError(f"{source_type.capitalize()} OCR extracted no readable data lines.")

        # Attempt structured delimiter-based parsing (e.g. CSV-like text inside image/scan)
        for candidate_delim in [",", "\t", ";", "|"]:
            if candidate_delim in clean_lines[0] and clean_lines[0].count(candidate_delim) >= 1:
                reader = csv.reader(clean_lines, delimiter=candidate_delim)
                raw_rows = [row for row in reader if any(cell.strip() for cell in row)]
                if len(raw_rows) >= 2:
                    header_row = raw_rows[0]
                    data_rows = raw_rows[1:]
                    return self._build_extracted_result(header_row, data_rows, source_page=source_page)

        # Tabular whitespace check: if header line has 2+ columns separated by 2+ spaces
        tokens_line_0 = re.split(r"\s{2,}|\t", clean_lines[0])
        if len(tokens_line_0) >= 2 and any(k in clean_lines[0].lower() for k in ["usn", "roll", "name", "email", "status", "candidate"]):
            headers = [t.strip() for t in tokens_line_0 if t.strip()]
            data_rows = []
            for line in clean_lines[1:]:
                parts = [p.strip() for p in re.split(r"\s{2,}|\t", line) if p.strip()]
                if parts:
                    data_rows.append(parts)
            if data_rows:
                return self._build_extracted_result(headers, data_rows, source_page=source_page)

        # Free-form line pattern matching for USN / Name / Email / Status
        headers = ["USN", "Name", "Email", "Status"]
        data_rows = []
        for line in clean_lines:
            # Check email
            email_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", line)
            email = email_match.group(0) if email_match else ""

            # Check USN pattern
            usn_match = re.search(r"\b[0-9][a-zA-Z]{2}[0-9]{2}[a-zA-Z]{2}[0-9]{3}\b|\b[a-zA-Z]{2,4}[0-9]{5,10}\b", line, re.IGNORECASE)
            usn = usn_match.group(0).upper() if usn_match else ""

            # Remainder as name / status
            rem = line
            if email:
                rem = rem.replace(email, "")
            if usn:
                rem = re.sub(re.escape(usn), "", rem, flags=re.IGNORECASE)
            rem = rem.strip(" ,-|:\t")

            status = "shortlisted"
            for term in ["selected", "rejected", "shortlisted", "absent", "cleared"]:
                if re.search(r"\b" + term + r"\b", rem, re.IGNORECASE):
                    status = term
                    rem = re.sub(r"\b" + term + r"\b", "", rem, flags=re.IGNORECASE).strip(" ,-|:\t")
                    break

            name = rem
            # Filter out non-candidate lines (like pure document titles or dates)
            if usn or email or (name and len(name) >= 3 and not re.match(r"^(shortlist|announcement|candidates|page\s*\d+|date|company)", name, re.IGNORECASE)):
                data_rows.append([usn, name, email, status])

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
        mapping: Dict[str, Optional[int]] = {
            "usn": None,
            "name": None,
            "email": None,
            "status": None,
            "branch": None,
            "remarks": None,
        }

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
        self, headers: List[str], data_rows: List[List[str]], source_page: int = 1
    ) -> Dict[str, Any]:
        """Convert tabular rows into structured JSON format."""
        rows_with_pages = [(row, source_page) for row in data_rows]
        return self._build_extracted_result_with_pages(headers, rows_with_pages)

    def _build_extracted_result_with_pages(
        self, headers: List[str], rows_with_pages: List[Tuple[List[str], int]]
    ) -> Dict[str, Any]:
        """Build full structured extraction response."""
        col_map = self._map_columns(headers)

        items: List[Dict[str, Any]] = []
        for row_idx, (row_cells, page_num) in enumerate(rows_with_pages, start=1):
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

            items.append({
                "row_index": row_idx,
                "source_page": page_num,
                "raw_data": raw_dict,
                "extracted_usn": extracted_usn or None,
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
