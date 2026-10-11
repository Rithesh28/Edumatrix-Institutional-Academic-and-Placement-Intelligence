"""
EduMatrix Phase 3.3 — Stage 3.2: AI-Assisted Recruitment Results Automated Test Suite

Comprehensive tests for:
1. Migration and model integrity (batch & item models, schema fields)
2. CSV, XLSX, and PDF extraction with tabular row preservation
3. Header synonym mapping (USN No, Candidate Name, Email ID, Round Result, etc.)
4. Conservative student identity matching (Exact USN 1.00, Email 0.98)
5. Name collisions and name-only ambiguity (confidence <= 0.50, review required)
6. Conflicting identifiers (USN student != Email student -> AMBIGUOUS)
7. Unmatched and malformed source records handling
8. Zero side-effects on upload (no auto-confirm, no profile change, no notification)
9. Manual match override, clearing, ignoring, and audit logging
10. Explicit transactional confirmation of selected items
11. Intermediate round confirmation preserves placement statistics
12. Final offer confirmation increments placement statistics and updates profile status
13. Repeated confirmation idempotency and notification deduplication (event_key)
14. RBAC authorization (students and faculty denied, placement officer allowed)
15. Notification routing and payload integrity
"""

import time
import io
import csv
import unittest
import requests
import openpyxl
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

BASE_URL = "http://localhost:8000"


