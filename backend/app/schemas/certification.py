from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class CertificationCreate(BaseModel):
    name: str
    issuer: Optional[str] = None
    credential_id: Optional[str] = None
    issue_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None


class CertificationUpdate(BaseModel):
    name: Optional[str] = None
    issuer: Optional[str] = None
    credential_id: Optional[str] = None
    issue_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    verified: Optional[bool] = None


class CertificationResponse(BaseModel):
    id: int
    student_id: int
    name: str
    issuer: Optional[str] = None
    credential_id: Optional[str] = None
    certificate_url: Optional[str] = None
    issue_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    verified: bool
    created_at: datetime

    class Config:
        from_attributes = True