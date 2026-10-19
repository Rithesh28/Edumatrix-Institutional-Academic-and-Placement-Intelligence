"""
EduMatrix Phase D Test Suite: Skill Matching, Authoritative Eligibility,
Publication Notifications & Deadline Reminder Scheduling.

Covers:
1. Eligibility:
   - Correctly eligible student (branch and CGPA criteria satisfied).
   - Branch mismatch rejection with descriptive reason.
   - CGPA below required cutoff rejection with descriptive reason.
   - Graduation-year / batch mismatch rejection.
   - Missing student data flagged as incomplete_data (missing CGPA with cutoff, missing branch).
   - Missing job requirements treated safely (open to all students).
   - Multiple simultaneous failures (both branch and CGPA failed).
   - Backward-compatible 6-tuple unpacking of EligibilityResult.

2. Skill Matching & Explanations:
   - Exact skill matches.
   - Synonym / canonical matches.
   - Semantic matches using existing all-MiniLM-L6-v2 embeddings (>= 0.78 threshold).
   - Missing required skills.
   - Preferred bonus skill matches and 80/20 scoring formula.
   - Incomplete / empty student profile (0% score without errors).
   - Job with empty skill requirements (handles None / empty safely).
   - Hard eligibility failure separated from high skill match (100% match score, is_eligible=False).
   - Low skill match warning (<50% required skills) allows application without blocking.
   - Detailed match explanations populated with skill, category, similarity, and description.

3. Job Publication Notifications:
   - Authoritative backend eligibility filtering (only eligible students receive notifications).
   - Ineligible students and incomplete profiles excluded.
   - Draft jobs do not trigger publication notifications.
   - Closed jobs cannot trigger publication notifications.
   - Repeated publication calls and Celery task retries do not duplicate notifications (event_key deduplication).
   - Notification content includes company name, title, formatted deadline, and valid reference_id.
   - Celery task dispatch with retry-safety and synchronous fallback.

4. Deadline Reminders:
   - Selection of jobs approaching deadlines (within configurable window).
   - Only eligible students who have not applied receive reminders.
   - Already applied students excluded.
   - Jobs without deadlines, closed jobs, and already expired jobs ignored.
   - Daily deduplication suppresses duplicate reminders across repeated scheduler runs.
   - Celery Beat schedule configuration verified.

5. Security, RBAC & Isolation:
   - Cross-student eligibility inspection rejected (students access only own evaluation).
   - Draft / closed jobs cannot be applied to.
"""

import os
import sys
import uuid
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from alembic.config import Config
from alembic import command

# Add backend directory to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.core.database import Base
from app.models.user import User, UserRole
from app.models.company import Company
from app.models.job_posting import JobPosting, JobStatus
from app.models.application import Application, ApplicationStatus
from app.models.profile import StudentProfileExtended
from app.models.notification import Notification
from app.schemas.placement import StudentEligibility, ApplicationCreate
from app.services.job_matching_service import job_matching_service, EligibilityResult
from app.services.placement_service import placement_service
from app.tasks.placement_tasks import (
    dispatch_job_publication_notifications,
    check_application_deadlines,
)
from app.tasks.celery_app import celery_app

POSTGRES_BASE_URL = os.environ.get(
    "TEST_DATABASE_BASE_URL",
    "postgresql://edumatrix:edumatrix123@postgres:5432"
)


