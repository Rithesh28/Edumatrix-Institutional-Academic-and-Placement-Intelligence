"""
EduMatrix Phase B — Placement Data Contracts & Schema Foundation Tests

Covers:
1. Company creation rejects missing industry.
2. Company creation rejects missing location.
3. Blank and whitespace-only required company values are rejected.
4. Valid company data succeeds.
5. Optional email, description, and phone remain optional.
6. Company update validation behaves as intended (rejects blank updates, permits partial updates).
7. Job can exist without an attached file (file_id=None).
8. Job can reference a valid file record (file_id=file.id).
9. Invalid file reference is rejected (foreign key / service validation).
10. Deleting a referenced file follows ON DELETE SET NULL behavior.
11. Existing placement model relationships and constraints remain valid.
12. Alembic migration upgrade and downgrade work on an isolated temporary test database.
13. Migration test dynamically discovers the actual configured Alembic head and validates single-head policy.
"""

import os
import unittest
import uuid
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from pydantic import ValidationError

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic import command
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.schemas.placement import (
    CompanyCreate,
    CompanyUpdate,
    CompanyResponse,
    JobPostingCreate,
    JobPostingUpdate,
    JobPostingResponse,
)
from app.models.company import Company
from app.models.job_posting import JobPosting, JobStatus
from app.models.file import File, FileStatus
from app.models.user import User, UserRole


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ALEMBIC_INI_PATH = os.path.join(BASE_DIR, "alembic.ini")
POSTGRES_BASE_URL = "postgresql://edumatrix:edumatrix123@postgres:5432"


class TestCompanyValidationAndSchemas(unittest.TestCase):
    """Unit tests for Pydantic schema validation without database dependencies."""

    def test_company_creation_rejects_missing_industry(self):
        """Verify that omitting industry in CompanyCreate raises a ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            CompanyCreate(
                name="Acme Corp",
                location="Bangalore",
            )
        errors = ctx.exception.errors()
        field_names = [e["loc"][0] for e in errors]
        self.assertIn("industry", field_names)

    def test_company_creation_rejects_missing_location(self):
        """Verify that omitting location in CompanyCreate raises a ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            CompanyCreate(
                name="Acme Corp",
                industry="Information Technology",
            )
        errors = ctx.exception.errors()
        field_names = [e["loc"][0] for e in errors]
        self.assertIn("location", field_names)

    def test_company_creation_rejects_blank_or_whitespace_values(self):
        """Verify that empty strings and whitespace-only strings are rejected for required fields."""
        # Blank industry
        with self.assertRaises(ValidationError):
            CompanyCreate(name="Acme Corp", industry="", location="Bangalore")
        with self.assertRaises(ValidationError):
            CompanyCreate(name="Acme Corp", industry="   ", location="Bangalore")

        # Blank location
        with self.assertRaises(ValidationError):
            CompanyCreate(name="Acme Corp", industry="IT", location="")
        with self.assertRaises(ValidationError):
            CompanyCreate(name="Acme Corp", industry="IT", location="   ")

        # Blank name
        with self.assertRaises(ValidationError):
            CompanyCreate(name="", industry="IT", location="Bangalore")
        with self.assertRaises(ValidationError):
            CompanyCreate(name="   ", industry="IT", location="Bangalore")

    def test_valid_company_data_succeeds(self):
        """Verify that supplying valid name, industry, and location succeeds."""
        c = CompanyCreate(
            name="Google DeepMind",
            industry="Artificial Intelligence",
            location="London / Bangalore",
        )
        self.assertEqual(c.name, "Google DeepMind")
        self.assertEqual(c.industry, "Artificial Intelligence")
        self.assertEqual(c.location, "London / Bangalore")
        self.assertTrue(c.is_active)

    def test_optional_fields_remain_optional(self):
        """Verify that email, description, phone, website, and logo_url remain optional."""
        c = CompanyCreate(
            name="Open Tech Labs",
            industry="Open Source",
            location="Remote",
            contact_email=None,
            contact_phone=None,
            description=None,
            website=None,
            logo_url=None,
        )
        self.assertIsNone(c.contact_email)
        self.assertIsNone(c.contact_phone)
        self.assertIsNone(c.description)
        self.assertIsNone(c.website)
        self.assertIsNone(c.logo_url)

    def test_company_update_validation(self):
        """Verify CompanyUpdate rejects blank strings when fields are provided, but allows partial updates."""
        # Partial update with only industry
        u = CompanyUpdate(industry="Biotechnology")
        self.assertEqual(u.industry, "Biotechnology")
        self.assertIsNone(u.name)
        self.assertIsNone(u.location)

        # Blank industry update rejected
        with self.assertRaises(ValidationError):
            CompanyUpdate(industry="   ")

        # Blank location update rejected
        with self.assertRaises(ValidationError):
            CompanyUpdate(location="   ")

        # Blank name update rejected
        with self.assertRaises(ValidationError):
            CompanyUpdate(name="   ")

    def test_company_response_backward_compatibility(self):
        """Verify CompanyResponse tolerates null industry/location for legacy fallback compatibility."""
        resp = CompanyResponse(
            id=1,
            name="Legacy Corp",
            industry=None,
            location=None,
            created_at="2026-01-01T00:00:00",
        )
        self.assertEqual(resp.id, 1)
        self.assertEqual(resp.name, "Legacy Corp")
        self.assertIsNone(resp.industry)
        self.assertIsNone(resp.location)

    def test_job_posting_schemas_file_id_support(self):
        """Verify JobPostingCreate and JobPostingResponse accept and serialize file_id."""
        test_uuid = uuid.uuid4()
        j_create = JobPostingCreate(
            company_id=1,
            title="Software Engineer",
            file_id=test_uuid,
        )
        self.assertEqual(j_create.file_id, test_uuid)

        # When file_id is omitted, defaults to None
        j_create_no_file = JobPostingCreate(
            company_id=1,
            title="Software Engineer",
        )
        self.assertIsNone(j_create_no_file.file_id)

        # JobPostingResponse serialization
        j_resp = JobPostingResponse(
            id=10,
            company_id=1,
            title="Software Engineer",
            file_id=test_uuid,
            file_name="JD_Document.pdf",
            created_at="2026-01-01T00:00:00",
        )
        self.assertEqual(j_resp.file_id, test_uuid)
        self.assertEqual(j_resp.file_name, "JD_Document.pdf")


