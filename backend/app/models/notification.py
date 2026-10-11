from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from ..core.database import Base

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String, nullable=False)  # circular, message, doubt, deadline, exam_nudge
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    reference_id = Column(Integer, nullable=True)  # ID of related object (circular_id, message_id, etc.)
    event_key = Column(String(255), nullable=True, unique=True, index=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())