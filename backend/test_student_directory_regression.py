"""
EduMatrix Phase 3.2 — Student Directory Regression Test Suite

Verifies:
1. Successful student retrieval by Placement Officer (HTTP 200 with complete academic & application data).
2. Application timestamp serialization (ensures 'created_at' and 'applied_at' do not raise AttributeError).
3. Students without extended profiles are handled gracefully without 500 error or being omitted.
4. Search and placement_status query parameter filtering.
5. Empty query result handling (returns HTTP 200 with [] when no matches).
6. RBAC rejection (HTTP 401 for unauthenticated, HTTP 403 for student role on directory endpoint).
7. Student detail endpoint permissions (Student can view own details, blocked from other students' details).
"""

import unittest
import requests

BASE_URL = "http://localhost:8000"


class TestStudentDirectoryRegression(unittest.TestCase):
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

        # 2. Login as Student (adi01@gmail.com, ID: 1)
        s_login = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": "adi01@gmail.com", "password": "54321"}
        )
        assert s_login.status_code == 200, f"Student login failed: {s_login.text}"
        cls.s_token = s_login.json()["access_token"]
        cls.s_headers = {"Authorization": f"Bearer {cls.s_token}"}
        cls.s_user = s_login.json()["user"]

    def test_01_successful_student_directory_retrieval(self):
        """Verify Placement Officer can retrieve student directory (HTTP 200)."""
        res = requests.get(f"{BASE_URL}/placement/students", headers=self.po_headers)
        self.assertEqual(res.status_code, 200, f"Expected 200, got {res.status_code}: {res.text}")
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0, "Expected at least one registered student")

        # Verify record shape
        sample = data[0]
        self.assertIn("id", sample)
        self.assertIn("name", sample)
        self.assertIn("email", sample)
        self.assertIn("department", sample)
        self.assertIn("status", sample)
        self.assertIn("placement_status", sample)
        self.assertIn("skills", sample)
        self.assertIn("applications", sample)
        self.assertIn("total_applications", sample)

    def test_02_application_serialization_has_created_at_and_applied_at(self):
        """Verify students with applications serialize timestamps without AttributeError."""
        res = requests.get(f"{BASE_URL}/placement/students", headers=self.po_headers)
        self.assertEqual(res.status_code, 200)
        students = res.json()

        # Find any student with applications (e.g. mani@gmail.com)
        students_with_apps = [s for s in students if s.get("total_applications", 0) > 0]
        if students_with_apps:
            student = students_with_apps[0]
            apps = student["applications"]
            self.assertGreater(len(apps), 0)
            app = apps[0]
            self.assertIn("id", app)
            self.assertIn("job_id", app)
            self.assertIn("status", app)
            self.assertIn("created_at", app)
            self.assertIn("applied_at", app)
            # Timestamps must be valid ISO strings if present
            if app["applied_at"]:
                self.assertIsInstance(app["applied_at"], str)
            if app["created_at"]:
                self.assertIsInstance(app["created_at"], str)

    def test_03_students_without_profile_handled_gracefully(self):
        """Verify students missing an extended profile are rendered with fallback data and no 500 error."""
        res = requests.get(f"{BASE_URL}/placement/students", headers=self.po_headers)
        self.assertEqual(res.status_code, 200)
        students = res.json()

        # Check that none of the students crashed or have None for name/department/status
        for s in students:
            self.assertIsNotNone(s.get("id"))
            self.assertIsNotNone(s.get("name"))
            self.assertIsNotNone(s.get("department"))
            self.assertIsNotNone(s.get("status"))
            self.assertIsInstance(s.get("skills"), list)
            self.assertIsInstance(s.get("applications"), list)

    def test_04_search_and_status_filtering(self):
        """Verify search query parameter filters students by name/email/department."""
        # Search by specific student name
        res = requests.get(f"{BASE_URL}/placement/students?search=Adithya", headers=self.po_headers)
        self.assertEqual(res.status_code, 200)
        results = res.json()
        self.assertTrue(all("adithya" in s["name"].lower() or "adithya" in s["email"].lower() for s in results))

        # Filter by placement status
        res_applied = requests.get(f"{BASE_URL}/placement/students?placement_status=applied", headers=self.po_headers)
        self.assertEqual(res_applied.status_code, 200)
        applied_results = res_applied.json()
        self.assertTrue(all(s["status"] == "applied" for s in applied_results))

    def test_05_empty_database_result_returns_200_empty_list(self):
        """Verify querying non-existent student search returns HTTP 200 with empty list []."""
        res = requests.get(
            f"{BASE_URL}/placement/students?search=non_existent_student_xyz_99999",
            headers=self.po_headers
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])

    def test_06_rbac_unauthenticated_request_rejected(self):
        """Verify unauthenticated request to /placement/students returns HTTP 401."""
        res = requests.get(f"{BASE_URL}/placement/students")
        self.assertEqual(res.status_code, 401)

    def test_07_rbac_student_role_rejected(self):
        """Verify student role attempting to access /placement/students returns HTTP 403."""
        res = requests.get(f"{BASE_URL}/placement/students", headers=self.s_headers)
        self.assertEqual(res.status_code, 403)

    def test_08_student_details_endpoint_rbac_and_data(self):
        """Verify placement officer can view student details, and student self-access permissions."""
        student_id = self.s_user["id"]

        # 1. Placement officer can view student details
        po_res = requests.get(f"{BASE_URL}/placement/students/{student_id}", headers=self.po_headers)
        self.assertEqual(po_res.status_code, 200)
        data = po_res.json()
        self.assertEqual(data["id"], student_id)
        self.assertIn("skills", data)
        self.assertIn("applications", data)
        self.assertIn("resumes", data)

        # 2. Student can view own details
        s_self_res = requests.get(f"{BASE_URL}/placement/students/{student_id}", headers=self.s_headers)
        self.assertEqual(s_self_res.status_code, 200)

        # 3. Student cannot view other student's details (e.g. ID 68)
        s_other_res = requests.get(f"{BASE_URL}/placement/students/68", headers=self.s_headers)
        self.assertEqual(s_other_res.status_code, 403)


if __name__ == "__main__":
    unittest.main()
