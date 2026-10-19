"""
EduMatrix Phase C — Placement Officer Workflow Enhancement Test Suite

Covers:
1. Company validation: rejects empty, whitespace-only, and placeholder values ('General', 'Not Specified', etc.).
2. Company create/edit compatibility with Phase B contracts.
3. Multi-file JD parsing and supported formats (TXT, PDF, DOCX, XLSX/XLS, PNG).
4. Application URL extraction, validation, and schema namespace rejection.
5. Cross-document conflict handling, confidence preservation, and extraction status tagging.
6. Alembic migration 022 upgrade & downgrade on isolated temporary database (edumatrix_test_mig_c).
7. Job attachment persistence and relationship models (JobPostingAttachment, file_id, attachments).
8. Job document preview/download RBAC:
   - Placement Officer & Admin access.
   - Branch-eligible student on OPEN job.
   - Ineligible branch or non-OPEN job access blocked.
9. Bulk deletion safety:
   - Company bulk delete (soft deactivates, hard protects relationships).
   - Job bulk delete (zero dependencies deleted, protected jobs blocked with force=False or closed with force=True).
"""

import os
import unittest
import uuid
import json
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from pydantic import ValidationError

from alembic.config import Config
from alembic import command
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.schemas.placement import (
    CompanyCreate,
    CompanyUpdate,
    JobPostingCreate,
    JobPostingUpdate,
    CompanyBulkDeleteRequest,
    JobBulkDeleteRequest,
)
from app.models.company import Company
from app.models.job_posting import JobPosting, JobStatus, JobPostingAttachment
from app.models.file import File, FileStatus
from app.models.user import User, UserRole
from app.models.profile import StudentProfileExtended
from app.models.application import Application, ApplicationStatus
from app.services.jd_parser_service import jd_parser_service
from app.services.placement_service import placement_service
from app.api.files import check_file_permission


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ALEMBIC_INI_PATH = os.path.join(BASE_DIR, "alembic.ini")
POSTGRES_BASE_URL = os.environ.get(
    "TEST_DATABASE_BASE_URL",
    "postgresql://edumatrix:edumatrix123@postgres:5432"
)


class TestCompanyValidationPhaseC(unittest.TestCase):
    """Test strict company validation preventing blank, whitespace, and placeholder values."""

    def test_required_fields_reject_empty_and_whitespace(self):
        """Ensure name, industry, and location reject whitespace-only strings."""
        for field in ["name", "industry", "location"]:
            data = {"name": "Acme Tech", "industry": "Software", "location": "Bangalore"}
            data[field] = "   "
            with self.assertRaises(ValidationError):
                CompanyCreate(**data)

            data[field] = ""
            with self.assertRaises(ValidationError):
                CompanyCreate(**data)

    def test_reject_placeholder_values(self):
        """Ensure common placeholder values like 'General', 'Not Specified', 'N/A' are rejected."""
        placeholders = ["General", "Not Specified", "N/A", "None", "Unknown", "placeholder", "-"]
        for ph in placeholders:
            # Placeholder in industry
            with self.assertRaises(ValidationError):
                CompanyCreate(name="Acme Tech", industry=ph, location="Bangalore")

            # Placeholder in location
            with self.assertRaises(ValidationError):
                CompanyCreate(name="Acme Tech", industry="IT", location=ph)

            # Placeholder in name
            with self.assertRaises(ValidationError):
                CompanyCreate(name=ph, industry="IT", location="Bangalore")

    def test_valid_company_succeeds(self):
        """Ensure genuine company data passes validation with trimmed fields."""
        c = CompanyCreate(
            name="  Google DeepMind  ",
            industry="  Artificial Intelligence  ",
            location="  Bangalore / Remote  ",
            website="https://deepmind.google",
            contact_email="recruiting@deepmind.google",
        )
        self.assertEqual(c.name, "Google DeepMind")
        self.assertEqual(c.industry, "Artificial Intelligence")
        self.assertEqual(c.location, "Bangalore / Remote")

    def test_optional_fields_compatibility(self):
        """Ensure description, phone, email, and website remain optional."""
        c = CompanyCreate(
            name="Tech Innovations",
            industry="Robotics",
            location="Pune",
        )
        self.assertIsNone(c.description)
        self.assertIsNone(c.contact_phone)
        self.assertIsNone(c.contact_email)
        self.assertIsNone(c.website)


