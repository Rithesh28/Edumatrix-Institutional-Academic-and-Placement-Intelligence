"""
Audit Service for Tracking Administrative, Security, and File Operations
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..models.audit_log import AuditLog
from ..models.user import User

logger = logging.getLogger(__name__)

SENSITIVE_KEYS = {"password", "password_hash", "token", "access_token", "secret", "authorization", "cookie"}


def _sanitize_details(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Recursively strip passwords, tokens, and sensitive headers from details."""
    if not data or not isinstance(data, dict):
        return data
    
    sanitized = {}
    for k, v in data.items():
        if any(sens in k.lower() for sens in SENSITIVE_KEYS):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = _sanitize_details(v)
        elif isinstance(v, list):
            sanitized[k] = [
                _sanitize_details(item) if isinstance(item, dict) else item 
                for item in v
            ]
        else:
            sanitized[k] = v
    return sanitized


class AuditService:
    """Service for capturing and querying audit logs."""

    @staticmethod
    def log_action(
        db: Session,
        action: str,
        actor: Optional[User] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        outcome: str = "SUCCESS",
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        auto_commit: bool = True,
    ) -> Optional[AuditLog]:
        """
        Record a security or administrative action in the audit log.
        Safe against logging failures so business logic is not interrupted.
        Supports outer transactions when auto_commit=False.
        """
        try:
            actor_id = actor.id if actor else None
            actor_email = actor.email if actor else "system"
            actor_role = actor.role.value if (actor and hasattr(actor.role, "value")) else str(actor.role) if actor else "system"

            clean_details = _sanitize_details(details)

            log_entry = AuditLog(
                actor_id=actor_id,
                actor_email=actor_email,
                actor_role=actor_role,
                action=action.upper(),
                target_type=target_type.lower() if target_type else None,
                target_id=str(target_id) if target_id is not None else None,
                outcome=outcome.upper(),
                details=clean_details,
                ip_address=ip_address,
            )

            db.add(log_entry)
            if auto_commit:
                db.commit()
                db.refresh(log_entry)
            else:
                db.flush()
            logger.info(f"📝 [AUDIT] {action.upper()} by {actor_email} on {target_type}:{target_id} -> {outcome.upper()}")
            return log_entry
        except Exception as e:
            logger.error(f"❌ Failed to record audit log: {str(e)}")
            if auto_commit:
                try:
                    db.rollback()
                except Exception:
                    pass
            return None

    @staticmethod
    def get_audit_logs(
        db: Session,
        action: Optional[str] = None,
        actor_email: Optional[str] = None,
        target_type: Optional[str] = None,
        outcome: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Query audit logs with optional filters and pagination."""
        query = db.query(AuditLog)

        if action:
            query = query.filter(AuditLog.action.ilike(f"%{action.strip()}%"))
        if actor_email:
            query = query.filter(AuditLog.actor_email.ilike(f"%{actor_email.strip()}%"))
        if target_type:
            query = query.filter(AuditLog.target_type == target_type.strip().lower())
        if outcome:
            query = query.filter(AuditLog.outcome == outcome.strip().upper())

        total = query.count()
        logs = query.order_by(desc(AuditLog.created_at)).offset(offset).limit(min(limit, 100)).all()

        return {
            "total": total,
            "items": [log.to_dict() for log in logs],
            "limit": limit,
            "offset": offset,
        }


audit_service = AuditService()
