"""
Recruitment Circular API Endpoints

Provides REST endpoints for company recruitment circulars:
- Placement officer CRUD, attachment management, job linking
- Atomic publication with linked draft jobs
- Student listing, search, filtering, and detail view
"""

import os
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..api.auth import get_current_user
from ..models.user import User, UserRole
from ..models.file import File
from ..models.profile import StudentProfileExtended
from ..models.recruitment_circular import (
    RecruitmentCircular,
    RecruitmentCircularStatus,
    RecruitmentCircularAttachment,
)
from ..schemas.recruitment_circular import (
    RecruitmentCircularCreate,
    RecruitmentCircularUpdate,
    RecruitmentCircularResponse,
    RecruitmentCircularPublishResponse,
    CircularAttachmentCreate,
    CircularJobLinkRequest,
    DriveReportResponse,
)
from ..services.recruitment_circular_service import recruitment_circular_service
from ..services.file_storage.minio_client import minio_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/placement/circulars", tags=["Recruitment Circulars"])


def require_placement_officer_or_admin(current_user: User = Depends(get_current_user)) -> User:
    """Ensure the user is a Placement Officer or Admin."""
    if current_user.role not in [UserRole.ADMIN, UserRole.PLACEMENT_OFFICER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only Placement Officers and Admins can manage recruitment circulars."
        )
    return current_user


# ============================================
# CIRCULAR CRUD ENDPOINTS
# ============================================

@router.post("", response_model=RecruitmentCircularResponse, status_code=status.HTTP_201_CREATED)
async def create_circular_draft(
    circular_in: RecruitmentCircularCreate,
    current_user: User = Depends(require_placement_officer_or_admin),
    db: Session = Depends(get_db),
):
    """Create a new recruitment circular draft."""
    try:
        circular = recruitment_circular_service.create_draft(db, circular_in, current_user)
        return circular
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating recruitment circular: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create circular draft.")


@router.get("", response_model=List[RecruitmentCircularResponse])
async def list_circulars(
    status_filter: Optional[str] = Query(None, alias="status"),
    company_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List recruitment circulars.
    - Placement Officers / Admins can view all and filter by status.
    - Students can only view published circulars for which they are eligible.
    - Lecturers / HODs are denied access to recruitment circulars.
    """
    if current_user.role in [UserRole.LECTURER, UserRole.HOD]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Academic faculty cannot access recruitment circulars."
        )

    circulars = recruitment_circular_service.list_circulars(
        db=db,
        current_user=current_user,
        skip=skip,
        limit=limit,
        status=status_filter,
        company_id=company_id,
        search=search,
    )
    return circulars


@router.get("/{circular_id}", response_model=RecruitmentCircularResponse)
async def get_circular_detail(
    circular_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve recruitment circular details.
    - Students can only view published circulars they are eligible for.
    - Drafts and ineligible circulars return 404 for students to prevent information leaks.
    """
    if current_user.role in [UserRole.LECTURER, UserRole.HOD]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Academic faculty cannot access recruitment circulars."
        )

    circular = recruitment_circular_service.get_circular(db, circular_id, current_user)
    if not circular:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recruitment circular not found or you are not eligible to view it."
        )
    return circular


