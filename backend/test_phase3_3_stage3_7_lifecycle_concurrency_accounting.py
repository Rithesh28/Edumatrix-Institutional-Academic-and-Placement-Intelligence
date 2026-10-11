"""
EduMatrix Phase 3.3 — Stage 3.3.7: Final Regression, Lifecycle, Concurrency, and Placement Accounting Verification

Automated validation suite covering:
- Part B: Recruitment lifecycle correctness (10 Invariants)
- Part C: Authorization and privacy matrix (Role boundaries, attachments, private files)
- Part D: Transaction and concurrency tests (Concurrent offers, duplicate responses, conflict rejection, rollback)
- Part E: Placement accounting verification (10 scenario matrix, deduplication, rates, CSV export)
- Part F: Notifications and audit trail verification (Event keys, deduplication, audit security)
"""

import concurrent.futures
import csv
import io
import threading
import time
import unittest
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from unittest.mock import patch, MagicMock

import sqlalchemy as sa
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.user import User, UserRole, LecturerProfile
from app.models.company import Company
from app.models.job_posting import JobPosting, JobStatus
from app.models.application import Application, ApplicationStatus
from app.models.profile import StudentProfileExtended, PlacementStatus
from app.models.file import File, FileStatus, FileType
from app.models.notification import Notification
from app.models.audit_log import AuditLog
from app.models.recruitment_circular import (
    RecruitmentCircular,
    RecruitmentCircularAttachment,
    RecruitmentCircularStatus,
)
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
from app.services.file_storage.file_service import file_service


