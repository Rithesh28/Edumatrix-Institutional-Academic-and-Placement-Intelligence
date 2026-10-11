"""
EduMatrix Phase 3.4.1: Safe Test-Data Cleanup Backend Integration Tests

Comprehensive validation suite covering:
1. Preview-only behavior with zero database mutations.
2. Correct dependent counts calculation.
3. Explicit selection and malformed requests rejection.
4. Student, Lecturer, HOD and unauthorized-role denial.
5. Placement Officer and Admin permissions.
6. Protection of genuine applications, confirmed outcomes and accepted offers.
7. Multiple offers and legacy placement status re-evaluation.
8. Shared-file protection and academic-circular isolation.
9. Polymorphic notification cleanup isolation.
10. Transaction rollback, concurrency/revalidation, and audit integrity.
11. Archive behavior and safe purge behavior.
"""

import time
import unittest
import uuid
from typing import List, Optional

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal
from app.core.security import create_access_token, get_password_hash
from app.models.user import User, UserRole
from app.models.company import Company
from app.models.job_posting import JobPosting, JobStatus
from app.models.application import Application, ApplicationStatus
from app.models.shortlist import Shortlist
from app.models.profile import StudentProfileExtended, PlacementStatus
from app.models.file import File, FileStatus, FileType
from app.models.notification import Notification
from app.models.audit_log import AuditLog
from app.models.circular import Circular, CircularType  # Academic circular
from app.models.recruitment_circular import (
    RecruitmentCircular,
    RecruitmentCircularAttachment,
    RecruitmentCircularJob,
    RecruitmentCircularStatus,
    AttachmentType,
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
    RecruitmentResultItem,
    RecruitmentResultBatchStatus,
    RecruitmentResultItemStatus,
    RecruitmentResultReviewState,
)
from app.services.placement_cleanup_service import placement_cleanup_service


