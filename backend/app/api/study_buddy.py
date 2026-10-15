"""
Study Buddy API Endpoints

Provides institutional endpoints for:
- Subject management (scoped by department and academic role)
- Syllabus document upload, extraction, and version tracking
- Structured unit and topic retrieval with page provenance
- Review and publication workflows
"""

import logging
import urllib.parse
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File as FastAPIFile, Query, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..core.database import get_db
from ..api.auth import get_current_user
from ..models.user import User, UserRole
from ..models.study_buddy import (
    Subject,
    SyllabusDocument,
    SyllabusUnit,
    SyllabusTopic,
    SyllabusProcessingStatus,
    SyllabusReviewStatus,
    LectureNote,
    LectureNoteStatus,
    LectureNoteProcessingStatus,
    LectureNoteIndexingStatus,
    StudentStudyDocument,
    StudentDocProcessingStatus,
    StudentDocIndexingStatus,
)
from ..schemas.study_buddy import (
    SubjectCreate,
    SubjectUpdate,
    SubjectResponse,
    SyllabusDocumentResponse,
    SyllabusDocumentDetailResponse,
    SyllabusUnitResponse,
    SyllabusTopicResponse,
    SyllabusReviewRequest,
    SyllabusPublishRequest,
    StudyBuddySourceMode,
    StudyBuddyQuestionRequest,
    StudyBuddyAnswerResponse,
    StudyBuddySummaryRequest,
    StudyBuddySummaryResponse,
    StudyBuddyQuizCreateRequest,
    StudyBuddyQuizPublicResponse,
    StudyBuddyQuizSubmitRequest,
    StudyBuddyQuizResultResponse,
    StudyBuddyQuizAttemptSummaryResponse,
    StudentProgressDashboardResponse,
    StudyBuddyPlanResponse,
    StudyBuddyPlanTaskResponse,
    StudyBuddyPlanCreateRequest,
    StudyBuddyPlanUpdateRequest,
    StudyBuddyTaskStatusUpdateRequest,
    LectureNoteResponse,
    LectureNoteDetailResponse,
    LectureNoteUpdateRequest,
    LectureNoteListResponse,
    StudentStudyDocumentResponse,
    StudentStudyDocumentDetailResponse,
    StudentStudyDocumentUpdateRequest,
    StudentStudyDocumentListResponse,
)
from ..services.syllabus_ingestion_service import syllabus_ingestion_service
from ..services.syllabus_indexing_service import syllabus_indexing_service
from ..services.study_buddy_chat_service import study_buddy_chat_service
from ..services.study_buddy_content_service import study_buddy_content_service
from ..services.study_buddy_progress_service import study_buddy_progress_service
from ..services.lecture_notes_service import lecture_notes_service
from ..services.lecture_notes_indexing_service import lecture_notes_indexing_service
from ..services.student_documents_service import student_documents_service
from ..services.student_documents_indexing_service import student_documents_indexing_service
from ..services.file_storage.minio_client import minio_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/study-buddy", tags=["Study Buddy"])


# ============================================
# AUTHORIZATION HELPERS
# ============================================

def _normalize_dept(dept: Optional[str]) -> str:
    """Normalize department strings for robust case-insensitive comparison."""
    return (dept or "").strip().lower()


def _get_user_department(user: User) -> Optional[str]:
    """Resolve department for user across roles (including student profile branch)."""
    if user.department:
        return user.department
    if user.student_profile and user.student_profile.branch:
        return user.student_profile.branch
    return None


def verify_study_buddy_access(current_user: User) -> None:
    """Block placement officers from syllabus management by virtue of placement role."""
    if current_user.role == UserRole.PLACEMENT_OFFICER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Placement Officers do not have syllabus management permissions."
        )


def verify_subject_access(subject: Subject, current_user: User, require_write: bool = False) -> None:
    """
    Enforce institutional role and department scoping on a subject.
    """
    verify_study_buddy_access(current_user)

    if current_user.role == UserRole.ADMIN:
        return

    user_dept = _get_user_department(current_user)
    dept_matches = _normalize_dept(user_dept) == _normalize_dept(subject.department)

    if current_user.role == UserRole.HOD:
        if not dept_matches:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"HOD access restricted to department '{user_dept}'."
            )
        return

    if current_user.role == UserRole.LECTURER:
        assigned_subjects = []
        if current_user.lecturer_profile and current_user.lecturer_profile.subjects:
            assigned_subjects = [str(s).strip().upper() for s in current_user.lecturer_profile.subjects]

        if not dept_matches:
            # Check if lecturer has subject assigned in profile
            if subject.code.strip().upper() not in assigned_subjects:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Lecturer access restricted to department '{user_dept}' or assigned subjects."
                )
        elif require_write and assigned_subjects and subject.code.strip().upper() not in assigned_subjects:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Lecturer is not assigned to teach subject '{subject.code}'."
            )
        return

    if current_user.role == UserRole.STUDENT:
        if require_write:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students are not authorized to modify syllabus records."
            )
        if not dept_matches:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students can only access syllabus materials within their own department."
            )
        if not subject.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subject is not active."
            )
        return


def _build_subject_response(subject: Subject, db: Session, is_student: bool = False) -> SubjectResponse:
    """Helper to populate syllabus count and active published document."""
    query = db.query(SyllabusDocument).filter(SyllabusDocument.subject_id == subject.id)
    if is_student:
        query = query.filter(
            SyllabusDocument.is_published == True,
            SyllabusDocument.review_status == SyllabusReviewStatus.APPROVED
        )

    docs = query.all()
    count = len(docs)

    published_doc = db.query(SyllabusDocument).filter(
        SyllabusDocument.subject_id == subject.id,
        SyllabusDocument.is_published == True,
        SyllabusDocument.review_status == SyllabusReviewStatus.APPROVED
    ).order_by(SyllabusDocument.version.desc()).first()

    return SubjectResponse(
        id=subject.id,
        code=subject.code,
        name=subject.name,
        department=subject.department,
        semester=subject.semester,
        academic_year=subject.academic_year,
        curriculum_version=subject.curriculum_version,
        description=subject.description,
        is_active=subject.is_active,
        created_at=subject.created_at,
        updated_at=subject.updated_at,
        syllabus_documents_count=count,
        published_document_id=published_doc.id if published_doc else None
    )


