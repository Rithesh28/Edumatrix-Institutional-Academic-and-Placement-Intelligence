from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Text, Enum, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..core.database import Base
import enum
from .certification import Certification


class PlacementStatus(str, enum.Enum):
    NOT_APPLIED = "not_applied"
    APPLIED = "applied"
    SHORTLISTED = "shortlisted"
    PLACED = "placed"


class SkillProficiency(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class ProjectType(str, enum.Enum):
    ACADEMIC = "academic"
    PERSONAL = "personal"
    HACKATHON = "hackathon"
    INTERNSHIP = "internship"


class ProjectStatus(str, enum.Enum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    PLANNING = "planning"


class StudentProfileExtended(Base):
    __tablename__ = "student_profiles"
    __table_args__ = {"extend_existing": True}
    __mapper_args__ = {
        "exclude_properties": ["skills"]
    }

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    # Personal Information
    full_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    date_of_birth = Column(DateTime(timezone=True), nullable=True)
    address = Column(Text, nullable=True)
    profile_picture_url = Column(String, nullable=True)

    # Academic Information
    enrollment_number = Column(String, nullable=True)
    year = Column(Integer, nullable=True)
    branch = Column(String, nullable=True)
    cgpa = Column(Float, nullable=True)
    semester = Column(Integer, nullable=True)

    # Placement
    placement_status = Column(Enum(PlacementStatus), default=PlacementStatus.NOT_APPLIED)
    github_profile = Column(String, nullable=True)
    linkedin_profile = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="student_profile")
    skills = relationship("Skill", back_populates="student", cascade="all, delete-orphan")
    certifications = relationship("Certification", back_populates="student", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="student", cascade="all, delete-orphan")


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("student_profiles.id"), nullable=False)
    name = Column(String, nullable=False)
    proficiency = Column(Enum(SkillProficiency), default=SkillProficiency.INTERMEDIATE)
    added_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("StudentProfileExtended", back_populates="skills")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("student_profiles.id"), nullable=False)

    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    technologies = Column(JSON, default=list)
    project_type = Column(Enum(ProjectType), default=ProjectType.PERSONAL)
    status = Column(Enum(ProjectStatus), default=ProjectStatus.COMPLETED)

    github_link = Column(String, nullable=True)
    live_link = Column(String, nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)

    is_active = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("StudentProfileExtended", back_populates="projects")


# ============================================
# Alias for backward compatibility
# ============================================
StudentProfile = StudentProfileExtended