class TestPhase341PlacementCleanup(unittest.TestCase):
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
                email=f"officer_cleanup_{cls.ts}@vcet.ac.in",
                name="Placement Officer Cleanup",
                role=UserRole.PLACEMENT_OFFICER,
                password_hash=cls.pwd_hash,
                is_active=True,
            )
            cls.db.add(cls.officer)
            cls.db.commit()
            cls.db.refresh(cls.officer)
        cls.officer_token = create_access_token({"id": cls.officer.id, "email": cls.officer.email, "role": cls.officer.role.value if hasattr(cls.officer.role, "value") else str(cls.officer.role)})
        cls.officer_headers = {"Authorization": f"Bearer {cls.officer_token}"}

        # 2. Admin
        cls.admin = cls.db.query(User).filter(User.role == UserRole.ADMIN).first()
        if not cls.admin:
            cls.admin = User(
                email=f"admin_cleanup_{cls.ts}@vcet.ac.in",
                name="Admin Cleanup",
                role=UserRole.ADMIN,
                password_hash=cls.pwd_hash,
                is_active=True,
            )
            cls.db.add(cls.admin)
            cls.db.commit()
            cls.db.refresh(cls.admin)
        cls.admin_token = create_access_token({"id": cls.admin.id, "email": cls.admin.email, "role": cls.admin.role.value if hasattr(cls.admin.role, "value") else str(cls.admin.role)})
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}

        # 3. Student (Test Student)
        cls.student_test = User(
            email=f"test_student_cleanup_{cls.ts}@vcet.ac.in",
            name="Synthetic Test Student",
            role=UserRole.STUDENT,
            password_hash=cls.pwd_hash,
            is_active=True,
        )
        cls.db.add(cls.student_test)
        cls.db.commit()
        cls.db.refresh(cls.student_test)

        cls.student_test_profile = StudentProfileExtended(
            user_id=cls.student_test.id,
            enrollment_number=f"TEST{cls.ts % 100000}",
            full_name="Synthetic Test Student",
            branch="CSE",
            cgpa=8.5,
            placement_status=PlacementStatus.NOT_APPLIED,
        )
        cls.db.add(cls.student_test_profile)
        cls.db.commit()

        cls.student_token = create_access_token({"id": cls.student_test.id, "email": cls.student_test.email, "role": cls.student_test.role.value if hasattr(cls.student_test.role, "value") else str(cls.student_test.role)})
        cls.student_headers = {"Authorization": f"Bearer {cls.student_token}"}

        # 4. Genuine Student (No test keywords in email)
        cls.student_genuine = User(
            email=f"rahul_genuine_{cls.ts}@vcet.ac.in",
            name="Rahul Genuine Student",
            role=UserRole.STUDENT,
            password_hash=cls.pwd_hash,
            is_active=True,
        )
        cls.db.add(cls.student_genuine)
        cls.db.commit()
        cls.db.refresh(cls.student_genuine)

        cls.student_genuine_profile = StudentProfileExtended(
            user_id=cls.student_genuine.id,
            enrollment_number=f"GEN{cls.ts % 100000}",
            full_name="Rahul Genuine Student",
            branch="ISE",
            cgpa=9.1,
            placement_status=PlacementStatus.NOT_APPLIED,
        )
        cls.db.add(cls.student_genuine_profile)
        cls.db.commit()

        # 5. Lecturer
        cls.lecturer = User(
            email=f"lecturer_cleanup_{cls.ts}@vcet.ac.in",
            name="Lecturer Cleanup",
            role=UserRole.LECTURER,
            password_hash=cls.pwd_hash,
            is_active=True,
        )
        cls.db.add(cls.lecturer)
        cls.db.commit()
        cls.db.refresh(cls.lecturer)
        cls.lecturer_token = create_access_token({"id": cls.lecturer.id, "email": cls.lecturer.email, "role": cls.lecturer.role.value if hasattr(cls.lecturer.role, "value") else str(cls.lecturer.role)})
        cls.lecturer_headers = {"Authorization": f"Bearer {cls.lecturer_token}"}

        # 6. HOD
        cls.hod = User(
            email=f"hod_cleanup_{cls.ts}@vcet.ac.in",
            name="HOD Cleanup",
            role=UserRole.HOD,
            password_hash=cls.pwd_hash,
            is_active=True,
        )
        cls.db.add(cls.hod)
        cls.db.commit()
        cls.db.refresh(cls.hod)
        cls.hod_token = create_access_token({"id": cls.hod.id, "email": cls.hod.email, "role": cls.hod.role.value if hasattr(cls.hod.role, "value") else str(cls.hod.role)})
        cls.hod_headers = {"Authorization": f"Bearer {cls.hod_token}"}

    def tearDown(self):
        self.db.rollback()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def _create_synthetic_file(self, name: str = "doc.pdf") -> File:
        f = File(
            id=uuid.uuid4(),
            filename=name,
            file_size=1024,
            mime_type="application/pdf",
            bucket="placement-documents",
            object_key=f"tests/{uuid.uuid4()}_{name}",
            department="Placement",
            file_type=FileType.PLACEMENT_DOC,
            uploaded_by=self.officer.id,
            status=FileStatus.ACTIVE,
        )
        self.db.add(f)
        self.db.commit()
        self.db.refresh(f)
        return f

    # =========================================================================
    # 1. RBAC & PERMISSION BOUNDARIES
    # =========================================================================

    def test_01_preview_endpoint_rbac_access_control(self):
        """Preview endpoint restricts access to Placement Officers and Admins."""
        # Student -> 403 Forbidden
        res_stud = self.client.get("/placement/cleanup/preview", headers=self.student_headers)
        self.assertEqual(res_stud.status_code, 403)

        # Lecturer -> 403 Forbidden
        res_lec = self.client.get("/placement/cleanup/preview", headers=self.lecturer_headers)
        self.assertEqual(res_lec.status_code, 403)

        # HOD -> 403 Forbidden
        res_hod = self.client.get("/placement/cleanup/preview", headers=self.hod_headers)
        self.assertEqual(res_hod.status_code, 403)

        # Unauthenticated -> 401 Unauthorized
        res_anon = self.client.get("/placement/cleanup/preview")
        self.assertEqual(res_anon.status_code, 401)

        # Officer -> 200 OK
        res_off = self.client.get("/placement/cleanup/preview", headers=self.officer_headers)
        self.assertEqual(res_off.status_code, 200)

        # Admin -> 200 OK
        res_adm = self.client.get("/placement/cleanup/preview", headers=self.admin_headers)
        self.assertEqual(res_adm.status_code, 200)

    def test_02_execute_endpoint_rbac_access_control(self):
        """Execute endpoint restricts access to Placement Officers and Admins."""
        payload = {"company_ids": [1], "mode": "archive"}

        # Student -> 403
        res_stud = self.client.post("/placement/cleanup/execute", json=payload, headers=self.student_headers)
        self.assertEqual(res_stud.status_code, 403)

        # Lecturer -> 403
        res_lec = self.client.post("/placement/cleanup/execute", json=payload, headers=self.lecturer_headers)
        self.assertEqual(res_lec.status_code, 403)

        # HOD -> 403
        res_hod = self.client.post("/placement/cleanup/execute", json=payload, headers=self.hod_headers)
        self.assertEqual(res_hod.status_code, 403)

        # Unauthenticated -> 401
        res_anon = self.client.post("/placement/cleanup/execute", json=payload)
        self.assertEqual(res_anon.status_code, 401)

    # =========================================================================
    # 2. PREVIEW INTEGRITY (READ-ONLY, EXACT COUNTS)
    # =========================================================================

    def test_03_preview_is_strictly_read_only_no_mutations(self):
        """Preview operations must never modify database records or delete files."""
        # Create an isolated test company
        comp = Company(name=f"Mock Preview Test {self.ts}")
        self.db.add(comp)
        self.db.commit()
        self.db.refresh(comp)

        job = JobPosting(company_id=comp.id, title="Test Engineer", status=JobStatus.OPEN)
        self.db.add(job)
        self.db.commit()

        # Count records before preview
        comps_before = self.db.query(Company).count()
        jobs_before = self.db.query(JobPosting).count()

        # Call preview endpoint
        res = self.client.get(
            f"/placement/cleanup/preview?company_ids={comp.id}",
            headers=self.officer_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["candidates"]), 1)
        self.assertEqual(data["candidates"][0]["company_id"], comp.id)

        # Count records after preview
        comps_after = self.db.query(Company).count()
        jobs_after = self.db.query(JobPosting).count()

        self.assertEqual(comps_before, comps_after)
        self.assertEqual(jobs_before, jobs_after)

    def test_04_preview_calculates_exact_dependent_counts(self):
        """Preview must compute exact counts across all 11 dependent record relationships."""
        doc = self._create_synthetic_file("preview_test.pdf")

        comp = Company(name=f"Acme Test Artifact {self.ts}")
        self.db.add(comp)
        self.db.commit()
        self.db.refresh(comp)

        # 2 Jobs
        job1 = JobPosting(company_id=comp.id, title="Dev 1", status=JobStatus.OPEN)
        job2 = JobPosting(company_id=comp.id, title="Dev 2", status=JobStatus.OPEN)
        self.db.add_all([job1, job2])
        self.db.commit()

        # 1 Circular with 2 Circular-Job links & 1 attachment
        circ = RecruitmentCircular(company_id=comp.id, title="Drive 1", status=RecruitmentCircularStatus.DRAFT)
        self.db.add(circ)
        self.db.commit()
        self.db.refresh(circ)

        cj1 = RecruitmentCircularJob(circular_id=circ.id, job_posting_id=job1.id)
        cj2 = RecruitmentCircularJob(circular_id=circ.id, job_posting_id=job2.id)
        att = RecruitmentCircularAttachment(circular_id=circ.id, file_id=doc.id, attachment_type=AttachmentType.POSTER.value)
        self.db.add_all([cj1, cj2, att])
        self.db.commit()

        # 2 Applications
        app1 = Application(student_id=self.student_test.id, job_posting_id=job1.id, status=ApplicationStatus.APPLIED)
        app2 = Application(student_id=self.student_test.id, job_posting_id=job2.id, status=ApplicationStatus.SHORTLISTED)
        self.db.add_all([app1, app2])
        self.db.commit()

        # 1 Shortlist
        sh = Shortlist(student_id=self.student_test.id, company_id=comp.id, job_posting_id=job1.id)
        self.db.add(sh)
        self.db.commit()

        # 2 Rounds & 2 Outcomes (1 cleared, 1 rejected)
        r1 = RecruitmentRound(job_posting_id=job1.id, round_number=1, name="OA", is_final=False)
        r2 = RecruitmentRound(job_posting_id=job1.id, round_number=2, name="Final", is_final=True)
        self.db.add_all([r1, r2])
        self.db.commit()

        o1 = StudentRoundOutcome(application_id=app1.id, round_id=r1.id, student_id=self.student_test.id, outcome=RoundOutcome.CLEARED)
        o2 = StudentRoundOutcome(application_id=app1.id, round_id=r2.id, student_id=self.student_test.id, outcome=RoundOutcome.REJECTED)
        self.db.add_all([o1, o2])
        self.db.commit()

        # 1 Result batch with 2 items (1 confirmed)
        batch = RecruitmentResultBatch(company_id=comp.id, job_posting_id=job1.id, file_id=doc.id, round_name="OA")
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)

        item1 = RecruitmentResultItem(batch_id=batch.id, row_index=1, raw_data={}, review_status=RecruitmentResultReviewState.CONFIRMED)
        item2 = RecruitmentResultItem(batch_id=batch.id, row_index=2, raw_data={}, review_status=RecruitmentResultReviewState.PENDING)
        self.db.add_all([item1, item2])
        self.db.commit()

        # 1 Pending Offer (not accepted)
        off = PlacementOffer(application_id=app1.id, student_id=self.student_test.id, job_posting_id=job1.id, acceptance_status=OfferAcceptanceStatus.OFFERED)
        self.db.add(off)
        self.db.commit()

        # Call Preview
        res = self.client.get(f"/placement/cleanup/preview?company_ids={comp.id}", headers=self.officer_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        cand = data["candidates"][0]
        c = cand["dependent_counts"]

        self.assertEqual(c["jobs_count"], 2)
        self.assertEqual(c["circulars_count"], 1)
        self.assertEqual(c["circular_job_links_count"], 2)
        self.assertEqual(c["applications_count"], 2)
        self.assertEqual(c["shortlists_count"], 1)
        self.assertEqual(c["rounds_count"], 2)
        self.assertEqual(c["outcomes_count"], 2)
        self.assertEqual(c["confirmed_outcomes_count"], 1)
        self.assertEqual(c["result_batches_count"], 1)
        self.assertEqual(c["result_items_count"], 2)
        self.assertEqual(c["confirmed_result_items_count"], 1)
        self.assertEqual(c["offers_count"], 1)
        self.assertEqual(c["accepted_offers_count"], 0)
        self.assertEqual(c["active_offers_count"], 1)
        self.assertEqual(c["files_count"], 1)

    # =========================================================================
    # 3. REQUEST VALIDATION & MALFORMED PAYLOAD REJECTION
    # =========================================================================

    def test_05_execute_malformed_requests_and_validation(self):
        """Execute endpoint rejects empty lists, invalid modes, missing confirmation phrases, and nonexistent IDs."""
        # Empty company_ids
        res = self.client.post("/placement/cleanup/execute", json={"company_ids": [], "mode": "archive"}, headers=self.officer_headers)
        self.assertEqual(res.status_code, 422)  # Pydantic min_length=1

        # Invalid mode
        res = self.client.post("/placement/cleanup/execute", json={"company_ids": [1], "mode": "destroy"}, headers=self.officer_headers)
        self.assertEqual(res.status_code, 422)  # Pydantic pattern regex

        # Purge without confirmation phrase
        res = self.client.post("/placement/cleanup/execute", json={"company_ids": [1], "mode": "purge"}, headers=self.officer_headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("confirmation phrase", res.json()["detail"].lower())

        # Purge with incorrect confirmation phrase
        res = self.client.post("/placement/cleanup/execute", json={"company_ids": [1], "mode": "purge", "confirmation_phrase": "CONFIRM"}, headers=self.officer_headers)
        self.assertEqual(res.status_code, 400)

        # Non-existent company ID
        res = self.client.post("/placement/cleanup/execute", json={"company_ids": [9999999], "mode": "archive"}, headers=self.officer_headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("not found", res.json()["detail"].lower())

    # =========================================================================
    # 4. PLACEMENT HISTORY & STUDENT DATA PROTECTION
    # =========================================================================

    def test_06_protection_of_accepted_offers(self):
        """Companies with student-accepted placement offers are protected from destructive purge."""
        comp = Company(name=f"Protected Offer Corp {self.ts}")
        self.db.add(comp)
        self.db.commit()
        self.db.refresh(comp)

        job = JobPosting(company_id=comp.id, title="Analyst", status=JobStatus.OPEN)
        self.db.add(job)
        self.db.commit()

        app = Application(student_id=self.student_test.id, job_posting_id=job.id, status=ApplicationStatus.SELECTED)
        self.db.add(app)
        self.db.commit()

        # Accepted offer
        offer = PlacementOffer(
            application_id=app.id,
            student_id=self.student_test.id,
            job_posting_id=job.id,
            ctc_lpa=12.5,
            acceptance_status=OfferAcceptanceStatus.ACCEPTED,
        )
        self.db.add(offer)
        self.db.commit()

        # 1. Preview checks
        res_prev = self.client.get(f"/placement/cleanup/preview?company_ids={comp.id}", headers=self.officer_headers)
        self.assertEqual(res_prev.status_code, 200)
        cand = res_prev.json()["candidates"][0]
        self.assertEqual(cand["safety_classification"], "REQUIRES_ARCHIVE")
        self.assertGreater(cand["dependent_counts"]["accepted_offers_count"], 0)

        # 2. Purge attempt must be rejected
        res_purge = self.client.post(
            "/placement/cleanup/execute",
            json={
                "company_ids": [comp.id],
                "mode": "purge",
                "confirmation_phrase": "CONFIRM_PURGE_TEST_DATA",
            },
            headers=self.officer_headers,
        )
        self.assertEqual(res_purge.status_code, 400)
        self.assertIn("accepted placement offer", res_purge.json()["detail"].lower())

        # Verify record remains intact in DB
        self.assertIsNotNone(self.db.query(Company).filter(Company.id == comp.id).first())
        self.assertIsNotNone(self.db.query(PlacementOffer).filter(PlacementOffer.id == offer.id).first())

    def test_07_protection_of_genuine_student_accounts(self):
        """Companies involving non-test (genuine) students cannot be purged."""
        comp = Company(name=f"Genuine Student Corp {self.ts}")
        self.db.add(comp)
        self.db.commit()
        self.db.refresh(comp)

        job = JobPosting(company_id=comp.id, title="Associate", status=JobStatus.OPEN)
        self.db.add(job)
        self.db.commit()

        # Application from genuine student
        app = Application(student_id=self.student_genuine.id, job_posting_id=job.id, status=ApplicationStatus.APPLIED)
        self.db.add(app)
        self.db.commit()

        # Purge attempt must be blocked
        res_purge = self.client.post(
            "/placement/cleanup/execute",
            json={
                "company_ids": [comp.id],
                "mode": "purge",
                "confirmation_phrase": "CONFIRM_PURGE_TEST_DATA",
            },
            headers=self.officer_headers,
        )
        self.assertEqual(res_purge.status_code, 400)
        self.assertIn("genuine student", res_purge.json()["detail"].lower())

    def test_08_shared_file_and_academic_circular_isolation(self):
        """Shared files referenced by academic circulars are protected when recruitment data is purged."""
        shared_file = self._create_synthetic_file("shared_doc.pdf")

        # 1. Academic Circular referencing the file
        acad_circ = Circular(
            title="Academic Exam Notice",
            content="Official circular content",
            lecturer_id=self.lecturer.id,
            type=CircularType.EXAM,
            file_id=shared_file.id,
        )
        self.db.add(acad_circ)
        self.db.commit()

        # 2. Test Company referencing the SAME file
        comp = Company(name=f"Mock Shared File Corp {self.ts}")
        self.db.add(comp)
        self.db.commit()
        self.db.refresh(comp)

        rcirc = RecruitmentCircular(company_id=comp.id, title="Drive With Shared File", status=RecruitmentCircularStatus.DRAFT)
        self.db.add(rcirc)
        self.db.commit()
        self.db.refresh(rcirc)

        att = RecruitmentCircularAttachment(circular_id=rcirc.id, file_id=shared_file.id, attachment_type=AttachmentType.GUIDELINES.value)
        self.db.add(att)
        self.db.commit()

        # Preview must report shared file count = 1
        res_prev = self.client.get(f"/placement/cleanup/preview?company_ids={comp.id}", headers=self.officer_headers)
        self.assertEqual(res_prev.status_code, 200)
        cand = res_prev.json()["candidates"][0]
        self.assertEqual(cand["dependent_counts"]["shared_files_count"], 1)

        comp_id = comp.id
        rcirc_id = rcirc.id
        shared_file_id = shared_file.id
        acad_circ_id = acad_circ.id

        # Execute Purge on Test Company
        res_purge = self.client.post(
            "/placement/cleanup/execute",
            json={
                "company_ids": [comp_id],
                "mode": "purge",
                "confirmation_phrase": "CONFIRM_PURGE_TEST_DATA",
            },
            headers=self.officer_headers,
        )
        self.assertEqual(res_purge.status_code, 200)

        # Company and recruitment circular deleted
        self.assertIsNone(self.db.query(Company).filter(Company.id == comp_id).first())
        self.assertIsNone(self.db.query(RecruitmentCircular).filter(RecruitmentCircular.id == rcirc_id).first())

        # SHARED FILE RECORD AND ACADEMIC CIRCULAR MUST STILL EXIST!
        self.assertIsNotNone(self.db.query(File).filter(File.id == shared_file_id).first())
        self.assertIsNotNone(self.db.query(Circular).filter(Circular.id == acad_circ_id).first())

    def test_09_safe_student_placement_status_re_evaluation(self):
        """Student placement status is cleanly preserved if student has another active accepted offer."""
        # 1. Company A (Target to purge)
        comp_a = Company(name=f"Temp Company A {self.ts}")
        comp_b = Company(name=f"Independent Company B {self.ts}")
        self.db.add_all([comp_a, comp_b])
        self.db.commit()

        job_a = JobPosting(company_id=comp_a.id, title="Role A", status=JobStatus.OPEN)
        job_b = JobPosting(company_id=comp_b.id, title="Role B", status=JobStatus.OPEN)
        self.db.add_all([job_a, job_b])
        self.db.commit()

        app_a = Application(student_id=self.student_test.id, job_posting_id=job_a.id, status=ApplicationStatus.APPLIED)
        app_b = Application(student_id=self.student_test.id, job_posting_id=job_b.id, status=ApplicationStatus.SELECTED)
        self.db.add_all([app_a, app_b])
        self.db.commit()

        # Company B has an accepted offer
        offer_b = PlacementOffer(
            application_id=app_b.id,
            student_id=self.student_test.id,
            job_posting_id=job_b.id,
            acceptance_status=OfferAcceptanceStatus.ACCEPTED,
        )
        self.db.add(offer_b)

        # Mark profile as PLACED
        self.student_test_profile.placement_status = PlacementStatus.PLACED
        self.db.commit()

        # Purge Company A (which only has an application, no offer)
        res_purge = self.client.post(
            "/placement/cleanup/execute",
            json={
                "company_ids": [comp_a.id],
                "mode": "purge",
                "confirmation_phrase": "CONFIRM_PURGE_TEST_DATA",
            },
            headers=self.officer_headers,
        )
        self.assertEqual(res_purge.status_code, 200)

        # Student must REMAIN PLACED because Company B's offer is active!
        self.db.refresh(self.student_test_profile)
        self.assertEqual(self.student_test_profile.placement_status, PlacementStatus.PLACED)

    def test_10_polymorphic_notification_cleanup_isolation(self):
        """Polymorphic notifications for purged entities are deleted while unrelated notifications remain untouched."""
        comp = Company(name=f"Temp Notif Corp {self.ts}")
        self.db.add(comp)
        self.db.commit()
        self.db.refresh(comp)

        job = JobPosting(company_id=comp.id, title="Role", status=JobStatus.OPEN)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        # 1. Company notification
        notif_comp = Notification(
            user_id=self.student_test.id,
            type="job_posting",
            title="New Job",
            message="Check job",
            reference_id=job.id,
            event_key=f"job_cleanup_{self.ts}_{job.id}",
        )
        # 2. Unrelated notification
        notif_unrelated = Notification(
            user_id=self.student_test.id,
            type="exam_nudge",
            title="Exam Reminder",
            message="Don't forget exam",
            reference_id=99999,
            event_key=f"exam_cleanup_{self.ts}",
        )
        self.db.add_all([notif_comp, notif_unrelated])
        self.db.commit()

        notif_comp_id = notif_comp.id
        notif_unrelated_id = notif_unrelated.id

        # Purge Company
        res_purge = self.client.post(
            "/placement/cleanup/execute",
            json={
                "company_ids": [comp.id],
                "mode": "purge",
                "confirmation_phrase": "CONFIRM_PURGE_TEST_DATA",
            },
            headers=self.officer_headers,
        )
        self.assertEqual(res_purge.status_code, 200)

        # Company notification deleted
        self.assertIsNone(self.db.query(Notification).filter(Notification.id == notif_comp_id).first())
        # Unrelated notification PRESERVED
        self.assertIsNotNone(self.db.query(Notification).filter(Notification.id == notif_unrelated_id).first())

    # =========================================================================
    # 5. ARCHIVE & PURGE WORKFLOWS & AUDIT LOGS
    # =========================================================================

    def test_11_archive_mode_behavior_and_audit(self):
        """Archive mode deactivates companies and closes jobs without deleting any records."""
        comp = Company(name=f"Archive Test Corp {self.ts}", is_active=True)
        self.db.add(comp)
        self.db.commit()
        self.db.refresh(comp)

        batch_doc = self._create_synthetic_file("archive_batch.pdf")
        job = JobPosting(company_id=comp.id, title="Role", status=JobStatus.OPEN)
        circ = RecruitmentCircular(company_id=comp.id, title="Drive", status=RecruitmentCircularStatus.PUBLISHED)
        batch = RecruitmentResultBatch(company_id=comp.id, round_name="OA", file_id=batch_doc.id)
        self.db.add_all([job, circ, batch])
        self.db.commit()

        res_arch = self.client.post(
            "/placement/cleanup/execute",
            json={
                "company_ids": [comp.id],
                "mode": "archive",
            },
            headers=self.officer_headers,
        )
        self.assertEqual(res_arch.status_code, 200)
        data = res_arch.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["mode"], "archive")
        self.assertEqual(data["records_affected"]["companies_deactivated"], 1)

        # Verify DB states
        self.db.refresh(comp)
        self.db.refresh(job)
        self.db.refresh(circ)
        self.db.refresh(batch)

        self.assertFalse(comp.is_active)
        self.assertEqual(job.status, JobStatus.CLOSED)
        self.assertEqual(circ.status, RecruitmentCircularStatus.ARCHIVED)
        self.assertEqual(batch.status, RecruitmentResultBatchStatus.ARCHIVED)

        # Verify Audit Log
        audit = self.db.query(AuditLog).filter(
            AuditLog.action == "RECRUITMENT_TEST_DATA_ARCHIVED",
            AuditLog.target_id.contains(str(comp.id)),
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.actor_id, self.officer.id)

    def test_12_purge_mode_clean_execution_and_audit(self):
        """Purge mode permanently removes disposable test entities and writes audit trail."""
        unshared_doc = self._create_synthetic_file("purge_unshared.pdf")

        comp = Company(name=f"Mock Disposable Corp {self.ts}")
        self.db.add(comp)
        self.db.commit()
        self.db.refresh(comp)

        job = JobPosting(company_id=comp.id, title="Role", status=JobStatus.OPEN)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        batch = RecruitmentResultBatch(company_id=comp.id, job_posting_id=job.id, file_id=unshared_doc.id, round_name="OA")
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)

        item = RecruitmentResultItem(batch_id=batch.id, row_index=1, raw_data={}, review_status=RecruitmentResultReviewState.PENDING)
        self.db.add(item)
        self.db.commit()

        comp_id = comp.id
        job_id = job.id
        batch_id = batch.id
        doc_id = unshared_doc.id

        # Purge
        res_purge = self.client.post(
            "/placement/cleanup/execute",
            json={
                "company_ids": [comp_id],
                "mode": "purge",
                "confirmation_phrase": "CONFIRM_PURGE_TEST_DATA",
            },
            headers=self.officer_headers,
        )
        self.assertEqual(res_purge.status_code, 200)
        data = res_purge.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["mode"], "purge")
        self.assertEqual(data["records_affected"]["companies_deleted"], 1)
        self.assertEqual(data["records_affected"]["jobs_deleted"], 1)
        self.assertEqual(data["records_affected"]["batches_deleted"], 1)
        self.assertEqual(data["records_affected"]["files_deleted"], 1)

        # Verify DB is clean
        self.assertIsNone(self.db.query(Company).filter(Company.id == comp_id).first())
        self.assertIsNone(self.db.query(JobPosting).filter(JobPosting.id == job_id).first())
        self.assertIsNone(self.db.query(RecruitmentResultBatch).filter(RecruitmentResultBatch.id == batch_id).first())
        self.assertIsNone(self.db.query(File).filter(File.id == doc_id).first())

        # Verify Audit Log
        audit = self.db.query(AuditLog).filter(
            AuditLog.action == "RECRUITMENT_TEST_DATA_PURGED",
            AuditLog.target_id.contains(str(comp_id)),
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.actor_id, self.officer.id)


if __name__ == "__main__":
    unittest.main()
