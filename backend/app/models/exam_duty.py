from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Time, Date, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..core.database import Base
import enum


class DutyStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ExamDuty(Base):
    __tablename__ = "exam_duties"

    id = Column(Integer, primary_key=True, index=True)
    lecturer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    hod_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    department = Column(String, nullable=False)
    
    exam_name = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    venue = Column(String, nullable=True)
    
    status = Column(Enum(DutyStatus), default=DutyStatus.PENDING)
    reminder_sent = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    lecturer = relationship("User", foreign_keys=[lecturer_id])
    hod = relationship("User", foreign_keys=[hod_id])