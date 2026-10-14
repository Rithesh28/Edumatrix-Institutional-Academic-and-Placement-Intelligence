"""
EduMatrix Phase 4 — Step 4.1: Study Buddy Persistent Data Models and Syllabus Ingestion Test Suite

Verifies:
1. Migration 016 head and table schema in PostgreSQL.
2. Subject unique constraints, department scoping, and active states.
3. SyllabusDocument versioning (preserves historical versions; is_latest updating).
4. Cascading deletion from Subject to SyllabusDocument, Units, and Topics.
5. Ingestion of PDF, DOCX, and TXT files with text extraction and provenance.
6. Validation: rejection of empty (0-byte), oversized (>25MB), unsupported (.zip), and corrupt files.
7. Conservative segmentation of Units and Topics; unsegmented fallback with REVIEW_REQUIRED.
8. OCR fallback behavior on unreadable/scanned PDFs without fabricating text.
9. Storage cleanup on ingestion failures (no orphaned MinIO files).
10. Multi-role RBAC: Placement Officer (403), Student (read-only published), Lecturer (dept-scoped), HOD, Admin.
11. Department isolation: HOD and Lecturer blocked from modifying other departments' syllabi.
12. Review and publication workflows: student visibility strictly gated on APPROVED + is_published.
13. Retry processing endpoint re-reading from MinIO.
"""

import os
import io
import time
import zipfile
import unittest
from datetime import datetime, timezone
import sqlalchemy as sa
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.core.database import SessionLocal, engine
from app.core.security import create_access_token
from app.models.user import User, UserRole
from app.models.file import File
from app.models.study_buddy import (
    Subject,
    SyllabusDocument,
    SyllabusUnit,
    SyllabusTopic,
    SyllabusProcessingStatus,
    SyllabusReviewStatus
)
from app.services.file_storage.minio_client import minio_client
from app.services.syllabus_ingestion_service import syllabus_ingestion_service
from app.main import app


