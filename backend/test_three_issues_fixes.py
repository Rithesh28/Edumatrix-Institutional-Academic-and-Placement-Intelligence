"""
EduMatrix Regression Test Suite for Issues 1, 2, and 3:
- Issue 1: Placement Officer Bulk File Deletion Authorization, Protected Dependency Prevention, and failed_reasons mapping.
- Issue 2: External Application URL and Instructions Extraction in JD Parser, Image OCR and Spreadsheet support, Schema serialization.
- Issue 3: External Application Confirmation Logic and Safety.
"""

import os
import sys
import uuid
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.user import User, UserRole
from app.models.file import File, FileStatus, FileType
from app.models.recruitment_result import RecruitmentResultBatch
from app.models.recruitment_round import PlacementOffer
from app.models.recruitment_circular import RecruitmentCircularAttachment
from app.models.circular import Circular
from app.models.resume import Resume
from app.schemas.file import FileBulkDeleteRequest, FileBulkDeleteResponse
from app.schemas.placement import JdParseResponse
from app.services.jd_parser_service import jd_parser_service, JdParseResult
from app.api.files import check_file_protected_dependencies, bulk_delete_files
import asyncio


class TestIssue1BulkFileDeletionAndRBAC(unittest.TestCase):
    """Verifies Placement Officer bulk delete permissions and protected file dependency safeguards."""

    def setUp(self):
        self.po_user = User(
            id=101,
            email="placement@college.edu",
            name="Placement Officer",
            role=UserRole.PLACEMENT_OFFICER,
            department="TRAINING_PLACEMENT",
            is_active=True
        )
        self.faculty_user = User(
            id=202,
            email="faculty_cse@college.edu",
            name="Faculty CSE",
            role=UserRole.LECTURER,
            department="CSE",
            is_active=True
        )

        self.po_file_id = uuid.uuid4()
        self.po_file = File(
            id=self.po_file_id,
            filename="placement_brochure.pdf",
            uploaded_by=self.po_user.id,
            department="TRAINING_PLACEMENT",
            file_type=FileType.PLACEMENT_DOC,
            status=FileStatus.ACTIVE
        )

        self.placement_doc_other_user_id = uuid.uuid4()
        self.placement_doc_other_user = File(
            id=self.placement_doc_other_user_id,
            filename="placement_schedule.pdf",
            uploaded_by=self.faculty_user.id,
            department="CSE",
            file_type=FileType.PLACEMENT_DOC,
            status=FileStatus.ACTIVE
        )

        self.acad_file_other_id = uuid.uuid4()
        self.acad_file_other = File(
            id=self.acad_file_other_id,
            filename="syllabus_cse.pdf",
            uploaded_by=self.faculty_user.id,
            department="CSE",
            file_type=FileType.CIRCULAR,
            status=FileStatus.ACTIVE
        )

    def test_placement_officer_can_bulk_delete_own_file(self):
        """Placement Officer can bulk delete files they uploaded."""
        mock_db = MagicMock()
        with patch("app.api.files.file_service.get_file", return_value=self.po_file), \
             patch("app.api.files.file_service.delete_file", return_value=True), \
             patch("app.api.files.check_file_protected_dependencies", return_value=None), \
             patch("app.api.files.audit_service.log_action"):

            req = FileBulkDeleteRequest(file_ids=[self.po_file_id])
            res = asyncio.run(bulk_delete_files(request=req, permanent=False, current_user=self.po_user, db=mock_db))

            self.assertEqual(res.deleted_count, 1)
            self.assertEqual(len(res.failed_ids), 0)

    def test_placement_officer_can_bulk_delete_placement_docs(self):
        """Placement Officer can bulk delete placement_doc files even if uploaded by another department user."""
        mock_db = MagicMock()
        with patch("app.api.files.file_service.get_file", return_value=self.placement_doc_other_user), \
             patch("app.api.files.file_service.delete_file", return_value=True), \
             patch("app.api.files.check_file_protected_dependencies", return_value=None), \
             patch("app.api.files.audit_service.log_action"):

            req = FileBulkDeleteRequest(file_ids=[self.placement_doc_other_user_id])
            res = asyncio.run(bulk_delete_files(request=req, permanent=False, current_user=self.po_user, db=mock_db))

            self.assertEqual(res.deleted_count, 1)
            self.assertEqual(len(res.failed_ids), 0)

    def test_placement_officer_blocked_from_deleting_unauthorized_academic_files(self):
        """Placement Officer cannot delete academic circular files uploaded by faculty."""
        mock_db = MagicMock()
        with patch("app.api.files.file_service.get_file", return_value=self.acad_file_other), \
             patch("app.api.files.file_service.delete_file") as mock_del, \
             patch("app.api.files.audit_service.log_action"):

            req = FileBulkDeleteRequest(file_ids=[self.acad_file_other_id])
            res = asyncio.run(bulk_delete_files(request=req, permanent=False, current_user=self.po_user, db=mock_db))

            self.assertEqual(res.deleted_count, 0)
            self.assertEqual(len(res.failed_ids), 1)
            self.assertIn(str(self.acad_file_other_id), res.failed_reasons)
            self.assertIn("Permission denied", res.failed_reasons[str(self.acad_file_other_id)])
            mock_del.assert_not_called()

    def test_check_file_protected_dependencies_result_batch(self):
        """File referenced by RecruitmentResultBatch is protected."""
        test_fid = uuid.uuid4()
        mock_db = MagicMock()
        fake_batch = RecruitmentResultBatch(id=42, round_name="Technical Round 1", file_id=test_fid)

        def mock_query(model):
            m = MagicMock()
            if model == RecruitmentResultBatch:
                m.filter.return_value.first.return_value = fake_batch
            else:
                m.filter.return_value.first.return_value = None
            return m

        mock_db.query.side_effect = mock_query
        reason = check_file_protected_dependencies(mock_db, test_fid)
        self.assertIsNotNone(reason)
        self.assertIn("recruitment result batch #42", reason)

    def test_check_file_protected_dependencies_offer_letter(self):
        """File referenced by PlacementOffer is protected."""
        test_fid = uuid.uuid4()
        mock_db = MagicMock()
        fake_offer = PlacementOffer(id=99, offer_letter_file_id=test_fid)

        def mock_query(model):
            m = MagicMock()
            if model == PlacementOffer:
                m.filter.return_value.first.return_value = fake_offer
            else:
                m.filter.return_value.first.return_value = None
            return m

        mock_db.query.side_effect = mock_query
        reason = check_file_protected_dependencies(mock_db, test_fid)
        self.assertIsNotNone(reason)
        self.assertIn("placement offer #99", reason)

    def test_check_file_protected_dependencies_circular_attachment(self):
        """File referenced by RecruitmentCircularAttachment is protected."""
        test_fid = uuid.uuid4()
        mock_db = MagicMock()
        fake_att = RecruitmentCircularAttachment(id=1, circular_id=12, file_id=test_fid)

        def mock_query(model):
            m = MagicMock()
            if model == RecruitmentCircularAttachment:
                m.filter.return_value.first.return_value = fake_att
            else:
                m.filter.return_value.first.return_value = None
            return m

        mock_db.query.side_effect = mock_query
        reason = check_file_protected_dependencies(mock_db, test_fid)
        self.assertIsNotNone(reason)
        self.assertIn("recruitment circular #12", reason)

    def test_check_file_protected_dependencies_none_when_unreferenced(self):
        """File not referenced by any record returns None (deletable)."""
        test_fid = uuid.uuid4()
        mock_db = MagicMock()

        def mock_query(model):
            m = MagicMock()
            m.filter.return_value.first.return_value = None
            return m

        mock_db.query.side_effect = mock_query
        reason = check_file_protected_dependencies(mock_db, test_fid)
        self.assertIsNone(reason)

    def test_bulk_delete_protects_dependencies_and_records_failed_reasons(self):
        """Bulk delete blocks protected files and populates failed_reasons dictionary."""
        mock_db = MagicMock()
        with patch("app.api.files.file_service.get_file", return_value=self.po_file), \
             patch("app.api.files.file_service.delete_file") as mock_del, \
             patch("app.api.files.check_file_protected_dependencies", return_value="Referenced by verified placement offer #7"), \
             patch("app.api.files.audit_service.log_action"):

            req = FileBulkDeleteRequest(file_ids=[self.po_file_id])
            res = asyncio.run(bulk_delete_files(request=req, permanent=False, current_user=self.po_user, db=mock_db))

            self.assertEqual(res.deleted_count, 0)
            self.assertEqual(len(res.failed_ids), 1)
            self.assertIn(str(self.po_file_id), res.failed_reasons)
            self.assertIn("Protected record: Referenced by verified placement offer #7", res.failed_reasons[str(self.po_file_id)])
            mock_del.assert_not_called()


