from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any, List

class ChatMessageSend(BaseModel):
    receiver_id: int = 0  # 0 indicates AI Assistant
    content: str
    is_ai: Optional[bool] = False

class ChatMessageResponse(BaseModel):
    id: int
    sender_id: Optional[int] = None
    receiver_id: Optional[int] = None
    content: str
    is_read: bool = False
    read_at: Optional[datetime] = None
    created_at: datetime
    is_ai: bool = False
    ai_participant: Optional[str] = None
    intent: Optional[str] = None
    intent_confidence: Optional[float] = None
    sentiment: Optional[str] = None
    sentiment_confidence: Optional[float] = None
    ai_metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True

class ChatConversationResponse(BaseModel):
    user_id: int
    user_name: str
    user_role: str
    last_message: Optional[str] = None
    last_message_time: Optional[datetime] = None
    unread_count: int = 0
    is_ai: bool = False

class AIChatRequest(BaseModel):
    content: str

class AIChatResponse(BaseModel):
    user_message: ChatMessageResponse
    ai_response: ChatMessageResponse
    intent: Optional[str] = None
    intent_confidence: Optional[float] = None
    sentiment: Optional[str] = None
    sentiment_confidence: Optional[float] = None
    retrieval_strategy: Optional[str] = None
    retrieval_sources: Optional[List[Dict[str, Any]]] = None
    ai_metadata: Optional[Dict[str, Any]] = None