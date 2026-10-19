"""
Placement API Endpoints

Provides REST API for placement operations:
- Company management
- Job posting management
- Application management
- Shortlist management
- Eligibility checking
- Statistics and reports
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Response, File, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, subqueryload
from typing import List, Optional, Any, Dict
from uuid import UUID
import uuid
import os
import io
import csv
from datetime import datetime
import logging

from ..core.database import get_db
from ..core.config import settings
from ..api.auth import get_current_user, get_current_placement_officer
from ..models.user import User, UserRole
from ..models.company import Company
from ..models.job_posting import JobPosting, JobStatus, JobPostingAttachment
from ..models.file import File as FileModel, FileStatus, FileType
from ..models.application import Application
from ..models.shortlist import Shortlist
from ..models.profile import StudentProfileExtended, Skill, Project
from ..models.certification import Certification
from ..models.resume import Resume
from ..models.recruitment_circular import RecruitmentCircular, RecruitmentCircularJob
from ..models.audit_log import AuditLog
from ..models.recruitment_round import (
    PlacementOffer,
    OfferAcceptanceStatus,
    RecruitmentRound,
    StudentRoundOutcome,
)
from ..schemas.placement import (
    CompanyCreate, CompanyUpdate, CompanyResponse,
    CompanyBulkDeleteRequest, CompanyBulkDeleteResponse,
    JobPostingCreate, JobPostingUpdate, JobPostingResponse,
    JobBulkDeleteRequest, JobBulkDeleteResponse,
    ApplicationCreate, ApplicationUpdate, ApplicationResponse,
    ShortlistCreate, ShortlistUpdate, ShortlistResponse,
    PlacementStatistics, CompanyStatistics, StudentPlacementStatus,
    StudentEligibility, JobMatchRequest, JobMatchResponse,
    JdParseRequest, JdParseResponse,
    PlacementOfferCreate, PlacementOfferUpdate,
    PlacementOfferResponseRequest, PlacementOfferRescindRequest,
    PlacementOfferResponse,
    RecruitmentRoundCreate, RecruitmentRoundResponse,
    StudentRoundOutcomeCorrectionRequest, StudentProgressionItem,
    CleanupPreviewResponse, CleanupExecuteRequest, CleanupExecuteResponse,
)
from ..services.placement_service import placement_service
from ..services.jd_parser_service import jd_parser_service
from ..services.file_storage.file_service import file_service
from ..services.placement_offer_service import placement_offer_service
from ..services.recruitment_progression_service import recruitment_progression_service
from ..services.placement_cleanup_service import placement_cleanup_service

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/placement", tags=["Placement"])


# ============================================
# HELPER FUNCTIONS
# ============================================

def check_placement_officer_or_admin(current_user: User):
    """Check if user is placement officer or admin."""
    if current_user.role not in [UserRole.ADMIN, UserRole.PLACEMENT_OFFICER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Placement Officers and Admins can perform this action"
        )
    return current_user


# ============================================
# COMPANY ENDPOINTS
# ============================================

@router.post("/companies", response_model=CompanyResponse)
async def create_company(
    company_data: CompanyCreate,
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db)
):
    """Create a new company."""
    company = placement_service.create_company(db, company_data, current_user.id)
    return CompanyResponse.model_validate(company)


@router.get("/companies", response_model=List[CompanyResponse])
async def get_companies(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all companies."""
    companies = placement_service.get_companies(db, skip, limit, is_active)
    return [CompanyResponse.model_validate(c) for c in companies]


@router.get("/companies/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a company by ID."""
    company = placement_service.get_company(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return CompanyResponse.model_validate(company)


@router.put("/companies/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: int,
    company_data: CompanyUpdate,
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db)
):
    """Update a company."""
    company = placement_service.update_company(db, company_id, company_data)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return CompanyResponse.model_validate(company)


@router.delete("/companies/{company_id}")
async def delete_company(
    company_id: int,
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db)
):
    """Delete a company (soft delete)."""
    result = placement_service.delete_company(db, company_id)
    if not result:
        raise HTTPException(status_code=404, detail="Company not found")
    return {"message": "Company deleted successfully"}


@router.post("/companies/bulk-delete", response_model=CompanyBulkDeleteResponse)
async def bulk_delete_companies(
    request: CompanyBulkDeleteRequest,
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db)
):
    """
    Bulk delete or deactivate companies with relationship-aware safety handling.
    - 'soft' mode: Deactivates companies and closes open jobs.
    - 'hard' mode: Permanently deletes only if zero applications/circulars/offers exist.
    """
    if not request.company_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one company ID must be provided."
        )
    result = placement_service.bulk_delete_companies(db, request.company_ids, mode=request.mode)
    return CompanyBulkDeleteResponse(**result)


# ============================================
# JOB POSTING ENDPOINTS
# ============================================