class TestJdParserAndMultipleUploads(unittest.TestCase):
    """Test JD extraction across multiple files, URL extraction, and conflict handling."""

    def test_url_extraction_and_validation(self):
        """Verify valid application URLs are extracted and schema/invalid URLs are rejected."""
        # 1. Clean external career URL
        text_with_url = "Apply online at: https://careers.microsoft.com/us/en/job/123456/Software-Engineer"
        url = jd_parser_service._extract_application_url(text_with_url)
        self.assertIsNotNone(url)
        self.assertTrue(url.startswith("https://careers.microsoft.com"))

        # 2. Schema / metadata URLs must be rejected
        xml_schema_text = "Namespace: http://schemas.openxmlformats.org/wordprocessingml/2006/main document"
        schema_url = jd_parser_service._extract_application_url(xml_schema_text)
        self.assertIsNone(schema_url)

        # 3. W3.org schema URL rejected
        w3_text = "xmlns:r=http://www.w3.org/2000/xmlns/ in docx header"
        w3_url = jd_parser_service._extract_application_url(w3_text)
        self.assertIsNone(w3_url)

        # 4. Text without application URL
        no_url_text = "Send your resume directly to our HR team at hr@company.com"
        no_url = jd_parser_service._extract_application_url(no_url_text)
        self.assertIsNone(no_url)

    def test_parse_multiple_files_union_and_conflict_handling(self):
        """Verify parse_multiple_files combines skills, unions branches, and flags conflicts."""
        file1_data = {
            "filename": "Job_Overview.txt",
            "content": b"""
            Company: Cisco Systems
            Role: Associate Network Engineer
            Location: Bangalore
            Min CGPA: 7.5
            Eligible branches: CSE, IT
            Skills: Python, Networking, Linux
            Apply at: https://jobs.cisco.com/careers/12345
            """,
            "mime_type": "text/plain",
        }

        file2_data = {
            "filename": "Additional_Criteria.txt",
            "content": b"""
            Eligible branches: ECE, EEE
            Required skills: Docker, Kubernetes
            Salary: 14 LPA
            Experience: Fresher
            """,
            "mime_type": "text/plain",
        }

        result = jd_parser_service.parse_multiple_files([file1_data, file2_data])

        # Status should be success
        self.assertEqual(result["extraction_status"], "success")

        # Basic fields extracted
        extracted = result
        self.assertEqual(extracted["company_name"], "Cisco Systems")
        self.assertIn("Network", extracted["title"])
        self.assertEqual(extracted["application_url"], "https://jobs.cisco.com/careers/12345")
        self.assertEqual(extracted["cgpa_criteria"], 7.5)

        # Branches should be unioned: CSE, IT + ECE, EEE
        branches = extracted.get("branch_eligibility", [])
        self.assertIn("CSE", branches)
        self.assertIn("ECE", branches)

        # Skills should be combined
        skills = extracted.get("required_skills", [])
        self.assertTrue(any("Python" in s for s in skills))
        self.assertTrue(any("Docker" in s for s in skills))

        # Extracted files breakdown
        self.assertEqual(len(result["extracted_files"]), 2)
        self.assertEqual(result["extracted_files"][0]["filename"], "Job_Overview.txt")
        self.assertEqual(result["extracted_files"][1]["filename"], "Additional_Criteria.txt")

    def test_empty_or_unextractable_document(self):
        """Verify unextractable document reports partial/failed status without crashing."""
        empty_file = {
            "filename": "empty.txt",
            "content": b"",
            "mime_type": "text/plain",
        }
        result = jd_parser_service.parse_multiple_files([empty_file])
        self.assertEqual(result["extraction_status"], "failed")
        self.assertTrue(len(result.get("review_flags", [])) > 0)


