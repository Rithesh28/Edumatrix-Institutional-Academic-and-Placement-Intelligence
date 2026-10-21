"""
EduMatrix Phase 4: Candidate Identity Safety & Verification Regression Suite

Tests the targeted identity safety fix for:
1. Correct USN + consistent candidate name -> normal match (EXACT_USN, MATCHED, confidence 1.00, name_verified=True).
2. Correct USN + reordered / reasonably abbreviated name -> valid match (EXACT_USN, MATCHED).
3. Valid USN + clearly contradictory name -> AMBIGUOUS, matched_student_id=None, NAME_USN_CONTRADICTION.
4. Valid USN + missing candidate name -> normal match (EXACT_USN, MATCHED, confidence 1.00, name_verified=False, note documented).
5. Valid USN + conflicting registered email -> CONFLICTING_IDENTIFIERS, AMBIGUOUS, matched_student_id=None.
6. Duplicate USNs -> USN_COLLISION, AMBIGUOUS, matched_student_id=None.
7. Conservative college code normalization -> distinct codes (UP, WP, YP, 1MS) are NOT rewritten to VP.
8. Ambiguous candidate cannot be confirmed or notified through default batch path or explicit alternate path.
"""

import os
import sys
import uuid
import unittest
from datetime import datetime

from app.core.database import SessionLocal
from app.models.user import User, UserRole
from app.models.profile import StudentProfileExtended
from app.models.notification import Notification
from app.models.company import Company
from app.models.file import File
from app.models.recruitment_result import (
    RecruitmentResultBatch,
    RecruitmentResultItem,
    RecruitmentResultBatchStatus,
    RecruitmentResultItemStatus,
    RecruitmentResultReviewState,
)
from app.services.recruitment_result_matcher import (
    recruitment_result_matcher,
    normalize_usn,
    normalize_name,
    normalize_name_tokens,
)
from app.services.recruitment_result_extractor import recruitment_result_extractor
from app.services.recruitment_result_service import recruitment_result_service


class TestCandidateIdentitySafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        # Verify baseline test students exist in DB
        # Student 104: Rakshith R Shetty, USN: 4VP23AI037
        cls.s104 = cls.db.query(User).filter(User.id == 104).first()
        # Student 1: Adithya CS, email: adi01@gmail.com, USN: 4VP23AI002
        cls.s1 = cls.db.query(User).filter(User.id == 1).first()
        # Placement officer for test actions
        cls.officer = cls.db.query(User).filter(User.role == UserRole.PLACEMENT_OFFICER, User.is_active == True).first()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    # =========================================================================
    # TEST 1: Correct USN and consistent candidate name -> normal match
    # =========================================================================
    def test_01_correct_usn_and_consistent_name(self):
        """Exact USN match with consistent candidate name returns confidence 1.00, MATCHED, and name_verified=True."""
        res = recruitment_result_matcher.match_row(
            db=self.db,
            extracted_usn="4VP23AI037",
            extracted_email=None,
            extracted_name="Rakshith R Shetty",
        )
        self.assertEqual(res["matched_student_id"], 104)
        self.assertEqual(res["match_confidence"], 1.00)
        self.assertEqual(res["match_method"], "EXACT_USN")
        self.assertEqual(res["review_status"], RecruitmentResultReviewState.MATCHED)

        evidence = res["match_evidence"]
        self.assertEqual(evidence["matched_field"], "enrollment_number")
        self.assertEqual(evidence["matched_value"], "4VP23AI037")
        self.assertTrue(evidence["name_verified"])
        self.assertEqual(evidence["corroborated_name"], "rakshith r shetty")

    # =========================================================================
    # TEST 2: Correct USN with reordered, abbreviated, or minor typo name
    # =========================================================================
    def test_02_correct_usn_reordered_or_abbreviated_name(self):
        """Reordered tokens, middle-initial omission, or minor typos match consistently."""
        # 1. Reordered tokens: "Shetty Rakshith R"
        res_reordered = recruitment_result_matcher.match_row(
            db=self.db,
            extracted_usn="4VP23AI037",
            extracted_email=None,
            extracted_name="Shetty Rakshith R",
        )
        self.assertEqual(res_reordered["matched_student_id"], 104)
        self.assertEqual(res_reordered["review_status"], RecruitmentResultReviewState.MATCHED)
        self.assertTrue(res_reordered["match_evidence"]["name_verified"])

        # 2. Middle-initial omission: "Rakshith Shetty"
        res_no_initial = recruitment_result_matcher.match_row(
            db=self.db,
            extracted_usn="4VP23AI037",
            extracted_email=None,
            extracted_name="Rakshith Shetty",
        )
        self.assertEqual(res_no_initial["matched_student_id"], 104)
        self.assertEqual(res_no_initial["review_status"], RecruitmentResultReviewState.MATCHED)
        self.assertTrue(res_no_initial["match_evidence"]["name_verified"])

        # 3. Minor OCR typo tolerance: "Rakshit R Shetty" (difflib ratio >= 0.80)
        res_typo = recruitment_result_matcher.match_row(
            db=self.db,
            extracted_usn="4VP23AI037",
            extracted_email=None,
            extracted_name="Rakshit R Shetty",
        )
        self.assertEqual(res_typo["matched_student_id"], 104)
        self.assertEqual(res_typo["review_status"], RecruitmentResultReviewState.MATCHED)
        self.assertTrue(res_typo["match_evidence"]["name_verified"])

    # =========================================================================
    # TEST 3: Valid USN with clearly contradictory candidate name -> AMBIGUOUS
    # =========================================================================
    def test_03_valid_usn_with_contradictory_name_returns_ambiguous(self):
        """Valid USN with a contradictory name must return AMBIGUOUS with matched_student_id=None."""
        # Case A: Completely different person (the audit reproduction)
        res_contradiction = recruitment_result_matcher.match_row(
            db=self.db,
            extracted_usn="4VP23AI037",
            extracted_email=None,
            extracted_name="Completely Different Person",
        )
        self.assertIsNone(res_contradiction["matched_student_id"])
        self.assertEqual(res_contradiction["match_confidence"], 0.40)
        self.assertEqual(res_contradiction["match_method"], "NAME_USN_CONTRADICTION")
        self.assertEqual(res_contradiction["review_status"], RecruitmentResultReviewState.AMBIGUOUS)

        evidence = res_contradiction["match_evidence"]
        self.assertIn("contradiction_details", evidence)
        self.assertEqual(evidence["extracted_name"], "Completely Different Person")
        self.assertIn("Rakshith R  Shetty", evidence["reason"])

        # Case B: Generic patronymic/surname match with contradictory given name
        # Create a temporary student with name "Ashok Kumar" to verify collision guard
        temp_user = self.db.query(User).filter(User.email == "test_generic_ashok@example.com").first()
        if not temp_user:
            temp_user = User(
                email="test_generic_ashok@example.com",
                name="Ashok Kumar",
                password_hash="fakehash",
                role=UserRole.STUDENT,
                is_active=True,
            )
            self.db.add(temp_user)
            self.db.flush()
            temp_prof = StudentProfileExtended(
                user_id=temp_user.id,
                enrollment_number="4VP99CS777",
                full_name="Ashok Kumar",
                branch="CSE",
            )
            self.db.add(temp_prof)
            self.db.commit()

        # Query with USN 4VP99CS777 and name "Ramesh Kumar" (shares only generic "Kumar")
        res_generic = recruitment_result_matcher.match_row(
            db=self.db,
            extracted_usn="4VP99CS777",
            extracted_email=None,
            extracted_name="Ramesh Kumar",
        )
        self.assertIsNone(res_generic["matched_student_id"])
        self.assertEqual(res_generic["match_method"], "NAME_USN_CONTRADICTION")
        self.assertEqual(res_generic["review_status"], RecruitmentResultReviewState.AMBIGUOUS)
        self.assertIn("generic token", res_generic["match_evidence"]["contradiction_details"])

    # =========================================================================
    # TEST 4: Valid USN with no extracted name -> safe documented behavior
    # =========================================================================
    def test_04_valid_usn_with_no_extracted_name(self):
        """Valid USN without extracted name matches normally but records name_verified=False and a cautionary note."""
        res_no_name = recruitment_result_matcher.match_row(
            db=self.db,
            extracted_usn="4VP23AI037",
            extracted_email=None,
            extracted_name=None,
        )
        self.assertEqual(res_no_name["matched_student_id"], 104)
        self.assertEqual(res_no_name["match_confidence"], 1.00)
        self.assertEqual(res_no_name["match_method"], "EXACT_USN")
        self.assertEqual(res_no_name["review_status"], RecruitmentResultReviewState.MATCHED)

        evidence = res_no_name["match_evidence"]
        self.assertFalse(evidence["name_verified"])
        self.assertIn("No candidate name was available", evidence["note"])

        # Also test empty whitespace name string
        res_empty = recruitment_result_matcher.match_row(
            db=self.db,
            extracted_usn="4VP23AI037",
            extracted_email=None,
            extracted_name="   ",
        )
        self.assertEqual(res_empty["matched_student_id"], 104)
        self.assertEqual(res_empty["review_status"], RecruitmentResultReviewState.MATCHED)
        self.assertFalse(res_empty["match_evidence"]["name_verified"])

    # =========================================================================
    # TEST 5: Valid USN with conflicting registered email -> AMBIGUOUS
    # =========================================================================
    def test_05_valid_usn_with_conflicting_email(self):
        """Preserves existing safeguard: USN pointing to Student A and Email to Student B flags CONFLICTING_IDENTIFIERS."""
        res_conflict = recruitment_result_matcher.match_row(
            db=self.db,
            extracted_usn="4VP23AI037",  # Student 104
            extracted_email="adi01@gmail.com",  # Student 1
            extracted_name="Any Name",
        )
        self.assertIsNone(res_conflict["matched_student_id"])
        self.assertEqual(res_conflict["match_method"], "CONFLICTING_IDENTIFIERS")
        self.assertEqual(res_conflict["review_status"], RecruitmentResultReviewState.AMBIGUOUS)

    # =========================================================================
    # TEST 6: Duplicate USNs -> USN_COLLISION safeguard remains intact
    # =========================================================================
    def test_06_duplicate_usn_collision(self):
        """USN mapped to multiple student accounts without disambiguating email returns USN_COLLISION."""
        res_collision = recruitment_result_matcher.match_row(
            db=self.db,
            extracted_usn="4VP23AI002",  # Mapped to multiple active students (User 1 and User 71)
            extracted_email=None,
            extracted_name="Adithya CS",
        )
        self.assertIsNone(res_collision["matched_student_id"])
        self.assertEqual(res_collision["match_method"], "USN_COLLISION")
        self.assertEqual(res_collision["review_status"], RecruitmentResultReviewState.AMBIGUOUS)

    # =========================================================================
    # TEST 7: Distinct college codes are not silently rewritten into VP
    # =========================================================================
    def test_07_distinct_college_codes_preserved(self):
        """Extractor normalizes college codes conservatively without rewriting UP, WP, YP, or 1MS into VP."""
        cases = [
            ("4UP23CS001", "4UP23CS001"),
            ("4WP23CS045", "4WP23CS045"),
            ("4YP23CS012", "4YP23CS012"),
            ("1MS23CS099", "1MS23CS099"),
            ("4VP23CS001", "4VP23CS001"),
        ]
        for raw_in, expected_out in cases:
            usn_clean, _, _, _ = recruitment_result_extractor._normalize_candidate_fields(
                raw_usn=raw_in,
                raw_name="Test Student",
                raw_email="",
                raw_status="Selected",
            )
            self.assertEqual(usn_clean, expected_out, f"USN {raw_in} was unexpectedly altered to {usn_clean}")

        # Verify OCR fix for VTU region 'A' / 'H' only applies when college code is VP
        usn_vtu_fix, _, _, _ = recruitment_result_extractor._normalize_candidate_fields(
            raw_usn="AVP23CS001",
            raw_name="Test Student",
            raw_email="",
            raw_status="Selected",
        )
        self.assertEqual(usn_vtu_fix, "4VP23CS001", "VTU region 'A' before 'VP' should normalize to '4'")

    # =========================================================================
    # TEST 8: Ambiguous candidate cannot be confirmed or notified in batch or alternate paths
    # =========================================================================
    def test_08_ambiguous_candidate_cannot_be_confirmed_or_notified(self):
        """
        Behavior verification:
        1. Default batch confirmation (item_ids=None) confirms only MATCHED rows and completely ignores AMBIGUOUS rows.
        2. Explicit confirmation of an AMBIGUOUS row raises ValueError and blocks execution.
        3. Ambiguous student (Student 104) receives exactly ZERO notification records or dispatches.
        """
        # Create a transient test batch
        company = self.db.query(Company).first()
        test_file = self.db.query(File).first()
        batch = RecruitmentResultBatch(
            company_id=company.id if company else None,
            file_id=test_file.id if test_file else None,
            round_name="Safety Test Round",
            round_type="technical_interview",
            is_final_round=False,
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            total_rows=2,
            matched_count=1,
            ambiguous_count=1,
            confirmed_count=0,
            uploaded_by=self.officer.id if self.officer else 1,
        )
        self.db.add(batch)
        self.db.flush()

        # Item 1: Valid clean match to Student 1
        item1 = RecruitmentResultItem(
            batch_id=batch.id,
            row_index=1,
            source_page=1,
            raw_data={"USN": "4VP23AI002", "Name": "Adithya CS"},
            extracted_usn="4VP23AI002",
            extracted_name="Adithya CS",
            extracted_email="adi01@gmail.com",
            normalized_status=RecruitmentResultItemStatus.SHORTLISTED,
            matched_student_id=1,
            match_confidence=1.00,
            match_method="EXACT_USN",
            review_status=RecruitmentResultReviewState.MATCHED,
        )
        self.db.add(item1)

        # Item 2: Contradictory row for Student 104's USN (4VP23AI037) with completely contradictory name
        item2 = RecruitmentResultItem(
            batch_id=batch.id,
            row_index=2,
            source_page=1,
            raw_data={"USN": "4VP23AI037", "Name": "Completely Different Person"},
            extracted_usn="4VP23AI037",
            extracted_name="Completely Different Person",
            extracted_email=None,
            normalized_status=RecruitmentResultItemStatus.SHORTLISTED,
            matched_student_id=None,  # Crucial safety invariant
            match_confidence=0.40,
            match_method="NAME_USN_CONTRADICTION",
            review_status=RecruitmentResultReviewState.AMBIGUOUS,
        )
        self.db.add(item2)
        self.db.commit()

        try:
            # Baseline notification counts for Student 1 and Student 104
            baseline_s1_notifs = self.db.query(Notification).filter(Notification.user_id == 1).count()
            baseline_s104_notifs = self.db.query(Notification).filter(Notification.user_id == 104).count()

            # --- PATH A: Default Batch Confirmation (item_ids=None) ---
            confirm_res = recruitment_result_service.confirm_batch_results(
                db=self.db,
                batch_id=batch.id,
                item_ids=None,
                current_user=self.officer or self.s1,
            )
            self.assertEqual(confirm_res["confirmed_count"], 1)
            self.assertEqual(confirm_res["notifications_dispatched"], 1)

            # Refresh item states from DB
            self.db.refresh(item1)
            self.db.refresh(item2)

            # Verify Item 1 was confirmed
            self.assertEqual(item1.review_status, RecruitmentResultReviewState.CONFIRMED)

            # Verify Item 2 was NOT confirmed and remains AMBIGUOUS with NO matched student
            self.assertEqual(item2.review_status, RecruitmentResultReviewState.AMBIGUOUS)
            self.assertIsNone(item2.matched_student_id)

            # Verify Notifications:
            # Student 1 received exactly 1 progression notification
            post_s1_notifs = self.db.query(Notification).filter(Notification.user_id == 1).count()
            self.assertEqual(post_s1_notifs, baseline_s1_notifs + 1)

            # Student 104 received EXACTLY ZERO notifications!
            post_s104_notifs = self.db.query(Notification).filter(Notification.user_id == 104).count()
            self.assertEqual(
                post_s104_notifs,
                baseline_s104_notifs,
                "Student 104 must NOT receive any notifications for ambiguous contradictory record!",
            )

            # --- PATH B: Explicit Alternate Path (Attempting to confirm ambiguous row directly) ---
            with self.assertRaises(ValueError) as cm:
                recruitment_result_service.confirm_batch_results(
                    db=self.db,
                    batch_id=batch.id,
                    item_ids=[item2.id],
                    current_user=self.officer or self.s1,
                )
            self.assertIn("cannot be confirmed because it has no matched student", str(cm.exception))

            # Verify notification count for Student 104 remains unchanged (still 0 new notifications)
            final_s104_notifs = self.db.query(Notification).filter(Notification.user_id == 104).count()
            self.assertEqual(final_s104_notifs, baseline_s104_notifs)

        finally:
            # Cleanup test records
            self.db.query(Notification).filter(
                Notification.user_id == 1,
                Notification.title.like("%Safety Test Round%"),
            ).delete(synchronize_session=False)
            self.db.query(RecruitmentResultItem).filter(RecruitmentResultItem.batch_id == batch.id).delete()
            self.db.query(RecruitmentResultBatch).filter(RecruitmentResultBatch.id == batch.id).delete()
            # Clean temp user if created
            temp_user = self.db.query(User).filter(User.email == "test_generic_ashok@example.com").first()
            if temp_user:
                self.db.query(StudentProfileExtended).filter(StudentProfileExtended.user_id == temp_user.id).delete()
                self.db.delete(temp_user)
            self.db.commit()


    # =========================================================================
    # TEST 9: Harmless formatting cleanup vs identity-changing OCR corrections
    # =========================================================================
    def test_09_formatting_cleanup_vs_identity_changing_correction(self):
        """
        Verify:
        1. Harmless formatting cleanup (spaces, hyphens) preserves ordinary exact-USN matching (MATCHED, 1.00).
        2. Identity-changing character correction without name/email corroboration routes to UNCERTAIN_OCR_USN (AMBIGUOUS, matched_student_id=None).
        3. Identity-changing character correction WITH corroborating name confirms safely (MATCHED, 1.00).
        """
        # Case A: Harmless whitespace/hyphen cleanup on Student 104 (4VP23AI037) with no candidate name
        res_harmless = recruitment_result_matcher.match_row(
            db=self.db,
            extracted_usn="4VP23AI037",
            extracted_email=None,
            extracted_name=None,
            raw_usn=" 4VP-23-AI-037 ",
        )
        self.assertEqual(res_harmless["matched_student_id"], 104)
        self.assertEqual(res_harmless["match_confidence"], 1.00)
        self.assertEqual(res_harmless["match_method"], "EXACT_USN")
        self.assertEqual(res_harmless["review_status"], RecruitmentResultReviewState.MATCHED)

        ev_harmless = res_harmless["match_evidence"]
        self.assertTrue(ev_harmless["usn_normalization_applied"])
        self.assertTrue(ev_harmless["formatting_cleanup_only"])
        self.assertFalse(ev_harmless["identity_changing_correction"])
        self.assertFalse(ev_harmless["name_verified"])
        self.assertEqual(ev_harmless["raw_extracted_usn"], "4VP-23-AI-037")

        # Case B: Identity-changing OCR correction (AVP -> 4VP) with NO extracted name or email
        res_ocr_uncorroborated = recruitment_result_matcher.match_row(
            db=self.db,
            extracted_usn="4VP23AI037",
            extracted_email=None,
            extracted_name=None,
            raw_usn="AVP23AI037",
        )
        self.assertIsNone(res_ocr_uncorroborated["matched_student_id"])
        self.assertEqual(res_ocr_uncorroborated["match_confidence"], 0.60)
        self.assertEqual(res_ocr_uncorroborated["match_method"], "UNCERTAIN_OCR_USN")
        self.assertEqual(res_ocr_uncorroborated["review_status"], RecruitmentResultReviewState.AMBIGUOUS)

        ev_ocr = res_ocr_uncorroborated["match_evidence"]
        self.assertTrue(ev_ocr["usn_normalization_applied"])
        self.assertTrue(ev_ocr["identity_changing_correction"])
        self.assertFalse(ev_ocr["formatting_cleanup_only"])
        self.assertEqual(ev_ocr["raw_extracted_usn"], "AVP23AI037")
        self.assertEqual(ev_ocr["normalized_usn"], "4VP23AI037")
        self.assertIn("required character-level OCR correction", ev_ocr["reason"])

        # Case C: Identity-changing OCR correction WITH corroborating candidate name
        res_ocr_corroborated = recruitment_result_matcher.match_row(
            db=self.db,
            extracted_usn="4VP23AI037",
            extracted_email=None,
            extracted_name="Rakshith R Shetty",
            raw_usn="AVP23AI037",
        )
        self.assertEqual(res_ocr_corroborated["matched_student_id"], 104)
        self.assertEqual(res_ocr_corroborated["match_confidence"], 1.00)
        self.assertEqual(res_ocr_corroborated["match_method"], "EXACT_USN")
        self.assertEqual(res_ocr_corroborated["review_status"], RecruitmentResultReviewState.MATCHED)

        ev_corroborated = res_ocr_corroborated["match_evidence"]
        self.assertTrue(ev_corroborated["usn_normalization_applied"])
        self.assertTrue(ev_corroborated["identity_changing_correction"])
        self.assertFalse(ev_corroborated["formatting_cleanup_only"])
        self.assertTrue(ev_corroborated["name_verified"])
        self.assertEqual(ev_corroborated["corroborated_name"], "rakshith r shetty")

    # =========================================================================
    # TEST 10: Short initials and common surnames contradiction handling
    # =========================================================================
    def test_10_short_initials_and_common_surnames(self):
        """
        Verify:
        1. Short initial with contradictory given name and common surname (e.g. 'A Kumar' vs 'Suresh Kumar') -> AMBIGUOUS.
        2. Short initial with matching given name and common surname (e.g. 'A Kumar' vs 'Adithya Kumar') -> MATCHED.
        3. 'R Sharma' vs 'Deepak Sharma' -> AMBIGUOUS.
        4. 'R Shetty' vs 'Rakshith R Shetty' -> MATCHED.
        5. 'K Shetty' vs 'Rakshith R Shetty' -> AMBIGUOUS.
        """
        # Create temporary students for testing initial contradictions
        u_suresh = self.db.query(User).filter(User.email == "test_suresh_kumar@example.com").first()
        if not u_suresh:
            u_suresh = User(
                email="test_suresh_kumar@example.com",
                name="Suresh Kumar",
                password_hash="fakehash",
                role=UserRole.STUDENT,
                is_active=True,
            )
            self.db.add(u_suresh)
            self.db.flush()
            p_suresh = StudentProfileExtended(
                user_id=u_suresh.id,
                enrollment_number="4VP88CS101",
                full_name="Suresh Kumar",
                branch="CSE",
            )
            self.db.add(p_suresh)

        u_adithya = self.db.query(User).filter(User.email == "test_adithya_kumar@example.com").first()
        if not u_adithya:
            u_adithya = User(
                email="test_adithya_kumar@example.com",
                name="Adithya Kumar",
                password_hash="fakehash",
                role=UserRole.STUDENT,
                is_active=True,
            )
            self.db.add(u_adithya)
            self.db.flush()
            p_adithya = StudentProfileExtended(
                user_id=u_adithya.id,
                enrollment_number="4VP88CS102",
                full_name="Adithya Kumar",
                branch="CSE",
            )
            self.db.add(p_adithya)

        u_deepak = self.db.query(User).filter(User.email == "test_deepak_sharma@example.com").first()
        if not u_deepak:
            u_deepak = User(
                email="test_deepak_sharma@example.com",
                name="Deepak Sharma",
                password_hash="fakehash",
                role=UserRole.STUDENT,
                is_active=True,
            )
            self.db.add(u_deepak)
            self.db.flush()
            p_deepak = StudentProfileExtended(
                user_id=u_deepak.id,
                enrollment_number="4VP88CS103",
                full_name="Deepak Sharma",
                branch="CSE",
            )
            self.db.add(p_deepak)

        self.db.commit()

        try:
            # 1. 'A Kumar' vs registered 'Suresh Kumar' (USN 4VP88CS101) -> CONTRADICTION!
            res1 = recruitment_result_matcher.match_row(
                db=self.db,
                extracted_usn="4VP88CS101",
                extracted_email=None,
                extracted_name="A Kumar",
            )
            self.assertIsNone(res1["matched_student_id"])
            self.assertEqual(res1["match_method"], "NAME_USN_CONTRADICTION")
            self.assertEqual(res1["review_status"], RecruitmentResultReviewState.AMBIGUOUS)

            # 2. 'A Kumar' vs registered 'Adithya Kumar' (USN 4VP88CS102) -> MATCHED!
            res2 = recruitment_result_matcher.match_row(
                db=self.db,
                extracted_usn="4VP88CS102",
                extracted_email=None,
                extracted_name="A Kumar",
            )
            self.assertEqual(res2["matched_student_id"], u_adithya.id)
            self.assertEqual(res2["match_method"], "EXACT_USN")
            self.assertEqual(res2["review_status"], RecruitmentResultReviewState.MATCHED)

            # 3. 'R Sharma' vs registered 'Deepak Sharma' (USN 4VP88CS103) -> CONTRADICTION!
            res3 = recruitment_result_matcher.match_row(
                db=self.db,
                extracted_usn="4VP88CS103",
                extracted_email=None,
                extracted_name="R Sharma",
            )
            self.assertIsNone(res3["matched_student_id"])
            self.assertEqual(res3["match_method"], "NAME_USN_CONTRADICTION")
            self.assertEqual(res3["review_status"], RecruitmentResultReviewState.AMBIGUOUS)

            # 4. 'R Shetty' vs registered Student 104 'Rakshith R Shetty' (USN 4VP23AI037) -> MATCHED!
            res4 = recruitment_result_matcher.match_row(
                db=self.db,
                extracted_usn="4VP23AI037",
                extracted_email=None,
                extracted_name="R Shetty",
            )
            self.assertEqual(res4["matched_student_id"], 104)
            self.assertEqual(res4["match_method"], "EXACT_USN")
            self.assertEqual(res4["review_status"], RecruitmentResultReviewState.MATCHED)

            # 5. 'K Shetty' vs registered Student 104 'Rakshith R Shetty' (USN 4VP23AI037) -> CONTRADICTION!
            res5 = recruitment_result_matcher.match_row(
                db=self.db,
                extracted_usn="4VP23AI037",
                extracted_email=None,
                extracted_name="K Shetty",
            )
            self.assertIsNone(res5["matched_student_id"])
            self.assertEqual(res5["match_method"], "NAME_USN_CONTRADICTION")
            self.assertEqual(res5["review_status"], RecruitmentResultReviewState.AMBIGUOUS)

        finally:
            # Clean up temporary users
            for email in ["test_suresh_kumar@example.com", "test_adithya_kumar@example.com", "test_deepak_sharma@example.com"]:
                u = self.db.query(User).filter(User.email == email).first()
                if u:
                    prof = self.db.query(StudentProfileExtended).filter(StudentProfileExtended.user_id == u.id).first()
                    if prof:
                        self.db.delete(prof)
                    self.db.delete(u)
            self.db.commit()


if __name__ == "__main__":
    unittest.main()