@router.post("/jobs", response_model=JobPostingResponse)
async def create_job_posting(
    job_data: JobPostingCreate,
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db)
):
    """Create a new job posting."""
    try:
        job = placement_service.create_job_posting(db, job_data, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    response = JobPostingResponse.model_validate(job)
    if job.company:
        response.company_name = job.company.name
    if job.file:
        response.file_name = job.file.filename
    return response


@router.get("/jobs", response_model=List[JobPostingResponse])
async def get_job_postings(
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all job postings."""
    # RBAC: Students can ONLY view OPEN jobs (drafts are hidden from students)
    if current_user.role == UserRole.STUDENT:
        status = JobStatus.OPEN.value

    jobs = placement_service.get_job_postings(db, skip, limit, company_id, status)
    responses = []
    for job in jobs:
        response = JobPostingResponse.model_validate(job)
        if job.company:
            response.company_name = job.company.name
        if job.file:
            response.file_name = job.file.filename
        responses.append(response)
    return responses


@router.get("/jobs/{job_id}", response_model=JobPostingResponse)
async def get_job_posting(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a job posting by ID."""
    job = placement_service.get_job_posting(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found")
    
    # RBAC: Students cannot view draft jobs
    if current_user.role == UserRole.STUDENT and job.status != JobStatus.OPEN:
        raise HTTPException(status_code=404, detail="Job posting not found")

    response = JobPostingResponse.model_validate(job)
    if job.company:
        response.company_name = job.company.name
    if job.file:
        response.file_name = job.file.filename
    return response


@router.put("/jobs/{job_id}", response_model=JobPostingResponse)
async def update_job_posting(
    job_id: int,
    job_data: JobPostingUpdate,
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db)
):
    """Update a job posting."""
    try:
        job = placement_service.update_job_posting(db, job_id, job_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found")
    response = JobPostingResponse.model_validate(job)
    if job.company:
        response.company_name = job.company.name
    if job.file:
        response.file_name = job.file.filename
    return response


@router.delete("/jobs/{job_id}")
async def delete_job_posting(
    job_id: int,
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db)
):
    """Delete a job posting safely. Blocks deletion if applications exist."""
    try:
        result = placement_service.delete_job_posting(db, job_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Job posting not found")
    return {"message": "Job posting deleted successfully"}


@router.post("/jobs/bulk-delete", response_model=JobBulkDeleteResponse)
async def bulk_delete_jobs(
    request: JobBulkDeleteRequest,
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db)
):
    """
    Bulk delete or close job postings with relationship-aware safety handling.
    - Jobs with zero applications/circulars are permanently deleted.
    - Jobs with applications/circulars: closed if force=True, blocked if force=False.
    """
    if not request.job_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one job ID must be provided."
        )
    result = placement_service.bulk_delete_jobs(db, request.job_ids, force=request.force)
    return JobBulkDeleteResponse(**result)


@router.get("/jobs/{job_id}/files/{file_id}/download")
async def download_job_file(
    job_id: int,
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Download a file attached to a job posting.
    Enforces RBAC:
    - Admins and Placement Officers have full access.
    - Students have access only if the job is OPEN and matches their branch eligibility.
    """
    job = placement_service.get_job_posting(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found")

    attached_ids = []
    if job.file_id:
        attached_ids.append(job.file_id)
    if job.attachments:
        attached_ids.extend([att.file_id for att in job.attachments])

    if file_id not in attached_ids:
        raise HTTPException(status_code=404, detail="File is not attached to this job posting")

    if current_user.role == UserRole.STUDENT:
        if job.status != JobStatus.OPEN:
            raise HTTPException(status_code=404, detail="Job posting not found")
        if job.eligible_branches and len(job.eligible_branches) > 0:
            student_branch = None
            if current_user.student_profile and current_user.student_profile.branch:
                student_branch = current_user.student_profile.branch
            elif current_user.department:
                student_branch = current_user.department
            target_branches = {str(b).strip().lower() for b in job.eligible_branches if b}
            if not student_branch or str(student_branch).strip().lower() not in target_branches:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: You are not eligible for this job posting.")
    elif current_user.role not in [UserRole.ADMIN, UserRole.PLACEMENT_OFFICER]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    result = file_service.download_file(db, file_id)
    if not result:
        raise HTTPException(status_code=404, detail="File content not found")

    content = result['content']
    filename = result['filename']
    mime_type = result['mime_type']

    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(content))
        }
    )


@router.get("/jobs/{job_id}/files/{file_id}/preview")
async def preview_job_file(
    job_id: int,
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Preview (inline display) a file attached to a job posting.
    Enforces RBAC:
    - Admins and Placement Officers have full access.
    - Students have access only if the job is OPEN and matches their branch eligibility.
    """
    job = placement_service.get_job_posting(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found")

    attached_ids = []
    if job.file_id:
        attached_ids.append(job.file_id)
    if job.attachments:
        attached_ids.extend([att.file_id for att in job.attachments])

    if file_id not in attached_ids:
        raise HTTPException(status_code=404, detail="File is not attached to this job posting")

    if current_user.role == UserRole.STUDENT:
        if job.status != JobStatus.OPEN:
            raise HTTPException(status_code=404, detail="Job posting not found")
        if job.eligible_branches and len(job.eligible_branches) > 0:
            student_branch = None
            if current_user.student_profile and current_user.student_profile.branch:
                student_branch = current_user.student_profile.branch
            elif current_user.department:
                student_branch = current_user.department
            target_branches = {str(b).strip().lower() for b in job.eligible_branches if b}
            if not student_branch or str(student_branch).strip().lower() not in target_branches:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: You are not eligible for this job posting.")
    elif current_user.role not in [UserRole.ADMIN, UserRole.PLACEMENT_OFFICER]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    result = file_service.download_file(db, file_id)
    if not result:
        raise HTTPException(status_code=404, detail="File content not found")

    content = result['content']
    filename = result['filename']
    mime_type = result['mime_type']

    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Content-Length": str(len(content))
        }
    )


@router.post("/jobs/parse-jd", response_model=JdParseResponse)
async def parse_job_description(
    request: JdParseRequest,
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db)
):
    """
    Parse a raw Job Description text to extract structured requirements:
    - Required skills
    - Preferred skills
    - Minimum CGPA
    - Eligible branches
    - Experience level, location, salary range
    Allows Placement Officer to review and edit before creating/publishing the job.
    """
    raw_text = request.text.strip() if request and request.text else ""
    if not raw_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job description text is required"
        )
    parsed = jd_parser_service.parse_jd_text(raw_text)
    return JdParseResponse(**parsed)


@router.post("/jobs/upload-jd", response_model=JdParseResponse)
async def upload_job_description(
    files: Optional[List[UploadFile]] = File(None),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db)
):
    """
    Upload one or multiple Job Description files (PDF, DOCX, TXT, PNG, XLSX, etc.)
    Persists uploaded files to storage and extracts structured job requirements
    for Placement Officer review and editing before publication.
    """
    upload_list: List[UploadFile] = []
    if files:
        upload_list.extend([f for f in files if f and f.filename])
    if file and file.filename:
        upload_list.append(file)

    if not upload_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one job document file must be uploaded."
        )

    allowed_extensions = {".pdf", ".docx", ".doc", ".txt", ".png", ".jpg", ".jpeg", ".xlsx", ".xls", ".csv"}
    files_data = []

    for f in upload_list:
        ext = os.path.splitext(f.filename)[1].lower() if f.filename else ""
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{ext}' for file '{f.filename}'. Allowed: {', '.join(sorted(allowed_extensions))}."
            )

        content = await f.read()
        if len(content) > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File '{f.filename}' exceeds maximum allowed size of {settings.MAX_FILE_SIZE // (1024 * 1024)}MB."
            )

        await f.seek(0)
        file_id = None
        try:
            upload_res = await file_service.upload_file(
                db=db,
                file=f,
                uploaded_by=current_user,
                title=f.filename,
                file_type="placement_doc",
                department=current_user.department or "Placement",
                extra_data={"module": "placement", "purpose": "job_document"}
            )
            if upload_res and upload_res.get("file_id"):
                file_id = upload_res["file_id"]
        except Exception as upload_err:
            logger.warning(f"File storage upload failed for {f.filename}: {upload_err}")
            try:
                fallback_file = FileModel(
                    id=uuid.uuid4(),
                    filename=f.filename,
                    file_size=len(content),
                    mime_type=f.content_type or "application/octet-stream",
                    bucket="placement-docs",
                    object_key=f"fallback/{uuid.uuid4()}/{f.filename}",
                    title=f.filename,
                    department=current_user.department or "Placement",
                    file_type=FileType.PLACEMENT_DOC,
                    uploaded_by=current_user.id,
                    version=1,
                    is_latest=True,
                    status=FileStatus.ACTIVE
                )
                db.add(fallback_file)
                db.commit()
                db.refresh(fallback_file)
                file_id = fallback_file.id
            except Exception as db_err:
                db.rollback()
                logger.error(f"Fallback DB file creation failed for {f.filename}: {db_err}")

        files_data.append({
            "content": content,
            "filename": f.filename,
            "file_id": file_id
        })

    try:
        parsed = jd_parser_service.parse_multiple_files(files_data)
        return JdParseResponse(**parsed)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/jobs/{job_id}/publish", response_model=JobPostingResponse)
async def publish_job_posting(
    job_id: int,
    confirm_no_skills: bool = Query(False, description="Explicit confirmation if publishing without skills"),
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db)
):
    """
    Publish a draft job posting (status -> OPEN), making it active for matching.
    Validates that skills exist unless confirm_no_skills=True is explicitly passed.
    """
    try:
        job = placement_service.publish_job_posting(db, job_id, confirm_no_skills=confirm_no_skills)
        if not job:
            raise HTTPException(status_code=404, detail="Job posting not found")
        response = JobPostingResponse.model_validate(job)
        if job.company:
            response.company_name = job.company.name
        return response
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================
# APPLICATION ENDPOINTS
# ============================================