class TestAlembicMigrationIsolated(unittest.TestCase):
    """Tests Alembic migrations against a strictly isolated temporary database."""

    @classmethod
    def setUpClass(cls):
        cls.orig_db_url = os.environ.get("DATABASE_URL")
        cls.test_db_name = f"edumatrix_test_mig_{uuid.uuid4().hex[:8]}"
        cls.test_db_url = f"{POSTGRES_BASE_URL}/{cls.test_db_name}"

        # Create isolated test database
        conn = psycopg2.connect(f"{POSTGRES_BASE_URL}/edumatrix")
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute(f"CREATE DATABASE {cls.test_db_name}")
        cur.close()
        conn.close()

        # Point environment to isolated test database
        os.environ["DATABASE_URL"] = cls.test_db_url

    @classmethod
    def tearDownClass(cls):
        # Restore original environment
        if cls.orig_db_url:
            os.environ["DATABASE_URL"] = cls.orig_db_url
        elif "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]

        # Drop isolated test database
        try:
            conn = psycopg2.connect(f"{POSTGRES_BASE_URL}/edumatrix")
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cur = conn.cursor()
            cur.execute(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{cls.test_db_name}'
                  AND pid <> pg_backend_pid();
            """)
            cur.execute(f"DROP DATABASE IF EXISTS {cls.test_db_name}")
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Warning: Failed to drop test db {cls.test_db_name}: {e}")

    def test_alembic_upgrade_and_downgrade(self):
        """Verify migration 021 upgrade, schema inspection, downgrade to 020, and re-upgrade."""
        alembic_cfg = Config(ALEMBIC_INI_PATH)
        alembic_cfg.set_main_option("sqlalchemy.url", self.test_db_url)

        engine = sa.create_engine(self.test_db_url)

        # 1. Create base tables up to 020 state so migrations can run against real tables
        # First create initial tables
        Base.metadata.create_all(bind=engine)
        
        # Stamp revision 020
        command.stamp(alembic_cfg, "020")

        # In 020 state, set industry and location to nullable=True and drop file_id if created by create_all
        with engine.begin() as conn:
            conn.execute(sa.text("ALTER TABLE companies ALTER COLUMN industry DROP NOT NULL"))
            conn.execute(sa.text("ALTER TABLE companies ALTER COLUMN location DROP NOT NULL"))
            conn.execute(sa.text("ALTER TABLE job_postings DROP COLUMN IF EXISTS file_id CASCADE"))

        # Verify pre-021 state
        inspector = sa.inspect(engine)
        comp_cols_pre = {c["name"]: c for c in inspector.get_columns("companies")}
        self.assertTrue(comp_cols_pre["industry"]["nullable"], "industry should be nullable before 021")
        self.assertTrue(comp_cols_pre["location"]["nullable"], "location should be nullable before 021")

        # 2. Upgrade to 021 (head)
        command.upgrade(alembic_cfg, "head")

        # Inspect schema at head (021)
        inspector = sa.inspect(engine)

        # Check companies table columns are NOT NULL
        comp_cols = {c["name"]: c for c in inspector.get_columns("companies")}
        self.assertFalse(comp_cols["industry"]["nullable"], "companies.industry must be NOT NULL after 021")
        self.assertFalse(comp_cols["location"]["nullable"], "companies.location must be NOT NULL after 021")

        # Check job_postings table columns
        job_cols = {c["name"]: c for c in inspector.get_columns("job_postings")}
        self.assertIn("file_id", job_cols, "job_postings must contain file_id column after 021")
        self.assertTrue(job_cols["file_id"]["nullable"], "job_postings.file_id must be nullable")

        # Check foreign keys on job_postings
        fks = inspector.get_foreign_keys("job_postings")
        file_fk = next((fk for fk in fks if fk["referred_table"] == "files"), None)
        self.assertIsNotNone(file_fk, "job_postings must have a foreign key to files")
        self.assertEqual(file_fk["constrained_columns"], ["file_id"])
        self.assertEqual(file_fk["referred_columns"], ["id"])

        # Check index on file_id
        indexes = inspector.get_indexes("job_postings")
        file_idx = next((idx for idx in indexes if idx["name"] == "ix_job_postings_file_id"), None)
        self.assertIsNotNone(file_idx, "ix_job_postings_file_id index must exist")

        # 3. Downgrade to 020
        command.downgrade(alembic_cfg, "020")

        # Verify rollback at revision 020
        inspector = sa.inspect(engine)
        comp_cols_020 = {c["name"]: c for c in inspector.get_columns("companies")}
        self.assertTrue(comp_cols_020["industry"]["nullable"], "companies.industry must be nullable at 020")
        self.assertTrue(comp_cols_020["location"]["nullable"], "companies.location must be nullable at 020")

        job_cols_020 = {c["name"]: c for c in inspector.get_columns("job_postings")}
        self.assertNotIn("file_id", job_cols_020, "job_postings.file_id must not exist at 020")

        # 4. Re-upgrade to head (021)
        command.upgrade(alembic_cfg, "head")
        inspector = sa.inspect(engine)
        job_cols_re = {c["name"]: c for c in inspector.get_columns("job_postings")}
        self.assertIn("file_id", job_cols_re, "job_postings.file_id must exist after re-upgrade")
        engine.dispose()


class TestJobPostingFilePersistenceAndSetNull(unittest.TestCase):
    """Tests JobPosting file_id persistence, constraints, and SET NULL cascade on an isolated database."""

    @classmethod
    def setUpClass(cls):
        cls.orig_db_url = os.environ.get("DATABASE_URL")
        cls.test_db_name = f"edumatrix_test_job_{uuid.uuid4().hex[:8]}"
        cls.test_db_url = f"{POSTGRES_BASE_URL}/{cls.test_db_name}"

        # Create isolated test database
        conn = psycopg2.connect(f"{POSTGRES_BASE_URL}/edumatrix")
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute(f"CREATE DATABASE {cls.test_db_name}")
        cur.close()
        conn.close()

        # Point environment to isolated test database
        os.environ["DATABASE_URL"] = cls.test_db_url

        cls.engine = sa.create_engine(cls.test_db_url)
        # Create all tables using metadata
        Base.metadata.create_all(bind=cls.engine)

        cls.Session = sessionmaker(bind=cls.engine)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        # Restore environment
        if cls.orig_db_url:
            os.environ["DATABASE_URL"] = cls.orig_db_url
        elif "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]

        try:
            conn = psycopg2.connect(f"{POSTGRES_BASE_URL}/edumatrix")
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cur = conn.cursor()
            cur.execute(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{cls.test_db_name}'
                  AND pid <> pg_backend_pid();
            """)
            cur.execute(f"DROP DATABASE IF EXISTS {cls.test_db_name}")
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Warning: Failed to drop test db {cls.test_db_name}: {e}")

    def setUp(self):
        self.db = self.Session()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_job_without_attached_file(self):
        """Verify that a job can exist without an attached file (file_id=None)."""
        company = Company(
            name="Initech Technologies",
            industry="Enterprise Software",
            location="Austin, TX",
        )
        self.db.add(company)
        self.db.commit()

        job = JobPosting(
            company_id=company.id,
            title="Software Developer",
            file_id=None,
            status=JobStatus.DRAFT,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        self.assertIsNotNone(job.id)
        self.assertIsNone(job.file_id)
        self.assertIsNone(job.file)
        self.assertEqual(job.to_dict()["file_id"], None)
        self.assertEqual(job.to_dict()["file_name"], None)

    def test_job_with_valid_file_and_set_null_cascade(self):
        """Verify job referencing a valid file record, and verify ON DELETE SET NULL on file deletion."""
        company = Company(
            name="Pied Piper Inc",
            industry="Data Compression",
            location="Palo Alto, CA",
        )
        self.db.add(company)
        self.db.commit()

        # Create a valid file record
        file_rec = File(
            filename="PiedPiper_JD_2026.pdf",
            file_size=204800,
            mime_type="application/pdf",
            bucket="edumatrix-files",
            object_key=f"placement/jobs/jd_{uuid.uuid4().hex}.pdf",
            department="Computer Science",
            file_type="placement_doc",
            status=FileStatus.ACTIVE,
        )
        self.db.add(file_rec)
        self.db.commit()
        self.db.refresh(file_rec)

        # Create job referencing the file
        job = JobPosting(
            company_id=company.id,
            title="Compression Algorithm Engineer",
            file_id=file_rec.id,
            status=JobStatus.OPEN,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        self.assertEqual(job.file_id, file_rec.id)
        self.assertIsNotNone(job.file)
        self.assertEqual(job.file.filename, "PiedPiper_JD_2026.pdf")
        self.assertEqual(job.to_dict()["file_name"], "PiedPiper_JD_2026.pdf")

        # Delete the file record to test ON DELETE SET NULL
        self.db.delete(file_rec)
        self.db.commit()

        # Re-query the job: job must still exist, with file_id set to None
        job_after = self.db.query(JobPosting).filter(JobPosting.id == job.id).first()
        self.assertIsNotNone(job_after, "Job must not be deleted when attached file is deleted")
        self.assertIsNone(job_after.file_id, "file_id must be SET NULL when referenced file is deleted")
        self.assertIsNone(job_after.file)

    def test_invalid_file_reference_rejected_by_db(self):
        """Verify that supplying a non-existent UUID as file_id raises a database IntegrityError."""
        company = Company(
            name="Hooli Corp",
            industry="Big Tech",
            location="Mountain View, CA",
        )
        self.db.add(company)
        self.db.commit()

        non_existent_uuid = uuid.uuid4()
        job = JobPosting(
            company_id=company.id,
            title="Cloud Architect",
            file_id=non_existent_uuid,
            status=JobStatus.DRAFT,
        )
        self.db.add(job)
        with self.assertRaises(sa.exc.IntegrityError):
            self.db.commit()
        self.db.rollback()


class TestAlembicHeadDiscovery(unittest.TestCase):
    """Validates the project's migration head discovery and single-head policy."""

    def test_single_head_policy(self):
        """Verify that Alembic configuration discovers exactly one head."""
        alembic_cfg = Config(ALEMBIC_INI_PATH)
        script_dir = ScriptDirectory.from_config(alembic_cfg)
        heads = script_dir.get_heads()
        self.assertEqual(len(heads), 1, f"Expected single migration head, found: {heads}")
        self.assertEqual(heads[0], "021", "Current migration head must be 021")


if __name__ == "__main__":
    unittest.main()