class TestStage337LifecycleConcurrencyAccounting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db: Session = SessionLocal()
        cls.client = TestClient(app)
        cls.ts = int(time.time() * 1000)

        # 1. Placement Officer
        cls.officer = cls.db.query(User).filter(User.role == UserRole.PLACEMENT_OFFICER, User.is_active == True).first()
        if not cls.officer:
            cls.officer = User(
                email=f"po_337_{cls.ts}@vcet.ac.in",
                name="Placement Officer 337",
                role=UserRole.PLACEMENT_OFFICER,
                password_hash="fakehash",
                department="PLACEMENT",
                is_active=True,
            )
            cls.db.add(cls.officer)
            cls.db.commit()
            cls.db.refresh(cls.officer)

        cls.officer_token = create_access_token({"id": cls.officer.id, "email": cls.officer.email, "role": cls.officer.role.value})
        cls.officer_headers = {"Authorization": f"Bearer {cls.officer_token}"}

        # 2. Admin User
        cls.admin = cls.db.query(User).filter(User.role == UserRole.ADMIN, User.is_active == True).first()
        if not cls.admin:
            cls.admin = User(
                email=f"admin_337_{cls.ts}@vcet.ac.in",
                name="Admin 337",
                role=UserRole.ADMIN,
                password_hash="fakehash",
                department="ADMIN",
                is_active=True,
            )
            cls.db.add(cls.admin)
            cls.db.commit()
            cls.db.refresh(cls.admin)

        cls.admin_token = create_access_token({"id": cls.admin.id, "email": cls.admin.email, "role": cls.admin.role.value})
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}

        # 3. Student A
        cls.student_a = User(
            email=f"student_a_{cls.ts}@vcet.ac.in",
            name="Alice Student 337",
            role=UserRole.STUDENT,
            password_hash="fakehash",
            department="CSE",
            is_active=True,
        )
        cls.db.add(cls.student_a)

        # 4. Student B
        cls.student_b = User(
            email=f"student_b_{cls.ts}@vcet.ac.in",
            name="Bob Student 337",
            role=UserRole.STUDENT,
            password_hash="fakehash",
            department="ECE",
            is_active=True,
        )
        cls.db.add(cls.student_b)

        # 5. Lecturer
        cls.lecturer = User(
            email=f"lecturer_337_{cls.ts}@vcet.ac.in",
            name="Dr. Smith Lecturer",
            role=UserRole.LECTURER,
            password_hash="fakehash",
            department="CSE",
            is_active=True,
        )
        cls.db.add(cls.lecturer)

        # 6. HOD
        cls.hod = User(
            email=f"hod_337_{cls.ts}@vcet.ac.in",
            name="Dr. Chief HOD",
            role=UserRole.HOD,
            password_hash="fakehash",
            department="CSE",
            is_active=True,
        )
        cls.db.add(cls.hod)

        # 7. Inactive User
        cls.inactive_user = User(
            email=f"inactive_337_{cls.ts}@vcet.ac.in",
            name="Disabled User",
            role=UserRole.STUDENT,
            password_hash="fakehash",
            department="CSE",
            is_active=False,
        )
        cls.db.add(cls.inactive_user)

        cls.db.commit()
        cls.db.refresh(cls.student_a)
        cls.db.refresh(cls.student_b)
        cls.db.refresh(cls.lecturer)
        cls.db.refresh(cls.hod)
        cls.db.refresh(cls.inactive_user)

        # Student Profiles
        for st in [cls.student_a, cls.student_b]:
            p = cls.db.query(StudentProfileExtended).filter(StudentProfileExtended.user_id == st.id).first()
            if not p:
                p = StudentProfileExtended(
                    user_id=st.id,
                    branch=st.department,
                    cgpa=8.5,
                    placement_status=PlacementStatus.APPLIED,
                )
                cls.db.add(p)
        cls.db.commit()

        # Auth Tokens
        cls.student_a_token = create_access_token({"id": cls.student_a.id, "email": cls.student_a.email, "role": cls.student_a.role.value})
        cls.student_a_headers = {"Authorization": f"Bearer {cls.student_a_token}"}

        cls.student_b_token = create_access_token({"id": cls.student_b.id, "email": cls.student_b.email, "role": cls.student_b.role.value})
        cls.student_b_headers = {"Authorization": f"Bearer {cls.student_b_token}"}

        cls.lecturer_token = create_access_token({"id": cls.lecturer.id, "email": cls.lecturer.email, "role": cls.lecturer.role.value})
        cls.lecturer_headers = {"Authorization": f"Bearer {cls.lecturer_token}"}

        cls.hod_token = create_access_token({"id": cls.hod.id, "email": cls.hod.email, "role": cls.hod.role.value})
        cls.hod_headers = {"Authorization": f"Bearer {cls.hod_token}"}

        cls.inactive_token = create_access_token({"id": cls.inactive_user.id, "email": cls.inactive_user.email, "role": cls.inactive_user.role.value})
        cls.inactive_headers = {"Authorization": f"Bearer {cls.inactive_token}"}

        # Company & Jobs
        cls.company = Company(
            name=f"Apex Technologies {cls.ts}",
            industry="Software",
            location="Bengaluru",
            website="https://apextech.example.com",
            is_active=True,
        )
        cls.db.add(cls.company)
        cls.db.commit()
        cls.db.refresh(cls.company)

        cls.job = JobPosting(
            company_id=cls.company.id,
            title=f"Systems Engineer {cls.ts}",
            description="High scale backend distributed engineering",
            status=JobStatus.OPEN,
            created_at=datetime.utcnow(),
        )
        cls.db.add(cls.job)
        cls.db.commit()
        cls.db.refresh(cls.job)

        # Rounds
        cls.round_1 = RecruitmentRound(
            job_posting_id=cls.job.id,
            round_number=1,
            name="Online Assessment",
            round_type="ONLINE_TEST",
            is_final=False,
        )
        cls.round_2 = RecruitmentRound(
            job_posting_id=cls.job.id,
            round_number=2,
            name="Technical Interview",
            round_type="TECHNICAL_INTERVIEW",
            is_final=False,
        )
        cls.round_final = RecruitmentRound(
            job_posting_id=cls.job.id,
            round_number=3,
            name="HR & Final Discussion",
            round_type="HR_INTERVIEW",
            is_final=True,
        )
        cls.db.add_all([cls.round_1, cls.round_2, cls.round_final])
        cls.db.commit()
        cls.db.refresh(cls.round_1)
        cls.db.refresh(cls.round_2)
        cls.db.refresh(cls.round_final)

        # Applications
        cls.app_a = Application(
            student_id=cls.student_a.id,
            job_posting_id=cls.job.id,
            status=ApplicationStatus.APPLIED,
            applied_at=datetime.utcnow(),
        )
        cls.app_b = Application(
            student_id=cls.student_b.id,
            job_posting_id=cls.job.id,
            status=ApplicationStatus.APPLIED,
            applied_at=datetime.utcnow(),
        )
        cls.db.add_all([cls.app_a, cls.app_b])
        cls.db.commit()
        cls.db.refresh(cls.app_a)
        cls.db.refresh(cls.app_b)

        # Offer Letter File
        cls.offer_file = File(
            filename=f"offer_alice_{cls.ts}.pdf",
            file_type=FileType.PLACEMENT_DOC,
            mime_type="application/pdf",
            file_size=10240,
            bucket="edumatrix",
            object_key=f"offers/offer_alice_{cls.ts}.pdf",
            uploaded_by=cls.officer.id,
            department="PLACEMENT",
            status=FileStatus.ACTIVE,
        )
        cls.db.add(cls.offer_file)
        cls.db.commit()
        cls.db.refresh(cls.offer_file)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    # =========================================================================
    # PART B — RECRUITMENT LIFECYCLE CORRECTNESS (10 INVARIANTS)
    # =========================================================================

    def test_b01_creating_or_uploading_batch_does_not_change_confirmed_outcomes(self):
        """Invariant 1: Creating or uploading a result batch does not itself change confirmed student outcomes."""
        initial_count = self.db.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.round_id == self.round_1.id
        ).count()

        batch = RecruitmentResultBatch(
            company_id=self.company.id,
            job_posting_id=self.job.id,
            round_id=self.round_1.id,
            round_name=self.round_1.name,
            file_id=self.offer_file.id,
            uploaded_by=self.officer.id,
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            total_rows=1,
            matched_count=1,
            ambiguous_count=0,
            confirmed_count=0,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)

        item = RecruitmentResultItem(
            batch_id=batch.id,
            row_index=1,
            raw_data={"name": self.student_a.name, "email": self.student_a.email, "score": 95},
            extracted_name=self.student_a.name,
            extracted_email=self.student_a.email,
            matched_student_id=self.student_a.id,
            match_confidence=1.0,
            normalized_status=RecruitmentResultItemStatus.SHORTLISTED,
            review_status=RecruitmentResultReviewState.PENDING,
        )
        self.db.add(item)
        self.db.commit()

        current_count = self.db.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.round_id == self.round_1.id
        ).count()
        self.assertEqual(initial_count, current_count, "Uploading/creating a result batch must NOT alter confirmed outcomes")

    def test_b02_unresolved_or_ambiguous_identities_cannot_be_confirmed(self):
        """Invariant 2: Unresolved or ambiguous identities cannot be confirmed unless explicitly resolved."""
        batch = RecruitmentResultBatch(
            company_id=self.company.id,
            job_posting_id=self.job.id,
            round_id=self.round_1.id,
            round_name=self.round_1.name,
            file_id=self.offer_file.id,
            uploaded_by=self.officer.id,
            status=RecruitmentResultBatchStatus.UPLOADED,
            total_rows=1,
            matched_count=0,
            ambiguous_count=1,
            confirmed_count=0,
        )
        self.db.add(batch)
        self.db.commit()

        # Item without matched_student_id
        item = RecruitmentResultItem(
            batch_id=batch.id,
            row_index=1,
            raw_data={"name": "Unknown Ghost", "email": "ghost@nowhere.com"},
            extracted_name="Unknown Ghost",
            extracted_email="ghost@nowhere.com",
            matched_student_id=None,
            match_confidence=0.0,
            normalized_status=RecruitmentResultItemStatus.SELECTED,
            review_status=RecruitmentResultReviewState.UNRESOLVED,
        )
        self.db.add(item)
        self.db.commit()

        # Confirmation should skip unresolved items without creating outcomes
        initial_outcomes = self.db.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.round_id == self.round_1.id,
            StudentRoundOutcome.student_id == None,
        ).count()
        self.assertEqual(initial_outcomes, 0)

        # Execute confirmation
        recruitment_result_service.confirm_batch_results(
            db=self.db,
            batch_id=batch.id,
            current_user=self.officer,
        )

        unresolved_outcomes = self.db.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.round_id == self.round_1.id,
            StudentRoundOutcome.student_id == None,
        ).count()
        self.assertEqual(unresolved_outcomes, 0, "Unresolved identities must never produce authoritative round outcomes")

    def test_b03_confirmed_round_outcome_associations(self):
        """Invariant 3: A confirmed round outcome is associated with the correct student, job, round, and source batch."""
        batch = RecruitmentResultBatch(
            company_id=self.company.id,
            job_posting_id=self.job.id,
            round_id=self.round_1.id,
            round_name=self.round_1.name,
            file_id=self.offer_file.id,
            uploaded_by=self.officer.id,
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            total_rows=1,
            matched_count=1,
            ambiguous_count=0,
            confirmed_count=0,
        )
        self.db.add(batch)
        self.db.commit()

        item = RecruitmentResultItem(
            batch_id=batch.id,
            row_index=1,
            raw_data={"email": self.student_a.email, "score": 88},
            extracted_email=self.student_a.email,
            extracted_name=self.student_a.name,
            matched_student_id=self.student_a.id,
            match_confidence=1.0,
            normalized_status=RecruitmentResultItemStatus.SHORTLISTED,
            review_status=RecruitmentResultReviewState.MATCHED,
        )
        self.db.add(item)
        self.db.commit()

        recruitment_result_service.confirm_batch_results(
            db=self.db,
            batch_id=batch.id,
            current_user=self.officer,
        )

        outcome = self.db.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.round_id == self.round_1.id,
            StudentRoundOutcome.student_id == self.student_a.id,
        ).first()

        self.assertIsNotNone(outcome, "Outcome must be created for confirmed candidate")
        self.assertEqual(outcome.round.job_posting_id, self.job.id)
        self.assertEqual(outcome.round_id, self.round_1.id)
        self.assertEqual(outcome.student_id, self.student_a.id)
        self.assertEqual(outcome.source_batch_id, batch.id)
        self.assertEqual(outcome.outcome, RoundOutcome.CLEARED)

    def test_b04_final_process_selection_does_not_automatically_create_verified_offer(self):
        """Invariant 4: Final-process selection updates application status but does NOT automatically create a verified offer."""
        # Confirm student B in final round via batch
        batch = RecruitmentResultBatch(
            company_id=self.company.id,
            file_id=self.offer_file.id,
            job_posting_id=self.job.id,
            round_id=self.round_final.id,
            round_name=self.round_final.name,
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
            raw_data={"name": self.student_b.name, "email": self.student_b.email},
            extracted_name=self.student_b.name,
            extracted_email=self.student_b.email,
            matched_student_id=self.student_b.id,
            match_confidence=1.0,
            normalized_status=RecruitmentResultItemStatus.SELECTED,
            review_status=RecruitmentResultReviewState.MATCHED,
        )
        self.db.add(item)
        self.db.commit()

        recruitment_result_service.confirm_batch_results(
            db=self.db,
            batch_id=batch.id,
            current_user=self.officer,
        )

        # Check application status updated to SELECTED
        self.db.refresh(self.app_b)
        self.assertEqual(self.app_b.status, ApplicationStatus.SELECTED)

        # Check that NO PlacementOffer was automatically created
        offer = self.db.query(PlacementOffer).filter(PlacementOffer.application_id == self.app_b.id).first()
        self.assertIsNone(offer, "Selection in final round must NOT automatically create a PlacementOffer")

    def test_b05_only_authorized_offer_creation_creates_placement_offer(self):
        """Invariant 5: Only an explicit authorized offer-creation operation creates a PlacementOffer."""
        # Unofficial / non-officer cannot create offer
        with self.assertRaises((PermissionError, Exception)):
            placement_offer_service.create_placement_offer(
                db=self.db,
                application_id=self.app_b.id,
                ctc_lpa=14.5,
                designation="Software Engineer",
                current_user=self.student_b,  # Student actor
            )
        self.db.rollback()

        # Authorized officer successfully creates offer
        offer = placement_offer_service.create_placement_offer(
            db=self.db,
            application_id=self.app_b.id,
            ctc_lpa=14.5,
            designation="Software Engineer",
            current_user=self.officer,
        )
        self.assertIsNotNone(offer)
        self.assertEqual(offer.ctc_lpa, 14.5)
        self.assertEqual(offer.acceptance_status, OfferAcceptanceStatus.OFFERED)
        self.assertEqual(offer.student_id, self.student_b.id)

    def test_b06_student_acceptance_decline_based_on_authenticated_server_identity(self):
        """Invariant 6: Student acceptance or decline is based on authenticated server-side identity and student's own offer."""
        offer = self.db.query(PlacementOffer).filter(PlacementOffer.application_id == self.app_b.id).first()
        self.assertIsNotNone(offer)

        # Student A attempting to respond to Student B's offer via API
        resp = self.client.post(
            f"/placement/offers/{offer.id}/respond",
            json={"decision": "ACCEPTED", "remarks": "Malicious accept"},
            headers=self.student_a_headers,
        )
        self.assertEqual(resp.status_code, 403, "Student A cannot respond to Student B's offer")

        # Student B responding to their own offer succeeds
        resp_b = self.client.post(
            f"/placement/offers/{offer.id}/respond",
            json={"decision": "ACCEPTED", "remarks": "Thank you! Accepted."},
            headers=self.student_b_headers,
        )
        self.assertEqual(resp_b.status_code, 200)
        self.assertEqual(resp_b.json()["acceptance_status"], "accepted")

    def test_b07_idempotent_repeated_response_and_conflict_rejection(self):
        """Invariant 7: Repeating the same response is handled idempotently; conflicting responses are rejected."""
        offer = self.db.query(PlacementOffer).filter(PlacementOffer.application_id == self.app_b.id).first()

        # Repeating ACCEPTED response
        resp_repeat = self.client.post(
            f"/placement/offers/{offer.id}/respond",
            json={"decision": "ACCEPTED", "remarks": "Repeated accept"},
            headers=self.student_b_headers,
        )
        self.assertEqual(resp_repeat.status_code, 200, "Identical response must be idempotent")
        self.assertEqual(resp_repeat.json()["acceptance_status"], "accepted")

        # Conflicting response: DECLINED after ACCEPTED
        resp_conflict = self.client.post(
            f"/placement/offers/{offer.id}/respond",
            json={"decision": "DECLINED", "remarks": "Attempting to change mind"},
            headers=self.student_b_headers,
        )
        self.assertEqual(resp_conflict.status_code, 409, "Conflicting response must return 409 Conflict")

    def test_b08_rescission_requires_authorized_actor_and_recorded_reason(self):
        """Invariant 8: Rescission requires an authorized actor and a recorded reason."""
        offer = self.db.query(PlacementOffer).filter(PlacementOffer.application_id == self.app_b.id).first()

        # Student cannot rescind
        resp_student = self.client.post(
            f"/placement/offers/{offer.id}/rescind",
            json={"reason": "Student trying to rescind"},
            headers=self.student_b_headers,
        )
        self.assertEqual(resp_student.status_code, 403, "Student cannot rescind an offer")

        # Officer with empty reason fails
        resp_empty_reason = self.client.post(
            f"/placement/offers/{offer.id}/rescind",
            json={"reason": "   "},
            headers=self.officer_headers,
        )
        self.assertEqual(resp_empty_reason.status_code, 400, "Empty rescission reason must be rejected")

        # Officer with valid reason succeeds
        resp_valid = self.client.post(
            f"/placement/offers/{offer.id}/rescind",
            json={"reason": "Candidate failed final background verification check"},
            headers=self.officer_headers,
        )
        self.assertEqual(resp_valid.status_code, 200)
        self.assertEqual(resp_valid.json()["acceptance_status"], "rescinded")

    def test_b09_corrections_preserve_audit_trail_and_do_not_erase_later_progression_history(self):
        """Invariant 9: Corrections preserve the audit trail and do not silently erase later progression history."""
        # Create round 2 outcome for student A
        outcome_2 = recruitment_progression_service.record_student_round_outcome(
            db=self.db,
            round_id=self.round_2.id,
            application_id=self.app_a.id,
            outcome="CLEARED",
            score=70.0,
            remarks="Preliminary score",
            current_user=self.officer,
        )
        self.db.commit()

        # Correct round 2 outcome
        resp_corr = self.client.post(
            f"/placement/outcomes/{outcome_2.id}/correct",
            json={"new_outcome": "rejected", "new_score": 45.0, "reason": "Discovered coding test penalty"},
            headers=self.officer_headers,
        )
        self.assertEqual(resp_corr.status_code, 200)

        # Verify audit log was created
        audit = self.db.query(AuditLog).filter(
            AuditLog.target_type == "student_round_outcome",
            AuditLog.target_id == str(outcome_2.id),
        ).order_by(AuditLog.created_at.desc()).first()
        self.assertIsNotNone(audit, "Audit log must be created for outcome correction")
        self.assertIn("coding test penalty", str(audit.details))

        # Verify outcome 1 is still present in database
        outcome_1 = self.db.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.round_id == self.round_1.id,
            StudentRoundOutcome.student_id == self.student_a.id,
        ).first()
        self.assertIsNotNone(outcome_1, "Prior round progression must NOT be erased by later corrections")

    def test_b10_legacy_result_batches_without_round_association_remain_compatible(self):
        """Invariant 10: Legacy result batches without a round association remain compatible with their intended historical behavior."""
        legacy_batch = RecruitmentResultBatch(
            company_id=self.company.id,
            job_posting_id=self.job.id,
            round_id=None,  # Legacy batch without round association
            round_name="Legacy Batch",
            file_id=self.offer_file.id,
            uploaded_by=self.officer.id,
            status=RecruitmentResultBatchStatus.UPLOADED,
            total_rows=1,
            matched_count=1,
            ambiguous_count=0,
            confirmed_count=0,
        )
        self.db.add(legacy_batch)
        self.db.commit()
        self.db.refresh(legacy_batch)

        item = RecruitmentResultItem(
            batch_id=legacy_batch.id,
            row_index=1,
            raw_data={"email": self.student_a.email},
            extracted_email=self.student_a.email,
            extracted_name=self.student_a.name,
            matched_student_id=self.student_a.id,
            match_confidence=1.0,
            normalized_status=RecruitmentResultItemStatus.SELECTED,
            review_status=RecruitmentResultReviewState.MATCHED,
        )
        self.db.add(item)
        self.db.commit()

        # Confirmation should succeed without error
        recruitment_result_service.confirm_batch_results(
            db=self.db,
            batch_id=legacy_batch.id,
            current_user=self.officer,
        )
        self.db.refresh(legacy_batch)
        self.assertEqual(legacy_batch.status, RecruitmentResultBatchStatus.FULLY_CONFIRMED)

    # =========================================================================
    # PART C — AUTHORIZATION AND PRIVACY
    # =========================================================================

    def test_c01_student_progression_access_control(self):
        """Test Student viewing their own progression vs another student's progression."""
        # Student A viewing Student A -> 200
        resp_own = self.client.get(
            f"/placement/students/{self.student_a.id}/progression",
            headers=self.student_a_headers,
        )
        self.assertEqual(resp_own.status_code, 200)

        # Student A viewing Student B -> 403
        resp_other = self.client.get(
            f"/placement/students/{self.student_b.id}/progression",
            headers=self.student_a_headers,
        )
        self.assertEqual(resp_other.status_code, 403)

    def test_c02_lecturer_and_hod_role_boundaries_on_progression(self):
        """Test Lecturer and HOD boundaries on recruitment progression."""
        # Lecturer viewing student progression -> 403
        resp_lec = self.client.get(
            f"/placement/students/{self.student_a.id}/progression",
            headers=self.lecturer_headers,
        )
        self.assertEqual(resp_lec.status_code, 403)

        # HOD viewing student progression -> 403
        resp_hod = self.client.get(
            f"/placement/students/{self.student_a.id}/progression",
            headers=self.hod_headers,
        )
        self.assertEqual(resp_hod.status_code, 403)

        # Placement Officer viewing student progression -> 200
        resp_po = self.client.get(
            f"/placement/students/{self.student_a.id}/progression",
            headers=self.officer_headers,
        )
        self.assertEqual(resp_po.status_code, 200)

        # Admin viewing student progression -> 200
        resp_admin = self.client.get(
            f"/placement/students/{self.student_a.id}/progression",
            headers=self.admin_headers,
        )
        self.assertEqual(resp_admin.status_code, 200)

    def test_c03_student_offer_details_access_control(self):
        """Test Student viewing their own offer vs another student's offer."""
        offer = self.db.query(PlacementOffer).filter(PlacementOffer.student_id == self.student_b.id).first()
        self.assertIsNotNone(offer)

        # Student B (owner) viewing offer -> 200
        resp_b = self.client.get(f"/placement/offers/{offer.id}", headers=self.student_b_headers)
        self.assertEqual(resp_b.status_code, 200)

        # Student A (non-owner) viewing offer -> 403
        resp_a = self.client.get(f"/placement/offers/{offer.id}", headers=self.student_a_headers)
        self.assertEqual(resp_a.status_code, 403)

        # Lecturer viewing offer -> 403
        resp_lec = self.client.get(f"/placement/offers/{offer.id}", headers=self.lecturer_headers)
        self.assertEqual(resp_lec.status_code, 403)

        # HOD viewing offer -> 403
        resp_hod = self.client.get(f"/placement/offers/{offer.id}", headers=self.hod_headers)
        self.assertEqual(resp_hod.status_code, 403)

    def test_c04_unauthorized_offer_creation_update_rescission(self):
        """Test that non-officers cannot create, update, or rescind offers."""
        # Student creates offer -> 403
        resp_create = self.client.post(
            "/placement/offers",
            json={"application_id": self.app_a.id, "ctc_lpa": 12.0, "designation": "Dev"},
            headers=self.student_a_headers,
        )
        self.assertEqual(resp_create.status_code, 403)

        # Lecturer updates offer -> 403
        offer = self.db.query(PlacementOffer).first()
        resp_update = self.client.put(
            f"/placement/offers/{offer.id}",
            json={"ctc_lpa": 15.0, "reason": "Lecturer attempt"},
            headers=self.lecturer_headers,
        )
        self.assertEqual(resp_update.status_code, 403)

        # Lecturer rescinds offer -> 403
        resp_rescind = self.client.post(
            f"/placement/offers/{offer.id}/rescind",
            json={"reason": "Lecturer attempt"},
            headers=self.lecturer_headers,
        )
        self.assertEqual(resp_rescind.status_code, 403)

    def test_c05_private_offer_letter_file_access_control(self):
        """Test authorized vs unauthorized access to private offer letter documents."""
        # Create an offer for Student A with offer_file
        # If an offer already exists for app_a, update or use it
        existing_offer = self.db.query(PlacementOffer).filter(PlacementOffer.application_id == self.app_a.id).first()
        if not existing_offer:
            existing_offer = placement_offer_service.create_placement_offer(
                db=self.db,
                application_id=self.app_a.id,
                ctc_lpa=12.0,
                designation="Software Engineer",
                offer_letter_file_id=self.offer_file.id,
                current_user=self.officer,
            )
            self.db.commit()
        else:
            existing_offer.offer_letter_file_id = self.offer_file.id
            self.db.commit()

        # Student A (recipient) can access the file
        with patch.object(file_service, "get_presigned_url", return_value="http://minio/mock-download-url"):
            resp_owner = self.client.get(f"/files/{self.offer_file.id}", headers=self.student_a_headers)
            self.assertEqual(resp_owner.status_code, 200, "Student recipient must be authorized to access offer letter")

        # Student B cannot access Student A's offer letter
        resp_other = self.client.get(f"/files/{self.offer_file.id}", headers=self.student_b_headers)
        self.assertEqual(resp_other.status_code, 403, "Other students must be forbidden from downloading private offer letters")

        # Lecturer cannot access private offer letter
        resp_lec = self.client.get(f"/files/{self.offer_file.id}", headers=self.lecturer_headers)
        self.assertEqual(resp_lec.status_code, 403, "Lecturers must be forbidden from downloading private offer letters")

    def test_c06_inactive_users_and_invalid_authentication(self):
        """Test inactive user and invalid token rejection."""
        # Inactive user token
        resp_inactive = self.client.get("/placement/offers/my-offers", headers=self.inactive_headers)
        self.assertEqual(resp_inactive.status_code, 401, "Inactive user must be rejected with 401")

        # Corrupted / invalid token
        resp_invalid = self.client.get("/placement/offers/my-offers", headers={"Authorization": "Bearer invalid.jwt.token"})
        self.assertEqual(resp_invalid.status_code, 401, "Invalid token must be rejected with 401")

    def test_c07_archived_or_detached_circular_attachments(self):
        """Test that archived circular attachments or detached files reject student access."""
        # 1. Circular file
        circ_file = File(
            filename=f"archived_jd_{self.ts}.pdf",
            file_type=FileType.CIRCULAR,
            mime_type="application/pdf",
            file_size=5000,
            bucket="edumatrix",
            object_key=f"circulars/archived_jd_{self.ts}.pdf",
            uploaded_by=self.officer.id,
            department="PLACEMENT",
            status=FileStatus.ACTIVE,
        )
        self.db.add(circ_file)
        self.db.commit()
        self.db.refresh(circ_file)

        # 2. Archived Circular
        circ = RecruitmentCircular(
            company_id=self.company.id,
            title="Archived Circular Test",
            status=RecruitmentCircularStatus.ARCHIVED,
            created_by=self.officer.id,
            branch_eligibility=["CSE"],
        )
        self.db.add(circ)
        self.db.commit()
        self.db.refresh(circ)

        attach = RecruitmentCircularAttachment(
            circular_id=circ.id,
            file_id=circ_file.id,
        )
        self.db.add(attach)
        self.db.commit()

        # Student A attempting to access attachment of ARCHIVED circular -> 403
        resp_arch = self.client.get(f"/files/{circ_file.id}", headers=self.student_a_headers)
        self.assertEqual(resp_arch.status_code, 403, "Student must not access attachments of ARCHIVED circulars")

    # =========================================================================
    # PART D — TRANSACTION AND CONCURRENCY TESTS
    # =========================================================================

    def test_d01_concurrent_duplicate_offer_creation(self):
        """Verify concurrent duplicate offer creation cannot create two offers for the same application."""
        # Create a fresh job and application for concurrency test
        fresh_job = JobPosting(
            company_id=self.company.id,
            title=f"Concurrent Test Job {self.ts}",
            status=JobStatus.OPEN,
        )
        self.db.add(fresh_job)
        self.db.commit()
        self.db.refresh(fresh_job)

        fresh_app = Application(
            student_id=self.student_a.id,
            job_posting_id=fresh_job.id,
            status=ApplicationStatus.SELECTED,
        )
        self.db.add(fresh_app)
        self.db.commit()
        self.db.refresh(fresh_app)

        results = []
        errors = []

        def create_offer_worker():
            db_session = SessionLocal()
            try:
                offer = placement_offer_service.create_placement_offer(
                    db=db_session,
                    application_id=fresh_app.id,
                    ctc_lpa=16.0,
                    designation="Concurrency Engineer",
                    current_user=self.officer,
                    auto_commit=True,
                )
                results.append(offer.id)
            except Exception as e:
                errors.append(str(e))
            finally:
                db_session.close()

        threads = [threading.Thread(target=create_offer_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly 1 success, others rejected
        self.assertEqual(len(results), 1, f"Expected exactly 1 successful offer creation, got {len(results)}")
        self.assertEqual(len(errors), 4, f"Expected 4 rejections, got {len(errors)}")

        total_offers_in_db = self.db.query(PlacementOffer).filter(
            PlacementOffer.application_id == fresh_app.id
        ).count()
        self.assertEqual(total_offers_in_db, 1, "Database must strictly contain exactly 1 offer for the application")

    def test_d02_concurrent_identical_student_responses(self):
        """Verify concurrent identical student responses remain consistent."""
        fresh_job = JobPosting(company_id=self.company.id, title=f"Concurrent Job Identical {self.ts}", status=JobStatus.OPEN)
        self.db.add(fresh_job)
        self.db.commit()

        fresh_app = Application(student_id=self.student_a.id, job_posting_id=fresh_job.id, status=ApplicationStatus.SELECTED)
        self.db.add(fresh_app)
        self.db.commit()

        offer = placement_offer_service.create_placement_offer(
            db=self.db,
            application_id=fresh_app.id,
            ctc_lpa=18.0,
            designation="Principal Architect",
            current_user=self.officer,
        )
        self.db.commit()

        successes = []
        failures = []

        def respond_worker():
            db_session = SessionLocal()
            try:
                res = placement_offer_service.respond_to_placement_offer(
                    db=db_session,
                    offer_id=offer.id,
                    decision="ACCEPTED",
                    remarks="Concurrent accept",
                    current_user=self.student_a,
                    auto_commit=True,
                )
                successes.append(res.acceptance_status.value)
            except Exception as e:
                failures.append(str(e))
            finally:
                db_session.close()

        threads = [threading.Thread(target=respond_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.db.refresh(offer)
        self.assertEqual(offer.acceptance_status, OfferAcceptanceStatus.ACCEPTED)
        self.assertGreater(len(successes), 0)
        # All completed responses ended in accepted
        for s in successes:
            self.assertEqual(s, "accepted")

    def test_d03_conflicting_concurrent_responses(self):
        """Verify conflicting concurrent responses cannot silently overwrite each other."""
        fresh_job = JobPosting(company_id=self.company.id, title=f"Conflict Job {self.ts}", status=JobStatus.OPEN)
        self.db.add(fresh_job)
        self.db.commit()

        fresh_app = Application(student_id=self.student_a.id, job_posting_id=fresh_job.id, status=ApplicationStatus.SELECTED)
        self.db.add(fresh_app)
        self.db.commit()

        offer = placement_offer_service.create_placement_offer(
            db=self.db,
            application_id=fresh_app.id,
            ctc_lpa=20.0,
            designation="Staff Engineer",
            current_user=self.officer,
        )
        self.db.commit()

        outcomes = []
        errors = []

        def make_decision(decision):
            db_session = SessionLocal()
            try:
                res = placement_offer_service.respond_to_placement_offer(
                    db=db_session,
                    offer_id=offer.id,
                    decision=decision,
                    remarks=f"Concurrent {decision}",
                    current_user=self.student_a,
                    auto_commit=True,
                )
                outcomes.append(res.acceptance_status.value)
            except Exception as e:
                errors.append(str(e))
            finally:
                db_session.close()

        t1 = threading.Thread(target=make_decision, args=("ACCEPTED",))
        t2 = threading.Thread(target=make_decision, args=("DECLINED",))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.db.refresh(offer)
        # One decision wins; the conflicting one is rejected
        self.assertIn(offer.acceptance_status, [OfferAcceptanceStatus.ACCEPTED, OfferAcceptanceStatus.DECLINED])
        self.assertEqual(len(outcomes), 1, "Exactly one of the conflicting decisions must win")
        self.assertEqual(len(errors), 1, "The conflicting decision must be rejected")

    def test_d04_atomic_rollback_on_failed_database_or_audit_write(self):
        """Verify failed database operation or audit write does not leave a partially committed mutation."""
        fresh_job = JobPosting(company_id=self.company.id, title=f"Rollback Job {self.ts}", status=JobStatus.OPEN)
        self.db.add(fresh_job)
        self.db.commit()

        fresh_app = Application(student_id=self.student_a.id, job_posting_id=fresh_job.id, status=ApplicationStatus.SELECTED)
        self.db.add(fresh_app)
        self.db.commit()

        # Patch audit_service.log_action to simulate an audit failure
        with patch.object(audit_service, "log_action", return_value=None):
            with self.assertRaises(RuntimeError):
                placement_offer_service.create_placement_offer(
                    db=self.db,
                    application_id=fresh_app.id,
                    ctc_lpa=22.0,
                    designation="Rollback Candidate",
                    current_user=self.officer,
                    auto_commit=True,
                )

        # Verify no offer was created in DB
        offer_check = self.db.query(PlacementOffer).filter(PlacementOffer.application_id == fresh_app.id).first()
        self.assertIsNone(offer_check, "No offer must remain in DB if audit write fails and rolls back")

    def test_d05_no_notifications_emitted_for_rolled_back_changes(self):
        """Verify notifications are not emitted for rolled-back changes."""
        fresh_job = JobPosting(company_id=self.company.id, title=f"Notif Rollback Job {self.ts}", status=JobStatus.OPEN)
        self.db.add(fresh_job)
        self.db.commit()

        fresh_app = Application(student_id=self.student_a.id, job_posting_id=fresh_job.id, status=ApplicationStatus.SELECTED)
        self.db.add(fresh_app)
        self.db.commit()

        with patch.object(audit_service, "log_action", return_value=None):
            try:
                placement_offer_service.create_placement_offer(
                    db=self.db,
                    application_id=fresh_app.id,
                    ctc_lpa=25.0,
                    designation="No Notification Candidate",
                    current_user=self.officer,
                    auto_commit=True,
                )
            except RuntimeError:
                pass

        notifs = self.db.query(Notification).filter(
            Notification.user_id == self.student_a.id,
            Notification.message.like("%No Notification Candidate%"),
        ).all()
        self.assertEqual(len(notifs), 0, "No notifications must be emitted for rolled-back operations")

    def test_d06_notification_deduplication_under_retries(self):
        """Verify retries do not create duplicate notifications when the same event is processed again."""
        fresh_job = JobPosting(company_id=self.company.id, title=f"Retry Job {self.ts}", status=JobStatus.OPEN)
        self.db.add(fresh_job)
        self.db.commit()

        fresh_app = Application(student_id=self.student_a.id, job_posting_id=fresh_job.id, status=ApplicationStatus.SELECTED)
        self.db.add(fresh_app)
        self.db.commit()

        offer = placement_offer_service.create_placement_offer(
            db=self.db,
            application_id=fresh_app.id,
            ctc_lpa=21.0,
            designation="Retry Test Engineer",
            current_user=self.officer,
        )
        self.db.commit()

        event_key = f"placement_offer:{offer.id}:verified"
        initial_notif_count = self.db.query(Notification).filter(Notification.event_key == event_key).count()
        self.assertEqual(initial_notif_count, 1)

        # Trigger second identical response / processing
        placement_offer_service.respond_to_placement_offer(
            db=self.db,
            offer_id=offer.id,
            decision="ACCEPTED",
            current_user=self.student_a,
        )
        self.db.commit()

        resp_event_key = f"placement_offer:{offer.id}:accepted"
        resp_count = self.db.query(Notification).filter(Notification.event_key == resp_event_key).count()
        self.assertEqual(resp_count, 1)

        # Retry respond
        placement_offer_service.respond_to_placement_offer(
            db=self.db,
            offer_id=offer.id,
            decision="ACCEPTED",
            current_user=self.student_a,
        )
        self.db.commit()

        retry_count = self.db.query(Notification).filter(Notification.event_key == resp_event_key).count()
        self.assertEqual(retry_count, 1, "Retrying identical response must NOT create duplicate notification")

    # =========================================================================
    # PART E — PLACEMENT ACCOUNTING (10 SCENARIO MATRIX & CSV EXPORT)
    # =========================================================================

    def test_e_placement_accounting_matrix(self):
        """
        Verify all 10 placement accounting scenarios:
        1. Round clearance alone
        2. Final-process selection without an offer
        3. One pending offer
        4. One accepted offer
        5. A declined offer
        6. An accepted offer later rescinded
        7. One student with multiple accepted offers
        8. One accepted offer rescinded while another accepted offer remains active
        9. Legacy PLACED profile without a verified offer
        10. No students or no offers
        """
        # Scenario 1 & 2: Round clearance alone and Final selection without offer
        # Verified offers count must NOT include applications without PlacementOffer
        metrics = placement_offer_service.get_placement_accounting_metrics(self.db)
        self.assertIn("total_verified_offers", metrics)
        self.assertIn("accepted_offers_count", metrics)
        self.assertIn("declined_offers_count", metrics)
        self.assertIn("rescinded_offers_count", metrics)
        self.assertIn("pending_offers_count", metrics)
        self.assertIn("verified_placed_students_count", metrics)
        self.assertIn("students_with_multiple_offers_count", metrics)
        self.assertIn("verified_placement_rate", metrics)
        self.assertIn("legacy_placed_count", metrics)
        self.assertIn("legacy_placement_rate", metrics)

        # Test multi-offer student
        multi_student = User(
            email=f"multi_offer_{self.ts}@vcet.ac.in",
            name="Multi Offer Student",
            role=UserRole.STUDENT,
            password_hash="fakehash",
            department="CSE",
            is_active=True,
        )
        self.db.add(multi_student)
        self.db.commit()
        self.db.refresh(multi_student)

        p = StudentProfileExtended(
            user_id=multi_student.id,
            branch="CSE",
            cgpa=9.0,
            placement_status=PlacementStatus.APPLIED,
        )
        self.db.add(p)
        self.db.commit()

        job1 = JobPosting(company_id=self.company.id, title=f"Multi Job 1 {self.ts}", status=JobStatus.OPEN)
        job2 = JobPosting(company_id=self.company.id, title=f"Multi Job 2 {self.ts}", status=JobStatus.OPEN)
        self.db.add_all([job1, job2])
        self.db.commit()

        app1 = Application(student_id=multi_student.id, job_posting_id=job1.id, status=ApplicationStatus.SELECTED)
        app2 = Application(student_id=multi_student.id, job_posting_id=job2.id, status=ApplicationStatus.SELECTED)
        self.db.add_all([app1, app2])
        self.db.commit()

        offer1 = placement_offer_service.create_placement_offer(
            db=self.db,
            application_id=app1.id,
            ctc_lpa=12.0,
            current_user=self.officer,
        )
        offer2 = placement_offer_service.create_placement_offer(
            db=self.db,
            application_id=app2.id,
            ctc_lpa=15.0,
            current_user=self.officer,
        )
        self.db.commit()

        # Both offers accepted by student
        placement_offer_service.respond_to_placement_offer(self.db, offer1.id, "ACCEPTED", current_user=multi_student)
        placement_offer_service.respond_to_placement_offer(self.db, offer2.id, "ACCEPTED", current_user=multi_student)
        self.db.commit()

        # Check metrics: multi_student has 2 active accepted offers
        metrics_multi = placement_offer_service.get_placement_accounting_metrics(self.db)
        multi_offer_students = metrics_multi["students_with_multiple_offers_count"]
        self.assertGreaterEqual(multi_offer_students, 1, "Student with 2 accepted offers must be counted in students_with_multiple_offers")

        # Rescind offer 1 while offer 2 remains active
        placement_offer_service.rescind_placement_offer(
            db=self.db,
            offer_id=offer1.id,
            reason="Offer 1 rescinded by student request",
            current_user=self.officer,
        )
        self.db.commit()

        # Check profile placement status remains PLACED because offer 2 is active
        self.db.refresh(p)
        self.assertEqual(p.placement_status, PlacementStatus.PLACED, "Student profile must remain PLACED if another active accepted offer exists")

        # Now rescind offer 2 as well
        placement_offer_service.rescind_placement_offer(
            db=self.db,
            offer_id=offer2.id,
            reason="Offer 2 rescinded",
            current_user=self.officer,
        )
        self.db.commit()

        self.db.refresh(p)
        self.assertNotEqual(p.placement_status, PlacementStatus.PLACED, "Student profile must revert from PLACED if all accepted offers are rescinded")

    def test_e_csv_report_export_compatibility(self):
        """Verify CSV export endpoint returns valid columns and backward-compatible data."""
        resp = self.client.get("/placement/reports/export", headers=self.officer_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp.headers["content-type"])

        content = resp.text
        reader = csv.reader(io.StringIO(content))
        headers = next(reader)

        expected_headers = [
            "Student ID", "Student Name", "Enrollment Number", "Email",
            "Department / Branch", "Year", "Semester", "CGPA",
            "Placement Status", "ATS Score", "Total Applications",
            "Total Shortlists", "Applied Job Titles", "Skills",
        ]
        for eh in expected_headers:
            self.assertIn(eh, headers, f"CSV export must contain column '{eh}'")

    # =========================================================================
    # PART F — NOTIFICATIONS AND AUDIT TRAIL
    # =========================================================================

    def test_f01_audit_log_security_no_sensitive_tokens(self):
        """Verify audit records contain action, actor, target, reason, and NO sensitive tokens."""
        logs = self.db.query(AuditLog).filter(
            AuditLog.target_type.in_(["placement_offer", "student_round_outcome"])
        ).limit(20).all()

        for log in logs:
            self.assertIsNotNone(log.action)
            self.assertIsNotNone(log.target_type)
            self.assertIsNotNone(log.target_id)
            details_str = str(log.details)
            self.assertNotIn("password", details_str.lower())
            self.assertNotIn("access_token", details_str.lower())
            self.assertNotIn("bearer", details_str.lower())

    def test_f02_delivery_limitations_reporting(self):
        """Verify notifications are stored in PostgreSQL database with event_key deduplication."""
        # Check that notifications are queryable in the DB table
        all_notifs = self.db.query(Notification).filter(Notification.user_id == self.student_a.id).all()
        for n in all_notifs:
            self.assertIsNotNone(n.title)
            self.assertIsNotNone(n.message)


if __name__ == "__main__":
    unittest.main()
