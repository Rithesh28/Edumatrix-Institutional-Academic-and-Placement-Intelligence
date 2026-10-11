"""
Schemas for Safe Placement Test-Data Cleanup Service (Phase 3.4.1)

Provides models for:
- Dependency counts and inspection
- Company cleanup candidate preview
- Explicit execution request and response
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field, ConfigDict


class CleanupDependentCounts(BaseModel):
    """Counts of all dependent records tied to a company and its recruitment drives."""
    jobs_count: int = Field(0, description="Total job postings under company")
    circulars_count: int = Field(0, description="Total recruitment circulars for company")
    circular_job_links_count: int = Field(0, description="Junction links between circulars and jobs")
    applications_count: int = Field(0, description="Total student job applications")
    shortlists_count: int = Field(0, description="Total shortlist table entries")
    rounds_count: int = Field(0, description="Total recruitment rounds configured")
    outcomes_count: int = Field(0, description="Total student round progression outcomes recorded")
    confirmed_outcomes_count: int = Field(0, description="Round outcomes with non-rejected/confirmed status")
    result_batches_count: int = Field(0, description="Total uploaded recruitment result batches")
    result_items_count: int = Field(0, description="Total candidate items in result batches")
    confirmed_result_items_count: int = Field(0, description="Candidate items in confirmed state")
    offers_count: int = Field(0, description="Total verified placement offers extended")
    accepted_offers_count: int = Field(0, description="Offers accepted by students")
    active_offers_count: int = Field(0, description="Offers currently offered or accepted")
    files_count: int = Field(0, description="Total files referenced by circulars, batches or offers")
    shared_files_count: int = Field(0, description="Files also referenced elsewhere in the system (cannot be deleted)")


class CompanyCleanupCandidate(BaseModel):
    """Detailed preview of an explicitly identified company cleanup candidate."""
    company_id: int
    company_name: str
    is_active: bool
    flag_reasons: List[str] = Field(default_factory=list, description="Signals that flagged this company")
    dependent_counts: CleanupDependentCounts
    safety_classification: str = Field(
        ...,
        description="'SAFE_TO_PURGE', 'REQUIRES_ARCHIVE', or 'PROTECTED_GENUINE'"
    )
    protection_reasons: List[str] = Field(
        default_factory=list,
        description="Reasons why purge is blocked if protected or requiring archive"
    )
    affected_student_count: int = Field(0, description="Number of unique students tied to this company's jobs")

    model_config = ConfigDict(from_attributes=True)


class CleanupPreviewSummary(BaseModel):
    """Aggregate totals across all preview candidates."""
    total_candidates_flagged: int
    total_safe_to_purge: int
    total_requires_archive: int
    total_protected_genuine: int
    total_dependent_jobs: int
    total_dependent_circulars: int
    total_dependent_applications: int
    total_dependent_result_batches: int
    total_dependent_offers: int
    total_dependent_accepted_offers: int
    total_files_identified: int
    total_shared_files_preserved: int


class CleanupPreviewResponse(BaseModel):
    """Response model for GET /placement/cleanup/preview."""
    summary: CleanupPreviewSummary
    candidates: List[CompanyCleanupCandidate]


class CleanupExecuteRequest(BaseModel):
    """Request model for POST /placement/cleanup/execute."""
    company_ids: List[int] = Field(..., min_length=1, description="Explicit list of company IDs to clean up")
    mode: str = Field(..., pattern="^(archive|purge)$", description="Execution mode: 'archive' or 'purge'")
    confirmation_phrase: Optional[str] = Field(
        None,
        description="Mandatory confirmation string required for 'purge' mode: 'CONFIRM_PURGE_TEST_DATA'"
    )


class CleanupExecuteResponse(BaseModel):
    """Response model for POST /placement/cleanup/execute."""
    success: bool
    mode: str
    companies_processed: int
    company_ids: List[int]
    records_affected: Dict[str, int] = Field(default_factory=dict)
    audit_log_id: Optional[int] = None
    message: str
