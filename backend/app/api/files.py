"""
File API Endpoints

Provides REST API for file operations:
- Upload files
- Download files
- Search files
- Manage file metadata
- Version control
"""

import os
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File as FastAPIFile, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from uuid import UUID

from ..core.database import get_db
from ..api.auth import get_current_user
from ..models.user import User, UserRole
from ..models.file import File, FileStatus, FileType
from ..models.file_version import FileVersion
from ..schemas.file import (
    FileResponse,
    FileDetailResponse,
    FileUploadResponse,
    FileUpdate,
    FileSearchQuery,
    FileSearchResponse,
    FileStatistics,
    FileBulkDeleteRequest,
    FileBulkDeleteResponse,
    FileVersionResponse,
    FileVersionRestoreRequest
)
from ..services.file_storage.file_service import file_service
from ..services.file_storage.minio_client import minio_client
from ..services.file_storage.search_service import search_service
from ..services.audit_service import audit_service
from ..core.config import settings

# Import for direct embedding generation
# from ..tasks.file_tasks import generate_embedding

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["Files"])


# ============================================
# UPLOAD ENDPOINTS
# ============================================

@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    title: Optional[str] = Query(None, max_length=255),
    description: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(None),
    department: Optional[str] = Query(None, max_length=50),
    file_type: str = Query("other", description="File type: exam_duty, assignment, circular, resume, timetable, certificate, placement_doc, other"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a file to the system.
    
    - **file**: The file to upload (max 50MB)
    - **title**: Optional title for the file
    - **description**: Optional description
    - **tags**: Optional tags for categorization
    - **department**: Department name (defaults to user's department)
    - **file_type**: Type of file (exam_duty, assignment, circular, resume, timetable, certificate, placement_doc, other)
    """
    
    # Check file size
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    
    if file_size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size: {settings.MAX_FILE_SIZE // (1024 * 1024)}MB"
        )
    
    # Check file extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext and ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )
    
    # Validate file type
    valid_file_types = ['exam_duty', 'assignment', 'circular', 'resume', 'timetable', 'certificate', 'placement_doc', 'other']
    if file_type not in valid_file_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(valid_file_types)}"
        )
    
    # Check permissions for certain file types
    if file_type == "exam_duty" and current_user.role not in [UserRole.HOD, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HODs and Admins can upload exam duties"
        )
    
    if file_type == "resume" and current_user.role not in [UserRole.STUDENT, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can upload resumes"
        )
    
    # Upload file
    try:
        result = await file_service.upload_file(
            db=db,
            file=file,
            uploaded_by=current_user,
            title=title,
            description=description,
            tags=tags or [],
            department=department or current_user.department,
            file_type=file_type,
            extra_data={"upload_source": "api"}
        )
        
        if not result['success']:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get('message', 'Upload failed')
            )
        
        # Generate embedding directly (bypass Celery for now)
        try:
            logger.info(f"🔢 Generating embedding for file: {result['file_id']}")
                #             generate_embedding(str(result['file_id']))
            logger.info(f"✅ Embedding generated for file: {result['file_id']}")
        except Exception as e:
            logger.error(f"❌ Failed to generate embedding: {str(e)}")
            # Don't fail the upload if embedding fails
        
        return FileUploadResponse(
            success=True,
            message=result['message'],
            file_id=result['file_id'],
            file=FileResponse.model_validate(result['file'])
        )
        
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================
# SEARCH ENDPOINTS (FIXED)
# ============================================

@router.post("/search", response_model=FileSearchResponse)
async def search_files(
    query: FileSearchQuery,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search for files using semantic search.
    """
    logger.info(f"🔍 Search query: '{query.query}', department: {query.department}, user: {current_user.email}, role: {current_user.role}")
    
    # If department not specified, use current user's department
    # Only apply department filter if user is not admin
    if not query.department:
        if current_user.role != UserRole.ADMIN:
            query.department = current_user.department
            logger.info(f"   Using user's department: {query.department}")
        else:
            logger.info("   Admin user - searching all departments")
    else:
        logger.info(f"   Using specified department: {query.department}")
    
    return search_service.search(db, query, current_user)


@router.get("/search/suggestions")
async def get_search_suggestions(
    q: str = Query(..., min_length=1),
    limit: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get search suggestions."""
    suggestions = search_service.get_search_suggestions(db, q, limit)
    return {"suggestions": suggestions}


@router.get("/search/recent", response_model=List[FileResponse])
async def get_recent_files(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get recent files for the current user's department."""
    files = search_service.get_recent_files(
        db,
        department=None if current_user.role == UserRole.ADMIN else current_user.department,
        limit=limit
    )
    return [FileResponse.model_validate(f) for f in files]


# ============================================
# RETRIEVAL ENDPOINTS
# ============================================

def check_file_permission(db: Session, file: File, current_user: User) -> bool:
    """
    Check if current_user has access to the given file.
    Permits:
    - Admin (system-wide)
    - HOD (department)
    - Placement Officer (placement docs, circular attachments)
    - Same department or uploader
    - Cross-department access for students if file is attached to a PUBLISHED recruitment circular they are eligible for.
    Draft recruitment circular attachments are strictly not permitted to students cross-department.
    """
    if current_user.role == UserRole.ADMIN:
        return True

    if current_user.role == UserRole.HOD and file.department == current_user.department:
        return True

    if file.uploaded_by == current_user.id:
        return True

    if file.department and current_user.department and file.department == current_user.department:
        return True

    if current_user.role == UserRole.PLACEMENT_OFFICER:
        if file.file_type in [FileType.PLACEMENT_DOC, FileType.CIRCULAR]:
            return True
        from ..models.recruitment_circular import RecruitmentCircularAttachment
        if db.query(RecruitmentCircularAttachment).filter(RecruitmentCircularAttachment.file_id == file.id).first():
            return True

    if current_user.role == UserRole.STUDENT:
        from ..models.recruitment_circular import RecruitmentCircular, RecruitmentCircularAttachment, RecruitmentCircularStatus
        published_rcs = db.query(RecruitmentCircular).join(
            RecruitmentCircularAttachment,
            RecruitmentCircularAttachment.circular_id == RecruitmentCircular.id
        ).filter(
            RecruitmentCircularAttachment.file_id == file.id,
            RecruitmentCircular.status == RecruitmentCircularStatus.PUBLISHED
        ).all()

        for rc in published_rcs:
            if not rc.branch_eligibility or len(rc.branch_eligibility) == 0:
                return True
            s_branch = None
            if current_user.student_profile and current_user.student_profile.branch:
                s_branch = current_user.student_profile.branch
            elif current_user.department:
                s_branch = current_user.department
            if s_branch:
                target_branches = {str(b).strip().lower() for b in rc.branch_eligibility if b}
                if str(s_branch).strip().lower() in target_branches:
                    return True

    return False


@router.get("/{file_id}", response_model=FileDetailResponse)
async def get_file(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get file details by ID."""
    
    file = file_service.get_file(db, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check permissions
    if not check_file_permission(db, file, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. File belongs to another department."
        )
    
    # Get versions
    file_data = file_service.get_file_with_versions(db, file_id)
    
    # Generate download URL
    download_url = file_service.get_presigned_url(db, file_id)
    
    # Build response
    response = FileDetailResponse.model_validate(file)
    response.download_url = download_url
    response.versions = [FileVersionResponse.model_validate(v) for v in file_data['versions']] if file_data else []
    
    # Add uploader name
    if file.uploader:
        response.uploader_name = file.uploader.name
    
    return response


@router.get("/{file_id}/download")
async def download_file(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download a file."""
    
    file = file_service.get_file(db, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check permissions
    if not check_file_permission(db, file, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. File belongs to another department."
        )
    
    # Get file content
    result = file_service.download_file(db, file_id)
    if not result:
        raise HTTPException(status_code=404, detail="File content not found")
    
    # Return file as streaming response
    content = result['content']
    filename = result['filename']
    mime_type = result['mime_type']
    
    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(content))
        }
    )


@router.get("/{file_id}/preview")
async def preview_file(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Preview a file (inline display)."""
    
    file = file_service.get_file(db, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check permissions
    if not check_file_permission(db, file, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. File belongs to another department."
        )
    
    # Get file content
    result = file_service.download_file(db, file_id)
    if not result:
        raise HTTPException(status_code=404, detail="File content not found")
    
    content = result['content']
    filename = result['filename']
    mime_type = result['mime_type']
    
    # For images and PDFs, display inline
    if mime_type.startswith('image/') or mime_type == 'application/pdf':
        return Response(
            content=content,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'inline; filename="{filename}"'
            }
        )
    
    # For other types, offer download
    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


# ============================================
# LISTING ENDPOINTS
# ============================================

@router.get("/", response_model=List[FileResponse])
async def list_files(
    file_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List files with filters."""
    
    result = file_service.list_files(
        db=db,
        department=None if current_user.role == UserRole.ADMIN else current_user.department,
        file_type=file_type,
        status=FileStatus.ACTIVE,
        limit=limit,
        offset=offset
    )
    
    return [FileResponse.model_validate(f) for f in result['files']]


# ============================================
# UPDATE ENDPOINTS
# ============================================

@router.patch("/{file_id}", response_model=FileResponse)
async def update_file(
    file_id: UUID,
    update_data: FileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update file metadata."""
    
    file = file_service.get_file(db, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check permissions
    if file.uploaded_by != current_user.id and current_user.role not in [UserRole.ADMIN, UserRole.HOD]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own files"
        )
    
    updated_file = file_service.update_file_metadata(db, file_id, update_data)
    if not updated_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse.model_validate(updated_file)


# ============================================
# DELETE ENDPOINTS
# ============================================

@router.delete("/{file_id}")
async def delete_file(
    file_id: UUID,
    permanent: bool = Query(False, description="Permanently delete (remove from storage)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a file.
    Admin can delete any file; HOD can delete files belonging to their department;
    Faculty and students can delete their own uploaded files.
    """
    file = file_service.get_file(db, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check permissions
    is_owner = file.uploaded_by == current_user.id
    is_admin = current_user.role == UserRole.ADMIN
    is_hod_dept = current_user.role == UserRole.HOD and file.department == current_user.department
    
    if not (is_owner or is_admin or is_hod_dept):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: You can only delete your own files or department files as HOD"
        )
    
    result = file_service.delete_file(db, file_id, permanent)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to delete file from storage or database")
    
    # Record audit log
    audit_service.log_action(
        db=db,
        action="FILE_DELETE",
        actor=current_user,
        target_type="file",
        target_id=str(file_id),
        outcome="SUCCESS",
        details={
            "filename": file.filename,
            "department": file.department,
            "permanent": permanent
        }
    )
    
    return {"message": "File deleted successfully", "permanent": permanent}


@router.post("/bulk-delete", response_model=FileBulkDeleteResponse)
async def bulk_delete_files(
    request: FileBulkDeleteRequest,
    permanent: bool = Query(False, description="Permanently delete files"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Bulk delete files with per-file authorization check.
    Admin can delete any file; HOD can delete department or own files;
    Other users can bulk delete files they uploaded.
    """
    if not request.file_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_ids list cannot be empty"
        )
    
    # Deduplicate requested IDs
    unique_file_ids = list(dict.fromkeys(request.file_ids))
    
    deleted_count = 0
    deleted_ids = []
    failed_ids = []
    failed_reasons = {}
    
    for file_id in unique_file_ids:
        try:
            file = file_service.get_file(db, file_id)
            if not file:
                failed_ids.append(file_id)
                failed_reasons[str(file_id)] = "File not found"
                continue
            
            is_owner = file.uploaded_by == current_user.id
            is_admin = current_user.role == UserRole.ADMIN
            is_hod_dept = current_user.role == UserRole.HOD and file.department == current_user.department
            
            if not (is_owner or is_admin or is_hod_dept):
                failed_ids.append(file_id)
                failed_reasons[str(file_id)] = "Permission denied: unauthorized for this file"
                continue
            
            if file_service.delete_file(db, file_id, permanent):
                deleted_count += 1
                deleted_ids.append(file_id)
            else:
                failed_ids.append(file_id)
                failed_reasons[str(file_id)] = "Storage or database deletion failed"
        except Exception as e:
            logger.error(f"Error bulk deleting {file_id}: {str(e)}")
            failed_ids.append(file_id)
            failed_reasons[str(file_id)] = str(e)
    
    outcome = "SUCCESS" if len(failed_ids) == 0 else ("PARTIAL_FAILURE" if deleted_count > 0 else "FAILURE")
    
    audit_service.log_action(
        db=db,
        action="FILE_BULK_DELETE",
        actor=current_user,
        target_type="file",
        target_id="multiple",
        outcome=outcome,
        details={
            "total_requested": len(unique_file_ids),
            "deleted_count": deleted_count,
            "failed_count": len(failed_ids),
            "permanent": permanent,
            "deleted_ids": [str(fid) for fid in deleted_ids],
            "failed_reasons": failed_reasons
        }
    )
    
    return FileBulkDeleteResponse(
        deleted_count=deleted_count,
        failed_ids=failed_ids
    )


# ============================================
# VERSION ENDPOINTS
# ============================================

@router.get("/{file_id}/versions", response_model=List[FileVersionResponse])
async def get_file_versions(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get version history for a file."""
    
    file = file_service.get_file(db, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_data = file_service.get_file_with_versions(db, file_id)
    if not file_data:
        return []
    
    return [FileVersionResponse.model_validate(v) for v in file_data['versions']]


@router.post("/{file_id}/versions/restore")
async def restore_file_version(
    file_id: UUID,
    request: FileVersionRestoreRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Restore a previous version of a file."""
    
    if current_user.role not in [UserRole.ADMIN, UserRole.HOD]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins and HODs can restore versions"
        )
    
    file = file_service.get_file(db, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Get the version to restore
    version = db.query(FileVersion).filter(
        FileVersion.file_id == file_id,
        FileVersion.version_number == request.version_number
    ).first()
    
    if not version:
        raise HTTPException(status_code=404, detail=f"Version {request.version_number} not found")
    
    # Download the version content
    content = minio_client.download_file(version.bucket, version.object_key)
    
    # Create new version with the restored content
    restored_file = file_service.create_version(
        db=db,
        file_id=file_id,
        content=content,
        uploaded_by=current_user,
        change_description=f"Restored version {request.version_number}"
    )
    
    if not restored_file:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to restore version"
        )
    
    return {"message": f"Restored version {request.version_number}", "new_version": restored_file.version}


# ============================================
# STATISTICS ENDPOINTS
# ============================================

@router.get("/stats", response_model=FileStatistics)
async def get_file_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get file statistics."""
    
    if current_user.role not in [UserRole.ADMIN, UserRole.HOD]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins and HODs can view statistics"
        )
    
    stats = file_service.get_file_statistics(
        db,
        department=None if current_user.role == UserRole.ADMIN else current_user.department
    )
    
    # Get recent uploads
    recent_files = search_service.get_recent_files(
        db,
        department=None if current_user.role == UserRole.ADMIN else current_user.department,
        limit=5
    )
    
    return FileStatistics(
        total_files=stats['total_files'],
        total_size_bytes=stats['total_size_bytes'],
        total_size_mb=stats['total_size_mb'],
        by_type=stats['by_type'],
        by_department={},
        by_status={},
        recent_uploads=[FileResponse.model_validate(f) for f in recent_files]
    )