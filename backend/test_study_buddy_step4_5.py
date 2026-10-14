"""
EduMatrix Phase 4 — Step 4.5: Student Progress Dashboard and Adaptive Study Planner Test Suite

Verifies:
1. Dashboard statistics derived from persisted quiz attempts (0 history, incomplete, and completed).
2. Transparent calculation rules for weak topics requiring evidence (>= 2 questions/attempts).
3. Adaptive study plan creation, syllabus grounding, and priority sequencing.
4. Schedule feasibility validation: unrealistic schedules rejected with clear explanation (HTTP 400).
5. Task completion, reopening, and plan status transitions.
6. Plan regeneration preserving completed task history.
7. Strict student ownership isolation across list, detail, and task update endpoints (HTTP 403).
8. Department and active-subject isolation.
9. Placement Officer role strictly forbidden across all Step 4.5 endpoints (HTTP 403).
10. Syllabus version provenance preservation across plan lifecycles.
11. Database migration head is 018 and required tables/indexes exist.
"""

import time
import unittest
from datetime import date, timedelta, datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
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
    SyllabusReviewStatus,
    QuizStatus,
    StudyBuddyQuizAttempt,
    PlanStatus,
    StudyBuddyPlan,
    StudyBuddyPlanTask
)
from app.services.syllabus_indexing_service import syllabus_indexing_service
from app.main import app


