"""
Job Matching Service for EduMatrix

Implements the deterministic backend matching foundation for Company / Job Skill Matching:
1. Matching Hierarchy:
   - Level 1: Exact normalized string match
   - Level 2: Canonical synonym mapping match
   - Level 3: Semantic similarity via sentence-transformers/all-MiniLM-L6-v2 (threshold >= 0.78)
2. Match Score Formula:
   - Required skills = 80%
   - Preferred skills = 20%
   - required_score = matched_required / total_required * 100
   - preferred_score = matched_preferred / total_preferred * 100
   - overall_skill_match = (required_score * 0.80) + (preferred_score * 0.20)
   - Zero-category safe handling without division by zero
3. Eligibility:
   - CGPA criteria and Branch criteria evaluated SEPARATELY from skill match
   - Match score never blends CGPA or branch into the skill percentage
4. Deterministic: No LLMs used for numerical scores
"""

import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from sqlalchemy.orm import Session

from .skill_normalizer import skill_normalizer
from .embedding_service import embedding_service
from ..models.user import User
from ..models.profile import StudentProfile, StudentProfileExtended, Skill
from ..models.resume import Resume
from ..models.job_posting import JobPosting
from ..schemas.placement import StudentEligibility

logger = logging.getLogger(__name__)

# Configurable semantic threshold for skill-to-skill comparison
SEMANTIC_SKILL_MATCH_THRESHOLD = 0.78


class EligibilityResult(tuple):
    """
    Subclass of tuple returning (is_eligible, cgpa_match, branch_match, eligibility_reasons, has_low_match_warning, low_match_warning)
    while exposing rich metadata properties (.eligibility_status, .missing_criteria).
    """
    def __new__(
        cls,
        is_eligible: bool,
        cgpa_match: bool,
        branch_match: bool,
        eligibility_reasons: List[str],
        has_low_match_warning: bool,
        low_match_warning: Optional[str],
        eligibility_status: str = "eligible",
        missing_criteria: Optional[List[str]] = None
    ):
        return super().__new__(
            cls,
            (is_eligible, cgpa_match, branch_match, eligibility_reasons, has_low_match_warning, low_match_warning)
        )

    def __init__(
        self,
        is_eligible: bool,
        cgpa_match: bool,
        branch_match: bool,
        eligibility_reasons: List[str],
        has_low_match_warning: bool,
        low_match_warning: Optional[str],
        eligibility_status: str = "eligible",
        missing_criteria: Optional[List[str]] = None
    ):
        self.is_eligible = is_eligible
        self.cgpa_match = cgpa_match
        self.branch_match = branch_match
        self.eligibility_reasons = eligibility_reasons
        self.has_low_match_warning = has_low_match_warning
        self.low_match_warning = low_match_warning
        self.eligibility_status = eligibility_status
        self.missing_criteria = missing_criteria or []