# ============================================
# SUBJECT ENDPOINTS
# ============================================

@router.get("/subjects", response_model=List[SubjectResponse])
async def list_subjects(
    department: Optional[str] = Query(None, description="Filter by department"),
    semester: Optional[int] = Query(None, ge=1, le=8, description="Filter by semester"),
    active_only: bool = Query(True, description="Filter active subjects only"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List subjects within the caller's authorized scope.
    - Admin: institutional scope.
    - HOD & Lecturer: scoped to caller's department.
    - Student: scoped to caller's department and active subjects only.
    - Placement Officer: forbidden.
    """
    verify_study_buddy_access(current_user)
    user_dept = _get_user_department(current_user)

    query = db.query(Subject)

    if current_user.role == UserRole.ADMIN:
        if department:
            query = query.filter(func.lower(Subject.department) == func.lower(department))
    else:
        # HOD, Lecturer, Student scoped to their department
        if user_dept:
            query = query.filter(func.lower(Subject.department) == func.lower(user_dept))
        else:
            query = query.filter(func.lower(Subject.department) == func.lower(department or ""))

    if current_user.role == UserRole.STUDENT or active_only:
        query = query.filter(Subject.is_active == True)

    if semester:
        query = query.filter(Subject.semester == semester)

    subjects = query.order_by(Subject.code.asc()).all()
    is_student = current_user.role == UserRole.STUDENT
    return [_build_subject_response(s, db, is_student=is_student) for s in subjects]


@router.post("/subjects", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(
    payload: SubjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new academic subject.
    Authorized: Admin, HOD (for own department only).
    """
    verify_study_buddy_access(current_user)

    if current_user.role not in [UserRole.ADMIN, UserRole.HOD]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Administrators and HODs can create subjects."
        )

    dept = payload.department or current_user.department
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department is required to create a subject."
        )

    if current_user.role == UserRole.HOD and _normalize_dept(dept) != _normalize_dept(current_user.department):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HOD cannot create subjects for another department."
        )

    code = payload.code.strip().upper()
    existing = db.query(Subject).filter(
        Subject.code == code,
        Subject.department == dept,
        Subject.curriculum_version == payload.curriculum_version
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Subject with code '{code}' already exists for department '{dept}' (curriculum version: {payload.curriculum_version})."
        )

    new_subject = Subject(
        code=code,
        name=payload.name.strip(),
        department=dept,
        semester=payload.semester,
        academic_year=payload.academic_year,
        curriculum_version=payload.curriculum_version,
        description=payload.description,
        is_active=True
    )
    db.add(new_subject)
    db.commit()
    db.refresh(new_subject)

    return _build_subject_response(new_subject, db)


