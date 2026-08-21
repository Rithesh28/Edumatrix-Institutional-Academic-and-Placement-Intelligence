"""
Reminder Schemas - Pydantic models for request/response validation
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum


class ReminderType(str, Enum):
    SEVEN_DAY = "7_day"
    THREE_DAY = "3_day"
    ONE_DAY = "1_day"
    DEADLINE_DAY = "deadline_day"
    MISSED_DEADLINE = "missed_deadline"


class ReminderStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReminderChannel(str, Enum):
    IN_APP = "in_app"
    PUSH = "push"
    EMAIL = "email"


class ReminderCreate(BaseModel):
    circular_id: Optional[int] = None
    user_id: int
    reminder_type: ReminderType
    scheduled_at: datetime


class ReminderUpdate(BaseModel):
    status: Optional[ReminderStatus] = None
    channel: Optional[ReminderChannel] = None
    sent_at: Optional[datetime] = None


class ReminderResponse(BaseModel):
    id: int
    circular_id: Optional[int] = None
    user_id: int
    reminder_type: ReminderType
    status: ReminderStatus
    channel: Optional[ReminderChannel] = None
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    # Additional fields for frontend display
    circular_title: Optional[str] = None
    circular_content: Optional[str] = None
    circular_due_date: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReminderCountResponse(BaseModel):
    total: int
    pending: int
    sent: int
    failed: int


class UnreadReminderCountResponse(BaseModel):
    count: int