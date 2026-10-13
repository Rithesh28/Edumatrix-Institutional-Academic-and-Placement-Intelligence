"""
Study Buddy Pydantic Schemas

Data transfer and validation schemas for Subjects, Syllabus Documents,
Units, and Topics.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from ..models.study_buddy import SyllabusProcessingStatus, SyllabusReviewStatus


# ============================================
# SUBJECT SCHEMAS
# ============================================

class SubjectBase(BaseModel):
    code: str = Field(..., max_length=50, description="Unique subject/course code (e.g., CS601)")
    name: str = Field(..., max_length=255, description="Full subject name")
    department: str = Field(..., max_length=100, description="Department name (e.g., CSE)")
    semester: Optional[int] = Field(None, ge=1, le=8, description="Semester (1-8)")
    academic_year: Optional[str] = Field(None, max_length=50, description="Academic year (e.g., 2025-2026)")
    curriculum_version: Optional[str] = Field(None, max_length=50, description="Curriculum version (e.g., R2021)")
    description: Optional[str] = None
    is_active: bool = True


class SubjectCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=255)
    department: Optional[str] = Field(None, max_length=100)
    semester: Optional[int] = Field(None, ge=1, le=8)
    academic_year: Optional[str] = Field(None, max_length=50)
    curriculum_version: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None


class SubjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    semester: Optional[int] = Field(None, ge=1, le=8)
    academic_year: Optional[str] = Field(None, max_length=50)
    curriculum_version: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class SubjectResponse(BaseModel):
    id: int
    code: str
    name: str
    department: str
    semester: Optional[int] = None
    academic_year: Optional[str] = None
    curriculum_version: Optional[str] = None
    description: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    syllabus_documents_count: Optional[int] = 0
    published_document_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================
# SYLLABUS TOPIC & UNIT SCHEMAS
# ============================================

class SyllabusTopicResponse(BaseModel):
    id: int
    unit_id: int
    title: str
    order: int
    extracted_text: Optional[str] = None
    source_page: Optional[int] = None
    source_evidence: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SyllabusUnitResponse(BaseModel):
    id: int
    document_id: int
    unit_number: Optional[int] = None
    title: str
    order: int
    description: Optional[str] = None
    source_page_start: Optional[int] = None
    source_page_end: Optional[int] = None
    source_evidence: Optional[str] = None
    topics: List[SyllabusTopicResponse] = []
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================
# SYLLABUS DOCUMENT SCHEMAS
# ============================================

class SyllabusDocumentResponse(BaseModel):
    id: int
    subject_id: int
    file_id: Optional[UUID] = None
    version: int
    is_latest: bool
    title: str
    original_filename: str
    file_size: int
    mime_type: str
    uploaded_by_id: Optional[int] = None
    processing_status: SyllabusProcessingStatus
    review_status: SyllabusReviewStatus
    is_published: bool
    published_at: Optional[datetime] = None
    published_by_id: Optional[int] = None
    extraction_error: Optional[str] = None
    units_count: Optional[int] = 0
    topics_count: Optional[int] = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SyllabusDocumentDetailResponse(SyllabusDocumentResponse):
    extracted_text: Optional[str] = None
    extraction_metadata: Optional[Dict[str, Any]] = None
    units: List[SyllabusUnitResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ============================================
# WORKFLOW ACTION SCHEMAS
# ============================================

class SyllabusReviewRequest(BaseModel):
    review_status: SyllabusReviewStatus = Field(..., description="Target review status: APPROVED, REJECTED, or DRAFT")
    review_notes: Optional[str] = Field(None, max_length=1000)


class SyllabusPublishRequest(BaseModel):
    is_published: bool = Field(..., description="True to publish to students, False to unpublish")
