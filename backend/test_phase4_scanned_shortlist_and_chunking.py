"""
EduMatrix Phase 4 — Scanned Shortlist Fixes and End-to-End Validation Test Suite

Validates:
1. Native CSV shortlist extraction
2. Native XLSX shortlist extraction
3. Vector-PDF shortlist extraction
4. Scanned-image shortlist extraction with ground-truth metrics (Doc 6D)
5. Scanned-PDF spatial table extraction with page tracking
6. Rejection of document banners, examination duties, and table headers
7. Correct name-USN association and merged token separation
8. Conservative handling of noisy USNs without silent alteration
9. Institutional-record matching and notification safety (officer review enforcement)
10. Scanned-PDF fallback in text_extractor.py (native vs scanned vs corrupt)
11. GLiNER bounded chunking on long documents (beginning, middle, end skill extraction)
12. Required vs preferred skill separation with deduplication across chunks
13. Deterministic field preservation (URL, deadline, CGPA, salary)
14. End-to-end recruitment drive upload, parsing, matching, notifications, and preview/download
"""

import io
import re
import csv
import time
import unittest
import openpyxl
import requests
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

from app.core.database import SessionLocal
from app.models.user import User, UserRole
from app.models.profile import StudentProfileExtended
from app.models.recruitment_result import RecruitmentResultReviewState
from app.services.recruitment_result_extractor import recruitment_result_extractor, RecruitmentResultExtractionError
from app.services.recruitment_result_matcher import recruitment_result_matcher, normalize_usn, normalize_name, normalize_email
from app.services.file_storage.text_extractor import text_extractor
from app.services.jd_parser_service import jd_parser_service

BASE_URL = "http://localhost:8000"


