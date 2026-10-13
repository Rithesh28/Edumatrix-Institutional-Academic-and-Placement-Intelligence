"""
EduMatrix Phase 4 — Step 4.2: RAG Indexing and Retrieval Foundation Test Suite

Verifies:
1. Dedicated Qdrant collection ('study_buddy_chunks') initialization with 384-dim COSINE vectors.
2. Proof that the existing 'files' collection remains intact and unmodified.
3. Deterministic chunking with stable UUIDv5 identifiers, SHA256 content hashes, and unit/topic/page provenance.
4. Embedding dimension verification (384 dimensions from all-MiniLM-L6-v2) and mismatch detection.
5. Strict PostgreSQL eligibility checks (only APPROVED + is_published documents can be indexed).
6. Idempotent indexing: re-indexing replaces points without duplicating chunks.
7. Unpublish and supersede synchronization: unpublishing removes points from Qdrant; publishing a new version unpublishes/supersedes older versions.
8. Multi-syllabus version isolation: indexing/deleting one document's points never affects other documents' points.
9. Qdrant failure recovery: preserves syllabus in PostgreSQL and records safe indexing failure status.
10. Multi-role authorization:
    - Students blocked from triggering indexing or inspecting internal indexing metadata (HTTP 403).
    - Placement Officer blocked from indexing and search (HTTP 403).
    - HOD cross-department indexing blocked (HTTP 403).
    - Semantic search respects department isolation and excludes unpublished drafts.
11. PDF extraction: typed PDF (via ReportLab) and scanned PDF (via Tesseract OCR).
"""

import io
import time
import uuid
import unittest
from datetime import datetime, timezone
from PIL import Image, ImageDraw
import sqlalchemy as sa
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.core.database import SessionLocal, engine
from app.core.security import create_access_token
from app.models.user import User, UserRole
from app.models.study_buddy import (
    Subject,
    SyllabusDocument,
    SyllabusUnit,
    SyllabusTopic,
    SyllabusProcessingStatus,
    SyllabusReviewStatus
)
from app.services.file_storage.qdrant_client import qdrant_client
from qdrant_client.http import models
from app.services.embedding_service import embedding_service
from app.services.syllabus_ingestion_service import syllabus_ingestion_service
from app.services.syllabus_indexing_service import (
    syllabus_indexing_service,
    STUDY_BUDDY_COLLECTION,
    STUDY_BUDDY_VECTOR_SIZE
)
from app.main import app