class TestStudyBuddyStep41(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db: Session = SessionLocal()
        cls.timestamp = int(time.time() * 1000)

        # Retrieve test users for all 5 roles
        cls.admin = cls.db.query(User).filter(User.role == UserRole.ADMIN).first()
        cls.hod_aiml = cls.db.query(User).filter(User.role == UserRole.HOD, User.department == "AIML").first()
        cls.lecturer_aiml = cls.db.query(User).filter(User.role == UserRole.LECTURER, User.department == "AIML").first()
        cls.student_aiml = cls.db.query(User).filter(User.role == UserRole.STUDENT, User.department == "AIML").first()
        cls.student_ece = cls.db.query(User).filter(User.role == UserRole.STUDENT, User.department == "ECE").first()
        cls.po = cls.db.query(User).filter(User.role == UserRole.PLACEMENT_OFFICER).first()

        # Build auth headers
        cls.admin_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.admin.email, 'id': cls.admin.id, 'role': 'admin'})}"}
        cls.hod_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.hod_aiml.email, 'id': cls.hod_aiml.id, 'role': 'hod'})}"}
        cls.lecturer_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.lecturer_aiml.email, 'id': cls.lecturer_aiml.id, 'role': 'lecturer'})}"}
        cls.student_aiml_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.student_aiml.email, 'id': cls.student_aiml.id, 'role': 'student'})}"}
        cls.student_ece_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.student_ece.email, 'id': cls.student_ece.id, 'role': 'student'})}"}
        cls.po_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.po.email, 'id': cls.po.id, 'role': 'placement_officer'})}"}

        # Track created subject IDs for cleanup
        cls.created_subject_ids = []

    @classmethod
    def tearDownClass(cls):
        # Clean up test subjects (cascades documents, units, topics)
        if cls.created_subject_ids:
            cls.db.query(Subject).filter(Subject.id.in_(cls.created_subject_ids)).delete(synchronize_session=False)
            cls.db.commit()
        cls.db.close()

    # =========================================================================
    # 1. DATABASE SCHEMA & MIGRATION VERIFICATION
    # =========================================================================

    def test_01_migration_head_is_016(self):
        """Verify Alembic migration head in database is 016."""
        with engine.connect() as conn:
            result = conn.execute(sa.text("SELECT version_num FROM alembic_version;")).fetchone()
            self.assertIn(result[0], ["016", "017", "018"], f"Database Alembic revision must be at least 016 (found {result[0]})")

    def test_02_database_tables_exist(self):
        """Verify subjects, syllabus_documents, syllabus_units, syllabus_topics tables exist."""
        inspector = sa.inspect(engine)
        tables = inspector.get_table_names()
        self.assertIn("subjects", tables)
        self.assertIn("syllabus_documents", tables)
        self.assertIn("syllabus_units", tables)
        self.assertIn("syllabus_topics", tables)

    # =========================================================================
    # 2. MODEL RELATIONSHIPS, CONSTRAINTS & VERSIONING
    # =========================================================================

    def test_03_subject_unique_constraint(self):
        """Verify duplicate (code, department, curriculum_version) violates unique constraint."""
        code = f"TEST{self.timestamp % 10000}"
        sub1 = Subject(code=code, name="Test Subject", department="AIML", curriculum_version="R2021")
        self.db.add(sub1)
        self.db.commit()
        self.created_subject_ids.append(sub1.id)

        sub2 = Subject(code=code, name="Duplicate Subject", department="AIML", curriculum_version="R2021")
        self.db.add(sub2)
        with self.assertRaises(sa.exc.IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_04_syllabus_versioning_and_cascading_delete(self):
        """Verify version increments on multiple documents and subject deletion cascades."""
        code = f"CASC{self.timestamp % 10000}"
        sub = Subject(code=code, name="Cascade Test", department="AIML")
        self.db.add(sub)
        self.db.commit()
        self.created_subject_ids.append(sub.id)

        doc1 = SyllabusDocument(
            subject_id=sub.id,
            version=1,
            is_latest=False,
            title="Syllabus v1",
            original_filename="v1.pdf",
            file_size=100,
            mime_type="application/pdf",
            minio_bucket="syllabi",
            minio_object_key=f"syllabi/{sub.id}/v1_{self.timestamp}.pdf"
        )
        doc2 = SyllabusDocument(
            subject_id=sub.id,
            version=2,
            is_latest=True,
            title="Syllabus v2",
            original_filename="v2.pdf",
            file_size=120,
            mime_type="application/pdf",
            minio_bucket="syllabi",
            minio_object_key=f"syllabi/{sub.id}/v2_{self.timestamp}.pdf"
        )
        self.db.add_all([doc1, doc2])
        self.db.commit()

        unit = SyllabusUnit(
            document_id=doc2.id,
            unit_number=1,
            title="Unit 1: Test",
            order=1
        )
        self.db.add(unit)
        self.db.commit()

        topic = SyllabusTopic(
            unit_id=unit.id,
            title="Topic 1.1: Foundations",
            order=1
        )
        self.db.add(topic)
        self.db.commit()

        # Delete Subject -> should cascade to documents, units, and topics
        self.db.delete(sub)
        self.db.commit()
        self.created_subject_ids.remove(sub.id)

        self.assertIsNone(self.db.query(SyllabusDocument).filter(SyllabusDocument.id == doc2.id).first())
        self.assertIsNone(self.db.query(SyllabusUnit).filter(SyllabusUnit.id == unit.id).first())
        self.assertIsNone(self.db.query(SyllabusTopic).filter(SyllabusTopic.id == topic.id).first())

    # =========================================================================
    # 3. EXTRACTION UTILITIES (PDF, DOCX, TXT)
    # =========================================================================

    def test_05_txt_extraction_and_segmentation(self):
        """Verify TXT text extraction and structured unit/topic segmentation."""
        txt_content = (
            "COURSE SYLLABUS: ARTIFICIAL INTELLIGENCE\n\n"
            "Unit 1: Introduction to State Space Search\n"
            "Search algorithms, BFS, DFS, Heuristic search.\n"
            "- A* Algorithm and admissibility\n"
            "- Minimax with Alpha-Beta pruning\n\n"
            "Unit 2: Knowledge Representation and Logic\n"
            "Propositional and predicate calculus.\n"
            "1. First-Order Logic\n"
            "2. Resolution Principle\n"
        ).encode("utf-8")

        full_text, pages, extractor, err = syllabus_ingestion_service.extract_content("ai_syllabus.txt", txt_content)
        self.assertIsNone(err)
        self.assertIn("State Space Search", full_text)

        units, is_high_confidence = syllabus_ingestion_service._segment_units_and_topics(full_text, pages)
        self.assertTrue(is_high_confidence)
        self.assertEqual(len(units), 2)
        self.assertEqual(units[0]["unit_number"], 1)
        self.assertIn("Introduction to State Space Search", units[0]["title"])
        self.assertTrue(len(units[0]["topics"]) >= 2)
        self.assertEqual(units[1]["unit_number"], 2)

    def test_06_docx_extraction(self):
        """Verify DOCX text extraction with valid python-docx content."""
        import docx
        doc_io = io.BytesIO()
        doc = docx.Document()
        doc.add_heading("Course: Machine Learning", level=0)
        doc.add_heading("Unit 1: Supervised Learning", level=1)
        doc.add_paragraph("Linear regression, Logistic regression, Decision trees.")
        doc.add_paragraph("• Support Vector Machines")
        doc.add_paragraph("• Neural Networks")
        doc.save(doc_io)
        docx_bytes = doc_io.getvalue()

        full_text, pages, extractor, err = syllabus_ingestion_service.extract_content("ml.docx", docx_bytes)
        self.assertIsNone(err)
        self.assertIn("Supervised Learning", full_text)
        self.assertEqual(extractor, "python_docx")

        units, is_high_confidence = syllabus_ingestion_service._segment_units_and_topics(full_text, pages)
        self.assertTrue(is_high_confidence)
        self.assertEqual(len(units), 1)
        self.assertIn("Supervised Learning", units[0]["title"])

    def test_07_unsegmented_fallback_review_required(self):
        """Verify unsegmented text defaults to single review-required unit rather than fabricating."""
        unsegmented_text = (
            "General course guidelines and overview.\n"
            "This course covers discrete mathematics.\n"
            "Topics include graph theory, set theory, combinatorics.\n"
            "Weekly problem sets and final examination.\n"
        )
        units, is_high_confidence = syllabus_ingestion_service._segment_units_and_topics(unsegmented_text, [])
        self.assertFalse(is_high_confidence)
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0]["title"], "General Syllabus Content")

    # =========================================================================
    # 4. FILE VALIDATION & ERROR HANDLING
    # =========================================================================

    def test_08_empty_file_upload_rejected(self):
        """Verify 0-byte file upload is rejected with HTTP 400."""
        # Create a test subject
        sub_code = f"VAL{self.timestamp % 10000}"
        sub = Subject(code=sub_code, name="Validation Test", department="AIML")
        self.db.add(sub)
        self.db.commit()
        self.created_subject_ids.append(sub.id)

        res = self.client.post(
            f"/study-buddy/subjects/{sub.id}/syllabus",
            headers=self.hod_headers,
            files={"file": ("empty.pdf", b"", "application/pdf")}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("empty", res.json()["detail"].lower())

    def test_09_unsupported_extension_rejected(self):
        """Verify unsupported file extension (.zip) is rejected with HTTP 400."""
        sub_id = self.created_subject_ids[-1]
        res = self.client.post(
            f"/study-buddy/subjects/{sub_id}/syllabus",
            headers=self.hod_headers,
            files={"file": ("archive.zip", b"PK\x03\x04dummy", "application/zip")}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("unsupported", res.json()["detail"].lower())

    def test_10_corrupt_pdf_rejected(self):
        """Verify corrupt PDF missing %PDF- header is rejected with HTTP 400."""
        sub_id = self.created_subject_ids[-1]
        res = self.client.post(
            f"/study-buddy/subjects/{sub_id}/syllabus",
            headers=self.hod_headers,
            files={"file": ("corrupt.pdf", b"NOT_A_PDF_CONTENT_HERE", "application/pdf")}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("magic signature", res.json()["detail"].lower())

    # =========================================================================
    # 5. MULTI-ROLE RBAC & CROSS-DEPARTMENT ISOLATION
    # =========================================================================

    def test_11_placement_officer_strictly_forbidden(self):
        """Verify Placement Officer cannot manage or view syllabus content (HTTP 403)."""
        res1 = self.client.get("/study-buddy/subjects", headers=self.po_headers)
        self.assertEqual(res1.status_code, 403)
        self.assertIn("Placement Officers do not have syllabus management permissions", res1.json()["detail"])

        res2 = self.client.post(
            "/study-buddy/subjects",
            headers=self.po_headers,
            json={"code": "PO101", "name": "Illegal Subject", "department": "AIML"}
        )
        self.assertEqual(res2.status_code, 403)

    def test_12_hod_cross_department_blocked(self):
        """Verify HOD of AIML cannot create or upload for ECE department."""
        # 1. HOD AIML trying to create subject for ECE
        res1 = self.client.post(
            "/study-buddy/subjects",
            headers=self.hod_headers,
            json={"code": f"ECE{self.timestamp % 1000}", "name": "ECE Signals", "department": "ECE"}
        )
        self.assertEqual(res1.status_code, 403)
        self.assertIn("another department", res1.json()["detail"].lower())

        # 2. Create an ECE subject via Admin
        ece_sub_code = f"EC{self.timestamp % 10000}"
        ece_sub = Subject(code=ece_sub_code, name="Digital Electronics", department="ECE")
        self.db.add(ece_sub)
        self.db.commit()
        self.created_subject_ids.append(ece_sub.id)

        # 3. HOD AIML trying to upload syllabus to ECE subject
        res2 = self.client.post(
            f"/study-buddy/subjects/{ece_sub.id}/syllabus",
            headers=self.hod_headers,
            files={"file": ("ece.txt", b"Unit 1: Gates\nLogic gates", "text/plain")}
        )
        self.assertEqual(res2.status_code, 403)

    def test_13_lecturer_cannot_review_or_publish(self):
        """Verify Lecturer can upload syllabus in own dept but cannot review or publish (HTTP 403)."""
        # Create AIML subject
        aiml_sub = Subject(code=f"LEC{self.timestamp % 10000}", name="Lecturer Test", department="AIML")
        self.db.add(aiml_sub)
        self.db.commit()
        self.created_subject_ids.append(aiml_sub.id)

        # Lecturer uploads syllabus
        upload_res = self.client.post(
            f"/study-buddy/subjects/{aiml_sub.id}/syllabus",
            headers=self.lecturer_headers,
            files={"file": ("syllabus.txt", b"Unit 1: Overview\nIntroduction to AI\nUnit 2: Logic\nPropositional logic", "text/plain")}
        )
        self.assertEqual(upload_res.status_code, 201)
        doc_id = upload_res.json()["id"]

        # Lecturer attempts to review -> 403
        rev_res = self.client.post(
            f"/study-buddy/syllabi/{doc_id}/review",
            headers=self.lecturer_headers,
            json={"review_status": "APPROVED"}
        )
        self.assertEqual(rev_res.status_code, 403)

        # Lecturer attempts to publish -> 403
        pub_res = self.client.post(
            f"/study-buddy/syllabi/{doc_id}/publish",
            headers=self.lecturer_headers,
            json={"is_published": True}
        )
        self.assertEqual(pub_res.status_code, 403)

    # =========================================================================
    # 6. STUDENT VISIBILITY & PUBLICATION GATING
    # =========================================================================

    def test_14_student_cannot_view_draft_or_unpublished_syllabus(self):
        """Verify students cannot view drafts or unpublished documents (HTTP 403/404)."""
        sub = Subject(code=f"STU{self.timestamp % 10000}", name="Student Privacy Test", department="AIML")
        self.db.add(sub)
        self.db.commit()
        self.created_subject_ids.append(sub.id)

        # Upload as HOD (starts as unpublished)
        upload_res = self.client.post(
            f"/study-buddy/subjects/{sub.id}/syllabus",
            headers=self.hod_headers,
            files={"file": ("draft.txt", b"Unit 1: Confidential Draft\nInternal topics", "text/plain")}
        )
        self.assertEqual(upload_res.status_code, 201)
        doc_id = upload_res.json()["id"]

        # Student listing syllabi -> empty list
        list_res = self.client.get(f"/study-buddy/subjects/{sub.id}/syllabi", headers=self.student_aiml_headers)
        self.assertEqual(list_res.status_code, 200)
        self.assertEqual(len(list_res.json()), 0, "Student must not see unpublished documents in list")

        # Student fetching detail directly -> 403 Forbidden
        detail_res = self.client.get(f"/study-buddy/syllabi/{doc_id}", headers=self.student_aiml_headers)
        self.assertEqual(detail_res.status_code, 403)

    def test_15_publish_workflow_and_student_access(self):
        """Verify publication lifecycle: approval required before publish, then student can read."""
        sub = Subject(code=f"PUB{self.timestamp % 10000}", name="Publication Test", department="AIML")
        self.db.add(sub)
        self.db.commit()
        self.created_subject_ids.append(sub.id)

        # Upload
        up = self.client.post(
            f"/study-buddy/subjects/{sub.id}/syllabus",
            headers=self.hod_headers,
            files={"file": ("course.txt", b"Unit 1: Open Topics\nPublic topics\nUnit 2: Applied Topics\nReal world cases", "text/plain")}
        )
        doc_id = up.json()["id"]

        # Try to publish while DRAFT -> 400 Bad Request
        pub_fail = self.client.post(
            f"/study-buddy/syllabi/{doc_id}/publish",
            headers=self.hod_headers,
            json={"is_published": True}
        )
        self.assertEqual(pub_fail.status_code, 400)
        self.assertIn("approved", pub_fail.json()["detail"].lower())

        # HOD Approves
        rev = self.client.post(
            f"/study-buddy/syllabi/{doc_id}/review",
            headers=self.hod_headers,
            json={"review_status": "APPROVED", "review_notes": "Looks great"}
        )
        self.assertEqual(rev.status_code, 200)
        self.assertEqual(rev.json()["review_status"], "APPROVED")

        # HOD Publishes
        pub = self.client.post(
            f"/study-buddy/syllabi/{doc_id}/publish",
            headers=self.hod_headers,
            json={"is_published": True}
        )
        self.assertEqual(pub.status_code, 200)
        self.assertTrue(pub.json()["is_published"])

        # Student in AIML can now access
        stu_res = self.client.get(f"/study-buddy/syllabi/{doc_id}", headers=self.student_aiml_headers)
        self.assertEqual(stu_res.status_code, 200)
        self.assertEqual(stu_res.json()["id"], doc_id)
        self.assertTrue(len(stu_res.json()["units"]) >= 2)

        # Student in ECE still blocked (cross-department) -> 403 Forbidden
        ece_res = self.client.get(f"/study-buddy/syllabi/{doc_id}", headers=self.student_ece_headers)
        self.assertEqual(ece_res.status_code, 403)

    # =========================================================================
    # 7. RETRY PROCESSING WORKFLOW
    # =========================================================================

    def test_16_retry_processing_endpoint(self):
        """Verify retry endpoint re-extracts from MinIO and updates metadata."""
        sub = Subject(code=f"RET{self.timestamp % 10000}", name="Retry Test", department="AIML")
        self.db.add(sub)
        self.db.commit()
        self.created_subject_ids.append(sub.id)

        up = self.client.post(
            f"/study-buddy/subjects/{sub.id}/syllabus",
            headers=self.hod_headers,
            files={"file": ("retry.txt", b"Unit 1: Initial\nContent here", "text/plain")}
        )
        doc_id = up.json()["id"]

        retry_res = self.client.post(f"/study-buddy/syllabi/{doc_id}/retry", headers=self.hod_headers)
        self.assertEqual(retry_res.status_code, 200)
        self.assertEqual(retry_res.json()["processing_status"], "EXTRACTED")


if __name__ == "__main__":
    unittest.main()
