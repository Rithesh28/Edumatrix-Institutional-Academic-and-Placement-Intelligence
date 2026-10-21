"""
EduMatrix Automated Test Suite: Recruitment Drive Job Navigation + Attachment Preview/Download

Validates:
1. Linked Job Navigation:
   - Published drive linked job detail retrieval as an authorized student.
   - Job ID consistency between drive data, link construction, and backend detail lookup.
   - Reopening of previously closed linked jobs and deadline synchronization.
   - Inaccessibility of unlinked draft jobs to students (returns 404).
   - Correct student eligibility check on linked jobs.
   - Standalone job navigation and external URL support.

2. Attachment Preview & Download:
   - Preview of image attachments with inline Content-Disposition and image MIME type.
   - Preview of PDF attachments inline.
   - Download of original image with matching bytes and filename.
   - Download of original PDF document with matching bytes and filename.
   - 404 handling on nonexistent attachments or circulars.
   - 401 / 403 rejection for unauthenticated users or academic faculty.
   - Direct verification that /v1 and /api/v1 prefixes resolve identically without proxy 404s.
"""

import unittest
import time
import io
import requests

BASE_URL = "http://localhost:8000"


class TestRecruitmentDriveNavigationAndAttachments(unittest.TestCase):
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

        # 2. Login as Student (adi01@gmail.com - CSE)
        s1_login = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": "adi01@gmail.com", "password": "54321"}
        )
        assert s1_login.status_code == 200, f"Student login failed: {s1_login.text}"
        cls.s1_token = s1_login.json()["access_token"]
        cls.s1_headers = {"Authorization": f"Bearer {cls.s1_token}"}
        cls.s1_user = s1_login.json()["user"]

        # 3. Create Lecturer token for RBAC testing
        try:
            from app.core.database import SessionLocal
            from app.models.user import User
            from app.core.security import create_access_token
            _db = SessionLocal()
            _lec = _db.query(User).filter_by(role="lecturer").first()
            if _lec:
                cls.lec_token = create_access_token({"id": _lec.id, "sub": _lec.email, "role": _lec.role.value})
                cls.lec_headers = {"Authorization": f"Bearer {cls.lec_token}"}
            else:
                cls.lec_headers = None
            _db.close()
        except Exception:
            cls.lec_headers = None

        # 4. Create a test company
        ts = int(time.time() * 1000)
        co_res = requests.post(
            f"{BASE_URL}/placement/companies",
            json={
                "name": f"NavAttach Tech {ts}",
                "website": "https://navattach.example.com",
                "industry": "Software",
                "location": "Bangalore"
            },
            headers=cls.po_headers
        )
        assert co_res.status_code in [200, 201], f"Company creation failed: {co_res.text}"
        cls.company_id = co_res.json()["id"]

    def test_01_published_drive_with_linked_job_opens_for_student(self):
        """Published drive with a linked job allows student to view full job details."""
        ts = int(time.time() * 1000)
        # Create a job with required skills
        job_res = requests.post(
            f"{BASE_URL}/placement/jobs",
            json={
                "company_id": self.company_id,
                "title": f"Associate Cloud Engineer {ts}",
                "description": "Full-stack cloud engineering role",
                "required_skills": ["Python", "Docker", "AWS"],
                "experience_level": "Fresher",
                "salary_range": "6-8 LPA",
                "location": "Bangalore",
                "branch_eligibility": ["CSE", "ISE", "AIML"],
                "application_url": "https://careers.navattach.example.com/apply/123",
            },
            headers=self.po_headers
        )
        self.assertEqual(job_res.status_code, 200)
        job_id = job_res.json()["id"]

        # Create recruitment drive circular
        circ_res = requests.post(
            f"{BASE_URL}/placement/circulars",
            json={
                "company_id": self.company_id,
                "title": f"NavAttach Campus Drive 2027 {ts}",
                "summary": "Annual campus hiring drive for software roles",
                "branch_eligibility": ["CSE", "ISE", "AIML"],
                "job_posting_ids": [job_id],
            },
            headers=self.po_headers
        )
        self.assertIn(circ_res.status_code, [200, 201])
        circ_id = circ_res.json()["id"]

        # Publish the recruitment drive
        pub_res = requests.post(
            f"{BASE_URL}/placement/circulars/{circ_id}/publish",
            json={"confirm_no_skills": False},
            headers=self.po_headers
        )
        self.assertEqual(pub_res.status_code, 200)

        # Student opens recruitment circular details
        student_circ_res = requests.get(
            f"{BASE_URL}/placement/circulars/{circ_id}",
            headers=self.s1_headers
        )
        self.assertEqual(student_circ_res.status_code, 200)
        circ_data = student_circ_res.json()
        self.assertEqual(len(circ_data["linked_jobs"]), 1)
        linked_role = circ_data["linked_jobs"][0]
        
        # Verify job ID consistency between drive data and link target
        target_job_id = linked_role["job_posting_id"]
        self.assertEqual(target_job_id, job_id)

        # Student navigates to job detail endpoint
        student_job_res = requests.get(
            f"{BASE_URL}/placement/jobs/{target_job_id}",
            headers=self.s1_headers
        )
        self.assertEqual(student_job_res.status_code, 200)
        job_data = student_job_res.json()
        self.assertEqual(job_data["id"], job_id)
        self.assertEqual(job_data["title"], f"Associate Cloud Engineer {ts}")
        self.assertEqual(job_data["status"], "open")
        self.assertEqual(job_data["application_url"], "https://careers.navattach.example.com/apply/123")
        self.assertIn("Python", job_data["required_skills"])

        # Student checks eligibility for the linked job
        elig_res = requests.get(
            f"{BASE_URL}/placement/jobs/{target_job_id}/check-eligibility/{self.s1_user['id']}",
            headers=self.s1_headers
        )
        self.assertEqual(elig_res.status_code, 200)
        elig_data = elig_res.json()
        self.assertIn("is_eligible", elig_data)
        self.assertIn("overall_skill_match", elig_data)

    def test_02_previously_closed_job_reopens_upon_drive_publish(self):
        """A linked job that was previously closed or expired is reopened and synchronized on publish."""
        ts = int(time.time() * 1000)
        # Create a job with an expired application deadline
        job_res = requests.post(
            f"{BASE_URL}/placement/jobs",
            json={
                "company_id": self.company_id,
                "title": f"Reopened Junior Developer {ts}",
                "required_skills": ["Java", "SQL"],
                "application_deadline": "2020-01-01T10:00:00Z",
                "branch_eligibility": ["CSE", "AIML"],
            },
            headers=self.po_headers
        )
        self.assertEqual(job_res.status_code, 200)
        job_id = job_res.json()["id"]

        # Explicitly close the job to simulate past deadline closure
        close_res = requests.put(
            f"{BASE_URL}/placement/jobs/{job_id}",
            json={"status": "closed"},
            headers=self.po_headers
        )
        self.assertEqual(close_res.status_code, 200)
        self.assertEqual(close_res.json()["status"], "closed")

        # Create recruitment circular linking this closed job, with a future drive date
        circ_res = requests.post(
            f"{BASE_URL}/placement/circulars",
            json={
                "company_id": self.company_id,
                "title": f"Reopening Recruitment Drive {ts}",
                "drive_date": "2027-05-15T09:00:00Z",
                "job_posting_ids": [job_id],
            },
            headers=self.po_headers
        )
        self.assertIn(circ_res.status_code, [200, 201])
        circ_id = circ_res.json()["id"]

        # Publish the circular
        pub_res = requests.post(
            f"{BASE_URL}/placement/circulars/{circ_id}/publish",
            json={},
            headers=self.po_headers
        )
        self.assertEqual(pub_res.status_code, 200)

        # Verify job is now open with synchronized deadline/drive date
        student_job_res = requests.get(
            f"{BASE_URL}/placement/jobs/{job_id}",
            headers=self.s1_headers
        )
        self.assertEqual(student_job_res.status_code, 200)
        job_data = student_job_res.json()
        self.assertEqual(job_data["status"], "open")
        self.assertIsNotNone(job_data["application_deadline"])

    def test_03_unlinked_draft_job_remains_inaccessible_to_students(self):
        """Unlinked draft job is concealed from students (returns 404)."""
        ts = int(time.time() * 1000)
        job_res = requests.post(
            f"{BASE_URL}/placement/jobs",
            json={
                "company_id": self.company_id,
                "title": f"Confidential Internal Role {ts}",
                "required_skills": ["Rust"],
                "branch_eligibility": ["CSE"],
            },
            headers=self.po_headers
        )
        self.assertEqual(job_res.status_code, 200)
        job_id = job_res.json()["id"]

        # Set status to draft
        draft_res = requests.put(
            f"{BASE_URL}/placement/jobs/{job_id}",
            json={"status": "draft"},
            headers=self.po_headers
        )
        self.assertEqual(draft_res.status_code, 200)

        # Placement officer can view
        po_view = requests.get(f"{BASE_URL}/placement/jobs/{job_id}", headers=self.po_headers)
        self.assertEqual(po_view.status_code, 200)

        # Student receives 404
        stu_view = requests.get(f"{BASE_URL}/placement/jobs/{job_id}", headers=self.s1_headers)
        self.assertEqual(stu_view.status_code, 404)

        # Student checking eligibility on draft job also receives 404
        stu_elig = requests.get(
            f"{BASE_URL}/placement/jobs/{job_id}/check-eligibility/{self.s1_user['id']}",
            headers=self.s1_headers
        )
        self.assertEqual(stu_elig.status_code, 404)

    def test_04_attachment_preview_and_download_image(self):
        """Authorized student can preview and download uploaded image attachment with exact bytes."""
        ts = int(time.time() * 1000)
        # Create genuine minimal PNG bytes (1x1 red PNG)
        png_bytes = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0'
            b'\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        img_filename = f"eligibility_poster_{ts}.png"

        # Upload file as placement officer
        upload_res = requests.post(
            f"{BASE_URL}/files/upload",
            files={"file": (img_filename, png_bytes, "image/png")},
            params={"file_type": "placement_doc"},
            headers=self.po_headers
        )
        self.assertEqual(upload_res.status_code, 200, f"File upload failed: {upload_res.text}")
        file_id = upload_res.json().get("file_id") or upload_res.json().get("id")

        # Create job & circular
        job_res = requests.post(
            f"{BASE_URL}/placement/jobs",
            json={
                "company_id": self.company_id,
                "title": f"Frontend React Specialist {ts}",
                "required_skills": ["React", "JavaScript"],
                "branch_eligibility": ["CSE", "AIML"],
            },
            headers=self.po_headers
        )
        self.assertEqual(job_res.status_code, 200)
        job_id = job_res.json()["id"]

        circ_res = requests.post(
            f"{BASE_URL}/placement/circulars",
            json={
                "company_id": self.company_id,
                "title": f"Frontend Hiring Drive {ts}",
                "branch_eligibility": ["CSE", "AIML"],
                "job_posting_ids": [job_id],
                "attachments": [
                    {
                        "file_id": file_id,
                        "attachment_type": "eligibility_sheet",
                        "display_order": 1,
                    }
                ],
            },
            headers=self.po_headers
        )
        self.assertIn(circ_res.status_code, [200, 201])
        circ_data = circ_res.json()
        circ_id = circ_data["id"]
        attachment_id = circ_data["attachments"][0]["id"]

        # Publish the drive
        pub_res = requests.post(
            f"{BASE_URL}/placement/circulars/{circ_id}/publish",
            json={},
            headers=self.po_headers
        )
        self.assertEqual(pub_res.status_code, 200)

        # 1. Preview attachment via direct route with Authorization header
        prev_res = requests.get(
            f"{BASE_URL}/placement/circulars/{circ_id}/attachments/{attachment_id}/preview",
            headers=self.s1_headers
        )
        self.assertEqual(prev_res.status_code, 200)
        self.assertTrue(prev_res.headers.get("content-type", "").startswith("image/"))
        self.assertIn("inline", prev_res.headers.get("content-disposition", "").lower())
        self.assertEqual(prev_res.content, png_bytes)

        # 2. Preview attachment via URL token query parameter (used by <img> and <iframe>)
        prev_token_res = requests.get(
            f"{BASE_URL}/placement/circulars/{circ_id}/attachments/{attachment_id}/preview?token={self.s1_token}"
        )
        self.assertEqual(prev_token_res.status_code, 200)
        self.assertEqual(prev_token_res.content, png_bytes)

        # 3. Download attachment via Authorization header
        down_res = requests.get(
            f"{BASE_URL}/placement/circulars/{circ_id}/attachments/{attachment_id}/download",
            headers=self.s1_headers
        )
        self.assertEqual(down_res.status_code, 200)
        self.assertIn("attachment", down_res.headers.get("content-disposition", "").lower())
        self.assertIn(img_filename, down_res.headers.get("content-disposition", ""))
        self.assertEqual(down_res.content, png_bytes)

        # 4. Verify /v1 and /api/v1 prefix compatibility
        v1_prev = requests.get(
            f"{BASE_URL}/v1/placement/circulars/{circ_id}/attachments/{attachment_id}/preview?token={self.s1_token}"
        )
        self.assertEqual(v1_prev.status_code, 200)
        self.assertEqual(v1_prev.content, png_bytes)

        apiv1_prev = requests.get(
            f"{BASE_URL}/api/v1/placement/circulars/{circ_id}/attachments/{attachment_id}/preview?token={self.s1_token}"
        )
        self.assertEqual(apiv1_prev.status_code, 200)
        self.assertEqual(apiv1_prev.content, png_bytes)

    def test_05_attachment_preview_and_download_pdf(self):
        """Authorized student can preview and download PDF attachment with proper headers and bytes."""
        ts = int(time.time() * 1000)
        # Genuine minimal PDF bytes
        pdf_bytes = (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000053 00000 n \n"
            b"0000000102 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF\n"
        )
        pdf_filename = f"schedule_{ts}.pdf"

        upload_res = requests.post(
            f"{BASE_URL}/files/upload",
            files={"file": (pdf_filename, pdf_bytes, "application/pdf")},
            params={"file_type": "placement_doc"},
            headers=self.po_headers
        )
        self.assertEqual(upload_res.status_code, 200)
        file_id = upload_res.json().get("file_id") or upload_res.json().get("id")

        job_res = requests.post(
            f"{BASE_URL}/placement/jobs",
            json={
                "company_id": self.company_id,
                "title": f"DevOps Trainee {ts}",
                "required_skills": ["Linux", "Bash"],
                "branch_eligibility": ["CSE", "AIML"],
            },
            headers=self.po_headers
        )
        self.assertEqual(job_res.status_code, 200)
        job_id = job_res.json()["id"]

        circ_res = requests.post(
            f"{BASE_URL}/placement/circulars",
            json={
                "company_id": self.company_id,
                "title": f"DevOps Drive {ts}",
                "branch_eligibility": ["CSE", "AIML"],
                "job_posting_ids": [job_id],
                "attachments": [
                    {
                        "file_id": file_id,
                        "attachment_type": "poster",
                        "display_order": 1,
                    }
                ],
            },
            headers=self.po_headers
        )
        self.assertIn(circ_res.status_code, [200, 201])
        circ_data = circ_res.json()
        circ_id = circ_data["id"]
        attachment_id = circ_data["attachments"][0]["id"]

        pub_res = requests.post(
            f"{BASE_URL}/placement/circulars/{circ_id}/publish",
            json={},
            headers=self.po_headers
        )
        self.assertEqual(pub_res.status_code, 200)

        # Preview PDF
        prev_res = requests.get(
            f"{BASE_URL}/placement/circulars/{circ_id}/attachments/{attachment_id}/preview",
            headers=self.s1_headers
        )
        self.assertEqual(prev_res.status_code, 200)
        self.assertIn("application/pdf", prev_res.headers.get("content-type", ""))
        self.assertIn("inline", prev_res.headers.get("content-disposition", "").lower())
        self.assertEqual(prev_res.content, pdf_bytes)

        # Download PDF
        down_res = requests.get(
            f"{BASE_URL}/placement/circulars/{circ_id}/attachments/{attachment_id}/download",
            headers=self.s1_headers
        )
        self.assertEqual(down_res.status_code, 200)
        self.assertIn("attachment", down_res.headers.get("content-disposition", "").lower())
        self.assertIn(pdf_filename, down_res.headers.get("content-disposition", ""))
        self.assertEqual(down_res.content, pdf_bytes)

    def test_06_attachment_access_control_and_error_handling(self):
        """Unauthorized access is rejected and missing attachments return clean 404."""
        # Nonexistent attachment returns 404
        bad_att_res = requests.get(
            f"{BASE_URL}/placement/circulars/467/attachments/999999/preview",
            headers=self.s1_headers
        )
        self.assertEqual(bad_att_res.status_code, 404)

        # Nonexistent circular returns 404
        bad_circ_res = requests.get(
            f"{BASE_URL}/placement/circulars/999999/attachments/114/preview",
            headers=self.s1_headers
        )
        self.assertEqual(bad_circ_res.status_code, 404)

        # Unauthenticated request returns 401
        unauth_res = requests.get(
            f"{BASE_URL}/placement/circulars/467/attachments/114/preview"
        )
        self.assertEqual(unauth_res.status_code, 401)

        # Academic faculty access returns 403
        fac_res = requests.get(
            f"{BASE_URL}/placement/circulars/467/attachments/114/preview",
            headers=self.lec_headers
        )
        self.assertEqual(fac_res.status_code, 403)


if __name__ == "__main__":
    unittest.main()
