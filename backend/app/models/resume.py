"""
Resume Model for AI Resume Analyzer

Stores structured resume data extracted from student resumes.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum as SQLEnum, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID
import uuid
from datetime import datetime
import enum

from ..core.database import Base


# ============================================
# ENUMS
# ============================================

class ResumeStatus(str, enum.Enum):
    """Resume processing status."""
    PENDING = "pending"          # Uploaded, waiting for processing
    PROCESSING = "processing"    # Currently being analyzed
    COMPLETED = "completed"      # Successfully processed
    FAILED = "failed"            # Processing failed


class ResumeEntityType(str, enum.Enum):
    """Entity types extracted from resumes."""
    NAME = "NAME"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    SKILL = "SKILL"
    EDUCATION = "EDUCATION"
    EXPERIENCE = "EXPERIENCE"
    PROJECT = "PROJECT"
    CERTIFICATION = "CERTIFICATION"
    INTERNSHIP = "INTERNSHIP"
    UNIVERSITY = "UNIVERSITY"
    DEGREE = "DEGREE"
    COMPANY = "COMPANY"


# ============================================
# MODEL
# ============================================

class Resume(Base):
    """
    Resume model for storing extracted resume data.
    
    This table stores all information extracted from a student's resume:
    - Contact information (name, email, phone)
    - Structured data (skills, education, experience, projects, certifications)
    - ATS score and improvement suggestions
    - Processing status
    """
    
    __tablename__ = "resumes"
    
    # ============================================
    # IDENTITY FIELDS
    # ============================================
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    student_id = Column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    file_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("files.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # ============================================
    # CONTACT INFORMATION
    # ============================================
    
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    
    # ============================================
    # STRUCTURED DATA (JSON)
    # ============================================
    
    # Skills: ["Python", "Java", "SQL", ...]
    skills = Column(JSONB, nullable=True, default=list)
    
    # Education: [{"degree": "B.Tech", "branch": "CSE", ...}]
    education = Column(JSONB, nullable=True, default=list)
    
    # Experience: [{"title": "Software Engineer", "company": "Google", ...}]
    experience = Column(JSONB, nullable=True, default=list)
    
    # Projects: [{"name": "AI Chatbot", "description": "...", ...}]
    projects = Column(JSONB, nullable=True, default=list)
    
    # Certifications: [{"name": "AWS Certified", "issuer": "Amazon", ...}]
    certifications = Column(JSONB, nullable=True, default=list)
    
    # Internships: [{"title": "Intern", "company": "Microsoft", ...}]
    internships = Column(JSONB, nullable=True, default=list)
    
    # Additional: [{"key": "value"}]
    additional_data = Column(JSONB, nullable=True, default=dict)
    
    # ============================================
    # ATS SCORE & SUGGESTIONS
    # ============================================
    
    ats_score = Column(Float, nullable=True)  # 0-100
    
    # Suggestions: [{"category": "skills", "message": "...", "priority": "high"}]
    suggestions = Column(JSONB, nullable=True, default=list)
    
    # Skill gap: [{"skill": "Python", "priority": "high"}]
    skill_gap = Column(JSONB, nullable=True, default=list)
    
    # ============================================
    # STATUS & TIMESTAMPS
    # ============================================
    
    status = Column(
        SQLEnum(
            ResumeStatus,
            name="resume_status",
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=True
        ), 
        default=ResumeStatus.PENDING,
        nullable=False
    )
    
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True), 
        onupdate=func.now()
    )
    
    # ============================================
    # RELATIONSHIPS
    # ============================================
    
    # Student who uploaded the resume
    student = relationship("User", foreign_keys=[student_id], back_populates="resumes")
    
    # File associated with the resume
    file = relationship("File", foreign_keys=[file_id])
    
    # ============================================
    # TABLE INDEXES
    # ============================================
    
    __table_args__ = (
        Index("idx_resumes_student_status", "student_id", "status"),
        Index("idx_resumes_created_at", "created_at"),
        Index("idx_resumes_ats_score", "ats_score"),
    )
    
    # ============================================
    # METHODS
    # ============================================
    
    def __repr__(self):
        return f"<Resume {self.id} - {self.name or 'Unnamed'}>"
    
    def to_dict(self) -> dict:
        """Convert resume to dictionary."""
        return {
            "id": self.id,
            "student_id": self.student_id,
            "student_name": self.student.name if self.student else None,
            "file_id": str(self.file_id) if self.file_id else None,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "skills": self.skills or [],
            "education": self.education or [],
            "experience": self.experience or [],
            "projects": self.projects or [],
            "certifications": self.certifications or [],
            "internships": self.internships or [],
            "additional_data": self.additional_data or {},
            "ats_score": self.ats_score,
            "suggestions": self.suggestions or [],
            "skill_gap": self.skill_gap or [],
            "status": self.status.value if self.status else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def to_dict_with_file(self) -> dict:
        """Convert resume to dictionary with file details."""
        data = self.to_dict()
        if self.file:
            data["file"] = {
                "id": str(self.file.id),
                "filename": self.file.filename,
                "file_size": self.file.file_size,
                "mime_type": self.file.mime_type,
                "download_url": f"/files/{self.file.id}/download",
            }
        return data
    
    def get_ats_summary(self) -> dict:
        """Get ATS score summary."""
        return {
            "score": self.ats_score,
            "suggestions": self.suggestions or [],
            "total_suggestions": len(self.suggestions or []),
            "high_priority": len([s for s in self.suggestions or [] if s.get("priority") == "high"]),
            "medium_priority": len([s for s in self.suggestions or [] if s.get("priority") == "medium"]),
            "low_priority": len([s for s in self.suggestions or [] if s.get("priority") == "low"]),
        }
    
    def get_skills_summary(self) -> dict:
        """Get skills summary."""
        return {
            "total_skills": len(self.skills or []),
            "skills": self.skills or [],
            "missing_skills": self.skill_gap or [],
        }