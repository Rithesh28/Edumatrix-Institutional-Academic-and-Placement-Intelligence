"""
Reminder Model - Stores all reminders scheduled for students
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..core.database import Base
import enum


class ReminderType(str, enum.Enum):
    """Types of reminders"""
    SEVEN_DAY = "7_day"
    THREE_DAY = "3_day"
    ONE_DAY = "1_day"
    DEADLINE_DAY = "deadline_day"
    MISSED_DEADLINE = "missed_deadline"


class ReminderStatus(str, enum.Enum):
    """Status of reminder delivery"""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReminderChannel(str, enum.Enum):
    """Channels through which reminder was sent"""
    IN_APP = "in_app"
    PUSH = "push"
    EMAIL = "email"


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    circular_id = Column(Integer, ForeignKey("circulars.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reminder_type = Column(Enum(ReminderType), nullable=False)
    status = Column(Enum(ReminderStatus), default=ReminderStatus.PENDING)
    channel = Column(Enum(ReminderChannel), nullable=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    circular = relationship("Circular", backref="reminders")
    user = relationship("User", backref="reminders")

    def __repr__(self):
        return f"<Reminder {self.id} - {self.reminder_type} - {self.status}>"