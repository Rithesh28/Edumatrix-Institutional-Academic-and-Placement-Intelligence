"""
EduMatrix Phase 3.4 — Stage 3.4.3: Recruitment Drive Integration Unit & Integration Tests

Validates:
1. Applications aggregation by circular_id (scoped strictly to linked jobs, with branch/cgpa payload).
2. Verified offers aggregation by circular_id (scoped to linked roles).
3. Result batches scoping by circular_id with fallback to linked job roles.
4. Drive Placement Report API:
   - Server-authoritative calculation of unique applicants, submissions, external confirmations.
   - Strict Institutional Placement Accounting: only unique students holding active accepted offers are counted as placed.
   - Rounds progression breakdown and funnel outcomes.
   - Role-wise and branch-wise breakdown.
5. RBAC enforcement:
   - Placement Officer and Admin allowed.
   - Student forbidden (403).
"""

import time
import unittest
import uuid
from datetime import datetime
from typing import List

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
from app.models.file import File, FileStatus, FileType
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
from app.models.recruitment_result import (
    RecruitmentResultBatch,
    RecruitmentResultBatchStatus,
)


class TestPhase343DriveIntegration(unittest.TestCase):
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
                email=f"officer_drive_{cls.ts}@vcet.ac.in",
                name="Placement Officer Drive",
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

        # 2. Admin
        cls.admin = cls.db.query(User).filter(User.role == UserRole.ADMIN).first()
        if not cls.admin:
            cls.admin = User(
                email=f"admin_drive_{cls.ts}@vcet.ac.in",
                name="Admin Drive",
                role=UserRole.ADMIN,
                password_hash=cls.pwd_hash,
                is_active=True,
            )
            cls.db.add(cls.admin)
            cls.db.commit()
            cls.db.refresh(cls.admin)
        cls.admin_token = create_access_token(
            {"id": cls.admin.id, "email": cls.admin.email, "role": cls.admin.role.value if hasattr(cls.admin.role, "value") else str(cls.admin.role)}
        )
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}

        # 3. Student
        cls.student_user = User(
            email=f"student_drive_{cls.ts}@vcet.ac.in",
            name="Student Drive",
            role=UserRole.STUDENT,
            password_hash=cls.pwd_hash,
            is_active=True,
        )
        cls.db.add(cls.student_user)
        cls.db.commit()
        cls.db.refresh(cls.student_user)
        cls.student_token = create_access_token(
            {"id": cls.student_user.id, "email": cls.student_user.email, "role": cls.student_user.role.value if hasattr(cls.student_user.role, "value") else str(cls.student_user.role)}
        )
        cls.student_headers = {"Authorization": f"Bearer {cls.student_token}"}

        # Setup Company
        cls.company = Company(
            name=f"Drive Integration Tech {cls.ts}",
            website="https://drive-integ.test",
        )
        cls.db.add(cls.company)
        cls.db.commit()
        cls.db.refresh(cls.company)

        # Setup 3 Jobs (Job A & Job B linked to circular, Job C unlinked)
        cls.job_a = JobPosting(
            company_id=cls.company.id,
            title=f"Software Engineer {cls.ts}",
            status=JobStatus.OPEN,
            created_by=cls.officer.id,
        )
        cls.job_b = JobPosting(
            company_id=cls.company.id,
            title=f"QA Automation Engineer {cls.ts}",
            status=JobStatus.OPEN,
            created_by=cls.officer.id,
        )
        cls.job_c = JobPosting(
            company_id=cls.company.id,
            title=f"Unlinked DevOps Engineer {cls.ts}",
            status=JobStatus.OPEN,
            created_by=cls.officer.id,
        )
        cls.db.add_all([cls.job_a, cls.job_b, cls.job_c])
        cls.db.commit()
        cls.db.refresh(cls.job_a)
        cls.db.refresh(cls.job_b)
        cls.db.refresh(cls.job_c)

        # Setup Recruitment Circular
        cls.circular = RecruitmentCircular(
            company_id=cls.company.id,
            title=f"Annual Campus Drive {cls.ts}",
            summary="Full campus recruitment drive for engineering graduates.",
            status=RecruitmentCircularStatus.PUBLISHED,
            branch_eligibility=["CSE", "ECE", "IT"],
            created_by=cls.officer.id,
        )
        cls.db.add(cls.circular)
        cls.db.commit()
        cls.db.refresh(cls.circular)

        # Link Job A and Job B to Circular
        cls.link_a = RecruitmentCircularJob(
            circular_id=cls.circular.id,
            job_posting_id=cls.job_a.id,
        )
        cls.link_b = RecruitmentCircularJob(
            circular_id=cls.circular.id,
            job_posting_id=cls.job_b.id,
        )
        cls.db.add_all([cls.link_a, cls.link_b])
        cls.db.commit()

        # Setup 5 Test Students with Profiles
        cls.students = []
        cls.profiles = []
        branches = ["CSE", "CSE", "ECE", "IT", "MECH"]
        cgpas = [8.8, 7.5, 9.1, 8.2, 6.9]

        for i in range(5):
            u = User(
                email=f"applicant_{i}_{cls.ts}@vcet.ac.in",
                name=f"Applicant {i} {cls.ts}",
                role=UserRole.STUDENT,
                password_hash=cls.pwd_hash,
                is_active=True,
            )
            cls.db.add(u)
            cls.db.commit()
            cls.db.refresh(u)
            cls.students.append(u)

            p = StudentProfileExtended(
                user_id=u.id,
                enrollment_number=f"ENR{cls.ts % 10000}{i}",
                full_name=f"Applicant {i} {cls.ts}",
                branch=branches[i],
                cgpa=cgpas[i],
            )
            cls.db.add(p)
            cls.db.commit()
            cls.db.refresh(p)
            cls.profiles.append(p)

        # Setup Applications:
        # Student 0: Applied to Job A (external confirmed, selected)
        cls.app_0_a = Application(
            student_id=cls.students[0].id,
            job_posting_id=cls.job_a.id,
            status=ApplicationStatus.SELECTED,
            external_applied_at=datetime.utcnow(),
        )
        # Student 1: Applied to Job A (pending confirmation, shortlisted) AND Job B (applied) -> tests multi-role student aggregation!
        cls.app_1_a = Application(
            student_id=cls.students[1].id,
            job_posting_id=cls.job_a.id,
            status=ApplicationStatus.SHORTLISTED,
            external_applied_at=None,
        )
        cls.app_1_b = Application(
            student_id=cls.students[1].id,
            job_posting_id=cls.job_b.id,
            status=ApplicationStatus.APPLIED,
            external_applied_at=datetime.utcnow(),
        )
        # Student 2: Applied to Job B (external confirmed, selected)
        cls.app_2_b = Application(
            student_id=cls.students[2].id,
            job_posting_id=cls.job_b.id,
            status=ApplicationStatus.SELECTED,
            external_applied_at=datetime.utcnow(),
        )
        # Student 3: Applied to Job B (rejected)
        cls.app_3_b = Application(
            student_id=cls.students[3].id,
            job_posting_id=cls.job_b.id,
            status=ApplicationStatus.REJECTED,
            external_applied_at=None,
        )
        # Student 4: Applied to unlinked Job C (must NOT show in drive!)
        cls.app_4_c = Application(
            student_id=cls.students[4].id,
            job_posting_id=cls.job_c.id,
            status=ApplicationStatus.SELECTED,
            external_applied_at=datetime.utcnow(),
        )

        cls.db.add_all([cls.app_0_a, cls.app_1_a, cls.app_1_b, cls.app_2_b, cls.app_3_b, cls.app_4_c])
        cls.db.commit()
        for a in [cls.app_0_a, cls.app_1_a, cls.app_1_b, cls.app_2_b, cls.app_3_b, cls.app_4_c]:
            cls.db.refresh(a)

        # Setup Recruitment Rounds:
        # Job A Round 1: Online Assessment
        cls.round_a1 = RecruitmentRound(
            job_posting_id=cls.job_a.id,
            round_number=1,
            name="Online Coding Assessment",
            round_type="coding",
            is_final=False,
        )
        cls.db.add(cls.round_a1)
        cls.db.commit()
        cls.db.refresh(cls.round_a1)

        # Outcomes for Round A1:
        # Student 0: Cleared
        cls.out_0 = StudentRoundOutcome(
            application_id=cls.app_0_a.id,
            round_id=cls.round_a1.id,
            student_id=cls.students[0].id,
            outcome=RoundOutcome.CLEARED,
            score=95.0,
            confirmed_by=cls.officer.id,
        )
        # Student 1: Rejected
        cls.out_1 = StudentRoundOutcome(
            application_id=cls.app_1_a.id,
            round_id=cls.round_a1.id,
            student_id=cls.students[1].id,
            outcome=RoundOutcome.REJECTED,
            score=45.0,
            confirmed_by=cls.officer.id,
        )
        cls.db.add_all([cls.out_0, cls.out_1])
        cls.db.commit()

        # Setup Verified Offers (Testing Institutional Placement Accounting):
        # 1. Student 0: Holds ACCEPTED offer for Job A -> OFFICIALLY PLACED
        cls.offer_0 = PlacementOffer(
            application_id=cls.app_0_a.id,
            student_id=cls.students[0].id,
            job_posting_id=cls.job_a.id,
            designation="Software Engineer",
            ctc_lpa=12.5,
            acceptance_status=OfferAcceptanceStatus.ACCEPTED,
            verified_by=cls.officer.id,
        )
        # 2. Student 2: Holds OFFERED (pending) offer for Job B -> NOT PLACED YET (decision pending)
        cls.offer_2 = PlacementOffer(
            application_id=cls.app_2_b.id,
            student_id=cls.students[2].id,
            job_posting_id=cls.job_b.id,
            designation="QA Engineer",
            ctc_lpa=8.0,
            acceptance_status=OfferAcceptanceStatus.OFFERED,
            verified_by=cls.officer.id,
        )
        # 3. Student 3: Holds RESCINDED offer for Job B -> NOT PLACED
        cls.offer_3 = PlacementOffer(
            application_id=cls.app_3_b.id,
            student_id=cls.students[3].id,
            job_posting_id=cls.job_b.id,
            designation="QA Engineer",
            ctc_lpa=8.0,
            acceptance_status=OfferAcceptanceStatus.RESCINDED,
            verified_by=cls.officer.id,
        )
        # 4. Student 4: Offer on unlinked Job C -> NOT in drive report!
        cls.offer_4 = PlacementOffer(
            application_id=cls.app_4_c.id,
            student_id=cls.students[4].id,
            job_posting_id=cls.job_c.id,
            designation="DevOps Engineer",
            ctc_lpa=10.0,
            acceptance_status=OfferAcceptanceStatus.ACCEPTED,
            verified_by=cls.officer.id,
        )
        cls.db.add_all([cls.offer_0, cls.offer_2, cls.offer_3, cls.offer_4])
        cls.db.commit()

        # Synthetic File for Batches
        cls.test_file = File(
            id=uuid.uuid4(),
            filename=f"batch_results_{cls.ts}.csv",
            file_size=1024,
            mime_type="text/csv",
            bucket="placement-documents",
            object_key=f"tests/{cls.ts}_batch.csv",
            department="Placement",
            file_type=FileType.PLACEMENT_DOC,
            uploaded_by=cls.officer.id,
            status=FileStatus.ACTIVE,
        )
        cls.db.add(cls.test_file)
        cls.db.commit()
        cls.db.refresh(cls.test_file)

        # Batch 1: Directly linked via circular_id
        cls.batch_1 = RecruitmentResultBatch(
            company_id=cls.company.id,
            circular_id=cls.circular.id,
            file_id=cls.test_file.id,
            round_name="Drive Coding Round",
            round_type="coding",
            status=RecruitmentResultBatchStatus.FULLY_CONFIRMED,
            uploaded_by=cls.officer.id,
        )
        # Batch 2: Legacy / unlinked circular_id, but linked to Job A
        cls.batch_2 = RecruitmentResultBatch(
            company_id=cls.company.id,
            job_posting_id=cls.job_a.id,
            file_id=cls.test_file.id,
            round_name="Job A Interview Round",
            round_type="technical_interview",
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            uploaded_by=cls.officer.id,
        )
        # Batch 3: Linked to unlinked Job C (must NOT show in circular results!)
        cls.batch_3 = RecruitmentResultBatch(
            company_id=cls.company.id,
            job_posting_id=cls.job_c.id,
            file_id=cls.test_file.id,
            round_name="DevOps Round",
            round_type="technical_interview",
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            uploaded_by=cls.officer.id,
        )
        cls.db.add_all([cls.batch_1, cls.batch_2, cls.batch_3])
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        # Clean up test entities created
        try:
            cls.db.query(RecruitmentResultBatch).filter(
                RecruitmentResultBatch.company_id == cls.company.id
            ).delete()
            cls.db.query(PlacementOffer).filter(
                PlacementOffer.job_posting_id.in_([cls.job_a.id, cls.job_b.id, cls.job_c.id])
            ).delete()
            cls.db.query(StudentRoundOutcome).filter(
                StudentRoundOutcome.round_id == cls.round_a1.id
            ).delete()
            cls.db.query(RecruitmentRound).filter(
                RecruitmentRound.job_posting_id.in_([cls.job_a.id, cls.job_b.id, cls.job_c.id])
            ).delete()
            cls.db.query(Application).filter(
                Application.job_posting_id.in_([cls.job_a.id, cls.job_b.id, cls.job_c.id])
            ).delete()
            cls.db.query(RecruitmentCircularJob).filter(
                RecruitmentCircularJob.circular_id == cls.circular.id
            ).delete()
            cls.db.query(RecruitmentCircular).filter(
                RecruitmentCircular.id == cls.circular.id
            ).delete()
            cls.db.query(JobPosting).filter(
                JobPosting.company_id == cls.company.id
            ).delete()
            cls.db.query(Company).filter(Company.id == cls.company.id).delete()
            cls.db.query(File).filter(File.id == cls.test_file.id).delete()

            for p in cls.profiles:
                cls.db.query(StudentProfileExtended).filter(
                    StudentProfileExtended.id == p.id
                ).delete()
            for u in cls.students:
                cls.db.query(User).filter(User.id == u.id).delete()
            cls.db.query(User).filter(User.id == cls.student_user.id).delete()

            cls.db.commit()
        except Exception as e:
            cls.db.rollback()
        finally:
            cls.db.close()

    def test_01_applications_filtered_by_circular_id(self):
        """Verify GET /placement/applications?circular_id={id} scopes to linked roles and adds student profile info."""
        res = self.client.get(
            f"/placement/applications?circular_id={self.circular.id}",
            headers=self.officer_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Job A has 2 applications, Job B has 3 applications => Total 5 applications for this drive
        # Job C application (Student 4) must NOT be returned!
        app_ids = [a["id"] for a in data]
        self.assertIn(self.app_0_a.id, app_ids)
        self.assertIn(self.app_1_a.id, app_ids)
        self.assertIn(self.app_1_b.id, app_ids)
        self.assertIn(self.app_2_b.id, app_ids)
        self.assertIn(self.app_3_b.id, app_ids)
        self.assertNotIn(self.app_4_c.id, app_ids)
        self.assertEqual(len(data), 5)

        # Verify branch and CGPA are returned in ApplicationResponse
        app_0_dict = next(a for a in data if a["id"] == self.app_0_a.id)
        self.assertEqual(app_0_dict["student_branch"], "CSE")
        self.assertEqual(app_0_dict["student_cgpa"], 8.8)
        self.assertTrue(app_0_dict["is_external_confirmed"])

    def test_02_verified_offers_filtered_by_circular_id(self):
        """Verify GET /placement/offers?circular_id={id} scopes strictly to drive linked roles."""
        res = self.client.get(
            f"/placement/offers?circular_id={self.circular.id}",
            headers=self.officer_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()

        offer_ids = [o["id"] for o in data]
        self.assertIn(self.offer_0.id, offer_ids)
        self.assertIn(self.offer_2.id, offer_ids)
        self.assertIn(self.offer_3.id, offer_ids)
        self.assertNotIn(self.offer_4.id, offer_ids)
        self.assertEqual(len(data), 3)

    def test_03_result_batches_filtered_by_circular_id(self):
        """Verify GET /placement/results/batches?circular_id={id} returns direct circular batches and linked role batches."""
        res = self.client.get(
            f"/placement/results/batches?circular_id={self.circular.id}",
            headers=self.officer_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()

        batch_ids = [b["id"] for b in data]
        self.assertIn(self.batch_1.id, batch_ids)  # direct circular_id
        self.assertIn(self.batch_2.id, batch_ids)  # linked to job_a
        self.assertNotIn(self.batch_3.id, batch_ids)  # linked to unlinked job_c

    def test_04_drive_report_placement_accounting_and_metrics(self):
        """Verify GET /placement/circulars/{id}/report provides authoritative metrics and strict institutional placement accounting."""
        res = self.client.get(
            f"/placement/circulars/{self.circular.id}/report",
            headers=self.officer_headers,
        )
        self.assertEqual(res.status_code, 200)
        report = res.json()

        # Basic Metadata
        self.assertEqual(report["circular_id"], self.circular.id)
        self.assertEqual(report["company_name"], self.company.name)
        self.assertEqual(report["linked_roles_count"], 2)

        # Applicant and Application Counts:
        # Total applications = 5 (across Job A and Job B)
        # Unique applicants = 4 (Student 0, 1, 2, 3; Student 1 applied to both jobs)
        self.assertEqual(report["total_applications_count"], 5)
        self.assertEqual(report["unique_applicants_count"], 4)

        # External Confirmations count:
        # app_0_a (True), app_1_b (True), app_2_b (True) => 3 confirmed
        self.assertEqual(report["external_confirmations_count"], 3)

        # STRICT INSTITUTIONAL PLACEMENT ACCOUNTING:
        # - Total verified offers in drive = 3 (offer_0, offer_2, offer_3)
        # - Placed students strictly requires acceptance_status == 'accepted' (offer_0 only)
        # - offer_2 is 'offered' (pending), offer_3 is 'rescinded'
        self.assertEqual(report["total_verified_offers_count"], 3)
        self.assertEqual(report["verified_placed_students_count"], 1)

        offers_summary = report["offers_summary"]
        self.assertEqual(offers_summary["total_offers"], 3)
        self.assertEqual(offers_summary["accepted_count"], 1)
        self.assertEqual(offers_summary["offered_count"], 1)
        self.assertEqual(offers_summary["rescinded_count"], 1)
        self.assertEqual(offers_summary["unique_students_placed"], 1)

        # Applications by role breakdown:
        roles_summary = {r["job_title"]: r for r in report["applications_by_role"]}
        self.assertIn(self.job_a.title, roles_summary)
        self.assertEqual(roles_summary[self.job_a.title]["total_applications"], 2)
        self.assertIn(self.job_b.title, roles_summary)
        self.assertEqual(roles_summary[self.job_b.title]["total_applications"], 3)

        # Rounds outcomes summary:
        self.assertEqual(len(report["rounds_summary"]), 1)
        rd = report["rounds_summary"][0]
        self.assertEqual(rd["round_id"], self.round_a1.id)
        self.assertEqual(rd["cleared_count"], 1)
        self.assertEqual(rd["rejected_count"], 1)
        self.assertEqual(rd["total_outcomes"], 2)

        # Branch representation:
        # Student 0 (CSE), Student 1 (CSE), Student 2 (ECE), Student 3 (IT)
        self.assertEqual(report["branch_breakdown"]["CSE"], 2)
        self.assertEqual(report["branch_breakdown"]["ECE"], 1)
        self.assertEqual(report["branch_breakdown"]["IT"], 1)

    def test_05_drive_report_rbac_permissions(self):
        """Verify RBAC: Admin and Officer can view drive report; Student receives 403 Forbidden."""
        # Admin can view
        res_admin = self.client.get(
            f"/placement/circulars/{self.circular.id}/report",
            headers=self.admin_headers,
        )
        self.assertEqual(res_admin.status_code, 200)

        # Student is forbidden
        res_student = self.client.get(
            f"/placement/circulars/{self.circular.id}/report",
            headers=self.student_headers,
        )
        self.assertEqual(res_student.status_code, 403)


if __name__ == "__main__":
    unittest.main()
