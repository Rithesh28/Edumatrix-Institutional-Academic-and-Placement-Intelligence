"""
Placement Pydantic Schemas

Defines request/response validation for placement operations:
- Companies
- Job Postings
- Applications
- Shortlists
"""

from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


# ============================================
# ENUMS
# ============================================

class JobStatus(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"


class ApplicationStatus(str, Enum):
    APPLIED = "applied"
    SHORTLISTED = "shortlisted"
    REJECTED = "rejected"
    SELECTED = "selected"


# ============================================
# COMPANY SCHEMAS
# ============================================

class CompanyBase(BaseModel):
    """Base company schema."""
    name: str = Field(..., max_length=255, description="Company name")
    description: Optional[str] = Field(None, description="Company description")
    website: Optional[str] = Field(None, max_length=255, description="Company website")
    industry: Optional[str] = Field(None, max_length=100, description="Industry type")
    location: Optional[str] = Field(None, max_length=255, description="Company location")
    contact_email: Optional[str] = Field(None, max_length=255, description="Contact email")
    contact_phone: Optional[str] = Field(None, max_length=50, description="Contact phone")
    logo_url: Optional[str] = Field(None, max_length=500, description="Company logo URL")
    is_active: bool = Field(True, description="Whether company is active")


class CompanyCreate(CompanyBase):
    """Schema for creating a company."""
    pass


class CompanyUpdate(BaseModel):
    """Schema for updating a company."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    website: Optional[str] = Field(None, max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=50)
    logo_url: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class CompanyResponse(CompanyBase):
    """Schema for company response."""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Additional fields
    job_count: Optional[int] = Field(0, description="Number of job postings")
    
    model_config = ConfigDict(from_attributes=True)


# ============================================
# JOB POSTING SCHEMAS
# ============================================

class JobPostingBase(BaseModel):
    """Base job posting schema."""
    company_id: int = Field(..., description="Company ID")
    title: str = Field(..., max_length=255, description="Job title")
    description: Optional[str] = Field(None, description="Job description")
    required_skills: List[str] = Field(default=[], description="Required skills")
    experience_level: Optional[str] = Field(None, max_length=50, description="Experience level required")
    cgpa_criteria: Optional[float] = Field(None, ge=0, le=10, description="Minimum CGPA requirement")
    branch_eligibility: List[str] = Field(default=[], description="Eligible branches")
    location: Optional[str] = Field(None, max_length=255, description="Job location")
    salary_range: Optional[str] = Field(None, max_length=100, description="Salary range")
    application_deadline: Optional[datetime] = Field(None, description="Application deadline")
    drive_date: Optional[datetime] = Field(None, description="Placement drive date")
    status: JobStatus = Field(JobStatus.OPEN, description="Job status")


class JobPostingCreate(JobPostingBase):
    """Schema for creating a job posting."""
    created_by: Optional[int] = Field(None, description="User ID who created")


class JobPostingUpdate(BaseModel):
    """Schema for updating a job posting."""
    company_id: Optional[int] = None
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    required_skills: Optional[List[str]] = None
    experience_level: Optional[str] = Field(None, max_length=50)
    cgpa_criteria: Optional[float] = Field(None, ge=0, le=10)
    branch_eligibility: Optional[List[str]] = None
    location: Optional[str] = Field(None, max_length=255)
    salary_range: Optional[str] = Field(None, max_length=100)
    application_deadline: Optional[datetime] = None
    drive_date: Optional[datetime] = None
    status: Optional[JobStatus] = None


class JobPostingResponse(JobPostingBase):
    id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Additional fields from relationships
    company_name: Optional[str] = None  # Make sure this exists
    applications_count: Optional[int] = Field(0, description="Number of applications")
    shortlisted_count: Optional[int] = Field(0, description="Number of shortlisted students")
    
    model_config = ConfigDict(from_attributes=True)


# ============================================
# APPLICATION SCHEMAS
# ============================================

class ApplicationBase(BaseModel):
    """Base application schema."""
    student_id: int = Field(..., description="Student user ID")
    job_posting_id: int = Field(..., description="Job posting ID")
    status: ApplicationStatus = Field(ApplicationStatus.APPLIED, description="Application status")
    eligibility_score: Optional[float] = Field(None, ge=0, le=100, description="Eligibility score")
    match_percentage: Optional[float] = Field(None, ge=0, le=100, description="AI match percentage")
    notes: Optional[str] = Field(None, description="Additional notes")


class ApplicationCreate(ApplicationBase):
    """Schema for creating an application."""
    pass


class ApplicationUpdate(BaseModel):
    """Schema for updating an application."""
    status: Optional[ApplicationStatus] = None
    eligibility_score: Optional[float] = Field(None, ge=0, le=100)
    match_percentage: Optional[float] = Field(None, ge=0, le=100)
    notes: Optional[str] = None


class ApplicationResponse(ApplicationBase):
    """Schema for application response."""
    id: int
    applied_at: datetime
    updated_at: Optional[datetime] = None
    
    # Additional fields from relationships
    student_name: Optional[str] = None
    student_email: Optional[str] = None
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# ============================================
# SHORTLIST SCHEMAS
# ============================================

class ShortlistBase(BaseModel):
    """Base shortlist schema."""
    student_id: int = Field(..., description="Student user ID")
    company_id: int = Field(..., description="Company ID")
    job_posting_id: int = Field(..., description="Job posting ID")
    reason: Optional[str] = Field(None, description="Reason for shortlisting")
    shortlisted_by: Optional[int] = Field(None, description="User ID who shortlisted")


class ShortlistCreate(ShortlistBase):
    """Schema for creating a shortlist entry."""
    pass


class ShortlistUpdate(BaseModel):
    """Schema for updating a shortlist entry."""
    reason: Optional[str] = None


class ShortlistResponse(ShortlistBase):
    """Schema for shortlist response."""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Additional fields from relationships
    student_name: Optional[str] = None
    student_email: Optional[str] = None
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    shortlister_name: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# ============================================
# DASHBOARD & STATISTICS SCHEMAS
# ============================================

class PlacementStatistics(BaseModel):
    """Schema for placement statistics."""
    total_companies: int
    active_companies: int
    total_jobs: int
    open_jobs: int
    total_applications: int
    total_shortlists: int
    total_students: int
    placement_rate: Optional[float] = Field(None, description="Placement rate percentage")
    
    # Breakdowns
    applications_by_status: Dict[str, int] = Field(default={})
    jobs_by_status: Dict[str, int] = Field(default={})


class CompanyStatistics(BaseModel):
    """Schema for company statistics."""
    company_id: int
    company_name: str
    total_jobs: int
    total_applications: int
    total_shortlists: int
    total_selected: int


class StudentPlacementStatus(BaseModel):
    """Schema for student placement status."""
    student_id: int
    student_name: str
    email: str
    branch: Optional[str] = None
    cgpa: Optional[float] = None
    
    total_applications: int
    shortlisted_count: int
    selected_count: int
    status: str = Field(description= "not_applied, applied, shortlisted, selected")
    
    applications: List[ApplicationResponse] = []


# ============================================
# MATCHING & ELIGIBILITY SCHEMAS
# ============================================

class StudentEligibility(BaseModel):
    """Schema for student eligibility check."""
    student_id: int
    student_name: str
    email: str
    branch: str
    cgpa: float
    
    is_eligible: bool
    eligibility_reasons: List[str] = Field(default=[], description="Reasons for eligibility/ineligibility")
    match_score: float = Field(..., ge=0, le=100, description="Overall match score")
    
    skill_match: float = Field(..., ge=0, le=100, description="Skill match percentage")
    cgpa_match: bool = Field(..., description="Whether CGPA criteria is met")
    branch_match: bool = Field(..., description="Whether branch criteria is met")
    
    missing_skills: List[str] = Field(default=[], description="Skills the student is missing")
    matched_skills: List[str] = Field(default=[], description="Skills the student has")


class JobMatchRequest(BaseModel):
    """Schema for matching request."""
    job_posting_id: int
    student_ids: Optional[List[int]] = None  # If None, check all students


class JobMatchResponse(BaseModel):
    """Schema for job matching response."""
    job_posting_id: int
    job_title: str
    company_name: str
    
    total_eligible: int
    eligible_students: List[StudentEligibility]
    
    top_candidates: List[StudentEligibility] = Field(default=[], description="Top 10 candidates")