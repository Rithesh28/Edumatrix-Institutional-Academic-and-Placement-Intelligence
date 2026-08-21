"""
Application Model for Placement Management
"""

from sqlalchemy import Column, Integer, Float, Text, DateTime, ForeignKey, Enum
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
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_posting_id = Column(Integer, ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.APPLIED)
    eligibility_score = Column(Float, nullable=True)  # Score based on eligibility criteria
    match_percentage = Column(Float, nullable=True)  # AI-based match percentage
    notes = Column(Text, nullable=True)
    applied_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    student = relationship("User", foreign_keys=[student_id])
    job_posting = relationship("JobPosting", back_populates="applications")
    
    def __repr__(self):
        return f"<Application {self.student_id} -> {self.job_posting_id}>"
    
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
            "notes": self.notes,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }