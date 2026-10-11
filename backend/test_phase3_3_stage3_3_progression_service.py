"""
EduMatrix Phase 3.3 — Stage 3.3.2: Recruitment Progression Service Test Suite

Tests:
1. Valid round creation and retrieval.
2. Duplicate round number rejected for the same job.
3. Same round number allowed for different jobs.
4. Cross-job round/application mismatch rejected.
5. Inactive student outcome rejected.
6. Source batch belonging to another job rejected.
7. Source item belonging to another student/batch rejected.
8. Duplicate outcome processing handled safely (idempotent if identical, error if changed).
9. Older or conflicting batch cannot silently regress a confirmed outcome.
10. Correction without a reason rejected.
11. Correction preserves before/after values and audit details in AuditLog.
12. Unauthorized corrections rejected (PermissionError).
13. Invalid offer application combination rejected.
14. Invalid CTC values (<= 0) rejected.
15. Existing offers are updated with audit logging rather than silent overwrite.
16. Legacy batches with null round IDs remain fully functional and reported.
17. Existing Application and profile placement statuses remain untouched by progression service.
18. Chronological student progression retrieval returns complete round history.
19. Recruitment integrity health check accurately reports round/batch summary.
"""

import time
import unittest
from datetime import datetime, timezone
import sqlalchemy as sa
from sqlalchemy import desc, asc
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.user import User, UserRole
from app.models.company import Company
from app.models.job_posting import JobPosting, JobStatus
from app.models.application import Application, ApplicationStatus
from app.models.profile import StudentProfileExtended, PlacementStatus
from app.models.file import File
from app.models.audit_log import AuditLog
from app.models.recruitment_result import (
    RecruitmentResultBatch,
    RecruitmentResultItem,
    RecruitmentResultBatchStatus,
    RecruitmentResultItemStatus,
    RecruitmentResultReviewState,
)
from app.models.recruitment_round import (
    RecruitmentRound,
    StudentRoundOutcome,
    RoundOutcome,
    PlacementOffer,
    OfferAcceptanceStatus,
)
from app.services.recruitment_progression_service import recruitment_progression_service


