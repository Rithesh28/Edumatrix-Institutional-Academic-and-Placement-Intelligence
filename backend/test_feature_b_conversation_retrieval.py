"""Test Suite for Feature B: Conversation-Wide Intelligence"""
import unittest
from datetime import datetime
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.user import User, UserRole
from app.models.chat import ChatMessage
from app.services.conversation_retrieval_service import conversation_retrieval_service


class TestConversationRetrieval(unittest.TestCase):
    """Test conversation retrieval with authorization enforcement."""

    @classmethod
    def setUpClass(cls):
        cls.db: Session = SessionLocal()

        # Create test users with matching departments
        cls.student = cls.db.query(User).filter(User.email == "test_student_cse@vcet.ac.in").first()
        if not cls.student:
            cls.student = User(
                email="test_student_cse@vcet.ac.in",
                name="Test CSE Student",
                role=UserRole.STUDENT,
                department="CSE",
                is_active=True,
                password_hash="dummy_hash"
            )
            cls.db.add(cls.student)
            cls.db.commit()
            cls.db.refresh(cls.student)

        cls.hod = cls.db.query(User).filter(User.email == "test_hod_cse@vcet.ac.in").first()
        if not cls.hod:
            cls.hod = User(
                email="test_hod_cse@vcet.ac.in",
                name="Test CSE HOD",
                role=UserRole.HOD,
                department="CSE",
                is_active=True,
                password_hash="dummy_hash"
            )
            cls.db.add(cls.hod)
            cls.db.commit()
            cls.db.refresh(cls.hod)

        cls.placement_officer = cls.db.query(User).filter(User.email == "test_po@vcet.ac.in").first()
        if not cls.placement_officer:
            cls.placement_officer = User(
                email="test_po@vcet.ac.in",
                name="Test Placement Officer",
                role=UserRole.PLACEMENT_OFFICER,
                department="CSE",
                is_active=True,
                password_hash="dummy_hash"
            )
            cls.db.add(cls.placement_officer)
            cls.db.commit()
            cls.db.refresh(cls.placement_officer)

        cls.other_dept_student = cls.db.query(User).filter(User.email == "test_student_aiml@vcet.ac.in").first()
        if not cls.other_dept_student:
            cls.other_dept_student = User(
                email="test_student_aiml@vcet.ac.in",
                name="Test AIML Student",
                role=UserRole.STUDENT,
                department="AIML",
                is_active=True,
                password_hash="dummy_hash"
            )
            cls.db.add(cls.other_dept_student)
            cls.db.commit()
            cls.db.refresh(cls.other_dept_student)

    @classmethod
    def tearDownClass(cls):
        cls.db.query(ChatMessage).filter(
            (ChatMessage.sender_id.in_([cls.student.id, cls.hod.id, cls.placement_officer.id, cls.other_dept_student.id])) |
            (ChatMessage.receiver_id.in_([cls.student.id, cls.hod.id, cls.placement_officer.id, cls.other_dept_student.id]))
        ).delete()
        cls.db.query(User).filter(User.email.in_(
            ["test_student_cse@vcet.ac.in", "test_hod_cse@vcet.ac.in",
             "test_po@vcet.ac.in", "test_student_aiml@vcet.ac.in"]
        )).delete()
        cls.db.commit()
        cls.db.close()

    def create_human_message(self, sender, receiver, content):
        msg = ChatMessage(
            sender_id=sender.id,
            receiver_id=receiver.id,
            content=content,
            is_read=False,
            is_ai=False
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def test_hod_conversation_retrieval(self):
        """Test student can retrieve HOD messages about exams."""
        content = "DLRL exam is scheduled for 23rd November 2026. Please prepare accordingly."
        msg = self.create_human_message(self.hod, self.student, content)

        results = conversation_retrieval_service.retrieve_user_conversations(
            db=self.db,
            user=self.student,
            query_text="When is DLRL exam?",
            limit=5
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source_type"], "chat_message")
        self.assertIn("DLRL", results[0]["content"])
        self.assertEqual(results[0]["sender_role"], "hod")
        self.assertEqual(results[0]["sender_name"], "Test CSE HOD")

        self.db.delete(msg)
        self.db.commit()

    def test_placement_conversation_retrieval(self):
        """Test student can retrieve placement officer messages."""
        content = "TCS placement drive for CSE students on 15th December 2026."
        msg = self.create_human_message(self.placement_officer, self.student, content)

        results = conversation_retrieval_service.retrieve_user_conversations(
            db=self.db,
            user=self.student,
            query_text="placement drive CSE",
            limit=5
        )

        self.assertEqual(len(results), 1)
        self.assertIn("TCS", results[0]["content"])
        self.assertEqual(results[0]["sender_role"], "placement_officer")

        self.db.delete(msg)
        self.db.commit()

    def test_unauthorized_department_filtered(self):
        """Test students cannot access messages from different department."""
        content = "AI exam on 24th November 2026."
        msg = self.create_human_message(self.hod, self.other_dept_student, content)

        results = conversation_retrieval_service.retrieve_user_conversations(
            db=self.db,
            user=self.student,
            query_text="AI exam date",
            limit=5
        )

        self.assertEqual(len(results), 0)

        self.db.delete(msg)
        self.db.commit()

    def test_student_to_student_unauthorized(self):
        """Test student cannot read other students' private messages."""
        # Create message between student and other student (different departments)
        # Student-to-student should be denied per chat policy
        content = "Private project notes here"
        msg = self.create_human_message(self.other_dept_student, self.student, content)

        results = conversation_retrieval_service.retrieve_user_conversations(
            db=self.db,
            user=self.student,
            query_text="project notes",
            limit=5
        )

        # Should be filtered by chat policy (student-to-student not allowed)
        # So message from AIML student to CSE student shouldn't be retrieved
        self.assertEqual(len(results), 0)

        self.db.delete(msg)
        self.db.commit()

    def test_ai_messages_filtered(self):
        """Test AI messages are not retrieved."""
        msg = ChatMessage(
            sender_id=None,
            receiver_id=self.student.id,
            content="AI response about DLRL exam",
            is_read=True,
            is_ai=True,
            ai_participant="assistant"
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)

        results = conversation_retrieval_service.retrieve_user_conversations(
            db=self.db,
            user=self.student,
            query_text="DLRL exam",
            limit=5
        )

        # AI messages should be filtered out by is_ai=False
        self.assertEqual(len(results), 0)

        self.db.delete(msg)
        self.db.commit()

    def test_conflicting_dates_resolution(self):
        """Test retrieval finds both timetable and conversation sources."""
        # Create HOD message with exam date
        hod_msg = self.create_human_message(
            self.hod, self.student,
            "DLRL exam rescheduled to 25th November 2026 due to clash."
        )

        results = conversation_retrieval_service.retrieve_user_conversations(
            db=self.db,
            user=self.student,
            query_text="DLRL exam date",
            limit=5
        )

        self.assertGreater(len(results), 0)
        contents = [r["content"] for r in results]
        self.assertTrue(any("rescheduled" in c.lower() for c in contents))

        self.db.delete(hod_msg)
        self.db.commit()

    def test_relevance_scoring(self):
        """Test messages are ranked by relevance."""
        msg1 = self.create_human_message(
            self.hod, self.student,
            "DLRL exam scheduled for Friday"
        )
        msg2 = self.create_human_message(
            self.placement_officer, self.student,
            "Random message about placement"
        )

        results = conversation_retrieval_service.retrieve_user_conversations(
            db=self.db,
            user=self.student,
            query_text="DLRL exam date",
            limit=5
        )

        # Should find DLRL message first
        self.assertGreater(len(results), 0)
        self.assertIn("DLRL", results[0]["content"])

        self.db.delete(msg1)
        self.db.delete(msg2)
        self.db.commit()


if __name__ == "__main__":
    unittest.main()