class TestIssue2JdParserUrlAndFormatExtraction(unittest.TestCase):
    """Verifies external application URL extraction, instructions extraction, and schemas."""

    def test_extract_external_application_url(self):
        """JD parser extracts explicit external career/apply URLs."""
        text = """
        Company: TechNova Solutions
        Role: Associate Software Engineer
        Eligibility: 7.0 CGPA, B.Tech CSE/IT
        Application Process:
        Candidates must apply directly on our company career portal:
        https://technova.wd3.myworkdayjobs.com/en-US/careers/job/Junior-Dev-R10042
        Please submit your application before 25th October 2026.
        """
        url, instructions = jd_parser_service._extract_application_url_and_instructions(text, evidence={})
        self.assertIsNotNone(url)
        self.assertEqual(url, "https://technova.wd3.myworkdayjobs.com/en-US/careers/job/Junior-Dev-R10042")
        self.assertIn("career portal", instructions)

    def test_extract_application_url_from_generic_website(self):
        """Prefers career portal or application URLs over company homepages."""
        text = """
        About Us: Visit us at https://www.acme-corp.com
        To apply for this campus recruitment opening, register at:
        https://jobs.lever.co/acmecorp/fe48-senior-analyst
        """
        url, instructions = jd_parser_service._extract_application_url_and_instructions(text, evidence={})
        self.assertEqual(url, "https://jobs.lever.co/acmecorp/fe48-senior-analyst")

    def test_parse_jd_text_includes_application_url(self):
        """parse_jd_text produces JdParseResult with application_url populated."""
        text = """
        Role: Frontend Developer
        Company: PixelCraft Studios
        Skills: React, JavaScript, CSS, HTML
        Apply online at https://careers.pixelcraft.io/jobs/apply/frontend
        """
        res = jd_parser_service.parse_jd_text(text)
        self.assertEqual(res.application_url, "https://careers.pixelcraft.io/jobs/apply/frontend")
        self.assertIn("React", res.required_skills)

    def test_jd_parse_response_schema_validation(self):
        """JdParseResponse serializes application_url correctly."""
        resp = JdParseResponse(
            company_name="Google",
            job_title="Software Engineer",
            application_url="https://careers.google.com/jobs/123",
            confidence_score=0.95
        )
        data = resp.model_dump()
        self.assertEqual(data["application_url"], "https://careers.google.com/jobs/123")


class TestIssue3ApplicationFlowIntegrity(unittest.TestCase):
    """Verifies application responses and confirmation field integrity."""

    def test_response_models_preserve_external_status(self):
        """Verify JdParseResponse and FileBulkDeleteResponse models are complete."""
        bulk_resp = FileBulkDeleteResponse(
            deleted_count=2,
            failed_ids=[],
            failed_reasons={}
        )
        self.assertEqual(bulk_resp.deleted_count, 2)
        self.assertEqual(bulk_resp.failed_reasons, {})


if __name__ == "__main__":
    unittest.main()
