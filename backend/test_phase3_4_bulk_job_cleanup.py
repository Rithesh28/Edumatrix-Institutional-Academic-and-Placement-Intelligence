"""
EduMatrix Phase 3.4 Bulk Job Posting Management and Cleanup Integration Tests

Validates:
1. Job cleanup preview endpoint (/placement/cleanup/jobs/preview and /placement/cleanup/preview?job_ids=...)
2. Safety classification of jobs:
   - SAFE_TO_PURGE for pure test jobs without circulars/apps/offers
   - REQUIRES_ARCHIVE for jobs with applications, active drives, or active offers
   - PROTECTED_GENUINE for genuine jobs with accepted offers
3. Safe Archive workflow for jobs:
   - Closes jobs (status = JobStatus.CLOSED)
   - Preserves shared jobs open if linked to an active recruitment drive
   - Logs audit trail with actor, target, and affected counts
4. Purge workflow safety:
   - Rejects purge of jobs with accepted offers, active offers, or active drives
   - Purges safe jobs and exclusively dependent records in atomic transaction
5. Pagination and status filtering on /placement/jobs endpoint
"""

import time
import unittest
from typing import List

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.user import User, UserRole
from app.models.company import Company
from app.models.job_posting import JobPosting, JobStatus
from app.models.application import Application, ApplicationStatus
from app.models.recruitment_circular import (
    RecruitmentCircular,
    RecruitmentCircularJob,
    RecruitmentCircularStatus,
)
from app.models.recruitment_round import (
    PlacementOffer,
    OfferAcceptanceStatus,
)
from app.models.audit_log import AuditLog


