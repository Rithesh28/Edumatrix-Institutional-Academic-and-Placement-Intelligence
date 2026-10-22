"""
EduMatrix Phase 2 Placement Fix Pass - Focused Regression Test Suite

Validates the three targeted bug fixes:
- Fix A: Company ID validation returning HTTP 404 for non-existent companies
- Fix B: Scanned PDF OCR fallback with extraction status / warning
- Fix C: Salary / CTC validation, normalization (LPA), and structured bounds

Safety mandate: Target database MUST be 'edumatrix_test_phase2a'.
"""

import os
import io
import unittest
import reportlab.pdfgen.canvas as canvas
from PIL import Image, ImageDraw
from reportlab.lib.utils import ImageReader

# Force DATABASE_URL safety guard
DATABASE_URL = os.getenv("DATABASE_URL", "")
if "edumatrix_test_phase2a" not in DATABASE_URL:
    raise RuntimeError(
        f"CRITICAL SAFETY VIOLATION: DATABASE_URL must point to 'edumatrix_test_phase2a'. Current: '{DATABASE_URL}'"
    )

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.main import app
from app.core.database import SessionLocal, engine
from app.core.security import create_access_token
from app.models.user import User, UserRole
from app.models.company import Company
from app.models.job_posting import JobPosting
from app.services.resume_parser import resume_parser
from app.services.salary_normalizer import normalize_salary_range, extract_ctc_lpa_bounds
from app.schemas.placement import JobPostingCreate, JobPostingUpdate, JobPostingResponse


