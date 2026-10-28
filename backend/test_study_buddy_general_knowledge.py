"""
Test Suite: Study Buddy General Knowledge Mode

Verifies that Study Buddy can answer general academic questions without document evidence,
while still providing document-grounded answers when relevant evidence exists.
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.ai_generator_service import ai_generator
from app.services.ollama_client import OllamaClient
from app.services.study_buddy_chat_service import study_buddy_chat_service


class TestGeneralKnowledgeMode(unittest.TestCase):
    """Test general knowledge mode for Study Buddy."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_db = Mock()
        self.mock_user = Mock()
        self.mock_user.id = 1
        self.mock_user.role = Mock()
        self.mock_user.role.value = "student"
        self.mock_user.department = "CSE"
        self.mock_user.student_profile = Mock()
        self.mock_user.student_profile.branch = "CSE"
        self.mock_user.student_profile.semester = 3

    @patch('app.services.ai_generator_service.ollama_client')
    def test_general_knowledge_question_no_documents(self, mock_ollama):
        """Test that general academic questions work without any document context."""
        # Mock Ollama response for general knowledge
        mock_result = Mock()
        mock_result.error = None
        mock_result.response = "Supervised learning uses labeled data to train models, while unsupervised learning finds patterns in unlabeled data."
        mock_result.total_duration = 1000000000
        mock_ollama.generate_study_buddy_answer = AsyncMock(return_value={
            "answer": "Supervised learning uses labeled data to train models, while unsupervised learning finds patterns in unlabeled data.",
            "has_sufficient_evidence": True,
            "model_used": "phi4-mini",
            "latency_ms": 1000,
            "is_fallback": False
        })

        # Call with empty sources and context
        result = ai_generator.generate_study_buddy_answer(
            query="Explain supervised vs unsupervised learning",
            context_str="",
            sources=[]
        )

        # Verify general knowledge answer is returned
        self.assertIn("supervised", result["answer"].lower())
        self.assertIn("unsupervised", result["answer"].lower())
        self.assertFalse(result["is_fallback"])
        self.assertEqual(result["model_used"], "phi4-mini")
        self.assertTrue(result["has_sufficient_evidence"])

    @patch('app.services.ai_generator_service.ollama_client')
    def test_document_grounded_answer_with_sources(self, mock_ollama):
        """Test that document-grounded answers work when sources are provided."""
        # Mock Ollama response for document-grounded answer
        mock_ollama.generate_study_buddy_answer = AsyncMock(return_value={
            "answer": "Based on the syllabus, backpropagation calculates gradients using chain rule.",
            "has_sufficient_evidence": True,
            "model_used": "phi4-mini",
            "latency_ms": 1500,
            "is_fallback": False
        })

        sources = [{
            "text": "Backpropagation uses the chain rule to compute gradients layer by layer.",
            "source_type": "syllabus",
            "subject_code": "CS601",
            "subject_name": "Machine Learning",
            "unit_number": 2,
            "topic_title": "Neural Networks",
            "source_page": 15
        }]

        result = ai_generator.generate_study_buddy_answer(
            query="How does backpropagation work?",
            context_str="[Passage 1 - Syllabus] CS601 Machine Learning | Unit 2: Neural Networks (Page 15)\nContent: Backpropagation uses the chain rule to compute gradients layer by layer.",
            sources=sources
        )

        # Verify document-grounded answer
        self.assertIn("backpropagation", result["answer"].lower())
        self.assertFalse(result["is_fallback"])
        self.assertTrue(result["has_sufficient_evidence"])

    @patch('app.services.ai_generator_service.ollama_client')
    def test_ollama_error_fallback_general_knowledge(self, mock_ollama):
        """Test that Ollama errors in general knowledge mode return fallback text."""
        import asyncio
        mock_ollama.generate_study_buddy_answer = AsyncMock(side_effect=asyncio.TimeoutError())

        result = ai_generator.generate_study_buddy_answer(
            query="What is gradient descent?",
            context_str="",
            sources=[]
        )

        # Should return exact fallback text
        self.assertEqual(result["answer"], "This is not covered in the provided notes.")
        self.assertTrue(result["is_fallback"])
        self.assertFalse(result["has_sufficient_evidence"])
        self.assertEqual(result["fallback_reason"], "ollama_timeout")

    @patch('app.services.ai_generator_service.ollama_client')
    def test_ollama_error_fallback_with_context(self, mock_ollama):
        """Test that Ollama errors with context return synthesized answer."""
        import asyncio
        mock_ollama.generate_study_buddy_answer = AsyncMock(side_effect=asyncio.TimeoutError())

        sources = [{"text": "Some syllabus text", "source_type": "syllabus"}]

        result = ai_generator.generate_study_buddy_answer(
            query="What is gradient descent?",
            context_str="Some syllabus text",
            sources=sources
        )

        # Should return synthesized answer (not exact fallback)
        self.assertTrue(result["is_fallback"])
        self.assertIn("gradient", result["answer"].lower())

    @patch('app.services.ollama_client.OllamaClient.generate')
    def test_ollama_client_general_knowledge_prompt(self, mock_generate):
        """Test that Ollama client builds correct prompt for general knowledge mode."""
        mock_result = Mock()
        mock_result.error = None
        mock_result.response = "General knowledge answer"
        mock_result.total_duration = 500000000
        mock_generate.return_value = mock_result

        client = OllamaClient()
        import asyncio

        async def test():
            return await client.generate_study_buddy_answer(
                query="Explain K-means clustering",
                context_str="",  # Empty context
                system_prompt="Test prompt"
            )

        result = asyncio.run(test())

        # Verify prompt was built without document passages
        call_args = mock_generate.call_args
        prompt = call_args.kwargs['prompt']
        self.assertIn("NO DOCUMENT CONTEXT PROVIDED", prompt)
        self.assertIn("Answer from your general academic knowledge", prompt)
        self.assertNotIn("APPROVED SYLLABUS PASSAGES", prompt)

        self.assertTrue(result["has_sufficient_evidence"])
        self.assertFalse(result["is_fallback"])

    @patch('app.services.ollama_client.OllamaClient.generate')
    def test_ollama_client_document_grounded_prompt(self, mock_generate):
        """Test that Ollama client builds correct prompt for document-grounded mode."""
        mock_result = Mock()
        mock_result.error = None
        mock_result.response = "Document grounded answer"
        mock_result.total_duration = 500000000
        mock_generate.return_value = mock_result

        client = OllamaClient()
        import asyncio

        async def test():
            return await client.generate_study_buddy_answer(
                query="Explain K-means clustering",
                context_str="Some syllabus content about K-means",
                system_prompt="Test prompt"
            )

        result = asyncio.run(test())

        # Verify prompt was built with document passages
        call_args = mock_generate.call_args
        prompt = call_args.kwargs['prompt']
        self.assertIn("APPROVED SYLLABUS PASSAGES", prompt)
        self.assertIn("Some syllabus content about K-means", prompt)
        self.assertIn("Answer strictly based on the provided passages", prompt)
        self.assertNotIn("NO DOCUMENT CONTEXT PROVIDED", prompt)

    @patch('app.services.ollama_client.OllamaClient.generate')
    def test_ollama_client_normalizes_no_evidence_response(self, mock_generate):
        """Test that model's 'not enough info' responses are normalized to exact text."""
        mock_result = Mock()
        mock_result.error = None
        mock_result.response = "The approved academic reference materials do not provide enough information to answer this question."
        mock_result.total_duration = 500000000
        mock_generate.return_value = mock_result

        client = OllamaClient()
        import asyncio

        async def test():
            return await client.generate_study_buddy_answer(
                query="What is the secret formula?",
                context_str="Some unrelated syllabus content",
                system_prompt="Test prompt"
            )

        result = asyncio.run(test())

        # Should normalize to exact required text
        self.assertEqual(result["answer"], "This is not covered in the provided notes.")
        self.assertFalse(result["has_sufficient_evidence"])
        self.assertFalse(result["is_fallback"])

    @patch('app.services.ollama_client.OllamaClient.generate')
    def test_ollama_client_general_knowledge_not_normalized(self, mock_generate):
        """Test that 'not enough info' in general knowledge mode is NOT normalized."""
        mock_result = Mock()
        mock_result.error = None
        mock_result.response = "I don't have enough information to answer that specific question."
        mock_result.total_duration = 500000000
        mock_generate.return_value = mock_result

        client = OllamaClient()
        import asyncio

        async def test():
            return await client.generate_study_buddy_answer(
                query="What is the secret formula?",
                context_str="",  # Empty context - general knowledge mode
                system_prompt="Test prompt"
            )

        result = asyncio.run(test())

        # In general knowledge mode, should NOT normalize - model can answer from its knowledge
        # The "not enough info" check only applies when context was provided
        self.assertNotEqual(result["answer"], "This is not covered in the provided notes.")
        self.assertTrue(result["has_sufficient_evidence"])
        self.assertFalse(result["is_fallback"])


