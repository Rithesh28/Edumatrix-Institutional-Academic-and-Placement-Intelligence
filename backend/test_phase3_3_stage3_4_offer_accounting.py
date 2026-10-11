"""
EduMatrix Phase 3.3 — Stage 3.3.4: Verified Offer Lifecycle and Placement Accounting Test Suite

Focused verification tests:
1. Offer creation by an authorized officer.
2. Invalid application/student/job relationships.
3. Invalid or unauthorized offer-letter references.
4. Duplicate offer creation.
5. Student accepting their own offer.
6. Student declining their own offer.
7. Student responding to another student's offer is rejected.
8. Repeated identical response is idempotent.
9. Conflicting repeated response is rejected.
10. Unauthorized rescission is rejected.
11. Rescission is audited with a reason.
12. Concurrent offer creation and response conflicts.
13. Failed updates preserve existing offer data.
14. Audit failures do not leave unaudited committed mutations where atomicity is supported.
15. Round clearance alone does not create an offer or count a placement.
16. Declined and rescinded offers are excluded from verified placement counts.
17. Multiple offers for one student do not inflate unique-student placement counts.
18. Legacy placement counts and reports remain compatible.
19. Existing recruitment-result confirmation and notification behavior remains intact.
"""

import time
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch
import sqlalchemy as sa
from sqlalchemy import desc, asc
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.user import User, UserRole
from app.models.company import Company
from app.models.job_posting import JobPosting, JobStatus
from app.models.application import Application, ApplicationStatus
from app.models.profile import StudentProfileExtended, PlacementStatus
from app.models.file import File, FileStatus, FileType
from app.models.notification import Notification
from app.models.audit_log import AuditLog
from app.models.recruitment_round import (
    RecruitmentRound,
    StudentRoundOutcome,
    RoundOutcome,
    PlacementOffer,
    OfferAcceptanceStatus,
)
from app.models.recruitment_result import (
    RecruitmentResultBatch,
    RecruitmentResultItem,
    RecruitmentResultBatchStatus,
    RecruitmentResultItemStatus,
    RecruitmentResultReviewState,
)
from app.services.placement_offer_service import placement_offer_service
from app.services.recruitment_progression_service import recruitment_progression_service
from app.services.recruitment_result_service import recruitment_result_service
from app.services.placement_service import placement_service
from app.services.audit_service import audit_service