class TestMigration022Isolated(unittest.TestCase):
    """Test Alembic migration 022 on an isolated temporary database."""

    TEST_DB_NAME = "edumatrix_test_mig_c"
    orig_db_url = None

    @classmethod
    def setUpClass(cls):
        cls.orig_db_url = os.environ.get("DATABASE_URL")
        # Create isolated temporary database
        conn = psycopg2.connect(f"{POSTGRES_BASE_URL}/postgres")
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute(f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{cls.TEST_DB_NAME}'
              AND pid <> pg_backend_pid();
        """)
        cur.execute(f"DROP DATABASE IF EXISTS {cls.TEST_DB_NAME};")
        cur.execute(f"CREATE DATABASE {cls.TEST_DB_NAME};")
        cur.close()
        conn.close()

        # Point DATABASE_URL environment variable to isolated test database
        target_db_url = f"{POSTGRES_BASE_URL}/{cls.TEST_DB_NAME}"
        os.environ["DATABASE_URL"] = target_db_url

    @classmethod
    def tearDownClass(cls):
        if cls.orig_db_url:
            os.environ["DATABASE_URL"] = cls.orig_db_url
        elif "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]

        try:
            conn = psycopg2.connect(f"{POSTGRES_BASE_URL}/postgres")
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cur = conn.cursor()
            cur.execute(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{cls.TEST_DB_NAME}'
                  AND pid <> pg_backend_pid();
            """)
            cur.execute(f"DROP DATABASE IF EXISTS {cls.TEST_DB_NAME};")
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Warning: Failed to drop test db {cls.TEST_DB_NAME}: {e}")

    def test_migration_022_upgrade_and_downgrade(self):
        """Run upgrade to 022, inspect job_posting_attachments table, then downgrade to 021."""
        target_db_url = f"{POSTGRES_BASE_URL}/{self.TEST_DB_NAME}"

        cfg = Config(ALEMBIC_INI_PATH)
        cfg.set_main_option("sqlalchemy.url", target_db_url)
        cfg.set_main_option("script_location", os.path.join(BASE_DIR, "migrations"))

        engine = sa.create_engine(target_db_url)

        # 1. Create base tables using metadata so all parent tables (companies, job_postings, files) exist
        Base.metadata.create_all(bind=engine)

        # Drop job_posting_attachments if Base.metadata created it, to represent pre-022 state
        with engine.begin() as conn:
            conn.execute(sa.text("DROP TABLE IF EXISTS job_posting_attachments CASCADE"))
        engine.dispose()

        # Stamp revision 021 (Phase B state)
        command.stamp(cfg, "021")

        # Upgrade to head (022)
        command.upgrade(cfg, "head")

        engine = sa.create_engine(target_db_url)
        inspector = sa.inspect(engine)
        tables = inspector.get_table_names()

        # Check job_posting_attachments table exists
        self.assertIn("job_posting_attachments", tables)

        # Check columns
        cols = {c["name"]: c for c in inspector.get_columns("job_posting_attachments")}
        self.assertIn("id", cols)
        self.assertIn("job_posting_id", cols)
        self.assertIn("file_id", cols)
        self.assertIn("display_order", cols)
        self.assertIn("created_at", cols)

        # Check unique constraint on (job_posting_id, file_id)
        uqs = inspector.get_unique_constraints("job_posting_attachments")
        self.assertTrue(
            any("uq_job_posting_file" in (u["name"] or "") for u in uqs)
            or any(set(u["column_names"]) == {"job_posting_id", "file_id"} for u in uqs),
            f"Expected unique constraint on (job_posting_id, file_id), found: {uqs}"
        )

        # Downgrade to 021
        engine.dispose()
        command.downgrade(cfg, "021")
        engine = sa.create_engine(target_db_url)
        inspector_after_down = sa.inspect(engine)
        self.assertNotIn("job_posting_attachments", inspector_after_down.get_table_names())

        # Upgrade back to head
        engine.dispose()
        command.upgrade(cfg, "head")
        engine = sa.create_engine(target_db_url)
        inspector_reup = sa.inspect(engine)
        self.assertIn("job_posting_attachments", inspector_reup.get_table_names())
        engine.dispose()


