from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..core.database import Base


class Certification(Base):
    __tablename__ = "certifications"
    __table_args__ = {"extend_existing": True}  # ← ADD THIS

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("student_profiles.id"), nullable=False)

    name = Column(String, nullable=False)
    issuer = Column(String, nullable=True)
    credential_id = Column(String, nullable=True)
    certificate_url = Column(String, nullable=True)

    issue_date = Column(DateTime(timezone=True), nullable=True)
    expiry_date = Column(DateTime(timezone=True), nullable=True)

    verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    student = relationship("StudentProfileExtended", back_populates="certifications")