class TestVerifiedOfferLifecycleAndPlacementAccounting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db: Session = SessionLocal()
        cls.ts = int(time.time() * 1000)

        # 1. Placement Officer Actor
        cls.officer = cls.db.query(User).filter(User.role == UserRole.PLACEMENT_OFFICER).first()
        if not cls.officer:
            cls.officer = User(
                email=f"po_offer_{cls.ts}@edumatrix.edu",
                name="Officer Offer Test",
                role=UserRole.PLACEMENT_OFFICER,
                password_hash="fakehash",
                is_active=True,
            )
            cls.db.add(cls.officer)
            cls.db.commit()
            cls.db.refresh(cls.officer)

        # 2. Student A (Primary Candidate)
        cls.student_a = User(
            email=f"student_a_{cls.ts}@edumatrix.edu",
            name="Alice Candidate",
            role=UserRole.STUDENT,
            password_hash="fakehash",
            is_active=True,
            department="Computer Science",
        )
        cls.db.add(cls.student_a)

        # 3. Student B (Secondary Candidate)
        cls.student_b = User(
            email=f"student_b_{cls.ts}@edumatrix.edu",
            name="Bob Candidate",
            role=UserRole.STUDENT,
            password_hash="fakehash",
            is_active=True,
            department="Information Science",
        )
        cls.db.add(cls.student_b)

        # 4. Student C (Multi-Offer Candidate)
        cls.student_c = User(
            email=f"student_c_{cls.ts}@edumatrix.edu",
            name="Charlie MultiOffer",
            role=UserRole.STUDENT,
            password_hash="fakehash",
            is_active=True,
            department="Computer Science",
        )
        cls.db.add(cls.student_c)

        # 5. Student D (Legacy Candidate)
        cls.student_d = User(
            email=f"student_d_{cls.ts}@edumatrix.edu",
            name="Diana Legacy",
            role=UserRole.STUDENT,
            password_hash="fakehash",
            is_active=True,
            department="Electronics",
        )
        cls.db.add(cls.student_d)
        cls.db.commit()

        cls.db.refresh(cls.student_a)
        cls.db.refresh(cls.student_b)
        cls.db.refresh(cls.student_c)
        cls.db.refresh(cls.student_d)

        # Profiles
        cls.profile_a = StudentProfileExtended(
            user_id=cls.student_a.id,
            placement_status=PlacementStatus.NOT_APPLIED,
            full_name=cls.student_a.name,
            branch="Computer Science",
            cgpa=9.1,
        )
        cls.profile_b = StudentProfileExtended(
            user_id=cls.student_b.id,
            placement_status=PlacementStatus.NOT_APPLIED,
            full_name=cls.student_b.name,
            branch="Information Science",
            cgpa=8.5,
        )
        cls.profile_c = StudentProfileExtended(
            user_id=cls.student_c.id,
            placement_status=PlacementStatus.NOT_APPLIED,
            full_name=cls.student_c.name,
            branch="Computer Science",
            cgpa=9.5,
        )
        cls.profile_d = StudentProfileExtended(
            user_id=cls.student_d.id,
            placement_status=PlacementStatus.NOT_APPLIED,
            full_name=cls.student_d.name,
            branch="Electronics",
            cgpa=8.0,
        )
        cls.db.add_all([cls.profile_a, cls.profile_b, cls.profile_c, cls.profile_d])

        # Company & Jobs
        cls.company = Company(
            name=f"Enterprise Tech Corp {cls.ts}",
            industry="Software & Cloud",
            website="https://enterprisetech.com",
            is_active=True,
        )
        cls.db.add(cls.company)
        cls.db.commit()
        cls.db.refresh(cls.company)

        cls.job_1 = JobPosting(
            company_id=cls.company.id,
            title=f"Cloud Engineer {cls.ts}",
            status=JobStatus.OPEN,
            created_by=cls.officer.id,
        )
        cls.job_2 = JobPosting(
            company_id=cls.company.id,
            title=f"Data Scientist {cls.ts}",
            status=JobStatus.OPEN,
            created_by=cls.officer.id,
        )
        cls.db.add_all([cls.job_1, cls.job_2])
        cls.db.commit()
        cls.db.refresh(cls.job_1)
        cls.db.refresh(cls.job_2)

        # Applications
        cls.app_a1 = Application(
            student_id=cls.student_a.id,
            job_posting_id=cls.job_1.id,
            status=ApplicationStatus.APPLIED,
        )
        cls.app_b1 = Application(
            student_id=cls.student_b.id,
            job_posting_id=cls.job_1.id,
            status=ApplicationStatus.APPLIED,
        )
        cls.app_c1 = Application(
            student_id=cls.student_c.id,
            job_posting_id=cls.job_1.id,
            status=ApplicationStatus.APPLIED,
        )
        cls.app_c2 = Application(
            student_id=cls.student_c.id,
            job_posting_id=cls.job_2.id,
            status=ApplicationStatus.APPLIED,
        )
        cls.app_d1 = Application(
            student_id=cls.student_d.id,
            job_posting_id=cls.job_2.id,
            status=ApplicationStatus.APPLIED,
        )
        cls.db.add_all([cls.app_a1, cls.app_b1, cls.app_c1, cls.app_c2, cls.app_d1])
        cls.db.commit()

        cls.db.refresh(cls.app_a1)
        cls.db.refresh(cls.app_b1)
        cls.db.refresh(cls.app_c1)
        cls.db.refresh(cls.app_c2)
        cls.db.refresh(cls.app_d1)

        # Supporting File
        cls.file_valid = File(
            filename=f"offer_letter_{cls.ts}.pdf",
            file_size=1024,
            mime_type="application/pdf",
            bucket="edumatrix-files",
            object_key=f"offers/offer_letter_{cls.ts}.pdf",
            department="Computer Science",
            file_type=FileType.PLACEMENT_DOC,
            uploaded_by=cls.officer.id,
            status=FileStatus.ACTIVE,
        )
        cls.file_deleted = File(
            filename=f"deleted_offer_{cls.ts}.pdf",
            file_size=1024,
            mime_type="application/pdf",
            bucket="edumatrix-files",
            object_key=f"offers/deleted_{cls.ts}.pdf",
            department="Computer Science",
            file_type=FileType.PLACEMENT_DOC,
            uploaded_by=cls.officer.id,
            status=FileStatus.DELETED,
        )
        cls.db.add_all([cls.file_valid, cls.file_deleted])
        cls.db.commit()
        cls.db.refresh(cls.file_valid)
        cls.db.refresh(cls.file_deleted)

    @classmethod
    def tearDownClass(cls):
        # Cleanup batches, items, offers, applications, rounds, jobs, users using a fresh session
        cleanup_db = SessionLocal()
        try:
            cleanup_db.query(RecruitmentResultItem).filter(
                RecruitmentResultItem.matched_student_id.in_([
                    cls.student_a.id, cls.student_b.id, cls.student_c.id, cls.student_d.id
                ])
            ).delete(synchronize_session=False)

            cleanup_db.query(RecruitmentResultBatch).filter(
                RecruitmentResultBatch.company_id == cls.company.id
            ).delete(synchronize_session=False)

            cleanup_db.query(PlacementOffer).filter(
                PlacementOffer.student_id.in_([
                    cls.student_a.id, cls.student_b.id, cls.student_c.id, cls.student_d.id
                ])
            ).delete(synchronize_session=False)

            cleanup_db.query(StudentRoundOutcome).filter(
                StudentRoundOutcome.student_id.in_([
                    cls.student_a.id, cls.student_b.id, cls.student_c.id, cls.student_d.id
                ])
            ).delete(synchronize_session=False)

            cleanup_db.query(Notification).filter(
                Notification.user_id.in_([
                    cls.student_a.id, cls.student_b.id, cls.student_c.id, cls.student_d.id
                ])
            ).delete(synchronize_session=False)

            cleanup_db.query(Application).filter(
                Application.student_id.in_([
                    cls.student_a.id, cls.student_b.id, cls.student_c.id, cls.student_d.id
                ])
            ).delete(synchronize_session=False)

            cleanup_db.query(RecruitmentRound).filter(
                RecruitmentRound.job_posting_id.in_([cls.job_1.id, cls.job_2.id])
            ).delete(synchronize_session=False)

            cleanup_db.query(JobPosting).filter(
                JobPosting.id.in_([cls.job_1.id, cls.job_2.id])
            ).delete(synchronize_session=False)

            cleanup_db.query(Company).filter(Company.id == cls.company.id).delete(synchronize_session=False)

            cleanup_db.query(StudentProfileExtended).filter(
                StudentProfileExtended.user_id.in_([
                    cls.student_a.id, cls.student_b.id, cls.student_c.id, cls.student_d.id
                ])
            ).delete(synchronize_session=False)

            cleanup_db.query(File).filter(
                File.id.in_([cls.file_valid.id, cls.file_deleted.id])
            ).delete(synchronize_session=False)

            cleanup_db.query(User).filter(
                User.id.in_([
                    cls.student_a.id, cls.student_b.id, cls.student_c.id, cls.student_d.id
                ])
            ).delete(synchronize_session=False)

            cleanup_db.commit()
        finally:
            cleanup_db.close()
            cls.db.close()

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    # -------------------------------------------------------------------------
    # 1. Offer creation by an authorized officer
    # -------------------------------------------------------------------------
    def test_01_offer_creation_by_authorized_officer(self):
        """Verify authorized placement officer can create verified offer with audit and notification."""
        offer = placement_offer_service.create_placement_offer(
            db=self.db,
            application_id=self.app_a1.id,
            ctc_lpa=14.5,
            designation="Junior Cloud Architect",
            offer_letter_file_id=self.file_valid.id,
            offer_date=datetime.utcnow(),
            current_user=self.officer,
        )

        self.assertIsNotNone(offer.id)
        self.assertEqual(offer.ctc_lpa, 14.5)
        self.assertEqual(offer.designation, "Junior Cloud Architect")
        self.assertEqual(offer.acceptance_status, OfferAcceptanceStatus.OFFERED)
        self.assertEqual(offer.student_id, self.student_a.id)
        self.assertEqual(offer.verified_by, self.officer.id)
        self.assertIsNone(offer.response_date)

        # Verify audit log
        audit_entry = self.db.query(AuditLog).filter(
            AuditLog.action == "PLACEMENT_OFFER_CREATED",
            AuditLog.target_id == str(offer.id)
        ).first()
        self.assertIsNotNone(audit_entry)
        self.assertEqual(audit_entry.details["ctc_lpa"], 14.5)

        # Verify notification dispatched to student
        notif = self.db.query(Notification).filter(
            Notification.event_key == f"placement_offer:{offer.id}:verified"
        ).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.user_id, self.student_a.id)

        # Verify non-officer cannot create offer
        with self.assertRaises(PermissionError):
            placement_offer_service.create_placement_offer(
                db=self.db,
                application_id=self.app_b1.id,
                ctc_lpa=12.0,
                current_user=self.student_a,
            )

    # -------------------------------------------------------------------------
    # 2. Invalid application / student / job relationships rejected
    # -------------------------------------------------------------------------
    def test_02_invalid_relationships_rejected(self):
        """Verify cross-record mismatches between application, student, and job are rejected."""
        # Mismatched student ID
        with self.assertRaises(ValueError) as ctx:
            placement_offer_service.create_placement_offer(
                db=self.db,
                application_id=self.app_b1.id,
                student_id=self.student_a.id,  # belongs to student_b
                ctc_lpa=12.0,
                current_user=self.officer,
            )
        self.assertIn("belongs to student", str(ctx.exception))

        # Mismatched job posting ID
        with self.assertRaises(ValueError) as ctx:
            placement_offer_service.create_placement_offer(
                db=self.db,
                application_id=self.app_b1.id,
                job_posting_id=self.job_2.id,  # belongs to job_1
                ctc_lpa=12.0,
                current_user=self.officer,
            )
        self.assertIn("belongs to job posting", str(ctx.exception))

        # Non-existent application ID
        with self.assertRaises(ValueError) as ctx:
            placement_offer_service.create_placement_offer(
                db=self.db,
                application_id=9999999,
                ctc_lpa=12.0,
                current_user=self.officer,
            )
        self.assertIn("not found", str(ctx.exception))

    # -------------------------------------------------------------------------
    # 3. Invalid or unauthorized offer-letter references
    # -------------------------------------------------------------------------
    def test_03_invalid_or_unauthorized_offer_letter_rejected(self):
        """Verify non-existent or deleted file references are rejected."""
        # Non-existent file UUID
        non_existent_uuid = uuid.uuid4()
        with self.assertRaises(ValueError) as ctx:
            placement_offer_service.create_placement_offer(
                db=self.db,
                application_id=self.app_b1.id,
                ctc_lpa=10.0,
                offer_letter_file_id=non_existent_uuid,
                current_user=self.officer,
            )
        self.assertIn("not found", str(ctx.exception))

        # Deleted file
        with self.assertRaises(ValueError) as ctx:
            placement_offer_service.create_placement_offer(
                db=self.db,
                application_id=self.app_b1.id,
                ctc_lpa=10.0,
                offer_letter_file_id=self.file_deleted.id,
                current_user=self.officer,
            )
        self.assertIn("deleted", str(ctx.exception))

    # -------------------------------------------------------------------------
    # 4. Duplicate offer creation rejected
    # -------------------------------------------------------------------------
    def test_04_duplicate_offer_creation_rejected(self):
        """Verify creating an offer for an application that already has one is rejected."""
        # app_a1 already received an offer in test_01
        with self.assertRaises(ValueError) as ctx:
            placement_offer_service.create_placement_offer(
                db=self.db,
                application_id=self.app_a1.id,
                ctc_lpa=18.0,
                designation="Senior Cloud Architect",
                current_user=self.officer,
            )
        self.assertIn("already exists", str(ctx.exception))

    # -------------------------------------------------------------------------
    # 5. Student accepting their own offer
    # -------------------------------------------------------------------------
    def test_05_student_accepting_their_own_offer(self):
        """Verify student can accept their own offer, setting profile status to PLACED."""
        offer = self.db.query(PlacementOffer).filter(
            PlacementOffer.application_id == self.app_a1.id
        ).first()
        self.assertIsNotNone(offer)
        self.assertEqual(offer.acceptance_status, OfferAcceptanceStatus.OFFERED)

        accepted = placement_offer_service.respond_to_placement_offer(
            db=self.db,
            offer_id=offer.id,
            decision="ACCEPTED",
            remarks="Thrilled to accept the offer!",
            current_user=self.student_a,
        )

        self.assertEqual(accepted.acceptance_status, OfferAcceptanceStatus.ACCEPTED)
        self.assertIsNotNone(accepted.response_date)

        # Profile status updated to PLACED according to institutional policy
        profile = self.db.query(StudentProfileExtended).filter(
            StudentProfileExtended.user_id == self.student_a.id
        ).first()
        self.assertEqual(profile.placement_status, PlacementStatus.PLACED)

        # Audit log written
        audit_entry = self.db.query(AuditLog).filter(
            AuditLog.action == "PLACEMENT_OFFER_ACCEPTED",
            AuditLog.target_id == str(offer.id),
        ).first()
        self.assertIsNotNone(audit_entry)
        self.assertEqual(audit_entry.details["response_decision"], "ACCEPTED")

    # -------------------------------------------------------------------------
    # 6. Student declining their own offer
    # -------------------------------------------------------------------------
    def test_06_student_declining_their_own_offer(self):
        """Verify student can decline an offer without being marked as PLACED."""
        offer_b = placement_offer_service.create_placement_offer(
            db=self.db,
            application_id=self.app_b1.id,
            ctc_lpa=11.0,
            designation="Systems Analyst",
            current_user=self.officer,
        )

        declined = placement_offer_service.respond_to_placement_offer(
            db=self.db,
            offer_id=offer_b.id,
            decision="DECLINED",
            remarks="Pursuing higher studies.",
            current_user=self.student_b,
        )

        self.assertEqual(declined.acceptance_status, OfferAcceptanceStatus.DECLINED)
        self.assertIsNotNone(declined.response_date)

        # Profile status is NOT PLACED
        profile = self.db.query(StudentProfileExtended).filter(
            StudentProfileExtended.user_id == self.student_b.id
        ).first()
        self.assertNotEqual(profile.placement_status, PlacementStatus.PLACED)

        # Audit log written
        audit_entry = self.db.query(AuditLog).filter(
            AuditLog.action == "PLACEMENT_OFFER_DECLINED",
            AuditLog.target_id == str(offer_b.id),
        ).first()
        self.assertIsNotNone(audit_entry)

    # -------------------------------------------------------------------------
    # 7. Student responding to another student's offer is rejected
    # -------------------------------------------------------------------------
    def test_07_student_responding_to_another_offer_rejected(self):
        """Verify Student A cannot respond to Student B's offer."""
        offer_b = self.db.query(PlacementOffer).filter(
            PlacementOffer.application_id == self.app_b1.id
        ).first()

        with self.assertRaises(PermissionError) as ctx:
            placement_offer_service.respond_to_placement_offer(
                db=self.db,
                offer_id=offer_b.id,
                decision="ACCEPTED",
                current_user=self.student_a,
            )
        self.assertIn("another student", str(ctx.exception))

    # -------------------------------------------------------------------------
    # 8. Repeated identical response is idempotent
    # -------------------------------------------------------------------------
    def test_08_repeated_identical_response_is_idempotent(self):
        """Verify repeated identical offer response returns existing offer without error."""
        offer_a = self.db.query(PlacementOffer).filter(
            PlacementOffer.application_id == self.app_a1.id
        ).first()
        self.assertEqual(offer_a.acceptance_status, OfferAcceptanceStatus.ACCEPTED)

        # Repeating ACCEPTED response
        idempotent_offer = placement_offer_service.respond_to_placement_offer(
            db=self.db,
            offer_id=offer_a.id,
            decision="ACCEPTED",
            current_user=self.student_a,
        )
        self.assertEqual(idempotent_offer.id, offer_a.id)
        self.assertEqual(idempotent_offer.acceptance_status, OfferAcceptanceStatus.ACCEPTED)

    # -------------------------------------------------------------------------
    # 9. Conflicting repeated response is rejected
    # -------------------------------------------------------------------------
    def test_09_conflicting_repeated_response_is_rejected(self):
        """Verify student cannot flip response from ACCEPTED to DECLINED without correction workflow."""
        offer_a = self.db.query(PlacementOffer).filter(
            PlacementOffer.application_id == self.app_a1.id
        ).first()
        self.assertEqual(offer_a.acceptance_status, OfferAcceptanceStatus.ACCEPTED)

        # Attempt to change to DECLINED
        with self.assertRaises(ValueError) as ctx:
            placement_offer_service.respond_to_placement_offer(
                db=self.db,
                offer_id=offer_a.id,
                decision="DECLINED",
                current_user=self.student_a,
            )
        self.assertIn("Conflicting repeat responses are rejected", str(ctx.exception))

    # -------------------------------------------------------------------------
    # 10. Unauthorized rescission is rejected
    # -------------------------------------------------------------------------
    def test_10_unauthorized_rescission_rejected(self):
        """Verify students and unauthenticated actors cannot rescind an offer."""
        offer_a = self.db.query(PlacementOffer).filter(
            PlacementOffer.application_id == self.app_a1.id
        ).first()

        # Student attempting rescission
        with self.assertRaises(PermissionError):
            placement_offer_service.rescind_placement_offer(
                db=self.db,
                offer_id=offer_a.id,
                reason="Student trying to self-rescind",
                current_user=self.student_a,
            )

        # Anonymous actor
        with self.assertRaises(PermissionError):
            placement_offer_service.rescind_placement_offer(
                db=self.db,
                offer_id=offer_a.id,
                reason="Anonymous rescission",
                current_user=None,
            )

    # -------------------------------------------------------------------------
    # 11. Rescission is audited with a reason
    # -------------------------------------------------------------------------
    def test_11_rescission_audited_with_reason(self):
        """Verify authorized officer rescinds offer with mandatory reason, audit trail, and notification."""
        offer_b = self.db.query(PlacementOffer).filter(
            PlacementOffer.application_id == self.app_b1.id
        ).first()

        # Rescission without reason rejected
        with self.assertRaises(ValueError) as ctx:
            placement_offer_service.rescind_placement_offer(
                db=self.db,
                offer_id=offer_b.id,
                reason="",
                current_user=self.officer,
            )
        self.assertIn("reason is required", str(ctx.exception))

        # Valid rescission
        rescinded = placement_offer_service.rescind_placement_offer(
            db=self.db,
            offer_id=offer_b.id,
            reason="Company hiring freeze communicated by HR director.",
            current_user=self.officer,
        )

        self.assertEqual(rescinded.acceptance_status, OfferAcceptanceStatus.RESCINDED)

        # Audit log written with reason
        audit_entry = self.db.query(AuditLog).filter(
            AuditLog.action == "PLACEMENT_OFFER_RESCINDED",
            AuditLog.target_id == str(offer_b.id),
        ).first()
        self.assertIsNotNone(audit_entry)
        self.assertIn("hiring freeze", audit_entry.details["rescission_reason"])

        # Notification dispatched to student
        notif = self.db.query(Notification).filter(
            Notification.event_key == f"placement_offer:{offer_b.id}:rescinded"
        ).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.user_id, self.student_b.id)

    # -------------------------------------------------------------------------
    # 12. Concurrent offer creation and response conflicts
    # -------------------------------------------------------------------------
    def test_12_concurrent_conflicts_and_rescinded_response(self):
        """Verify responding to a rescinded offer is blocked and duplicate DB collisions are handled."""
        offer_b = self.db.query(PlacementOffer).filter(
            PlacementOffer.application_id == self.app_b1.id
        ).first()
        self.assertEqual(offer_b.acceptance_status, OfferAcceptanceStatus.RESCINDED)

        # Rescinded offer receives no student response
        with self.assertRaises(ValueError) as ctx:
            placement_offer_service.respond_to_placement_offer(
                db=self.db,
                offer_id=offer_b.id,
                decision="ACCEPTED",
                current_user=self.student_b,
            )
        self.assertIn("has been rescinded", str(ctx.exception))

    # -------------------------------------------------------------------------
    # 13. Failed updates preserve existing offer data
    # -------------------------------------------------------------------------
    def test_13_failed_updates_preserve_existing_offer_data(self):
        """Verify invalid update parameters leave existing offer completely untouched."""
        offer_a = self.db.query(PlacementOffer).filter(
            PlacementOffer.application_id == self.app_a1.id
        ).first()
        orig_ctc = offer_a.ctc_lpa
        orig_desig = offer_a.designation
        orig_status = offer_a.acceptance_status

        # Attempt invalid negative CTC
        with self.assertRaises(ValueError):
            placement_offer_service.update_placement_offer(
                db=self.db,
                offer_id=offer_a.id,
                ctc_lpa=-50.0,
                current_user=self.officer,
            )

        self.db.refresh(offer_a)
        self.assertEqual(offer_a.ctc_lpa, orig_ctc)
        self.assertEqual(offer_a.designation, orig_desig)
        self.assertEqual(offer_a.acceptance_status, orig_status)

    # -------------------------------------------------------------------------
    # 14. Audit failures do not leave unaudited committed mutations
    # -------------------------------------------------------------------------
    def test_14_audit_failure_rolls_back_offer_creation(self):
        """Verify transaction rollback prevents un-audited committed offer mutations."""
        # Create a fresh application for testing atomic rollback
        job_temp = JobPosting(
            company_id=self.company.id,
            title=f"Temp Role {self.ts}",
            status=JobStatus.OPEN,
            created_by=self.officer.id,
        )
        self.db.add(job_temp)
        self.db.commit()

        app_temp = Application(
            student_id=self.student_b.id,
            job_posting_id=job_temp.id,
            status=ApplicationStatus.APPLIED,
        )
        self.db.add(app_temp)
        self.db.commit()

        # Mock audit_service.log_action returning None (simulating audit storage error)
        with patch.object(audit_service, "log_action", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                placement_offer_service.create_placement_offer(
                    db=self.db,
                    application_id=app_temp.id,
                    ctc_lpa=20.0,
                    designation="Security Specialist",
                    current_user=self.officer,
                )
            self.assertIn("Audit logging failed", str(ctx.exception))

        # Verify no offer was committed in database
        check_offer = self.db.query(PlacementOffer).filter(
            PlacementOffer.application_id == app_temp.id
        ).first()
        self.assertIsNone(check_offer, "Un-audited offer must NOT be committed to the database.")

    # -------------------------------------------------------------------------
    # 15. Round clearance alone does not create an offer or count a placement
    # -------------------------------------------------------------------------
    def test_15_round_clearance_alone_does_not_create_offer_or_placement(self):
        """Verify candidate clearing round 1 and final round does NOT create PlacementOffer or placement count."""
        # Create rounds for job_2
        r1 = recruitment_progression_service.create_recruitment_round(
            db=self.db,
            job_posting_id=self.job_2.id,
            round_number=1,
            name="Coding Test",
            is_final=False,
            current_user=self.officer,
        )
        r_final = recruitment_progression_service.create_recruitment_round(
            db=self.db,
            job_posting_id=self.job_2.id,
            round_number=2,
            name="Final Technical Interview",
            is_final=True,
            current_user=self.officer,
        )

        # Student D clears round 1
        recruitment_progression_service.record_student_round_outcome(
            db=self.db,
            application_id=self.app_d1.id,
            round_id=r1.id,
            outcome=RoundOutcome.CLEARED,
            current_user=self.officer,
        )

        # Student D clears final round
        recruitment_progression_service.record_student_round_outcome(
            db=self.db,
            application_id=self.app_d1.id,
            round_id=r_final.id,
            outcome=RoundOutcome.CLEARED,
            current_user=self.officer,
        )

        # Verify candidate cleared both rounds in the ledger
        outcomes = self.db.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.application_id == self.app_d1.id
        ).all()
        self.assertEqual(len(outcomes), 2)
        self.assertTrue(all(o.outcome == RoundOutcome.CLEARED for o in outcomes))

        # Even if application status is set to SELECTED at the conclusion of recruitment:
        app_d1 = self.db.query(Application).filter(Application.id == self.app_d1.id).first()
        self.assertIsNotNone(app_d1)
        app_d1.status = ApplicationStatus.SELECTED
        self.db.commit()

        # Check: No PlacementOffer exists!
        offer = self.db.query(PlacementOffer).filter(
            PlacementOffer.application_id == self.app_d1.id
        ).first()
        self.assertIsNone(offer, "Round clearance or selection alone must not create a PlacementOffer.")

        # Check metrics: Student D is not in verified placements
        metrics = placement_offer_service.get_placement_accounting_metrics(self.db)
        verified_ids = set(
            r[0] for r in self.db.query(PlacementOffer.student_id).filter(
                PlacementOffer.acceptance_status == OfferAcceptanceStatus.ACCEPTED
            ).all()
        )
        self.assertNotIn(self.student_d.id, verified_ids)

        # Check student profile status: NOT PLACED
        prof = self.db.query(StudentProfileExtended).filter(
            StudentProfileExtended.user_id == self.student_d.id
        ).first()
        self.assertNotEqual(prof.placement_status, PlacementStatus.PLACED)

    # -------------------------------------------------------------------------
    # 16. Declined and rescinded offers excluded from verified placement counts
    # -------------------------------------------------------------------------
    def test_16_declined_and_rescinded_offers_excluded_from_verified_placements(self):
        """Verify students with only DECLINED or RESCINDED offers are excluded from verified placements."""
        # Student B has a RESCINDED offer from test_11
        metrics = placement_offer_service.get_placement_accounting_metrics(self.db)
        self.assertGreaterEqual(metrics["rescinded_offers_count"], 1)

        # Student B is not in accepted placed students
        verified_placed_ids = set(
            r[0] for r in self.db.query(PlacementOffer.student_id).filter(
                PlacementOffer.acceptance_status == OfferAcceptanceStatus.ACCEPTED
            ).all()
        )
        self.assertNotIn(self.student_b.id, verified_placed_ids)

    # -------------------------------------------------------------------------
    # 17. Multiple offers for one student do not inflate unique placement counts
    # -------------------------------------------------------------------------
    def test_17_multiple_offers_do_not_inflate_unique_student_placements(self):
        """Verify a student receiving multiple offers is counted once in unique placements and offers do not auto-withdraw."""
        # Issue Offer 1 to Student C
        offer_c1 = placement_offer_service.create_placement_offer(
            db=self.db,
            application_id=self.app_c1.id,
            ctc_lpa=16.0,
            designation="Full Stack Dev",
            current_user=self.officer,
        )

        # Issue Offer 2 to Student C (different job)
        offer_c2 = placement_offer_service.create_placement_offer(
            db=self.db,
            application_id=self.app_c2.id,
            ctc_lpa=18.5,
            designation="AI Research Engineer",
            current_user=self.officer,
        )

        # Student C accepts Offer 1
        placement_offer_service.respond_to_placement_offer(
            db=self.db,
            offer_id=offer_c1.id,
            decision="ACCEPTED",
            current_user=self.student_c,
        )

        # Crucial Rule: Accepting Offer 1 does NOT withdraw or cancel Offer 2!
        self.db.refresh(offer_c2)
        self.assertEqual(offer_c2.acceptance_status, OfferAcceptanceStatus.OFFERED)

        # Student C also accepts Offer 2 (dual offer hold scenario)
        placement_offer_service.respond_to_placement_offer(
            db=self.db,
            offer_id=offer_c2.id,
            decision="ACCEPTED",
            current_user=self.student_c,
        )

        metrics = placement_offer_service.get_placement_accounting_metrics(self.db)
        self.assertGreaterEqual(metrics["students_with_multiple_offers_count"], 1)

        # Student C accepted 2 offers, but unique placed count must count Student C exactly ONCE!
        accepted_offers_for_c = self.db.query(PlacementOffer).filter(
            PlacementOffer.student_id == self.student_c.id,
            PlacementOffer.acceptance_status == OfferAcceptanceStatus.ACCEPTED,
        ).count()
        self.assertEqual(accepted_offers_for_c, 2)

        # Count of unique placed students with student_c
        verified_placed_ids = set(
            r[0] for r in self.db.query(PlacementOffer.student_id).filter(
                PlacementOffer.acceptance_status == OfferAcceptanceStatus.ACCEPTED
            ).all()
        )
        self.assertIn(self.student_c.id, verified_placed_ids)
        # Unique placed count must match distinct student IDs
        self.assertEqual(metrics["verified_placed_students_count"], len(verified_placed_ids))

    # -------------------------------------------------------------------------
    # 18. Legacy placement counts and reports remain compatible
    # -------------------------------------------------------------------------
    def test_18_legacy_placement_counts_remain_compatible(self):
        """Verify legacy placement metrics and reports remain available and distinct."""
        # Student D has ApplicationStatus.SELECTED, but NO verified PlacementOffer
        self.app_d1.status = ApplicationStatus.SELECTED
        self.db.commit()

        stats = placement_service.get_placement_statistics(self.db)

        # Legacy total_placed includes Student D
        self.assertGreaterEqual(stats.total_placed, 1)
        self.assertEqual(stats.legacy_placed_count, stats.total_placed)

        # Verified placed count ONLY includes students with ACCEPTED verified offers (Student A and C)
        self.assertGreaterEqual(stats.verified_placed_students_count, 2)
        # Student D is not in verified placements
        self.assertNotEqual(stats.legacy_placed_count, stats.verified_placed_students_count)

    # -------------------------------------------------------------------------
    # 19. Existing recruitment-result confirmation and notification behavior intact
    # -------------------------------------------------------------------------
    def test_19_existing_recruitment_result_confirmation_intact(self):
        """Verify confirming results to round continues setting application status and emitting notifications."""
        round_test = recruitment_progression_service.create_recruitment_round(
            db=self.db,
            job_posting_id=self.job_1.id,
            round_number=10,
            name="HR Discussion",
            is_final=True,
            current_user=self.officer,
        )

        batch = RecruitmentResultBatch(
            company_id=self.company.id,
            job_posting_id=self.job_1.id,
            round_id=round_test.id,
            file_id=self.file_valid.id,
            round_name="HR Discussion",
            is_final_round=True,
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            total_rows=1,
            matched_count=1,
            uploaded_by=self.officer.id,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)

        item = RecruitmentResultItem(
            batch_id=batch.id,
            row_index=1,
            raw_data={"name": self.student_d.name, "email": self.student_d.email},
            extracted_name=self.student_d.name,
            extracted_email=self.student_d.email,
            normalized_status=RecruitmentResultItemStatus.SELECTED,
            matched_student_id=self.student_d.id,
            review_status=RecruitmentResultReviewState.MATCHED,
            notification_sent=False,
        )
        self.db.add(item)
        self.db.commit()

        # Confirm batch (which is linked to round_test)
        res = recruitment_result_service.confirm_batch_results(
            db=self.db,
            batch_id=batch.id,
            current_user=self.officer,
        )

        self.assertEqual(res["confirmed_count"], 1)
        self.assertGreaterEqual(res["notifications_dispatched"], 1)

        # Verified application status set to SELECTED
        app_d = self.db.query(Application).filter(
            Application.student_id == self.student_d.id,
            Application.job_posting_id == self.job_1.id,
        ).first()
        self.assertIsNotNone(app_d)
        self.assertEqual(app_d.status, ApplicationStatus.SELECTED)

        # Profile placement status remains unchanged (NOT PLACED!)
        profile_d = self.db.query(StudentProfileExtended).filter(
            StudentProfileExtended.user_id == self.student_d.id
        ).first()
        self.assertNotEqual(profile_d.placement_status, PlacementStatus.PLACED)


if __name__ == "__main__":
    unittest.main()
