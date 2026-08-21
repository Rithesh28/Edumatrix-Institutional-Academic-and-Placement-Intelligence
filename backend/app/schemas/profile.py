"""
Profile Schemas - Pydantic models for validation
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from typing import Optional, List, Any
from enum import Enum
from .certification import CertificationResponse


class PlacementStatus(str, Enum):
    NOT_APPLIED = "not_applied"
    APPLIED = "applied"
    SHORTLISTED = "shortlisted"
    PLACED = "placed"


class SkillProficiency(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class ProjectType(str, Enum):
    ACADEMIC = "academic"
    PERSONAL = "personal"
    HACKATHON = "hackathon"
    INTERNSHIP = "internship"


class ProjectStatus(str, Enum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    PLANNING = "planning"


# ============================================
# Skill Schemas
# ============================================

class SkillCreate(BaseModel):
    name: str
    proficiency: SkillProficiency = SkillProficiency.INTERMEDIATE


class SkillUpdate(BaseModel):
    name: Optional[str] = None
    proficiency: Optional[SkillProficiency] = None


class SkillResponse(BaseModel):
    id: int
    student_id: int
    name: str
    proficiency: SkillProficiency
    added_at: datetime

    class Config:
        from_attributes = True


# ============================================
# Project Schemas
# ============================================

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    technologies: Optional[List[str]] = []
    project_type: ProjectType = ProjectType.PERSONAL
    status: ProjectStatus = ProjectStatus.COMPLETED
    github_link: Optional[str] = None
    live_link: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    technologies: Optional[List[str]] = None
    project_type: Optional[ProjectType] = None
    status: Optional[ProjectStatus] = None
    github_link: Optional[str] = None
    live_link: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_active: Optional[int] = None


class ProjectResponse(BaseModel):
    id: int
    student_id: int
    name: str
    description: Optional[str] = None
    technologies: List[str]
    project_type: ProjectType
    status: ProjectStatus
    github_link: Optional[str] = None
    live_link: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_active: int
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================
# Profile Schemas
# ============================================

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    address: Optional[str] = None
    enrollment_number: Optional[str] = None
    year: Optional[int] = Field(None, ge=1, le=4)
    branch: Optional[str] = None
    cgpa: Optional[float] = Field(None, ge=0, le=10)
    semester: Optional[int] = Field(None, ge=1, le=8)
    placement_status: Optional[PlacementStatus] = None
    github_profile: Optional[str] = None
    linkedin_profile: Optional[str] = None

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def parse_dob(cls, v: Any) -> Optional[datetime]:
        if not v or v == "":
            return None
        if isinstance(v, str):
            try:
                # Support YYYY-MM-DD or ISO
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except Exception:
                return None
        return v

    @field_validator("year", "semester", mode="before")
    @classmethod
    def parse_ints(cls, v: Any) -> Optional[int]:
        if v is None or v == "":
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    @field_validator("cgpa", mode="before")
    @classmethod
    def parse_floats(cls, v: Any) -> Optional[float]:
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    @field_validator("placement_status", mode="before")
    @classmethod
    def parse_placement_status(cls, v: Any) -> Optional[PlacementStatus]:
        if not v or v == "":
            return None
        return v


class ProfileResponse(BaseModel):
    id: int
    user_id: int
    full_name: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    address: Optional[str] = None
    profile_picture_url: Optional[str] = None
    enrollment_number: Optional[str] = None
    year: Optional[int] = None
    branch: Optional[str] = None
    cgpa: Optional[float] = None
    semester: Optional[int] = None
    placement_status: PlacementStatus
    github_profile: Optional[str] = None
    linkedin_profile: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    skills: List[SkillResponse] = []
    certifications: List[CertificationResponse] = []
    projects: List[ProjectResponse] = []

    class Config:
        from_attributes = True


class ProfileWithUserResponse(BaseModel):
    profile: ProfileResponse
    email: str
    role: str

    class Config:
        from_attributes = True