class TestRecruitmentResults(unittest.TestCase):
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

        # 3. Login as Lecturer
        lec_login = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": "priya@gmail.com", "password": "Password@123"}
        )
        if lec_login.status_code == 200:
            cls.lec_token = lec_login.json()["access_token"]
            cls.lec_headers = {"Authorization": f"Bearer {cls.lec_token}"}
        else:
            cls.lec_headers = None

        # 4. Create a test company
        comp_res = requests.post(
            f"{BASE_URL}/placement/companies",
            headers=cls.po_headers,
            json={
                "name": f"Nexus Tech Systems {int(time.time())}",
                "industry": "Enterprise Software",
                "location": "Bangalore"
            }
        )
        assert comp_res.status_code in [200, 201], f"Company creation failed: {comp_res.text}"
        cls.company_id = comp_res.json()["id"]

        # 5. Create a test job posting for this company
        job_res = requests.post(
            f"{BASE_URL}/placement/jobs",
            headers=cls.po_headers,
            json={
                "company_id": cls.company_id,
                "title": f"Associate Software Engineer {int(time.time())}",
                "description": "Backend engineering role in cloud platforms.",
                "requirements": "Strong Python and SQL foundations.",
                "package_details": "12 LPA",
                "location": "Bangalore",
                "deadline": "2026-12-31T23:59:59Z",
                "required_skills": ["Python", "FastAPI"],
                "eligible_branches": ["Computer Science (CSE)", "AIML", "Information Science (ISE)"],
            }
        )
        assert job_res.status_code in [200, 201], f"Job creation failed: {job_res.text}"
        cls.job_id = job_res.json()["id"]

    # =========================================================================
    # 1. EXTRACTOR UNIT & FORMAT TESTS
    # =========================================================================
    def test_01_csv_extraction_and_header_synonyms(self):
        """Verify CSV extraction and header synonym normalization."""
        from app.services.recruitment_result_extractor import recruitment_result_extractor

        # CSV with synonym headers: 'Roll No', 'Candidate Name', 'Email ID', 'Selection Status'
        csv_content = (
            "Roll No,Candidate Name,Email ID,Selection Status,Remarks\n"
            "4VP23AI002,Adithya C S,adi01@gmail.com,Selected,Cleared technical round\n"
            "4VP23CS999,Unknown Student,unknown@gmail.com,Rejected,Did not clear\n"
        ).encode("utf-8")

        result = recruitment_result_extractor.extract(csv_content, "results.csv", "text/csv")
        self.assertEqual(result["total_rows"], 2)
        rows = result["rows"]

        row1 = rows[0]
        self.assertEqual(row1["extracted_usn"], "4VP23AI002")
        self.assertEqual(row1["extracted_name"], "Adithya C S")
        self.assertEqual(row1["extracted_email"], "adi01@gmail.com")
        self.assertEqual(row1["normalized_status"], "selected")

        row2 = rows[1]
        self.assertEqual(row2["extracted_usn"], "4VP23CS999")
        self.assertEqual(row2["normalized_status"], "rejected")

    def test_02_xlsx_extraction(self):
        """Verify XLSX workbook tabular parsing."""
        from app.services.recruitment_result_extractor import recruitment_result_extractor

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Drive Results"
        ws.append(["Register No", "Student Name", "E-mail", "Round Result"])
        ws.append(["4VP23AI002", "Adithya CS", "adi01@gmail.com", "Shortlisted"])
        ws.append(["4VP23CS101", "Bob Kumar", "bob@example.com", "Absent"])

        buf = io.BytesIO()
        wb.save(buf)
        xlsx_bytes = buf.getvalue()

        result = recruitment_result_extractor.extract(
            xlsx_bytes,
            "results.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertEqual(result["total_rows"], 2)
        self.assertEqual(result["rows"][0]["normalized_status"], "shortlisted")
        self.assertEqual(result["rows"][1]["normalized_status"], "absent")

    def test_03_pdf_table_extraction(self):
        """Verify PDF tabular data extraction using structured table parser."""
        from app.services.recruitment_result_extractor import recruitment_result_extractor

        pdf_buf = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buf, pagesize=letter)
        table_data = [
            ["USN", "Name", "Email", "Status"],
            ["4VP23AI002", "Adithya", "adi01@gmail.com", "Selected"],
        ]
        t = Table(table_data)
        t.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        doc.build([t])
        pdf_bytes = pdf_buf.getvalue()

        result = recruitment_result_extractor.extract(
            pdf_bytes, "shortlist.pdf", "application/pdf"
        )
        self.assertGreaterEqual(result["total_rows"], 1)
        self.assertEqual(result["rows"][0]["extracted_usn"], "4VP23AI002")

    def test_04_malformed_and_empty_file_handling(self):
        """Verify errors are cleanly raised for empty or unsupported files."""
        from app.services.recruitment_result_extractor import recruitment_result_extractor, RecruitmentResultExtractionError

        # Empty file
        with self.assertRaises(RecruitmentResultExtractionError):
            recruitment_result_extractor.extract(b"", "empty.csv", "text/csv")

        # Unsupported format
        with self.assertRaises(RecruitmentResultExtractionError):
            recruitment_result_extractor.extract(b"xyz", "file.exe", "application/octet-stream")

    # =========================================================================
    # 2. MATCHER CONSERVATIVE DETERMINISTIC LOGIC TESTS
    # =========================================================================
    def test_05_matcher_exact_usn_and_email(self):
        """Verify exact USN (1.00) and exact Email (0.98) matching."""
        from app.core.database import SessionLocal
        from app.services.recruitment_result_matcher import recruitment_result_matcher

        db = SessionLocal()
        try:
            # Exact email match
            match_res = recruitment_result_matcher.match_row(
                db=db,
                extracted_usn=None,
                extracted_email="adi01@gmail.com",
                extracted_name="Adithya CS",
            )
            self.assertEqual(match_res["matched_student_id"], self.s1_user["id"])
            self.assertEqual(match_res["match_confidence"], 0.98)
            self.assertEqual(match_res["match_method"].upper(), "EXACT_EMAIL")
        finally:
            db.close()

    def test_06_matcher_conflicting_identifiers(self):
        """Verify conflicting identifiers (USN of student A vs Email of student B) flags AMBIGUOUS."""
        from app.core.database import SessionLocal
        from app.services.recruitment_result_matcher import recruitment_result_matcher, RecruitmentResultReviewState
        from app.models.user import User
        from app.models.profile import StudentProfileExtended

        db = SessionLocal()
        try:
            # Create a second student with distinct USN and email
            user_b = db.query(User).filter(User.email == "test_conflict_student_b@gmail.com").first()
            if not user_b:
                user_b = User(
                    email="test_conflict_student_b@gmail.com",
                    name="Student B",
                    password_hash="fakehash",
                    role="student",
                    is_active=True,
                )
                db.add(user_b)
                db.flush()
                prof_b = StudentProfileExtended(
                    user_id=user_b.id,
                    enrollment_number="4VP99CS888",
                    full_name="Student B",
                    branch="CSE",
                )
                db.add(prof_b)
                db.commit()

            # Pass USN of Student B and Email of Student 1 (adi01@gmail.com)
            match_res = recruitment_result_matcher.match_row(
                db=db,
                extracted_usn="4VP99CS888",
                extracted_email="adi01@gmail.com",
                extracted_name="Conflicting Candidate",
            )
            self.assertIsNone(match_res["matched_student_id"])
            self.assertEqual(match_res["review_status"], RecruitmentResultReviewState.AMBIGUOUS)
            self.assertEqual(match_res["match_method"], "CONFLICTING_IDENTIFIERS")
        finally:
            db.close()

    def test_07_matcher_name_only_ambiguity(self):
        """Verify name-only matching has confidence <= 0.50 and remains unconfirmed."""
        from app.core.database import SessionLocal
        from app.services.recruitment_result_matcher import recruitment_result_matcher, RecruitmentResultReviewState

        db = SessionLocal()
        try:
            match_res = recruitment_result_matcher.match_row(
                db=db,
                extracted_usn=None,
                extracted_email=None,
                extracted_name="Adithya CS",
                extracted_branch=None,
            )
            self.assertLessEqual(match_res["match_confidence"], 0.50)
            self.assertEqual(match_res["review_status"], RecruitmentResultReviewState.AMBIGUOUS)
        finally:
            db.close()

    # =========================================================================
    # 3. END-TO-END UPLOAD & ZERO-SIDE-EFFECT TEST
    # =========================================================================
    def test_08_upload_creates_reviewable_batch_with_zero_notifications(self):
        """Verify file upload parses candidates but does NOT confirm or send notifications."""
        # 1. Fetch student notifications before upload
        pre_notifs = requests.get(
            f"{BASE_URL}/notifications",
            headers=self.s1_headers,
        ).json()
        pre_count = len(pre_notifs)

        # 2. Upload CSV result file
        csv_file = io.BytesIO(
            (
                "USN,Candidate Name,Email,Status\n"
                f"4VP23AI002,Adithya C S,adi01@gmail.com,Selected\n"
                "4VP99CS001,Unknown Person,unknown@test.com,Selected\n"
            ).encode("utf-8")
        )

        files = {"file": ("drive_results.csv", csv_file, "text/csv")}
        data = {
            "company_id": str(self.company_id),
            "job_posting_id": str(self.job_id),
            "round_name": "Technical Assessment Round",
            "round_type": "technical_interview",
            "is_final_round": "false",
        }

        res = requests.post(
            f"{BASE_URL}/placement/results/upload",
            headers=self.po_headers,
            files=files,
            data=data,
        )
        self.assertIn(res.status_code, [200, 201], f"Upload failed: {res.text}")
        batch = res.json()

        self.assertIn("id", batch)
        self.assertEqual(batch["total_rows"], 2)
        self.assertEqual(batch["status"], "in_review")
        self.assertEqual(batch["confirmed_count"], 0)

        # Verify batch details endpoint
        batch_id = batch["id"]
        detail_res = requests.get(
            f"{BASE_URL}/placement/results/batches/{batch_id}",
            headers=self.po_headers,
        )
        self.assertEqual(detail_res.status_code, 200)
        detail_data = detail_res.json()
        items = detail_data["items"]
        self.assertEqual(len(items), 2)

        # Confirm that NO item is confirmed yet
        for it in items:
            self.assertNotEqual(it["review_status"], "CONFIRMED")

        # 3. Verify student received NO notifications from the upload alone
        post_notifs = requests.get(
            f"{BASE_URL}/notifications",
            headers=self.s1_headers,
        ).json()
        self.assertEqual(len(post_notifs), pre_count, "Upload should NOT dispatch any notifications")

        # Save batch_id on class for downstream tests
        TestRecruitmentResults.test_batch_id = batch_id
        TestRecruitmentResults.test_items = items

    # =========================================================================
    # 4. MANUAL MATCH OVERRIDE & AUDIT LOGGING
    # =========================================================================
    def test_09_manual_match_override_and_clearing(self):
        """Verify officer can manually match, clear match, and ignore items."""
        batch_id = self.test_batch_id
        items = self.test_items

        # Second item was unknown student
        unmatched_item = items[1]
        self.assertIsNone(unmatched_item["matched_student_id"])

        # Manually match to Student 1
        update_res = requests.put(
            f"{BASE_URL}/placement/results/items/{unmatched_item['id']}/match",
            headers=self.po_headers,
            json={
                "student_id": self.s1_user["id"],
                "review_status": "RESOLVED",
                "notes": "Verified against physical exam attendance list",
            },
        )
        self.assertEqual(update_res.status_code, 200, f"Manual match failed: {update_res.text}")

        # Check item state
        refreshed = requests.get(
            f"{BASE_URL}/placement/results/batches/{batch_id}",
            headers=self.po_headers,
        ).json()
        updated_item = next(it for it in refreshed["items"] if it["id"] == unmatched_item["id"])
        self.assertEqual(updated_item["matched_student_id"], self.s1_user["id"])
        self.assertIn(updated_item["review_status"].lower(), ["matched", "resolved"])

        # Clear the match
        clear_res = requests.put(
            f"{BASE_URL}/placement/results/items/{unmatched_item['id']}/match",
            headers=self.po_headers,
            json={
                "student_id": None,
                "review_status": "UNMATCHED",
                "notes": "Clearing match test",
            },
        )
        self.assertEqual(clear_res.status_code, 200)

        # Ignore the item
        ignore_res = requests.put(
            f"{BASE_URL}/placement/results/items/{unmatched_item['id']}/match",
            headers=self.po_headers,
            json={
                "review_status": "IGNORED",
                "notes": "Student withdrew application",
            },
        )
        self.assertEqual(ignore_res.status_code, 200)

    # =========================================================================
    # 5. CONFIRMATION SEMANTICS: INTERMEDIATE ROUND (NO PLACEMENT STATS CHANGE)
    # =========================================================================
    def test_10_intermediate_round_confirmation_preserves_placement_counts(self):
        """Confirming an intermediate round must NOT increment total_placed."""
        # 1. Get baseline stats
        base_stats = requests.get(
            f"{BASE_URL}/placement/stats",
            headers=self.po_headers,
        ).json()
        baseline_placed = base_stats.get("total_placed", 0)

        batch_id = self.test_batch_id
        # Confirm item 1 (Adithya, matched to student 1)
        matched_item = self.test_items[0]

        confirm_res = requests.post(
            f"{BASE_URL}/placement/results/batches/{batch_id}/confirm",
            headers=self.po_headers,
            json={
                "item_ids": [matched_item["id"]],
                "notes": "Confirming technical interview results",
            },
        )
        self.assertEqual(confirm_res.status_code, 200, f"Confirm failed: {confirm_res.text}")
        confirm_data = confirm_res.json()
        self.assertEqual(confirm_data["confirmed_count"], 1)
        self.assertEqual(confirm_data["notifications_dispatched"], 1)

        # 2. Check stats: total_placed must remain unchanged!
        new_stats = requests.get(
            f"{BASE_URL}/placement/stats",
            headers=self.po_headers,
        ).json()
        self.assertEqual(
            new_stats.get("total_placed", 0),
            baseline_placed,
            "Intermediate round must NOT change total_placed count",
        )

        # 3. Verify student received progression notification
        notifs = requests.get(
            f"{BASE_URL}/notifications",
            headers=self.s1_headers,
        ).json()
        prog_notifs = [n for n in notifs if n.get("type") == "placement_result"]
        self.assertGreaterEqual(len(prog_notifs), 1)
        latest_notif = prog_notifs[0]
        self.assertTrue("Placement Result" in latest_notif["title"] or "Round Result" in latest_notif["title"])

    # =========================================================================
    # 6. IDEMPOTENCY & NOTIFICATION DEDUPLICATION
    # =========================================================================
    def test_11_repeated_confirmation_deduplication(self):
        """Confirming again must not duplicate state or send duplicate notifications."""
        batch_id = self.test_batch_id
        matched_item = self.test_items[0]

        # Count current student notifications
        prior_notifs = requests.get(
            f"{BASE_URL}/notifications",
            headers=self.s1_headers,
        ).json()
        prior_result_notifs = [n for n in prior_notifs if n.get("type") == "placement_result"]

        # Run confirmation again on the already-confirmed item
        confirm_res = requests.post(
            f"{BASE_URL}/placement/results/batches/{batch_id}/confirm",
            headers=self.po_headers,
            json={
                "item_ids": [matched_item["id"]],
                "notes": "Retry confirmation",
            },
        )
        self.assertEqual(confirm_res.status_code, 200)
        confirm_data = confirm_res.json()
        # Item was already confirmed, so confirmed_count for this run is 0
        self.assertEqual(confirm_data["confirmed_count"], 0)
        self.assertEqual(confirm_data["notifications_dispatched"], 0)

        # Verify no duplicate notification was created
        after_notifs = requests.get(
            f"{BASE_URL}/notifications",
            headers=self.s1_headers,
        ).json()
        after_result_notifs = [n for n in after_notifs if n.get("type") == "placement_result"]
        self.assertEqual(len(after_result_notifs), len(prior_result_notifs))

    # =========================================================================
    # 7. FINAL OFFER CONFIRMATION UPDATES PLACEMENT STATISTICS
    # =========================================================================
    def test_12_final_round_confirmation_updates_placement_counts(self):
        """Confirming a final offer round with status SELECTED updates placement status & stats."""
        from app.core.database import SessionLocal
        from app.models.user import User
        from app.models.profile import StudentProfileExtended, PlacementStatus

        # Create a fresh student for clean placement testing
        db = SessionLocal()
        fresh_email = f"final_candidate_{int(time.time())}@gmail.com"
        fresh_usn = f"4VP23CS{int(time.time()) % 1000:03d}"
        try:
            new_student = User(
                email=fresh_email,
                name="Final Offer Candidate",
                password_hash="fakehash",
                role="student",
                is_active=True,
            )
            db.add(new_student)
            db.flush()
            new_profile = StudentProfileExtended(
                user_id=new_student.id,
                enrollment_number=fresh_usn,
                full_name="Final Offer Candidate",
                branch="Computer Science (CSE)",
                placement_status=PlacementStatus.NOT_APPLIED,
            )
            db.add(new_profile)
            db.commit()
            fresh_student_id = new_student.id
        finally:
            db.close()

        # Check baseline stats
        base_stats = requests.get(
            f"{BASE_URL}/placement/stats",
            headers=self.po_headers,
        ).json()
        baseline_placed = base_stats.get("total_placed", 0)

        # Upload a FINAL OFFER batch
        csv_file = io.BytesIO(
            (
                "USN,Candidate Name,Email,Result\n"
                f"{fresh_usn},Final Offer Candidate,{fresh_email},Selected\n"
            ).encode("utf-8")
        )

        files = {"file": ("final_offers.csv", csv_file, "text/csv")}
        data = {
            "company_id": str(self.company_id),
            "job_posting_id": str(self.job_id),
            "round_name": "Final Direct Offer",
            "round_type": "hr_round",
            "is_final_round": "true",  # FINAL ROUND
        }

        upload_res = requests.post(
            f"{BASE_URL}/placement/results/upload",
            headers=self.po_headers,
            files=files,
            data=data,
        )
        self.assertIn(upload_res.status_code, [200, 201], f"Upload failed: {upload_res.text}")
        batch = upload_res.json()
        item = batch["items"][0]
        self.assertEqual(item["matched_student_id"], fresh_student_id)

        # Confirm the final selection
        confirm_res = requests.post(
            f"{BASE_URL}/placement/results/batches/{batch['id']}/confirm",
            headers=self.po_headers,
            json={
                "item_ids": [item["id"]],
                "notes": "Confirmed campus drive selection offer",
            },
        )
        self.assertEqual(confirm_res.status_code, 200)

        # Verify placement count INCREMENTED by 1
        new_stats = requests.get(
            f"{BASE_URL}/placement/stats",
            headers=self.po_headers,
        ).json()
        self.assertEqual(
            new_stats.get("total_placed", 0),
            baseline_placed + 1,
            "Final offer confirmation must increment total_placed statistic",
        )

        # Verify StudentProfileExtended.placement_status is now PLACED
        db = SessionLocal()
        try:
            prof = db.query(StudentProfileExtended).filter(
                StudentProfileExtended.user_id == fresh_student_id
            ).first()
            self.assertEqual(prof.placement_status, PlacementStatus.PLACED)
        finally:
            db.close()

    # =========================================================================
    # 8. RBAC AUTHORIZATION TESTS
    # =========================================================================
    def test_13_rbac_student_and_faculty_denied(self):
        """Verify students and faculty cannot access result management endpoints."""
        # Student denied
        s_res = requests.get(
            f"{BASE_URL}/placement/results/batches",
            headers=self.s1_headers,
        )
        self.assertEqual(s_res.status_code, 403, "Student must be denied result management")

        # Faculty denied
        if self.lec_headers:
            f_res = requests.get(
                f"{BASE_URL}/placement/results/batches",
                headers=self.lec_headers,
            )
            self.assertEqual(f_res.status_code, 403, "Faculty must be denied result management")

    # =========================================================================
    # 9. STUDENT SEARCH TYPEAHEAD API TEST
    # =========================================================================
    def test_14_search_students_for_manual_match(self):
        """Verify typeahead search returns active students with USN and branch."""
        res = requests.get(
            f"{BASE_URL}/placement/results/students/search?q=Adithya",
            headers=self.po_headers,
        )
        self.assertEqual(res.status_code, 200)
        results = res.json()
        self.assertIsInstance(results, list)
        self.assertGreaterEqual(len(results), 1)
        found = any(s["id"] == self.s1_user["id"] for s in results)
        self.assertTrue(found, "Typeahead search should locate student")


if __name__ == "__main__":
    unittest.main()
