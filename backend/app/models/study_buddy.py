"""
Study Buddy Database Models

Persistent models for academic subjects, syllabus documents,
units, and topics supporting versioning, review workflows,
provenance tracking, and multi-role institutional access.
"""

import enum
from sqlalchemy import (
    Column,
    Integer,
    Float,
    String,
    Text,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Enum,
    UniqueConstraint,
    Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, JSONB

from ..core.database import Base


class SyllabusProcessingStatus(str, enum.Enum):
    """Status of syllabus document text extraction and parsing."""
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    EXTRACTED = "EXTRACTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    FAILED = "FAILED"


class SyllabusReviewStatus(str, enum.Enum):
    """Institutional review and approval state for syllabus documents."""
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Subject(Base):
    """
    Academic subject / course entity.
    Scoped by department and optionally semester and curriculum version.
    """
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    department = Column(String(100), nullable=False, index=True)
    semester = Column(Integer, nullable=True)
    academic_year = Column(String(50), nullable=True)
    curriculum_version = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    syllabus_documents = relationship(
        "SyllabusDocument",
        back_populates="subject",
        cascade="all, delete-orphan",
        order_by="desc(SyllabusDocument.version)"
    )
    lecture_notes = relationship(
        "LectureNote",
        back_populates="subject",
        cascade="all, delete-orphan",
        order_by="desc(LectureNote.created_at)"
    )

    __table_args__ = (
        UniqueConstraint(
            "code",
            "department",
            "curriculum_version",
            name="uq_subject_code_dept_version"
        ),
        Index("ix_subjects_dept_active", "department", "is_active"),
    )

    def __repr__(self):
        return f"<Subject {self.code} - {self.name} ({self.department})>"


class SyllabusDocument(Base):
    """
    Syllabus document metadata, extraction outputs, and lifecycle state.
    Preserves multiple versions without overwriting historical documents.
    """
    __tablename__ = "syllabus_documents"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"), nullable=True, index=True)

    version = Column(Integer, default=1, nullable=False)
    is_latest = Column(Boolean, default=True, nullable=False, index=True)

    title = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)

    # MinIO Storage references
    minio_bucket = Column(String(100), nullable=False)
    minio_object_key = Column(String(500), nullable=False, unique=True)

    # Ownership & Review
    uploaded_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    processing_status = Column(
        Enum(SyllabusProcessingStatus, name="syllabus_processing_status"),
        default=SyllabusProcessingStatus.UPLOADED,
        nullable=False,
        index=True
    )
    review_status = Column(
        Enum(SyllabusReviewStatus, name="syllabus_review_status"),
        default=SyllabusReviewStatus.DRAFT,
        nullable=False,
        index=True
    )

    is_published = Column(Boolean, default=False, nullable=False, index=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    published_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Content & Provenance
    extracted_text = Column(Text, nullable=True)
    extraction_error = Column(Text, nullable=True)
    extraction_metadata = Column(JSONB, nullable=True, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    subject = relationship("Subject", back_populates="syllabus_documents")
    file = relationship("File", foreign_keys=[file_id])
    uploader = relationship("User", foreign_keys=[uploaded_by_id])
    publisher = relationship("User", foreign_keys=[published_by_id])
    units = relationship(
        "SyllabusUnit",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="SyllabusUnit.order"
    )

    __table_args__ = (
        UniqueConstraint("subject_id", "version", name="uq_syllabus_subject_version"),
        Index("ix_syllabus_subject_latest", "subject_id", "is_latest"),
        Index("ix_syllabus_published_state", "is_published", "review_status"),
    )

    def __repr__(self):
        return f"<SyllabusDocument id={self.id} subject_id={self.subject_id} v={self.version} status={self.processing_status}>"


class SyllabusUnit(Base):
    """
    A segmented unit or module of a syllabus document.
    """
    __tablename__ = "syllabus_units"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("syllabus_documents.id", ondelete="CASCADE"), nullable=False, index=True)

    unit_number = Column(Integer, nullable=True)
    title = Column(String(255), nullable=False)
    order = Column(Integer, nullable=False, default=1)
    description = Column(Text, nullable=True)

    source_page_start = Column(Integer, nullable=True)
    source_page_end = Column(Integer, nullable=True)
    source_evidence = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    document = relationship("SyllabusDocument", back_populates="units")
    topics = relationship(
        "SyllabusTopic",
        back_populates="unit",
        cascade="all, delete-orphan",
        order_by="SyllabusTopic.order"
    )

    __table_args__ = (
        UniqueConstraint("document_id", "order", name="uq_syllabus_unit_order"),
        Index("ix_syllabus_unit_doc_order", "document_id", "order"),
    )

    def __repr__(self):
        return f"<SyllabusUnit id={self.id} doc={self.document_id} order={self.order} title={self.title}>"


class SyllabusTopic(Base):
    """
    A specific topic within a syllabus unit.
    """
    __tablename__ = "syllabus_topics"

    id = Column(Integer, primary_key=True, index=True)
    unit_id = Column(Integer, ForeignKey("syllabus_units.id", ondelete="CASCADE"), nullable=False, index=True)

    title = Column(String(255), nullable=False)
    order = Column(Integer, nullable=False, default=1)
    extracted_text = Column(Text, nullable=True)

    source_page = Column(Integer, nullable=True)
    source_evidence = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    unit = relationship("SyllabusUnit", back_populates="topics")

    __table_args__ = (
        UniqueConstraint("unit_id", "order", name="uq_syllabus_topic_order"),
        Index("ix_syllabus_topic_unit_order", "unit_id", "order"),
    )

    def __repr__(self):
        return f"<SyllabusTopic id={self.id} unit={self.unit_id} order={self.order} title={self.title}>"


class QuizStatus(str, enum.Enum):
    """Lifecycle status for a syllabus-grounded quiz attempt."""
    GENERATED = "GENERATED"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"


class StudyBuddyQuizAttempt(Base):
    """
    Persisted quiz attempt and result tracking for students.
    Stores question snapshots with hidden answer keys, student answers,
    scoring metrics, syllabus provenance, and submission timestamps.
    """
    __tablename__ = "study_buddy_quiz_attempts"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    syllabus_document_id = Column(Integer, ForeignKey("syllabus_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    syllabus_version = Column(Integer, nullable=False)
    unit_id = Column(Integer, ForeignKey("syllabus_units.id", ondelete="SET NULL"), nullable=True, index=True)
    topic_id = Column(Integer, ForeignKey("syllabus_topics.id", ondelete="SET NULL"), nullable=True, index=True)

    title = Column(String(255), nullable=False)
    difficulty = Column(String(50), nullable=False, default="medium")
    total_questions = Column(Integer, nullable=False)
    questions_data = Column(JSONB, nullable=False)

    status = Column(Enum(QuizStatus, name="study_buddy_quiz_status"), default=QuizStatus.GENERATED, nullable=False, index=True)

    # Submission & grading results
    score = Column(Float, nullable=True)
    max_score = Column(Integer, nullable=True)
    percentage = Column(Float, nullable=True)
    student_answers = Column(JSONB, nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    student = relationship("User")
    subject = relationship("Subject")
    syllabus_document = relationship("SyllabusDocument")
    unit = relationship("SyllabusUnit")
    topic = relationship("SyllabusTopic")

    __table_args__ = (
        Index("ix_quiz_attempts_student_subject", "student_id", "subject_id"),
        Index("ix_quiz_attempts_student_status", "student_id", "status"),
    )

    def __repr__(self):
        return f"<StudyBuddyQuizAttempt id={self.id} student={self.student_id} subject={self.subject_id} status={self.status}>"


class PlanStatus(str, enum.Enum):
    """Lifecycle status for a study plan."""
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class StudyBuddyPlan(Base):
    """
    Persistent adaptive study plan for a student covering a subject
    and grounded in an approved syllabus document version.
    """
    __tablename__ = "study_buddy_plans"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    syllabus_document_id = Column(Integer, ForeignKey("syllabus_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    syllabus_version = Column(Integer, nullable=False)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    target_date = Column(Date, nullable=True)
    daily_budget_minutes = Column(Integer, nullable=False, default=60)
    status = Column(Enum(PlanStatus, name="study_buddy_plan_status"), default=PlanStatus.ACTIVE, nullable=False, index=True)

    total_tasks = Column(Integer, default=0, nullable=False)
    completed_tasks = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    student = relationship("User")
    subject = relationship("Subject")
    syllabus_document = relationship("SyllabusDocument")
    tasks = relationship("StudyBuddyPlanTask", back_populates="plan", cascade="all, delete-orphan", order_by="StudyBuddyPlanTask.order")

    __table_args__ = (
        Index("ix_study_buddy_plans_student_status", "student_id", "status"),
        Index("ix_study_buddy_plans_student_subject", "student_id", "subject_id"),
    )

    def __repr__(self):
        return f"<StudyBuddyPlan id={self.id} student={self.student_id} subject={self.subject_id} status={self.status}>"


class StudyBuddyPlanTask(Base):
    """
    Individual syllabus-grounded learning task within an adaptive study plan.
    Maintains provenance to syllabus document, version, unit, and topic.
    """
    __tablename__ = "study_buddy_plan_tasks"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("study_buddy_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    order = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    unit_id = Column(Integer, ForeignKey("syllabus_units.id", ondelete="SET NULL"), nullable=True, index=True)
    topic_id = Column(Integer, ForeignKey("syllabus_topics.id", ondelete="SET NULL"), nullable=True, index=True)
    syllabus_document_id = Column(Integer, ForeignKey("syllabus_documents.id", ondelete="CASCADE"), nullable=False)
    syllabus_version = Column(Integer, nullable=False)

    estimated_duration_minutes = Column(Integer, nullable=False, default=30)
    scheduled_date = Column(Date, nullable=True)
    priority = Column(String(50), nullable=False, default="medium")
    recommendation_reason = Column(String(500), nullable=True)
    task_type = Column(String(50), nullable=False, default="concept_study")

    is_completed = Column(Boolean, default=False, nullable=False, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    plan = relationship("StudyBuddyPlan", back_populates="tasks")
    unit = relationship("SyllabusUnit")
    topic = relationship("SyllabusTopic")

    __table_args__ = (
        Index("ix_study_buddy_plan_tasks_plan_order", "plan_id", "order"),
    )

    def __repr__(self):
        return f"<StudyBuddyPlanTask id={self.id} plan={self.plan_id} order={self.order} completed={self.is_completed}>"


class LectureNoteStatus(str, enum.Enum):
    """Lifecycle status for a lecture note."""
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class LectureNoteProcessingStatus(str, enum.Enum):
    """Extraction processing status for a lecture note."""
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    EXTRACTED = "EXTRACTED"
    FAILED = "FAILED"


class LectureNoteIndexingStatus(str, enum.Enum):
    """Qdrant RAG vector indexing status for a lecture note."""
    NOT_INDEXED = "NOT_INDEXED"
    INDEXING = "INDEXING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


class LectureNote(Base):
    """
    Lecture note uploaded by faculty for an academic subject.
    Optionally associated with a syllabus unit/topic.
    Maintains independent lifecycle and RAG vector indexing state
    without affecting official syllabus versioning or publication.
    """
    __tablename__ = "study_buddy_lecture_notes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    uploaded_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"), nullable=True, index=True)

    # Optional syllabus alignment
    unit_id = Column(Integer, ForeignKey("syllabus_units.id", ondelete="SET NULL"), nullable=True, index=True)
    topic_id = Column(Integer, ForeignKey("syllabus_topics.id", ondelete="SET NULL"), nullable=True, index=True)

    # Note Content & Storage coordinates
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    original_filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)

    minio_bucket = Column(String(100), nullable=False, default="lecture-notes")
    minio_object_key = Column(String(500), nullable=False, unique=True)

    # Lifecycle status
    status = Column(
        Enum(LectureNoteStatus, name="study_buddy_lecture_note_status"),
        default=LectureNoteStatus.DRAFT,
        nullable=False,
        index=True
    )
    is_published = Column(Boolean, default=False, nullable=False, index=True)
    published_at = Column(DateTime(timezone=True), nullable=True)

    # Text extraction status
    processing_status = Column(
        Enum(LectureNoteProcessingStatus, name="study_buddy_lecture_note_processing_status"),
        default=LectureNoteProcessingStatus.UPLOADED,
        nullable=False,
        index=True
    )
    extracted_text = Column(Text, nullable=True)
    extraction_error = Column(Text, nullable=True)
    extraction_metadata = Column(JSONB, nullable=True, default=dict)

    # Vector indexing status
    indexing_status = Column(
        Enum(LectureNoteIndexingStatus, name="study_buddy_lecture_note_indexing_status"),
        default=LectureNoteIndexingStatus.NOT_INDEXED,
        nullable=False,
        index=True
    )
    indexed_chunk_count = Column(Integer, default=0, nullable=False)

    # Usage metrics
    download_count = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    subject = relationship("Subject", back_populates="lecture_notes")
    uploader = relationship("User", foreign_keys=[uploaded_by_id])
    file = relationship("File", foreign_keys=[file_id])
    unit = relationship("SyllabusUnit")
    topic = relationship("SyllabusTopic")

    __table_args__ = (
        Index("ix_study_buddy_lecture_notes_subject_status", "subject_id", "status"),
        Index("ix_study_buddy_lecture_notes_subject_published", "subject_id", "is_published"),
    )

    def __repr__(self):
        return f"<LectureNote id={self.id} subject_id={self.subject_id} title={self.title} status={self.status}>"


