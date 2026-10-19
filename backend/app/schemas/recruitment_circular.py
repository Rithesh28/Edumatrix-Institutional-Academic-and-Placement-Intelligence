"""
Recruitment Circular Pydantic Schemas

Defines request/response validation for company recruitment circular operations:
- Draft creation, update, retrieval, listing
- Attachment association and metadata
- Job link association and metadata
- Safe publication response
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from enum import Enum

from ..models.recruitment_circular import RecruitmentCircularStatus, AttachmentType


# ============================================
# ATTACHMENT SCHEMAS
# ============================================

class CircularAttachmentCreate(BaseModel):
    """Schema for adding an attachment to a circular."""
    file_id: UUID = Field(..., description="UUID of the existing uploaded file")
    attachment_type: AttachmentType = Field(AttachmentType.OTHER, description="Attachment category")
    display_order: int = Field(0, description="Display order for UI rendering")


class CircularAttachmentResponse(BaseModel):
    """Schema for attachment details in response."""
    id: int
    circular_id: int
    file_id: UUID
    attachment_type: str
    display_order: int
    created_at: datetime

    # Populated file metadata
    filename: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    download_url: Optional[str] = None
    preview_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================
# LINKED JOB SCHEMAS
# ============================================

class CircularJobLinkRequest(BaseModel):
    """Schema for linking job postings to a circular."""
    job_posting_ids: List[int] = Field(..., min_length=1, description="List of JobPosting IDs to link")


class CircularJobUnlinkRequest(BaseModel):
    """Schema for unlinking a job posting from a circular."""
    job_posting_id: int = Field(..., description="JobPosting ID to unlink")


class CircularJobResponse(BaseModel):
    """Schema for linked job summary inside circular response."""
    id: int
    circular_id: int
    job_posting_id: int
    created_at: datetime

    # Populated job details
    title: Optional[str] = None
    status: Optional[str] = None
    company_name: Optional[str] = None
    experience_level: Optional[str] = None
    salary_range: Optional[str] = None
    location: Optional[str] = None
    required_skills: Optional[List[str]] = None
    branch_eligibility: Optional[List[str]] = None
    application_deadline: Optional[datetime] = None
    drive_date: Optional[datetime] = None
    application_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================
# CIRCULAR SCHEMAS
# ============================================

class RecruitmentCircularCreate(BaseModel):
    """Schema for creating a recruitment circular draft."""
    company_id: int = Field(..., description="ID of the recruitment drive company")
    title: str = Field(..., min_length=2, max_length=255, description="Circular title")
    summary: Optional[str] = Field(None, description="Drive summary or overview")
    instructions: Optional[str] = Field(None, description="Registration / drive instructions")
    application_deadline: Optional[datetime] = Field(None, description="Application submission deadline")
    drive_date: Optional[datetime] = Field(None, description="Drive or interview date")
    branch_eligibility: Optional[List[str]] = Field(default_factory=list, description="List of eligible engineering branches")
    job_posting_ids: Optional[List[int]] = Field(default_factory=list, description="Initial job postings to link")
    attachments: Optional[List[CircularAttachmentCreate]] = Field(default_factory=list, description="Initial attachments")

    @field_validator("application_deadline", "drive_date", mode="before")
    def clean_empty_dates(cls, v):
        if v == "" or v is None:
            return None
        return v


class RecruitmentCircularUpdate(BaseModel):
    """Schema for updating a recruitment circular draft."""
    title: Optional[str] = Field(None, min_length=2, max_length=255)
    summary: Optional[str] = None
    instructions: Optional[str] = None
    application_deadline: Optional[datetime] = None
    drive_date: Optional[datetime] = None
    branch_eligibility: Optional[List[str]] = None
    company_id: Optional[int] = None

    @field_validator("application_deadline", "drive_date", mode="before")
    def clean_empty_dates(cls, v):
        if v == "" or v is None:
            return None
        return v


# ============================================
# REDESIGNED RECRUITMENT DRIVE WORKFLOW SCHEMAS
# ============================================

class DriveCandidateMatchItem(BaseModel):
    row_index: int
    source_filename: str
    extracted_usn: Optional[str] = None
    extracted_name: Optional[str] = None
    extracted_email: Optional[str] = None
    extracted_branch: Optional[str] = None
    matched_student_id: Optional[int] = None
    matched_student_name: Optional[str] = None
    matched_student_usn: Optional[str] = None
    matched_student_email: Optional[str] = None
    matched_student_branch: Optional[str] = None
    match_confidence: float = 0.0
    match_method: Optional[str] = None
    match_evidence: Optional[Any] = None
    review_status: str  # "matched", "ambiguous", "unmatched"
    is_duplicate: bool = False
    is_confirmed: bool = False


class DriveCandidateSummary(BaseModel):
    total: int = 0
    matched: int = 0
    ambiguous: int = 0
    unmatched: int = 0
    duplicate: int = 0


class DriveAttachmentFileInfo(BaseModel):
    file_id: UUID
    filename: str
    file_size: Optional[int] = None
    content_type: Optional[str] = None


class DriveParseShortlistResponse(BaseModel):
    description: str
    candidates: List[DriveCandidateMatchItem] = []
    candidate_summary: DriveCandidateSummary
    attachment_files: List[DriveAttachmentFileInfo] = []


class CreateAndPostDriveRequest(BaseModel):
    company_id: int
    title: Optional[str] = None
    description: str
    branch_eligibility: List[str] = []
    linked_job_ids: List[int] = []
    drive_date: Optional[datetime] = None
    attachment_file_ids: List[UUID] = []
    candidates: List[Dict[str, Any]] = []

    @field_validator("drive_date", mode="before")
    def clean_drive_date(cls, v):
        if v == "" or v is None:
            return None
        return v


class CreateAndPostDriveResponse(BaseModel):
    success: bool
    circular: "RecruitmentCircularResponse"
    notified_students_count: int
    candidates_count: int
    message: str


class RecruitmentCircularResponse(BaseModel):
    """Full recruitment circular response schema."""
    id: int
    company_id: int
    company_name: Optional[str] = None
    company_logo_url: Optional[str] = None
    title: str
    summary: Optional[str] = None
    instructions: Optional[str] = None
    application_deadline: Optional[datetime] = None
    drive_date: Optional[datetime] = None
    branch_eligibility: Optional[List[str]] = []
    status: RecruitmentCircularStatus
    created_by: Optional[int] = None
    creator_name: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    published_at: Optional[datetime] = None

    attachments: List[CircularAttachmentResponse] = []
    linked_jobs: List[CircularJobResponse] = []
    linked_jobs_count: int = 0
    attachments_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class RecruitmentCircularPublishResponse(BaseModel):
    """Response returned upon successful atomic circular publication."""
    success: bool
    circular: RecruitmentCircularResponse
    published_jobs_count: int
    message: str


# ============================================
# DRIVE REPORT SCHEMAS (STAGE 3.4.3)
# ============================================

class RoleApplicationSummary(BaseModel):
    """Application breakdown per linked job role."""
    job_posting_id: int
    job_title: str
    total_applications: int
    applications_by_status: Dict[str, int]
    external_confirmed_count: int


class RoundOutcomeSummary(BaseModel):
    """Recruitment round outcome summary per round and role."""
    round_id: int
    round_number: int
    round_name: str
    round_type: str
    job_posting_id: int
    job_title: str
    cleared_count: int
    rejected_count: int
    absent_count: int
    on_hold_count: int
    total_outcomes: int


class DriveOffersSummary(BaseModel):
    """Drive-level verified offer metrics."""
    total_offers: int
    offered_count: int
    accepted_count: int
    declined_count: int
    rescinded_count: int
    unique_students_with_offers: int
    unique_students_placed: int  # >= 1 ACCEPTED offer per institutional accounting


class DriveReportResponse(BaseModel):
    """Full drive placement report response."""
    circular_id: int
    circular_title: str
    company_id: int
    company_name: str
    linked_roles_count: int

    # Executive counts
    unique_applicants_count: int
    total_applications_count: int
    external_confirmations_count: int

    # Placed accounting (institutional standard: strictly active accepted offers)
    verified_placed_students_count: int
    total_verified_offers_count: int

    # Categorical breakdowns
    applications_by_status: Dict[str, int]
    applications_by_role: List[RoleApplicationSummary]
    branch_breakdown: Dict[str, int]
    rounds_summary: List[RoundOutcomeSummary]
    offers_summary: DriveOffersSummary

    generated_at: datetime


CreateAndPostDriveResponse.model_rebuild()

