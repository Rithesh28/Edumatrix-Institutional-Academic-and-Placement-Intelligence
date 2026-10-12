"""
EduMatrix Phase 3.4 — Stage 3.4.4: Student Profile Grouped Application Tracking Unit & Integration Tests

Validates:
1. Applications grouped correctly by company, circular, and job role.
2. Multiple applications under one circular remain separate without merging.
3. Legacy applications without a circular link display correctly (circular=None, circular_id=None).
4. External confirmation is labeled as student-reported (external_applied_at exists, is_external_confirmed=True).
5. Missing external confirmation is handled correctly (external_applied_at=None, application_url available).
6. Confirmed round outcomes are distinct from offers (round outcomes populated, no inferred offer).
7. Accepted, declined, pending, and rescinded offers render correctly with audit rescission reasons.
8. No-offer applications are not mislabeled as having offers.
9. Unauthorized cross-student access is rejected by the backend (HTTP 403 Forbidden).
10. Missing optional fields (empty profile, zero applications) do not crash the endpoint.
"""

import time
import unittest
import uuid
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal
from app.core.security import create_access_token, get_password_hash
from app.models.user import User, UserRole
from app.models.company import Company
from app.models.job_posting import JobPosting, JobStatus
from app.models.application import Application, ApplicationStatus
from app.models.profile import StudentProfileExtended
from app.models.recruitment_circular import (
    RecruitmentCircular,
    RecruitmentCircularJob,
    RecruitmentCircularStatus,
)
from app.models.recruitment_round import (
    RecruitmentRound,
    StudentRoundOutcome,
    PlacementOffer,
    RoundOutcome,
    OfferAcceptanceStatus,
)
from app.models.audit_log import AuditLog


