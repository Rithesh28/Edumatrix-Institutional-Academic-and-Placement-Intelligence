"""Regression test for general knowledge routing."""
import unittest
from app.services.query_router import query_router
from app.services.ai_generator_service import ai_generator
from app.core.database import SessionLocal

class TestGeneralKnowledgeRouting(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_general_knowledge_routing_no_retrieval(self):
        """Verify GK query selects correct strategy and zero retrieval."""
        query = "Who is the president of India?"
        # Strategy should be general_knowledge
        strategy = query_router.determine_strategy("other", query, intent_confidence=0.22)
        self.assertEqual(strategy, "general_knowledge")

        # Routing result should have requires_retrieval=False
        result = query_router.execute_routing(self.db, "other", query, intent_confidence=0.22)
        self.assertFalse(result["requires_retrieval"])
        self.assertEqual(result["source_count"], 0)

        # AI Generator should produce restriction explanation
        gen_result = ai_generator.generate_grounded_answer(
            query=query,
            sources=[],
            strategy=strategy
        )
        self.assertIn("restricted to institutional knowledge", gen_result["answer"])

    def test_dlrl_timetable_still_uses_retrieval(self):
        """Verify timetable query still uses institutional retrieval."""
        query = "When is DLRL CIE 2?"
        strategy = query_router.determine_strategy("other", query, intent_confidence=0.22)
        # Should be exam_information (from institutional keywords)
        self.assertEqual(strategy, "exam_information")

        result = query_router.execute_routing(self.db, "other", query, intent_confidence=0.22)
        self.assertTrue(result["requires_retrieval"])
        self.assertGreater(result["source_count"], 0)

if __name__ == "__main__":
    unittest.main()