class TestPhase2PlacementFixesRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url_str = str(engine.url)
        if "edumatrix_test_phase2a" not in url_str:
            raise RuntimeError(f"Engine URL target safety violation: {url_str}")
        
        cls.client = TestClient(app, raise_server_exceptions=False)
        cls.db: Session = SessionLocal()
        
        res = cls.db.execute(text("SELECT current_database();")).scalar()
        if res != "edumatrix_test_phase2a":
            raise RuntimeError(f"Connected to WRONG database: {res}. Aborting.")
        
        print(f"\n[SAFETY VERIFIED] Fix Pass Regression running on: {res}")
        
        # Ensure test PO user exists
        cls.po = cls.db.query(User).filter(User.email == "po_p2c@test.edu").first()
        if not cls.po:
            raise RuntimeError("po_p2c@test.edu not found in test database")
        
        token = create_access_token(data={"id": cls.po.id, "email": cls.po.email, "role": cls.po.role.value})
        cls.headers = {"Authorization": f"Bearer {token}"}
        
        # Ensure a test company exists
        cls.company = cls.db.query(Company).first()
        if not cls.company:
            cls.company = Company(name="Test Regression Corp", website="https://testcorp.com", created_by=cls.po.id)
            cls.db.add(cls.company)
            cls.db.commit()
            cls.db.refresh(cls.company)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def setUp(self):
        self.db.rollback()

    # =========================================================================
    # FIX A REGRESSION TESTS: Invalid Company ID Handling
    # =========================================================================

    def test_01_fix_a_valid_company_id_creates_job_successfully(self):
        """1. Valid company ID creates a job successfully."""
        payload = {
            "company_id": self.company.id,
            "title": "Platform Reliability Engineer",
            "description": "Manage Kubernetes clusters",
            "required_skills": ["Kubernetes", "Linux", "Python"],
            "salary_range": "14.0 LPA"
        }
        resp = self.client.post("/placement/jobs", json=payload, headers=self.headers)
        self.assertEqual(resp.status_code, 200, f"Expected 200 OK, got: {resp.text}")
        data = resp.json()
        self.assertEqual(data["company_id"], self.company.id)
        self.assertEqual(data["title"], "Platform Reliability Engineer")
        self.assertEqual(data["salary_range"], "14.0 LPA")

    def test_02_fix_a_nonexistent_company_id_returns_404_not_500(self):
        """2. Nonexistent company ID returns HTTP 404, not HTTP 500."""
        payload = {
            "company_id": 99999999,
            "title": "Ghost Role",
            "description": "Company does not exist",
            "required_skills": ["Python"]
        }
        resp = self.client.post("/placement/jobs", json=payload, headers=self.headers)
        self.assertEqual(
            resp.status_code, 404,
            f"Expected HTTP 404 Not Found, but got HTTP {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        self.assertIn("detail", data)
        self.assertIn("not found", data["detail"].lower())

    def test_03_fix_a_invalid_company_creates_no_job_record(self):
        """3. Invalid company ID creates no job record in the database."""
        count_before = self.db.query(JobPosting).filter(JobPosting.title == "Orphan Job Attempt").count()
        payload = {
            "company_id": 88888888,
            "title": "Orphan Job Attempt",
            "description": "Should never be persisted",
            "required_skills": ["C++"]
        }
        resp = self.client.post("/placement/jobs", json=payload, headers=self.headers)
        self.assertEqual(resp.status_code, 404)
        
        self.db.expire_all()
        count_after = self.db.query(JobPosting).filter(JobPosting.title == "Orphan Job Attempt").count()
        self.assertEqual(count_before, count_after, "A job record was unexpectedly created on 404 failure!")

    def test_04_fix_a_update_job_with_invalid_company_returns_404(self):
        """4. Updating an existing job with a nonexistent company_id returns HTTP 404."""
        # Create a job first
        job = JobPosting(
            company_id=self.company.id,
            title="Mutable Job",
            required_skills=["SQL"],
            created_by=self.po.id
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        
        update_payload = {"company_id": 77777777}
        resp = self.client.put(f"/placement/jobs/{job.id}", json=update_payload, headers=self.headers)
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.json()["detail"].lower())

    # =========================================================================
    # FIX B REGRESSION TESTS: Scanned PDF Resumes & OCR Fallback
    # =========================================================================

    def test_01_fix_b_text_based_pdf_extracts_correctly(self):
        """1. Normal text-based PDF still extracts correctly using pdfplumber."""
        pdf_buf = io.BytesIO()
        c = canvas.Canvas(pdf_buf)
        c.drawString(100, 750, "Alice Student - Senior Software Engineer")
        c.drawString(100, 730, "Skills: Python, FastAPI, PostgreSQL, Docker, Kubernetes")
        c.drawString(100, 710, "Education: B.E. in Computer Science (CGPA: 8.9)")
        c.drawString(100, 690, "Email: alice.student@test.edu | Phone: 9876543210")
        c.save()
        pdf_bytes = pdf_buf.getvalue()

        result = resume_parser.parse_resume("alice_text_resume.pdf", content=pdf_bytes)
        self.assertTrue(result["success"])
        self.assertEqual(result["extractor_used"], "pdfplumber")
        self.assertIsNone(result["warning"])
        self.assertIn("python", [s.lower() for s in result["entities"].get("skills", [])])
        self.assertIn("fastapi", [s.lower() for s in result["entities"].get("skills", [])])

    def test_02_fix_b_scanned_image_based_pdf_triggers_ocr_fallback(self):
        """2. Synthetic scanned/image-based PDF triggers the OCR fallback and returns warning."""
        pdf_buf = io.BytesIO()
        c = canvas.Canvas(pdf_buf)
        
        # Render text into an image
        img = Image.new("RGB", (600, 150), color="white")
        d = ImageDraw.Draw(img)
        d.text((20, 30), "Bob Candidate - Data Engineer", fill="black")
        d.text((20, 60), "Skills: Apache Spark, Hadoop, Python, Docker", fill="black")
        d.text((20, 90), "Education: B.Tech AIML (CGPA: 8.5)", fill="black")
        
        img_buf = io.BytesIO()
        img.save(img_buf, format="PNG")
        img_buf.seek(0)
        c.drawImage(ImageReader(img_buf), 50, 650, width=500, height=125)
        c.save()
        pdf_bytes = pdf_buf.getvalue()

        result = resume_parser.parse_resume("scanned_data_engineer.pdf", content=pdf_bytes)
        self.assertTrue(result["success"])
        self.assertEqual(result["extractor_used"], "tesseract_ocr")
        self.assertIsNotNone(result["warning"])
        self.assertIn("scanned", result["warning"].lower())
        self.assertEqual(result["extraction_status"], "OCR_FALLBACK")
        # Ensure OCR extracted text has expected content
        self.assertIn("spark", result["text"].lower())

    def test_03_fix_b_empty_or_corrupt_pdf_handled_safely(self):
        """3. Empty or corrupt PDF is handled safely with meaningful error."""
        corrupt_bytes = b"%PDF-1.4\n%corrupt garbage content that is not a real pdf"
        result = resume_parser.parse_resume("corrupted.pdf", content=corrupt_bytes)
        self.assertFalse(result["success"])
        self.assertIsNotNone(result["error"])
        
        empty_bytes = b""
        result_empty = resume_parser.parse_resume("empty.pdf", content=empty_bytes)
        self.assertFalse(result_empty["success"])
        self.assertIsNotNone(result_empty["error"])

    def test_04_fix_b_blank_page_pdf_returns_clear_scanned_status(self):
        """4. PDF with blank image pages returns clear actionable status, not silent empty parse."""
        pdf_buf = io.BytesIO()
        c = canvas.Canvas(pdf_buf)
        # Blank page (pure white image)
        img = Image.new("RGB", (400, 400), color="white")
        img_buf = io.BytesIO()
        img.save(img_buf, format="PNG")
        img_buf.seek(0)
        c.drawImage(ImageReader(img_buf), 50, 400, width=300, height=300)
        c.save()
        pdf_bytes = pdf_buf.getvalue()

        result = resume_parser.parse_resume("blank_scan.pdf", content=pdf_bytes)
        self.assertFalse(result["success"])
        self.assertEqual(result["extraction_status"], "SCANNED_PDF_NO_TEXT")
        self.assertIn("scanned or image-based", result["error"].lower())

    def test_05_fix_b_genuine_resume_with_missing_fields_no_fabrication(self):
        """5. Genuine resume with missing fields does not receive fabricated values."""
        pdf_buf = io.BytesIO()
        c = canvas.Canvas(pdf_buf)
        c.drawString(100, 750, "Jane Doe")
        c.drawString(100, 730, "Skills: Python, Git")
        # Intentionally omitting education, experience, phone, certifications
        c.save()
        pdf_bytes = pdf_buf.getvalue()

        result = resume_parser.parse_resume("jane_minimal.pdf", content=pdf_bytes)
        self.assertTrue(result["success"])
        entities = result["entities"]
        # Must not fabricate education or experience
        self.assertEqual(entities.get("education", []), [])
        self.assertEqual(entities.get("experience", []), [])
        self.assertEqual(entities.get("certifications", []), [])

    # =========================================================================
    # FIX C REGRESSION TESTS: Salary / CTC Validation & Normalization
    # =========================================================================

    def test_01_fix_c_numeric_salary_normalized_to_lpa(self):
        """1. Raw numeric salary input normalized according to documented unit convention."""
        # e.g., '12' -> '12.0 LPA'
        norm = normalize_salary_range("12")
        self.assertEqual(norm, "12.0 LPA")
        low, high = extract_ctc_lpa_bounds(norm)
        self.assertEqual(low, 12.0)
        self.assertEqual(high, 12.0)

    def test_02_fix_c_explicit_lpa_interpreted_correctly(self):
        """2. '12 LPA' and '12.5 LPA' interpreted correctly."""
        norm = normalize_salary_range("12 LPA")
        self.assertEqual(norm, "12.0 LPA")
        norm2 = normalize_salary_range("12.5 LPA")
        self.assertEqual(norm2, "12.5 LPA")

    def test_03_fix_c_annual_rupee_amount_interpreted_correctly(self):
        """3. '1200000' and '12,00,000' interpreted under explicit annual INR / 100,000 convention."""
        norm1 = normalize_salary_range("1200000")
        self.assertEqual(norm1, "12.0 LPA")
        norm2 = normalize_salary_range("12,00,000")
        self.assertEqual(norm2, "12.0 LPA")
        norm3 = normalize_salary_range("₹2.16 LPA")
        self.assertEqual(norm3, "2.16 LPA")

    def test_04_fix_c_salary_range_bounds_extracted_correctly(self):
        """4. '6 - 8 LPA' normalized and min/max bounds correctly extracted."""
        norm = normalize_salary_range("6 - 8 LPA")
        self.assertEqual(norm, "6.0 - 8.0 LPA")
        low, high = extract_ctc_lpa_bounds(norm)
        self.assertEqual(low, 6.0)
        self.assertEqual(high, 8.0)

    def test_05_fix_c_ambiguous_foreign_currency_rejected(self):
        """5. '$90k' rejected as ambiguous currency."""
        bad_currency = chr(36) + "90k"
        with self.assertRaises(ValueError) as ctx:
            normalize_salary_range(bad_currency)
        self.assertIn("ambiguous currency", str(ctx.exception).lower())

    def test_06_fix_c_arbitrary_unparseable_text_rejected(self):
        """6. 'Best in industry' and 'Negotiable' rejected (not silently interpreted as numeric)."""
        with self.assertRaises(ValueError) as ctx:
            normalize_salary_range("Best in industry")
        self.assertIn("invalid salary/ctc format", str(ctx.exception).lower())

        with self.assertRaises(ValueError) as ctx2:
            normalize_salary_range("Negotiable")
        self.assertIn("invalid salary/ctc format", str(ctx2.exception).lower())

    def test_07_fix_c_job_posting_api_enforces_normalization_and_ctc_bounds(self):
        """7. POST /placement/jobs normalizes valid CTC and computes min_ctc_lpa / max_ctc_lpa."""
        payload = {
            "company_id": self.company.id,
            "title": "Machine Learning Engineer",
            "required_skills": ["PyTorch", "Python"],
            "salary_range": "18 - 22 LPA"
        }
        resp = self.client.post("/placement/jobs", json=payload, headers=self.headers)
        self.assertEqual(resp.status_code, 200, f"Error: {resp.text}")
        data = resp.json()
        self.assertEqual(data["salary_range"], "18.0 - 22.0 LPA")
        self.assertEqual(data["min_ctc_lpa"], 18.0)
        self.assertEqual(data["max_ctc_lpa"], 22.0)

    def test_08_fix_c_job_posting_api_rejects_best_in_industry(self):
        """8. POST /placement/jobs rejects 'Best in industry' with HTTP 422."""
        payload = {
            "company_id": self.company.id,
            "title": "Unvalidated Lead",
            "required_skills": ["Java"],
            "salary_range": "Best in industry"
        }
        resp = self.client.post("/placement/jobs", json=payload, headers=self.headers)
        self.assertEqual(resp.status_code, 422)


if __name__ == "__main__":
    unittest.main()
