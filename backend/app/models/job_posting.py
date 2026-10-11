"""
Job Posting Model for Placement Management
"""

from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

from ..core.database import Base
import enum


class JobStatus(str, enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"


class JobPosting(Base):
    """Job posting model for placement drives."""
    
    __tablename__ = "job_postings"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    required_skills = Column(JSONB, nullable=True, default=[])  # List of skills
    preferred_skills = Column(JSONB, nullable=True, default=[])  # List of preferred skills
    experience_level = Column(String(50), nullable=True)
    cgpa_criteria = Column(Float, nullable=True)  # Minimum CGPA requirement
    branch_eligibility = Column(JSONB, nullable=True, default=[])  # List of eligible branches
    location = Column(String(255), nullable=True)
    salary_range = Column(String(100), nullable=True)
    application_url = Column(String(2048), nullable=True)  # Official external company application URL
    application_deadline = Column(DateTime(timezone=True), nullable=True)
    drive_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(Enum(JobStatus), default=JobStatus.DRAFT)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    company = relationship("Company", back_populates="job_postings")
    applications = relationship("Application", back_populates="job_posting", cascade="all, delete-orphan")
    shortlists = relationship("Shortlist", back_populates="job_posting")
    rounds = relationship("RecruitmentRound", back_populates="job_posting", cascade="all, delete-orphan", order_by="RecruitmentRound.round_number")
    
    def __repr__(self):
        return f"<JobPosting {self.title} at {self.company.name if self.company else 'Unknown'}>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "company_id": self.company_id,
            "company_name": self.company.name if self.company else None,
            "title": self.title,
            "description": self.description,
            "application_url": self.application_url,
            "required_skills": self.required_skills or [],
            "preferred_skills": self.preferred_skills or [],
            "experience_level": self.experience_level,
            "cgpa_criteria": self.cgpa_criteria,
            "branch_eligibility": self.branch_eligibility or [],
            "location": self.location,
            "salary_range": self.salary_range,
            "application_deadline": self.application_deadline.isoformat() if self.application_deadline else None,
            "drive_date": self.drive_date.isoformat() if self.drive_date else None,
            "status": self.status.value if self.status else None,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }