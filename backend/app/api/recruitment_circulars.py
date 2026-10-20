"""
Recruitment Circular API Endpoints

Provides REST endpoints for company recruitment circulars:
- Placement officer CRUD, attachment management, job linking
- Atomic publication with linked draft jobs
- Student listing, search, filtering, and detail view
"""

import os
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File as FastAPIFile, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from ..core.database import get_db
from ..api.auth import get_current_user, get_current_user_flexible
from ..models.user import User, UserRole
from ..models.file import File
from ..models.company import Company
from ..models.job_posting import JobPosting
from ..models.notification import Notification
from ..models.profile import StudentProfileExtended
from ..models.recruitment_circular import (
    RecruitmentCircular,
    RecruitmentCircularStatus,
    RecruitmentCircularAttachment,
    RecruitmentCircularJob,
    AttachmentType,
)
from ..models.recruitment_result import (
    RecruitmentResultBatch,
    RecruitmentResultBatchStatus,
    RecruitmentResultItem,
    RecruitmentResultReviewState,
)
from ..schemas.recruitment_circular import (
    RecruitmentCircularCreate,
    RecruitmentCircularUpdate,
    RecruitmentCircularResponse,
    RecruitmentCircularPublishResponse,
    CircularAttachmentCreate,
    CircularJobLinkRequest,
    DriveReportResponse,
    DriveParseShortlistResponse,
    CreateAndPostDriveRequest,
    CreateAndPostDriveResponse,
    DriveCandidateMatchItem,
    DriveCandidateSummary,
    DriveAttachmentFileInfo,
)
from ..services.recruitment_circular_service import recruitment_circular_service
from ..services.file_storage.minio_client import minio_client
from ..services.file_storage.file_service import file_service
from ..services.recruitment_result_extractor import RecruitmentResultExtractor
from ..services.recruitment_result_matcher import (
    RecruitmentResultMatcher,
    normalize_usn,
    normalize_email,
    normalize_name,
)
from ..services.file_storage.text_extractor import text_extractor

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
    current_user: User = Depends(get_current_user_flexible),
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File content not found in storage")

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
    current_user: User = Depends(get_current_user_flexible),
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File content not found in storage")

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


# ============================================
# REDESIGNED RECRUITMENT DRIVE WORKFLOW ENDPOINTS
# ============================================

