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
from typing import List, Optional, Dict, Any, Tuple, Union
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from datetime import datetime

from ..models.company import Company
from ..models.job_posting import JobPosting, JobStatus
from ..models.application import Application, ApplicationStatus
from ..models.shortlist import Shortlist
from ..models.user import User, UserRole
from ..models.profile import StudentProfile, Skill, StudentProfileExtended, PlacementStatus
from ..models.resume import Resume
from ..models.notification import Notification
from ..schemas.placement import (
    CompanyCreate, CompanyUpdate,
    JobPostingCreate, JobPostingUpdate,
    ApplicationCreate, ApplicationUpdate, ApplicationResponse,
    ShortlistCreate, ShortlistUpdate,
    StudentEligibility, JobMatchRequest, JobMatchResponse,
    PlacementStatistics, CompanyStatistics, StudentPlacementStatus
)
from .job_matching_service import job_matching_service

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
        """Create a new job posting (defaults to DRAFT status)."""
        job = JobPosting(
            company_id=job_data.company_id,
            title=job_data.title,
            description=job_data.description,
            required_skills=job_data.required_skills,
            preferred_skills=getattr(job_data, 'preferred_skills', []),
            experience_level=job_data.experience_level,
            cgpa_criteria=job_data.cgpa_criteria,
            branch_eligibility=job_data.branch_eligibility,
            location=job_data.location,
            salary_range=job_data.salary_range,
            application_url=getattr(job_data, 'application_url', None),
            application_deadline=job_data.application_deadline,
            drive_date=job_data.drive_date,
            status=job_data.status if job_data.status else JobStatus.DRAFT,
            created_by=created_by
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        logger.info(f"✅ Job posting created: {job.title} (ID: {job.id})")
        return job

    def publish_job_posting(self, db: Session, job_id: int, confirm_no_skills: bool = False) -> Optional[JobPosting]:
        """Publish a draft job posting (status -> OPEN). Validates that skills exist unless confirmed."""
        job = self.get_job_posting(db, job_id)
        if not job:
            return None

        # Validate that job has meaningful skill requirements unless confirmed
        has_required = bool(job.required_skills and len(job.required_skills) > 0)
        has_preferred = bool(job.preferred_skills and len(job.preferred_skills) > 0)
        if not has_required and not has_preferred and not confirm_no_skills:
            raise ValueError(
                "Job cannot be published without skill requirements unless explicitly confirmed with confirm_no_skills=True"
            )

        was_open = (job.status == JobStatus.OPEN)
        job.status = JobStatus.OPEN
        job.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
        logger.info(f"📢 Job posting published: {job.title} (ID: {job.id})")

        # Notify students only on real transition to OPEN (not on repeated publish of an already-open job)
        if not was_open:
            try:
                self.notify_students_on_job_publish(db, job)
            except Exception as e:
                logger.error(f"❌ Failed to dispatch job publication notifications for job {job.id}: {e}", exc_info=True)

        return job

    def notify_students_on_job_publish(self, db: Session, job: JobPosting) -> int:
        """
        Notify appropriate students when a job is published (status -> OPEN).
        Respects branch eligibility targeting if specified, or all active students otherwise.
        Uses event_key to ensure strict idempotency and deduplication.
        Returns the number of notifications created.
        """
        # 1. Determine eligible branches if configured
        target_branches: Optional[set] = None
        if job.branch_eligibility and isinstance(job.branch_eligibility, (list, tuple)) and len(job.branch_eligibility) > 0:
            target_branches = {
                str(b).strip().lower() for b in job.branch_eligibility if b and str(b).strip()
            }

        # 2. Query active students with profile
        students = db.query(User).options(
            joinedload(User.student_profile)
        ).filter(
            User.role == UserRole.STUDENT,
            User.is_active == True
        ).all()

        company_name = job.company.name if job.company else "Campus Recruiter"
        title = f"💼 New Job: {job.title} at {company_name}"

        deadline_str = ""
        if job.application_deadline:
            if hasattr(job.application_deadline, "strftime"):
                deadline_str = f" • Deadline: {job.application_deadline.strftime('%d %b %Y')}"
            else:
                deadline_str = f" • Deadline: {job.application_deadline}"

        message = (
            f"{company_name} is hiring for {job.title}{deadline_str}. "
            f"Check your skill match and apply via Campus Jobs."
        )

        notif_count = 0
        for student in students:
            # Check branch eligibility if targeted
            if target_branches:
                s_branch = None
                if student.student_profile and student.student_profile.branch:
                    s_branch = student.student_profile.branch
                elif student.department:
                    s_branch = student.department

                if not s_branch or str(s_branch).strip().lower() not in target_branches:
                    continue

            event_key = f"job_publish:{job.id}:student:{student.id}"

            # Check if notification with this event_key already exists
            existing = db.query(Notification).filter(Notification.event_key == event_key).first()
            if existing:
                continue

            notif = Notification(
                user_id=student.id,
                type="placement_job",
                title=title,
                message=message,
                reference_id=job.id,
                event_key=event_key,
                is_read=False
            )
            db.add(notif)
            notif_count += 1

        if notif_count > 0:
            try:
                db.commit()
                logger.info(f"📢 Created {notif_count} job-publication notifications for job {job.id}")
            except Exception as e:
                db.rollback()
                logger.warning(f"Handled notification commit for job {job.id}: {e}")

        return notif_count
    
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
        
        old_status = job.status
        update_dict = job_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(job, key, value)
        
        job.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
        logger.info(f"✅ Job posting updated: {job.title} (ID: {job.id})")

        # If updated to OPEN from a non-OPEN status, dispatch notifications safely
        if old_status != JobStatus.OPEN and job.status == JobStatus.OPEN:
            try:
                self.notify_students_on_job_publish(db, job)
            except Exception as e:
                logger.error(f"❌ Failed to dispatch job publication notifications on update for job {job.id}: {e}", exc_info=True)

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
    
    def create_application(
        self,
        db: Session,
        app_data: ApplicationCreate,
        current_user: Optional[User] = None
    ) -> Application:
        """
        Create a new application with server-authoritative scoring, eligibility validation,
        and immutable snapshot persistence.
        """
        from sqlalchemy.exc import IntegrityError
        from datetime import timezone

        # 1. Determine and authenticate student identity
        if current_user:
            if current_user.role == UserRole.STUDENT:
                student_id = current_user.id
            elif current_user.role in [UserRole.ADMIN, UserRole.PLACEMENT_OFFICER]:
                student_id = app_data.student_id if app_data.student_id else current_user.id
            else:
                student_id = current_user.id
        else:
            if not app_data.student_id:
                raise ValueError("Student ID is required")
            student_id = app_data.student_id

        student = db.query(User).filter(User.id == student_id).first()
        if not student:
            raise ValueError(f"Student with ID {student_id} not found")

        # 2. Fetch and validate job posting
        job = self.get_job_posting(db, app_data.job_posting_id)
        if not job:
            raise ValueError(f"Job posting with ID {app_data.job_posting_id} not found")

        if job.status != JobStatus.OPEN:
            raise ValueError("Job posting is not open for applications")

        # Check deadline if configured
        if job.application_deadline:
            now_utc = datetime.now(timezone.utc)
            deadline = job.application_deadline
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            if now_utc > deadline:
                raise ValueError("Application deadline has passed")

        # 3. Prevent duplicate applications (application-level check)
        existing = db.query(Application).filter(
            Application.student_id == student_id,
            Application.job_posting_id == job.id
        ).first()
        if existing:
            raise ValueError("You have already applied for this job")

        # 4. Server-Authoritative Matching and Eligibility
        eligibility = job_matching_service.match_student_to_job(db, student, job)

        # Reject submission when an explicit eligibility requirement fails
        if not eligibility.is_eligible:
            reasons_str = "; ".join(eligibility.eligibility_reasons) if eligibility.eligibility_reasons else "Candidate does not meet explicit eligibility criteria"
            raise ValueError(f"Application rejected: {reasons_str}")

        # 5. Build immutable application-time snapshot
        skill_res = job_matching_service.get_student_skills(db, student_id)
        candidate_skills = skill_res[0] if skill_res else []

        match_snapshot = {
            "snapshot_version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "student_id": student.id,
            "student_name": student.name,
            "branch": eligibility.branch,
            "cgpa": eligibility.cgpa,
            "resume_id": eligibility.resume_id,
            "resume_filename": eligibility.resume_filename,
            "skill_sources": eligibility.skill_sources,
            "candidate_skills": candidate_skills,
            "job_required_skills": job.required_skills or [],
            "job_preferred_skills": job.preferred_skills or [],
            "matched_required_skills": eligibility.matched_required_skills,
            "missing_required_skills": eligibility.missing_required_skills,
            "matched_preferred_skills": eligibility.matched_preferred_skills,
            "missing_preferred_skills": eligibility.missing_preferred_skills,
            "semantic_matches": eligibility.semantic_matches,
            "required_score": eligibility.required_score,
            "preferred_score": eligibility.preferred_score,
            "match_percentage": eligibility.match_score,
            "is_eligible": eligibility.is_eligible,
            "eligibility_reasons": eligibility.eligibility_reasons,
            "has_low_match_warning": eligibility.has_low_match_warning,
            "low_match_warning": eligibility.low_match_warning,
            "cgpa_match": eligibility.cgpa_match,
            "branch_match": eligibility.branch_match,
            "job_criteria": {
                "cgpa_criteria": job.cgpa_criteria,
                "branch_eligibility": job.branch_eligibility or [],
                "experience_level": job.experience_level,
            }
        }

        # 6. Persist application with server-authoritative scores
        authoritative_match_score = eligibility.match_score
        authoritative_eligibility_score = eligibility.match_score if eligibility.match_score is not None else 100.0

        application = Application(
            student_id=student_id,
            job_posting_id=job.id,
            status=app_data.status or ApplicationStatus.APPLIED,
            eligibility_score=authoritative_eligibility_score,
            match_percentage=authoritative_match_score,
            notes=app_data.notes,
            match_snapshot=match_snapshot
        )
        db.add(application)
        try:
            db.commit()
            db.refresh(application)
        except IntegrityError:
            db.rollback()
            raise ValueError("You have already applied for this job")

        logger.info(f"✅ Authoritative Application created: Student {student_id} -> Job {job.id} (Score: {authoritative_match_score}%)")
        return application
    
    def get_application(self, db: Session, app_id: int) -> Optional[Application]:
        """Get an application by ID."""
        return db.query(Application).options(
            joinedload(Application.student),
            joinedload(Application.job_posting)
        ).filter(Application.id == app_id).first()
    
    def get_applications(self, db: Session, student_id: Optional[int] = None,
                         job_posting_id: Optional[int] = None,
                         circular_id: Optional[int] = None,
                         status: Optional[ApplicationStatus] = None,
                         skip: int = 0, limit: int = 100) -> List[Application]:
        """Get applications with filters."""
        query = db.query(Application).options(
            joinedload(Application.student).joinedload(User.student_profile),
            joinedload(Application.job_posting).joinedload(JobPosting.company)
        )
        
        if student_id:
            query = query.filter(Application.student_id == student_id)
        if job_posting_id:
            query = query.filter(Application.job_posting_id == job_posting_id)
        if circular_id:
            from ..models.recruitment_circular import RecruitmentCircularJob
            query = query.join(
                RecruitmentCircularJob,
                RecruitmentCircularJob.job_posting_id == Application.job_posting_id
            ).filter(RecruitmentCircularJob.circular_id == circular_id)
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

    def confirm_external_application(
        self,
        db: Session,
        application_or_id: Union[Application, int],
        current_user: Optional[User] = None
    ) -> Application:
        """
        Idempotently confirm student external application submission.
        Validates ownership, job visibility, and external URL presence.
        Preserves original confirmation timestamp on repeated requests.
        """
        from datetime import timezone

        if isinstance(application_or_id, Application):
            application = application_or_id
        else:
            application = self.get_application(db, application_or_id)
            if not application:
                raise ValueError(f"Application with ID {application_or_id} not found")

        if current_user:
            if current_user.role == UserRole.STUDENT and application.student_id != current_user.id:
                raise PermissionError("You can only confirm your own applications")

        job = application.job_posting or self.get_job_posting(db, application.job_posting_id)
        if not job:
            raise ValueError("Associated job posting not found")

        if job.status != JobStatus.OPEN:
            raise ValueError("Job posting is no longer open for applications")

        if not job.application_url or not job.application_url.strip():
            raise ValueError("Job posting does not have an external application URL to confirm")

        # Idempotent: preserve original timestamp if already set
        if application.external_applied_at is not None:
            logger.info(f"External application already confirmed for app {application.id} at {application.external_applied_at}")
            return application

        now_utc = datetime.now(timezone.utc)
        application.external_applied_at = now_utc
        application.updated_at = now_utc
        db.commit()
        db.refresh(application)
        logger.info(f"✅ External application confirmed: Student {application.student_id} -> Job {job.id} at {now_utc}")

        # Notify Placement Officers of first-time external confirmation
        try:
            student_user = current_user if (current_user and current_user.id == application.student_id) else application.student
            self.notify_officers_on_external_confirm(db, application, job, student_user)
        except Exception as e:
            logger.error(f"❌ Failed to dispatch external confirmation notifications for app {application.id}: {e}", exc_info=True)

        return application

    def notify_officers_on_external_confirm(
        self,
        db: Session,
        application: Application,
        job: JobPosting,
        student: Optional[User] = None
    ) -> int:
        """
        Notify Placement Officers when a student confirms external application submission.
        Uses event_key for deduplication and protects sensitive student data.
        Returns the number of notifications created.
        """
        # 1. Identify recipient placement officers
        officers = db.query(User).filter(
            User.role == UserRole.PLACEMENT_OFFICER,
            User.is_active == True
        ).all()

        recipient_ids = {u.id for u in officers}
        # If job creator is an active placement officer or admin, ensure they are included
        if job.created_by and job.created_by not in recipient_ids:
            creator = db.query(User).filter(
                User.id == job.created_by,
                User.is_active == True,
                User.role.in_([UserRole.PLACEMENT_OFFICER, UserRole.ADMIN])
            ).first()
            if creator:
                recipient_ids.add(creator.id)

        if not recipient_ids:
            logger.warning(f"No active Placement Officers found to notify for external confirmation of app {application.id}")
            return 0

        # Resolve student name safely
        student_name = None
        if student and hasattr(student, 'name') and student.name:
            student_name = student.name
        elif application.student and hasattr(application.student, 'name') and application.student.name:
            student_name = application.student.name
        else:
            student_rec = db.query(User).filter(User.id == application.student_id).first()
            student_name = student_rec.name if student_rec else f"Student #{application.student_id}"

        # Resolve company name safely
        company_name = job.company.name if job.company else "Company"

        applied_time_str = ""
        if application.external_applied_at and hasattr(application.external_applied_at, "strftime"):
            applied_time_str = application.external_applied_at.strftime("%d %b %Y, %H:%M UTC")
        else:
            applied_time_str = datetime.utcnow().strftime("%d %b %Y, %H:%M UTC")

        title = f"📝 External Application: {student_name} - {job.title}"
        message = (
            f"{student_name} confirmed external application submission for "
            f"{job.title} at {company_name} on {applied_time_str}."
        )

        notif_count = 0
        for officer_id in recipient_ids:
            event_key = f"external_confirm:{application.id}:officer:{officer_id}"

            existing = db.query(Notification).filter(Notification.event_key == event_key).first()
            if existing:
                continue

            notif = Notification(
                user_id=officer_id,
                type="placement_confirm",
                title=title,
                message=message,
                reference_id=job.id,
                event_key=event_key,
                is_read=False
            )
            db.add(notif)
            notif_count += 1

        if notif_count > 0:
            try:
                db.commit()
                logger.info(f"📢 Created {notif_count} external application confirmation notifications for app {application.id}")
            except Exception as e:
                db.rollback()
                logger.warning(f"Handled notification commit for app {application.id}: {e}")

        return notif_count
    
    # ============================================
    # SHORTLIST MANAGEMENT
    # ============================================
    
    def create_shortlist(
        self,
        db: Session,
        shortlist_data: ShortlistCreate,
        current_user_id: Optional[int] = None
    ) -> Shortlist:
        """Create a new shortlist entry with authoritative validation."""
        # 1. Fetch and validate job posting
        job = db.query(JobPosting).filter(JobPosting.id == shortlist_data.job_posting_id).first()
        if not job:
            raise ValueError(f"Job posting with ID {shortlist_data.job_posting_id} not found")

        # 2. Authoritative Company Relationship: Verify or auto-resolve from JobPosting
        if shortlist_data.company_id and shortlist_data.company_id != job.company_id:
            raise ValueError(
                f"Company ID {shortlist_data.company_id} does not match job posting's company ({job.company_id})"
            )
        resolved_company_id = job.company_id

        # 3. Fetch and validate student
        student = db.query(User).filter(User.id == shortlist_data.student_id, User.role == UserRole.STUDENT).first()
        if not student:
            raise ValueError(f"Student with ID {shortlist_data.student_id} not found")

        # 4. Check for duplicate shortlisting
        existing = db.query(Shortlist).filter(
            Shortlist.student_id == shortlist_data.student_id,
            Shortlist.job_posting_id == shortlist_data.job_posting_id
        ).first()
        if existing:
            raise ValueError(f"Student {student.name or shortlist_data.student_id} is already shortlisted for this job")

        # 5. Create shortlist entry
        shortlist = Shortlist(
            student_id=shortlist_data.student_id,
            company_id=resolved_company_id,
            job_posting_id=job.id,
            reason=shortlist_data.reason,
            shortlisted_by=shortlist_data.shortlisted_by or current_user_id
        )
        db.add(shortlist)
        db.commit()
        db.refresh(shortlist)

        # 6. Update application status to SHORTLISTED if an application exists
        application = db.query(Application).filter(
            Application.student_id == shortlist_data.student_id,
            Application.job_posting_id == shortlist_data.job_posting_id
        ).first()
        if application:
            application.status = ApplicationStatus.SHORTLISTED
            application.updated_at = datetime.utcnow()
            db.commit()

        logger.info(f"✅ Student {shortlist_data.student_id} shortlisted for job {job.id} at company {resolved_company_id}")
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
    # ELIGIBILITY & MATCHING
    # ============================================
    
    def check_student_eligibility(self, db: Session, student_id: int, job_posting_id: int) -> StudentEligibility:
        """Check if a student is eligible for a job posting with normalized and semantic skill matching."""
        student = db.query(User).filter(User.id == student_id).first()
        job = self.get_job_posting(db, job_posting_id)
        
        if not student or not job:
            raise ValueError("Student or job not found")
        
        return job_matching_service.match_student_to_job(db, student, job)
    
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
        all_candidates = []
        for student in students:
            try:
                eligibility = self.check_student_eligibility(db, student.id, request.job_posting_id)
                all_candidates.append(eligibility)
                if eligibility.is_eligible:
                    eligible_students.append(eligibility)
            except Exception as e:
                logger.error(f"Error checking eligibility for student {student.id}: {str(e)}")
        
        # Sort by match score (highest first, None scores at end)
        eligible_students.sort(key=lambda x: (x.match_score if x.match_score is not None else -1.0), reverse=True)
        all_candidates.sort(key=lambda x: (x.match_score if x.match_score is not None else -1.0), reverse=True)
        
        return JobMatchResponse(
            job_posting_id=job.id,
            job_title=job.title,
            company_name=job.company.name if job.company else "Unknown",
            total_eligible=len(eligible_students),
            eligible_students=eligible_students,
            top_candidates=eligible_students[:10],
            all_candidates=all_candidates
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
        
        # Placed / Selected students calculation:
        # A student is considered placed if they have at least one Application with status SELECTED
        # OR their StudentProfileExtended has placement_status PLACED.
        # Intermediate shortlisting (ApplicationStatus.SHORTLISTED or Shortlist entry) is tracked
        # separately and NOT counted as a final placement.
        selected_student_ids = set(
            r[0] for r in db.query(Application.student_id).filter(Application.status == ApplicationStatus.SELECTED).all()
        )
        profile_placed_ids = set(
            r[0] for r in db.query(StudentProfileExtended.user_id).filter(StudentProfileExtended.placement_status == PlacementStatus.PLACED).all()
        )
        placed_student_ids = selected_student_ids.union(profile_placed_ids)
        total_placed = len(placed_student_ids)

        placement_rate = (total_placed / total_students * 100.0) if total_students > 0 else 0.0

        # Verified Accounting Metrics (Phase 3.3.4)
        from .placement_offer_service import placement_offer_service
        verified_metrics = placement_offer_service.get_placement_accounting_metrics(db)

        return PlacementStatistics(
            total_companies=total_companies,
            active_companies=active_companies,
            total_jobs=total_jobs,
            open_jobs=open_jobs,
            total_applications=total_applications,
            total_shortlists=total_shortlists,
            total_students=total_students,
            # Legacy metrics
            total_placed=total_placed,
            placement_rate=round(placement_rate, 2),
            legacy_placed_count=total_placed,
            legacy_placement_rate=round(placement_rate, 2),
            # Verified Accounting metrics
            total_verified_offers=verified_metrics["total_verified_offers"],
            verified_offers_count=verified_metrics["total_verified_offers"],
            accepted_offers_count=verified_metrics["accepted_offers_count"],
            declined_offers_count=verified_metrics["declined_offers_count"],
            rescinded_offers_count=verified_metrics["rescinded_offers_count"],
            pending_offers_count=verified_metrics["pending_offers_count"],
            verified_placed_students_count=verified_metrics["verified_placed_students_count"],
            students_with_multiple_offers_count=verified_metrics["students_with_multiple_offers_count"],
            verified_placement_rate=verified_metrics["verified_placement_rate"],
            # Breakdowns
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