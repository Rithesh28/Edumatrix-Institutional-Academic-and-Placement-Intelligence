"""
EduMatrix Phase 4 — Step 4.3: RAG-Powered Student Study Buddy Chat Test Suite

Verifies:
1. Relevant question retrieves correct unit/topic and yields grounded answer with citations.
2. Weak or unrelated query receives an honest insufficient-evidence response.
3. Unpublished, draft, and rejected syllabus material cannot leak into student answers.
4. Cross-department material cannot leak; cross-department subject ID access is blocked with 403.
5. Citations strictly correspond to actual retrieved chunks and verified PostgreSQL records.
6. Placement Officer is forbidden from Study Buddy chat (HTTP 403).
7. Honest and safe fallback behavior when Qwen is offline or unavailable.
8. Concurrent generation inference synchronization between Study Buddy and AI Chat Analyzer.
9. Endpoint aliases (/chat and /ask) and input validation (empty query, nonexistent subject).
"""

import time
import unittest
import threading
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.core.config import settings
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
from app.services.embedding_service import embedding_service
from app.services.syllabus_ingestion_service import syllabus_ingestion_service
from app.services.syllabus_indexing_service import syllabus_indexing_service
from app.services.ai_generator_service import ai_generator
from app.main import app


class TestStudyBuddyStep43(unittest.TestCase):
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

        # Ensure dedicated collection exists
        syllabus_indexing_service.ensure_collection()

        # Record points count in files collection before tests
        cls.files_collection_points_before = 0
        try:
            info = qdrant_client.client.get_collection("files")
            cls.files_collection_points_before = info.points_count
        except Exception:
            pass

    @classmethod
    def tearDownClass(cls):
        # Clean test subjects and their Qdrant chunks
        if cls.created_subject_ids:
            docs = cls.db.query(SyllabusDocument).filter(
                SyllabusDocument.subject_id.in_(cls.created_subject_ids)
            ).all()
            for d in docs:
                syllabus_indexing_service.delete_document_chunks(d.id)

            cls.db.query(Subject).filter(Subject.id.in_(cls.created_subject_ids)).delete(synchronize_session=False)
            cls.db.commit()
        cls.db.close()

    def _create_test_subject(self, code_prefix: str, name: str, dept: str = "AIML") -> int:
        code = f"{code_prefix}{self.timestamp % 10000}"
        res = self.client.post(
            "/study-buddy/subjects",
            headers=self.admin_headers,
            json={"code": code, "name": name, "department": dept, "semester": 6}
        )
        self.assertEqual(res.status_code, 201)
        sub_id = res.json()["id"]
        self.created_subject_ids.append(sub_id)
        return sub_id

    def test_01_relevant_question_retrieves_correct_topic_and_citations(self):
        """
        Verify that a relevant question retrieves the correct unit and topic,
        yielding a grounded answer with citations containing document, unit, and page provenance.
        """
        sub_id = self._create_test_subject("REL", "Relational Database Management Systems", "AIML")

        content = (
            "Unit 1: Relational Query Languages\n"
            "Topic: Relational Calculus and Tuple Calculus\n"
            "Relational calculus is a non-procedural formal query language that uses mathematical logic.\n"
            "Tuple relational calculus expresses queries by defining predicates over tuples.\n"
        )
        up_res = self.client.post(
            f"/study-buddy/subjects/{sub_id}/syllabus",
            headers=self.hod_headers,
            files={"file": ("relational.txt", content.encode("utf-8"), "text/plain")}
        )
        self.assertEqual(up_res.status_code, 201)
        doc_id = up_res.json()["id"]

        # Approve and publish (triggers automatic indexing into study_buddy_chunks)
        self.client.post(f"/study-buddy/syllabi/{doc_id}/review", headers=self.hod_headers, json={"review_status": "APPROVED"})
        pub_res = self.client.post(f"/study-buddy/syllabi/{doc_id}/publish", headers=self.hod_headers, json={"is_published": True})
        self.assertEqual(pub_res.status_code, 200)

        # Ask question as AIML student
        chat_res = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={"question": "What is relational calculus and how does tuple calculus work?", "subject_id": sub_id}
        )
        self.assertEqual(chat_res.status_code, 200)
        data = chat_res.json()

        self.assertTrue(data["has_sufficient_evidence"])
        self.assertIn("answer", data)
        self.assertGreater(len(data["answer"]), 10)
        self.assertGreater(len(data["citations"]), 0)

        # Verify citation metadata
        first_citation = data["citations"][0]
        self.assertEqual(first_citation["subject_id"], sub_id)
        self.assertEqual(first_citation["document_id"], doc_id)
        self.assertGreaterEqual(first_citation["relevance_score"], settings.STUDY_BUDDY_MIN_RELEVANCE_SCORE)
        self.assertIsNotNone(first_citation["subject_code"])
        self.assertIsNotNone(first_citation["subject_name"])

    def test_02_weak_or_unrelated_query_insufficient_evidence_response(self):
        """
        Verify that a weak or completely off-topic query returns an honest insufficient-evidence response
        with has_sufficient_evidence=False and 0 citations.
        """
        sub_id = self._create_test_subject("OFF", "Compiler Construction", "AIML")
        content = "Unit 1: Lexical Analysis\nTopic: Tokenization\nLexical analyzers identify lexemes in code."
        up_res = self.client.post(
            f"/study-buddy/subjects/{sub_id}/syllabus",
            headers=self.hod_headers,
            files={"file": ("compiler.txt", content.encode("utf-8"), "text/plain")}
        )
        doc_id = up_res.json()["id"]
        self.client.post(f"/study-buddy/syllabi/{doc_id}/review", headers=self.hod_headers, json={"review_status": "APPROVED"})
        self.client.post(f"/study-buddy/syllabi/{doc_id}/publish", headers=self.hod_headers, json={"is_published": True})

        # Ask off-topic query about culinary recipes
        chat_res = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={"question": "How do you prepare Italian lasagna with béchamel sauce?", "subject_id": sub_id}
        )
        self.assertEqual(chat_res.status_code, 200)
        data = chat_res.json()

        self.assertFalse(data["has_sufficient_evidence"])
        self.assertEqual(len(data["citations"]), 0)
        self.assertIn("does not provide sufficient information", data["answer"].lower())
        self.assertEqual(data["model_used"], "syllabus_evidence_guard")

    def test_03_unpublished_and_rejected_syllabus_cannot_leak(self):
        """
        Verify that draft, rejected, or unpublished syllabi cannot leak into student answers.
        """
        sub_id = self._create_test_subject("DRF", "Quantum Neural Architectures", "AIML")
        secret_topic = "TopSecretQuantumGateSynthesis12345"
        content = f"Unit 1: Quantum Logic\nTopic: {secret_topic}\nExperimental proprietary quantum algorithms."

        # Ingest syllabus but DO NOT approve or publish
        up_res = self.client.post(
            f"/study-buddy/subjects/{sub_id}/syllabus",
            headers=self.hod_headers,
            files={"file": ("secret.txt", content.encode("utf-8"), "text/plain")}
        )
        doc_id = up_res.json()["id"]

        # Student searches for the secret topic
        chat_res = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={"question": f"Explain {secret_topic} in detail."}
        )
        self.assertEqual(chat_res.status_code, 200)
        data = chat_res.json()

        # Must not have leaked
        self.assertFalse(data["has_sufficient_evidence"])
        self.assertNotIn(secret_topic, data["answer"])
        self.assertEqual(len(data["citations"]), 0)

    def test_04_cross_department_material_cannot_leak(self):
        """
        Verify that students in department AIML cannot query or view syllabus content
        from department ECE, and client cannot spoof subject_id across departments.
        """
        # Create ECE subject
        ece_sub_id = self._create_test_subject("ECE", "Analog Integrated Circuits", "ECE")
        ece_content = (
            "Unit 1: Operational Amplifiers\n"
            "Topic: Slew Rate and Gain Bandwidth Product\n"
            "Slew rate defines the maximum rate of change of output voltage per unit of time in an op-amp.\n"
        )
        up_res = self.client.post(
            f"/study-buddy/subjects/{ece_sub_id}/syllabus",
            headers=self.admin_headers,
            files={"file": ("analog.txt", ece_content.encode("utf-8"), "text/plain")}
        )
        doc_id = up_res.json()["id"]
        self.client.post(f"/study-buddy/syllabi/{doc_id}/review", headers=self.admin_headers, json={"review_status": "APPROVED"})
        self.client.post(f"/study-buddy/syllabi/{doc_id}/publish", headers=self.admin_headers, json={"is_published": True})

        # 1. AIML student explicitly requests ECE subject_id -> 403 Forbidden
        spoofed_res = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={"question": "What is slew rate in operational amplifiers?", "subject_id": ece_sub_id}
        )
        self.assertEqual(spoofed_res.status_code, 403)
        self.assertIn("Access denied", spoofed_res.json()["detail"])

        # 2. AIML student asks general question without subject_id -> ECE content must NOT be retrieved
        general_res = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={"question": "What is slew rate in operational amplifiers?"}
        )
        self.assertEqual(general_res.status_code, 200)
        # Should be insufficient evidence because AIML department has no such approved syllabus
        self.assertFalse(general_res.json()["has_sufficient_evidence"])

        # 3. ECE student asking the same question receives valid grounded response
        ece_res = self.client.post(
            "/study-buddy/chat",
            headers=self.student_ece_headers,
            json={"question": "What is slew rate in operational amplifiers?", "subject_id": ece_sub_id}
        )
        self.assertEqual(ece_res.status_code, 200)
        self.assertTrue(ece_res.json()["has_sufficient_evidence"])
        self.assertGreater(len(ece_res.json()["citations"]), 0)
        self.assertEqual(ece_res.json()["citations"][0]["department"], "ECE")

    def test_05_citations_correspond_to_actual_retrieved_chunks(self):
        """
        Verify that every citation in the response corresponds to a verified PostgreSQL syllabus
        and subject, proving citations are not fabricated by model output.
        """
        sub_id = self._create_test_subject("CIT", "Database Concurrency Control", "AIML")
        content = (
            "Unit 2: Transaction Management\n"
            "Topic: Two-Phase Locking Protocol\n"
            "The two-phase locking protocol guarantees serializability by requiring transactions to obtain locks in a growing phase and release them in a shrinking phase.\n"
        )
        up_res = self.client.post(
            f"/study-buddy/subjects/{sub_id}/syllabus",
            headers=self.hod_headers,
            files={"file": ("concurrency.txt", content.encode("utf-8"), "text/plain")}
        )
        doc_id = up_res.json()["id"]
        self.client.post(f"/study-buddy/syllabi/{doc_id}/review", headers=self.hod_headers, json={"review_status": "APPROVED"})
        self.client.post(f"/study-buddy/syllabi/{doc_id}/publish", headers=self.hod_headers, json={"is_published": True})

        chat_res = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={"question": "Explain the growing and shrinking phases of two-phase locking.", "subject_id": sub_id}
        )
        self.assertEqual(chat_res.status_code, 200)
        citations = chat_res.json()["citations"]
        self.assertGreater(len(citations), 0)

        for cit in citations:
            # Check existence in PostgreSQL
            db_doc = self.db.query(SyllabusDocument).filter(SyllabusDocument.id == cit["document_id"]).first()
            self.assertIsNotNone(db_doc)
            self.assertEqual(db_doc.version, cit["version"])
            self.assertTrue(db_doc.is_published)
            self.assertEqual(db_doc.subject_id, cit["subject_id"])

            db_subj = self.db.query(Subject).filter(Subject.id == cit["subject_id"]).first()
            self.assertIsNotNone(db_subj)
            self.assertEqual(db_subj.code, cit["subject_code"])

    def test_06_placement_officer_forbidden_from_study_buddy_chat(self):
        """
        Verify that Placement Officer role is strictly forbidden from Study Buddy chat.
        """
        res = self.client.post(
            "/study-buddy/chat",
            headers=self.po_headers,
            json={"question": "What is the syllabus for AIML?"}
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("Placement Officers do not have", res.json()["detail"])

    def test_07_honest_safe_fallback_when_qwen_unavailable(self):
        """
        Verify that when Qwen model is unavailable or offline, the service falls back
        safely to deterministic grounded synthesis without crashing or fabricating facts.
        """
        sub_id = self._create_test_subject("FAL", "Distributed Systems Architecture", "AIML")
        content = (
            "Unit 1: Fundamentals of Distributed Systems\n"
            "Topic: CAP Theorem\n"
            "The CAP theorem states that a distributed data store can only simultaneously provide two out of three guarantees: Consistency, Availability, and Partition tolerance.\n"
        )
        up_res = self.client.post(
            f"/study-buddy/subjects/{sub_id}/syllabus",
            headers=self.hod_headers,
            files={"file": ("cap.txt", content.encode("utf-8"), "text/plain")}
        )
        doc_id = up_res.json()["id"]
        self.client.post(f"/study-buddy/syllabi/{doc_id}/review", headers=self.hod_headers, json={"review_status": "APPROVED"})
        self.client.post(f"/study-buddy/syllabi/{doc_id}/publish", headers=self.hod_headers, json={"is_published": True})

        # Temporarily simulate Qwen model unavailable
        original_ensure_model = ai_generator._ensure_model
        ai_generator._ensure_model = lambda: False

        try:
            chat_res = self.client.post(
                "/study-buddy/chat",
                headers=self.student_aiml_headers,
                json={"question": "What does the CAP theorem state regarding consistency and partition tolerance?", "subject_id": sub_id}
            )
            self.assertEqual(chat_res.status_code, 200)
            data = chat_res.json()
            self.assertTrue(data["has_sufficient_evidence"])
            self.assertEqual(data["model_used"], "deterministic_syllabus_synthesizer")
            self.assertIn("According to the approved syllabus", data["answer"])
            self.assertIn("CAP theorem", data["answer"])
            self.assertGreater(len(data["citations"]), 0)
        finally:
            ai_generator._ensure_model = original_ensure_model

    def test_08_concurrent_generation_synchronization(self):
        """
        Verify that concurrent inference calls through the shared QwenGenerator singleton
        use the inference lock safely without crashing, race conditions, or output corruption.
        """
        sources = [
            {
                "subject_code": "CS101",
                "subject_name": "Intro to Computing",
                "unit_number": 1,
                "unit_title": "Binary Systems",
                "topic_title": "Boolean Algebra",
                "text": "Boolean algebra deals with binary variables and logic gates.",
                "has_verified_text": True,
                "title": "Intro to Computing Syllabus"
            }
        ]

        def call_study_buddy():
            return ai_generator.generate_study_buddy_answer(
                query="What is Boolean algebra?",
                context_str="Passage: Boolean algebra deals with binary variables and logic gates.",
                sources=sources
            )

        def call_chat_analyzer():
            return ai_generator.generate_grounded_answer(
                query="What is the Boolean algebra assignment?",
                sources=sources,
                intent="assignment_query"
            )

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(call_study_buddy),
                executor.submit(call_chat_analyzer),
                executor.submit(call_study_buddy),
                executor.submit(call_chat_analyzer)
            ]
            results = [f.result() for f in futures]

        self.assertEqual(len(results), 4)
        for r in results:
            self.assertIn("answer", r)
            self.assertGreater(len(r["answer"]), 5)

    def test_09_alias_endpoint_and_validation(self):
        """
        Verify that /study-buddy/ask functions as an alias to /study-buddy/chat,
        and verify input validations (empty string, nonexistent subject_id).
        """
        # 1. Alias /ask
        alias_res = self.client.post(
            "/study-buddy/ask",
            headers=self.student_aiml_headers,
            json={"question": "What is machine learning?"}
        )
        self.assertEqual(alias_res.status_code, 200)

        # 2. Empty question -> 422 Unprocessable Entity (min_length=2)
        empty_res = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={"question": ""}
        )
        self.assertEqual(empty_res.status_code, 422)

        # 3. Nonexistent subject_id -> 404 Not Found
        not_found_res = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={"question": "What is neural network architecture?", "subject_id": 999999}
        )
        self.assertEqual(not_found_res.status_code, 404)
        self.assertIn("not found or inactive", not_found_res.json()["detail"])

    def test_10_superseded_syllabus_versions_cannot_be_retrieved_or_cited(self):
        """
        Case 1: Verify that when a newer version (v2) of a syllabus is published,
        older versions (v1) are automatically unpublished and cannot be retrieved or cited.
        """
        sub_id = self._create_test_subject("SUP", "Graph Algorithms and Optimization", "AIML")

        # Ingest and publish Version 1
        v1_content = (
            "Unit 1: Classical Graph Theory\n"
            "Topic: Euler Tours and Fleury Algorithm\n"
            "Euler tour visits every edge of a graph exactly once using Fleury algorithm.\n"
        )
        v1_up = self.client.post(
            f"/study-buddy/subjects/{sub_id}/syllabus",
            headers=self.hod_headers,
            files={"file": ("v1.txt", v1_content.encode("utf-8"), "text/plain")}
        )
        self.assertEqual(v1_up.status_code, 201)
        v1_doc_id = v1_up.json()["id"]
        self.client.post(f"/study-buddy/syllabi/{v1_doc_id}/review", headers=self.hod_headers, json={"review_status": "APPROVED"})
        v1_pub = self.client.post(f"/study-buddy/syllabi/{v1_doc_id}/publish", headers=self.hod_headers, json={"is_published": True})
        self.assertEqual(v1_pub.status_code, 200)

        # Ingest and publish Version 2 (superseding Version 1)
        v2_content = (
            "Unit 1: Modern Spectral Graph Theory\n"
            "Topic: Graph Laplacians and Cheeger Inequality\n"
            "Graph Laplacians define diffusion dynamics on discrete Riemannian manifolds.\n"
        )
        v2_up = self.client.post(
            f"/study-buddy/subjects/{sub_id}/syllabus",
            headers=self.hod_headers,
            files={"file": ("v2.txt", v2_content.encode("utf-8"), "text/plain")}
        )
        self.assertEqual(v2_up.status_code, 201)
        v2_doc_id = v2_up.json()["id"]
        self.client.post(f"/study-buddy/syllabi/{v2_doc_id}/review", headers=self.hod_headers, json={"review_status": "APPROVED"})
        v2_pub = self.client.post(f"/study-buddy/syllabi/{v2_doc_id}/publish", headers=self.hod_headers, json={"is_published": True})
        self.assertEqual(v2_pub.status_code, 200)

        # Verify PostgreSQL state: v1 is now un-published, v2 is published
        self.db.expire_all()
        v1_doc = self.db.query(SyllabusDocument).filter(SyllabusDocument.id == v1_doc_id).first()
        v2_doc = self.db.query(SyllabusDocument).filter(SyllabusDocument.id == v2_doc_id).first()
        self.assertFalse(v1_doc.is_published)
        self.assertTrue(v2_doc.is_published)

        # Query exclusive v1 concept: must NOT be cited or retrieved
        chat_v1 = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={"question": "What is Fleury algorithm for Euler tours?", "subject_id": sub_id}
        )
        self.assertEqual(chat_v1.status_code, 200)
        # Cannot retrieve v1
        self.assertFalse(chat_v1.json()["has_sufficient_evidence"])
        self.assertEqual(len(chat_v1.json()["citations"]), 0)

        # Query exclusive v2 concept: succeeds and cites v2
        chat_v2 = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={"question": "What are Graph Laplacians and Cheeger inequality?", "subject_id": sub_id}
        )
        self.assertEqual(chat_v2.status_code, 200)
        self.assertTrue(chat_v2.json()["has_sufficient_evidence"])
        self.assertGreater(len(chat_v2.json()["citations"]), 0)
        for cit in chat_v2.json()["citations"]:
            self.assertEqual(cit["document_id"], v2_doc_id)
            self.assertEqual(cit["version"], 2)

    def test_11_inactive_subjects_cannot_contribute_chunks_to_student_answers(self):
        """
        Case 2: Verify that deactivated subjects cannot contribute syllabus chunks
        to student answers, either with explicit subject_id or general department queries.
        """
        sub_id = self._create_test_subject("INA", "Heuristic Optimization Systems", "AIML")
        content = (
            "Unit 1: Metaheuristic Search\n"
            "Topic: Simulated Annealing Cooling Protocols\n"
            "Simulated annealing cooling protocols systematically lower temperature parameters to escape sub-optimal local traps.\n"
        )
        up_res = self.client.post(
            f"/study-buddy/subjects/{sub_id}/syllabus",
            headers=self.hod_headers,
            files={"file": ("anneal.txt", content.encode("utf-8"), "text/plain")}
        )
        doc_id = up_res.json()["id"]
        self.client.post(f"/study-buddy/syllabi/{doc_id}/review", headers=self.hod_headers, json={"review_status": "APPROVED"})
        self.client.post(f"/study-buddy/syllabi/{doc_id}/publish", headers=self.hod_headers, json={"is_published": True})

        # When active: general student query retrieves chunks
        chat_active = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={"question": "Explain simulated annealing cooling protocols and local traps."}
        )
        self.assertEqual(chat_active.status_code, 200)
        self.assertTrue(chat_active.json()["has_sufficient_evidence"])

        # Deactivate subject
        deact_res = self.client.put(
            f"/study-buddy/subjects/{sub_id}",
            headers=self.hod_headers,
            json={"is_active": False}
        )
        self.assertEqual(deact_res.status_code, 200)
        self.assertFalse(deact_res.json()["is_active"])

        # 1. Direct query with deactivated subject_id -> 404
        direct_res = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={"question": "Explain simulated annealing cooling protocols.", "subject_id": sub_id}
        )
        self.assertEqual(direct_res.status_code, 404)
        self.assertIn("not found or inactive", direct_res.json()["detail"])

        # 2. General department query without subject_id -> must NOT retrieve inactive subject chunks
        gen_res = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={"question": "Explain simulated annealing cooling protocols and local traps."}
        )
        self.assertEqual(gen_res.status_code, 200)
        self.assertFalse(gen_res.json()["has_sufficient_evidence"])
        self.assertEqual(len(gen_res.json()["citations"]), 0)

        # Reactivate subject
        react_res = self.client.put(
            f"/study-buddy/subjects/{sub_id}",
            headers=self.hod_headers,
            json={"is_active": True}
        )
        self.assertEqual(react_res.status_code, 200)
        self.assertTrue(react_res.json()["is_active"])

        # Chunks re-indexed on reactivation, student query succeeds again
        chat_react = self.client.post(
            "/study-buddy/chat",
            headers=self.student_aiml_headers,
            json={"question": "Explain simulated annealing cooling protocols.", "subject_id": sub_id}
        )
        self.assertEqual(chat_react.status_code, 200)
        self.assertTrue(chat_react.json()["has_sufficient_evidence"])

    def test_12_role_based_access_rules_lecturer_hod_admin(self):
        """
        Case 4: Verify role-based authorization rules for Lecturer, HOD, and Admin.
        - Admin has institutional access and can query any department subject.
        - HOD is scoped to their department and blocked from other departments.
        - Lecturer is scoped to their department or assigned subjects.
        """
        # Create ECE subject
        ece_sub_id = self._create_test_subject("MIC", "Microcontroller System Design", "ECE")
        content = (
            "Unit 1: Computer Architecture\n"
            "Topic: Harvard vs Von Neumann Architectures\n"
            "Harvard architecture provides physically separate storage and signal buses for instructions and data.\n"
        )
        up_res = self.client.post(
            f"/study-buddy/subjects/{ece_sub_id}/syllabus",
            headers=self.admin_headers,
            files={"file": ("micro.txt", content.encode("utf-8"), "text/plain")}
        )
        doc_id = up_res.json()["id"]
        self.client.post(f"/study-buddy/syllabi/{doc_id}/review", headers=self.admin_headers, json={"review_status": "APPROVED"})
        self.client.post(f"/study-buddy/syllabi/{doc_id}/publish", headers=self.admin_headers, json={"is_published": True})

        # 1. Admin can query ECE subject without restriction
        admin_res = self.client.post(
            "/study-buddy/chat",
            headers=self.admin_headers,
            json={"question": "What is Harvard architecture with separate storage?", "subject_id": ece_sub_id}
        )
        self.assertEqual(admin_res.status_code, 200)
        self.assertTrue(admin_res.json()["has_sufficient_evidence"])
        self.assertEqual(admin_res.json()["citations"][0]["department"], "ECE")

        # 2. AIML HOD cannot query ECE subject -> 403 Forbidden
        hod_res = self.client.post(
            "/study-buddy/chat",
            headers=self.hod_headers,
            json={"question": "What is Harvard architecture?", "subject_id": ece_sub_id}
        )
        self.assertEqual(hod_res.status_code, 403)
        self.assertIn("Access denied", hod_res.json()["detail"])

        # 3. AIML Lecturer cannot query unassigned ECE subject -> 403 Forbidden
        lec_res = self.client.post(
            "/study-buddy/chat",
            headers=self.lecturer_headers,
            json={"question": "What is Harvard architecture?", "subject_id": ece_sub_id}
        )
        self.assertEqual(lec_res.status_code, 403)
        self.assertIn("Access denied", lec_res.json()["detail"])

        # 4. Lecturer cannot publish syllabus -> 403 Forbidden
        lec_pub = self.client.post(
            f"/study-buddy/syllabi/{doc_id}/publish",
            headers=self.lecturer_headers,
            json={"is_published": True}
        )
        self.assertEqual(lec_pub.status_code, 403)


if __name__ == "__main__":
    unittest.main()

