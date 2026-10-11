"""
Recruitment Results API Router

Endpoints for:
- Uploading and parsing company recruitment result documents
- Listing and inspecting result batches with candidate rows
- Manually resolving student matches
- Transactionally confirming intermediate vs. final results
"""

import os
import logging
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File as FastAPIFile, Form, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.config import settings
from ..api.auth import get_current_placement_officer
from ..models.user import User
from ..schemas.recruitment_result import (
    RecruitmentResultBatchResponse,
    RecruitmentResultItemResponse,
    RecruitmentResultItemMatchUpdate,
    RecruitmentResultBatchConfirmRequest,
    RecruitmentResultConfirmResponse,
    StudentSearchItem,
)
from ..services.recruitment_result_service import recruitment_result_service
from ..services.recruitment_progression_service import recruitment_progression_service
from ..services.file_storage.file_service import file_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/placement/results", tags=["Placement Results"])


# =============================================================================
# UPLOAD & PROCESS ENDPOINTS
# =============================================================================

@router.post("/upload", response_model=RecruitmentResultBatchResponse, status_code=status.HTTP_201_CREATED)
async def upload_and_process_result_file(
    file: UploadFile = FastAPIFile(...),
    company_id: int = Form(...),
    round_name: str = Form(...),
    round_type: str = Form("assessment"),
    is_final_round: bool = Form(False),
    job_posting_id: Optional[int] = Form(None),
    circular_id: Optional[int] = Form(None),
    round_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db),
):
    """
    Upload a result document (CSV, XLSX, XLS, PDF), save it to MinIO,
    extract candidate rows, match against active students, and return
    a reviewable result batch.
    
    NOTE: Does NOT confirm any candidates or dispatch notifications.
    """
    # Validate extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".csv", ".xlsx", ".xls", ".pdf"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed: .csv, .xlsx, .xls, .pdf",
        )

    # Check file size
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size: {settings.MAX_FILE_SIZE // (1024 * 1024)}MB",
        )

    # Save to MinIO via file_service
    upload_result = await file_service.upload_file(
        db=db,
        file=file,
        file_type="placement_doc",
        department="Placement",
        uploaded_by=current_user,
        description=f"Recruitment Result: {round_name}",
    )
    if not upload_result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=upload_result.get("message", "File upload failed"),
        )
    file_id = upload_result["file_id"]

    try:
        batch = recruitment_result_service.upload_and_process_result_file(
            db=db,
            company_id=company_id,
            file_id=file_id,
            round_name=round_name,
            round_type=round_type,
            is_final_round=is_final_round,
            job_posting_id=job_posting_id,
            circular_id=circular_id,
            round_id=round_id,
            current_user=current_user,
        )
        return recruitment_result_service.get_batch_by_id(db, batch.id, include_items=True)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing result file: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/process-existing", response_model=RecruitmentResultBatchResponse, status_code=status.HTTP_201_CREATED)
async def process_existing_file(
    company_id: int = Query(...),
    file_id: UUID = Query(...),
    round_name: str = Query(...),
    round_type: str = Query("assessment"),
    is_final_round: bool = Query(False),
    job_posting_id: Optional[int] = Query(None),
    circular_id: Optional[int] = Query(None),
    round_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db),
):
    """Process an already uploaded File record by UUID."""
    try:
        batch = recruitment_result_service.upload_and_process_result_file(
            db=db,
            company_id=company_id,
            file_id=file_id,
            round_name=round_name,
            round_type=round_type,
            is_final_round=is_final_round,
            job_posting_id=job_posting_id,
            circular_id=circular_id,
            round_id=round_id,
            current_user=current_user,
        )
        return recruitment_result_service.get_batch_by_id(db, batch.id, include_items=True)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/batches/{batch_id}/link-round", response_model=RecruitmentResultBatchResponse)
async def link_batch_to_round(
    batch_id: int,
    round_id: int = Query(...),
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db),
):
    """Explicitly link a recruitment result batch to an authoritative RecruitmentRound."""
    try:
        recruitment_progression_service.link_batch_to_round(
            db=db,
            batch_id=batch_id,
            round_id=round_id,
            current_user=current_user,
        )
        return recruitment_result_service.get_batch_by_id(db, batch_id, include_items=True)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# BATCH LIST & DETAIL
# =============================================================================

@router.get("/batches", response_model=List[RecruitmentResultBatchResponse])
async def list_result_batches(
    company_id: Optional[int] = Query(None),
    job_posting_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db),
):
    """List result batches with review summaries."""
    return recruitment_result_service.get_batches(
        db=db,
        company_id=company_id,
        job_posting_id=job_posting_id,
        status=status,
        skip=skip,
        limit=limit,
    )


@router.get("/batches/{batch_id}", response_model=RecruitmentResultBatchResponse)
async def get_batch_details(
    batch_id: int,
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db),
):
    """Retrieve full batch details and all candidate review rows."""
    batch_data = recruitment_result_service.get_batch_by_id(db, batch_id, include_items=True)
    if not batch_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result batch not found")
    return batch_data


# =============================================================================
# ITEM MATCH OVERRIDE
# =============================================================================

@router.put("/items/{item_id}/match", response_model=RecruitmentResultBatchResponse)
async def update_item_match(
    item_id: int,
    payload: RecruitmentResultItemMatchUpdate,
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db),
):
    """Manually assign, override, or clear student match for a row."""
    try:
        return recruitment_result_service.update_item_match(
            db=db,
            item_id=item_id,
            student_id=payload.student_id,
            review_status=payload.review_status,
            current_user=current_user,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# CONFIRMATION
# =============================================================================

@router.post("/batches/{batch_id}/confirm", response_model=RecruitmentResultConfirmResponse)
async def confirm_batch_results(
    batch_id: int,
    payload: Optional[RecruitmentResultBatchConfirmRequest] = None,
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db),
):
    """
    Explicitly confirm resolved candidate records:
    - Intermediate rounds update Application status without incrementing final placement stats.
    - Final rounds with SELECTED status update Application to SELECTED and profile to PLACED.
    - Dispatches deduplicated student notifications with unique event keys.
    """
    item_ids = payload.item_ids if payload else None
    try:
        result = recruitment_result_service.confirm_batch_results(
            db=db,
            batch_id=batch_id,
            item_ids=item_ids,
            current_user=current_user,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Confirmation failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# =============================================================================
# STUDENT SEARCH (TYPEAHEAD)
# =============================================================================

@router.get("/students/search", response_model=List[StudentSearchItem])
async def search_students_for_matching(
    q: str = Query(..., min_length=2, description="Search by name, USN, or email"),
    limit: int = Query(15, ge=1, le=50),
    current_user: User = Depends(get_current_placement_officer),
    db: Session = Depends(get_db),
):
    """Search active students to resolve ambiguous or unmatched records."""
    return recruitment_result_service.search_students(db=db, query=q, limit=limit)
