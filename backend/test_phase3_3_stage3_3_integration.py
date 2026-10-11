"""
EduMatrix Phase 3.3 — Stage 3.3.3: Recruitment Results & Progression Integration Test Suite

Comprehensive tests covering all 16 required areas:
1. Explicitly linked batch confirms valid outcomes for its own round.
2. Batch linked to a round from another job is rejected.
3. Cross-company associations are rejected.
4. Legacy batch with null round_id retains prior behavior.
5. Pending or ambiguous matches do not enter the authoritative ledger.
6. Correct mapping of confirmed statuses to round outcomes.
7. Intermediate selection does not mark a student finally placed.
8. Verified offers are not inferred from ordinary round selection.
9. Duplicate batch confirmation is idempotent.
10. Conflicting confirmation requires an explicit audited correction.
11. Duplicate student rows in a batch are handled safely.
12. Concurrent confirmation cannot create duplicate authoritative outcomes.
13. Notification is emitted only after successful confirmation.
14. Failed confirmation does not leave partial ledger state.
15. Existing notification deduplication still works.
16. Existing result upload, circular, and student application workflows remain compatible.
"""

import time
import unittest
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.models.user import User, UserRole
from app.models.company import Company
from app.models.job_posting import JobPosting, JobStatus
from app.models.application import Application, ApplicationStatus
from app.models.profile import StudentProfileExtended, PlacementStatus
from app.models.notification import Notification
from app.models.audit_log import AuditLog
from app.models.file import File
from app.models.recruitment_circular import RecruitmentCircular, RecruitmentCircularStatus
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
)
from app.services.recruitment_result_service import recruitment_result_service
from app.services.recruitment_progression_service import recruitment_progression_service


class TestRecruitmentResultsProgressionIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db: Session = SessionLocal()
        cls.ts = int(time.time() * 1000)

        # 1. Placement Officer Actor
        cls.officer = cls.db.query(User).filter(User.role == UserRole.PLACEMENT_OFFICER).first()
        if not cls.officer:
            cls.officer = User(
                email=f"po_int_{cls.ts}@edumatrix.edu",
                name="Officer Integration Test",
                role=UserRole.PLACEMENT_OFFICER,
                password_hash="fakehash",
                is_active=True,
            )
            cls.db.add(cls.officer)
            cls.db.commit()
            cls.db.refresh(cls.officer)

        # 2. Test Students
        cls.students = []
        for i in range(5):
            s = User(
                email=f"student_{i}_{cls.ts}@edumatrix.edu",
                name=f"Student Candidate {i}",
                role=UserRole.STUDENT,
                password_hash="fakehash",
                is_active=True,
            )
            cls.db.add(s)
            cls.db.commit()
            cls.db.refresh(s)

            prof = StudentProfileExtended(
                user_id=s.id,
                enrollment_number=f"4VP23CS{900 + i}",
                full_name=s.name,
                placement_status=PlacementStatus.NOT_APPLIED,
                branch="Computer Science (CSE)",
                cgpa=8.5,
            )
            cls.db.add(prof)
            cls.students.append(s)

        # Inactive student
        cls.inactive_student = User(
            email=f"inactive_{cls.ts}@edumatrix.edu",
            name="Inactive Candidate",
            role=UserRole.STUDENT,
            password_hash="fakehash",
            is_active=False,
        )
        cls.db.add(cls.inactive_student)
        cls.db.commit()
        cls.db.refresh(cls.inactive_student)

        # 3. Companies
        cls.company_a = Company(
            name=f"Acme Corp {cls.ts}",
            industry="Technology",
            location="Bangalore",
            is_active=True,
        )
        cls.company_b = Company(
            name=f"Global Systems {cls.ts}",
            industry="Consulting",
            location="Hyderabad",
            is_active=True,
        )
        cls.db.add_all([cls.company_a, cls.company_b])
        cls.db.commit()
        cls.db.refresh(cls.company_a)
        cls.db.refresh(cls.company_b)

        # 4. Job Postings
        cls.job_a = JobPosting(
            company_id=cls.company_a.id,
            title=f"Software Engineer {cls.ts}",
            status=JobStatus.OPEN,
        )
        cls.job_b = JobPosting(
            company_id=cls.company_b.id,
            title=f"Data Analyst {cls.ts}",
            status=JobStatus.OPEN,
        )
        cls.db.add_all([cls.job_a, cls.job_b])
        cls.db.commit()
        cls.db.refresh(cls.job_a)
        cls.db.refresh(cls.job_b)

        # 5. Recruitment Rounds for Job A
        cls.round_a1 = RecruitmentRound(
            job_posting_id=cls.job_a.id,
            round_number=1,
            name="Online Assessment",
            round_type="assessment",
            is_final=False,
        )
        cls.round_a2 = RecruitmentRound(
            job_posting_id=cls.job_a.id,
            round_number=2,
            name="Technical Interview",
            round_type="interview",
            is_final=False,
        )
        cls.round_a_final = RecruitmentRound(
            job_posting_id=cls.job_a.id,
            round_number=3,
            name="HR & Final Discussion",
            round_type="interview",
            is_final=True,
        )

        # Round for Job B
        cls.round_b1 = RecruitmentRound(
            job_posting_id=cls.job_b.id,
            round_number=1,
            name="Aptitude Test",
            round_type="assessment",
            is_final=False,
        )

        cls.db.add_all([cls.round_a1, cls.round_a2, cls.round_a_final, cls.round_b1])
        cls.db.commit()
        cls.db.refresh(cls.round_a1)
        cls.db.refresh(cls.round_a2)
        cls.db.refresh(cls.round_a_final)
        cls.db.refresh(cls.round_b1)

        # 6. Sample File for Batches
        cls.sample_file = cls.db.query(File).first()
        if not cls.sample_file:
            cls.sample_file = File(
                filename="test_results.csv",
                file_size=1024,
                mime_type="text/csv",
                bucket="edumatrix-files",
                object_key=f"placement/test_results_{cls.ts}.csv",
                department="Placement",
                file_type="placement_doc",
                uploaded_by=cls.officer.id,
            )
            cls.db.add(cls.sample_file)
            cls.db.commit()
            cls.db.refresh(cls.sample_file)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    # =========================================================================
    # TEST 1: Explicitly linked batch confirms valid outcomes for its own round
    # =========================================================================
    def test_01_explicitly_linked_batch_confirms_valid_outcomes_for_own_round(self):
        """Batch explicitly linked to Round 1 confirms items into StudentRoundOutcome ledger."""
        student = self.students[0]

        # Create batch linked to round_a1
        batch = RecruitmentResultBatch(
            company_id=self.company_a.id,
            file_id=self.sample_file.id,
            job_posting_id=self.job_a.id,
            round_id=self.round_a1.id,
            round_name="Online Assessment",
            round_type="assessment",
            is_final_round=False,
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            total_rows=1,
            matched_count=1,
            ambiguous_count=0,
            confirmed_count=0,
            uploaded_by=self.officer.id,
        )
        self.db.add(batch)
        self.db.flush()

        item = RecruitmentResultItem(
            batch_id=batch.id,
            row_index=1,
            extracted_usn="4VP23CS900",
            extracted_name=student.name,
            extracted_email=student.email,
            extracted_status_raw="Shortlisted",
            normalized_status=RecruitmentResultItemStatus.SHORTLISTED,
            matched_student_id=student.id,
            match_confidence=1.0,
            match_method="exact_usn",
            review_status=RecruitmentResultReviewState.MATCHED,
        )
        self.db.add(item)
        self.db.commit()

        # Confirm batch
        res = recruitment_result_service.confirm_batch_results(
            db=self.db,
            batch_id=batch.id,
            current_user=self.officer,
        )

        self.assertEqual(res["confirmed_count"], 1)
        self.assertEqual(res["outcomes_recorded"], 1)
        self.assertEqual(res["round_id"], self.round_a1.id)

        # Verify StudentRoundOutcome record
        outcome = self.db.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.student_id == student.id,
            StudentRoundOutcome.round_id == self.round_a1.id,
        ).first()

        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.outcome, RoundOutcome.CLEARED)
        self.assertEqual(outcome.source_batch_id, batch.id)
        self.assertEqual(outcome.source_item_id, item.id)
        self.assertEqual(outcome.confirmed_by, self.officer.id)

        # Verify batch status is FULLY_CONFIRMED
        self.db.refresh(batch)
        self.assertEqual(batch.status, RecruitmentResultBatchStatus.FULLY_CONFIRMED)
        self.assertEqual(batch.confirmed_count, 1)

    # =========================================================================
    # TEST 2: Batch linked to a round from another job is rejected
    # =========================================================================
    def test_02_batch_linked_to_round_from_another_job_rejected(self):
        """Cross-job round associations are strictly prohibited."""
        student = self.students[1]

        # Batch belongs to Job A, but round_id points to Round B1 (Job B)
        batch = RecruitmentResultBatch(
            company_id=self.company_a.id,
            file_id=self.sample_file.id,
            job_posting_id=self.job_a.id,
            round_id=self.round_b1.id,
            round_name="Mismatched Round",
            round_type="assessment",
            is_final_round=False,
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            total_rows=1,
            matched_count=1,
            ambiguous_count=0,
            confirmed_count=0,
            uploaded_by=self.officer.id,
        )
        self.db.add(batch)
        self.db.flush()

        item = RecruitmentResultItem(
            batch_id=batch.id,
            row_index=1,
            extracted_usn="4VP23CS901",
            extracted_name=student.name,
            extracted_email=student.email,
            extracted_status_raw="Selected",
            normalized_status=RecruitmentResultItemStatus.SELECTED,
            matched_student_id=student.id,
            review_status=RecruitmentResultReviewState.MATCHED,
        )
        self.db.add(item)
        self.db.commit()

        # Confirmation must fail
        with self.assertRaises(ValueError) as ctx:
            recruitment_result_service.confirm_batch_results(
                db=self.db,
                batch_id=batch.id,
                current_user=self.officer,
            )
        self.assertIn("Cross-job", str(ctx.exception))

        # Explicit linking API must also reject cross-job association
        with self.assertRaises(ValueError) as ctx2:
            recruitment_progression_service.link_batch_to_round(
                db=self.db,
                batch_id=batch.id,
                round_id=self.round_b1.id,
                current_user=self.officer,
            )
        self.assertIn("Cross-job", str(ctx2.exception))

    # =========================================================================
    # TEST 3: Cross-company associations are rejected
    # =========================================================================
    def test_03_cross_company_associations_rejected(self):
        """Cross-company batch-to-round associations are strictly prohibited."""
        student = self.students[1]

        # Batch belongs to Company A, but linked round belongs to Company B's job
        batch = RecruitmentResultBatch(
            company_id=self.company_a.id,
            file_id=self.sample_file.id,
            job_posting_id=None,  # batch without job posting but with company_a
            round_id=self.round_b1.id,  # round_b1 belongs to Company B
            round_name="Cross Company Round",
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            total_rows=1,
            matched_count=1,
            uploaded_by=self.officer.id,
        )
        self.db.add(batch)
        self.db.flush()

        item = RecruitmentResultItem(
            batch_id=batch.id,
            row_index=1,
            extracted_usn="4VP23CS901",
            extracted_name=student.name,
            extracted_email=student.email,
            extracted_status_raw="Shortlisted",
            normalized_status=RecruitmentResultItemStatus.SHORTLISTED,
            matched_student_id=student.id,
            review_status=RecruitmentResultReviewState.MATCHED,
        )
        self.db.add(item)
        self.db.commit()

        with self.assertRaises(ValueError) as ctx:
            recruitment_result_service.confirm_batch_results(
                db=self.db,
                batch_id=batch.id,
                current_user=self.officer,
            )
        self.assertIn("Cross-company", str(ctx.exception))

    # =========================================================================
    # TEST 4: Legacy batch with null round_id retains prior behavior
    # =========================================================================
    def test_04_legacy_batch_with_null_round_id_retains_prior_behavior(self):
        """Legacy batches with round_id = NULL must confirm without creating progression outcomes."""
        student = self.students[2]

        batch = RecruitmentResultBatch(
            company_id=self.company_a.id,
            file_id=self.sample_file.id,
            job_posting_id=self.job_a.id,
            round_id=None,  # LEGACY NULL ROUND
            round_name="Legacy Free Text Round",
            round_type="assessment",
            is_final_round=False,
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            total_rows=1,
            matched_count=1,
            ambiguous_count=0,
            confirmed_count=0,
            uploaded_by=self.officer.id,
        )
        self.db.add(batch)
        self.db.flush()

        item = RecruitmentResultItem(
            batch_id=batch.id,
            row_index=1,
            extracted_usn="4VP23CS902",
            extracted_name=student.name,
            extracted_email=student.email,
            extracted_status_raw="Shortlisted",
            normalized_status=RecruitmentResultItemStatus.SHORTLISTED,
            matched_student_id=student.id,
            review_status=RecruitmentResultReviewState.MATCHED,
        )
        self.db.add(item)
        self.db.commit()

        # Confirmation succeeds via legacy path
        res = recruitment_result_service.confirm_batch_results(
            db=self.db,
            batch_id=batch.id,
            current_user=self.officer,
        )

        self.assertEqual(res["confirmed_count"], 1)
        self.assertIsNone(res.get("round_id"))

        # Zero StudentRoundOutcome records must be created for this batch
        prog_count = self.db.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.source_batch_id == batch.id
        ).count()
        self.assertEqual(prog_count, 0)

        # Legacy application update took place
        app = self.db.query(Application).filter(
            Application.student_id == student.id,
            Application.job_posting_id == self.job_a.id,
        ).first()
        self.assertIsNotNone(app)
        self.assertEqual(app.status, ApplicationStatus.SHORTLISTED)

    # =========================================================================
    # TEST 5: Pending or ambiguous matches do not enter authoritative ledger
    # =========================================================================
    def test_05_pending_or_ambiguous_matches_do_not_enter_authoritative_ledger(self):
        """Ambiguous, unlinked, or ignored rows must be blocked from confirmation."""
        batch = RecruitmentResultBatch(
            company_id=self.company_a.id,
            file_id=self.sample_file.id,
            job_posting_id=self.job_a.id,
            round_id=self.round_a1.id,
            round_name="Online Assessment",
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            total_rows=2,
            matched_count=0,
            ambiguous_count=1,
            uploaded_by=self.officer.id,
        )
        self.db.add(batch)
        self.db.flush()

        item_ambiguous = RecruitmentResultItem(
            batch_id=batch.id,
            row_index=1,
            extracted_name="Ambiguous Candidate",
            extracted_status_raw="Selected",
            normalized_status=RecruitmentResultItemStatus.SELECTED,
            matched_student_id=self.students[0].id,
            review_status=RecruitmentResultReviewState.AMBIGUOUS,
        )
        item_unmatched = RecruitmentResultItem(
            batch_id=batch.id,
            row_index=2,
            extracted_name="Unknown Candidate",
            extracted_status_raw="Selected",
            normalized_status=RecruitmentResultItemStatus.SELECTED,
            matched_student_id=None,
            review_status=RecruitmentResultReviewState.UNRESOLVED,
        )
        self.db.add_all([item_ambiguous, item_unmatched])
        self.db.commit()

        # Confirmation with explicit ambiguous item must raise ValueError
        with self.assertRaises(ValueError) as ctx:
            recruitment_result_service.confirm_batch_results(
                db=self.db,
                batch_id=batch.id,
                item_ids=[item_ambiguous.id],
                current_user=self.officer,
            )
        self.assertIn("AMBIGUOUS", str(ctx.exception))

        # Confirmation with unmatched item must raise ValueError
        with self.assertRaises(ValueError) as ctx2:
            recruitment_result_service.confirm_batch_results(
                db=self.db,
                batch_id=batch.id,
                item_ids=[item_unmatched.id],
                current_user=self.officer,
            )
        self.assertIn("no matched student", str(ctx2.exception))

    # =========================================================================
    # TEST 6: Correct mapping of confirmed statuses to round outcomes
    # =========================================================================
    def test_06_correct_mapping_of_confirmed_statuses_to_round_outcomes(self):
        """Verify explicit status-to-outcome mapping rules."""
        # Intermediate round
        self.assertEqual(
            recruitment_result_service.map_result_status_to_round_outcome(
                RecruitmentResultItemStatus.SHORTLISTED, is_final_round=False
            ),
            RoundOutcome.CLEARED,
        )
        self.assertEqual(
            recruitment_result_service.map_result_status_to_round_outcome(
                RecruitmentResultItemStatus.SELECTED, is_final_round=False
            ),
            RoundOutcome.CLEARED,
        )
        self.assertEqual(
            recruitment_result_service.map_result_status_to_round_outcome(
                RecruitmentResultItemStatus.REJECTED, is_final_round=False
            ),
            RoundOutcome.REJECTED,
        )
        self.assertEqual(
            recruitment_result_service.map_result_status_to_round_outcome(
                RecruitmentResultItemStatus.ABSENT, is_final_round=False
            ),
            RoundOutcome.ABSENT,
        )
        self.assertEqual(
            recruitment_result_service.map_result_status_to_round_outcome(
                RecruitmentResultItemStatus.ON_HOLD, is_final_round=False
            ),
            RoundOutcome.ON_HOLD,
        )

        # Final round (Phase 3.3.4 corrected review mapping)
        self.assertEqual(
            recruitment_result_service.map_result_status_to_round_outcome(
                RecruitmentResultItemStatus.SELECTED, is_final_round=True
            ),
            RoundOutcome.CLEARED,
        )
        self.assertEqual(
            recruitment_result_service.map_result_status_to_round_outcome(
                RecruitmentResultItemStatus.SELECTED, is_final_round=True, legacy_offered=True
            ),
            RoundOutcome.OFFERED,
        )

        self.assertEqual(
            recruitment_result_service.map_result_status_to_round_outcome(
                RecruitmentResultItemStatus.SHORTLISTED, is_final_round=True
            ),
            RoundOutcome.CLEARED,
        )
        self.assertEqual(
            recruitment_result_service.map_result_status_to_round_outcome(
                RecruitmentResultItemStatus.REJECTED, is_final_round=True
            ),
            RoundOutcome.REJECTED,
        )

    # =========================================================================
    # TEST 7: Intermediate selection does not mark student finally placed
    # =========================================================================
    def test_07_intermediate_selection_does_not_mark_student_finally_placed(self):
        """Selected in intermediate round marks CLEARED, never modifies profile placement status."""
        student = self.students[3]
        profile = self.db.query(StudentProfileExtended).filter(
            StudentProfileExtended.user_id == student.id
        ).first()
        profile.placement_status = PlacementStatus.NOT_APPLIED
        self.db.commit()

        batch = RecruitmentResultBatch(
            company_id=self.company_a.id,
            file_id=self.sample_file.id,
            job_posting_id=self.job_a.id,
            round_id=self.round_a2.id,  # Intermediate Round 2
            round_name="Technical Interview",
            is_final_round=False,
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            total_rows=1,
            matched_count=1,
            uploaded_by=self.officer.id,
        )
        self.db.add(batch)
        self.db.flush()

        item = RecruitmentResultItem(
            batch_id=batch.id,
            row_index=1,
            extracted_usn="4VP23CS903",
            extracted_name=student.name,
            extracted_email=student.email,
            extracted_status_raw="Selected",
            normalized_status=RecruitmentResultItemStatus.SELECTED,
            matched_student_id=student.id,
            review_status=RecruitmentResultReviewState.MATCHED,
        )
        self.db.add(item)
        self.db.commit()

        recruitment_result_service.confirm_batch_results(
            db=self.db,
            batch_id=batch.id,
            current_user=self.officer,
        )

        # 1. Progression outcome is CLEARED
        outcome = self.db.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.student_id == student.id,
            StudentRoundOutcome.round_id == self.round_a2.id,
        ).first()
        self.assertEqual(outcome.outcome, RoundOutcome.CLEARED)

        # 2. Profile placement status is STILL NOT_APPLIED (never set to PLACED!)
        self.db.refresh(profile)
        self.assertEqual(profile.placement_status, PlacementStatus.NOT_APPLIED)

        # 3. Application status is SHORTLISTED (for next round)
        app = self.db.query(Application).filter(
            Application.student_id == student.id,
            Application.job_posting_id == self.job_a.id,
        ).first()
        self.assertEqual(app.status, ApplicationStatus.SHORTLISTED)

    # =========================================================================
    # TEST 8: Verified offers are not inferred from ordinary round selection
    # =========================================================================
    def test_08_verified_offers_not_inferred_from_ordinary_round_selection(self):
        """Final round selection records OFFERED outcome, but does NOT create PlacementOffer or mark PLACED."""
        student = self.students[4]
        profile = self.db.query(StudentProfileExtended).filter(
            StudentProfileExtended.user_id == student.id
        ).first()
        profile.placement_status = PlacementStatus.SHORTLISTED
        self.db.commit()

        batch = RecruitmentResultBatch(
            company_id=self.company_a.id,
            file_id=self.sample_file.id,
            job_posting_id=self.job_a.id,
            round_id=self.round_a_final.id,  # Final Round 3
            round_name="HR & Final Discussion",
            is_final_round=True,
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            total_rows=1,
            matched_count=1,
            uploaded_by=self.officer.id,
        )
        self.db.add(batch)
        self.db.flush()

        item = RecruitmentResultItem(
            batch_id=batch.id,
            row_index=1,
            extracted_usn="4VP23CS904",
            extracted_name=student.name,
            extracted_email=student.email,
            extracted_status_raw="Selected",
            normalized_status=RecruitmentResultItemStatus.SELECTED,
            matched_student_id=student.id,
            review_status=RecruitmentResultReviewState.MATCHED,
        )
        self.db.add(item)
        self.db.commit()

        recruitment_result_service.confirm_batch_results(
            db=self.db,
            batch_id=batch.id,
            current_user=self.officer,
        )

        # 1. Progression outcome is CLEARED (cleared final recruitment round)
        outcome = self.db.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.student_id == student.id,
            StudentRoundOutcome.round_id == self.round_a_final.id,
        ).first()
        self.assertEqual(outcome.outcome, RoundOutcome.CLEARED)


        # 2. No automatic PlacementOffer record is created
        app = self.db.query(Application).filter(
            Application.student_id == student.id,
            Application.job_posting_id == self.job_a.id,
        ).first()
        offer = self.db.query(PlacementOffer).filter(
            PlacementOffer.application_id == app.id
        ).first()
        self.assertIsNone(offer, "PlacementOffer must not be inferred automatically without explicit verification.")

        # 3. Profile placement status remains SHORTLISTED (OFFERED is not ACCEPTED!)
        self.db.refresh(profile)
        self.assertEqual(profile.placement_status, PlacementStatus.SHORTLISTED)

    # =========================================================================
    # TEST 9: Duplicate batch confirmation is idempotent
    # =========================================================================
    def test_09_duplicate_batch_confirmation_is_idempotent(self):
        """Reconfirming an already confirmed batch is completely idempotent."""
        student = self.students[0]

        # Fetch batch from test 1
        batch = self.db.query(RecruitmentResultBatch).filter(
            RecruitmentResultBatch.round_id == self.round_a1.id
        ).first()

        outcome_count_before = self.db.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.student_id == student.id,
            StudentRoundOutcome.round_id == self.round_a1.id,
        ).count()

        notif_count_before = self.db.query(Notification).filter(
            Notification.user_id == student.id
        ).count()

        # Re-confirm
        res = recruitment_result_service.confirm_batch_results(
            db=self.db,
            batch_id=batch.id,
            current_user=self.officer,
        )

        outcome_count_after = self.db.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.student_id == student.id,
            StudentRoundOutcome.round_id == self.round_a1.id,
        ).count()

        notif_count_after = self.db.query(Notification).filter(
            Notification.user_id == student.id
        ).count()

        self.assertEqual(outcome_count_before, outcome_count_after)
        self.assertEqual(notif_count_before, notif_count_after)

    # =========================================================================
    # TEST 10: Conflicting confirmation requires an explicit audited correction
    # =========================================================================
    def test_10_conflicting_confirmation_requires_explicit_audited_correction(self):
        """Conflicting batch outcome is rejected; explicit correction workflow required."""
        student = self.students[0]
        # Student already has CLEARED in round_a1 from test 1.
        app = self.db.query(Application).filter(
            Application.student_id == student.id,
            Application.job_posting_id == self.job_a.id,
        ).first()

        # Attempting to record conflicting outcome REJECTED must raise ValueError
        with self.assertRaises(ValueError) as ctx:
            recruitment_progression_service.record_student_round_outcome(
                db=self.db,
                application_id=app.id,
                round_id=self.round_a1.id,
                outcome=RoundOutcome.REJECTED,
                current_user=self.officer,
            )
        self.assertIn("authoritative outcome", str(ctx.exception))
        self.assertIn("correct_student_round_outcome", str(ctx.exception))

        existing_outcome = self.db.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.student_id == student.id,
            StudentRoundOutcome.round_id == self.round_a1.id,
        ).first()

        # Explicit audited correction succeeds
        corrected = recruitment_progression_service.correct_student_round_outcome(
            db=self.db,
            outcome_id=existing_outcome.id,
            new_outcome=RoundOutcome.REJECTED,
            reason="Score sheet calculation error corrected by Placement Director",
            current_user=self.officer,
        )
        self.assertEqual(corrected.outcome, RoundOutcome.REJECTED)

        # Audit log verification
        audit = self.db.query(AuditLog).filter(
            AuditLog.action == "STUDENT_ROUND_OUTCOME_CORRECTED",
            AuditLog.target_id == str(corrected.id),
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.details["previous_outcome"], "cleared")
        self.assertEqual(audit.details["new_outcome"], "rejected")

    # =========================================================================
    # TEST 11: Duplicate student rows in a batch are handled safely
    # =========================================================================
    def test_11_duplicate_student_rows_in_batch_handled_safely(self):
        """Batch containing duplicate rows for the same student creates 1 outcome and 1 notification."""
        student = self.students[1]

        batch = RecruitmentResultBatch(
            company_id=self.company_a.id,
            file_id=self.sample_file.id,
            job_posting_id=self.job_a.id,
            round_id=self.round_a1.id,
            round_name="Online Assessment",
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            total_rows=2,
            matched_count=2,
            uploaded_by=self.officer.id,
        )
        self.db.add(batch)
        self.db.flush()

        item1 = RecruitmentResultItem(
            batch_id=batch.id,
            row_index=1,
            extracted_usn="4VP23CS901",
            extracted_name=student.name,
            extracted_email=student.email,
            extracted_status_raw="Shortlisted",
            normalized_status=RecruitmentResultItemStatus.SHORTLISTED,
            matched_student_id=student.id,
            review_status=RecruitmentResultReviewState.MATCHED,
        )
        item2 = RecruitmentResultItem(
            batch_id=batch.id,
            row_index=2,
            extracted_usn="4VP23CS901",
            extracted_name=student.name,
            extracted_email=student.email,
            extracted_status_raw="Shortlisted",
            normalized_status=RecruitmentResultItemStatus.SHORTLISTED,
            matched_student_id=student.id,
            review_status=RecruitmentResultReviewState.MATCHED,
        )
        self.db.add_all([item1, item2])
        self.db.commit()

        notifs_before = self.db.query(Notification).filter(
            Notification.user_id == student.id,
            Notification.event_key.like(f"recruitment_round:{self.round_a1.id}:student:{student.id}:batch:{batch.id}"),
        ).count()

        recruitment_result_service.confirm_batch_results(
            db=self.db,
            batch_id=batch.id,
            current_user=self.officer,
        )

        # Exactly 1 StudentRoundOutcome exists
        outcomes = self.db.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.student_id == student.id,
            StudentRoundOutcome.round_id == self.round_a1.id,
        ).all()
        self.assertEqual(len(outcomes), 1)

        # Exactly 1 Notification exists
        notifs_after = self.db.query(Notification).filter(
            Notification.user_id == student.id,
            Notification.event_key.like(f"recruitment_round:{self.round_a1.id}:student:{student.id}:batch:{batch.id}"),
        ).count()
        self.assertEqual(notifs_after, 1)

    # =========================================================================
    # TEST 12: Concurrent confirmation cannot create duplicate authoritative outcomes
    # =========================================================================
    def test_12_concurrent_confirmation_cannot_create_duplicate_authoritative_outcomes(self):
        """Database constraint uq_student_round_outcome prevents duplicate entries."""
        student = self.students[2]
        app = self.db.query(Application).filter(
            Application.student_id == student.id,
            Application.job_posting_id == self.job_a.id,
        ).first()
        if not app:
            app = Application(
                student_id=student.id,
                job_posting_id=self.job_a.id,
                status=ApplicationStatus.APPLIED,
            )
            self.db.add(app)
            self.db.commit()
            self.db.refresh(app)

        # Record outcome in session 1
        recruitment_progression_service.record_student_round_outcome(
            db=self.db,
            application_id=app.id,
            round_id=self.round_a2.id,
            outcome=RoundOutcome.CLEARED,
            current_user=self.officer,
            auto_commit=True,
        )

        # Direct insert attempt in another session violating constraint raises IntegrityError
        session2 = SessionLocal()
        try:
            dup = StudentRoundOutcome(
                application_id=app.id,
                round_id=self.round_a2.id,
                student_id=student.id,
                outcome=RoundOutcome.CLEARED,
            )
            session2.add(dup)
            with self.assertRaises(IntegrityError):
                session2.commit()
        finally:
            session2.rollback()
            session2.close()

    # =========================================================================
    # TEST 13: Notification is emitted only after successful confirmation
    # =========================================================================
    def test_13_notification_emitted_only_after_successful_confirmation(self):
        """Notifications are generated post-confirmation with full context."""
        student = self.students[3]

        batch = RecruitmentResultBatch(
            company_id=self.company_a.id,
            file_id=self.sample_file.id,
            job_posting_id=self.job_a.id,
            round_id=self.round_a1.id,
            round_name="Online Assessment",
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            total_rows=1,
            matched_count=1,
            uploaded_by=self.officer.id,
        )
        self.db.add(batch)
        self.db.flush()

        item = RecruitmentResultItem(
            batch_id=batch.id,
            row_index=1,
            extracted_usn="4VP23CS903",
            extracted_name=student.name,
            extracted_email=student.email,
            extracted_status_raw="Shortlisted",
            normalized_status=RecruitmentResultItemStatus.SHORTLISTED,
            matched_student_id=student.id,
            review_status=RecruitmentResultReviewState.MATCHED,
        )
        self.db.add(item)
        self.db.commit()

        # Before confirmation: check notif count for this round
        key = f"recruitment_round:{self.round_a1.id}:student:{student.id}:batch:{batch.id}"
        before = self.db.query(Notification).filter(Notification.event_key == key).count()
        self.assertEqual(before, 0)

        # After confirmation: 1 notification
        recruitment_result_service.confirm_batch_results(
            db=self.db,
            batch_id=batch.id,
            current_user=self.officer,
        )
        after = self.db.query(Notification).filter(Notification.event_key == key).first()
        self.assertIsNotNone(after)
        self.assertIn("Round 1 (Online Assessment)", after.title)
        self.assertIn(self.company_a.name, after.message)

    # =========================================================================
    # TEST 14: Failed confirmation does not leave partial ledger state
    # =========================================================================
    def test_14_failed_confirmation_does_not_leave_partial_ledger_state(self):
        """Session transaction rollback ensures zero partial ledger writes on failure."""
        valid_student = self.students[3]
        inactive_student = self.inactive_student

        batch = RecruitmentResultBatch(
            company_id=self.company_a.id,
            file_id=self.sample_file.id,
            job_posting_id=self.job_a.id,
            round_id=self.round_a_final.id,
            round_name="HR & Final Discussion",
            is_final_round=True,
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            total_rows=2,
            matched_count=2,
            uploaded_by=self.officer.id,
        )
        self.db.add(batch)
        self.db.flush()

        # Item 1 is valid
        item1 = RecruitmentResultItem(
            batch_id=batch.id,
            row_index=1,
            extracted_usn="4VP23CS903",
            extracted_name=valid_student.name,
            extracted_email=valid_student.email,
            extracted_status_raw="Selected",
            normalized_status=RecruitmentResultItemStatus.SELECTED,
            matched_student_id=valid_student.id,
            review_status=RecruitmentResultReviewState.MATCHED,
        )
        # Item 2 is inactive student (triggers validation error)
        item2 = RecruitmentResultItem(
            batch_id=batch.id,
            row_index=2,
            extracted_name=inactive_student.name,
            extracted_email=inactive_student.email,
            extracted_status_raw="Selected",
            normalized_status=RecruitmentResultItemStatus.SELECTED,
            matched_student_id=inactive_student.id,
            review_status=RecruitmentResultReviewState.MATCHED,
        )
        self.db.add_all([item1, item2])
        self.db.commit()

        # Confirmation must fail
        with self.assertRaises(ValueError) as ctx:
            recruitment_result_service.confirm_batch_results(
                db=self.db,
                batch_id=batch.id,
                current_user=self.officer,
            )
        self.assertIn("inactive", str(ctx.exception))

        # Ledger state verification: Item 1's outcome must NOT be persisted
        outcome = self.db.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.source_batch_id == batch.id
        ).all()
        self.assertEqual(len(outcome), 0, "No partial outcomes may be written on failed confirmation.")

        # Batch remains IN_REVIEW
        self.db.refresh(batch)
        self.assertEqual(batch.status, RecruitmentResultBatchStatus.IN_REVIEW)

        # Items remain MATCHED (not CONFIRMED)
        self.db.refresh(item1)
        self.assertEqual(item1.review_status, RecruitmentResultReviewState.MATCHED)

    # =========================================================================
    # TEST 15: Existing notification deduplication still works
    # =========================================================================
    def test_15_existing_notification_deduplication_still_works(self):
        """Pre-existing notification prevents duplicate creation."""
        student = self.students[4]

        batch = RecruitmentResultBatch(
            company_id=self.company_a.id,
            file_id=self.sample_file.id,
            job_posting_id=self.job_a.id,
            round_id=self.round_a1.id,
            round_name="Online Assessment",
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            total_rows=1,
            matched_count=1,
            uploaded_by=self.officer.id,
        )
        self.db.add(batch)
        self.db.flush()

        event_key = f"recruitment_round:{self.round_a1.id}:student:{student.id}:batch:{batch.id}"

        # Pre-seed notification
        pre_notif = Notification(
            user_id=student.id,
            type="placement_result",
            title="Pre-seeded Notification",
            message="Already dispatched",
            event_key=event_key,
        )
        self.db.add(pre_notif)

        item = RecruitmentResultItem(
            batch_id=batch.id,
            row_index=1,
            extracted_usn="4VP23CS904",
            extracted_name=student.name,
            extracted_email=student.email,
            extracted_status_raw="Shortlisted",
            normalized_status=RecruitmentResultItemStatus.SHORTLISTED,
            matched_student_id=student.id,
            review_status=RecruitmentResultReviewState.MATCHED,
        )
        self.db.add(item)
        self.db.commit()

        # Confirmation
        res = recruitment_result_service.confirm_batch_results(
            db=self.db,
            batch_id=batch.id,
            current_user=self.officer,
        )
        self.assertEqual(res["notifications_dispatched"], 0)

        # Count of notifications with this key is still 1
        count = self.db.query(Notification).filter(Notification.event_key == event_key).count()
        self.assertEqual(count, 1)

    # =========================================================================
    # TEST 16: Existing result upload, circular, and student workflows compatible
    # =========================================================================
    def test_16_existing_workflows_compatibility(self):
        """Batch serialization, circular linking, and round link methods remain fully functional."""
        # 1. Circular-linked batch creation
        circular = RecruitmentCircular(
            company_id=self.company_a.id,
            title=f"Circular {self.ts}",
            status=RecruitmentCircularStatus.PUBLISHED,
        )
        self.db.add(circular)
        self.db.flush()

        batch = RecruitmentResultBatch(
            company_id=self.company_a.id,
            file_id=self.sample_file.id,
            job_posting_id=self.job_a.id,
            circular_id=circular.id,
            round_id=self.round_a1.id,
            round_name="Circular Drive Round",
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            total_rows=1,
            matched_count=1,
            uploaded_by=self.officer.id,
        )
        self.db.add(batch)
        self.db.commit()

        # 2. Serialization includes round_id and round_number
        data = recruitment_result_service.get_batch_by_id(self.db, batch.id, include_items=False)
        self.assertIsNotNone(data)
        self.assertEqual(data["round_id"], self.round_a1.id)
        self.assertEqual(data["round_number"], 1)
        self.assertEqual(data["circular_id"], circular.id)

        # 3. get_batches list serialization
        batch_list = recruitment_result_service.get_batches(
            db=self.db, company_id=self.company_a.id, limit=5
        )
        found = any(b["id"] == batch.id for b in batch_list)
        self.assertTrue(found)


if __name__ == "__main__":
    unittest.main()
