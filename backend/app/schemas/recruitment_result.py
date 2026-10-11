"""
Recruitment Result Pydantic Schemas

Schemas for result batches, tabular items, manual match overrides,
and confirmation responses.
"""

from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class RecruitmentResultItemBase(BaseModel):
    row_index: int
    source_page: Optional[int] = None
    raw_data: Dict[str, Any]
    extracted_usn: Optional[str] = None
    extracted_name: Optional[str] = None
    extracted_email: Optional[str] = None
    extracted_status_raw: Optional[str] = None
    extracted_remarks: Optional[str] = None
    normalized_status: str = "shortlisted"


class RecruitmentResultItemResponse(RecruitmentResultItemBase):
    id: int
    batch_id: int
    matched_student_id: Optional[int] = None
    matched_student_name: Optional[str] = None
    matched_student_email: Optional[str] = None
    matched_student_usn: Optional[str] = None
    matched_student_branch: Optional[str] = None
    match_confidence: float = 0.0
    match_method: Optional[str] = None
    match_evidence: Optional[Dict[str, Any]] = None
    review_status: str
    confirmed_by: Optional[int] = None
    confirmed_at: Optional[datetime] = None
    notification_sent: bool = False

    model_config = ConfigDict(from_attributes=True)


class RecruitmentResultBatchCreate(BaseModel):
    company_id: int
    job_posting_id: Optional[int] = None
    circular_id: Optional[int] = None
    round_name: str
    round_type: Optional[str] = "assessment"
    is_final_round: Optional[bool] = False


class RecruitmentResultBatchResponse(BaseModel):
    id: int
    company_id: int
    company_name: Optional[str] = None
    job_posting_id: Optional[int] = None
    job_title: Optional[str] = None
    circular_id: Optional[int] = None
    circular_title: Optional[str] = None
    file_id: UUID
    filename: Optional[str] = None
    round_name: str
    round_type: str
    is_final_round: bool
    status: str
    total_rows: int
    matched_count: int
    ambiguous_count: int
    confirmed_count: int
    uploaded_by: Optional[int] = None
    uploader_name: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    items: Optional[List[RecruitmentResultItemResponse]] = None

    model_config = ConfigDict(from_attributes=True)


class RecruitmentResultItemMatchUpdate(BaseModel):
    student_id: Optional[int] = None
    review_status: Optional[str] = None  # matched, ambiguous, unresolved, ignored


class RecruitmentResultBatchConfirmRequest(BaseModel):
    item_ids: Optional[List[int]] = None  # Specific items to confirm; if empty, all resolved matched items


class RecruitmentResultConfirmResponse(BaseModel):
    batch_id: int
    confirmed_count: int
    notifications_dispatched: int
    skipped_count: int
    is_final_round: bool
    batch_status: str
    message: str


class StudentSearchItem(BaseModel):
    id: int
    name: str
    email: str
    usn: Optional[str] = None
    branch: Optional[str] = None
    cgpa: Optional[float] = None
    year: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)
