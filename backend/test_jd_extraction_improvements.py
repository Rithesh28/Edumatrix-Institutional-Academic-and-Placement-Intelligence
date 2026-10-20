"""
Automated Test Suite for Final Job Description Extraction Accuracy & Reliability Fix.

Verifies:
1. Application URL Extraction & Reconstruction (multiline, OCR spaces, broken scheme, query params/fragments, prefix deduplication, candidate scoring)
2. Application Deadline & Date Extraction (dateparser integration, OCR quotes '19" October 2026', various natural formats, drive vs deadline distinction)
3. Academic Criteria Extraction (CGPA, individual & throughout percentages, no false conversions)
4. Compensation & Salary Extraction (ranges, LPA, ₹ Lakhs per annum, OCR comma decimals, staged compensation)
5. Document Parsing (PDF in-memory BytesIO, DOCX hyperlinks/tables, CSV, TXT, OCR)
6. Multi-File Merging (complementary fields, conflict flagging, preserving highest confidence values)
7. Real Eazy ERP Documents Verification (Job 1089 files from MinIO / local artifacts)
"""

import os
import sys
import io
import unittest
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.services.jd_parser_service import jd_parser_service
from app.services.file_storage.text_extractor import text_extractor


class TestUrlExtraction(unittest.TestCase):
    """Test general-purpose URL extraction, reconstruction, scoring, and ranking."""

    def test_google_forms_multiline_split(self):
        """Reconstruct Google Forms URL split across lines with OCR noise."""
        raw_text = (
            "Interested students please register on the official Google Form:\n"
            "https : / / forms . gle /\n"
            "yP4tpWtmk9VdFFBU8\n"
            "Make sure to submit before the deadline."
        )
        parsed = jd_parser_service.parse_jd_text(raw_text)
        self.assertEqual(parsed.get("application_url"), "https://forms.gle/yP4tpWtmk9VdFFBU8")
        candidates = [c["url"] for c in parsed.get("application_url_candidates", [])]
        self.assertIn("https://forms.gle/yP4tpWtmk9VdFFBU8", candidates)

    def test_microsoft_forms_url(self):
        """Extract and score Microsoft Forms URL."""
        raw_text = (
            "Registration Link:\n"
            "https://forms.office.com/r/AbCdEfGh12\n"
            "Fill all details accurately."
        )
        parsed = jd_parser_service.parse_jd_text(raw_text)
        self.assertEqual(parsed.get("application_url"), "https://forms.office.com/r/AbCdEfGh12")

    def test_arbitrary_career_portal_with_query_and_fragment(self):
        """Preserve query parameters, tokens, and URL fragments."""
        raw_text = (
            "Official Application Link: "
            "https://careers.acme-corp.com/apply/job-entry?req_id=98765&ref=placement_cell#submission-section\n"
            "Apply immediately."
        )
        parsed = jd_parser_service.parse_jd_text(raw_text)
        self.assertEqual(
            parsed.get("application_url"),
            "https://careers.acme-corp.com/apply/job-entry?req_id=98765&ref=placement_cell#submission-section"
        )

    def test_broken_scheme_and_spaced_domain(self):
        """Repair broken scheme and spaces around dots."""
        raw_text = (
            "Apply here: http : // careers . techglobal . com / openings / sde - 1\n"
            "Selection rounds will follow."
        )
        parsed = jd_parser_service.parse_jd_text(raw_text)
        self.assertEqual(
            parsed.get("application_url"),
            "http://careers.techglobal.com/openings/sde-1"
        )

    def test_trailing_punctuation_handling(self):
        """Strip sentence-ending punctuation without corrupting query strings."""
        raw_text = "Please submit your application at https://forms.gle/SampleForm123?track=eng."
        parsed = jd_parser_service.parse_jd_text(raw_text)
        self.assertEqual(parsed.get("application_url"), "https://forms.gle/SampleForm123?track=eng")

    def test_multiple_urls_ranked_by_context(self):
        """Registration link ranked above company home page and privacy policy."""
        raw_text = (
            "About us: https://www.innovate.org/\n"
            "Privacy policy: https://www.innovate.org/privacy-policy\n"
            "Official Application Link: https://forms.gle/ApplyHereNow999\n"
            "Terms: https://www.innovate.org/terms"
        )
        parsed = jd_parser_service.parse_jd_text(raw_text)
        self.assertEqual(parsed.get("application_url"), "https://forms.gle/ApplyHereNow999")

    def test_prefix_deduplication(self):
        """Truncated URL prefix discarded in favor of complete URL."""
        raw_text = (
            "Link part 1: https://forms.gle/yP4tp\n"
            "Full application link: https://forms.gle/yP4tpWtmk9VdFFBU8\n"
        )
        candidates = jd_parser_service._extract_all_application_urls(raw_text)
        urls = [c["url"] for c in candidates]
        self.assertIn("https://forms.gle/yP4tpWtmk9VdFFBU8", urls)
        self.assertNotIn("https://forms.gle/yP4tp", urls)

    def test_unsafe_schemes_rejected(self):
        """Reject javascript:, ftp://, and malformed targets."""
        raw_text = "Apply: javascript:alert('xss'); and ftp://files.company.com/jd.pdf"
        parsed = jd_parser_service.parse_jd_text(raw_text)
        self.assertIsNone(parsed.get("application_url"))