@router.post("/applications", response_model=ApplicationResponse)
async def create_application(
    app_data: ApplicationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new application with server-authoritative scoring and eligibility."""
    # Check if student is applying for themselves
    if current_user.role == UserRole.STUDENT and app_data.student_id and app_data.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only apply on your own behalf"
        )
    
    try:
        application = placement_service.create_application(db, app_data, current_user)
        resp = ApplicationResponse.model_validate(application)
        if application.match_snapshot:
            resp.has_low_match_warning = application.match_snapshot.get("has_low_match_warning", False)
            resp.low_match_warning = application.match_snapshot.get("low_match_warning")
        return resp
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
        elif "already applied" in error_msg.lower():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        elif "not open" in error_msg.lower() or "deadline" in error_msg.lower():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        elif "rejected" in error_msg.lower():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)


@router.get("/applications", response_model=List[ApplicationResponse])
async def get_applications(
    student_id: Optional[int] = Query(None, description="Filter by student ID"),
    job_posting_id: Optional[int] = Query(None, description="Filter by job posting ID"),
    circular_id: Optional[int] = Query(None, description="Filter by recruitment circular ID"),
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    branch: Optional[str] = Query(None, description="Filter by student branch"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search by student name, USN, job title, company"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all applications with role-based scoping and filtering."""
    # Students can only see their own applications
    if current_user.role == UserRole.STUDENT:
        student_id = current_user.id
    
    applications = placement_service.get_applications(
        db, student_id=student_id, job_posting_id=job_posting_id,
        circular_id=circular_id, company_id=company_id, branch=branch,
        status=status, search=search, skip=skip, limit=limit
    )
    results = []
    for a in applications:
        resp = ApplicationResponse.model_validate(a)
        if a.match_snapshot:
            resp.has_low_match_warning = a.match_snapshot.get("has_low_match_warning", False)
            resp.low_match_warning = a.match_snapshot.get("low_match_warning")
        results.append(resp)
    return results


@router.get("/applications/{app_id}", response_model=ApplicationResponse)
async def get_application(
    app_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get an application by ID."""
    application = placement_service.get_application(db, app_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    
    # Check permissions
    if current_user.role == UserRole.STUDENT and application.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own applications"
        )
    
    resp = ApplicationResponse.model_validate(application)
    if application.match_snapshot:
        resp.has_low_match_warning = application.match_snapshot.get("has_low_match_warning", False)
        resp.low_match_warning = application.match_snapshot.get("low_match_warning")
    return resp


@router.put("/applications/{app_id}", response_model=ApplicationResponse)
async def update_application(
    app_id: int,
    app_data: ApplicationUpdate,
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db)
):
    """Update an application status."""
    application = placement_service.update_application(db, app_id, app_data)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return ApplicationResponse.model_validate(application)


@router.post("/applications/{app_id}/confirm-external", response_model=ApplicationResponse)
async def confirm_external_application(
    app_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Idempotently confirm that the student submitted an external application on the company's website.
    Validates ownership, job visibility, and external URL configuration.
    """
    # 1. Fetch application
    application = placement_service.get_application(db, app_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application with ID {app_id} not found"
        )

    # 2. RBAC and Ownership: Only the authenticated student owner can confirm
    if current_user.role != UserRole.STUDENT or application.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only confirm your own applications"
        )

    # 3. Validate job existence and visibility
    job = application.job_posting or placement_service.get_job_posting(db, application.job_posting_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated job posting not found"
        )

    if job.status != JobStatus.OPEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job posting is no longer open for applications"
        )

    # 4. Validate job has external application URL and uses HTTP/HTTPS
    if not job.application_url or not job.application_url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This job posting does not have an external application URL to confirm"
        )
    url_clean = job.application_url.strip().lower()
    if not (url_clean.startswith("http://") or url_clean.startswith("https://")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job application URL must use HTTP or HTTPS protocol"
        )

    # Validate application deadline
    if job.application_deadline:
        from datetime import timezone
        now_utc = datetime.now(timezone.utc)
        deadline = job.application_deadline
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if now_utc > deadline:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Application deadline has passed"
            )

    # 5. Idempotent confirmation
    confirmed_app = placement_service.confirm_external_application(db, application, current_user)
    resp = ApplicationResponse.model_validate(confirmed_app)
    if confirmed_app.match_snapshot:
        resp.has_low_match_warning = confirmed_app.match_snapshot.get("has_low_match_warning", False)
        resp.low_match_warning = confirmed_app.match_snapshot.get("low_match_warning")
    return resp


@router.post("/jobs/{job_id}/confirm-external", response_model=ApplicationResponse)
async def confirm_external_job_application(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Idempotently confirm that the student submitted an external application on the company's website
    directly by job_id. If no application record exists yet, creates one via the server-authoritative
    matching and eligibility workflow before recording the external confirmation.
    """
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can confirm external applications"
        )

    job = placement_service.get_job_posting(db, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job posting #{job_id} not found"
        )

    if job.status != JobStatus.OPEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job posting is no longer open for applications"
        )

    if not job.application_url or not job.application_url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This job posting does not have an external application URL to confirm"
        )

    url_clean = job.application_url.strip().lower()
    if not (url_clean.startswith("http://") or url_clean.startswith("https://")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job application URL must use HTTP or HTTPS protocol"
        )

    # Validate application deadline
    if job.application_deadline:
        from datetime import timezone
        now_utc = datetime.now(timezone.utc)
        deadline = job.application_deadline
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if now_utc > deadline:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Application deadline has passed"
            )

    # Check if application already exists for this student and job
    existing_app = db.query(Application).filter(
        Application.student_id == current_user.id,
        Application.job_posting_id == job_id
    ).first()

    if not existing_app:
        app_create = ApplicationCreate(
            job_posting_id=job_id,
            notes="Applied via external company portal"
        )
        try:
            existing_app = placement_service.create_application(
                db, app_create, current_user, allow_existing=True
            )
        except ValueError as e:
            # Handle race condition or duplicate attempt gracefully
            existing_app = db.query(Application).filter(
                Application.student_id == current_user.id,
                Application.job_posting_id == job_id
            ).first()
            if not existing_app:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )

    confirmed_app = placement_service.confirm_external_application(db, existing_app, current_user)
    resp = ApplicationResponse.model_validate(confirmed_app)
    if confirmed_app.match_snapshot:
        resp.has_low_match_warning = confirmed_app.match_snapshot.get("has_low_match_warning", False)
        resp.low_match_warning = confirmed_app.match_snapshot.get("low_match_warning")
    return resp


# ============================================
# SHORTLIST ENDPOINTS
# ============================================

@router.post("/shortlist", response_model=ShortlistResponse)
async def create_shortlist(
    shortlist_data: ShortlistCreate,
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db)
):
    """Shortlist a student for a job."""
    try:
        shortlist = placement_service.create_shortlist(db, shortlist_data, current_user_id=current_user.id)
        return ShortlistResponse.model_validate(shortlist)
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)


@router.get("/shortlist", response_model=List[ShortlistResponse])
async def get_shortlists(
    student_id: Optional[int] = Query(None, description="Filter by student ID"),
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    job_posting_id: Optional[int] = Query(None, description="Filter by job posting ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all shortlists."""
    # Students can only see their own shortlists
    if current_user.role == UserRole.STUDENT:
        student_id = current_user.id
    
    shortlists = placement_service.get_shortlists(db, student_id, company_id, job_posting_id, skip, limit)
    return [ShortlistResponse.model_validate(s) for s in shortlists]


@router.delete("/shortlist/{shortlist_id}")
async def remove_from_shortlist(
    shortlist_id: int,
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db)
):
    """Remove a student from shortlist."""
    result = placement_service.remove_from_shortlist(db, shortlist_id)
    if not result:
        raise HTTPException(status_code=404, detail="Shortlist entry not found")
    return {"message": "Student removed from shortlist successfully"}


