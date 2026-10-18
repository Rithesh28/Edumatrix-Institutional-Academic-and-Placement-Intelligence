"""
Study Buddy Pydantic Schemas

Data transfer and validation schemas for Subjects, Syllabus Documents,
Units, and Topics.
"""

import enum
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from ..models.study_buddy import (
    SyllabusProcessingStatus,
    SyllabusReviewStatus,
    LectureNoteStatus,
    LectureNoteProcessingStatus,
    LectureNoteIndexingStatus,
    StudentDocProcessingStatus,
    StudentDocIndexingStatus,
)


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
    code: Optional[str] = Field(None, min_length=2, max_length=50)
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    department: Optional[str] = Field(None, max_length=100)
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
    lecture_notes_count: Optional[int] = 0
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


# ============================================
# STUDY BUDDY RAG CHAT SCHEMAS
# ============================================

class StudyBuddySourceMode(str, enum.Enum):
    SYLLABUS = "syllabus"
    LECTURE_NOTES = "lecture_notes"
    ALL = "all"
    MY_DOCUMENTS = "my_documents"
    ALL_MY_SOURCES = "all_my_sources"


class StudyBuddyQuestionRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000, description="Student academic query")
    subject_id: Optional[int] = Field(None, description="Optional subject ID to focus the query")
    source_mode: Optional[StudyBuddySourceMode] = Field(
        default=StudyBuddySourceMode.SYLLABUS,
        description="Source mode: 'syllabus', 'lecture_notes', 'all', 'my_documents', or 'all_my_sources'"
    )
    attached_document_id: Optional[int] = Field(
        default=None,
        description="Optional student study document ID attached to this specific query"
    )


class StudyBuddyCitation(BaseModel):
    source_type: str = "syllabus"  # "syllabus", "lecture_note", or "student_upload"
    source_id: Optional[int] = None
    source_title: Optional[str] = None
    original_filename: Optional[str] = None
    document_id: Optional[int] = None
    version: Optional[int] = None
    lecture_note_id: Optional[int] = None
    student_study_document_id: Optional[int] = None
    is_attached_file: Optional[bool] = False
    subject_id: Optional[int] = None
    subject_code: Optional[str] = None
    subject_name: Optional[str] = None
    department: Optional[str] = None
    unit_number: Optional[int] = None
    unit_title: Optional[str] = None
    topic_title: Optional[str] = None
    source_page: Optional[int] = None
    source_evidence: Optional[str] = None
    chunk_order: Optional[int] = None
    relevance_score: float

    model_config = ConfigDict(from_attributes=True)


class StudyBuddyAnswerResponse(BaseModel):
    answer: str
    has_sufficient_evidence: bool
    citations: List[StudyBuddyCitation] = []
    subject_id: Optional[int] = None
    model_used: str
    latency_ms: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================
# STUDY BUDDY SUMMARY SCHEMAS
# ============================================

class StudyBuddySummaryRequest(BaseModel):
    subject_id: int = Field(..., description="Target academic subject ID")
    unit_id: Optional[int] = Field(None, description="Optional unit ID to scope summary")
    topic_id: Optional[int] = Field(None, description="Optional topic ID to scope summary")
    format_type: str = Field("concise", pattern="^(concise|detailed)$", description="Format: concise revision notes or detailed explanation")


class StudyBuddySummaryResponse(BaseModel):
    title: str
    summary: str
    format_type: str
    has_sufficient_evidence: bool
    citations: List[StudyBuddyCitation] = []
    subject_id: int
    subject_code: str
    subject_name: str
    unit_id: Optional[int] = None
    topic_id: Optional[int] = None
    model_used: str
    latency_ms: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================
# STUDY BUDDY QUIZ SCHEMAS
# ============================================

class StudyBuddyQuizCreateRequest(BaseModel):
    subject_id: int = Field(..., description="Target academic subject ID")
    unit_id: Optional[int] = Field(None, description="Optional unit ID to scope quiz")
    topic_id: Optional[int] = Field(None, description="Optional topic ID to scope quiz")
    num_questions: int = Field(5, ge=3, le=10, description="Requested number of questions (3-10)")
    difficulty: str = Field("medium", pattern="^(easy|medium|hard)$", description="Quiz difficulty level")