@router.post("/parse-shortlist", response_model=DriveParseShortlistResponse)
async def parse_shortlist_documents(
    files: List[UploadFile] = FastAPIFile(...),
    company_id: Optional[int] = Form(None),
    current_user: User = Depends(require_placement_officer_or_admin),
    db: Session = Depends(get_db),
):
    """
    Extract readable text and candidate details from uploaded shortlist documents:
    - Retains uploaded files securely in MinIO storage
    - Extracts candidates (USN, name, email, branch) via multi-format extractor (CSV, XLSX, PDF, DOCX, TXT, OCR)
    - Corroborates candidates against authoritative student records via RecruitmentResultMatcher
    - Detects intra-file and duplicate entries
    - Generates preliminary announcement description draft
    """
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please upload at least one shortlist document.")

    extractor = RecruitmentResultExtractor()
    matcher = RecruitmentResultMatcher()

    saved_files: List[Dict[str, Any]] = []
    all_extracted_candidates: List[Dict[str, Any]] = []
    extracted_texts: List[str] = []
    extraction_errors: List[str] = []

    for file_upload in files:
        content = await file_upload.read()
        if not content or len(content) == 0:
            continue
        fn = file_upload.filename or "shortlist_document"

        # 1. Save file in MinIO & database
        try:
            content_type = getattr(file_upload, "content_type", None) or "application/octet-stream"
            file_record = file_service.save_file_direct(
                db=db,
                file_content=content,
                filename=fn,
                uploader_id=current_user.id,
                department=getattr(current_user, "department", "Placement Cell") or "Placement Cell",
                file_type="circular",
                mime_type=content_type
            )
            saved_files.append({
                "file_id": file_record.id,
                "filename": file_record.filename,
                "file_size": file_record.file_size,
                "content_type": file_record.mime_type
            })
        except Exception as e:
            logger.error(f"Failed to persist file {fn}: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to save uploaded file '{fn}'.")

        # 2. Extract text for human-readable circular description
        try:
            t_res = text_extractor.extract_text(fn, content=content)
            if t_res and t_res.get("text"):
                extracted_texts.append(t_res.get("text").strip())
        except Exception as e:
            logger.warning(f"Text extraction failed for description on {fn}: {e}")

        # 3. Extract candidate rows
        try:
            cand_result = extractor.extract_candidates_from_bytes(content, fn)
            rows = cand_result.get("rows") or cand_result.get("candidates") or []
            if not rows:
                extraction_errors.append(f"{fn}: No candidate rows found.")
            for r in rows:
                r["source_filename"] = fn
                all_extracted_candidates.append(r)
        except Exception as e:
            logger.warning(f"Candidate extraction failed on {fn}: {e}")
            extraction_errors.append(f"{fn}: {str(e)}")

    if not all_extracted_candidates and extraction_errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Candidate extraction failed: {'; '.join(extraction_errors)}"
        )

    # Fetch active students for matching
    active_students = db.query(User).options(
        joinedload(User.student_profile)
    ).filter(
        User.role == UserRole.STUDENT,
        User.is_active == True
    ).all()

    seen_keys: Dict[str, int] = {}
    processed_candidates: List[Dict[str, Any]] = []

    for idx, cand in enumerate(all_extracted_candidates):
        raw_usn = cand.get("usn") or cand.get("extracted_usn")
        raw_name = cand.get("name") or cand.get("extracted_name")
        raw_email = cand.get("email") or cand.get("extracted_email")
        raw_branch = cand.get("branch") or cand.get("extracted_branch")
        fn = cand.get("source_filename", "document")

        match_res = matcher.match_row(
            db=db,
            extracted_usn=raw_usn,
            extracted_email=raw_email,
            extracted_name=raw_name,
            extracted_branch=raw_branch
        )

        matched_user_id = match_res.get("matched_student_id")
        confidence = float(match_res.get("match_confidence") if match_res.get("match_confidence") is not None else match_res.get("confidence", 0.0))
        method = match_res.get("match_method") or match_res.get("method")
        evidence = match_res.get("match_evidence") or match_res.get("evidence")

        matched_student = None
        if matched_user_id:
            matched_student = next((s for s in active_students if s.id == matched_user_id), None)
            if not matched_student:
                matched_student = db.query(User).options(joinedload(User.student_profile)).filter(User.id == matched_user_id).first()

        s_name = (matched_student.student_profile.full_name if (matched_student and matched_student.student_profile and matched_student.student_profile.full_name) else (matched_student.name if matched_student else None))
        s_usn = (matched_student.student_profile.enrollment_number if matched_student and matched_student.student_profile else None)
        s_email = matched_student.email if matched_student else None
        s_branch = (matched_student.student_profile.branch if matched_student and matched_student.student_profile else getattr(matched_student, "department", None))

        # Duplicate detection key
        norm_u = normalize_usn(raw_usn or s_usn)
        norm_e = normalize_email(raw_email or s_email)
        norm_n = normalize_name(raw_name or s_name)

        dup_key = norm_u or norm_e or norm_n
        is_dup = False
        if dup_key:
            if dup_key in seen_keys:
                is_dup = True
            else:
                seen_keys[dup_key] = idx

        # Matching Hierarchy & Confirmation:
        # Confidence >= 0.95 (exact USN or exact email) without duplicates -> auto-confirmed match
        # Lower confidence (name+branch, name-only, conflicts) -> ambiguous, requires explicit officer confirmation
        # Unmatched -> unmatched
        if is_dup:
            review_status = "ambiguous"
            is_confirmed = False
        elif matched_user_id and confidence >= 0.95:
            review_status = "matched"
            is_confirmed = True
        elif matched_user_id:
            review_status = "ambiguous"
            is_confirmed = False
        else:
            review_status = "unmatched"
            is_confirmed = False

        processed_candidates.append({
            "row_index": idx,
            "source_filename": fn,
            "extracted_usn": raw_usn,
            "extracted_name": raw_name,
            "extracted_email": raw_email,
            "extracted_branch": raw_branch,
            "matched_student_id": matched_user_id,
            "matched_student_name": s_name,
            "matched_student_usn": s_usn,
            "matched_student_email": s_email,
            "matched_student_branch": s_branch,
            "match_confidence": confidence,
            "match_method": method,
            "match_evidence": evidence,
            "review_status": review_status,
            "is_duplicate": is_dup,
            "is_confirmed": is_confirmed
        })

    total_c = len(processed_candidates)
    matched_c = sum(1 for c in processed_candidates if c["review_status"] == "matched" and not c["is_duplicate"])
    ambiguous_c = sum(1 for c in processed_candidates if (c["review_status"] == "ambiguous" or c["is_duplicate"]))
    unmatched_c = sum(1 for c in processed_candidates if c["review_status"] == "unmatched")
    duplicate_c = sum(1 for c in processed_candidates if c["is_duplicate"])

    summary = {
        "total": total_c,
        "matched": matched_c,
        "ambiguous": ambiguous_c,
        "unmatched": unmatched_c,
        "duplicate": duplicate_c,
    }

    # Generate draft description
    company_name = "Company"
    if company_id:
        comp = db.query(Company).filter(Company.id == company_id).first()
        if comp:
            company_name = comp.name

    desc_lines = [
        f"Recruitment Drive Shortlist Announcement — {company_name}",
        "",
        f"We are pleased to announce the shortlisted candidates for the {company_name} recruitment drive.",
    ]
    if total_c > 0:
        desc_lines.append(f"A total of {total_c} candidates were extracted from the uploaded shortlist documentation.")
        desc_lines.append(f"• Verified Matched Candidates: {matched_c}")
        if ambiguous_c > 0:
            desc_lines.append(f"• Candidates Requiring Review: {ambiguous_c}")
        if duplicate_c > 0:
            desc_lines.append(f"• Duplicate Entries Flagged: {duplicate_c}")
        desc_lines.append("")
        desc_lines.append("Shortlisted students should review the attached documents and prepare for upcoming evaluation rounds.")
    elif extracted_texts:
        desc_lines.append("")
        desc_lines.append("\n\n".join(extracted_texts[:2]))

    return DriveParseShortlistResponse(
        description="\n".join(desc_lines).strip(),
        candidates=processed_candidates,
        candidate_summary=summary,
        attachment_files=saved_files,
        extraction_errors=extraction_errors,
    )


