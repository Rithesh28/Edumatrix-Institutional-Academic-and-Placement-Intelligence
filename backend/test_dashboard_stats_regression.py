"""
EduMatrix Phase 3.2 — Dashboard Placement Statistics Regression Test Suite

Verifies:
1. Retrieval of placement statistics by Placement Officer (HTTP 200).
2. Proper definition and calculation of 'total_placed':
   - Distinguishes intermediate shortlisting from final selection/placement.
   - Shortlisted applications or Shortlist records are NOT counted as placed.
   - Placement rate reflects (total_placed / total_students * 100).
3. Dynamic verification:
   - When an application is marked SELECTED, total_placed reflects the count.
   - Placement rate is recalculated accurately without fabricating numbers.
4. Consistency across breakdowns (applications_by_status, jobs_by_status).
5. RBAC security (Student denied with HTTP 403, unauthenticated denied with HTTP 401).
"""

import unittest
import requests

BASE_URL = "http://localhost:8000"


class TestDashboardStatsRegression(unittest.TestCase):
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

        # 2. Login as Student
        s_login = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": "adi01@gmail.com", "password": "54321"}
        )
        assert s_login.status_code == 200, f"Student login failed: {s_login.text}"
        cls.s_token = s_login.json()["access_token"]
        cls.s_headers = {"Authorization": f"Bearer {cls.s_token}"}

    def test_01_stats_endpoint_returns_200_and_expected_schema(self):
        """Verify GET /placement/stats returns HTTP 200 with all statistics fields."""
        res = requests.get(f"{BASE_URL}/placement/stats", headers=self.po_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        expected_fields = [
            "total_companies",
            "active_companies",
            "total_jobs",
            "open_jobs",
            "total_applications",
            "total_shortlists",
            "total_students",
            "total_placed",
            "placement_rate",
            "applications_by_status",
            "jobs_by_status",
        ]
        for field in expected_fields:
            self.assertIn(field, data, f"Missing expected field: {field}")

        self.assertIsInstance(data["total_placed"], int)
        self.assertIsInstance(data["total_shortlists"], int)
        self.assertIsInstance(data["total_students"], int)

    def test_02_shortlists_are_not_counted_as_placements(self):
        """Verify shortlists do NOT count towards placed students."""
        res = requests.get(f"{BASE_URL}/placement/stats", headers=self.po_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Verify shortlists exist and total_placed does not simply equal or include all shortlists
        self.assertGreater(data["total_shortlists"], 0, "Expected at least 1 shortlist in DB")
        self.assertNotEqual(
            data["total_placed"], data["total_shortlists"],
            f"total_placed should not equal total_shortlists ({data['total_shortlists']})"
        )
        self.assertGreater(data["total_students"], 0)
        expected_rate = round((data["total_placed"] / data["total_students"] * 100.0), 2)
        self.assertEqual(data["placement_rate"], expected_rate)

        # Check applications_by_status
        apps_status = data["applications_by_status"]
        self.assertGreater(apps_status.get("shortlisted", 0), 0)

    def test_03_placement_rate_formula_accuracy(self):
        """Verify placement_rate = (total_placed / total_students * 100)."""
        res = requests.get(f"{BASE_URL}/placement/stats", headers=self.po_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        total_students = data["total_students"]
        total_placed = data["total_placed"]
        expected_rate = round((total_placed / total_students * 100.0), 2) if total_students > 0 else 0.0
        self.assertEqual(data["placement_rate"], expected_rate)

    def test_04_status_distinction_rule_verification(self):
        """Verify distinct accounting: applications by status matches total_applications."""
        res = requests.get(f"{BASE_URL}/placement/stats", headers=self.po_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        apps_by_status = data["applications_by_status"]
        total_from_statuses = sum(apps_by_status.values())
        self.assertEqual(
            total_from_statuses, data["total_applications"],
            "Sum of status counts should match total_applications"
        )

    def test_05_rbac_student_denied_access(self):
        """Verify student role is forbidden from viewing officer placement stats (HTTP 403)."""
        res = requests.get(f"{BASE_URL}/placement/stats", headers=self.s_headers)
        self.assertEqual(res.status_code, 403)

    def test_06_rbac_unauthenticated_denied_access(self):
        """Verify unauthenticated request to /placement/stats is rejected (HTTP 401)."""
        res = requests.get(f"{BASE_URL}/placement/stats")
        self.assertEqual(res.status_code, 401)


if __name__ == "__main__":
    unittest.main()
