"""
Recruitment Circular Service

Handles all recruitment circular business logic:
- Draft creation, update, retrieval, listing
- Attachment association and metadata enrichment
- Job links management (same-company enforcement)
- Atomic publication with linked draft jobs
- Idempotent student notification dispatch with deduplication
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from datetime import datetime
from uuid import UUID

from ..models.recruitment_circular import (
    RecruitmentCircular,
    RecruitmentCircularStatus,
    RecruitmentCircularAttachment,
    RecruitmentCircularJob,
    AttachmentType,
)
from ..models.company import Company
from ..models.job_posting import JobPosting, JobStatus
from ..models.file import File
from ..models.user import User, UserRole
from ..models.notification import Notification
from ..schemas.recruitment_circular import (
    RecruitmentCircularCreate,
    RecruitmentCircularUpdate,
    CircularAttachmentCreate,
    RecruitmentCircularResponse,
    CircularAttachmentResponse,
    CircularJobResponse,
)

logger = logging.getLogger(__name__)


class RecruitmentCircularService:
    """Service handling company recruitment circulars."""

    def _enrich_circular_response(self, circular: RecruitmentCircular) -> Dict[str, Any]:
        """Convert a RecruitmentCircular model instance to a dict ready for RecruitmentCircularResponse."""
        company_name = circular.company.name if circular.company else None
        company_logo_url = circular.company.logo_url if circular.company else None
        creator_name = circular.creator.name if circular.creator else None

        # Build attachments list
        attachments_list = []
        for att in (circular.attachments or []):
            file_meta = att.file
            att_dict = {
                "id": att.id,
                "circular_id": att.circular_id,
                "file_id": att.file_id,
                "attachment_type": att.attachment_type,
                "display_order": att.display_order,
                "created_at": att.created_at,
                "filename": file_meta.filename if file_meta else None,
                "file_size": file_meta.file_size if file_meta else None,
                "mime_type": file_meta.mime_type if file_meta else None,
                "download_url": f"/files/{att.file_id}/download",
                "preview_url": f"/files/{att.file_id}/preview",
            }
            attachments_list.append(att_dict)

        # Sort attachments by display_order
        attachments_list.sort(key=lambda x: (x["display_order"], x["id"]))

        # Build linked jobs list
        jobs_list = []
        for cj in (circular.linked_jobs or []):
            job = cj.job_posting
            if job:
                job_dict = {
                    "id": cj.id,
                    "circular_id": cj.circular_id,
                    "job_posting_id": cj.job_posting_id,
                    "created_at": cj.created_at,
                    "title": job.title,
                    "status": job.status.value if hasattr(job.status, "value") else str(job.status),
                    "company_name": job.company.name if job.company else company_name,
                    "experience_level": job.experience_level,
                    "salary_range": job.salary_range,
                    "location": job.location,
                    "required_skills": job.required_skills or [],
                    "branch_eligibility": job.branch_eligibility or [],
                    "application_deadline": job.application_deadline,
                    "drive_date": job.drive_date,
                    "application_url": getattr(job, "application_url", None),
                }
                jobs_list.append(job_dict)

        return {
            "id": circular.id,
            "company_id": circular.company_id,
            "company_name": company_name,
            "company_logo_url": company_logo_url,
            "title": circular.title,
            "summary": circular.summary,
            "instructions": circular.instructions,
            "application_deadline": circular.application_deadline,
            "drive_date": circular.drive_date,
            "branch_eligibility": circular.branch_eligibility or [],
            "status": circular.status,
            "created_by": circular.created_by,
            "creator_name": creator_name,
            "created_at": circular.created_at,
            "updated_at": circular.updated_at,
            "published_at": circular.published_at,
            "attachments": attachments_list,
            "linked_jobs": jobs_list,
            "attachments_count": len(attachments_list),
            "linked_jobs_count": len(jobs_list),
        }

    def create_draft(self, db: Session, data: RecruitmentCircularCreate, current_user: User) -> Dict[str, Any]:
        """Create a new recruitment circular draft."""
        # 1. Verify company exists
        company = db.query(Company).filter(Company.id == data.company_id).first()
        if not company:
            raise ValueError(f"Company with ID {data.company_id} does not exist.")

        circular = RecruitmentCircular(
            company_id=data.company_id,
            title=data.title.strip(),
            summary=data.summary,
            instructions=data.instructions,
            application_deadline=data.application_deadline,
            drive_date=data.drive_date,
            branch_eligibility=data.branch_eligibility or [],
            status=RecruitmentCircularStatus.DRAFT,
            created_by=current_user.id,
        )
        db.add(circular)
        db.flush()  # Obtain circular.id

        # 2. Add initial attachments if supplied
        if data.attachments:
            for att_in in data.attachments:
                file_obj = db.query(File).filter(File.id == att_in.file_id).first()
                if not file_obj:
                    db.rollback()
                    raise ValueError(f"File with ID {att_in.file_id} not found.")
                att = RecruitmentCircularAttachment(
                    circular_id=circular.id,
                    file_id=att_in.file_id,
                    attachment_type=att_in.attachment_type.value if hasattr(att_in.attachment_type, "value") else str(att_in.attachment_type),
                    display_order=att_in.display_order,
                )
                db.add(att)

        # 3. Add initial linked jobs if supplied (must be same company)
        if data.job_posting_ids:
            for j_id in data.job_posting_ids:
                job = db.query(JobPosting).filter(JobPosting.id == j_id).first()
                if not job:
                    db.rollback()
                    raise ValueError(f"Job posting with ID {j_id} not found.")
                if job.company_id != circular.company_id:
                    db.rollback()
                    raise ValueError(f"Job posting {j_id} belongs to another company, not company {circular.company_id}.")
                link = RecruitmentCircularJob(
                    circular_id=circular.id,
                    job_posting_id=j_id,
                )
                db.add(link)

        db.commit()
        db.refresh(circular)
        logger.info(f"✅ Created recruitment circular draft ID {circular.id} for company {data.company_id}")
        return self._enrich_circular_response(circular)

    def get_circular_raw(self, db: Session, circular_id: int) -> Optional[RecruitmentCircular]:
        """Fetch raw ORM model with relationships joined."""
        return db.query(RecruitmentCircular).options(
            joinedload(RecruitmentCircular.company),
            joinedload(RecruitmentCircular.creator),
            joinedload(RecruitmentCircular.attachments).joinedload(RecruitmentCircularAttachment.file),
            joinedload(RecruitmentCircular.linked_jobs).joinedload(RecruitmentCircularJob.job_posting).joinedload(JobPosting.company),
        ).filter(RecruitmentCircular.id == circular_id).first()

    def get_circular(self, db: Session, circular_id: int, current_user: User) -> Optional[Dict[str, Any]]:
        """Retrieve circular details enforcing access controls."""
        circular = self.get_circular_raw(db, circular_id)
        if not circular:
            return None

        # Student access enforcement
        if current_user.role == UserRole.STUDENT:
            if circular.status != RecruitmentCircularStatus.PUBLISHED:
                # Drafts must never leak to students
                return None
            # Branch eligibility check
            if circular.branch_eligibility and len(circular.branch_eligibility) > 0:
                s_branch = None
                if current_user.student_profile and current_user.student_profile.branch:
                    s_branch = current_user.student_profile.branch
                elif current_user.department:
                    s_branch = current_user.department
                
                target_branches = {str(b).strip().lower() for b in circular.branch_eligibility if b}
                if not s_branch or str(s_branch).strip().lower() not in target_branches:
                    return None

        elif current_user.role not in [UserRole.PLACEMENT_OFFICER, UserRole.ADMIN]:
            # Lecturers and HODs must not access recruitment circular details
            return None

        return self._enrich_circular_response(circular)

    def list_circulars(
        self,
        db: Session,
        current_user: User,
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
        company_id: Optional[int] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List circulars with role-based filtering."""
        query = db.query(RecruitmentCircular).options(
            joinedload(RecruitmentCircular.company),
            joinedload(RecruitmentCircular.creator),
            joinedload(RecruitmentCircular.attachments).joinedload(RecruitmentCircularAttachment.file),
            joinedload(RecruitmentCircular.linked_jobs).joinedload(RecruitmentCircularJob.job_posting).joinedload(JobPosting.company),
        )

        if current_user.role == UserRole.STUDENT:
            # Students can only see published circulars
            query = query.filter(RecruitmentCircular.status == RecruitmentCircularStatus.PUBLISHED)
        elif current_user.role in [UserRole.PLACEMENT_OFFICER, UserRole.ADMIN]:
            if status:
                query = query.filter(RecruitmentCircular.status == status)
        else:
            # Lecturers and HODs do not have recruitment circular viewing permissions
            return []

        if company_id:
            query = query.filter(RecruitmentCircular.company_id == company_id)

        if search:
            search_term = f"%{search}%"
            query = query.join(RecruitmentCircular.company).filter(
                or_(
                    RecruitmentCircular.title.ilike(search_term),
                    RecruitmentCircular.summary.ilike(search_term),
                    Company.name.ilike(search_term),
                )
            )

        query = query.order_by(RecruitmentCircular.created_at.desc())
        all_circulars = query.offset(skip).limit(limit).all()

        results = []
        for circ in all_circulars:
            # Filter branch eligibility for students
            if current_user.role == UserRole.STUDENT and circ.branch_eligibility and len(circ.branch_eligibility) > 0:
                s_branch = None
                if current_user.student_profile and current_user.student_profile.branch:
                    s_branch = current_user.student_profile.branch
                elif current_user.department:
                    s_branch = current_user.department
                
                target_branches = {str(b).strip().lower() for b in circ.branch_eligibility if b}
                if not s_branch or str(s_branch).strip().lower() not in target_branches:
                    continue

            results.append(self._enrich_circular_response(circ))

        return results

    def update_draft(
        self,
        db: Session,
        circular_id: int,
        data: RecruitmentCircularUpdate,
        current_user: User,
    ) -> Dict[str, Any]:
        """Update a circular. Non-drafts cannot have their company changed if jobs are linked."""
        circular = self.get_circular_raw(db, circular_id)
        if not circular:
            raise ValueError(f"Recruitment circular with ID {circular_id} not found.")

        if circular.status != RecruitmentCircularStatus.DRAFT and data.company_id is not None and data.company_id != circular.company_id:
            raise ValueError("Cannot change company on a published or archived circular.")

        if data.company_id is not None and data.company_id != circular.company_id:
            # Verify new company exists
            new_comp = db.query(Company).filter(Company.id == data.company_id).first()
            if not new_comp:
                raise ValueError(f"Company ID {data.company_id} does not exist.")
            # Check if any linked jobs belong to the old company
            for cj in circular.linked_jobs:
                if cj.job_posting and cj.job_posting.company_id != data.company_id:
                    raise ValueError(
                        f"Cannot change circular company to ID {data.company_id}: "
                        f"linked job '{cj.job_posting.title}' belongs to old company ID {cj.job_posting.company_id}. "
                        "Unlink existing jobs first."
                    )
            circular.company_id = data.company_id

        if data.title is not None:
            circular.title = data.title.strip()
        if data.summary is not None:
            circular.summary = data.summary
        if data.instructions is not None:
            circular.instructions = data.instructions
        if data.application_deadline is not None:
            circular.application_deadline = data.application_deadline
        if data.drive_date is not None:
            circular.drive_date = data.drive_date
        if data.branch_eligibility is not None:
            circular.branch_eligibility = data.branch_eligibility

        circular.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(circular)
        logger.info(f"Updated recruitment circular ID {circular.id}")
        return self._enrich_circular_response(circular)

    def add_attachment(
        self,
        db: Session,
        circular_id: int,
        attachment_data: CircularAttachmentCreate,
        current_user: User,
    ) -> Dict[str, Any]:
        """Add an attachment to a circular."""
        circular = self.get_circular_raw(db, circular_id)
        if not circular:
            raise ValueError(f"Recruitment circular with ID {circular_id} not found.")

        # Verify file exists
        file_obj = db.query(File).filter(File.id == attachment_data.file_id).first()
        if not file_obj:
            raise ValueError(f"File with ID {attachment_data.file_id} not found.")

        # Check if already attached
        existing = db.query(RecruitmentCircularAttachment).filter(
            RecruitmentCircularAttachment.circular_id == circular_id,
            RecruitmentCircularAttachment.file_id == attachment_data.file_id,
        ).first()
        if existing:
            # Update display order or attachment type
            existing.attachment_type = attachment_data.attachment_type.value if hasattr(attachment_data.attachment_type, "value") else str(attachment_data.attachment_type)
            existing.display_order = attachment_data.display_order
            db.commit()
            return self._enrich_circular_response(self.get_circular_raw(db, circular_id))

        attachment = RecruitmentCircularAttachment(
            circular_id=circular_id,
            file_id=attachment_data.file_id,
            attachment_type=attachment_data.attachment_type.value if hasattr(attachment_data.attachment_type, "value") else str(attachment_data.attachment_type),
            display_order=attachment_data.display_order,
        )
        db.add(attachment)
        circular.updated_at = datetime.utcnow()
        db.commit()
        logger.info(f"📎 Attached file {attachment_data.file_id} to circular {circular_id}")
        return self._enrich_circular_response(self.get_circular_raw(db, circular_id))

    def remove_attachment(
        self,
        db: Session,
        circular_id: int,
        attachment_id: int,
        current_user: User,
    ) -> Dict[str, Any]:
        """
        Remove an attachment from a circular.
        Safeguard: Deletes only the junction record, NOT the underlying File or MinIO object.
        """
        circular = self.get_circular_raw(db, circular_id)
        if not circular:
            raise ValueError(f"Recruitment circular with ID {circular_id} not found.")

        att = db.query(RecruitmentCircularAttachment).filter(
            RecruitmentCircularAttachment.id == attachment_id,
            RecruitmentCircularAttachment.circular_id == circular_id,
        ).first()
        if not att:
            raise ValueError(f"Attachment {attachment_id} not found on circular {circular_id}.")

        db.delete(att)
        circular.updated_at = datetime.utcnow()
        db.commit()
        logger.info(f"🗑️ Removed attachment {attachment_id} from circular {circular_id} (File retained safely)")
        return self._enrich_circular_response(self.get_circular_raw(db, circular_id))

    def link_jobs(
        self,
        db: Session,
        circular_id: int,
        job_posting_ids: List[int],
        current_user: User,
    ) -> Dict[str, Any]:
        """Link one or more JobPostings to the circular, enforcing same-company constraint."""
        circular = self.get_circular_raw(db, circular_id)
        if not circular:
            raise ValueError(f"Recruitment circular with ID {circular_id} not found.")

        linked_any = False
        for j_id in job_posting_ids:
            job = db.query(JobPosting).filter(JobPosting.id == j_id).first()
            if not job:
                raise ValueError(f"Job posting {j_id} not found.")

            # Same company enforcement
            if job.company_id != circular.company_id:
                company_name = circular.company.name if circular.company else f"ID {circular.company_id}"
                job_company_name = job.company.name if job.company else f"ID {job.company_id}"
                raise ValueError(
                    f"Job '{job.title}' belongs to '{job_company_name}', which does not match "
                    f"the circular's company '{company_name}'. Unrelated companies cannot be linked."
                )

            # Check if already linked
            existing = db.query(RecruitmentCircularJob).filter(
                RecruitmentCircularJob.circular_id == circular_id,
                RecruitmentCircularJob.job_posting_id == j_id,
            ).first()
            if not existing:
                link = RecruitmentCircularJob(
                    circular_id=circular_id,
                    job_posting_id=j_id,
                )
                db.add(link)
                linked_any = True

        if linked_any:
            circular.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"🔗 Linked jobs {job_posting_ids} to circular {circular_id}")

        return self._enrich_circular_response(self.get_circular_raw(db, circular_id))

    def unlink_job(
        self,
        db: Session,
        circular_id: int,
        job_posting_id: int,
        current_user: User,
    ) -> Dict[str, Any]:
        """Unlink a JobPosting from the circular."""
        circular = self.get_circular_raw(db, circular_id)
        if not circular:
            raise ValueError(f"Recruitment circular with ID {circular_id} not found.")

        link = db.query(RecruitmentCircularJob).filter(
            RecruitmentCircularJob.circular_id == circular_id,
            RecruitmentCircularJob.job_posting_id == job_posting_id,
        ).first()
        if not link:
            raise ValueError(f"Job {job_posting_id} is not linked to circular {circular_id}.")

        db.delete(link)
        circular.updated_at = datetime.utcnow()
        db.commit()
        logger.info(f"Unlinked job {job_posting_id} from circular {circular_id}")
        return self._enrich_circular_response(self.get_circular_raw(db, circular_id))

    def publish_circular(
        self,
        db: Session,
        circular_id: int,
        confirm_no_skills: bool = False,
        current_user: User = None,
    ) -> Dict[str, Any]:
        """
        Atomically publish a recruitment circular and its linked draft jobs.
        
        Requirements:
        1. Validates circular is in DRAFT status.
        2. Enforces at least one linked job.
        3. Enforces that all linked jobs belong to the same company.
        4. Validates required skills for each draft job (or confirms confirm_no_skills=True).
        5. Performs atomic status update in a single transaction (circular -> PUBLISHED, jobs -> OPEN).
        6. Suppresses individual job notifications for jobs opened by this circular.
        7. Dispatches idempotent aggregate notification to eligible students.
        """
        circular = self.get_circular_raw(db, circular_id)
        if not circular:
            raise ValueError(f"Recruitment circular with ID {circular_id} not found.")

        if circular.status == RecruitmentCircularStatus.PUBLISHED:
            # Idempotent response if already published
            return {
                "success": True,
                "circular": self._enrich_circular_response(circular),
                "published_jobs_count": 0,
                "message": "Circular is already published.",
            }

        if circular.status == RecruitmentCircularStatus.ARCHIVED:
            raise ValueError("Archived circular cannot be published directly.")

        # Require at least one linked job
        if not circular.linked_jobs or len(circular.linked_jobs) == 0:
            raise ValueError(
                "A recruitment circular must have at least one linked job role before publication."
            )

        # Validate linked jobs
        jobs_to_open: List[JobPosting] = []
        for cj in circular.linked_jobs:
            job = cj.job_posting
            if not job:
                continue

            # Verify same company
            if job.company_id != circular.company_id:
                raise ValueError(
                    f"Job {job.id} ('{job.title}') belongs to company {job.company_id}, "
                    f"differing from circular company {circular.company_id}."
                )

            # Check skill safeguard for jobs that are in DRAFT status
            if job.status == JobStatus.DRAFT:
                has_req = bool(job.required_skills and len(job.required_skills) > 0)
                has_pref = bool(getattr(job, "preferred_skills", None) and len(job.preferred_skills) > 0)
                if not has_req and not has_pref and not confirm_no_skills:
                    raise ValueError(
                        f"Linked draft job '{job.title}' (ID {job.id}) has no required or preferred skills configured. "
                        "Add skills or explicitly confirm publication with confirm_no_skills=True."
                    )
                jobs_to_open.append(job)

        now = datetime.utcnow()
        try:
            # Atomic transition
            circular.status = RecruitmentCircularStatus.PUBLISHED
            circular.published_at = now
            circular.updated_at = now

            for job in jobs_to_open:
                job.status = JobStatus.OPEN
                job.updated_at = now

            db.commit()
            db.refresh(circular)
            logger.info(
                f"🚀 Published recruitment circular ID {circular.id} and transitioned "
                f"{len(jobs_to_open)} linked draft job(s) to OPEN."
            )
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Failed to publish circular {circular_id}: {e}", exc_info=True)
            raise e

        # Dispatched aggregate notification for students
        # Note: individual job notifications for jobs_to_open were NOT sent, avoiding double alerts!
        try:
            self.notify_students_on_circular_publish(db, circular)
        except Exception as e:
            logger.error(f"❌ Failed to dispatch notifications for circular {circular.id}: {e}", exc_info=True)

        return {
            "success": True,
            "circular": self._enrich_circular_response(self.get_circular_raw(db, circular_id)),
            "published_jobs_count": len(jobs_to_open),
            "message": f"Successfully published circular and {len(jobs_to_open)} linked role(s).",
        }

    def notify_students_on_circular_publish(self, db: Session, circular: RecruitmentCircular) -> int:
        """
        Notify active, eligible students when a recruitment circular is published.
        Uses unique event_key: 'circular_publish:{circular.id}:student:{student.id}'
        for safe deduplication.
        """
        # Determine target branches if specified
        target_branches: Optional[set] = None
        if circular.branch_eligibility and isinstance(circular.branch_eligibility, (list, tuple)) and len(circular.branch_eligibility) > 0:
            target_branches = {
                str(b).strip().lower() for b in circular.branch_eligibility if b and str(b).strip()
            }

        students = db.query(User).options(
            joinedload(User.student_profile)
        ).filter(
            User.role == UserRole.STUDENT,
            User.is_active == True,
        ).all()

        company_name = circular.company.name if circular.company else "Campus Recruiter"
        title = f"📢 Recruitment Drive: {company_name} - {circular.title}"

        deadline_str = ""
        if circular.application_deadline:
            if hasattr(circular.application_deadline, "strftime"):
                deadline_str = f" • Deadline: {circular.application_deadline.strftime('%d %b %Y')}"
            else:
                deadline_str = f" • Deadline: {circular.application_deadline}"

        roles_count = len(circular.linked_jobs) if circular.linked_jobs else 1
        roles_text = f"{roles_count} role{'s' if roles_count != 1 else ''}"
        message = (
            f"{company_name} announced a recruitment drive for {roles_text}{deadline_str}. "
            "Review drive instructions, circular attachments, and apply for eligible roles."
        )

        notif_count = 0
        for student in students:
            # Branch check
            if target_branches:
                s_branch = None
                if student.student_profile and student.student_profile.branch:
                    s_branch = student.student_profile.branch
                elif student.department:
                    s_branch = student.department

                if not s_branch or str(s_branch).strip().lower() not in target_branches:
                    continue

            event_key = f"circular_publish:{circular.id}:student:{student.id}"

            # Check deduplication
            existing = db.query(Notification).filter(Notification.event_key == event_key).first()
            if existing:
                continue

            notif = Notification(
                user_id=student.id,
                type="placement_circular",
                title=title,
                message=message,
                reference_id=circular.id,
                event_key=event_key,
                is_read=False,
            )
            db.add(notif)
            notif_count += 1

        if notif_count > 0:
            try:
                db.commit()
                logger.info(f"📢 Created {notif_count} circular-publication notifications for circular {circular.id}")
            except Exception as e:
                db.rollback()
                logger.warning(f"Handled notification commit for circular {circular.id}: {e}")

        return notif_count

    def archive_circular(self, db: Session, circular_id: int, current_user: User) -> Dict[str, Any]:
        """Archive a recruitment circular."""
        circular = self.get_circular_raw(db, circular_id)
        if not circular:
            raise ValueError(f"Recruitment circular with ID {circular_id} not found.")

        circular.status = RecruitmentCircularStatus.ARCHIVED
        circular.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(circular)
        logger.info(f"Archived recruitment circular {circular_id}")
        return self._enrich_circular_response(circular)


recruitment_circular_service = RecruitmentCircularService()