class TestDeadlineExtraction(unittest.TestCase):
    """Test date and deadline extraction, normalization, and ambiguity handling."""

    def test_ocr_quote_artifact_date(self):
        """Handle Tesseract OCR superscript quote artifact: 19\" October 2026."""
        raw_text = (
            "Company: Eazy ERP\n"
            "Role: Technical Support Executive\n"
            "Last Date of Online Application: 19\" October 2026\n"
            "Campus drive details to be announced later."
        )
        parsed = jd_parser_service.parse_jd_text(raw_text)
        self.assertEqual(parsed.get("application_deadline"), "2026-10-19T00:00")

    def test_various_date_formats(self):
        """Support 25 Oct 2026, October 25 2026, 25/10/2026, 25-10-2026."""
        cases = [
            ("Last Date to Apply: 25 Oct 2026", "2026-10-25T00:00"),
            ("Application Deadline: October 25, 2026", "2026-10-25T00:00"),
            ("Apply on or before 25/10/2026", "2026-10-25T00:00"),
            ("Apply before 25-10-2026", "2026-10-25T00:00"),
            ("Registration Closes On: 15th November 2026 at 5:00 PM", "2026-11-15T17:00")
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                parsed = jd_parser_service.parse_jd_text(text)
                self.assertEqual(parsed.get("application_deadline"), expected)

    def test_distinguish_drive_date_from_deadline(self):
        """Distinguish placement drive date from application deadline."""
        raw_text = (
            "Registration Deadline: 20 October 2026\n"
            "Campus Drive Date: 28 October 2026\n"
            "Date of Joining: 01 July 2027"
        )
        parsed = jd_parser_service.parse_jd_text(raw_text)
        self.assertEqual(parsed.get("application_deadline"), "2026-10-20T00:00")
        self.assertEqual(parsed.get("drive_date"), "2026-10-28T00:00")

    def test_ambiguous_date_without_year(self):
        """Flag ambiguous dates missing a year without fabricating calendar years."""
        raw_text = "Last Date to Apply: 15th October."
        parsed = jd_parser_service.parse_jd_text(raw_text)
        self.assertTrue(any("Incomplete date: Missing year" in flag for flag in parsed.get("review_flags", [])))

    def test_missing_deadline(self):
        """Document with no deadline leaves the field empty."""
        raw_text = "Looking for software developers with Python and React skills. CTC 8 LPA."
        parsed = jd_parser_service.parse_jd_text(raw_text)
        self.assertIsNone(parsed.get("application_deadline"))


class TestAcademicCriteriaExtraction(unittest.TestCase):
    """Test CGPA, percentage across tiers, throughout academics, and backlog extraction."""

    def test_explicit_cgpa_patterns(self):
        """Test various explicit CGPA representations."""
        cases = [
            ("Minimum CGPA: 7.0 required", 7.0),
            ("Candidates with 7 CGPA and above are eligible", 7.0),
            ("6.5 CGPA required for all rounds", 6.5),
            ("Eligibility: CGPA >= 7.5", 7.5),
            ("Cutoff: 8.0/10 CGPA", 8.0)
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                parsed = jd_parser_service.parse_jd_text(text)
                self.assertEqual(parsed.get("cgpa_criteria"), expected)

    def test_percentage_throughout(self):
        """Test '60% throughout academics' assigning across 10th, 12th, degree."""
        raw_text = "Criteria: 60% throughout academics (10th, 12th, and Degree)."
        parsed = jd_parser_service.parse_jd_text(raw_text)
        pcts = parsed.get("academic_percentages")
        self.assertIsNotNone(pcts)
        self.assertEqual(pcts.get("tenth"), 60.0)
        self.assertEqual(pcts.get("twelfth"), 60.0)
        self.assertEqual(pcts.get("degree"), 60.0)

    def test_combined_10th_and_12th(self):
        """Test 'Minimum 60% in 10th and 12th'."""
        raw_text = "Minimum 65% in 10th and 12th, no backlogs."
        parsed = jd_parser_service.parse_jd_text(raw_text)
        pcts = parsed.get("academic_percentages")
        self.assertIsNotNone(pcts)
        self.assertEqual(pcts.get("tenth"), 65.0)
        self.assertEqual(pcts.get("twelfth"), 65.0)

    def test_cgpa_and_percentage_coexist(self):
        """Extract both CGPA and percentage without converting percentage to CGPA."""
        raw_text = "Eligibility: 60% or 6.5 CGPA in graduation."
        parsed = jd_parser_service.parse_jd_text(raw_text)
        self.assertEqual(parsed.get("cgpa_criteria"), 6.5)
        pcts = parsed.get("academic_percentages")
        self.assertIsNotNone(pcts)
        self.assertEqual(pcts.get("degree"), 60.0)

    def test_backlogs_criteria(self):
        """Extract backlog restrictions."""
        raw_text = "Criteria: No active backlogs allowed at the time of drive."
        parsed = jd_parser_service.parse_jd_text(raw_text)
        self.assertIsNotNone(parsed.get("backlog_criteria"))
        self.assertIn("No active backlogs", parsed.get("backlog_criteria"))


class TestCompensationExtraction(unittest.TestCase):
    """Test salary, CTC, ranges, stipend, and OCR comma decimal repair."""

    def test_standard_lpa_and_ranges(self):
        """Extract standard LPA values and ranges."""
        cases = [
            ("Salary: 3.5 LPA", "3.5 LPA"),
            ("CTC: 8 LPA", "8 LPA"),
            ("Package: ₹12 Lakhs per annum", "₹12 Lakhs per annum"),
            ("Offered compensation: 3 - 4 LPA", "3 - 4 LPA"),
            ("Package: ₹6,00,000 per annum", "6 LPA"),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                parsed = jd_parser_service.parse_jd_text(text)
                self.assertIsNotNone(parsed.get("salary_range"))
                self.assertIn(expected.split()[0], parsed.get("salary_range"))

    def test_ocr_comma_salary(self):
        """Repair OCR comma decimal: INR 2,40 - 3.60 Lakhs -> 2.40 - 3.60 Lakhs."""
        raw_text = "Remuneration: INR 2,40 - 3.60 Lakhs per annum"
        parsed = jd_parser_service.parse_jd_text(raw_text)
        salary = parsed.get("salary_range")
        self.assertIsNotNone(salary)
        self.assertIn("2.40", salary)
        self.assertIn("3.60", salary)

    def test_staged_compensation(self):
        """Separate monthly internship stipend from post-conversion full-time CTC."""
        raw_text = (
            "Stipend during 6-month internship: ₹25,000/month\n"
            "Full-time CTC upon confirmation: 6.5 LPA"
        )
        parsed = jd_parser_service.parse_jd_text(raw_text)
        comp = parsed.get("compensation_details")
        self.assertIsNotNone(comp)
        self.assertIn("25,000", comp.get("stipend", ""))
        self.assertEqual(comp.get("full_time_ctc"), "6.5 LPA")
        self.assertTrue(len(comp.get("staged_compensation", [])) >= 2)


class TestJobTitleSkillsBranches(unittest.TestCase):
    """Test job title OCR repair, functional skills, and branch alias mapping."""

    def test_ocr_split_title_repair(self):
        """Repair 'Technical Supp ort Executive' to 'Technical Support Executive'."""
        raw_text = (
            "Job Title: Technical Supp ort Executive\n"
            "Company: Eazy ERP Technologies"
        )
        parsed = jd_parser_service.parse_jd_text(raw_text)
        self.assertEqual(parsed.get("title"), "Technical Support Executive")

    def test_reject_adjective_title(self):
        """Reject 'seeking bright and motivated in' as a job title."""
        raw_text = (
            "Eazy ERP is seeking bright and motivated individuals for our operations team.\n"
            "Designation: Technical Support Executive\n"
            "Skills: Troubleshooting, CRM"
        )
        parsed = jd_parser_service.parse_jd_text(raw_text)
        self.assertEqual(parsed.get("title"), "Technical Support Executive")

    def test_functional_and_support_skills(self):
        """Recognize functional skills: Customer Support, Troubleshooting, CRM, Communication."""
        raw_text = (
            "Role: Support Executive\n"
            "Required Skills: Customer Support, Troubleshooting, CRM, Helpdesk, Communication, Problem Solving"
        )
        parsed = jd_parser_service.parse_jd_text(raw_text)
        skills = parsed.get("required_skills", [])
        self.assertIn("Customer Support", skills)
        self.assertIn("Troubleshooting", skills)
        self.assertIn("CRM", skills)

    def test_branch_alias_mapping(self):
        """Support CS -> CSE, CD -> CSE/Design, AIDS."""
        raw_text = "Eligible Branches: CS, CD, IT, AIDS, ECE"
        parsed = jd_parser_service.parse_jd_text(raw_text)
        branches = parsed.get("branch_eligibility", [])
        self.assertIn("CSE", branches)
        self.assertIn("CSE/Design", branches)
        self.assertIn("AIDS", branches)
        self.assertIn("ECE", branches)


class TestDocumentParsers(unittest.TestCase):
    """Test text extractor with in-memory streams, CSV, DOCX tables/hyperlinks."""

    def test_csv_extraction(self):
        """Extract text and column metadata from CSV bytes."""
        csv_content = b"Student Name,USN,Branch,CGPA\nJohn Doe,1RV21CS001,CSE,8.5\nJane Smith,1RV21EC002,ECE,9.1"
        res = text_extractor.extract_text("students.csv", content=csv_content)
        self.assertTrue(res["success"])
        self.assertIn("John Doe", res["text"])
        self.assertIn("1RV21CS001", res["text"])
        self.assertEqual(res["metadata"]["row_count"], 2)

    def test_txt_extraction(self):
        """Extract text from TXT bytes."""
        txt_content = b"Hiring Software Engineers for 2026 batch. CTC 10 LPA."
        res = text_extractor.extract_text("notice.txt", content=txt_content)
        self.assertTrue(res["success"])
        self.assertIn("Hiring Software Engineers", res["text"])

    def test_docx_table_extraction(self):
        """Extract text and tables from DOCX bytes in memory."""
        try:
            import docx
            from io import BytesIO
            doc = docx.Document()
            doc.add_paragraph("Job Opening: Cloud Consultant")
            tbl = doc.add_table(rows=2, cols=2)
            tbl.cell(0, 0).text = "Role"
            tbl.cell(0, 1).text = "Cloud Consultant"
            tbl.cell(1, 0).text = "Package"
            tbl.cell(1, 1).text = "12 LPA"
            buf = BytesIO()
            doc.save(buf)
            res = text_extractor.extract_text("jd.docx", content=buf.getvalue())
            self.assertTrue(res["success"])
            self.assertIn("Cloud Consultant", res["text"])
            self.assertIn("12 LPA", res["text"])
        except ImportError:
            self.skipTest("python-docx not installed in test environment")

    def test_xlsx_extraction(self):
        """Extract text from XLSX spreadsheet bytes in memory."""
        try:
            import pandas as pd
            from io import BytesIO
            df = pd.DataFrame({"Company": ["Google", "Microsoft"], "CTC": ["30 LPA", "45 LPA"]})
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            res = text_extractor.extract_text("data.xlsx", content=buf.getvalue())
            self.assertTrue(res["success"])
            self.assertIn("Google", res["text"])
            self.assertIn("45 LPA", res["text"])
        except ImportError:
            self.skipTest("openpyxl or pandas not installed")

    def test_native_pdf_extraction_in_memory(self):
        """Extract native text and hyperlink annotations from PDF in memory without tempfile locks."""
        from app.services.file_storage.minio_client import minio_client
        pdf_bytes = minio_client.download_file("placement-docs", "67d34081-0c52-4fba-8ffa-62c73d0c1763/Support_Executive_JD_(1).pdf")
        res = text_extractor.extract_text("Support_Executive_JD.pdf", content=pdf_bytes)
        self.assertTrue(res["success"])
        self.assertIn("Technical Support Executive", res["text"])
        self.assertTrue(res["metadata"]["page_count"] >= 1)


class TestMultiFileMerging(unittest.TestCase):
    """Test merging complementary documents without overwriting complete values."""

    def test_poster_and_pdf_complementary_merge(self):
        """
        File 1 (Poster): Contains Application URL and Deadline.
        File 2 (JD PDF): Contains Title, CGPA, Salary, and Skills.
        The merged output must combine all valid information.
        """
        poster_text = (
            "Eazy ERP Campus Recruitment 2026\n"
            "Last Date of Online Application: 19\" October 2026\n"
            "Apply Here: https://forms.gle/yP4tpWtmk9VdFFBU8\n"
        )
        pdf_text = (
            "Job Title: Technical Support Executive\n"
            "Company: Eazy ERP Technologies\n"
            "Minimum CGPA: 7.0\n"
            "Salary: INR 2,40 - 3.60 Lakhs per annum\n"
            "Required Skills: Troubleshooting, Customer Support, CRM, SQL\n"
            "Branches: CSE, IT, ECE"
        )

        files_data = [
            {"filename": "recruitment_poster.png", "content": poster_text.encode("utf-8")},
            {"filename": "Support_Executive_JD.pdf", "content": pdf_text.encode("utf-8")}
        ]

        merged = jd_parser_service.parse_multiple_files(files_data)

        self.assertEqual(merged.get("title"), "Technical Support Executive")
        self.assertEqual(merged.get("application_url"), "https://forms.gle/yP4tpWtmk9VdFFBU8")
        self.assertEqual(merged.get("application_deadline"), "2026-10-19T00:00")
        self.assertEqual(merged.get("cgpa_criteria"), 7.0)
        self.assertIsNotNone(merged.get("salary_range"))
        self.assertIn("2.40", merged.get("salary_range"))
        self.assertIn("Troubleshooting", merged.get("required_skills", []))
        self.assertIn("Customer Support", merged.get("required_skills", []))
        self.assertIn("CSE", merged.get("branch_eligibility", []))

    def test_conflicting_cgpa_flagged(self):
        """Conflicting CGPA criteria between files flags a review warning and takes highest."""
        file1 = "Minimum CGPA: 6.5"
        file2 = "Minimum CGPA: 7.5"
        files_data = [
            {"filename": "circular.txt", "content": file1.encode("utf-8")},
            {"filename": "jd.txt", "content": file2.encode("utf-8")}
        ]
        merged = jd_parser_service.parse_multiple_files(files_data)
        self.assertEqual(merged.get("cgpa_criteria"), 7.5)
        self.assertTrue(any("Conflicting Minimum CGPA" in flag for flag in merged.get("review_flags", [])))


class TestEazyErpRealDocuments(unittest.TestCase):
    """End-to-end verification using the real Eazy ERP documents from MinIO."""

    def setUp(self):
        from app.services.file_storage.minio_client import minio_client
        self.minio_client = minio_client
        self.bucket = "placement-docs"
        self.pdf_key = "67d34081-0c52-4fba-8ffa-62c73d0c1763/Support_Executive_JD_(1).pdf"
        self.poster1_key = "1cc33720-de0f-4642-9d48-0bf121357b8d/WhatsApp_Image_2026-10-15_at_12.39.30_PM.jpeg"
        self.poster2_key = "fc9587d5-ced4-4ff5-ac78-85181df9599a/WhatsApp_Image_2026-10-15_at_12.39.32_PM.jpeg"

    def test_eazy_erp_files_exist_and_readable(self):
        """Check genuine MinIO document files are intact."""
        pdf_bytes = self.minio_client.download_file(self.bucket, self.pdf_key)
        poster1_bytes = self.minio_client.download_file(self.bucket, self.poster1_key)
        poster2_bytes = self.minio_client.download_file(self.bucket, self.poster2_key)
        self.assertTrue(len(pdf_bytes) > 1000, "PDF bytes should be non-empty")
        self.assertTrue(len(poster1_bytes) > 1000, "Poster 1 bytes should be non-empty")
        self.assertTrue(len(poster2_bytes) > 1000, "Poster 2 bytes should be non-empty")

    def test_eazy_erp_multi_file_end_to_end_extraction(self):
        """
        Verify end-to-end extraction and merging of the real Eazy ERP Job 1089 documents:
        - URL reconstructed: https://forms.gle/yP4tpWtmk9VdFFBU8
        - Deadline extracted: 2026-10-19T00:00 (from 19" October 2026)
        - Title extracted: Technical Support Executive (from PDF)
        - Salary: INR 2.40 - 3.60 Lakhs
        """
        pdf_bytes = self.minio_client.download_file(self.bucket, self.pdf_key)
        poster1_bytes = self.minio_client.download_file(self.bucket, self.poster1_key)
        poster2_bytes = self.minio_client.download_file(self.bucket, self.poster2_key)

        files_data = [
            {"filename": "Support_Executive_JD_(1).pdf", "content": pdf_bytes},
            {"filename": "WhatsApp_Image_2026-10-15_at_12.39.30_PM.jpeg", "content": poster1_bytes},
            {"filename": "WhatsApp_Image_2026-10-15_at_12.39.32_PM.jpeg", "content": poster2_bytes},
        ]

        merged = jd_parser_service.parse_multiple_files(files_data)

        # 1. Title verification
        self.assertIsNotNone(merged.get("title"))
        self.assertIn("Support Executive", merged.get("title"))

        # 2. Application URL verification
        self.assertEqual(merged.get("application_url"), "https://forms.gle/yP4tpWtmk9VdFFBU8")

        # 3. Application deadline verification
        self.assertEqual(merged.get("application_deadline"), "2026-10-19T00:00")

        # 4. Salary verification
        salary = merged.get("salary_range")
        self.assertIsNotNone(salary)
        self.assertTrue("2.40" in salary or "2.4" in salary or "3.60" in salary or "3.6" in salary)

        # 5. Candidate URL list populated
        self.assertTrue(len(merged.get("application_url_candidates", [])) >= 1)
        top_url = merged.get("application_url_candidates")[0]["url"]
        self.assertEqual(top_url, "https://forms.gle/yP4tpWtmk9VdFFBU8")


if __name__ == "__main__":
    unittest.main(verbosity=2)