class QuizQuestionPublicResponse(BaseModel):
    question_id: int
    question: str
    options: List[str]


class StudyBuddyQuizPublicResponse(BaseModel):
    id: int
    subject_id: int
    subject_code: str
    subject_name: str
    syllabus_version: int
    unit_id: Optional[int] = None
    topic_id: Optional[int] = None
    title: str
    difficulty: str
    total_questions: int
    questions: List[QuizQuestionPublicResponse]
    status: str
    created_at: datetime
    model_used: str
    shortfall_note: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class StudyBuddyQuizSubmitRequest(BaseModel):
    answers: Dict[str, int] = Field(..., description="Mapping of question_id (as str) to selected option index (0-3)")


class QuizQuestionResultResponse(BaseModel):
    question_id: int
    question: str
    options: List[str]
    selected_option_index: Optional[int] = None
    correct_option_index: int
    is_correct: bool
    explanation: str
    citation: Optional[StudyBuddyCitation] = None


class StudyBuddyQuizResultResponse(BaseModel):
    id: int
    student_id: int
    subject_id: int
    subject_code: str
    subject_name: str
    syllabus_version: int
    unit_id: Optional[int] = None
    topic_id: Optional[int] = None
    title: str
    difficulty: str
    status: str
    score: float
    max_score: int
    percentage: float
    submitted_at: Optional[datetime] = None
    questions_results: List[QuizQuestionResultResponse] = []

    model_config = ConfigDict(from_attributes=True)


class StudyBuddyQuizAttemptSummaryResponse(BaseModel):
    id: int
    subject_id: int
    subject_code: str
    subject_name: str
    syllabus_version: int
    title: str
    difficulty: str
    status: str
    score: Optional[float] = None
    max_score: Optional[int] = None
    percentage: Optional[float] = None
    total_questions: int
    created_at: datetime
    submitted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================
# PROGRESS DASHBOARD & ADAPTIVE PLANNER SCHEMAS
# ============================================

class SubjectPerformanceSummary(BaseModel):
    subject_id: int
    subject_code: str
    subject_name: str
    quizzes_attempted: int
    quizzes_completed: int
    average_score: Optional[float] = None
    average_percentage: Optional[float] = None
    latest_quiz_date: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class WeakTopicSummary(BaseModel):
    subject_id: int
    subject_code: str
    subject_name: str
    unit_id: Optional[int] = None
    unit_title: Optional[str] = None
    topic_id: Optional[int] = None
    topic_title: Optional[str] = None
    attempts_evaluated: int
    questions_evaluated: int
    accuracy_percentage: float
    reason: str
    has_sufficient_evidence: bool = True

    model_config = ConfigDict(from_attributes=True)


class ActivityHistoryItem(BaseModel):
    date: str  # YYYY-MM-DD
    count: int
    average_percentage: Optional[float] = None


class ActivePlanSummary(BaseModel):
    plan_id: int
    title: str
    subject_id: int
    subject_code: str
    subject_name: str
    status: str
    target_date: Optional[date] = None
    daily_budget_minutes: int
    total_tasks: int
    completed_tasks: int
    progress_percentage: float

    model_config = ConfigDict(from_attributes=True)


class StudentProgressDashboardResponse(BaseModel):
    quizzes_attempted: int
    quizzes_completed: int
    average_percentage: Optional[float] = None
    most_recent_quiz: Optional[StudyBuddyQuizAttemptSummaryResponse] = None
    subject_performances: List[SubjectPerformanceSummary] = []
    recent_attempts: List[StudyBuddyQuizAttemptSummaryResponse] = []
    activity_history: List[ActivityHistoryItem] = []
    weak_topics: List[WeakTopicSummary] = []
    active_plan: Optional[ActivePlanSummary] = None
    plan_task_stats: Dict[str, int] = Field(
        default_factory=lambda: {"total": 0, "completed": 0, "pending": 0}
    )
    metric_rules: Dict[str, str] = Field(
        default_factory=lambda: {
            "average_percentage": "Calculated as the unweighted mean percentage across all COMPLETED quiz attempts. Excludes abandoned or unsubmitted quizzes. Null if no quizzes completed.",
            "weak_topics": "Identified strictly when a student has answered at least 2 questions or completed 2 quizzes covering a specific unit/topic with an accuracy rate below 60%. Single quiz results are never used to claim weakness or mastery.",
            "unpracticed_topics": "Syllabus units or topics present in published curriculum where no quiz attempts have been recorded yet."
        }
    )

    model_config = ConfigDict(from_attributes=True)


