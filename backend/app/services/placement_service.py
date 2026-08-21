"""
Placement Service - Core Business Logic

Handles all placement operations:
- Company management (CRUD)
- Job posting management (CRUD)
- Application management (CRUD)
- Shortlist management (CRUD)
- Student eligibility checking
- AI-based matching
- Statistics and reporting
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from datetime import datetime

from ..models.company import Company
from ..models.job_posting import JobPosting, JobStatus
from ..models.application import Application, ApplicationStatus
from ..models.shortlist import Shortlist
from ..models.user import User, UserRole
from ..models.profile import StudentProfile
from ..schemas.placement import (
    CompanyCreate, CompanyUpdate,
    JobPostingCreate, JobPostingUpdate,
    ApplicationCreate, ApplicationUpdate,
    ShortlistCreate, ShortlistUpdate,
    StudentEligibility, JobMatchRequest, JobMatchResponse,
    PlacementStatistics, CompanyStatistics, StudentPlacementStatus
)

logger = logging.getLogger(__name__)


class PlacementService:
    """Core placement service."""
    
    # ============================================
    # COMPANY MANAGEMENT
    # ============================================
    
    def create_company(self, db: Session, company_data: CompanyCreate, created_by: int) -> Company:
        """Create a new company."""
        company = Company(
            name=company_data.name,
            description=company_data.description,
            website=company_data.website,
            industry=company_data.industry,
            location=company_data.location,
            contact_email=company_data.contact_email,
            contact_phone=company_data.contact_phone,
            logo_url=company_data.logo_url,
            is_active=company_data.is_active
        )
        db.add(company)
        db.commit()
        db.refresh(company)
        logger.info(f"✅ Company created: {company.name} (ID: {company.id})")
        return company
    
    def get_company(self, db: Session, company_id: int) -> Optional[Company]:
        """Get a company by ID."""
        return db.query(Company).filter(Company.id == company_id).first()
    
    def get_companies(self, db: Session, skip: int = 0, limit: int = 100, is_active: Optional[bool] = None) -> List[Company]:
        """Get all companies with pagination."""
        query = db.query(Company)
        if is_active is not None:
            query = query.filter(Company.is_active == is_active)
        return query.offset(skip).limit(limit).all()
    
    def update_company(self, db: Session, company_id: int, company_data: CompanyUpdate) -> Optional[Company]:
        """Update a company."""
        company = self.get_company(db, company_id)
        if not company:
            return None
        
        update_dict = company_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(company, key, value)
        
        company.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(company)
        logger.info(f"✅ Company updated: {company.name} (ID: {company.id})")
        return company
    
    def delete_company(self, db: Session, company_id: int) -> bool:
        """Delete a company (soft delete by setting is_active=False)."""
        company = self.get_company(db, company_id)
        if not company:
            return False
        
        company.is_active = False
        company.updated_at = datetime.utcnow()
        db.commit()
        logger.info(f"🗑️ Company soft deleted: {company.name} (ID: {company.id})")
        return True
    
    # ============================================
    # JOB POSTING MANAGEMENT
    # ============================================
    
    def create_job_posting(self, db: Session, job_data: JobPostingCreate, created_by: int) -> JobPosting:
        """Create a new job posting."""
        job = JobPosting(
            company_id=job_data.company_id,
            title=job_data.title,
            description=job_data.description,
            required_skills=job_data.required_skills,
            experience_level=job_data.experience_level,
            cgpa_criteria=job_data.cgpa_criteria,
            branch_eligibility=job_data.branch_eligibility,
            location=job_data.location,
            salary_range=job_data.salary_range,
            application_deadline=job_data.application_deadline,
            drive_date=job_data.drive_date,
            status=job_data.status,
            created_by=created_by
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        logger.info(f"✅ Job posting created: {job.title} (ID: {job.id})")
        return job
    
    def get_job_posting(self, db: Session, job_id: int) -> Optional[JobPosting]:
        """Get a job posting by ID with company data."""
        return db.query(JobPosting).options(
            joinedload(JobPosting.company)  # Make sure company is joined
        ).filter(JobPosting.id == job_id).first()

    def get_job_postings(self, db: Session, skip: int = 0, limit: int = 100, 
                        company_id: Optional[int] = None, 
                        status: Optional[JobStatus] = None) -> List[JobPosting]:
        """Get all job postings with filters."""
        query = db.query(JobPosting).options(joinedload(JobPosting.company))  # Join company
        # ... rest of the code
        
        if company_id:
            query = query.filter(JobPosting.company_id == company_id)
        if status:
            query = query.filter(JobPosting.status == status)
        
        return query.order_by(JobPosting.created_at.desc()).offset(skip).limit(limit).all()
    
    def update_job_posting(self, db: Session, job_id: int, job_data: JobPostingUpdate) -> Optional[JobPosting]:
        """Update a job posting."""
        job = self.get_job_posting(db, job_id)
        if not job:
            return None
        
        update_dict = job_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(job, key, value)
        
        job.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
        logger.info(f"✅ Job posting updated: {job.title} (ID: {job.id})")
        return job
    
    def delete_job_posting(self, db: Session, job_id: int) -> bool:
        """Delete a job posting."""
        job = self.get_job_posting(db, job_id)
        if not job:
            return False
        
        db.delete(job)
        db.commit()
        logger.info(f"🗑️ Job posting deleted: {job.title} (ID: {job.id})")
        return True
    
    # ============================================
    # APPLICATION MANAGEMENT
    # ============================================
    
    def create_application(self, db: Session, app_data: ApplicationCreate) -> Application:
        """Create a new application."""
        application = Application(
            student_id=app_data.student_id,
            job_posting_id=app_data.job_posting_id,
            status=app_data.status,
            eligibility_score=app_data.eligibility_score,
            match_percentage=app_data.match_percentage,
            notes=app_data.notes
        )
        db.add(application)
        db.commit()
        db.refresh(application)
        logger.info(f"✅ Application created: Student {app_data.student_id} -> Job {app_data.job_posting_id}")
        return application
    
    def get_application(self, db: Session, app_id: int) -> Optional[Application]:
        """Get an application by ID."""
        return db.query(Application).options(
            joinedload(Application.student),
            joinedload(Application.job_posting)
        ).filter(Application.id == app_id).first()
    
    def get_applications(self, db: Session, student_id: Optional[int] = None,
                         job_posting_id: Optional[int] = None,
                         status: Optional[ApplicationStatus] = None,
                         skip: int = 0, limit: int = 100) -> List[Application]:
        """Get applications with filters."""
        query = db.query(Application).options(
            joinedload(Application.student),
            joinedload(Application.job_posting)
        )
        
        if student_id:
            query = query.filter(Application.student_id == student_id)
        if job_posting_id:
            query = query.filter(Application.job_posting_id == job_posting_id)
        if status:
            query = query.filter(Application.status == status)
        
        return query.order_by(Application.applied_at.desc()).offset(skip).limit(limit).all()
    
    def update_application(self, db: Session, app_id: int, app_data: ApplicationUpdate) -> Optional[Application]:
        """Update an application."""
        application = self.get_application(db, app_id)
        if not application:
            return None
        
        update_dict = app_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(application, key, value)
        
        application.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(application)
        logger.info(f"✅ Application updated: ID {app_id}")
        return application
    
    # ============================================
    # SHORTLIST MANAGEMENT
    # ============================================
    
    def create_shortlist(self, db: Session, shortlist_data: ShortlistCreate) -> Shortlist:
        """Create a new shortlist entry."""
        shortlist = Shortlist(
            student_id=shortlist_data.student_id,
            company_id=shortlist_data.company_id,
            job_posting_id=shortlist_data.job_posting_id,
            reason=shortlist_data.reason,
            shortlisted_by=shortlist_data.shortlisted_by
        )
        db.add(shortlist)
        db.commit()
        db.refresh(shortlist)
        
        # Update application status to SHORTLISTED
        application = db.query(Application).filter(
            Application.student_id == shortlist_data.student_id,
            Application.job_posting_id == shortlist_data.job_posting_id
        ).first()
        if application:
            application.status = ApplicationStatus.SHORTLISTED
            application.updated_at = datetime.utcnow()
            db.commit()
        
        logger.info(f"✅ Student {shortlist_data.student_id} shortlisted for job {shortlist_data.job_posting_id}")
        return shortlist
    
    def get_shortlists(self, db: Session, student_id: Optional[int] = None,
                       company_id: Optional[int] = None,
                       job_posting_id: Optional[int] = None,
                       skip: int = 0, limit: int = 100) -> List[Shortlist]:
        """Get shortlists with filters."""
        query = db.query(Shortlist).options(
            joinedload(Shortlist.student),
            joinedload(Shortlist.company),
            joinedload(Shortlist.job_posting)
        )
        
        if student_id:
            query = query.filter(Shortlist.student_id == student_id)
        if company_id:
            query = query.filter(Shortlist.company_id == company_id)
        if job_posting_id:
            query = query.filter(Shortlist.job_posting_id == job_posting_id)
        
        return query.order_by(Shortlist.created_at.desc()).offset(skip).limit(limit).all()
    
    def remove_from_shortlist(self, db: Session, shortlist_id: int) -> bool:
        """Remove a student from shortlist."""
        shortlist = db.query(Shortlist).filter(Shortlist.id == shortlist_id).first()
        if not shortlist:
            return False
        
        # Update application status back to APPLIED
        application = db.query(Application).filter(
            Application.student_id == shortlist.student_id,
            Application.job_posting_id == shortlist.job_posting_id
        ).first()
        if application:
            application.status = ApplicationStatus.APPLIED
            application.updated_at = datetime.utcnow()
            db.commit()
        
        db.delete(shortlist)
        db.commit()
        logger.info(f"🗑️ Student removed from shortlist: ID {shortlist_id}")
        return True
    
    # ============================================
    # ELIGIBILITY & MATCHING (Simplified - No Skill Model)
    # ============================================
    
    def check_student_eligibility(self, db: Session, student_id: int, job_posting_id: int) -> StudentEligibility:
        """Check if a student is eligible for a job posting."""
        student = db.query(User).filter(User.id == student_id).first()
        job = self.get_job_posting(db, job_posting_id)
        
        if not student or not job:
            raise ValueError("Student or job not found")
        
        # Get student profile
        profile = db.query(StudentProfile).filter(StudentProfile.user_id == student_id).first()
        
        # Get student skills from profile (if available)
        student_skills = []
        if profile and hasattr(profile, 'skills') and profile.skills:
            student_skills = profile.skills if isinstance(profile.skills, list) else []
        
        # Get skills from job posting
        required_skills = job.required_skills or []
        
        # Calculate scores
        is_eligible = True
        eligibility_reasons = []
        
        # Check CGPA
        cgpa_match = True
        if job.cgpa_criteria and profile and hasattr(profile, 'cgpa'):
            cgpa_match = profile.cgpa >= job.cgpa_criteria
            if not cgpa_match:
                is_eligible = False
                eligibility_reasons.append(f"CGPA {profile.cgpa} < {job.cgpa_criteria}")
        
        # Check branch
        branch_match = True
        if job.branch_eligibility and profile and hasattr(profile, 'branch'):
            branch_match = profile.branch in job.branch_eligibility
            if not branch_match:
                is_eligible = False
                eligibility_reasons.append(f"Branch {profile.branch} not eligible")
        
        # Check skills
        matched_skills = [s for s in required_skills if s in student_skills]
        missing_skills = [s for s in required_skills if s not in student_skills]
        
        skill_match = (len(matched_skills) / len(required_skills) * 100) if required_skills else 100
        if skill_match < 50 and required_skills:
            is_eligible = False
            eligibility_reasons.append(f"Skill match {skill_match:.1f}% < 50%")
        
        # Calculate overall match score
        match_score = (skill_match * 0.5) + (100 if cgpa_match else 0) * 0.25 + (100 if branch_match else 0) * 0.25
        
        return StudentEligibility(
            student_id=student.id,
            student_name=student.name,
            email=student.email,
            branch=profile.branch if profile and hasattr(profile, 'branch') else "N/A",
            cgpa=profile.cgpa if profile and hasattr(profile, 'cgpa') else 0,
            is_eligible=is_eligible,
            eligibility_reasons=eligibility_reasons,
            match_score=min(match_score, 100),
            skill_match=skill_match,
            cgpa_match=cgpa_match,
            branch_match=branch_match,
            missing_skills=missing_skills,
            matched_skills=matched_skills
        )
    
    def match_students_for_job(self, db: Session, request: JobMatchRequest) -> JobMatchResponse:
        """Match students for a job posting."""
        job = self.get_job_posting(db, request.job_posting_id)
        if not job:
            raise ValueError("Job not found")
        
        # Get students to evaluate
        if request.student_ids:
            students = db.query(User).filter(User.id.in_(request.student_ids)).all()
        else:
            students = db.query(User).filter(User.role == UserRole.STUDENT).all()
        
        # Evaluate each student
        eligible_students = []
        for student in students:
            try:
                eligibility = self.check_student_eligibility(db, student.id, request.job_posting_id)
                if eligibility.is_eligible:
                    eligible_students.append(eligibility)
            except Exception as e:
                logger.error(f"Error checking eligibility for student {student.id}: {str(e)}")
        
        # Sort by match score (highest first)
        eligible_students.sort(key=lambda x: x.match_score, reverse=True)
        
        return JobMatchResponse(
            job_posting_id=job.id,
            job_title=job.title,
            company_name=job.company.name if job.company else "Unknown",
            total_eligible=len(eligible_students),
            eligible_students=eligible_students,
            top_candidates=eligible_students[:10]
        )
    
    # ============================================
    # STATISTICS & REPORTS
    # ============================================
    
    def get_placement_statistics(self, db: Session) -> PlacementStatistics:
        """Get overall placement statistics."""
        total_companies = db.query(Company).count()
        active_companies = db.query(Company).filter(Company.is_active == True).count()
        total_jobs = db.query(JobPosting).count()
        open_jobs = db.query(JobPosting).filter(JobPosting.status == JobStatus.OPEN).count()
        total_applications = db.query(Application).count()
        total_shortlists = db.query(Shortlist).count()
        total_students = db.query(User).filter(User.role == UserRole.STUDENT).count()
        
        # Applications by status
        apps_by_status = {}
        for status in ApplicationStatus:
            count = db.query(Application).filter(Application.status == status).count()
            apps_by_status[status.value] = count
        
        # Jobs by status
        jobs_by_status = {}
        for status in JobStatus:
            count = db.query(JobPosting).filter(JobPosting.status == status).count()
            jobs_by_status[status.value] = count
        
        return PlacementStatistics(
            total_companies=total_companies,
            active_companies=active_companies,
            total_jobs=total_jobs,
            open_jobs=open_jobs,
            total_applications=total_applications,
            total_shortlists=total_shortlists,
            total_students=total_students,
            placement_rate=(total_shortlists / total_students * 100) if total_students > 0 else 0,
            applications_by_status=apps_by_status,
            jobs_by_status=jobs_by_status
        )
    
    def get_company_statistics(self, db: Session, company_id: int) -> Optional[CompanyStatistics]:
        """Get statistics for a specific company."""
        company = self.get_company(db, company_id)
        if not company:
            return None
        
        total_jobs = db.query(JobPosting).filter(JobPosting.company_id == company_id).count()
        total_applications = db.query(Application).join(JobPosting).filter(
            JobPosting.company_id == company_id
        ).count()
        total_shortlists = db.query(Shortlist).filter(Shortlist.company_id == company_id).count()
        
        total_selected = db.query(Application).join(JobPosting).filter(
            JobPosting.company_id == company_id,
            Application.status == ApplicationStatus.SELECTED
        ).count()
        
        return CompanyStatistics(
            company_id=company_id,
            company_name=company.name,
            total_jobs=total_jobs,
            total_applications=total_applications,
            total_shortlists=total_shortlists,
            total_selected=total_selected
        )
    
    def get_student_placement_status(self, db: Session, student_id: int) -> Optional[StudentPlacementStatus]:
        """Get placement status for a student."""
        student = db.query(User).filter(User.id == student_id).first()
        if not student:
            return None
        
        profile = db.query(StudentProfile).filter(StudentProfile.user_id == student_id).first()
        
        applications = db.query(Application).filter(
            Application.student_id == student_id
        ).all()
        
        shortlisted_count = len([a for a in applications if a.status == ApplicationStatus.SHORTLISTED])
        selected_count = len([a for a in applications if a.status == ApplicationStatus.SELECTED])
        
        status = "not_applied"
        if selected_count > 0:
            status = "selected"
        elif shortlisted_count > 0:
            status = "shortlisted"
        elif len(applications) > 0:
            status = "applied"
        
        return StudentPlacementStatus(
            student_id=student.id,
            student_name=student.name,
            email=student.email,
            branch=profile.branch if profile and hasattr(profile, 'branch') else None,
            cgpa=profile.cgpa if profile and hasattr(profile, 'cgpa') else None,
            total_applications=len(applications),
            shortlisted_count=shortlisted_count,
            selected_count=selected_count,
            status=status,
            applications=[ApplicationResponse.model_validate(a) for a in applications]
        )


# Singleton instance
placement_service = PlacementService()