"""
AI Chat Orchestrator Service

Provides the end-to-end pipeline for the EduMatrix AI Chat Assistant:
Student Message
   ↓
Validate Input
   ↓
Intent Classification
   ↓
Sentiment Analysis
   ↓
Query Routing
   ↓
Institutional Retrieval (PostgreSQL / Qdrant)
   ↓
Grounded Context Assembly
   ↓
Qwen / Anti-Hallucination Generation
   ↓
Store AI Metadata & Messages
   ↓
Return Response
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from ..models.user import User
from ..models.chat import ChatMessage
from .intent_classifier import intent_classifier
from .sentiment_analyser import sentiment_analyser
from .query_router import query_router
from .ai_generator_service import ai_generator
from ..core.config import settings
from ..core.study_buddy_timing import record_perf_metric

logger = logging.getLogger(__name__)


class AIChatService:
    """
    Central orchestration service for EduMatrix AI Chat interactions.
    """

    def process_user_message(
        self,
        db: Session,
        user: User,
        message: str
    ) -> Dict[str, Any]:
        """
        Executes the full AI chat pipeline for an incoming user message.
        """
        total_start = time.perf_counter()
        clean_text = (message or "").strip()
        if not clean_text:
            raise ValueError("Message content cannot be empty")

        logger.info(f"🤖 [AI-CHAT] Processing message from User ID {user.id} ({user.email}): '{clean_text[:50]}...'")

        # 2. Detect Intent
        t0 = time.perf_counter()
        intent_result = intent_classifier.predict(clean_text)
        detected_intent = intent_result.get("intent", "other")
        intent_conf = float(intent_result.get("confidence", 0.5))
        intent_ms = (time.perf_counter() - t0) * 1000.0
        record_perf_metric("intent_classification", intent_ms, intent=detected_intent, confidence=round(intent_conf, 3))
        logger.info(f"🎯 [AI-CHAT] Intent: {detected_intent} (conf: {intent_conf:.2f}) | {intent_ms:.1f}ms")

        # 3. Detect Sentiment
        t0 = time.perf_counter()
        sentiment_result = sentiment_analyser.analyse(clean_text)
        detected_sentiment = sentiment_result.get("sentiment", "neutral")
        sentiment_conf = float(sentiment_result.get("confidence", 0.5))
        sentiment_ms = (time.perf_counter() - t0) * 1000.0
        record_perf_metric("sentiment_analysis", sentiment_ms, sentiment=detected_sentiment, confidence=round(sentiment_conf, 3))
        logger.info(f"🎭 [AI-CHAT] Sentiment: {detected_sentiment} (conf: {sentiment_conf:.2f}) | {sentiment_ms:.1f}ms")

        # 4. Route Query & Retrieve Institutional Evidence
        t0 = time.perf_counter()
        department = getattr(user, "department", None)
        routing_result = query_router.execute_routing(
            db=db,
            intent=detected_intent,
            query_text=clean_text,
            department=department
        )
        routing_ms = (time.perf_counter() - t0) * 1000.0
        strategy = routing_result.get("strategy", "general_institutional")
        sources = routing_result.get("sources", [])
        is_ambiguous = routing_result.get("is_ambiguous", False)
        ambiguous_candidates = routing_result.get("ambiguous_candidates", [])
        ambiguity_category = routing_result.get("ambiguity_category", "assignment")
        record_perf_metric("query_routing_and_retrieval", routing_ms, strategy=strategy, sources=len(sources), ambiguous=is_ambiguous)
        logger.info(f"📚 [AI-CHAT] Strategy: {strategy} | Sources: {len(sources)} | Ambiguous: {is_ambiguous} | {routing_ms:.1f}ms")

        # 5. Generate Grounded Answer (with strict anti-hallucination guardrail)
        t0 = time.perf_counter()
        generation_result = ai_generator.generate_grounded_answer(
            query=clean_text,
            sources=sources,
            intent=detected_intent,
            is_ambiguous=is_ambiguous,
            ambiguous_candidates=ambiguous_candidates,
            ambiguity_category=ambiguity_category
        )
        generation_ms = (time.perf_counter() - t0) * 1000.0
        answer_text = generation_result.get("answer", "")
        model_used = generation_result.get("model_used", settings.AI_MODEL_NAME)
        has_grounded_evidence = bool(generation_result.get("has_evidence", False))
        record_perf_metric("model_generation", generation_ms, model=model_used, has_evidence=has_grounded_evidence, ambiguous=is_ambiguous)
        logger.info(f"🧠 [AI-CHAT] Generation: model={model_used} evidence={has_grounded_evidence} | {generation_ms:.1f}ms")

        total_ms = (time.perf_counter() - total_start) * 1000.0
        record_perf_metric("ai_chat_total", total_ms, intent=detected_intent, strategy=strategy, model=model_used, has_evidence=has_grounded_evidence)
        logger.info(f"✅ [AI-CHAT] Total pipeline: {total_ms:.1f}ms")

        # 6. Assemble AI Metadata & Strictly Filter Sources Supporting the Answer
        clean_sources_meta = []
        if is_ambiguous and ambiguous_candidates:
            # Expose the verified candidate assignments listed in the clarification
            for s in ambiguous_candidates[:5]:
                clean_sources_meta.append({
                    "type": s.get("source_type"),
                    "id": str(s.get("source_id")),
                    "title": s.get("title"),
                    "category": s.get("category"),
                    "due_date": s.get("due_date"),
                    "score": s.get("score"),
                    "has_verified_text": s.get("has_verified_text", False)
                })
        elif has_grounded_evidence and sources:
            # Only expose sources that actually have verified text or due dates
            for s in sources[:5]:
                if s.get("has_verified_text") or s.get("due_date"):
                    clean_sources_meta.append({
                        "type": s.get("source_type"),
                        "id": str(s.get("source_id")),
                        "title": s.get("title"),
                        "category": s.get("category"),
                        "due_date": s.get("due_date"),
                        "score": s.get("score"),
                        "has_verified_text": s.get("has_verified_text", False)
                    })

        if is_ambiguous:
            grounding_status = "ambiguity_clarification"
        elif has_grounded_evidence:
            grounding_status = "grounded"
        else:
            grounding_status = "no_evidence_fallback"

        ai_metadata = {
            "intent": detected_intent,
            "intent_confidence": intent_conf,
            "sentiment": detected_sentiment,
            "sentiment_confidence": sentiment_conf,
            "retrieval_strategy": strategy,
            "retrieval_sources": clean_sources_meta,
            "has_grounded_evidence": has_grounded_evidence,
            "is_ambiguous": is_ambiguous,
            "grounding_status": grounding_status,
            "model": model_used,
            "is_hallucinated": False,
            "processed_at": datetime.utcnow().isoformat()
        }

        # 7. Persist Student Message in Database
        student_msg = ChatMessage(
            sender_id=user.id,
            receiver_id=None,
            content=clean_text,
            is_read=True,
            is_ai=True,
            ai_participant="assistant",
            intent=detected_intent,
            intent_confidence=intent_conf,
            sentiment=detected_sentiment,
            sentiment_confidence=sentiment_conf
        )
        db.add(student_msg)
        db.flush()

        # 8. Persist AI Response in Database
        ai_msg = ChatMessage(
            sender_id=None,
            receiver_id=user.id,
            content=answer_text,
            is_read=True,
            is_ai=True,
            ai_participant="assistant",
            intent=detected_intent,
            intent_confidence=intent_conf,
            sentiment=detected_sentiment,
            sentiment_confidence=sentiment_conf,
            ai_metadata=ai_metadata
        )
        db.add(ai_msg)
        db.commit()
        db.refresh(student_msg)
        db.refresh(ai_msg)

        logger.info(f"✅ [AI-CHAT] Interaction persisted successfully. UserMsg ID: {student_msg.id}, AIMsg ID: {ai_msg.id}")

        return {
            "user_message": student_msg,
            "ai_response": ai_msg,
            "intent": detected_intent,
            "intent_confidence": intent_conf,
            "sentiment": detected_sentiment,
            "sentiment_confidence": sentiment_conf,
            "retrieval_strategy": strategy,
            "retrieval_sources": clean_sources_meta,
            "ai_metadata": ai_metadata
        }


ai_chat_service = AIChatService()
