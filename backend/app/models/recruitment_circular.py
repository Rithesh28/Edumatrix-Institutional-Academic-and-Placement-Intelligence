"""
Recruitment Circular Database Models

Provides models for company recruitment drives:
- RecruitmentCircular: Company drive announcement, dates, instructions, eligibility, draft/publish lifecycle
- RecruitmentCircularAttachment: Junction to File model for multiple attachments (posters, JDs, spreadsheets)
- RecruitmentCircularJob: Junction to JobPosting model for linking multiple job opportunities
"""

import enum
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from ..core.database import Base


class RecruitmentCircularStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class AttachmentType(str, enum.Enum):
    POSTER = "poster"
    JOB_DESCRIPTION = "job_description"
    ELIGIBILITY_SHEET = "eligibility_sheet"
    GUIDELINES = "guidelines"
    OTHER = "other"


class RecruitmentCircular(Base):
    """Company recruitment circular model for campus placement drives."""

    __tablename__ = "recruitment_circulars"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)
    instructions = Column(Text, nullable=True)
    application_deadline = Column(DateTime(timezone=True), nullable=True)
    drive_date = Column(DateTime(timezone=True), nullable=True)
    branch_eligibility = Column(JSONB, nullable=True, default=[])  # List of eligible branches
    status = Column(Enum(RecruitmentCircularStatus, name="recruitment_circular_status", create_type=False), default=RecruitmentCircularStatus.DRAFT, nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    company = relationship("Company", lazy="joined")
    creator = relationship("User", foreign_keys=[created_by], lazy="joined")
    attachments = relationship(
        "RecruitmentCircularAttachment",
        back_populates="circular",
        cascade="all, delete-orphan",
        order_by="RecruitmentCircularAttachment.display_order"
    )
    linked_jobs = relationship(
        "RecruitmentCircularJob",
        back_populates="circular",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<RecruitmentCircular {self.id}: {self.title} ({self.status.value})>"


class RecruitmentCircularAttachment(Base):
    """Attachment metadata for recruitment circulars (referencing files table)."""

    __tablename__ = "recruitment_circular_attachments"

    id = Column(Integer, primary_key=True, index=True)
    circular_id = Column(Integer, ForeignKey("recruitment_circulars.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    attachment_type = Column(String(50), nullable=False, default=AttachmentType.OTHER.value)
    display_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    circular = relationship("RecruitmentCircular", back_populates="attachments")
    file = relationship("File", lazy="joined")

    def __repr__(self):
        return f"<RecruitmentCircularAttachment {self.id}: file={self.file_id} type={self.attachment_type}>"


class RecruitmentCircularJob(Base):
    """Junction table linking a recruitment circular to one or more existing JobPostings."""

    __tablename__ = "recruitment_circular_jobs"

    id = Column(Integer, primary_key=True, index=True)
    circular_id = Column(Integer, ForeignKey("recruitment_circulars.id", ondelete="CASCADE"), nullable=False, index=True)
    job_posting_id = Column(Integer, ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("circular_id", "job_posting_id", name="uq_recruitment_circular_job"),
    )

    # Relationships
    circular = relationship("RecruitmentCircular", back_populates="linked_jobs")
    job_posting = relationship("JobPosting", lazy="joined")

    def __repr__(self):
        return f"<RecruitmentCircularJob {self.id}: circular={self.circular_id} job={self.job_posting_id}>"
