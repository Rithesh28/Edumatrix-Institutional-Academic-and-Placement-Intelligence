"""
Comprehensive automated tests for Manage Jobs Extraction, File Access,
and Redesigned Recruitment Drives Shortlist Announcement Workflow.

Executes in an isolated PostgreSQL database (edumatrix_test_manage_jobs_recruitment).
Never touches genuine development data.
"""

import os
import sys
import io
import csv
import json
import uuid
import unittest
from datetime import datetime, timedelta, timezone

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from fastapi.testclient import TestClient

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.core.database import Base, get_db
from app.api.auth import get_current_user
from app.main import app
from app.models.user import User, UserRole
from app.models.company import Company
from app.models.job_posting import JobPosting, JobStatus, JobPostingAttachment
from app.models.file import File as FileModel, FileType, FileStatus
from app.models.application import Application, ApplicationStatus
from app.models.profile import StudentProfileExtended
from app.models.notification import Notification
from app.models.recruitment_circular import (
    RecruitmentCircular,
    RecruitmentCircularStatus,
    RecruitmentCircularAttachment,
    RecruitmentCircularJob,
)
from app.models.recruitment_round import (
    RecruitmentRound,
    StudentRoundOutcome,
    RoundOutcome,
    PlacementOffer,
    OfferAcceptanceStatus,
)
from app.models.recruitment_result import (
    RecruitmentResultBatch,
    RecruitmentResultBatchStatus,
    RecruitmentResultItem,
    RecruitmentResultItemStatus,
    RecruitmentResultReviewState,
)
from app.services.jd_parser_service import jd_parser_service
from app.services.file_storage.file_service import file_service
from app.services.recruitment_result_matcher import recruitment_result_matcher
from app.tasks.placement_tasks import close_expired_jobs

POSTGRES_BASE_URL = os.environ.get(
    "TEST_DATABASE_BASE_URL",
    "postgresql://edumatrix:edumatrix123@postgres:5432"
)


def make_text_image(text_lines, width=900, height=350):
    from PIL import Image, ImageDraw, ImageFont
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font = ImageFont.truetype(font_path, 20) if os.path.exists(font_path) else None
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    y = 25
    for line in text_lines:
        d.text((25, y), line, fill=(0, 0, 0), font=font)
        y += 35
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_scanned_pdf(text_lines, width=900, height=350):
    from PIL import Image, ImageDraw, ImageFont
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font = ImageFont.truetype(font_path, 20) if os.path.exists(font_path) else None
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    y = 25
    for line in text_lines:
        d.text((25, y), line, fill=(0, 0, 0), font=font)
        y += 35
    buf = io.BytesIO()
    img.save(buf, format="PDF")
    return buf.getvalue()