@router.post("/create-and-post-drive", response_model=CreateAndPostDriveResponse)
async def create_and_post_drive(
    data: CreateAndPostDriveRequest,
    current_user: User = Depends(require_placement_officer_or_admin),
    db: Session = Depends(get_db),
):
    """
    Simplified Recruitment Drive creation and announcement workflow:
    1. Validates required company and linked job roles
    2. Persists the recruitment circular (status: PUBLISHED)
    3. Persists file attachments and linked roles
    4. Persists confirmed candidate matching outcomes (RecruitmentResultBatch/Items)
    5. Sends notifications ONLY to confirmed matched students
    6. Guarantees transactional consistency and deduplication
    """
    company = db.query(Company).filter(Company.id == data.company_id).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Selected company not found.")

    # Validate linked jobs belong to the selected company
    if data.linked_job_ids:
        invalid_jobs = db.query(JobPosting).filter(
            JobPosting.id.in_(data.linked_job_ids),
            JobPosting.company_id != data.company_id
        ).all()
        if invalid_jobs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="All linked job roles must belong to the selected company."
            )

    title = data.title.strip() if data.title and data.title.strip() else f"{company.name} Recruitment Drive"

    # 1. Create and persist circular
    circular = RecruitmentCircular(
        company_id=data.company_id,
        title=title,
        summary=data.description,
        instructions=data.description,
        branch_eligibility=data.branch_eligibility or [],
        drive_date=data.drive_date,
        status=RecruitmentCircularStatus.PUBLISHED,
        created_by=current_user.id,
        published_at=datetime.now(timezone.utc),
    )
    db.add(circular)
    db.flush()

    # 2. Attach uploaded documents
    for idx, fid in enumerate(data.attachment_file_ids):
        att = RecruitmentCircularAttachment(
            circular_id=circular.id,
            file_id=fid,
            attachment_type=AttachmentType.ELIGIBILITY_SHEET.value,
            display_order=idx
        )
        db.add(att)

    # 3. Link jobs
    for jid in data.linked_job_ids:
        rcj = RecruitmentCircularJob(
            circular_id=circular.id,
            job_posting_id=jid
        )
        db.add(rcj)

    # 4. Save confirmed candidate review records in RecruitmentResultBatch
    first_fid = data.attachment_file_ids[0] if data.attachment_file_ids else None
    confirmed_student_ids: List[int] = []

    if first_fid:
        batch = RecruitmentResultBatch(
            company_id=data.company_id,
            job_posting_id=data.linked_job_ids[0] if data.linked_job_ids else None,
            circular_id=circular.id,
            file_id=first_fid,
            round_name="Shortlist Announcement",
            round_type="shortlist",
            status=RecruitmentResultBatchStatus.FULLY_CONFIRMED,
            total_rows=len(data.candidates),
            matched_count=sum(1 for c in data.candidates if c.get("is_confirmed") and c.get("matched_student_id")),
            confirmed_count=sum(1 for c in data.candidates if c.get("is_confirmed") and c.get("matched_student_id")),
            uploaded_by=current_user.id
        )
        db.add(batch)
        db.flush()

        for idx, cand in enumerate(data.candidates):
            is_conf = bool(cand.get("is_confirmed"))
            student_id = cand.get("matched_student_id")

            if is_conf and student_id:
                confirmed_student_ids.append(student_id)
                review_st = RecruitmentResultReviewState.CONFIRMED
            elif cand.get("is_duplicate") or cand.get("review_status") == "ambiguous":
                review_st = RecruitmentResultReviewState.AMBIGUOUS
            elif not student_id:
                review_st = RecruitmentResultReviewState.UNRESOLVED
            else:
                review_st = RecruitmentResultReviewState.IGNORED

            item = RecruitmentResultItem(
                batch_id=batch.id,
                row_index=idx,
                raw_data=cand,
                extracted_usn=cand.get("extracted_usn"),
                extracted_name=cand.get("extracted_name"),
                extracted_email=cand.get("extracted_email"),
                matched_student_id=student_id if is_conf else None,
                match_confidence=float(cand.get("match_confidence") or 0.0),
                match_method=cand.get("match_method"),
                match_evidence=cand.get("match_evidence"),
                review_status=review_st,
                confirmed_by=current_user.id if is_conf else None,
                confirmed_at=datetime.now(timezone.utc) if is_conf else None,
                notification_sent=False
            )
            db.add(item)

    # Commit circular, attachments, and candidate outcome records
    db.commit()

    # 5. Notify confirmed shortlisted students
    notified_count = 0
    unique_confirmed_ids = list(dict.fromkeys(confirmed_student_ids))

    for s_id in unique_confirmed_ids:
        event_key = f"recruitment_circular_shortlist:{circular.id}:student:{s_id}"
        existing = db.query(Notification).filter(Notification.event_key == event_key).first()
        if not existing:
            notif = Notification(
                user_id=s_id,
                type="placement_shortlist",
                title=f"🎯 Shortlisted: {company.name} Recruitment Drive",
                message=f"Congratulations! You have been shortlisted for the {company.name} recruitment drive. View circular details in your placement portal.",
                reference_id=circular.id,
                event_key=event_key,
                is_read=False
            )
            db.add(notif)
            notified_count += 1

    # Also notify branch-eligible students of the general circular publication
    recruitment_circular_service.notify_students_on_circular_publish(db, circular)

    db.commit()

    # Enrich circular response
    enriched = recruitment_circular_service._enrich_circular_response(circular)

    return CreateAndPostDriveResponse(
        success=True,
        circular=enriched,
        notified_students_count=notified_count,
        candidates_count=len(data.candidates),
        message=f"Recruitment drive circular posted successfully. Notified {notified_count} confirmed shortlisted students."
    )