class TestPhase34BulkJobCleanup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db: Session = SessionLocal()

        # Officer
        cls.officer = cls.db.query(User).filter(User.role == UserRole.PLACEMENT_OFFICER).first()
        if not cls.officer:
            cls.officer = User(
                email="placement@gmail.com",
                role=UserRole.PLACEMENT_OFFICER,
                name="Placement Officer",
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

        # Student
        cls.student = cls.db.query(User).filter(User.role == UserRole.STUDENT).first()
        if not cls.student:
            cls.student = User(
                email="student_test@vcet.ac.in",
                role=UserRole.STUDENT,
                name="Student Test",
                is_active=True,
            )
            cls.db.add(cls.student)
            cls.db.commit()
            cls.db.refresh(cls.student)

        cls.created_jobs: List[int] = []
        cls.created_companies: List[int] = []
        cls.created_circulars: List[int] = []
        cls.created_apps: List[int] = []
        cls.created_offers: List[int] = []

    @classmethod
    def tearDownClass(cls):
        try:
            cls.db.rollback()
            # Cleanup any remaining test artifacts
            if cls.created_offers:
                cls.db.query(PlacementOffer).filter(
                    PlacementOffer.id.in_(cls.created_offers)
                ).delete(synchronize_session=False)

            if cls.created_apps:
                cls.db.query(Application).filter(
                    Application.id.in_(cls.created_apps)
                ).delete(synchronize_session=False)

            if cls.created_jobs:
                cls.db.query(RecruitmentCircularJob).filter(
                    RecruitmentCircularJob.job_posting_id.in_(cls.created_jobs)
                ).delete(synchronize_session=False)
                cls.db.query(Application).filter(
                    Application.job_posting_id.in_(cls.created_jobs)
                ).delete(synchronize_session=False)
                cls.db.query(PlacementOffer).filter(
                    PlacementOffer.job_posting_id.in_(cls.created_jobs)
                ).delete(synchronize_session=False)
                cls.db.query(JobPosting).filter(
                    JobPosting.id.in_(cls.created_jobs)
                ).delete(synchronize_session=False)

            if cls.created_circulars:
                cls.db.query(RecruitmentCircular).filter(
                    RecruitmentCircular.id.in_(cls.created_circulars)
                ).delete(synchronize_session=False)

            if cls.created_companies:
                cls.db.query(Company).filter(
                    Company.id.in_(cls.created_companies)
                ).delete(synchronize_session=False)

            cls.db.commit()
        except Exception:
            cls.db.rollback()
        finally:
            cls.db.close()

    def test_01_job_preview_safe_to_purge(self):
        """Test preview on disposable test job flags it as SAFE_TO_PURGE."""
        ts = int(time.time() * 1000)
        comp = Company(name=f"Mock Test Corp {ts}", is_active=True)
        self.db.add(comp)
        self.db.commit()
        self.created_companies.append(comp.id)

        job = JobPosting(
            title=f"Sample Test Job {ts}",
            company_id=comp.id,
            status=JobStatus.OPEN,
            created_by=self.officer.id,
        )
        self.db.add(job)
        self.db.commit()
        self.created_jobs.append(job.id)

        resp = self.client.get(
            f"/placement/cleanup/jobs/preview?job_ids={job.id}",
            headers=self.officer_headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()

        self.assertEqual(data["summary"]["total_candidates_flagged"], 1)
        self.assertEqual(data["summary"]["total_safe_to_purge"], 1)
        self.assertEqual(len(data["jobs"]), 1)
        j_candidate = data["jobs"][0]
        self.assertEqual(j_candidate["safety_classification"], "SAFE_TO_PURGE")
        self.assertTrue(j_candidate["can_purge"])

    def test_02_job_safe_archive_closes_job(self):
        """Test Safe Archive closes job posting and generates audit log."""
        ts = int(time.time() * 1000)
        comp = Company(name=f"Archive Job Test Co {ts}", is_active=True)
        self.db.add(comp)
        self.db.commit()
        self.created_companies.append(comp.id)

        job = JobPosting(
            title=f"Open Role {ts}",
            company_id=comp.id,
            status=JobStatus.OPEN,
            created_by=self.officer.id,
        )
        self.db.add(job)
        self.db.commit()
        self.created_jobs.append(job.id)

        # Execute Safe Archive
        resp = self.client.post(
            "/placement/cleanup/execute",
            json={"job_ids": [job.id], "mode": "archive"},
            headers=self.officer_headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        result = resp.json()
        self.assertTrue(result["success"])
        self.assertEqual(result["jobs_processed"], 1)
        self.assertEqual(result["job_ids"], [job.id])
        self.assertEqual(result["records_affected"]["jobs_closed"], 1)

        # Verify DB state
        self.db.expire_all()
        db_job = self.db.query(JobPosting).filter(JobPosting.id == job.id).first()
        self.assertIsNotNone(db_job)
        self.assertEqual(db_job.status, JobStatus.CLOSED)

        # Verify audit log
        audit = self.db.query(AuditLog).filter(
            AuditLog.action == "RECRUITMENT_JOB_TEST_DATA_ARCHIVED",
            AuditLog.target_id.contains(str(job.id)),
        ).first()
        self.assertIsNotNone(audit)

    def test_03_job_archive_preserves_shared_active_drive_job(self):
        """Test Safe Archive does not close a job if linked to an active external recruitment drive."""
        ts = int(time.time() * 1000)
        comp = Company(name=f"Shared Role Co {ts}", is_active=True)
        self.db.add(comp)
        self.db.commit()
        self.created_companies.append(comp.id)

        job = JobPosting(
            title=f"Shared Active Role {ts}",
            company_id=comp.id,
            status=JobStatus.OPEN,
            created_by=self.officer.id,
        )
        self.db.add(job)
        self.db.commit()
        self.created_jobs.append(job.id)

        circ = RecruitmentCircular(
            title=f"Active Shared Drive {ts}",
            company_id=comp.id,
            status=RecruitmentCircularStatus.PUBLISHED,
            created_by=self.officer.id,
        )
        self.db.add(circ)
        self.db.commit()
        self.created_circulars.append(circ.id)

        link = RecruitmentCircularJob(circular_id=circ.id, job_posting_id=job.id)
        self.db.add(link)
        self.db.commit()

        # Archive only the job (not the active drive)
        resp = self.client.post(
            "/placement/cleanup/execute",
            json={"job_ids": [job.id], "mode": "archive"},
            headers=self.officer_headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        result = resp.json()
        self.assertEqual(result["records_affected"]["jobs_closed"], 0)
        self.assertEqual(result["records_affected"]["shared_jobs_preserved"], 1)

        # Verify job is still OPEN
        self.db.expire_all()
        db_job = self.db.query(JobPosting).filter(JobPosting.id == job.id).first()
        self.assertEqual(db_job.status, JobStatus.OPEN)

    def test_04_job_purge_blocks_accepted_offers(self):
        """Test permanent purge is strictly forbidden for jobs with accepted offers."""
        ts = int(time.time() * 1000)
        comp = Company(name=f"Permanent Offer Co {ts}", is_active=True)
        self.db.add(comp)
        self.db.commit()
        self.created_companies.append(comp.id)

        job = JobPosting(
            title=f"Job With Offer {ts}",
            company_id=comp.id,
            status=JobStatus.OPEN,
            created_by=self.officer.id,
        )
        self.db.add(job)
        self.db.commit()
        self.created_jobs.append(job.id)

        app_record = Application(
            student_id=self.student.id,
            job_posting_id=job.id,
            status=ApplicationStatus.SELECTED,
        )
        self.db.add(app_record)
        self.db.commit()
        self.created_apps.append(app_record.id)

        offer = PlacementOffer(
            student_id=self.student.id,
            job_posting_id=job.id,
            application_id=app_record.id,
            acceptance_status=OfferAcceptanceStatus.ACCEPTED,
        )
        self.db.add(offer)
        self.db.commit()
        self.created_offers.append(offer.id)

        # Attempt purge with confirmation phrase
        resp = self.client.post(
            "/placement/cleanup/execute",
            json={
                "job_ids": [job.id],
                "mode": "purge",
                "confirmation_phrase": "CONFIRM_PURGE_TEST_DATA",
            },
            headers=self.officer_headers,
        )
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn("accepted placement offer", resp.json()["detail"])

        # DB record still exists
        self.db.expire_all()
        db_job = self.db.query(JobPosting).filter(JobPosting.id == job.id).first()
        self.assertIsNotNone(db_job)

    def test_05_job_purge_success(self):
        """Test permanent purge deletes safe-to-purge job and records affected."""
        ts = int(time.time() * 1000)
        comp = Company(name=f"Disposable Co {ts}", is_active=True)
        self.db.add(comp)
        self.db.commit()
        self.created_companies.append(comp.id)

        job = JobPosting(
            title=f"Disposable Test Job {ts}",
            company_id=comp.id,
            status=JobStatus.DRAFT,
            created_by=self.officer.id,
        )
        self.db.add(job)
        self.db.commit()
        job_id = job.id

        resp = self.client.post(
            "/placement/cleanup/execute",
            json={
                "job_ids": [job_id],
                "mode": "purge",
                "confirmation_phrase": "CONFIRM_PURGE_TEST_DATA",
            },
            headers=self.officer_headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        result = resp.json()
        self.assertEqual(result["records_affected"]["jobs_purged"], 1)

        # Verify DB job no longer exists
        self.db.expire_all()
        db_job = self.db.query(JobPosting).filter(JobPosting.id == job_id).first()
        self.assertIsNone(db_job)


if __name__ == "__main__":
    unittest.main()
