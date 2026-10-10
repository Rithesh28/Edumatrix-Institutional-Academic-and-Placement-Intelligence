"""
EduMatrix Phase 3.2 — Shortlist Regression Test Suite
Verifies:
1. Successful shortlist with explicit company_id matching job
2. Successful shortlist with omitted company_id (server resolves from job posting relationship)
3. Rejection (400) when company_id mismatches job posting company
4. Rejection (404) for non-existent job posting ID
5. Rejection (404) for non-existent student ID
6. Rejection (400) for duplicate shortlisting attempts with clear message
7. RBAC rejection (403) when student attempts to shortlist
8. RBAC rejection (401) when unauthenticated user attempts to shortlist
9. Automatic status update of student's Application to SHORTLISTED upon shortlisting
"""

import sys
import unittest
import requests

BASE_URL = "http://localhost:8000"

class TestPlacementShortlistRegression(unittest.TestCase):
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

        # 2. Login as Student (adi01, ID: 1)
        s_login = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": "adi01@gmail.com", "password": "54321"}
        )
        assert s_login.status_code == 200, f"Student login failed: {s_login.text}"
        cls.s_token = s_login.json()["access_token"]
        cls.s_headers = {"Authorization": f"Bearer {cls.s_token}"}
        cls.s_user = s_login.json()["user"]

        # 3. Ensure a test company exists
        comp_res = requests.get(f"{BASE_URL}/placement/companies", headers=cls.po_headers)
        companies = comp_res.json()
        if companies:
            cls.company = companies[0]
            cls.company_id = cls.company["id"]
        else:
            new_comp = requests.post(
                f"{BASE_URL}/placement/companies",
                headers=cls.po_headers,
                json={"name": "Shortlist Test Corp", "industry": "Technology", "location": "Bangalore"}
            )
            cls.company = new_comp.json()
            cls.company_id = cls.company["id"]

        # 4. Create a dedicated test job for shortlisting
        job_payload = {
            "company_id": cls.company_id,
            "title": "Shortlist Regression Test Role",
            "description": "Job for shortlisting verification",
            "required_skills": ["Python", "FastAPI"],
            "preferred_skills": ["Docker"],
            "cgpa_criteria": 7.0,
            "branch_eligibility": ["AIML", "CSE"],
            "location": "Bangalore",
            "salary_range": "10-12 LPA",
            "status": "open"
        }
        job_res = requests.post(f"{BASE_URL}/placement/jobs", headers=cls.po_headers, json=job_payload)
        assert job_res.status_code == 200, f"Job creation failed: {job_res.text}"
        cls.test_job = job_res.json()
        cls.test_job_id = cls.test_job["id"]

        # Track created records for cleanup
        cls.created_shortlists = []
        cls.created_applications = []
        cls.created_jobs = [cls.test_job_id]

    @classmethod
    def tearDownClass(cls):
        from app.core.database import SessionLocal
        from app.models.shortlist import Shortlist
        from app.models.application import Application
        from app.models.job_posting import JobPosting
        db = SessionLocal()
        try:
            if cls.created_shortlists:
                db.query(Shortlist).filter(Shortlist.id.in_(cls.created_shortlists)).delete(synchronize_session=False)
            if cls.created_applications:
                db.query(Application).filter(Application.id.in_(cls.created_applications)).delete(synchronize_session=False)
            if cls.created_jobs:
                db.query(Shortlist).filter(Shortlist.job_posting_id.in_(cls.created_jobs)).delete(synchronize_session=False)
                db.query(Application).filter(Application.job_posting_id.in_(cls.created_jobs)).delete(synchronize_session=False)
                db.query(JobPosting).filter(JobPosting.id.in_(cls.created_jobs)).delete(synchronize_session=False)
            db.commit()
        except Exception as e:
            print("Cleanup exception:", e)
            db.rollback()
        finally:
            db.close()

    def test_01_shortlist_with_explicit_matching_company_id(self):
        """Test 1: Successful shortlist with explicit company_id matching the job."""
        student_id = self.s_user["id"]
        payload = {
            "job_posting_id": self.test_job_id,
            "company_id": self.company_id,
            "student_id": student_id,
            "reason": "Matched via test suite"
        }
        res = requests.post(f"{BASE_URL}/placement/shortlist", headers=self.po_headers, json=payload)
        self.assertEqual(res.status_code, 200, f"Shortlist failed: {res.text}")
        data = res.json()
        self.created_shortlists.append(data["id"])

        self.assertEqual(data["student_id"], student_id)
        self.assertEqual(data["company_id"], self.company_id)
        self.assertEqual(data["job_posting_id"], self.test_job_id)
        self.assertIn("reason", data)

    def test_02_duplicate_shortlist_rejected_with_clear_message(self):
        """Test 2: Re-shortlisting the same student for the same job is rejected (400)."""
        student_id = self.s_user["id"]
        payload = {
            "job_posting_id": self.test_job_id,
            "company_id": self.company_id,
            "student_id": student_id,
            "reason": "Second shortlist attempt"
        }
        res = requests.post(f"{BASE_URL}/placement/shortlist", headers=self.po_headers, json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("already shortlisted", res.text.lower())

    def test_03_shortlist_with_omitted_company_id_auto_resolves(self):
        """Test 3: Shortlisting without company_id auto-resolves company_id from the job."""
        # Use Student B (ID: 54)
        student_b_id = 54
        payload = {
            "job_posting_id": self.test_job_id,
            # company_id intentionally omitted
            "student_id": student_b_id,
            "reason": "Auto-resolved company test"
        }
        res = requests.post(f"{BASE_URL}/placement/shortlist", headers=self.po_headers, json=payload)
        self.assertEqual(res.status_code, 200, f"Auto-resolve shortlist failed: {res.text}")
        data = res.json()
        self.created_shortlists.append(data["id"])

        self.assertEqual(data["student_id"], student_b_id)
        # Verify company_id was authoritatively resolved from the job posting
        self.assertEqual(data["company_id"], self.company_id)
        self.assertEqual(data["job_posting_id"], self.test_job_id)

    def test_04_shortlist_with_mismatched_company_id_rejected(self):
        """Test 4: Shortlist with incorrect company_id is rejected (400)."""
        payload = {
            "job_posting_id": self.test_job_id,
            "company_id": 99999,  # Non-matching company ID
            "student_id": 1,
            "reason": "Mismatched company test"
        }
        res = requests.post(f"{BASE_URL}/placement/shortlist", headers=self.po_headers, json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("does not match", res.text.lower())

    def test_05_shortlist_invalid_job_id_rejected(self):
        """Test 5: Shortlist with non-existent job ID returns 404."""
        payload = {
            "job_posting_id": 999999,
            "company_id": self.company_id,
            "student_id": 1,
            "reason": "Invalid job"
        }
        res = requests.post(f"{BASE_URL}/placement/shortlist", headers=self.po_headers, json=payload)
        self.assertEqual(res.status_code, 404)
        self.assertIn("not found", res.text.lower())

    def test_06_shortlist_invalid_student_id_rejected(self):
        """Test 6: Shortlist with non-existent student ID returns 404."""
        # Create a second temp job to avoid duplicate constraint
        job_payload = {
            "company_id": self.company_id,
            "title": "Temp Job Invalid Student",
            "required_skills": ["Python"],
            "status": "open"
        }
        temp_job = requests.post(f"{BASE_URL}/placement/jobs", headers=self.po_headers, json=job_payload).json()
        self.created_jobs.append(temp_job["id"])

        payload = {
            "job_posting_id": temp_job["id"],
            "company_id": self.company_id,
            "student_id": 999999,
            "reason": "Invalid student"
        }
        res = requests.post(f"{BASE_URL}/placement/shortlist", headers=self.po_headers, json=payload)
        self.assertEqual(res.status_code, 404)
        self.assertIn("student with id 999999 not found", res.text.lower())

    def test_07_unauthorized_student_cannot_shortlist(self):
        """Test 7: Students cannot shortlist candidates (403 Forbidden)."""
        payload = {
            "job_posting_id": self.test_job_id,
            "company_id": self.company_id,
            "student_id": 1,
            "reason": "Unauthorized attempt"
        }
        res = requests.post(f"{BASE_URL}/placement/shortlist", headers=self.s_headers, json=payload)
        self.assertEqual(res.status_code, 403)

    def test_08_unauthenticated_cannot_shortlist(self):
        """Test 8: Unauthenticated requests cannot shortlist candidates (401 Unauthorized)."""
        payload = {
            "job_posting_id": self.test_job_id,
            "company_id": self.company_id,
            "student_id": 1,
            "reason": "Unauthenticated attempt"
        }
        res = requests.post(f"{BASE_URL}/placement/shortlist", json=payload)
        self.assertEqual(res.status_code, 401)

    def test_09_application_status_updated_to_shortlisted(self):
        """Test 9: Shortlisting a candidate updates their existing Application status to 'shortlisted'."""
        # 1. Create a third temp job
        job_payload = {
            "company_id": self.company_id,
            "title": "Job for App Status Update",
            "required_skills": ["Python"],
            "cgpa_criteria": 5.0,
            "branch_eligibility": ["AIML"],
            "status": "open"
        }
        app_job = requests.post(f"{BASE_URL}/placement/jobs", headers=self.po_headers, json=job_payload).json()
        self.created_jobs.append(app_job["id"])

        # 2. Student A applies to this job
        app_res = requests.post(
            f"{BASE_URL}/placement/applications",
            headers=self.s_headers,
            json={"job_posting_id": app_job["id"], "notes": "E2E status test"}
        )
        self.assertEqual(app_res.status_code, 200)
        app_data = app_res.json()
        self.created_applications.append(app_data["id"])
        self.assertEqual(app_data["status"], "applied")

        # 3. Placement Officer shortlists Student A for this job
        shortlist_res = requests.post(
            f"{BASE_URL}/placement/shortlist",
            headers=self.po_headers,
            json={
                "job_posting_id": app_job["id"],
                "company_id": self.company_id,
                "student_id": self.s_user["id"],
                "reason": "Strong profile"
            }
        )
        self.assertEqual(shortlist_res.status_code, 200)
        self.created_shortlists.append(shortlist_res.json()["id"])

        # 4. Fetch the application and verify status transitioned to 'shortlisted'
        fetched_app = requests.get(
            f"{BASE_URL}/placement/applications/{app_data['id']}",
            headers=self.s_headers
        ).json()
        self.assertEqual(fetched_app["status"], "shortlisted")


if __name__ == "__main__":
    unittest.main()
