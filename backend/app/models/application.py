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

    @property
    def student_name(self):
        return self.student.name if self.student else None

    @property
    def student_email(self):
        return self.student.email if self.student else None

    @property
    def student_branch(self):
        if self.student:
            if hasattr(self.student, "student_profile") and self.student.student_profile and self.student.student_profile.branch:
                return self.student.student_profile.branch
            return self.student.department
        return None

    @property
    def student_cgpa(self):
        if self.student and hasattr(self.student, "student_profile") and self.student.student_profile:
            return self.student.student_profile.cgpa
        return None

    @property
    def student_usn(self):
        if self.student and hasattr(self.student, "student_profile") and self.student.student_profile:
            return self.student.student_profile.enrollment_number
        return None

    @property
    def job_title(self):
        return self.job_posting.title if self.job_posting else None

    @property
    def company_name(self):
        return self.job_posting.company.name if self.job_posting and self.job_posting.company else None

    @property
    def company_id(self):
        return self.job_posting.company_id if self.job_posting else None

    @property
    def job_deadline(self):
        return self.job_posting.application_deadline if self.job_posting else None

    @property
    def job_status(self):
        return self.job_posting.status.value if (self.job_posting and self.job_posting.status) else None

    @property
    def recruitment_progression(self):
        if not self.round_outcomes:
            return []
        return [
            {
                "id": outcome.id,
                "round_id": outcome.round_id,
                "round_number": outcome.round.round_number if outcome.round else None,
                "round_name": outcome.round.name if outcome.round else None,
                "round_type": outcome.round.round_type if outcome.round else None,
                "outcome": outcome.outcome.value if outcome.outcome else None,
                "score": outcome.score,
                "remarks": outcome.remarks,
                "confirmed_at": outcome.confirmed_at.isoformat() if outcome.confirmed_at else None,
            }
            for outcome in self.round_outcomes
        ]

    @property
    def verified_offer(self):
        if not self.placement_offer:
            return None
        offer = self.placement_offer
        return {
            "id": offer.id,
            "ctc_lpa": offer.ctc_lpa,
            "designation": offer.designation,
            "acceptance_status": offer.acceptance_status.value if offer.acceptance_status else None,
            "offer_date": offer.offer_date.isoformat() if offer.offer_date else None,
            "response_date": offer.response_date.isoformat() if offer.response_date else None,
        }

    def to_dict(self):
        return {
            "id": self.id,
            "student_id": self.student_id,
            "student_name": self.student_name,
            "student_email": self.student_email,
            "student_branch": self.student_branch,
            "student_cgpa": self.student_cgpa,
            "student_usn": self.student_usn,
            "job_posting_id": self.job_posting_id,
            "job_title": self.job_title,
            "company_name": self.company_name,
            "company_id": self.company_id,
            "job_deadline": self.job_deadline.isoformat() if self.job_deadline else None,
            "job_status": self.job_status,
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
            "recruitment_progression": self.recruitment_progression,
            "verified_offer": self.verified_offer,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }