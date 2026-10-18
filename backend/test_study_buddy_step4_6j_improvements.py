"""
Step 4.6J Verification Test Suite: Grounding Simplification & Lecturer Subject Creation
Tests:
- Part A: Ask Buddy Grounding Simplification (Lecturer Notes default, grounding alone, attached document co-grounding, source-aware citations)
- Part B: Lecturer Subject Creation (authorized department, semester validation, cross-department rejection, duplicate rejection, student role rejection, immediate note upload)
- Part C: Student visibility, Admin catalog management, and API preservation
"""

import io
import time
import uuid
import unittest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.user import User, UserRole
from app.models.study_buddy import (
    Subject,
    LectureNote,
    LectureNoteStatus,
    LectureNoteProcessingStatus,
    LectureNoteIndexingStatus,
    StudentStudyDocument,
)
from app.services.file_storage.minio_client import minio_client
from app.services.student_documents_service import student_documents_service
from app.services.student_documents_indexing_service import student_documents_indexing_service
from app.services.lecture_notes_indexing_service import lecture_notes_indexing_service


class TestStudyBuddyStep46JImprovements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db: Session = SessionLocal()
        cls.timestamp = int(time.time() * 1000)

        # 1. Resolve Users across roles
        cls.admin_user = cls.db.query(User).filter(User.role == UserRole.ADMIN).first()
        cls.student_aiml = cls.db.query(User).filter(User.role == UserRole.STUDENT, User.department == "AIML").first()
        cls.student_ece = cls.db.query(User).filter(User.role == UserRole.STUDENT, User.department == "ECE").first()
        cls.lecturer_aiml = cls.db.query(User).filter(User.role == UserRole.LECTURER, User.department == "AIML").first()

        cls.admin_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.admin_user.email, 'id': cls.admin_user.id, 'role': 'admin'})}"}
        cls.student_aiml_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.student_aiml.email, 'id': cls.student_aiml.id, 'role': 'student'})}"}
        cls.student_ece_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.student_ece.email, 'id': cls.student_ece.id, 'role': 'student'})}"}
        cls.lecturer_aiml_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.lecturer_aiml.email, 'id': cls.lecturer_aiml.id, 'role': 'lecturer'})}"}

        cls.created_subject_ids = []
        cls.created_sdoc_ids = []
        cls.created_minio_keys = []
        cls.created_note_ids = []

        cls.student_sem = getattr(cls.student_aiml.student_profile, 'semester', 6) or 6

    @classmethod
    def tearDownClass(cls):
        # 1. Clean up student documents
        for sdoc_id in cls.created_sdoc_ids:
            try:
                student_documents_indexing_service.delete_document_chunks(sdoc_id)
            except Exception:
                pass
            try:
                doc = cls.db.query(StudentStudyDocument).filter(StudentStudyDocument.id == sdoc_id).first()
                if doc:
                    minio_client.delete_file(doc.minio_bucket, doc.minio_object_key)
                    cls.db.delete(doc)
            except Exception:
                pass

        # 2. Clean up lecture notes
        for note_id in cls.created_note_ids:
            try:
                lecture_notes_indexing_service.delete_note_chunks(note_id)
            except Exception:
                pass
            try:
                note = cls.db.query(LectureNote).filter(LectureNote.id == note_id).first()
                if note:
                    minio_client.delete_file(note.minio_bucket, note.minio_object_key)
                    cls.db.delete(note)
            except Exception:
                pass

        # 3. Clean up created subjects
        for subj_id in cls.created_subject_ids:
            try:
                subj = cls.db.query(Subject).filter(Subject.id == subj_id).first()
                if subj:
                    cls.db.delete(subj)
            except Exception:
                pass

        # 4. Clean up minio keys
        for bucket, key in cls.created_minio_keys:
            try:
                minio_client.delete_file(bucket, key)
            except Exception:
                pass

        cls.db.commit()
        cls.db.close()

    # =========================================================================
    # PART B: LECTURER SUBJECT CREATION & PERMISSIONS
    # =========================================================================

    def test_01_lecturer_create_subject_authorized_dept(self):
        """Verify Lecturer can create a subject for their authorized department and semester."""
        sub_code = f"AIML{self.timestamp % 10000}"
        payload = {
            "code": sub_code,
            "name": f"Foundations of Transformers {self.timestamp}",
            "department": "AIML",
            "semester": self.student_sem,
            "curriculum_version": "2024.1",
            "academic_year": "2026-2027",
            "description": "Transformers and Attention Mechanisms"
        }

        resp = self.client.post("/study-buddy/subjects", headers=self.lecturer_aiml_headers, json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["code"], sub_code)
        self.assertEqual(data["department"], "AIML")
        self.assertEqual(data["semester"], self.student_sem)
        self.assertTrue(data["is_active"])
        self.created_subject_ids.append(data["id"])

    def test_02_lecturer_create_subject_different_dept_rejected(self):
        """Verify Lecturer cannot create a subject for another department (403 Forbidden)."""
        payload = {
            "code": f"ECE{self.timestamp % 10000}",
            "name": "VLSI Circuit Design",
            "department": "ECE",  # Lecturer is AIML!
            "semester": 6,
            "curriculum_version": "2024.1"
        }

        resp = self.client.post("/study-buddy/subjects", headers=self.lecturer_aiml_headers, json=payload)
        self.assertEqual(resp.status_code, 403)
        self.assertIn("cannot create subjects for another department", resp.json().get("detail", "").lower())

    def test_03_student_create_subject_forbidden(self):
        """Verify Students cannot create subjects (403 Forbidden)."""
        payload = {
            "code": f"STUD{self.timestamp % 10000}",
            "name": "Unauthorized Student Subject",
            "department": "AIML",
            "semester": 6
        }

        resp = self.client.post("/study-buddy/subjects", headers=self.student_aiml_headers, json=payload)
        self.assertEqual(resp.status_code, 403)

    def test_04_duplicate_subject_code_rejected(self):
        """Verify duplicate subject code within department returns 409 Conflict."""
        sub_code = f"DUP{self.timestamp % 10000}"
        payload = {
            "code": sub_code,
            "name": "Duplicate Subject First",
            "semester": 6,
            "curriculum_version": "2024.1"
        }

        # First creation succeeds
        resp1 = self.client.post("/study-buddy/subjects", headers=self.lecturer_aiml_headers, json=payload)
        self.assertEqual(resp1.status_code, 201)
        self.created_subject_ids.append(resp1.json()["id"])

        # Second creation with same code & department fails with 409 Conflict
        payload["name"] = "Duplicate Subject Second"
        resp2 = self.client.post("/study-buddy/subjects", headers=self.lecturer_aiml_headers, json=payload)
        self.assertEqual(resp2.status_code, 409)
        self.assertIn("already exists", resp2.json().get("detail", "").lower())

    def test_05_invalid_semester_rejected(self):
        """Verify semester outside 1-8 is rejected with 400 Bad Request."""
        payload = {
            "code": f"SEM{self.timestamp % 10000}",
            "name": "Invalid Semester Subject",
            "semester": 0,  # Invalid!
            "curriculum_version": "2024.1"
        }
        resp0 = self.client.post("/study-buddy/subjects", headers=self.lecturer_aiml_headers, json=payload)
        self.assertIn(resp0.status_code, [400, 422])

        payload["semester"] = 9  # Invalid!
        resp9 = self.client.post("/study-buddy/subjects", headers=self.lecturer_aiml_headers, json=payload)
        self.assertIn(resp9.status_code, [400, 422])

    def test_06_student_visibility_matching_dept_and_semester(self):
        """Verify newly created subject is visible to students in the same department/semester, but hidden from other depts."""
        sub_code = f"VIS{self.timestamp % 10000}"
        payload = {
            "code": sub_code,
            "name": f"Visibility Test Subject {self.timestamp}",
            "semester": self.student_sem,
            "curriculum_version": "2024.1"
        }

        resp = self.client.post("/study-buddy/subjects", headers=self.lecturer_aiml_headers, json=payload)
        self.assertEqual(resp.status_code, 201)
        created_id = resp.json()["id"]
        self.created_subject_ids.append(created_id)

        # 1. AIML student in same semester queries subjects -> MUST find it
        resp_aiml = self.client.get("/study-buddy/subjects", headers=self.student_aiml_headers)
        self.assertEqual(resp_aiml.status_code, 200)
        aiml_subj_ids = [s["id"] for s in resp_aiml.json()]
        self.assertIn(created_id, aiml_subj_ids)

        # 2. ECE student queries subjects -> MUST NOT find it
        resp_ece = self.client.get("/study-buddy/subjects", headers=self.student_ece_headers)
        self.assertEqual(resp_ece.status_code, 200)
        ece_subj_ids = [s["id"] for s in resp_ece.json()]
        self.assertNotIn(created_id, ece_subj_ids)

    @staticmethod
    def _create_sample_pdf(text: str = "Sample lecture note content") -> bytes:
        from reportlab.pdfgen import canvas
        pdf_io = io.BytesIO()
        c = canvas.Canvas(pdf_io)
        c.drawString(100, 750, text)
        c.drawString(100, 730, "Mathematics and algorithmic foundations for deep neural networks.")
        c.showPage()
        c.save()
        return pdf_io.getvalue()

    def test_07_lecturer_immediate_note_upload_and_student_access(self):
        """Verify Lecturer who created the subject can immediately upload notes for it without authorization error."""
        sub_code = f"UPL{self.timestamp % 10000}"
        payload = {
            "code": sub_code,
            "name": f"Upload Test Subject {self.timestamp}",
            "semester": self.student_sem,
            "curriculum_version": "2024.1"
        }

        resp_sub = self.client.post("/study-buddy/subjects", headers=self.lecturer_aiml_headers, json=payload)
        self.assertEqual(resp_sub.status_code, 201)
        sub_id = resp_sub.json()["id"]
        self.created_subject_ids.append(sub_id)

        # Lecturer uploads a lecture note for this new subject
        note_pdf = self._create_sample_pdf("Self-attention layers compute pairwise token alignments using Query, Key, and Value matrices.")
        resp_note = self.client.post(
            f"/study-buddy/subjects/{sub_id}/notes",
            headers=self.lecturer_aiml_headers,
            files={"file": ("attention_mechanisms.pdf", io.BytesIO(note_pdf), "application/pdf")},
            data={"title": "Attention Mechanisms Lecture"}
        )
        self.assertEqual(resp_note.status_code, 201)
        note_data = resp_note.json()
        note_id = note_data["id"]
        self.created_note_ids.append(note_id)

        # Publish the note
        resp_pub = self.client.patch(
            f"/study-buddy/notes/{note_id}",
            headers=self.lecturer_aiml_headers,
            json={"status": "PUBLISHED", "is_published": True}
        )
        self.assertEqual(resp_pub.status_code, 200)

        # Student in AIML queries notes for this subject
        resp_student_notes = self.client.get(
            f"/study-buddy/subjects/{sub_id}/notes",
            headers=self.student_aiml_headers
        )
        self.assertEqual(resp_student_notes.status_code, 200)
        retrieved_ids = [n["id"] for n in resp_student_notes.json()]
        self.assertIn(note_id, retrieved_ids)

    # =========================================================================
    # PART A: ASK BUDDY GROUNDING (LECTURER NOTES DEFAULT & ATTACHMENT CO-GROUNDING)
    # =========================================================================

    def test_08_ask_buddy_lecture_notes_grounding_alone(self):
        """Verify Ask Buddy query with default source_mode='lecture_notes' grounds against published lecture notes."""
        # Create subject and published indexed lecture note
        sub_code = f"RAG{self.timestamp % 10000}"
        payload = {
            "code": sub_code,
            "name": f"Deep Sequence Models {self.timestamp}",
            "semester": self.student_sem,
            "curriculum_version": "2024.1"
        }
        resp_sub = self.client.post("/study-buddy/subjects", headers=self.lecturer_aiml_headers, json=payload)
        self.assertEqual(resp_sub.status_code, 201)
        sub_id = resp_sub.json()["id"]
        self.created_subject_ids.append(sub_id)

        note_text = "Multi-head attention allows the model to jointly attend to information from different representation subspaces."
        note_pdf = self._create_sample_pdf(note_text)
        resp_note = self.client.post(
            f"/study-buddy/subjects/{sub_id}/notes",
            headers=self.lecturer_aiml_headers,
            files={"file": ("mha_notes.pdf", io.BytesIO(note_pdf), "application/pdf")},
            data={"title": "Multi-Head Attention Notes"}
        )
        self.assertEqual(resp_note.status_code, 201)
        note_id = resp_note.json()["id"]
        self.created_note_ids.append(note_id)

        # Publish and index note
        self.client.patch(
            f"/study-buddy/notes/{note_id}",
            headers=self.lecturer_aiml_headers,
            json={"status": "PUBLISHED", "is_published": True}
        )
        lecture_notes_indexing_service.index_lecture_note(self.db, note_id)

        # Student queries Ask Buddy in lecture_notes mode (default)
        chat_resp = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={
                "question": "What is the purpose of multi-head attention?",
                "subject_id": sub_id,
                "source_mode": "lecture_notes"
            }
        )
        self.assertEqual(chat_resp.status_code, 200)
        data = chat_resp.json()
        self.assertTrue(data["has_sufficient_evidence"])
        self.assertGreater(len(data["citations"]), 0)

        # Citations must be from lecture note
        lecture_note_citations = [c for c in data["citations"] if c.get("source_type") == "lecture_note"]
        self.assertGreater(len(lecture_note_citations), 0)
        self.assertEqual(lecture_note_citations[0]["lecture_note_id"], note_id)

    def test_09_ask_buddy_lecture_notes_plus_attachment_grounding(self):
        """Verify Ask Buddy synthesizes lecture notes together with attached student document with source-aware citations."""
        # 1. Subject & lecture note
        sub_code = f"SYN{self.timestamp % 10000}"
        payload = {
            "code": sub_code,
            "name": f"Diffusion Models {self.timestamp}",
            "semester": self.student_sem,
            "curriculum_version": "2024.1"
        }
        resp_sub = self.client.post("/study-buddy/subjects", headers=self.lecturer_aiml_headers, json=payload)
        self.assertEqual(resp_sub.status_code, 201)
        sub_id = resp_sub.json()["id"]
        self.created_subject_ids.append(sub_id)

        note_text = "Denoising score matching minimizes the expected squared difference between true score and neural score network."
        note_pdf = self._create_sample_pdf(note_text)
        resp_note = self.client.post(
            f"/study-buddy/subjects/{sub_id}/notes",
            headers=self.lecturer_aiml_headers,
            files={"file": ("score_matching.pdf", io.BytesIO(note_pdf), "application/pdf")},
            data={"title": "Score Matching Slides"}
        )
        self.assertEqual(resp_note.status_code, 201)
        note_id = resp_note.json()["id"]
        self.created_note_ids.append(note_id)
        self.client.patch(
            f"/study-buddy/notes/{note_id}",
            headers=self.lecturer_aiml_headers,
            json={"status": "PUBLISHED", "is_published": True}
        )
        lecture_notes_indexing_service.index_lecture_note(self.db, note_id)

        # 2. Student uploads an attachment file
        attach_text = "Langevin dynamics uses the learned score function to iteratively generate sample trajectories from Gaussian noise."
        resp_attach = self.client.post(
            "/study-buddy/my-documents",
            headers=self.student_aiml_headers,
            files={"file": ("langevin_dynamics.txt", io.BytesIO(attach_text.encode("utf-8")), "text/plain")},
            data={"title": "Langevin Dynamics Notes", "reuse_existing": "true"}
        )
        self.assertEqual(resp_attach.status_code, 201)
        attach_id = resp_attach.json()["id"]
        self.created_sdoc_ids.append(attach_id)

        # 3. Student asks Ask Buddy linking attachment in lecture_notes mode
        chat_resp = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={
                "question": "How do score matching and Langevin dynamics work together?",
                "subject_id": sub_id,
                "source_mode": "lecture_notes",
                "attached_document_id": attach_id
            }
        )
        self.assertEqual(chat_resp.status_code, 200)
        data = chat_resp.json()
        self.assertTrue(data["has_sufficient_evidence"])
        self.assertGreater(len(data["citations"]), 0)

        # Source-aware citations verification:
        # Must contain citation with is_attached_file = True
        attached_cits = [c for c in data["citations"] if c.get("is_attached_file")]
        self.assertGreater(len(attached_cits), 0)
        self.assertEqual(attached_cits[0]["student_study_document_id"], attach_id)

    # =========================================================================
    # PART C: ADMIN MANAGEMENT & API PRESERVATION
    # =========================================================================

    def test_10_admin_subject_management_and_preservation(self):
        """Verify Admin can view, update, deactivate, and delete lecturer-created subjects."""
        # 1. Lecturer creates subject
        sub_code = f"ADM{self.timestamp % 10000}"
        payload = {
            "code": sub_code,
            "name": f"Admin Manageable Subject {self.timestamp}",
            "semester": 6,
            "curriculum_version": "2024.1"
        }
        resp = self.client.post("/study-buddy/subjects", headers=self.lecturer_aiml_headers, json=payload)
        self.assertEqual(resp.status_code, 201)
        sub_id = resp.json()["id"]

        # 2. Admin queries all subjects (including inactive) -> finds it
        resp_admin_list = self.client.get("/study-buddy/subjects?active_only=false", headers=self.admin_headers)
        self.assertEqual(resp_admin_list.status_code, 200)
        all_ids = [s["id"] for s in resp_admin_list.json()]
        self.assertIn(sub_id, all_ids)

        # 3. Admin updates subject
        resp_update = self.client.put(
            f"/study-buddy/subjects/{sub_id}",
            headers=self.admin_headers,
            json={"name": "Admin Updated Subject Name", "is_active": False}
        )
        self.assertEqual(resp_update.status_code, 200)
        self.assertEqual(resp_update.json()["name"], "Admin Updated Subject Name")
        self.assertFalse(resp_update.json()["is_active"])

        # 4. Admin deletes subject
        resp_delete = self.client.delete(f"/study-buddy/subjects/{sub_id}", headers=self.admin_headers)
        self.assertEqual(resp_delete.status_code, 200)

        # Verify subject is gone
        resp_get = self.client.get(f"/study-buddy/subjects/{sub_id}", headers=self.admin_headers)
        self.assertEqual(resp_get.status_code, 404)


if __name__ == "__main__":
    unittest.main()
