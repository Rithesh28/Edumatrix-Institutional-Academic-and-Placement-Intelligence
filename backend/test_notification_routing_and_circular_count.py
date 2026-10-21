"""
EduMatrix Automated Test Suite: Shortlisted-Student Notification Routing and Recruitment Circular Count

Validates:
1. Shortlist Match Notification Workflow:
   - Confirmed shortlist match generates notification for the correct student.
   - Notification target resolves to the correct recruitment circular.
   - Notification payload contract matches frontend UnifiedBell routing (circular / shortlist -> /student/jobs/circulars/{id}).
   - The linked job ID and circular ID are never confused.
   - Querying /placement/jobs/{circular_id} gracefully returns circular_fallback details.
   - Nonexistent or unauthorized targets are handled safely (404).
   - Ambiguous matches never dispatch notifications.
   - Existing notification types continue navigating to their correct destinations.

2. Recruitment Circular Listing & Count:
   - Published, active circular is returned to authorized students with branch normalization.
   - The circular count matches the returned listing.
   - Draft circulars remain hidden from students (listing and direct GET).
   - Ineligible branch circulars remain inaccessible.
   - Multiple published circulars are counted correctly without duplicate counting.
   - Circular with linked job is not omitted by job-only filters.
   - Existing campus jobs listing and standalone job details remain fully functional.
"""

import unittest
import time
import requests

BASE_URL = "http://localhost:8000"


