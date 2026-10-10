"""
Admin API - User Management, System Auditing, and Governance
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from ..core.database import get_db
from ..models.user import User, UserRole
from ..models.profile import StudentProfileExtended
from ..schemas.user import UserResponse
from ..schemas.admin import (
    UserUpdateRoleRequest,
    UserUpdateStatusRequest,
    UserListResponse,
    AuditLogListResponse,
)
from ..services.audit_service import audit_service
from .auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin Management"])


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to enforce that current user is an administrator."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Administrator privileges required"
        )
    return current_user


# ============================================
# USER MANAGEMENT ENDPOINTS
# ============================================

@router.get("/users", response_model=UserListResponse)
async def list_users(
    search: Optional[str] = Query(None, description="Search by name or email"),
    role: Optional[UserRole] = Query(None, description="Filter by user role"),
    department: Optional[str] = Query(None, description="Filter by department"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List and filter institutional users (Admin only)."""
    query = db.query(User)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(User.name.ilike(term), User.email.ilike(term)))

    if role:
        query = query.filter(User.role == role)

    if department:
        query = query.filter(User.department.ilike(f"%{department.strip()}%"))

    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    total = query.count()
    offset = (page - 1) * limit
    users = query.order_by(desc(User.created_at)).offset(offset).limit(limit).all()

    return UserListResponse(
        total=total,
        page=page,
        limit=limit,
        items=[UserResponse.model_validate(u) for u in users]
    )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_details(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Retrieve detailed user information by ID (Admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found")
    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: int,
    request: UserUpdateRoleRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Update a user's role (Admin only).
    Prevents self-demotion to preserve at least one active administrator.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found")

    # Prevent admin from changing their own role to prevent lockout
    if current_user.id == user_id and request.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Self-demotion is prevented: Administrators cannot remove their own admin role"
        )

    old_role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
    new_role_val = request.role.value if hasattr(request.role, "value") else str(request.role)

    user.role = request.role
    db.commit()
    db.refresh(user)

    audit_service.log_action(
        db=db,
        action="USER_ROLE_UPDATE",
        actor=current_user,
        target_type="user",
        target_id=str(user_id),
        outcome="SUCCESS",
        details={
            "target_email": user.email,
            "old_role": old_role_val,
            "new_role": new_role_val
        }
    )

    logger.info(f"👑 User {user.email} (ID {user_id}) role changed from {old_role_val} to {new_role_val} by admin {current_user.email}")
    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: int,
    request: UserUpdateStatusRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Activate or deactivate a user account (Admin only).
    Prevents an administrator from deactivating their own account.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found")

    # Prevent admin from disabling their own account
    if current_user.id == user_id and not request.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot deactivate their own account"
        )

    user.is_active = request.is_active
    db.commit()
    db.refresh(user)

    audit_service.log_action(
        db=db,
        action="USER_STATUS_UPDATE",
        actor=current_user,
        target_type="user",
        target_id=str(user_id),
        outcome="SUCCESS",
        details={
            "target_email": user.email,
            "is_active": request.is_active
        }
    )

    status_str = "activated" if request.is_active else "deactivated"
    logger.info(f"🔒 User {user.email} (ID {user_id}) account {status_str} by admin {current_user.email}")
    return UserResponse.model_validate(user)


# ============================================
# AUDIT LOG ENDPOINTS
# ============================================

@router.get("/logs", response_model=AuditLogListResponse)
async def get_audit_logs(
    action: Optional[str] = Query(None, description="Filter by action name"),
    actor_email: Optional[str] = Query(None, description="Filter by actor email"),
    target_type: Optional[str] = Query(None, description="Filter by target type (user, file, etc.)"),
    outcome: Optional[str] = Query(None, description="Filter by outcome (SUCCESS, FAILURE)"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Retrieve system and security audit logs (Admin only)."""
    return audit_service.get_audit_logs(
        db=db,
        action=action,
        actor_email=actor_email,
        target_type=target_type,
        outcome=outcome,
        limit=limit,
        offset=offset
    )