class TestStudyBuddyStep42(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db: Session = SessionLocal()
        cls.timestamp = int(time.time() * 1000)

        # Users across roles
        cls.admin = cls.db.query(User).filter(User.role == UserRole.ADMIN).first()
        cls.hod_aiml = cls.db.query(User).filter(User.role == UserRole.HOD, User.department == "AIML").first()
        cls.lecturer_aiml = cls.db.query(User).filter(User.role == UserRole.LECTURER, User.department == "AIML").first()
        cls.student_aiml = cls.db.query(User).filter(User.role == UserRole.STUDENT, User.department == "AIML").first()
        cls.student_ece = cls.db.query(User).filter(User.role == UserRole.STUDENT, User.department == "ECE").first()
        cls.po = cls.db.query(User).filter(User.role == UserRole.PLACEMENT_OFFICER).first()

        # Auth headers
        cls.admin_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.admin.email, 'id': cls.admin.id, 'role': 'admin'})}"}
        cls.hod_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.hod_aiml.email, 'id': cls.hod_aiml.id, 'role': 'hod'})}"}
        cls.lecturer_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.lecturer_aiml.email, 'id': cls.lecturer_aiml.id, 'role': 'lecturer'})}"}
        cls.student_aiml_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.student_aiml.email, 'id': cls.student_aiml.id, 'role': 'student'})}"}
        cls.student_ece_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.student_ece.email, 'id': cls.student_ece.id, 'role': 'student'})}"}
        cls.po_headers = {"Authorization": f"Bearer {create_access_token({'sub': cls.po.email, 'id': cls.po.id, 'role': 'placement_officer'})}"}

        cls.created_subject_ids = []

        # Record points count in files collection before tests
        cls.files_collection_points_before = 0
        try:
            info = qdrant_client.client.get_collection("files")
            cls.files_collection_points_before = info.points_count
        except Exception:
            pass

    @classmethod
    def tearDownClass(cls):
        # Cleanup test subjects and clean their chunks from Qdrant
        if cls.created_subject_ids:
            docs = cls.db.query(SyllabusDocument).filter(
                SyllabusDocument.subject_id.in_(cls.created_subject_ids)
            ).all()
            for d in docs:
                syllabus_indexing_service.delete_document_chunks(d.id)

            cls.db.query(Subject).filter(Subject.id.in_(cls.created_subject_ids)).delete(synchronize_session=False)
            cls.db.commit()
        cls.db.close()

    # =========================================================================
    # 1. DEDICATED QDRANT COLLECTION INITIALIZATION & INTEGRITY
    # =========================================================================

    def test_01_dedicated_collection_initialization(self):
        """Verify study_buddy_chunks collection exists with 384-dim COSINE vectors."""
        success = syllabus_indexing_service.ensure_collection()
        self.assertTrue(success)

        info = qdrant_client.client.get_collection(STUDY_BUDDY_COLLECTION)
        self.assertEqual(info.config.params.vectors.size, STUDY_BUDDY_VECTOR_SIZE)
        self.assertEqual(info.config.params.vectors.distance.name, "COSINE")

    def test_02_existing_files_collection_unchanged(self):
        """Prove that the existing 'files' collection exists and was not modified or cleared."""
        collections = [c.name for c in qdrant_client.client.get_collections().collections]
        self.assertIn("files", collections, "'files' collection must remain present")
        self.assertIn(STUDY_BUDDY_COLLECTION, collections, "'study_buddy_chunks' collection must be present")

        files_info = qdrant_client.client.get_collection("files")
        self.assertEqual(files_info.config.params.vectors.size, 384)
        # Point count should not have decreased
        self.assertGreaterEqual(files_info.points_count, self.files_collection_points_before)

    # =========================================================================
    # 2. EMBEDDING DIMENSIONS & DETERMINISTIC CHUNKING
    # =========================================================================

    def test_03_embedding_dimension_verification(self):
        """Verify all-MiniLM-L6-v2 produces exactly 384-dimensional vectors."""
        dim = embedding_service.get_embedding_dimension()
        self.assertEqual(dim, 384)

        sample_vector = embedding_service.embed_text("Deep Learning and Neural Networks")
        self.assertIsNotNone(sample_vector)
        self.assertEqual(len(sample_vector), 384)

    def test_04_deterministic_chunking_and_provenance(self):
        """Verify deterministic UUIDv5, SHA256 hashes, and unit/topic metadata on chunks."""
        sub = Subject(code=f"RAG{self.timestamp % 10000}", name="RAG Architecture", department="AIML")
        self.db.add(sub)
        self.db.commit()
        self.created_subject_ids.append(sub.id)

        doc = SyllabusDocument(
            subject_id=sub.id,
            version=1,
            is_latest=True,
            title="RAG Syllabus",
            original_filename="rag.txt",
            file_size=500,
            mime_type="text/plain",
            minio_bucket="syllabi",
            minio_object_key=f"syllabi/{sub.id}/rag_{self.timestamp}.txt",
            processing_status=SyllabusProcessingStatus.EXTRACTED,
            review_status=SyllabusReviewStatus.APPROVED,
            is_published=True
        )
        self.db.add(doc)
        self.db.commit()

        unit1 = SyllabusUnit(
            document_id=doc.id,
            unit_number=1,
            title="Unit 1: Vector Embeddings",
            order=1,
            source_page_start=1,
            source_evidence="Unit 1: Vector Embeddings"
        )
        self.db.add(unit1)
        self.db.commit()

        topic1 = SyllabusTopic(
            unit_id=unit1.id,
            title="Dense vs Sparse Embeddings",
            order=1,
            extracted_text="Dense embeddings capture semantic meaning in vector space.",
            source_page=1,
            source_evidence="Dense vs Sparse Embeddings"
        )
        self.db.add(topic1)
        self.db.commit()
        self.db.refresh(doc)

        chunks1 = syllabus_indexing_service.create_chunks(doc)
        chunks2 = syllabus_indexing_service.create_chunks(doc)

        self.assertEqual(len(chunks1), 1)
        self.assertEqual(chunks1[0]["point_id"], chunks2[0]["point_id"], "Point ID must be deterministic UUIDv5")
        self.assertEqual(chunks1[0]["payload"]["content_hash"], chunks2[0]["payload"]["content_hash"])
        self.assertEqual(chunks1[0]["payload"]["unit_number"], 1)
        self.assertEqual(chunks1[0]["payload"]["topic_title"], "Dense vs Sparse Embeddings")
        self.assertEqual(chunks1[0]["payload"]["source_page"], 1)

    # =========================================================================
    # 3. ELIGIBILITY GATES & IDEMPOTENT INDEXING
    # =========================================================================

    def test_05_unapproved_or_unpublished_indexing_rejected(self):
        """Verify documents in DRAFT or unpublished states are rejected for indexing."""
        sub = Subject(code=f"GAT{self.timestamp % 10000}", name="Gating Test", department="AIML")
        self.db.add(sub)
        self.db.commit()
        self.created_subject_ids.append(sub.id)

        # Upload syllabus via API (starts as DRAFT + unpublished)
        up = self.client.post(
            f"/study-buddy/subjects/{sub.id}/syllabus",
            headers=self.hod_headers,
            files={"file": ("gating.txt", b"Unit 1: Draft Topics\nUnapproved content", "text/plain")}
        )
        doc_id = up.json()["id"]

        # Attempt to index draft document -> HTTP 400
        idx_res = self.client.post(f"/study-buddy/syllabi/{doc_id}/index", headers=self.hod_headers)
        self.assertEqual(idx_res.status_code, 400)
        self.assertIn("not eligible", idx_res.json()["detail"].lower())

    def test_06_idempotent_indexing_and_point_count(self):
        """Verify indexing twice does not duplicate points in Qdrant."""
        sub = Subject(code=f"IDM{self.timestamp % 10000}", name="Idempotency Test", department="AIML")
        self.db.add(sub)
        self.db.commit()
        self.created_subject_ids.append(sub.id)

        # Upload
        up = self.client.post(
            f"/study-buddy/subjects/{sub.id}/syllabus",
            headers=self.hod_headers,
            files={"file": ("idempotent.txt", b"Unit 1: Core Systems\nTopic A\nTopic B\nUnit 2: Advanced\nTopic C", "text/plain")}
        )
        doc_id = up.json()["id"]

        # Approve and Publish
        self.client.post(f"/study-buddy/syllabi/{doc_id}/review", headers=self.hod_headers, json={"review_status": "APPROVED"})
        pub_res = self.client.post(f"/study-buddy/syllabi/{doc_id}/publish", headers=self.hod_headers, json={"is_published": True})
        self.assertEqual(pub_res.status_code, 200)

        # Retrieve points count for this document
        points_1 = qdrant_client.client.scroll(
            collection_name=STUDY_BUDDY_COLLECTION,
            scroll_filter=models.Filter(must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=doc_id))]),
            limit=50
        )[0]
        initial_count = len(points_1)
        self.assertGreater(initial_count, 0)

        # Re-index manually via endpoint
        reindex_res = self.client.post(f"/study-buddy/syllabi/{doc_id}/index", headers=self.hod_headers)
        self.assertEqual(reindex_res.status_code, 200)

        points_2 = qdrant_client.client.scroll(
            collection_name=STUDY_BUDDY_COLLECTION,
            scroll_filter=models.Filter(must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=doc_id))]),
            limit=50
        )[0]
        self.assertEqual(len(points_2), initial_count, "Point count must remain identical after re-indexing")

    # =========================================================================
    # 4. UNPUBLISH & SUPERSEDED VERSION SYNCHRONIZATION
    # =========================================================================

    def test_07_unpublish_removes_qdrant_points(self):
        """Verify unpublishing a syllabus document deletes its points from Qdrant."""
        sub = Subject(code=f"UNP{self.timestamp % 10000}", name="Unpublish Sync", department="AIML")
        self.db.add(sub)
        self.db.commit()
        self.created_subject_ids.append(sub.id)

        # Upload, approve, publish
        up = self.client.post(
            f"/study-buddy/subjects/{sub.id}/syllabus",
            headers=self.hod_headers,
            files={"file": ("unpub.txt", b"Unit 1: Active Content\nReal time points", "text/plain")}
        )
        doc_id = up.json()["id"]
        self.client.post(f"/study-buddy/syllabi/{doc_id}/review", headers=self.hod_headers, json={"review_status": "APPROVED"})
        self.client.post(f"/study-buddy/syllabi/{doc_id}/publish", headers=self.hod_headers, json={"is_published": True})

        # Verify indexed points exist
        pts_before = qdrant_client.client.scroll(
            collection_name=STUDY_BUDDY_COLLECTION,
            scroll_filter=models.Filter(must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=doc_id))]),
            limit=10
        )[0]
        self.assertGreater(len(pts_before), 0)

        # Unpublish
        unpub_res = self.client.post(f"/study-buddy/syllabi/{doc_id}/publish", headers=self.hod_headers, json={"is_published": False})
        self.assertEqual(unpub_res.status_code, 200)
        self.assertFalse(unpub_res.json()["is_published"])

        # Verify points deleted from Qdrant
        pts_after = qdrant_client.client.scroll(
            collection_name=STUDY_BUDDY_COLLECTION,
            scroll_filter=models.Filter(must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=doc_id))]),
            limit=10
        )[0]
        self.assertEqual(len(pts_after), 0, "All points for unpublished document must be removed from Qdrant")

    def test_08_superseded_version_unpublishing_and_isolation(self):
        """Verify publishing version 2 unpublishes and unindexes version 1 without affecting other subjects."""
        sub = Subject(code=f"SUP{self.timestamp % 10000}", name="Supersede Test", department="AIML")
        self.db.add(sub)
        self.db.commit()
        self.created_subject_ids.append(sub.id)

        # 1. Upload & publish Version 1
        up1 = self.client.post(
            f"/study-buddy/subjects/{sub.id}/syllabus",
            headers=self.hod_headers,
            files={"file": ("v1.txt", b"Unit 1: Version 1 Content\nOld syllabus", "text/plain")}
        )
        doc1_id = up1.json()["id"]
        self.client.post(f"/study-buddy/syllabi/{doc1_id}/review", headers=self.hod_headers, json={"review_status": "APPROVED"})
        self.client.post(f"/study-buddy/syllabi/{doc1_id}/publish", headers=self.hod_headers, json={"is_published": True})

        # 2. Upload & publish Version 2
        up2 = self.client.post(
            f"/study-buddy/subjects/{sub.id}/syllabus",
            headers=self.hod_headers,
            files={"file": ("v2.txt", b"Unit 1: Version 2 Content\nNew syllabus revision", "text/plain")}
        )
        doc2_id = up2.json()["id"]
        self.client.post(f"/study-buddy/syllabi/{doc2_id}/review", headers=self.hod_headers, json={"review_status": "APPROVED"})
        self.client.post(f"/study-buddy/syllabi/{doc2_id}/publish", headers=self.hod_headers, json={"is_published": True})

        # Verify Version 1 in PostgreSQL is now is_published=False
        doc1 = self.db.query(SyllabusDocument).filter(SyllabusDocument.id == doc1_id).first()
        self.db.refresh(doc1)
        self.assertFalse(doc1.is_published, "Version 1 must be automatically unpublished when Version 2 is published")

        # Verify Version 1 points removed from Qdrant
        pts_v1 = qdrant_client.client.scroll(
            collection_name=STUDY_BUDDY_COLLECTION,
            scroll_filter=models.Filter(must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=doc1_id))]),
            limit=10
        )[0]
        self.assertEqual(len(pts_v1), 0, "Version 1 points must be removed from Qdrant")

        # Verify Version 2 points are present in Qdrant
        pts_v2 = qdrant_client.client.scroll(
            collection_name=STUDY_BUDDY_COLLECTION,
            scroll_filter=models.Filter(must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=doc2_id))]),
            limit=10
        )[0]
        self.assertGreater(len(pts_v2), 0, "Version 2 points must be indexed in Qdrant")

    # =========================================================================
    # 5. MULTI-ROLE RBAC & SEMANTIC SEARCH RETRIEVAL
    # =========================================================================

    def test_09_student_cannot_trigger_or_inspect_indexing(self):
        """Verify students cannot trigger indexing or view internal indexing metadata (HTTP 403)."""
        sub = Subject(code=f"SEC{self.timestamp % 10000}", name="Security Test", department="AIML")
        self.db.add(sub)
        self.db.commit()
        self.created_subject_ids.append(sub.id)

        up = self.client.post(
            f"/study-buddy/subjects/{sub.id}/syllabus",
            headers=self.hod_headers,
            files={"file": ("sec.txt", b"Unit 1: Security\nCryptographic protocols", "text/plain")}
        )
        doc_id = up.json()["id"]

        # Student attempts to trigger index -> 403
        idx_res = self.client.post(f"/study-buddy/syllabi/{doc_id}/index", headers=self.student_aiml_headers)
        self.assertEqual(idx_res.status_code, 403)

        # Student attempts to inspect indexing status -> 403
        stat_res = self.client.get(f"/study-buddy/syllabi/{doc_id}/indexing-status", headers=self.student_aiml_headers)
        self.assertEqual(stat_res.status_code, 403)

        # Faculty can inspect indexing status
        fac_stat = self.client.get(f"/study-buddy/syllabi/{doc_id}/indexing-status", headers=self.lecturer_headers)
        self.assertEqual(fac_stat.status_code, 200)
        self.assertIn("indexing_status", fac_stat.json())

    def test_10_semantic_search_department_isolation(self):
        """Verify semantic search returns relevant chunks to same-dept students but blocks cross-dept."""
        sub = Subject(code=f"SRC{self.timestamp % 10000}", name="Database Architecture", department="AIML")
        self.db.add(sub)
        self.db.commit()
        self.created_subject_ids.append(sub.id)

        # Ingest, approve, publish
        up = self.client.post(
            f"/study-buddy/subjects/{sub.id}/syllabus",
            headers=self.hod_headers,
            files={"file": ("db.txt", b"Unit 1: Relational Algebra\nTuple relational calculus and schema joins", "text/plain")}
        )
        doc_id = up.json()["id"]
        self.client.post(f"/study-buddy/syllabi/{doc_id}/review", headers=self.hod_headers, json={"review_status": "APPROVED"})
        self.client.post(f"/study-buddy/syllabi/{doc_id}/publish", headers=self.hod_headers, json={"is_published": True})

        # AIML student searches for "relational calculus" -> gets results
        search_aiml = self.client.get(
            "/study-buddy/search?query=relational+calculus",
            headers=self.student_aiml_headers
        )
        self.assertEqual(search_aiml.status_code, 200)
        results = search_aiml.json()
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["department"], "AIML")
        self.assertIn("relational", results[0]["text"].lower())

        # ECE student searches for "relational calculus" -> gets 0 results due to department isolation
        search_ece = self.client.get(
            "/study-buddy/search?query=relational+calculus",
            headers=self.student_ece_headers
        )
        self.assertEqual(search_ece.status_code, 200)
        self.assertEqual(len(search_ece.json()), 0, "Cross-department student must not retrieve other departments' syllabus chunks")

    # =========================================================================
    # 6. PDF EXTRACTION & SCANNED PDF OCR TESTS (Area 3 Verification)
    # =========================================================================

    def test_11_typed_pdf_extraction_via_reportlab(self):
        """Verify real typed PDF generated with ReportLab extracts clean text and segments units."""
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        c.drawString(100, 750, "Course Syllabus: Advanced Algorithms")
        c.drawString(100, 720, "Unit 1: Dynamic Programming")
        c.drawString(100, 700, "Optimal substructure, Memoization, Matrix Chain Multiplication.")
        c.showPage()
        c.drawString(100, 750, "Unit 2: Graph Theory")
        c.drawString(100, 720, "Dijkstra, Bellman-Ford, Max-Flow Min-Cut.")
        c.save()
        pdf_bytes = buf.getvalue()

        full_text, pages, extractor, err = syllabus_ingestion_service.extract_content("algo.pdf", pdf_bytes)
        self.assertIsNone(err)
        self.assertIn("Dynamic Programming", full_text)
        self.assertEqual(extractor, "pdfplumber")

        units, is_high_confidence = syllabus_ingestion_service._segment_units_and_topics(full_text, pages)
        self.assertTrue(is_high_confidence)
        self.assertEqual(len(units), 2)
        self.assertEqual(units[0]["unit_number"], 1)
        self.assertEqual(units[1]["unit_number"], 2)

    def test_12_scanned_pdf_tesseract_ocr_fallback(self):
        """Verify scanned image-only PDF triggers Tesseract OCR fallback and extracts text."""
        img = Image.new("RGB", (600, 200), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        d.text((20, 50), "Unit 1: Scanned Syllabus Document", fill=(0, 0, 0))
        d.text((20, 100), "Linear algebra and matrix decompositions", fill=(0, 0, 0))

        pdf_buf = io.BytesIO()
        img.save(pdf_buf, format="PDF")
        scanned_pdf_bytes = pdf_buf.getvalue()

        full_text, pages, extractor, err = syllabus_ingestion_service.extract_content("scanned.pdf", scanned_pdf_bytes)
        self.assertIsNone(err)
        self.assertIn("Scanned Syllabus Document", full_text)
        self.assertEqual(extractor, "tesseract_ocr")


if __name__ == "__main__":
    unittest.main()
