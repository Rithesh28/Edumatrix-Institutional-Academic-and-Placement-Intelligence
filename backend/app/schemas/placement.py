"""
Placement Pydantic Schemas

Defines request/response validation for placement operations:
- Companies
- Job Postings
- Applications
- Shortlists
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from enum import Enum
from uuid import UUID



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

INVALID_COMPANY_PLACEHOLDERS = {"general", "not specified", "n/a", "none", "unknown", "placeholder", "-"}


class CompanyBase(BaseModel):
    """Base company schema."""
    name: str = Field(..., min_length=1, max_length=255, description="Company name")
    description: Optional[str] = Field(None, description="Company description")
    website: Optional[str] = Field(None, max_length=255, description="Company website")
    industry: str = Field(..., min_length=1, max_length=100, description="Industry type")
    location: str = Field(..., min_length=1, max_length=255, description="Company location")
    contact_email: Optional[str] = Field(None, max_length=255, description="Contact email")
    contact_phone: Optional[str] = Field(None, max_length=50, description="Contact phone")
    logo_url: Optional[str] = Field(None, max_length=500, description="Company logo URL")
    is_active: bool = Field(True, description="Whether company is active")

    @field_validator("name", "industry", "location")
    @classmethod
    def validate_non_blank_string(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v_clean = v.strip()
        if not v_clean:
            raise ValueError("Field cannot be blank or whitespace-only")
        if v_clean.lower() in INVALID_COMPANY_PLACEHOLDERS:
            raise ValueError(f"Placeholder values such as '{v_clean}' are not permitted. Please specify an actual value.")
        return v_clean


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

    @field_validator("name", "industry", "location")
    @classmethod
    def validate_optional_non_blank_string(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_clean = v.strip()
            if not v_clean:
                raise ValueError("Field cannot be blank or whitespace-only")
            if v_clean.lower() in INVALID_COMPANY_PLACEHOLDERS:
                raise ValueError(f"Placeholder values such as '{v_clean}' are not permitted. Please specify an actual value.")
            return v_clean
        return v


class CompanyResponse(CompanyBase):
    """Schema for company response."""
    id: int
    industry: Optional[str] = Field(None, description="Industry type")
    location: Optional[str] = Field(None, description="Company location")
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Additional fields
    job_count: Optional[int] = Field(0, description="Number of job postings")
    
    model_config = ConfigDict(from_attributes=True)


import urllib.parse


def validate_http_or_https_url(v: Optional[str]) -> Optional[str]:
    """Validate that the URL uses http or https and has a valid domain, rejecting unsafe schemes."""
    if v is None:
        return None
    v_clean = v.strip()
    if not v_clean:
        return None
    parsed = urllib.parse.urlparse(v_clean)
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError("Application URL must use http or https scheme (unsafe schemes like javascript: or file: are rejected)")
    if not parsed.netloc:
        raise ValueError("Application URL must include a valid host or domain")
    if "." not in parsed.netloc and parsed.netloc != "localhost":
        raise ValueError("Application URL must include a valid domain name")
    return v_clean


# ============================================
# JOB POSTING SCHEMAS
# ============================================

class JobAttachmentResponse(BaseModel):
    """Schema for attached job document response."""
    id: int
    file_id: UUID
    filename: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class JobPostingBase(BaseModel):
    """Base job posting schema."""
    company_id: int = Field(..., description="Company ID")
    title: str = Field(..., max_length=255, description="Job title")
    description: Optional[str] = None
    file_id: Optional[UUID] = Field(None, description="Optional attached document file ID (UUID from files table)")
    required_skills: List[str] = Field(default=[], description="Required skills")
    preferred_skills: List[str] = Field(default=[], description="Preferred skills")
    experience_level: Optional[str] = Field(None, max_length=50, description="Experience level required")
    cgpa_criteria: Optional[float] = Field(None, ge=0, le=10, description="Minimum CGPA requirement")
    branch_eligibility: List[str] = Field(default=[], description="Eligible branches")
    location: Optional[str] = Field(None, max_length=255, description="Job location")
    salary_range: Optional[str] = Field(None, max_length=100, description="Salary range")
    application_url: Optional[str] = Field(None, max_length=2048, description="Official external company application URL")
    application_deadline: Optional[datetime] = Field(None, description="Application deadline")
    drive_date: Optional[datetime] = Field(None, description="Placement drive date")
    status: JobStatus = Field(JobStatus.DRAFT, description="Job status")

    @field_validator("application_url")
    @classmethod
    def check_application_url(cls, v: Optional[str]) -> Optional[str]:
        return validate_http_or_https_url(v)


class JobPostingCreate(JobPostingBase):
    """Schema for creating a job posting."""
    created_by: Optional[int] = Field(None, description="User ID who created")
    attachment_file_ids: Optional[List[UUID]] = Field(default=None, description="Optional list of attached document UUIDs from files table")


class JobPostingUpdate(BaseModel):
    """Schema for updating a job posting."""
    company_id: Optional[int] = None
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    file_id: Optional[UUID] = Field(None, description="Optional attached document file ID (UUID from files table)")
    attachment_file_ids: Optional[List[UUID]] = Field(default=None, description="Optional list of attached document UUIDs from files table")
    required_skills: Optional[List[str]] = None
    preferred_skills: Optional[List[str]] = None
    experience_level: Optional[str] = Field(None, max_length=50)
    cgpa_criteria: Optional[float] = Field(None, ge=0, le=10)
    branch_eligibility: Optional[List[str]] = None
    location: Optional[str] = Field(None, max_length=255)
    salary_range: Optional[str] = Field(None, max_length=100)
    application_url: Optional[str] = Field(None, max_length=2048)
    application_deadline: Optional[datetime] = None
    drive_date: Optional[datetime] = None
    status: Optional[JobStatus] = None

    @field_validator("application_url")
    @classmethod
    def check_application_url(cls, v: Optional[str]) -> Optional[str]:
        return validate_http_or_https_url(v)


class JobPostingResponse(JobPostingBase):
    id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Additional fields from relationships
    company_name: Optional[str] = None  # Make sure this exists
    file_name: Optional[str] = Field(None, description="Filename of attached document if present")
    attachments: List[JobAttachmentResponse] = Field(default=[], description="List of all attached job documents")
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


class ApplicationCreate(BaseModel):
    """Schema for creating an application."""
    student_id: Optional[int] = Field(None, description="Student user ID (server derives from authenticated user)")
    job_posting_id: int = Field(..., description="Job posting ID")
    status: Optional[ApplicationStatus] = Field(ApplicationStatus.APPLIED, description="Application status")
    eligibility_score: Optional[float] = Field(None, ge=0, le=100, description="Untrusted client preview score - ignored by server")
    match_percentage: Optional[float] = Field(None, ge=0, le=100, description="Untrusted client preview score - ignored by server")
    notes: Optional[str] = Field(None, description="Additional notes")


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
    student_branch: Optional[str] = None
    student_cgpa: Optional[float] = None
    student_usn: Optional[str] = None
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    company_id: Optional[int] = None
    job_deadline: Optional[datetime] = None
    job_status: Optional[str] = None
    
    # Recruitment progression and offers
    recruitment_progression: Optional[List[Dict[str, Any]]] = None
    verified_offer: Optional[Dict[str, Any]] = None
    
    # Authoritative Snapshot & Warning
    match_snapshot: Optional[Dict[str, Any]] = Field(None, description="Immutable application-time snapshot")
    has_low_match_warning: Optional[bool] = Field(None, description="Whether required skill match is below 50%")
    low_match_warning: Optional[str] = Field(None, description="Low skill match warning message")

    # External Application Confirmation
    external_applied_at: Optional[datetime] = Field(None, description="Timestamp when student confirmed external submission")
    is_external_confirmed: bool = Field(False, description="Whether student confirmed external submission")

    @model_validator(mode="after")
    def compute_is_external_confirmed(self) -> "ApplicationResponse":
        if self.external_applied_at is not None:
            self.is_external_confirmed = True
        return self

    @field_validator("match_snapshot", mode="before")
    @classmethod
    def validate_match_snapshot(cls, v):
        if v is not None and not isinstance(v, dict):
            return None
        return v

    @field_validator("low_match_warning", mode="before")
    @classmethod
    def validate_low_match_warning(cls, v):
        if v is not None and not isinstance(v, str):
            return None
        return v

    @field_validator("has_low_match_warning", mode="before")
    @classmethod
    def validate_has_low_match_warning(cls, v):
        if v is not None and not isinstance(v, bool):
            return None
        return v
    
    model_config = ConfigDict(from_attributes=True)


# ============================================
# SHORTLIST SCHEMAS
# ============================================

class ShortlistBase(BaseModel):
    """Base shortlist schema."""
    student_id: int = Field(..., description="Student user ID")
    company_id: Optional[int] = Field(None, description="Company ID (auto-resolved from job posting relationship if omitted)")
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
    company_id: int
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
    """Schema for placement statistics, including both legacy and verified accounting metrics."""
    total_companies: int
    active_companies: int
    total_jobs: int
    open_jobs: int
    total_applications: int
    total_shortlists: int
    total_students: int
    total_placed: int = Field(0, description="Unique students placed/selected (legacy)")
    placement_rate: Optional[float] = Field(None, description="Placement rate percentage (legacy)")
    
    # Breakdowns
    applications_by_status: Dict[str, int] = Field(default={})
    jobs_by_status: Dict[str, int] = Field(default={})

    # Phase F: Recruitment Drives & Authoritative Progression Metrics
    total_recruitment_drives: int = Field(0, description="Total recruitment circulars / drives")
    total_rounds: int = Field(0, description="Total recruitment rounds")
    total_outcomes: int = Field(0, description="Total recorded student round outcomes")
    students_shortlisted: int = Field(0, description="Distinct students shortlisted")
    students_selected: int = Field(0, description="Distinct students selected")

    # Verified Placement Accounting Metrics (Phase 3.3.4)
    legacy_placed_count: int = Field(0, description="Legacy placed student count")
    legacy_placement_rate: Optional[float] = Field(None, description="Legacy placement rate percentage")
    total_verified_offers: int = Field(0, description="Total verified offers created")
    verified_offers_count: int = Field(0, description="Total verified offers created (alias)")
    accepted_offers_count: int = Field(0, description="Total offers accepted by students")
    declined_offers_count: int = Field(0, description="Total offers declined by students")
    rescinded_offers_count: int = Field(0, description="Total offers rescinded")
    pending_offers_count: int = Field(0, description="Total offers awaiting student response")
    verified_placed_students_count: int = Field(0, description="Unique students with >= 1 verified accepted offer")
    students_with_multiple_offers_count: int = Field(0, description="Unique students with multiple active verified offers")
    verified_placement_rate: Optional[float] = Field(None, description="Verified placement rate percentage")



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
    match_score: Optional[float] = Field(None, ge=0, le=100, description="Overall match score (None if no skill requirements)")
    
    skill_match: Optional[float] = Field(None, ge=0, le=100, description="Skill match percentage (None if no skill requirements)")
    cgpa_match: bool = Field(..., description="Whether CGPA criteria is met")
    branch_match: bool = Field(..., description="Whether branch criteria is met")
    
    missing_skills: List[str] = Field(default=[], description="Skills the student is missing")
    matched_skills: List[str] = Field(default=[], description="Skills the student has")
    
    # Detailed Breakdown for Phase 3.2 Matching Foundation
    required_total: int = Field(default=0, description="Total required skills count")
    required_matched: int = Field(default=0, description="Matched required skills count")
    required_missing: int = Field(default=0, description="Missing required skills count")
    preferred_total: int = Field(default=0, description="Total preferred skills count")
    preferred_matched: int = Field(default=0, description="Matched preferred skills count")
    preferred_missing: int = Field(default=0, description="Missing preferred skills count")
    
    required_score: Optional[float] = Field(default=None, ge=0, le=100, description="Required skills score percentage")
    preferred_score: Optional[float] = Field(default=None, ge=0, le=100, description="Preferred skills score percentage")
    overall_skill_match: Optional[float] = Field(default=None, ge=0, le=100, description="80% required + 20% preferred skill match score")
    
    matched_required_skills: List[str] = Field(default=[], description="Matched required skills")
    matched_preferred_skills: List[str] = Field(default=[], description="Matched preferred skills")
    missing_required_skills: List[str] = Field(default=[], description="Missing required skills")
    missing_preferred_skills: List[str] = Field(default=[], description="Missing preferred skills")
    semantic_matches: List[Dict[str, Any]] = Field(default=[], description="Details of semantic skill matches")
    
    # Low Match Warning (<50% required skill match)
    has_low_match_warning: bool = Field(default=False, description="Whether required skill match is below 50%")
    low_match_warning: Optional[str] = Field(default=None, description="Warning message for low skill match")
    
    # Traceability for Phase 3.2 Audit
    resume_id: Optional[int] = Field(default=None, description="Resume ID used for matching")
    resume_filename: Optional[str] = Field(default=None, description="Filename of resume used")
    skill_sources: Dict[str, List[str]] = Field(default={}, description="Sources of student skills (profile_skills, resume_skills)")

    # Phase D Match Explanations & Granular Status
    eligibility_status: str = Field(default="eligible", description="Authoritative eligibility status: eligible, ineligible, or incomplete_data")
    missing_criteria: List[str] = Field(default=[], description="List of missing criteria causing incomplete_data or ineligibility")
    skill_match_explanations: List[Dict[str, Any]] = Field(default=[], description="Comprehensive explanation entries for all matched skills (exact, synonym, semantic)")


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
    all_candidates: List[StudentEligibility] = Field(default=[], description="All evaluated candidates including ineligible")


# ============================================
# JD PARSER SCHEMAS
# ============================================

class JdParseRequest(BaseModel):
    """Schema for JD text parsing request."""
    text: Optional[str] = Field(None, description="Raw job description text")


class JdParseResponse(BaseModel):
    """Schema for parsed JD extraction result."""
    # Core job requirements (100% backward compatible)
    title: Optional[str] = Field(None, description="Extracted job title")
    description: Optional[str] = Field(None, description="Extracted job summary or description")
    required_skills: List[str] = Field(default=[], description="Extracted required skills")
    preferred_skills: List[str] = Field(default=[], description="Extracted preferred skills")
    experience_level: Optional[str] = Field(None, description="Extracted experience level (e.g. fresher, 1-3 years)")
    cgpa_criteria: Optional[float] = Field(None, description="Extracted minimum CGPA criteria (0-10 scale)")
    branch_eligibility: List[str] = Field(default=[], description="Extracted eligible branches")
    location: Optional[str] = Field(None, description="Extracted job location")
    salary_range: Optional[str] = Field(None, description="Extracted salary or CTC range")
    raw_text_length: int = Field(default=0, description="Length of processed JD text")

    # General-purpose extended fields (Phase 3.2 Step C Improvement)
    company_name: Optional[str] = Field(None, description="Extracted company or organization name")
    job_type: Optional[str] = Field(None, description="Job / employment type (e.g. Full-Time, Internship, Internship + Full-Time)")
    degree_eligibility: List[str] = Field(default=[], description="Eligible degrees (e.g. B.E, B.Tech, M.Tech, MCA)")
    graduation_years: List[Union[int, str]] = Field(default=[], description="Eligible passing out / batch years (e.g. ['2025', '2026'])")
    
    # Academic percentage criteria across tiers
    academic_percentages: Optional[Dict[str, Optional[float]]] = Field(
        default=None,
        description="Minimum percentage requirements across academic tiers: tenth, twelfth, diploma, degree, postgraduate"
    )
    backlog_criteria: Optional[str] = Field(None, description="Extracted backlog / arrear criteria")
    certifications: List[str] = Field(default=[], description="Preferred or required professional certifications")
    
    # Compensation and Staged Package Breakdown
    compensation_details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured compensation details including currency, stipend, CTC, and staged progression"
    )
    
    # Dates and Deadlines
    application_deadline: Optional[str] = Field(None, description="Extracted registration / application deadline")
    drive_date: Optional[str] = Field(None, description="Extracted placement drive date")
    joining_date: Optional[str] = Field(None, description="Extracted joining or commencement date")
    
    # Workplace & Agreements
    work_mode: Optional[str] = Field(None, description="Work mode (On-site, Hybrid, Remote)")
    bond_details: Optional[str] = Field(None, description="Service agreement or bond duration/terms")
    selection_rounds: List[str] = Field(default=[], description="Selection / interview rounds")
    application_instructions: Optional[str] = Field(None, description="Instructions or portal link for applying")
    application_url: Optional[str] = Field(None, description="Extracted external application URL (http/https)")
    
    # File Persistence and Multi-Document Linkage (Phase C)
    file_id: Optional[UUID] = Field(None, description="Persisted primary File ID in files table")
    file_name: Optional[str] = Field(None, description="Filename of the persisted primary file")
    file_ids: List[UUID] = Field(default=[], description="List of all persisted file IDs for multiple uploads")
    file_names: List[str] = Field(default=[], description="List of filenames of all persisted files")
    extracted_files: List[Dict[str, Any]] = Field(default=[], description="Per-file extraction breakdown and source tracking")
    extraction_status: str = Field(default="success", description="Overall extraction outcome: success, partial, or failed")

    # Verification, Auditability & Quality Assurance
    review_flags: List[str] = Field(
        default=[],
        description="Actionable review warnings and ambiguity flags for Placement Officer confirmation"
    )
    field_evidence: Dict[str, Any] = Field(
        default={},
        description="Source text snippets justifying each extracted field for full auditability"
    )


# ============================================
# BULK DELETION SCHEMAS (Phase C)
# ============================================

class CompanyBulkDeleteRequest(BaseModel):
    """Request payload for multi-select company deletion."""
    company_ids: List[int] = Field(..., min_length=1, description="List of company IDs to delete")
    mode: str = Field("soft", description="Deletion mode: 'soft' (deactivate company and jobs) or 'hard' (permanent delete)")


class CompanyBulkDeleteResultItem(BaseModel):
    """Result per company in bulk deletion."""
    id: int
    name: Optional[str] = None
    success: bool
    status: str  # "deactivated", "deleted", "blocked", "not_found"
    message: str
    dependent_counts: Optional[Dict[str, int]] = None


class CompanyBulkDeleteResponse(BaseModel):
    """Summary response for bulk company deletion."""
    total_requested: int
    successful_count: int
    failed_count: int
    deleted_count: Optional[int] = 0
    deactivated_count: Optional[int] = 0
    blocked_count: Optional[int] = 0
    results: List[CompanyBulkDeleteResultItem]


class JobBulkDeleteRequest(BaseModel):
    """Request payload for multi-select job deletion."""
    job_ids: List[int] = Field(..., min_length=1, description="List of job IDs to delete")
    force: bool = Field(False, description="Whether to close jobs with applications instead of blocking")


class JobBulkDeleteResultItem(BaseModel):
    """Result per job in bulk deletion."""
    id: int
    title: Optional[str] = None
    success: bool
    status: str  # "deleted", "closed", "blocked", "not_found"
    message: str
    dependent_counts: Optional[Dict[str, int]] = None


class JobBulkDeleteResponse(BaseModel):
    """Summary response for bulk job deletion."""
    total_requested: int
    successful_count: int
    failed_count: int
    deleted_count: Optional[int] = 0
    closed_count: Optional[int] = 0
    blocked_count: Optional[int] = 0
    results: List[JobBulkDeleteResultItem]


# ============================================
# PLACEMENT OFFER SCHEMAS (Phase 3.3.4)
# ============================================

class PlacementOfferCreate(BaseModel):
    """Schema for creating / verifying a placement offer by Placement Officer."""
    application_id: int = Field(..., description="Target Application ID")
    student_id: Optional[int] = Field(None, description="Optional student ID for cross-validation")
    job_posting_id: Optional[int] = Field(None, description="Optional job posting ID for cross-validation")
    ctc_lpa: Optional[float] = Field(None, gt=0, description="Annual Cost to Company in LPA (must be > 0)")
    designation: Optional[str] = Field(None, max_length=255, description="Offered role designation")
    offer_letter_file_id: Optional[UUID] = Field(None, description="Supporting offer letter document UUID")
    offer_date: Optional[datetime] = Field(None, description="Offer issuance date")


class PlacementOfferUpdate(BaseModel):
    """Schema for updating offer terms by Placement Officer."""
    ctc_lpa: Optional[float] = Field(None, gt=0, description="Revised CTC in LPA (must be > 0)")
    designation: Optional[str] = Field(None, max_length=255, description="Revised designation")
    offer_letter_file_id: Optional[UUID] = Field(None, description="Revised offer letter document UUID")
    offer_date: Optional[datetime] = Field(None, description="Revised offer date")
    reason: Optional[str] = Field(None, description="Mandatory audit rationale for modifying terms")


class PlacementOfferResponseRequest(BaseModel):
    """Schema for student responding to their own placement offer."""
    decision: str = Field(..., description="Student response decision: ACCEPTED or DECLINED")
    remarks: Optional[str] = Field(None, description="Optional student comments or remarks")


class PlacementOfferRescindRequest(BaseModel):
    """Schema for authorized officer rescinding an offer."""
    reason: str = Field(..., min_length=3, description="Mandatory administrative reason for rescission")


class PlacementOfferResponse(BaseModel):
    """Schema for detailed placement offer response."""
    id: int
    application_id: int
    student_id: int
    job_posting_id: int
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    student_name: Optional[str] = None
    student_email: Optional[str] = None
    ctc_lpa: Optional[float] = None
    designation: Optional[str] = None
    acceptance_status: str
    offer_letter_file_id: Optional[UUID] = None
    offer_date: Optional[datetime] = None
    response_date: Optional[datetime] = None
    verified_by: Optional[int] = None
    rescission_reason: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================
# RECRUITMENT ROUND & PROGRESSION SCHEMAS (Phase 3.3.5)
# ============================================

class RecruitmentRoundCreate(BaseModel):
    """Schema for creating a recruitment round."""
    round_number: int = Field(..., gt=0, description="Sequential round number (must be > 0)")
    name: str = Field(..., min_length=1, max_length=100, description="Round title or name")
    round_type: Optional[str] = Field("assessment", max_length=50, description="Round type (e.g. assessment, technical, hr)")
    is_final: Optional[bool] = Field(False, description="Whether this is the final recruitment round")
    round_date: Optional[datetime] = Field(None, description="Scheduled date for the round")


class RecruitmentRoundResponse(BaseModel):
    """Schema for recruitment round details."""
    id: int
    job_posting_id: int
    round_number: int
    name: str
    round_type: str
    is_final: bool
    round_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    outcomes_count: Optional[int] = 0

    class Config:
        from_attributes = True


class StudentRoundOutcomeCorrectionRequest(BaseModel):
    """Schema for officer correcting an authoritative student round outcome."""
    new_outcome: str = Field(..., description="Target outcome: cleared, rejected, absent, on_hold, offered")
    new_score: Optional[float] = Field(None, description="Optional revised score")
    reason: str = Field(..., min_length=3, description="Mandatory audit rationale for correcting outcome")


class StudentProgressionItem(BaseModel):
    """Schema for a single round outcome in student progression history."""
    outcome_id: int
    application_id: int
    job_posting_id: int
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    round_id: int
    round_number: int
    round_name: str
    round_type: str
    is_final_round: bool
    round_date: Optional[str] = None
    outcome: str
    score: Optional[float] = None
    remarks: Optional[str] = None
    confirmed_at: Optional[str] = None
    has_offer: bool = False
    offer_status: Optional[str] = None
    offer_ctc_lpa: Optional[float] = None


# ============================================
# SAFE PLACEMENT TEST-DATA CLEANUP SCHEMAS (Phase 3.4.1)
# ============================================

from .placement_cleanup import (
    CleanupDependentCounts,
    CompanyCleanupCandidate,
    CleanupPreviewSummary,
    CleanupPreviewResponse,
    CleanupExecuteRequest,
    CleanupExecuteResponse,
)


