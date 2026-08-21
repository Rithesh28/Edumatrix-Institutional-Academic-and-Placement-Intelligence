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
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from celery import shared_task

from ..core.database import SessionLocal
from ..models.user import User, UserRole
from ..models.company import Company
from ..models.job_posting import JobPosting, JobStatus
from ..models.application import Application, ApplicationStatus
from ..models.shortlist import Shortlist
from ..models.notification import Notification
from ..services.placement_service import placement_service

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
# DEADLINE & REMINDER TASKS
# ============================================

@shared_task(name="placement_tasks.check_application_deadlines", max_retries=2)
def check_application_deadlines():
    """
    Check for upcoming application deadlines and send reminders.
    """
    logger.info("🔄 Checking application deadlines...")
    
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        # Check deadlines within next 3 days
        deadline_threshold = now + timedelta(days=3)
        
        jobs = db.query(JobPosting).filter(
            JobPosting.status == JobStatus.OPEN,
            JobPosting.application_deadline <= deadline_threshold,
            JobPosting.application_deadline >= now
        ).all()
        
        for job in jobs:
            days_left = (job.application_deadline - now).days
            if days_left < 0:
                continue
            
            # Get students who haven't applied
            applied_student_ids = db.query(Application.student_id).filter(
                Application.job_posting_id == job.id
            ).all()
            applied_ids = [a[0] for a in applied_student_ids]
            
            students = db.query(User).filter(
                User.role == UserRole.STUDENT,
                User.id.notin_(applied_ids) if applied_ids else True
            ).all()
            
            company_name = job.company.name if job.company else "Unknown"
            
            for student in students:
                notification = Notification(
                    user_id=student.id,
                    type="placement",
                    title=f"⏰ Deadline Approaching: {job.title}",
                    message=f"Application deadline for {job.title} at {company_name} is in {days_left} days. Apply now!",
                    reference_id=job.id,
                    is_read=False
                )
                db.add(notification)
            
            logger.info(f"📢 Sent deadline reminders for {job.title} to {len(students)} students")
        
        db.commit()
        logger.info(f"✅ Deadline check complete. Found {len(jobs)} upcoming deadlines")
        
    except Exception as e:
        logger.error(f"❌ Deadline check failed: {str(e)}")
        db.rollback()
    finally:
        db.close()


@shared_task(name="placement_tasks.close_expired_jobs", max_retries=2)
def close_expired_jobs():
    """
    Automatically close job postings past their application deadline.
    """
    logger.info("🔄 Closing expired jobs...")
    
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        
        expired_jobs = db.query(JobPosting).filter(
            JobPosting.status == JobStatus.OPEN,
            JobPosting.application_deadline < now
        ).all()
        
        for job in expired_jobs:
            job.status = JobStatus.CLOSED
            job.updated_at = now
            logger.info(f"🔒 Job closed: {job.title} (ID: {job.id})")
        
        db.commit()
        logger.info(f"✅ Closed {len(expired_jobs)} expired jobs")
        
    except Exception as e:
        logger.error(f"❌ Failed to close expired jobs: {str(e)}")
        db.rollback()
    finally:
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