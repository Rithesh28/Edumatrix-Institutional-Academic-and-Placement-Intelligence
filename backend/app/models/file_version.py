"""
File Version Database Model

Stores version history for files.
"""

import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from ..core.database import Base


class FileVersion(Base):
    """
    File Version model for tracking file history.
    """
    
    __tablename__ = "file_versions"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Reference to File
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Version Info
    version_number = Column(Integer, nullable=False)
    
    # Storage Location (MinIO)
    bucket = Column(String(50), nullable=False)
    object_key = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    
    # Version Metadata
    change_description = Column(Text, nullable=True)
    
    # Who uploaded this version - Using Integer to match User.id
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Additional Metadata
    extra_data = Column(JSON, nullable=True, default={})
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    file = relationship("File", back_populates="versions")
    uploader = relationship("User", foreign_keys=[uploaded_by], lazy="joined")
    
    def __repr__(self):
        return f"<FileVersion {self.version_number} for file {self.file_id}>"
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "file_id": str(self.file_id),
            "version_number": self.version_number,
            "bucket": self.bucket,
            "object_key": self.object_key,
            "file_size": self.file_size,
            "change_description": self.change_description,
            "uploaded_by": self.uploaded_by,
            "extra_data": self.extra_data or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }