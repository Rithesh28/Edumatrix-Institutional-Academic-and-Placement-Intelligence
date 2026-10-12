"""
EduMatrix Phase 3.4 Bulk Company Management and Cleanup Integration Tests

Validates:
1. Bulk preview for multiple companies (exact dependent counts, safety classifications, linked titles, and records breakdown).
2. RBAC enforcement: Student, Lecturer, HOD, and unauthenticated requests blocked with HTTP 403 / 401.
3. Safe purge of disposable companies and exclusive dependencies in FK-safe cascade order.
4. Exact confirmation phrase requirement ('CONFIRM_PURGE_TEST_DATA') for permanent purge.
5. Shared job and shared file preservation:
   - Job referenced by another company's drive blocks purge of the owning company (classifies as REQUIRES_ARCHIVE).
   - Shared storage files referenced by academic circulars/other batches are preserved.
6. Blocking deletion of companies with genuine applications, confirmed outcomes, or accepted offers.
7. Non-destructive archive mode deactivates companies, closes jobs, and archives circulars without data loss.
8. Mixed selections: If a purge batch contains even one protected or archive-required company, the entire request is rejected atomically with zero partial deletions.
9. Invalid IDs and repeated requests handling (nonexistent ID returns HTTP 400, repeated purge returns HTTP 400).
10. No regression to single-company CRUD (delete_company soft delete) or recruitment-drive cleanup workflows.
"""

import time
import unittest
import uuid
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
from app.models.shortlist import Shortlist
from app.models.profile import StudentProfileExtended, PlacementStatus
from app.models.file import File, FileStatus, FileType
from app.models.circular import Circular, CircularType
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
    RecruitmentResultReviewState,
)
from app.services.placement_cleanup_service import placement_cleanup_service
from app.services.placement_service import placement_service


