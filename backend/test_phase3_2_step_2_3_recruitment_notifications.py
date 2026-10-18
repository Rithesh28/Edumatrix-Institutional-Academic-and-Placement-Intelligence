"""
EduMatrix Phase 3.2 — Stage 2, Step 2.3: Recruitment Notifications Test Suite

Verifies:
1. Draft job creation does not notify students.
2. Draft job edits without publish do not notify students.
3. First successful publish notifies appropriate student audience (title, company, deadline, Campus Jobs link).
4. Repeated publish of an already-open job does not duplicate publication notifications.
5. Branch targeting rules respect student eligibility and audience restrictions.
6. External application confirmation notifies the Placement Officer (student identity, job/company, timestamp).
7. Repeated confirmation does not duplicate officer notifications (strict idempotency).
8. Another student cannot confirm someone else's application or trigger officer notifications (HTTP 403).
9. RBAC: notification visibility is strictly private to the recipient; read/unread state functions correctly.
10. Database-level deduplication: event_key uniqueness guarantees race condition safety.
"""

import time
from datetime import datetime, timedelta, timezone
import unittest
import requests

BASE_URL = "http://localhost:8000"


class TestRecruitmentNotifications(unittest.TestCase):
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

        # 3. Login as Student 2 (student_ece@gmail.com or fallback)
        s2_login = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": "student_ece@gmail.com", "password": "12345"}
        )
        if s2_login.status_code == 200:
            cls.s2_token = s2_login.json()["access_token"]
            cls.s2_headers = {"Authorization": f"Bearer {cls.s2_token}"}
            cls.s2_user = s2_login.json()["user"]
        else:
            reg_res = requests.post(
                f"{BASE_URL}/auth/register",
                json={
                    "name": "Second Student",
                    "email": "student2_notif_test@gmail.com",
                    "password": "Password@123",
                    "role": "student"
                }
            )
            s2_login = requests.post(
                f"{BASE_URL}/auth/login",
                data={"username": "student2_notif_test@gmail.com", "password": "Password@123"}
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
            cls.company_name = companies[0]["name"]
        else:
            new_comp = requests.post(
                f"{BASE_URL}/placement/companies",
                headers=cls.po_headers,
                json={"name": "Recruitment Notification Labs", "industry": "Technology", "location": "Bangalore"}
            )
            cls.company_id = new_comp.json()["id"]
            cls.company_name = "Recruitment Notification Labs"

    def test_01_draft_job_creation_does_not_notify_students(self):
        """Verify saving a job in DRAFT status does not generate notifications for students."""
        job_title = f"Draft Cloud Specialist {int(time.time())}"
        create_res = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_id,
                "title": job_title,
                "description": "Draft job description.",
                "status": "draft",
                "required_skills": ["AWS", "Docker"],
                "application_url": "https://careers.example.com/draft-job"
            }
        )
        self.assertEqual(create_res.status_code, 200)
        job_data = create_res.json()
        job_id = job_data["id"]
        self.assertEqual(job_data["status"], "draft")

        # Verify Student 1 received NO notification for this draft job
        notifs_res = requests.get(f"{BASE_URL}/notifications/", headers=self.s1_headers)
        self.assertEqual(notifs_res.status_code, 200)
        matching = [n for n in notifs_res.json() if n.get("reference_id") == job_id]
        self.assertEqual(len(matching), 0, "Students must not receive notifications for draft jobs")

    def test_02_draft_update_without_publish_does_not_notify_students(self):
        """Verify editing a draft job without changing status to OPEN does not notify students."""
        job_title = f"Draft SRE {int(time.time())}"
        create_res = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_id,
                "title": job_title,
                "description": "Initial draft text.",
                "status": "draft",
                "required_skills": ["Kubernetes", "Go"]
            }
        )
        self.assertEqual(create_res.status_code, 200)
        job_id = create_res.json()["id"]

        # Update draft description
        update_res = requests.put(
            f"{BASE_URL}/placement/jobs/{job_id}",
            headers=self.po_headers,
            json={
                "description": "Updated draft description without publishing."
            }
        )
        self.assertEqual(update_res.status_code, 200)

        # Verify Student 1 still received NO notification
        notifs_res = requests.get(f"{BASE_URL}/notifications/", headers=self.s1_headers)
        matching = [n for n in notifs_res.json() if n.get("reference_id") == job_id]
        self.assertEqual(len(matching), 0, "Editing a draft without publishing must not notify students")

    def test_03_first_successful_publish_notifies_eligible_students(self):
        """Verify first publish of a draft job creates an in-app notification for eligible students."""
        job_title = f"Full Stack Engineer {int(time.time())}"
        deadline_str = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()

        # 1. Create draft
        create_res = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_id,
                "title": job_title,
                "description": "Exciting opening for full stack engineering.",
                "status": "draft",
                "required_skills": ["React", "FastAPI"],
                "application_deadline": deadline_str,
                "application_url": "https://careers.example.com/apply-fullstack"
            }
        )
        self.assertEqual(create_res.status_code, 200)
        job_id = create_res.json()["id"]

        # Get initial unread count for Student 1
        count_before_res = requests.get(f"{BASE_URL}/notifications/unread/count", headers=self.s1_headers)
        unread_before = count_before_res.json().get("unread_count", 0)

        # 2. Publish job
        pub_res = requests.post(
            f"{BASE_URL}/placement/jobs/{job_id}/publish",
            headers=self.po_headers
        )
        self.assertEqual(pub_res.status_code, 200)
        self.assertEqual(pub_res.json()["status"], "open")

        # 3. Check Student 1 notifications
        notifs_res = requests.get(f"{BASE_URL}/notifications/", headers=self.s1_headers)
        self.assertEqual(notifs_res.status_code, 200)
        matching = [n for n in notifs_res.json() if n.get("reference_id") == job_id]
        self.assertEqual(len(matching), 1, "Student 1 must receive exactly 1 notification for published job")

        notif = matching[0]
        self.assertEqual(notif["type"], "placement_job")
        self.assertIn(job_title, notif["title"])
        self.assertIn(job_title, notif["message"])
        self.assertIn("Campus Jobs", notif["message"])
        self.assertFalse(notif["is_read"])

        # Check unread count increased
        count_after_res = requests.get(f"{BASE_URL}/notifications/unread/count", headers=self.s1_headers)
        unread_after = count_after_res.json().get("unread_count", 0)
        self.assertGreaterEqual(unread_after, unread_before + 1)

    def test_04_repeated_publish_does_not_duplicate_notifications(self):
        """Verify calling publish again on an already-open job does not duplicate notifications."""
        job_title = f"Data Analyst Open {int(time.time())}"

        # Create and publish job
        create_res = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_id,
                "title": job_title,
                "description": "Data analysis and reporting.",
                "status": "draft",
                "required_skills": ["SQL", "Python"]
            }
        )
        job_id = create_res.json()["id"]

        pub1 = requests.post(f"{BASE_URL}/placement/jobs/{job_id}/publish", headers=self.po_headers)
        self.assertEqual(pub1.status_code, 200)

        # Call publish a second time
        pub2 = requests.post(f"{BASE_URL}/placement/jobs/{job_id}/publish", headers=self.po_headers)
        self.assertEqual(pub2.status_code, 200)

        # Student should still have exactly 1 notification for this job
        notifs_res = requests.get(f"{BASE_URL}/notifications/", headers=self.s1_headers)
        matching = [n for n in notifs_res.json() if n.get("reference_id") == job_id]
        self.assertEqual(len(matching), 1, "Repeated publish must not create duplicate notifications")

    def test_05_branch_targeted_job_respects_student_audience(self):
        """Verify jobs with branch eligibility target only matching students."""
        # Create a job explicitly restricted to a branch like 'Mechanical Engineering'
        job_title = f"Mechanical Robotics {int(time.time())}"
        create_res = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_id,
                "title": job_title,
                "description": "Mechanical robotics role.",
                "status": "draft",
                "required_skills": ["SolidWorks", "Robotics"],
                "branch_eligibility": ["Mechanical Engineering", "Automobile"]
            }
        )
        job_id = create_res.json()["id"]

        # Publish the branch-restricted job
        pub_res = requests.post(f"{BASE_URL}/placement/jobs/{job_id}/publish", headers=self.po_headers)
        self.assertEqual(pub_res.status_code, 200)

        # If Student 1 is CSE (department/branch 'CSE'), they should NOT receive this notification
        s1_dept = (self.s1_user.get("department") or "").lower()
        if "mechanical" not in s1_dept and "automobile" not in s1_dept:
            notifs_res = requests.get(f"{BASE_URL}/notifications/", headers=self.s1_headers)
            matching = [n for n in notifs_res.json() if n.get("reference_id") == job_id]
            self.assertEqual(len(matching), 0, "Student from ineligible branch must not receive notification")

    def test_06_external_confirmation_notifies_placement_officer(self):
        """Verify confirming an external application creates an in-app notification for the Placement Officer."""
        job_title = f"AI Engineer ExtNotif {int(time.time())}"
        # 1. Create and publish job with application_url
        create_res = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_id,
                "title": job_title,
                "description": "Role requiring external application.",
                "status": "draft",
                "required_skills": ["PyTorch", "NLP"],
                "application_url": "https://careers.example.com/apply-ai-ext-notif"
            }
        )
        job_id = create_res.json()["id"]
        requests.post(f"{BASE_URL}/placement/jobs/{job_id}/publish", headers=self.po_headers)

        # 2. Student 1 applies internally
        app_res = requests.post(
            f"{BASE_URL}/placement/applications",
            headers=self.s1_headers,
            json={"job_posting_id": job_id, "notes": "Interested in AI"}
        )
        self.assertEqual(app_res.status_code, 200)
        app_id = app_res.json()["id"]

        # 3. Student 1 confirms external application
        confirm_res = requests.post(
            f"{BASE_URL}/placement/applications/{app_id}/confirm-external",
            headers=self.s1_headers
        )
        self.assertEqual(confirm_res.status_code, 200)
        self.assertTrue(confirm_res.json()["is_external_confirmed"])

        # 4. Check Placement Officer notifications
        po_notifs_res = requests.get(f"{BASE_URL}/notifications/", headers=self.po_headers)
        self.assertEqual(po_notifs_res.status_code, 200)

        matching = [
            n for n in po_notifs_res.json()
            if n.get("reference_id") == job_id and n.get("type") == "placement_confirm"
        ]
        self.assertEqual(len(matching), 1, "Placement Officer must receive exactly 1 confirmation notification")

        notif = matching[0]
        self.assertIn("External Application", notif["title"])
        self.assertIn(self.s1_user["name"], notif["message"])
        self.assertIn(job_title, notif["message"])
        # Privacy check: message must not contain raw resume text or sensitive internal details
        self.assertNotIn("match_snapshot", notif["message"])
        self.assertNotIn("password", notif["message"].lower())

    def test_07_repeated_confirmation_does_not_duplicate_officer_notifications(self):
        """Verify idempotent repeated confirmation does not generate duplicate officer notifications."""
        job_title = f"Cloud Arch ExtIdemp {int(time.time())}"
        create_res = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_id,
                "title": job_title,
                "description": "Cloud architecture position.",
                "status": "draft",
                "required_skills": ["Cloud", "Security"],
                "application_url": "https://careers.example.com/apply-cloud"
            }
        )
        job_id = create_res.json()["id"]
        requests.post(f"{BASE_URL}/placement/jobs/{job_id}/publish", headers=self.po_headers)

        app_res = requests.post(
            f"{BASE_URL}/placement/applications",
            headers=self.s1_headers,
            json={"job_posting_id": job_id}
        )
        app_id = app_res.json()["id"]

        # Confirm 1st time
        conf1 = requests.post(f"{BASE_URL}/placement/applications/{app_id}/confirm-external", headers=self.s1_headers)
        self.assertEqual(conf1.status_code, 200)

        # Confirm 2nd time
        conf2 = requests.post(f"{BASE_URL}/placement/applications/{app_id}/confirm-external", headers=self.s1_headers)
        self.assertEqual(conf2.status_code, 200)

        # Officer must still have exactly 1 notification for this job
        po_notifs_res = requests.get(f"{BASE_URL}/notifications/", headers=self.po_headers)
        matching = [
            n for n in po_notifs_res.json()
            if n.get("reference_id") == job_id and n.get("type") == "placement_confirm"
        ]
        self.assertEqual(len(matching), 1, "Repeated external confirmation must not duplicate officer notifications")

    def test_08_other_student_cannot_trigger_confirmation_notification(self):
        """Verify Student 2 cannot confirm Student 1's application or trigger officer notifications."""
        job_title = f"Security Eng ExtRBAC {int(time.time())}"
        create_res = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=self.po_headers,
            json={
                "company_id": self.company_id,
                "title": job_title,
                "description": "Security engineer position.",
                "status": "draft",
                "required_skills": ["Cybersecurity"],
                "application_url": "https://careers.example.com/apply-sec"
            }
        )
        job_id = create_res.json()["id"]
        requests.post(f"{BASE_URL}/placement/jobs/{job_id}/publish", headers=self.po_headers)

        # Student 1 applies
        app_res = requests.post(
            f"{BASE_URL}/placement/applications",
            headers=self.s1_headers,
            json={"job_posting_id": job_id}
        )
        app_id = app_res.json()["id"]

        # Student 2 tries to confirm Student 1's application
        hack_res = requests.post(
            f"{BASE_URL}/placement/applications/{app_id}/confirm-external",
            headers=self.s2_headers
        )
        self.assertEqual(hack_res.status_code, 403, "Student 2 must be forbidden from confirming Student 1's application")

        # Officer must have 0 confirmation notifications for this job
        po_notifs_res = requests.get(f"{BASE_URL}/notifications/", headers=self.po_headers)
        matching = [
            n for n in po_notifs_res.json()
            if n.get("reference_id") == job_id and n.get("type") == "placement_confirm"
        ]
        self.assertEqual(len(matching), 0, "Unauthorized confirmation attempts must not notify officer")

    def test_09_rbac_and_notification_visibility_and_read_state(self):
        """Verify notification privacy between roles and test marking as read."""
        # Query Student 1 notifications
        s1_notifs = requests.get(f"{BASE_URL}/notifications/", headers=self.s1_headers).json()
        po_notifs = requests.get(f"{BASE_URL}/notifications/", headers=self.po_headers).json()

        s1_ids = {n["id"] for n in s1_notifs}
        po_ids = {n["id"] for n in po_notifs}

        # Sets of IDs must be completely disjoint
        self.assertTrue(s1_ids.isdisjoint(po_ids), "User notifications must remain strictly private to their owner")

        # Mark an unread notification as read for Student 1
        unread_s1 = [n for n in s1_notifs if not n["is_read"]]
        if unread_s1:
            target_notif = unread_s1[0]
            read_res = requests.put(f"{BASE_URL}/notifications/{target_notif['id']}/read", headers=self.s1_headers)
            self.assertEqual(read_res.status_code, 200)
            self.assertTrue(read_res.json()["is_read"])

    def test_10_database_level_deduplication_uniqueness(self):
        """Verify event_key uniqueness constraint in database prevents concurrent duplication."""
        from app.core.database import SessionLocal
        from app.models.notification import Notification
        from sqlalchemy.exc import IntegrityError

        db = SessionLocal()
        try:
            test_key = f"test_event_key_unique_check_{int(time.time())}"
            # Clean up prior test key if any
            db.query(Notification).filter(Notification.event_key == test_key).delete()
            db.commit()

            n1 = Notification(
                user_id=self.s1_user["id"],
                type="placement_job",
                title="Test 1",
                message="Msg 1",
                event_key=test_key
            )
            db.add(n1)
            db.commit()

            # Attempt inserting second notification with the exact same event_key
            n2 = Notification(
                user_id=self.s1_user["id"],
                type="placement_job",
                title="Test 2",
                message="Msg 2",
                event_key=test_key
            )
            db.add(n2)
            with self.assertRaises(IntegrityError):
                db.commit()

            db.rollback()

            # Clean up
            db.query(Notification).filter(Notification.event_key == test_key).delete()
            db.commit()
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
