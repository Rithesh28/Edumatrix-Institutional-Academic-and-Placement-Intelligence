"""
EduMatrix Phase 3.2 — Step 2.1: External Application URLs Test Suite

Verifies:
1. Placement Officer can create a job posting with a valid HTTPS application URL.
2. Placement Officer can update a job posting with a valid HTTP application URL.
3. API rejects unsafe URL schemes (javascript:, file:, data:) with HTTP 422 on creation and update.
4. Jobs with no URL (None or empty) are accepted and default to None without crashing.
5. URL persists accurately after saving, reloading, and publishing.
6. Authorized students can read the application_url for OPEN jobs.
7. Students are strictly forbidden from modifying job postings or URLs (HTTP 403).
8. Unauthenticated requests are rejected (HTTP 401).
9. Full integration non-regression: eligibility checks and matching work identically with application_url present.
"""

import unittest
import requests

BASE_URL = "http://localhost:8000"


class TestExternalApplicationUrl(unittest.TestCase):
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
            data={"username": "adi01@gmail.com", "password": "12345"}
        )
        if s_login.status_code != 200:
            s_login = requests.post(
                f"{BASE_URL}/auth/login",
                data={"username": "adi01@gmail.com", "password": "54321"}
            )
        assert s_login.status_code == 200, f"Student login failed: {s_login.text}"
        cls.s_token = s_login.json()["access_token"]
        cls.s_headers = {"Authorization": f"Bearer {cls.s_token}"}
        cls.s_user = s_login.json()["user"]

        # 3. Retrieve or create a company for test jobs
        comp_res = requests.get(f"{BASE_URL}/placement/companies", headers=cls.po_headers)
        companies = comp_res.json()
        if companies:
            cls.company_id = companies[0]["id"]
        else:
            new_comp = requests.post(
                f"{BASE_URL}/placement/companies",
                headers=cls.po_headers,
                json={"name": "External URL Test Corp", "industry": "Technology", "location": "Bangalore"}
            )
            cls.company_id = new_comp.json()["id"]

    def test_01_create_job_with_valid_https_url(self):
        """Verify Placement Officer can create a job with a valid HTTPS application URL."""
        payload = {
            "company_id": self.company_id,
            "title": "Software Engineer (External URL HTTPS Test)",
            "description": "Role requires applying via official careers portal.",
            "application_url": "https://careers.example.com/jobs/swe-2026",
            "required_skills": ["Python", "React", "PostgreSQL"],
            "preferred_skills": ["Docker"],
            "cgpa_criteria": 7.0,
            "branch_eligibility": ["Computer Science", "Information Technology"],
            "location": "Bangalore (Hybrid)",
            "salary_range": "10 - 14 LPA",
            "status": "draft"
        }
        res = requests.post(f"{BASE_URL}/placement/jobs", headers=self.po_headers, json=payload)
        self.assertEqual(res.status_code, 200, f"Failed to create job: {res.text}")
        data = res.json()
        self.assertIn("id", data)
        self.assertEqual(data["application_url"], "https://careers.example.com/jobs/swe-2026")

        # Verify persistence on re-fetch
        job_id = data["id"]
        fetch_res = requests.get(f"{BASE_URL}/placement/jobs/{job_id}", headers=self.po_headers)
        self.assertEqual(fetch_res.status_code, 200)
        self.assertEqual(fetch_res.json()["application_url"], "https://careers.example.com/jobs/swe-2026")

    def test_02_update_job_with_valid_http_url(self):
        """Verify Placement Officer can update a job with a valid HTTP URL."""
        # Create initial job
        create_res = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_id,
                "title": "Data Analyst (HTTP URL Update Test)",
                "required_skills": ["Python", "SQL"],
                "status": "draft"
            }
        )
        self.assertEqual(create_res.status_code, 200)
        job_id = create_res.json()["id"]

        # Update with HTTP URL
        update_res = requests.put(
            f"{BASE_URL}/placement/jobs/{job_id}",
            headers=self.po_headers,
            json={"application_url": "http://careers.partner.org/apply/da-401"}
        )
        self.assertEqual(update_res.status_code, 200)
        self.assertEqual(update_res.json()["application_url"], "http://careers.partner.org/apply/da-401")

        # Verify persistence
        fetch_res = requests.get(f"{BASE_URL}/placement/jobs/{job_id}", headers=self.po_headers)
        self.assertEqual(fetch_res.json()["application_url"], "http://careers.partner.org/apply/da-401")

    def test_03_reject_unsafe_url_schemes_on_create(self):
        """Verify API rejects unsafe schemes (javascript:, file:, data:) with HTTP 422."""
        unsafe_schemes = [
            "javascript:alert(1)",
            "javascript:window.location='http://attacker.com'",
            "file:///etc/passwd",
            "file:///C:/Windows/System32",
            "data:text/html,<script>alert(1)</script>",
            "ftp://ftp.example.com/jobs",
            "mailto:jobs@example.com",
            "not_even_a_url",
            "https://"  # missing host
        ]
        for bad_url in unsafe_schemes:
            payload = {
                "company_id": self.company_id,
                "title": f"Unsafe URL Test ({bad_url[:15]})",
                "application_url": bad_url,
                "required_skills": ["Python"],
                "status": "draft"
            }
            res = requests.post(f"{BASE_URL}/placement/jobs", headers=self.po_headers, json=payload)
            self.assertEqual(
                res.status_code, 422,
                f"Expected HTTP 422 for unsafe scheme '{bad_url}', got {res.status_code}: {res.text}"
            )

    def test_04_reject_unsafe_url_schemes_on_update(self):
        """Verify API rejects unsafe schemes on PUT /placement/jobs/{id}."""
        create_res = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_id,
                "title": "Job for Update Scheme Test",
                "required_skills": ["Python"],
                "status": "draft"
            }
        )
        job_id = create_res.json()["id"]

        update_res = requests.put(
            f"{BASE_URL}/placement/jobs/{job_id}",
            headers=self.po_headers,
            json={"application_url": "javascript:void(0)"}
        )
        self.assertEqual(update_res.status_code, 422)

    def test_05_legacy_or_empty_job_has_none_application_url(self):
        """Verify jobs created with no application_url or empty string default to None."""
        # 1. Omitted field
        res1 = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_id,
                "title": "No URL Test Job",
                "required_skills": ["Java"],
                "status": "draft"
            }
        )
        self.assertEqual(res1.status_code, 200)
        self.assertIsNone(res1.json().get("application_url"))

        # 2. Empty string is normalized to None
        res2 = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_id,
                "title": "Empty String URL Test Job",
                "application_url": "   ",
                "required_skills": ["Java"],
                "status": "draft"
            }
        )
        self.assertEqual(res2.status_code, 200)
        self.assertIsNone(res2.json().get("application_url"))

    def test_06_students_can_read_application_url_for_open_jobs(self):
        """Verify authenticated students can read application_url on open job postings."""
        # 1. Create and publish job with URL
        create_res = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_id,
                "title": "Open Job with External Portal",
                "application_url": "https://careers.google.com/jobs/results/9999",
                "required_skills": ["Python", "FastAPI"],
                "status": "draft"
            }
        )
        job_id = create_res.json()["id"]

        # Publish the job so it becomes visible to students (status -> open)
        pub_res = requests.put(
            f"{BASE_URL}/placement/jobs/{job_id}",
            headers=self.po_headers,
            json={"status": "open"}
        )
        self.assertEqual(pub_res.status_code, 200)

        # 2. Student retrieves the job
        student_res = requests.get(f"{BASE_URL}/placement/jobs/{job_id}", headers=self.s_headers)
        self.assertEqual(student_res.status_code, 200)
        student_data = student_res.json()
        self.assertEqual(student_data["application_url"], "https://careers.google.com/jobs/results/9999")
        self.assertEqual(student_data["status"], "open")

    def test_07_students_forbidden_from_modifying_jobs_or_urls(self):
        """Verify student role cannot create or update job postings (HTTP 403)."""
        # Create a job as PO
        create_res = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_id,
                "title": "Student Modification Protection Job",
                "application_url": "https://original.com/apply",
                "required_skills": ["Python"],
                "status": "open"
            }
        )
        job_id = create_res.json()["id"]

        # Student attempts to modify job
        modify_res = requests.put(
            f"{BASE_URL}/placement/jobs/{job_id}",
            headers=self.s_headers,
            json={"application_url": "https://hacked.com/apply"}
        )
        self.assertEqual(modify_res.status_code, 403)

        # Student attempts to create a job
        create_attempt = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.s_headers,
            json={
                "company_id": self.company_id,
                "title": "Student Created Job",
                "application_url": "https://rogue.com/apply",
                "required_skills": ["Hacking"],
                "status": "open"
            }
        )
        self.assertEqual(create_attempt.status_code, 403)

    def test_08_unauthenticated_requests_rejected(self):
        """Verify unauthenticated requests cannot create or update jobs."""
        unauth_create = requests.post(
            f"{BASE_URL}/placement/jobs",
            json={"company_id": self.company_id, "title": "Unauth Job", "required_skills": ["Go"]}
        )
        self.assertEqual(unauth_create.status_code, 401)

        unauth_update = requests.put(
            f"{BASE_URL}/placement/jobs/1",
            json={"application_url": "https://unauth.com"}
        )
        self.assertEqual(unauth_update.status_code, 401)

    def test_09_eligibility_and_matching_unaffected_by_application_url(self):
        """Verify skill matching and eligibility checks work flawlessly on jobs with application_url."""
        # 1. Create and publish job with URL and requirements
        create_res = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_id,
                "title": "Eligibility Compatibility Check Job",
                "application_url": "https://careers.amazon.jobs/apply",
                "required_skills": ["Python", "SQL"],
                "preferred_skills": ["AWS"],
                "cgpa_criteria": 6.0,
                "status": "open"
            }
        )
        job_id = create_res.json()["id"]

        # 2. Check eligibility for student
        elig_res = requests.get(
            f"{BASE_URL}/placement/jobs/{job_id}/check-eligibility/{self.s_user['id']}",
            headers=self.s_headers
        )
        self.assertEqual(elig_res.status_code, 200)
        elig_data = elig_res.json()
        self.assertIn("is_eligible", elig_data)
        self.assertIn("overall_skill_match", elig_data)
        self.assertIn("cgpa_match", elig_data)


if __name__ == "__main__":
    unittest.main()