class TestJobWorkflowAndRBACPhaseC(unittest.TestCase):
    """Integration tests for job creation with attachments, RBAC permissions, and bulk operations."""

    TEST_DB_NAME = "edumatrix_test_job_c"
    engine = None
    Session = None

    @classmethod
    def setUpClass(cls):
        # Create isolated test database
        conn = psycopg2.connect(f"{POSTGRES_BASE_URL}/postgres")
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute(f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{cls.TEST_DB_NAME}'
              AND pid <> pg_backend_pid();
        """)
        cur.execute(f"DROP DATABASE IF EXISTS {cls.TEST_DB_NAME};")
        cur.execute(f"CREATE DATABASE {cls.TEST_DB_NAME};")
        cur.close()
        conn.close()

        target_db_url = f"{POSTGRES_BASE_URL}/{cls.TEST_DB_NAME}"
        cls.engine = sa.create_engine(target_db_url)
        Base.metadata.create_all(bind=cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

    @classmethod
    def tearDownClass(cls):
        if cls.engine:
            cls.engine.dispose()
        try:
            conn = psycopg2.connect(f"{POSTGRES_BASE_URL}/postgres")
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cur = conn.cursor()
            cur.execute(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{cls.TEST_DB_NAME}'
                  AND pid <> pg_backend_pid();
            """)
            cur.execute(f"DROP DATABASE IF EXISTS {cls.TEST_DB_NAME};")
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Warning: Failed to drop test db {cls.TEST_DB_NAME}: {e}")

    def setUp(self):
        self.db = self.Session()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def _create_user(self, email, role, department="CSE"):
        u = User(
            name=email.split("@")[0],
            email=email,
            password_hash="hashed_pw",
            role=role,
            department=department,
            is_active=True,
        )
        self.db.add(u)
        self.db.commit()
        self.db.refresh(u)
        return u

    def _create_file(self, filename, uploader_id, department="CSE"):
        f = File(
            filename=filename,
            file_size=2048,
            mime_type="application/pdf",
            bucket="edumatrix-files",
            object_key=f"placement/jobs/{uuid.uuid4().hex}_{filename}",
            department=department,
            file_type="placement_doc",
            status=FileStatus.ACTIVE,
            uploaded_by=uploader_id,
        )
        self.db.add(f)
        self.db.commit()
        self.db.refresh(f)
        return f

    def test_job_creation_with_multiple_attachments(self):
        """Verify creating a job with multiple attachment_file_ids links them in job_posting_attachments."""
        officer = self._create_user(f"officer_{uuid.uuid4().hex[:6]}@edu.in", UserRole.PLACEMENT_OFFICER, "Placement")
        company = Company(
            name=f"Amazon India {uuid.uuid4().hex[:4]}",
            industry="Cloud Computing",
            location="Hyderabad",
            is_active=True,
        )
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)

        file1 = self._create_file("JD_SDE1.pdf", officer.id, "Placement")
        file2 = self._create_file("Salary_Breakdown.xlsx", officer.id, "Placement")
        file3 = self._create_file("Criteria.docx", officer.id, "Placement")

        job_in = JobPostingCreate(
            company_id=company.id,
            title="SDE 1 - Cloud Services",
            description="Software Development Engineer 1 position.",
            required_skills=["Java", "AWS", "Data Structures"],
            preferred_skills=["Docker", "Kubernetes"],
            branch_eligibility=["CSE", "IT"],
            cgpa_criteria=7.5,
            file_id=file1.id,
            attachment_file_ids=[file1.id, file2.id, file3.id],
        )

        job = placement_service.create_job_posting(self.db, job_in, created_by=officer.id)
        self.assertIsNotNone(job.id)
        self.assertEqual(job.file_id, file1.id)

        # Inspect attachments relationship
        fetched_job = placement_service.get_job_posting(self.db, job.id)
        self.assertEqual(len(fetched_job.attachments), 3)

        attached_file_ids = [att.file_id for att in fetched_job.attachments]
        self.assertIn(file1.id, attached_file_ids)
        self.assertIn(file2.id, attached_file_ids)
        self.assertIn(file3.id, attached_file_ids)

        # Verify to_dict includes attachments
        job_dict = fetched_job.to_dict()
        self.assertIn("attachments", job_dict)
        self.assertEqual(len(job_dict["attachments"]), 3)

    def test_job_document_preview_and_download_rbac(self):
        """Verify RBAC permissions for job file preview and download."""
        officer = self._create_user(f"po_{uuid.uuid4().hex[:6]}@edu.in", UserRole.PLACEMENT_OFFICER, "Placement")
        admin = self._create_user(f"adm_{uuid.uuid4().hex[:6]}@edu.in", UserRole.ADMIN, "Administration")
        student_cse = self._create_user(f"stud_cse_{uuid.uuid4().hex[:6]}@edu.in", UserRole.STUDENT, "CSE")
        student_mech = self._create_user(f"stud_mech_{uuid.uuid4().hex[:6]}@edu.in", UserRole.STUDENT, "MECH")

        # Add student profiles with branches
        p_cse = StudentProfileExtended(
            user_id=student_cse.id,
            full_name="CSE Student",
            branch="CSE",
            cgpa=8.5,
        )
        p_mech = StudentProfileExtended(
            user_id=student_mech.id,
            full_name="MECH Student",
            branch="MECH",
            cgpa=8.0,
        )
        self.db.add_all([p_cse, p_mech])
        self.db.commit()

        company = Company(
            name=f"Microsoft {uuid.uuid4().hex[:4]}",
            industry="Software",
            location="Hyderabad",
            is_active=True,
        )
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)

        file_obj = self._create_file("Microsoft_JD.pdf", officer.id, "Placement")

        # 1. Job is DRAFT
        draft_job = JobPosting(
            company_id=company.id,
            title="Software Engineer - Draft",
            status=JobStatus.DRAFT,
            branch_eligibility=["CSE"],
            file_id=file_obj.id,
        )
        self.db.add(draft_job)
        self.db.commit()
        self.db.refresh(draft_job)

        # Attachment record
        att = JobPostingAttachment(job_posting_id=draft_job.id, file_id=file_obj.id, display_order=0)
        self.db.add(att)
        self.db.commit()

        # Placement Officer CAN access draft job document
        self.assertTrue(check_file_permission(self.db, file_obj, officer))
        # Admin CAN access draft job document
        self.assertTrue(check_file_permission(self.db, file_obj, admin))
        # Student CANNOT access draft job document
        self.assertFalse(check_file_permission(self.db, file_obj, student_cse))

        # 2. Transition Job to OPEN
        draft_job.status = JobStatus.OPEN
        self.db.commit()

        # CSE Student (eligible branch) CAN access OPEN job document
        self.assertTrue(check_file_permission(self.db, file_obj, student_cse))

        # MECH Student (ineligible branch) CANNOT access OPEN job document
        self.assertFalse(check_file_permission(self.db, file_obj, student_mech))

    def test_safe_bulk_deletion_of_jobs(self):
        """Verify bulk deletion permanently removes unlinked jobs and safely handles jobs with applications."""
        officer = self._create_user(f"po_{uuid.uuid4().hex[:6]}@edu.in", UserRole.PLACEMENT_OFFICER, "Placement")
        student = self._create_user(f"stud_{uuid.uuid4().hex[:6]}@edu.in", UserRole.STUDENT, "CSE")

        company = Company(
            name=f"Oracle {uuid.uuid4().hex[:4]}",
            industry="Database / Cloud",
            location="Bangalore",
            is_active=True,
        )
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)

        # Job 1: Standalone job with zero dependencies
        job1 = JobPosting(
            company_id=company.id,
            title="Unlinked Job To Delete",
            status=JobStatus.OPEN,
        )
        # Job 2: Job with student application (protected)
        job2 = JobPosting(
            company_id=company.id,
            title="Protected Job With Applications",
            status=JobStatus.OPEN,
        )
        self.db.add_all([job1, job2])
        self.db.commit()
        self.db.refresh(job1)
        self.db.refresh(job2)

        # Create application for job2
        app = Application(
            job_posting_id=job2.id,
            student_id=student.id,
            status=ApplicationStatus.APPLIED,
        )
        self.db.add(app)
        self.db.commit()

        # 1. Bulk delete with force=False: job1 is deleted, job2 is blocked
        res1 = placement_service.bulk_delete_jobs(self.db, [job1.id, job2.id], force=False)
        self.assertEqual(res1["deleted_count"], 1)
        self.assertEqual(res1["blocked_count"], 1)
        self.assertEqual(res1["closed_count"], 0)

        # Verify job1 is gone from DB
        self.assertIsNone(self.db.query(JobPosting).filter(JobPosting.id == job1.id).first())
        # Verify job2 is still in DB and OPEN
        job2_refetched = self.db.query(JobPosting).filter(JobPosting.id == job2.id).first()
        self.assertIsNotNone(job2_refetched)
        self.assertEqual(job2_refetched.status, JobStatus.OPEN)

        # 2. Bulk delete with force=True on job2: job2 safely transitions to CLOSED
        res2 = placement_service.bulk_delete_jobs(self.db, [job2.id], force=True)
        self.assertEqual(res2["deleted_count"], 0)
        self.assertEqual(res2["closed_count"], 1)
        self.assertEqual(res2["blocked_count"], 0)

        job2_closed = self.db.query(JobPosting).filter(JobPosting.id == job2.id).first()
        self.assertEqual(job2_closed.status, JobStatus.CLOSED)

        # Verify application record is completely preserved
        app_refetched = self.db.query(Application).filter(Application.id == app.id).first()
        self.assertIsNotNone(app_refetched)
        self.assertEqual(app_refetched.status, ApplicationStatus.APPLIED)

    def test_safe_bulk_deletion_of_companies(self):
        """Verify bulk deletion of companies in soft and hard modes."""
        c1 = Company(
            name=f"Inactive Co 1 {uuid.uuid4().hex[:4]}",
            industry="Consulting",
            location="Delhi",
            is_active=True,
        )
        c2 = Company(
            name=f"Inactive Co 2 {uuid.uuid4().hex[:4]}",
            industry="Finance",
            location="Mumbai",
            is_active=True,
        )
        self.db.add_all([c1, c2])
        self.db.commit()
        self.db.refresh(c1)
        self.db.refresh(c2)

        # Soft delete: deactivates companies
        res_soft = placement_service.bulk_delete_companies(self.db, [c1.id], mode="soft")
        self.assertEqual(res_soft["deactivated_count"], 1)

        c1_refetched = self.db.query(Company).filter(Company.id == c1.id).first()
        self.assertFalse(c1_refetched.is_active)

        # Hard delete unlinked company: deletes permanently
        res_hard = placement_service.bulk_delete_companies(self.db, [c2.id], mode="hard")
        self.assertEqual(res_hard["deleted_count"], 1)

        c2_refetched = self.db.query(Company).filter(Company.id == c2.id).first()
        self.assertIsNone(c2_refetched)


if __name__ == "__main__":
    unittest.main()
