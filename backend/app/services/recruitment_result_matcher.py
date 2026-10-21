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
from difflib import SequenceMatcher
from sqlalchemy.orm import Session, joinedload

from ..models.user import User, UserRole
from ..models.profile import StudentProfileExtended
from ..models.recruitment_result import RecruitmentResultReviewState

logger = logging.getLogger(__name__)

GENERIC_NAME_TOKENS = {
    "kumar", "kumari", "singh", "sharma", "devi", "prasad", "lal", "babu",
    "rao", "shetty", "bhat", "hegde", "gowda", "poojary", "acharya", "nayak", "pai", "kamath"
}


def normalize_usn(val: Optional[str]) -> Optional[str]:
    """Clean USN / Roll number: uppercase, remove spaces, hyphens, slashes."""
    if not val:
        return None
    cleaned = re.sub(r"[\s\-\/\.]+", "", str(val)).upper()
    return cleaned if len(cleaned) >= 3 else None


def is_identity_changing_usn_correction(raw_val: Optional[str], norm_val: Optional[str]) -> bool:
    """
    Determine if the transformation from raw_val to norm_val involved
    character alterations (e.g. A->4, 1/L->I, 9/5->S, digit restructuring) rather than
    harmless whitespace/punctuation/casing normalization.
    """
    if not raw_val or not norm_val:
        return False
    harmless_cleaned = re.sub(r"[\s\-\/\.]+", "", str(raw_val)).upper()
    return harmless_cleaned != norm_val


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


