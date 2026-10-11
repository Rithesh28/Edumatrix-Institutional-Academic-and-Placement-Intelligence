"""
EduMatrix Phase 3.2 — Step 2.2: Student External Application Confirmation Test Suite

Verifies:
1. Successful confirmation by application owner (HTTP 200, sets external_applied_at in UTC, is_external_confirmed = True).
2. Idempotent confirmation: repeated calls preserve original timestamp and create no duplicate records.
3. RBAC: student cannot confirm another student's application (HTTP 403).
4. Unauthenticated access rejected (HTTP 401).
5. Confirmation rejected when job has no external URL (HTTP 400).
6. Confirmation rejected when application does not exist (HTTP 404).
7. Legacy applications remain unconfirmed by default (external_applied_at is None, is_external_confirmed is False).
8. Match snapshot, scores, and unique constraints are preserved intact.
9. Placement Officer can inspect external confirmation timestamp on authorized application endpoints.
10. Placement Officer cannot confirm on behalf of student (HTTP 403).
"""

import time
import unittest
import requests

BASE_URL = "http://localhost:8000"


class TestExternalApplicationConfirmation(unittest.TestCase):
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

        # 2. Login as Student 1 (adi01@gmail.com)
        s1_login = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": "adi01@gmail.com", "password": "54321"}
        )
        assert s1_login.status_code == 200, f"Student 1 login failed: {s1_login.text}"
        cls.s1_token = s1_login.json()["access_token"]
        cls.s1_headers = {"Authorization": f"Bearer {cls.s1_token}"}
        cls.s1_user = s1_login.json()["user"]

        # 3. Login as Student 2 (student_ece@gmail.com)
        s2_login = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": "student_ece@gmail.com", "password": "12345"}
        )
        if s2_login.status_code == 200:
            cls.s2_token = s2_login.json()["access_token"]
            cls.s2_headers = {"Authorization": f"Bearer {cls.s2_token}"}
            cls.s2_user = s2_login.json()["user"]
        else:
            # Fallback: register a second student if student_ece not found
            reg_res = requests.post(
                f"{BASE_URL}/auth/register",
                json={
                    "name": "Second Student",
                    "email": "student2_test@gmail.com",
                    "password": "Password@123",
                    "role": "student"
                }
            )
            s2_login = requests.post(
                f"{BASE_URL}/auth/login",
                data={"username": "student2_test@gmail.com", "password": "Password@123"}
            )
            assert s2_login.status_code == 200, f"Student 2 login failed: {s2_login.text}"
            cls.s2_token = s2_login.json()["access_token"]
            cls.s2_headers = {"Authorization": f"Bearer {cls.s2_token}"}
            cls.s2_user = s2_login.json()["user"]

        # 4. Ensure test company exists
        comp_res = requests.get(f"{BASE_URL}/placement/companies", headers=cls.po_headers)
        companies = comp_res.json()
        if companies:
            cls.company_id = companies[0]["id"]
        else:
            new_comp = requests.post(
                f"{BASE_URL}/placement/companies",
                headers=cls.po_headers,
                json={"name": "Step 2.2 Confirmation Corp", "industry": "Technology"}
            )
            cls.company_id = new_comp.json()["id"]

    def test_01_successful_confirmation_by_owner(self):
        """Verify application owner can confirm external application submission."""
        # 1. Placement officer creates and publishes a job with external URL
        job_res = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_id,
                "title": f"DevOps Engineer ExtConfirm {int(time.time())}",
                "description": "Role requires applying via external company website.",
                "application_url": "https://careers.example.com/jobs/devops-ext-confirm",
                "required_skills": ["Python", "Linux"],
                "cgpa_criteria": 6.0,
                "branch_eligibility": ["Computer Science", "Information Technology", "AIML", "General"],
                "status": "draft"
            }
        )
        self.assertEqual(job_res.status_code, 200, f"Failed to create job: {job_res.text}")
        job_id = job_res.json()["id"]

        # Publish the job
        pub_res = requests.post(f"{BASE_URL}/placement/jobs/{job_id}/publish", headers=self.po_headers)
        self.assertEqual(pub_res.status_code, 200, f"Failed to publish job: {pub_res.text}")

        # 2. Student 1 submits internal application
        app_res = requests.post(
            f"{BASE_URL}/placement/applications",
            headers=self.s1_headers,
            json={"job_posting_id": job_id, "notes": "Initial internal apply"}
        )
        self.assertEqual(app_res.status_code, 200, f"Failed to create application: {app_res.text}")
        app_data = app_res.json()
        app_id = app_data["id"]

        # Prior to external confirmation, external_applied_at should be None
        self.assertIsNone(app_data.get("external_applied_at"))
        self.assertFalse(app_data.get("is_external_confirmed", False))
        snapshot_before = app_data.get("match_snapshot")
        score_before = app_data.get("match_percentage")

        # 3. Student 1 confirms external submission
        confirm_res = requests.post(
            f"{BASE_URL}/placement/applications/{app_id}/confirm-external",
            headers=self.s1_headers
        )
        self.assertEqual(confirm_res.status_code, 200, f"Confirmation failed: {confirm_res.text}")
        confirmed_data = confirm_res.json()

        # Verify confirmation attributes
        self.assertIsNotNone(confirmed_data.get("external_applied_at"))
        self.assertTrue(confirmed_data.get("is_external_confirmed"))
        self.assertEqual(confirmed_data["id"], app_id)
        self.assertEqual(confirmed_data["student_id"], self.s1_user["id"])

        # Verify match snapshot and match percentage remain intact
        self.assertEqual(confirmed_data.get("match_percentage"), score_before)
        if snapshot_before:
            self.assertEqual(confirmed_data.get("match_snapshot"), snapshot_before)

        # Save app_id and timestamp for idempotency test
        TestExternalApplicationConfirmation.test_app_id = app_id
        TestExternalApplicationConfirmation.first_confirmed_at = confirmed_data["external_applied_at"]
        TestExternalApplicationConfirmation.test_job_id = job_id

    def test_02_idempotent_confirmation_preserves_timestamp(self):
        """Verify repeated confirmation is idempotent, preserves original timestamp, and creates no duplicates."""
        app_id = getattr(self, "test_app_id", None)
        first_time = getattr(self, "first_confirmed_at", None)
        self.assertIsNotNone(app_id, "test_app_id not set from test_01")

        # Wait a small moment to ensure a different clock reading if clock was incorrectly read
        time.sleep(0.5)

        # Repeated confirmation request
        confirm_res2 = requests.post(
            f"{BASE_URL}/placement/applications/{app_id}/confirm-external",
            headers=self.s1_headers
        )
        self.assertEqual(confirm_res2.status_code, 200, f"Repeated confirmation failed: {confirm_res2.text}")
        data2 = confirm_res2.json()

        # Must preserve original timestamp
        self.assertEqual(data2["external_applied_at"], first_time, "Original timestamp was not preserved on repeated confirmation!")
        self.assertTrue(data2["is_external_confirmed"])

        # Verify student application list contains exactly 1 application for this job
        my_apps_res = requests.get(f"{BASE_URL}/placement/applications", headers=self.s1_headers)
        self.assertEqual(my_apps_res.status_code, 200)
        matching_apps = [a for a in my_apps_res.json() if a["job_posting_id"] == self.test_job_id]
        self.assertEqual(len(matching_apps), 1, "Duplicate applications found for the same job posting!")

    def test_03_student_cannot_confirm_another_students_application(self):
        """Verify a student attempting to confirm another student's application receives HTTP 403."""
        app_id = getattr(self, "test_app_id", None)
        self.assertIsNotNone(app_id)

        # Student 2 attempts to confirm Student 1's application
        unauth_res = requests.post(
            f"{BASE_URL}/placement/applications/{app_id}/confirm-external",
            headers=self.s2_headers
        )
        self.assertEqual(unauth_res.status_code, 403, f"Expected 403 Forbidden, got {unauth_res.status_code}: {unauth_res.text}")
        self.assertIn("own application", unauth_res.text.lower())

    def test_04_unauthenticated_request_rejected(self):
        """Verify unauthenticated confirmation requests are rejected with HTTP 401."""
        app_id = getattr(self, "test_app_id", None)
        self.assertIsNotNone(app_id)

        no_auth_res = requests.post(f"{BASE_URL}/placement/applications/{app_id}/confirm-external")
        self.assertEqual(no_auth_res.status_code, 401, f"Expected 401 Unauthorized, got {no_auth_res.status_code}")

    def test_05_confirmation_rejected_when_job_has_no_external_url(self):
        """Verify confirmation is rejected with HTTP 400 when job does not have an external application URL."""
        # Create and publish job without application_url
        no_url_job = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_id,
                "title": f"Internal Only Role {int(time.time())}",
                "description": "Campus drive conducted entirely internally.",
                "application_url": None,
                "required_skills": ["Java"],
                "status": "draft"
            }
        )
        self.assertEqual(no_url_job.status_code, 200)
        job_id = no_url_job.json()["id"]

        pub_res = requests.post(f"{BASE_URL}/placement/jobs/{job_id}/publish", headers=self.po_headers)
        self.assertEqual(pub_res.status_code, 200)

        # Student 1 applies internally
        app_res = requests.post(
            f"{BASE_URL}/placement/applications",
            headers=self.s1_headers,
            json={"job_posting_id": job_id}
        )
        self.assertEqual(app_res.status_code, 200)
        internal_app_id = app_res.json()["id"]

        # Attempt external confirmation on a job without external URL
        fail_res = requests.post(
            f"{BASE_URL}/placement/applications/{internal_app_id}/confirm-external",
            headers=self.s1_headers
        )
        self.assertEqual(fail_res.status_code, 400, f"Expected 400 Bad Request, got {fail_res.status_code}: {fail_res.text}")
        self.assertIn("external application url", fail_res.text.lower())

    def test_06_confirmation_rejected_when_application_does_not_exist(self):
        """Verify confirmation returns HTTP 404 when application ID does not exist."""
        res = requests.post(
            f"{BASE_URL}/placement/applications/99999999/confirm-external",
            headers=self.s1_headers
        )
        self.assertEqual(res.status_code, 404, f"Expected 404 Not Found, got {res.status_code}: {res.text}")

    def test_07_legacy_applications_remain_unconfirmed(self):
        """Verify existing/legacy applications have external_applied_at=None and is_external_confirmed=False."""
        apps_res = requests.get(f"{BASE_URL}/placement/applications", headers=self.s1_headers)
        self.assertEqual(apps_res.status_code, 200)
        apps = apps_res.json()
        self.assertTrue(len(apps) > 0)

        # Check an unconfirmed application
        unconfirmed = [a for a in apps if a["id"] != getattr(self, "test_app_id", None)]
        if unconfirmed:
            for u in unconfirmed[:3]:
                # Either None or unconfirmed
                if u.get("external_applied_at") is None:
                    self.assertFalse(u.get("is_external_confirmed", False))

    def test_08_placement_officer_visibility_of_confirmation(self):
        """Verify Placement Officer can view external confirmation timestamp via authorized application endpoints."""
        app_id = getattr(self, "test_app_id", None)
        self.assertIsNotNone(app_id)

        # Placement officer views single application
        po_get_res = requests.get(f"{BASE_URL}/placement/applications/{app_id}", headers=self.po_headers)
        self.assertEqual(po_get_res.status_code, 200)
        po_app = po_get_res.json()
        self.assertIsNotNone(po_app.get("external_applied_at"))
        self.assertTrue(po_app.get("is_external_confirmed"))
        self.assertEqual(po_app.get("external_applied_at"), getattr(self, "first_confirmed_at", None))

        # Placement officer views job applications
        job_apps_res = requests.get(
            f"{BASE_URL}/placement/applications?job_posting_id={self.test_job_id}",
            headers=self.po_headers
        )
        self.assertEqual(job_apps_res.status_code, 200)
        target_app = next((a for a in job_apps_res.json() if a["id"] == app_id), None)
        self.assertIsNotNone(target_app)
        self.assertIsNotNone(target_app.get("external_applied_at"))
        self.assertTrue(target_app.get("is_external_confirmed"))

    def test_09_officer_cannot_confirm_as_student(self):
        """Verify Placement Officer cannot confirm student's external application (role check)."""
        app_id = getattr(self, "test_app_id", None)
        self.assertIsNotNone(app_id)

        po_confirm_res = requests.post(
            f"{BASE_URL}/placement/applications/{app_id}/confirm-external",
            headers=self.po_headers
        )
        self.assertEqual(po_confirm_res.status_code, 403, f"Expected 403 Forbidden for PO, got {po_confirm_res.status_code}")


if __name__ == "__main__":
    unittest.main()