# ============================================
# ELIGIBILITY & MATCHING ENDPOINTS
# ============================================

@router.post("/match", response_model=JobMatchResponse)
@router.post("/jobs/match", response_model=JobMatchResponse)
async def match_students_for_job(
    request: JobMatchRequest,
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db)
):
    """Match students for a job posting."""
    try:
        result = placement_service.match_students_for_job(db, request)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/jobs/{job_id}/check-eligibility/{student_id}", response_model=StudentEligibility)
async def check_student_eligibility(
    job_id: int,
    student_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check if a student is eligible for a job."""
    # Check permissions
    if current_user.role == UserRole.STUDENT and current_user.id != student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only check your own eligibility"
        )
    
    # RBAC: Students can only check eligibility for OPEN jobs
    if current_user.role == UserRole.STUDENT:
        job = placement_service.get_job_posting(db, job_id)
        if not job or job.status != JobStatus.OPEN:
            raise HTTPException(status_code=404, detail="Job posting not found or not open for applications")

    try:
        result = placement_service.check_student_eligibility(db, student_id, job_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ============================================
# STATISTICS & REPORT ENDPOINTS
# ============================================

def sanitize_csv_cell(val: Any) -> Any:
    """Neutralize formula injection by prefixing dangerous characters with a single quote."""
    if val is None:
        return ""
    s = str(val)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{s}"
    return s


@router.get("/reports/export")
async def export_placement_report(
    company_id: Optional[int] = Query(None),
    job_id: Optional[int] = Query(None),
    branch: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export institutional placement report as a downloadable CSV with optional filters and formula injection protection.
    Accessible by Placement Officers and Admins.
    """
    check_placement_officer_or_admin(current_user)

    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except Exception:
            pass
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            if end_dt.hour == 0 and end_dt.minute == 0 and end_dt.second == 0:
                end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        except Exception:
            pass

    users_q = db.query(User).filter(User.role == UserRole.STUDENT)
    if branch:
        users_q = users_q.outerjoin(StudentProfileExtended, User.id == StudentProfileExtended.user_id).filter(
            (func.lower(StudentProfileExtended.branch) == branch.strip().lower()) |
            (func.lower(User.department) == branch.strip().lower())
        )
    users = users_q.all()

    output = io.StringIO()
    writer = csv.writer(output)

    # CSV Header
    header = [
        "Student ID",
        "Student Name",
        "Enrollment Number",
        "Email",
        "Department / Branch",
        "Year",
        "Semester",
        "CGPA",
        "Placement Status",
        "ATS Score",
        "Total Applications",
        "Total Shortlists",
        "Applied Job Titles",
        "Skills",
        "Verified Offers Count",
        "Accepted Offer CTC (LPA)",
        "Offer Acceptance Status",
    ]
    writer.writerow([sanitize_csv_cell(h) for h in header])

    for u in users:
        profile = db.query(StudentProfileExtended).filter(StudentProfileExtended.user_id == u.id).first()
        skills = db.query(Skill).filter(Skill.student_id == profile.id).all() if profile else []
        latest_resume = db.query(Resume).filter(Resume.student_id == u.id).order_by(Resume.created_at.desc()).first()

        apps_q = db.query(Application).filter(Application.student_id == u.id)
        if company_id:
            apps_q = apps_q.join(JobPosting, Application.job_posting_id == JobPosting.id).filter(
                JobPosting.company_id == company_id
            )
        if job_id:
            apps_q = apps_q.filter(Application.job_posting_id == job_id)
        if start_dt:
            apps_q = apps_q.filter(Application.created_at >= start_dt)
        if end_dt:
            apps_q = apps_q.filter(Application.created_at <= end_dt)
        apps = apps_q.all()

        sl_q = db.query(Shortlist).filter(Shortlist.student_id == u.id)
        if company_id:
            sl_q = sl_q.filter(Shortlist.company_id == company_id)
        if job_id:
            sl_q = sl_q.filter(Shortlist.job_posting_id == job_id)
        shortlists = sl_q.all()

        # If filtering by company or job, skip students who have no applications or shortlists for that scope
        if (company_id or job_id) and len(apps) == 0 and len(shortlists) == 0:
            continue

        # Determine placement status
        status_val = "not_applied"
        if any(a.status == "selected" or (hasattr(a.status, "value") and a.status.value == "selected") for a in apps):
            status_val = "selected"
        elif len(shortlists) > 0 or any(a.status == "shortlisted" or (hasattr(a.status, "value") and a.status.value == "shortlisted") for a in apps):
            status_val = "shortlisted"
        elif len(apps) > 0:
            status_val = "applied"
        elif profile and profile.placement_status:
            status_val = profile.placement_status.value if hasattr(profile.placement_status, "value") else str(profile.placement_status)

        # Filter by status if requested
        if status:
            target_status = status.strip().lower()
            if status_val.lower() != target_status and not (target_status == "placed" and status_val.lower() == "selected"):
                continue

        student_skills_list = [s.name for s in skills] + (latest_resume.skills if (latest_resume and latest_resume.skills) else [])
        skills_str = ", ".join(dict.fromkeys(student_skills_list))

        applied_jobs = []
        for a in apps:
            job = db.query(JobPosting).filter(JobPosting.id == a.job_posting_id).first()
            if job and job.title:
                applied_jobs.append(job.title)
        jobs_str = "; ".join(applied_jobs)

        # Verified Offer Details
        offers_q = db.query(PlacementOffer).filter(
            PlacementOffer.student_id == u.id,
            PlacementOffer.acceptance_status != OfferAcceptanceStatus.RESCINDED
        )
        if company_id:
            offers_q = offers_q.join(JobPosting, PlacementOffer.job_posting_id == JobPosting.id).filter(
                JobPosting.company_id == company_id
            )
        if job_id:
            offers_q = offers_q.filter(PlacementOffer.job_posting_id == job_id)
        offers = offers_q.all()

        accepted_offer = next((o for o in offers if o.acceptance_status == OfferAcceptanceStatus.ACCEPTED), None)
        accepted_ctc_str = f"{accepted_offer.ctc_lpa:.2f}" if (accepted_offer and accepted_offer.ctc_lpa is not None) else ""
        if accepted_offer:
            offer_status_str = "ACCEPTED"
        elif len(offers) > 0:
            offer_status_str = offers[0].acceptance_status.value.upper()
        else:
            offer_status_str = "NONE"

        row = [
            u.id,
            profile.full_name if (profile and profile.full_name) else u.name,
            profile.enrollment_number if profile else "",
            u.email,
            profile.branch if (profile and profile.branch) else (u.department or "General"),
            profile.year if profile else "",
            profile.semester if profile else "",
            f"{profile.cgpa:.2f}" if (profile and profile.cgpa is not None) else "",
            status_val,
            f"{latest_resume.ats_score:.1f}" if (latest_resume and latest_resume.ats_score is not None) else "",
            len(apps),
            len(shortlists),
            jobs_str,
            skills_str,
            len(offers),
            accepted_ctc_str,
            offer_status_str,
        ]
        writer.writerow([sanitize_csv_cell(cell) for cell in row])

    csv_content = output.getvalue()
    filename = f"placement_report_{datetime.utcnow().strftime('%Y-%m-%d')}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )


@router.get("/stats", response_model=PlacementStatistics)
async def get_placement_statistics(
    company_id: Optional[int] = Query(None),
    job_id: Optional[int] = Query(None),
    branch: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db)
):
    """Get overall placement statistics with optional filters."""
    return placement_service.get_placement_statistics(
        db,
        company_id=company_id,
        job_id=job_id,
        branch=branch,
        status=status,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/companies/{company_id}/stats", response_model=CompanyStatistics)
async def get_company_statistics(
    company_id: int,
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db)
):
    """Get statistics for a specific company."""
    stats = placement_service.get_company_statistics(db, company_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Company not found")
    return stats


@router.get("/students/{student_id}/placement-status", response_model=StudentPlacementStatus)
async def get_student_placement_status(
    student_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get placement status for a student."""
    # Check permissions
    if current_user.role == UserRole.STUDENT and current_user.id != student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own placement status"
        )
    
    status = placement_service.get_student_placement_status(db, student_id)
    if not status:
        raise HTTPException(status_code=404, detail="Student not found")
    return status


# ============================================
# STUDENTS DIRECTORY FOR PLACEMENT OFFICERS
# ============================================

@router.get("/students")
async def get_all_placement_students(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    department: Optional[str] = Query(None),
    placement_status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of all available students with profiles and resumes for placement officers.
    """
    check_placement_officer_or_admin(current_user)
    
    query = db.query(User).filter(User.role == UserRole.STUDENT)
    
    if department:
        query = query.filter(User.department.ilike(f"%{department}%"))
    
    if search:
        query = query.filter(
            (User.name.ilike(f"%{search}%")) | (User.email.ilike(f"%{search}%"))
        )
    
    users = query.offset(skip).limit(limit).all()
    results = []
    
    for u in users:
        profile = db.query(StudentProfileExtended).filter(StudentProfileExtended.user_id == u.id).first()
        skills = db.query(Skill).filter(Skill.student_id == profile.id).all() if profile else []
        latest_resume = db.query(Resume).filter(Resume.student_id == u.id).order_by(Resume.created_at.desc()).first()
        apps = db.query(Application).filter(Application.student_id == u.id).all()
        shortlists = db.query(Shortlist).filter(Shortlist.student_id == u.id).all()
        
        # Calculate status
        status_val = "not_applied"
        if any(a.status == "selected" for a in apps):
            status_val = "selected"
        elif len(shortlists) > 0 or any(a.status == "shortlisted" for a in apps):
            status_val = "shortlisted"
        elif len(apps) > 0:
            status_val = "applied"
        elif profile and profile.placement_status:
            status_val = profile.placement_status.value if hasattr(profile.placement_status, "value") else str(profile.placement_status)
        
        if placement_status and status_val.lower() != placement_status.lower():
            continue
        
        resume_skills = latest_resume.skills if (latest_resume and isinstance(latest_resume.skills, list)) else []
        combined_skills = [s.name for s in skills] + [sk for sk in resume_skills if isinstance(sk, str)]

        results.append({
            "id": u.id,
            "user_id": u.id,
            "name": profile.full_name if (profile and profile.full_name) else u.name,
            "email": u.email,
            "phone": profile.phone if profile else "",
            "department": profile.branch if (profile and profile.branch) else (u.department or "General"),
            "branch": profile.branch if (profile and profile.branch) else (u.department or "General"),
            "year": profile.year if profile else None,
            "semester": profile.semester if profile else None,
            "cgpa": profile.cgpa if profile else None,
            "enrollment_number": profile.enrollment_number if profile else "",
            "status": status_val,
            "placement_status": status_val,
            "skills": combined_skills,
            "ats_score": latest_resume.ats_score if latest_resume else None,
            "resume_id": latest_resume.id if latest_resume else None,
            "total_applications": len(apps),
            "applications": [{
                "id": a.id,
                "job_id": a.job_posting_id,
                "status": a.status.value if hasattr(a.status, "value") else str(a.status),
                "created_at": a.applied_at.isoformat() if getattr(a, "applied_at", None) else None,
                "applied_at": a.applied_at.isoformat() if getattr(a, "applied_at", None) else None,
                "external_applied_at": a.external_applied_at.isoformat() if getattr(a, "external_applied_at", None) else None,
                "is_external_confirmed": bool(getattr(a, "external_applied_at", None))
            } for a in apps]
        })
    
    return results


@router.get("/students/{student_id}")
async def get_student_details_for_placement(
    student_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed student profile, applications, and resume data.
    """
    # Permission check: student viewing own profile OR placement officer / admin / hod
    is_self = current_user.role == UserRole.STUDENT and current_user.id == student_id
    is_staff = current_user.role in [UserRole.PLACEMENT_OFFICER, UserRole.ADMIN, UserRole.HOD]
    if not (is_self or is_staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You can only view your own placement profile"
        )
    
    user = db.query(User).filter(User.id == student_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Student user not found")
    
    profile = db.query(StudentProfileExtended).filter(StudentProfileExtended.user_id == student_id).first()
    skills = db.query(Skill).filter(Skill.student_id == profile.id).all() if profile else []
    certifications = db.query(Certification).filter(Certification.student_id == profile.id).all() if profile else []
    projects = db.query(Project).filter(Project.student_id == profile.id, Project.is_active == 1).all() if profile else []
    resumes = db.query(Resume).filter(Resume.student_id == student_id).order_by(Resume.created_at.desc()).all()
    apps = (
        db.query(Application)
        .options(
            joinedload(Application.job_posting).joinedload(JobPosting.company),
            subqueryload(Application.round_outcomes).joinedload(StudentRoundOutcome.round),
            joinedload(Application.placement_offer),
        )
        .filter(Application.student_id == student_id)
        .order_by(Application.applied_at.desc())
        .all()
    )
    shortlists = db.query(Shortlist).filter(Shortlist.student_id == student_id).all()
    
    latest_resume = resumes[0] if resumes else None
    
    # Calculate status
    status_val = "not_applied"
    if any(a.status == "selected" for a in apps):
        status_val = "selected"
    elif len(shortlists) > 0 or any(a.status == "shortlisted" for a in apps):
        status_val = "shortlisted"
    elif len(apps) > 0:
        status_val = "applied"
    elif profile and profile.placement_status:
        status_val = profile.placement_status.value if hasattr(profile.placement_status, "value") else str(profile.placement_status)

    # Batch circular lookup for linked jobs
    job_ids = [a.job_posting_id for a in apps if a.job_posting_id]
    circular_map = {}
    if job_ids:
        links = (
            db.query(RecruitmentCircularJob, RecruitmentCircular)
            .join(RecruitmentCircular, RecruitmentCircular.id == RecruitmentCircularJob.circular_id)
            .filter(RecruitmentCircularJob.job_posting_id.in_(job_ids))
            .all()
        )
        for link, circ in links:
            circular_map[link.job_posting_id] = {
                "id": circ.id,
                "title": circ.title,
                "summary": circ.summary,
                "drive_date": circ.drive_date.isoformat() if circ.drive_date else None,
                "application_deadline": circ.application_deadline.isoformat() if circ.application_deadline else None,
                "status": circ.status.value if hasattr(circ.status, "value") else str(circ.status),
                "branch_eligibility": circ.branch_eligibility or [],
            }

    # Rescission reasons lookup for offers
    rescinded_offer_ids = [str(a.placement_offer.id) for a in apps if a.placement_offer and a.placement_offer.acceptance_status == OfferAcceptanceStatus.RESCINDED]
    rescission_reasons = {}
    if rescinded_offer_ids:
        audit_entries = (
            db.query(AuditLog)
            .filter(
                AuditLog.action == "PLACEMENT_OFFER_RESCINDED",
                AuditLog.target_type == "placement_offer",
                AuditLog.target_id.in_(rescinded_offer_ids),
            )
            .order_by(AuditLog.id.desc())
            .all()
        )
        for entry in audit_entries:
            if entry.target_id not in rescission_reasons and entry.details and isinstance(entry.details, dict):
                rescission_reasons[entry.target_id] = entry.details.get("rescission_reason")

    serialized_apps = []
    for a in apps:
        job = a.job_posting
        company = job.company if job else None
        circ_info = circular_map.get(a.job_posting_id)

        # Round outcomes
        outcomes_list = []
        for ro in (a.round_outcomes or []):
            rec_round = ro.round
            outcomes_list.append({
                "id": ro.id,
                "outcome_id": ro.id,
                "round_id": ro.round_id,
                "round_number": rec_round.round_number if rec_round else None,
                "round_name": getattr(rec_round, "name", None) or f"Round {rec_round.round_number}" if rec_round else "Round",
                "round_type": rec_round.round_type if rec_round else "assessment",
                "is_final": rec_round.is_final if rec_round else False,
                "outcome": ro.outcome.value if hasattr(ro.outcome, "value") else str(ro.outcome),
                "score": ro.score,
                "remarks": ro.remarks,
                "confirmed_at": ro.confirmed_at.isoformat() if ro.confirmed_at else None,
            })

        # Offer
        offer_info = None
        if a.placement_offer:
            po = a.placement_offer
            offer_info = {
                "id": po.id,
                "application_id": po.application_id,
                "student_id": po.student_id,
                "job_posting_id": po.job_posting_id,
                "designation": po.designation,
                "ctc_lpa": po.ctc_lpa,
                "acceptance_status": po.acceptance_status.value if hasattr(po.acceptance_status, "value") else str(po.acceptance_status),
                "offer_letter_file_id": str(po.offer_letter_file_id) if po.offer_letter_file_id else None,
                "offer_date": po.offer_date.isoformat() if po.offer_date else None,
                "response_date": po.response_date.isoformat() if po.response_date else None,
                "rescission_reason": rescission_reasons.get(str(po.id)),
                "created_at": po.created_at.isoformat() if po.created_at else None,
            }

        serialized_apps.append({
            "id": a.id,
            "job_id": a.job_posting_id,
            "job_posting_id": a.job_posting_id,
            "job_title": job.title if job else f"Job #{a.job_posting_id}",
            "job_location": job.location if job else None,
            "location": job.location if job else None,
            "application_url": job.application_url if job else None,
            "cgpa_criteria": job.cgpa_criteria if job else None,
            "branch_eligibility": job.branch_eligibility if job else [],
            "salary_range": job.salary_range if job else None,
            "job_deadline": job.application_deadline.isoformat() if (job and job.application_deadline) else None,
            "job_drive_date": job.drive_date.isoformat() if (job and job.drive_date) else None,
            "company_id": company.id if company else None,
            "company_name": company.name if company else "Company",
            "circular_id": circ_info["id"] if circ_info else None,
            "circular_title": circ_info["title"] if circ_info else None,
            "circular_drive_date": circ_info["drive_date"] if circ_info else None,
            "circular_deadline": circ_info["application_deadline"] if circ_info else None,
            "circular": circ_info,
            "status": a.status.value if hasattr(a.status, "value") else str(a.status),
            "match_percentage": a.match_percentage,
            "eligibility_score": a.eligibility_score,
            "match_snapshot": a.match_snapshot,
            "has_low_match_warning": a.match_snapshot.get("has_low_match_warning", False) if a.match_snapshot else False,
            "low_match_warning": a.match_snapshot.get("low_match_warning") if a.match_snapshot else None,
            "created_at": a.applied_at.isoformat() if a.applied_at else None,
            "applied_at": a.applied_at.isoformat() if a.applied_at else None,
            "external_applied_at": a.external_applied_at.isoformat() if getattr(a, "external_applied_at", None) else None,
            "is_external_confirmed": bool(getattr(a, "external_applied_at", None)),
            "round_outcomes": outcomes_list,
            "offer": offer_info,
        })
    
    return {
        "id": user.id,
        "student_id": user.id,
        "student_name": profile.full_name if (profile and profile.full_name) else user.name,
        "name": profile.full_name if (profile and profile.full_name) else user.name,
        "student_email": user.email,
        "email": user.email,
        "phone": profile.phone if profile else "",
        "branch": profile.branch if (profile and profile.branch) else (user.department or "General"),
        "department": profile.branch if (profile and profile.branch) else (user.department or "General"),
        "year": profile.year if profile else None,
        "semester": profile.semester if profile else None,
        "cgpa": profile.cgpa if profile else None,
        "enrollment_number": profile.enrollment_number if profile else "",
        "github_profile": profile.github_profile if profile else "",
        "linkedin_profile": profile.linkedin_profile if profile else "",
        "status": status_val,
        "placement_status": status_val,
        "skills": [s.name for s in skills] + (latest_resume.skills if (latest_resume and latest_resume.skills) else []),
        "certifications": [{
            "id": c.id,
            "name": c.name,
            "issuing_organization": getattr(c, "issuer", getattr(c, "issuing_organization", "")),
            "issuer": getattr(c, "issuer", getattr(c, "issuing_organization", "")),
            "issue_date": c.issue_date
        } for c in certifications],
        "projects": [{
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "technologies": p.technologies
        } for p in projects],
        "resumes": [{
            "id": r.id,
            "name": r.name,
            "ats_score": r.ats_score,
            "skills": r.skills,
            "created_at": r.created_at
        } for r in resumes],
        "applications": serialized_apps,
        "total_applications": len(apps),
        "total_shortlists": len(shortlists)
    }


# ============================================
# VERIFIED PLACEMENT OFFER ENDPOINTS (Phase 3.3.4)
# ============================================

def _serialize_placement_offer(offer: PlacementOffer, db: Optional[Session] = None) -> PlacementOfferResponse:
    job = offer.job_posting
    company = job.company if job else None
    student = offer.student
    rescission_reason = None
    if db is not None and offer.acceptance_status == OfferAcceptanceStatus.RESCINDED:
        log_entry = (
            db.query(AuditLog)
            .filter(
                AuditLog.action == "PLACEMENT_OFFER_RESCINDED",
                AuditLog.target_type == "placement_offer",
                AuditLog.target_id == str(offer.id),
            )
            .order_by(AuditLog.id.desc())
            .first()
        )
        if log_entry and log_entry.details and isinstance(log_entry.details, dict):
            rescission_reason = log_entry.details.get("rescission_reason")

    return PlacementOfferResponse(
        id=offer.id,
        application_id=offer.application_id,
        student_id=offer.student_id,
        job_posting_id=offer.job_posting_id,
        job_title=job.title if job else None,
        company_name=company.name if company else None,
        student_name=student.name if student else None,
        student_email=student.email if student else None,
        ctc_lpa=offer.ctc_lpa,
        designation=offer.designation,
        acceptance_status=offer.acceptance_status.value if hasattr(offer.acceptance_status, "value") else str(offer.acceptance_status),
        offer_letter_file_id=offer.offer_letter_file_id,
        offer_date=offer.offer_date,
        response_date=offer.response_date,
        verified_by=offer.verified_by,
        rescission_reason=rescission_reason,
        created_at=offer.created_at,
        updated_at=offer.updated_at,
    )


@router.post("/offers", response_model=PlacementOfferResponse, status_code=status.HTTP_201_CREATED)
async def create_verified_offer(
    payload: PlacementOfferCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a formal placement offer after Placement Officer verification.
    Accessible only by Placement Officers and Admins.
    """
    check_placement_officer_or_admin(current_user)
    try:
        offer = placement_offer_service.create_placement_offer(
            db=db,
            application_id=payload.application_id,
            ctc_lpa=payload.ctc_lpa,
            designation=payload.designation,
            offer_letter_file_id=payload.offer_letter_file_id,
            offer_date=payload.offer_date,
            student_id=payload.student_id,
            job_posting_id=payload.job_posting_id,
            current_user=current_user,
        )
        return _serialize_placement_offer(offer, db)
    except ValueError as e:
        if "already exists" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.put("/offers/{offer_id}", response_model=PlacementOfferResponse)
async def update_offer_terms(
    offer_id: int,
    payload: PlacementOfferUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update terms of an existing verified placement offer.
    Accessible only by Placement Officers and Admins.
    """
    check_placement_officer_or_admin(current_user)
    try:
        offer = placement_offer_service.update_placement_offer(
            db=db,
            offer_id=offer_id,
            ctc_lpa=payload.ctc_lpa,
            designation=payload.designation,
            offer_letter_file_id=payload.offer_letter_file_id,
            offer_date=payload.offer_date,
            reason=payload.reason,
            current_user=current_user,
        )
        return _serialize_placement_offer(offer, db)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post("/offers/{offer_id}/respond", response_model=PlacementOfferResponse)
async def respond_to_offer(
    offer_id: int,
    payload: PlacementOfferResponseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Student response (accept or decline) to their own verified placement offer.
    Student identity is taken strictly from authenticated server-side user.
    """
    try:
        offer = placement_offer_service.respond_to_placement_offer(
            db=db,
            offer_id=offer_id,
            decision=payload.decision,
            remarks=payload.remarks,
            current_user=current_user,
        )
        return _serialize_placement_offer(offer, db)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        err_msg = str(e)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        if "conflicting" in err_msg.lower() or "cannot change" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.post("/offers/{offer_id}/rescind", response_model=PlacementOfferResponse)
async def rescind_offer(
    offer_id: int,
    payload: PlacementOfferRescindRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Rescind a placement offer with a mandatory audit reason.
    Accessible only by Placement Officers and Admins.
    """
    check_placement_officer_or_admin(current_user)
    try:
        offer = placement_offer_service.rescind_placement_offer(
            db=db,
            offer_id=offer_id,
            reason=payload.reason,
            current_user=current_user,
        )
        return _serialize_placement_offer(offer, db)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/offers/my-offers", response_model=List[PlacementOfferResponse])
async def get_my_placement_offers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve all placement offers extended to the authenticated student."""
    if current_user.role != UserRole.STUDENT and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can view their offers")
    offers = placement_offer_service.get_student_offers(db=db, student_id=current_user.id, current_user=current_user)
    return [_serialize_placement_offer(o, db) for o in offers]


@router.get("/offers/{offer_id}", response_model=PlacementOfferResponse)
async def get_placement_offer_details(
    offer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get placement offer details. Accessible by Placement Officers, Admins, or offer recipient."""
    try:
        offer = placement_offer_service.get_placement_offer_by_id(db=db, offer_id=offer_id, current_user=current_user)
        return _serialize_placement_offer(offer, db)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/offers", response_model=List[PlacementOfferResponse])
async def list_placement_offers(
    job_posting_id: Optional[int] = Query(None),
    circular_id: Optional[int] = Query(None, description="Filter offers by recruitment circular ID"),
    student_id: Optional[int] = Query(None),
    acceptance_status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all placement offers with optional filtering. Accessible by Placement Officers and Admins."""
    check_placement_officer_or_admin(current_user)
    offers = placement_offer_service.list_placement_offers(
        db=db,
        job_posting_id=job_posting_id,
        circular_id=circular_id,
        student_id=student_id,
        acceptance_status=acceptance_status,
        skip=skip,
        limit=limit,
        current_user=current_user,
    )
    return [_serialize_placement_offer(o, db) for o in offers]


@router.get("/accounting")
async def get_placement_accounting(
    company_id: Optional[int] = None,
    job_id: Optional[int] = None,
    branch: Optional[str] = None,
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db),
):
    """Retrieve detailed placement accounting metrics with optional filtering."""
    return placement_offer_service.get_placement_accounting_metrics(
        db, company_id=company_id, job_id=job_id, branch=branch
    )


# ============================================
# RECRUITMENT ROUND & PROGRESSION ENDPOINTS (Phase 3.3.5)
# ============================================

def _serialize_round(r: RecruitmentRound, db: Session) -> RecruitmentRoundResponse:
    outcomes_count = db.query(StudentRoundOutcome).filter(StudentRoundOutcome.round_id == r.id).count()
    return RecruitmentRoundResponse(
        id=r.id,
        job_posting_id=r.job_posting_id,
        round_number=r.round_number,
        name=r.name,
        round_type=r.round_type,
        is_final=r.is_final,
        round_date=r.round_date,
        created_at=r.created_at,
        updated_at=r.updated_at,
        outcomes_count=outcomes_count,
    )


@router.get("/jobs/{job_id}/rounds", response_model=List[RecruitmentRoundResponse])
async def get_job_recruitment_rounds(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve all defined recruitment rounds for a job posting, ordered by round number."""
    try:
        rounds = recruitment_progression_service.get_job_rounds(db=db, job_posting_id=job_id)
        return [_serialize_round(r, db) for r in rounds]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/jobs/{job_id}/rounds", response_model=RecruitmentRoundResponse, status_code=status.HTTP_201_CREATED)
async def create_job_recruitment_round(
    job_id: int,
    payload: RecruitmentRoundCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new sequential recruitment round for a job posting.
    Accessible only by Placement Officers and Admins.
    """
    check_placement_officer_or_admin(current_user)
    try:
        new_round = recruitment_progression_service.create_recruitment_round(
            db=db,
            job_posting_id=job_id,
            round_number=payload.round_number,
            name=payload.name,
            round_type=payload.round_type or "assessment",
            is_final=bool(payload.is_final),
            round_date=payload.round_date,
            current_user=current_user,
        )
        return _serialize_round(new_round, db)
    except ValueError as e:
        err = str(e)
        if "already exists" in err.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/rounds/{round_id}", response_model=RecruitmentRoundResponse)
async def get_recruitment_round(
    round_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve details of a single recruitment round."""
    r = recruitment_progression_service.get_round_by_id(db=db, round_id=round_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Recruitment round #{round_id} not found.")
    return _serialize_round(r, db)


@router.get("/rounds/{round_id}/outcomes")
async def get_round_outcomes(
    round_id: int,
    outcome: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve confirmed candidate outcomes for a specific round."""
    check_placement_officer_or_admin(current_user)
    try:
        outcomes = recruitment_progression_service.get_round_outcomes(db=db, round_id=round_id, outcome_filter=outcome)
        return [{
            "id": o.id,
            "application_id": o.application_id,
            "student_id": o.student_id,
            "student_name": o.student.name if o.student else None,
            "student_email": o.student.email if o.student else None,
            "outcome": o.outcome.value,
            "score": o.score,
            "remarks": o.remarks,
            "confirmed_at": o.confirmed_at.isoformat() if o.confirmed_at else None,
        } for o in outcomes]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/students/{student_id}/progression", response_model=List[StudentProgressionItem])
async def get_student_recruitment_progression(
    student_id: int,
    job_posting_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve chronological recruitment progression history across rounds for a student.
    Accessible by Placement Officers, Admins, or the student themselves.
    """
    if current_user.role not in [UserRole.ADMIN, UserRole.PLACEMENT_OFFICER]:
        if current_user.role != UserRole.STUDENT or current_user.id != student_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access another student's progression.")
    
    try:
        progression = recruitment_progression_service.get_student_progression(
            db=db,
            student_id=student_id,
            job_posting_id=job_posting_id,
        )
        return [StudentProgressionItem(**item) for item in progression]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/outcomes/{outcome_id}/correct")
async def correct_round_outcome(
    outcome_id: int,
    payload: StudentRoundOutcomeCorrectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Administrative correction of a previously recorded round outcome.
    Requires an explicit audited reason.
    Accessible only by Placement Officers and Admins.
    """
    check_placement_officer_or_admin(current_user)
    try:
        updated = recruitment_progression_service.correct_student_round_outcome(
            db=db,
            outcome_id=outcome_id,
            new_outcome=payload.new_outcome,
            new_score=payload.new_score,
            reason=payload.reason,
            current_user=current_user,
        )
        return {
            "id": updated.id,
            "outcome": updated.outcome.value,
            "score": updated.score,
            "remarks": updated.remarks,
            "message": "Round outcome corrected successfully."
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


# =============================================================================
# SAFE TEST-DATA CLEANUP ENDPOINTS (Phase 3.4.1 & Drive Bulk Management)
# =============================================================================

def _normalize_id_list(raw_ids: Optional[List[Any]]) -> Optional[List[int]]:
    if not raw_ids:
        return None
    res = []
    for item in raw_ids:
        if isinstance(item, int):
            res.append(item)
        elif isinstance(item, str):
            for part in item.split(","):
                part_clean = part.strip()
                if part_clean.isdigit():
                    res.append(int(part_clean))
    return res or None


@router.get("/cleanup/preview", response_model=CleanupPreviewResponse)
async def preview_recruitment_cleanup(
    company_ids: Optional[List[str]] = Query(None),
    circular_ids: Optional[List[str]] = Query(None),
    job_ids: Optional[List[str]] = Query(None),
    pattern: Optional[str] = Query(None),
    include_all_candidates: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Preview candidates for safe recruitment test-data cleanup (companies, drives, or jobs).
    Evaluates dependent record counts, safety classifications, and protection reasons.
    Preview operations are strictly read-only and never mutate records or delete storage files.
    Accessible only by Placement Officers and Admins.
    """
    check_placement_officer_or_admin(current_user)
    try:
        norm_company_ids = _normalize_id_list(company_ids)
        norm_circular_ids = _normalize_id_list(circular_ids)
        norm_job_ids = _normalize_id_list(job_ids)
        preview_data = placement_cleanup_service.generate_cleanup_preview(
            db=db,
            company_ids=norm_company_ids,
            circular_ids=norm_circular_ids,
            job_ids=norm_job_ids,
            pattern=pattern,
            include_all_candidates=include_all_candidates,
        )
        return CleanupPreviewResponse(**preview_data)
    except Exception as e:
        logger.error(f"Error generating cleanup preview: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate cleanup preview: {str(e)}"
        )


@router.get("/cleanup/drives/preview", response_model=CleanupPreviewResponse)
async def preview_recruitment_drives_cleanup(
    circular_ids: Optional[List[str]] = Query(None),
    drive_status: Optional[str] = Query(None, alias="status"),
    include_all_candidates: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Preview recruitment drives for safe bulk test-data cleanup.
    Evaluates dependent jobs, rounds, applications, batches, offers, and safety classifications.
    Accessible only by Placement Officers and Admins.
    """
    check_placement_officer_or_admin(current_user)
    try:
        norm_circular_ids = _normalize_id_list(circular_ids)
        preview_data = placement_cleanup_service.generate_drives_cleanup_preview(
            db=db,
            circular_ids=norm_circular_ids,
            status=drive_status,
            include_all_candidates=include_all_candidates,
        )
        return CleanupPreviewResponse(**preview_data)
    except Exception as e:
        logger.error(f"Error generating drives cleanup preview: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate drives cleanup preview: {str(e)}"
        )


@router.get("/cleanup/jobs/preview", response_model=CleanupPreviewResponse)
async def preview_job_postings_cleanup(
    job_ids: Optional[List[str]] = Query(None),
    company_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    pattern: Optional[str] = Query(None),
    include_all_candidates: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Preview job postings for safe bulk test-data cleanup.
    Evaluates dependent applications, rounds, outcomes, batches, offers, and safety classifications.
    Accessible only by Placement Officers and Admins.
    """
    check_placement_officer_or_admin(current_user)
    try:
        norm_job_ids = _normalize_id_list(job_ids)
        preview_data = placement_cleanup_service.generate_jobs_cleanup_preview(
            db=db,
            job_ids=norm_job_ids,
            company_id=company_id,
            status=status,
            pattern=pattern,
            include_all_candidates=include_all_candidates,
        )
        return CleanupPreviewResponse(**preview_data)
    except Exception as e:
        logger.error(f"Error generating jobs cleanup preview: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate jobs cleanup preview: {str(e)}"
        )


@router.post("/cleanup/execute", response_model=CleanupExecuteResponse)
async def execute_recruitment_cleanup(
    payload: CleanupExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Execute explicit recruitment test-data cleanup ('archive' or 'purge').
    Requires explicit company, drive, or job selection and strict safety re-validation at execution time.
    'purge' mode requires confirmation_phrase='CONFIRM_PURGE_TEST_DATA'.
    Accessible only by Placement Officers and Admins.
    """
    check_placement_officer_or_admin(current_user)
    try:
        result = placement_cleanup_service.execute_cleanup(
            db=db,
            company_ids=payload.company_ids,
            circular_ids=payload.circular_ids,
            orphaned_job_ids=payload.orphaned_job_ids,
            job_ids=payload.job_ids,
            mode=payload.mode,
            confirmation_phrase=payload.confirmation_phrase,
            current_user=current_user,
        )
        return CleanupExecuteResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Error executing cleanup: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cleanup execution failed: {str(e)}"
        )

