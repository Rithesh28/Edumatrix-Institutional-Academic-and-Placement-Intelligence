from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from enum import Enum

class CircularTypeEnum(str, Enum):
    EXAM = "exam"
    ASSIGNMENT = "assignment"
    GENERAL = "general"

class CircularCreate(BaseModel):
    type: CircularTypeEnum
    title: str
    content: str
    due_date: Optional[datetime] = None
    file_id: Optional[UUID] = None

class CircularUpdate(BaseModel):
    type: Optional[CircularTypeEnum] = None
    title: Optional[str] = None
    content: Optional[str] = None
    due_date: Optional[datetime] = None
    file_id: Optional[UUID] = None

class FileDetails(BaseModel):
    id: UUID
    filename: str
    file_size: int
    mime_type: str
    download_url: str
    preview_url: Optional[str] = None

class CircularResponse(BaseModel):
    id: int
    lecturer_id: int
    lecturer_name: Optional[str] = None
    type: CircularTypeEnum
    title: str
    content: str
    file_url: Optional[str] = None
    file_id: Optional[UUID] = None
    file_type: Optional[str] = None
    file_details: Optional[FileDetails] = None
    due_date: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    extra_data: Optional[Dict[str, Any]] = None  # ADD THIS FIELD
    
    class Config:
        from_attributes = True