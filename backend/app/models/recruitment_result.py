"""
Recruitment Result Database Models

Provides models for recruitment result uploads, tabular extraction,
candidate identity matching, and officer confirmation workflows.
"""

import enum
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey, Enum, UniqueConstraint, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from ..core.database import Base


class RecruitmentResultBatchStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    IN_REVIEW = "in_review"
    PARTIALLY_CONFIRMED = "partially_confirmed"
    FULLY_CONFIRMED = "fully_confirmed"
    ARCHIVED = "archived"


class RecruitmentResultReviewState(str, enum.Enum):
    PENDING = "pending"
    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"
    CONFIRMED = "confirmed"
    IGNORED = "ignored"


class RecruitmentResultItemStatus(str, enum.Enum):
    SHORTLISTED = "shortlisted"
    SELECTED = "selected"
    REJECTED = "rejected"
    ABSENT = "absent"
    ON_HOLD = "on_hold"


class RecruitmentResultBatch(Base):
    """
    Tracks an uploaded recruitment result batch (spreadsheet, PDF table, or document).
    Retains source file reference, company/job drive provenance, round metadata, and review progress.
    """

    __tablename__ = "recruitment_result_batches"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    job_posting_id = Column(Integer, ForeignKey("job_postings.id", ondelete="SET NULL"), nullable=True, index=True)
    circular_id = Column(Integer, ForeignKey("recruitment_circulars.id", ondelete="SET NULL"), nullable=True, index=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="RESTRICT"), nullable=False, index=True)
    round_name = Column(String(100), nullable=False)
    round_type = Column(String(50), nullable=False, default="assessment")
    is_final_round = Column(Boolean, default=False, nullable=False)
    status = Column(
        Enum(RecruitmentResultBatchStatus, name="recruitment_result_batch_status", create_type=False),
        default=RecruitmentResultBatchStatus.IN_REVIEW,
        nullable=False,
        index=True
    )
    total_rows = Column(Integer, default=0, nullable=False)
    matched_count = Column(Integer, default=0, nullable=False)
    ambiguous_count = Column(Integer, default=0, nullable=False)
    confirmed_count = Column(Integer, default=0, nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    company = relationship("Company", lazy="joined")
    job_posting = relationship("JobPosting", lazy="joined")
    circular = relationship("RecruitmentCircular", lazy="joined")
    file = relationship("File", lazy="joined")
    uploader = relationship("User", foreign_keys=[uploaded_by], lazy="joined")
    items = relationship(
        "RecruitmentResultItem",
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="RecruitmentResultItem.row_index"
    )

    def __repr__(self):
        return f"<RecruitmentResultBatch {self.id}: {self.round_name} (company={self.company_id}, status={self.status.value})>"


class RecruitmentResultItem(Base):
    """
    Individual extracted candidate result row from an uploaded batch.
    Stores raw row JSONB, extracted fields, identity match confidence & evidence,
    and review/confirmation state.
    """

    __tablename__ = "recruitment_result_items"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("recruitment_result_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    row_index = Column(Integer, nullable=False)
    source_page = Column(Integer, nullable=True)
    raw_data = Column(JSONB, nullable=False, default=dict)
    extracted_usn = Column(String(50), nullable=True, index=True)
    extracted_name = Column(String(255), nullable=True)
    extracted_email = Column(String(255), nullable=True, index=True)
    extracted_status_raw = Column(String(100), nullable=True)
    extracted_remarks = Column(Text, nullable=True)
    normalized_status = Column(
        Enum(RecruitmentResultItemStatus, name="recruitment_result_item_status", create_type=False),
        default=RecruitmentResultItemStatus.SHORTLISTED,
        nullable=False
    )
    matched_student_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    match_confidence = Column(Float, default=0.0, nullable=False)
    match_method = Column(String(50), nullable=True)
    match_evidence = Column(JSONB, nullable=True)
    review_status = Column(
        Enum(RecruitmentResultReviewState, name="recruitment_result_review_state", create_type=False),
        default=RecruitmentResultReviewState.PENDING,
        nullable=False,
        index=True
    )
    confirmed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    notification_sent = Column(Boolean, default=False, nullable=False)
    notification_event_key = Column(String(255), unique=True, nullable=True, index=True)

    # Relationships
    batch = relationship("RecruitmentResultBatch", back_populates="items")
    matched_student = relationship("User", foreign_keys=[matched_student_id], lazy="joined")
    confirmer = relationship("User", foreign_keys=[confirmed_by], lazy="joined")

    __table_args__ = (
        Index("idx_result_items_batch_review", "batch_id", "review_status"),
    )

    def __repr__(self):
        return f"<RecruitmentResultItem {self.id}: batch={self.batch_id} row={self.row_index} student={self.matched_student_id} ({self.review_status.value})>"
