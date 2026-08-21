"""
File Pydantic Schemas

Defines request/response validation for file operations.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


# ============================================
# ENUMS
# ============================================

class FileType(str):
    """File type constants (matches model)."""
    EXAM_DUTY = "exam_duty"
    ASSIGNMENT = "assignment"
    CIRCULAR = "circular"
    RESUME = "resume"
    TIMETABLE = "timetable"
    CERTIFICATE = "certificate"
    PLACEMENT_DOC = "placement_doc"
    OTHER = "other"


class FileStatus(str):
    """File status constants."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


# ============================================
# BASE SCHEMAS
# ============================================

class FileBase(BaseModel):
    """Base file schema with common fields."""
    title: Optional[str] = Field(None, max_length=255, description="File title")
    description: Optional[str] = Field(None, description="File description")
    tags: Optional[List[str]] = Field(default=[], description="File tags")
    department: str = Field(..., max_length=50, description="Department name")
    file_type: str = Field(..., description="File type (exam_duty, assignment, etc.)")
    extra_data: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata")


class FileCreate(FileBase):
    """Schema for creating a new file."""
    filename: str = Field(..., max_length=255, description="Original filename")
    file_size: int = Field(..., gt=0, description="File size in bytes")
    mime_type: str = Field(..., max_length=100, description="MIME type")
    bucket: str = Field(..., max_length=50, description="MinIO bucket name")
    object_key: str = Field(..., max_length=500, description="MinIO object key")
    uploaded_by: Optional[int] = Field(None, description="User ID who uploaded")
    hod_id: Optional[int] = Field(None, description="HOD ID who approved")


class FileUpdate(BaseModel):
    """Schema for updating file metadata."""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    department: Optional[str] = Field(None, max_length=50)
    file_type: Optional[str] = None
    status: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None


# ============================================
# RESPONSE SCHEMAS
# ============================================

class FileVersionResponse(BaseModel):
    """Schema for file version response."""
    id: UUID
    file_id: UUID
    version_number: int
    bucket: str
    object_key: str
    file_size: int
    change_description: Optional[str]
    uploaded_by: Optional[int]
    extra_data: Dict[str, Any] = {}
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class FileResponse(BaseModel):
    """Schema for file response."""
    id: UUID
    filename: str
    file_size: int
    mime_type: str
    bucket: str
    object_key: str
    title: Optional[str]
    description: Optional[str]
    tags: List[str]
    department: str
    file_type: str
    uploaded_by: Optional[int]
    hod_id: Optional[int]
    version: int
    is_latest: bool
    status: str
    extra_data: Dict[str, Any] = {}
    created_at: datetime
    updated_at: Optional[datetime]
    
    # Additional fields from relationships
    uploader_name: Optional[str] = None
    hod_name: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class FileDetailResponse(FileResponse):
    """Detailed file response with versions."""
    versions: List[FileVersionResponse] = []
    download_url: Optional[str] = None
    preview_url: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# ============================================
# SEARCH SCHEMAS
# ============================================

class FileSearchQuery(BaseModel):
    """Schema for file search query."""
    query: str = Field(..., min_length=1, description="Search query text")
    limit: int = Field(10, ge=1, le=100, description="Max results")
    offset: int = Field(0, ge=0, description="Pagination offset")
    
    # Filters
    file_type: Optional[str] = Field(None, description="Filter by file type")
    department: Optional[str] = Field(None, description="Filter by department")
    uploaded_by: Optional[int] = Field(None, description="Filter by uploader (user ID)")
    status: Optional[str] = Field("active", description="Filter by status")
    date_from: Optional[datetime] = Field(None, description="Filter by date from")
    date_to: Optional[datetime] = Field(None, description="Filter by date to")


class FileSearchResult(BaseModel):
    """Schema for individual search result."""
    file_id: UUID
    filename: str
    title: Optional[str]
    description: Optional[str]
    file_type: str
    department: str
    score: float = Field(..., ge=0, le=1, description="Relevance score")
    extra_data: Dict[str, Any] = {}
    created_at: datetime


class FileSearchResponse(BaseModel):
    """Schema for search response."""
    total: int
    results: List[FileSearchResult]
    took_ms: Optional[float] = None


# ============================================
# UPLOAD SCHEMAS
# ============================================

class FileUploadRequest(BaseModel):
    """Schema for file upload request (metadata part)."""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    tags: Optional[List[str]] = Field(default=[])
    department: str = Field(..., max_length=50)
    file_type: str = Field(...)
    extra_data: Optional[Dict[str, Any]] = Field(default={})


class FileUploadResponse(BaseModel):
    """Schema for file upload response."""
    success: bool
    message: str
    file_id: Optional[UUID] = None
    file: Optional[FileResponse] = None


# ============================================
# BULK OPERATIONS
# ============================================

class FileBulkDeleteRequest(BaseModel):
    """Schema for bulk delete request."""
    file_ids: List[UUID] = Field(..., min_length=1, description="List of file IDs to delete")


class FileBulkDeleteResponse(BaseModel):
    """Schema for bulk delete response."""
    deleted_count: int
    failed_ids: List[UUID] = []


class FileBulkMoveRequest(BaseModel):
    """Schema for bulk move request."""
    file_ids: List[UUID] = Field(..., min_length=1)
    target_department: str = Field(..., max_length=50)


# ============================================
# STATISTICS
# ============================================

class FileStatistics(BaseModel):
    """Schema for file statistics."""
    total_files: int
    total_size_bytes: int
    total_size_mb: float
    by_type: Dict[str, int]
    by_department: Dict[str, int]
    by_status: Dict[str, int]
    recent_uploads: List[FileResponse]


class BucketUsage(BaseModel):
    """Schema for MinIO bucket usage."""
    bucket: str
    total_objects: int
    total_size_bytes: int
    total_size_mb: float


# ============================================
# VERSION SCHEMAS
# ============================================

class FileVersionCreate(BaseModel):
    """Schema for creating a new version."""
    file_id: UUID
    version_number: int
    bucket: str
    object_key: str
    file_size: int
    change_description: Optional[str] = None
    uploaded_by: Optional[int] = None
    extra_data: Optional[Dict[str, Any]] = {}


class FileVersionRestoreRequest(BaseModel):
    """Schema for restoring a version."""
    version_number: int = Field(..., description="Version number to restore")