@router.put("/{circular_id}", response_model=RecruitmentCircularResponse)
async def update_circular_draft(
    circular_id: int,
    update_in: RecruitmentCircularUpdate,
    current_user: User = Depends(require_placement_officer_or_admin),
    db: Session = Depends(get_db),
):
    """Update a recruitment circular."""
    try:
        updated = recruitment_circular_service.update_draft(db, circular_id, update_in, current_user)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating recruitment circular {circular_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update circular.")


# ============================================
# PUBLISH & ARCHIVE ENDPOINTS
# ============================================

@router.post("/{circular_id}/publish", response_model=RecruitmentCircularPublishResponse)
async def publish_circular(
    circular_id: int,
    confirm_no_skills: bool = Query(False, description="Bypass missing skills safeguard on linked draft jobs"),
    current_user: User = Depends(require_placement_officer_or_admin),
    db: Session = Depends(get_db),
):
    """
    Atomically publish recruitment circular and linked draft jobs.
    Enforces same-company rule, required skills safeguard, and deduplicated notification delivery.
    """
    try:
        result = recruitment_circular_service.publish_circular(
            db=db,
            circular_id=circular_id,
            confirm_no_skills=confirm_no_skills,
            current_user=current_user,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error publishing circular {circular_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to publish circular: {str(e)}")


@router.post("/{circular_id}/archive", response_model=RecruitmentCircularResponse)
async def archive_circular(
    circular_id: int,
    current_user: User = Depends(require_placement_officer_or_admin),
    db: Session = Depends(get_db),
):
    """Archive a recruitment circular."""
    try:
        result = recruitment_circular_service.archive_circular(db, circular_id, current_user)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error archiving circular {circular_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to archive circular.")


# ============================================
# ATTACHMENT MANAGEMENT ENDPOINTS
# ============================================

@router.post("/{circular_id}/attachments", response_model=RecruitmentCircularResponse)
async def add_attachment(
    circular_id: int,
    attachment_in: CircularAttachmentCreate,
    current_user: User = Depends(require_placement_officer_or_admin),
    db: Session = Depends(get_db),
):
    """Add an attachment to a recruitment circular."""
    try:
        updated = recruitment_circular_service.add_attachment(db, circular_id, attachment_in, current_user)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding attachment to circular {circular_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to add attachment.")


@router.delete("/{circular_id}/attachments/{attachment_id}", response_model=RecruitmentCircularResponse)
async def remove_attachment(
    circular_id: int,
    attachment_id: int,
    current_user: User = Depends(require_placement_officer_or_admin),
    db: Session = Depends(get_db),
):
    """Remove an attachment from a recruitment circular (retains underlying File safely)."""
    try:
        updated = recruitment_circular_service.remove_attachment(db, circular_id, attachment_id, current_user)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error removing attachment {attachment_id} from circular {circular_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to remove attachment.")


def _verify_attachment_access(
    db: Session,
    circular_id: int,
    attachment_id: int,
    current_user: User,
) -> tuple[RecruitmentCircularAttachment, File]:
    """
    Verify access authorization for circular attachments:
    - Officers/Admins: allowed
    - Students: allowed ONLY if circular is PUBLISHED and student is branch-eligible
    - Faculty/HODs: 403 Forbidden
    """
    if current_user.role in [UserRole.LECTURER, UserRole.HOD]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Academic faculty cannot access recruitment circular files."
        )

    circular = db.query(RecruitmentCircular).filter(RecruitmentCircular.id == circular_id).first()
    if not circular:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recruitment circular not found.")

    if current_user.role == UserRole.STUDENT:
        if circular.status != RecruitmentCircularStatus.PUBLISHED:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recruitment circular not found or unpublished."
            )
        if circular.branch_eligibility and len(circular.branch_eligibility) > 0:
            s_branch = None
            profile = db.query(StudentProfileExtended).filter(StudentProfileExtended.user_id == current_user.id).first()
            if profile and profile.branch:
                s_branch = profile.branch
            elif getattr(current_user, "department", None):
                s_branch = current_user.department

            target_branches = {str(b).strip().lower() for b in circular.branch_eligibility if b}
            if not s_branch or str(s_branch).strip().lower() not in target_branches:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not eligible for this recruitment drive."
                )

    attachment = db.query(RecruitmentCircularAttachment).filter(
        RecruitmentCircularAttachment.id == attachment_id,
        RecruitmentCircularAttachment.circular_id == circular_id,
    ).first()
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found on this circular.")

    file_record = db.query(File).filter(File.id == attachment.file_id).first()
    if not file_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attached file not found.")

    return attachment, file_record


@router.get("/{circular_id}/attachments/{attachment_id}/download")
async def download_circular_attachment(
    circular_id: int,
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Explicit, secure download route for published circular attachments.
    Enforces student branch eligibility and draft concealment.
    """
    attachment, file_record = _verify_attachment_access(db, circular_id, attachment_id, current_user)

    try:
        content_stream, file_size, content_type = minio_client.get_file_stream(
            file_record.bucket, file_record.object_key
        )
    except Exception as e:
        logger.error(f"Error fetching circular attachment from storage: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve file")

    safe_filename = os.path.basename(file_record.filename).replace('"', '')
    return StreamingResponse(
        content_stream,
        media_type=content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "Content-Length": str(file_size) if file_size else "",
            "Access-Control-Expose-Headers": "Content-Disposition",
        }
    )


@router.get("/{circular_id}/attachments/{attachment_id}/preview")
async def preview_circular_attachment(
    circular_id: int,
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Explicit, secure inline preview route for published circular attachments.
    """
    attachment, file_record = _verify_attachment_access(db, circular_id, attachment_id, current_user)

    try:
        content_stream, file_size, content_type = minio_client.get_file_stream(
            file_record.bucket, file_record.object_key
        )
    except Exception as e:
        logger.error(f"Error previewing circular attachment from storage: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve file")

    safe_filename = os.path.basename(file_record.filename).replace('"', '')
    return StreamingResponse(
        content_stream,
        media_type=content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'inline; filename="{safe_filename}"',
            "Content-Length": str(file_size) if file_size else "",
            "Access-Control-Expose-Headers": "Content-Disposition",
        }
    )


# ============================================
# LINKED JOBS MANAGEMENT ENDPOINTS
# ============================================

@router.post("/{circular_id}/jobs", response_model=RecruitmentCircularResponse)
async def link_jobs(
    circular_id: int,
    jobs_in: CircularJobLinkRequest,
    current_user: User = Depends(require_placement_officer_or_admin),
    db: Session = Depends(get_db),
):
    """Link one or more JobPostings to the circular (enforcing same company)."""
    try:
        updated = recruitment_circular_service.link_jobs(db, circular_id, jobs_in.job_posting_ids, current_user)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error linking jobs to circular {circular_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to link jobs.")


@router.delete("/{circular_id}/jobs/{job_posting_id}", response_model=RecruitmentCircularResponse)
async def unlink_job(
    circular_id: int,
    job_posting_id: int,
    current_user: User = Depends(require_placement_officer_or_admin),
    db: Session = Depends(get_db),
):
    """Unlink a JobPosting from the recruitment circular."""
    try:
        updated = recruitment_circular_service.unlink_job(db, circular_id, job_posting_id, current_user)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error unlinking job {job_posting_id} from circular {circular_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to unlink job.")


# ============================================
# DRIVE PLACEMENT REPORT (STAGE 3.4.3)
# ============================================

@router.get("/{circular_id}/report", response_model=DriveReportResponse)
async def get_drive_report(
    circular_id: int,
    current_user: User = Depends(require_placement_officer_or_admin),
    db: Session = Depends(get_db),
):
    """
    Get authoritative drive placement report.
    Scoped to the selected circular and all its linked job roles.
    Enforces Placement Officer and Admin authorization.
    """
    try:
        report = recruitment_circular_service.get_drive_report(db, circular_id, current_user)
        return report
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating drive report for circular {circular_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate drive report.")

