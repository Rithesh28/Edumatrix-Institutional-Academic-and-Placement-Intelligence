"""
Audit Log Model for Institutional and Security Actions
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from ..core.database import Base


class AuditLog(Base):
    """
    Model for recording security and administrative audit events.
    Records actor, action, target resource, outcome, and non-sensitive metadata.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_email = Column(String(255), nullable=True, index=True)
    actor_role = Column(String(50), nullable=True, index=True)
    
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(100), nullable=True, index=True)
    target_id = Column(String(100), nullable=True, index=True)
    
    outcome = Column(String(50), nullable=False, default="SUCCESS", index=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(100), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    def __repr__(self):
        return f"<AuditLog {self.action} by {self.actor_email} at {self.created_at}>"

    def to_dict(self):
        return {
            "id": self.id,
            "actor_id": self.actor_id,
            "actor_email": self.actor_email,
            "actor_role": self.actor_role,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "outcome": self.outcome,
            "details": self.details,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