def normalize_name_tokens(name_str: Optional[str]) -> List[str]:
    """Extract clean lowercase alphanumeric tokens from a student/candidate name."""
    norm = normalize_name(name_str)
    return norm.split() if norm else []


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
        raw_usn: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate a single candidate row against active students and return
        matched_student_id, confidence, method, evidence, and review_status.
        """
        norm_usn = normalize_usn(extracted_usn)
        norm_email = normalize_email(extracted_email)
        norm_name = normalize_name(extracted_name)
        effective_raw_usn = raw_usn if raw_usn is not None else extracted_usn

        student_by_usn: Optional[User] = None
        student_by_email: Optional[User] = None
        matched_profiles: List[StudentProfileExtended] = []

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

        # Handle USN collision if multiple profiles have the exact same USN
        if norm_usn and len(matched_profiles) > 1:
            if student_by_email and any(p.user_id == student_by_email.id for p in matched_profiles):
                student_by_usn = student_by_email
            else:
                return {
                    "matched_student_id": None,
                    "match_confidence": 0.40,
                    "match_method": "USN_COLLISION",
                    "review_status": RecruitmentResultReviewState.AMBIGUOUS,
                    "match_evidence": {
                        "reason": f"USN {norm_usn} maps to multiple active student accounts.",
                        "candidates": [self._serialize_student(p.user) for p in matched_profiles],
                    },
                }

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
            is_contradiction, contradiction_reason = self._is_name_contradiction(
                extracted_name, student_by_usn, matched_profiles[0] if matched_profiles else None
            )
            if is_contradiction:
                logger.warning(
                    f"⚠️ Strong name-USN contradiction: USN {norm_usn} resolves to "
                    f"'{student_by_usn.name}', but document specifies '{extracted_name}'. "
                    f"Details: {contradiction_reason}"
                )
                return {
                    "matched_student_id": None,
                    "match_confidence": 0.40,
                    "match_method": "NAME_USN_CONTRADICTION",
                    "review_status": RecruitmentResultReviewState.AMBIGUOUS,
                    "match_evidence": {
                        "reason": (
                            f"USN {norm_usn} resolves to '{student_by_usn.name}', but document specifies "
                            f"candidate name '{extracted_name}'. {contradiction_reason}"
                        ),
                        "usn_candidate": self._serialize_student(student_by_usn),
                        "extracted_name": extracted_name,
                        "contradiction_details": contradiction_reason,
                    },
                }

            is_identity_changing = is_identity_changing_usn_correction(effective_raw_usn, norm_usn)
            has_name_corroboration = bool(norm_name)
            has_email_corroboration = bool(student_by_email and student_by_email.id == student_by_usn.id)

            # If USN underwent an identity-changing OCR correction and neither name nor email corroborates it:
            if is_identity_changing and not (has_name_corroboration or has_email_corroboration):
                logger.warning(
                    f"⚠️ Uncorroborated OCR USN correction: raw '{effective_raw_usn}' corrected to '{norm_usn}' "
                    f"without candidate name or email corroboration. Routing to officer review."
                )
                return {
                    "matched_student_id": None,
                    "match_confidence": 0.60,
                    "match_method": "UNCERTAIN_OCR_USN",
                    "review_status": RecruitmentResultReviewState.AMBIGUOUS,
                    "match_evidence": {
                        "reason": (
                            f"Extracted USN '{effective_raw_usn}' required character-level OCR correction to '{norm_usn}' "
                            f"without candidate name or email corroboration. Routed to placement officer for review."
                        ),
                        "raw_extracted_usn": str(effective_raw_usn).strip() if effective_raw_usn else None,
                        "normalized_usn": norm_usn,
                        "usn_normalization_applied": True,
                        "identity_changing_correction": True,
                        "formatting_cleanup_only": False,
                        "candidate": self._serialize_student(student_by_usn),
                    },
                }

            evidence = {
                "matched_field": "enrollment_number",
                "matched_value": norm_usn,
                "student": self._serialize_student(student_by_usn),
            }
            if norm_name:
                evidence["name_verified"] = True
                evidence["corroborated_name"] = norm_name
            else:
                evidence["name_verified"] = False
                evidence["note"] = "Exact USN match. No candidate name was available in document for corroboration."

            is_normalized = bool(effective_raw_usn and norm_usn and str(effective_raw_usn).strip() != norm_usn)
            evidence["usn_normalization_applied"] = is_normalized
            if is_normalized:
                evidence["raw_extracted_usn"] = str(effective_raw_usn).strip()
                evidence["identity_changing_correction"] = is_identity_changing
                evidence["formatting_cleanup_only"] = not is_identity_changing
            else:
                evidence["identity_changing_correction"] = False
                evidence["formatting_cleanup_only"] = False

            return {
                "matched_student_id": student_by_usn.id,
                "match_confidence": 1.00,
                "match_method": "EXACT_USN",
                "review_status": RecruitmentResultReviewState.MATCHED,
                "match_evidence": evidence,
            }

        # TIER 2: Exact Email Match
        if student_by_email:
            is_contradiction, contradiction_reason = self._is_name_contradiction(
                extracted_name, student_by_email, getattr(student_by_email, "student_profile", None)
            )
            if is_contradiction:
                logger.warning(
                    f"⚠️ Strong name-Email contradiction: Email {norm_email} resolves to "
                    f"'{student_by_email.name}', but document specifies '{extracted_name}'. "
                    f"Details: {contradiction_reason}"
                )
                return {
                    "matched_student_id": None,
                    "match_confidence": 0.40,
                    "match_method": "NAME_EMAIL_CONTRADICTION",
                    "review_status": RecruitmentResultReviewState.AMBIGUOUS,
                    "match_evidence": {
                        "reason": (
                            f"Email {norm_email} resolves to '{student_by_email.name}', but document specifies "
                            f"candidate name '{extracted_name}'. {contradiction_reason}"
                        ),
                        "email_candidate": self._serialize_student(student_by_email),
                        "extracted_name": extracted_name,
                        "contradiction_details": contradiction_reason,
                    },
                }

            evidence = {
                "matched_field": "email",
                "matched_value": norm_email,
                "student": self._serialize_student(student_by_email),
            }
            if norm_name:
                evidence["name_verified"] = True
                evidence["corroborated_name"] = norm_name
            else:
                evidence["name_verified"] = False
                evidence["note"] = "Exact email match. No candidate name was available in document for corroboration."

            return {
                "matched_student_id": student_by_email.id,
                "match_confidence": 0.98,
                "match_method": "EXACT_EMAIL",
                "review_status": RecruitmentResultReviewState.MATCHED,
                "match_evidence": evidence,
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

    def _is_name_contradiction(
        self,
        extracted_name: Optional[str],
        student: User,
        profile: Optional[StudentProfileExtended] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Conservative comparison between extracted candidate name and registered student name.
        Returns (is_contradiction, reason_if_contradiction).

        Rules:
        - If extracted_name is missing/empty, returns (False, None) (cannot contradict).
        - If student has no registered name, returns (False, None).
        - Compares extracted name tokens against all registered name fields (User.name, StudentProfileExtended.full_name).
        - Accounts for reordering (sorted tokens match), prefixes/initials (e.g. 'A' vs 'Adithya'),
          and minor OCR typo tolerance (difflib ratio >= 0.80).
        - Distinguishes strong contradiction from insufficient evidence:
          * If only generic surname/patronymic matches (e.g. 'Kumar', 'Shetty') while substantive
            given names conflict (e.g. 'Ramesh Kumar' vs 'Ashok Kumar'), flags contradiction.
          * If zero token overlap and no initial/fuzzy match (e.g. 'Completely Different Person' vs 'Rakshith R Shetty'),
            flags contradiction.
        """
        ext_tokens = normalize_name_tokens(extracted_name)
        if not ext_tokens:
            return False, None

        registered_names: List[str] = []
        if getattr(student, "name", None):
            registered_names.append(student.name)
        if profile and getattr(profile, "full_name", None):
            registered_names.append(profile.full_name)
        elif getattr(student, "student_profile", None) and getattr(student.student_profile, "full_name", None):
            registered_names.append(student.student_profile.full_name)

        reg_name_token_lists = []
        for rn in registered_names:
            if rn:
                tokens = normalize_name_tokens(rn)
                if tokens and tokens not in reg_name_token_lists:
                    reg_name_token_lists.append(tokens)

        if not reg_name_token_lists:
            return False, None

        reasons = []
        for reg_tokens in reg_name_token_lists:
            # 1. Exact token set match (including reordered)
            if sorted(ext_tokens) == sorted(reg_tokens):
                return False, None

            # 2. Token overlap & fuzzy / initial matches
            matched_ext = set()
            matched_reg = set()
            non_generic_matches = set()

            for et in ext_tokens:
                for rt in reg_tokens:
                    is_match = False
                    if et == rt:
                        is_match = True
                    elif len(et) == 1 and rt.startswith(et):
                        is_match = True
                    elif len(rt) == 1 and et.startswith(rt):
                        is_match = True
                    elif len(et) >= 3 and len(rt) >= 3:
                        if SequenceMatcher(None, et, rt).ratio() >= 0.80:
                            is_match = True

                    if is_match:
                        matched_ext.add(et)
                        matched_reg.add(rt)
                        # A match is non-generic only if neither token is a generic surname/family title
                        if et not in GENERIC_NAME_TOKENS and rt not in GENERIC_NAME_TOKENS:
                            non_generic_matches.add((et, rt))

            if not matched_ext:
                reasons.append(
                    f"Extracted name tokens {ext_tokens} share no common words or initials with registered name {reg_tokens}"
                )
                continue

            # If all matches were generic surname/family tokens, verify that distinct given names/initials do not conflict
            if not non_generic_matches:
                unmatched_ext = [t for t in ext_tokens if t not in matched_ext]
                unmatched_reg = [t for t in reg_tokens if t not in matched_reg]
                if unmatched_ext and unmatched_reg:
                    reasons.append(
                        f"Names only share generic token, while given names/initials ({unmatched_ext} vs {unmatched_reg}) contradict"
                    )
                    continue

            # This registered name variant is consistent with extracted candidate name
            return False, None

        # None of the registered name variants was consistent
        return True, "; ".join(reasons)


# Global singleton instance
recruitment_result_matcher = RecruitmentResultMatcher()
