from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float, JSON
from sqlalchemy.sql import func
from ..core.database import Base

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # AI Assistant Support
    is_ai = Column(Boolean, default=False, nullable=False, index=True)
    ai_participant = Column(String(50), nullable=True)  # e.g. "assistant"
    intent = Column(String(50), nullable=True)
    intent_confidence = Column(Float, nullable=True)
    sentiment = Column(String(50), nullable=True)
    sentiment_confidence = Column(Float, nullable=True)
    ai_metadata = Column(JSON, nullable=True)