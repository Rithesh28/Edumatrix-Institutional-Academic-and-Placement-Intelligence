"""
Pydantic Schemas for Admin User Management and Audit Logs
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from ..models.user import UserRole
from .user import UserResponse


class UserUpdateRoleRequest(BaseModel):
    """Request schema for updating a user's role."""
    role: UserRole = Field(..., description="New role to assign to the user")


class UserUpdateStatusRequest(BaseModel):
    """Request schema for activating or deactivating a user account."""
    is_active: bool = Field(..., description="Active status flag")


class UserListResponse(BaseModel):
    """Response schema for paginated user list."""
    total: int
    page: int
    limit: int
    items: List[UserResponse]

    model_config = ConfigDict(from_attributes=True)


class AuditLogResponse(BaseModel):
    """Response schema for a single audit log entry."""
    id: int
    actor_id: Optional[int] = None
    actor_email: Optional[str] = None
    actor_role: Optional[str] = None
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    outcome: str
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AuditLogListResponse(BaseModel):
    """Response schema for paginated audit log list."""
    total: int
    limit: int
    offset: int
    items: List[AuditLogResponse]