class TestStudyBuddyChatService(unittest.TestCase):
    """Test StudyBuddyChatService general knowledge behavior."""

    @patch('app.services.study_buddy_chat_service.embedding_service')
    @patch('app.services.study_buddy_chat_service.ai_generator')
    @patch('app.services.study_buddy_chat_service.syllabus_indexing_service')
    @patch('app.services.study_buddy_chat_service.lecture_notes_indexing_service')
    @patch('app.services.study_buddy_chat_service.student_documents_indexing_service')
    def test_ask_question_no_evidence_general_knowledge(self, mock_student_idx, mock_lecture_idx, mock_syllabus_idx, mock_ai_gen, mock_embed):
        """Test that ask_question proceeds to LLM even with no qualifying chunks."""
        from app.services.study_buddy_chat_service import study_buddy_chat_service
        from app.models.user import User, UserRole

        # Setup mocks
        mock_embed.embed_text.return_value = [0.1] * 384
        mock_syllabus_idx.search_chunks.return_value = []
        mock_lecture_idx.search_chunks.return_value = []
        mock_student_idx.search_chunks.return_value = []

        # Mock AI generator to return general knowledge answer
        mock_ai_gen.generate_study_buddy_answer.return_value = {
            "answer": "Gradient descent is an optimization algorithm that iteratively moves toward the minimum of a function.",
            "has_sufficient_evidence": True,
            "model_used": "phi4-mini",
            "latency_ms": 1000,
            "is_fallback": False
        }

        mock_db = Mock()
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.role = UserRole.STUDENT
        mock_user.department = "CSE"
        mock_user.student_profile = Mock()
        mock_user.student_profile.branch = "CSE"
        mock_user.student_profile.semester = 3

        # Call ask_question with no document evidence
        result = study_buddy_chat_service.ask_question(
            db=mock_db,
            current_user=mock_user,
            question="What is gradient descent?",
            subject_id=None,
            source_mode="all",
            attached_document_id=None
        )

        # Should call AI generator and return general knowledge answer
        self.assertTrue(mock_ai_gen.generate_study_buddy_answer.called)
        self.assertIn("gradient descent", result["answer"].lower())
        self.assertTrue(result["has_sufficient_evidence"])
        self.assertFalse(result["is_fallback"])
        self.assertEqual(len(result["citations"]), 0)  # No citations in general knowledge mode

    @patch('app.services.study_buddy_chat_service.embedding_service')
    @patch('app.services.study_buddy_chat_service.ai_generator')
    @patch('app.services.study_buddy_chat_service.syllabus_indexing_service')
    @patch('app.services.study_buddy_chat_service.lecture_notes_indexing_service')
    @patch('app.services.study_buddy_chat_service.student_documents_indexing_service')
    def test_ask_question_with_evidence_document_grounded(self, mock_student_idx, mock_lecture_idx, mock_syllabus_idx, mock_ai_gen, mock_embed):
        """Test that ask_question uses document-grounded mode when evidence exists."""
        from app.services.study_buddy_chat_service import study_buddy_chat_service
        from app.models.user import User, UserRole

        # Setup mocks
        mock_embed.embed_text.return_value = [0.1] * 384

        # Return qualifying chunks
        mock_syllabus_idx.search_chunks.return_value = [{
            "score": 0.85,
            "text": "Gradient descent minimizes loss function by updating weights.",
            "source_type": "syllabus",
            "subject_code": "CS601",
            "subject_name": "Machine Learning",
            "unit_number": 3,
            "unit_title": "Optimization",
            "topic_title": "Gradient Descent",
            "source_page": 20
        }]
        mock_lecture_idx.search_chunks.return_value = []
        mock_student_idx.search_chunks.return_value = []

        # Mock AI generator
        mock_ai_gen.generate_study_buddy_answer.return_value = {
            "answer": "Based on the syllabus, gradient descent minimizes the loss function by iteratively updating weights in the direction of the negative gradient.",
            "has_sufficient_evidence": True,
            "model_used": "phi4-mini",
            "latency_ms": 1200,
            "is_fallback": False
        }

        mock_db = Mock()
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.role = UserRole.STUDENT
        mock_user.department = "CSE"
        mock_user.student_profile = Mock()
        mock_user.student_profile.branch = "CSE"
        mock_user.student_profile.semester = 3

        result = study_buddy_chat_service.ask_question(
            db=mock_db,
            current_user=mock_user,
            question="What is gradient descent?",
            subject_id=1,
            source_mode="all",
            attached_document_id=None
        )

        # Should use document-grounded mode with citations
        self.assertTrue(mock_ai_gen.generate_study_buddy_answer.called)
        self.assertIn("gradient descent", result["answer"].lower())
        self.assertTrue(result["has_sufficient_evidence"])
        self.assertFalse(result["is_fallback"])
        self.assertEqual(len(result["citations"]), 1)  # Should have citation


if __name__ == "__main__":
    unittest.main()