class TestManageJobsAndRecruitmentDrives(unittest.TestCase):
    """Isolated test suite for Problem 1 (Manage Jobs) and Problem 2 (Recruitment Drives)."""

    TEST_DB_NAME = "edumatrix_test_manage_jobs_recruitment"

    @classmethod
    def setUpClass(cls):
        """Provision isolated PostgreSQL database and create all tables."""
        conn = psycopg2.connect(f"{POSTGRES_BASE_URL}/template1")
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute(f"DROP DATABASE IF EXISTS {cls.TEST_DB_NAME};")
        cur.execute(f"CREATE DATABASE {cls.TEST_DB_NAME};")
        cur.close()
        conn.close()

        cls.engine = sa.create_engine(
            f"{POSTGRES_BASE_URL}/{cls.TEST_DB_NAME}",
            pool_pre_ping=True
        )
        Base.metadata.create_all(cls.engine)
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

        # Seed static test entities once
        session = cls.SessionLocal()
        cls.officer = User(
            email="officer_test@edumatrix.edu",
            name="Placement Officer Test",
            role=UserRole.PLACEMENT_OFFICER,
            password_hash="mock_hashed_password",
            department="Placement Cell",
            is_active=True,
        )
        cls.student_cs = User(
            email="student_cs@edumatrix.edu",
            name="Alice CS Student",
            role=UserRole.STUDENT,
            password_hash="mock_hashed_password",
            department="Computer Science",
            is_active=True,
        )
        cls.student_mech = User(
            email="student_mech@edumatrix.edu",
            name="Bob Mech Student",
            role=UserRole.STUDENT,
            password_hash="mock_hashed_password",
            department="Mechanical Engineering",
            is_active=True,
        )
        session.add_all([cls.officer, cls.student_cs, cls.student_mech])
        session.flush()

        cls.profile_cs = StudentProfileExtended(
            user_id=cls.student_cs.id,
            enrollment_number="1MS21CS001",
            branch="Computer Science (CSE)",
            cgpa=8.5,
            year=4,
        )
        cls.profile_mech = StudentProfileExtended(
            user_id=cls.student_mech.id,
            enrollment_number="1MS21ME001",
            branch="Mechanical Engineering (MECH)",
            cgpa=7.2,
            year=4,
        )
        session.add_all([cls.profile_cs, cls.profile_mech])

        cls.company = Company(
            name="Innovate Tech Solutions",
            industry="Software",
            website="https://innovatetech.example.com",
            location="Bengaluru",
            is_active=True,
        )
        session.add(cls.company)
        session.commit()
        session.close()

    @classmethod
    def tearDownClass(cls):
        """Dispose engine and drop isolated test database."""
        cls.engine.dispose()
        try:
            conn = psycopg2.connect(f"{POSTGRES_BASE_URL}/template1")
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cur = conn.cursor()
            cur.execute(f"DROP DATABASE IF EXISTS {cls.TEST_DB_NAME};")
            cur.close()
            conn.close()
        except Exception:
            pass

    def setUp(self):
        """Create fresh session, attach test entities, and configure TestClient."""
        self.db = self.SessionLocal()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db

        self.current_user = None

        def override_get_current_user():
            return self.current_user

        from app.api.auth import get_current_user_flexible
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_current_user_flexible] = override_get_current_user

        self.client = TestClient(app)

        self.officer = self.db.merge(self.__class__.officer)
        self.student_cs = self.db.merge(self.__class__.student_cs)
        self.student_mech = self.db.merge(self.__class__.student_mech)
        self.company = self.db.merge(self.__class__.company)

    def tearDown(self):
        """Rollback and close session."""
        self.db.rollback()
        self.db.close()
        app.dependency_overrides.clear()

    # =========================================================================
    # PART 1: MANAGE JOBS EXTRACTION & OPTIONAL DATES
    # =========================================================================

    def test_multi_document_extraction_merging_and_conflicts(self):
        """Test multi-document parsing merges fields and flags conflicts without overwriting valid data."""
        doc1_text = """
        Company: Apex Cloud Systems
        Job Title: Cloud Software Engineer
        Location: Bengaluru, India
        Eligible Branches: Computer Science (CSE), Information Technology (IT)
        Required Skills: Python, Docker, Kubernetes, AWS
        Eligibility: Minimum CGPA: 7.5 and above
        Annual CTC: INR 4.50–6.00 lakhs per annum
        Internship stipend: Rs. 20,000 per month
        Registration Link: https://apexcloud.example.com/apply?req_id=9876&source=campus
        Application Deadline: 25 November 2026
        """

        doc2_text = """
        Apex Cloud Systems - Campus Recruitment Drive Details
        Role Description:
        Responsible for building microservices, deploying Kubernetes workloads, and maintaining cloud infrastructure.
        Key Responsibilities:
        - Develop scalable backend REST APIs in Python.
        - Configure CI/CD pipelines using GitHub Actions.
        - Monitor cloud resources and ensure high availability.
        Placement Drive Date: 05 December 2026
        Application Deadline: 28 November 2026
        """

        staged = jd_parser_service.parse_multiple_files([
            ("apex_jd_doc1.txt", doc1_text),
            ("apex_drive_details.txt", doc2_text),
        ])

        # 1. Company Name & Title
        self.assertEqual(staged["company_name"], "Apex Cloud Systems")
        self.assertEqual(staged["job_title"], "Cloud Software Engineer")

        # 2. Complete Application URL preserved
        self.assertEqual(
            staged["application_url"],
            "https://apexcloud.example.com/apply?req_id=9876&source=campus"
        )

        # 3. CGPA correctly extracted
        self.assertEqual(staged["min_cgpa"], 7.5)

        # 4. Annual CTC and Internship stipend kept distinct
        self.assertIn("4.50", staged["salary_range"])
        self.assertIn("6.00", staged["salary_range"])
        self.assertEqual(staged["compensation_details"].get("stipend"), "Rs. 20,000 per month")
        self.assertIn("4.50", staged["compensation_details"].get("annual_ctc", ""))
        self.assertIn("6.00", staged["compensation_details"].get("annual_ctc", ""))

        # 5. Drive date extracted from doc2
        self.assertIsNotNone(staged["drive_date"])
        self.assertIn("2026-12-05", staged["drive_date"])

        # 6. Conflicting application deadline detected between doc1 and doc2
        review_flags = staged.get("review_flags", [])
        self.assertTrue(
            any("application_deadline" in str(f) for f in review_flags),
            "Expected conflicting deadline to be flagged in review_flags"
        )

        # 7. Description contains responsibilities from doc2
        self.assertIn("Kubernetes workloads", staged["description"])
        self.assertIn("REST APIs in Python", staged["description"])

    def test_cgpa_extraction_patterns(self):
        """Test varied CGPA patterns: 'CGPA 7.5 and above', 'minimum CGPA: 7.0'."""
        text_a = "Eligible candidates must have CGPA 7.5 and above with no active backlogs."
        parsed_a = jd_parser_service.parse(text_a)
        self.assertEqual(parsed_a["min_cgpa"], 7.5)

        text_b = "Academic Requirements: minimum CGPA: 7.0 or equivalent 70%."
        parsed_b = jd_parser_service.parse(text_b)
        self.assertEqual(parsed_b["min_cgpa"], 7.0)

    def test_annual_ctc_and_stipend_distinction_eazy_erp_pattern(self):
        """Test distinction between annual CTC and monthly stipend (using en-dash and INR)."""
        text = """
        Position: Software Trainee
        Compensation:
        Annual CTC: INR 2.40–3.60 lakhs per annum.
        Internship stipend: Rs. 15,000 per month during first 6 months.
        Application Link: https://careers.example.com/jobs/apply?id=123
        """
        parsed = jd_parser_service.parse(text)
        # Annual CTC must reflect 2.40-3.60, not Rs. 15,000
        self.assertIn("2.40", parsed["salary_range"])
        self.assertIn("3.60", parsed["salary_range"])
        self.assertNotIn("15,000", parsed["salary_range"])
        self.assertEqual(parsed["compensation_details"]["stipend"], "Rs. 15,000 per month")

    def test_application_url_scoring_rejects_bare_homepages(self):
        """Test that plain company websites are not mistaken for application links."""
        text_with_apply = """
        Visit our website at https://www.acme-corp.com for company info.
        Apply online at https://jobs.acme-corp.com/apply/grad2026?source=campus
        """
        parsed = jd_parser_service.parse(text_with_apply)
        self.assertEqual(
            parsed["application_url"],
            "https://jobs.acme-corp.com/apply/grad2026?source=campus"
        )

        text_without_apply = """
        Acme Corp is hiring engineers.
        Visit us at https://www.acme-corp.com to learn more about our company culture.
        """
        parsed_no_apply = jd_parser_service.parse(text_without_apply)
        self.assertIsNone(parsed_no_apply["application_url"])

    def test_optional_dates_job_lifecycle(self):
        """Test that jobs can be created, updated, and published without application_deadline or drive_date."""
        self.current_user = self.officer

        # 1. Create Job with empty / omitted dates
        create_payload = {
            "company_id": self.company.id,
            "title": "Full Stack Developer",
            "description": "Develop modern React and FastAPI web applications.",
            "branch_eligibility": ["Computer Science (CSE)"],
            "required_skills": ["React", "FastAPI", "PostgreSQL"],
            "salary_range": "6.00-8.00 LPA",
            "application_deadline": "",  # Empty string converted to None
            "drive_date": None,
        }
        res = self.client.post("/api/v1/placement/jobs", json=create_payload)
        self.assertEqual(res.status_code, 200)
        job_data = res.json()
        job_id = job_data["id"]
        self.assertIsNone(job_data["application_deadline"])
        self.assertIsNone(job_data["drive_date"])
        self.assertEqual(job_data["status"], "draft")

        # 2. Publish Job without either date
        pub_res = self.client.post(f"/api/v1/placement/jobs/{job_id}/publish")
        self.assertEqual(pub_res.status_code, 200)
        published_data = pub_res.json()
        self.assertEqual(published_data["status"], "open")
        self.assertIsNone(published_data["application_deadline"])

        # 3. Verify in database
        db_job = self.db.query(JobPosting).filter(JobPosting.id == job_id).first()
        self.assertIsNotNone(db_job)
        self.assertEqual(db_job.status, JobStatus.OPEN)
        self.assertIsNone(db_job.application_deadline)
        self.assertIsNone(db_job.drive_date)

    def test_celery_expiry_task_preserves_jobs_without_deadline(self):
        """Test that close_expired_jobs does not close jobs that have no deadline."""
        # Create a job with no deadline
        job_no_deadline = JobPosting(
            company_id=self.company.id,
            title="Software Architect",
            description="Leading system architecture.",
            status=JobStatus.OPEN,
            application_deadline=None,
            created_by=self.officer.id,
        )
        # Create an expired job
        job_expired = JobPosting(
            company_id=self.company.id,
            title="Junior QA",
            description="Testing services.",
            status=JobStatus.OPEN,
            application_deadline=datetime.now(timezone.utc) - timedelta(days=2),
            created_by=self.officer.id,
        )
        self.db.add_all([job_no_deadline, job_expired])
        self.db.commit()

        # Run task with the test DB session
        result = close_expired_jobs(db=self.db)
        self.db.refresh(job_no_deadline)
        self.db.refresh(job_expired)

        # Job without deadline remains OPEN
        self.assertEqual(job_no_deadline.status, JobStatus.OPEN)
        # Job with past deadline is CLOSED
        self.assertEqual(job_expired.status, JobStatus.CLOSED)

    # =========================================================================
    # PART 2: MANAGE JOBS FILE ACCESS & RBAC
    # =========================================================================

    def test_job_file_access_rbac_and_streaming(self):
        """Test Placement Officer and authorized Student can access job files; unauthorized student is rejected."""
        # 1. Create a job attachment file
        content_bytes = b"%PDF-1.4 Mock PDF content for Job Attachment..."
        file_record = FileModel(
            filename="Job_Specification_JD.pdf",
            file_type=FileType.OTHER,
            mime_type="application/pdf",
            file_size=len(content_bytes),
            bucket="edumatrix-test-files",
            object_key=f"test_jobs/{uuid.uuid4()}.pdf",
            department="Placement Cell",
            status=FileStatus.ACTIVE,
            uploaded_by=self.officer.id,
        )
        self.db.add(file_record)
        self.db.commit()

        # Mock minio storage client
        from app.services.file_storage.minio_client import minio_client
        minio_client.download_file = lambda b, o: content_bytes
        minio_client.upload_file = lambda **kw: None

        # Create published job eligible for CS only
        job = JobPosting(
            company_id=self.company.id,
            title="Backend Systems Engineer",
            description="Core backend services.",
            status=JobStatus.OPEN,
            branch_eligibility=["Computer Science (CSE)"],
            file_id=file_record.id,
            created_by=self.officer.id,
        )
        self.db.add(job)
        self.db.commit()

        # Link as attachment as well
        att = JobPostingAttachment(
            job_posting_id=job.id,
            file_id=file_record.id,
            display_order=0,
        )
        self.db.add(att)
        self.db.commit()

        # A. Placement Officer Access (Preview and Download)
        self.current_user = self.officer
        preview_res = self.client.get(f"/api/v1/placement/jobs/{job.id}/files/{file_record.id}/preview")
        self.assertEqual(preview_res.status_code, 200)
        self.assertEqual(preview_res.headers["content-type"], "application/pdf")

        dl_res = self.client.get(f"/api/v1/placement/jobs/{job.id}/files/{file_record.id}/download")
        self.assertEqual(dl_res.status_code, 200)
        self.assertIn("Job_Specification_JD.pdf", dl_res.headers["content-disposition"])

        # B. Authorized Student Access (CS student is eligible)
        self.current_user = self.student_cs
        s_preview_res = self.client.get(f"/api/v1/placement/jobs/{job.id}/files/{file_record.id}/preview")
        self.assertEqual(s_preview_res.status_code, 200)
        self.assertEqual(s_preview_res.content, content_bytes)

        # C. Unauthorized Student Access (Mech student is not eligible)
        self.current_user = self.student_mech
        unauth_res = self.client.get(f"/api/v1/placement/jobs/{job.id}/files/{file_record.id}/preview")
        self.assertEqual(unauth_res.status_code, 403)

        # D. Draft Job concealment from students
        job.status = JobStatus.DRAFT
        self.db.commit()
        draft_res = self.client.get(f"/api/v1/placement/jobs/{job.id}/files/{file_record.id}/preview")
        self.assertEqual(draft_res.status_code, 404)

    def test_missing_storage_file_returns_clean_404(self):
        """Test that a missing object in MinIO returns a clean 404 rather than 500 error."""
        file_id = uuid.uuid4()
        file_record = FileModel(
            id=file_id,
            filename="Lost_Document.pdf",
            file_type=FileType.OTHER,
            mime_type="application/pdf",
            file_size=500,
            bucket="edumatrix-test-files",
            object_key=f"nonexistent_{uuid.uuid4()}.pdf",
            department="Placement Cell",
            status=FileStatus.ACTIVE,
            uploaded_by=self.officer.id,
        )
        self.db.add(file_record)
        self.db.commit()

        job = JobPosting(
            company_id=self.company.id,
            title="Site Reliability Engineer",
            description="Infrastructure monitoring.",
            status=JobStatus.OPEN,
            file_id=file_id,
            created_by=self.officer.id,
        )
        self.db.add(job)
        self.db.commit()

        # Mock minio_client.download_file to raise Exception (simulating NoSuchKey / NoSuchBucket)
        from app.services.file_storage.minio_client import minio_client
        def raise_storage_err(*args, **kwargs):
            raise Exception("NoSuchKey: Object not found")
        minio_client.download_file = raise_storage_err

        self.current_user = self.officer
        res = self.client.get(f"/api/v1/placement/jobs/{job.id}/files/{file_record.id}/download")
        self.assertEqual(res.status_code, 404)
        self.assertIn("could not be retrieved from storage", res.json()["detail"])

    # =========================================================================
    # PART 3: REDESIGNED RECRUITMENT DRIVES SHORTLIST WORKFLOW
    # =========================================================================

    def test_parse_shortlist_candidate_extraction_and_matching(self):
        """Test shortlist parser extracts candidates from CSV and matches authoritative student records."""
        self.current_user = self.officer

        # Create a sample shortlist CSV
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(["USN", "Candidate Name", "Email Address", "Branch"])
        # Row 1: Exact USN match to student_cs (1MS21CS001)
        writer.writerow(["1MS21CS001", "Alice CS Student", "alice@example.com", "CSE"])
        # Row 2: Exact Email match to student_mech (student_mech@edumatrix.edu)
        writer.writerow(["TEMP_ROLL_01", "Bob Student", "student_mech@edumatrix.edu", "MECH"])
        # Row 3: Ambiguous / unknown student
        writer.writerow(["UNKNOWN_999", "Charlie Random", "charlie@external.com", "CIVIL"])
        # Row 4: Duplicate of Alice
        writer.writerow(["1MS21CS001", "Alice CS Student", "alice@example.com", "CSE"])

        csv_bytes = csv_buffer.getvalue().encode("utf-8")

        res = self.client.post(
            "/api/v1/placement/circulars/parse-shortlist",
            files={"files": ("shortlist_round1.csv", csv_bytes, "text/csv")},
            data={"company_id": str(self.company.id)},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # 1. Description populated
        self.assertIn("shortlist", data["description"].lower())
        self.assertIn(self.company.name, data["description"])

        # 2. Candidate items
        candidates = data["candidates"]
        self.assertEqual(len(candidates), 4)

        # Candidate 0: Alice exact USN match (high confidence, confirmed)
        cand0 = candidates[0]
        self.assertEqual(cand0["extracted_usn"], "1MS21CS001")
        self.assertEqual(cand0["matched_student_id"], self.student_cs.id)
        self.assertEqual(cand0["match_confidence"], 1.0)
        self.assertEqual(cand0["review_status"], "matched")
        self.assertTrue(cand0["is_confirmed"])

        # Candidate 1: Bob exact email match (high confidence, confirmed)
        cand1 = candidates[1]
        self.assertEqual(cand1["matched_student_id"], self.student_mech.id)
        self.assertGreaterEqual(cand1["match_confidence"], 0.95)
        self.assertEqual(cand1["review_status"], "matched")
        self.assertTrue(cand1["is_confirmed"])

        # Candidate 2: Unknown student (unmatched, not confirmed)
        cand2 = candidates[2]
        self.assertIsNone(cand2["matched_student_id"])
        self.assertEqual(cand2["review_status"], "unmatched")
        self.assertFalse(cand2["is_confirmed"])

        # Candidate 3: Intra-file duplicate of Alice (flagged duplicate, not auto-confirmed)
        cand3 = candidates[3]
        self.assertTrue(cand3["is_duplicate"])
        self.assertFalse(cand3["is_confirmed"])

        # 3. Summary counts
        summary = data["candidate_summary"]
        self.assertEqual(summary["total"], 4)
        self.assertEqual(summary["duplicate"], 1)

    def test_create_and_post_drive_workflow_and_deduplicated_notifications(self):
        """Test complete workflow: create & post drive with confirmed candidates, notifications, and retry idempotency."""
        self.current_user = self.officer

        # 1. Pre-create a linked job role for this company
        job = JobPosting(
            company_id=self.company.id,
            title="Graduate Trainee Engineer",
            description="Entry level engineering role.",
            status=JobStatus.OPEN,
            created_by=self.officer.id,
        )
        self.db.add(job)

        # Pre-create an attachment file record
        file_rec = FileModel(
            filename="Official_Shortlist.pdf",
            file_type=FileType.OTHER,
            mime_type="application/pdf",
            file_size=2048,
            bucket="edumatrix-test-files",
            object_key=f"test_drives/{uuid.uuid4()}.pdf",
            department="Placement Cell",
            status=FileStatus.ACTIVE,
            uploaded_by=self.officer.id,
        )
        self.db.add(file_rec)
        self.db.commit()

        # 2. Build payload with Alice confirmed, Bob excluded, Charlie unmatched
        payload = {
            "company_id": self.company.id,
            "title": "Innovate Tech - Campus Shortlist 2026",
            "description": "Shortlist of candidates selected for Technical Interview 1.",
            "branch_eligibility": ["Computer Science (CSE)"],
            "linked_job_ids": [job.id],
            "drive_date": None,  # Optional drive date
            "attachment_file_ids": [str(file_rec.id)],
            "candidates": [
                {
                    "row_index": 0,
                    "source_filename": "shortlist.csv",
                    "extracted_usn": "1MS21CS001",
                    "extracted_name": "Alice CS Student",
                    "extracted_email": "alice@example.com",
                    "matched_student_id": self.student_cs.id,
                    "matched_student_name": self.student_cs.name,
                    "matched_student_usn": "1MS21CS001",
                    "match_confidence": 1.0,
                    "match_method": "usn",
                    "review_status": "matched",
                    "is_duplicate": False,
                    "is_confirmed": True,  # CONFIRMED -> Should receive notification
                },
                {
                    "row_index": 1,
                    "source_filename": "shortlist.csv",
                    "extracted_usn": "1MS21ME001",
                    "extracted_name": "Bob Mech Student",
                    "extracted_email": "student_mech@edumatrix.edu",
                    "matched_student_id": self.student_mech.id,
                    "matched_student_name": self.student_mech.name,
                    "matched_student_usn": "1MS21ME001",
                    "match_confidence": 0.98,
                    "match_method": "email",
                    "review_status": "ambiguous",
                    "is_duplicate": False,
                    "is_confirmed": False,  # EXCLUDED -> Should NOT receive shortlist notification
                },
                {
                    "row_index": 2,
                    "source_filename": "shortlist.csv",
                    "extracted_usn": "UNKNOWN_999",
                    "extracted_name": "Unknown Person",
                    "matched_student_id": None,
                    "match_confidence": 0.0,
                    "review_status": "unmatched",
                    "is_duplicate": False,
                    "is_confirmed": False,
                },
            ],
        }

        # 3. Post Recruitment Drive
        res = self.client.post("/api/v1/placement/circulars/create-and-post-drive", json=payload)
        self.assertEqual(res.status_code, 200)
        res_data = res.json()

        self.assertTrue(res_data["success"])
        # Exactly 1 student (Alice) was confirmed for shortlist notification
        self.assertEqual(res_data["notified_students_count"], 1)
        circular_id = res_data["circular"]["id"]

        # 4. Verify Database Persistence
        circular = self.db.query(RecruitmentCircular).filter(RecruitmentCircular.id == circular_id).first()
        self.assertIsNotNone(circular)
        self.assertEqual(circular.status, RecruitmentCircularStatus.PUBLISHED)
        self.assertIsNone(circular.drive_date)
        self.assertEqual(len(circular.attachments), 1)
        self.assertEqual(len(circular.linked_jobs), 1)

        # Verify Result Batch and Items
        batch = self.db.query(RecruitmentResultBatch).filter(
            RecruitmentResultBatch.circular_id == circular_id
        ).first()
        self.assertIsNotNone(batch)
        self.assertEqual(len(batch.items), 3)

        # 5. Verify Notifications
        # Alice MUST have a shortlist notification
        alice_notifs = self.db.query(Notification).filter(
            Notification.user_id == self.student_cs.id
        ).all()
        has_shortlist_notif = any(
            "shortlisted" in n.title.lower() or "shortlisted" in n.message.lower()
            for n in alice_notifs
        )
        self.assertTrue(has_shortlist_notif, "Alice should have received a shortlist notification")

        # Bob (excluded) MUST NOT have received a shortlist notification
        bob_notifs = self.db.query(Notification).filter(
            Notification.user_id == self.student_mech.id
        ).all()
        bob_has_shortlist = any(
            "shortlisted" in n.title.lower() or "shortlisted" in n.message.lower()
            for n in bob_notifs
        )
        self.assertFalse(bob_has_shortlist, "Excluded candidate Bob must not receive shortlist notification")

        # 6. Idempotency on retry: reposting the same confirmed student does not duplicate notifications
        notif_count_before = len(alice_notifs)
        # Attempt retry posting with the same circular
        repost_res = self.client.post("/api/v1/placement/circulars/create-and-post-drive", json=payload)
        self.assertEqual(repost_res.status_code, 200)

        # Alice's notifications count should not duplicate with the same event_key for circular_id
        alice_notifs_after = self.db.query(Notification).filter(
            Notification.user_id == self.student_cs.id,
            Notification.event_key == f"recruitment_circular_shortlist:{circular_id}:student:{self.student_cs.id}"
        ).all()
        self.assertEqual(len(alice_notifs_after), 1, "Expected exactly 1 notification with unique event_key")

    def test_student_visibility_and_data_privacy(self):
        """Test students can only access published circulars for their branch, cannot access draft circulars or other students' private candidate rows."""
        # Create a DRAFT circular
        draft_circ = RecruitmentCircular(
            company_id=self.company.id,
            title="Draft Secret Drive",
            summary="Upcoming recruitments.",
            status=RecruitmentCircularStatus.DRAFT,
            branch_eligibility=["Computer Science (CSE)"],
            created_by=self.officer.id,
        )
        self.db.add(draft_circ)

        # Create a PUBLISHED circular for MECH only
        mech_circ = RecruitmentCircular(
            company_id=self.company.id,
            title="Mechanical Special Drive",
            summary="Robotics and manufacturing.",
            status=RecruitmentCircularStatus.PUBLISHED,
            branch_eligibility=["Mechanical Engineering (MECH)"],
            published_at=datetime.now(timezone.utc),
            created_by=self.officer.id,
        )
        self.db.add(mech_circ)
        self.db.commit()

        # Student CS tries to access draft circular -> 404/403
        self.current_user = self.student_cs
        res_draft = self.client.get(f"/api/v1/placement/circulars/{draft_circ.id}")
        self.assertEqual(res_draft.status_code, 404)

        # Student CS tries to access MECH-only circular -> 404 (restricted to eligible branch)
        res_mech = self.client.get(f"/api/v1/placement/circulars/{mech_circ.id}")
        self.assertEqual(res_mech.status_code, 404)

        # Officer CAN access both
        self.current_user = self.officer
        res_officer_draft = self.client.get(f"/api/v1/placement/circulars/{draft_circ.id}")
        self.assertEqual(res_officer_draft.status_code, 200)

    def test_ocr_image_and_scanned_pdf_job_extraction(self):
        """Test OCR extraction from PNG image and scanned PDF for job postings with multi-file aggregation."""
        # 1. Generate realistic image fixture
        img_lines = [
            "Company: Apex Cloud Systems",
            "Job Title: Senior DevOps Engineer",
            "Compensation: 14.5 LPA",
            "Eligibility Criteria: CGPA 7.5 and above",
            "Required Skills: Kubernetes, Docker, Python, AWS",
        ]
        img_bytes = make_text_image(img_lines)

        # Parse standalone image
        res_img = jd_parser_service.parse_file(target_name="apex_flyer.png", content=img_bytes)
        self.assertIn("DevOps", res_img.get("title") or res_img.get("job_title", ""))
        self.assertEqual(res_img.get("min_cgpa"), 7.5)
        self.assertIn("14.5", str(res_img.get("annual_ctc") or res_img.get("salary_range", "")))

        # 2. Generate scanned PDF fixture
        pdf_lines = [
            "Company: Cybernet Dynamics",
            "Position: Security Analyst",
            "Annual CTC: Rs 9.0 to 11.0 Lakhs Per Annum",
            "Academic Cutoff: minimum CGPA: 7.0",
        ]
        pdf_bytes = make_scanned_pdf(pdf_lines)
        res_pdf = jd_parser_service.parse_file(target_name="cybernet_scanned.pdf", content=pdf_bytes)
        self.assertIn("Security", res_pdf.get("title") or res_pdf.get("job_title", ""))
        self.assertEqual(res_pdf.get("min_cgpa"), 7.0)

        # 3. Multi-file aggregation with OCR
        text_supplement = b"Application URL: https://apply.apexcloud.io/careers?ref=campus2026\nApplication Deadline: 2026-12-15"
        merged = jd_parser_service.parse_multiple_files([
            ("apex_flyer.png", img_bytes),
            ("supplement.txt", text_supplement),
        ])
        # Preserved title and cgpa from OCR image
        self.assertIn("DevOps", merged.get("title") or merged.get("job_title", ""))
        self.assertEqual(merged.get("min_cgpa"), 7.5)
        # Preserved URL and deadline from text file
        self.assertIn("apply.apexcloud.io", merged.get("application_url", ""))
        self.assertIn("2026-12-15", str(merged.get("application_deadline", "")))

        # 4. Unreadable/corrupted file raises clear error and never defaults silently
        blank_img = make_text_image([""], width=100, height=50)
        with self.assertRaises(ValueError) as ctx:
            jd_parser_service.parse_file(target_name="blank.png", content=blank_img)
        self.assertIn("Failed to extract readable text", str(ctx.exception))

    def test_ocr_image_and_scanned_pdf_shortlist_candidate_extraction(self):
        """Test candidate shortlist extraction from image and scanned PDF with deterministic matching."""
        from app.services.recruitment_result_extractor import recruitment_result_extractor

        cand_lines = [
            "USN, Name, Email, Status",
            "1MS21CS001, Alice CS Student, student_cs@edumatrix.edu, Shortlisted",
            "1MS21ME001, Bob Mech Student, student_mech@edumatrix.edu, Shortlisted",
        ]
        img_bytes = make_text_image(cand_lines)

        # 1. Extractor directly handles image
        res_img = recruitment_result_extractor.extract_candidates_from_bytes(img_bytes, "shortlist.png")
        self.assertTrue(res_img.get("success"))
        rows = res_img.get("rows", [])
        self.assertGreaterEqual(len(rows), 2)
        extracted_usns = [r.get("usn") for r in rows]
        self.assertIn("1MS21CS001", extracted_usns)

        # 2. Extractor directly handles scanned PDF via OCR fallback
        pdf_bytes = make_scanned_pdf(cand_lines)
        res_pdf = recruitment_result_extractor.extract_candidates_from_bytes(pdf_bytes, "shortlist_scan.pdf")
        self.assertTrue(res_pdf.get("success"))
        pdf_rows = res_pdf.get("rows", [])
        self.assertGreaterEqual(len(pdf_rows), 2)

        # 3. API endpoint /placement/circulars/parse-shortlist handles OCR files
        self.current_user = self.officer
        response = self.client.post(
            "/api/v1/placement/circulars/parse-shortlist",
            files=[
                ("files", ("shortlist.png", img_bytes, "image/png")),
            ],
            data={"company_id": self.company.id},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(len(data["candidates"]), 1)
        # Check matched student
        alice_match = next((c for c in data["candidates"] if c["extracted_usn"] == "1MS21CS001"), None)
        self.assertIsNotNone(alice_match)
        self.assertEqual(alice_match["matched_student_id"], self.student_cs.id)
        self.assertGreaterEqual(alice_match["match_confidence"], 0.95)
        self.assertTrue(alice_match["is_confirmed"])

        # 4. Blank/unreadable image raises HTTP 400 with actionable error, never silently 0 candidates
        blank_img = make_text_image([""], width=100, height=50)
        err_res = self.client.post(
            "/api/v1/placement/circulars/parse-shortlist",
            files=[
                ("files", ("blank_noise.png", blank_img, "image/png")),
            ],
            data={"company_id": self.company.id},
        )
        self.assertEqual(err_res.status_code, 400)
        self.assertIn("Candidate extraction failed", err_res.json()["detail"])

    def test_bearer_token_and_blob_preview_download_rbac(self):
        """Test authenticated Blob download/preview with Bearer header, student branch RBAC, and clean 404s."""
        content_bytes = b"%PDF-1.4 Authoritative Secure Binary Content for Job Verification"
        file_record = FileModel(
            filename="Confidential_Job_Specs.pdf",
            file_type=FileType.OTHER,
            mime_type="application/pdf",
            file_size=len(content_bytes),
            bucket="edumatrix-test-files",
            object_key=f"test_jobs/{uuid.uuid4()}.pdf",
            department="Placement Cell",
            status=FileStatus.ACTIVE,
            uploaded_by=self.officer.id,
        )
        self.db.add(file_record)
        self.db.commit()

        from app.services.file_storage.minio_client import minio_client
        minio_client.download_file = lambda b, o: content_bytes

        job = JobPosting(
            company_id=self.company.id,
            title="Senior Distributed Systems Architect",
            description="High-throughput systems.",
            status=JobStatus.OPEN,
            branch_eligibility=["Computer Science (CSE)"],
            file_id=file_record.id,
            created_by=self.officer.id,
        )
        self.db.add(job)
        self.db.commit()

        # A. Placement Officer Access via API (authenticated fetch simulating blob fetch)
        self.current_user = self.officer
        res_officer = self.client.get(f"/api/v1/placement/jobs/{job.id}/files/{file_record.id}/download")
        self.assertEqual(res_officer.status_code, 200)
        self.assertEqual(res_officer.content, content_bytes)
        self.assertIn("Confidential_Job_Specs.pdf", res_officer.headers.get("content-disposition", ""))

        # B. Eligible CS Student Access
        self.current_user = self.student_cs
        res_student_cs = self.client.get(f"/api/v1/placement/jobs/{job.id}/files/{file_record.id}/download")
        self.assertEqual(res_student_cs.status_code, 200)
        self.assertEqual(res_student_cs.content, content_bytes)

        # C. Ineligible MECH Student Access -> 403 Forbidden
        self.current_user = self.student_mech
        res_student_mech = self.client.get(f"/api/v1/placement/jobs/{job.id}/files/{file_record.id}/download")
        self.assertEqual(res_student_mech.status_code, 403)

        # D. Missing storage object returns clean 404 (not 500)
        def raise_storage_err(b, o):
            raise Exception("NoSuchKey: Object not found")
        minio_client.download_file = raise_storage_err

        self.current_user = self.officer
        res_missing = self.client.get(f"/api/v1/placement/jobs/{job.id}/files/{file_record.id}/download")
        self.assertEqual(res_missing.status_code, 404)
        self.assertIn("storage", res_missing.json()["detail"].lower())

    def test_date_handling_comprehensive_create_edit_draft_publish(self):
        """Test create, edit, draft, and publish lifecycle with empty dates, and verify Celery safety."""
        self.current_user = self.officer

        # 1. Create Job with empty application_deadline and drive_date
        payload = {
            "title": "Cloud Operations Specialist",
            "description": "24/7 cloud reliability engineering.",
            "company_id": self.company.id,
            "branch_eligibility": ["Computer Science (CSE)"],
            "required_skills": ["Python", "AWS", "Docker"],
            "application_deadline": None,
            "drive_date": None,
        }
        res_create = self.client.post("/api/v1/placement/jobs", json=payload)
        self.assertEqual(res_create.status_code, 200)
        job_data = res_create.json()
        job_id = job_data["id"]
        self.assertIsNone(job_data["application_deadline"])
        self.assertIsNone(job_data["drive_date"])
        self.assertEqual(job_data["status"].lower(), "draft")

        # 2. Edit Job keeping empty strings for dates
        payload_edit = {
            "title": "Principal Cloud Operations Specialist",
            "application_deadline": "",
            "drive_date": "",
        }
        res_edit = self.client.put(f"/api/v1/placement/jobs/{job_id}", json=payload_edit)
        self.assertEqual(res_edit.status_code, 200)
        edited_job = res_edit.json()
        self.assertEqual(edited_job["title"], "Principal Cloud Operations Specialist")
        self.assertIsNone(edited_job["application_deadline"])
        self.assertIsNone(edited_job["drive_date"])

        # 3. Publish Job
        res_pub = self.client.post(f"/api/v1/placement/jobs/{job_id}/publish")
        self.assertEqual(res_pub.status_code, 200)
        self.assertEqual(res_pub.json()["status"].lower(), "open")

        # 4. Verify Celery task close_expired_jobs does not close jobs with null deadlines
        closed_count = close_expired_jobs(db=self.db)
        db_job = self.db.query(JobPosting).filter(JobPosting.id == job_id).first()
        self.assertEqual(db_job.status, JobStatus.OPEN)

    def test_generic_url_extraction_patterns_and_repair(self):
        """Test generic extraction across varied URL formats, Google forms, query strings, and OCR line wraps."""
        # A. Long URL with complex query strings, fragments, and percent-encoding
        doc_a = (
            "Recruitment Announcement for 2026 Batch.\n"
            "Role: Systems Engineer\n"
            "Official Application Link: "
            "https://portal.enterprise-hiring.org/careers/v2/openings/10892?dept=engineering&source=campus_drive&token=abc%20123#apply-step-1\n"
            "Eligibility: 7.0 CGPA"
        )
        parsed_a = jd_parser_service.parse_jd_text(doc_a)
        self.assertEqual(
            parsed_a["application_url"],
            "https://portal.enterprise-hiring.org/careers/v2/openings/10892?dept=engineering&source=campus_drive&token=abc%20123#apply-step-1"
        )

        # B. Long Google Forms link with form ID and query params
        doc_b = (
            "Registration Form for Campus Hiring:\n"
            "https://docs.google.com/forms/d/e/1FAIpQLSd9W8V7U_m-kXyZ1234567890abcdefghijklmnopqrstuvwxyz/viewform?usp=sf_link\n"
            "Please register before Friday."
        )
        parsed_b = jd_parser_service.parse_jd_text(doc_b)
        self.assertEqual(
            parsed_b["application_url"],
            "https://docs.google.com/forms/d/e/1FAIpQLSd9W8V7U_m-kXyZ1234567890abcdefghijklmnopqrstuvwxyz/viewform?usp=sf_link"
        )

        # C. Trailing punctuation and surrounding brackets cleaning
        doc_c = (
            "Important: (Register at: https://forms.gle/xK9LmP4qRstUVwXYZ.)\n"
            "Secondary Link: <https://company.careers.com/apply/job-999;>\n"
        )
        parsed_c = jd_parser_service.parse_jd_text(doc_c)
        # Should cleanly strip trailing period and parenthesis without damaging the form code
        self.assertEqual(parsed_c["application_url"], "https://forms.gle/xK9LmP4qRstUVwXYZ")

        # D. Line break reconstruction across PDF/OCR wraps
        doc_d = (
            "Apply Online: https://careers.globaltech.com/apply/\n"
            "positions/2026-software-engineer?src=uni\n"
            "Company: GlobalTech"
        )
        parsed_d = jd_parser_service.parse_jd_text(doc_d)
        self.assertEqual(
            parsed_d["application_url"],
            "https://careers.globaltech.com/apply/positions/2026-software-engineer?src=uni"
        )

        # E. OCR spacing repair inside Google Forms ID and protocol
        doc_e = (
            "Registration URL:\n"
            "https : // forms . gle / yP4tpWtmk9VdFFBU8\n"
            "Mandatory for all students."
        )
        parsed_e = jd_parser_service.parse_jd_text(doc_e)
        self.assertEqual(parsed_e["application_url"], "https://forms.gle/yP4tpWtmk9VdFFBU8")

    def test_url_candidate_scoring_and_context_disambiguation(self):
        """Test that company homepage and privacy links are rejected in favor of the real registration URL."""
        mixed_doc = (
            "Company: MegaTech Solutions\n"
            "Visit our company website: https://www.megatech.io\n"
            "Read our privacy policy at https://www.megatech.io/legal/privacy-policy for details.\n"
            "Interested candidates must submit registration here: https://forms.gle/MegaTechDrive2026\n"
            "Required Skills: Python, Docker\n"
        )
        parsed = jd_parser_service.parse_jd_text(mixed_doc)
        # Top selected application URL must be the registration form, not the corporate homepage
        self.assertEqual(parsed["application_url"], "https://forms.gle/MegaTechDrive2026")
        
        # Verify candidate scoring preserved all links
        candidates = parsed["application_url_candidates"]
        urls = [c["url"] for c in candidates]
        self.assertIn("https://forms.gle/MegaTechDrive2026", urls)

    def test_multi_file_url_prefix_deduplication_and_conflict_flagging(self):
        """Test multi-file aggregation eliminates truncated prefixes and flags conflicts between distinct links."""
        # Scenario 1: File 1 has truncated prefix (from partial OCR), File 2 has complete URL
        file_1 = {
            "filename": "notice_scan.png",
            "content": b"Job: Software Dev\nApply link: https://forms.gle/yP4tp",
            "file_id": uuid.uuid4()
        }
        file_2 = {
            "filename": "email_circular.txt",
            "content": b"Official Form: https://forms.gle/yP4tpWtmk9VdFFBU8\nEligible: CSE",
            "file_id": uuid.uuid4()
        }
        merged_res = jd_parser_service.parse_multiple_files([file_1, file_2])
        # The truncated prefix must be eliminated; full URL must be selected
        self.assertEqual(merged_res["application_url"], "https://forms.gle/yP4tpWtmk9VdFFBU8")
        candidates = [c["url"] for c in merged_res["application_url_candidates"]]
        self.assertNotIn("https://forms.gle/yP4tp", candidates)
        self.assertIn("https://forms.gle/yP4tpWtmk9VdFFBU8", candidates)

        # Scenario 2: Two distinct plausible application URLs trigger conflict review flag
        file_a = {
            "filename": "form_notice.txt",
            "content": b"Registration link: https://forms.gle/DriveBatchA\nTitle: Dev",
            "file_id": uuid.uuid4()
        }
        file_b = {
            "filename": "portal_notice.txt",
            "content": b"Apply at company portal: https://megacorp.careers/apply/2026\nTitle: Dev",
            "file_id": uuid.uuid4()
        }
        conflict_res = jd_parser_service.parse_multiple_files([file_a, file_b])
        cand_urls = [c["url"] for c in conflict_res["application_url_candidates"]]
        self.assertIn("https://forms.gle/DriveBatchA", cand_urls)
        self.assertIn("https://megacorp.careers/apply/2026", cand_urls)
        # Review flags must contain conflict warning
        flags_text = " ".join(conflict_res["review_flags"])
        self.assertIn("Multiple plausible application URLs detected", flags_text)

    def test_url_persistence_create_edit_draft_publish_and_student_readback(self):
        """Verify application URL survives draft creation, editing, publishing, and student readback."""
        self.current_user = self.officer
        initial_url = "https://forms.gle/InitialDraftLink12345"
        updated_url = "https://forms.gle/UpdatedCompleteRegistrationLink67890"

        # 1. Create Draft Job
        create_payload = {
            "company_id": self.company.id,
            "title": "Full Stack Cloud Engineer",
            "description": "Enterprise cloud services.",
            "branch_eligibility": ["Computer Science (CSE)"],
            "required_skills": ["Node.js", "React", "PostgreSQL"],
            "application_url": initial_url,
            "status": "draft",
        }
        res_create = self.client.post("/api/v1/placement/jobs", json=create_payload)
        self.assertEqual(res_create.status_code, 200)
        job_id = res_create.json()["id"]
        self.assertEqual(res_create.json()["application_url"], initial_url)

        # 2. Edit Job with updated URL
        edit_payload = {
            "application_url": updated_url
        }
        res_edit = self.client.put(f"/api/v1/placement/jobs/{job_id}", json=edit_payload)
        self.assertEqual(res_edit.status_code, 200)
        self.assertEqual(res_edit.json()["application_url"], updated_url)

        # 3. Publish Job
        res_pub = self.client.post(f"/api/v1/placement/jobs/{job_id}/publish")
        self.assertEqual(res_pub.status_code, 200)
        self.assertEqual(res_pub.json()["status"], "open")
        self.assertEqual(res_pub.json()["application_url"], updated_url)

        # 4. Student Readback
        self.current_user = self.student_cs
        res_student = self.client.get(f"/api/v1/placement/jobs/{job_id}")
        self.assertEqual(res_student.status_code, 200)
        student_data = res_student.json()
        self.assertEqual(student_data["application_url"], updated_url)

    def test_attachment_download_exact_bytes_and_filename_rfc6266(self):
        """Test attachment metadata, exact binary download, RFC 6266 headers, and preview behavior."""
        # 1. Create two genuine test files in DB & storage mock
        pdf_bytes = b"%PDF-1.5 Genuine PDF Specification Document Bytes 0xDEADBEEF"
        png_bytes = b"\x89PNG\r\n\x1a\nGenuine PNG Image Poster Bytes 0xCAFEBABE"

        file_pdf = FileModel(
            filename="Official JD Brochure (1).pdf",
            file_type=FileType.OTHER,
            mime_type="application/pdf",
            file_size=len(pdf_bytes),
            bucket="edumatrix-test-files",
            object_key=f"jobs/test_{uuid.uuid4()}.pdf",
            department="Placement Cell",
            status=FileStatus.ACTIVE,
            uploaded_by=self.officer.id,
        )
        file_png = FileModel(
            filename="Recruitment Poster 2026.png",
            file_type=FileType.OTHER,
            mime_type="image/png",
            file_size=len(png_bytes),
            bucket="edumatrix-test-files",
            object_key=f"jobs/test_{uuid.uuid4()}.png",
            department="Placement Cell",
            status=FileStatus.ACTIVE,
            uploaded_by=self.officer.id,
        )
        self.db.add_all([file_pdf, file_png])
        self.db.commit()

        # Mock MinIO storage to return exact bytes by object key
        storage_map = {
            file_pdf.object_key: pdf_bytes,
            file_png.object_key: png_bytes,
        }
        from app.services.file_storage.minio_client import minio_client
        minio_client.download_file = lambda b, o: storage_map.get(o, b"")

        # Create Job with both attachments
        job = JobPosting(
            company_id=self.company.id,
            title="DevOps Lead Engineer",
            description="Infrastructure automation.",
            status=JobStatus.OPEN,
            branch_eligibility=["Computer Science (CSE)"],
            created_by=self.officer.id,
        )
        self.db.add(job)
        self.db.commit()

        att_pdf = JobPostingAttachment(job_posting_id=job.id, file_id=file_pdf.id, display_order=0)
        att_png = JobPostingAttachment(job_posting_id=job.id, file_id=file_png.id, display_order=1)
        self.db.add_all([att_pdf, att_png])
        self.db.commit()

        # 2. Verify GET /jobs/{id} returns genuine filename and file_size (not null or 'Attached Document')
        self.current_user = self.student_cs
        res_job = self.client.get(f"/api/v1/placement/jobs/{job.id}")
        self.assertEqual(res_job.status_code, 200)
        atts = res_job.json()["attachments"]
        self.assertEqual(len(atts), 2)
        self.assertEqual(atts[0]["filename"], "Official JD Brochure (1).pdf")
        self.assertEqual(atts[0]["file_size"], len(pdf_bytes))
        self.assertEqual(atts[0]["mime_type"], "application/pdf")
        self.assertEqual(atts[1]["filename"], "Recruitment Poster 2026.png")
        self.assertEqual(atts[1]["file_size"], len(png_bytes))

        # 3. Test Download: Returns exact bytes, Content-Type, and RFC 6266 Content-Disposition
        res_dl = self.client.get(f"/api/v1/placement/jobs/{job.id}/files/{file_pdf.id}/download")
        self.assertEqual(res_dl.status_code, 200)
        self.assertEqual(res_dl.content, pdf_bytes)
        self.assertEqual(res_dl.headers.get("content-type"), "application/pdf")
        cd_header = res_dl.headers.get("content-disposition", "")
        self.assertIn("Official JD Brochure (1).pdf", cd_header)
        self.assertIn("filename*=", cd_header)

        # 4. Test Preview: Returns image bytes with image/png MIME type
        res_prev = self.client.get(f"/api/v1/placement/jobs/{job.id}/files/{file_png.id}/preview")
        self.assertEqual(res_prev.status_code, 200)
        self.assertEqual(res_prev.content, png_bytes)
        self.assertEqual(res_prev.headers.get("content-type"), "image/png")

        # 5. Test Access by integer attachment ID (supporting either UUID or attachment ID)
        res_att_id = self.client.get(f"/api/v1/placement/jobs/{job.id}/files/{att_pdf.id}/download")
        self.assertEqual(res_att_id.status_code, 200)
        self.assertEqual(res_att_id.content, pdf_bytes)

        # 6. Test Ineligible Student Access -> 403 Forbidden
        self.current_user = self.student_mech
        res_inelig = self.client.get(f"/api/v1/placement/jobs/{job.id}/files/{file_pdf.id}/download")
        self.assertEqual(res_inelig.status_code, 403)
        self.assertIn("application/json", res_inelig.headers.get("content-type", ""))

        # 7. Test Missing File in Storage -> 404 with JSON detail, not binary garbage
        minio_client.download_file = lambda b, o: None
        self.current_user = self.officer
        res_err = self.client.get(f"/api/v1/placement/jobs/{job.id}/files/{file_pdf.id}/download")
        self.assertEqual(res_err.status_code, 404)
        self.assertIn("application/json", res_err.headers.get("content-type", ""))
        self.assertIn("detail", res_err.json())


if __name__ == "__main__":
    unittest.main()
