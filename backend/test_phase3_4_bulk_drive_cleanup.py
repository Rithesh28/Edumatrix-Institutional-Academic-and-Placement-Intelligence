"""
EduMatrix Phase 3.4 Bulk Recruitment Drive Cleanup Integration Tests

Validates:
1. Preview-only behavior with detailed dependency graphs and safety classifications.
2. Filtering by specific circular_ids.
3. RBAC enforcement: Student and unauthorized requests blocked with HTTP 403 / 401.
4. Confirmation phrase requirement (CONFIRM_PURGE_TEST_DATA) for permanent purge.
5. Safe purge of test drives and exclusive dependencies in foreign-key cascade order.
6. Shared job preservation (role linked to multiple drives is unlinked, not deleted).
7. Shared file preservation (files referenced by other circulars/attachments are not deleted).
8. Protection of genuine applications and accepted offers (blocks purge; archive allowed).
9. Atomic batch validation (mixed safe + protected batch is completely rejected with zero partial deletion).
10. Orphaned test job detection and cleanup.
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
from app.models.audit_log import AuditLog
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
    RecruitmentResultItemStatus,
    RecruitmentResultReviewState,
)
from app.services.placement_cleanup_service import placement_cleanup_service


class TestBulkDriveCleanup(unittest.TestCase):
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
                email=f"officer_drive_test_{cls.ts}@vcet.ac.in",
                name="Placement Officer Drive Test",
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
            email=f"test_student_drive_{cls.ts}@vcet.ac.in",
            name="Synthetic Test Student",
            role=UserRole.STUDENT,
            password_hash=cls.pwd_hash,
            is_active=True,
        )
        cls.db.add(cls.student)
        cls.db.commit()
        cls.db.refresh(cls.student)

        cls.student_profile = StudentProfileExtended(
            user_id=cls.student.id,
            enrollment_number=f"TESTDRV{cls.ts % 100000}",
            full_name="Synthetic Test Student",
            branch="CSE",
            cgpa=8.0,
            placement_status=PlacementStatus.NOT_APPLIED,
        )
        cls.db.add(cls.student_profile)
        cls.db.commit()

        cls.student_token = create_access_token({
            "id": cls.student.id,
            "email": cls.student.email,
            "role": cls.student.role.value if hasattr(cls.student.role, "value") else str(cls.student.role),
        })
        cls.student_headers = {"Authorization": f"Bearer {cls.student_token}"}

        # 3. Genuine Student (No test keywords in name/email)
        cls.genuine_student = User(
            email=f"pooja_genuine_{cls.ts}@vcet.ac.in",
            name="Pooja Genuine Student",
            role=UserRole.STUDENT,
            password_hash=cls.pwd_hash,
            is_active=True,
        )
        cls.db.add(cls.genuine_student)
        cls.db.commit()
        cls.db.refresh(cls.genuine_student)

        cls.genuine_profile = StudentProfileExtended(
            user_id=cls.genuine_student.id,
            enrollment_number=f"GENDRV{cls.ts % 100000}",
            full_name="Pooja Genuine Student",
            branch="ECE",
            cgpa=9.2,
            placement_status=PlacementStatus.NOT_APPLIED,
        )
        cls.db.add(cls.genuine_profile)
        cls.db.commit()

        # Track entities created across tests for tearDownClass
        cls.created_circular_ids: List[int] = []
        cls.created_job_ids: List[int] = []
        cls.created_company_ids: List[int] = []
        cls.created_file_ids: List[uuid.UUID] = []

    @classmethod
    def tearDownClass(cls):
        # Clean up any leftover test entities
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
                cls.db.query(Company).filter(
                    Company.id.in_(cls.created_company_ids)
                ).delete(synchronize_session=False)

            if cls.created_file_ids:
                cls.db.query(File).filter(
                    File.id.in_(cls.created_file_ids)
                ).delete(synchronize_session=False)

            if hasattr(cls, "student_profile"):
                cls.db.delete(cls.student_profile)
            if hasattr(cls, "student"):
                cls.db.delete(cls.student)
            if hasattr(cls, "genuine_profile"):
                cls.db.delete(cls.genuine_profile)
            if hasattr(cls, "genuine_student"):
                cls.db.delete(cls.genuine_student)

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


    def test_01_drive_preview_endpoint_auth_and_structure(self):
        """GET /placement/cleanup/drives/preview returns summary and drive candidates."""
        resp = self.client.get("/placement/cleanup/drives/preview", headers=self.officer_headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()

        self.assertIn("summary", data)
        self.assertIn("drives", data)
        self.assertIn("orphaned_jobs", data)

        summary = data["summary"]
        self.assertIn("total_drives_flagged", summary)
        self.assertIn("total_drives_safe_to_purge", summary)
        self.assertIn("total_drives_requires_archive", summary)
        self.assertIn("total_drives_protected_genuine", summary)
        self.assertIn("total_orphaned_jobs", summary)

    def test_02_rbac_unauthorized_roles_forbidden(self):
        """Students and unauthenticated users are forbidden from cleanup preview and execution."""
        # 1. Preview by student -> 403
        resp_prev = self.client.get(
            "/placement/cleanup/drives/preview",
            headers=self.student_headers,
        )
        self.assertEqual(resp_prev.status_code, 403)

        # 2. Execute by student -> 403
        resp_exec = self.client.post(
            "/placement/cleanup/execute",
            headers=self.student_headers,
            json={"circular_ids": [1], "mode": "archive"},
        )
        self.assertEqual(resp_exec.status_code, 403)

        # 3. Unauthenticated -> 401
        resp_unauth = self.client.get("/placement/cleanup/drives/preview")
        self.assertEqual(resp_unauth.status_code, 401)

    def test_03_confirmation_phrase_validation(self):
        """Permanent purge requires exact CONFIRM_PURGE_TEST_DATA confirmation phrase."""
        # Missing confirmation phrase
        resp_no_phrase = self.client.post(
            "/placement/cleanup/execute",
            headers=self.officer_headers,
            json={"circular_ids": [999999], "mode": "purge"},
        )
        self.assertEqual(resp_no_phrase.status_code, 400)
        self.assertIn("CONFIRM_PURGE_TEST_DATA", resp_no_phrase.text)

        # Wrong confirmation phrase
        resp_wrong_phrase = self.client.post(
            "/placement/cleanup/execute",
            headers=self.officer_headers,
            json={
                "circular_ids": [999999],
                "mode": "purge",
                "confirmation_phrase": "CONFIRM_DELETE",
            },
        )
        self.assertEqual(resp_wrong_phrase.status_code, 400)
        self.assertIn("CONFIRM_PURGE_TEST_DATA", resp_wrong_phrase.text)

    def test_04_safe_purge_test_drive_and_exclusive_dependencies(self):
        """Purge permanently deletes disposable test drive and exclusive job/attachments in atomic order."""
        sub_ts = int(time.time() * 1000)

        # 1. Create test company
        comp = Company(
            name=f"Mock Test Corp {sub_ts}",
            is_active=True,
        )
        self.db.add(comp)
        self.db.commit()
        self.db.refresh(comp)
        self.created_company_ids.append(comp.id)

        # 2. Create test job
        job = JobPosting(
            company_id=comp.id,
            title=f"Test Role {sub_ts}",
            status=JobStatus.DRAFT,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        self.created_job_ids.append(job.id)

        # 3. Create test circular
        circ = RecruitmentCircular(
            company_id=comp.id,
            title=f"Test Campus Drive {sub_ts}",
            status=RecruitmentCircularStatus.DRAFT,
            created_by=self.officer.id,
        )
        self.db.add(circ)
        self.db.commit()
        self.db.refresh(circ)
        self.created_circular_ids.append(circ.id)

        # 4. Link job to circular
        link = RecruitmentCircularJob(circular_id=circ.id, job_posting_id=job.id)
        self.db.add(link)

        # 5. Add circular attachment file
        f = self._create_synthetic_file(f"test_drive_doc_{sub_ts}.pdf")

        att = RecruitmentCircularAttachment(
            circular_id=circ.id,
            file_id=f.id,
            attachment_type=AttachmentType.OTHER,
        )
        self.db.add(att)

        # 6. Add synthetic application
        app_rec = Application(
            job_posting_id=job.id,
            student_id=self.student.id,
            status=ApplicationStatus.APPLIED,
        )
        self.db.add(app_rec)
        self.db.commit()

        # Save entity IDs before deletion
        job_id = job.id
        circ_id = circ.id
        app_id = app_rec.id
        file_id = f.id

        # Preview drive
        resp_prev = self.client.get(
            f"/placement/cleanup/drives/preview?circular_ids={circ_id}",
            headers=self.officer_headers,
        )
        self.assertEqual(resp_prev.status_code, 200)
        pdata = resp_prev.json()
        self.assertEqual(len(pdata["drives"]), 1)
        self.assertEqual(pdata["drives"][0]["safety_classification"], "SAFE_TO_PURGE")
        self.assertEqual(pdata["drives"][0]["dependent_counts"]["jobs_count"], 1)
        self.assertEqual(pdata["drives"][0]["dependent_counts"]["applications_count"], 1)

        # Purge drive
        resp_purge = self.client.post(
            "/placement/cleanup/execute",
            headers=self.officer_headers,
            json={
                "circular_ids": [circ_id],
                "mode": "purge",
                "confirmation_phrase": "CONFIRM_PURGE_TEST_DATA",
            },
        )
        self.assertEqual(resp_purge.status_code, 200, resp_purge.text)
        res_data = resp_purge.json()
        self.assertEqual(res_data["drives_processed"], 1)
        self.assertIn("records_affected", res_data)

        # Verify circular, job, application, attachment, and file were deleted
        self.assertIsNone(self.db.query(RecruitmentCircular).filter(RecruitmentCircular.id == circ_id).first())
        self.assertIsNone(self.db.query(JobPosting).filter(JobPosting.id == job_id).first())
        self.assertIsNone(self.db.query(Application).filter(Application.id == app_id).first())
        self.assertIsNone(self.db.query(RecruitmentCircularAttachment).filter(RecruitmentCircularAttachment.circular_id == circ_id).first())
        self.assertIsNone(self.db.query(File).filter(File.id == file_id).first())

    def test_05_shared_job_preservation(self):
        """When a job is shared between two drives, purging one drive unlinks the junction but preserves the job."""
        sub_ts = int(time.time() * 1000)

        comp = Company(name=f"Shared Role Corp {sub_ts}", is_active=True)
        self.db.add(comp)
        self.db.commit()
        self.db.refresh(comp)
        self.created_company_ids.append(comp.id)

        shared_job = JobPosting(company_id=comp.id, title=f"Shared Engineer {sub_ts}", status=JobStatus.DRAFT)
        self.db.add(shared_job)
        self.db.commit()
        self.db.refresh(shared_job)
        self.created_job_ids.append(shared_job.id)

        # Drive A (to be purged)
        circ_a = RecruitmentCircular(
            company_id=comp.id,
            title=f"Test Drive A {sub_ts}",
            status=RecruitmentCircularStatus.DRAFT,
            created_by=self.officer.id,
        )
        # Drive B (to be kept)
        circ_b = RecruitmentCircular(
            company_id=comp.id,
            title=f"Keep Drive B {sub_ts}",
            status=RecruitmentCircularStatus.PUBLISHED,
            created_by=self.officer.id,
        )
        self.db.add_all([circ_a, circ_b])
        self.db.commit()
        self.db.refresh(circ_a)
        self.db.refresh(circ_b)
        self.created_circular_ids.extend([circ_a.id, circ_b.id])

        # Link shared_job to both Drive A and Drive B
        link_a = RecruitmentCircularJob(circular_id=circ_a.id, job_posting_id=shared_job.id)
        link_b = RecruitmentCircularJob(circular_id=circ_b.id, job_posting_id=shared_job.id)
        self.db.add_all([link_a, link_b])
        self.db.commit()

        # Preview Drive A: shared_job should be classified as shared
        resp_prev = self.client.get(
            f"/placement/cleanup/drives/preview?circular_ids={circ_a.id}",
            headers=self.officer_headers,
        )
        self.assertEqual(resp_prev.status_code, 200)
        pdata = resp_prev.json()
        self.assertIn(shared_job.title, pdata["drives"][0]["shared_job_roles"])

        # Purge Drive A only
        resp_purge = self.client.post(
            "/placement/cleanup/execute",
            headers=self.officer_headers,
            json={
                "circular_ids": [circ_a.id],
                "mode": "purge",
                "confirmation_phrase": "CONFIRM_PURGE_TEST_DATA",
            },
        )
        self.assertEqual(resp_purge.status_code, 200)

        # Verify Drive A is gone
        self.assertIsNone(self.db.query(RecruitmentCircular).filter(RecruitmentCircular.id == circ_a.id).first())
        # Verify shared_job is STILL PRESENT in database
        refetched_job = self.db.query(JobPosting).filter(JobPosting.id == shared_job.id).first()
        self.assertIsNotNone(refetched_job, "Shared job must NOT be deleted!")
        # Verify Drive B is STILL PRESENT
        refetched_b = self.db.query(RecruitmentCircular).filter(RecruitmentCircular.id == circ_b.id).first()
        self.assertIsNotNone(refetched_b, "Drive B must NOT be deleted!")
        # Verify link to Drive B remains intact
        refetched_link_b = self.db.query(RecruitmentCircularJob).filter(
            RecruitmentCircularJob.circular_id == circ_b.id,
            RecruitmentCircularJob.job_posting_id == shared_job.id,
        ).first()
        self.assertIsNotNone(refetched_link_b)

    def test_06_shared_file_preservation(self):
        """Files referenced by multiple entities (e.g. academic circular) are not deleted when a drive is purged."""
        sub_ts = int(time.time() * 1000)

        comp = Company(name=f"Shared File Corp {sub_ts}", is_active=True)
        self.db.add(comp)
        self.db.commit()
        self.db.refresh(comp)
        self.created_company_ids.append(comp.id)

        circ = RecruitmentCircular(
            company_id=comp.id,
            title=f"Test Drive Shared File {sub_ts}",
            status=RecruitmentCircularStatus.DRAFT,
            created_by=self.officer.id,
        )
        self.db.add(circ)
        self.db.commit()
        self.db.refresh(circ)
        self.created_circular_ids.append(circ.id)

        shared_file = self._create_synthetic_file(f"academic_policy_{sub_ts}.pdf")

        # 1. Attach to recruitment drive
        att = RecruitmentCircularAttachment(
            circular_id=circ.id,
            file_id=shared_file.id,
            attachment_type=AttachmentType.OTHER,
        )
        self.db.add(att)

        # 2. Reference in academic Circular table
        acad_circ = Circular(
            title=f"Academic Policy {sub_ts}",
            content="Academic policy test notice",
            type=CircularType.GENERAL,
            file_id=shared_file.id,
            lecturer_id=self.officer.id,
        )
        self.db.add(acad_circ)
        self.db.commit()

        # Preview: verify shared_files_count == 1
        resp_prev = self.client.get(
            f"/placement/cleanup/drives/preview?circular_ids={circ.id}",
            headers=self.officer_headers,
        )
        self.assertEqual(resp_prev.status_code, 200)
        pdata = resp_prev.json()
        self.assertEqual(pdata["drives"][0]["dependent_counts"]["shared_files_count"], 1)

        # Purge drive
        resp_purge = self.client.post(
            "/placement/cleanup/execute",
            headers=self.officer_headers,
            json={
                "circular_ids": [circ.id],
                "mode": "purge",
                "confirmation_phrase": "CONFIRM_PURGE_TEST_DATA",
            },
        )
        self.assertEqual(resp_purge.status_code, 200)

        # Verify drive is deleted
        self.assertIsNone(self.db.query(RecruitmentCircular).filter(RecruitmentCircular.id == circ.id).first())
        # Verify recruitment circular attachment is deleted
        self.assertIsNone(self.db.query(RecruitmentCircularAttachment).filter(RecruitmentCircularAttachment.circular_id == circ.id).first())
        # Verify File row is PRESERVED!
        refetched_file = self.db.query(File).filter(File.id == shared_file.id).first()
        self.assertIsNotNone(refetched_file, "Shared file must NOT be deleted!")

        # Clean up academic circular
        self.db.delete(acad_circ)
        self.db.commit()

    def test_07_protection_of_genuine_applications_and_accepted_offers(self):
        """Drives with genuine student applications and accepted offers are blocked from purge; archive allowed."""
        code = self.ts % 900 + 100

        comp = Company(name=f"Genuine Prime Org {code}", is_active=True)
        self.db.add(comp)
        self.db.commit()
        self.db.refresh(comp)
        self.created_company_ids.append(comp.id)

        job = JobPosting(company_id=comp.id, title=f"Associate SDE {code}", status=JobStatus.OPEN)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        self.created_job_ids.append(job.id)

        circ = RecruitmentCircular(
            company_id=comp.id,
            title=f"Campus Placement Drive {code}",
            status=RecruitmentCircularStatus.PUBLISHED,
            created_by=self.officer.id,
        )
        self.db.add(circ)
        self.db.commit()
        self.db.refresh(circ)
        self.created_circular_ids.append(circ.id)

        link = RecruitmentCircularJob(circular_id=circ.id, job_posting_id=job.id)
        self.db.add(link)

        # Add genuine student application
        app_rec = Application(
            job_posting_id=job.id,
            student_id=self.genuine_student.id,
            status=ApplicationStatus.SELECTED,
        )
        self.db.add(app_rec)
        self.db.flush()

        # Add accepted placement offer
        offer = PlacementOffer(
            application_id=app_rec.id,
            job_posting_id=job.id,
            student_id=self.genuine_student.id,
            acceptance_status=OfferAcceptanceStatus.ACCEPTED,
            ctc_lpa=12.5,
        )
        self.db.add(offer)
        self.db.commit()

        # Preview: verify PROTECTED_GENUINE
        resp_prev = self.client.get(
            f"/placement/cleanup/drives/preview?circular_ids={circ.id}",
            headers=self.officer_headers,
        )
        self.assertEqual(resp_prev.status_code, 200)
        pdata = resp_prev.json()
        self.assertEqual(pdata["drives"][0]["safety_classification"], "PROTECTED_GENUINE")
        self.assertFalse(pdata["drives"][0]["can_purge"])

        # Attempt to purge -> must fail with HTTP 400
        resp_purge = self.client.post(
            "/placement/cleanup/execute",
            headers=self.officer_headers,
            json={
                "circular_ids": [circ.id],
                "mode": "purge",
                "confirmation_phrase": "CONFIRM_PURGE_TEST_DATA",
            },
        )
        self.assertEqual(resp_purge.status_code, 400)
        self.assertIn("cannot be purged", resp_purge.text)

        # Archive drive -> must SUCCEED safely
        resp_arch = self.client.post(
            "/placement/cleanup/execute",
            headers=self.officer_headers,
            json={
                "circular_ids": [circ.id],
                "mode": "archive",
            },
        )
        self.assertEqual(resp_arch.status_code, 200, resp_arch.text)
        self.assertEqual(resp_arch.json()["drives_processed"], 1)

        # Verify circular is ARCHIVED and job is CLOSED
        self.db.expire_all()
        refetched_circ = self.db.query(RecruitmentCircular).filter(RecruitmentCircular.id == circ.id).first()
        self.assertEqual(refetched_circ.status, RecruitmentCircularStatus.ARCHIVED)
        refetched_job = self.db.query(JobPosting).filter(JobPosting.id == job.id).first()
        self.assertEqual(refetched_job.status, JobStatus.CLOSED)

        # Verify genuine student application & offer PRESERVED
        refetched_app = self.db.query(Application).filter(Application.id == app_rec.id).first()
        self.assertIsNotNone(refetched_app)
        refetched_offer = self.db.query(PlacementOffer).filter(PlacementOffer.id == offer.id).first()
        self.assertIsNotNone(refetched_offer)

    def test_08_mixed_selection_all_or_nothing_validation(self):
        """Mixed batches containing safe and protected drives are rejected atomically without partial deletion."""
        sub_ts = int(time.time() * 1000)

        comp = Company(name=f"Mixed Test Corp {sub_ts}", is_active=True)
        self.db.add(comp)
        self.db.commit()
        self.db.refresh(comp)
        self.created_company_ids.append(comp.id)

        # Drive 1: Safe to purge
        circ_safe = RecruitmentCircular(
            company_id=comp.id,
            title=f"Safe Test Drive {sub_ts}",
            status=RecruitmentCircularStatus.DRAFT,
            created_by=self.officer.id,
        )
        # Drive 2: Protected genuine
        circ_prot = RecruitmentCircular(
            company_id=comp.id,
            title=f"Protected Genuine Drive {sub_ts}",
            status=RecruitmentCircularStatus.PUBLISHED,
            created_by=self.officer.id,
        )
        self.db.add_all([circ_safe, circ_prot])
        self.db.commit()
        self.db.refresh(circ_safe)
        self.db.refresh(circ_prot)
        self.created_circular_ids.extend([circ_safe.id, circ_prot.id])

        job_prot = JobPosting(company_id=comp.id, title=f"Prot Role {sub_ts}", status=JobStatus.OPEN)
        self.db.add(job_prot)
        self.db.commit()
        self.db.refresh(job_prot)
        self.created_job_ids.append(job_prot.id)

        link_prot = RecruitmentCircularJob(circular_id=circ_prot.id, job_posting_id=job_prot.id)
        self.db.add(link_prot)

        app_prot = Application(
            job_posting_id=job_prot.id,
            student_id=self.genuine_student.id,
            status=ApplicationStatus.SELECTED,
        )
        self.db.add(app_prot)
        self.db.flush()

        offer_prot = PlacementOffer(
            application_id=app_prot.id,
            job_posting_id=job_prot.id,
            student_id=self.genuine_student.id,
            acceptance_status=OfferAcceptanceStatus.ACCEPTED,
        )
        self.db.add(offer_prot)
        self.db.commit()

        # Attempt to purge BOTH in one batch
        resp_purge = self.client.post(
            "/placement/cleanup/execute",
            headers=self.officer_headers,
            json={
                "circular_ids": [circ_safe.id, circ_prot.id],
                "mode": "purge",
                "confirmation_phrase": "CONFIRM_PURGE_TEST_DATA",
            },
        )
        # Must be rejected with HTTP 400
        self.assertEqual(resp_purge.status_code, 400)

        # Verify ZERO partial deletion occurred: Safe drive must STILL EXIST
        refetched_safe = self.db.query(RecruitmentCircular).filter(RecruitmentCircular.id == circ_safe.id).first()
        self.assertIsNotNone(refetched_safe, "Safe drive must NOT be partially deleted on batch failure!")

    def test_09_orphaned_jobs_detection_and_cleanup(self):
        """Test-generated jobs unlinked from any circular appear in orphaned_jobs and can be purged."""
        sub_ts = int(time.time() * 1000)

        comp = Company(name=f"Orphan Test Corp {sub_ts}", is_active=True)
        self.db.add(comp)
        self.db.commit()
        self.db.refresh(comp)
        self.created_company_ids.append(comp.id)

        # Job not linked to any circular
        orphan_job = JobPosting(
            company_id=comp.id,
            title=f"Test Orphaned Role {sub_ts}",
            status=JobStatus.DRAFT,
        )
        self.db.add(orphan_job)
        self.db.commit()
        self.db.refresh(orphan_job)
        self.created_job_ids.append(orphan_job.id)

        # Preview: verify job appears in orphaned_jobs
        resp_prev = self.client.get(
            "/placement/cleanup/drives/preview",
            headers=self.officer_headers,
        )
        self.assertEqual(resp_prev.status_code, 200)
        pdata = resp_prev.json()
        orphan_ids = [j["job_id"] for j in pdata["orphaned_jobs"]]
        self.assertIn(orphan_job.id, orphan_ids)

        # Purge orphaned job
        resp_purge = self.client.post(
            "/placement/cleanup/execute",
            headers=self.officer_headers,
            json={
                "orphaned_job_ids": [orphan_job.id],
                "mode": "purge",
                "confirmation_phrase": "CONFIRM_PURGE_TEST_DATA",
            },
        )
        self.assertEqual(resp_purge.status_code, 200)

        # Verify job is deleted
        self.assertIsNone(self.db.query(JobPosting).filter(JobPosting.id == orphan_job.id).first())


if __name__ == "__main__":
    unittest.main()
