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
from sqlalchemy.orm import Session
from typing import List, Optional
import io
import csv
from datetime import datetime
import logging

from ..core.database import get_db
from ..api.auth import get_current_user, get_current_placement_officer
from ..models.user import User, UserRole
from ..models.company import Company
from ..models.job_posting import JobPosting, JobStatus
from ..models.application import Application
from ..models.shortlist import Shortlist
from ..models.profile import StudentProfileExtended, Skill, Project
from ..models.certification import Certification
from ..models.resume import Resume
from ..schemas.placement import (
    CompanyCreate, CompanyUpdate, CompanyResponse,
    JobPostingCreate, JobPostingUpdate, JobPostingResponse,
    ApplicationCreate, ApplicationUpdate, ApplicationResponse,
    ShortlistCreate, ShortlistUpdate, ShortlistResponse,
    PlacementStatistics, CompanyStatistics, StudentPlacementStatus,
    StudentEligibility, JobMatchRequest, JobMatchResponse,
    JdParseRequest, JdParseResponse
)
from ..services.placement_service import placement_service
from ..services.jd_parser_service import jd_parser_service

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
    limit: int = Query(100, ge=1, le=200),
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
    job = placement_service.create_job_posting(db, job_data, current_user.id)
    response = JobPostingResponse.model_validate(job)
    if job.company:
        response.company_name = job.company.name
    return response


@router.get("/jobs", response_model=List[JobPostingResponse])
async def get_job_postings(
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
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
    return response


@router.put("/jobs/{job_id}", response_model=JobPostingResponse)
async def update_job_posting(
    job_id: int,
    job_data: JobPostingUpdate,
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db)
):
    """Update a job posting."""
    job = placement_service.update_job_posting(db, job_id, job_data)
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found")
    response = JobPostingResponse.model_validate(job)
    if job.company:
        response.company_name = job.company.name
    return response


@router.delete("/jobs/{job_id}")
async def delete_job_posting(
    job_id: int,
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db)
):
    """Delete a job posting."""
    result = placement_service.delete_job_posting(db, job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Job posting not found")
    return {"message": "Job posting deleted successfully"}


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
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db)
):
    """
    Upload a Job Description file (PDF, DOCX, TXT) to extract structured requirements.
    Allows Placement Officer to review and edit before creating/publishing the job.
    """
    try:
        content = await file.read()
        extracted_text = jd_parser_service.extract_text_from_file(
            content=content,
            filename=file.filename
        )
        parsed = jd_parser_service.parse_jd_text(extracted_text)
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
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all applications."""
    # Students can only see their own applications
    if current_user.role == UserRole.STUDENT:
        student_id = current_user.id
    
    applications = placement_service.get_applications(db, student_id, job_posting_id, status, skip, limit)
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

    # 4. Validate job has external application URL
    if not job.application_url or not job.application_url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This job posting does not have an external application URL to confirm"
        )

    # 5. Idempotent confirmation
    confirmed_app = placement_service.confirm_external_application(db, application, current_user)
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

@router.get("/reports/export")
async def export_placement_report(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export institutional placement report as a downloadable CSV.
    Accessible by Placement Officers and Admins.
    """
    check_placement_officer_or_admin(current_user)
    
    users = db.query(User).filter(User.role == UserRole.STUDENT).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # CSV Header
    writer.writerow([
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
        "Skills"
    ])
    
    for u in users:
        profile = db.query(StudentProfileExtended).filter(StudentProfileExtended.user_id == u.id).first()
        skills = db.query(Skill).filter(Skill.student_id == profile.id).all() if profile else []
        latest_resume = db.query(Resume).filter(Resume.student_id == u.id).order_by(Resume.created_at.desc()).first()
        apps = db.query(Application).filter(Application.student_id == u.id).all()
        shortlists = db.query(Shortlist).filter(Shortlist.student_id == u.id).all()
        
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
        
        student_skills_list = [s.name for s in skills] + (latest_resume.skills if (latest_resume and latest_resume.skills) else [])
        skills_str = ", ".join(dict.fromkeys(student_skills_list))
        
        applied_jobs = []
        for a in apps:
            job = db.query(JobPosting).filter(JobPosting.id == a.job_posting_id).first()
            if job and job.title:
                applied_jobs.append(job.title)
        jobs_str = "; ".join(applied_jobs)
        
        writer.writerow([
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
            skills_str
        ])
    
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
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db)
):
    """Get overall placement statistics."""
    return placement_service.get_placement_statistics(db)


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
    apps = db.query(Application).filter(Application.student_id == student_id).all()
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
        "applications": [{
            "id": a.id,
            "job_id": a.job_posting_id,
            "job_title": a.job_posting.title if a.job_posting else f"Job #{a.job_posting_id}",
            "company_name": a.job_posting.company.name if (a.job_posting and a.job_posting.company) else "Company",
            "status": a.status.value if hasattr(a.status, "value") else str(a.status),
            "match_percentage": a.match_percentage,
            "eligibility_score": a.eligibility_score,
            "match_snapshot": a.match_snapshot,
            "has_low_match_warning": a.match_snapshot.get("has_low_match_warning", False) if a.match_snapshot else False,
            "low_match_warning": a.match_snapshot.get("low_match_warning") if a.match_snapshot else None,
            "created_at": a.applied_at.isoformat() if a.applied_at else None,
            "applied_at": a.applied_at.isoformat() if a.applied_at else None,
            "external_applied_at": a.external_applied_at.isoformat() if getattr(a, "external_applied_at", None) else None,
            "is_external_confirmed": bool(getattr(a, "external_applied_at", None))
        } for a in apps],
        "total_applications": len(apps),
        "total_shortlists": len(shortlists)
    }