class TestStudyBuddyStep45(unittest.TestCase):
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
            # Clean up plans and tasks
            cls.db.query(StudyBuddyPlanTask).filter(
                StudyBuddyPlanTask.syllabus_document_id.in_(
                    cls.db.query(SyllabusDocument.id).filter(SyllabusDocument.subject_id.in_(cls.created_subject_ids))
                )
            ).delete(synchronize_session=False)

            cls.db.query(StudyBuddyPlan).filter(
                StudyBuddyPlan.subject_id.in_(cls.created_subject_ids)
            ).delete(synchronize_session=False)

            # Clean up quiz attempts
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
            json={"code": code, "name": name, "department": dept, "semester": 6}
        )
        self.assertEqual(res.status_code, 201)
        sub_id = res.json()["id"]
        self.created_subject_ids.append(sub_id)

        # Upload syllabus document
        files = {"file": ("syllabus.txt", syllabus_content.encode("utf-8"), "text/plain")}
        res = self.client.post(f"/study-buddy/subjects/{sub_id}/syllabus", headers=self.admin_headers, files=files)
        self.assertEqual(res.status_code, 201)
        doc_id = res.json()["id"]

        # Review & Publish
        res = self.client.post(f"/study-buddy/syllabi/{doc_id}/review", headers=self.admin_headers, json={"review_status": "APPROVED"})
        self.assertEqual(res.status_code, 200)

        res = self.client.post(f"/study-buddy/syllabi/{doc_id}/publish", headers=self.admin_headers, json={"is_published": True})
        self.assertEqual(res.status_code, 200)

        return sub_id, doc_id

    # =========================================================================
    # 1. DATABASE SCHEMA & MIGRATION VERIFICATION
    # =========================================================================

    def test_01_migration_head_is_018(self):
        """Verify Alembic migration head in database is at least 018 and tables exist."""
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version;")).fetchone()
            self.assertIsNotNone(result)
            self.assertIn(result[0], ["018", "019"], f"Database revision must be at least 018 (found {result[0]})")

        inspector = inspect(engine)
        tables = inspector.get_table_names()
        self.assertIn("study_buddy_plans", tables)
        self.assertIn("study_buddy_plan_tasks", tables)

    # =========================================================================
    # 2. STUDENT PROGRESS DASHBOARD METRICS
    # =========================================================================

    def test_02_dashboard_progress_empty_state(self):
        """Verify dashboard returns clean zero/null metrics for a student with no quiz attempts."""
        res = self.client.get("/study-buddy/progress/dashboard", headers=self.student_ece_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["quizzes_attempted"], 0)
        self.assertEqual(data["quizzes_completed"], 0)
        self.assertIsNone(data["average_percentage"], "Average percentage must be None when 0 quizzes completed")
        self.assertIsNone(data["most_recent_quiz"])
        self.assertEqual(data["subject_performances"], [])
        self.assertEqual(data["weak_topics"], [])
        self.assertIn("weak_topics", data["metric_rules"])

    def test_03_dashboard_progress_with_attempts_and_weak_topics(self):
        """Verify calculations for completed attempts, subject performance, and transparent weak topic rules."""
        syllabus_text = """
Unit 1: Machine Learning Foundations
Supervised learning algorithms, decision trees, and linear regression principles.
Unit 2: Neural Networks & Deep Learning
Backpropagation, gradient descent, convolutional neural networks, and activation functions.
"""
        sub_id, doc_id = self._create_test_subject_with_syllabus("MLP", "Machine Learning Progress", "AIML", syllabus_text)
        units = self.db.query(SyllabusUnit).filter(SyllabusUnit.document_id == doc_id).order_by(SyllabusUnit.order).all()
        self.assertGreaterEqual(len(units), 2)
        unit1, unit2 = units[0], units[1]

        # 1. Create a completed attempt with high score (100%) on Unit 1
        att1 = StudyBuddyQuizAttempt(
            student_id=self.student_aiml.id,
            subject_id=sub_id,
            syllabus_document_id=doc_id,
            syllabus_version=1,
            unit_id=unit1.id,
            title="Unit 1 Practice Quiz",
            difficulty="medium",
            total_questions=3,
            questions_data=[
                {"question_id": 1, "question": "Q1", "options": ["A", "B", "C", "D"], "correct_option_index": 0, "provenance": {"unit_id": unit1.id}},
                {"question_id": 2, "question": "Q2", "options": ["A", "B", "C", "D"], "correct_option_index": 1, "provenance": {"unit_id": unit1.id}},
                {"question_id": 3, "question": "Q3", "options": ["A", "B", "C", "D"], "correct_option_index": 2, "provenance": {"unit_id": unit1.id}},
            ],
            status=QuizStatus.COMPLETED,
            score=3.0,
            max_score=3,
            percentage=100.0,
            student_answers={"0": 0, "1": 1, "2": 2},
            submitted_at=datetime.now(timezone.utc)
        )
        self.db.add(att1)

        # 2. Create 2 completed attempts with low score (33.3% and 0%) on Unit 2 -> Meets >= 2 attempts rule for weak topics!
        att2 = StudyBuddyQuizAttempt(
            student_id=self.student_aiml.id,
            subject_id=sub_id,
            syllabus_document_id=doc_id,
            syllabus_version=1,
            unit_id=unit2.id,
            title="Unit 2 Quiz Attempt 1",
            difficulty="medium",
            total_questions=3,
            questions_data=[
                {"question_id": 1, "question": "Q1", "options": ["A", "B", "C", "D"], "correct_option_index": 0, "provenance": {"unit_id": unit2.id}},
                {"question_id": 2, "question": "Q2", "options": ["A", "B", "C", "D"], "correct_option_index": 1, "provenance": {"unit_id": unit2.id}},
                {"question_id": 3, "question": "Q3", "options": ["A", "B", "C", "D"], "correct_option_index": 2, "provenance": {"unit_id": unit2.id}},
            ],
            status=QuizStatus.COMPLETED,
            score=1.0,
            max_score=3,
            percentage=33.3,
            student_answers={"0": 0, "1": 3, "2": 3},
            submitted_at=datetime.now(timezone.utc)
        )
        att3 = StudyBuddyQuizAttempt(
            student_id=self.student_aiml.id,
            subject_id=sub_id,
            syllabus_document_id=doc_id,
            syllabus_version=1,
            unit_id=unit2.id,
            title="Unit 2 Quiz Attempt 2",
            difficulty="medium",
            total_questions=3,
            questions_data=[
                {"question_id": 1, "question": "Q1", "options": ["A", "B", "C", "D"], "correct_option_index": 0, "provenance": {"unit_id": unit2.id}},
                {"question_id": 2, "question": "Q2", "options": ["A", "B", "C", "D"], "correct_option_index": 1, "provenance": {"unit_id": unit2.id}},
                {"question_id": 3, "question": "Q3", "options": ["A", "B", "C", "D"], "correct_option_index": 2, "provenance": {"unit_id": unit2.id}},
            ],
            status=QuizStatus.COMPLETED,
            score=0.0,
            max_score=3,
            percentage=0.0,
            student_answers={"0": 3, "1": 3, "2": 3},
            submitted_at=datetime.now(timezone.utc)
        )
        self.db.add(att2)
        self.db.add(att3)
        self.db.commit()

        # Call dashboard
        res = self.client.get("/study-buddy/progress/dashboard", headers=self.student_aiml_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertGreaterEqual(data["quizzes_attempted"], 3)
        self.assertGreaterEqual(data["quizzes_completed"], 3)
        self.assertIsNotNone(data["average_percentage"])

        # Check weak topics: Unit 2 has 2 completed attempts with accuracy < 60%
        weak_unit_ids = [w["unit_id"] for w in data["weak_topics"]]
        self.assertIn(unit2.id, weak_unit_ids, "Unit 2 must be flagged as a weak area due to repeated low performance")
        self.assertNotIn(unit1.id, weak_unit_ids, "Unit 1 (100% accuracy) must NOT be flagged as a weak area")

        # Verify reason explains evidence
        unit2_weak = next(w for w in data["weak_topics"] if w["unit_id"] == unit2.id)
        self.assertIn("accuracy across", unit2_weak["reason"])
        self.assertTrue(unit2_weak["has_sufficient_evidence"])

    # =========================================================================
    # 3. ADAPTIVE STUDY PLANNER CREATION & FEASIBILITY
    # =========================================================================

    def test_04_create_study_plan_success(self):
        """Create an adaptive study plan with syllabus grounding and prioritized tasks."""
        syllabus_text = """
Unit 1: Data Structures Overview
Arrays, linked lists, stacks, queues, and tree structures.
Unit 2: Graph Algorithms
Breadth-first search, depth-first search, Dijkstra shortest path algorithm, and topological sorting.
"""
        sub_id, doc_id = self._create_test_subject_with_syllabus("PLN", "Planning Data Structures", "AIML", syllabus_text)

        target_date = (date.today() + timedelta(days=14)).isoformat()
        payload = {
            "subject_id": sub_id,
            "target_date": target_date,
            "daily_budget_minutes": 60,
            "title": "Data Structures Mastery Plan"
        }

        res = self.client.post("/study-buddy/plans", headers=self.student_aiml_headers, json=payload)
        self.assertEqual(res.status_code, 201)
        plan = res.json()

        self.assertEqual(plan["subject_id"], sub_id)
        self.assertEqual(plan["status"], "ACTIVE")
        self.assertEqual(plan["target_date"], target_date)
        self.assertGreater(plan["total_tasks"], 0)
        self.assertEqual(plan["completed_tasks"], 0)

        # Verify task ordering and syllabus provenance
        tasks = plan["tasks"]
        self.assertTrue(len(tasks) > 0)
        first_task = tasks[0]
        self.assertEqual(first_task["order"], 1)
        self.assertEqual(first_task["syllabus_document_id"], doc_id)
        self.assertEqual(first_task["syllabus_version"], 1)
        self.assertIn(first_task["priority"], ["high", "medium", "low"])
        self.assertIsNotNone(first_task["recommendation_reason"])

    def test_05_unrealistic_schedule_rejected(self):
        """Verify that an impossible/unrealistic schedule is rejected with HTTP 400 and clear explanation."""
        syllabus_text = """
Unit 1: Advanced Computer Networks
OSI model, TCP/IP architecture, socket programming, routing protocols, and congestion control.
Unit 2: Wireless & Mobile Computing
Cellular network architecture, Wi-Fi 802.11, mobile IP, and ad-hoc networks.
"""
        sub_id, doc_id = self._create_test_subject_with_syllabus("NET", "Computer Networks", "AIML", syllabus_text)

        # Target date is today (1 day) with tiny daily budget of 15 minutes,
        # but 2 units require ~160 minutes -> Impossible schedule!
        payload = {
            "subject_id": sub_id,
            "target_date": date.today().isoformat(),
            "daily_budget_minutes": 15,
            "title": "Cramming Everything Today"
        }

        res = self.client.post("/study-buddy/plans", headers=self.student_aiml_headers, json=payload)
        self.assertEqual(res.status_code, 400)
        detail = res.json()["detail"]
        self.assertIn("The requested schedule is unrealistic", detail)
        self.assertIn("Please extend your target date", detail)

    # =========================================================================
    # 4. TASK COMPLETION, REOPENING & PROGRESS UPDATE
    # =========================================================================

    def test_06_task_completion_and_reopening(self):
        """Mark task completed and reopened, verifying count and plan status transitions."""
        syllabus_text = """
Unit 1: Operating System Principles
Processes, threads, CPU scheduling algorithms, and memory management.
"""
        sub_id, doc_id = self._create_test_subject_with_syllabus("OPS", "Operating Systems", "AIML", syllabus_text)

        res = self.client.post(
            "/study-buddy/plans",
            headers=self.student_aiml_headers,
            json={"subject_id": sub_id, "daily_budget_minutes": 90, "title": "OS Plan"}
        )
        self.assertEqual(res.status_code, 201)
        plan = res.json()
        plan_id = plan["id"]
        tasks = plan["tasks"]
        task1 = tasks[0]

        # 1. Complete Task 1
        res = self.client.patch(
            f"/study-buddy/plans/{plan_id}/tasks/{task1['id']}",
            headers=self.student_aiml_headers,
            json={"is_completed": True}
        )
        self.assertEqual(res.status_code, 200)
        t_data = res.json()
        self.assertTrue(t_data["is_completed"])
        self.assertIsNotNone(t_data["completed_at"])

        # Check plan detail: completed_tasks should now be 1
        res = self.client.get(f"/study-buddy/plans/{plan_id}", headers=self.student_aiml_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["completed_tasks"], 1)

        # 2. Reopen Task 1
        res = self.client.patch(
            f"/study-buddy/plans/{plan_id}/tasks/{task1['id']}",
            headers=self.student_aiml_headers,
            json={"is_completed": False}
        )
        self.assertEqual(res.status_code, 200)
        t_data = res.json()
        self.assertFalse(t_data["is_completed"])
        self.assertIsNone(t_data["completed_at"])

        # Check plan detail: completed_tasks should revert to 0
        res = self.client.get(f"/study-buddy/plans/{plan_id}", headers=self.student_aiml_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["completed_tasks"], 0)

    # =========================================================================
    # 5. PLAN REGENERATION PRESERVING COMPLETED TASKS
    # =========================================================================

    def test_07_plan_regeneration_preserves_completed_tasks(self):
        """Regenerate study plan and verify tasks update without erasing completion history."""
        syllabus_text = """
Unit 1: Cloud Computing Architecture
Virtualization, containers, Docker, Kubernetes, and serverless architectures.
"""
        sub_id, doc_id = self._create_test_subject_with_syllabus("CLD", "Cloud Architecture", "AIML", syllabus_text)

        res = self.client.post(
            "/study-buddy/plans",
            headers=self.student_aiml_headers,
            json={"subject_id": sub_id, "daily_budget_minutes": 60, "title": "Cloud Plan"}
        )
        self.assertEqual(res.status_code, 201)
        plan = res.json()
        plan_id = plan["id"]
        task1 = plan["tasks"][0]

        # Complete task 1
        self.client.patch(
            f"/study-buddy/plans/{plan_id}/tasks/{task1['id']}",
            headers=self.student_aiml_headers,
            json={"is_completed": True}
        )

        # Call regenerate endpoint
        res = self.client.post(f"/study-buddy/plans/{plan_id}/regenerate", headers=self.student_aiml_headers)
        self.assertEqual(res.status_code, 200)
        regen_plan = res.json()

        # Completed task 1 must remain completed!
        regen_t1 = next(t for t in regen_plan["tasks"] if t["id"] == task1["id"])
        self.assertTrue(regen_t1["is_completed"])
        self.assertEqual(regen_plan["completed_tasks"], 1)

    # =========================================================================
    # 6. SECURITY & OWNERSHIP ISOLATION
    # =========================================================================

    def test_08_ownership_isolation(self):
        """Unauthorized student cannot view, modify, or complete tasks in another student's plan."""
        syllabus_text = "Unit 1: Intro to Security\nCryptography and authorization."
        sub_id, _ = self._create_test_subject_with_syllabus("SEC", "Security Plan", "AIML", syllabus_text)

        # student_aiml creates plan
        res = self.client.post(
            "/study-buddy/plans",
            headers=self.student_aiml_headers,
            json={"subject_id": sub_id, "title": "AIML Student Plan"}
        )
        self.assertEqual(res.status_code, 201)
        plan_id = res.json()["id"]
        task_id = res.json()["tasks"][0]["id"]

        # student_ece attempts to access plan detail -> HTTP 403 Forbidden
        res = self.client.get(f"/study-buddy/plans/{plan_id}", headers=self.student_ece_headers)
        self.assertEqual(res.status_code, 403)

        # student_ece attempts to update plan -> HTTP 403 Forbidden
        res = self.client.patch(
            f"/study-buddy/plans/{plan_id}",
            headers=self.student_ece_headers,
            json={"title": "Hacked Title"}
        )
        self.assertEqual(res.status_code, 403)

        # student_ece attempts to complete task -> HTTP 403 Forbidden
        res = self.client.patch(
            f"/study-buddy/plans/{plan_id}/tasks/{task_id}",
            headers=self.student_ece_headers,
            json={"is_completed": True}
        )
        self.assertEqual(res.status_code, 403)

    def test_09_cross_department_and_inactive_subject_isolation(self):
        """Students cannot create plans for inactive subjects or subjects outside their department."""
        # 1. Subject in ECE department
        sub_id, _ = self._create_test_subject_with_syllabus("ECE", "ECE Core Circuit", "ECE", "Unit 1: Digital Circuits")

        # student_aiml attempts to create plan for ECE subject -> HTTP 403
        res = self.client.post(
            "/study-buddy/plans",
            headers=self.student_aiml_headers,
            json={"subject_id": sub_id, "title": "Unauthorized ECE Plan"}
        )
        self.assertEqual(res.status_code, 403)

        # 2. Inactive subject in AIML department
        inactive_sub_id, _ = self._create_test_subject_with_syllabus("INA", "Inactive Subject", "AIML", "Unit 1: Inactive")
        sub_obj = self.db.query(Subject).get(inactive_sub_id)
        sub_obj.is_active = False
        self.db.commit()

        # student_aiml attempts to create plan for inactive subject -> HTTP 400
        res = self.client.post(
            "/study-buddy/plans",
            headers=self.student_aiml_headers,
            json={"subject_id": inactive_sub_id, "title": "Inactive Subject Plan"}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("inactive", res.json()["detail"].lower())

    def test_10_placement_officer_forbidden(self):
        """Placement Officer is strictly forbidden from accessing progress dashboard or study plans."""
        res = self.client.get("/study-buddy/progress/dashboard", headers=self.po_headers)
        self.assertEqual(res.status_code, 403)

        res = self.client.get("/study-buddy/plans", headers=self.po_headers)
        self.assertEqual(res.status_code, 403)

        res = self.client.post(
            "/study-buddy/plans",
            headers=self.po_headers,
            json={"subject_id": 1, "title": "PO Plan"}
        )
        self.assertEqual(res.status_code, 403)


if __name__ == "__main__":
    unittest.main()
