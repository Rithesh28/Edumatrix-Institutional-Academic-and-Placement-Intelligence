"""
Chat Policy Service - Enforces Institutional Communication Matrix for EduMatrix P2P Chat
Phase 3.1 Step E
"""

from typing import Tuple, Optional
from ..models.user import User, UserRole


def normalize_role(role) -> str:
    """Normalize role string or enum to lowercase string."""
    if hasattr(role, "value"):
        return str(role.value).strip().lower()
    return str(role).strip().lower()


def is_same_department(user1: User, user2: User) -> bool:
    """Check if two users belong to the exact same department (case-insensitive)."""
    dept1 = (user1.department or "").strip().casefold()
    dept2 = (user2.department or "").strip().casefold()
    return bool(dept1 and dept2 and dept1 == dept2)


def is_ai_allowed(user: User) -> bool:
    """AI Assistant is strictly available to students only."""
    if not user or not user.is_active:
        return False
    return normalize_role(user.role) == "student"


def can_chat(sender: User, receiver: User) -> Tuple[bool, str]:
    """
    Evaluates whether sender is authorized to initiate or send a P2P message to receiver.

    Communication Matrix:
    1. Student:
       - Lecturer: SAME DEPARTMENT
       - HOD: SAME DEPARTMENT
       - Placement Officer: INSTITUTION-WIDE
       - Student: BLOCKED
       - Admin: BLOCKED

    2. Lecturer:
       - Student: SAME DEPARTMENT
       - Lecturer: BLOCKED
       - HOD: BLOCKED
       - Placement Officer: BLOCKED
       - Admin: BLOCKED

    3. HOD:
       - Student: SAME DEPARTMENT
       - Lecturer: SAME DEPARTMENT
       - HOD: BLOCKED
       - Placement Officer: BLOCKED
       - Admin: BLOCKED

    4. Placement Officer:
       - Student: INSTITUTION-WIDE
       - Lecturer: BLOCKED
       - HOD: BLOCKED
       - Placement Officer: BLOCKED
       - Admin: BLOCKED

    5. Admin:
       - Normal P2P: BLOCKED
    """
    if not sender or not receiver:
        return False, "User not found."

    if not sender.is_active or not receiver.is_active:
        return False, "You are not allowed to message this user."

    if sender.id == receiver.id:
        return False, "You are not allowed to message this user."

    s_role = normalize_role(sender.role)
    r_role = normalize_role(receiver.role)

    # 1. STUDENT SENDER
    if s_role == "student":
        if r_role == "lecturer":
            if is_same_department(sender, receiver):
                return True, ""
            return False, "You are not allowed to message this user."
        elif r_role == "hod":
            if is_same_department(sender, receiver):
                return True, ""
            return False, "You are not allowed to message this user."
        elif r_role in ("placement_officer", "placement"):
            return True, ""
        else:
            return False, "You are not allowed to message this user."

    # 2. LECTURER SENDER
    elif s_role == "lecturer":
        if r_role == "student":
            if is_same_department(sender, receiver):
                return True, ""
            return False, "You are not allowed to message this user."
        else:
            return False, "You are not allowed to message this user."

    # 3. HOD SENDER
    elif s_role == "hod":
        if r_role == "student":
            if is_same_department(sender, receiver):
                return True, ""
            return False, "You are not allowed to message this user."
        elif r_role == "lecturer":
            if is_same_department(sender, receiver):
                return True, ""
            return False, "You are not allowed to message this user."
        else:
            return False, "You are not allowed to message this user."

    # 4. PLACEMENT OFFICER SENDER
    elif s_role in ("placement_officer", "placement"):
        if r_role == "student":
            return True, ""
        else:
            return False, "You are not allowed to message this user."

    # 5. ADMIN OR OTHER
    else:
        return False, "You are not allowed to message this user."
