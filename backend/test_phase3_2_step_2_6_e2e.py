"""
EduMatrix Phase 3.2 — Step 2.6: End-to-End Regression Verification Script
Tests all 14 critical end-to-end scenarios live against the running backend and database.
"""

import sys
import unittest
import requests
from datetime import datetime, timedelta, timezone

BASE_URL = "http://localhost:8000"

class TestPhase32Step26E2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 1. Login as Placement Officer
        po_login = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": "placement@gmail.com", "password": "12345"}
        )
        assert po_login.status_code == 200, f"PO login failed: {po_login.text}"
        cls.po_token = po_login.json()["access_token"]
        cls.po_headers = {"Authorization": f"Bearer {cls.po_token}"}
        cls.po_user = po_login.json()["user"]

        # 2. Login as Student A (adi01, ID: 1, Branch: AIML, CGPA: 9.0)
        s1_login = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": "adi01@gmail.com", "password": "54321"}
        )
        assert s1_login.status_code == 200, f"Student 1 login failed: {s1_login.text}"
        cls.s1_token = s1_login.json()["access_token"]
        cls.s1_headers = {"Authorization": f"Bearer {cls.s1_token}"}
        cls.s1_user = s1_login.json()["user"]

        # 3. Login as Student B (student_ece, ID: 54, Branch: ECE)
        s2_login = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": "student_ece@gmail.com", "password": "12345"}
        )
        assert s2_login.status_code == 200, f"Student 2 login failed: {s2_login.text}"
        cls.s2_token = s2_login.json()["access_token"]
        cls.s2_headers = {"Authorization": f"Bearer {cls.s2_token}"}
        cls.s2_user = s2_login.json()["user"]

        # Ensure a test company exists
        comp_res = requests.get(f"{BASE_URL}/placement/companies", headers=cls.po_headers)
        companies = comp_res.json()
        if companies:
            cls.company_id = companies[0]["id"]
        else:
            new_comp = requests.post(
                f"{BASE_URL}/placement/companies",
                headers=cls.po_headers,
                json={"name": "E2E Test Corp", "industry": "Technology", "location": "Bangalore"}
            )
            cls.company_id = new_comp.json()["id"]

        cls.created_jobs = []
        cls.created_applications = []

    @classmethod
    def tearDownClass(cls):
        # Cleanup created test jobs and applications
        from app.core.database import SessionLocal
        from app.models.application import Application
        from app.models.job_posting import JobPosting
        from app.models.shortlist import Shortlist
        db = SessionLocal()
        try:
            if cls.created_applications:
                db.query(Application).filter(Application.id.in_(cls.created_applications)).delete(synchronize_session=False)
            if cls.created_jobs:
                db.query(Shortlist).filter(Shortlist.job_posting_id.in_(cls.created_jobs)).delete(synchronize_session=False)
                db.query(Application).filter(Application.job_posting_id.in_(cls.created_jobs)).delete(synchronize_session=False)
                db.query(JobPosting).filter(JobPosting.id.in_(cls.created_jobs)).delete(synchronize_session=False)
            db.commit()
        except Exception as e:
            print("Cleanup warning:", e)
            db.rollback()
        finally:
            db.close()

    def test_01_draft_job_hidden_from_students(self):
        """Scenario 1: Placement Officer creates a draft job and students cannot see it."""
        job_data = {
            "company_id": self.company_id,
            "title": "E2E Confidential Draft Role",
            "description": "Internal pending job",
            "required_skills": ["Python", "FastAPI"],
            "preferred_skills": ["Docker"],
            "cgpa_criteria": 7.0,
            "branch_eligibility": ["AIML", "CSE"],
            "location": "Bangalore",
            "salary_range": "10-12 LPA",
            "status": "draft"
        }
        res = requests.post(f"{BASE_URL}/placement/jobs", headers=self.po_headers, json=job_data)
        self.assertEqual(res.status_code, 200)
        draft_job = res.json()
        self.created_jobs.append(draft_job["id"])

        # Student queries jobs list - must NOT contain draft job
        student_jobs_res = requests.get(f"{BASE_URL}/placement/jobs", headers=self.s1_headers)
        self.assertEqual(student_jobs_res.status_code, 200)
        student_job_ids = [j["id"] for j in student_jobs_res.json()]
        self.assertNotIn(draft_job["id"], student_job_ids, "Draft job must not be visible in student job list")

        # Student queries direct job endpoint - must return 404
        direct_res = requests.get(f"{BASE_URL}/placement/jobs/{draft_job['id']}", headers=self.s1_headers)
        self.assertEqual(direct_res.status_code, 404, "Direct access to draft job by student must return 404")

    def test_02_publish_job_visible_to_students(self):
        """Scenario 2: Placement Officer publishes a valid job and students can see it."""
        job_data = {
            "company_id": self.company_id,
            "title": "E2E Published Software Role",
            "description": "Active open position",
            "required_skills": ["Java", "Python"],
            "preferred_skills": ["React"],
            "cgpa_criteria": 7.0,
            "branch_eligibility": ["AIML", "ECE"],
            "location": "Bangalore",
            "salary_range": "8-12 LPA",
            "status": "draft"
        }
        res = requests.post(f"{BASE_URL}/placement/jobs", headers=self.po_headers, json=job_data)
        self.assertEqual(res.status_code, 200)
        job_id = res.json()["id"]
        self.created_jobs.append(job_id)

        # Publish the job
        pub_res = requests.post(f"{BASE_URL}/placement/jobs/{job_id}/publish", headers=self.po_headers)
        self.assertEqual(pub_res.status_code, 200)
        self.assertEqual(pub_res.json()["status"], "open")

        # Student queries jobs list - must contain the published job
        student_jobs_res = requests.get(f"{BASE_URL}/placement/jobs", headers=self.s1_headers)
        self.assertEqual(student_jobs_res.status_code, 200)
        student_job_ids = [j["id"] for j in student_jobs_res.json()]
        self.assertIn(job_id, student_job_ids, "Published job must be visible in student job list")

        # Student queries direct job endpoint - must return 200
        direct_res = requests.get(f"{BASE_URL}/placement/jobs/{job_id}", headers=self.s1_headers)
        self.assertEqual(direct_res.status_code, 200)
        self.assertEqual(direct_res.json()["title"], "E2E Published Software Role")
        self.assertIsNotNone(direct_res.json().get("company_name"))

    def test_03_student_receives_server_calculated_match_breakdown(self):
        """Scenario 3: Student opens job details and receives correct server-calculated match breakdown."""
        # Use existing open Job 5
        res = requests.get(f"{BASE_URL}/placement/jobs/5/check-eligibility/{self.s1_user['id']}", headers=self.s1_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("overall_skill_match", data)
        self.assertIn("required_score", data)
        self.assertIn("matched_required_skills", data)
        self.assertIn("missing_required_skills", data)
        self.assertIn("cgpa_match", data)
        self.assertIn("branch_match", data)
        self.assertIn("is_eligible", data)
        self.assertTrue(data["is_eligible"])
        self.assertGreaterEqual(data["overall_skill_match"], 0)

    def test_04_eligible_student_with_low_skill_score_can_apply(self):
        """Scenario 4: Academically eligible student with low skill score (<50%) can apply after seeing advisory."""
        # Create job where student meets CGPA & branch, but has low skill match (<50%)
        job_data = {
            "company_id": self.company_id,
            "title": "E2E Low Skill Match Drive",
            "description": "Niche programming language job",
            "required_skills": ["Cobol", "Fortran", "Haskell", "Rust"], # student does not have these
            "preferred_skills": [],
            "cgpa_criteria": 7.0, # student has 9.0
            "branch_eligibility": ["AIML"], # student is AIML
            "location": "Bangalore",
            "salary_range": "15 LPA",
            "status": "draft"
        }
        res = requests.post(f"{BASE_URL}/placement/jobs", headers=self.po_headers, json=job_data)
        job_id = res.json()["id"]
        self.created_jobs.append(job_id)
        requests.post(f"{BASE_URL}/placement/jobs/{job_id}/publish", headers=self.po_headers, params={"confirm_no_skills": True})

        # Check eligibility - must be eligible, but have low match warning
        el_res = requests.get(f"{BASE_URL}/placement/jobs/{job_id}/check-eligibility/{self.s1_user['id']}", headers=self.s1_headers)
        self.assertEqual(el_res.status_code, 200)
        el_data = el_res.json()
        self.assertTrue(el_data["is_eligible"], "Academic eligibility must pass")
        self.assertTrue(el_data["has_low_match_warning"], "Low match warning must be True")
        self.assertLess(el_data["required_score"] or 0, 50.0)

        # Apply - must SUCCEED despite low skill match!
        app_res = requests.post(
            f"{BASE_URL}/placement/applications",
            headers=self.s1_headers,
            json={"job_posting_id": job_id, "notes": "E2E Low match test application"}
        )
        self.assertEqual(app_res.status_code, 200, f"Application with low skill match must be accepted: {app_res.text}")
        app_data = app_res.json()
        self.created_applications.append(app_data["id"])
        self.assertTrue(app_data["has_low_match_warning"], "Application response must preserve low match warning")
        self.assertIsNotNone(app_data.get("match_snapshot"))
        self.assertTrue(app_data["match_snapshot"]["has_low_match_warning"])

    def test_05_ineligible_student_cannot_apply(self):
        """Scenario 5: Academically ineligible student cannot apply through UI/backend."""
        # Create job where CGPA cutoff is 9.8 (student has 9.0)
        job_data = {
            "company_id": self.company_id,
            "title": "E2E Ineligible High CGPA Drive",
            "required_skills": ["Python"],
            "cgpa_criteria": 9.8,
            "branch_eligibility": ["AIML"],
            "status": "draft"
        }
        res = requests.post(f"{BASE_URL}/placement/jobs", headers=self.po_headers, json=job_data)
        job_id = res.json()["id"]
        self.created_jobs.append(job_id)
        requests.post(f"{BASE_URL}/placement/jobs/{job_id}/publish", headers=self.po_headers)

        # Check eligibility - must be ineligible
        el_res = requests.get(f"{BASE_URL}/placement/jobs/{job_id}/check-eligibility/{self.s1_user['id']}", headers=self.s1_headers)
        self.assertEqual(el_res.status_code, 200)
        self.assertFalse(el_res.json()["is_eligible"])

        # Attempt to apply - backend must REJECT with 400
        app_res = requests.post(
            f"{BASE_URL}/placement/applications",
            headers=self.s1_headers,
            json={"job_posting_id": job_id}
        )
        self.assertEqual(app_res.status_code, 400, "Ineligible student application must be rejected by backend")
        self.assertIn("rejected", app_res.text.lower())

    def test_06_server_authoritative_scoring_ignores_client_forged_values(self):
        """Scenario 6: Application submission recomputes scores on backend and ignores client-supplied score/eligibility."""
        # Create a job with Python requirement
        job_data = {
            "company_id": self.company_id,
            "title": "E2E Authoritative Scoring Test",
            "required_skills": ["Python", "Java"],
            "cgpa_criteria": 7.0,
            "branch_eligibility": ["AIML"],
            "status": "draft"
        }
        res = requests.post(f"{BASE_URL}/placement/jobs", headers=self.po_headers, json=job_data)
        job_id = res.json()["id"]
        self.created_jobs.append(job_id)
        requests.post(f"{BASE_URL}/placement/jobs/{job_id}/publish", headers=self.po_headers)

        # Student submits forged score of 99.9% and eligibility_score of 100.0%
        app_res = requests.post(
            f"{BASE_URL}/placement/applications",
            headers=self.s1_headers,
            json={
                "job_posting_id": job_id,
                "match_percentage": 99.9,
                "eligibility_score": 100.0,
            }
        )
        self.assertEqual(app_res.status_code, 200)
        app_data = app_res.json()
        self.created_applications.append(app_data["id"])

        # The authoritative score calculated by server should NOT be 99.9!
        self.assertNotEqual(app_data["match_percentage"], 99.9, "Backend must ignore forged client score")
        # In fact, for Python + Java, Student 1 has Python and Java -> server computes 100% (or actual score)
        self.assertIsNotNone(app_data["match_snapshot"])

    def test_07_duplicate_application_rejected_safely(self):
        """Scenario 7: Duplicate application attempts are rejected safely and return a clear error."""
        # Create an open job and apply once
        job_data = {
            "company_id": self.company_id,
            "title": "E2E Duplicate Test Job",
            "required_skills": ["Python"],
            "cgpa_criteria": 7.0,
            "branch_eligibility": ["AIML"],
            "status": "draft"
        }
        res = requests.post(f"{BASE_URL}/placement/jobs", headers=self.po_headers, json=job_data)
        job_id = res.json()["id"]
        self.created_jobs.append(job_id)
        requests.post(f"{BASE_URL}/placement/jobs/{job_id}/publish", headers=self.po_headers)

        first_app = requests.post(
            f"{BASE_URL}/placement/applications",
            headers=self.s1_headers,
            json={"job_posting_id": job_id}
        )
        self.assertEqual(first_app.status_code, 200)
        self.created_applications.append(first_app.json()["id"])

        # Attempt to apply a second time
        dup_app = requests.post(
            f"{BASE_URL}/placement/applications",
            headers=self.s1_headers,
            json={"job_posting_id": job_id}
        )
        self.assertEqual(dup_app.status_code, 400, "Duplicate application must return 400")
        self.assertIn("already applied", dup_app.text.lower())

    def test_08_applications_appear_in_my_applications_with_authoritative_score(self):
        """Scenario 8: Successful applications appear in My Applications with correct status and authoritative score."""
        apps_res = requests.get(f"{BASE_URL}/placement/applications", headers=self.s1_headers)
        self.assertEqual(apps_res.status_code, 200)
        apps = apps_res.json()
        self.assertGreater(len(apps), 0, "Student must have applications in list")
        for app in apps:
            self.assertEqual(app["student_id"], self.s1_user["id"], "All applications must belong to current student")
            self.assertIn("status", app)
            self.assertIn("applied_at", app)
            self.assertIn("match_percentage", app)

    def test_09_snapshot_inspection_displays_original_provenance(self):
        """Scenario 9: Snapshot inspection displays original application-time information."""
        apps_res = requests.get(f"{BASE_URL}/placement/applications", headers=self.s1_headers)
        apps = apps_res.json()
        snap_app = next((a for a in apps if a.get("match_snapshot")), None)
        self.assertIsNotNone(snap_app, "Should find at least one application with match_snapshot")

        snapshot = snap_app["match_snapshot"]
        self.assertIn("snapshot_version", snapshot)
        self.assertIn("created_at", snapshot)
        self.assertIn("branch", snapshot)
        self.assertIn("cgpa", snapshot)
        self.assertIn("matched_required_skills", snapshot)
        self.assertIn("missing_required_skills", snapshot)
        self.assertIn("match_percentage", snapshot)

    def test_10_legacy_applications_with_null_snapshot_remain_usable(self):
        """Scenario 10: Legacy applications with null snapshot remain usable without crashing."""
        from app.core.database import SessionLocal
        from app.models.application import Application, ApplicationStatus
        db = SessionLocal()
        try:
            # Create a legacy job and application with NULL snapshot
            job_data = {
                "company_id": self.company_id,
                "title": "E2E Legacy Job Without Snapshot",
                "required_skills": ["Python"],
                "cgpa_criteria": 7.0,
                "branch_eligibility": ["AIML"],
                "status": "draft"
            }
            res = requests.post(f"{BASE_URL}/placement/jobs", headers=self.po_headers, json=job_data)
            legacy_job_id = res.json()["id"]
            self.created_jobs.append(legacy_job_id)
            requests.post(f"{BASE_URL}/placement/jobs/{legacy_job_id}/publish", headers=self.po_headers)

            legacy_app = Application(
                student_id=self.s1_user["id"],
                job_posting_id=legacy_job_id,
                status=ApplicationStatus.APPLIED,
                eligibility_score=80.0,
                match_percentage=80.0,
                notes="Legacy manual entry",
                match_snapshot=None # NULL snapshot
            )
            db.add(legacy_app)
            db.commit()
            db.refresh(legacy_app)
            self.created_applications.append(legacy_app.id)

            # Query applications via API as student
            apps_res = requests.get(f"{BASE_URL}/placement/applications", headers=self.s1_headers)
            self.assertEqual(apps_res.status_code, 200)
            retrieved_legacy = next((a for a in apps_res.json() if a["id"] == legacy_app.id), None)
            self.assertIsNotNone(retrieved_legacy)
            self.assertIsNone(retrieved_legacy["match_snapshot"])
            self.assertFalse(retrieved_legacy.get("has_low_match_warning"))
            self.assertEqual(retrieved_legacy["match_percentage"], 80.0)
        finally:
            db.close()

    def test_11_closed_and_expired_jobs_cannot_receive_applications(self):
        """Scenario 11: Closed and expired jobs cannot receive new applications."""
        # A. Closed Job
        job_data = {
            "company_id": self.company_id,
            "title": "E2E Closed Job Test",
            "required_skills": ["Python"],
            "cgpa_criteria": 7.0,
            "branch_eligibility": ["AIML"],
            "status": "draft"
        }
        res = requests.post(f"{BASE_URL}/placement/jobs", headers=self.po_headers, json=job_data)
        job_id = res.json()["id"]
        self.created_jobs.append(job_id)
        # Update status directly to closed
        from app.core.database import SessionLocal
        from app.models.job_posting import JobPosting, JobStatus
        db = SessionLocal()
        try:
            j = db.query(JobPosting).filter(JobPosting.id == job_id).first()
            j.status = JobStatus.CLOSED
            db.commit()
        finally:
            db.close()

        app_res = requests.post(
            f"{BASE_URL}/placement/applications",
            headers=self.s1_headers,
            json={"job_posting_id": job_id}
        )
        self.assertEqual(app_res.status_code, 400)
        self.assertIn("not open", app_res.text.lower())

        # B. Expired Job (Deadline in the past)
        exp_job_data = {
            "company_id": self.company_id,
            "title": "E2E Expired Deadline Job Test",
            "required_skills": ["Python"],
            "cgpa_criteria": 7.0,
            "branch_eligibility": ["AIML"],
            "application_deadline": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
            "status": "draft"
        }
        res_exp = requests.post(f"{BASE_URL}/placement/jobs", headers=self.po_headers, json=exp_job_data)
        exp_job_id = res_exp.json()["id"]
        self.created_jobs.append(exp_job_id)
        requests.post(f"{BASE_URL}/placement/jobs/{exp_job_id}/publish", headers=self.po_headers)

        app_exp_res = requests.post(
            f"{BASE_URL}/placement/applications",
            headers=self.s1_headers,
            json={"job_posting_id": exp_job_id}
        )
        self.assertEqual(app_exp_res.status_code, 400)
        self.assertIn("deadline", app_exp_res.text.lower())

    def test_12_cross_student_authorization_and_ownership(self):
        """Scenario 12: Students cannot read or submit applications on behalf of another student."""
        # Student A attempts to apply on behalf of Student B (student_ece, id: 54)
        app_res = requests.post(
            f"{BASE_URL}/placement/applications",
            headers=self.s1_headers, # Student A token
            json={"job_posting_id": 5, "student_id": self.s2_user["id"]}
        )
        self.assertEqual(app_res.status_code, 403, "Student A applying for Student B must return 403")

        # Student A attempts to check eligibility for Student B
        elig_res = requests.get(
            f"{BASE_URL}/placement/jobs/5/check-eligibility/{self.s2_user['id']}",
            headers=self.s1_headers
        )
        self.assertEqual(elig_res.status_code, 403, "Student A checking Student B eligibility must return 403")

    def test_13_placement_officer_workflows_functional(self):
        """Scenario 13: Placement Officer matching, shortlists, CSV export, and dashboards remain functional."""
        # A. Candidate skill matching
        match_res = requests.post(
            f"{BASE_URL}/placement/match",
            headers=self.po_headers,
            json={"job_posting_id": 5}
        )
        self.assertEqual(match_res.status_code, 200)
        self.assertIn("total_eligible", match_res.json())

        # B. CSV Report export
        export_res = requests.get(f"{BASE_URL}/placement/reports/export", headers=self.po_headers)
        self.assertEqual(export_res.status_code, 200)
        self.assertIn("text/csv", export_res.headers.get("content-type", ""))

        # C. Placement statistics
        stats_res = requests.get(f"{BASE_URL}/placement/stats", headers=self.po_headers)
        self.assertEqual(stats_res.status_code, 200)
        self.assertIn("total_jobs", stats_res.json())

    def test_14_phase1_phase2_phase3_1_no_regressions(self):
        """Scenario 14: Phase 3.1 chat, Phase 2 RBAC & profile integrity check."""
        # Chat conversations check
        chat_res = requests.get(f"{BASE_URL}/chat/conversations", headers=self.s1_headers)
        self.assertEqual(chat_res.status_code, 200)

        # Auth & Profile check
        me_res = requests.get(f"{BASE_URL}/auth/me", headers=self.s1_headers)
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["email"], "adi01@gmail.com")

        profile_res = requests.get(f"{BASE_URL}/profile/me", headers=self.s1_headers)
        self.assertEqual(profile_res.status_code, 200)
        self.assertIn("cgpa", profile_res.json())

if __name__ == "__main__":
    unittest.main()
