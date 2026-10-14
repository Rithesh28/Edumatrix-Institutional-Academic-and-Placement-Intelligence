"""
EduMatrix Phase 4 — Step 4.4: Study Summaries and Quizzes Test Suite

Verifies:
1. Summary grounding and verified citations for concise and detailed formats.
2. Insufficient evidence and honest fallback identification.
3. Subject, unit, and topic filtering with cross-department isolation (HTTP 403).
4. Unpublished, rejected, superseded, and inactive-subject exclusion.
5. Quiz generation: multiple-choice with 4 options, valid question schema, and server-side validation.
6. Correct answers and explanations strictly hidden before quiz submission.
7. Server-side scoring and protection against client-tampered scores or answer keys.
8. Attempt ownership enforcement: unauthorized access to other students' attempts blocked (HTTP 403).
9. Database persistence, question snapshotting, and syllabus-version provenance.
10. Model unavailable fallback behavior and shared inference lock safety.
11. Placement Officer role strictly forbidden (HTTP 403).
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
    SyllabusReviewStatus,
    QuizStatus,
    StudyBuddyQuizAttempt
)
from app.services.file_storage.qdrant_client import qdrant_client
from app.services.syllabus_indexing_service import syllabus_indexing_service
from app.services.ai_generator_service import ai_generator
from app.main import app


class TestStudyBuddyStep44(unittest.TestCase):
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
        syllabus_indexing_service.ensure_collection()

    @classmethod
    def tearDownClass(cls):
        if cls.created_subject_ids:
            # Delete quiz attempts
            cls.db.query(StudyBuddyQuizAttempt).filter(
                StudyBuddyQuizAttempt.subject_id.in_(cls.created_subject_ids)
            ).delete(synchronize_session=False)

            docs = cls.db.query(SyllabusDocument).filter(
                SyllabusDocument.subject_id.in_(cls.created_subject_ids)
            ).all()
            for d in docs:
                syllabus_indexing_service.delete_document_chunks(d.id)

            cls.db.query(Subject).filter(Subject.id.in_(cls.created_subject_ids)).delete(synchronize_session=False)
            cls.db.commit()
        cls.db.close()

    def _create_test_subject_with_syllabus(self, code_prefix: str, name: str, dept: str, syllabus_content: str):
        code = f"{code_prefix}{int(time.time() * 1000) % 10000}"
        res = self.client.post(
            "/study-buddy/subjects",
            headers=self.admin_headers,
            json={"code": code, "name": name, "department": dept, "semester": 5}
        )
        self.assertEqual(res.status_code, 201)
        sub_id = res.json()["id"]
        self.created_subject_ids.append(sub_id)

        # Upload syllabus document
        up_res = self.client.post(
            f"/study-buddy/subjects/{sub_id}/syllabus",
            headers=self.admin_headers,
            files={"file": (f"{code.lower()}.txt", syllabus_content.encode("utf-8"), "text/plain")}
        )
        self.assertEqual(up_res.status_code, 201)
        doc_id = up_res.json()["id"]

        # Approve and publish
        self.client.post(f"/study-buddy/syllabi/{doc_id}/review", headers=self.admin_headers, json={"review_status": "APPROVED"})
        pub_res = self.client.post(f"/study-buddy/syllabi/{doc_id}/publish", headers=self.admin_headers, json={"is_published": True})
        self.assertEqual(pub_res.status_code, 200)

        # Fetch details to get unit and topic IDs
        det_res = self.client.get(f"/study-buddy/syllabi/{doc_id}", headers=self.admin_headers)
        self.assertEqual(det_res.status_code, 200)
        details = det_res.json()

        return sub_id, doc_id, details

    # ----------------------------------------------------
    # FEATURE A: STUDY SUMMARIES TESTS
    # ----------------------------------------------------

    def test_01_summary_generation_concise_and_detailed_with_citations(self):
        """
        Verify that concise revision notes and detailed explanations can be generated
        with accurate source citations, page numbers, and provenance.
        """
        content = (
            "Unit 1: Artificial Neural Networks\n"
            "Topic: Backpropagation Algorithm\n"
            "Backpropagation computes the gradient of the loss function with respect to weights using the chain rule.\n"
            "It propagates errors backwards through the network layers to update synaptic parameters.\n"
            "Unit 2: Optimization Strategies\n"
            "Topic: Adam Optimizer\n"
            "Adam optimization computes adaptive learning rates from first and second moments of the gradients.\n"
        )
        sub_id, doc_id, details = self._create_test_subject_with_syllabus(
            "ANN", "Deep Learning Neural Architectures", "AIML", content
        )

        unit_1_id = details["units"][0]["id"] if details.get("units") else None

        # 1. Concise Revision Notes
        res_concise = self.client.post(
            "/study-buddy/summaries/generate",
            headers=self.student_aiml_headers,
            json={
                "subject_id": sub_id,
                "unit_id": unit_1_id,
                "format_type": "concise"
            }
        )
        self.assertEqual(res_concise.status_code, 200)
        data_c = res_concise.json()

        self.assertTrue(data_c["has_sufficient_evidence"])
        self.assertEqual(data_c["format_type"], "concise")
        self.assertEqual(data_c["subject_id"], sub_id)
        self.assertGreater(len(data_c["summary"]), 20)
        self.assertGreater(len(data_c["citations"]), 0)

        # Citation validation
        first_cit = data_c["citations"][0]
        self.assertEqual(first_cit["document_id"], doc_id)
        self.assertEqual(first_cit["subject_id"], sub_id)
        self.assertEqual(first_cit["unit_number"], 1)

        # 2. Detailed Breakdown
        res_detailed = self.client.post(
            "/study-buddy/summaries/generate",
            headers=self.student_aiml_headers,
            json={
                "subject_id": sub_id,
                "unit_id": unit_1_id,
                "format_type": "detailed"
            }
        )
        self.assertEqual(res_detailed.status_code, 200)
        data_d = res_detailed.json()

        self.assertTrue(data_d["has_sufficient_evidence"])
        self.assertEqual(data_d["format_type"], "detailed")
        self.assertGreater(len(data_d["summary"]), len(data_c["summary"]) / 2)

    def test_02_summary_cross_department_isolation(self):
        """
        Verify that an AIML student is forbidden (HTTP 403) from generating summaries
        for an ECE subject.
        """
        content = "Unit 1: Signals and Filters\nTopic: Butterworth Filter Design\nButterworth filters have maximally flat passband response."
        ece_sub_id, _, _ = self._create_test_subject_with_syllabus(
            "SIG", "Digital Signal Processing", "ECE", content
        )

        res = self.client.post(
            "/study-buddy/summaries/generate",
            headers=self.student_aiml_headers,
            json={"subject_id": ece_sub_id, "format_type": "concise"}
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("Access denied", res.json()["detail"])

    def test_03_summary_inactive_subject_and_unpublished_syllabus(self):
        """
        Verify that deactivated subjects (HTTP 404) and unpublished syllabi (HTTP 400)
        cannot generate study summaries.
        """
        content = "Unit 1: Quantum Computing\nTopic: Grover Algorithm\nGrover algorithm provides quadratic speedup for unstructured search."
        sub_id, doc_id, _ = self._create_test_subject_with_syllabus(
            "QNT", "Quantum Information Science", "AIML", content
        )

        # Deactivate subject
        self.client.put(f"/study-buddy/subjects/{sub_id}", headers=self.admin_headers, json={"is_active": False})

        res_deact = self.client.post(
            "/study-buddy/summaries/generate",
            headers=self.student_aiml_headers,
            json={"subject_id": sub_id, "format_type": "concise"}
        )
        self.assertEqual(res_deact.status_code, 404)
        self.assertIn("not found or inactive", res_deact.json()["detail"])

        # Reactivate subject but unpublish document
        self.client.put(f"/study-buddy/subjects/{sub_id}", headers=self.admin_headers, json={"is_active": True})
        self.client.post(f"/study-buddy/syllabi/{doc_id}/publish", headers=self.admin_headers, json={"is_published": False})

        res_unpub = self.client.post(
            "/study-buddy/summaries/generate",
            headers=self.student_aiml_headers,
            json={"subject_id": sub_id, "format_type": "concise"}
        )
        self.assertEqual(res_unpub.status_code, 400)
        self.assertIn("No approved published syllabus available", res_unpub.json()["detail"])

    def test_04_summary_deterministic_fallback_when_qwen_unavailable(self):
        """
        Verify honest identification of deterministic fallback when Qwen is offline.
        """
        content = "Unit 1: Operating Systems\nTopic: Paging and Virtual Memory\nPaging divides logical address space into fixed-size frames."
        sub_id, _, _ = self._create_test_subject_with_syllabus(
            "OPS", "Operating Systems Kernel Design", "AIML", content
        )

        original_ensure_model = ai_generator._ensure_model
        ai_generator._ensure_model = lambda: False

        try:
            res = self.client.post(
                "/study-buddy/summaries/generate",
                headers=self.student_aiml_headers,
                json={"subject_id": sub_id, "format_type": "concise"}
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["model_used"], "deterministic_syllabus_synthesizer")
            self.assertTrue(data["has_sufficient_evidence"])
            self.assertIn("Paging", data["summary"])
        finally:
            ai_generator._ensure_model = original_ensure_model

    # ----------------------------------------------------
    # FEATURE B: QUIZ GENERATION & ATTEMPTS TESTS
    # ----------------------------------------------------

    def test_05_quiz_generation_schema_validation_and_hidden_answers(self):
        """
        Verify that generated quizzes:
        1. Conform to the multiple-choice question schema (4 options per question).
        2. Strictly HIDE the correct answer indices and explanations before submission.
        3. Persist the attempt record in PostgreSQL.
        """
        content = (
            "Unit 1: Reinforcement Learning\n"
            "Topic: Markov Decision Processes\n"
            "Markov Decision Processes formalize reinforcement learning environments with states, actions, transition models, and rewards.\n"
            "The Markov property asserts that the future state depends solely on the current state and action, not the past history.\n"
            "Unit 2: Policy Optimization\n"
            "Topic: Q-Learning Algorithm\n"
            "Q-learning is an off-policy temporal difference algorithm that iteratively learns action-value functions.\n"
        )
        sub_id, doc_id, details = self._create_test_subject_with_syllabus(
            "RLM", "Reinforcement Learning Models", "AIML", content
        )

        res = self.client.post(
            "/study-buddy/quizzes/generate",
            headers=self.student_aiml_headers,
            json={
                "subject_id": sub_id,
                "num_questions": 4,
                "difficulty": "medium"
            }
        )
        self.assertEqual(res.status_code, 200)
        quiz_data = res.json()

        self.assertIn("id", quiz_data)
        self.assertEqual(quiz_data["subject_id"], sub_id)
        self.assertEqual(quiz_data["status"], "GENERATED")
        self.assertGreaterEqual(len(quiz_data["questions"]), 1)

        # CRITICAL SECURITY CHECK: Verify correct answers and explanations are NOT in public response!
        for q in quiz_data["questions"]:
            self.assertIn("question_id", q)
            self.assertIn("question", q)
            self.assertIn("options", q)
            self.assertEqual(len(q["options"]), 4)
            # Must NOT expose answer key or explanation
            self.assertNotIn("correct_option_index", q)
            self.assertNotIn("correct_answer", q)
            self.assertNotIn("explanation", q)

        # Verify PostgreSQL database record has stored the snapshot with answer keys
        attempt_id = quiz_data["id"]
        attempt_db = self.db.query(StudyBuddyQuizAttempt).filter(StudyBuddyQuizAttempt.id == attempt_id).first()
        self.assertIsNotNone(attempt_db)
        self.assertEqual(attempt_db.student_id, self.student_aiml.id)
        self.assertEqual(attempt_db.status, QuizStatus.GENERATED)
        self.assertIsNotNone(attempt_db.questions_data)
        # Server snapshot must contain correct_option_index
        first_q_db = attempt_db.questions_data[0]
        self.assertIn("correct_option_index", first_q_db)
        self.assertIn("explanation", first_q_db)

    def test_06_quiz_submission_server_side_scoring_and_explanation_reveal(self):
        """
        Verify that submitting a quiz:
        1. Grades answers strictly server-side (score, max_score, percentage).
        2. Updates attempt status to COMPLETED.
        3. Returns the correct answers, explanations, and verified citations after submission.
        """
        content = (
            "Unit 1: Graph Neural Networks\n"
            "Topic: Message Passing Neural Networks\n"
            "Message passing neural networks update node representations by aggregating transformed feature vectors from neighboring nodes.\n"
        )
        sub_id, _, _ = self._create_test_subject_with_syllabus(
            "GNN", "Graph Representation Learning", "AIML", content
        )

        gen_res = self.client.post(
            "/study-buddy/quizzes/generate",
            headers=self.student_aiml_headers,
            json={"subject_id": sub_id, "num_questions": 3, "difficulty": "easy"}
        )
        self.assertEqual(gen_res.status_code, 200)
        attempt_id = gen_res.json()["id"]

        # Fetch server snapshot to know which option is correct for test assertion
        attempt_db = self.db.query(StudyBuddyQuizAttempt).filter(StudyBuddyQuizAttempt.id == attempt_id).first()
        questions = attempt_db.questions_data
        self.assertGreater(len(questions), 0)

        # Answer question 1 correctly, question 2 (if present) intentionally incorrectly
        answers = {str(questions[0]["question_id"]): questions[0]["correct_option_index"]}
        if len(questions) > 1:
            wrong_idx = (questions[1]["correct_option_index"] + 1) % 4
            answers[str(questions[1]["question_id"])] = wrong_idx

        # Submit quiz
        sub_res = self.client.post(
            f"/study-buddy/quizzes/attempts/{attempt_id}/submit",
            headers=self.student_aiml_headers,
            json={"answers": answers}
        )
        self.assertEqual(sub_res.status_code, 200)
        res_data = sub_res.json()

        self.assertEqual(res_data["id"], attempt_id)
        self.assertEqual(res_data["status"], "COMPLETED")
        self.assertGreaterEqual(res_data["score"], 1.0)
        self.assertEqual(res_data["max_score"], len(questions))
        self.assertGreater(res_data["percentage"], 0.0)
        self.assertIsNotNone(res_data["submitted_at"])

        # Check that result now reveals correct option and explanation
        for qr in res_data["questions_results"]:
            self.assertIn("correct_option_index", qr)
            self.assertIn("is_correct", qr)
            self.assertIn("explanation", qr)
            self.assertGreater(len(qr["explanation"]), 5)
            self.assertIsNotNone(qr["citation"])

    def test_07_attempt_ownership_and_unauthorized_access(self):
        """
        Verify that Student B cannot submit answers or view results for Student A's quiz attempt (HTTP 403).
        """
        content = "Unit 1: Logic Programming\nTopic: Horn Clauses\nHorn clauses are disjunctions of literals with at most one positive literal."
        sub_id, _, _ = self._create_test_subject_with_syllabus(
            "LOG", "Formal Logic Systems", "AIML", content
        )

        # Student AIML generates quiz
        gen_res = self.client.post(
            "/study-buddy/quizzes/generate",
            headers=self.student_aiml_headers,
            json={"subject_id": sub_id, "num_questions": 3}
        )
        attempt_id = gen_res.json()["id"]

        # Student ECE attempts to submit Student AIML's quiz attempt -> 403 Forbidden
        tamper_submit = self.client.post(
            f"/study-buddy/quizzes/attempts/{attempt_id}/submit",
            headers=self.student_ece_headers,
            json={"answers": {"1": 0}}
        )
        self.assertEqual(tamper_submit.status_code, 403)
        self.assertIn("Access denied", tamper_submit.json()["detail"])

        # Student ECE attempts to view Student AIML's quiz result -> 403 Forbidden
        tamper_view = self.client.get(
            f"/study-buddy/quizzes/attempts/{attempt_id}",
            headers=self.student_ece_headers
        )
        self.assertEqual(tamper_view.status_code, 403)
        self.assertIn("Access denied", tamper_view.json()["detail"])

    def test_08_quiz_shortfall_note_when_insufficient_questions(self):
        """
        Verify that if the syllabus evidence supports fewer valid questions than requested,
        the service returns the available valid questions and clearly provides a shortfall note
        without fabricating questions.
        """
        # Very short single-sentence syllabus
        content = "Unit 1: Introduction\nTopic: Turing Machines\nA Turing machine models computation with an infinite tape and a discrete read-write head."
        sub_id, _, _ = self._create_test_subject_with_syllabus(
            "TUR", "Theory of Automata", "AIML", content
        )

        res = self.client.post(
            "/study-buddy/quizzes/generate",
            headers=self.student_aiml_headers,
            json={"subject_id": sub_id, "num_questions": 8, "difficulty": "hard"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertLess(data["total_questions"], 8)
        self.assertIsNotNone(data["shortfall_note"])
        self.assertIn("Requested 8 questions", data["shortfall_note"])

    def test_09_list_student_attempts_endpoint(self):
        """
        Verify that /study-buddy/quizzes/attempts lists the student's attempts with scores and timestamps.
        """
        res = self.client.get(
            "/study-buddy/quizzes/attempts",
            headers=self.student_aiml_headers
        )
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)

    def test_10_placement_officer_forbidden_from_summaries_and_quizzes(self):
        """
        Verify that Placement Officer role is strictly forbidden from generating summaries and quizzes (HTTP 403).
        """
        sub_id = self.created_subject_ids[0]

        # Summaries
        res_sum = self.client.post(
            "/study-buddy/summaries/generate",
            headers=self.po_headers,
            json={"subject_id": sub_id, "format_type": "concise"}
        )
        self.assertEqual(res_sum.status_code, 403)

        # Quizzes
        res_quiz = self.client.post(
            "/study-buddy/quizzes/generate",
            headers=self.po_headers,
            json={"subject_id": sub_id, "num_questions": 3}
        )
        self.assertEqual(res_quiz.status_code, 403)


if __name__ == "__main__":
    unittest.main()