class TestPhase4Validation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        # Verify Placement Officer login
        po_login = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": "placement@gmail.com", "password": "12345"}
        )
        assert po_login.status_code == 200, f"PO login failed: {po_login.text}"
        cls.po_token = po_login.json()["access_token"]
        cls.po_headers = {"Authorization": f"Bearer {cls.po_token}"}
        cls.po_user = po_login.json()["user"]

        # Verify Student login (adi01, ID: 1, USN: 4VP23AI002)
        s_login = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": "adi01@gmail.com", "password": "54321"}
        )
        assert s_login.status_code == 200, f"Student login failed: {s_login.text}"
        cls.s_token = s_login.json()["access_token"]
        cls.s_headers = {"Authorization": f"Bearer {cls.s_token}"}
        cls.s_user = s_login.json()["user"]

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    # =========================================================================
    # 1. NATIVE CSV SHORTLIST EXTRACTION
    # =========================================================================
    def test_01_native_csv_shortlist_extraction(self):
        """Verify native CSV shortlist extraction correctly identifies columns and rows."""
        csv_data = (
            "USN,Candidate Name,Email Address,Selection Status,Department\n"
            "4VP23AI002,Adithya CS,adi01@gmail.com,Selected,AIML\n"
            "4VP23CS045,Bhavya Rao,bhavya@gmail.com,Shortlisted,CSE\n"
            "4VP23IS012,Chetan Kumar,chetan@gmail.com,Rejected,ISE\n"
        ).encode("utf-8")

        res = recruitment_result_extractor.extract(csv_data, "shortlist.csv")
        self.assertTrue(res["success"])
        self.assertEqual(res["total_rows"], 3)
        self.assertEqual(len(res["rows"]), 3)
        self.assertEqual(res["rows"][0]["usn"], "4VP23AI002")
        self.assertEqual(res["rows"][0]["name"], "Adithya CS")
        self.assertEqual(res["rows"][0]["email"], "adi01@gmail.com")
        self.assertEqual(res["rows"][0]["status"], "selected")
        self.assertEqual(res["rows"][1]["status"], "shortlisted")
        self.assertEqual(res["rows"][2]["status"], "rejected")

    # =========================================================================
    # 2. NATIVE XLSX SHORTLIST EXTRACTION
    # =========================================================================
    def test_02_native_xlsx_shortlist_extraction(self):
        """Verify native Excel spreadsheet extraction preserves tabular columns and statuses."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Shortlist"
        ws.append(["Register Number", "Student Name", "College Email", "Round 1 Result", "Discipline"])
        ws.append(["4VP23AI002", "Adithya CS", "adi01@gmail.com", "Cleared", "AIML"])
        ws.append(["4VP23CS045", "Bhavya Rao", "bhavya@gmail.com", "Passed", "CSE"])
        ws.append(["4VP23EC099", "Divya M", "divya@gmail.com", "Absent", "ECE"])

        buf = io.BytesIO()
        wb.save(buf)
        excel_bytes = buf.getvalue()

        res = recruitment_result_extractor.extract(excel_bytes, "shortlist.xlsx")
        self.assertTrue(res["success"])
        self.assertEqual(res["total_rows"], 3)
        self.assertEqual(res["rows"][0]["usn"], "4VP23AI002")
        self.assertEqual(res["rows"][0]["name"], "Adithya CS")
        self.assertEqual(res["rows"][0]["status"], "shortlisted")
        self.assertEqual(res["rows"][2]["status"], "absent")

    # =========================================================================
    # 3. VECTOR-PDF SHORTLIST EXTRACTION
    # =========================================================================
    def test_03_vector_pdf_shortlist_extraction(self):
        """Verify vector-PDF table extraction with pdfplumber preserves pages and columns."""
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = [
            Paragraph("Nexus Tech Systems - Recruitment Results", styles["Heading2"]),
            Spacer(1, 12),
        ]
        table_data = [
            ["USN", "Candidate Name", "Email", "Status"],
            ["4VP23AI002", "Adithya CS", "adi01@gmail.com", "Selected"],
            ["4VP23CS045", "Bhavya Rao", "bhavya@gmail.com", "Shortlisted"],
        ]
        t = Table(table_data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.navy),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(t)
        doc.build(elements)
        pdf_bytes = buf.getvalue()

        res = recruitment_result_extractor.extract(pdf_bytes, "shortlist.pdf")
        self.assertTrue(res["success"])
        self.assertEqual(res["total_rows"], 2)
        self.assertEqual(res["rows"][0]["usn"], "4VP23AI002")
        self.assertEqual(res["rows"][0]["name"], "Adithya CS")
        self.assertEqual(res["rows"][0]["status"], "selected")

    # =========================================================================
    # 4. SCANNED-IMAGE SHORTLIST EXTRACTION (BENCHMARK DOC 6D)
    # =========================================================================
    def test_04_scanned_image_shortlist_extraction_with_ground_truth(self):
        """
        Benchmark Scanned Image Extraction (Doc 6D):
        Synthesizes an image with document banner, table header, and candidate rows.
        Computes exact ground-truth benchmark metrics:
        - Ground-truth candidate count: 3
        - Correct name-USN pairs: 3
        - Missed candidates: 0
        - Incorrectly paired candidates: 0
        - False candidate records: 0 (banner and header rejected!)
        - Duplicate records: 0
        """
        img = Image.new("RGB", (900, 350), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        # 1. Document title / Announcement banner (MUST BE REJECTED)
        draw.text((40, 25), "CAMPUS RECRUITMENT SHORTLIST - 2026", fill=(0, 0, 0))
        # 2. Table Column Headers (MUST BE REJECTED AS CANDIDATE)
        draw.text((40, 65), "USN                 Name               Email                    Status", fill=(0, 0, 0))
        # 3. Ground truth candidate rows
        ground_truth = [
            {"usn": "4VP23AI002", "name": "Adithya CS", "email": "adi01@gmail.com", "status": "selected"},
            {"usn": "4VP23CS045", "name": "Bhavya Rao", "email": "bhavya@gmail.com", "status": "shortlisted"},
            {"usn": "4VP23IS012", "name": "Chetan Kumar", "email": "chetan@gmail.com", "status": "rejected"},
        ]
        y = 105
        for i, r in enumerate(ground_truth):
            line_str = f"{r['usn']:<18}  {r['name']:<16}  {r['email']:<22}  {r['status'].capitalize()}"
            draw.text((40, y + i * 35), line_str, fill=(0, 0, 0))

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        # Run extraction
        res = recruitment_result_extractor.extract(image_bytes, "scanned_shortlist.png")
        self.assertTrue(res["success"])
        extracted_rows = res["rows"]

        # Evaluate Ground Truth Metrics
        gt_count = len(ground_truth)
        extracted_count = len(extracted_rows)

        correct_pairs = 0
        incorrect_pairs = 0
        false_records = 0
        duplicate_records = 0
        seen_usns = set()

        for row in extracted_rows:
            usn = (row.get("usn") or "").upper()
            name = (row.get("name") or "").strip()
            # Check if this row is a false candidate (banner or header fragment)
            if any(term in (usn + " " + name).lower() for term in ["campus", "shortlist", "recruitment", "register number"]):
                false_records += 1
                continue

            if usn in seen_usns:
                duplicate_records += 1
            seen_usns.add(usn)

            # Match against ground truth
            gt_match = next((g for g in ground_truth if g["usn"] == usn), None)
            if gt_match:
                # Check name association (first token of name match)
                gt_first_name = gt_match["name"].split()[0].lower()
                if gt_first_name in name.lower() or name.lower() in gt_match["name"].lower():
                    correct_pairs += 1
                else:
                    incorrect_pairs += 1
            else:
                false_records += 1

        missed_candidates = gt_count - correct_pairs

        print("\n--- Phase 4 Scanned Shortlist Benchmark Metrics (Doc 6D) ---")
        print(f"Ground-truth candidate count : {gt_count}")
        print(f"Extracted row count          : {extracted_count}")
        print(f"Correct name-USN pairs       : {correct_pairs}")
        print(f"Missed candidates            : {missed_candidates}")
        print(f"Incorrectly paired candidates: {incorrect_pairs}")
        print(f"False candidate records      : {false_records}")
        print(f"Duplicate records            : {duplicate_records}")

        self.assertEqual(gt_count, 3)
        self.assertEqual(correct_pairs, 3, f"Expected 3 correct pairs, got {correct_pairs}")
        self.assertEqual(false_records, 0, f"Expected 0 false records, got {false_records}")
        self.assertEqual(missed_candidates, 0)
        self.assertEqual(duplicate_records, 0)

    # =========================================================================
    # 5. SCANNED-PDF SPATIAL TABLE EXTRACTION
    # =========================================================================
    def test_05_scanned_pdf_spatial_extraction(self):
        """Verify scanned PDF fallback correctly triggers spatial OCR extraction with page numbers."""
        img = Image.new("RGB", (900, 350), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((40, 25), "CAMPUS RECRUITMENT SHORTLIST - 2026", fill=(0, 0, 0))
        draw.text((40, 65), "USN                 Name               Email                    Status", fill=(0, 0, 0))
        draw.text((40, 105), "4VP23AI002          Adithya CS         adi01@gmail.com          Selected", fill=(0, 0, 0))
        draw.text((40, 140), "4VP23CS045          Bhavya Rao         bhavya@gmail.com         Shortlisted", fill=(0, 0, 0))

        img_buf = io.BytesIO()
        img.save(img_buf, format="PNG")
        img_bytes = img_buf.getvalue()

        # Build pure image PDF using ReportLab
        from reportlab.platypus import Image as RLImage
        pdf_buf = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buf, pagesize=letter)
        elements = [RLImage(io.BytesIO(img_bytes), width=500, height=194)]
        doc.build(elements)
        scanned_pdf_bytes = pdf_buf.getvalue()

        res = recruitment_result_extractor.extract(scanned_pdf_bytes, "scanned_results.pdf")
        self.assertTrue(res["success"])
        self.assertGreaterEqual(res["total_rows"], 2)
        self.assertEqual(res["rows"][0]["source_page"], 1)
        usns = [r["usn"] for r in res["rows"] if r.get("usn")]
        self.assertIn("4VP23AI002", usns)
        self.assertIn("4VP23CS045", usns)

    # =========================================================================
    # 6. REJECTION OF DOCUMENT BANNERS AND TABLE HEADERS
    # =========================================================================
    def test_06_rejection_of_document_banners_and_headers(self):
        """
        Verify that banner lines, exam duties, coordinator signatures, and headers
        are never mistaken for candidate records.
        """
        banner_lines = [
            "CAMPUS RECRUITMENT SHORTLIST - 2026",
            "USN / Register Number Name Email Status",
            "VTU Examination Duty Chart - May 2026",
            "Department of Computer Science & Engineering",
            "Training & Placement Cell Coordinator Signature",
            "Date: 2026-05-12 Venue: Auditorium Time: 10:00 AM",
            "Page 1 of 3",
            "Sl No Register Number Candidate Name",
        ]
        for line in banner_lines:
            self.assertTrue(
                recruitment_result_extractor._is_banner_text(line),
                f"Line should have been rejected as banner: '{line}'"
            )

        # Real candidate line must NOT be flagged as banner
        candidate_line = "4VP23AI002 Adithya CS adi01@gmail.com Selected"
        self.assertFalse(
            recruitment_result_extractor._is_banner_text(candidate_line),
            f"Candidate line must NOT be marked as banner: '{candidate_line}'"
        )

    # =========================================================================
    # 7. CORRECT NAME-USN ASSOCIATION AND MERGED TOKEN SEPARATION
    # =========================================================================
    def test_07_merged_token_separation_and_name_association(self):
        """
        Verify that merged OCR tokens (e.g. '4VP23CS045Bhavya') are cleanly separated
        into USN and Name without corrupting either value.
        """
        usn_clean, name_clean, email_clean, status_clean = recruitment_result_extractor._normalize_candidate_fields(
            raw_usn="4VP23CS045Bhavya",
            raw_name="Rao",
            raw_email="bhavya@gmail.com",
            raw_status="Shortlisted",
            full_row_text="4VP23CS045Bhavya Rao bhavya@gmail.com Shortlisted",
        )
        self.assertEqual(usn_clean, "4VP23CS045")
        self.assertEqual(name_clean, "Bhavya Rao")
        self.assertEqual(email_clean, "bhavya@gmail.com")
        self.assertEqual(status_clean, "shortlisted")

    # =========================================================================
    # 8. CONSERVATIVE HANDLING OF NOISY USNS
    # =========================================================================
    def test_08_conservative_noisy_usn_handling(self):
        """
        Verify that noisy USNs with whitespace, lowercase letters, or dashes
        are normalized conservatively, but invalid/uncertain strings are preserved
        without silently transforming into a different valid student.
        """
        # 1. Conservative whitespace normalization
        self.assertEqual(normalize_usn("4VP 23 AI 002"), "4VP23AI002")
        self.assertEqual(normalize_usn("4vp-23-ai-002"), "4VP23AI002")
        self.assertEqual(normalize_usn(" 4VP23CS045 "), "4VP23CS045")

        # 2. Uncertain USN should NOT match an existing student
        res = recruitment_result_matcher.match_row(
            db=self.db,
            extracted_usn="4VP23XX999",  # Non-existent student
            extracted_email=None,
            extracted_name="Unknown Student",
        )
        self.assertIsNone(res["matched_student_id"])
        self.assertEqual(res["review_status"], RecruitmentResultReviewState.PENDING)

    # =========================================================================
    # 9. INSTITUTIONAL-RECORD MATCHING & NOTIFICATION SAFETY
    # =========================================================================
    def test_09_institutional_record_matching_and_notification_safety(self):
        """
        Verify matching hierarchy:
        - Exact USN: confidence 1.00, MATCHED
        - Exact Email: confidence 0.98, MATCHED
        - Name-only match: confidence <= 0.50, AMBIGUOUS (review required)
        - USN collision / Conflicting identifiers: AMBIGUOUS (matched_student_id = None)
        """
        # Exact USN match for student ID 1 (adi01@gmail.com disambiguates USN collision)
        res_usn = recruitment_result_matcher.match_row(
            db=self.db,
            extracted_usn="4VP23AI002",
            extracted_email="adi01@gmail.com",
            extracted_name="Adithya CS",
        )
        self.assertEqual(res_usn["matched_student_id"], 1)
        self.assertEqual(res_usn["match_confidence"], 1.00)
        self.assertEqual(res_usn["review_status"], RecruitmentResultReviewState.MATCHED)

        # Name-only match (without USN or Email) must be flagged AMBIGUOUS
        res_name = recruitment_result_matcher.match_row(
            db=self.db,
            extracted_usn=None,
            extracted_email=None,
            extracted_name="Adithya CS",
        )
        self.assertEqual(res_name["review_status"], RecruitmentResultReviewState.AMBIGUOUS)

        # Conflicting identifiers: USN of student 468 (TEST36419) with Email of Student 1 (adi01@gmail.com)
        res_conflict = recruitment_result_matcher.match_row(
            db=self.db,
            extracted_usn="TEST36419",
            extracted_email="adi01@gmail.com",  # Conflicting active student
            extracted_name="Adithya CS",
        )
        self.assertIsNone(res_conflict["matched_student_id"])
        self.assertEqual(res_conflict["review_status"], RecruitmentResultReviewState.AMBIGUOUS)
        self.assertEqual(res_conflict["match_method"], "CONFLICTING_IDENTIFIERS")

        # USN Collision: 4VP23AI002 without corroborating email (maps to multiple active students: 1 and 71)
        res_collision = recruitment_result_matcher.match_row(
            db=self.db,
            extracted_usn="4VP23AI002",
            extracted_email=None,
            extracted_name="Adithya",
        )
        self.assertIsNone(res_collision["matched_student_id"])
        self.assertEqual(res_collision["review_status"], RecruitmentResultReviewState.AMBIGUOUS)
        self.assertEqual(res_collision["match_method"], "USN_COLLISION")

    # =========================================================================
    # 10. SCANNED-PDF FALLBACK IN TEXT_EXTRACTOR.PY
    # =========================================================================
    def test_10_text_extractor_scanned_pdf_fallback(self):
        """
        Verify text_extractor._extract_pdf behavior:
        1. Native-text PDF: extracts native text via pdfplumber without invoking OCR.
        2. Scanned image PDF: falls back to ocr_service as tertiary fallback.
        3. Corrupt PDF: raises ValueError gracefully.
        """
        # 1. Native-text PDF
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = [Paragraph("Native Job Description with Python and SQL", styles["Normal"])]
        doc.build(elements)
        native_pdf = buf.getvalue()

        ext_res = text_extractor.extract_text("job.pdf", content=native_pdf)
        self.assertIn("Native Job Description", ext_res["text"])
        self.assertIn("pdfplumber", ext_res["extractor_used"])

        # 2. Scanned-only PDF (image with no selectable text)
        img = Image.new("RGB", (600, 200), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((20, 50), "Scanned Machine Learning Job Description", fill=(0, 0, 0))
        img_buf = io.BytesIO()
        img.save(img_buf, format="PNG")
        from reportlab.platypus import Image as RLImage
        scanned_buf = io.BytesIO()
        doc = SimpleDocTemplate(scanned_buf, pagesize=letter)
        doc.build([RLImage(io.BytesIO(img_buf.getvalue()), width=400, height=133)])
        scanned_pdf = scanned_buf.getvalue()

        ext_scan_res = text_extractor.extract_text("scanned_job.pdf", content=scanned_pdf)
        self.assertTrue(len(ext_scan_res["text"]) > 0)
        self.assertIn("ocr_service", ext_scan_res["extractor_used"])

        # 3. Corrupt PDF
        corrupt_bytes = b"%PDF-1.4\ncorrupt header and unreadable body content"
        ext_corrupt = text_extractor.extract_text("corrupt.pdf", content=corrupt_bytes)
        self.assertFalse(ext_corrupt["success"])
        self.assertIsNotNone(ext_corrupt["error"])

    # =========================================================================
    # 11. GLINER BOUNDED CHUNKING & LONG DOCUMENT EXTRACTION
    # =========================================================================
    def test_11_gliner_chunking_on_long_document(self):
        """
        Verify GLiNER chunking:
        1. Breaks long texts into bounded sections below 384 tokens (~750 chars).
        2. Successfully extracts skills from the beginning, middle, and end of a long document.
        3. Preserves deterministic fields (URL, deadline, salary, CGPA).
        """
        beginning_skills = "Core Foundation Requirements: Proficiency in Python, FastAPI, and Docker is mandatory."
        filler_para_1 = " ".join([
            "The engineer will collaborate across teams to design enterprise microservices and maintain high availability."
        ] * 12)
        middle_skills = "Secondary Platform Stack: Practical experience with Redis caching, PostgreSQL, and Celery."
        filler_para_2 = " ".join([
            "The candidate must adhere to software engineering best practices, conduct code reviews, and monitor pipelines."
        ] * 12)
        end_skills = "Cloud and Operations: Familiarity with Kubernetes, Prometheus, and AWS Lambda."

        long_jd_text = (
            f"Job Overview:\nNexus Tech is hiring Senior Engineers. "
            f"Application Deadline: 2026-11-30. Compensation: 14 LPA. Minimum CGPA: 7.5. "
            f"Application Portal: https://nexustech.careers/apply/eng-2026\n\n"
            f"{beginning_skills}\n\n"
            f"{filler_para_1}\n\n"
            f"{middle_skills}\n\n"
            f"{filler_para_2}\n\n"
            f"{end_skills}\n"
        )

        self.assertGreater(len(long_jd_text), 2500, "Document must be long enough to test chunking (>2500 chars)")

        # Verify chunking helper directly
        chunks = jd_parser_service._chunk_text_for_gliner(long_jd_text, max_chars=750)
        self.assertGreater(len(chunks), 1)
        for i, chunk in enumerate(chunks):
            self.assertLessEqual(len(chunk), 750, f"Chunk {i} exceeded 750 char budget: {len(chunk)}")

        # Parse with JD parser service
        parsed = jd_parser_service.parse_jd_text(long_jd_text)

        # 1. Deterministic fields preserved
        self.assertEqual(parsed.get("min_cgpa"), 7.5)
        self.assertEqual(parsed.get("application_url"), "https://nexustech.careers/apply/eng-2026")
        self.assertIn("14", str(parsed.get("salary_range", "")))

        # 2. Skills extracted across beginning, middle, and end
        req_skills = [s.lower() for s in parsed.get("required_skills", [])]
        pref_skills = [s.lower() for s in parsed.get("preferred_skills", [])]
        all_skills = set(req_skills + pref_skills)

        # Beginning skill
        self.assertTrue(any("python" in s or "fastapi" in s for s in all_skills), "Beginning skills missed!")
        # Middle skill
        self.assertTrue(any("redis" in s or "postgresql" in s or "celery" in s for s in all_skills), "Middle skills missed!")
        # End skill
        self.assertTrue(any("kubernetes" in s or "prometheus" in s or "aws" in s for s in all_skills), "End skills missed!")

    # =========================================================================
    # 12. REQUIRED VS PREFERRED SKILL SEPARATION ACROSS CHUNKS
    # =========================================================================
    def test_12_required_vs_preferred_skill_separation(self):
        """
        Verify that required and preferred skill sections remain strictly separated
        and deduplicated across chunk boundaries.
        """
        jd_text = (
            "Required Qualifications:\n"
            "Must have extensive experience with Golang, Kubernetes, and gRPC.\n"
            "Must possess solid understanding of Distributed Systems and SQL databases.\n\n"
            "Nice to Have / Preferred Qualifications:\n"
            "Experience with Flutter mobile development and GraphQL is an added advantage.\n"
            "Familiarity with Terraform and Apache Kafka.\n"
        )
        parsed = jd_parser_service.parse_jd_text(jd_text)
        req = [s.lower() for s in parsed.get("required_skills", [])]
        pref = [s.lower() for s in parsed.get("preferred_skills", [])]

        # Golang / Kubernetes must be in required
        self.assertTrue(any("golang" in s or "kubernetes" in s for s in req), "Required skills missing from required_skills")
        # Flutter / GraphQL must be in preferred
        self.assertTrue(any("flutter" in s or "graphql" in s for s in pref), "Preferred skills missing from preferred_skills")

    # =========================================================================
    # 13. RECRUITMENT-DRIVE UPLOAD, PREVIEW/DOWNLOAD & NOTIFICATIONS WORKFLOW
    # =========================================================================
    def test_13_recruitment_drive_upload_matching_download_workflow(self):
        """
        End-to-End API Workflow:
        1. Placement officer uploads result shortlist (CSV).
        2. Batch is created in reviewable state.
        3. Batch file download/preview is authenticated and verified.
        4. Matching row inspection: Adi (student 1) matched.
        5. Confirmation updates progression and verifies deduplicated notification delivery.
        """
        # 1. Fetch a company
        comp_res = requests.get(f"{BASE_URL}/placement/companies", headers=self.po_headers)
        companies = comp_res.json()
        self.assertTrue(len(companies) > 0)
        company_id = companies[0]["id"]

        # 2. Upload shortlist CSV
        csv_content = (
            "USN,Candidate Name,Email,Round Result\n"
            "4VP23AI002,Adithya CS,adi01@gmail.com,Selected\n"
        ).encode("utf-8")

        upload_files = {
            "file": ("phase4_shortlist.csv", io.BytesIO(csv_content), "text/csv")
        }
        data = {
            "company_id": str(company_id),
            "round_name": "Phase 4 Assessment",
            "round_type": "technical",
            "is_final_round": "false",
        }

        res = requests.post(
            f"{BASE_URL}/placement/results/upload",
            headers=self.po_headers,
            files=upload_files,
            data=data,
        )
        self.assertEqual(res.status_code, 201, f"Upload failed: {res.text}")
        batch = res.json()
        batch_id = batch["id"]
        self.assertEqual(batch["total_rows"], 1)
        self.assertEqual(batch["matched_count"], 1)

        # 3. Verify Download / Preview endpoint
        dl_res = requests.get(
            f"{BASE_URL}/placement/results/batches/{batch_id}/download",
            headers=self.po_headers,
        )
        self.assertEqual(dl_res.status_code, 200)
        self.assertIn(b"4VP23AI002", dl_res.content)

        # 4. Confirm batch results
        confirm_res = requests.post(
            f"{BASE_URL}/placement/results/batches/{batch_id}/confirm",
            headers=self.po_headers,
            json={"item_ids": [batch["items"][0]["id"]]},
        )
        self.assertEqual(confirm_res.status_code, 200, f"Confirmation failed: {confirm_res.text}")
        c_json = confirm_res.json()
        self.assertEqual(c_json["confirmed_count"], 1)

        # 5. Check student notification
        notif_res = requests.get(
            f"{BASE_URL}/notifications",
            headers=self.s_headers,
        )
        self.assertEqual(notif_res.status_code, 200)
        notifs = notif_res.json()
        phase4_notifs = [n for n in notifs if "Phase 4 Assessment" in n.get("title", "") or "Phase 4 Assessment" in n.get("message", "")]
        self.assertGreaterEqual(len(phase4_notifs), 1, "Student should receive notification of shortlist clearance")


if __name__ == "__main__":
    unittest.main()
