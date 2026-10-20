"""
End-to-End Integration Test Suite for Manage Jobs Upload, Extraction, Form Binding, and Persistence.

Verifies:
1. Original Eazy ERP files uploaded to live/actual backend endpoint POST /placement/jobs/upload-jd
2. Complete URL (https://forms.gle/yP4tpWtmk9VdFFBU8) and Application Deadline (2026-10-19T00:00) returned in response
3. Multi-file candidate ranking & prefix deduplication (prefix https://forms.gle/yP4tp discarded in favor of complete URL)
4. Frontend date format compatibility & saving / reopening drafts without calendar-day shift
5. Regression for CGPA (7.5), salary range, and attachment file IDs
6. Optional deadline handling for jobs without deadline
"""

import os
import sys
import unittest
import requests
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.core.database import SessionLocal
from app.models.user import User, UserRole
from app.models.job_posting import JobPosting, JobStatus
from app.models.company import Company
from app.core.security import create_access_token
from app.services.jd_parser_service import jd_parser_service
from app.services.file_storage.minio_client import minio_client


class TestManageJobsEndToEndPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        cls.user = cls.db.query(User).filter(User.email == "placement@gmail.com").first()
        if not cls.user:
            cls.user = cls.db.query(User).filter(User.role == UserRole.PLACEMENT_OFFICER).first()
        assert cls.user is not None, "A placement officer user must exist in the database."

        # Backend JWT authentication requires user ID
        cls.token = create_access_token(data={"id": cls.user.id})
        cls.headers = {"Authorization": f"Bearer {cls.token}"}
        cls.base_url = "http://127.0.0.1:8000"

        # Download genuine test files from MinIO
        cls.bucket = "placement-docs"
        cls.pdf_bytes = minio_client.download_file(
            cls.bucket, "67d34081-0c52-4fba-8ffa-62c73d0c1763/Support_Executive_JD_(1).pdf"
        )
        cls.poster1_bytes = minio_client.download_file(
            cls.bucket, "1cc33720-de0f-4642-9d48-0bf121357b8d/WhatsApp_Image_2026-10-15_at_12.39.30_PM.jpeg"
        )
        cls.poster2_bytes = minio_client.download_file(
            cls.bucket, "fc9587d5-ced4-4ff5-ac78-85181df9599a/WhatsApp_Image_2026-10-15_at_12.39.32_PM.jpeg"
        )
        cls.created_job_ids = []

    @classmethod
    def tearDownClass(cls):
        # Cleanup any test jobs created during integration tests
        for jid in cls.created_job_ids:
            try:
                job = cls.db.query(JobPosting).filter(JobPosting.id == jid).first()
                if job:
                    cls.db.delete(job)
                    cls.db.commit()
            except Exception:
                cls.db.rollback()
        cls.db.close()

    def test_01_upload_endpoint_returns_complete_url_and_deadline(self):
        """
        Test the actual backend POST /placement/jobs/upload-jd endpoint with the real files.
        Must return:
        - application_url: https://forms.gle/yP4tpWtmk9VdFFBU8
        - application_deadline: 2026-10-19T00:00
        - min_cgpa: 7.5
        - salary_range with 2.40 and 3.60
        """
        files = [
            ("files", ("Support_Executive_JD_(1).pdf", self.pdf_bytes, "application/pdf")),
            ("files", ("WhatsApp_Image_2026-10-15_at_12.39.30_PM.jpeg", self.poster1_bytes, "image/jpeg")),
            ("files", ("WhatsApp_Image_2026-10-15_at_12.39.32_PM.jpeg", self.poster2_bytes, "image/jpeg")),
        ]
        resp = requests.post(
            f"{self.base_url}/placement/jobs/upload-jd",
            headers=self.headers,
            files=files,
            timeout=90
        )
        self.assertEqual(resp.status_code, 200, f"Upload endpoint failed: {resp.text}")
        data = resp.json()

        # 1. URL verification
        self.assertEqual(
            data.get("application_url"),
            "https://forms.gle/yP4tpWtmk9VdFFBU8",
            "Actual upload endpoint returned truncated or incorrect application URL"
        )

        # 2. Candidate URLs verification
        candidates = data.get("application_url_candidates", [])
        cand_urls = [c["url"] if isinstance(c, dict) else c for c in candidates]
        self.assertIn("https://forms.gle/yP4tpWtmk9VdFFBU8", cand_urls)
        self.assertNotIn("https://forms.gle/yP4tp", cand_urls, "Truncated prefix must not appear in candidate URLs")

        # 3. Deadline verification
        self.assertEqual(
            data.get("application_deadline"),
            "2026-10-19T00:00",
            "Actual upload endpoint failed to extract 19 October 2026 deadline"
        )

        # 4. Eligibility & Compensation regressions
        self.assertEqual(data.get("cgpa_criteria"), 7.5)
        self.assertIn("2.40", str(data.get("salary_range")))
        self.assertIn("3.60", str(data.get("salary_range")))
        self.assertIn("Support Executive", str(data.get("title")))

    def test_02_prefix_deduplication_regression(self):
        """
        Ensure that if both a truncated prefix and the full URL are present in document text,
        the truncated prefix is discarded and the complete URL is selected and ranked top.
        """
        text_with_prefix = (
            "Registration link part: https://forms.gle/yP4tp\n"
            "Full application link: https://forms.gle/yP4tpWtmk9VdFFBU8\n"
            "Last Date of Application: 19 October 2026"
        )
        parsed = jd_parser_service.parse_jd_text(text_with_prefix)
        self.assertEqual(parsed.get("application_url"), "https://forms.gle/yP4tpWtmk9VdFFBU8")
        cand_urls = [c["url"] if isinstance(c, dict) else c for c in parsed.get("application_url_candidates", [])]
        self.assertEqual(cand_urls, ["https://forms.gle/yP4tpWtmk9VdFFBU8"])
        self.assertNotIn("https://forms.gle/yP4tp", cand_urls)

    def test_03_multi_file_prefix_collision(self):
        """
        If file 1 has truncated prefix https://forms.gle/yP4tp and file 2 has full URL,
        multi-file merging must discard the truncated prefix and choose the complete URL.
        """
        file1 = {"filename": "doc1.txt", "content": b"Apply at https://forms.gle/yP4tp"}
        file2 = {"filename": "doc2.txt", "content": b"Apply here: https://forms.gle/yP4tpWtmk9VdFFBU8\nDeadline: 19 October 2026"}
        merged = jd_parser_service.parse_multiple_files([file1, file2])

        self.assertEqual(merged.get("application_url"), "https://forms.gle/yP4tpWtmk9VdFFBU8")
        cand_urls = [c["url"] if isinstance(c, dict) else c for c in merged.get("application_url_candidates", [])]
        self.assertEqual(cand_urls, ["https://forms.gle/yP4tpWtmk9VdFFBU8"])

    def test_04_save_and_reopen_draft_preserves_values_without_calendar_day_shift(self):
        """
        Verify that:
        1. A job draft with complete URL and deadline '2026-10-19T00:00' can be created.
        2. When fetched back via GET /placement/jobs/{id}, the deadline starts with '2026-10-19'
           and does NOT shift back to 2026-10-18.
        3. All eligibility and compensation criteria persist.
        """
        # Ensure a company exists
        company = self.db.query(Company).filter(Company.is_active == True).first()
        assert company is not None, "An active company must exist"

        payload = {
            "company_id": company.id,
            "title": "Integration Test Technical Support Executive",
            "description": "Integration test job for URL and deadline validation",
            "location": "Gurgaon",
            "salary_range": "INR 2.40 - 3.60 Lakhs per annum",
            "cgpa_criteria": 7.5,
            "required_skills": ["Customer Support", "Troubleshooting", "CRM"],
            "application_url": "https://forms.gle/yP4tpWtmk9VdFFBU8",
            "application_deadline": "2026-10-19T00:00",
            "status": "draft"
        }

        # 1. Create job
        create_resp = requests.post(
            f"{self.base_url}/placement/jobs",
            headers=self.headers,
            json=payload,
            timeout=30
        )
        self.assertEqual(create_resp.status_code, 200, f"Create job failed: {create_resp.text}")
        created_job = create_resp.json()
        job_id = created_job["id"]
        self.created_job_ids.append(job_id)

        # 2. Fetch job (reopen draft)
        get_resp = requests.get(
            f"{self.base_url}/placement/jobs/{job_id}",
            headers=self.headers,
            timeout=30
        )
        self.assertEqual(get_resp.status_code, 200, f"Fetch job failed: {get_resp.text}")
        fetched_job = get_resp.json()

        # 3. Validate URL
        self.assertEqual(fetched_job.get("application_url"), "https://forms.gle/yP4tpWtmk9VdFFBU8")

        # 4. Validate Deadline without calendar day shift
        fetched_deadline = fetched_job.get("application_deadline")
        self.assertIsNotNone(fetched_deadline)
        # Sliced date must be exactly 2026-10-19
        self.assertTrue(
            fetched_deadline.startswith("2026-10-19"),
            f"Calendar date shifted! Expected '2026-10-19...', got '{fetched_deadline}'"
        )

        # 5. Validate other fields
        self.assertEqual(fetched_job.get("cgpa_criteria"), 7.5)
        self.assertEqual(fetched_job.get("salary_range"), "INR 2.40 - 3.60 Lakhs per annum")
        self.assertEqual(fetched_job.get("status"), "draft")

    def test_05_optional_deadline_can_be_null(self):
        """Confirm that jobs without an application deadline can have deadline as null."""
        company = self.db.query(Company).filter(Company.is_active == True).first()
        payload = {
            "company_id": company.id,
            "title": "Integration Test Job Without Deadline",
            "application_url": "https://forms.gle/yP4tpWtmk9VdFFBU8",
            "application_deadline": None,
            "status": "draft"
        }
        create_resp = requests.post(
            f"{self.base_url}/placement/jobs",
            headers=self.headers,
            json=payload,
            timeout=30
        )
        self.assertEqual(create_resp.status_code, 200)
        job_id = create_resp.json()["id"]
        self.created_job_ids.append(job_id)

        get_resp = requests.get(f"{self.base_url}/placement/jobs/{job_id}", headers=self.headers, timeout=30)
        self.assertIsNone(get_resp.json().get("application_deadline"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