class StudyBuddyPlanTaskResponse(BaseModel):
    id: int
    plan_id: int
    order: int
    title: str
    description: Optional[str] = None
    unit_id: Optional[int] = None
    unit_title: Optional[str] = None
    topic_id: Optional[int] = None
    topic_title: Optional[str] = None
    syllabus_document_id: int
    syllabus_version: int
    estimated_duration_minutes: int
    scheduled_date: Optional[date] = None
    priority: str
    recommendation_reason: Optional[str] = None
    task_type: str
    is_completed: bool
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class StudyBuddyPlanResponse(BaseModel):
    id: int
    student_id: int
    subject_id: int
    subject_code: str
    subject_name: str
    syllabus_document_id: int
    syllabus_version: int
    title: str
    description: Optional[str] = None
    target_date: Optional[date] = None
    daily_budget_minutes: int
    status: str
    total_tasks: int
    completed_tasks: int
    progress_percentage: float
    tasks: List[StudyBuddyPlanTaskResponse] = []
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class StudyBuddyPlanCreateRequest(BaseModel):
    subject_id: int = Field(..., description="Target academic subject ID")
    unit_ids: Optional[List[int]] = Field(None, description="Optional unit IDs to focus the study plan on")
    target_date: Optional[date] = Field(None, description="Optional target completion date (must be today or in future)")
    daily_budget_minutes: int = Field(60, ge=15, le=480, description="Daily study time budget in minutes (15 - 480)")
    title: Optional[str] = Field(None, max_length=255, description="Custom title for the study plan")


class StudyBuddyPlanUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    target_date: Optional[date] = None
    daily_budget_minutes: Optional[int] = Field(None, ge=15, le=480)
    status: Optional[str] = Field(None, pattern="^(ACTIVE|COMPLETED|ARCHIVED)$")


class StudyBuddyTaskStatusUpdateRequest(BaseModel):
    is_completed: bool = Field(..., description="Set true to mark completed, false to reopen")


# ============================================
# LECTURE NOTE SCHEMAS
# ============================================

class LectureNoteResponse(BaseModel):
    id: int
    subject_id: int
    uploaded_by_id: Optional[int] = None
    file_id: Optional[UUID] = None
    unit_id: Optional[int] = None
    topic_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    original_filename: str
    file_size: int
    mime_type: str
    status: LectureNoteStatus
    is_published: bool
    published_at: Optional[datetime] = None
    processing_status: LectureNoteProcessingStatus
    indexing_status: LectureNoteIndexingStatus
    indexed_chunk_count: int = 0
    download_count: int = 0
    extraction_error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class LectureNoteDetailResponse(LectureNoteResponse):
    subject_name: Optional[str] = None
    subject_code: Optional[str] = None
    uploader_name: Optional[str] = None
    unit_title: Optional[str] = None
    topic_title: Optional[str] = None
    extraction_metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class LectureNoteUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    unit_id: Optional[int] = None
    topic_id: Optional[int] = None
    status: Optional[LectureNoteStatus] = None
    is_published: Optional[bool] = None


class LectureNoteListResponse(BaseModel):
    items: List[LectureNoteResponse]
    total: int
    skip: int
    limit: int


# ============================================
# STUDENT STUDY DOCUMENT SCHEMAS
# ============================================

class StudentStudyDocumentResponse(BaseModel):
    id: int
    student_id: int
    subject_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    original_filename: str
    file_size: int
    mime_type: str
    content_hash: str
    is_active: bool
    processing_status: StudentDocProcessingStatus
    indexing_status: StudentDocIndexingStatus
    indexed_chunk_count: int = 0
    extraction_error: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class StudentStudyDocumentDetailResponse(StudentStudyDocumentResponse):
    subject_name: Optional[str] = None
    subject_code: Optional[str] = None
    subject_department: Optional[str] = None
    extraction_metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class StudentStudyDocumentUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class StudentStudyDocumentListResponse(BaseModel):
    items: List[StudentStudyDocumentResponse]
    total: int
    skip: int
    limit: int



