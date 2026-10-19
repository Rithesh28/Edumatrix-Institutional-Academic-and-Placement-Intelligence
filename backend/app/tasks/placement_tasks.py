"""
Placement Celery Tasks

Handles background tasks for placement operations:
- Match students for jobs (async)
- Send placement notifications
- Generate placement reports
- Update placement statistics
- Sync placement data
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from celery import shared_task
from sqlalchemy.orm import joinedload

from ..core.database import SessionLocal
from ..models.user import User, UserRole
from ..models.company import Company
from ..models.job_posting import JobPosting, JobStatus
from ..models.application import Application, ApplicationStatus
from ..models.shortlist import Shortlist
from ..models.notification import Notification
from ..services.placement_service import placement_service
from ..services.job_matching_service import job_matching_service

logger = logging.getLogger(__name__)


# ============================================
# MATCHING TASKS
# ============================================

@shared_task(name="placement_tasks.match_students_for_job", bind=True, max_retries=3)
def match_students_for_job(self, job_posting_id: int, student_ids: Optional[List[int]] = None):
    """
    Asynchronously match students for a job posting.
    
    Args:
        job_posting_id: ID of the job posting
        student_ids: Optional list of student IDs to match (if None, match all)
    """
    logger.info(f"🔄 Starting job matching for job {job_posting_id}")
    
    db = SessionLocal()
    try:
        from ..schemas.placement import JobMatchRequest
        
        request = JobMatchRequest(
            job_posting_id=job_posting_id,
            student_ids=student_ids
        )
        
        result = placement_service.match_students_for_job(db, request)
        
        logger.info(f"✅ Job matching complete for {job_posting_id}: {result.total_eligible} eligible students")
        
        # Create notifications for eligible students
        if result.eligible_students:
            create_placement_notifications.delay(
                job_posting_id=job_posting_id,
                student_ids=[s.student_id for s in result.eligible_students],
                notification_type="match"
            )
        
        return {
            "job_posting_id": job_posting_id,
            "total_eligible": result.total_eligible,
            "status": "completed"
        }
        
    except Exception as e:
        logger.error(f"❌ Job matching failed for {job_posting_id}: {str(e)}")
        self.retry(countdown=60, exc=e)
    finally:
        db.close()


@shared_task(name="placement_tasks.batch_match_jobs", max_retries=2)
def batch_match_jobs(job_posting_ids: List[int]):
    """
    Batch match students for multiple job postings.
    
    Args:
        job_posting_ids: List of job posting IDs
    """
    logger.info(f"🔄 Starting batch job matching for {len(job_posting_ids)} jobs")
    
    results = []
    for job_id in job_posting_ids:
        try:
            result = match_students_for_job.delay(job_id)
            results.append({"job_id": job_id, "task_id": result.id})
        except Exception as e:
            logger.error(f"❌ Failed to start matching for job {job_id}: {str(e)}")
            results.append({"job_id": job_id, "error": str(e)})
    
    logger.info(f"✅ Batch job matching initiated for {len(results)} jobs")
    return {"total_jobs": len(job_posting_ids), "results": results}


# ============================================
# NOTIFICATION TASKS
# ============================================

@shared_task(name="placement_tasks.create_placement_notifications", max_retries=3)
def create_placement_notifications(
    job_posting_id: int,
    student_ids: List[int],
    notification_type: str = "match"
):
    """
    Create placement notifications for students.
    
    Args:
        job_posting_id: ID of the job posting
        student_ids: List of student IDs
        notification_type: Type of notification (match, shortlist, selection, rejection)
    """
    logger.info(f"📢 Creating {notification_type} notifications for {len(student_ids)} students")
    
    db = SessionLocal()
    try:
        job = db.query(JobPosting).filter(JobPosting.id == job_posting_id).first()
        if not job:
            logger.error(f"❌ Job posting {job_posting_id} not found")
            return
        
        company_name = job.company.name if job.company else "Unknown Company"
        
        # Different notification messages based on type
        messages = {
            "match": {
                "title": f"🎯 New Job Match: {job.title}",
                "message": f"You have been matched with {company_name} for {job.title}. Check your eligibility and apply now!"
            },
            "shortlist": {
                "title": f"⭐ Shortlisted: {job.title}",
                "message": f"Congratulations! You have been shortlisted for {job.title} at {company_name}."
            },
            "selection": {
                "title": f"🎉 Selected: {job.title}",
                "message": f"Congratulations! You have been selected for {job.title} at {company_name}."
            },
            "rejection": {
                "title": f"📫 Application Update: {job.title}",
                "message": f"Your application for {job.title} at {company_name} has been reviewed. Thank you for applying."
            }
        }
        
        msg = messages.get(notification_type, messages["match"])
        
        for student_id in student_ids:
            notification = Notification(
                user_id=student_id,
                type="placement",
                title=msg["title"],
                message=msg["message"],
                reference_id=job_posting_id,
                is_read=False
            )
            db.add(notification)
        
        db.commit()
        logger.info(f"✅ Created {len(student_ids)} {notification_type} notifications")
        
    except Exception as e:
        logger.error(f"❌ Notification creation failed: {str(e)}")
        db.rollback()
        self.retry(countdown=60, exc=e)
    finally:
        db.close()


@shared_task(name="placement_tasks.send_shortlist_notifications", max_retries=3)
def send_shortlist_notifications(shortlist_ids: List[int]):
    """
    Send notifications for newly shortlisted students.
    
    Args:
        shortlist_ids: List of shortlist entry IDs
    """
    logger.info(f"📢 Sending shortlist notifications for {len(shortlist_ids)} entries")
    
    db = SessionLocal()
    try:
        shortlists = db.query(Shortlist).filter(Shortlist.id.in_(shortlist_ids)).all()
        
        for shortlist in shortlists:
            job = db.query(JobPosting).filter(JobPosting.id == shortlist.job_posting_id).first()
            if not job:
                continue
            
            company_name = job.company.name if job.company else "Unknown Company"
            
            notification = Notification(
                user_id=shortlist.student_id,
                type="placement",
                title=f"⭐ Shortlisted: {job.title}",
                message=f"Congratulations! You have been shortlisted for {job.title} at {company_name}.",
                reference_id=job.id,
                is_read=False
            )
            db.add(notification)
        
        db.commit()
        logger.info(f"✅ Sent {len(shortlists)} shortlist notifications")
        
    except Exception as e:
        logger.error(f"❌ Shortlist notification failed: {str(e)}")
        db.rollback()
    finally:
        db.close()


# ============================================
# REPORT GENERATION TASKS
# ============================================

@shared_task(name="placement_tasks.generate_placement_report", max_retries=2)
def generate_placement_report():
    """
    Generate placement report for all companies and students.
    """
    logger.info("🔄 Generating placement report...")
    
    db = SessionLocal()
    try:
        # Get placement statistics
        stats = placement_service.get_placement_statistics(db)
        
        # Get all companies
        companies = db.query(Company).filter(Company.is_active == True).all()
        company_stats = []
        for company in companies:
            cs = placement_service.get_company_statistics(db, company.id)
            if cs:
                company_stats.append(cs)
        
        # Get all students with placement status
        students = db.query(User).filter(User.role == UserRole.STUDENT).all()
        student_status = []
        for student in students:
            status = placement_service.get_student_placement_status(db, student.id)
            if status:
                student_status.append(status)
        
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "statistics": {
                "total_companies": stats.total_companies,
                "active_companies": stats.active_companies,
                "total_jobs": stats.total_jobs,
                "open_jobs": stats.open_jobs,
                "total_applications": stats.total_applications,
                "total_shortlists": stats.total_shortlists,
                "total_students": stats.total_students,
                "placement_rate": stats.placement_rate
            },
            "companies": [{
                "name": cs.company_name,
                "total_jobs": cs.total_jobs,
                "total_applications": cs.total_applications,
                "total_shortlists": cs.total_shortlists,
                "total_selected": cs.total_selected
            } for cs in company_stats],
            "students": [{
                "name": s.student_name,
                "branch": s.branch,
                "status": s.status,
                "applications": s.total_applications,
                "shortlists": s.shortlisted_count,
                "selections": s.selected_count
            } for s in student_status]
        }
        
        logger.info(f"✅ Placement report generated for {len(company_stats)} companies and {len(student_status)} students")
        return report
        
    except Exception as e:
        logger.error(f"❌ Placement report generation failed: {str(e)}")
        self.retry(countdown=60, exc=e)
    finally:
        db.close()


# ============================================
# PUBLICATION NOTIFICATION TASK
# ============================================

@shared_task(name="placement_tasks.dispatch_job_publication_notifications", bind=True, max_retries=3)
def dispatch_job_publication_notifications(self, job_id: int):
    """
    Asynchronously notify eligible students when a job is published.
    Idempotent and safe against duplicates via event_key.
    """
    logger.info(f"📢 Starting async job-publication notifications for job {job_id}")
    db = SessionLocal()
    try:
        job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
        if not job:
            logger.warning(f"Job {job_id} not found; skipping publication notifications.")
            return {"job_id": job_id, "status": "job_not_found"}

        if job.status != JobStatus.OPEN:
            logger.info(f"Job {job_id} status is {job.status} (not OPEN); skipping publication notifications.")
            return {"job_id": job_id, "status": "job_not_open"}

        notif_count = placement_service.notify_students_on_job_publish(db, job)
        logger.info(f"✅ Dispatched {notif_count} publication notifications for job {job_id}")
        return {
            "job_id": job_id,
            "status": "completed",
            "notifications_created": notif_count
        }
    except Exception as e:
        logger.error(f"❌ Job publication notification failed for job {job_id}: {e}")
        try:
            self.retry(countdown=30, exc=e)
        except Exception:
            raise
    finally:
        db.close()


# ============================================
# DEADLINE & REMINDER TASKS
# ============================================

@shared_task(name="placement_tasks.check_application_deadlines", bind=True, max_retries=2)
def check_application_deadlines(self, window_days: int = 3):
    """
    Check for upcoming application deadlines and send deduplicated reminders
    exclusively to eligible students who have not yet applied.
    """
    logger.info(f"🔄 Checking application deadlines (window: {window_days} days)...")
    db = SessionLocal()
    try:
        now_utc = datetime.now(timezone.utc)
        deadline_threshold = now_utc + timedelta(days=window_days)

        # Query open jobs with future deadlines within window
        jobs = db.query(JobPosting).options(
            joinedload(JobPosting.company)
        ).filter(
            JobPosting.status == JobStatus.OPEN,
            JobPosting.application_deadline.isnot(None),
            JobPosting.application_deadline <= deadline_threshold,
            JobPosting.application_deadline >= now_utc
        ).all()

        total_notifications_sent = 0

        # Query all active students with profile loaded once
        students = db.query(User).options(
            joinedload(User.student_profile)
        ).filter(
            User.role == UserRole.STUDENT,
            User.is_active == True
        ).all()

        date_bucket = now_utc.strftime("%Y-%m-%d")

        for job in jobs:
            deadline = job.application_deadline
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)

            remaining = (deadline - now_utc).total_seconds()
            if remaining < 0:
                continue

            days_left = max(0, int(remaining // 86400))
            hours_left = max(0, int(remaining // 3600))

            if days_left == 0:
                timing_str = f"{max(1, hours_left)} hour(s)"
            elif days_left == 1:
                timing_str = "1 day"
            else:
                timing_str = f"{days_left} days"

            # Query student IDs who already applied for this job
            applied_student_ids = {
                r[0] for r in db.query(Application.student_id).filter(
                    Application.job_posting_id == job.id
                ).all()
            }

            company_name = job.company.name if job.company else "Campus Recruiter"
            title = f"⏰ Deadline Approaching: {job.title} at {company_name}"
            formatted_deadline = deadline.strftime("%d %b %Y, %I:%M %p")
            message = (
                f"Only {timing_str} left to apply for {job.title} at {company_name} "
                f"(Deadline: {formatted_deadline}). Submit your application before it closes!"
            )

            job_notifs = 0
            for student in students:
                # Exclude students who already applied
                if student.id in applied_student_ids:
                    continue

                # Authoritative eligibility filter (respects branch and CGPA)
                profile = student.student_profile
                elig_res = job_matching_service.check_eligibility(profile, job)
                if not elig_res.is_eligible:
                    continue

                event_key = f"job_deadline:{job.id}:student:{student.id}:{date_bucket}"

                existing = db.query(Notification).filter(Notification.event_key == event_key).first()
                if existing:
                    continue

                notification = Notification(
                    user_id=student.id,
                    type="placement_deadline",
                    title=title,
                    message=message,
                    reference_id=job.id,
                    event_key=event_key,
                    is_read=False
                )
                db.add(notification)
                job_notifs += 1

            if job_notifs > 0:
                try:
                    db.commit()
                    total_notifications_sent += job_notifs
                    logger.info(f"📢 Sent {job_notifs} deadline reminders for {job.title} (ID: {job.id})")
                except Exception as commit_err:
                    db.rollback()
                    logger.warning(f"Failed to commit deadline reminders for job {job.id}: {commit_err}")

        logger.info(f"✅ Deadline check complete. Found {len(jobs)} upcoming deadlines, sent {total_notifications_sent} reminders.")
        return {
            "jobs_checked": len(jobs),
            "notifications_sent": total_notifications_sent,
            "status": "completed"
        }

    except Exception as e:
        logger.error(f"❌ Deadline check failed: {str(e)}")
        db.rollback()
        try:
            self.retry(countdown=60, exc=e)
        except Exception:
            raise
    finally:
        db.close()


@shared_task(name="placement_tasks.close_expired_jobs", max_retries=2)
def close_expired_jobs(db=None):
    """
    Automatically close job postings past their application deadline.
    """
    logger.info("🔄 Closing expired jobs...")
    
    close_db_on_exit = False
    if db is None:
        db = SessionLocal()
        close_db_on_exit = True
    try:
        now = datetime.utcnow()
        
        expired_jobs = db.query(JobPosting).filter(
            JobPosting.status == JobStatus.OPEN,
            JobPosting.application_deadline.isnot(None),
            JobPosting.application_deadline < now
        ).all()
        
        for job in expired_jobs:
            job.status = JobStatus.CLOSED
            job.updated_at = now
            logger.info(f"🔒 Job closed: {job.title} (ID: {job.id})")
        
        db.commit()
        logger.info(f"✅ Closed {len(expired_jobs)} expired jobs")
        return len(expired_jobs)
    except Exception as e:
        logger.error(f"❌ Failed to close expired jobs: {str(e)}")
        db.rollback()
        raise
    finally:
        if close_db_on_exit:
            db.close()


# ============================================
# SYNC TASKS
# ============================================

@shared_task(name="placement_tasks.sync_placement_data", max_retries=2)
def sync_placement_data():
    """
    Sync placement data across services (refresh statistics, update statuses).
    """
    logger.info("🔄 Syncing placement data...")
    
    db = SessionLocal()
    try:
        # Update application statuses based on shortlists
        shortlisted_apps = db.query(Application).filter(
            Application.status == ApplicationStatus.APPLIED
        ).all()
        
        updated_count = 0
        for app in shortlisted_apps:
            # Check if student is shortlisted
            shortlist = db.query(Shortlist).filter(
                Shortlist.student_id == app.student_id,
                Shortlist.job_posting_id == app.job_posting_id
            ).first()
            
            if shortlist and app.status != ApplicationStatus.SHORTLISTED:
                app.status = ApplicationStatus.SHORTLISTED
                app.updated_at = datetime.utcnow()
                updated_count += 1
        
        db.commit()
        logger.info(f"✅ Synced placement data. Updated {updated_count} applications")
        
    except Exception as e:
        logger.error(f"❌ Sync failed: {str(e)}")
        db.rollback()
    finally:
        db.close()


# ============================================
# PLACEMENT OFFICER DASHBOARD TASKS
# ============================================

@shared_task(name="placement_tasks.update_dashboard_stats", max_retries=2)
def update_dashboard_stats():
    """
    Update dashboard statistics cache.
    """
    logger.info("🔄 Updating dashboard statistics...")
    
    db = SessionLocal()
    try:
        stats = placement_service.get_placement_statistics(db)
        
        # Cache statistics (you can store in Redis if needed)
        logger.info(f"📊 Dashboard stats updated: {stats.total_companies} companies, {stats.total_jobs} jobs")
        
        return {
            "total_companies": stats.total_companies,
            "active_companies": stats.active_companies,
            "total_jobs": stats.total_jobs,
            "open_jobs": stats.open_jobs,
            "total_applications": stats.total_applications,
            "total_shortlists": stats.total_shortlists,
            "placement_rate": stats.placement_rate
        }
        
    except Exception as e:
        logger.error(f"❌ Dashboard stats update failed: {str(e)}")
        self.retry(countdown=60, exc=e)
    finally:
        db.close()