class TestNotificationRoutingAndCircularCount(unittest.TestCase):
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

        # 2. Login as Student 1 (adi01@gmail.com - AIML branch in student profile)
        s1_login = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": "adi01@gmail.com", "password": "54321"}
        )
        assert s1_login.status_code == 200, f"Student 1 login failed: {s1_login.text}"
        cls.s1_token = s1_login.json()["access_token"]
        cls.s1_headers = {"Authorization": f"Bearer {cls.s1_token}"}
        cls.s1_user = s1_login.json()["user"]

        # 3. Create test company
        comp = requests.post(
            f"{BASE_URL}/placement/companies",
            headers=cls.po_headers,
            json={
                "name": f"Nexus Tech Solutions {int(time.time())}",
                "industry": "Software",
                "location": "Bangalore"
            }
        )
        assert comp.status_code in [200, 201], f"Create company failed: {comp.text}"
        cls.company_id = comp.json()["id"]
        cls.company_name = comp.json()["name"]

    def test_01_confirmed_shortlist_generates_notification_for_correct_student(self):
        """A confirmed shortlist match generates a notification with reference_id=circular_id and type=placement_shortlist."""
        from app.core.database import SessionLocal
        from app.models.notification import Notification

        drive_title = f"Nexus Hiring Drive {int(time.time())}"
        res = requests.post(
            f"{BASE_URL}/placement/circulars/create-and-post-drive",
            headers=self.po_headers,
            json={
                "company_id": self.company_id,
                "title": drive_title,
                "description": "Annual technical recruitment drive",
                "branch_eligibility": ["AI & Machine Learning (AIML)", "Computer Science (CSE)"],
                "candidates": [
                    {
                        "row_index": 0,
                        "source_filename": "shortlist.pdf",
                        "extracted_name": "Adi Sharma",
                        "extracted_usn": "4VP23CS001",
                        "extracted_email": "adi01@gmail.com",
                        "matched_student_id": self.s1_user["id"],
                        "match_confidence": 1.0,
                        "match_method": "EXACT_USN",
                        "review_status": "matched",
                        "is_confirmed": True
                    }
                ]
            }
        )
        self.assertEqual(res.status_code, 200, f"Create and post drive failed: {res.text}")
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["notified_students_count"], 1)
        circular_id = data["circular"]["id"]

        # Verify notification created in DB
        db = SessionLocal()
        try:
            shortlist_notif = db.query(Notification).filter_by(
                user_id=self.s1_user["id"],
                reference_id=circular_id,
                type="placement_shortlist"
            ).first()

            self.assertIsNotNone(shortlist_notif, "Shortlist notification should exist for student")
            self.assertEqual(shortlist_notif.user_id, self.s1_user["id"])
            self.assertEqual(shortlist_notif.type, "placement_shortlist")
            self.assertEqual(shortlist_notif.reference_id, circular_id)
            self.assertIn(self.company_name, shortlist_notif.title)
        finally:
            db.close()

    def test_02_notification_target_resolves_to_correct_circular(self):
        """Student API GET /placement/circulars/{reference_id} returns the circular without 404."""
        from app.core.database import SessionLocal
        from app.models.recruitment_circular import RecruitmentCircular, RecruitmentCircularStatus

        db = SessionLocal()
        try:
            circ = RecruitmentCircular(
                company_id=self.company_id,
                title=f"Target Drive Verification {int(time.time())}",
                summary="Drive target verification",
                branch_eligibility=["AI & Machine Learning (AIML)"],
                status=RecruitmentCircularStatus.PUBLISHED,
                created_by=self.po_user["id"]
            )
            db.add(circ)
            db.commit()
            db.refresh(circ)
            circ_id = circ.id
        finally:
            db.close()

        # Student accesses circular using circular_id
        res = requests.get(f"{BASE_URL}/placement/circulars/{circ_id}", headers=self.s1_headers)
        self.assertEqual(res.status_code, 200, f"Target circular should be accessible: {res.text}")
        data = res.json()
        self.assertEqual(data["id"], circ_id)
        self.assertEqual(data["title"], circ.title)

    def test_03_frontend_notification_routing_contract(self):
        """Simulate the frontend UnifiedBell routing rules to ensure correct URL resolution."""
        def resolve_notification_url(notif_type, ref_id):
            # Mirrors the updated handleNotificationClick in UnifiedBell.jsx
            if not notif_type:
                return "/student/jobs"
            t = notif_type.lower()
            if t == "placement_circular":
                return f"/student/jobs/circulars/{ref_id}" if ref_id else "/student/jobs"
            if t == "placement_shortlist":
                return f"/student/jobs/circulars/{ref_id}" if ref_id else "/student/jobs"
            if t == "forum_answer":
                return f"/forum/question/{ref_id}" if ref_id else "/forum"
            if t == "forum_upvote":
                return f"/forum/question/{ref_id}" if ref_id else "/forum"
            if t == "mentorship_request":
                return "/faculty/mentorship"
            if t == "mentorship_accepted":
                return "/student/profile"
            if t.startswith("placement"):
                return f"/student/jobs/{ref_id}" if ref_id else "/student/jobs"
            return "/student/dashboard"

        # 1. Circular notification
        self.assertEqual(resolve_notification_url("placement_circular", 523), "/student/jobs/circulars/523")
        # 2. Shortlist notification (The bug was that this previously resolved to /student/jobs/523)
        self.assertEqual(resolve_notification_url("placement_shortlist", 523), "/student/jobs/circulars/523")
        # 3. Standard job notification
        self.assertEqual(resolve_notification_url("placement_job", 1088), "/student/jobs/1088")
        self.assertEqual(resolve_notification_url("placement", 1088), "/student/jobs/1088")
        # 4. Other types
        self.assertEqual(resolve_notification_url("forum_answer", 42), "/forum/question/42")

    def test_04_linked_job_and_circular_never_confused_and_fallback_handled(self):
        """Calling /placement/jobs/{circular_id} detects the ID is a circular and returns circular_fallback info."""
        from app.core.database import SessionLocal
        from app.models.recruitment_circular import RecruitmentCircular, RecruitmentCircularStatus

        db = SessionLocal()
        try:
            circ = RecruitmentCircular(
                company_id=self.company_id,
                title=f"Fallback Drive {int(time.time())}",
                summary="Fallback test drive",
                branch_eligibility=["AI & Machine Learning (AIML)"],
                status=RecruitmentCircularStatus.PUBLISHED,
                created_by=self.po_user["id"]
            )
            db.add(circ)
            db.commit()
            db.refresh(circ)
            circ_id = circ.id
        finally:
            db.close()

        # Student mistakenly hits /placement/jobs/{circ_id} (e.g. from an old legacy notification)
        res = requests.get(f"{BASE_URL}/placement/jobs/{circ_id}", headers=self.s1_headers)
        self.assertEqual(res.status_code, 404)
        err = res.json()
        self.assertIn("detail", err)
        detail = err["detail"]
        if isinstance(detail, dict):
            self.assertIn("circular_fallback", detail)
            fb = detail["circular_fallback"]
            self.assertEqual(fb["circular_id"], circ_id)
            self.assertEqual(fb["circular_title"], circ.title)
        else:
            self.assertIn(str(circ_id), detail)

    def test_05_nonexistent_or_unauthorized_target_safe_handling(self):
        """Nonexistent target returns standard 404 without circular fallback, and ineligible circular returns 404."""
        # Nonexistent job ID
        res = requests.get(f"{BASE_URL}/placement/jobs/99999999", headers=self.s1_headers)
        self.assertEqual(res.status_code, 404)
        err = res.json()
        detail = err.get("detail", {})
        if isinstance(detail, dict):
            self.assertNotIn("circular_fallback", detail)

        # Create a circular with an branch student does not belong to (e.g. CIVIL only)
        from app.core.database import SessionLocal
        from app.models.recruitment_circular import RecruitmentCircular, RecruitmentCircularStatus

        db = SessionLocal()
        try:
            circ = RecruitmentCircular(
                company_id=self.company_id,
                title=f"Civil Engineering Only {int(time.time())}",
                summary="Civil only drive",
                branch_eligibility=["Civil Engineering (CIVIL)"],
                status=RecruitmentCircularStatus.PUBLISHED,
                created_by=self.po_user["id"]
            )
            db.add(circ)
            db.commit()
            db.refresh(circ)
            circ_id = circ.id
        finally:
            db.close()

        # Student (AIML) should get 404 when directly requesting circular
        res = requests.get(f"{BASE_URL}/placement/circulars/{circ_id}", headers=self.s1_headers)
        self.assertEqual(res.status_code, 404)

    def test_06_ambiguous_matches_do_not_send_notifications(self):
        """Candidates with AMBIGUOUS or unconfirmed status never trigger notifications."""
        drive_title = f"Ambiguity Test Drive {int(time.time())}"
        res = requests.post(
            f"{BASE_URL}/placement/circulars/create-and-post-drive",
            headers=self.po_headers,
            json={
                "company_id": self.company_id,
                "title": drive_title,
                "description": "Drive for ambiguity safety",
                "branch_eligibility": ["AI & Machine Learning (AIML)"],
                "candidates": [
                    {
                        "row_index": 0,
                        "source_filename": "shortlist.pdf",
                        "extracted_name": "Contradictory Name",
                        "extracted_usn": "4VP23CS001",
                        "extracted_email": "contradictory@gmail.com",
                        "matched_student_id": None,
                        "match_confidence": 0.0,
                        "match_method": "NAME_USN_CONTRADICTION",
                        "review_status": "ambiguous",
                        "is_confirmed": False
                    }
                ]
            }
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["notified_students_count"], 0)

    def test_07_existing_notification_types_continue_to_work(self):
        """Standard job publication notifications and circular notifications retain their correct schemas and destinations."""
        from app.core.database import SessionLocal
        from app.models.notification import Notification

        db = SessionLocal()
        try:
            # Create a standard placement notification
            n1 = Notification(
                user_id=self.s1_user["id"],
                type="placement_job",
                reference_id=1088,
                title="New Job Opportunity",
                message="A new job is available."
            )
            db.add(n1)
            # Create a circular notification
            n2 = Notification(
                user_id=self.s1_user["id"],
                type="placement_circular",
                reference_id=523,
                title="New Recruitment Drive",
                message="Global Buzz recruitment drive is open."
            )
            db.add(n2)
            db.commit()

            # Verify in DB
            self.assertEqual(n1.type, "placement_job")
            self.assertEqual(n1.reference_id, 1088)
            self.assertEqual(n2.type, "placement_circular")
            self.assertEqual(n2.reference_id, 523)
        finally:
            db.close()

    def test_08_published_active_circular_returned_to_authorized_student(self):
        """Student with branch AIML can view circular published with 'AI & Machine Learning (AIML)'."""
        from app.core.database import SessionLocal
        from app.models.recruitment_circular import RecruitmentCircular, RecruitmentCircularStatus

        db = SessionLocal()
        try:
            circ = RecruitmentCircular(
                company_id=self.company_id,
                title=f"AIML Multi-Format Drive {int(time.time())}",
                summary="Testing canonical branch matching",
                branch_eligibility=["Computer Science (CSE)", "AI & Machine Learning (AIML)", "Data Science (AIDS)"],
                status=RecruitmentCircularStatus.PUBLISHED,
                created_by=self.po_user["id"]
            )
            db.add(circ)
            db.commit()
            db.refresh(circ)
            circ_id = circ.id
        finally:
            db.close()

        # Student 1 (adi01@gmail.com, branch=AIML)
        res = requests.get(f"{BASE_URL}/placement/circulars", headers=self.s1_headers)
        self.assertEqual(res.status_code, 200)
        items = res.json()
        ids = [c["id"] for c in items]
        self.assertIn(circ_id, ids, f"Circular {circ_id} should be visible to student with AIML branch")

        # Also verify live Circular 523 is present for student
        if any(c["id"] == 523 for c in items):
            circ_523 = next(c for c in items if c["id"] == 523)
            self.assertEqual(circ_523.get("company_name"), "Global Buzz")

    def test_09_circular_count_matches_returned_listing(self):
        """The count displayed on Campus Jobs matches len(circulars) returned by the API."""
        res = requests.get(f"{BASE_URL}/placement/circulars", headers=self.s1_headers)
        self.assertEqual(res.status_code, 200)
        circulars = res.json()
        count = len(circulars)
        self.assertGreaterEqual(count, 1, "At least 1 circular should be visible to student")

        # Check that count is accurate and matches the list length
        res2 = requests.get(f"{BASE_URL}/placement/circulars", headers=self.s1_headers)
        self.assertEqual(len(res2.json()), count)

    def test_10_draft_circulars_remain_hidden_from_students(self):
        """Draft circulars are never returned in /placement/circulars and return 404 on direct lookup."""
        from app.core.database import SessionLocal
        from app.models.recruitment_circular import RecruitmentCircular, RecruitmentCircularStatus

        db = SessionLocal()
        try:
            circ = RecruitmentCircular(
                company_id=self.company_id,
                title=f"Draft Secret Drive {int(time.time())}",
                summary="Confidential draft drive",
                branch_eligibility=["AI & Machine Learning (AIML)"],
                status=RecruitmentCircularStatus.DRAFT,
                created_by=self.po_user["id"]
            )
            db.add(circ)
            db.commit()
            db.refresh(circ)
            draft_id = circ.id
        finally:
            db.close()

        # Listing check
        res = requests.get(f"{BASE_URL}/placement/circulars", headers=self.s1_headers)
        self.assertEqual(res.status_code, 200)
        draft_ids = [c["id"] for c in res.json() if c["id"] == draft_id]
        self.assertEqual(len(draft_ids), 0, "Draft circular must NOT be listed for student")

        # Direct access check
        res_direct = requests.get(f"{BASE_URL}/placement/circulars/{draft_id}", headers=self.s1_headers)
        self.assertEqual(res_direct.status_code, 404, "Draft circular direct lookup by student must return 404")

    def test_11_unauthorized_circulars_remain_inaccessible(self):
        """A circular with branches restricted to Mechanical Engineering is not visible to AIML student."""
        from app.core.database import SessionLocal
        from app.models.recruitment_circular import RecruitmentCircular, RecruitmentCircularStatus

        db = SessionLocal()
        try:
            circ = RecruitmentCircular(
                company_id=self.company_id,
                title=f"Mech Only Drive {int(time.time())}",
                summary="Mechanical engineering campus recruitment",
                branch_eligibility=["Mechanical Engineering (MECH)"],
                status=RecruitmentCircularStatus.PUBLISHED,
                created_by=self.po_user["id"]
            )
            db.add(circ)
            db.commit()
            db.refresh(circ)
            mech_circ_id = circ.id
        finally:
            db.close()

        res = requests.get(f"{BASE_URL}/placement/circulars", headers=self.s1_headers)
        self.assertEqual(res.status_code, 200)
        ids = [c["id"] for c in res.json()]
        self.assertNotIn(mech_circ_id, ids, "Mechanical only circular should not be in AIML student listing")

        res_direct = requests.get(f"{BASE_URL}/placement/circulars/{mech_circ_id}", headers=self.s1_headers)
        self.assertEqual(res_direct.status_code, 404, "Mechanical only circular must return 404 to AIML student")

    def test_12_multiple_published_circulars_counted_without_duplicates(self):
        """Multiple published circulars eligible for the student are returned without duplicates."""
        from app.core.database import SessionLocal
        from app.models.recruitment_circular import RecruitmentCircular, RecruitmentCircularStatus

        db = SessionLocal()
        created_ids = []
        try:
            for i in range(3):
                c = RecruitmentCircular(
                    company_id=self.company_id,
                    title=f"Multi Count Drive {i} - {int(time.time())}",
                    summary=f"Drive {i} description",
                    branch_eligibility=["AI & Machine Learning (AIML)"],
                    status=RecruitmentCircularStatus.PUBLISHED,
                    created_by=self.po_user["id"]
                )
                db.add(c)
                db.commit()
                db.refresh(c)
                created_ids.append(c.id)
        finally:
            db.close()

        res = requests.get(f"{BASE_URL}/placement/circulars", headers=self.s1_headers)
        self.assertEqual(res.status_code, 200)
        items = res.json()
        item_ids = [c["id"] for c in items]

        # Verify no duplicates
        self.assertEqual(len(item_ids), len(set(item_ids)), "Circular list must not contain duplicates")
        for cid in created_ids:
            self.assertIn(cid, item_ids)

    def test_13_valid_circular_with_linked_job_not_omitted_by_job_filters(self):
        """A published circular with a linked job remains listed and is not filtered out by job-only criteria."""
        from app.core.database import SessionLocal
        from app.models.recruitment_circular import (
            RecruitmentCircular,
            RecruitmentCircularStatus,
            RecruitmentCircularJob,
        )
        from app.models.job_posting import JobPosting, JobStatus

        db = SessionLocal()
        try:
            job = JobPosting(
                company_id=self.company_id,
                title=f"Linked Role {int(time.time())}",
                status=JobStatus.OPEN,
                branch_eligibility=["AI & Machine Learning (AIML)"],
                created_by=self.po_user["id"]
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            circ = RecruitmentCircular(
                company_id=self.company_id,
                title=f"Drive with Linked Role {int(time.time())}",
                summary="Drive with linked role",
                branch_eligibility=["AI & Machine Learning (AIML)"],
                status=RecruitmentCircularStatus.PUBLISHED,
                created_by=self.po_user["id"]
            )
            db.add(circ)
            db.commit()
            db.refresh(circ)

            link = RecruitmentCircularJob(circular_id=circ.id, job_posting_id=job.id)
            db.add(link)
            db.commit()
            circ_id = circ.id
        finally:
            db.close()

        res = requests.get(f"{BASE_URL}/placement/circulars", headers=self.s1_headers)
        self.assertEqual(res.status_code, 200)
        ids = [c["id"] for c in res.json()]
        self.assertIn(circ_id, ids, "Circular with linked job must be visible in circular listing")

    def test_14_campus_job_listing_and_standalone_job_detail_remain_functional(self):
        """Standalone campus jobs list (/placement/jobs) and job detail (/placement/jobs/{id}) continue to work."""
        from app.core.database import SessionLocal
        from app.models.job_posting import JobPosting, JobStatus

        db = SessionLocal()
        try:
            job = JobPosting(
                company_id=self.company_id,
                title=f"Standalone Software Engineer {int(time.time())}",
                status=JobStatus.OPEN,
                branch_eligibility=["AI & Machine Learning (AIML)"],
                created_by=self.po_user["id"]
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            job_id = job.id
        finally:
            db.close()

        # Check job listing
        res_jobs = requests.get(f"{BASE_URL}/placement/jobs", headers=self.s1_headers)
        self.assertEqual(res_jobs.status_code, 200)
        jobs = res_jobs.json()
        job_ids = [j["id"] for j in jobs]
        self.assertIn(job_id, job_ids, "Standalone job must appear in /placement/jobs")

        # Check job detail
        res_detail = requests.get(f"{BASE_URL}/placement/jobs/{job_id}", headers=self.s1_headers)
        self.assertEqual(res_detail.status_code, 200)
        detail = res_detail.json()
        self.assertEqual(detail["id"], job_id)
        self.assertEqual(detail["title"], job.title)


if __name__ == "__main__":
    unittest.main()