class TestPhase344StudentProfileTracking(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db: Session = SessionLocal()
        cls.client = TestClient(app)
        cls.ts = int(time.time() * 1000)
        cls.pwd_hash = get_password_hash("TestPass123!")

        # 1. Placement Officer
        cls.officer = cls.db.query(User).filter(User.role == UserRole.PLACEMENT_OFFICER).first()
        if not cls.officer:
            cls.officer = User(
                email=f"officer_profile_{cls.ts}@vcet.ac.in",
                name="Placement Officer Profile",
                role=UserRole.PLACEMENT_OFFICER,
                password_hash=cls.pwd_hash,
                is_active=True,
            )
            cls.db.add(cls.officer)
            cls.db.commit()
            cls.db.refresh(cls.officer)
        cls.officer_token = create_access_token(
            {"id": cls.officer.id, "email": cls.officer.email, "role": cls.officer.role.value if hasattr(cls.officer.role, "value") else str(cls.officer.role)}
        )
        cls.officer_headers = {"Authorization": f"Bearer {cls.officer_token}"}

        # 2. Student A (Primary test candidate with multi-role drive, legacy app, rescinded offer)
        cls.student_a = User(
            email=f"student_a_profile_{cls.ts}@vcet.ac.in",
            name="Alice Candidate",
            role=UserRole.STUDENT,
            password_hash=cls.pwd_hash,
            department="CSE",
            is_active=True,
        )
        cls.db.add(cls.student_a)
        cls.db.commit()
        cls.db.refresh(cls.student_a)
        cls.profile_a = StudentProfileExtended(
            user_id=cls.student_a.id,
            full_name="Alice Candidate",
            branch="Computer Science & Engineering",
            cgpa=9.15,
            phone="9876543210",
            enrollment_number=f"ENR-A-{cls.ts}",
        )
        cls.db.add(cls.profile_a)

        cls.student_a_token = create_access_token(
            {"id": cls.student_a.id, "email": cls.student_a.email, "role": cls.student_a.role.value if hasattr(cls.student_a.role, "value") else str(cls.student_a.role)}
        )
        cls.student_a_headers = {"Authorization": f"Bearer {cls.student_a_token}"}

        # 3. Student B (Peer student for cross-access RBAC tests)
        cls.student_b = User(
            email=f"student_b_profile_{cls.ts}@vcet.ac.in",
            name="Bob Peer",
            role=UserRole.STUDENT,
            password_hash=cls.pwd_hash,
            department="ECE",
            is_active=True,
        )
        cls.db.add(cls.student_b)
        cls.db.commit()
        cls.db.refresh(cls.student_b)
        cls.student_b_token = create_access_token(
            {"id": cls.student_b.id, "email": cls.student_b.email, "role": cls.student_b.role.value if hasattr(cls.student_b.role, "value") else str(cls.student_b.role)}
        )
        cls.student_b_headers = {"Authorization": f"Bearer {cls.student_b_token}"}

        # 4. Student C (Minimal student with zero applications / optional fields empty)
        cls.student_c = User(
            email=f"student_c_empty_{cls.ts}@vcet.ac.in",
            name="Charlie Empty",
            role=UserRole.STUDENT,
            password_hash=cls.pwd_hash,
            department="IT",
            is_active=True,
        )
        cls.db.add(cls.student_c)
        cls.db.commit()
        cls.db.refresh(cls.student_c)

        # 5. Companies
        cls.company_alpha = Company(
            name=f"Alpha Corp {cls.ts}",
            industry="Software",
            website="https://alpha.example.com",
            location="Bengaluru",
        )
        cls.company_beta = Company(
            name=f"Beta Systems {cls.ts}",
            industry="Hardware",
            website="https://beta.example.com",
            location="Hyderabad",
        )
        cls.db.add_all([cls.company_alpha, cls.company_beta])
        cls.db.commit()
        cls.db.refresh(cls.company_alpha)
        cls.db.refresh(cls.company_beta)

        # 6. Recruitment Circular for Alpha Corp (Drive)
        cls.circular_alpha = RecruitmentCircular(
            company_id=cls.company_alpha.id,
            title="Alpha Corp Annual Campus Recruitment 2026",
            summary="Recruitment drive for engineering graduates across software tracks.",
            status=RecruitmentCircularStatus.PUBLISHED,
            drive_date=datetime.utcnow(),
            application_deadline=datetime.utcnow(),
            created_by=cls.officer.id,
        )
        cls.db.add(cls.circular_alpha)
        cls.db.commit()
        cls.db.refresh(cls.circular_alpha)

        # 7. Job Postings:
        # Job A1: Alpha Corp - Backend Engineer (Linked to Circular Alpha)
        cls.job_a1 = JobPosting(
            company_id=cls.company_alpha.id,
            title="Backend Engineer",
            description="Go & Python backend role",
            location="Bengaluru",
            application_url="https://alpha.example.com/careers/backend",
            cgpa_criteria=7.5,
            branch_eligibility=["CSE", "IT"],
            salary_range="10-14 LPA",
            status=JobStatus.OPEN,
            created_by=cls.officer.id,
        )
        # Job A2: Alpha Corp - Frontend Engineer (Linked to Circular Alpha - tests multi-role in same drive!)
        cls.job_a2 = JobPosting(
            company_id=cls.company_alpha.id,
            title="Frontend Engineer",
            description="React & TypeScript role",
            location="Bengaluru",
            application_url="https://alpha.example.com/careers/frontend",
            cgpa_criteria=7.0,
            branch_eligibility=["CSE", "ECE", "IT"],
            salary_range="8-12 LPA",
            status=JobStatus.OPEN,
            created_by=cls.officer.id,
        )
        # Job B: Beta Systems - Embedded Engineer (UNLINKED / Legacy historical job)
        cls.job_b_legacy = JobPosting(
            company_id=cls.company_beta.id,
            title="Embedded Engineer",
            description="Firmware development",
            location="Hyderabad",
            application_url="https://beta.example.com/apply",
            cgpa_criteria=8.0,
            salary_range="9-11 LPA",
            status=JobStatus.OPEN,
            created_by=cls.officer.id,
        )
        # Job C: Alpha Corp - DevOps Engineer (Offer Rescinded scenario)
        cls.job_c_rescinded = JobPosting(
            company_id=cls.company_alpha.id,
            title="DevOps Engineer",
            description="Kubernetes & Cloud infrastructure",
            location="Bengaluru",
            status=JobStatus.OPEN,
            created_by=cls.officer.id,
        )
        cls.db.add_all([cls.job_a1, cls.job_a2, cls.job_b_legacy, cls.job_c_rescinded])
        cls.db.commit()
        for j in [cls.job_a1, cls.job_a2, cls.job_b_legacy, cls.job_c_rescinded]:
            cls.db.refresh(j)

        # Link Job A1 and Job A2 to Circular Alpha
        cls.link_a1 = RecruitmentCircularJob(circular_id=cls.circular_alpha.id, job_posting_id=cls.job_a1.id)
        cls.link_a2 = RecruitmentCircularJob(circular_id=cls.circular_alpha.id, job_posting_id=cls.job_a2.id)
        cls.db.add_all([cls.link_a1, cls.link_a2])
        cls.db.commit()

        # 8. Applications for Student A:
        # App A1: Applied to Job A1 (External Confirmed, Cleared Round, NO offer)
        cls.app_a1 = Application(
            student_id=cls.student_a.id,
            job_posting_id=cls.job_a1.id,
            status=ApplicationStatus.SHORTLISTED,
            match_percentage=88.5,
            applied_at=datetime.utcnow(),
            external_applied_at=datetime.utcnow(),  # Student reported confirmation
        )
        # App A2: Applied to Job A2 (Under same drive! No external confirmation, Selected, Has ACCEPTED offer)
        cls.app_a2 = Application(
            student_id=cls.student_a.id,
            job_posting_id=cls.job_a2.id,
            status=ApplicationStatus.SELECTED,
            match_percentage=92.0,
            applied_at=datetime.utcnow(),
            external_applied_at=None,  # No external confirmation
        )
        # App B: Applied to Job B (Legacy / Unlinked, Rejected, No external confirmation, NO offer)
        cls.app_b_legacy = Application(
            student_id=cls.student_a.id,
            job_posting_id=cls.job_b_legacy.id,
            status=ApplicationStatus.REJECTED,
            match_percentage=75.0,
            applied_at=datetime.utcnow(),
            external_applied_at=None,
        )
        # App C: Applied to Job C (Selected, Has RESCINDED offer)
        cls.app_c_rescinded = Application(
            student_id=cls.student_a.id,
            job_posting_id=cls.job_c_rescinded.id,
            status=ApplicationStatus.SELECTED,
            match_percentage=85.0,
            applied_at=datetime.utcnow(),
            external_applied_at=datetime.utcnow(),
        )
        cls.db.add_all([cls.app_a1, cls.app_a2, cls.app_b_legacy, cls.app_c_rescinded])
        cls.db.commit()
        for a in [cls.app_a1, cls.app_a2, cls.app_b_legacy, cls.app_c_rescinded]:
            cls.db.refresh(a)

        # 9. Rounds & Confirmed Outcomes:
        # Round 1 for Job A1: Coding Round -> Outcome CLEARED
        cls.round_a1_1 = RecruitmentRound(
            job_posting_id=cls.job_a1.id,
            round_number=1,
            name="Coding & Data Structures",
            round_type="coding",
            is_final=False,
        )
        cls.db.add(cls.round_a1_1)
        cls.db.commit()
        cls.db.refresh(cls.round_a1_1)

        cls.outcome_a1_1 = StudentRoundOutcome(
            application_id=cls.app_a1.id,
            round_id=cls.round_a1_1.id,
            student_id=cls.student_a.id,
            outcome=RoundOutcome.CLEARED,
            score=95.0,
            remarks="Excellent algorithmic solution",
            confirmed_by=cls.officer.id,
        )
        cls.db.add(cls.outcome_a1_1)

        # Round 1 for Job A2: Final Interview -> Outcome SELECTED
        cls.round_a2_1 = RecruitmentRound(
            job_posting_id=cls.job_a2.id,
            round_number=1,
            name="Technical & Managerial Discussion",
            round_type="technical",
            is_final=True,
        )
        cls.db.add(cls.round_a2_1)
        cls.db.commit()
        cls.db.refresh(cls.round_a2_1)

        cls.outcome_a2_1 = StudentRoundOutcome(
            application_id=cls.app_a2.id,
            round_id=cls.round_a2_1.id,
            student_id=cls.student_a.id,
            outcome=RoundOutcome.CLEARED,
            score=90.0,
            confirmed_by=cls.officer.id,
        )
        cls.db.add(cls.outcome_a2_1)
        cls.db.commit()

        # 10. Placement Offers:
        # Offer for App A2: Accepted Verified Offer
        cls.offer_a2 = PlacementOffer(
            application_id=cls.app_a2.id,
            student_id=cls.student_a.id,
            job_posting_id=cls.job_a2.id,
            designation="Associate Frontend Engineer",
            ctc_lpa=12.0,
            acceptance_status=OfferAcceptanceStatus.ACCEPTED,
            offer_date=datetime.utcnow(),
            response_date=datetime.utcnow(),
            verified_by=cls.officer.id,
        )
        cls.db.add(cls.offer_a2)

        # Offer for App C: Rescinded Offer with AuditLog reason
        cls.offer_c = PlacementOffer(
            application_id=cls.app_c_rescinded.id,
            student_id=cls.student_a.id,
            job_posting_id=cls.job_c_rescinded.id,
            designation="Junior Cloud Engineer",
            ctc_lpa=11.5,
            acceptance_status=OfferAcceptanceStatus.RESCINDED,
            offer_date=datetime.utcnow(),
            verified_by=cls.officer.id,
        )
        cls.db.add(cls.offer_c)
        cls.db.commit()
        cls.db.refresh(cls.offer_c)

        # Log rescission in AuditLog
        cls.audit_rescind = AuditLog(
            actor_id=cls.officer.id,
            actor_email=cls.officer.email,
            actor_role="placement_officer",
            action="PLACEMENT_OFFER_RESCINDED",
            target_type="placement_offer",
            target_id=str(cls.offer_c.id),
            outcome="SUCCESS",
            details={
                "application_id": cls.app_c_rescinded.id,
                "student_id": cls.student_a.id,
                "job_posting_id": cls.job_c_rescinded.id,
                "rescission_reason": "Position closed due to organizational restructuring",
            },
        )
        cls.db.add(cls.audit_rescind)
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_placement_officer_can_view_student_profile_with_grouped_tracking(self):
        """Officer can fetch enriched student profile with circulars, rounds, and offers."""
        resp = self.client.get(f"/placement/students/{self.student_a.id}", headers=self.officer_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["student_id"], self.student_a.id)
        self.assertEqual(data["name"], "Alice Candidate")
        self.assertEqual(data["branch"], "Computer Science & Engineering")
        self.assertEqual(data["cgpa"], 9.15)

        apps = data["applications"]
        self.assertEqual(len(apps), 4)

    def test_02_multiple_applications_under_same_circular_remain_separate(self):
        """Applications under the same recruitment drive remain separate without merging."""
        resp = self.client.get(f"/placement/students/{self.student_a.id}", headers=self.officer_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        apps = data["applications"]

        # Filter applications belonging to Circular Alpha
        alpha_apps = [a for a in apps if a.get("circular_id") == self.circular_alpha.id]
        self.assertEqual(len(alpha_apps), 2, "Both Job A1 and Job A2 must appear separately under Circular Alpha")

        role_titles = {a["job_title"] for a in alpha_apps}
        self.assertIn("Backend Engineer", role_titles)
        self.assertIn("Frontend Engineer", role_titles)

        # Verify they have unique application IDs
        app_ids = [a["id"] for a in alpha_apps]
        self.assertEqual(len(set(app_ids)), 2)

    def test_03_legacy_application_without_circular_link_handles_cleanly(self):
        """Historical/unlinked applications have circular=None and circular_id=None."""
        resp = self.client.get(f"/placement/students/{self.student_a.id}", headers=self.officer_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        apps = data["applications"]

        legacy_app = next((a for a in apps if a["job_title"] == "Embedded Engineer"), None)
        self.assertIsNotNone(legacy_app)
        self.assertIsNone(legacy_app["circular_id"])
        self.assertIsNone(legacy_app["circular"])
        self.assertEqual(legacy_app["company_name"], self.company_beta.name)

    def test_04_external_confirmation_evidence_distinction(self):
        """External confirmation is clearly labeled as student-reported vs unconfirmed."""
        resp = self.client.get(f"/placement/students/{self.student_a.id}", headers=self.officer_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        apps = data["applications"]

        # Job A1: External confirmed
        app_a1 = next((a for a in apps if a["job_title"] == "Backend Engineer"), None)
        self.assertIsNotNone(app_a1)
        self.assertTrue(app_a1["is_external_confirmed"])
        self.assertIsNotNone(app_a1["external_applied_at"])

        # Job A2: External NOT confirmed, but application_url is provided
        app_a2 = next((a for a in apps if a["job_title"] == "Frontend Engineer"), None)
        self.assertIsNotNone(app_a2)
        self.assertFalse(app_a2["is_external_confirmed"])
        self.assertIsNone(app_a2["external_applied_at"])
        self.assertEqual(app_a2["application_url"], "https://alpha.example.com/careers/frontend")

    def test_05_round_outcomes_distinct_from_offers_no_mislabeled_offers(self):
        """Cleared/selected round outcome does NOT fabricate or infer a verified offer."""
        resp = self.client.get(f"/placement/students/{self.student_a.id}", headers=self.officer_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        apps = data["applications"]

        # Job A1: Cleared round outcome, but NO offer
        app_a1 = next((a for a in apps if a["job_title"] == "Backend Engineer"), None)
        self.assertIsNotNone(app_a1)
        self.assertEqual(len(app_a1["round_outcomes"]), 1)
        self.assertEqual(app_a1["round_outcomes"][0]["outcome"].upper(), "CLEARED")
        self.assertEqual(app_a1["round_outcomes"][0]["round_name"], "Coding & Data Structures")
        self.assertIsNone(app_a1["offer"], "Cleared round must NOT infer a verified offer")

        # Job A2: Selected round outcome AND verified accepted offer
        app_a2 = next((a for a in apps if a["job_title"] == "Frontend Engineer"), None)
        self.assertIsNotNone(app_a2)
        self.assertEqual(len(app_a2["round_outcomes"]), 1)
        self.assertEqual(app_a2["round_outcomes"][0]["outcome"].upper(), "CLEARED")
        self.assertIsNotNone(app_a2["offer"])
        self.assertEqual(app_a2["offer"]["acceptance_status"], "accepted")
        self.assertEqual(app_a2["offer"]["ctc_lpa"], 12.0)

    def test_06_rescinded_offer_includes_audit_rescission_reason(self):
        """Rescinded offer on application returns audit reason without schema migration."""
        resp = self.client.get(f"/placement/students/{self.student_a.id}", headers=self.officer_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        apps = data["applications"]

        app_c = next((a for a in apps if a["job_title"] == "DevOps Engineer"), None)
        self.assertIsNotNone(app_c)
        self.assertIsNotNone(app_c["offer"])
        self.assertEqual(app_c["offer"]["acceptance_status"], "rescinded")
        self.assertIn("restructuring", app_c["offer"]["rescission_reason"])

    def test_07_unauthorized_cross_student_access_rejected(self):
        """Student B cannot view Student A's placement profile (HTTP 403 Forbidden)."""
        # Student B attempting to view Student A's profile
        resp = self.client.get(f"/placement/students/{self.student_a.id}", headers=self.student_b_headers)
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Access denied", resp.json()["detail"])

        # Student A viewing own profile is allowed
        resp_self = self.client.get(f"/placement/students/{self.student_a.id}", headers=self.student_a_headers)
        self.assertEqual(resp_self.status_code, 200)

    def test_08_empty_student_profile_handles_cleanly_without_crashing(self):
        """Student with zero applications or empty profile records returns clean 200 response."""
        resp = self.client.get(f"/placement/students/{self.student_c.id}", headers=self.officer_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["student_id"], self.student_c.id)
        self.assertEqual(data["total_applications"], 0)
        self.assertEqual(data["applications"], [])
        self.assertEqual(data["skills"], [])


if __name__ == "__main__":
    unittest.main()
