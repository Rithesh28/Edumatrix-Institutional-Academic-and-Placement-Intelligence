"""
AI Chat Analytics API

Provides endpoints for AI Chat Analyzer performance metrics and analytics.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, text, and_
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
import os
import glob

from ..core.database import get_db
from ..api.auth import get_current_user
from ..models.user import User
from ..models.chat import ChatMessage

router = APIRouter(prefix="/ai/chat-analytics", tags=["AI Chat Analytics"])

# Path to evaluation results
EVAL_RESULTS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'evaluation', 'results')


def _get_latest_eval_metrics() -> Dict[str, Any]:
    """Load latest AI chat analyzer evaluation metrics from JSON files.

    Supports both old format (metrics_*.json) and new v2 format
    (metrics_v2_*.json with intent/sentiment accuracy fields).
    """
    # Try v2 format first (more detailed metrics)
    pattern_v2 = os.path.join(EVAL_RESULTS_DIR, 'ai_chat_analyzer_metrics_v2_*.json')
    files_v2 = sorted(glob.glob(pattern_v2), key=os.path.getmtime, reverse=True)

    if files_v2:
        try:
            with open(files_v2[0], 'r') as f:
                metrics = json.load(f)
            # Add metadata
            metrics["data_source"] = "evaluation_v2"
            metrics["last_evaluated"] = os.path.getmtime(files_v2[0])
            metrics["total_cases"] = metrics.get("total_cases", 0)
            metrics["evaluated"] = metrics.get("evaluated", 0)
            return metrics
        except Exception:
            pass

    # Fallback to old format
    pattern_v1 = os.path.join(EVAL_RESULTS_DIR, 'ai_chat_analyzer_metrics_*.json')
    files_v1 = sorted(glob.glob(pattern_v1), key=os.path.getmtime, reverse=True)

    if not files_v1:
        return {
            "total_cases": 0,
            "pending_model_eval": 0,
            "evaluated": 0,
            "avg_grounding": 0,
            "hallucination_rate": 0.0,
            "ambiguity_detection_rate": 0.0,
            "intent_accuracy": 0.0,
            "sentiment_accuracy": 0.0,
            "data_source": "none",
            "last_evaluated": None
        }

    try:
        with open(files_v1[0], 'r') as f:
            metrics = json.load(f)
        metrics["data_source"] = "evaluation"
        metrics["last_evaluated"] = os.path.getmtime(files_v1[0])
        return metrics
    except Exception:
        return {
            "total_cases": 0,
            "pending_model_eval": 0,
            "evaluated": 0,
            "avg_grounding": 0,
            "hallucination_rate": 0.0,
            "ambiguity_detection_rate": 0.0,
            "intent_accuracy": 0.0,
            "sentiment_accuracy": 0.0,
            "data_source": "none",
            "last_evaluated": None
        }


def _get_chat_message_stats(db: Session) -> Dict[str, Any]:
    """Get live statistics from chat_messages table."""
    stats = {}

    # Total messages
    result = db.execute(func.count(ChatMessage.id))
    stats['total_messages'] = result.scalar() or 0

    # AI vs Human messages
    result = db.execute(
        func.count(ChatMessage.id).filter(ChatMessage.is_ai == True)
    )
    stats['ai_messages'] = result.scalar() or 0

    result = db.execute(
        func.count(ChatMessage.id).filter(ChatMessage.is_ai == False)
    )
    stats['human_messages'] = result.scalar() or 0

    # Messages with intent classification
    result = db.execute(
        func.count(ChatMessage.id).filter(ChatMessage.intent.isnot(None))
    )
    stats['classified_messages'] = result.scalar() or 0

    # Intent distribution
    from sqlalchemy import case
    intent_result = db.execute(text("""
        SELECT intent, COUNT(*) as count
        FROM chat_messages
        WHERE intent IS NOT NULL
        GROUP BY intent
        ORDER BY count DESC
    """))
    stats['intent_distribution'] = [
        {"intent": row[0], "count": row[1]}
        for row in intent_result.fetchall()
    ]

    # Sentiment distribution
    sentiment_result = db.execute(text("""
        SELECT sentiment, COUNT(*) as count
        FROM chat_messages
        WHERE sentiment IS NOT NULL
        GROUP BY sentiment
        ORDER BY count DESC
    """))
    stats['sentiment_distribution'] = [
        {"sentiment": row[0], "count": row[1]}
        for row in sentiment_result.fetchall()
    ]

    # Intent confidence stats
    result = db.execute(text("""
        SELECT
            AVG(intent_confidence) as avg_confidence,
            MIN(intent_confidence) as min_confidence,
            MAX(intent_confidence) as max_confidence
        FROM chat_messages
        WHERE intent_confidence IS NOT NULL
    """))
    row = result.fetchone()
    stats['intent_confidence'] = {
        'average': round(float(row[0]), 3) if row[0] else 0,
        'min': round(float(row[1]), 3) if row[1] else 0,
        'max': round(float(row[2]), 3) if row[2] else 0
    }

    # Sentiment confidence stats
    result = db.execute(text("""
        SELECT
            AVG(sentiment_confidence) as avg_confidence,
            MIN(sentiment_confidence) as min_confidence,
            MAX(sentiment_confidence) as max_confidence
        FROM chat_messages
        WHERE sentiment_confidence IS NOT NULL
    """))
    row = result.fetchone()
    stats['sentiment_confidence'] = {
        'average': round(float(row[0]), 3) if row[0] else 0,
        'min': round(float(row[1]), 3) if row[1] else 0,
        'max': round(float(row[2]), 3) if row[2] else 0
    }

    # Recent activity (last 7 days)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    result = db.execute(text("""
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM chat_messages
        WHERE created_at >= :seven_days_ago
        GROUP BY DATE(created_at)
        ORDER BY date DESC
        LIMIT 7
    """), {"seven_days_ago": seven_days_ago})
    stats['recent_activity'] = [
        {"date": str(row[0]), "count": row[1]}
        for row in result.fetchall()
    ]

    # Total AI responses
    result = db.execute(func.count(ChatMessage.id).filter(
        ChatMessage.is_ai == True,
        ChatMessage.ai_metadata.isnot(None)
    ))
    stats['grounded_responses'] = result.scalar() or 0

    return stats


@router.get("/metrics")
async def get_chat_analytics_metrics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive AI Chat Analyzer performance metrics.
    Combines live database statistics with evaluation results.
    """
    try:
        db_stats = _get_chat_message_stats(db)
        eval_metrics = _get_latest_eval_metrics()

        # Calculate derived metrics
        db_stats['classification_rate'] = (
            round(db_stats['classified_messages'] / db_stats['total_messages'] * 100, 2)
            if db_stats['total_messages'] > 0 else 0
        )

        db_stats['ai_usage_rate'] = (
            round(db_stats['ai_messages'] / db_stats['total_messages'] * 100, 2)
            if db_stats['total_messages'] > 0 else 0
        )

        # Combine with evaluation data
        combined = {
            **db_stats,
            **eval_metrics,
            "generated_at": datetime.utcnow().isoformat(),
            "data_quality": {
                "has_evaluation_data": eval_metrics.get("evaluated", 0) > 0,
                "has_live_data": db_stats['total_messages'] > 0,
                "evaluation_coverage": (
                    eval_metrics.get("evaluated", 0) / eval_metrics.get("total_cases", 1)
                    if eval_metrics.get("total_cases", 0) > 0 else 0
                )
            }
        }

        return {
            "success": True,
            "data": combined
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch AI chat analytics: {str(e)}"
        )


