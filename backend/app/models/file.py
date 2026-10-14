"""
File Database Model

Stores metadata for all files in the system.
"""

import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, JSON, Boolean, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY

from ..core.database import Base


class FileType:
    """File type constants."""
    EXAM_DUTY = "exam_duty"
    ASSIGNMENT = "assignment"
    CIRCULAR = "circular"
    RESUME = "resume"
    TIMETABLE = "timetable"
    CERTIFICATE = "certificate"
    PLACEMENT_DOC = "placement_doc"
    OTHER = "other"
    
    @classmethod
    def choices(cls):
        return [
            cls.EXAM_DUTY,
            cls.ASSIGNMENT,
            cls.CIRCULAR,
            cls.RESUME,
            cls.TIMETABLE,
            cls.CERTIFICATE,
            cls.PLACEMENT_DOC,
            cls.OTHER
        ]


class FileStatus:
    """File status constants."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"
    
    @classmethod
    def choices(cls):
        return [cls.ACTIVE, cls.ARCHIVED, cls.DELETED]


class File(Base):
    """
    File model for storing file metadata.
    """
    
    __tablename__ = "files"
    
    # Primary Key - Using UUID for file IDs
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # File Identity
    filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    
    # Storage Location (MinIO)
    bucket = Column(String(50), nullable=False)
    object_key = Column(String(500), nullable=False, unique=True)
    
    # File Metadata
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    tags = Column(ARRAY(String(50)), nullable=True, default=[])
    
    # Access Control
    department = Column(String(50), nullable=False, index=True)
    file_type = Column(String(50), nullable=False, index=True)
    
    # Ownership - Using Integer to match User.id (which is Integer)
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    hod_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Version Control
    version = Column(Integer, nullable=False, default=1)
    is_latest = Column(Boolean, nullable=False, default=True)
    
    # Status
    status = Column(String(20), nullable=False, default=FileStatus.ACTIVE, index=True)
    
    # Additional Metadata
    extra_data = Column(JSON, nullable=True, default={})
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    uploader = relationship("User", foreign_keys=[uploaded_by], lazy="joined")
    hod = relationship("User", foreign_keys=[hod_id], lazy="joined")
    versions = relationship("FileVersion", back_populates="file", cascade="all, delete-orphan")
    
    # Table Indexes
    __table_args__ = (
        Index("ix_files_department_type", "department", "file_type"),
        Index("ix_files_uploaded_by_created_at", "uploaded_by", "created_at"),
        Index("ix_files_status_type", "status", "file_type"),
    )
    
    def __repr__(self):
        return f"<File {self.filename} ({self.file_type})>"
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "filename": self.filename,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "bucket": self.bucket,
            "object_key": self.object_key,
            "title": self.title,
            "description": self.description,
            "tags": self.tags or [],
            "department": self.department,
            "file_type": self.file_type,
            "uploaded_by": self.uploaded_by,
            "hod_id": self.hod_id,
            "version": self.version,
            "is_latest": self.is_latest,
            "status": self.status,
            "extra_data": self.extra_data or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }