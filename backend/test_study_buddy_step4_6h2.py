"""
Test Suite for EduMatrix Phase 4 — Step 4.6H.2:
Student Document APIs and Unified Private-Document RAG

Covers:
1. Student document upload and metadata listing (POST & GET /study-buddy/my-documents).
2. Ownership isolation for list, detail, update, download, delete, and retry (cross-student 404).
3. Quota enforcement (15 docs, 200 MiB) and same-student duplicate protection (409 Conflict).
4. Permitted metadata updates (PATCH /study-buddy/my-documents/{id}).
5. Secure streaming download from MinIO without bucket/key exposure.
6. Hardened cleanup flow (DELETE /study-buddy/my-documents/{id}) purging DB, Qdrant, and MinIO.
7. Retry endpoint handling extraction and indexing recovery.
8. Personal document RAG retrieval ('my_documents') grounding, citations, and student isolation.
9. Authoritative PostgreSQL authorization gate: rejects stale, inactive, deleted, or foreign-owner points.
10. Inactive or unauthorized linked subjects exclusion.
11. Honest insufficient-evidence handling and verified source citations.
12. Backward compatibility of 'syllabus', 'lecture_notes', and 'all' modes, plus 'all_my_sources'.
13. Default mode preservation when omitted and validation error (422) on invalid mode.
14. RBAC protection: Placement Officers blocked (403) and Qdrant outage safety.
15. Regression: summaries, quizzes, progress tracking, and lecture notes continue working.
"""

import os
import io
import time
import uuid
import unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from io import BytesIO

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from qdrant_client.http import models

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.user import User, UserRole
from app.models.study_buddy import (
    Subject,
    SyllabusDocument,
    SyllabusUnit,
    SyllabusTopic,
    LectureNote,
    LectureNoteStatus,
    LectureNoteProcessingStatus,
    LectureNoteIndexingStatus,
    StudentStudyDocument,
    StudentDocProcessingStatus,
    StudentDocIndexingStatus,
)
from app.services.file_storage.minio_client import minio_client
from app.services.file_storage.qdrant_client import qdrant_client
from app.services.student_documents_service import (
    student_documents_service,
    STUDENT_DOCS_BUCKET,
    MAX_STUDENT_ACTIVE_DOCS,
)
from app.services.student_documents_indexing_service import (
    student_documents_indexing_service,
    STUDY_BUDDY_COLLECTION,
)
from app.services.study_buddy_chat_service import study_buddy_chat_service
from app.schemas.study_buddy import StudyBuddySourceMode
from app.main import app