@router.get("/trend")
async def get_chat_trend(
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get chat message trends over the specified period.
    """
    try:
        start_date = datetime.utcnow() - timedelta(days=days)

        # Daily message counts
        result = db.execute(text("""
            SELECT
                DATE(created_at) as date,
                COUNT(*) as total,
                SUM(CASE WHEN is_ai = true THEN 1 ELSE 0 END) as ai_count,
                SUM(CASE WHEN intent IS NOT NULL THEN 1 ELSE 0 END) as classified_count
            FROM chat_messages
            WHERE created_at >= :start_date
            GROUP BY DATE(created_at)
            ORDER BY date ASC
        """), {"start_date": start_date})

        trends = []
        for row in result.fetchall():
            trends.append({
                "date": str(row[0]),
                "total_messages": row[1],
                "ai_messages": row[2] or 0,
                "classified_messages": row[3] or 0
            })

        return {
            "success": True,
            "period": f"Last {days} days",
            "data": trends
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch chat trend: {str(e)}"
        )


@router.get("/intents")
async def get_intent_analysis(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed intent analysis with confidence breakdown.
    """
    try:
        result = db.execute(text("""
            SELECT
                intent,
                COUNT(*) as total,
                AVG(intent_confidence) as avg_confidence,
                MIN(intent_confidence) as min_confidence,
                MAX(intent_confidence) as max_confidence,
                SUM(CASE WHEN intent_confidence >= 0.8 THEN 1 ELSE 0 END) as high_confidence
            FROM chat_messages
            WHERE intent IS NOT NULL
            GROUP BY intent
            ORDER BY total DESC
        """))

        intents = []
        for row in result.fetchall():
            intents.append({
                "intent": row[0],
                "count": row[1],
                "avg_confidence": round(float(row[2]), 3) if row[2] else 0,
                "min_confidence": round(float(row[3]), 3) if row[3] else 0,
                "max_confidence": round(float(row[4]), 3) if row[4] else 0,
                "high_confidence_rate": round(
                    (row[5] / row[1] * 100) if row[1] > 0 else 0, 2
                )
            })

        return {
            "success": True,
            "data": intents,
            "total_classified": sum(i['count'] for i in intents)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch intent analysis: {str(e)}"
        )


@router.get("/sentiment")
async def get_sentiment_analysis(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get sentiment distribution and analysis.
    """
    try:
        result = db.execute(text("""
            SELECT
                sentiment,
                COUNT(*) as total,
                AVG(sentiment_confidence) as avg_confidence,
                SUM(CASE WHEN sentiment_confidence >= 0.7 THEN 1 ELSE 0 END) as high_confidence
            FROM chat_messages
            WHERE sentiment IS NOT NULL
            GROUP BY sentiment
            ORDER BY total DESC
        """))

        sentiments = []
        for row in result.fetchall():
            sentiments.append({
                "sentiment": row[0],
                "count": row[1],
                "percentage": round(
                    (row[1] / sum(r[1] for r in result.fetchall()) * 100)
                    if sum(r[1] for r in result.fetchall()) > 0 else 0, 2
                ),
                "avg_confidence": round(float(row[2]), 3) if row[2] else 0
            })

        return {
            "success": True,
            "data": sentiments
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch sentiment analysis: {str(e)}"
        )
