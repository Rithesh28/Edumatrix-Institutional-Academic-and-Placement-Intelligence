"""
Recruitment Round, Student Round Outcome, and Placement Offer Models

Provides database models for:
- RecruitmentRound: Defined recruitment stages for a JobPosting (OA, Tech, HR, Final Offer)
- StudentRoundOutcome: Confirmed candidate progression outcome in a specific recruitment round
- PlacementOffer: Confirmed placement offer extended to a student with CTC, designation, and acceptance tracking
"""

import enum
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    Float,
    DateTime,
    ForeignKey,
    Enum,
    UniqueConstraint,
    CheckConstraint,
    Index,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from ..core.database import Base


# =============================================================================
# ENUMS
# =============================================================================

class RoundOutcome(str, enum.Enum):
    """Authoritative outcome of a student in a specific recruitment round."""
    CLEARED = "cleared"
    REJECTED = "rejected"
    ABSENT = "absent"
    ON_HOLD = "on_hold"
    OFFERED = "offered"


class OfferAcceptanceStatus(str, enum.Enum):
    """Institutional placement offer acceptance status."""
    OFFERED = "offered"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    RESCINDED = "rescinded"


# =============================================================================
# RECRUITMENT ROUND MODEL
# =============================================================================

class RecruitmentRound(Base):
    """
    Represents one defined recruitment stage for a specific job posting.
    Ordered sequentially by round_number (e.g. 1: Resume Screen, 2: OA, 3: Tech, 4: HR & Offer).
    """

    __tablename__ = "recruitment_rounds"

    id = Column(Integer, primary_key=True, index=True)
    job_posting_id = Column(Integer, ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, index=True)
    round_number = Column(Integer, nullable=False)
    name = Column(String(100), nullable=False)
    round_type = Column(String(50), nullable=False, default="assessment")
    is_final = Column(Boolean, default=False, nullable=False)
    round_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    job_posting = relationship("JobPosting", back_populates="rounds", lazy="joined")
    student_outcomes = relationship(
        "StudentRoundOutcome",
        back_populates="round",
        cascade="all, delete-orphan",
        order_by="StudentRoundOutcome.id"
    )
    result_batches = relationship(
        "RecruitmentResultBatch",
        back_populates="round",
        foreign_keys="RecruitmentResultBatch.round_id"
    )

    __table_args__ = (
        UniqueConstraint("job_posting_id", "round_number", name="uq_recruitment_rounds_job_round_number"),
        CheckConstraint("round_number > 0", name="chk_recruitment_round_number_positive"),
        Index("idx_recruitment_rounds_job_number", "job_posting_id", "round_number"),
    )

    def __repr__(self):
        return (
            f"<RecruitmentRound id={self.id} job={self.job_posting_id} "
            f"round={self.round_number} '{self.name}' (final={self.is_final})>"
        )


# =============================================================================
# STUDENT ROUND OUTCOME MODEL
# =============================================================================

class StudentRoundOutcome(Base):
    """
    Authoritative confirmed outcome for one student in one defined recruitment round.
    Retains reference to the source result batch and row item for provenance.
    """

    __tablename__ = "student_round_outcomes"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    round_id = Column(Integer, ForeignKey("recruitment_rounds.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    outcome = Column(
        Enum(RoundOutcome, name="round_outcome", create_type=False),
        nullable=False,
        default=RoundOutcome.CLEARED,
        index=True
    )
    score = Column(Float, nullable=True)
    remarks = Column(Text, nullable=True)
    source_batch_id = Column(Integer, ForeignKey("recruitment_result_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    source_item_id = Column(Integer, ForeignKey("recruitment_result_items.id", ondelete="SET NULL"), nullable=True, index=True)
    confirmed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    confirmed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    application = relationship("Application", back_populates="round_outcomes", lazy="joined")
    round = relationship("RecruitmentRound", back_populates="student_outcomes", lazy="joined")
    student = relationship("User", foreign_keys=[student_id], lazy="joined")
    source_batch = relationship("RecruitmentResultBatch", foreign_keys=[source_batch_id], lazy="joined")
    source_item = relationship("RecruitmentResultItem", foreign_keys=[source_item_id], lazy="joined")
    confirmer = relationship("User", foreign_keys=[confirmed_by], lazy="joined")

    __table_args__ = (
        UniqueConstraint("application_id", "round_id", name="uq_student_round_outcome_app_round"),
        Index("idx_round_outcome_student", "student_id"),
        Index("idx_round_outcome_app_round", "application_id", "round_id"),
        Index("idx_round_outcome_round_outcome", "round_id", "outcome"),
    )

    def __repr__(self):
        return (
            f"<StudentRoundOutcome id={self.id} app={self.application_id} "
            f"round={self.round_id} student={self.student_id} outcome={self.outcome.value}>"
        )


# =============================================================================
# PLACEMENT OFFER MODEL
# =============================================================================

class PlacementOffer(Base):
    """
    Formal placement offer issued to a student for a specific job application.
    Tracks offered CTC, designation, acceptance status, and optional offer letter document.
    """

    __tablename__ = "placement_offers"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer,
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_posting_id = Column(Integer, ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, index=True)
    ctc_lpa = Column(Float, nullable=True)
    designation = Column(String(255), nullable=True)
    acceptance_status = Column(
        Enum(OfferAcceptanceStatus, name="offer_acceptance_status", create_type=False),
        nullable=False,
        default=OfferAcceptanceStatus.OFFERED,
        index=True
    )
    offer_letter_file_id = Column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="RESTRICT"),
        nullable=True,
        index=True
    )
    offer_date = Column(DateTime(timezone=True), nullable=True)
    response_date = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    application = relationship("Application", back_populates="placement_offer", lazy="joined")
    student = relationship("User", foreign_keys=[student_id], lazy="joined")
    job_posting = relationship("JobPosting", foreign_keys=[job_posting_id], lazy="joined")
    offer_letter_file = relationship("File", foreign_keys=[offer_letter_file_id], lazy="joined")
    verifier = relationship("User", foreign_keys=[verified_by], lazy="joined")

    __table_args__ = (
        Index("idx_placement_offers_student", "student_id"),
        Index("idx_placement_offers_job", "job_posting_id"),
        Index("idx_placement_offers_status", "acceptance_status"),
    )

    def __repr__(self):
        return (
            f"<PlacementOffer id={self.id} app={self.application_id} student={self.student_id} "
            f"status={self.acceptance_status.value} ctc={self.ctc_lpa}>"
        )
