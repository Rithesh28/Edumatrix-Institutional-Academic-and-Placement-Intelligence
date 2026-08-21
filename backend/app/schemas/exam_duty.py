from pydantic import BaseModel
from datetime import date, time, datetime
from typing import Optional, List
from enum import Enum


class DutyStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ExamDutyCreate(BaseModel):
    lecturer_id: int
    exam_name: str
    date: date
    start_time: time
    end_time: time


class ExamDutyUpdate(BaseModel):
    exam_name: Optional[str] = None
    date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    status: Optional[DutyStatus] = None


class ExamDutyResponse(BaseModel):
    id: int
    lecturer_id: int
    hod_id: int
    department: str
    exam_name: str
    date: date
    start_time: time
    end_time: time
    status: DutyStatus
    reminder_sent: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Additional fields for frontend
    lecturer_name: Optional[str] = None
    hod_name: Optional[str] = None

    class Config:
        from_attributes = True


class ExamDutyUploadResponse(BaseModel):
    total_extracted: int
    matched: int
    created: int
    conflicts: int
    duties: List[ExamDutyResponse]
    unmatched_lecturers: List[str] = []


# ✅ ADD THIS - Missing class
class ExamDutyParseResult(BaseModel):
    """Result from the parser"""
    success: bool
    created: int
    skipped: int
    conflicts: List[dict]
    errors: List[str]
    message: str
    unmatched_lecturers: List[str] = []


# ✅ ADD THIS - Missing class
class ExamDutyParsePreview(BaseModel):
    """Preview of parsed data before saving"""
    raw_text: Optional[str] = None
    parsed_duties: List[dict]
    faculty_names: List[str]
    dates: List[str]
    times: List[str]
    venues: List[str]
    total_duties: int


# ✅ ADD THIS - Missing class
class ExamDutyConflict(BaseModel):
    """Conflict information"""
    duty_id: int
    lecturer_id: int
    lecturer_name: Optional[str] = None
    date: date
    exam_name: str
    start_time: time
    end_time: time
    conflicting_duty_id: int
    conflicting_exam: str
    conflict_type: str