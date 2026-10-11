"""
Recruitment Result Student Identity Matcher

Performs conservative, deterministic matching of extracted candidate records
against active EduMatrix students.

Matching Hierarchy:
1. Exact normalized institutional enrollment number / USN (Confidence: 1.00)
2. Exact normalized account email (Confidence: 0.98)
3. Unique name + corroborating branch/department (Confidence: 0.75)
4. Name-only match (Confidence: 0.50, always flagged as AMBIGUOUS)
5. Identifier conflicts / Name collisions (Confidence: <= 0.40, AMBIGUOUS)
6. Unmatched (Confidence: 0.00, PENDING)

Never automatically confirms a match. Retains full evidence and alternatives.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from sqlalchemy.orm import Session, joinedload

from ..models.user import User, UserRole
from ..models.profile import StudentProfileExtended
from ..models.recruitment_result import RecruitmentResultReviewState

logger = logging.getLogger(__name__)


def normalize_usn(val: Optional[str]) -> Optional[str]:
    """Clean USN / Roll number: uppercase, remove spaces, hyphens, slashes."""
    if not val:
        return None
    cleaned = re.sub(r"[\s\-\/\.]+", "", str(val)).upper()
    return cleaned if len(cleaned) >= 3 else None


def normalize_email(val: Optional[str]) -> Optional[str]:
    """Clean email: lowercase, strip."""
    if not val:
        return None
    cleaned = str(val).strip().lower()
    return cleaned if "@" in cleaned and "." in cleaned else None


def normalize_name(val: Optional[str]) -> Optional[str]:
    """Clean student name: strip salutations, multiple spaces, lowercase."""
    if not val:
        return None
    s = str(val).strip().lower()
    # Strip prefixes like mr, ms, mrs, miss
    s = re.sub(r"^(mr\.|ms\.|mrs\.|miss\s+|dr\.)\s*", "", s)
    # Collapse multiple spaces and symbols
    s = re.sub(r"[^a-zA-Z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) >= 2 else None


class RecruitmentResultMatcher:
    """Service to match extracted candidate rows against active student profiles."""

    def __init__(self):
        pass

    def match_row(
        self,
        db: Session,
        extracted_usn: Optional[str],
        extracted_email: Optional[str],
        extracted_name: Optional[str],
        extracted_branch: Optional[str] = None,
        job_branches: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate a single candidate row against active students and return
        matched_student_id, confidence, method, evidence, and review_status.
        """
        norm_usn = normalize_usn(extracted_usn)
        norm_email = normalize_email(extracted_email)
        norm_name = normalize_name(extracted_name)

        student_by_usn: Optional[User] = None
        student_by_email: Optional[User] = None

        # 1. Search by USN / Enrollment Number
        if norm_usn:
            profile = (
                db.query(StudentProfileExtended)
                .join(User, StudentProfileExtended.user_id == User.id)
                .filter(
                    User.role == UserRole.STUDENT,
                    User.is_active == True,
                    StudentProfileExtended.enrollment_number.isnot(None),
                )
                .all()
            )
            # Match normalized enrollment numbers
            matched_profiles = [
                p for p in profile
                if normalize_usn(p.enrollment_number) == norm_usn
            ]
            if len(matched_profiles) == 1:
                student_by_usn = matched_profiles[0].user

        # 2. Search by Email
        if norm_email:
            student_by_email = (
                db.query(User)
                .options(joinedload(User.student_profile))
                .filter(
                    User.role == UserRole.STUDENT,
                    User.is_active == True,
                    User.email == norm_email,
                )
                .first()
            )

        # CHECK FOR IDENTIFIER CONFLICTS
        if student_by_usn and student_by_email and student_by_usn.id != student_by_email.id:
            logger.warning(
                f"⚠️ Conflicting identifiers: USN {norm_usn} (student {student_by_usn.id}) "
                f"vs Email {norm_email} (student {student_by_email.id})"
            )
            return {
                "matched_student_id": None,
                "match_confidence": 0.40,
                "match_method": "CONFLICTING_IDENTIFIERS",
                "review_status": RecruitmentResultReviewState.AMBIGUOUS,
                "match_evidence": {
                    "reason": "USN and Email point to two different student records in the system.",
                    "usn_candidate": self._serialize_student(student_by_usn),
                    "email_candidate": self._serialize_student(student_by_email),
                },
            }

        # TIER 1: Exact USN Match
        if student_by_usn:
            return {
                "matched_student_id": student_by_usn.id,
                "match_confidence": 1.00,
                "match_method": "EXACT_USN",
                "review_status": RecruitmentResultReviewState.MATCHED,
                "match_evidence": {
                    "matched_field": "enrollment_number",
                    "matched_value": norm_usn,
                    "student": self._serialize_student(student_by_usn),
                },
            }

        # TIER 2: Exact Email Match
        if student_by_email:
            return {
                "matched_student_id": student_by_email.id,
                "match_confidence": 0.98,
                "match_method": "EXACT_EMAIL",
                "review_status": RecruitmentResultReviewState.MATCHED,
                "match_evidence": {
                    "matched_field": "email",
                    "matched_value": norm_email,
                    "student": self._serialize_student(student_by_email),
                },
            }

        # TIER 3 & 4: Name Matching (with branch corroboration and collision detection)
        if norm_name:
            candidates = self._find_students_by_name(db, norm_name)
            if candidates:
                # Corroborate with branch
                target_branches: Set[str] = set()
                if extracted_branch:
                    target_branches.add(extracted_branch.strip().lower())
                if job_branches:
                    for b in job_branches:
                        if b:
                            target_branches.add(str(b).strip().lower())

                # Branch corroboration check
                branch_filtered = []
                if target_branches:
                    for cand in candidates:
                        s_branch = (
                            cand.student_profile.branch
                            if cand.student_profile and cand.student_profile.branch
                            else cand.department
                        )
                        if s_branch and str(s_branch).strip().lower() in target_branches:
                            branch_filtered.append(cand)

                if len(branch_filtered) == 1:
                    # Unique Name + Branch match -> 0.75 confidence, but AMBIGUOUS (requires officer sign-off)
                    cand = branch_filtered[0]
                    return {
                        "matched_student_id": cand.id,
                        "match_confidence": 0.75,
                        "match_method": "NAME_AND_BRANCH",
                        "review_status": RecruitmentResultReviewState.AMBIGUOUS,
                        "match_evidence": {
                            "matched_name": norm_name,
                            "corroborated_branch": [str(b) for b in target_branches],
                            "student": self._serialize_student(cand),
                            "note": "Matched via full name and department. Requires officer review.",
                        },
                    }

                if len(candidates) == 1:
                    # Single student across institution with this name, but no branch corroboration
                    cand = candidates[0]
                    return {
                        "matched_student_id": cand.id,
                        "match_confidence": 0.50,
                        "match_method": "NAME_ONLY",
                        "review_status": RecruitmentResultReviewState.AMBIGUOUS,
                        "match_evidence": {
                            "matched_name": norm_name,
                            "student": self._serialize_student(cand),
                            "note": "Name-only match without department verification. Needs officer confirmation.",
                        },
                    }

                # Multiple candidates found: Name Collision!
                return {
                    "matched_student_id": None,
                    "match_confidence": 0.30,
                    "match_method": "NAME_COLLISION",
                    "review_status": RecruitmentResultReviewState.AMBIGUOUS,
                    "match_evidence": {
                        "searched_name": norm_name,
                        "collision_count": len(candidates),
                        "alternatives": [self._serialize_student(c) for c in candidates[:5]],
                        "note": f"Found {len(candidates)} active students matching this name. Manual selection required.",
                    },
                }

        # TIER 5: Unmatched
        return {
            "matched_student_id": None,
            "match_confidence": 0.00,
            "match_method": "UNMATCHED",
            "review_status": RecruitmentResultReviewState.PENDING,
            "match_evidence": {
                "searched_usn": norm_usn,
                "searched_email": norm_email,
                "searched_name": norm_name,
                "note": "No active student record found matching any extracted identifier.",
            },
        }

    def _find_students_by_name(self, db: Session, target_norm_name: str) -> List[User]:
        """Find active students with matching or highly similar names."""
        all_students = (
            db.query(User)
            .options(joinedload(User.student_profile))
            .filter(
                User.role == UserRole.STUDENT,
                User.is_active == True,
            )
            .all()
        )

        matches = []
        for s in all_students:
            names_to_check = []
            if s.name:
                names_to_check.append(normalize_name(s.name))
            if s.student_profile and s.student_profile.full_name:
                names_to_check.append(normalize_name(s.student_profile.full_name))

            for n in names_to_check:
                if not n:
                    continue
                # Exact normalized name
                if n == target_norm_name:
                    matches.append(s)
                    break
                # Tokens reordered (e.g., "Rithesh K" vs "K Rithesh")
                t_tokens = sorted(target_norm_name.split())
                n_tokens = sorted(n.split())
                if t_tokens == n_tokens and len(t_tokens) > 1:
                    matches.append(s)
                    break

        return matches

    def _serialize_student(self, student: User) -> Dict[str, Any]:
        """Serialize student user and profile for match evidence storage."""
        profile = student.student_profile
        return {
            "id": student.id,
            "name": student.name,
            "email": student.email,
            "department": student.department,
            "usn": profile.enrollment_number if profile else None,
            "branch": profile.branch if profile else None,
            "cgpa": profile.cgpa if profile else None,
            "year": profile.year if profile else None,
        }


# Global singleton instance
recruitment_result_matcher = RecruitmentResultMatcher()
