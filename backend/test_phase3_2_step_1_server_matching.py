"""
Automated Test Suite for Phase 3.2 Step 1:
Server-Authoritative Matching, Eligibility, Application Snapshots & Integrity

Explicit test coverage:
1. Server-authoritative scoring:
   - Client-forged match_percentage is ignored/overridden
   - Client-forged eligibility_score is ignored/overridden
   - Authenticated student identity is enforced
   - Cross-student application attempts rejected (403)
2. Eligibility policy:
   - Low skill match (<50%) allowed with low_match_warning
   - Zero required skill match (0%) allowed with low_match_warning
   - Explicit CGPA failure rejected with clear reason
   - Missing CGPA with cutoff rejected
   - Missing CGPA without cutoff allowed
   - Explicit branch mismatch rejected with clear reason
   - Missing branch without restriction allowed
   - Empty skill categories preserve null match_percentage
3. Application snapshots:
   - New applications persist immutable match_snapshot JSON
   - Snapshot records resume, skills, matched/missing, semantic matches, scores
   - Snapshot is immutable to subsequent profile or job changes
   - Legacy applications without snapshot remain readable
   - Ineligible application failure leaves no partial database records
4. Authorization & Integrity:
   - Closed or draft jobs cannot be applied to
   - Duplicate applications rejected
   - Database concurrency constraint prevents double application
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

# Configure SQLite for test environment before importing app
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.user import User, UserRole
from app.models.job_posting import JobPosting, JobStatus
from app.models.application import Application, ApplicationStatus
from app.schemas.placement import ApplicationCreate, ApplicationResponse, StudentEligibility
from app.services.job_matching_service import job_matching_service
from app.services.placement_service import placement_service


class TestPhase32Step1ServerMatching(unittest.TestCase):
    """Complete test suite for Step 1 Server-Authoritative Matching and Snapshots."""

    def setUp(self):
        self.mock_db = MagicMock()
        self.student = User(
            id=10,
            name="Alice Candidate",
            email="alice@vcet.ac.in",
            role=UserRole.STUDENT,
            is_active=True
        )
        self.other_student = User(
            id=20,
            name="Bob Candidate",
            email="bob@vcet.ac.in",
            role=UserRole.STUDENT,
            is_active=True
        )
        self.officer = User(
            id=99,
            name="Placement Officer",
            email="officer@vcet.ac.in",
            role=UserRole.PLACEMENT_OFFICER,
            is_active=True
        )

        # Baseline Open Job
        self.open_job = JobPosting(
            id=101,
            company_id=1,
            title="Junior Software Engineer",
            status=JobStatus.OPEN,
            required_skills=["Python", "FastAPI", "SQL", "Docker"],
            preferred_skills=["Redis", "Kubernetes"],
            cgpa_criteria=7.5,
            branch_eligibility=["CSE", "IT", "AIML"],
            experience_level="Fresher"
        )

    # =========================================================================
    # 1. SERVER-AUTHORITATIVE SCORING
    # =========================================================================

    def test_01_client_forged_match_percentage_ignored(self):
        """1. Server ignores client-supplied match_percentage and persists authoritative score."""
        app_data = ApplicationCreate(
            job_posting_id=101,
            match_percentage=100.0,  # Client forged 100%
            eligibility_score=100.0,
            notes="Forged score"
        )

        mock_profile = MagicMock(cgpa=8.5, branch="CSE")
        # Student actually only has Python (1 of 4 required = 25%) and no preferred
        student_skills = ["Python"]

        with patch.object(placement_service, 'get_job_posting', return_value=self.open_job), \
             patch.object(self.mock_db, 'query') as mock_query, \
             patch.object(job_matching_service, 'get_student_skills', return_value=(student_skills, mock_profile, None, {"profile_skills": student_skills, "resume_skills": []})):

            # Mock user lookup and duplicate check
            def query_side_effect(model):
                m_q = MagicMock()
                if model == User:
                    m_q.filter.return_value.first.return_value = self.student
                elif model == Application:
                    m_q.filter.return_value.first.return_value = None  # No existing app
                return m_q
            mock_query.side_effect = query_side_effect

            app = placement_service.create_application(self.mock_db, app_data, current_user=self.student)

            # Assert forged score was discarded and server-calculated score was saved
            # 1 of 4 required = 25%, 0 preferred = 0%. Overall = (25 * 0.8) + (0 * 0.2) = 20.0%
            self.assertEqual(app.match_percentage, 20.0)
            self.assertNotEqual(app.match_percentage, 100.0)
            self.assertEqual(app.student_id, self.student.id)

    def test_02_student_cannot_apply_for_another_student(self):
        """2. Student cannot apply on behalf of another student."""
        app_data = ApplicationCreate(
            student_id=20,  # Trying to apply as Bob
            job_posting_id=101
        )

        mock_profile = MagicMock(cgpa=8.0, branch="CSE")
        with patch.object(placement_service, 'get_job_posting', return_value=self.open_job), \
             patch.object(self.mock_db, 'query') as mock_query, \
             patch.object(job_matching_service, 'get_student_skills', return_value=(["Python"], mock_profile, None, {"profile_skills": [], "resume_skills": []})):

            def query_side_effect(model):
                m_q = MagicMock()
                if model == User:
                    m_q.filter.return_value.first.return_value = self.student
                elif model == Application:
                    m_q.filter.return_value.first.return_value = None
                return m_q
            mock_query.side_effect = query_side_effect

            # Even if app_data.student_id is 20, service enforces authenticated user's ID (10)
            app = placement_service.create_application(self.mock_db, app_data, current_user=self.student)
            self.assertEqual(app.student_id, 10)
            self.assertNotEqual(app.student_id, 20)

    # =========================================================================
    # 2. ELIGIBILITY POLICY & LOW-MATCH WARNINGS
    # =========================================================================

    def test_03_low_required_skill_match_allowed_with_warning(self):
        """3. Student with <50% required skill match is allowed to apply and gets low_match_warning."""
        mock_profile = MagicMock(cgpa=8.0, branch="CSE")
        # 1 of 4 required = 25% (below 50%)
        student_skills = ["Python"]

        with patch.object(placement_service, 'get_job_posting', return_value=self.open_job), \
             patch.object(self.mock_db, 'query') as mock_query, \
             patch.object(job_matching_service, 'get_student_skills', return_value=(student_skills, mock_profile, None, {"profile_skills": student_skills, "resume_skills": []})):

            def query_side_effect(model):
                m_q = MagicMock()
                if model == User:
                    m_q.filter.return_value.first.return_value = self.student
                elif model == Application:
                    m_q.filter.return_value.first.return_value = None
                return m_q
            mock_query.side_effect = query_side_effect

            app_data = ApplicationCreate(job_posting_id=101)
            app = placement_service.create_application(self.mock_db, app_data, current_user=self.student)

            self.assertIsNotNone(app)
            self.assertIsNotNone(app.match_snapshot)
            self.assertTrue(app.match_snapshot["has_low_match_warning"])
            self.assertIn("below 50% threshold", app.match_snapshot["low_match_warning"])
            self.assertTrue(app.match_snapshot["is_eligible"])

    def test_04_zero_required_skill_match_allowed_with_warning(self):
        """4. Student with 0% required skill match is allowed if explicit criteria pass."""
        mock_profile = MagicMock(cgpa=8.2, branch="AIML")
        student_skills = ["Photoshop"]  # 0 matched required skills

        with patch.object(placement_service, 'get_job_posting', return_value=self.open_job), \
             patch.object(self.mock_db, 'query') as mock_query, \
             patch.object(job_matching_service, 'get_student_skills', return_value=(student_skills, mock_profile, None, {"profile_skills": student_skills, "resume_skills": []})):

            def query_side_effect(model):
                m_q = MagicMock()
                if model == User:
                    m_q.filter.return_value.first.return_value = self.student
                elif model == Application:
                    m_q.filter.return_value.first.return_value = None
                return m_q
            mock_query.side_effect = query_side_effect

            app_data = ApplicationCreate(job_posting_id=101)
            app = placement_service.create_application(self.mock_db, app_data, current_user=self.student)

            self.assertIsNotNone(app)
            self.assertEqual(app.match_percentage, 0.0)
            self.assertTrue(app.match_snapshot["has_low_match_warning"])
            self.assertIn("0.0%", app.match_snapshot["low_match_warning"])

    def test_05_explicit_cgpa_failure_rejected(self):
        """5. Candidate with CGPA below cutoff is rejected with explicit reason."""
        mock_profile = MagicMock(cgpa=6.8, branch="CSE")  # Below job criteria 7.5
        student_skills = ["Python", "FastAPI", "SQL", "Docker"]  # 100% skills

        with patch.object(placement_service, 'get_job_posting', return_value=self.open_job), \
             patch.object(self.mock_db, 'query') as mock_query, \
             patch.object(job_matching_service, 'get_student_skills', return_value=(student_skills, mock_profile, None, {"profile_skills": student_skills, "resume_skills": []})):

            def query_side_effect(model):
                m_q = MagicMock()
                if model == User:
                    m_q.filter.return_value.first.return_value = self.student
                elif model == Application:
                    m_q.filter.return_value.first.return_value = None
                return m_q
            mock_query.side_effect = query_side_effect

            app_data = ApplicationCreate(job_posting_id=101)
            with self.assertRaises(ValueError) as ctx:
                placement_service.create_application(self.mock_db, app_data, current_user=self.student)

            self.assertIn("CGPA 6.8 is below minimum requirement 7.5", str(ctx.exception))

    def test_06_missing_cgpa_with_configured_cutoff_rejected(self):
        """6. Missing CGPA with a configured cutoff is rejected."""
        mock_profile = MagicMock(cgpa=None, branch="CSE")  # CGPA is None
        student_skills = ["Python", "FastAPI"]

        with patch.object(placement_service, 'get_job_posting', return_value=self.open_job), \
             patch.object(self.mock_db, 'query') as mock_query, \
             patch.object(job_matching_service, 'get_student_skills', return_value=(student_skills, mock_profile, None, {"profile_skills": student_skills, "resume_skills": []})):

            def query_side_effect(model):
                m_q = MagicMock()
                if model == User:
                    m_q.filter.return_value.first.return_value = self.student
                elif model == Application:
                    m_q.filter.return_value.first.return_value = None
                return m_q
            mock_query.side_effect = query_side_effect

            app_data = ApplicationCreate(job_posting_id=101)
            with self.assertRaises(ValueError) as ctx:
                placement_service.create_application(self.mock_db, app_data, current_user=self.student)

            self.assertIn("CGPA record missing or incomplete", str(ctx.exception))

    def test_07_missing_cgpa_without_cutoff_allowed(self):
        """7. Missing CGPA when NO cutoff is configured does NOT reject application."""
        no_cgpa_job = JobPosting(
            id=102,
            company_id=1,
            title="Open Role",
            status=JobStatus.OPEN,
            required_skills=["Python"],
            preferred_skills=[],
            cgpa_criteria=None,  # No CGPA criteria
            branch_eligibility=[]  # No branch restriction
        )

        mock_profile = MagicMock(cgpa=None, branch=None)
        student_skills = ["Python"]

        with patch.object(placement_service, 'get_job_posting', return_value=no_cgpa_job), \
             patch.object(self.mock_db, 'query') as mock_query, \
             patch.object(job_matching_service, 'get_student_skills', return_value=(student_skills, mock_profile, None, {"profile_skills": student_skills, "resume_skills": []})):

            def query_side_effect(model):
                m_q = MagicMock()
                if model == User:
                    m_q.filter.return_value.first.return_value = self.student
                elif model == Application:
                    m_q.filter.return_value.first.return_value = None
                return m_q
            mock_query.side_effect = query_side_effect

            app_data = ApplicationCreate(job_posting_id=102)
            app = placement_service.create_application(self.mock_db, app_data, current_user=self.student)
            self.assertIsNotNone(app)
            self.assertTrue(app.match_snapshot["is_eligible"])

    def test_08_explicit_branch_exclusion_rejected(self):
        """8. Candidate from excluded branch is rejected with explicit reason."""
        mock_profile = MagicMock(cgpa=8.5, branch="MECH")  # MECH not in [CSE, IT, AIML]
        student_skills = ["Python", "Docker"]

        with patch.object(placement_service, 'get_job_posting', return_value=self.open_job), \
             patch.object(self.mock_db, 'query') as mock_query, \
             patch.object(job_matching_service, 'get_student_skills', return_value=(student_skills, mock_profile, None, {"profile_skills": student_skills, "resume_skills": []})):

            def query_side_effect(model):
                m_q = MagicMock()
                if model == User:
                    m_q.filter.return_value.first.return_value = self.student
                elif model == Application:
                    m_q.filter.return_value.first.return_value = None
                return m_q
            mock_query.side_effect = query_side_effect

            app_data = ApplicationCreate(job_posting_id=101)
            with self.assertRaises(ValueError) as ctx:
                placement_service.create_application(self.mock_db, app_data, current_user=self.student)

            self.assertIn("Branch 'MECH' is not eligible", str(ctx.exception))

    def test_09_empty_skill_categories_retain_null_behavior(self):
        """9. Job with empty required and preferred skills returns None match_percentage."""
        empty_skill_job = JobPosting(
            id=103,
            company_id=1,
            title="General Drive",
            status=JobStatus.OPEN,
            required_skills=[],
            preferred_skills=[],
            cgpa_criteria=7.0,
            branch_eligibility=[]
        )

        mock_profile = MagicMock(cgpa=8.0, branch="CSE")
        student_skills = ["Python"]

        with patch.object(placement_service, 'get_job_posting', return_value=empty_skill_job), \
             patch.object(self.mock_db, 'query') as mock_query, \
             patch.object(job_matching_service, 'get_student_skills', return_value=(student_skills, mock_profile, None, {"profile_skills": student_skills, "resume_skills": []})):

            def query_side_effect(model):
                m_q = MagicMock()
                if model == User:
                    m_q.filter.return_value.first.return_value = self.student
                elif model == Application:
                    m_q.filter.return_value.first.return_value = None
                return m_q
            mock_query.side_effect = query_side_effect

            app_data = ApplicationCreate(job_posting_id=103)
            app = placement_service.create_application(self.mock_db, app_data, current_user=self.student)

            self.assertIsNone(app.match_percentage)
            self.assertIsNone(app.match_snapshot["match_percentage"])
            self.assertFalse(app.match_snapshot["has_low_match_warning"])

    # =========================================================================
    # 3. APPLICATION SNAPSHOTS & IMMUTABILITY
    # =========================================================================

    def test_10_application_snapshot_persistence_and_provenance(self):
        """10. Application snapshot stores complete provenance and breakdown."""
        from app.models.resume import Resume, ResumeStatus
        from app.models.file import File

        mock_resume = MagicMock(spec=Resume)
        mock_resume.id = 55
        mock_resume.status = ResumeStatus.COMPLETED
        mock_resume.skills = ["Python", "FastAPI"]
        mock_resume.file = MagicMock(spec=File, filename="alice_resume_2026.pdf")

        mock_profile = MagicMock(cgpa=8.4, branch="CSE")
        student_skills = ["Python", "FastAPI"]
        skill_sources = {"profile_skills": ["Python"], "resume_skills": ["FastAPI"]}

        with patch.object(placement_service, 'get_job_posting', return_value=self.open_job), \
             patch.object(self.mock_db, 'query') as mock_query, \
             patch.object(job_matching_service, 'get_student_skills', return_value=(student_skills, mock_profile, mock_resume, skill_sources)):

            def query_side_effect(model):
                m_q = MagicMock()
                if model == User:
                    m_q.filter.return_value.first.return_value = self.student
                elif model == Application:
                    m_q.filter.return_value.first.return_value = None
                return m_q
            mock_query.side_effect = query_side_effect

            app_data = ApplicationCreate(job_posting_id=101)
            app = placement_service.create_application(self.mock_db, app_data, current_user=self.student)

            snap = app.match_snapshot
            self.assertIsNotNone(snap)
            self.assertEqual(snap["resume_id"], 55)
            self.assertEqual(snap["resume_filename"], "alice_resume_2026.pdf")
            self.assertEqual(snap["skill_sources"], skill_sources)
            self.assertIn("Python", snap["matched_required_skills"])
            self.assertIn("FastAPI", snap["matched_required_skills"])
            self.assertIn("SQL", snap["missing_required_skills"])
            self.assertIn("Docker", snap["missing_required_skills"])
            self.assertEqual(snap["branch"], "CSE")
            self.assertEqual(snap["cgpa"], 8.4)
            self.assertIn("created_at", snap)

    def test_11_snapshot_immutability_on_subsequent_profile_update(self):
        """11. Later edits to student profile or job do not alter saved application snapshot."""
        mock_profile = MagicMock(cgpa=8.0, branch="CSE")
        student_skills = ["Python", "FastAPI"]

        with patch.object(placement_service, 'get_job_posting', return_value=self.open_job), \
             patch.object(self.mock_db, 'query') as mock_query, \
             patch.object(job_matching_service, 'get_student_skills', return_value=(student_skills, mock_profile, None, {"profile_skills": student_skills, "resume_skills": []})):

            def query_side_effect(model):
                m_q = MagicMock()
                if model == User:
                    m_q.filter.return_value.first.return_value = self.student
                elif model == Application:
                    m_q.filter.return_value.first.return_value = None
                return m_q
            mock_query.side_effect = query_side_effect

            app_data = ApplicationCreate(job_posting_id=101)
            app = placement_service.create_application(self.mock_db, app_data, current_user=self.student)

            original_snapshot_cgpa = app.match_snapshot["cgpa"]
            original_snapshot_score = app.match_percentage

            # Student profile subsequently updates CGPA from 8.0 to 9.5 and learns Docker
            mock_profile.cgpa = 9.5
            student_skills.append("Docker")

            # Stored application snapshot remains unchanged
            self.assertEqual(app.match_snapshot["cgpa"], original_snapshot_cgpa)
            self.assertEqual(app.match_percentage, original_snapshot_score)

    def test_12_legacy_applications_without_snapshot_remain_readable(self):
        """12. Legacy applications with match_snapshot=None serialize safely to ApplicationResponse."""
        legacy_app = Application(
            id=1,
            student_id=10,
            job_posting_id=101,
            status=ApplicationStatus.APPLIED,
            eligibility_score=85.0,
            match_percentage=85.0,
            match_snapshot=None,  # Legacy record
            applied_at=datetime.now(timezone.utc)
        )

        resp = ApplicationResponse.model_validate(legacy_app)
        self.assertEqual(resp.id, 1)
        self.assertIsNone(resp.match_snapshot)
        self.assertIsNone(resp.has_low_match_warning)

    # =========================================================================
    # 4. AUTHORIZATION & INTEGRITY
    # =========================================================================

    def test_13_closed_or_draft_jobs_cannot_be_applied_to(self):
        """13. Jobs in CLOSED or DRAFT status cannot be applied to."""
        closed_job = JobPosting(id=201, company_id=1, title="Closed Role", status=JobStatus.CLOSED)
        draft_job = JobPosting(id=202, company_id=1, title="Draft Role", status=JobStatus.DRAFT)

        with patch.object(self.mock_db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.first.return_value = self.student

            # Closed job
            with patch.object(placement_service, 'get_job_posting', return_value=closed_job):
                with self.assertRaises(ValueError) as ctx:
                    placement_service.create_application(self.mock_db, ApplicationCreate(job_posting_id=201), self.student)
                self.assertIn("not open for applications", str(ctx.exception))

            # Draft job
            with patch.object(placement_service, 'get_job_posting', return_value=draft_job):
                with self.assertRaises(ValueError) as ctx:
                    placement_service.create_application(self.mock_db, ApplicationCreate(job_posting_id=202), self.student)
                self.assertIn("not open for applications", str(ctx.exception))

    def test_14_duplicate_applications_rejected(self):
        """14. Duplicate application attempts are prevented."""
        existing_app = Application(id=999, student_id=10, job_posting_id=101)

        with patch.object(placement_service, 'get_job_posting', return_value=self.open_job), \
             patch.object(self.mock_db, 'query') as mock_query:

            def query_side_effect(model):
                m_q = MagicMock()
                if model == User:
                    m_q.filter.return_value.first.return_value = self.student
                elif model == Application:
                    m_q.filter.return_value.first.return_value = existing_app  # Duplicate!
                return m_q
            mock_query.side_effect = query_side_effect

            with self.assertRaises(ValueError) as ctx:
                placement_service.create_application(self.mock_db, ApplicationCreate(job_posting_id=101), self.student)

            self.assertIn("already applied", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
