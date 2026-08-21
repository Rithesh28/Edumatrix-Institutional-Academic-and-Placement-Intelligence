from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum, UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from ..core.database import Base
import enum
import uuid

class CircularType(str, enum.Enum):
    EXAM = "exam"
    ASSIGNMENT = "assignment"
    GENERAL = "general"

class Circular(Base):
    __tablename__ = "circulars"
    
    id = Column(Integer, primary_key=True, index=True)
    lecturer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(Enum(CircularType), default=CircularType.GENERAL)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    file_url = Column(String, nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # NEW: File attachment fields
    file_id = Column(PGUUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"), nullable=True)
    file_type = Column(String(50), nullable=True)
    
    # Relationships
    lecturer = relationship("User", foreign_keys=[lecturer_id])
    file = relationship("File", foreign_keys=[file_id])