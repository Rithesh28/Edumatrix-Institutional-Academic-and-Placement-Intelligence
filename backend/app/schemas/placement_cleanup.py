"""
Schemas for Safe Placement Test-Data Cleanup Service (Phase 3.4.1 & Drive Bulk Management)

Provides models for:
- Dependency counts and inspection
- Company cleanup candidate preview
- Recruitment drive (circular) cleanup candidate preview
- Orphaned job cleanup candidate preview
- Explicit execution request and response
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, model_validator


class CleanupDependentCounts(BaseModel):
    """Counts of all dependent records tied to a company, recruitment drive, or role."""
    jobs_count: int = Field(0, description="Total job postings under company or drive")
    circulars_count: int = Field(0, description="Total recruitment circulars")
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
    can_purge: bool = Field(False, description="True only if safety_classification == 'SAFE_TO_PURGE'")
    linked_job_titles: List[str] = Field(default_factory=list, description="Titles of linked job postings")
    linked_circular_titles: List[str] = Field(default_factory=list, description="Titles of linked recruitment drives")
    records_breakdown: Optional[Dict[str, int]] = Field(default=None, description="Exact counts of records to be deleted, archived, or preserved")

    model_config = ConfigDict(from_attributes=True)


class DriveCleanupCandidate(BaseModel):
    """Detailed preview of an explicitly identified recruitment drive (circular) cleanup candidate."""
    circular_id: int
    title: str
    status: str
    company_id: int
    company_name: str
    drive_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    flag_reasons: List[str] = Field(default_factory=list, description="Signals that flagged this drive")
    linked_job_ids: List[int] = Field(default_factory=list, description="IDs of linked jobs")
    linked_job_titles: List[str] = Field(default_factory=list, description="Titles of linked jobs")
    dependent_counts: CleanupDependentCounts
    safety_classification: str = Field(
        ...,
        description="'SAFE_TO_PURGE', 'REQUIRES_ARCHIVE', or 'PROTECTED_GENUINE'"
    )
    protection_reasons: List[str] = Field(
        default_factory=list,
        description="Reasons why purge is blocked if protected or requiring archive"
    )
    affected_student_count: int = Field(0, description="Number of unique students tied to this drive")
    can_purge: bool = Field(False, description="True only if safety_classification == 'SAFE_TO_PURGE'")
    exclusive_job_roles: List[str] = Field(default_factory=list, description="Roles exclusive to this drive")
    shared_job_roles: List[str] = Field(default_factory=list, description="Roles shared with other drives")

    model_config = ConfigDict(from_attributes=True)


class OrphanedJobCleanupCandidate(BaseModel):
    """Detailed preview of an orphaned test job not linked to any active drive."""
    job_id: int
    title: str
    company_id: int
    company_name: str
    status: str
    applications_count: int = 0
    safety_classification: str = "SAFE_TO_PURGE"
    protection_reasons: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class CleanupPreviewSummary(BaseModel):
    """Aggregate totals across all preview candidates."""
    total_candidates_flagged: int = 0
    total_safe_to_purge: int = 0
    total_requires_archive: int = 0
    total_protected_genuine: int = 0
    total_dependent_jobs: int = 0
    total_dependent_circulars: int = 0
    total_dependent_applications: int = 0
    total_dependent_result_batches: int = 0
    total_dependent_offers: int = 0
    total_dependent_accepted_offers: int = 0
    total_files_identified: int = 0
    total_shared_files_preserved: int = 0
    # Additional drive-specific breakdown metrics
    total_drives_flagged: int = 0
    total_drives_safe_to_purge: int = 0
    total_drives_requires_archive: int = 0
    total_drives_protected_genuine: int = 0
    total_orphaned_jobs: int = 0


class CleanupPreviewResponse(BaseModel):
    """Response model for GET /placement/cleanup/preview and /placement/cleanup/drives/preview."""
    summary: CleanupPreviewSummary
    candidates: List[CompanyCleanupCandidate] = Field(default_factory=list)
    drives: List[DriveCleanupCandidate] = Field(default_factory=list)
    orphaned_jobs: List[OrphanedJobCleanupCandidate] = Field(default_factory=list)


class CleanupExecuteRequest(BaseModel):
    """Request model for POST /placement/cleanup/execute."""
    company_ids: Optional[List[int]] = Field(None, description="Explicit list of company IDs to clean up")
    circular_ids: Optional[List[int]] = Field(None, description="Explicit list of recruitment drive IDs to clean up")
    orphaned_job_ids: Optional[List[int]] = Field(None, description="Optional list of orphaned job IDs to clean up")
    mode: str = Field(..., pattern="^(archive|purge)$", description="Execution mode: 'archive' or 'purge'")
    confirmation_phrase: Optional[str] = Field(
        None,
        description="Mandatory confirmation string required for 'purge' mode: 'CONFIRM_PURGE_TEST_DATA'"
    )

    @model_validator(mode="after")
    def validate_targets(self):
        c_ids = self.company_ids or []
        circ_ids = self.circular_ids or []
        orph_ids = self.orphaned_job_ids or []
        if not c_ids and not circ_ids and not orph_ids:
            raise ValueError("At least one target (company_ids, circular_ids, or orphaned_job_ids) must have items to clean up.")
        return self


class CleanupExecuteResponse(BaseModel):
    """Response model for POST /placement/cleanup/execute."""
    success: bool
    mode: str
    companies_processed: int = 0
    drives_processed: int = 0
    company_ids: List[int] = Field(default_factory=list)
    circular_ids: List[int] = Field(default_factory=list)
    records_affected: Dict[str, int] = Field(default_factory=dict)
    skipped_records: List[Dict[str, Any]] = Field(default_factory=list)
    audit_log_id: Optional[int] = None
    message: str
