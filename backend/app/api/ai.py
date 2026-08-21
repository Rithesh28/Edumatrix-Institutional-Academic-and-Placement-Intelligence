from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..api.auth import get_current_user
from ..models.user import User
from ..services.intent_classifier import intent_classifier
from ..services.sentiment_analyser import sentiment_analyser
import logging

router = APIRouter(prefix="/ai", tags=["AI"])

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntentRequest(BaseModel):
    text: str

class IntentResponse(BaseModel):
    intent: str
    confidence: float
    all_scores: dict = {}

class SentimentResponse(BaseModel):
    sentiment: str
    confidence: float
    probabilities: dict = {}
    error: str = None

@router.post("/classify-intent", response_model=IntentResponse)
async def classify_intent(
    request: IntentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Classify the intent of a student's question"""
    
    result = intent_classifier.predict(request.text)
    logger.info(f"Intent classification: {result['intent']} (conf: {result['confidence']})")
    
    return IntentResponse(
        intent=result["intent"],
        confidence=result["confidence"],
        all_scores=result.get("all_scores", {})
    )

@router.post("/analyse-sentiment", response_model=SentimentResponse)
async def analyse_sentiment(
    request: IntentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Analyse the sentiment of a student's message"""
    
    logger.info(f"Analysing sentiment for: {request.text[:50]}...")
    
    result = sentiment_analyser.analyse(request.text)
    
    logger.info(f"Sentiment result: {result.get('sentiment')} (conf: {result.get('confidence')})")
    
    return SentimentResponse(
        sentiment=result.get("sentiment", "neutral"),
        confidence=result.get("confidence", 0.5),
        probabilities=result.get("probabilities", {}),
        error=result.get("error", None)
    )

@router.get("/health")
async def ai_health():
    """Check if AI models are loaded"""
    return {
        "intent_classifier_loaded": intent_classifier.is_loaded,
        "sentiment_analyser_loaded": sentiment_analyser.is_loaded,
        "status": "healthy" if (intent_classifier.is_loaded or sentiment_analyser.is_loaded) else "degraded"
    }