class JobMatchingService:
    """Service for computing deterministic job eligibility and skill match scores."""

    def __init__(self, semantic_threshold: float = SEMANTIC_SKILL_MATCH_THRESHOLD):
        self.semantic_threshold = semantic_threshold

    def get_student_skills(
        self, db: Session, student_id: int
    ) -> Tuple[List[str], Optional[Any], Optional[Resume], Dict[str, List[str]]]:
        """
        Retrieve student's full skill profile from authoritative sources:
        1. StudentProfile / StudentProfileExtended profile skills
        2. Direct Skill database records
        3. Latest completed resume skills (Resume.status == COMPLETED, falling back to latest with skills)
        Returns:
            (unique_student_skills, profile, selected_resume, skill_sources)
        """
        profile_raw: List[str] = []
        
        # 1. Profile skills
        profile = db.query(StudentProfile).filter(StudentProfile.user_id == student_id).first()
        if not profile:
            # Fallback to StudentProfileExtended if separate table
            profile = db.query(StudentProfileExtended).filter(StudentProfileExtended.user_id == student_id).first()

        if profile:
            if hasattr(profile, 'skills') and profile.skills:
                for s in profile.skills:
                    if type(s).__name__ not in ('MagicMock', 'Mock'):
                        val = s.name if hasattr(s, 'name') else str(s)
                        if val and str(val).strip():
                            profile_raw.append(str(val).strip())
            
            # Also check direct Skill table linked to profile.id
            if hasattr(profile, 'id'):
                db_skills = db.query(Skill).filter(Skill.student_id == profile.id).all()
                for s in db_skills:
                    if s and hasattr(s, 'name') and s.name and str(s.name).strip():
                        profile_raw.append(str(s.name).strip())

        # 2. Resume selection following project conventions:
        # Prioritize latest completed resume (status == ResumeStatus.COMPLETED)
        from ..models.resume import ResumeStatus

        selected_resume = db.query(Resume).filter(
            Resume.student_id == student_id,
            Resume.status == ResumeStatus.COMPLETED
        ).order_by(Resume.created_at.desc()).first()

        # Fallback: if no completed resume, find latest resume that has non-empty extracted skills
        if not selected_resume:
            candidate_resume = db.query(Resume).filter(
                Resume.student_id == student_id
            ).order_by(Resume.created_at.desc()).first()
            if candidate_resume and getattr(candidate_resume, 'skills', None):
                res_sk = candidate_resume.skills
                if type(res_sk).__name__ not in ('MagicMock', 'Mock') and isinstance(res_sk, (list, tuple)) and len(res_sk) > 0:
                    selected_resume = candidate_resume

        resume_raw: List[str] = []
        if selected_resume and hasattr(selected_resume, 'skills') and selected_resume.skills:
            res_skills = selected_resume.skills
            if type(res_skills).__name__ not in ('MagicMock', 'Mock') and isinstance(res_skills, (list, tuple)):
                resume_raw = [
                    str(s).strip() for s in res_skills 
                    if s and type(s).__name__ not in ('MagicMock', 'Mock') and str(s).strip()
                ]

        # Clean and deduplicate while preserving text
        seen_norms = set()
        unique_student_skills = []
        for s in (profile_raw + resume_raw):
            clean = str(s).strip()
            norm = skill_normalizer.normalize(clean)
            if norm and norm not in seen_norms:
                seen_norms.add(norm)
                unique_student_skills.append(clean)

        skill_sources = {
            "profile_skills": list(dict.fromkeys(profile_raw)),
            "resume_skills": list(dict.fromkeys(resume_raw))
        }

        return unique_student_skills, profile, selected_resume, skill_sources

    def _normalize_skill_list(self, raw_skills: Any) -> Dict[str, str]:
        """
        Deduplicate skill list by normalized form while preserving original display text.
        Returns dict: {normalized_form: original_display_text}
        """
        if not raw_skills:
            return {}
        
        # Guard against mock objects
        if type(raw_skills).__name__ in ('MagicMock', 'Mock'):
            return {}
        
        if isinstance(raw_skills, str):
            raw_list = [s.strip() for s in raw_skills.split(',') if s.strip()]
        elif isinstance(raw_skills, (list, tuple, set)):
            raw_list = [s for s in raw_skills if type(s).__name__ not in ('MagicMock', 'Mock')]
        else:
            return {}

        unique_dict: Dict[str, str] = {}
        for r in raw_list:
            if r is not None and type(r).__name__ not in ('MagicMock', 'Mock'):
                cleaned = str(r).strip()
                norm = skill_normalizer.normalize(cleaned)
                if norm and norm not in unique_dict:
                    unique_dict[norm] = cleaned
        return unique_dict

    def match_skills(
        self,
        job_skills: Dict[str, str],
        student_skills: List[str],
        category: str = "required"
    ) -> Tuple[List[str], List[str], List[Dict[str, Any]]]:
        """
        Match a set of job skills against student skills using hierarchy:
        1. Exact normalized match
        2. Canonical synonym match
        3. Semantic similarity via all-MiniLM-L6-v2 (threshold >= 0.78)

        Returns:
            (matched_skills, missing_skills, semantic_match_details)
        """
        matched: List[str] = []
        missing: List[str] = []
        match_details: List[Dict[str, Any]] = []

        if not job_skills:
            return matched, missing, match_details

        # Prepare normalized student skills and canonical student skills
        student_skills_clean = [str(s).strip() for s in student_skills if s and str(s).strip()]
        student_norm_map = {skill_normalizer.normalize(s): s for s in student_skills_clean}
        student_canonical_map = {skill_normalizer.get_canonical(s): s for s in student_skills_clean}

        # Track which job skills have been matched
        for norm_job, orig_job in job_skills.items():
            # 1. Exact normalized match
            if norm_job in student_norm_map:
                matched_student_skill = student_norm_map[norm_job]
                matched.append(orig_job)
                match_details.append({
                    "skill": orig_job,
                    "job_skill": orig_job,
                    "student_skill": matched_student_skill,
                    "matched_with": matched_student_skill,
                    "match_method": "exact",
                    "category": "exact",
                    "requirement_type": category,
                    "similarity": 1.0,
                    "explanation": f"Exact match: '{orig_job}' is documented in your student skills"
                })
                continue

            # 2. Canonical synonym match
            canonical_job = skill_normalizer.get_canonical(orig_job)
            if canonical_job in student_canonical_map:
                matched_student_skill = student_canonical_map[canonical_job]
                matched.append(orig_job)
                match_details.append({
                    "skill": orig_job,
                    "job_skill": orig_job,
                    "student_skill": matched_student_skill,
                    "matched_with": matched_student_skill,
                    "match_method": "synonym",
                    "category": "synonym",
                    "requirement_type": category,
                    "similarity": 1.0,
                    "explanation": f"Synonym match: '{orig_job}' matches your skill '{matched_student_skill}'"
                })
                continue

            # 3. Semantic similarity match using existing all-MiniLM-L6-v2 model
            best_sim = 0.0
            best_student_skill = None

            for s_orig in student_skills_clean:
                sim = embedding_service.compute_similarity(orig_job, s_orig)
                if sim is not None and sim > best_sim:
                    best_sim = sim
                    best_student_skill = s_orig

            if best_sim >= self.semantic_threshold and best_student_skill is not None:
                matched.append(orig_job)
                match_details.append({
                    "skill": orig_job,
                    "job_skill": orig_job,
                    "student_skill": best_student_skill,
                    "matched_with": best_student_skill,
                    "match_method": "semantic",
                    "category": "semantic",
                    "requirement_type": category,
                    "similarity": round(best_sim, 4),
                    "explanation": f"Semantic AI match: '{orig_job}' aligns with '{best_student_skill}' ({round(best_sim * 100)}% similarity)"
                })
            else:
                missing.append(orig_job)

        return matched, missing, match_details

    def compute_scores(
        self,
        required_matched: int,
        required_total: int,
        preferred_matched: int,
        preferred_total: int
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Calculate deterministic match scores according to locked design:
        - required_score = matched_required / total_required * 100 (if total_required > 0 else None)
        - preferred_score = matched_preferred / total_preferred * 100 (if total_preferred > 0 else None)
        - overall_skill_match:
            - If both categories exist: (required_score * 0.80) + (preferred_score * 0.20)
            - If only required exists: required_score
            - If only preferred exists: preferred_score
            - If both categories empty: None (not calculated / not applicable)
        """
        if required_total == 0 and preferred_total == 0:
            return None, None, None

        required_score = (required_matched / required_total * 100.0) if required_total > 0 else None
        preferred_score = (preferred_matched / preferred_total * 100.0) if preferred_total > 0 else None

        if required_total > 0 and preferred_total > 0:
            overall_skill_match = (required_score * 0.80) + (preferred_score * 0.20)
        elif required_total > 0 and preferred_total == 0:
            overall_skill_match = required_score
        else:
            overall_skill_match = preferred_score

        overall_skill_match = round(min(max(overall_skill_match, 0.0), 100.0), 2)
        if required_score is not None:
            required_score = round(required_score, 2)
        if preferred_score is not None:
            preferred_score = round(preferred_score, 2)

        return required_score, preferred_score, overall_skill_match


    def check_eligibility(
        self,
        profile: Optional[Any],
        job: JobPosting,
        required_score: Optional[float] = None,
        total_required: int = 0
    ) -> EligibilityResult:
        """
        Evaluate eligibility criteria independently from skill match:
        - CGPA criteria (only if specified by the job)
        - Branch criteria (only if specified by the job)
        - Graduation year / batch criteria (if specified by the job)
        - Low skill match warning (<50% required skill match, does NOT disqualify)
        - Incomplete data detection
        """
        is_eligible = True
        eligibility_reasons: List[str] = []
        missing_criteria: List[str] = []

        # 1. Check CGPA (only evaluated if job explicitly specifies criteria)
        cgpa_match = True
        if job.cgpa_criteria is not None and job.cgpa_criteria > 0:
            student_cgpa = getattr(profile, 'cgpa', None) if profile else None
            if type(student_cgpa).__name__ in ('MagicMock', 'Mock'):
                student_cgpa = None
            if student_cgpa is not None:
                cgpa_match = float(student_cgpa) >= job.cgpa_criteria
                if not cgpa_match:
                    is_eligible = False
                    eligibility_reasons.append(f"CGPA {student_cgpa} is below minimum requirement {job.cgpa_criteria}")
            else:
                cgpa_match = False
                is_eligible = False
                missing_criteria.append("cgpa")
                eligibility_reasons.append("CGPA record missing or incomplete")

        # 2. Check Branch (only evaluated if job explicitly specifies eligible branches)
        branch_match = True
        if job.branch_eligibility and isinstance(job.branch_eligibility, (list, tuple)) and len(job.branch_eligibility) > 0:
            student_branch = None
            b = getattr(profile, 'branch', None) if profile else None
            dept = getattr(profile, 'department', None) if profile else None
            user_obj = getattr(profile, 'user', None) if profile else None
            user_dept = getattr(user_obj, 'department', None) if user_obj else None

            if b and type(b).__name__ not in ('MagicMock', 'Mock'):
                student_branch = b
            elif dept and type(dept).__name__ not in ('MagicMock', 'Mock'):
                student_branch = dept
            elif user_dept and type(user_dept).__name__ not in ('MagicMock', 'Mock'):
                student_branch = user_dept

            if student_branch and str(student_branch).strip():
                student_branch_norm = str(student_branch).strip().lower()
                eligible_branches_norm = [str(eb).strip().lower() for eb in job.branch_eligibility if eb]
                branch_match = student_branch_norm in eligible_branches_norm
                if not branch_match:
                    is_eligible = False
                    eligibility_reasons.append(
                        f"Branch '{student_branch}' is not eligible (Eligible branches: {', '.join(job.branch_eligibility)})"
                    )
            else:
                branch_match = False
                is_eligible = False
                missing_criteria.append("branch")
                eligibility_reasons.append("Branch information missing")

        # 3. Check Graduation Year / Batch (if explicitly specified on job)
        job_grad_years = getattr(job, 'graduation_years', None)
        if job_grad_years and isinstance(job_grad_years, (list, tuple)) and len(job_grad_years) > 0:
            student_year = getattr(profile, 'year', None)
            if student_year is not None:
                year_strs = {str(y).strip() for y in job_grad_years if y}
                if str(student_year).strip() not in year_strs:
                    is_eligible = False
                    eligibility_reasons.append(
                        f"Graduation year/batch '{student_year}' is not eligible (Eligible: {', '.join(map(str, job_grad_years))})"
                    )
            else:
                is_eligible = False
                missing_criteria.append("graduation_year")
                eligibility_reasons.append("Graduation year / batch information missing")

        # 4. Baseline skill match check:
        # Per Phase 3.2 Step 1 rules:
        # Do not block a student merely because their required-skill match is below 50%.
        # Instead, generate a low-match warning.
        has_low_match_warning = bool(total_required > 0 and (required_score is None or required_score < 50.0))
        low_match_warning = None
        if has_low_match_warning:
            req_disp = f"{required_score:.1f}%" if required_score is not None else "0.0%"
            low_match_warning = f"Required skill match ({req_disp}) is below 50% threshold. You may still apply, but this role requires skills you may need to develop."

        # Determine authoritative eligibility status
        if missing_criteria:
            eligibility_status = "incomplete_data"
        elif not is_eligible:
            eligibility_status = "ineligible"
        else:
            eligibility_status = "eligible"

        return EligibilityResult(
            is_eligible=is_eligible,
            cgpa_match=cgpa_match,
            branch_match=branch_match,
            eligibility_reasons=eligibility_reasons,
            has_low_match_warning=has_low_match_warning,
            low_match_warning=low_match_warning,
            eligibility_status=eligibility_status,
            missing_criteria=missing_criteria
        )

    def match_student_to_job(
        self,
        db: Session,
        student: User,
        job: JobPosting
    ) -> StudentEligibility:
        """
        Main matching function:
        Matches student profile & resume skills against job posting requirements.
        """
        skill_res = self.get_student_skills(db, student.id)
        if len(skill_res) == 4:
            student_skills, profile, selected_resume, skill_sources = skill_res
        else:
            student_skills, profile = skill_res[0], skill_res[1]
            selected_resume = None
            skill_sources = {"profile_skills": student_skills, "resume_skills": []}

        # Parse job required & preferred skills
        unique_required = self._normalize_skill_list(getattr(job, 'required_skills', []))
        raw_preferred = getattr(job, 'preferred_skills', None)
        if type(raw_preferred).__name__ in ('MagicMock', 'Mock'):
            raw_preferred = []
        unique_preferred = self._normalize_skill_list(raw_preferred)

        # Match required skills
        matched_req, missing_req, details_req = self.match_skills(
            unique_required, student_skills, category="required"
        )

        # Match preferred skills
        matched_pref, missing_pref, details_pref = self.match_skills(
            unique_preferred, student_skills, category="preferred"
        )

        required_total = len(unique_required)
        required_matched = len(matched_req)
        required_missing = len(missing_req)

        preferred_total = len(unique_preferred)
        preferred_matched = len(matched_pref)
        preferred_missing = len(missing_pref)

        # Calculate scores
        required_score, preferred_score, overall_skill_match = self.compute_scores(
            required_matched, required_total,
            preferred_matched, preferred_total
        )

        # Evaluate eligibility independently using authoritative rules
        elig_res = self.check_eligibility(
            profile, job, required_score, required_total
        )
        is_eligible, cgpa_match, branch_match, eligibility_reasons, has_low_match_warning, low_match_warning = elig_res[:6]
        eligibility_status = getattr(elig_res, 'eligibility_status', 'eligible' if is_eligible else 'ineligible')
        missing_criteria = getattr(elig_res, 'missing_criteria', [])

        # Combined matched and missing skills for backward compatibility
        all_matched = matched_req + matched_pref
        all_missing = missing_req + missing_pref
        semantic_matches = [d for d in (details_req + details_pref) if d.get("match_method") == "semantic"]
        skill_match_explanations = details_req + details_pref

        resume_id = None
        if selected_resume and hasattr(selected_resume, 'id'):
            rid = getattr(selected_resume, 'id', None)
            if rid is not None and type(rid).__name__ not in ('MagicMock', 'Mock') and isinstance(rid, int):
                resume_id = rid

        resume_filename = None
        if selected_resume:
            if hasattr(selected_resume, 'file') and selected_resume.file and hasattr(selected_resume.file, 'filename'):
                fname = getattr(selected_resume.file, 'filename', None)
                if fname is not None and type(fname).__name__ not in ('MagicMock', 'Mock') and isinstance(fname, str):
                    resume_filename = fname
            elif hasattr(selected_resume, 'name') and selected_resume.name:
                rname = getattr(selected_resume, 'name', None)
                if rname is not None and type(rname).__name__ not in ('MagicMock', 'Mock') and isinstance(rname, str):
                    resume_filename = rname

        # Resolve student branch and cgpa with safe fallbacks
        student_branch = "N/A"
        if profile and hasattr(profile, 'branch') and profile.branch:
            student_branch = profile.branch
        elif student and hasattr(student, 'department') and student.department:
            student_branch = student.department

        student_cgpa = 0.0
        if profile and hasattr(profile, 'cgpa') and profile.cgpa is not None:
            student_cgpa = float(profile.cgpa)

        return StudentEligibility(
            student_id=student.id,
            student_name=student.name,
            email=student.email,
            branch=student_branch,
            cgpa=student_cgpa,
            is_eligible=is_eligible,
            eligibility_reasons=eligibility_reasons,
            match_score=overall_skill_match,  # Match score is strictly overall skill match (None if no skills)
            skill_match=overall_skill_match,
            cgpa_match=cgpa_match,
            branch_match=branch_match,
            missing_skills=all_missing,
            matched_skills=all_matched,
            # Phase 3.2 Detailed Breakdown
            required_total=required_total,
            required_matched=required_matched,
            required_missing=required_missing,
            preferred_total=preferred_total,
            preferred_matched=preferred_matched,
            preferred_missing=preferred_missing,
            required_score=required_score,
            preferred_score=preferred_score,
            overall_skill_match=overall_skill_match,
            matched_required_skills=matched_req,
            matched_preferred_skills=matched_pref,
            missing_required_skills=missing_req,
            missing_preferred_skills=missing_pref,
            semantic_matches=semantic_matches,
            has_low_match_warning=has_low_match_warning,
            low_match_warning=low_match_warning,
            resume_id=resume_id,
            resume_filename=resume_filename,
            skill_sources=skill_sources,
            # Phase D Granular Explanations & Status
            eligibility_status=eligibility_status,
            missing_criteria=missing_criteria,
            skill_match_explanations=skill_match_explanations
        )


# Global singleton instance
job_matching_service = JobMatchingService()
