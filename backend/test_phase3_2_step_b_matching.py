"""
Automated Test Suite for Phase 3.2 Step B: Backend Matching Foundation

Explicit test coverage for the 24 required test items:
1. Exact required skill match
2. Exact preferred skill match
3. Missing required skill
4. Missing preferred skill
5. 80/20 score calculation formula
6. Zero required skills safe handling
7. Zero preferred skills safe handling
8. Both skill categories empty safe handling
9. Skill normalization (whitespace, casing, hyphens, punctuation)
10. Canonical synonym matching (ml -> machine learning, k8s -> kubernetes, etc.)
11. Semantic match via sentence-transformers/all-MiniLM-L6-v2 (similarity >= 0.78)
12. Semantic non-match (dissimilar skills below threshold)
13. Eligibility pass (meets CGPA and branch)
14. Eligibility failure (fails CGPA or branch)
15. Branch eligibility evaluation
16. CGPA eligibility evaluation
17. Match score does not include CGPA
18. Match score does not include branch
19. Student cannot modify job requirements or publish jobs (RBAC 403)
20. Placement Officer authorization (allowed to parse JD, publish job, check matches)
21. Admin authorization (retains full placement access)
22. JD Parser requirement extraction from text (skills, CGPA, branches, experience)
23. Job publishing lifecycle (DRAFT -> OPEN)
24. Explainable, deterministic output structure without fake skills fabrication
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

# Configure SQLite for test environment before importing app
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.skill_normalizer import skill_normalizer
from app.services.job_matching_service import job_matching_service, SEMANTIC_SKILL_MATCH_THRESHOLD
from app.services.jd_parser_service import jd_parser_service
from app.models.job_posting import JobPosting, JobStatus
from app.models.user import User, UserRole
from app.schemas.placement import (
    JobPostingCreate, JobPostingUpdate, JdParseRequest, StudentEligibility
)


class TestPhase32StepBMatchingFoundation(unittest.TestCase):
    """Complete automated test suite covering all 24 required criteria."""

    def setUp(self):
        self.mock_db = MagicMock()
        self.student = User(
            id=10,
            name="Alice Candidate",
            email="alice@vcet.ac.in",
            role=UserRole.STUDENT,
            is_active=True
        )

    # -------------------------------------------------------------------------
    # TEST 1: Exact required skill match
    # -------------------------------------------------------------------------
    def test_01_exact_required_skill_match(self):
        """1. Exact normalized match for required skills."""
        job_req = {"python": "Python", "fastapi": "FastAPI"}
        student_skills = ["Python", "FastAPI"]
        matched, missing, details = job_matching_service.match_skills(
            job_req, student_skills, category="required"
        )
        self.assertEqual(len(matched), 2)
        self.assertEqual(len(missing), 0)
        self.assertIn("Python", matched)
        self.assertIn("FastAPI", matched)
        self.assertEqual(details[0]["match_method"], "exact")

    # -------------------------------------------------------------------------
    # TEST 2: Exact preferred skill match
    # -------------------------------------------------------------------------
    def test_02_exact_preferred_skill_match(self):
        """2. Exact normalized match for preferred skills."""
        job_pref = {"docker": "Docker", "redis": "Redis"}
        student_skills = ["Docker", "Redis"]
        matched, missing, details = job_matching_service.match_skills(
            job_pref, student_skills, category="preferred"
        )
        self.assertEqual(len(matched), 2)
        self.assertEqual(len(missing), 0)
        self.assertIn("Docker", matched)
        self.assertIn("Redis", matched)
        self.assertEqual(details[0]["match_method"], "exact")

    # -------------------------------------------------------------------------
    # TEST 3: Missing required skill
    # -------------------------------------------------------------------------
    def test_03_missing_required_skill(self):
        """3. Identification of missing required skill."""
        job_req = {"python": "Python", "rust": "Rust"}
        student_skills = ["Python"]
        matched, missing, _ = job_matching_service.match_skills(
            job_req, student_skills, category="required"
        )
        self.assertEqual(matched, ["Python"])
        self.assertEqual(missing, ["Rust"])

    # -------------------------------------------------------------------------
    # TEST 4: Missing preferred skill
    # -------------------------------------------------------------------------
    def test_04_missing_preferred_skill(self):
        """4. Identification of missing preferred skill."""
        job_pref = {"kubernetes": "Kubernetes", "aws": "AWS"}
        student_skills = ["AWS"]
        matched, missing, _ = job_matching_service.match_skills(
            job_pref, student_skills, category="preferred"
        )
        self.assertEqual(matched, ["AWS"])
        self.assertEqual(missing, ["Kubernetes"])

    # -------------------------------------------------------------------------
    # TEST 5: 80/20 score calculation formula
    # -------------------------------------------------------------------------
    def test_05_eighty_twenty_score_calculation(self):
        """5. Deterministic score calculation: (required * 0.80) + (preferred * 0.20)."""
        # 4 required, 3 matched -> 75%
        # 2 preferred, 1 matched -> 50%
        # overall = (75 * 0.8) + (50 * 0.2) = 60 + 10 = 70.0%
        req_score, pref_score, overall = job_matching_service.compute_scores(
            required_matched=3,
            required_total=4,
            preferred_matched=1,
            preferred_total=2
        )
        self.assertEqual(req_score, 75.0)
        self.assertEqual(pref_score, 50.0)
        self.assertEqual(overall, 70.0)

    # -------------------------------------------------------------------------
    # TEST 6: Zero required skills
    # -------------------------------------------------------------------------
    def test_06_zero_required_skills(self):
        """6. Safe handling when total required skills is zero (required_score is None)."""
        req_score, pref_score, overall = job_matching_service.compute_scores(
            required_matched=0,
            required_total=0,
            preferred_matched=2,
            preferred_total=2
        )
        self.assertIsNone(req_score)
        self.assertEqual(pref_score, 100.0)
        self.assertEqual(overall, 100.0)

    # -------------------------------------------------------------------------
    # TEST 7: Zero preferred skills
    # -------------------------------------------------------------------------
    def test_07_zero_preferred_skills(self):
        """7. Safe handling when total preferred skills is zero (preferred_score is None)."""
        req_score, pref_score, overall = job_matching_service.compute_scores(
            required_matched=2,
            required_total=3,
            preferred_matched=0,
            preferred_total=0
        )
        self.assertAlmostEqual(req_score, 66.67, places=1)
        self.assertIsNone(pref_score)
        self.assertAlmostEqual(overall, 66.67, places=1)

    # -------------------------------------------------------------------------
    # TEST 8: Both skill categories empty (nullable / not calculated)
    # -------------------------------------------------------------------------
    def test_08_both_skill_categories_empty(self):
        """8. Safe handling when both required and preferred skills are empty (returns None, not false 100%)."""
        req_score, pref_score, overall = job_matching_service.compute_scores(
            required_matched=0,
            required_total=0,
            preferred_matched=0,
            preferred_total=0
        )
        self.assertIsNone(req_score)
        self.assertIsNone(pref_score)
        self.assertIsNone(overall)

    # -------------------------------------------------------------------------
    # TEST 9: Normalization
    # -------------------------------------------------------------------------
    def test_09_normalization(self):
        """9. Whitespace, casing, hyphen, and punctuation normalization."""
        self.assertEqual(skill_normalizer.normalize("  PYTHON  "), "python")
        self.assertEqual(skill_normalizer.normalize("Machine-Learning"), "machine learning")
        self.assertEqual(skill_normalizer.normalize("Node.js"), "node.js")
        self.assertEqual(skill_normalizer.normalize("C++"), "c++")
        self.assertEqual(skill_normalizer.normalize("C#"), "c#")
        self.assertEqual(skill_normalizer.normalize("  React   Native  "), "react native")

    # -------------------------------------------------------------------------
    # TEST 10: Canonical synonym matching
    # -------------------------------------------------------------------------
    def test_10_canonical_synonym_matching(self):
        """10. Explicit canonical synonym resolution."""
        # ML -> machine learning
        self.assertTrue(skill_normalizer.is_canonical_match("ML", "Machine Learning"))
        self.assertTrue(skill_normalizer.is_canonical_match("machine-learning", "ML"))

        # K8s -> kubernetes
        self.assertTrue(skill_normalizer.is_canonical_match("k8s", "Kubernetes"))

        # Postgres / PostgreSQL / psql
        self.assertTrue(skill_normalizer.is_canonical_match("postgres", "postgresql"))
        self.assertTrue(skill_normalizer.is_canonical_match("psql", "PostgreSQL"))

        # ReactJS -> React
        self.assertTrue(skill_normalizer.is_canonical_match("ReactJS", "React"))

        # JS -> JavaScript
        self.assertTrue(skill_normalizer.is_canonical_match("js", "JavaScript"))

        # TS -> TypeScript
        self.assertTrue(skill_normalizer.is_canonical_match("ts", "TypeScript"))

    # -------------------------------------------------------------------------
    # TEST 11: Semantic match
    # -------------------------------------------------------------------------
    def test_11_semantic_match(self):
        """11. Semantic similarity match using all-MiniLM-L6-v2 (similarity >= 0.78)."""
        job_req = {"docker container": "Docker Container"}
        student_skills = ["Docker"]

        matched, missing, details = job_matching_service.match_skills(
            job_req, student_skills, category="required"
        )
        self.assertEqual(len(matched), 1)
        self.assertEqual(len(missing), 0)
        self.assertEqual(details[0]["match_method"], "semantic")
        self.assertGreaterEqual(details[0]["similarity"], SEMANTIC_SKILL_MATCH_THRESHOLD)

    # -------------------------------------------------------------------------
    # TEST 12: Semantic non-match
    # -------------------------------------------------------------------------
    def test_12_semantic_non_match(self):
        """12. Dissimilar skills below threshold do not match."""
        job_req = {"postgresql": "PostgreSQL"}
        student_skills = ["Photoshop", "Graphic Design"]

        matched, missing, details = job_matching_service.match_skills(
            job_req, student_skills, category="required"
        )
        self.assertEqual(len(matched), 0)
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing, ["PostgreSQL"])

    # -------------------------------------------------------------------------
    # TEST 13: Eligibility pass
    # -------------------------------------------------------------------------
    def test_13_eligibility_pass(self):
        """13. Student passes eligibility when CGPA and branch criteria are met."""
        mock_job = MagicMock(spec=JobPosting)
        mock_job.required_skills = ["Python", "FastAPI"]
        mock_job.preferred_skills = []
        mock_job.cgpa_criteria = 7.5
        mock_job.branch_eligibility = ["AIML", "CSE"]

        mock_profile = MagicMock()
        mock_profile.id = 1
        mock_profile.cgpa = 8.5
        mock_profile.branch = "AIML"
        mock_profile.skills = []

        with patch.object(job_matching_service, 'get_student_skills', return_value=(["Python", "FastAPI"], mock_profile)):
            result = job_matching_service.match_student_to_job(self.mock_db, self.student, mock_job)

        self.assertTrue(result.is_eligible)
        self.assertTrue(result.cgpa_match)
        self.assertTrue(result.branch_match)
        self.assertEqual(len(result.eligibility_reasons), 0)

    # -------------------------------------------------------------------------
    # TEST 14: Eligibility failure
    # -------------------------------------------------------------------------
    def test_14_eligibility_failure(self):
        """14. Student fails eligibility when criteria are unmet."""
        mock_job = MagicMock(spec=JobPosting)
        mock_job.required_skills = ["Python"]
        mock_job.preferred_skills = []
        mock_job.cgpa_criteria = 8.0
        mock_job.branch_eligibility = ["CSE"]

        mock_profile = MagicMock()
        mock_profile.id = 2
        mock_profile.cgpa = 6.5  # Below 8.0
        mock_profile.branch = "MECH"  # Not CSE

        with patch.object(job_matching_service, 'get_student_skills', return_value=(["Python"], mock_profile)):
            result = job_matching_service.match_student_to_job(self.mock_db, self.student, mock_job)

        self.assertFalse(result.is_eligible)
        self.assertFalse(result.cgpa_match)
        self.assertFalse(result.branch_match)
        self.assertGreater(len(result.eligibility_reasons), 0)

    # -------------------------------------------------------------------------
    # TEST 15: Branch eligibility
    # -------------------------------------------------------------------------
    def test_15_branch_eligibility(self):
        """15. Specific validation of branch criteria."""
        mock_job = MagicMock(spec=JobPosting)
        mock_job.required_skills = ["Python"]
        mock_job.preferred_skills = []
        mock_job.cgpa_criteria = None
        mock_job.branch_eligibility = ["AIML", "CSE"]

        mock_profile_eligible = MagicMock(cgpa=8.0, branch="AIML", skills=[])
        mock_profile_ineligible = MagicMock(cgpa=8.0, branch="CIVIL", skills=[])

        # Eligible branch
        with patch.object(job_matching_service, 'get_student_skills', return_value=(["Python"], mock_profile_eligible)):
            res_ok = job_matching_service.match_student_to_job(self.mock_db, self.student, mock_job)
        self.assertTrue(res_ok.branch_match)

        # Ineligible branch
        with patch.object(job_matching_service, 'get_student_skills', return_value=(["Python"], mock_profile_ineligible)):
            res_bad = job_matching_service.match_student_to_job(self.mock_db, self.student, mock_job)
        self.assertFalse(res_bad.branch_match)

    # -------------------------------------------------------------------------
    # TEST 16: CGPA eligibility
    # -------------------------------------------------------------------------
    def test_16_cgpa_eligibility(self):
        """16. Specific validation of CGPA criteria."""
        mock_job = MagicMock(spec=JobPosting)
        mock_job.required_skills = ["Python"]
        mock_job.preferred_skills = []
        mock_job.cgpa_criteria = 7.75
        mock_job.branch_eligibility = []

        mock_profile_pass = MagicMock(cgpa=8.0, branch="CSE", skills=[])
        mock_profile_fail = MagicMock(cgpa=7.5, branch="CSE", skills=[])

        with patch.object(job_matching_service, 'get_student_skills', return_value=(["Python"], mock_profile_pass)):
            res_pass = job_matching_service.match_student_to_job(self.mock_db, self.student, mock_job)
        self.assertTrue(res_pass.cgpa_match)

        with patch.object(job_matching_service, 'get_student_skills', return_value=(["Python"], mock_profile_fail)):
            res_fail = job_matching_service.match_student_to_job(self.mock_db, self.student, mock_job)
        self.assertFalse(res_fail.cgpa_match)

    # -------------------------------------------------------------------------
    # TEST 17: Match score does not include CGPA
    # -------------------------------------------------------------------------
    def test_17_match_score_does_not_include_cgpa(self):
        """17. Low CGPA does not dock or blend into the numerical skill match score."""
        mock_job = MagicMock(spec=JobPosting)
        mock_job.required_skills = ["Python", "FastAPI"]
        mock_job.preferred_skills = []
        mock_job.cgpa_criteria = 9.0  # Very high criteria
        mock_job.branch_eligibility = []

        mock_profile = MagicMock(id=10, cgpa=5.5, branch="CSE", skills=[])

        with patch.object(job_matching_service, 'get_student_skills', return_value=(["Python", "FastAPI"], mock_profile)):
            result = job_matching_service.match_student_to_job(self.mock_db, self.student, mock_job)

        self.assertFalse(result.is_eligible)
        self.assertFalse(result.cgpa_match)
        # Match score remains 100.0 (strictly skill-based, independent of CGPA)
        self.assertEqual(result.skill_match, 100.0)
        self.assertEqual(result.match_score, 100.0)

    # -------------------------------------------------------------------------
    # TEST 18: Match score does not include branch
    # -------------------------------------------------------------------------
    def test_18_match_score_does_not_include_branch(self):
        """18. Branch mismatch does not dock or blend into the numerical skill match score."""
        mock_job = MagicMock(spec=JobPosting)
        mock_job.required_skills = ["Python", "FastAPI"]
        mock_job.preferred_skills = []
        mock_job.cgpa_criteria = None
        mock_job.branch_eligibility = ["ECE"]

        mock_profile = MagicMock(id=11, cgpa=8.5, branch="CSE", skills=[])  # Branch mismatch

        with patch.object(job_matching_service, 'get_student_skills', return_value=(["Python", "FastAPI"], mock_profile)):
            result = job_matching_service.match_student_to_job(self.mock_db, self.student, mock_job)

        self.assertFalse(result.is_eligible)
        self.assertFalse(result.branch_match)
        # Match score remains 100.0 (strictly skill-based, independent of branch)
        self.assertEqual(result.skill_match, 100.0)
        self.assertEqual(result.match_score, 100.0)

    # -------------------------------------------------------------------------
    # TEST 19: Student cannot modify job requirements
    # -------------------------------------------------------------------------
    def test_19_student_cannot_modify_job_requirements(self):
        """19. RBAC: Student attempting to access Placement Officer endpoints gets 403."""
        from app.api.auth import get_current_placement_officer
        from fastapi import HTTPException

        student_user = User(id=99, email="student@vcet.ac.in", role=UserRole.STUDENT, is_active=True)

        with self.assertRaises(HTTPException) as ctx:
            get_current_placement_officer(current_user=student_user)
        self.assertEqual(ctx.exception.status_code, 403)

    # -------------------------------------------------------------------------
    # TEST 20: Placement Officer authorization
    # -------------------------------------------------------------------------
    def test_20_placement_officer_authorization(self):
        """20. Placement Officer is successfully authorized for placement operations."""
        from app.api.auth import get_current_placement_officer

        officer = User(id=50, email="officer@vcet.ac.in", role=UserRole.PLACEMENT_OFFICER, is_active=True)
        user = get_current_placement_officer(current_user=officer)
        self.assertEqual(user.id, 50)
        self.assertEqual(user.role, UserRole.PLACEMENT_OFFICER)

    # -------------------------------------------------------------------------
    # TEST 21: Admin authorization
    # -------------------------------------------------------------------------
    def test_21_admin_authorization(self):
        """21. Admin is successfully authorized for placement operations."""
        from app.api.auth import get_current_placement_officer

        admin = User(id=1, email="admin@vcet.ac.in", role=UserRole.ADMIN, is_active=True)
        user = get_current_placement_officer(current_user=admin)
        self.assertEqual(user.id, 1)
        self.assertEqual(user.role, UserRole.ADMIN)

    # -------------------------------------------------------------------------
    # TEST 22: JD Parser structured extraction
    # -------------------------------------------------------------------------
    def test_22_jd_parser_structured_extraction(self):
        """22. JD Parser extracts title, skills, CGPA, branch, experience, and location."""
        sample_jd = """
        Job Title: Senior Python Engineer
        Company: CloudTech Innovations
        Location: Bangalore, India
        Experience: 2-4 years
        Salary: 12-16 LPA
        
        Eligibility Criteria:
        - Minimum CGPA: 7.5 and above
        - Eligible branches: CSE, IT, AIML
        
        Required Skills:
        - Python
        - FastAPI
        - PostgreSQL
        - Docker
        
        Preferred Skills:
        - Kubernetes
        - AWS
        - Redis
        
        Job Description:
        Join our core backend engineering team to scale our distributed cloud systems.
        """
        extracted = jd_parser_service.parse_jd_text(sample_jd)

        self.assertEqual(extracted["title"], "Senior Python Engineer")
        self.assertEqual(extracted["cgpa_criteria"], 7.5)
        self.assertIn("CSE", extracted["branch_eligibility"])
        self.assertIn("IT", extracted["branch_eligibility"])
        self.assertIn("AIML", extracted["branch_eligibility"])
        self.assertEqual(extracted["experience_level"], "2-4 years")
        self.assertIn("Bangalore", extracted["location"])

        # Required skills
        self.assertIn("Python", extracted["required_skills"])
        self.assertIn("FastAPI", extracted["required_skills"])
        self.assertIn("PostgreSQL", extracted["required_skills"])
        self.assertIn("Docker", extracted["required_skills"])

        # Preferred skills
        self.assertIn("Kubernetes", extracted["preferred_skills"])
        self.assertIn("AWS", extracted["preferred_skills"])
        self.assertIn("Redis", extracted["preferred_skills"])

        # Ensure no overlap
        self.assertTrue(set(extracted["required_skills"]).isdisjoint(set(extracted["preferred_skills"])))

    # -------------------------------------------------------------------------
    # TEST 23: Job publishing lifecycle
    # -------------------------------------------------------------------------
    def test_23_job_publishing_lifecycle(self):
        """23. Job transitions from DRAFT to OPEN upon officer publication."""
        from app.services.placement_service import placement_service

        mock_db = MagicMock()
        mock_job = JobPosting(
            id=101,
            title="Backend Intern",
            company_id=5,
            status=JobStatus.DRAFT,
            required_skills=["Python"],
            preferred_skills=["Docker"]
        )

        with patch.object(placement_service, 'get_job_posting', return_value=mock_job):
            published_job = placement_service.publish_job_posting(mock_db, 101)

        self.assertIsNotNone(published_job)
        self.assertEqual(published_job.status, JobStatus.OPEN)
        mock_db.commit.assert_called_once()

    # -------------------------------------------------------------------------
    # TEST 24: Fake skills prevention and explainable breakdown
    # -------------------------------------------------------------------------
    def test_24_fake_skills_prevention_and_explainable_breakdown(self):
        """24. Results contain strictly authentic candidate skills and clear gap lists."""
        mock_job = MagicMock(spec=JobPosting)
        mock_job.required_skills = ["Python", "FastAPI", "PostgreSQL"]
        mock_job.preferred_skills = ["Docker", "Kubernetes"]
        mock_job.cgpa_criteria = 7.0
        mock_job.branch_eligibility = ["CSE"]

        # Candidate genuinely only has Python and Docker
        genuine_skills = ["Python", "Docker"]
        mock_profile = MagicMock(id=15, cgpa=8.2, branch="CSE", skills=[])

        with patch.object(job_matching_service, 'get_student_skills', return_value=(genuine_skills, mock_profile)):
            result = job_matching_service.match_student_to_job(self.mock_db, self.student, mock_job)

        # Matched skills only contain genuine candidate skills
        for m in result.matched_skills:
            norm_m = skill_normalizer.normalize(m)
            self.assertTrue(
                any(skill_normalizer.normalize(g) == norm_m for g in genuine_skills),
                f"Matched skill {m} was not in candidate genuine skills!"
            )

        # Missing skills are explicitly identified
        self.assertIn("FastAPI", result.missing_required_skills)
        self.assertIn("PostgreSQL", result.missing_required_skills)
        self.assertIn("Kubernetes", result.missing_preferred_skills)

        # Detailed breakdown counts are explainable and consistent
        self.assertEqual(result.required_total, 3)
        self.assertEqual(result.required_matched, 1)  # Python
        self.assertEqual(result.required_missing, 2)  # FastAPI, PostgreSQL
        self.assertEqual(result.preferred_total, 2)
        self.assertEqual(result.preferred_matched, 1)  # Docker
        self.assertEqual(result.preferred_missing, 1)  # Kubernetes

    # -------------------------------------------------------------------------
    # TEST 25: Job publish validation for empty skills
    # -------------------------------------------------------------------------
    def test_25_empty_skills_job_publish_validation(self):
        """25. Job without skill requirements cannot be published unless confirmed."""
        from app.services.placement_service import placement_service
        
        mock_job = MagicMock(spec=JobPosting)
        mock_job.id = 50
        mock_job.title = "No Skill Job"
        mock_job.required_skills = []
        mock_job.preferred_skills = []
        mock_job.status = JobStatus.DRAFT

        with patch.object(placement_service, 'get_job_posting', return_value=mock_job):
            # Attempting publish without confirmation raises ValueError
            with self.assertRaises(ValueError) as ctx:
                placement_service.publish_job_posting(self.mock_db, job_id=50, confirm_no_skills=False)
            self.assertIn("cannot be published without skill requirements", str(ctx.exception).lower())

            # Explicit confirmation succeeds
            published = placement_service.publish_job_posting(self.mock_db, job_id=50, confirm_no_skills=True)
            self.assertEqual(published.status, JobStatus.OPEN)

    # -------------------------------------------------------------------------
    # TEST 26: Student skill source selection and traceability
    # -------------------------------------------------------------------------
    def test_26_student_skill_source_selection_and_traceability(self):
        """26. Completed resume is prioritized, skills deduplicated, sources traced."""
        from app.models.resume import Resume, ResumeStatus
        from app.models.file import File
        from app.models.profile import Skill

        # Completed resume
        completed_resume = MagicMock(spec=Resume)
        completed_resume.id = 101
        completed_resume.status = ResumeStatus.COMPLETED
        completed_resume.skills = ["Python", "Django", "SQL"]
        completed_resume.file = MagicMock(spec=File, filename="resume_v2.pdf")

        mock_profile = MagicMock(id=1, skills=[])
        skill_db_rec = MagicMock(spec=Skill, name="Python")  # Duplicate

        mock_query = self.mock_db.query.return_value
        # Configure filter mocks
        def mock_filter(*args, **kwargs):
            m_res = MagicMock()
            # If filtering Skill
            m_res.all.return_value = [skill_db_rec]
            # If filtering Resume with order_by
            m_res.order_by.return_value.first.return_value = completed_resume
            m_res.first.return_value = mock_profile
            return m_res

        mock_query.filter.side_effect = mock_filter

        skills, prof, resume, sources = job_matching_service.get_student_skills(self.mock_db, student_id=10)

        # Python deduplicated
        self.assertIn("Python", skills)
        self.assertIn("Django", skills)
        self.assertIn("SQL", skills)
        self.assertEqual(len([s for s in skills if s.lower() == "python"]), 1)
        self.assertIsNotNone(resume)
        self.assertEqual(resume.id, 101)
        self.assertIn("profile_skills", sources)
        self.assertIn("resume_skills", sources)

    # -------------------------------------------------------------------------
    # TEST 27: Job creation defaults to DRAFT
    # -------------------------------------------------------------------------
    def test_27_job_creation_defaults_to_draft(self):
        """27. Newly created job postings default to DRAFT status."""
        from app.services.placement_service import placement_service

        job_in = JobPostingCreate(
            company_id=1,
            title="Junior Dev",
            required_skills=["Python"],
            preferred_skills=[]
        )
        self.assertEqual(job_in.status, JobStatus.DRAFT)

        created_job = placement_service.create_job_posting(self.mock_db, job_in, created_by=5)
        self.assertEqual(created_job.status, JobStatus.DRAFT)

    # -------------------------------------------------------------------------
    # TEST 28: Matching with both skill categories empty yields None score
    # -------------------------------------------------------------------------
    def test_28_matching_both_categories_empty_yields_none_score(self):
        """28. Matching student against job with empty skills returns match_score=None."""
        mock_job = MagicMock(spec=JobPosting)
        mock_job.required_skills = []
        mock_job.preferred_skills = []
        mock_job.cgpa_criteria = None
        mock_job.branch_eligibility = []

        mock_profile = MagicMock(id=1, cgpa=8.0, branch="CSE", skills=[])

        with patch.object(job_matching_service, 'get_student_skills', return_value=(["Python"], mock_profile)):
            result = job_matching_service.match_student_to_job(self.mock_db, self.student, mock_job)

        self.assertIsNone(result.match_score)
        self.assertIsNone(result.skill_match)
        self.assertIsNone(result.overall_skill_match)
        self.assertIsNone(result.required_score)
        self.assertIsNone(result.preferred_score)
        self.assertTrue(result.is_eligible)

    # -------------------------------------------------------------------------
    # TEST 29: API publish validation endpoint
    # -------------------------------------------------------------------------
    def test_29_api_publish_validation_endpoint(self):
        """29. API endpoint POST /placement/jobs/{id}/publish returns 400 without confirm_no_skills on empty skills."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.api.auth import get_current_placement_officer
        from app.core.database import get_db
        from app.services.placement_service import placement_service

        po_user = User(id=401, email="po@vcet.ac.in", role=UserRole.PLACEMENT_OFFICER, is_active=True)
        app.dependency_overrides[get_current_placement_officer] = lambda: po_user
        app.dependency_overrides[get_db] = lambda: self.mock_db

        try:
            client = TestClient(app)
            mock_draft_job = MagicMock(spec=JobPosting)
            mock_draft_job.id = 77
            mock_draft_job.company_id = 1
            mock_draft_job.title = "Empty Job"
            mock_draft_job.required_skills = []
            mock_draft_job.preferred_skills = []
            mock_draft_job.description = "Test Description"
            mock_draft_job.experience_level = "Fresher"
            mock_draft_job.cgpa_criteria = 7.0
            mock_draft_job.branch_eligibility = ["CSE"]
            mock_draft_job.location = "Remote"
            mock_draft_job.salary_range = "6 LPA"
            mock_draft_job.application_url = None
            mock_draft_job.application_deadline = None
            mock_draft_job.drive_date = None
            mock_draft_job.created_by = 401
            mock_draft_job.created_at = datetime.utcnow()
            mock_draft_job.updated_at = None
            mock_draft_job.company = None
            mock_draft_job.status = JobStatus.DRAFT

            with patch.object(placement_service, 'get_job_posting', return_value=mock_draft_job):
                # 1. Unconfirmed publish fails with 400
                res1 = client.post("/placement/jobs/77/publish")
                self.assertEqual(res1.status_code, 400)
                self.assertIn("cannot be published without skill requirements", res1.json()["detail"].lower())

                # 2. Confirmed publish succeeds with 200
                res2 = client.post("/placement/jobs/77/publish?confirm_no_skills=true")
                self.assertEqual(res2.status_code, 200)
        finally:
            app.dependency_overrides.pop(get_current_placement_officer, None)
            app.dependency_overrides.pop(get_db, None)

    # -------------------------------------------------------------------------
    # TEST 30: Student cannot view or check eligibility on draft jobs
    # -------------------------------------------------------------------------
    def test_30_api_student_draft_job_visibility(self):
        """30. Students cannot view draft jobs or check eligibility on draft jobs via API."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.api.auth import get_current_user
        from app.core.database import get_db
        from app.services.placement_service import placement_service

        student_user = User(id=10, email="student@vcet.ac.in", role=UserRole.STUDENT, is_active=True)
        app.dependency_overrides[get_current_user] = lambda: student_user
        app.dependency_overrides[get_db] = lambda: self.mock_db

        try:
            client = TestClient(app)
            
            # Check eligibility on draft job returns 404 for student
            mock_draft = MagicMock(spec=JobPosting)
            mock_draft.id = 88
            mock_draft.status = JobStatus.DRAFT

            with patch.object(placement_service, 'get_job_posting', return_value=mock_draft):
                res = client.get("/placement/jobs/88/check-eligibility/10")
                self.assertEqual(res.status_code, 404)
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)


if __name__ == "__main__":
    unittest.main()
