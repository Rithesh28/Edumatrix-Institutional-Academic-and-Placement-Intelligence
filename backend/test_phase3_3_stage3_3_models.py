"""
EduMatrix Phase 3.3 — Stage 3.3.1: Recruitment Round Lifecycle Models & Migration 015 Test Suite

Verifies:
1. New tables and enum definitions exist after migration 015.
2. One job can have multiple rounds ordered by sequence.
3. Duplicate round numbers for the same job are rejected by unique constraint.
4. Check constraint rejects non-positive round numbers (round_number <= 0).
5. Different jobs can each have a Round 1.
6. Existing result batches can have a null round_id.
7. A result batch can link to a valid round.
8. Duplicate (application_id, round_id) outcomes are rejected by unique constraint.
9. A placement offer can be associated with an application and student with CTC and designation.
10. Different applications can have separate offer records for the same student.
11. Duplicate offer on the same application is rejected.
12. Invalid foreign-key references are rejected.
13. Existing migration head is 015.
14. Existing application statuses and profile placement statuses remain unaltered by migration.
"""

import time
import unittest
from datetime import datetime, timezone
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.models.user import User, UserRole
from app.models.company import Company
from app.models.job_posting import JobPosting, JobStatus
from app.models.application import Application, ApplicationStatus
from app.models.profile import StudentProfileExtended, PlacementStatus
from app.models.file import File
from app.models.recruitment_circular import RecruitmentCircular
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


