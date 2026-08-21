"""
Shortlist Model for Placement Management
"""

from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from ..core.database import Base


class Shortlist(Base):
    """Shortlist model for tracking shortlisted students."""
    
    __tablename__ = "shortlists"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    job_posting_id = Column(Integer, ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, index=True)
    reason = Column(Text, nullable=True)
    shortlisted_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    student = relationship("User", foreign_keys=[student_id])
    company = relationship("Company", back_populates="shortlists")
    job_posting = relationship("JobPosting", back_populates="shortlists")
    shortlister = relationship("User", foreign_keys=[shortlisted_by])
    
    def __repr__(self):
        return f"<Shortlist {self.student_id} -> {self.company_id}>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "student_id": self.student_id,
            "student_name": self.student.name if self.student else None,
            "company_id": self.company_id,
            "company_name": self.company.name if self.company else None,
            "job_posting_id": self.job_posting_id,
            "job_title": self.job_posting.title if self.job_posting else None,
            "reason": self.reason,
            "shortlisted_by": self.shortlisted_by,
            "shortlister_name": self.shortlister.name if self.shortlister else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }