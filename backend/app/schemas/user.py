"""
User Schemas - Pydantic models for user authentication and profile management
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ============================================
# ENUMS
# ============================================

class UserRoleEnum(str, Enum):
    STUDENT = "student"
    LECTURER = "lecturer"
    HOD = "hod"
    ADMIN = "admin"
    PLACEMENT_OFFICER = "placement_officer"


# ============================================
# USER SCHEMAS
# ============================================

class UserBase(BaseModel):
    email: str = Field(..., description="User email address")
    name: str = Field(..., description="User full name")
    role: UserRoleEnum = Field(UserRoleEnum.STUDENT, description="User role")
    department: Optional[str] = Field(None, description="Department name")


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="User password")
    department: Optional[str] = Field(None, description="Department name")


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: UserRoleEnum
    department: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


# ============================================
# STUDENT PROFILE SCHEMAS
# ============================================

class StudentProfileBase(BaseModel):
    user_id: int
    skills: Optional[List[str]] = Field(default=[], description="List of skills")
    year: Optional[int] = Field(None, description="Current year of study")
    branch: Optional[str] = Field(None, description="Branch of study")
    cgpa: Optional[float] = Field(None, ge=0, le=10, description="CGPA")
    phone: Optional[str] = Field(None, description="Phone number")
    address: Optional[str] = Field(None, description="Address")


class StudentProfileUpdate(BaseModel):
    skills: Optional[List[str]] = None
    year: Optional[int] = None
    branch: Optional[str] = None
    cgpa: Optional[float] = Field(None, ge=0, le=10)
    phone: Optional[str] = None
    address: Optional[str] = None


class StudentProfileResponse(StudentProfileBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ============================================
# LECTURER PROFILE SCHEMAS
# ============================================

class LecturerProfileBase(BaseModel):
    user_id: int
    subjects: Optional[List[str]] = Field(default=[], description="Subjects taught")
    department: Optional[str] = None
    api_enabled: Optional[bool] = Field(default=False, description="API access enabled")


class LecturerProfileUpdate(BaseModel):
    subjects: Optional[List[str]] = None
    department: Optional[str] = None
    api_enabled: Optional[bool] = None


class LecturerProfileResponse(LecturerProfileBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True