class TestRecruitmentProgressionService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db: Session = SessionLocal()
        cls.ts = int(time.time() * 1000)

        # 1. Placement Officer Actor
        cls.officer = cls.db.query(User).filter(User.role == UserRole.PLACEMENT_OFFICER).first()
        if not cls.officer:
            cls.officer = User(
                email=f"po_service_{cls.ts}@edumatrix.edu",
                name="Officer Service Test",
                role=UserRole.PLACEMENT_OFFICER,
                password_hash="fakehash",
                is_active=True,
            )
            cls.db.add(cls.officer)
            cls.db.commit()
            cls.db.refresh(cls.officer)

        # 2. Unauthorized Student Actor
        cls.unauthorized_student = User(
            email=f"unauth_{cls.ts}@edumatrix.edu",
            name="Unauthorized Student",
            role=UserRole.STUDENT,
            password_hash="fakehash",
            is_active=True,
        )
        cls.db.add(cls.unauthorized_student)

        # 3. Target Student for Recruitment
        cls.student = User(
            email=f"candidate_{cls.ts}@edumatrix.edu",
            name="Candidate Student",
            role=UserRole.STUDENT,
            password_hash="fakehash",
            is_active=True,
        )
        cls.db.add(cls.student)
        cls.db.commit()
        cls.db.refresh(cls.student)

        # Student Profile
        cls.profile = StudentProfileExtended(
            user_id=cls.student.id,
            placement_status=PlacementStatus.NOT_APPLIED,
            full_name=cls.student.name,
        )
        cls.db.add(cls.profile)

        # 4. Inactive Student for Validation Testing
        cls.inactive_student = User(
            email=f"inactive_{cls.ts}@edumatrix.edu",
            name="Inactive Student",
            role=UserRole.STUDENT,
            password_hash="fakehash",
            is_active=False,
        )
        cls.db.add(cls.inactive_student)
        cls.db.commit()
        cls.db.refresh(cls.inactive_student)

        # 5. Companies & Jobs
        cls.company_a = Company(
            name=f"Progression Alpha Corp {cls.ts}",
            industry="Cloud Computing",
            location="Bangalore",
            is_active=True,
        )
        cls.company_b = Company(
            name=f"Progression Beta Labs {cls.ts}",
            industry="Data Analytics",
            location="Hyderabad",
            is_active=True,
        )
        cls.db.add_all([cls.company_a, cls.company_b])
        cls.db.commit()
        cls.db.refresh(cls.company_a)
        cls.db.refresh(cls.company_b)

        cls.job_a = JobPosting(
            company_id=cls.company_a.id,
            title=f"Cloud Specialist {cls.ts}",
            status=JobStatus.OPEN,
        )
        cls.job_b = JobPosting(
            company_id=cls.company_b.id,
            title=f"Data Specialist {cls.ts}",
            status=JobStatus.OPEN,
        )
        cls.db.add_all([cls.job_a, cls.job_b])
        cls.db.commit()
        cls.db.refresh(cls.job_a)
        cls.db.refresh(cls.job_b)

        # 6. Applications
        cls.app_a = Application(
            student_id=cls.student.id,
            job_posting_id=cls.job_a.id,
            status=ApplicationStatus.APPLIED,
            notes="Initial Application A",
        )
        cls.app_b = Application(
            student_id=cls.student.id,
            job_posting_id=cls.job_b.id,
            status=ApplicationStatus.APPLIED,
            notes="Initial Application B",
        )
        cls.app_inactive = Application(
            student_id=cls.inactive_student.id,
            job_posting_id=cls.job_a.id,
            status=ApplicationStatus.APPLIED,
            notes="Inactive student application",
        )
        cls.db.add_all([cls.app_a, cls.app_b, cls.app_inactive])
        cls.db.commit()
        cls.db.refresh(cls.app_a)
        cls.db.refresh(cls.app_b)
        cls.db.refresh(cls.app_inactive)

        # 7. Sample File for Batches/Offers
        cls.sample_file = cls.db.query(File).first()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.db.rollback()
            if hasattr(cls, "company_a") and cls.company_a.id:
                cls.db.query(JobPosting).filter(JobPosting.company_id == cls.company_a.id).delete(synchronize_session=False)
                cls.db.query(Company).filter(Company.id == cls.company_a.id).delete(synchronize_session=False)
            if hasattr(cls, "company_b") and cls.company_b.id:
                cls.db.query(JobPosting).filter(JobPosting.company_id == cls.company_b.id).delete(synchronize_session=False)
                cls.db.query(Company).filter(Company.id == cls.company_b.id).delete(synchronize_session=False)
            cls.db.commit()
        except Exception:
            cls.db.rollback()
        finally:
            cls.db.close()

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    # -------------------------------------------------------------------------
    # 1. Round Creation & Retrieval
    # -------------------------------------------------------------------------
    def test_01_valid_round_creation_and_retrieval(self):
        """Verify creating rounds and retrieving them in sequence."""
        r1 = recruitment_progression_service.create_recruitment_round(
            db=self.db,
            job_posting_id=self.job_a.id,
            round_number=1,
            name="Online Aptitude & Coding",
            round_type="assessment",
            is_final=False,
            current_user=self.officer,
        )
        r2 = recruitment_progression_service.create_recruitment_round(
            db=self.db,
            job_posting_id=self.job_a.id,
            round_number=2,
            name="Technical System Design",
            round_type="technical_interview",
            is_final=False,
            current_user=self.officer,
        )
        r3 = recruitment_progression_service.create_recruitment_round(
            db=self.db,
            job_posting_id=self.job_a.id,
            round_number=3,
            name="Director HR & Final Offer",
            round_type="hr_interview",
            is_final=True,
            current_user=self.officer,
        )

        rounds = recruitment_progression_service.get_job_rounds(self.db, self.job_a.id)
        self.assertEqual(len(rounds), 3)
        self.assertEqual([r.round_number for r in rounds], [1, 2, 3])
        self.assertEqual(rounds[0].name, "Online Aptitude & Coding")
        self.assertFalse(rounds[0].is_final)
        self.assertTrue(rounds[2].is_final)

    # -------------------------------------------------------------------------
    # 2. Duplicate Round Number Rejected for Same Job
    # -------------------------------------------------------------------------
    def test_02_duplicate_round_number_rejected_same_job(self):
        """Verify creating a duplicate round_number for the same job raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            recruitment_progression_service.create_recruitment_round(
                db=self.db,
                job_posting_id=self.job_a.id,
                round_number=1,
                name="Duplicate Round 1",
                current_user=self.officer,
            )
        self.assertIn("already exists", str(ctx.exception))

    # -------------------------------------------------------------------------
    # 3. Same Round Number Allowed for Different Jobs
    # -------------------------------------------------------------------------
    def test_03_same_round_number_allowed_different_jobs(self):
        """Verify different jobs can each have Round 1 without conflict."""
        round_b1 = recruitment_progression_service.create_recruitment_round(
            db=self.db,
            job_posting_id=self.job_b.id,
            round_number=1,
            name="Job B Screening",
            current_user=self.officer,
        )
        self.assertIsNotNone(round_b1.id)
        self.assertEqual(round_b1.job_posting_id, self.job_b.id)

    # -------------------------------------------------------------------------
    # 4. Cross-Job Round / Application Mismatch Rejected
    # -------------------------------------------------------------------------
    def test_04_cross_job_round_application_mismatch_rejected(self):
        """Verify outcome cannot be recorded if application and round belong to different jobs."""
        round_a1 = self.db.query(RecruitmentRound).filter(
            RecruitmentRound.job_posting_id == self.job_a.id,
            RecruitmentRound.round_number == 1
        ).first()

        # app_b belongs to job_b, but round_a1 belongs to job_a
        with self.assertRaises(ValueError) as ctx:
            recruitment_progression_service.record_student_round_outcome(
                db=self.db,
                application_id=self.app_b.id,
                round_id=round_a1.id,
                outcome=RoundOutcome.CLEARED,
                current_user=self.officer,
            )
        self.assertIn("Cross-job outcomes are prohibited", str(ctx.exception))

    # -------------------------------------------------------------------------
    # 5. Inactive Student Rejected
    # -------------------------------------------------------------------------
    def test_05_inactive_student_rejected(self):
        """Verify outcome cannot be recorded for an inactive student."""
        round_a1 = self.db.query(RecruitmentRound).filter(
            RecruitmentRound.job_posting_id == self.job_a.id,
            RecruitmentRound.round_number == 1
        ).first()

        with self.assertRaises(ValueError) as ctx:
            recruitment_progression_service.record_student_round_outcome(
                db=self.db,
                application_id=self.app_inactive.id,
                round_id=round_a1.id,
                outcome=RoundOutcome.CLEARED,
                current_user=self.officer,
            )
        self.assertIn("is inactive", str(ctx.exception))

    # -------------------------------------------------------------------------
    # 6. Source Batch Belonging to Another Job Rejected
    # -------------------------------------------------------------------------
    def test_06_source_batch_belonging_to_another_job_rejected(self):
        """Verify source batch must belong to the exact same job as the round."""
        round_a1 = self.db.query(RecruitmentRound).filter(
            RecruitmentRound.job_posting_id == self.job_a.id,
            RecruitmentRound.round_number == 1
        ).first()

        # Create batch pointing to Job B
        batch_b = RecruitmentResultBatch(
            company_id=self.company_b.id,
            job_posting_id=self.job_b.id,
            file_id=self.sample_file.id,
            round_name="Job B Test Batch",
            status=RecruitmentResultBatchStatus.IN_REVIEW,
        )
        self.db.add(batch_b)
        self.db.commit()

        # Attempt linking batch_b to round_a1
        with self.assertRaises(ValueError) as ctx:
            recruitment_progression_service.link_batch_to_round(
                db=self.db,
                batch_id=batch_b.id,
                round_id=round_a1.id,
                current_user=self.officer,
            )
        self.assertIn("Cross-job linking is prohibited", str(ctx.exception))

        # Attempt recording outcome on Round A with Batch B
        with self.assertRaises(ValueError) as ctx2:
            recruitment_progression_service.record_student_round_outcome(
                db=self.db,
                application_id=self.app_a.id,
                round_id=round_a1.id,
                outcome=RoundOutcome.CLEARED,
                source_batch_id=batch_b.id,
                current_user=self.officer,
            )
        self.assertIn("Source batch", str(ctx2.exception))

    # -------------------------------------------------------------------------
    # 7. Source Item Student Mismatch Rejected
    # -------------------------------------------------------------------------
    def test_07_source_item_student_mismatch_rejected(self):
        """Verify source result item must be matched to the same student as the application."""
        round_a1 = self.db.query(RecruitmentRound).filter(
            RecruitmentRound.job_posting_id == self.job_a.id,
            RecruitmentRound.round_number == 1
        ).first()

        batch_a = RecruitmentResultBatch(
            company_id=self.company_a.id,
            job_posting_id=self.job_a.id,
            file_id=self.sample_file.id,
            round_name="Batch A",
            status=RecruitmentResultBatchStatus.IN_REVIEW,
        )
        self.db.add(batch_a)
        self.db.commit()

        # Item matched to a different student (unauthorized_student)
        item_other = RecruitmentResultItem(
            batch_id=batch_a.id,
            row_index=1,
            raw_data={"name": "Someone Else"},
            matched_student_id=self.unauthorized_student.id,
            review_status=RecruitmentResultReviewState.MATCHED,
        )
        self.db.add(item_other)
        self.db.commit()

        with self.assertRaises(ValueError) as ctx:
            recruitment_progression_service.record_student_round_outcome(
                db=self.db,
                application_id=self.app_a.id,  # belongs to cls.student
                round_id=round_a1.id,
                outcome=RoundOutcome.CLEARED,
                source_batch_id=batch_a.id,
                source_item_id=item_other.id,
                current_user=self.officer,
            )
        self.assertIn("matched student", str(ctx.exception))

    # -------------------------------------------------------------------------
    # 8. Duplicate Outcome Processing Handled Safely
    # -------------------------------------------------------------------------
    def test_08_duplicate_outcome_processing_idempotent_or_guarded(self):
        """Verify recording exact same outcome is idempotent, while differing outcome raises error."""
        round_a1 = self.db.query(RecruitmentRound).filter(
            RecruitmentRound.job_posting_id == self.job_a.id,
            RecruitmentRound.round_number == 1
        ).first()

        outcome1 = recruitment_progression_service.record_student_round_outcome(
            db=self.db,
            application_id=self.app_a.id,
            round_id=round_a1.id,
            outcome=RoundOutcome.CLEARED,
            score=92.5,
            remarks="Passed OA with distinction",
            current_user=self.officer,
        )
        self.assertEqual(outcome1.outcome, RoundOutcome.CLEARED)

        # Idempotent re-execution with identical data
        outcome2 = recruitment_progression_service.record_student_round_outcome(
            db=self.db,
            application_id=self.app_a.id,
            round_id=round_a1.id,
            outcome=RoundOutcome.CLEARED,
            score=92.5,
            current_user=self.officer,
        )
        self.assertEqual(outcome1.id, outcome2.id)

        # Conflicting re-execution with different outcome without correction workflow
        with self.assertRaises(ValueError) as ctx:
            recruitment_progression_service.record_student_round_outcome(
                db=self.db,
                application_id=self.app_a.id,
                round_id=round_a1.id,
                outcome=RoundOutcome.REJECTED,
                current_user=self.officer,
            )
        self.assertIn("already exists", str(ctx.exception))
        self.assertIn("use correct_student_round_outcome", str(ctx.exception))

    # -------------------------------------------------------------------------
    # 9. Conflicting Batch Cannot Regress Confirmed Outcome
    # -------------------------------------------------------------------------
    def test_09_older_or_conflicting_batch_cannot_silently_regress_outcome(self):
        """Verify an authoritative CLEARED outcome cannot be overwritten silently by a later upload."""
        round_a1 = self.db.query(RecruitmentRound).filter(
            RecruitmentRound.job_posting_id == self.job_a.id,
            RecruitmentRound.round_number == 1
        ).first()

        outcome = db_outcome = self.db.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.application_id == self.app_a.id,
            StudentRoundOutcome.round_id == round_a1.id
        ).first()
        self.assertEqual(outcome.outcome, RoundOutcome.CLEARED)

        # Attempting silent regression
        with self.assertRaises(ValueError):
            recruitment_progression_service.record_student_round_outcome(
                db=self.db,
                application_id=self.app_a.id,
                round_id=round_a1.id,
                outcome=RoundOutcome.REJECTED,
                current_user=self.officer,
            )

        # Outcome in DB is still CLEARED
        self.db.refresh(outcome)
        self.assertEqual(outcome.outcome, RoundOutcome.CLEARED)

    # -------------------------------------------------------------------------
    # 10. Correction Without Reason Rejected
    # -------------------------------------------------------------------------
    def test_10_correction_without_reason_rejected(self):
        """Verify correction requires a non-empty audit reason."""
        round_a1 = self.db.query(RecruitmentRound).filter(
            RecruitmentRound.job_posting_id == self.job_a.id,
            RecruitmentRound.round_number == 1
        ).first()
        outcome = self.db.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.application_id == self.app_a.id,
            StudentRoundOutcome.round_id == round_a1.id
        ).first()

        with self.assertRaises(ValueError) as ctx:
            recruitment_progression_service.correct_student_round_outcome(
                db=self.db,
                outcome_id=outcome.id,
                new_outcome=RoundOutcome.REJECTED,
                reason="",  # Empty reason
                current_user=self.officer,
            )
        self.assertIn("correction reason is mandatory", str(ctx.exception))

    # -------------------------------------------------------------------------
    # 11. Correction Preserves Before/After and Audit Details
    # -------------------------------------------------------------------------
    def test_11_correction_preserves_before_after_values_and_audit(self):
        """Verify audited correction atomically updates outcome and logs complete diff to AuditLog."""
        round_a1 = self.db.query(RecruitmentRound).filter(
            RecruitmentRound.job_posting_id == self.job_a.id,
            RecruitmentRound.round_number == 1
        ).first()
        outcome = self.db.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.application_id == self.app_a.id,
            StudentRoundOutcome.round_id == round_a1.id
        ).first()

        old_score = outcome.score
        audit_reason = "Re-evaluation after technical coding score moderation dispute"

        corrected = recruitment_progression_service.correct_student_round_outcome(
            db=self.db,
            outcome_id=outcome.id,
            new_outcome=RoundOutcome.OFFERED,
            reason=audit_reason,
            new_score=97.0,
            new_remarks="Upgraded after dispute resolution",
            current_user=self.officer,
        )

        self.assertEqual(corrected.outcome, RoundOutcome.OFFERED)
        self.assertEqual(corrected.score, 97.0)

        # Inspect AuditLog entry
        log_entry = self.db.query(AuditLog).filter(
            AuditLog.action == "STUDENT_ROUND_OUTCOME_CORRECTED",
            AuditLog.target_id == str(outcome.id)
        ).order_by(desc(AuditLog.id)).first()

        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.actor_id, self.officer.id)
        details = log_entry.details
        self.assertEqual(details["previous_outcome"], "cleared")
        self.assertEqual(details["new_outcome"], "offered")
        self.assertEqual(details["previous_score"], old_score)
        self.assertEqual(details["new_score"], 97.0)
        self.assertEqual(details["correction_reason"], audit_reason)

    # -------------------------------------------------------------------------
    # 12. Unauthorized Corrections Rejected
    # -------------------------------------------------------------------------
    def test_12_unauthorized_corrections_rejected(self):
        """Verify student or unauthenticated actor cannot perform outcome corrections."""
        round_a1 = self.db.query(RecruitmentRound).filter(
            RecruitmentRound.job_posting_id == self.job_a.id,
            RecruitmentRound.round_number == 1
        ).first()
        outcome = self.db.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.application_id == self.app_a.id,
            StudentRoundOutcome.round_id == round_a1.id
        ).first()

        with self.assertRaises(PermissionError):
            recruitment_progression_service.correct_student_round_outcome(
                db=self.db,
                outcome_id=outcome.id,
                new_outcome=RoundOutcome.CLEARED,
                reason="Student trying to alter own outcome",
                current_user=self.unauthorized_student,
            )

    # -------------------------------------------------------------------------
    # 13. Invalid Offer Combinations Rejected
    # -------------------------------------------------------------------------
    def test_13_invalid_offer_application_combinations_rejected(self):
        """Verify offer cannot be created for a non-existent application."""
        with self.assertRaises(ValueError) as ctx:
            recruitment_progression_service.create_or_update_placement_offer(
                db=self.db,
                application_id=99999999,
                ctc_lpa=12.0,
                current_user=self.officer,
            )
        self.assertIn("not found", str(ctx.exception))

    # -------------------------------------------------------------------------
    # 14. Invalid CTC Values Rejected
    # -------------------------------------------------------------------------
    def test_14_invalid_ctc_values_rejected(self):
        """Verify CTC <= 0 raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            recruitment_progression_service.create_or_update_placement_offer(
                db=self.db,
                application_id=self.app_a.id,
                ctc_lpa=-1.0,
                current_user=self.officer,
            )
        self.assertIn("positive number", str(ctx.exception))

        with self.assertRaises(ValueError):
            recruitment_progression_service.create_or_update_placement_offer(
                db=self.db,
                application_id=self.app_a.id,
                ctc_lpa=0.0,
                current_user=self.officer,
            )

    # -------------------------------------------------------------------------
    # 15. Offer Foundations and Audit Trail
    # -------------------------------------------------------------------------
    def test_15_offer_creation_and_audited_update(self):
        """Verify PlacementOffer creation and subsequent update are logged in AuditLog."""
        offer = recruitment_progression_service.create_or_update_placement_offer(
            db=self.db,
            application_id=self.app_a.id,
            ctc_lpa=15.0,
            designation="Junior Cloud Architect",
            acceptance_status=OfferAcceptanceStatus.OFFERED,
            current_user=self.officer,
        )
        self.assertEqual(offer.ctc_lpa, 15.0)
        self.assertEqual(offer.designation, "Junior Cloud Architect")
        self.assertEqual(offer.acceptance_status, OfferAcceptanceStatus.OFFERED)

        # Update offer
        updated_offer = recruitment_progression_service.create_or_update_placement_offer(
            db=self.db,
            application_id=self.app_a.id,
            ctc_lpa=17.5,
            designation="Associate Cloud Architect",
            reason="Offer package renegotiated with employer",
            current_user=self.officer,
        )
        self.assertEqual(updated_offer.id, offer.id)
        self.assertEqual(updated_offer.ctc_lpa, 17.5)
        self.assertEqual(updated_offer.designation, "Associate Cloud Architect")

        # Verify audit log for offer update
        log_entry = self.db.query(AuditLog).filter(
            AuditLog.action == "PLACEMENT_OFFER_UPDATED",
            AuditLog.target_id == str(offer.id)
        ).order_by(desc(AuditLog.id)).first()

        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.details["previous_ctc_lpa"], 15.0)
        self.assertEqual(log_entry.details["new_ctc_lpa"], 17.5)

    # -------------------------------------------------------------------------
    # 16. Legacy Batches With Null Round ID Still Work
    # -------------------------------------------------------------------------
    def test_16_legacy_batches_null_round_id_still_work(self):
        """Verify batches with round_id=None are cleanly supported and reported."""
        legacy_batch = RecruitmentResultBatch(
            company_id=self.company_a.id,
            job_posting_id=self.job_a.id,
            file_id=self.sample_file.id,
            round_name="Legacy Unlinked Batch",
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            round_id=None,
        )
        self.db.add(legacy_batch)
        self.db.commit()

        health = recruitment_progression_service.validate_recruitment_integrity(
            db=self.db,
            job_posting_id=self.job_a.id
        )
        self.assertEqual(health["status"], "HEALTHY")
        self.assertGreaterEqual(health["unlinked_legacy_batches_count"], 1)

    # -------------------------------------------------------------------------
    # 17. Application and Profile Statuses Untouched
    # -------------------------------------------------------------------------
    def test_17_application_and_profile_statuses_remain_untouched(self):
        """Verify progression outcomes do NOT mutate Application.status or StudentProfileExtended."""
        app = self.db.query(Application).filter(Application.id == self.app_a.id).first()
        # Original status was APPLIED and notes was "Initial Application A"
        self.assertEqual(app.status, ApplicationStatus.APPLIED)
        self.assertEqual(app.notes, "Initial Application A")

        profile = self.db.query(StudentProfileExtended).filter(
            StudentProfileExtended.user_id == self.student.id
        ).first()
        self.assertEqual(profile.placement_status, PlacementStatus.NOT_APPLIED)

    # -------------------------------------------------------------------------
    # 18. Student Progression Timeline Retrieval
    # -------------------------------------------------------------------------
    def test_18_student_progression_timeline_retrieval(self):
        """Verify get_student_progression returns structured chronological history."""
        # Record outcome for Round 2 as well
        round_a2 = self.db.query(RecruitmentRound).filter(
            RecruitmentRound.job_posting_id == self.job_a.id,
            RecruitmentRound.round_number == 2
        ).first()

        recruitment_progression_service.record_student_round_outcome(
            db=self.db,
            application_id=self.app_a.id,
            round_id=round_a2.id,
            outcome=RoundOutcome.CLEARED,
            score=89.0,
            remarks="Excellent problem solving",
            current_user=self.officer,
        )

        progression = recruitment_progression_service.get_student_progression(
            db=self.db,
            student_id=self.student.id,
            job_posting_id=self.job_a.id
        )

        self.assertGreaterEqual(len(progression), 2)
        # Check ordering: round 1 followed by round 2
        round_numbers = [p["round_number"] for p in progression]
        self.assertEqual(round_numbers[:2], [1, 2])
        self.assertTrue(progression[0]["has_offer"])
        self.assertEqual(progression[0]["offer_ctc_lpa"], 17.5)

    # -------------------------------------------------------------------------
    # 19. Concurrent Duplicate Outcomes (Race Condition)
    # -------------------------------------------------------------------------
    def test_19_concurrent_identical_outcomes_race_condition(self):
        """Verify two simultaneous requests recording the identical outcome cleanly resolve to single record."""
        from concurrent.futures import ThreadPoolExecutor

        round_a3 = self.db.query(RecruitmentRound).filter(
            RecruitmentRound.job_posting_id == self.job_a.id,
            RecruitmentRound.round_number == 3
        ).first()

        def record_worker():
            worker_db = SessionLocal()
            try:
                outcome = recruitment_progression_service.record_student_round_outcome(
                    db=worker_db,
                    application_id=self.app_a.id,
                    round_id=round_a3.id,
                    outcome=RoundOutcome.OFFERED,
                    score=95.0,
                    remarks="Concurrent identical outcome",
                    current_user=self.officer,
                )
                return outcome.id
            finally:
                worker_db.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(record_worker)
            f2 = executor.submit(record_worker)
            res1 = f1.result()
            res2 = f2.result()

        # Both workers return the same record ID cleanly
        self.assertEqual(res1, res2)

        # In database, exactly 1 row exists
        count = self.db.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.application_id == self.app_a.id,
            StudentRoundOutcome.round_id == round_a3.id
        ).count()
        self.assertEqual(count, 1)

    # -------------------------------------------------------------------------
    # 20. Concurrent Conflicting Outcomes (Race Condition)
    # -------------------------------------------------------------------------
    def test_20_concurrent_conflicting_outcomes_race_condition(self):
        """Verify two simultaneous requests recording conflicting outcomes allow only one winner and controlled error."""
        from concurrent.futures import ThreadPoolExecutor

        round_b1 = self.db.query(RecruitmentRound).filter(
            RecruitmentRound.job_posting_id == self.job_b.id,
            RecruitmentRound.round_number == 1
        ).first()

        def worker_cleared():
            worker_db = SessionLocal()
            try:
                outcome = recruitment_progression_service.record_student_round_outcome(
                    db=worker_db,
                    application_id=self.app_b.id,
                    round_id=round_b1.id,
                    outcome=RoundOutcome.CLEARED,
                    score=90.0,
                    remarks="Worker Cleared",
                    current_user=self.officer,
                )
                return ("CLEARED", outcome.id, None)
            except Exception as e:
                # Confirm session is not broken after error
                test_query = worker_db.query(JobPosting).count()
                return ("CLEARED", None, (type(e).__name__, str(e), test_query > 0))
            finally:
                worker_db.close()

        def worker_rejected():
            worker_db = SessionLocal()
            try:
                outcome = recruitment_progression_service.record_student_round_outcome(
                    db=worker_db,
                    application_id=self.app_b.id,
                    round_id=round_b1.id,
                    outcome=RoundOutcome.REJECTED,
                    score=40.0,
                    remarks="Worker Rejected",
                    current_user=self.officer,
                )
                return ("REJECTED", outcome.id, None)
            except Exception as e:
                test_query = worker_db.query(JobPosting).count()
                return ("REJECTED", None, (type(e).__name__, str(e), test_query > 0))
            finally:
                worker_db.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(worker_cleared)
            f2 = executor.submit(worker_rejected)
            res1 = f1.result()
            res2 = f2.result()

        results = [res1, res2]
        successes = [r for r in results if r[1] is not None]
        failures = [r for r in results if r[2] is not None]

        # Exactly 1 request succeeds, and exactly 1 fails with controlled ValueError
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)

        err_type, err_msg, session_healthy = failures[0][2]
        self.assertEqual(err_type, "ValueError")
        self.assertIn("already confirmed concurrently", err_msg)
        self.assertTrue(session_healthy, "Worker session must remain functional after rollback")

        # Database has exactly 1 record
        count = self.db.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.application_id == self.app_b.id,
            StudentRoundOutcome.round_id == round_b1.id
        ).count()
        self.assertEqual(count, 1)

    # -------------------------------------------------------------------------
    # 21. Offer Update Failure Leaves Original Offer Untouched
    # -------------------------------------------------------------------------
    def test_21_offer_update_failure_leaves_original_offer_untouched(self):
        """Verify invalid offer update parameters leave the original offer in database untouched."""
        offer = self.db.query(PlacementOffer).filter(
            PlacementOffer.application_id == self.app_a.id
        ).first()
        self.assertIsNotNone(offer)
        original_ctc = offer.ctc_lpa
        original_status = offer.acceptance_status
        original_designation = offer.designation

        # Attempt invalid CTC update (negative value)
        with self.assertRaises(ValueError):
            recruitment_progression_service.create_or_update_placement_offer(
                db=self.db,
                application_id=self.app_a.id,
                ctc_lpa=-99.0,
                current_user=self.officer,
            )

        # Refresh offer from database and assert complete immutability
        self.db.refresh(offer)
        self.assertEqual(offer.ctc_lpa, original_ctc)
        self.assertEqual(offer.acceptance_status, original_status)
        self.assertEqual(offer.designation, original_designation)

    # -------------------------------------------------------------------------
    # 22. Unauthorized Offer Update Leaves Original Offer Untouched
    # -------------------------------------------------------------------------
    def test_22_unauthorized_offer_update_leaves_original_offer_untouched(self):
        """Verify unauthorized user cannot mutate placement offer and database record is untouched."""
        offer = self.db.query(PlacementOffer).filter(
            PlacementOffer.application_id == self.app_a.id
        ).first()
        original_ctc = offer.ctc_lpa

        # Attempt unauthorized mutation
        with self.assertRaises(PermissionError):
            recruitment_progression_service.create_or_update_placement_offer(
                db=self.db,
                application_id=self.app_a.id,
                ctc_lpa=50.0,
                designation="Unauthorized CEO",
                current_user=self.unauthorized_student,
            )

        self.db.refresh(offer)
        self.assertEqual(offer.ctc_lpa, original_ctc)


if __name__ == "__main__":
    unittest.main()