@router.get("/subjects/{subject_id}", response_model=SubjectResponse)
async def get_subject(
    subject_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve subject details by ID within authorized scope."""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found.")

    verify_subject_access(subject, current_user)
    return _build_subject_response(subject, db, is_student=(current_user.role == UserRole.STUDENT))


@router.put("/subjects/{subject_id}", response_model=SubjectResponse)
async def update_subject(
    subject_id: int,
    payload: SubjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update subject metadata (Admin, HOD for own department)."""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found.")

    if current_user.role not in [UserRole.ADMIN, UserRole.HOD]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to modify subjects.")

    verify_subject_access(subject, current_user, require_write=True)

    if payload.name is not None:
        subject.name = payload.name.strip()
    if payload.semester is not None:
        subject.semester = payload.semester
    if payload.academic_year is not None:
        subject.academic_year = payload.academic_year
    if payload.curriculum_version is not None:
        subject.curriculum_version = payload.curriculum_version
    if payload.description is not None:
        subject.description = payload.description
    if payload.is_active is not None and payload.is_active != subject.is_active:
        subject.is_active = payload.is_active
        if not payload.is_active:
            # Subject deactivated: delete chunks for all its syllabus documents from Qdrant
            for sdoc in subject.syllabus_documents:
                syllabus_indexing_service.delete_document_chunks(sdoc.id)
        else:
            # Subject reactivated: re-index any approved published syllabus document
            for sdoc in subject.syllabus_documents:
                if sdoc.is_published and sdoc.review_status == SyllabusReviewStatus.APPROVED:
                    try:
                        syllabus_indexing_service.index_syllabus_document(db, sdoc.id)
                    except Exception as reindex_err:
                        logger.warning(f"Re-indexing failed on subject reactivation for doc {sdoc.id}: {reindex_err}")

    db.commit()
    db.refresh(subject)
    return _build_subject_response(subject, db)


# ============================================
# SYLLABUS DOCUMENT INGESTION & RETRIEVAL
# ============================================

@router.post("/subjects/{subject_id}/syllabus", response_model=SyllabusDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_syllabus(
    subject_id: int,
    file: UploadFile = FastAPIFile(...),
    title: Optional[str] = Query(None, max_length=255),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload and ingest a syllabus document for a subject.
    Authorized: Admin, HOD, Lecturer within subject department.
    """
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found.")

    if current_user.role not in [UserRole.ADMIN, UserRole.HOD, UserRole.LECTURER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Faculty (HOD, Lecturer) and Admins can upload syllabus documents."
        )

    verify_subject_access(subject, current_user, require_write=True)

    syllabus_doc = await syllabus_ingestion_service.ingest_syllabus(
        db=db,
        subject_id=subject.id,
        file=file,
        current_user=current_user,
        title=title
    )

    # Count units and topics
    units_count = len(syllabus_doc.units)
    topics_count = sum(len(u.topics) for u in syllabus_doc.units)

    response = SyllabusDocumentResponse.model_validate(syllabus_doc)
    response.units_count = units_count
    response.topics_count = topics_count
    return response


@router.get("/subjects/{subject_id}/syllabi", response_model=List[SyllabusDocumentResponse])
async def list_subject_syllabi(
    subject_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List syllabus document versions for a subject.
    - Faculty/Admin: all versions with full extraction statuses.
    - Student: ONLY approved and published versions.
    """
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found.")

    verify_subject_access(subject, current_user)

    query = db.query(SyllabusDocument).filter(SyllabusDocument.subject_id == subject.id)

    if current_user.role == UserRole.STUDENT:
        query = query.filter(
            SyllabusDocument.is_published == True,
            SyllabusDocument.review_status == SyllabusReviewStatus.APPROVED
        )

    docs = query.order_by(SyllabusDocument.version.desc()).all()

    result = []
    for d in docs:
        resp = SyllabusDocumentResponse.model_validate(d)
        resp.units_count = len(d.units)
        resp.topics_count = sum(len(u.topics) for u in d.units)
        result.append(resp)

    return result


@router.get("/syllabi/{document_id}", response_model=SyllabusDocumentDetailResponse)
async def get_syllabus_detail(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve syllabus document details including units, topics, and source provenance.
    - Student: accessible ONLY if document is published and approved in student's department.
    - Faculty/Admin: full access within department scope.
    """
    verify_study_buddy_access(current_user)

    doc = db.query(SyllabusDocument).filter(SyllabusDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Syllabus document not found.")

    subject = doc.subject
    verify_subject_access(subject, current_user)

    if current_user.role == UserRole.STUDENT:
        if not (doc.is_published and doc.review_status == SyllabusReviewStatus.APPROVED):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Document is not published or approved for student viewing."
            )

    units_resp = []
    for u in doc.units:
        u_dict = {
            "id": u.id,
            "document_id": u.document_id,
            "unit_number": u.unit_number,
            "title": u.title,
            "order": u.order,
            "description": u.description,
            "source_page_start": u.source_page_start,
            "source_page_end": u.source_page_end,
            "source_evidence": u.source_evidence,
            "created_at": u.created_at,
            "topics": [
                SyllabusTopicResponse(
                    id=t.id,
                    unit_id=t.unit_id,
                    title=t.title,
                    order=t.order,
                    extracted_text=t.extracted_text,
                    source_page=t.source_page,
                    source_evidence=t.source_evidence,
                    created_at=t.created_at
                )
                for t in u.topics
            ]
        }
        units_resp.append(SyllabusUnitResponse(**u_dict))

    response = SyllabusDocumentDetailResponse.model_validate(doc)
    response.units = units_resp
    response.units_count = len(units_resp)
    response.topics_count = sum(len(u.topics) for u in units_resp)
    return response


# ============================================
# REVIEW, PUBLICATION & RETRY WORKFLOWS
# ============================================

@router.post("/syllabi/{document_id}/review", response_model=SyllabusDocumentResponse)
async def review_syllabus(
    document_id: int,
    payload: SyllabusReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Review syllabus extraction: Approve, Reject, or set to Draft.
    Authorized: Admin, HOD within department.
    """
    verify_study_buddy_access(current_user)

    if current_user.role not in [UserRole.ADMIN, UserRole.HOD]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Administrators and HODs can review syllabus documents."
        )

    doc = db.query(SyllabusDocument).filter(SyllabusDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Syllabus document not found.")

    verify_subject_access(doc.subject, current_user, require_write=True)

    doc.review_status = payload.review_status

    # If rejected or draft, ensure it cannot be published
    if payload.review_status in [SyllabusReviewStatus.REJECTED, SyllabusReviewStatus.DRAFT]:
        doc.is_published = False

    meta = doc.extraction_metadata or {}
    meta["review_notes"] = payload.review_notes
    meta["reviewed_by_id"] = current_user.id
    meta["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    doc.extraction_metadata = meta

    db.commit()
    db.refresh(doc)

    resp = SyllabusDocumentResponse.model_validate(doc)
    resp.units_count = len(doc.units)
    resp.topics_count = sum(len(u.topics) for u in doc.units)
    return resp


@router.post("/syllabi/{document_id}/publish", response_model=SyllabusDocumentResponse)
async def publish_syllabus(
    document_id: int,
    payload: SyllabusPublishRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Publish or unpublish a syllabus document to students.
    Document must be in APPROVED state before it can be published.
    Authorized: Admin, HOD within department.
    """
    verify_study_buddy_access(current_user)

    if current_user.role not in [UserRole.ADMIN, UserRole.HOD]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Administrators and HODs can publish syllabus documents."
        )

    doc = db.query(SyllabusDocument).filter(SyllabusDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Syllabus document not found.")

    verify_subject_access(doc.subject, current_user, require_write=True)

    if payload.is_published:
        if doc.review_status != SyllabusReviewStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Syllabus document must be approved before publication."
            )

        # Supersede older published versions for the same subject
        other_published = db.query(SyllabusDocument).filter(
            SyllabusDocument.subject_id == doc.subject_id,
            SyllabusDocument.id != doc.id,
            SyllabusDocument.is_published == True
        ).all()
        for other in other_published:
            other.is_published = False
            syllabus_indexing_service.delete_document_chunks(other.id)

        doc.is_published = True
        doc.published_at = datetime.now(timezone.utc)
        doc.published_by_id = current_user.id
        db.commit()
        db.refresh(doc)

        # Automatically index into dedicated study_buddy_chunks collection
        try:
            syllabus_indexing_service.index_syllabus_document(db, doc.id)
        except Exception as idx_err:
            logger.warning(f"Auto-indexing on publish failed for doc {doc.id}: {idx_err}")
    else:
        doc.is_published = False
        db.commit()
        db.refresh(doc)
        # Remove points from Qdrant upon unpublish
        syllabus_indexing_service.delete_document_chunks(doc.id)

    resp = SyllabusDocumentResponse.model_validate(doc)
    resp.units_count = len(doc.units)
    resp.topics_count = sum(len(u.topics) for u in doc.units)
    return resp


@router.post("/syllabi/{document_id}/retry", response_model=SyllabusDocumentResponse)
async def retry_syllabus(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retry extraction and parsing on a failed or review-required syllabus document.
    Authorized: Admin, HOD, Lecturer within department.
    """
    verify_study_buddy_access(current_user)

    if current_user.role not in [UserRole.ADMIN, UserRole.HOD, UserRole.LECTURER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Faculty and Administrators only."
        )

    doc = db.query(SyllabusDocument).filter(SyllabusDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Syllabus document not found.")

    verify_subject_access(doc.subject, current_user, require_write=True)

    updated_doc = syllabus_ingestion_service.retry_processing(db, document_id)

    resp = SyllabusDocumentResponse.model_validate(updated_doc)
    resp.units_count = len(updated_doc.units)
    resp.topics_count = sum(len(u.topics) for u in updated_doc.units)
    return resp


@router.post("/syllabi/{document_id}/index", response_model=Dict[str, Any])
async def trigger_indexing(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually trigger or retry vector indexing for an approved & published syllabus document.
    Authorized: Admin, HOD within department.
    """
    verify_study_buddy_access(current_user)

    if current_user.role not in [UserRole.ADMIN, UserRole.HOD]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Administrators and HODs can trigger syllabus indexing."
        )

    doc = db.query(SyllabusDocument).filter(SyllabusDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Syllabus document not found.")

    verify_subject_access(doc.subject, current_user, require_write=True)

    result = syllabus_indexing_service.index_syllabus_document(db, document_id)
    return result


@router.get("/syllabi/{document_id}/indexing-status", response_model=Dict[str, Any])
async def get_indexing_status(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Inspect internal indexing metadata and status.
    Authorized: Faculty and Administrators only. Students strictly forbidden.
    """
    verify_study_buddy_access(current_user)

    if current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students cannot inspect internal indexing metadata."
        )

    doc = db.query(SyllabusDocument).filter(SyllabusDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Syllabus document not found.")

    verify_subject_access(doc.subject, current_user)

    meta = doc.extraction_metadata or {}
    return {
        "document_id": doc.id,
        "version": doc.version,
        "is_published": doc.is_published,
        "review_status": doc.review_status.value if hasattr(doc.review_status, "value") else str(doc.review_status),
        "indexing_status": meta.get("indexing_status", "UNINDEXED"),
        "indexed_chunks_count": meta.get("indexed_chunks_count", 0),
        "indexed_at": meta.get("indexed_at"),
        "indexing_error": meta.get("indexing_error")
    }


@router.get("/search", response_model=List[Dict[str, Any]])
async def search_syllabus_content(
    query: str = Query(..., min_length=2, max_length=500, description="Search query string"),
    subject_id: Optional[int] = Query(None, description="Optional subject ID filter"),
    source_mode: Optional[StudyBuddySourceMode] = Query(StudyBuddySourceMode.SYLLABUS, description="Source mode: 'syllabus', 'lecture_notes', 'all', 'my_documents', or 'all_my_sources'"),
    limit: int = Query(5, ge=1, le=20, description="Max results to return"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Semantic search across approved and published academic chunks in dedicated Qdrant collection.
    - Scoped by source_mode: 'syllabus', 'lecture_notes', 'all', 'my_documents', or 'all_my_sources'.
    - Role & department authorization enforced against PostgreSQL before and after Qdrant search.
    - Placement Officer forbidden.
    """
    verify_study_buddy_access(current_user)
    return study_buddy_chat_service.search_unified_chunks(
        db=db,
        query=query,
        current_user=current_user,
        subject_id=subject_id,
        source_mode=source_mode,
        limit=limit
    )


@router.post("/chat", response_model=StudyBuddyAnswerResponse)
@router.post("/ask", response_model=StudyBuddyAnswerResponse)
async def ask_study_buddy(
    request: StudyBuddyQuestionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    RAG-powered academic Study Buddy QA endpoint.
    - Scoped strictly to student's authorized department and approved materials (or personal uploads).
    - Supports source modes: 'syllabus', 'lecture_notes', 'all', 'my_documents', or 'all_my_sources'.
    - Retrieves relevant chunks from dedicated Qdrant collection.
    - Passes bounded context to shared Qwen Instruct singleton.
    - Provides verified source citations with document, unit, topic, and page provenance.
    - Placement Officers forbidden.
    """
    verify_study_buddy_access(current_user)
    return study_buddy_chat_service.ask_question(
        db=db,
        current_user=current_user,
        question=request.question,
        subject_id=request.subject_id,
        source_mode=request.source_mode
    )


# ============================================
# STUDY SUMMARIES ENDPOINTS
# ============================================

@router.post("/summaries/generate", response_model=StudyBuddySummaryResponse)
async def generate_study_summary(
    request: StudyBuddySummaryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate syllabus-grounded academic study summaries.
    - Scoped strictly to student's authorized department and approved, published syllabi.
    - Supports concise revision notes or detailed breakdowns.
    - Returns verified source citations with provenance.
    - Placement Officers forbidden.
    """
    verify_study_buddy_access(current_user)
    return study_buddy_content_service.generate_summary(
        db=db,
        current_user=current_user,
        subject_id=request.subject_id,
        unit_id=request.unit_id,
        topic_id=request.topic_id,
        format_type=request.format_type
    )


# ============================================
# QUIZ GENERATION, ATTEMPTS & EVALUATION
# ============================================

@router.post("/quizzes/generate", response_model=StudyBuddyQuizPublicResponse)
async def generate_quiz(
    request: StudyBuddyQuizCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate and persist a syllabus-grounded multiple-choice quiz.
    - Answer keys and explanations are held securely server-side and omitted from this public response.
    - Strict validation rejects malformed, duplicate, or unsupported questions.
    - Placement Officers forbidden.
    """
    verify_study_buddy_access(current_user)
    return study_buddy_content_service.generate_quiz(
        db=db,
        current_user=current_user,
        subject_id=request.subject_id,
        unit_id=request.unit_id,
        topic_id=request.topic_id,
        num_questions=request.num_questions,
        difficulty=request.difficulty
    )


@router.post("/quizzes/attempts/{attempt_id}/submit", response_model=StudyBuddyQuizResultResponse)
async def submit_quiz(
    attempt_id: int,
    request: StudyBuddyQuizSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit answers for a generated quiz attempt.
    - Strictly graded server-side; prevents client score tampering.
    - Returns full question results, correct options, explanations, and verified citations.
    - Strict ownership check: only the student who created the attempt can submit.
    """
    verify_study_buddy_access(current_user)
    return study_buddy_content_service.submit_quiz(
        db=db,
        current_user=current_user,
        attempt_id=attempt_id,
        student_answers=request.answers
    )


@router.get("/quizzes/attempts", response_model=List[StudyBuddyQuizAttemptSummaryResponse])
async def list_quiz_attempts(
    subject_id: Optional[int] = Query(None, description="Optional subject ID filter"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List past quiz attempts and scores for the authenticated student.
    - Placement Officers forbidden.
    """
    verify_study_buddy_access(current_user)
    return study_buddy_content_service.list_student_attempts(
        db=db,
        current_user=current_user,
        subject_id=subject_id
    )


@router.get("/quizzes/attempts/{attempt_id}", response_model=StudyBuddyQuizResultResponse)
async def get_quiz_attempt_result(
    attempt_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve quiz results for an attempt.
    - Strict ownership check: students cannot view other students' results.
    - Placement Officers forbidden.
    """
    verify_study_buddy_access(current_user)
    return study_buddy_content_service.get_quiz_result(
        db=db,
        current_user=current_user,
        attempt_id=attempt_id
    )


# ============================================
# STEP 4.5: PROGRESS DASHBOARD & ADAPTIVE PLANNER
# ============================================

@router.get("/progress/dashboard", response_model=StudentProgressDashboardResponse)
async def get_student_progress_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve comprehensive learning progress metrics derived from persisted quiz attempts.
    - Gracefully handles zero attempts, incomplete attempts, and limited history.
    - Transparent weak-topic calculation rules.
    - Placement Officers forbidden.
    """
    verify_study_buddy_access(current_user)
    return study_buddy_progress_service.get_student_dashboard_progress(
        db=db,
        current_user=current_user
    )


@router.post("/plans", response_model=StudyBuddyPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_study_plan(
    request: StudyBuddyPlanCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate an adaptive, syllabus-grounded study plan.
    - Prioritizes topics with repeated low quiz scores and unpracticed topics.
    - Enforces realistic scheduling feasibility based on target date and daily study budget.
    - Placement Officers forbidden.
    """
    verify_study_buddy_access(current_user)
    return study_buddy_progress_service.create_study_plan(
        db=db,
        current_user=current_user,
        request=request
    )


@router.get("/plans", response_model=List[StudyBuddyPlanResponse])
async def list_student_plans(
    subject_id: Optional[int] = Query(None, description="Optional subject ID filter"),
    status: Optional[str] = Query(None, description="Optional plan status filter (ACTIVE, COMPLETED, ARCHIVED)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all study plans owned by the authenticated student.
    - Placement Officers forbidden.
    """
    verify_study_buddy_access(current_user)
    return study_buddy_progress_service.list_student_plans(
        db=db,
        current_user=current_user,
        subject_id=subject_id,
        status_filter=status
    )


@router.get("/plans/{plan_id}", response_model=StudyBuddyPlanResponse)
async def get_study_plan_detail(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve full study plan and ordered tasks with syllabus provenance.
    - Strict student ownership enforcement.
    - Placement Officers forbidden.
    """
    verify_study_buddy_access(current_user)
    return study_buddy_progress_service.get_plan_detail(
        db=db,
        current_user=current_user,
        plan_id=plan_id
    )


@router.patch("/plans/{plan_id}", response_model=StudyBuddyPlanResponse)
async def update_study_plan(
    plan_id: int,
    request: StudyBuddyPlanUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update permitted study plan settings (target_date, daily_budget_minutes, title, status).
    - Checks feasibility if schedule is modified.
    - Strict student ownership enforcement.
    """
    verify_study_buddy_access(current_user)
    return study_buddy_progress_service.update_plan(
        db=db,
        current_user=current_user,
        plan_id=plan_id,
        request=request
    )


@router.patch("/plans/{plan_id}/tasks/{task_id}", response_model=StudyBuddyPlanTaskResponse)
async def update_study_plan_task_status(
    plan_id: int,
    task_id: int,
    request: StudyBuddyTaskStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a study plan task as completed or reopen it.
    - Updates plan's completed_tasks counter and auto-updates plan status.
    - Strict student ownership enforcement.
    """
    verify_study_buddy_access(current_user)
    return study_buddy_progress_service.update_task_status(
        db=db,
        current_user=current_user,
        plan_id=plan_id,
        task_id=task_id,
        is_completed=request.is_completed
    )


@router.post("/plans/{plan_id}/regenerate", response_model=StudyBuddyPlanResponse)
async def regenerate_study_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Regenerate plan task priorities based on latest quiz history, preserving completed tasks.
    - Strict student ownership enforcement.
    """
    verify_study_buddy_access(current_user)
    return study_buddy_progress_service.regenerate_plan(
        db=db,
        current_user=current_user,
        plan_id=plan_id
    )


# ============================================
# LECTURE NOTES LIBRARY ENDPOINTS
# ============================================

@router.post(
    "/subjects/{subject_id}/notes",
    response_model=LectureNoteResponse,
    status_code=status.HTTP_201_CREATED
)
async def upload_lecture_note(
    subject_id: int,
    file: UploadFile = FastAPIFile(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    unit_id: Optional[int] = Form(None),
    topic_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload a lecture note for an authorized subject.
    - PDF, PNG, DOCX, and PPTX supported up to 500 MB.
    - Streams and validates file with bounded memory.
    - Extracts readable text and saves to dedicated 'lecture-notes' bucket.
    - Placement Officers blocked (403). Students blocked (403).
    - Lecturers authorized for subject, HODs for department, Admins global.
    """
    verify_study_buddy_access(current_user)
    if current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students are not authorized to upload lecture notes."
        )

    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {subject_id} not found."
        )

    verify_subject_access(subject, current_user, require_write=True)

    return await lecture_notes_service.upload_and_ingest_note(
        db=db,
        subject_id=subject_id,
        file=file,
        current_user=current_user,
        title=title,
        description=description,
        unit_id=unit_id,
        topic_id=topic_id
    )


@router.get(
    "/subjects/{subject_id}/notes",
    response_model=List[LectureNoteResponse]
)
async def list_lecture_notes(
    subject_id: int,
    unit_id: Optional[int] = None,
    topic_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List lecture notes for an authorized subject.
    - Students see only PUBLISHED notes for active subjects in their department.
    - Staff (Lecturer/HOD/Admin) see notes across lifecycle states.
    - Placement Officers blocked (403).
    """
    verify_study_buddy_access(current_user)

    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {subject_id} not found."
        )

    verify_subject_access(subject, current_user, require_write=False)

    query = db.query(LectureNote).filter(LectureNote.subject_id == subject_id)

    # Students strictly restricted to published notes
    if current_user.role == UserRole.STUDENT:
        query = query.filter(
            LectureNote.is_published == True,
            LectureNote.status == LectureNoteStatus.PUBLISHED
        )
    elif status_filter:
        query = query.filter(LectureNote.status == status_filter)

    if unit_id is not None:
        query = query.filter(LectureNote.unit_id == unit_id)
    if topic_id is not None:
        query = query.filter(LectureNote.topic_id == topic_id)
    if search and search.strip():
        query = query.filter(LectureNote.title.ilike(f"%{search.strip()}%"))

    notes = query.order_by(LectureNote.created_at.desc()).offset(skip).limit(limit).all()
    return notes


@router.get(
    "/notes/{note_id}",
    response_model=LectureNoteDetailResponse
)
async def get_lecture_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve metadata for an authorized lecture note.
    - Students can access only published notes for active subjects in their department.
    - Staff can access notes for subjects they are authorized to manage.
    - Placement Officers blocked (403).
    """
    verify_study_buddy_access(current_user)

    note = db.query(LectureNote).filter(LectureNote.id == note_id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lecture note with ID {note_id} not found."
        )

    verify_subject_access(note.subject, current_user, require_write=False)

    if current_user.role == UserRole.STUDENT:
        if not note.is_published or note.status != LectureNoteStatus.PUBLISHED:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lecture note not found or not published."
            )

    return LectureNoteDetailResponse(
        id=note.id,
        subject_id=note.subject_id,
        uploaded_by_id=note.uploaded_by_id,
        file_id=note.file_id,
        unit_id=note.unit_id,
        topic_id=note.topic_id,
        title=note.title,
        description=note.description,
        original_filename=note.original_filename,
        file_size=note.file_size,
        mime_type=note.mime_type,
        status=note.status,
        is_published=note.is_published,
        published_at=note.published_at,
        processing_status=note.processing_status,
        indexing_status=note.indexing_status,
        indexed_chunk_count=note.indexed_chunk_count,
        download_count=note.download_count,
        extraction_error=note.extraction_error,
        created_at=note.created_at,
        updated_at=note.updated_at,
        subject_name=note.subject.name,
        subject_code=note.subject.code,
        uploader_name=note.uploader.name if note.uploader else None,
        unit_title=note.unit.title if note.unit else None,
        topic_title=note.topic.title if note.topic else None,
        extraction_metadata=note.extraction_metadata
    )


@router.patch(
    "/notes/{note_id}",
    response_model=LectureNoteResponse
)
async def update_lecture_note(
    note_id: int,
    request: LectureNoteUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update lecture note metadata and publication status.
    - Students blocked (403). Placement Officers blocked (403).
    - Publication strictly guarded: requires successful text extraction.
    """
    verify_study_buddy_access(current_user)
    if current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students are not authorized to modify lecture notes."
        )

    note = db.query(LectureNote).filter(LectureNote.id == note_id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lecture note with ID {note_id} not found."
        )

    verify_subject_access(note.subject, current_user, require_write=True)

    return lecture_notes_service.update_note(db, note, request)


@router.delete(
    "/notes/{note_id}",
    status_code=status.HTTP_200_OK
)
async def delete_lecture_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Safely delete a lecture note and remove its binary object from MinIO.
    - Students blocked (403). Placement Officers blocked (403).
    """
    verify_study_buddy_access(current_user)
    if current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students are not authorized to delete lecture notes."
        )

    note = db.query(LectureNote).filter(LectureNote.id == note_id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lecture note with ID {note_id} not found."
        )

    verify_subject_access(note.subject, current_user, require_write=True)

    lecture_notes_service.delete_note(db, note)
    return {"message": "Lecture note deleted successfully", "id": note_id}


@router.post(
    "/notes/{note_id}/retry",
    response_model=LectureNoteResponse
)
async def retry_lecture_note_processing(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retry text extraction for an eligible failed lecture note by re-reading from MinIO.
    - Students blocked (403). Placement Officers blocked (403).
    """
    verify_study_buddy_access(current_user)
    if current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students are not authorized to retry processing lecture notes."
        )

    note = db.query(LectureNote).filter(LectureNote.id == note_id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lecture note with ID {note_id} not found."
        )

    verify_subject_access(note.subject, current_user, require_write=True)

    return await lecture_notes_service.retry_note_processing(db, note_id=note_id)


@router.get(
    "/notes/{note_id}/download",
    status_code=status.HTTP_200_OK
)
async def download_lecture_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Securely stream the original binary of an authorized lecture note.
    - Students: restricted to published notes of active subjects in their department (resolved via _get_user_department).
    - Lecturers: scoped to department or assigned subjects.
    - HOD: scoped to department.
    - Admin: institutional scope.
    - Placement Officers: forbidden (HTTP 403).
    - Unapproved / draft notes return 404 for students (anti-enumeration).
    - Increments download_count atomically on PostgreSQL before streaming begins.
    - Streams directly from MinIO with bounded memory (64 KiB chunks).
    """
    verify_study_buddy_access(current_user)

    note = db.query(LectureNote).filter(LectureNote.id == note_id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lecture note with ID {note_id} not found."
        )

    verify_subject_access(note.subject, current_user, require_write=False)

    if current_user.role == UserRole.STUDENT:
        if not note.is_published or note.status != LectureNoteStatus.PUBLISHED:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lecture note not found or not published."
            )

    # 1. Retrieve stream from MinIO bucket & key
    try:
        response_stream = minio_client.get_object_stream(note.minio_bucket, note.minio_object_key)
    except Exception as e:
        logger.error(f"MinIO storage error retrieving note {note_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Storage service error while retrieving file."
        )

    if response_stream is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lecture note file content not found in storage."
        )

    # 2. Atomically increment download_count once authorization succeeds and stream is ready
    try:
        db.query(LectureNote).filter(LectureNote.id == note_id).update(
            {LectureNote.download_count: LectureNote.download_count + 1},
            synchronize_session=False
        )
        db.commit()
    except Exception as count_err:
        logger.warning(f"Failed to increment download count for note {note_id}: {count_err}")
        db.rollback()

    # 3. Format safe Content-Disposition with RFC 5987 / RFC 6266 encoding
    clean_filename = (note.original_filename or f"note_{note.id}").replace('"', '\\"')
    encoded_filename = urllib.parse.quote(note.original_filename or f"note_{note.id}")

    def file_iterator():
        try:
            if hasattr(response_stream, "stream"):
                for chunk in response_stream.stream(amt=64 * 1024):
                    yield chunk
            else:
                while True:
                    chunk = response_stream.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk
        finally:
            try:
                if hasattr(response_stream, "close"):
                    response_stream.close()
                if hasattr(response_stream, "release_conn"):
                    response_stream.release_conn()
            except Exception as close_err:
                logger.debug(f"Error releasing MinIO stream connection: {close_err}")

    headers = {
        "Content-Disposition": f'attachment; filename="{clean_filename}"; filename*=UTF-8\'\'{encoded_filename}'
    }
    if note.file_size and note.file_size > 0:
        headers["Content-Length"] = str(note.file_size)

    return StreamingResponse(
        file_iterator(),
        media_type=note.mime_type or "application/octet-stream",
        headers=headers
    )


@router.post(
    "/notes/{note_id}/index",
    response_model=Dict[str, Any]
)
async def index_lecture_note_endpoint(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually trigger or retry vector indexing for an eligible published lecture note.
    - Requires faculty write access to note's subject (or Admin).
    - Students and Placement Officers strictly forbidden (403).
    """
    verify_study_buddy_access(current_user)
    if current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students are not authorized to trigger indexing."
        )

    note = db.query(LectureNote).filter(LectureNote.id == note_id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lecture note with ID {note_id} not found."
        )

    verify_subject_access(note.subject, current_user, require_write=True)

    return lecture_notes_indexing_service.index_lecture_note(db, note_id)


@router.get(
    "/notes/{note_id}/indexing-status",
    response_model=Dict[str, Any]
)
async def get_lecture_note_indexing_status(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Inspect indexing status and metadata for a lecture note.
    Faculty and Admin only.
    """
    verify_study_buddy_access(current_user)
    if current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students cannot inspect internal indexing status."
        )

    note = db.query(LectureNote).filter(LectureNote.id == note_id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lecture note with ID {note_id} not found."
        )

    verify_subject_access(note.subject, current_user, require_write=False)

    return {
        "note_id": note.id,
        "subject_id": note.subject_id,
        "status": note.status.value,
        "is_published": note.is_published,
        "indexing_status": note.indexing_status.value,
        "indexed_chunk_count": note.indexed_chunk_count,
        "extraction_metadata": note.extraction_metadata or {},
        "updated_at": note.updated_at.isoformat() if note.updated_at else None
    }


# ============================================
# STUDENT STUDY DOCUMENTS ENDPOINTS
# ============================================

def _format_student_doc_detail(doc: StudentStudyDocument) -> StudentStudyDocumentDetailResponse:
    """Format StudentStudyDocument to StudentStudyDocumentDetailResponse with sanitized metadata."""
    clean_meta = {}
    if doc.extraction_metadata:
        for k, v in doc.extraction_metadata.items():
            if k in ("file_path", "temp_path", "minio_bucket", "minio_object_key"):
                continue
            clean_meta[k] = v

    return StudentStudyDocumentDetailResponse(
        id=doc.id,
        student_id=doc.student_id,
        subject_id=doc.subject_id,
        title=doc.title,
        description=doc.description,
        original_filename=doc.original_filename,
        file_size=doc.file_size,
        mime_type=doc.mime_type,
        content_hash=doc.content_hash,
        is_active=doc.is_active,
        processing_status=doc.processing_status,
        indexing_status=doc.indexing_status,
        indexed_chunk_count=doc.indexed_chunk_count,
        extraction_error=doc.extraction_error,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        subject_name=doc.subject.name if doc.subject else None,
        subject_code=doc.subject.code if doc.subject else None,
        subject_department=doc.subject.department if doc.subject else None,
        extraction_metadata=clean_meta,
    )


@router.post(
    "/my-documents",
    response_model=StudentStudyDocumentDetailResponse,
    status_code=status.HTTP_201_CREATED
)
async def upload_student_study_document(
    file: UploadFile = FastAPIFile(...),
    title: str = Form(..., min_length=1, max_length=255, description="Document title"),
    description: Optional[str] = Form(None, description="Optional document description"),
    subject_id: Optional[int] = Form(None, description="Optional academic subject ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload and ingest a personal study document for the authenticated student.
    - Owner is strictly derived from the authenticated session (never trusted from body).
    - Enforces 50 MiB per-file limit, format validation, anti-zip-bomb, and active quotas.
    - Offloads text extraction to dedicated thread pool.
    - Automatically indexes extracted text into Qdrant vector collection for personal RAG.
    - Placement Officers forbidden.
    """
    verify_study_buddy_access(current_user)

    doc = await student_documents_service.upload_and_ingest_document(
        db=db,
        file=file,
        student=current_user,
        title=title,
        description=description,
        subject_id=subject_id
    )

    # Auto-index into Qdrant if text extraction was successful
    if doc.processing_status == StudentDocProcessingStatus.EXTRACTED:
        try:
            student_documents_indexing_service.index_student_document(db, doc.id, current_user.id)
            db.refresh(doc)
        except Exception as idx_err:
            logger.warning(f"Auto-indexing for student doc {doc.id} encountered error: {idx_err}")

    return _format_student_doc_detail(doc)


@router.get(
    "/my-documents",
    response_model=StudentStudyDocumentListResponse
)
async def list_my_study_documents(
    subject_id: Optional[int] = Query(None, description="Filter by subject ID"),
    search: Optional[str] = Query(None, description="Search by title or filename"),
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Page size limit"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List active study documents owned by the authenticated student.
    - Strictly scoped to current_user.id.
    - Placement Officers forbidden.
    """
    verify_study_buddy_access(current_user)

    query = db.query(StudentStudyDocument).filter(
        StudentStudyDocument.student_id == current_user.id,
        StudentStudyDocument.is_active == True
    )

    if subject_id is not None:
        query = query.filter(StudentStudyDocument.subject_id == subject_id)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            (StudentStudyDocument.title.ilike(term)) |
            (StudentStudyDocument.original_filename.ilike(term))
        )

    total = query.count()
    items = query.order_by(StudentStudyDocument.created_at.desc()).offset(skip).limit(limit).all()

    return StudentStudyDocumentListResponse(
        items=[StudentStudyDocumentResponse.model_validate(it) for it in items],
        total=total,
        skip=skip,
        limit=limit
    )


@router.get(
    "/my-documents/{document_id}",
    response_model=StudentStudyDocumentDetailResponse
)
async def get_my_study_document_detail(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get metadata and processing/indexing status for a student study document.
    - Strictly verifies ownership: returns 404 if not found or owned by another student.
    - Never leaks MinIO bucket names, object keys, or raw extracted text.
    - Placement Officers forbidden.
    """
    verify_study_buddy_access(current_user)

    doc = db.query(StudentStudyDocument).filter(
        StudentStudyDocument.id == document_id,
        StudentStudyDocument.student_id == current_user.id,
        StudentStudyDocument.is_active == True
    ).first()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student study document with ID {document_id} not found."
        )

    return _format_student_doc_detail(doc)


@router.patch(
    "/my-documents/{document_id}",
    response_model=StudentStudyDocumentDetailResponse
)
async def update_my_study_document_metadata(
    document_id: int,
    request: StudentStudyDocumentUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update permitted metadata (title, description) for an active personal study document.
    - Strictly verifies student ownership.
    - Placement Officers forbidden.
    """
    verify_study_buddy_access(current_user)

    doc = db.query(StudentStudyDocument).filter(
        StudentStudyDocument.id == document_id,
        StudentStudyDocument.student_id == current_user.id,
        StudentStudyDocument.is_active == True
    ).first()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student study document with ID {document_id} not found."
        )

    if request.title is not None:
        clean_title = request.title.strip()
        if not clean_title:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Title cannot be empty."
            )
        doc.title = clean_title

    if request.description is not None:
        doc.description = request.description.strip() if request.description.strip() else None

    doc.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(doc)

    return _format_student_doc_detail(doc)


@router.delete(
    "/my-documents/{document_id}",
    response_model=Dict[str, Any]
)
async def delete_my_study_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a personal study document using the hardened cleanup flow:
    1. Verifies ownership.
    2. Immediately marks inactive to release quotas and block retrieval.
    3. Purges Qdrant vector chunks.
    4. Purges binary file from MinIO.
    5. Permanently deletes database row upon full cleanup completion.
    - Placement Officers forbidden.
    """
    verify_study_buddy_access(current_user)

    doc = db.query(StudentStudyDocument).filter(
        StudentStudyDocument.id == document_id,
        StudentStudyDocument.student_id == current_user.id
    ).first()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student study document with ID {document_id} not found."
        )

    student_documents_service.delete_document(db, document_id, current_user.id)
    return {
        "message": "Document successfully deleted.",
        "document_id": document_id
    }


@router.post(
    "/my-documents/{document_id}/retry",
    response_model=StudentStudyDocumentDetailResponse
)
async def retry_my_study_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retry text extraction or vector indexing for an eligible failed document.
    - Verifies ownership and concurrency claim locks.
    - Placement Officers forbidden.
    """
    verify_study_buddy_access(current_user)

    doc = db.query(StudentStudyDocument).filter(
        StudentStudyDocument.id == document_id,
        StudentStudyDocument.student_id == current_user.id
    ).first()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student study document with ID {document_id} not found."
        )

    if not doc.is_active:
        meta = doc.extraction_metadata or {}
        if meta.get("cleanup_pending"):
            student_documents_service.retry_document_cleanup(db, document_id, current_user.id)
            return _format_student_doc_detail(doc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot retry an inactive or deleted document."
        )

    if doc.processing_status == StudentDocProcessingStatus.PROCESSING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document {document_id} is currently being processed by another task."
        )

    if doc.indexing_status == StudentDocIndexingStatus.INDEXING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document {document_id} is currently being indexed by another task."
        )

    # 1. Retry text extraction if failed or unextracted
    if doc.processing_status in (StudentDocProcessingStatus.FAILED, StudentDocProcessingStatus.UPLOADED):
        doc = await student_documents_service.retry_document_processing(db, document_id, current_user.id)
        if doc.processing_status == StudentDocProcessingStatus.EXTRACTED:
            try:
                student_documents_indexing_service.index_student_document(db, document_id, current_user.id)
                db.refresh(doc)
            except Exception as idx_err:
                logger.warning(f"Indexing error during retry for student doc {document_id}: {idx_err}")

    # 2. If extraction is already successful, retry indexing if not indexed or failed
    elif doc.processing_status == StudentDocProcessingStatus.EXTRACTED:
        student_documents_indexing_service.index_student_document(db, document_id, current_user.id)
        db.refresh(doc)

    return _format_student_doc_detail(doc)


@router.get("/my-documents/{document_id}/download")
async def download_my_study_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Download the authenticated student's original study document binary securely from MinIO.
    - Owner is strictly verified: returns 404 for missing or foreign-owned documents.
    - MinIO bucket names and storage keys are never exposed in URLs or responses.
    - Placement Officers forbidden.
    """
    verify_study_buddy_access(current_user)

    doc = db.query(StudentStudyDocument).filter(
        StudentStudyDocument.id == document_id,
        StudentStudyDocument.student_id == current_user.id,
        StudentStudyDocument.is_active == True
    ).first()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student study document with ID {document_id} not found."
        )

    try:
        response_stream = minio_client.get_object_stream(doc.minio_bucket, doc.minio_object_key)
    except Exception as e:
        logger.error(f"Failed to fetch student document from MinIO: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Storage service error while retrieving file."
        )

    if response_stream is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document binary file not found in storage."
        )

    def file_iterator():
        try:
            if hasattr(response_stream, "stream"):
                for chunk in response_stream.stream(amt=64 * 1024):
                    yield chunk
            else:
                while True:
                    chunk = response_stream.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk
        finally:
            try:
                if hasattr(response_stream, "close"):
                    response_stream.close()
                if hasattr(response_stream, "release_conn"):
                    response_stream.release_conn()
            except Exception as close_err:
                logger.debug(f"Error releasing MinIO stream connection: {close_err}")

    clean_filename = doc.original_filename.replace('"', '\\"')
    encoded_filename = urllib.parse.quote(doc.original_filename)
    headers = {
        "Content-Disposition": f'attachment; filename="{clean_filename}"; filename*=UTF-8\'\'{encoded_filename}'
    }
    if doc.file_size and doc.file_size > 0:
        headers["Content-Length"] = str(doc.file_size)

    return StreamingResponse(
        file_iterator(),
        media_type=doc.mime_type or "application/octet-stream",
        headers=headers
    )





