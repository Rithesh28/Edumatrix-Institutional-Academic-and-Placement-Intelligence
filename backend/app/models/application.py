"""
Application Model for Placement Management
"""

from sqlalchemy import Column, Integer, Float, Text, DateTime, ForeignKey, Enum, UniqueConstraint, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from ..core.database import Base
import enum


class ApplicationStatus(str, enum.Enum):
    APPLIED = "applied"
    SHORTLISTED = "shortlisted"
    REJECTED = "rejected"
    SELECTED = "selected"


class Application(Base):
    """Student application model for job postings."""
    
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("student_id", "job_posting_id", name="uq_applications_student_job"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_posting_id = Column(Integer, ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.APPLIED)
    eligibility_score = Column(Float, nullable=True)  # Score based on eligibility criteria
    match_percentage = Column(Float, nullable=True)  # AI-based match percentage
    match_snapshot = Column(JSONB, nullable=True)  # Immutable snapshot at application submission time
    notes = Column(Text, nullable=True)
    applied_at = Column(DateTime(timezone=True), server_default=func.now())
    external_applied_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    student = relationship("User", foreign_keys=[student_id])
    job_posting = relationship("JobPosting", back_populates="applications")
    round_outcomes = relationship("StudentRoundOutcome", back_populates="application", cascade="all, delete-orphan", order_by="StudentRoundOutcome.id")
    placement_offer = relationship("PlacementOffer", back_populates="application", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Application {self.student_id} -> {self.job_posting_id}>"
    
    @property
    def created_at(self):
        return self.applied_at

    @property
    def is_external_confirmed(self) -> bool:
        return self.external_applied_at is not None

    @property
    def has_low_match_warning(self):
        if self.match_snapshot and isinstance(self.match_snapshot, dict):
            return bool(self.match_snapshot.get("has_low_match_warning", False))
        return None

    @property
    def low_match_warning(self):
        if self.match_snapshot and isinstance(self.match_snapshot, dict):
            return self.match_snapshot.get("low_match_warning")
        return None

    def to_dict(self):
        return {
            "id": self.id,
            "student_id": self.student_id,
            "student_name": self.student.name if self.student else None,
            "job_posting_id": self.job_posting_id,
            "job_title": self.job_posting.title if self.job_posting else None,
            "company_name": self.job_posting.company.name if self.job_posting and self.job_posting.company else None,
            "status": self.status.value if self.status else None,
            "eligibility_score": self.eligibility_score,
            "match_percentage": self.match_percentage,
            "match_snapshot": self.match_snapshot,
            "has_low_match_warning": self.has_low_match_warning,
            "low_match_warning": self.low_match_warning,
            "notes": self.notes,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "external_applied_at": self.external_applied_at.isoformat() if self.external_applied_at else None,
            "is_external_confirmed": self.is_external_confirmed,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }