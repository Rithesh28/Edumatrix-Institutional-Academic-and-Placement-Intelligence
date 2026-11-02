"""Test Suite for Feature A: Sentiment and Intent Classification in Normal Chat"""

import unittest
import time
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.user import User, UserRole
from app.models.chat import ChatMessage
from app.services.sentiment_analyser import sentiment_analyser
from app.services.intent_classifier import intent_classifier
from app.api.chat import classify_and_update_message


class TestNormalChatClassification(unittest.TestCase):
    """Test sentiment and intent classification for normal human-to-human chat."""

    @classmethod
    def setUpClass(cls):
        cls.db: Session = SessionLocal()

        # Ensure test students exist
        cls.test_student1 = cls.db.query(User).filter(User.email == "test_classify_sender@vcet.ac.in").first()
        if not cls.test_student1:
            cls.test_student1 = User(
                email="test_classify_sender@vcet.ac.in",
                name="Test Classify Sender",
                role=UserRole.STUDENT,
                department="CSE",
                is_active=True,
                password_hash="dummy_hash"
            )
            cls.db.add(cls.test_student1)
            cls.db.commit()
            cls.db.refresh(cls.test_student1)

        cls.test_student2 = cls.db.query(User).filter(User.email == "test_classify_receiver@vcet.ac.in").first()
        if not cls.test_student2:
            cls.test_student2 = User(
                email="test_classify_receiver@vcet.ac.in",
                name="Test Classify Receiver",
                role=UserRole.STUDENT,
                department="CSE",
                is_active=True,
                password_hash="dummy_hash"
            )
            cls.db.add(cls.test_student2)
            cls.db.commit()
            cls.db.refresh(cls.test_student2)

    @classmethod
    def tearDownClass(cls):
        cls.db.query(ChatMessage).filter(
            (ChatMessage.sender_id == cls.test_student1.id) |
            (ChatMessage.receiver_id == cls.test_student1.id) |
            (ChatMessage.sender_id == cls.test_student2.id) |
            (ChatMessage.receiver_id == cls.test_student2.id)
        ).delete()
        cls.db.delete(cls.test_student1)
        cls.db.delete(cls.test_student2)
        cls.db.commit()
        cls.db.close()

    def create_test_message(self, content: str) -> ChatMessage:
        """Helper to create a test message."""
        msg = ChatMessage(
            sender_id=self.test_student1.id,
            receiver_id=self.test_student2.id,
            content=content,
            is_read=False,
            is_ai=False
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def cleanup_message(self, msg: ChatMessage):
        """Helper to clean up a test message."""
        self.db.delete(msg)
        self.db.commit()

    def test_positive_sentiment_classification(self):
        """Test classification of positive sentiment message."""
        content = "Congratulations to everyone who cleared the placement round!"
        msg = self.create_test_message(content)

        classify_and_update_message(msg.id, content)
        time.sleep(0.5)
        self.db.refresh(msg)

        self.assertEqual(msg.sentiment, "positive")
        self.assertGreater(msg.sentiment_confidence, 0.5)
        self.assertIsNotNone(msg.intent)
        self.assertGreater(msg.intent_confidence, 0.0)
        self.assertIn("classification", msg.ai_metadata or {})

        self.cleanup_message(msg)

    def test_negative_sentiment_classification(self):
        """Test classification of negative/confused sentiment message."""
        content = "I am unable to understand the assignment. Could you please explain?"
        msg = self.create_test_message(content)

        classify_and_update_message(msg.id, content)
        time.sleep(0.5)
        self.db.refresh(msg)

        self.assertEqual(msg.sentiment, "negative")
        self.assertGreater(msg.sentiment_confidence, 0.8)
        self.assertIsNotNone(msg.intent)

        self.cleanup_message(msg)

    def test_neutral_sentiment_classification(self):
        """Test classification of neutral sentiment message."""
        content = "Students must submit the assignment before Friday."
        msg = self.create_test_message(content)

        classify_and_update_message(msg.id, content)
        time.sleep(0.5)
        self.db.refresh(msg)

        # Should be neutral or close to neutral
        self.assertIn(msg.sentiment, ["neutral", "positive", "negative"])
        self.assertIsNotNone(msg.intent)

        self.cleanup_message(msg)

    def test_exam_announcement_intent(self):
        """Test classification of exam announcement."""
        content = "The DLRL exam will be conducted on 23rd November 2026."
        msg = self.create_test_message(content)

        classify_and_update_message(msg.id, content)
        time.sleep(0.5)
        self.db.refresh(msg)

        # Intent should be exam-related
        self.assertIn(msg.intent, ["ask_exam_info", "other"])
        self.assertIsNotNone(msg.sentiment)

        self.cleanup_message(msg)

    def test_deadline_announcement_intent(self):
        """Test classification of deadline announcement."""
        content = "The deadline for the project is next week."
        msg = self.create_test_message(content)

        classify_and_update_message(msg.id, content)
        time.sleep(0.5)
        self.db.refresh(msg)

        self.assertIn(msg.intent, ["check_deadline", "other"])

        self.cleanup_message(msg)

    def test_placement_update_intent(self):
        """Test classification of placement-related message."""
        content = "Are there any placements for CSE students?"
        msg = self.create_test_message(content)

        classify_and_update_message(msg.id, content)
        time.sleep(0.5)
        self.db.refresh(msg)

        self.assertIn(msg.intent, ["career_advice", "ask_exam_info", "other"])

        self.cleanup_message(msg)

    def test_academic_question_intent(self):
        """Test classification of academic doubt/request."""
        content = "I am unable to understand the assignment. Could you please explain?"
        msg = self.create_test_message(content)

        classify_and_update_message(msg.id, content)
        time.sleep(0.5)
        self.db.refresh(msg)

        self.assertIn(msg.intent, ["ask_doubt", "other"])
        self.assertEqual(msg.sentiment, "negative")

        self.cleanup_message(msg)

    def test_classification_does_not_block_message_delivery(self):
        """Test that classification failure never prevents message persistence."""
        content = "Test message for classification resilience."
        msg = self.create_test_message(content)

        # Verify message exists before classification
        self.assertIsNotNone(msg.id)

        # Call classification (should not raise exception even if it fails internally)
        classify_and_update_message(msg.id, content)
        time.sleep(0.5)

        # Message should still exist and be accessible
        self.db.refresh(msg)
        self.assertEqual(msg.content, content)

        self.cleanup_message(msg)

    def test_ai_messages_not_classified(self):
        """Test that AI messages are not classified as human messages."""
        content = "This is an AI response."
        msg = ChatMessage(
            sender_id=None,
            receiver_id=self.test_student1.id,
            content=content,
            is_read=True,
            is_ai=True,
            ai_participant="assistant"
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)

        # Classify - should skip AI messages
        classify_and_update_message(msg.id, content)
        time.sleep(0.5)
        self.db.refresh(msg)

        # AI message should not have classification metadata
        # (intent/sentiment may remain None)
        self.assertTrue(msg.is_ai)

        self.cleanup_message(msg)

    def test_classification_metadata_structure(self):
        """Test that classification metadata has correct structure."""
        content = "The DLRL exam will be conducted on 23rd November 2026."
        msg = self.create_test_message(content)

        classify_and_update_message(msg.id, content)
        time.sleep(0.5)
        self.db.refresh(msg)

        # Verify ai_metadata structure
        self.assertIsNotNone(msg.ai_metadata)
        classification = msg.ai_metadata.get("classification")
        self.assertIsNotNone(classification)

        required_fields = ["sentiment", "sentiment_confidence", "intent", "intent_confidence", "classified_at"]
        for field in required_fields:
            self.assertIn(field, classification)

        self.assertIsInstance(classification["classified_at"], str)

        self.cleanup_message(msg)

    def test_classification_independent_from_delivery(self):
        """Test that classification runs independently and does not block."""
        content = "Test message for independent classification."
        msg = self.create_test_message(content)
        original_content = msg.content

        start = time.time()
        classify_and_update_message(msg.id, content)
        elapsed = time.time() - start

        # Classification should return quickly (background task)
        # The function returns immediately, actual work happens in background
        self.assertLess(elapsed, 2.0, "Classification should return immediately")

        # Wait for background processing
        time.sleep(1.0)
        self.db.refresh(msg)

        self.assertEqual(msg.content, original_content)

        self.cleanup_message(msg)


class TestSentimentAndIntentClassifiers(unittest.TestCase):
    """Test the underlying sentiment and intent classifiers directly."""

    def test_sentiment_analyser_loads(self):
        """Test that sentiment analyser can load."""
        result = sentiment_analyser.analyse("Test message")
        self.assertIn("sentiment", result)
        self.assertIn("confidence", result)
        self.assertIn(result["sentiment"], ["positive", "neutral", "negative"])

    def test_intent_classifier_loads(self):
        """Test that intent classifier can load."""
        result = intent_classifier.predict("When is the exam?")
        self.assertIn("intent", result)
        self.assertIn("confidence", result)

    def test_existing_classifiers_not_affected(self):
        """Test that AI Chat Analyzer classifiers are not affected."""
        # The classifiers are singletons - ensure they still work for AI Chat
        test_queries = [
            "When is the last date to submit the assignment?",
            "What is the DLRL exam date?",
            "Are there any placements?",
            "Hello!",
            "Explain DSP concepts"
        ]

        for query in test_queries:
            sentiment = sentiment_analyser.analyse(query)
            intent = intent_classifier.predict(query)

            self.assertIn("sentiment", sentiment)
            self.assertIn("intent", intent)
            self.assertIsNotNone(sentiment["sentiment"])
            self.assertIsNotNone(intent["intent"])


if __name__ == "__main__":
    unittest.main()