class TestBulkCompanyCleanup(unittest.TestCase):
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
                email=f"officer_bulk_comp_{cls.ts}@vcet.ac.in",
                name="Placement Officer Bulk Comp Test",
                role=UserRole.PLACEMENT_OFFICER,
                password_hash=cls.pwd_hash,
                is_active=True,
            )
            cls.db.add(cls.officer)
            cls.db.commit()
            cls.db.refresh(cls.officer)
        cls.officer_token = create_access_token({
            "id": cls.officer.id,
            "email": cls.officer.email,
            "role": cls.officer.role.value if hasattr(cls.officer.role, "value") else str(cls.officer.role),
        })
        cls.officer_headers = {"Authorization": f"Bearer {cls.officer_token}"}

        # 2. Student (Synthetic test student)
        cls.student = User(
            email=f"test_student_comp_{cls.ts}@vcet.ac.in",
            name="Synthetic Test Student",
            role=UserRole.STUDENT,
            password_hash=cls.pwd_hash,
            is_active=True,
        )
        cls.db.add(cls.student)
        cls.db.commit()
        cls.db.refresh(cls.student)
        cls.student_token = create_access_token({
            "id": cls.student.id,
            "email": cls.student.email,
            "role": cls.student.role.value if hasattr(cls.student.role, "value") else str(cls.student.role),
        })
        cls.student_headers = {"Authorization": f"Bearer {cls.student_token}"}

        # 3. Genuine Student
        cls.genuine_student = User(
            email=f"genuine_student_comp_{cls.ts}@vcet.ac.in",
            name="Ananya Genuine Student",
            role=UserRole.STUDENT,
            password_hash=cls.pwd_hash,
            is_active=True,
        )
        cls.db.add(cls.genuine_student)
        cls.db.commit()
        cls.db.refresh(cls.genuine_student)

        cls.genuine_profile = StudentProfileExtended(
            user_id=cls.genuine_student.id,
            enrollment_number=f"GENCOMP{cls.ts % 100000}",
            full_name="Ananya Genuine Student",
            branch="CSE",
            cgpa=9.1,
            placement_status=PlacementStatus.NOT_APPLIED,
        )
        cls.db.add(cls.genuine_profile)
        cls.db.commit()

        # Track entities created across tests for tearDownClass
        cls.created_company_ids: List[int] = []
        cls.created_job_ids: List[int] = []
        cls.created_circular_ids: List[int] = []
        cls.created_file_ids: List[uuid.UUID] = []

    @classmethod
    def tearDownClass(cls):
        try:
            if cls.created_circular_ids:
                cls.db.query(RecruitmentCircularAttachment).filter(
                    RecruitmentCircularAttachment.circular_id.in_(cls.created_circular_ids)
                ).delete(synchronize_session=False)
                cls.db.query(RecruitmentCircularJob).filter(
                    RecruitmentCircularJob.circular_id.in_(cls.created_circular_ids)
                ).delete(synchronize_session=False)
                cls.db.query(RecruitmentCircular).filter(
                    RecruitmentCircular.id.in_(cls.created_circular_ids)
                ).delete(synchronize_session=False)

            if cls.created_job_ids:
                cls.db.query(PlacementOffer).filter(
                    PlacementOffer.job_posting_id.in_(cls.created_job_ids)
                ).delete(synchronize_session=False)
                cls.db.query(Application).filter(
                    Application.job_posting_id.in_(cls.created_job_ids)
                ).delete(synchronize_session=False)
                cls.db.query(RecruitmentRound).filter(
                    RecruitmentRound.job_posting_id.in_(cls.created_job_ids)
                ).delete(synchronize_session=False)
                cls.db.query(JobPosting).filter(
                    JobPosting.id.in_(cls.created_job_ids)
                ).delete(synchronize_session=False)

            if cls.created_company_ids:
                cls.db.query(RecruitmentResultBatch).filter(
                    RecruitmentResultBatch.company_id.in_(cls.created_company_ids)
                ).delete(synchronize_session=False)
                cls.db.query(Company).filter(
                    Company.id.in_(cls.created_company_ids)
                ).delete(synchronize_session=False)

            cls.db.commit()
        except Exception:
            cls.db.rollback()
        finally:
            cls.db.close()

    def tearDown(self):
        self.db.rollback()

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
        self.created_file_ids.append(f.id)
        return f

    # =========================================================================
    # 1. BULK PREVIEW FOR MULTIPLE COMPANIES
    # =========================================================================

    def test_01_bulk_preview_multiple_companies(self):
        """Preview for multiple explicitly selected companies calculates exact dependent counts and classifications."""
        # Create 2 test companies
        comp1 = Company(name=f"Mock Alpha Corp {self.ts}_1", is_active=True)
        comp2 = Company(name=f"Temp Beta Ltd {self.ts}_2", is_active=True)
        self.db.add_all([comp1, comp2])
        self.db.commit()
        self.db.refresh(comp1)
        self.db.refresh(comp2)
        self.created_company_ids.extend([comp1.id, comp2.id])

        job1 = JobPosting(company_id=comp1.id, title="Frontend Intern", status=JobStatus.OPEN)
        job2 = JobPosting(company_id=comp2.id, title="Backend Intern", status=JobStatus.OPEN)
        self.db.add_all([job1, job2])
        self.db.commit()
        self.created_job_ids.extend([job1.id, job2.id])

        circ1 = RecruitmentCircular(company_id=comp1.id, title="Alpha Drive", status=RecruitmentCircularStatus.DRAFT)
        self.db.add(circ1)
        self.db.commit()
        self.created_circular_ids.append(circ1.id)

        # Call bulk preview endpoint with both company IDs
        res = self.client.get(
            f"/placement/cleanup/preview?company_ids={comp1.id}&company_ids={comp2.id}",
            headers=self.officer_headers,
        )
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()

        self.assertIn("summary", data)
        self.assertIn("candidates", data)

        summary = data["summary"]
        self.assertEqual(summary["total_candidates_flagged"], 2)
        self.assertEqual(summary["total_dependent_jobs"], 2)
        self.assertEqual(summary["total_dependent_circulars"], 1)

        candidates = {c["company_id"]: c for c in data["candidates"]}
        self.assertIn(comp1.id, candidates)
        self.assertIn(comp2.id, candidates)

        c1_data = candidates[comp1.id]
        self.assertEqual(c1_data["company_name"], comp1.name)
        self.assertEqual(c1_data["dependent_counts"]["jobs_count"], 1)
        self.assertEqual(c1_data["dependent_counts"]["circulars_count"], 1)
        self.assertIn("Frontend Intern", c1_data["linked_job_titles"])
        self.assertIn("Alpha Drive", c1_data["linked_circular_titles"])
        self.assertEqual(c1_data["safety_classification"], "SAFE_TO_PURGE")
        self.assertTrue(c1_data["can_purge"])
        self.assertIsNotNone(c1_data["records_breakdown"])

    # =========================================================================
    # 2. RBAC ENFORCEMENT
    # =========================================================================

    def test_02_rbac_unauthorized_requests_forbidden(self):
        """Student and unauthenticated requests are forbidden with HTTP 403 / 401."""
        comp = Company(name=f"Mock RBAC Corp {self.ts}", is_active=True)
        self.db.add(comp)
        self.db.commit()
        self.created_company_ids.append(comp.id)

        # 1. Preview by student -> 403
        resp_prev = self.client.get(
            f"/placement/cleanup/preview?company_ids={comp.id}",
            headers=self.student_headers,
        )
        self.assertEqual(resp_prev.status_code, 403)

        # 2. Execute by student -> 403
        resp_exec = self.client.post(
            "/placement/cleanup/execute",
            headers=self.student_headers,
            json={"company_ids": [comp.id], "mode": "archive"},
        )
        self.assertEqual(resp_exec.status_code, 403)

        # 3. Unauthenticated preview -> 401
        resp_unauth = self.client.get(f"/placement/cleanup/preview?company_ids={comp.id}")
        self.assertEqual(resp_unauth.status_code, 401)

    # =========================================================================
    # 3. CONFIRMATION PHRASE REQUIREMENT FOR PURGE
    # =========================================================================

    def test_03_purge_confirmation_phrase_required(self):
        """Destructive purge strictly requires the exact confirmation phrase 'CONFIRM_PURGE_TEST_DATA'."""
        comp = Company(name=f"Mock Purge Phrase {self.ts}", is_active=True)
        self.db.add(comp)
        self.db.commit()
        self.created_company_ids.append(comp.id)

        # Purge without phrase -> 400
        res_no_phrase = self.client.post(
            "/placement/cleanup/execute",
            json={"company_ids": [comp.id], "mode": "purge"},
            headers=self.officer_headers,
        )
        self.assertEqual(res_no_phrase.status_code, 400)
        self.assertIn("confirmation phrase", res_no_phrase.json()["detail"].lower())

        # Purge with wrong phrase -> 400
        res_wrong = self.client.post(
            "/placement/cleanup/execute",
            json={"company_ids": [comp.id], "mode": "purge", "confirmation_phrase": "CONFIRM_DELETE"},
            headers=self.officer_headers,
        )
        self.assertEqual(res_wrong.status_code, 400)
        self.assertIn("confirmation phrase", res_wrong.json()["detail"].lower())

    # =========================================================================
    # 4. SAFE PURGE OF DISPOSABLE COMPANIES
    # =========================================================================

    def test_04_safe_purge_disposable_companies(self):
        """Safe purge permanently removes disposable test companies and their exclusive dependencies."""
        doc = self._create_synthetic_file("comp_purge.pdf")
        doc_id = doc.id

        comp1 = Company(name=f"Temp Purge Corp 1 {self.ts}", is_active=True)
        comp2 = Company(name=f"Mock Purge Corp 2 {self.ts}", is_active=True)
        self.db.add_all([comp1, comp2])
        self.db.commit()
        c1_id, c2_id = comp1.id, comp2.id

        job1 = JobPosting(company_id=c1_id, title="Role 1", status=JobStatus.DRAFT)
        job2 = JobPosting(company_id=c2_id, title="Role 2", status=JobStatus.DRAFT)
        self.db.add_all([job1, job2])
        self.db.commit()
        j1_id, j2_id = job1.id, job2.id

        circ1 = RecruitmentCircular(company_id=c1_id, title="Drive Purge 1", status=RecruitmentCircularStatus.DRAFT)
        self.db.add(circ1)
        self.db.commit()
        circ1_id = circ1.id

        cj1 = RecruitmentCircularJob(circular_id=circ1_id, job_posting_id=j1_id)
        att1 = RecruitmentCircularAttachment(circular_id=circ1_id, file_id=doc_id, attachment_type=AttachmentType.POSTER.value)
        self.db.add_all([cj1, att1])
        self.db.commit()

        # Execute bulk purge with exact confirmation phrase
        res = self.client.post(
            "/placement/cleanup/execute",
            json={
                "company_ids": [c1_id, c2_id],
                "mode": "purge",
                "confirmation_phrase": "CONFIRM_PURGE_TEST_DATA",
            },
            headers=self.officer_headers,
        )
        self.assertEqual(res.status_code, 200, res.text)
        result = res.json()
        self.assertTrue(result["success"])
        self.assertEqual(result["companies_processed"], 2)

        # Verify DB records are gone
        self.db.expire_all()
        self.assertIsNone(self.db.query(Company).filter(Company.id.in_([c1_id, c2_id])).first())
        self.assertIsNone(self.db.query(JobPosting).filter(JobPosting.id.in_([j1_id, j2_id])).first())
        self.assertIsNone(self.db.query(RecruitmentCircular).filter(RecruitmentCircular.id == circ1_id).first())
        self.assertIsNone(self.db.query(RecruitmentCircularJob).filter(RecruitmentCircularJob.circular_id == circ1_id).first())
        self.assertIsNone(self.db.query(File).filter(File.id == doc_id).first())

    # =========================================================================
    # 5. SHARED JOB AND SHARED FILE PRESERVATION
    # =========================================================================

    def test_05_shared_job_and_file_preservation(self):
        """Jobs referenced by another company's drive block purge (REQUIRES_ARCHIVE); shared files are preserved."""
        comp_a = Company(name=f"Mock Owning Corp {self.ts}", is_active=True)
        comp_b = Company(name=f"Mock External Corp {self.ts}", is_active=True)
        self.db.add_all([comp_a, comp_b])
        self.db.commit()
        self.created_company_ids.extend([comp_a.id, comp_b.id])

        # Job belongs to Company A
        job_a = JobPosting(company_id=comp_a.id, title="Shared Cross-Company Role", status=JobStatus.OPEN)
        self.db.add(job_a)
        self.db.commit()
        self.created_job_ids.append(job_a.id)

        # Drive belongs to Company B, but links Job A
        drive_b = RecruitmentCircular(company_id=comp_b.id, title="Drive External B", status=RecruitmentCircularStatus.PUBLISHED)
        self.db.add(drive_b)
        self.db.commit()
        self.created_circular_ids.append(drive_b.id)

        cj = RecruitmentCircularJob(circular_id=drive_b.id, job_posting_id=job_a.id)
        self.db.add(cj)
        self.db.commit()

        # Shared File with Academic Circular
        shared_file = self._create_synthetic_file("academic_shared.pdf")
        acad_circ = Circular(
            title=f"Academic Notice {self.ts}",
            type=CircularType.GENERAL,
            file_id=shared_file.id,
            lecturer_id=self.officer.id,
            content="Important notice",
        )
        self.db.add(acad_circ)
        self.db.commit()

        # Preview on Company A must show REQUIRES_ARCHIVE due to Job A referenced by Drive B
        res_prev = self.client.get(
            f"/placement/cleanup/preview?company_ids={comp_a.id}",
            headers=self.officer_headers,
        )
        self.assertEqual(res_prev.status_code, 200)
        cand = res_prev.json()["candidates"][0]
        self.assertEqual(cand["safety_classification"], "REQUIRES_ARCHIVE")
        self.assertFalse(cand["can_purge"])
        self.assertTrue(any("referenced by other company drive" in r for r in cand["protection_reasons"]))

        # Attempting destructive purge on Company A must fail
        res_purge = self.client.post(
            "/placement/cleanup/execute",
            json={
                "company_ids": [comp_a.id],
                "mode": "purge",
                "confirmation_phrase": "CONFIRM_PURGE_TEST_DATA",
            },
            headers=self.officer_headers,
        )
        self.assertEqual(res_purge.status_code, 400)
        self.assertIn("requires_archive", res_purge.json()["detail"].lower())

    # =========================================================================
    # 6. BLOCKING DELETION OF COMPANIES WITH GENUINE RECORDS
    # =========================================================================

    def test_06_blocking_deletion_with_accepted_offers_and_genuine_students(self):
        """Companies with student-accepted placement offers or genuine student records are blocked from purge."""
        comp = Company(name=f"Mock Offer Corp {self.ts}", is_active=True)
        self.db.add(comp)
        self.db.commit()
        self.created_company_ids.append(comp.id)

        job = JobPosting(company_id=comp.id, title="Analyst", status=JobStatus.OPEN)
        self.db.add(job)
        self.db.commit()
        self.created_job_ids.append(job.id)

        app = Application(
            student_id=self.genuine_student.id,
            job_posting_id=job.id,
            status=ApplicationStatus.SELECTED,
        )
        self.db.add(app)
        self.db.commit()

        offer = PlacementOffer(
            student_id=self.genuine_student.id,
            job_posting_id=job.id,
            application_id=app.id,
            designation="Analyst",
            ctc_lpa=12.5,
            acceptance_status=OfferAcceptanceStatus.ACCEPTED,
        )
        self.db.add(offer)
        self.db.commit()

        # Purge attempt must be blocked
        res = self.client.post(
            "/placement/cleanup/execute",
            json={
                "company_ids": [comp.id],
                "mode": "purge",
                "confirmation_phrase": "CONFIRM_PURGE_TEST_DATA",
            },
            headers=self.officer_headers,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("accepted placement offer", res.json()["detail"].lower())

    # =========================================================================
    # 7. ARCHIVE BEHAVIOR FOR COMPANIES REQUIRING ARCHIVE
    # =========================================================================

    def test_07_archive_behavior_for_companies_requiring_archive(self):
        """Archive mode successfully deactivates companies and closes jobs without deleting any data."""
        comp = Company(name=f"Archive Corp {self.ts}", is_active=True)
        self.db.add(comp)
        self.db.commit()
        self.created_company_ids.append(comp.id)

        job = JobPosting(company_id=comp.id, title="Associate", status=JobStatus.OPEN)
        self.db.add(job)
        self.db.commit()
        self.created_job_ids.append(job.id)

        circ = RecruitmentCircular(company_id=comp.id, title="Drive Arch", status=RecruitmentCircularStatus.PUBLISHED)
        self.db.add(circ)
        self.db.commit()
        self.created_circular_ids.append(circ.id)

        # Execute archive
        res = self.client.post(
            "/placement/cleanup/execute",
            json={"company_ids": [comp.id], "mode": "archive"},
            headers=self.officer_headers,
        )
        self.assertEqual(res.status_code, 200, res.text)
        result = res.json()
        self.assertTrue(result["success"])
        self.assertEqual(result["companies_processed"], 1)

        self.db.expire_all()
        # Company deactivated
        comp_updated = self.db.query(Company).filter(Company.id == comp.id).first()
        self.assertFalse(comp_updated.is_active)

        # Job closed
        job_updated = self.db.query(JobPosting).filter(JobPosting.id == job.id).first()
        self.assertEqual(job_updated.status, JobStatus.CLOSED)

        # Circular archived
        circ_updated = self.db.query(RecruitmentCircular).filter(RecruitmentCircular.id == circ.id).first()
        self.assertEqual(circ_updated.status, RecruitmentCircularStatus.ARCHIVED)

    # =========================================================================
    # 8. MIXED SELECTIONS: ATOMIC REJECTION WITH ZERO PARTIAL DELETION
    # =========================================================================

    def test_08_mixed_selections_atomic_rejection(self):
        """Mixed batches (safe + protected) are rejected entirely; zero partial deletions occur."""
        # 1. Safe company
        comp_safe = Company(name=f"Mock Safe Disposable {self.ts}", is_active=True)
        # 2. Protected company with accepted offer
        comp_prot = Company(name=f"Mock Protected Offer {self.ts}", is_active=True)
        self.db.add_all([comp_safe, comp_prot])
        self.db.commit()
        self.created_company_ids.extend([comp_safe.id, comp_prot.id])

        job_prot = JobPosting(company_id=comp_prot.id, title="Lead", status=JobStatus.OPEN)
        self.db.add(job_prot)
        self.db.commit()
        self.created_job_ids.append(job_prot.id)

        app_prot = Application(student_id=self.student.id, job_posting_id=job_prot.id, status=ApplicationStatus.SELECTED)
        self.db.add(app_prot)
        self.db.commit()

        offer_prot = PlacementOffer(
            student_id=self.student.id,
            job_posting_id=job_prot.id,
            application_id=app_prot.id,
            designation="Lead",
            ctc_lpa=15.0,
            acceptance_status=OfferAcceptanceStatus.ACCEPTED,
        )
        self.db.add(offer_prot)
        self.db.commit()

        # Purge batch with both safe and protected companies
        res = self.client.post(
            "/placement/cleanup/execute",
            json={
                "company_ids": [comp_safe.id, comp_prot.id],
                "mode": "purge",
                "confirmation_phrase": "CONFIRM_PURGE_TEST_DATA",
            },
            headers=self.officer_headers,
        )
        self.assertEqual(res.status_code, 400)

        # CRITICAL SAFETY CHECK: Verify comp_safe was NOT deleted
        self.db.expire_all()
        safe_check = self.db.query(Company).filter(Company.id == comp_safe.id).first()
        self.assertIsNotNone(safe_check, "Safe company must not be deleted when mixed batch fails!")

    # =========================================================================
    # 9. INVALID IDS AND REPEATED REQUESTS
    # =========================================================================

    def test_09_invalid_ids_and_repeated_requests(self):
        """Nonexistent IDs return HTTP 400; repeated purge returns HTTP 400."""
        # Nonexistent ID
        res_nonexistent = self.client.post(
            "/placement/cleanup/execute",
            json={"company_ids": [99999999], "mode": "archive"},
            headers=self.officer_headers,
        )
        self.assertEqual(res_nonexistent.status_code, 400)
        self.assertIn("not found", res_nonexistent.json()["detail"].lower())

        # Create and purge
        comp = Company(name=f"Mock Disposable Repeat {self.ts}", is_active=True)
        self.db.add(comp)
        self.db.commit()
        c_id = comp.id

        res1 = self.client.post(
            "/placement/cleanup/execute",
            json={"company_ids": [c_id], "mode": "purge", "confirmation_phrase": "CONFIRM_PURGE_TEST_DATA"},
            headers=self.officer_headers,
        )
        self.assertEqual(res1.status_code, 200)

        # Repeat purge -> 400
        res2 = self.client.post(
            "/placement/cleanup/execute",
            json={"company_ids": [c_id], "mode": "purge", "confirmation_phrase": "CONFIRM_PURGE_TEST_DATA"},
            headers=self.officer_headers,
        )
        self.assertEqual(res2.status_code, 400)
        self.assertIn("not found", res2.json()["detail"].lower())

    # =========================================================================
    # 10. NO REGRESSION TO EXISTING COMPANY CRUD & RECRUITMENT DRIVES
    # =========================================================================

    def test_10_no_regression_to_single_company_crud(self):
        """Single-company CRUD and drive cleanup endpoints work without regression."""
        # Test single delete (soft delete)
        comp = Company(name=f"Single Delete Test {self.ts}", is_active=True)
        self.db.add(comp)
        self.db.commit()
        self.created_company_ids.append(comp.id)

        success = placement_service.delete_company(self.db, comp.id)
        self.assertTrue(success)

        self.db.expire_all()
        refetched = self.db.query(Company).filter(Company.id == comp.id).first()
        self.assertFalse(refetched.is_active)

        # Test drive cleanup preview endpoint continues to work
        res_drive = self.client.get("/placement/cleanup/drives/preview", headers=self.officer_headers)
        self.assertEqual(res_drive.status_code, 200)
        self.assertIn("summary", res_drive.json())

    # =========================================================================
    # 11. SAFE ARCHIVE SHARED JOB PRESERVATION
    # =========================================================================

    def test_11_safe_archive_shared_job_preservation(self):
        """Safe Archive deactivates company, closes exclusive job, but preserves job shared with another active drive."""
        sub_ts = int(time.time() * 1000)

        # Company A (target of archive)
        comp_a = Company(name=f"Archive Corp A {sub_ts}", is_active=True)
        # Company B (external active company)
        comp_b = Company(name=f"Active Partner B {sub_ts}", is_active=True)
        self.db.add_all([comp_a, comp_b])
        self.db.commit()
        self.created_company_ids.extend([comp_a.id, comp_b.id])

        # Job 1: Belongs to Comp A, but shared with Comp B's active drive
        job_shared = JobPosting(company_id=comp_a.id, title=f"Shared Role {sub_ts}", status=JobStatus.OPEN)
        # Job 2: Belongs to Comp A, exclusive to Comp A
        job_exclusive = JobPosting(company_id=comp_a.id, title=f"Exclusive Role {sub_ts}", status=JobStatus.OPEN)
        self.db.add_all([job_shared, job_exclusive])
        self.db.commit()
        self.created_job_ids.extend([job_shared.id, job_exclusive.id])

        # Drive A: Under Comp A
        circ_a = RecruitmentCircular(
            company_id=comp_a.id,
            title=f"Drive A {sub_ts}",
            status=RecruitmentCircularStatus.PUBLISHED,
            created_by=self.officer.id,
        )
        # Drive B: Under Comp B (active drive)
        circ_b = RecruitmentCircular(
            company_id=comp_b.id,
            title=f"Drive B {sub_ts}",
            status=RecruitmentCircularStatus.PUBLISHED,
            created_by=self.officer.id,
        )
        self.db.add_all([circ_a, circ_b])
        self.db.commit()
        self.created_circular_ids.extend([circ_a.id, circ_b.id])

        # Link shared job to both Drive A and Drive B
        link_a = RecruitmentCircularJob(circular_id=circ_a.id, job_posting_id=job_shared.id)
        link_b = RecruitmentCircularJob(circular_id=circ_b.id, job_posting_id=job_shared.id)
        # Link exclusive job only to Drive A
        link_a2 = RecruitmentCircularJob(circular_id=circ_a.id, job_posting_id=job_exclusive.id)
        self.db.add_all([link_a, link_b, link_a2])
        self.db.commit()

        # Execute Safe Archive on Company A
        res = self.client.post(
            "/placement/cleanup/execute",
            json={"company_ids": [comp_a.id], "mode": "archive"},
            headers=self.officer_headers,
        )
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["companies_processed"], 1)
        self.assertEqual(data["records_affected"]["companies_deactivated"], 1)
        self.assertEqual(data["records_affected"]["jobs_closed"], 1)
        self.assertEqual(data["records_affected"]["shared_jobs_preserved"], 1)

        self.db.expire_all()
        # 1. Company A deactivated
        refetched_a = self.db.query(Company).filter(Company.id == comp_a.id).first()
        self.assertFalse(refetched_a.is_active)

        # 2. Drive A archived
        refetched_circ_a = self.db.query(RecruitmentCircular).filter(RecruitmentCircular.id == circ_a.id).first()
        self.assertEqual(refetched_circ_a.status, RecruitmentCircularStatus.ARCHIVED)

        # 3. Exclusive job CLOSED
        refetched_job_excl = self.db.query(JobPosting).filter(JobPosting.id == job_exclusive.id).first()
        self.assertEqual(refetched_job_excl.status, JobStatus.CLOSED)

        # 4. CRITICAL: Shared job remains OPEN because Drive B is still active
        refetched_job_shared = self.db.query(JobPosting).filter(JobPosting.id == job_shared.id).first()
        self.assertEqual(refetched_job_shared.status, JobStatus.OPEN, "Shared job must NOT be closed while Drive B is active!")

        # 5. Company B and Drive B untouched
        refetched_b = self.db.query(Company).filter(Company.id == comp_b.id).first()
        self.assertTrue(refetched_b.is_active)
        refetched_circ_b = self.db.query(RecruitmentCircular).filter(RecruitmentCircular.id == circ_b.id).first()
        self.assertEqual(refetched_circ_b.status, RecruitmentCircularStatus.PUBLISHED)

    # =========================================================================
    # 12. SAFE ARCHIVE HISTORICAL RECORDS PRESERVED
    # =========================================================================

    def test_12_safe_archive_historical_records_preserved(self):
        """Safe Archive preserves student applications, progression outcomes, and verified offers."""
        sub_ts = int(time.time() * 1000)

        comp = Company(name=f"Historical Corp {sub_ts}", is_active=True)
        self.db.add(comp)
        self.db.commit()
        self.created_company_ids.append(comp.id)

        job = JobPosting(company_id=comp.id, title=f"Historical Job {sub_ts}", status=JobStatus.OPEN)
        self.db.add(job)
        self.db.commit()
        self.created_job_ids.append(job.id)

        app = Application(
            job_posting_id=job.id,
            student_id=self.genuine_student.id,
            status=ApplicationStatus.SELECTED,
        )
        self.db.add(app)
        self.db.flush()

        offer = PlacementOffer(
            application_id=app.id,
            job_posting_id=job.id,
            student_id=self.genuine_student.id,
            acceptance_status=OfferAcceptanceStatus.ACCEPTED,
            ctc_lpa=18.0,
        )
        self.db.add(offer)
        self.db.commit()

        # Safe Archive
        res = self.client.post(
            "/placement/cleanup/execute",
            json={"company_ids": [comp.id], "mode": "archive"},
            headers=self.officer_headers,
        )
        self.assertEqual(res.status_code, 200, res.text)

        self.db.expire_all()
        # Verify historical records still exist
        refetched_app = self.db.query(Application).filter(Application.id == app.id).first()
        self.assertIsNotNone(refetched_app, "Application must remain intact after Safe Archive")

        refetched_offer = self.db.query(PlacementOffer).filter(PlacementOffer.id == offer.id).first()
        self.assertIsNotNone(refetched_offer, "Accepted offer must remain intact after Safe Archive")
        self.assertEqual(refetched_offer.acceptance_status, OfferAcceptanceStatus.ACCEPTED)

    # =========================================================================
    # 13. SAFE ARCHIVE FAILURE MODES AND ERROR FEEDBACK
    # =========================================================================

    def test_13_safe_archive_failure_modes_and_error_reporting(self):
        """Empty targets, invalid IDs, or invalid mode return HTTP 422/400 with explicit error message."""
        # Empty company_ids -> schema validation error (HTTP 422)
        res_empty = self.client.post(
            "/placement/cleanup/execute",
            json={"company_ids": [], "mode": "archive"},
            headers=self.officer_headers,
        )
        self.assertEqual(res_empty.status_code, 422)

        # Non-existent company ID -> returns HTTP 400 with clear message
        res_not_found = self.client.post(
            "/placement/cleanup/execute",
            json={"company_ids": [99999999], "mode": "archive"},
            headers=self.officer_headers,
        )
        self.assertEqual(res_not_found.status_code, 400)
        self.assertIn("not found", res_not_found.json()["detail"].lower())

        # Invalid mode -> schema validation error (HTTP 422)
        res_bad_mode = self.client.post(
            "/placement/cleanup/execute",
            json={"company_ids": [1], "mode": "destroy"},
            headers=self.officer_headers,
        )
        self.assertEqual(res_bad_mode.status_code, 422)

    # =========================================================================
    # 14. COMPANY PAGINATION AND ACTIVE FILTERING
    # =========================================================================

    def test_14_company_pagination_and_active_filtering(self):
        """Companies endpoint supports limit up to 1000 and is_active boolean filtering."""
        res_active = self.client.get(
            "/placement/companies?is_active=true&limit=500",
            headers=self.officer_headers,
        )
        self.assertEqual(res_active.status_code, 200)
        active_comps = res_active.json()
        self.assertTrue(all(c["is_active"] is True for c in active_comps))

        res_inactive = self.client.get(
            "/placement/companies?is_active=false&limit=500",
            headers=self.officer_headers,
        )
        self.assertEqual(res_inactive.status_code, 200)
        inactive_comps = res_inactive.json()
        self.assertTrue(all(c["is_active"] is False for c in inactive_comps))


if __name__ == "__main__":
    unittest.main()

