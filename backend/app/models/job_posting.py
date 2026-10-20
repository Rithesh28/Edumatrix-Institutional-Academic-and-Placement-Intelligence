"""
Job Posting Model for Placement Management
"""

from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Enum, JSON, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ..core.database import Base
import enum
from typing import Optional


class JobStatus(str, enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"


class JobPostingAttachment(Base):
    """Attachment metadata for job postings (referencing files table)."""
    
    __tablename__ = "job_posting_attachments"
    
    id = Column(Integer, primary_key=True, index=True)
    job_posting_id = Column(Integer, ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    display_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        UniqueConstraint("job_posting_id", "file_id", name="uq_job_posting_file"),
    )
    
    # Relationships
    job_posting = relationship("JobPosting", back_populates="attachments")
    file = relationship("File", lazy="joined")
    
    @property
    def filename(self) -> Optional[str]:
        """Original filename of the attached file."""
        return self.file.filename if self.file else None

    @property
    def file_name(self) -> Optional[str]:
        """Alias for original filename."""
        return self.file.filename if self.file else None

    @property
    def file_size(self) -> Optional[int]:
        """Size of the attached file in bytes."""
        return self.file.file_size if self.file else None

    @property
    def mime_type(self) -> Optional[str]:
        """MIME type of the attached file."""
        return self.file.mime_type if self.file else None

    def __repr__(self):
        return f"<JobPostingAttachment {self.id}: job={self.job_posting_id} file={self.file_id}>"


class JobPosting(Base):
    """Job posting model for placement drives."""
    
    __tablename__ = "job_postings"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"), nullable=True, index=True)
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
    file = relationship("File", foreign_keys=[file_id], lazy="joined")
    attachments = relationship(
        "JobPostingAttachment",
        back_populates="job_posting",
        cascade="all, delete-orphan",
        order_by="JobPostingAttachment.display_order",
        lazy="joined"
    )
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
            "file_id": str(self.file_id) if self.file_id else None,
            "file_name": self.file.filename if self.file else None,
            "attachments": [
                {
                    "id": att.id,
                    "file_id": str(att.file_id),
                    "filename": att.file.filename if att.file else None,
                    "file_size": att.file.file_size if att.file else None,
                    "mime_type": att.file.mime_type if att.file else None,
                    "created_at": att.created_at.isoformat() if att.created_at else None,
                }
                for att in (self.attachments or [])
            ],
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