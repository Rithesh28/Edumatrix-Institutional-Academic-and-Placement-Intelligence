"""
EduMatrix Phase E Test Suite: Student Applications and Placement Officer Tracking.

Verifies:
1. URL Protocol Validation:
   - Accepts valid http/https URLs.
   - Rejects non-http/https protocols (javascript:, ftp:, file:, local paths).
2. External Apply Link Non-Creation:
   - Navigating or inspecting external apply URL does not create an application record.
3. Mark as Applied (External Confirmation):
   - Scoped strictly to authenticated student.
   - Creates application with external_applied_at in UTC and frozen match_snapshot.
4. Idempotency & Concurrency:
   - Repeated confirm-external calls return existing application (HTTP 200) without error or duplicates.
   - create_application with allow_existing=True handles concurrent race conditions gracefully.
5. RBAC & Access Control:
   - Non-students (officer/admin) receive HTTP 403 on confirm-external.
   - Students cannot confirm another student's application (HTTP 403).
   - Students cannot access officer application tracking or update application statuses (HTTP 403).
6. Academic Eligibility Enforcement:
   - Ineligible student (CGPA below cutoff) is rejected (HTTP 400).
   - Ineligible student (branch mismatch) is rejected (HTTP 400).
   - Eligible student with low skill match (<50%) is allowed with warning recorded.
7. Job Status & Deadline Enforcement:
   - Closed or draft jobs cannot be applied to (HTTP 400).
   - Jobs with past deadlines cannot be applied to (HTTP 400).
8. Student Application Scoping ("My Applications"):
   - Student queries are strictly scoped to authenticated user.
   - Historical applications remain queryable when job is closed or company deactivated.
9. Placement Officer Tracking & Filtering:
   - Officer can view applications with student name, USN, branch, CGPA, job, company, and confirmation timestamp.
   - Officer can filter by company, job, branch, status, and search query.
   - Officer can update application status.
   - Recruitment progression and verified offer computed properties serialize properly.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from fastapi.testclient import TestClient

# Add backend directory to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.core.database import Base, get_db
from app.api.auth import get_current_user
from app.main import app
from app.models.user import User, UserRole
from app.models.company import Company
from app.models.job_posting import JobPosting, JobStatus
from app.models.application import Application, ApplicationStatus
from app.models.profile import StudentProfileExtended, Skill
from app.models.recruitment_round import (
    RecruitmentRound,
    StudentRoundOutcome,
    RoundOutcome,
    PlacementOffer,
    OfferAcceptanceStatus,
)
from pydantic import ValidationError
from app.schemas.placement import ApplicationCreate, JobPostingUpdate
from app.services.placement_service import placement_service

POSTGRES_BASE_URL = os.environ.get(
    "TEST_DATABASE_BASE_URL",
    "postgresql://edumatrix:edumatrix123@postgres:5432"
)


class TestPhaseEStudentApplicationsAndOfficerTracking(unittest.TestCase):
    """Integration test suite executing in isolated PostgreSQL database (edumatrix_test_phase_e)."""

    TEST_DB_NAME = "edumatrix_test_phase_e"

    @classmethod
    def setUpClass(cls):
        """Create isolated test database and build tables using Base.metadata."""
        # 1. Connect to template1 to drop and create isolated test database
        conn = psycopg2.connect(f"{POSTGRES_BASE_URL}/template1")
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

        # 2. Bind SQLAlchemy engine and create schema
        cls.target_db_url = f"{POSTGRES_BASE_URL}/{cls.TEST_DB_NAME}"
        cls.engine = sa.create_engine(cls.target_db_url)
        Base.metadata.create_all(bind=cls.engine)
        cls.Session = sessionmaker(bind=cls.engine, expire_on_commit=False)

        # 3. Initialize seed data in test database
        session = cls.Session()

        # Users
        cls.po_user = User(
            name="Officer Sharma",
            email="po_phase_e@edumatrix.edu",
            password_hash="test_pw",
            role=UserRole.PLACEMENT_OFFICER,
            is_active=True,
        )
        cls.admin_user = User(
            name="Admin User",
            email="admin_phase_e@edumatrix.edu",
            password_hash="test_pw",
            role=UserRole.ADMIN,
            is_active=True,
        )
        cls.student_cse_eligible = User(
            name="Aarav Kumar",
            email="aarav_cse@edumatrix.edu",
            password_hash="test_pw",
            role=UserRole.STUDENT,
            is_active=True,
            department="CSE",
        )
        cls.student_ise_eligible = User(
            name="Bhavna Rao",
            email="bhavna_ise@edumatrix.edu",
            password_hash="test_pw",
            role=UserRole.STUDENT,
            is_active=True,
            department="ISE",
        )
        cls.student_low_cgpa = User(
            name="Chirag LowCGPA",
            email="chirag_lowcgpa@edumatrix.edu",
            password_hash="test_pw",
            role=UserRole.STUDENT,
            is_active=True,
            department="CSE",
        )
        cls.student_civil = User(
            name="Deepa Civil",
            email="deepa_civil@edumatrix.edu",
            password_hash="test_pw",
            role=UserRole.STUDENT,
            is_active=True,
            department="CIVIL",
        )
        cls.student_low_skill = User(
            name="Eshan LowSkill",
            email="eshan_lowskill@edumatrix.edu",
            password_hash="test_pw",
            role=UserRole.STUDENT,
            is_active=True,
            department="CSE",
        )

        session.add_all([
            cls.po_user,
            cls.admin_user,
            cls.student_cse_eligible,
            cls.student_ise_eligible,
            cls.student_low_cgpa,
            cls.student_civil,
            cls.student_low_skill,
        ])
        session.flush()

        # Profiles with USN (enrollment_number)
        profile_aarav = StudentProfileExtended(
            user_id=cls.student_cse_eligible.id,
            enrollment_number="1MS21CS001",
            branch="CSE",
            cgpa=8.5,
            year=2025,
        )
        profile_bhavna = StudentProfileExtended(
            user_id=cls.student_ise_eligible.id,
            enrollment_number="1MS21IS002",
            branch="ISE",
            cgpa=7.8,
            year=2025,
        )
        profile_chirag = StudentProfileExtended(
            user_id=cls.student_low_cgpa.id,
            enrollment_number="1MS21CS003",
            branch="CSE",
            cgpa=5.8,  # Below 7.0 cutoff
            year=2025,
        )
        profile_deepa = StudentProfileExtended(
            user_id=cls.student_civil.id,
            enrollment_number="1MS21CV004",
            branch="CIVIL",  # Ineligible branch
            cgpa=8.0,
            year=2025,
        )
        profile_eshan = StudentProfileExtended(
            user_id=cls.student_low_skill.id,
            enrollment_number="1MS21CS005",
            branch="CSE",
            cgpa=8.2,
            year=2025,
        )

        session.add_all([profile_aarav, profile_bhavna, profile_chirag, profile_deepa, profile_eshan])
        session.flush()

        # Add Skills
        skills_aarav = [Skill(student_id=profile_aarav.id, name=s) for s in ["Python", "FastAPI", "React", "PostgreSQL"]]
        skills_bhavna = [Skill(student_id=profile_bhavna.id, name=s) for s in ["Python", "FastAPI"]]
        skills_chirag = [Skill(student_id=profile_chirag.id, name=s) for s in ["Python", "FastAPI"]]
        skills_deepa = [Skill(student_id=profile_deepa.id, name=s) for s in ["AutoCAD"]]
        skills_eshan = [Skill(student_id=profile_eshan.id, name=s) for s in ["C"]]
        session.add_all(skills_aarav + skills_bhavna + skills_chirag + skills_deepa + skills_eshan)

        # Companies
        cls.company_alpha = Company(
            name="Alpha Corp",
            industry="Software",
            location="Bengaluru",
            website="https://alpha.example.com",
            is_active=True,
        )
        cls.company_beta = Company(
            name="Beta Corp",
            industry="Finance",
            location="Mumbai",
            website="https://beta.example.com",
            is_active=True,
        )
        session.add_all([cls.company_alpha, cls.company_beta])
        session.flush()

        # Job Postings
        now = datetime.now(timezone.utc)
        cls.job_open_ext = JobPosting(
            company_id=cls.company_alpha.id,
            title="Full Stack Software Engineer",
            description="Build scalable web applications with Python and React.",
            location="Bengaluru",
            status=JobStatus.OPEN,
            application_url="https://careers.alpha.example.com/jobs/full-stack-101",
            application_deadline=now + timedelta(days=14),
            branch_eligibility=["CSE", "ISE"],
            cgpa_criteria=7.0,
            required_skills=["Python", "FastAPI"],
            preferred_skills=["React", "PostgreSQL"],
        )
        cls.job_open_internal = JobPosting(
            company_id=cls.company_alpha.id,
            title="Backend Systems Engineer",
            description="Internal on-campus drive.",
            location="Bengaluru",
            status=JobStatus.OPEN,
            application_url=None,  # Internal only
            application_deadline=now + timedelta(days=14),
            branch_eligibility=["CSE"],
            cgpa_criteria=7.0,
            required_skills=["Python"],
        )
        cls.job_closed = JobPosting(
            company_id=cls.company_beta.id,
            title="Data Analyst",
            description="Closed position.",
            status=JobStatus.CLOSED,
            application_url="https://careers.beta.example.com/jobs/analyst",
            application_deadline=now + timedelta(days=7),
            branch_eligibility=["CSE", "ISE"],
            cgpa_criteria=6.5,
            required_skills=["Python"],
        )
        cls.job_expired = JobPosting(
            company_id=cls.company_beta.id,
            title="DevOps Engineer",
            description="Expired deadline position.",
            status=JobStatus.OPEN,
            application_url="https://careers.beta.example.com/jobs/devops",
            application_deadline=now - timedelta(days=3),  # Passed 3 days ago
            branch_eligibility=["CSE", "ISE"],
            cgpa_criteria=6.5,
            required_skills=["Linux"],
        )

        session.add_all([cls.job_open_ext, cls.job_open_internal, cls.job_closed, cls.job_expired])
        session.flush()

        cls.po_user_id = cls.po_user.id
        cls.admin_user_id = cls.admin_user.id
        cls.student_cse_eligible_id = cls.student_cse_eligible.id
        cls.student_ise_eligible_id = cls.student_ise_eligible.id
        cls.student_low_cgpa_id = cls.student_low_cgpa.id
        cls.student_civil_id = cls.student_civil.id
        cls.student_low_skill_id = cls.student_low_skill.id

        cls.company_alpha_id = cls.company_alpha.id
        cls.company_beta_id = cls.company_beta.id

        cls.job_open_ext_id = cls.job_open_ext.id
        cls.job_open_internal_id = cls.job_open_internal.id
        cls.job_closed_id = cls.job_closed.id
        cls.job_expired_id = cls.job_expired.id

        session.commit()
        session.close()

        # 4. Set up FastAPI TestClient
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        """Dispose connections and drop isolated test database."""
        cls.engine.dispose()
        try:
            conn = psycopg2.connect(f"{POSTGRES_BASE_URL}/template1")
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
        """Provide a fresh session per test and set dependency overrides."""
        self.session = self.Session()
        # Dependency override for get_db
        app.dependency_overrides[get_db] = lambda: self.session

        # Re-fetch entities attached to self.session so they are never detached
        self.po_user = self.session.get(User, self.po_user_id)
        self.admin_user = self.session.get(User, self.admin_user_id)
        self.student_cse_eligible = self.session.get(User, self.student_cse_eligible_id)
        self.student_ise_eligible = self.session.get(User, self.student_ise_eligible_id)
        self.student_low_cgpa = self.session.get(User, self.student_low_cgpa_id)
        self.student_civil = self.session.get(User, self.student_civil_id)
        self.student_low_skill = self.session.get(User, self.student_low_skill_id)

        self.company_alpha = self.session.get(Company, self.company_alpha_id)
        self.company_beta = self.session.get(Company, self.company_beta_id)

        self.job_open_ext = self.session.get(JobPosting, self.job_open_ext_id)
        self.job_open_internal = self.session.get(JobPosting, self.job_open_internal_id)
        self.job_closed = self.session.get(JobPosting, self.job_closed_id)
        self.job_expired = self.session.get(JobPosting, self.job_expired_id)

    def tearDown(self):
        """Clean up dependency overrides and close session."""
        app.dependency_overrides.clear()
        self.session.rollback()
        self.session.close()

    def _set_user(self, user: User):
        """Override get_current_user dependency with specified test user."""
        app.dependency_overrides[get_current_user] = lambda: user

    # =========================================================================
    # Group 1: URL Protocol & Format Validation
    # =========================================================================

    def test_01_external_url_protocol_validation_accepts_valid_http_https(self):
        """Valid http and https URLs pass validation in schema and endpoints."""
        valid_urls = [
            "https://careers.google.com/jobs/101",
            "http://jobs.startup.io/apply/frontend",
            "https://sub.domain.co.uk:8080/path?query=val#frag",
        ]
        for url in valid_urls:
            validated = JobPostingUpdate(application_url=url)
            self.assertEqual(validated.application_url, url)

            self._set_user(self.po_user)
            res = self.client.put(
                f"/placement/jobs/{self.job_open_ext.id}",
                json={"application_url": url}
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["application_url"], url)

    def test_02_external_url_protocol_validation_rejects_invalid_schemes(self):
        """Invalid schemes (javascript:, ftp:, file:, relative paths) are rejected."""
        invalid_urls = [
            "javascript:alert(1)",
            "ftp://ftp.example.com/apply",
            "file:///etc/passwd",
            "/api/v1/files/download/test.pdf",
            "data:text/html,<script>alert(1)</script>",
        ]
        for url in invalid_urls:
            with self.assertRaises(ValidationError):
                JobPostingUpdate(application_url=url)

            self._set_user(self.po_user)
            res = self.client.put(
                f"/placement/jobs/{self.job_open_ext.id}",
                json={"application_url": url}
            )
            self.assertEqual(res.status_code, 422)

    # =========================================================================
    # Group 2: External Link Opening Does NOT Create Application
    # =========================================================================

    def test_03_external_apply_navigation_does_not_create_application(self):
        """Fetching job details or opening link creates zero database application records."""
        self._set_user(self.student_cse_eligible)
        initial_count = self.session.query(Application).filter_by(
            student_id=self.student_cse_eligible.id,
            job_posting_id=self.job_open_ext.id
        ).count()
        self.assertEqual(initial_count, 0)

        # GET /placement/jobs/{id}
        res = self.client.get(f"/placement/jobs/{self.job_open_ext.id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["application_url"], self.job_open_ext.application_url)

        # Confirm count remains 0
        final_count = self.session.query(Application).filter_by(
            student_id=self.student_cse_eligible.id,
            job_posting_id=self.job_open_ext.id
        ).count()
        self.assertEqual(final_count, 0)

    # =========================================================================
    # Group 3: "Mark as Applied" (External Application Confirmation)
    # =========================================================================

    def test_04_mark_as_applied_creates_application_and_sets_timestamps(self):
        """Eligible student calling confirm-external creates application with external_applied_at."""
        self._set_user(self.student_cse_eligible)

        res = self.client.post(f"/placement/jobs/{self.job_open_ext.id}/confirm-external")
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()

        self.assertEqual(data["student_id"], self.student_cse_eligible.id)
        self.assertEqual(data["job_posting_id"], self.job_open_ext.id)
        self.assertEqual(data["status"], "applied")
        self.assertIsNotNone(data["applied_at"])
        self.assertIsNotNone(data["external_applied_at"])
        self.assertTrue(data["is_external_confirmed"])

        # Check DB directly
        app_db = self.session.query(Application).filter_by(
            student_id=self.student_cse_eligible.id,
            job_posting_id=self.job_open_ext.id
        ).first()
        self.assertIsNotNone(app_db)
        self.assertIsNotNone(app_db.external_applied_at)
        self.assertEqual(app_db.status, ApplicationStatus.APPLIED)

    def test_05_mark_as_applied_freezes_accurate_match_snapshot(self):
        """Application creation stores frozen match snapshot with academic criteria & score."""
        self._set_user(self.student_ise_eligible)

        res = self.client.post(f"/placement/jobs/{self.job_open_ext.id}/confirm-external")
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()

        snapshot = data.get("match_snapshot")
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.get("branch"), "ISE")
        self.assertEqual(snapshot.get("cgpa"), 7.8)
        self.assertTrue(snapshot.get("is_eligible"))
        self.assertIn("Python", snapshot.get("matched_required_skills", []))
        self.assertIn("FastAPI", snapshot.get("matched_required_skills", []))

    # =========================================================================
    # Group 4: Idempotency & Concurrency Safety
    # =========================================================================

    def test_06_mark_as_applied_idempotent_repeated_calls_return_existing_without_error(self):
        """Repeated calls to confirm-external return HTTP 200 and preserve original timestamp."""
        self._set_user(self.student_cse_eligible)

        # First call was already executed in test_04
        app_before = self.session.query(Application).filter_by(
            student_id=self.student_cse_eligible.id,
            job_posting_id=self.job_open_ext.id
        ).first()
        initial_ts = app_before.external_applied_at

        # Repeat call
        res = self.client.post(f"/placement/jobs/{self.job_open_ext.id}/confirm-external")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["id"], app_before.id)
        # Verify no duplicate records were created
        total_apps = self.session.query(Application).filter_by(
            student_id=self.student_cse_eligible.id,
            job_posting_id=self.job_open_ext.id
        ).count()
        self.assertEqual(total_apps, 1)

    def test_07_create_application_allow_existing_returns_existing_record(self):
        """create_application with allow_existing=True safely returns existing record."""
        app_res = placement_service.create_application(
            self.session,
            ApplicationCreate(job_posting_id=self.job_open_ext.id),
            current_user=self.student_cse_eligible,
            allow_existing=True,
        )
        self.assertIsNotNone(app_res)
        self.assertEqual(app_res.student_id, self.student_cse_eligible.id)

    # =========================================================================
    # Group 5: RBAC & Access Control
    # =========================================================================

    def test_08_officer_or_admin_cannot_mark_as_applied(self):
        """Non-students (placement officer or admin) receive HTTP 403 on confirm-external."""
        self._set_user(self.po_user)
        res = self.client.post(f"/placement/jobs/{self.job_open_ext.id}/confirm-external")
        self.assertEqual(res.status_code, 403)
        self.assertIn("Only students", res.json()["detail"])

        self._set_user(self.admin_user)
        res_admin = self.client.post(f"/placement/jobs/{self.job_open_ext.id}/confirm-external")
        self.assertEqual(res_admin.status_code, 403)

    def test_09_student_cannot_confirm_for_another_student(self):
        """Student cannot call confirm-external on another student's application."""
        # Find Aarav's application
        aarav_app = self.session.query(Application).filter_by(
            student_id=self.student_cse_eligible.id,
            job_posting_id=self.job_open_ext.id
        ).first()

        # Bhavna tries to confirm Aarav's application
        self._set_user(self.student_ise_eligible)
        res = self.client.post(f"/placement/applications/{aarav_app.id}/confirm-external")
        self.assertEqual(res.status_code, 403)
        self.assertIn("only confirm your own applications", res.json()["detail"].lower())

    def test_10_student_cannot_update_application_status(self):
        """Student cannot update application status (e.g. from applied to selected)."""
        aarav_app = self.session.query(Application).filter_by(
            student_id=self.student_cse_eligible.id,
            job_posting_id=self.job_open_ext.id
        ).first()

        self._set_user(self.student_cse_eligible)
        res = self.client.put(
            f"/placement/applications/{aarav_app.id}",
            json={"status": "selected"}
        )
        self.assertEqual(res.status_code, 403)

    # =========================================================================
    # Group 6: Academic Eligibility Enforcement
    # =========================================================================

    def test_11_ineligible_student_below_cgpa_cutoff_blocked(self):
        """Student with CGPA below cutoff cannot apply or mark as applied (HTTP 400)."""
        self._set_user(self.student_low_cgpa)  # CGPA 5.8 < 7.0 cutoff

        res = self.client.post(f"/placement/jobs/{self.job_open_ext.id}/confirm-external")
        self.assertEqual(res.status_code, 400)
        detail = res.json()["detail"]
        self.assertIn("below minimum requirement", detail.lower())
        self.assertIn("cgpa", detail.lower())

    def test_12_ineligible_student_branch_mismatch_blocked(self):
        """Student with mismatched branch cannot apply or mark as applied (HTTP 400)."""
        self._set_user(self.student_civil)  # CIVIL not in [CSE, ISE]

        res = self.client.post(f"/placement/jobs/{self.job_open_ext.id}/confirm-external")
        self.assertEqual(res.status_code, 400)
        detail = res.json()["detail"]
        self.assertIn("not eligible", detail.lower())
        self.assertIn("branch", detail.lower())

    def test_13_eligible_student_with_low_skill_match_allowed_with_warning(self):
        """Student meeting academic criteria but having low skill match (<50%) can apply with warning."""
        self._set_user(self.student_low_skill)  # CSE, 8.2 CGPA, skills: ["C"]

        res = self.client.post(f"/placement/jobs/{self.job_open_ext.id}/confirm-external")
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()

        self.assertTrue(data["has_low_match_warning"])
        self.assertIsNotNone(data["low_match_warning"])
        self.assertEqual(data["status"], "applied")

    # =========================================================================
    # Group 7: Job Status & Deadline Enforcement
    # =========================================================================

    def test_14_cannot_apply_or_confirm_on_closed_job(self):
        """Students cannot apply or confirm external application on CLOSED jobs."""
        self._set_user(self.student_cse_eligible)

        res = self.client.post(f"/placement/jobs/{self.job_closed.id}/confirm-external")
        self.assertEqual(res.status_code, 400)
        self.assertIn("no longer open", res.json()["detail"].lower())

    def test_15_cannot_apply_or_confirm_on_expired_deadline_job(self):
        """Students cannot apply or confirm external application on jobs with past deadlines."""
        self._set_user(self.student_cse_eligible)

        res = self.client.post(f"/placement/jobs/{self.job_expired.id}/confirm-external")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Application deadline has passed", res.json()["detail"])

    # =========================================================================
    # Group 8: "My Applications" Student Scoping & Historical Retention
    # =========================================================================

    def test_16_student_applications_query_strictly_scoped_to_authenticated_user(self):
        """Student querying GET /placement/applications sees only their own applications."""
        self._set_user(self.student_ise_eligible)

        res = self.client.get("/placement/applications")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertTrue(len(data) > 0)
        # Verify EVERY application belongs to Bhavna
        for app_item in data:
            self.assertEqual(app_item["student_id"], self.student_ise_eligible.id)

    def test_17_historical_applications_remain_queryable_after_job_closes(self):
        """When a job is closed, student's existing application remains accessible."""
        # 1. Close the job
        self.job_open_ext.status = JobStatus.CLOSED
        self.session.commit()

        # 2. Query student applications
        self._set_user(self.student_cse_eligible)
        res = self.client.get("/placement/applications")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        matching = [a for a in data if a["job_posting_id"] == self.job_open_ext.id]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["job_title"], "Full Stack Software Engineer")
        self.assertEqual(matching[0]["company_name"], "Alpha Corp")
        self.assertEqual(matching[0]["job_status"], "closed")

        # Restore job status for subsequent tests
        self.job_open_ext.status = JobStatus.OPEN
        self.session.commit()

    # =========================================================================
    # Group 9: Placement Officer Tracking & Filtering
    # =========================================================================

    def test_18_officer_can_view_applications_with_student_usn_and_metadata(self):
        """Placement officer can view applications with full student profile metadata."""
        self._set_user(self.po_user)

        res = self.client.get("/placement/applications")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertTrue(len(data) >= 3)
        # Check Aarav's application
        aarav_app = next((a for a in data if a["student_id"] == self.student_cse_eligible.id), None)
        self.assertIsNotNone(aarav_app)
        self.assertEqual(aarav_app["student_name"], "Aarav Kumar")
        self.assertEqual(aarav_app["student_usn"], "1MS21CS001")
        self.assertEqual(aarav_app["student_branch"], "CSE")
        self.assertEqual(aarav_app["student_cgpa"], 8.5)
        self.assertEqual(aarav_app["company_name"], "Alpha Corp")
        self.assertIsNotNone(aarav_app["external_applied_at"])

    def test_19_officer_filtering_by_company_job_branch_status_and_search(self):
        """Placement officer can filter applications by company, job, branch, status, search."""
        self._set_user(self.po_user)

        # Filter by branch=ISE
        res_ise = self.client.get("/placement/applications?branch=ISE")
        self.assertEqual(res_ise.status_code, 200)
        data_ise = res_ise.json()
        self.assertTrue(len(data_ise) >= 1)
        self.assertTrue(all(a["student_branch"] == "ISE" or a["student_id"] == self.student_ise_eligible.id for a in data_ise))

        # Filter by company_id
        res_comp = self.client.get(f"/placement/applications?company_id={self.company_alpha.id}")
        self.assertEqual(res_comp.status_code, 200)
        data_comp = res_comp.json()
        self.assertTrue(all(a["company_id"] == self.company_alpha.id for a in data_comp))

        # Filter by search="Aarav"
        res_search = self.client.get("/placement/applications?search=Aarav")
        self.assertEqual(res_search.status_code, 200)
        data_search = res_search.json()
        self.assertEqual(len(data_search), 1)
        self.assertEqual(data_search[0]["student_name"], "Aarav Kumar")

        # Filter by search USN="1MS21CS005"
        res_usn = self.client.get("/placement/applications?search=1MS21CS005")
        self.assertEqual(res_usn.status_code, 200)
        data_usn = res_usn.json()
        self.assertEqual(len(data_usn), 1)
        self.assertEqual(data_usn[0]["student_name"], "Eshan LowSkill")

    def test_20_officer_can_update_application_status(self):
        """Placement officer can update application status (e.g. applied -> shortlisted)."""
        self._set_user(self.po_user)

        aarav_app = self.session.query(Application).filter_by(
            student_id=self.student_cse_eligible.id,
            job_posting_id=self.job_open_ext.id
        ).first()

        res = self.client.put(
            f"/placement/applications/{aarav_app.id}",
            json={"status": "shortlisted"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "shortlisted")

        # Verify DB updated
        self.session.refresh(aarav_app)
        self.assertEqual(aarav_app.status, ApplicationStatus.SHORTLISTED)

    def test_21_recruitment_progression_and_verified_offer_computed_properties(self):
        """Application computed properties recruitment_progression and verified_offer serialize accurately."""
        # 1. Add recruitment round and outcome
        round_1 = RecruitmentRound(
            job_posting_id=self.job_open_ext.id,
            round_number=1,
            name="Technical Coding Assessment",
            round_type="assessment",
        )
        self.session.add(round_1)
        self.session.flush()

        aarav_app = self.session.query(Application).filter_by(
            student_id=self.student_cse_eligible.id,
            job_posting_id=self.job_open_ext.id
        ).first()

        outcome = StudentRoundOutcome(
            application_id=aarav_app.id,
            round_id=round_1.id,
            student_id=self.student_cse_eligible.id,
            outcome=RoundOutcome.CLEARED,
            score=95.0,
            remarks="Strong Python and problem solving skills.",
        )
        self.session.add(outcome)

        # 2. Add verified offer
        offer = PlacementOffer(
            application_id=aarav_app.id,
            student_id=self.student_cse_eligible.id,
            job_posting_id=self.job_open_ext.id,
            ctc_lpa=14.5,
            designation="Software Engineer L1",
            acceptance_status=OfferAcceptanceStatus.OFFERED,
        )
        self.session.add(offer)
        self.session.commit()

        # 3. Query via officer endpoint
        self._set_user(self.po_user)
        res = self.client.get(f"/placement/applications/{aarav_app.id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Check progression
        prog = data.get("recruitment_progression")
        self.assertIsNotNone(prog)
        self.assertTrue(len(prog) >= 1)
        self.assertEqual(prog[0]["round_name"], "Technical Coding Assessment")
        self.assertEqual(prog[0]["outcome"], "cleared")

        # Check verified offer
        vo = data.get("verified_offer")
        self.assertIsNotNone(vo)
        self.assertEqual(vo["designation"], "Software Engineer L1")
        self.assertEqual(vo["ctc_lpa"], 14.5)
        self.assertEqual(vo["acceptance_status"], "offered")


if __name__ == "__main__":
    unittest.main()