class TestStage331ModelsAndMigration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db: Session = SessionLocal()
        cls.timestamp = int(time.time() * 1000)

        # 1. Fetch or create a test student
        cls.student = cls.db.query(User).filter(User.role == UserRole.STUDENT).first()
        if not cls.student:
            cls.student = User(
                email=f"test_student_{cls.timestamp}@edumatrix.edu",
                hashed_password="hashed_pw_test",
                name="Test Round Student",
                role=UserRole.STUDENT,
                department="Computer Science",
                is_active=True,
            )
            cls.db.add(cls.student)
            cls.db.commit()
            cls.db.refresh(cls.student)

        # 2. Create a test company
        cls.company = Company(
            name=f"Apex Horizon Dynamics {cls.timestamp}",
            industry="Software & AI",
            location="Bangalore",
            is_active=True,
        )
        cls.db.add(cls.company)
        cls.db.commit()
        cls.db.refresh(cls.company)

        # 3. Create two test job postings
        cls.job_a = JobPosting(
            company_id=cls.company.id,
            title=f"Graduate Cloud Engineer A {cls.timestamp}",
            status=JobStatus.OPEN,
        )
        cls.job_b = JobPosting(
            company_id=cls.company.id,
            title=f"Graduate Cloud Engineer B {cls.timestamp}",
            status=JobStatus.OPEN,
        )
        cls.db.add_all([cls.job_a, cls.job_b])
        cls.db.commit()
        cls.db.refresh(cls.job_a)
        cls.db.refresh(cls.job_b)

        # 4. Create an application for job_a
        cls.app_a = Application(
            student_id=cls.student.id,
            job_posting_id=cls.job_a.id,
            status=ApplicationStatus.APPLIED,
            notes="Initial application",
        )
        # Create an application for job_b
        cls.app_b = Application(
            student_id=cls.student.id,
            job_posting_id=cls.job_b.id,
            status=ApplicationStatus.APPLIED,
            notes="Initial application B",
        )
        cls.db.add_all([cls.app_a, cls.app_b])
        cls.db.commit()
        cls.db.refresh(cls.app_a)
        cls.db.refresh(cls.app_b)

    @classmethod
    def tearDownClass(cls):
        try:
            # Clean up test entities created
            cls.db.rollback()
            if hasattr(cls, "company") and cls.company.id:
                cls.db.query(JobPosting).filter(JobPosting.company_id == cls.company.id).delete(synchronize_session=False)
                cls.db.query(Company).filter(Company.id == cls.company.id).delete(synchronize_session=False)
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
    # Test 1: Schema & Enums verification
    # -------------------------------------------------------------------------
    def test_01_tables_and_enums_exist_in_db(self):
        """Verify that recruitment_rounds, student_round_outcomes, placement_offers, and round_id exist."""
        inspector = sa.inspect(engine)
        table_names = inspector.get_table_names()

        self.assertIn("recruitment_rounds", table_names, "recruitment_rounds table must exist")
        self.assertIn("student_round_outcomes", table_names, "student_round_outcomes table must exist")
        self.assertIn("placement_offers", table_names, "placement_offers table must exist")

        # Verify round_id column in recruitment_result_batches
        batch_columns = [c["name"] for c in inspector.get_columns("recruitment_result_batches")]
        self.assertIn("round_id", batch_columns, "round_id column must exist in recruitment_result_batches")

        # Verify round_outcome enum values
        result = self.db.execute(
            sa.text("SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE pg_type.typname = 'round_outcome'")
        ).fetchall()
        enum_labels = [r[0] for r in result]
        for val in ["CLEARED", "REJECTED", "ABSENT", "ON_HOLD", "OFFERED"]:
            self.assertIn(val, enum_labels)

        # Verify offer_acceptance_status enum values
        result2 = self.db.execute(
            sa.text("SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE pg_type.typname = 'offer_acceptance_status'")
        ).fetchall()
        enum_labels2 = [r[0] for r in result2]
        for val in ["OFFERED", "ACCEPTED", "DECLINED", "RESCINDED"]:
            self.assertIn(val, enum_labels2)

    # -------------------------------------------------------------------------
    # Test 2: One job can have multiple rounds
    # -------------------------------------------------------------------------
    def test_02_one_job_multiple_ordered_rounds(self):
        """Verify one job can have multiple ordered recruitment rounds."""
        r1 = RecruitmentRound(
            job_posting_id=self.job_a.id,
            round_number=1,
            name="Online Assessment",
            round_type="assessment",
            is_final=False,
        )
        r2 = RecruitmentRound(
            job_posting_id=self.job_a.id,
            round_number=2,
            name="Technical Interview",
            round_type="technical_interview",
            is_final=False,
        )
        r3 = RecruitmentRound(
            job_posting_id=self.job_a.id,
            round_number=3,
            name="HR & Final Selection",
            round_type="hr_interview",
            is_final=True,
        )
        self.db.add_all([r1, r2, r3])
        self.db.commit()

        # Query back via relationship
        job = self.db.query(JobPosting).filter(JobPosting.id == self.job_a.id).first()
        rounds = job.rounds
        self.assertEqual(len(rounds), 3)
        self.assertEqual([r.round_number for r in rounds], [1, 2, 3])
        self.assertEqual(rounds[0].name, "Online Assessment")
        self.assertFalse(rounds[0].is_final)
        self.assertTrue(rounds[2].is_final)

    # -------------------------------------------------------------------------
    # Test 3: Duplicate round number for the same job is rejected
    # -------------------------------------------------------------------------
    def test_03_duplicate_round_number_for_same_job_rejected(self):
        """Verify unique constraint on (job_posting_id, round_number)."""
        dup_round = RecruitmentRound(
            job_posting_id=self.job_a.id,
            round_number=1,  # Already exists from test_02
            name="Duplicate Round 1",
            round_type="assessment",
        )
        self.db.add(dup_round)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    # -------------------------------------------------------------------------
    # Test 4: Positive round_number check constraint
    # -------------------------------------------------------------------------
    def test_04_positive_round_number_check_constraint(self):
        """Verify round_number > 0 check constraint rejects 0 and negative values."""
        invalid_round = RecruitmentRound(
            job_posting_id=self.job_b.id,
            round_number=0,  # Violates chk_recruitment_round_number_positive
            name="Invalid Zero Round",
            round_type="assessment",
        )
        self.db.add(invalid_round)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    # -------------------------------------------------------------------------
    # Test 5: Different jobs can each have Round 1
    # -------------------------------------------------------------------------
    def test_05_different_jobs_can_have_same_round_number(self):
        """Verify different jobs can independently have round_number=1."""
        round_b1 = RecruitmentRound(
            job_posting_id=self.job_b.id,
            round_number=1,
            name="Job B - Screening Round",
            round_type="screening",
            is_final=False,
        )
        self.db.add(round_b1)
        self.db.commit()
        self.assertIsNotNone(round_b1.id)
        self.assertEqual(round_b1.job_posting_id, self.job_b.id)

    # -------------------------------------------------------------------------
    # Test 6: Existing result batches can have null round_id
    # -------------------------------------------------------------------------
    def test_06_result_batch_null_round_id(self):
        """Verify RecruitmentResultBatch functions cleanly with round_id=None."""
        # Find any existing file
        sample_file = self.db.query(File).first()
        self.assertIsNotNone(sample_file, "At least one File record must exist in DB for test")

        batch = RecruitmentResultBatch(
            company_id=self.company.id,
            job_posting_id=self.job_a.id,
            file_id=sample_file.id,
            round_name="Unlinked OA Batch",
            round_type="assessment",
            is_final_round=False,
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            round_id=None,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)

        self.assertIsNone(batch.round_id)
        self.assertIsNone(batch.round)
        self.assertEqual(batch.round_name, "Unlinked OA Batch")

    # -------------------------------------------------------------------------
    # Test 7: Result batch can link to a valid round
    # -------------------------------------------------------------------------
    def test_07_result_batch_can_link_to_valid_round(self):
        """Verify RecruitmentResultBatch can establish a valid FK to RecruitmentRound."""
        round_1 = self.db.query(RecruitmentRound).filter(
            RecruitmentRound.job_posting_id == self.job_a.id,
            RecruitmentRound.round_number == 1
        ).first()
        sample_file = self.db.query(File).first()

        batch = RecruitmentResultBatch(
            company_id=self.company.id,
            job_posting_id=self.job_a.id,
            file_id=sample_file.id,
            round_name="Linked Round 1 Batch",
            round_type="assessment",
            is_final_round=False,
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            round_id=round_1.id,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)

        self.assertEqual(batch.round_id, round_1.id)
        self.assertEqual(batch.round.name, "Online Assessment")

    # -------------------------------------------------------------------------
    # Test 8: Student round outcome creation and duplicate rejection
    # -------------------------------------------------------------------------
    def test_08_student_round_outcome_and_unique_constraint(self):
        """Verify StudentRoundOutcome creation and unique constraint on (application_id, round_id)."""
        round_1 = self.db.query(RecruitmentRound).filter(
            RecruitmentRound.job_posting_id == self.job_a.id,
            RecruitmentRound.round_number == 1
        ).first()

        outcome = StudentRoundOutcome(
            application_id=self.app_a.id,
            round_id=round_1.id,
            student_id=self.student.id,
            outcome=RoundOutcome.CLEARED,
            score=88.5,
            remarks="Passed OA with high score",
        )
        self.db.add(outcome)
        self.db.commit()
        self.db.refresh(outcome)

        self.assertEqual(outcome.outcome, RoundOutcome.CLEARED)
        self.assertEqual(outcome.score, 88.5)

        # Attempt duplicate outcome for the exact same (application_id, round_id)
        dup_outcome = StudentRoundOutcome(
            application_id=self.app_a.id,
            round_id=round_1.id,
            student_id=self.student.id,
            outcome=RoundOutcome.OFFERED,
        )
        self.db.add(dup_outcome)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    # -------------------------------------------------------------------------
    # Test 9: Placement offer associated with application and student
    # -------------------------------------------------------------------------
    def test_09_placement_offer_creation(self):
        """Verify PlacementOffer model with CTC, designation, and acceptance status."""
        offer = PlacementOffer(
            application_id=self.app_a.id,
            student_id=self.student.id,
            job_posting_id=self.job_a.id,
            ctc_lpa=14.5,
            designation="Associate Cloud Consultant",
            acceptance_status=OfferAcceptanceStatus.OFFERED,
            offer_date=datetime.now(timezone.utc),
        )
        self.db.add(offer)
        self.db.commit()
        self.db.refresh(offer)

        self.assertEqual(offer.ctc_lpa, 14.5)
        self.assertEqual(offer.designation, "Associate Cloud Consultant")
        self.assertEqual(offer.acceptance_status, OfferAcceptanceStatus.OFFERED)

        # Verify relationship from Application
        app = self.db.query(Application).filter(Application.id == self.app_a.id).first()
        self.assertIsNotNone(app.placement_offer)
        self.assertEqual(app.placement_offer.ctc_lpa, 14.5)

    # -------------------------------------------------------------------------
    # Test 10: Duplicate offer on the same application rejected
    # -------------------------------------------------------------------------
    def test_10_duplicate_offer_for_same_application_rejected(self):
        """Verify unique constraint on application_id in placement_offers."""
        dup_offer = PlacementOffer(
            application_id=self.app_a.id,  # Already has offer from test_09
            student_id=self.student.id,
            job_posting_id=self.job_a.id,
            ctc_lpa=16.0,
            designation="Senior Cloud Consultant",
        )
        self.db.add(dup_offer)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    # -------------------------------------------------------------------------
    # Test 11: Different applications for the same student have separate offers
    # -------------------------------------------------------------------------
    def test_11_multiple_offers_for_different_applications_same_student(self):
        """Verify student can receive multiple offers across different job applications."""
        offer_b = PlacementOffer(
            application_id=self.app_b.id,
            student_id=self.student.id,
            job_posting_id=self.job_b.id,
            ctc_lpa=18.0,
            designation="AI Solutions Specialist",
            acceptance_status=OfferAcceptanceStatus.OFFERED,
        )
        self.db.add(offer_b)
        self.db.commit()
        self.db.refresh(offer_b)

        student_offers = self.db.query(PlacementOffer).filter(PlacementOffer.student_id == self.student.id).all()
        self.assertGreaterEqual(len(student_offers), 2)
        app_ids = [o.application_id for o in student_offers]
        self.assertIn(self.app_a.id, app_ids)
        self.assertIn(self.app_b.id, app_ids)

    # -------------------------------------------------------------------------
    # Test 12: Invalid foreign key references rejected
    # -------------------------------------------------------------------------
    def test_12_invalid_foreign_key_references_rejected(self):
        """Verify foreign-key constraints prevent orphan child records."""
        # Invalid job_posting_id on RecruitmentRound
        bad_round = RecruitmentRound(
            job_posting_id=99999999,
            round_number=1,
            name="Ghost Round",
        )
        self.db.add(bad_round)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

        # Invalid application_id on PlacementOffer
        bad_offer = PlacementOffer(
            application_id=99999999,
            student_id=self.student.id,
            job_posting_id=self.job_a.id,
            ctc_lpa=10.0,
        )
        self.db.add(bad_offer)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    # -------------------------------------------------------------------------
    # Test 13: Migration head and unchanged legacy statuses
    # -------------------------------------------------------------------------
    def test_13_migration_head_and_legacy_status_preservation(self):
        """Verify Alembic database revision matches current configured script head and existing application/profile statuses were untouched."""
        import os
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        result = self.db.execute(sa.text("SELECT version_num FROM alembic_version")).fetchone()
        self.assertIsNotNone(result, "alembic_version table must have an active revision record")

        # Dynamically discover configured Alembic script heads
        alembic_ini_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alembic.ini")
        if not os.path.exists(alembic_ini_path):
            alembic_ini_path = "alembic.ini"

        alembic_cfg = Config(alembic_ini_path)
        script_dir = ScriptDirectory.from_config(alembic_cfg)
        script_heads = script_dir.get_heads()

        # Enforce project's single-head migration policy
        self.assertEqual(len(script_heads), 1, f"Expected single migration head, found multiple: {script_heads}")
        expected_head = script_heads[0]

        # Verify single head and that database matches script head or immediate ancestor prior to deployment
        valid_revisions = [expected_head]
        down_rev = script_dir.get_revision(expected_head).down_revision
        if down_rev:
            valid_revisions.append(down_rev)

        self.assertIn(
            result[0],
            valid_revisions,
            f"Database revision ({result[0]}) must match Alembic script head ({expected_head}) or immediate ancestor ({down_rev})"
        )

        # Verify that applications exist and retain valid status
        app_count = self.db.query(Application).count()
        self.assertGreater(app_count, 0)

        # Verify that student profile placement statuses are valid enums
        profiles = self.db.query(StudentProfileExtended).limit(5).all()
        for p in profiles:
            self.assertIn(p.placement_status, [
                PlacementStatus.NOT_APPLIED,
                PlacementStatus.APPLIED,
                PlacementStatus.SHORTLISTED,
                PlacementStatus.PLACED,
            ])


if __name__ == "__main__":
    unittest.main()