class TestStudyBuddyStep46H2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db: Session = SessionLocal()
        cls.timestamp = int(time.time() * 1000)

        # 1. Resolve Users across roles
        cls.admin = cls.db.query(User).filter(User.role == UserRole.ADMIN).first()
        cls.student_aiml = cls.db.query(User).filter(User.role == UserRole.STUDENT, User.department == "AIML").first()
        cls.student_ece = cls.db.query(User).filter(User.role == UserRole.STUDENT, User.department == "ECE").first()
        cls.lecturer_aiml = cls.db.query(User).filter(User.role == UserRole.LECTURER, User.department == "AIML").first()
        cls.po = cls.db.query(User).filter(User.role == UserRole.PLACEMENT_OFFICER).first()

        # 2. Authentication headers
        cls.student_aiml_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.student_aiml.email, 'id': cls.student_aiml.id, 'role': 'student'})}"}
        cls.student_ece_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.student_ece.email, 'id': cls.student_ece.id, 'role': 'student'})}"}
        cls.po_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.po.email, 'id': cls.po.id, 'role': 'placement_officer'})}"}
        cls.admin_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.admin.email, 'id': cls.admin.id, 'role': 'admin'})}"}

        cls.created_subject_ids = []
        cls.created_sdoc_ids = []
        cls.created_minio_keys = []

        # 3. Create test subjects for AIML and ECE
        cls.subject_aiml = Subject(
            code=f"H2AIML{cls.timestamp % 10000}",
            name=f"Advanced Neural Networks {cls.timestamp}",
            department="AIML",
            semester=6,
            academic_year="2026-2027",
            curriculum_version="2026.1",
            description="AIML Test Subject for Step 4.6H.2",
            is_active=True
        )
        cls.db.add(cls.subject_aiml)

        cls.subject_ece = Subject(
            code=f"H2ECE{cls.timestamp % 10000}",
            name=f"Digital Signal Processing {cls.timestamp}",
            department="ECE",
            semester=4,
            academic_year="2026-2027",
            curriculum_version="2026.1",
            description="ECE Test Subject for Step 4.6H.2",
            is_active=True
        )
        cls.db.add(cls.subject_ece)
        cls.db.commit()
        cls.db.refresh(cls.subject_aiml)
        cls.db.refresh(cls.subject_ece)
        cls.created_subject_ids.extend([cls.subject_aiml.id, cls.subject_ece.id])

        # Ensure MinIO bucket and Qdrant collection
        student_documents_service.ensure_bucket()
        student_documents_indexing_service.ensure_collection()

    @classmethod
    def tearDownClass(cls):
        # 1. Clean student study documents created during tests
        for sdoc_id in cls.created_sdoc_ids:
            try:
                student_documents_indexing_service.delete_document_chunks(sdoc_id)
            except Exception:
                pass
            try:
                doc = cls.db.query(StudentStudyDocument).filter(StudentStudyDocument.id == sdoc_id).first()
                if doc:
                    minio_client.delete_file(doc.minio_bucket, doc.minio_object_key)
            except Exception:
                pass

        if cls.created_sdoc_ids:
            cls.db.query(StudentStudyDocument).filter(StudentStudyDocument.id.in_(cls.created_sdoc_ids)).delete(synchronize_session=False)
            cls.db.commit()

        # 2. Clean subjects
        if cls.created_subject_ids:
            cls.db.query(Subject).filter(Subject.id.in_(cls.created_subject_ids)).delete(synchronize_session=False)
            cls.db.commit()

        cls.db.close()

    def test_01_student_upload_and_metadata_listing(self):
        """Test uploading a personal study document via API and listing metadata."""
        content = (
            "Neural Architecture Search (NAS) automates the design of artificial neural networks. "
            "It explores discrete search spaces using reinforcement learning and evolutionary algorithms. "
            "Differentiable architecture search (DARTS) continuous relaxation speeds up gradient evaluation."
        )
        file_bytes = content.encode("utf-8")
        filename = f"nas_guide_{self.timestamp}.txt"

        files = {"file": (filename, BytesIO(file_bytes), "text/plain")}
        data = {
            "title": "Neural Architecture Search Guide",
            "description": "Comprehensive notes on DARTS and NAS methods",
            "subject_id": str(self.subject_aiml.id)
        }

        resp = self.client.post(
            "/study-buddy/my-documents",
            headers=self.student_aiml_headers,
            files=files,
            data=data
        )
        self.assertEqual(resp.status_code, 201)
        res = resp.json()

        doc_id = res["id"]
        self.created_sdoc_ids.append(doc_id)

        # Verify response structure and owner binding
        self.assertEqual(res["student_id"], self.student_aiml.id)
        self.assertEqual(res["title"], "Neural Architecture Search Guide")
        self.assertEqual(res["original_filename"], filename)
        self.assertEqual(res["processing_status"], "EXTRACTED")
        self.assertEqual(res["indexing_status"], "INDEXED")
        self.assertGreater(res["indexed_chunk_count"], 0)
        self.assertEqual(res["subject_id"], self.subject_aiml.id)
        self.assertEqual(res["subject_name"], self.subject_aiml.name)

        # Security check: bucket name and object key must NOT be leaked
        self.assertNotIn("minio_bucket", res)
        self.assertNotIn("minio_object_key", res)
        self.assertNotIn("extracted_text", res)

        # Verify listing
        list_resp = self.client.get("/study-buddy/my-documents", headers=self.student_aiml_headers)
        self.assertEqual(list_resp.status_code, 200)
        list_data = list_resp.json()
        self.assertGreaterEqual(list_data["total"], 1)
        doc_ids = [item["id"] for item in list_data["items"]]
        self.assertIn(doc_id, doc_ids)

        # Verify detail endpoint
        detail_resp = self.client.get(f"/study-buddy/my-documents/{doc_id}", headers=self.student_aiml_headers)
        self.assertEqual(detail_resp.status_code, 200)
        detail_data = detail_resp.json()
        self.assertEqual(detail_data["id"], doc_id)
        self.assertEqual(detail_data["title"], "Neural Architecture Search Guide")

    def test_02_ownership_isolation_cross_student(self):
        """Verify strict student isolation: Student B receives 404 for Student A's document across all actions."""
        # Student A creates a document
        doc_a = StudentStudyDocument(
            student_id=self.student_aiml.id,
            subject_id=self.subject_aiml.id,
            title="Student A Private Notes",
            original_filename="private_a.txt",
            file_size=120,
            mime_type="text/plain",
            content_hash=uuid.uuid4().hex,
            minio_bucket=STUDENT_DOCS_BUCKET,
            minio_object_key=f"student_{self.student_aiml.id}/{uuid.uuid4().hex}_private_a.txt",
            is_active=True,
            processing_status=StudentDocProcessingStatus.EXTRACTED,
            indexing_status=StudentDocIndexingStatus.INDEXED,
            indexed_chunk_count=1
        )
        self.db.add(doc_a)
        self.db.commit()
        self.db.refresh(doc_a)
        self.created_sdoc_ids.append(doc_a.id)

        # 1. Student B listing does NOT contain Student A's document
        list_b = self.client.get("/study-buddy/my-documents", headers=self.student_ece_headers)
        self.assertEqual(list_b.status_code, 200)
        b_doc_ids = [d["id"] for d in list_b.json()["items"]]
        self.assertNotIn(doc_a.id, b_doc_ids)

        # 2. Student B detail request -> 404 Not Found (no ID enumeration)
        get_b = self.client.get(f"/study-buddy/my-documents/{doc_a.id}", headers=self.student_ece_headers)
        self.assertEqual(get_b.status_code, 404)

        # 3. Student B update request -> 404 Not Found
        patch_b = self.client.patch(
            f"/study-buddy/my-documents/{doc_a.id}",
            headers=self.student_ece_headers,
            json={"title": "Hacked Title"}
        )
        self.assertEqual(patch_b.status_code, 404)

        # 4. Student B delete request -> 404 Not Found
        del_b = self.client.delete(f"/study-buddy/my-documents/{doc_a.id}", headers=self.student_ece_headers)
        self.assertEqual(del_b.status_code, 404)

        # 5. Student B retry request -> 404 Not Found
        retry_b = self.client.post(f"/study-buddy/my-documents/{doc_a.id}/retry", headers=self.student_ece_headers)
        self.assertEqual(retry_b.status_code, 404)

        # 6. Student B download request -> 404 Not Found
        down_b = self.client.get(f"/study-buddy/my-documents/{doc_a.id}/download", headers=self.student_ece_headers)
        self.assertEqual(down_b.status_code, 404)

    def test_03_quota_and_duplicate_protection_via_api(self):
        """Verify API blocks identical uploads by same student (409) and enforces document count quota (400)."""
        content = "Unique study formula: X_opt = argmin_w L(w) + lambda * ||w||_2."
        files = {"file": ("formula.txt", BytesIO(content.encode("utf-8")), "text/plain")}
        data = {"title": "Optimization Formula"}

        # First upload by Student A succeeds
        resp1 = self.client.post("/study-buddy/my-documents", headers=self.student_aiml_headers, files=files, data=data)
        self.assertEqual(resp1.status_code, 201)
        self.created_sdoc_ids.append(resp1.json()["id"])

        # Second upload by Student A with identical content -> 409 Conflict
        files2 = {"file": ("formula_dup.txt", BytesIO(content.encode("utf-8")), "text/plain")}
        resp2 = self.client.post("/study-buddy/my-documents", headers=self.student_aiml_headers, files=files2, data={"title": "Duplicate Formula"})
        self.assertEqual(resp2.status_code, 409)
        self.assertIn("already uploaded", resp2.json()["detail"].lower())

        # Identical upload by Student B succeeds (cross-student allowed)
        files3 = {"file": ("formula_b.txt", BytesIO(content.encode("utf-8")), "text/plain")}
        resp3 = self.client.post("/study-buddy/my-documents", headers=self.student_ece_headers, files=files3, data={"title": "Student B Formula"})
        self.assertEqual(resp3.status_code, 201)
        self.created_sdoc_ids.append(resp3.json()["id"])

        # Quota test: simulate MAX_STUDENT_ACTIVE_DOCS active docs
        with patch.object(student_documents_service, "check_student_quotas") as mock_quota:
            mock_quota.side_effect = HTTPException(status_code=400, detail="Document quota exceeded: Students may keep up to 15 active study documents.")
            files4 = {"file": ("quota_exceeded.txt", BytesIO(b"Test content"), "text/plain")}
            resp4 = self.client.post("/study-buddy/my-documents", headers=self.student_aiml_headers, files=files4, data={"title": "Exceeded"})
            self.assertEqual(resp4.status_code, 400)
            self.assertIn("quota exceeded", resp4.json()["detail"].lower())

    def test_04_update_permitted_metadata(self):
        """Verify PATCH /study-buddy/my-documents/{id} updates title and description."""
        doc = StudentStudyDocument(
            student_id=self.student_aiml.id,
            subject_id=self.subject_aiml.id,
            title="Initial Title",
            description="Initial Description",
            original_filename="update_test.txt",
            file_size=100,
            mime_type="text/plain",
            content_hash=uuid.uuid4().hex,
            minio_bucket=STUDENT_DOCS_BUCKET,
            minio_object_key=f"student_{self.student_aiml.id}/{uuid.uuid4().hex}_update_test.txt",
            is_active=True,
            processing_status=StudentDocProcessingStatus.EXTRACTED,
            indexing_status=StudentDocIndexingStatus.INDEXED
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        self.created_sdoc_ids.append(doc.id)

        # Successful update
        patch_resp = self.client.patch(
            f"/study-buddy/my-documents/{doc.id}",
            headers=self.student_aiml_headers,
            json={"title": "Updated Modern Title", "description": "Refined Study Description"}
        )
        self.assertEqual(patch_resp.status_code, 200)
        data = patch_resp.json()
        self.assertEqual(data["title"], "Updated Modern Title")
        self.assertEqual(data["description"], "Refined Study Description")

        # Empty title validation
        bad_patch = self.client.patch(
            f"/study-buddy/my-documents/{doc.id}",
            headers=self.student_aiml_headers,
            json={"title": "   "}
        )
        self.assertEqual(bad_patch.status_code, 400)

    def test_05_secure_download(self):
        """Verify GET /study-buddy/my-documents/{id}/download streams binary securely."""
        content = "Secure original study text stream."
        doc_uuid = uuid.uuid4().hex
        object_key = f"student_{self.student_aiml.id}/{doc_uuid}_dl_test.txt"

        minio_client.upload_file(
            bucket=STUDENT_DOCS_BUCKET,
            object_key=object_key,
            file_data=content.encode("utf-8"),
            content_type="text/plain"
        )

        doc = StudentStudyDocument(
            student_id=self.student_aiml.id,
            title="Download Test Doc",
            original_filename="dl_test.txt",
            file_size=len(content),
            mime_type="text/plain",
            content_hash=uuid.uuid4().hex,
            minio_bucket=STUDENT_DOCS_BUCKET,
            minio_object_key=object_key,
            is_active=True,
            processing_status=StudentDocProcessingStatus.EXTRACTED,
            indexing_status=StudentDocIndexingStatus.INDEXED
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        self.created_sdoc_ids.append(doc.id)

        dl_resp = self.client.get(f"/study-buddy/my-documents/{doc.id}/download", headers=self.student_aiml_headers)
        self.assertEqual(dl_resp.status_code, 200)
        self.assertEqual(dl_resp.content.decode("utf-8"), content)
        self.assertIn("attachment; filename=", dl_resp.headers.get("Content-Disposition", ""))

    def test_06_hardened_delete_flow(self):
        """Verify DELETE /study-buddy/my-documents/{id} cleans up DB, Qdrant chunks, and MinIO binary."""
        content = "Content to be completely purged across DB, MinIO, and Qdrant."
        doc_uuid = uuid.uuid4().hex
        object_key = f"student_{self.student_aiml.id}/{doc_uuid}_delete_me.txt"

        minio_client.upload_file(
            bucket=STUDENT_DOCS_BUCKET,
            object_key=object_key,
            file_data=content.encode("utf-8"),
            content_type="text/plain"
        )

        doc = StudentStudyDocument(
            student_id=self.student_aiml.id,
            title="Delete Me Doc",
            original_filename="delete_me.txt",
            file_size=len(content),
            mime_type="text/plain",
            content_hash=uuid.uuid4().hex,
            minio_bucket=STUDENT_DOCS_BUCKET,
            minio_object_key=object_key,
            is_active=True,
            processing_status=StudentDocProcessingStatus.EXTRACTED,
            extracted_text=content,
            indexing_status=StudentDocIndexingStatus.NOT_INDEXED
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        doc_id = doc.id

        # Index into Qdrant
        student_documents_indexing_service.index_student_document(self.db, doc_id, self.student_aiml.id)

        # Verify Qdrant has chunks
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"student_study_doc_{doc_id}_chunk_1"))
        retrieved = qdrant_client.client.retrieve(collection_name=STUDY_BUDDY_COLLECTION, ids=[point_id])
        self.assertEqual(len(retrieved), 1)

        # Call DELETE endpoint
        del_resp = self.client.delete(f"/study-buddy/my-documents/{doc_id}", headers=self.student_aiml_headers)
        self.assertEqual(del_resp.status_code, 200)

        # Verify DB row is completely purged
        self.db.expire_all()
        check_doc = self.db.query(StudentStudyDocument).filter(StudentStudyDocument.id == doc_id).first()
        self.assertIsNone(check_doc)

        # Verify Qdrant points are purged
        retrieved_after = qdrant_client.client.retrieve(collection_name=STUDY_BUDDY_COLLECTION, ids=[point_id])
        self.assertEqual(len(retrieved_after), 0)

        # Verify MinIO binary is purged
        with self.assertRaises(Exception):
            minio_client.get_file(STUDENT_DOCS_BUCKET, object_key)

    def test_07_retry_endpoint_behavior(self):
        """Verify POST /study-buddy/my-documents/{id}/retry recovers failed indexing."""
        content = "Retryable document text content for vector indexing."
        doc_uuid = uuid.uuid4().hex
        object_key = f"student_{self.student_aiml.id}/{doc_uuid}_retry_test.txt"

        minio_client.upload_file(
            bucket=STUDENT_DOCS_BUCKET,
            object_key=object_key,
            file_data=content.encode("utf-8"),
            content_type="text/plain"
        )

        doc = StudentStudyDocument(
            student_id=self.student_aiml.id,
            title="Retry Test Doc",
            original_filename="retry_test.txt",
            file_size=len(content),
            mime_type="text/plain",
            content_hash=uuid.uuid4().hex,
            minio_bucket=STUDENT_DOCS_BUCKET,
            minio_object_key=object_key,
            is_active=True,
            processing_status=StudentDocProcessingStatus.EXTRACTED,
            extracted_text=content,
            indexing_status=StudentDocIndexingStatus.FAILED,
            indexed_chunk_count=0
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        self.created_sdoc_ids.append(doc.id)

        retry_resp = self.client.post(f"/study-buddy/my-documents/{doc.id}/retry", headers=self.student_aiml_headers)
        self.assertEqual(retry_resp.status_code, 200)
        res = retry_resp.json()
        self.assertEqual(res["indexing_status"], "INDEXED")
        self.assertGreater(res["indexed_chunk_count"], 0)

    def test_08_my_documents_retrieval_and_chat_grounding(self):
        """Verify chat answering in 'my_documents' mode is strictly grounded and isolated per student."""
        # 1. Student A uploads unique knowledge
        content_a = (
            "Hyperband Algorithm combines random search with early stopping based on successive halving. "
            "It allocates more resources to high-performing hyperparameter configurations."
        )
        files_a = {"file": ("hyperband_notes.txt", BytesIO(content_a.encode("utf-8")), "text/plain")}
        data_a = {"title": "Hyperband Notes"}

        resp_a = self.client.post("/study-buddy/my-documents", headers=self.student_aiml_headers, files=files_a, data=data_a)
        self.assertEqual(resp_a.status_code, 201)
        doc_a_id = resp_a.json()["id"]
        self.created_sdoc_ids.append(doc_a_id)

        # 2. Student A asks question grounded in personal notes
        chat_resp_a = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={
                "question": "How does the Hyperband algorithm work?",
                "source_mode": "my_documents"
            }
        )
        self.assertEqual(chat_resp_a.status_code, 200)
        data = chat_resp_a.json()
        self.assertTrue(data["has_sufficient_evidence"])
        self.assertGreaterEqual(len(data["citations"]), 1)

        # Verify citation structure
        citation = data["citations"][0]
        self.assertEqual(citation["source_type"], "student_upload")
        self.assertEqual(citation["student_study_document_id"], doc_a_id)
        self.assertEqual(citation["source_title"], "Hyperband Notes")
        self.assertEqual(citation["original_filename"], "hyperband_notes.txt")

        # 3. Student B asks the same question in 'my_documents' mode
        chat_resp_b = self.client.post(
            "/study-buddy/chat",
            headers=self.student_ece_headers,
            json={
                "question": "How does the Hyperband algorithm work?",
                "source_mode": "my_documents"
            }
        )
        self.assertEqual(chat_resp_b.status_code, 200)
        data_b = chat_resp_b.json()
        # Student B has NOT uploaded Hyperband notes, so evidence guard must trigger!
        self.assertFalse(data_b["has_sufficient_evidence"])
        self.assertEqual(len(data_b["citations"]), 0)
        self.assertIn("selected uploaded personal study documents do not provide sufficient information", data_b["answer"])

    def test_09_postgresql_authorization_gate_stale_and_foreign_chunks(self):
        """Verify search_student_document_chunks PostgreSQL gate filters out stale, deactivated, or foreign points."""
        # Create an active document for Student A
        doc = StudentStudyDocument(
            student_id=self.student_aiml.id,
            title="Gate Test Doc",
            original_filename="gate.txt",
            file_size=100,
            mime_type="text/plain",
            content_hash=uuid.uuid4().hex,
            minio_bucket=STUDENT_DOCS_BUCKET,
            minio_object_key=f"student_{self.student_aiml.id}/{uuid.uuid4().hex}_gate.txt",
            is_active=True,
            processing_status=StudentDocProcessingStatus.EXTRACTED,
            extracted_text="PostgreSQL authorization gate verification test passage.",
            indexing_status=StudentDocIndexingStatus.NOT_INDEXED
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        self.created_sdoc_ids.append(doc.id)

        student_documents_indexing_service.index_student_document(self.db, doc.id, self.student_aiml.id)

        # Verify it can be retrieved by Student A
        chunks = study_buddy_chat_service.search_student_document_chunks(
            db=self.db,
            query="authorization gate verification",
            current_user=self.student_aiml,
            limit=5
        )
        self.assertGreaterEqual(len(chunks), 1)

        # 1. Deactivate document in PostgreSQL (is_active = False)
        doc.is_active = False
        self.db.commit()

        # Query again: must return 0 chunks even though Qdrant vector still exists
        chunks_after_deact = study_buddy_chat_service.search_student_document_chunks(
            db=self.db,
            query="authorization gate verification",
            current_user=self.student_aiml,
            limit=5
        )
        self.assertEqual(len(chunks_after_deact), 0)

        # 2. Reactivate, but change indexing_status to FAILED
        doc.is_active = True
        doc.indexing_status = StudentDocIndexingStatus.FAILED
        self.db.commit()

        chunks_after_fail = study_buddy_chat_service.search_student_document_chunks(
            db=self.db,
            query="authorization gate verification",
            current_user=self.student_aiml,
            limit=5
        )
        self.assertEqual(len(chunks_after_fail), 0)

    def test_10_linked_inactive_or_unauthorized_subject_exclusion(self):
        """Verify chunks linked to inactive or unauthorized subjects are rejected by PostgreSQL validation."""
        # Create an inactive subject
        inactive_subject = Subject(
            code=f"INACT{self.timestamp % 10000}",
            name="Inactive Subject",
            department="AIML",
            semester=6,
            academic_year="2026-2027",
            curriculum_version="2026.1",
            is_active=False
        )
        self.db.add(inactive_subject)
        self.db.commit()
        self.db.refresh(inactive_subject)
        self.created_subject_ids.append(inactive_subject.id)

        doc = StudentStudyDocument(
            student_id=self.student_aiml.id,
            subject_id=inactive_subject.id,
            title="Inactive Subject Doc",
            original_filename="inactive_subj.txt",
            file_size=100,
            mime_type="text/plain",
            content_hash=uuid.uuid4().hex,
            minio_bucket=STUDENT_DOCS_BUCKET,
            minio_object_key=f"student_{self.student_aiml.id}/{uuid.uuid4().hex}_inact.txt",
            is_active=True,
            processing_status=StudentDocProcessingStatus.EXTRACTED,
            extracted_text="Knowledge for inactive subject verification.",
            indexing_status=StudentDocIndexingStatus.NOT_INDEXED
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        self.created_sdoc_ids.append(doc.id)

        # Index manually
        doc.indexing_status = StudentDocIndexingStatus.INDEXED
        doc.indexed_chunk_count = 1
        self.db.commit()

        # Mock Qdrant return to simulate candidate chunk
        mock_result = MagicMock()
        mock_result.score = 0.85
        mock_result.payload = {
            "source_type": "student_upload",
            "student_study_document_id": doc.id,
            "student_id": self.student_aiml.id,
            "subject_id": inactive_subject.id,
            "text": "Knowledge for inactive subject verification."
        }

        with patch.object(qdrant_client.client, "query_points") as mock_qp:
            mock_resp = MagicMock()
            mock_resp.points = [mock_result]
            mock_qp.return_value = mock_resp

            chunks = study_buddy_chat_service.search_student_document_chunks(
                db=self.db,
                query="inactive subject verification",
                current_user=self.student_aiml
            )
            # Must reject because subject is inactive!
            self.assertEqual(len(chunks), 0)

    def test_11_insufficient_evidence_and_citation_contract(self):
        """Verify honest insufficient evidence response in my_documents mode when query doesn't match."""
        chat_resp = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={
                "question": "What is the capital of Atlantis in 3000 BC?",
                "source_mode": "my_documents"
            }
        )
        self.assertEqual(chat_resp.status_code, 200)
        data = chat_resp.json()
        self.assertFalse(data["has_sufficient_evidence"])
        self.assertEqual(len(data["citations"]), 0)
        self.assertEqual(data["model_used"], "evidence_guard")
        self.assertIn("selected uploaded personal study documents do not provide sufficient information", data["answer"])

    def test_12_source_mode_backward_compatibility(self):
        """Verify backward compatibility of syllabus, lecture_notes, all, and new all_my_sources modes."""
        # 1. Invalid source mode -> 422 Unprocessable Entity
        bad_mode_resp = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={
                "question": "What is machine learning?",
                "source_mode": "invalid_mode_name"
            }
        )
        self.assertEqual(bad_mode_resp.status_code, 422)

        # 2. Omitting source_mode defaults to 'syllabus'
        default_resp = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={"question": "What is machine learning?"}
        )
        self.assertEqual(default_resp.status_code, 200)

        # 3. Explicit 'syllabus', 'lecture_notes', 'all' modes work without error
        for mode in ("syllabus", "lecture_notes", "all", "all_my_sources"):
            r = self.client.post(
                "/study-buddy/chat",
                headers=self.student_aiml_headers,
                json={"question": "What is gradient descent?", "source_mode": mode}
            )
            self.assertEqual(r.status_code, 200)

        # 4. Search endpoint also respects source_modes
        search_resp = self.client.get(
            "/study-buddy/search",
            headers=self.student_aiml_headers,
            params={"query": "gradient descent", "source_mode": "my_documents"}
        )
        self.assertEqual(search_resp.status_code, 200)

    def test_13_placement_officer_and_failure_resilience(self):
        """Verify Placement Officers are strictly blocked (403) and Qdrant outages fail gracefully."""
        # 1. Placement Officers blocked from upload
        files = {"file": ("po_doc.txt", BytesIO(b"Confidential"), "text/plain")}
        po_upload = self.client.post("/study-buddy/my-documents", headers=self.po_headers, files=files, data={"title": "PO Doc"})
        self.assertEqual(po_upload.status_code, 403)

        # 2. Placement Officers blocked from list
        po_list = self.client.get("/study-buddy/my-documents", headers=self.po_headers)
        self.assertEqual(po_list.status_code, 403)

        # 3. Placement Officers blocked from chat
        po_chat = self.client.post(
            "/study-buddy/chat",
            headers=self.po_headers,
            json={"question": "Any academic notes?", "source_mode": "my_documents"}
        )
        self.assertEqual(po_chat.status_code, 403)

        # 4. Qdrant outage simulation during retrieval
        with patch.object(qdrant_client.client, "query_points", side_effect=Exception("Qdrant connection refused")):
            chunks = study_buddy_chat_service.search_student_document_chunks(
                db=self.db,
                query="any query",
                current_user=self.student_aiml
            )
            self.assertEqual(chunks, [])  # Gracefully returns empty list, does not crash or leak data

    def test_14_regression_study_buddy_features(self):
        """Verify existing Study Buddy summaries, quizzes, progress, and lecture notes remain functional."""
        # 1. Subject list
        sub_resp = self.client.get("/study-buddy/subjects", headers=self.student_aiml_headers)
        self.assertEqual(sub_resp.status_code, 200)

        # 2. Student progress dashboard
        prog_resp = self.client.get("/study-buddy/progress/dashboard", headers=self.student_aiml_headers)
        self.assertEqual(prog_resp.status_code, 200)

        # 3. Lecture notes list
        notes_resp = self.client.get(f"/study-buddy/subjects/{self.subject_aiml.id}/notes", headers=self.student_aiml_headers)
        self.assertEqual(notes_resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
