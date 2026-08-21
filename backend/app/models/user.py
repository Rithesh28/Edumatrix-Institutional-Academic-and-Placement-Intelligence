"""
User Models - Authentication and User Management
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Enum, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from ..core.database import Base
import enum


class UserRole(str, enum.Enum):
    """User role enum - must match database enum exactly (uppercase)"""
    STUDENT = "student"
    LECTURER = "lecturer"
    HOD = "hod"
    ADMIN = "admin"
    PLACEMENT_OFFICER = "placement_officer"


class User(Base):
    """User model for authentication and role-based access"""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.STUDENT)
    department = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    student_profile = relationship("StudentProfileExtended", back_populates="user", uselist=False, cascade="all, delete-orphan")
    lecturer_profile = relationship("LecturerProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    resumes = relationship("Resume", back_populates="student", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.email} ({self.role.value if self.role else 'N/A'})>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role.value if self.role else None,
            "department": self.department,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class LecturerProfile(Base):
    """Lecturer profile with additional details"""
    
    __tablename__ = "lecturer_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    subjects = Column(JSON, default=list)
    department = Column(String, nullable=True)
    api_enabled = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User", back_populates="lecturer_profile")
    
    def __repr__(self):
        return f"<LecturerProfile for user_id {self.user_id}>"