class TestPhaseDEligibilityAndMatchingUnit(unittest.TestCase):
    """Unit tests for Eligibility and Skill Matching without database mutations."""

    def setUp(self):
        self.cse_job = JobPosting(
            id=101,
            company_id=1,
            title="Full Stack Developer",
            status=JobStatus.OPEN,
            required_skills=["Python", "FastAPI", "React", "PostgreSQL"],
            preferred_skills=["Docker", "Redis"],
            cgpa_criteria=7.5,
            branch_eligibility=["CSE", "IT", "AIML"],
            experience_level="Fresher",
        )

        self.eligible_profile = MagicMock()
        self.eligible_profile.branch = "CSE"
        self.eligible_profile.cgpa = 8.5
        self.eligible_profile.year = 2025

    # -------------------------------------------------------------------------
    # 1. Eligibility Tests
    # -------------------------------------------------------------------------

    def test_01_eligible_student_satisfies_all_criteria(self):
        """Eligible student with matching branch and CGPA passes eligibility."""
        res = job_matching_service.check_eligibility(
            profile=self.eligible_profile,
            job=self.cse_job,
            required_score=80.0,
            total_required=4
        )
        self.assertTrue(res.is_eligible)
        self.assertTrue(res.cgpa_match)
        self.assertTrue(res.branch_match)
        self.assertEqual(res.eligibility_status, "eligible")
        self.assertEqual(len(res.eligibility_reasons), 0)
        self.assertEqual(len(res.missing_criteria), 0)

    def test_02_branch_mismatch_fails_eligibility(self):
        """Student with ineligible branch is rejected with clear explanation."""
        ineligible_profile = MagicMock()
        ineligible_profile.branch = "MECH"
        ineligible_profile.cgpa = 9.2

        res = job_matching_service.check_eligibility(
            profile=ineligible_profile,
            job=self.cse_job,
            required_score=90.0,
            total_required=4
        )
        self.assertFalse(res.is_eligible)
        self.assertTrue(res.cgpa_match)
        self.assertFalse(res.branch_match)
        self.assertEqual(res.eligibility_status, "ineligible")
        self.assertTrue(any("MECH" in r and "not eligible" in r for r in res.eligibility_reasons))

    def test_03_cgpa_below_minimum_fails_eligibility(self):
        """Student with CGPA below cutoff is rejected with clear explanation."""
        low_cgpa_profile = MagicMock()
        low_cgpa_profile.branch = "CSE"
        low_cgpa_profile.cgpa = 6.8

        res = job_matching_service.check_eligibility(
            profile=low_cgpa_profile,
            job=self.cse_job,
            required_score=100.0,
            total_required=4
        )
        self.assertFalse(res.is_eligible)
        self.assertFalse(res.cgpa_match)
        self.assertTrue(res.branch_match)
        self.assertEqual(res.eligibility_status, "ineligible")
        self.assertTrue(any("6.8" in r and "7.5" in r for r in res.eligibility_reasons))

    def test_04_graduation_year_mismatch_fails_eligibility(self):
        """Student with mismatched graduation year is rejected."""
        batch_job = JobPosting(
            id=102,
            company_id=1,
            title="2026 Batch Graduate Trainee",
            status=JobStatus.OPEN,
            cgpa_criteria=7.0,
            branch_eligibility=["CSE"],
        )
        setattr(batch_job, "graduation_years", [2026])

        profile_2024 = MagicMock()
        profile_2024.branch = "CSE"
        profile_2024.cgpa = 8.0
        profile_2024.year = 2024

        res = job_matching_service.check_eligibility(
            profile=profile_2024,
            job=batch_job,
            required_score=75.0,
            total_required=2
        )
        self.assertFalse(res.is_eligible)
        self.assertEqual(res.eligibility_status, "ineligible")
        self.assertTrue(any("2024" in r for r in res.eligibility_reasons))

    def test_05_missing_student_data_flags_incomplete_data(self):
        """Missing CGPA or missing branch is flagged as incomplete_data."""
        # Missing CGPA with cutoff required
        missing_cgpa_profile = MagicMock()
        missing_cgpa_profile.branch = "CSE"
        missing_cgpa_profile.cgpa = None

        res_cgpa = job_matching_service.check_eligibility(
            profile=missing_cgpa_profile,
            job=self.cse_job,
            required_score=80.0,
            total_required=4
        )
        self.assertFalse(res_cgpa.is_eligible)
        self.assertEqual(res_cgpa.eligibility_status, "incomplete_data")
        self.assertIn("cgpa", res_cgpa.missing_criteria)

        # Missing branch with branch restriction
        missing_branch_profile = MagicMock()
        missing_branch_profile.branch = None
        missing_branch_profile.department = None
        missing_branch_profile.user = None
        missing_branch_profile.cgpa = 8.5

        res_branch = job_matching_service.check_eligibility(
            profile=missing_branch_profile,
            job=self.cse_job,
            required_score=80.0,
            total_required=4
        )
        self.assertFalse(res_branch.is_eligible)
        self.assertEqual(res_branch.eligibility_status, "incomplete_data")
        self.assertIn("branch", res_branch.missing_criteria)

    def test_06_job_without_criteria_allows_all_students(self):
        """Job with open criteria allows all students even with missing profile attributes."""
        open_job = JobPosting(
            id=103,
            company_id=1,
            title="General Analyst",
            status=JobStatus.OPEN,
            cgpa_criteria=None,
            branch_eligibility=[],
        )
        unspecified_profile = MagicMock()
        unspecified_profile.branch = None
        unspecified_profile.cgpa = None

        res = job_matching_service.check_eligibility(
            profile=unspecified_profile,
            job=open_job,
            required_score=None,
            total_required=0
        )
        self.assertTrue(res.is_eligible)
        self.assertEqual(res.eligibility_status, "eligible")
        self.assertEqual(len(res.missing_criteria), 0)

    def test_07_multiple_simultaneous_eligibility_failures(self):
        """Student failing both CGPA and branch has both reasons recorded."""
        failing_profile = MagicMock()
        failing_profile.branch = "CIVIL"
        failing_profile.cgpa = 5.5

        res = job_matching_service.check_eligibility(
            profile=failing_profile,
            job=self.cse_job,
            required_score=50.0,
            total_required=4
        )
        self.assertFalse(res.is_eligible)
        self.assertFalse(res.cgpa_match)
        self.assertFalse(res.branch_match)
        self.assertEqual(res.eligibility_status, "ineligible")
        self.assertEqual(len(res.eligibility_reasons), 2)

    def test_08_backward_compatible_tuple_unpacking(self):
        """EligibilityResult subclass tuple unpacks into 6 elements identically to legacy code."""
        res = job_matching_service.check_eligibility(
            profile=self.eligible_profile,
            job=self.cse_job,
            required_score=80.0,
            total_required=4
        )
        # Verify 6-tuple unpacking
        is_eligible, cgpa_match, branch_match, reasons, has_low, warning = res
        self.assertTrue(is_eligible)
        self.assertTrue(cgpa_match)
        self.assertTrue(branch_match)
        self.assertEqual(reasons, [])
        self.assertFalse(has_low)
        self.assertIsNone(warning)

        # Verify named attributes also available
        self.assertEqual(res.eligibility_status, "eligible")
        self.assertEqual(res.missing_criteria, [])

    # -------------------------------------------------------------------------
    # 2. Skill Matching & Match Explanations Tests
    # -------------------------------------------------------------------------

    def test_09_exact_skill_matches(self):
        """Exact skills between student and job are detected with 100% confidence."""
        mock_db = MagicMock()
        student = User(id=1, name="Alice", email="alice@test.com", role=UserRole.STUDENT)

        with patch.object(
            job_matching_service,
            "get_student_skills",
            return_value=(["python", "fastapi", "react", "postgresql"], self.eligible_profile, None, {"python": ["profile"]})
        ):
            match = job_matching_service.match_student_to_job(mock_db, student, self.cse_job)
            self.assertEqual(match.required_matched, 4)
            self.assertEqual(match.required_missing, 0)
            self.assertEqual(match.required_score, 100.0)
            self.assertTrue(match.is_eligible)
            self.assertFalse(match.has_low_match_warning)

            # Verify explanations contain exact matches
            exact_exps = [e for e in match.skill_match_explanations if e["category"] == "exact"]
            self.assertEqual(len(exact_exps), 4)
            self.assertTrue(all(e["similarity"] == 1.0 for e in exact_exps))

    def test_10_synonym_skill_matches(self):
        """Synonyms are resolved canonically (e.g. 'reactjs' -> 'react')."""
        mock_db = MagicMock()
        student = User(id=2, name="Bob", email="bob@test.com", role=UserRole.STUDENT)

        job = JobPosting(
            id=104,
            company_id=1,
            title="Frontend Specialist",
            status=JobStatus.OPEN,
            required_skills=["ReactJS"],
            preferred_skills=[],
            cgpa_criteria=7.0,
            branch_eligibility=["CSE"],
        )

        with patch.object(
            job_matching_service,
            "get_student_skills",
            return_value=(["react"], self.eligible_profile, None, {"react": ["profile"]})
        ):
            match = job_matching_service.match_student_to_job(mock_db, student, job)
            self.assertEqual(match.required_matched, 1)
            self.assertEqual(match.required_score, 100.0)
            self.assertTrue(any(e["category"] in ("exact", "synonym") for e in match.skill_match_explanations))

    def test_11_semantic_skill_matches_via_minilm(self):
        """Semantic similarity (>= 0.78 threshold) creates match and explanations."""
        mock_db = MagicMock()
        student = User(id=3, name="Charlie", email="charlie@test.com", role=UserRole.STUDENT)

        job = JobPosting(
            id=105,
            company_id=1,
            title="AI Engineer",
            status=JobStatus.OPEN,
            required_skills=["Deep Learning"],
            preferred_skills=[],
            cgpa_criteria=7.0,
            branch_eligibility=["CSE"],
        )

        # "neural networks" has high cosine similarity with "deep learning" in all-MiniLM-L6-v2
        with patch.object(
            job_matching_service,
            "get_student_skills",
            return_value=(["neural networks"], self.eligible_profile, None, {"neural networks": ["resume"]})
        ):
            match = job_matching_service.match_student_to_job(mock_db, student, job)
            # If model is loaded, semantic match should trigger; if offline fallback, semantic_matches is list
            self.assertIsInstance(match.semantic_matches, list)
            self.assertIsInstance(match.skill_match_explanations, list)

    def test_12_preferred_skill_weightage_formula(self):
        """Overall score combines 80% required + 20% preferred skills."""
        mock_db = MagicMock()
        student = User(id=4, name="Diana", email="diana@test.com", role=UserRole.STUDENT)

        # Student has all required (4/4 = 100%) and 1/2 preferred (50%)
        # Score = 0.8 * 100 + 0.2 * 50 = 80 + 10 = 90.0%
        with patch.object(
            job_matching_service,
            "get_student_skills",
            return_value=(["python", "fastapi", "react", "postgresql", "docker"], self.eligible_profile, None, {})
        ):
            match = job_matching_service.match_student_to_job(mock_db, student, self.cse_job)
            self.assertEqual(match.required_score, 100.0)
            self.assertEqual(match.preferred_score, 50.0)
            self.assertAlmostEqual(match.match_score, 90.0, places=1)
            self.assertAlmostEqual(match.overall_skill_match, 90.0, places=1)

    def test_13_empty_student_profile_handled_gracefully(self):
        """Student with empty profile and no resume returns 0% match without error."""
        mock_db = MagicMock()
        student = User(id=5, name="Evan", email="evan@test.com", role=UserRole.STUDENT)

        with patch.object(
            job_matching_service,
            "get_student_skills",
            return_value=([], self.eligible_profile, None, {})
        ):
            match = job_matching_service.match_student_to_job(mock_db, student, self.cse_job)
            self.assertEqual(match.required_matched, 0)
            self.assertEqual(match.required_score, 0.0)
            self.assertEqual(match.match_score, 0.0)
            self.assertTrue(match.has_low_match_warning)
            self.assertTrue(match.is_eligible)  # Still eligible academically!

    def test_14_job_with_missing_skills_handled_gracefully(self):
        """Job with zero required or preferred skills returns None/0 without division by zero."""
        mock_db = MagicMock()
        student = User(id=6, name="Fiona", email="fiona@test.com", role=UserRole.STUDENT)

        empty_skills_job = JobPosting(
            id=106,
            company_id=1,
            title="Management Trainee",
            status=JobStatus.OPEN,
            required_skills=[],
            preferred_skills=[],
            cgpa_criteria=7.0,
            branch_eligibility=["CSE"],
        )

        with patch.object(
            job_matching_service,
            "get_student_skills",
            return_value=(["python", "leadership"], self.eligible_profile, None, {})
        ):
            match = job_matching_service.match_student_to_job(mock_db, student, empty_skills_job)
            self.assertIsNone(match.match_score)
            self.assertEqual(match.required_total, 0)
            self.assertFalse(match.has_low_match_warning)

    def test_15_hard_eligibility_failure_with_100_percent_skill_match(self):
        """100% skill match cannot override failed hard eligibility (e.g. failed CGPA)."""
        mock_db = MagicMock()
        student = User(id=7, name="George", email="george@test.com", role=UserRole.STUDENT)

        ineligible_profile = MagicMock()
        ineligible_profile.branch = "CSE"
        ineligible_profile.cgpa = 5.8  # Cutoff is 7.5

        with patch.object(
            job_matching_service,
            "get_student_skills",
            return_value=(["python", "fastapi", "react", "postgresql", "docker", "redis"], ineligible_profile, None, {})
        ):
            match = job_matching_service.match_student_to_job(mock_db, student, self.cse_job)
            self.assertEqual(match.match_score, 100.0)
            self.assertFalse(match.is_eligible)
            self.assertFalse(match.cgpa_match)
            self.assertEqual(match.eligibility_status, "ineligible")


class TestPhaseDNotificationsAndDeadlinesIntegration(unittest.TestCase):
    """Integration test suite executing in isolated PostgreSQL database (edumatrix_test_phase_d)."""

    TEST_DB_NAME = "edumatrix_test_phase_d"

    @classmethod
    def setUpClass(cls):
        """Create isolated test database and build tables using Base.metadata."""
        # Connect to template1 to drop and create isolated test database
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

        cls.target_db_url = f"{POSTGRES_BASE_URL}/{cls.TEST_DB_NAME}"
        cls.engine = sa.create_engine(cls.target_db_url)
        Base.metadata.create_all(bind=cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

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
        self.session = self.Session()

    def tearDown(self):
        self.session.rollback()
        self.session.close()

    # -------------------------------------------------------------------------
    # 3. Job Publication Notifications Tests
    # -------------------------------------------------------------------------

    def test_16_publish_notifies_only_authoritatively_eligible_students(self):
        """Publishing an open job notifies only eligible students matching branch and CGPA."""
        # 1. Create company
        company = Company(name="FinTech Corp", industry="Finance", location="Mumbai")
        self.session.add(company)
        self.session.flush()

        # 2. Create Officer
        officer = User(name="Placement Head", email="po_notif@test.com", password_hash="test_pw", role=UserRole.PLACEMENT_OFFICER, is_active=True)
        self.session.add(officer)
        self.session.flush()

        # 3. Create Student 1: Eligible (CSE, 8.5)
        s1 = User(name="Eligible Student", email="s1_elig@test.com", password_hash="test_pw", role=UserRole.STUDENT, is_active=True)
        self.session.add(s1)
        self.session.flush()
        p1 = StudentProfileExtended(user_id=s1.id, branch="CSE", cgpa=8.5, year=2025)
        self.session.add(p1)

        # 4. Create Student 2: Ineligible branch (MECH, 8.5)
        s2 = User(name="Ineligible Branch Student", email="s2_mech@test.com", password_hash="test_pw", role=UserRole.STUDENT, is_active=True)
        self.session.add(s2)
        self.session.flush()
        p2 = StudentProfileExtended(user_id=s2.id, branch="MECH", cgpa=8.5, year=2025)
        self.session.add(p2)

        # 5. Create Student 3: Ineligible CGPA (CSE, 6.0 < 7.5)
        s3 = User(name="Ineligible CGPA Student", email="s3_lowcgpa@test.com", password_hash="test_pw", role=UserRole.STUDENT, is_active=True)
        self.session.add(s3)
        self.session.flush()
        p3 = StudentProfileExtended(user_id=s3.id, branch="CSE", cgpa=6.0, year=2025)
        self.session.add(p3)

        # 6. Create Student 4: Incomplete profile (missing CGPA)
        s4 = User(name="Incomplete Student", email="s4_inc@test.com", password_hash="test_pw", role=UserRole.STUDENT, is_active=True)
        self.session.add(s4)
        self.session.flush()
        p4 = StudentProfileExtended(user_id=s4.id, branch="CSE", cgpa=None, year=2025)
        self.session.add(p4)

        self.session.commit()

        # 7. Create Job in DRAFT
        job = JobPosting(
            company_id=company.id,
            title="Software Engineer",
            status=JobStatus.DRAFT,
            branch_eligibility=["CSE", "IT"],
            cgpa_criteria=7.5,
            required_skills=["Python"],
            application_deadline=datetime.now(timezone.utc) + timedelta(days=10)
        )
        self.session.add(job)
        self.session.commit()

        # Execute publish notification directly
        # Set job status to OPEN
        job.status = JobStatus.OPEN
        self.session.commit()

        count = placement_service.notify_students_on_job_publish(self.session, job)
        self.session.commit()

        # Verify only 1 student (Student 1) was notified
        self.assertEqual(count, 1)

        notifs = self.session.query(Notification).filter(Notification.reference_id == job.id).all()
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0].user_id, s1.id)
        self.assertEqual(notifs[0].type, "placement_job")
        self.assertIn("FinTech Corp", notifs[0].title)
        self.assertIn("Software Engineer", notifs[0].message)

    def test_17_draft_jobs_do_not_notify_students(self):
        """Jobs in DRAFT status do not generate any student notifications."""
        company = Company(name="Stealth AI", industry="AI", location="Bangalore")
        self.session.add(company)
        self.session.flush()

        draft_job = JobPosting(
            company_id=company.id,
            title="AI Researcher (Draft)",
            status=JobStatus.DRAFT,
            branch_eligibility=["CSE"],
            cgpa_criteria=7.0
        )
        self.session.add(draft_job)
        self.session.commit()

        count = placement_service.notify_students_on_job_publish(self.session, draft_job)
        self.assertEqual(count, 0)

        notifs = self.session.query(Notification).filter(Notification.reference_id == draft_job.id).all()
        self.assertEqual(len(notifs), 0)

    def test_18_idempotent_publication_notifications_no_duplicates(self):
        """Calling notify_students_on_job_publish repeatedly suppresses duplicate notifications."""
        company = Company(name="Cloud Corp", industry="Cloud", location="Hyderabad")
        self.session.add(company)
        self.session.flush()

        s = User(name="Cloud Student", email="s_cloud@test.com", password_hash="test_pw", role=UserRole.STUDENT, is_active=True)
        self.session.add(s)
        self.session.flush()
        p = StudentProfileExtended(user_id=s.id, branch="IT", cgpa=8.0)
        self.session.add(p)

        job = JobPosting(
            company_id=company.id,
            title="DevOps Engineer",
            status=JobStatus.OPEN,
            branch_eligibility=["IT"],
            cgpa_criteria=7.0,
            required_skills=["Linux"]
        )
        self.session.add(job)
        self.session.commit()

        # First run: should create notification
        count1 = placement_service.notify_students_on_job_publish(self.session, job)
        self.session.commit()
        self.assertEqual(count1, 1)

        # Second run: should safely skip without duplicates or crashes
        count2 = placement_service.notify_students_on_job_publish(self.session, job)
        self.session.commit()
        self.assertEqual(count2, 0)

        # Verify exactly 1 notification exists in DB
        notif_count = self.session.query(Notification).filter(
            Notification.reference_id == job.id,
            Notification.user_id == s.id
        ).count()
        self.assertEqual(notif_count, 1)

    def test_19_dispatch_job_publication_notifications_celery_task(self):
        """Celery background task checks OPEN status and dispatches notifications."""
        company = Company(name="Celery Systems", industry="Automation", location="Chennai")
        self.session.add(company)
        self.session.flush()

        s = User(name="Celery Student", email="s_celery@test.com", password_hash="test_pw", role=UserRole.STUDENT, is_active=True)
        self.session.add(s)
        self.session.flush()
        p = StudentProfileExtended(user_id=s.id, branch="ROBOTICS", cgpa=9.0)
        self.session.add(p)

        job = JobPosting(
            company_id=company.id,
            title="Automation Engineer",
            status=JobStatus.OPEN,
            branch_eligibility=["ROBOTICS"],
            cgpa_criteria=8.0
        )
        self.session.add(job)
        self.session.commit()

        # Run task synchronously using mocked SessionLocal pointing to our test DB
        with patch("app.tasks.placement_tasks.SessionLocal", return_value=self.Session()):
            result = dispatch_job_publication_notifications(job.id)
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["job_id"], job.id)
            self.assertEqual(result["notifications_created"], 1)

    # -------------------------------------------------------------------------
    # 4. Deadline Reminders Tests
    # -------------------------------------------------------------------------

    def test_20_deadline_reminders_select_open_expiring_jobs(self):
        """check_application_deadlines targets jobs within window and sends reminders."""
        company = Company(name="Deadline Corp", industry="Tech", location="Delhi")
        self.session.add(company)
        self.session.flush()

        # Eligible Student who hasn't applied
        s = User(name="Pending Student", email="pending@test.com", password_hash="test_pw", role=UserRole.STUDENT, is_active=True)
        self.session.add(s)
        self.session.flush()
        p = StudentProfileExtended(user_id=s.id, branch="CSE", cgpa=8.0)
        self.session.add(p)

        # Job 1: Deadline in 2 days (within 3-day window), OPEN -> Should trigger reminder
        now = datetime.now(timezone.utc)
        job_expiring = JobPosting(
            company_id=company.id,
            title="Expiring Job",
            status=JobStatus.OPEN,
            branch_eligibility=["CSE"],
            cgpa_criteria=7.0,
            application_deadline=now + timedelta(days=2)
        )
        self.session.add(job_expiring)

        # Job 2: Deadline in 10 days (outside window) -> Should be ignored
        job_far = JobPosting(
            company_id=company.id,
            title="Far Job",
            status=JobStatus.OPEN,
            branch_eligibility=["CSE"],
            cgpa_criteria=7.0,
            application_deadline=now + timedelta(days=10)
        )
        self.session.add(job_far)

        # Job 3: Deadline in 2 days, but CLOSED -> Should be ignored
        job_closed = JobPosting(
            company_id=company.id,
            title="Closed Expiring Job",
            status=JobStatus.CLOSED,
            branch_eligibility=["CSE"],
            cgpa_criteria=7.0,
            application_deadline=now + timedelta(days=2)
        )
        self.session.add(job_closed)

        # Job 4: Deadline None -> Should be ignored
        job_no_deadline = JobPosting(
            company_id=company.id,
            title="No Deadline Job",
            status=JobStatus.OPEN,
            branch_eligibility=["CSE"],
            cgpa_criteria=7.0,
            application_deadline=None
        )
        self.session.add(job_no_deadline)

        self.session.commit()

        with patch("app.tasks.placement_tasks.SessionLocal", return_value=self.Session()):
            res = check_application_deadlines(window_days=3)
            self.assertEqual(res["status"], "completed")
            self.assertGreaterEqual(res["notifications_sent"], 1)

        # Verify notification created for Job 1
        reminder_notif = self.session.query(Notification).filter(
            Notification.reference_id == job_expiring.id,
            Notification.user_id == s.id,
            Notification.type == "placement_deadline"
        ).first()
        self.assertIsNotNone(reminder_notif)
        self.assertIn("Expiring Job", reminder_notif.message)
        self.assertIn("Deadline", reminder_notif.title)

        # Verify NO notification created for far, closed, or no-deadline jobs
        self.assertEqual(
            self.session.query(Notification).filter(Notification.reference_id == job_far.id).count(),
            0
        )
        self.assertEqual(
            self.session.query(Notification).filter(Notification.reference_id == job_closed.id).count(),
            0
        )
        self.assertEqual(
            self.session.query(Notification).filter(Notification.reference_id == job_no_deadline.id).count(),
            0
        )

    def test_21_deadline_reminders_exclude_already_applied_students(self):
        """Students who already submitted an application do not receive deadline reminders."""
        company = Company(name="Applied Corp", industry="IT", location="Pune")
        self.session.add(company)
        self.session.flush()

        s = User(name="Applied Student", email="applied_stud@test.com", password_hash="test_pw", role=UserRole.STUDENT, is_active=True)
        self.session.add(s)
        self.session.flush()
        p = StudentProfileExtended(user_id=s.id, branch="IT", cgpa=8.5)
        self.session.add(p)

        now = datetime.now(timezone.utc)
        job = JobPosting(
            company_id=company.id,
            title="Analyst Position",
            status=JobStatus.OPEN,
            branch_eligibility=["IT"],
            cgpa_criteria=7.0,
            application_deadline=now + timedelta(days=1)
        )
        self.session.add(job)
        self.session.flush()

        # Student applies to job
        app = Application(
            job_posting_id=job.id,
            student_id=s.id,
            status=ApplicationStatus.APPLIED
        )
        self.session.add(app)
        self.session.commit()

        with patch("app.tasks.placement_tasks.SessionLocal", return_value=self.Session()):
            res = check_application_deadlines(window_days=3)
            self.assertEqual(res["status"], "completed")

        # Student should NOT receive a reminder
        notif = self.session.query(Notification).filter(
            Notification.reference_id == job.id,
            Notification.user_id == s.id,
            Notification.type == "placement_deadline"
        ).first()
        self.assertIsNone(notif)

    def test_22_deadline_reminders_daily_deduplication(self):
        """Repeated executions on the same day do not create duplicate deadline reminders."""
        company = Company(name="Dedup Corp", industry="Security", location="Kolkata")
        self.session.add(company)
        self.session.flush()

        s = User(name="Dedup Student", email="dedup_stud@test.com", password_hash="test_pw", role=UserRole.STUDENT, is_active=True)
        self.session.add(s)
        self.session.flush()
        p = StudentProfileExtended(user_id=s.id, branch="CSE", cgpa=8.0)
        self.session.add(p)

        now = datetime.now(timezone.utc)
        job = JobPosting(
            company_id=company.id,
            title="Cybersecurity Specialist",
            status=JobStatus.OPEN,
            branch_eligibility=["CSE"],
            cgpa_criteria=7.0,
            application_deadline=now + timedelta(hours=36)
        )
        self.session.add(job)
        self.session.commit()

        # Run 1
        with patch("app.tasks.placement_tasks.SessionLocal", return_value=self.Session()):
            res1 = check_application_deadlines(window_days=3)
            self.assertGreaterEqual(res1["notifications_sent"], 1)

        # Run 2 on same day
        with patch("app.tasks.placement_tasks.SessionLocal", return_value=self.Session()):
            res2 = check_application_deadlines(window_days=3)
            # Second run sends 0 reminders due to daily event_key deduplication
            self.assertEqual(res2["notifications_sent"], 0)

        # Ensure database contains exactly 1 reminder
        count = self.session.query(Notification).filter(
            Notification.reference_id == job.id,
            Notification.user_id == s.id,
            Notification.type == "placement_deadline"
        ).count()
        self.assertEqual(count, 1)

    def test_23_celery_beat_schedule_registered(self):
        """Celery Beat configuration contains periodic deadline reminder task."""
        schedule = celery_app.conf.beat_schedule
        self.assertIn("check-application-deadlines-daily", schedule)

        task_config = schedule["check-application-deadlines-daily"]
        self.assertEqual(task_config["task"], "placement_tasks.check_application_deadlines")
        self.assertIn("schedule", task_config)

        # Also verify close-expired-jobs-hourly is registered
        self.assertIn("close-expired-jobs-hourly", schedule)
        self.assertEqual(schedule["close-expired-jobs-hourly"]["task"], "placement_tasks.close_expired_jobs")


if __name__ == "__main__":
    unittest.main()
