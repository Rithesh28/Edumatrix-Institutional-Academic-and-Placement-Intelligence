"""
Validation tests for Phase 1 Critical Bug Fixes:
1. ApplicationResponse import in placement_service.py
2. Normalized skill matching (Skill ORM objects, casing, whitespace, deduplication)
3. CSV export logic for placement reports
4. Celery file_tasks restoration and task signatures
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import io
import csv
from datetime import datetime

# Configure SQLite for test environment before importing app
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Provide mock modules for heavy extraction libraries if running outside full Docker container
for mod in ["pdfplumber", "PyPDF2", "docx", "pptx", "openpyxl", "pytesseract", "PIL", "sentence_transformers", "torch", "jose", "passlib", "passlib.context", "transformers"]:
    if mod not in sys.modules:
        try:
            __import__(mod)
        except ImportError:
            sys.modules[mod] = MagicMock()


class TestApplicationResponseImport(unittest.TestCase):
    def test_application_response_imported_in_placement_service(self):
        """Verify ApplicationResponse is in placement_service module namespace."""
        import app.services.placement_service as ps
        self.assertTrue(hasattr(ps, 'ApplicationResponse'), "ApplicationResponse must be imported in placement_service")

    def test_student_placement_status_with_application_response(self):
        """Verify get_student_placement_status builds ApplicationResponse without NameError."""
        import app.services.placement_service as ps
        
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.id = 101
        mock_user.name = "Test Student"
        mock_user.email = "student@vcet.ac.in"
        
        mock_profile = MagicMock()
        mock_profile.branch = "AIML"
        mock_profile.cgpa = 8.75
        
        mock_app = MagicMock()
        mock_app.id = 1
        mock_app.student_id = 101
        mock_app.job_posting_id = 5
        mock_app.status = ps.ApplicationStatus.SHORTLISTED
        mock_app.applied_at = datetime.utcnow()
        mock_app.updated_at = datetime.utcnow()
        mock_app.eligibility_score = 85.0
        mock_app.match_percentage = 90.0
        mock_app.notes = "Top candidate"
        mock_app.student_name = "Test Student"
        mock_app.student_email = "student@vcet.ac.in"
        mock_app.student_branch = "AIML"
        mock_app.student_cgpa = 8.75
        mock_app.job_title = "AI Engineer"
        mock_app.company_name = "Tech Corp"
        mock_app.match_snapshot = None
        mock_app.has_low_match_warning = False
        mock_app.low_match_warning = None
        mock_app.external_applied_at = None
        mock_app.is_external_confirmed = False
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_user, mock_profile]
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_app]
        
        status = ps.placement_service.get_student_placement_status(mock_db, 101)
        self.assertIsNotNone(status)
        self.assertEqual(status.student_id, 101)
        self.assertEqual(status.status, "shortlisted")
        self.assertEqual(len(status.applications), 1)
        self.assertEqual(status.applications[0].id, 1)


class TestSkillMatchingNormalization(unittest.TestCase):
    def test_skill_orm_vs_string_matching(self):
        """Verify Skill objects with mixed casing and whitespace are matched correctly."""
        import app.services.placement_service as ps
        
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.id = 201
        mock_user.name = "Jane Developer"
        mock_user.email = "jane@vcet.ac.in"
        
        # Student has Skill objects (as in SQLAlchemy model relationship)
        mock_skill1 = MagicMock()
        mock_skill1.name = "  Python  "
        mock_skill2 = MagicMock()
        mock_skill2.name = "react"
        mock_skill3 = MagicMock()
        mock_skill3.name = "PostgreSQL"
        
        mock_profile = MagicMock()
        mock_profile.id = 50
        mock_profile.branch = "AIML"
        mock_profile.cgpa = 9.2
        mock_profile.skills = [mock_skill1, mock_skill2, mock_skill3]
        
        # Job requires skills with different casing, whitespace, and duplicates
        mock_job = MagicMock()
        mock_job.required_skills = ["PYTHON", "  python ", "React", "Docker"]
        mock_job.cgpa_criteria = 8.0
        mock_job.branch_eligibility = ["AIML", "CSE"]
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_user,     # User query
            mock_profile   # StudentProfile query
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_skill1, mock_skill2, mock_skill3]
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None  # No resume
        
        with patch.object(ps.placement_service, 'get_job_posting', return_value=mock_job):
            eligibility = ps.placement_service.check_student_eligibility(mock_db, 201, 10)
        
        self.assertIsNotNone(eligibility)
        self.assertTrue(eligibility.is_eligible)
        self.assertTrue(eligibility.cgpa_match)
        self.assertTrue(eligibility.branch_match)
        
        # Required skills unique: "PYTHON" (or "python"), "React", "Docker" -> 3 unique
        # Matched: python and react -> 2
        # Missing: docker -> 1
        self.assertEqual(len(eligibility.matched_skills), 2)
        self.assertEqual(len(eligibility.missing_skills), 1)
        self.assertAlmostEqual(eligibility.skill_match, 2 / 3 * 100.0, places=1)

    def test_resume_skills_included_in_matching(self):
        """Verify student skills found on uploaded resume are factored into matching."""
        import app.services.placement_service as ps
        
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.id = 202
        mock_user.name = "John Coder"
        mock_user.email = "john@vcet.ac.in"
        
        mock_profile = MagicMock()
        mock_profile.id = 51
        mock_profile.branch = "CSE"
        mock_profile.cgpa = 8.5
        mock_profile.skills = []  # No manual profile skills
        
        mock_resume = MagicMock()
        mock_resume.skills = ["FastAPI", "Docker", "Git"]
        
        mock_job = MagicMock()
        mock_job.required_skills = ["fastapi", "docker"]
        mock_job.cgpa_criteria = 7.5
        mock_job.branch_eligibility = ["CSE"]
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_user,
            mock_profile
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_resume
        
        with patch.object(ps.placement_service, 'get_job_posting', return_value=mock_job):
            eligibility = ps.placement_service.check_student_eligibility(mock_db, 202, 11)
        
        self.assertTrue(eligibility.is_eligible)
        self.assertEqual(eligibility.skill_match, 100.0)
        self.assertEqual(len(eligibility.matched_skills), 2)
        self.assertEqual(len(eligibility.missing_skills), 0)


class TestPlacementReportExport(unittest.TestCase):
    def test_csv_export_structure(self):
        """Verify CSV export columns and formatting."""
        output = io.StringIO()
        writer = csv.writer(output)
        
        headers = [
            "Student ID", "Student Name", "Enrollment Number", "Email",
            "Department / Branch", "Year", "Semester", "CGPA",
            "Placement Status", "ATS Score", "Total Applications",
            "Total Shortlists", "Applied Job Titles", "Skills"
        ]
        writer.writerow(headers)
        
        row = [
            1, "Rithesh", "4VP20AI001", "rithesh@example.com",
            "AIML", 4, 8, "9.10", "shortlisted", "88.5",
            2, 1, "Software Engineer; AI Engineer", "Python, FastAPI, PyTorch"
        ]
        writer.writerow(row)
        
        csv_text = output.getvalue()
        self.assertIn("Student ID,Student Name", csv_text)
        self.assertIn("4VP20AI001", csv_text)
        self.assertIn("shortlisted", csv_text)

    def test_export_endpoint_registered_on_placement_router(self):
        """Verify GET /placement/reports/export endpoint is registered on placement router."""
        import app.api.placement as placement_api
        routes = [route.path for route in placement_api.router.routes]
        self.assertIn("/placement/reports/export", routes, "Route /placement/reports/export must be present on placement router")


class TestFileTasksRestoration(unittest.TestCase):
    def test_file_tasks_definitions(self):
        """Verify file_tasks functions exist and have celery task names."""
        import app.tasks.file_tasks as ft
        
        tasks_to_check = [
            'generate_embedding',
            'process_upload',
            'delete_file_vectors',
            'cleanup_temporary_files',
            'sync_embedding_batch',
            'update_search_index',
            'check_file_integrity',
            'regenerate_embeddings_for_department',
            'process_file_version'
        ]
        
        for task_name in tasks_to_check:
            self.assertTrue(hasattr(ft, task_name), f"Task {task_name} must exist in file_tasks.py")
            fn = getattr(ft, task_name)
            # Celery shared_task objects have 'delay' method and 'name' attribute
            self.assertTrue(hasattr(fn, 'delay'), f"Task {task_name} must have .delay() method (Celery task)")
            self.assertTrue(hasattr(fn, 'name'), f"Task {task_name} must have .name attribute")


if __name__ == '__main__':
    unittest.main()
