"""
Resume Pydantic Schemas

Defines request/response validation for resume operations.
"""

from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from uuid import UUID


# ============================================
# ENUMS
# ============================================

class ResumeStatusEnum(str, Enum):
    """Resume status enum for schemas."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================
# SUB-SCHEMAS (Nested Structures)
# ============================================

class EducationItem(BaseModel):
    """Education entry schema."""
    degree: Optional[str] = None
    branch: Optional[str] = None
    institution: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    cgpa: Optional[float] = Field(None, ge=0, le=10)


class ExperienceItem(BaseModel):
    """Experience entry schema."""
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None


class ProjectItem(BaseModel):
    """Project entry schema."""
    name: Optional[str] = None
    description: Optional[str] = None
    technologies: Optional[List[str]] = None
    link: Optional[str] = None


class CertificationItem(BaseModel):
    """Certification entry schema."""
    name: Optional[str] = None
    issuer: Optional[str] = None
    year: Optional[int] = None


class InternshipItem(BaseModel):
    """Internship entry schema."""
    title: Optional[str] = None
    company: Optional[str] = None
    duration: Optional[str] = None
    description: Optional[str] = None


class SuggestionItem(BaseModel):
    """Improvement suggestion schema."""
    category: str = Field(..., description="Category: skills, experience, projects, etc.")
    message: str = Field(..., description="Suggestion message")
    priority: str = Field(..., description="Priority: high, medium, low")
    impact: Optional[str] = Field(None, description="Estimated impact on ATS score")


# ============================================
# BASE SCHEMAS
# ============================================

class ResumeBase(BaseModel):
    """Base resume schema."""
    name: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    skills: Optional[List[str]] = Field(default=[])
    education: Optional[List[EducationItem]] = Field(default=[])
    experience: Optional[List[ExperienceItem]] = Field(default=[])
    projects: Optional[List[ProjectItem]] = Field(default=[])
    certifications: Optional[List[CertificationItem]] = Field(default=[])
    internships: Optional[List[InternshipItem]] = Field(default=[])
    additional_data: Optional[Dict[str, Any]] = Field(default={})


class ResumeCreate(BaseModel):
    """Schema for creating a resume (upload)."""
    student_id: int = Field(..., description="Student user ID")
    file_id: UUID = Field(..., description="File ID from MinIO")


class ResumeUpdate(BaseModel):
    """Schema for updating a resume."""
    name: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    skills: Optional[List[str]] = None
    education: Optional[List[EducationItem]] = None
    experience: Optional[List[ExperienceItem]] = None
    projects: Optional[List[ProjectItem]] = None
    certifications: Optional[List[CertificationItem]] = None
    internships: Optional[List[InternshipItem]] = None
    additional_data: Optional[Dict[str, Any]] = None
    ats_score: Optional[float] = Field(None, ge=0, le=100)
    suggestions: Optional[List[SuggestionItem]] = None
    skill_gap: Optional[List[str]] = None
    status: Optional[ResumeStatusEnum] = None


class ResumeUpdateStatus(BaseModel):
    """Schema for updating resume status."""
    status: ResumeStatusEnum = Field(..., description="New status")


# ============================================
# RESPONSE SCHEMAS
# ============================================

class ResumeResponse(BaseModel):
    """Schema for resume response."""
    id: int
    student_id: int
    student_name: Optional[str] = None
    file_id: Optional[UUID] = None
    
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    
    skills: List[str] = []
    education: List[EducationItem] = []
    experience: List[ExperienceItem] = []
    projects: List[ProjectItem] = []
    certifications: List[CertificationItem] = []
    internships: List[InternshipItem] = []
    additional_data: Dict[str, Any] = {}
    
    ats_score: Optional[float] = None
    suggestions: List[SuggestionItem] = []
    skill_gap: List[str] = []
    
    status: ResumeStatusEnum
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class ResumeDetailResponse(ResumeResponse):
    """Detailed resume response with file details."""
    file_details: Optional[Dict[str, Any]] = None
    ats_summary: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(from_attributes=True)


class ResumeUploadResponse(BaseModel):
    """Schema for resume upload response."""
    success: bool
    message: str
    resume_id: Optional[int] = None
    status: ResumeStatusEnum = ResumeStatusEnum.PENDING


# ============================================
# ATS SCORE SCHEMAS
# ============================================

class AtsScoreRequest(BaseModel):
    """Schema for requesting ATS score calculation."""
    job_posting_id: Optional[int] = Field(None, description="Job posting to compare against")


class AtsScoreResponse(BaseModel):
    """Schema for ATS score response."""
    resume_id: int
    student_id: int
    student_name: str
    
    ats_score: float
    skill_match: float = Field(..., description="Skills match percentage")
    education_match: float = Field(..., description="Education match percentage")
    experience_match: float = Field(..., description="Experience match percentage")
    project_match: float = Field(..., description="Projects match percentage")
    certification_match: float = Field(..., description="Certifications match percentage")
    format_score: float = Field(..., description="Resume format score")
    
    suggestions: List[SuggestionItem] = []
    skill_gap: List[str] = []
    
    model_config = ConfigDict(from_attributes=True)


# ============================================
# LISTING SCHEMAS
# ============================================

class ResumeListQuery(BaseModel):
    """Schema for listing resumes with filters."""
    student_id: Optional[int] = Field(None, description="Filter by student ID")
    status: Optional[ResumeStatusEnum] = Field(None, description="Filter by status")
    department: Optional[str] = Field(None, description="Filter by department")
    min_ats_score: Optional[float] = Field(None, ge=0, le=100)
    max_ats_score: Optional[float] = Field(None, ge=0, le=100)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class ResumeListResponse(BaseModel):
    """Schema for listing resumes response."""
    total: int
    limit: int
    offset: int
    resumes: List[ResumeResponse]