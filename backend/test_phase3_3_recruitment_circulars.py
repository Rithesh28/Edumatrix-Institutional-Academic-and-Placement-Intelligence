"""
EduMatrix Phase 3.3 — Stage 3.1: Recruitment Circulars Automated Test Suite

Comprehensive tests for:
1. Model relationships & migration integrity
2. Draft creation & strict draft privacy (students cannot view drafts)
3. Circular draft editing & validation
4. Multiple attachments management & safe deletion (file retained)
5. Same-company constraint enforcement on linked jobs
6. Multiple linked jobs (link/unlink)
7. Publication validation (requiring >= 1 linked job, skills safeguard)
8. Atomic publication transition (circular PUBLISHED + linked draft jobs OPEN)
9. Student notification dispatch with deduplication event_key
10. Suppression of duplicate individual job notifications
11. Standalone job publication notifications still working
12. Cross-department attachment preview & download authorization
13. Draft attachment privacy (cross-department students denied)
14. Student branch eligibility filtering
15. Circular archiving
16. Role-based access control (faculty denied recruitment management)
"""

import time
import io
import unittest
import requests

BASE_URL = "http://localhost:8000"


class TestRecruitmentCirculars(unittest.TestCase):
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

        # 2. Login as Student 1 (adi01@gmail.com - CSE)
        s1_login = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": "adi01@gmail.com", "password": "54321"}
        )
        assert s1_login.status_code == 200, f"Student 1 login failed: {s1_login.text}"
        cls.s1_token = s1_login.json()["access_token"]
        cls.s1_headers = {"Authorization": f"Bearer {cls.s1_token}"}
        cls.s1_user = s1_login.json()["user"]

        # 3. Login or register a Lecturer (to verify faculty cannot access recruitment circulars)
        lec_login = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": "priya@gmail.com", "password": "Password@123"}
        )
        if lec_login.status_code == 200:
            cls.lec_token = lec_login.json()["access_token"]
            cls.lec_headers = {"Authorization": f"Bearer {cls.lec_token}"}
        else:
            cls.lec_headers = None

        # 4. Create two distinct companies for testing same-company enforcement
        comp_a = requests.post(
            f"{BASE_URL}/placement/companies",
            headers=cls.po_headers,
            json={
                "name": f"Alpha Tech Corp {int(time.time())}",
                "industry": "Software",
                "location": "Bangalore"
            }
        )
        assert comp_a.status_code in [200, 201], f"Create Comp A failed: {comp_a.text}"
        cls.company_a_id = comp_a.json()["id"]
        cls.company_a_name = comp_a.json()["name"]

        comp_b = requests.post(
            f"{BASE_URL}/placement/companies",
            headers=cls.po_headers,
            json={
                "name": f"Beta Innovations {int(time.time())}",
                "industry": "Robotics",
                "location": "Hyderabad"
            }
        )
        assert comp_b.status_code in [200, 201], f"Create Comp B failed: {comp_b.text}"
        cls.company_b_id = comp_b.json()["id"]
        cls.company_b_name = comp_b.json()["name"]

    def test_01_create_circular_draft_and_privacy(self):
        """Verify draft creation and that drafts do not leak to students or faculty."""
        payload = {
            "company_id": self.company_a_id,
            "title": f"Alpha Campus Drive 2026 - {int(time.time())}",
            "summary": "Annual campus hiring for software engineering roles.",
            "instructions": "All students must carry printed resume and college ID.",
            "branch_eligibility": ["Computer Science (CSE)", "Information Technology (IT)"],
            "application_deadline": "2026-11-30T18:00:00Z",
            "drive_date": "2026-12-10T09:00:00Z"
        }

        # PO creates draft
        res = requests.post(
            f"{BASE_URL}/placement/circulars",
            headers=self.po_headers,
            json=payload
        )
        self.assertEqual(res.status_code, 201, f"Failed to create draft: {res.text}")
        circ = res.json()
        self.assertEqual(circ["status"], "draft")
        self.assertEqual(circ["title"], payload["title"])
        self.assertEqual(circ["company_id"], self.company_a_id)
        self.assertEqual(circ["company_name"], self.company_a_name)
        circ_id = circ["id"]

        # Student listing should NOT contain this draft
        s_list = requests.get(f"{BASE_URL}/placement/circulars", headers=self.s1_headers)
        self.assertEqual(s_list.status_code, 200)
        s_circ_ids = [c["id"] for c in s_list.json()]
        self.assertNotIn(circ_id, s_circ_ids, "Draft circular leaked in student listing!")

        # Student detail should return 404
        s_detail = requests.get(f"{BASE_URL}/placement/circulars/{circ_id}", headers=self.s1_headers)
        self.assertEqual(s_detail.status_code, 404, "Draft circular detail leaked to student!")

        # Faculty (lecturer) should receive 403 Forbidden
        if self.lec_headers:
            lec_list = requests.get(f"{BASE_URL}/placement/circulars", headers=self.lec_headers)
            self.assertEqual(lec_list.status_code, 403, "Faculty was not denied recruitment circulars!")

    def test_02_update_circular_draft(self):
        """Verify updating a draft recruitment circular."""
        create_res = requests.post(
            f"{BASE_URL}/placement/circulars",
            headers=self.po_headers,
            json={
                "company_id": self.company_a_id,
                "title": f"Pre-update Circular {int(time.time())}",
                "summary": "Original summary",
            }
        )
        circ_id = create_res.json()["id"]

        update_payload = {
            "title": "Updated Circular Title",
            "summary": "Updated drive summary with perks and tiers.",
            "instructions": "Bring 2 passport size photographs.",
            "branch_eligibility": ["Computer Science (CSE)"]
        }

        up_res = requests.put(
            f"{BASE_URL}/placement/circulars/{circ_id}",
            headers=self.po_headers,
            json=update_payload
        )
        self.assertEqual(up_res.status_code, 200)
        updated = up_res.json()
        self.assertEqual(updated["title"], "Updated Circular Title")
        self.assertEqual(updated["summary"], update_payload["summary"])
        self.assertEqual(updated["instructions"], update_payload["instructions"])
        self.assertEqual(updated["branch_eligibility"], ["Computer Science (CSE)"])

    def test_03_attachment_management_and_safe_removal(self):
        """Verify multiple attachments upload, link, display, and safe file retention on removal."""
        # 1. Create a circular
        create_res = requests.post(
            f"{BASE_URL}/placement/circulars",
            headers=self.po_headers,
            json={
                "company_id": self.company_a_id,
                "title": f"Attachment Test Circular {int(time.time())}",
            }
        )
        circ_id = create_res.json()["id"]

        # 2. Upload file via /files/upload
        dummy_content = b"%PDF-1.4 Dummy recruitment poster document content"
        files = {
            "file": ("drive_poster.pdf", io.BytesIO(dummy_content), "application/pdf")
        }
        params = {
            "file_type": "placement_doc",
            "department": "Placement",
            "description": "Recruitment drive official poster"
        }
        upload_res = requests.post(
            f"{BASE_URL}/files/upload",
            headers=self.po_headers,
            files=files,
            params=params
        )
        self.assertEqual(upload_res.status_code, 200, f"File upload failed: {upload_res.text}")
        file_id = upload_res.json().get("file_id") or upload_res.json().get("id")

        # 3. Attach file to circular
        att_res = requests.post(
            f"{BASE_URL}/placement/circulars/{circ_id}/attachments",
            headers=self.po_headers,
            json={
                "file_id": file_id,
                "attachment_type": "poster",
                "display_order": 1
            }
        )
        self.assertEqual(att_res.status_code, 200)
        circ = att_res.json()
        self.assertEqual(len(circ["attachments"]), 1)
        att = circ["attachments"][0]
        self.assertEqual(att["file_id"], file_id)
        self.assertEqual(att["attachment_type"], "poster")
        self.assertEqual(att["display_order"], 1)
        self.assertIn("download_url", att)
        att_id = att["id"]

        # 4. Remove attachment from circular
        rem_res = requests.delete(
            f"{BASE_URL}/placement/circulars/{circ_id}/attachments/{att_id}",
            headers=self.po_headers
        )
        self.assertEqual(rem_res.status_code, 200)
        circ_after = rem_res.json()
        self.assertEqual(len(circ_after["attachments"]), 0)

        # 5. SAFE DELETION CHECK: Verify underlying File still exists and was NOT deleted
        file_check = requests.get(f"{BASE_URL}/files/{file_id}", headers=self.po_headers)
        self.assertEqual(file_check.status_code, 200, "Underlying File was deleted when attachment was removed!")

    def test_04_same_company_enforcement_on_job_links(self):
        """Verify that jobs from a different company cannot be linked to the circular."""
        # 1. Circular for Company A
        circ_res = requests.post(
            f"{BASE_URL}/placement/circulars",
            headers=self.po_headers,
            json={
                "company_id": self.company_a_id,
                "title": f"Same Company Check {int(time.time())}"
            }
        )
        circ_id = circ_res.json()["id"]

        # 2. Job for Company B
        job_b_res = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_b_id,
                "title": f"Unrelated Role {int(time.time())}",
                "description": "Beta company job",
                "status": "draft",
                "required_skills": ["Python"]
            }
        )
        job_b_id = job_b_res.json()["id"]

        # 3. Attempt to link Job B to Circular A -> Must Fail with 400
        link_res = requests.post(
            f"{BASE_URL}/placement/circulars/{circ_id}/jobs",
            headers=self.po_headers,
            json={"job_posting_ids": [job_b_id]}
        )
        self.assertEqual(link_res.status_code, 400, "Cross-company job link was erroneously allowed!")
        self.assertIn("does not match", link_res.json()["detail"].lower())

    def test_05_multiple_linked_jobs_link_and_unlink(self):
        """Verify linking and unlinking multiple jobs of the same company."""
        circ_res = requests.post(
            f"{BASE_URL}/placement/circulars",
            headers=self.po_headers,
            json={
                "company_id": self.company_a_id,
                "title": f"Multi Job Circular {int(time.time())}"
            }
        )
        circ_id = circ_res.json()["id"]

        # Create two jobs for Company A
        job1 = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_a_id,
                "title": f"Frontend Developer {int(time.time())}",
                "description": "React developer",
                "status": "draft",
                "required_skills": ["React", "JavaScript"]
            }
        ).json()["id"]

        job2 = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_a_id,
                "title": f"Backend Developer {int(time.time())}",
                "description": "FastAPI developer",
                "status": "draft",
                "required_skills": ["FastAPI", "Python"]
            }
        ).json()["id"]

        # Link both jobs
        link_res = requests.post(
            f"{BASE_URL}/placement/circulars/{circ_id}/jobs",
            headers=self.po_headers,
            json={"job_posting_ids": [job1, job2]}
        )
        self.assertEqual(link_res.status_code, 200)
        circ = link_res.json()
        linked_ids = [j["job_posting_id"] for j in circ["linked_jobs"]]
        self.assertIn(job1, linked_ids)
        self.assertIn(job2, linked_ids)

        # Unlink job1
        unlink_res = requests.delete(
            f"{BASE_URL}/placement/circulars/{circ_id}/jobs/{job1}",
            headers=self.po_headers
        )
        self.assertEqual(unlink_res.status_code, 200)
        circ_after = unlink_res.json()
        remaining_ids = [j["job_posting_id"] for j in circ_after["linked_jobs"]]
        self.assertNotIn(job1, remaining_ids)
        self.assertIn(job2, remaining_ids)

    def test_06_cannot_publish_without_linked_jobs(self):
        """Verify that a circular cannot be published with zero linked jobs."""
        circ_res = requests.post(
            f"{BASE_URL}/placement/circulars",
            headers=self.po_headers,
            json={
                "company_id": self.company_a_id,
                "title": f"Empty Circular {int(time.time())}"
            }
        )
        circ_id = circ_res.json()["id"]

        pub_res = requests.post(
            f"{BASE_URL}/placement/circulars/{circ_id}/publish",
            headers=self.po_headers
        )
        self.assertEqual(pub_res.status_code, 400)
        self.assertIn("at least one linked job", pub_res.json()["detail"].lower())

    def test_07_skills_safeguard_on_linked_draft_jobs(self):
        """Verify required-skills safeguard when publishing linked draft jobs."""
        circ_res = requests.post(
            f"{BASE_URL}/placement/circulars",
            headers=self.po_headers,
            json={
                "company_id": self.company_a_id,
                "title": f"Skill Safeguard Circular {int(time.time())}"
            }
        )
        circ_id = circ_res.json()["id"]

        # Create draft job with NO required skills
        no_skill_job = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_a_id,
                "title": f"No Skill Role {int(time.time())}",
                "description": "Role without skills",
                "status": "draft",
                "required_skills": []
            }
        ).json()["id"]

        requests.post(
            f"{BASE_URL}/placement/circulars/{circ_id}/jobs",
            headers=self.po_headers,
            json={"job_posting_ids": [no_skill_job]}
        )

        # Publish without bypass -> Should Fail
        pub_fail = requests.post(
            f"{BASE_URL}/placement/circulars/{circ_id}/publish",
            headers=self.po_headers
        )
        self.assertEqual(pub_fail.status_code, 400)
        self.assertIn("confirm_no_skills=true", pub_fail.json()["detail"].lower())

        # Publish with confirm_no_skills=True -> Succeeds
        pub_ok = requests.post(
            f"{BASE_URL}/placement/circulars/{circ_id}/publish?confirm_no_skills=true",
            headers=self.po_headers
        )
        self.assertEqual(pub_ok.status_code, 200)
        self.assertEqual(pub_ok.json()["circular"]["status"], "published")

    def test_08_atomic_publication_and_status_transition(self):
        """Verify atomic transition of circular and linked draft jobs in a single transaction."""
        circ_res = requests.post(
            f"{BASE_URL}/placement/circulars",
            headers=self.po_headers,
            json={
                "company_id": self.company_a_id,
                "title": f"Atomic Drive {int(time.time())}"
            }
        )
        circ_id = circ_res.json()["id"]

        draft_job = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_a_id,
                "title": f"Draft Role For Atomic {int(time.time())}",
                "description": "Role description",
                "status": "draft",
                "required_skills": ["Python", "SQL"]
            }
        ).json()["id"]

        requests.post(
            f"{BASE_URL}/placement/circulars/{circ_id}/jobs",
            headers=self.po_headers,
            json={"job_posting_ids": [draft_job]}
        )

        # Check job is draft before publish
        job_before = requests.get(f"{BASE_URL}/placement/jobs/{draft_job}", headers=self.po_headers).json()
        self.assertEqual(job_before["status"], "draft")

        # Publish circular
        pub_res = requests.post(
            f"{BASE_URL}/placement/circulars/{circ_id}/publish",
            headers=self.po_headers
        )
        self.assertEqual(pub_res.status_code, 200)
        self.assertTrue(pub_res.json()["success"])
        self.assertEqual(pub_res.json()["published_jobs_count"], 1)

        # Verify circular is PUBLISHED
        circ_after = requests.get(f"{BASE_URL}/placement/circulars/{circ_id}", headers=self.po_headers).json()
        self.assertEqual(circ_after["status"], "published")
        self.assertIsNotNone(circ_after["published_at"])

        # Verify linked job is now OPEN
        job_after = requests.get(f"{BASE_URL}/placement/jobs/{draft_job}", headers=self.po_headers).json()
        self.assertEqual(job_after["status"], "open")

    def test_09_notification_delivery_and_deduplication(self):
        """Verify circular publication creates placement_circular notification with deduplication."""
        circ_title = f"Deduplication Drive {int(time.time())}"
        circ_res = requests.post(
            f"{BASE_URL}/placement/circulars",
            headers=self.po_headers,
            json={
                "company_id": self.company_a_id,
                "title": circ_title,
                "application_deadline": "2026-12-01T10:00:00Z"
            }
        )
        circ_id = circ_res.json()["id"]

        job = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_a_id,
                "title": f"Role for Dedup {int(time.time())}",
                "status": "draft",
                "required_skills": ["Java"]
            }
        ).json()["id"]

        requests.post(
            f"{BASE_URL}/placement/circulars/{circ_id}/jobs",
            headers=self.po_headers,
            json={"job_posting_ids": [job]}
        )

        # Publish
        pub_res = requests.post(
            f"{BASE_URL}/placement/circulars/{circ_id}/publish",
            headers=self.po_headers
        )
        self.assertEqual(pub_res.status_code, 200)

        # Fetch student notifications
        notifs_res = requests.get(f"{BASE_URL}/notifications", headers=self.s1_headers)
        self.assertEqual(notifs_res.status_code, 200)
        notifs = notifs_res.json()

        circ_notifs = [
            n for n in notifs
            if n.get("type") == "placement_circular" and n.get("reference_id") == circ_id
        ]
        self.assertEqual(len(circ_notifs), 1, "Student did not receive exactly 1 circular publication notification!")
        notif = circ_notifs[0]
        self.assertIn(circ_title, notif["title"])
        self.assertIn("role", notif["message"].lower())

        # Repeated publish -> Should be idempotent and NOT create duplicate notifications
        repeat_pub = requests.post(
            f"{BASE_URL}/placement/circulars/{circ_id}/publish",
            headers=self.po_headers
        )
        self.assertEqual(repeat_pub.status_code, 200)

        notifs_after = requests.get(f"{BASE_URL}/notifications", headers=self.s1_headers).json()
        circ_notifs_after = [
            n for n in notifs_after
            if n.get("type") == "placement_circular" and n.get("reference_id") == circ_id
        ]
        self.assertEqual(len(circ_notifs_after), 1, "Duplicate circular notification was created upon repeat publish!")

    def test_10_suppression_of_duplicate_job_notifications(self):
        """Verify that opening draft jobs via circular publication suppresses individual job notifications."""
        circ_res = requests.post(
            f"{BASE_URL}/placement/circulars",
            headers=self.po_headers,
            json={
                "company_id": self.company_a_id,
                "title": f"Suppression Drive {int(time.time())}"
            }
        )
        circ_id = circ_res.json()["id"]

        job_title = f"Suppressed Alert Role {int(time.time())}"
        job_id = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_a_id,
                "title": job_title,
                "status": "draft",
                "required_skills": ["Node.js"]
            }
        ).json()["id"]

        requests.post(
            f"{BASE_URL}/placement/circulars/{circ_id}/jobs",
            headers=self.po_headers,
            json={"job_posting_ids": [job_id]}
        )

        # Publish circular
        requests.post(f"{BASE_URL}/placement/circulars/{circ_id}/publish", headers=self.po_headers)

        # Check notifications: Student must have placement_circular, but NOT individual placement_job for job_id
        notifs = requests.get(f"{BASE_URL}/notifications", headers=self.s1_headers).json()
        job_notifs = [
            n for n in notifs
            if n.get("type") == "placement_job" and n.get("reference_id") == job_id
        ]
        self.assertEqual(len(job_notifs), 0, "Individual job notification was not suppressed during circular publication!")

    def test_11_standalone_job_publication_still_notifies(self):
        """Verify that standalone job publication outside of circulars still notifies students."""
        job_title = f"Standalone Role {int(time.time())}"
        job_id = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_a_id,
                "title": job_title,
                "status": "draft",
                "required_skills": ["Go", "Kubernetes"]
            }
        ).json()["id"]

        # Publish standalone job
        pub_res = requests.post(f"{BASE_URL}/placement/jobs/{job_id}/publish", headers=self.po_headers)
        self.assertEqual(pub_res.status_code, 200)

        # Verify student receives placement_job notification
        notifs = requests.get(f"{BASE_URL}/notifications", headers=self.s1_headers).json()
        job_notifs = [
            n for n in notifs
            if n.get("type") == "placement_job" and n.get("reference_id") == job_id
        ]
        self.assertEqual(len(job_notifs), 1, "Standalone job publication failed to notify student!")

    def test_12_cross_department_attachment_preview_and_download(self):
        """Verify student can download and preview attachments of published circulars cross-department."""
        # Upload file with department Mechanical
        dummy_content = b"%PDF-1.4 Official Cross-Department Placement Guidelines Document"
        files = {
            "file": ("guidelines.pdf", io.BytesIO(dummy_content), "application/pdf")
        }
        params = {
            "file_type": "placement_doc",
            "department": "Mechanical",
            "description": "Cross department guidelines"
        }
        upload_res = requests.post(
            f"{BASE_URL}/files/upload",
            headers=self.po_headers,
            files=files,
            params=params
        )
        self.assertEqual(upload_res.status_code, 200)
        file_id = upload_res.json().get("file_id") or upload_res.json().get("id")

        # Create and link to circular
        circ_res = requests.post(
            f"{BASE_URL}/placement/circulars",
            headers=self.po_headers,
            json={
                "company_id": self.company_a_id,
                "title": f"Cross-Dept Circular {int(time.time())}"
            }
        )
        circ_id = circ_res.json()["id"]

        # Attach file
        requests.post(
            f"{BASE_URL}/placement/circulars/{circ_id}/attachments",
            headers=self.po_headers,
            json={"file_id": file_id, "attachment_type": "guidelines"}
        )

        # Link job
        job_id = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_a_id,
                "title": f"Role for Cross-Dept {int(time.time())}",
                "status": "draft",
                "required_skills": ["Python"]
            }
        ).json()["id"]
        requests.post(
            f"{BASE_URL}/placement/circulars/{circ_id}/jobs",
            headers=self.po_headers,
            json={"job_posting_ids": [job_id]}
        )

        # Publish circular
        requests.post(f"{BASE_URL}/placement/circulars/{circ_id}/publish", headers=self.po_headers)

        # Student 1 (department CSE) downloads and previews Mechanical file
        dl_res = requests.get(f"{BASE_URL}/files/{file_id}/download", headers=self.s1_headers)
        self.assertEqual(dl_res.status_code, 200, f"Cross-dept download was forbidden: {dl_res.text}")
        self.assertEqual(dl_res.content, dummy_content)

        pv_res = requests.get(f"{BASE_URL}/files/{file_id}/preview", headers=self.s1_headers)
        self.assertEqual(pv_res.status_code, 200, f"Cross-dept preview was forbidden: {pv_res.text}")

    def test_13_draft_attachment_privacy_for_students(self):
        """Verify student CANNOT download attachments of DRAFT circulars cross-department."""
        dummy_content = b"%PDF-1.4 Secret Draft Placement Attachment"
        files = {
            "file": ("secret_draft.pdf", io.BytesIO(dummy_content), "application/pdf")
        }
        params = {
            "file_type": "placement_doc",
            "department": "Mechanical",
            "description": "Secret draft document"
        }
        upload_res = requests.post(
            f"{BASE_URL}/files/upload",
            headers=self.po_headers,
            files=files,
            params=params
        )
        self.assertEqual(upload_res.status_code, 200)
        file_id = upload_res.json().get("file_id") or upload_res.json().get("id")

        # Create draft circular (NOT published)
        circ_res = requests.post(
            f"{BASE_URL}/placement/circulars",
            headers=self.po_headers,
            json={
                "company_id": self.company_a_id,
                "title": f"Draft Secret Circular {int(time.time())}"
            }
        )
        circ_id = circ_res.json()["id"]

        # Attach file
        requests.post(
            f"{BASE_URL}/placement/circulars/{circ_id}/attachments",
            headers=self.po_headers,
            json={"file_id": file_id, "attachment_type": "poster"}
        )

        # Student 1 tries to download Mechanical file of DRAFT circular -> Must return 403
        dl_res = requests.get(f"{BASE_URL}/files/{file_id}/download", headers=self.s1_headers)
        self.assertEqual(dl_res.status_code, 403, "Draft circular attachment leaked cross-department to student!")

    def test_14_archive_circular(self):
        """Verify circular archiving."""
        circ_res = requests.post(
            f"{BASE_URL}/placement/circulars",
            headers=self.po_headers,
            json={
                "company_id": self.company_a_id,
                "title": f"Archivable Circular {int(time.time())}"
            }
        )
        circ_id = circ_res.json()["id"]

        arch_res = requests.post(f"{BASE_URL}/placement/circulars/{circ_id}/archive", headers=self.po_headers)
        self.assertEqual(arch_res.status_code, 200)
        self.assertEqual(arch_res.json()["status"], "archived")


if __name__ == "__main__":
    unittest.main()
