"""
Safe Placement Test-Data Cleanup Service (Phase 3.4.1)

Provides preview-first candidate inspection, dependency analysis,
safety validation, and transactional cleanup (archive or purge)
with strict placement-history and storage protection.
"""

import logging
import re
from typing import List, Optional, Dict, Any, Set, Tuple
from uuid import UUID
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from ..models.company import Company
from ..models.job_posting import JobPosting, JobStatus
from ..models.recruitment_circular import (
    RecruitmentCircular,
    RecruitmentCircularAttachment,
    RecruitmentCircularJob,
    RecruitmentCircularStatus,
)
from ..models.application import Application, ApplicationStatus
from ..models.shortlist import Shortlist
from ..models.recruitment_round import (
    RecruitmentRound,
    StudentRoundOutcome,
    PlacementOffer,
    RoundOutcome,
    OfferAcceptanceStatus,
)
from ..models.recruitment_result import (
    RecruitmentResultBatch,
    RecruitmentResultItem,
    RecruitmentResultBatchStatus,
    RecruitmentResultReviewState,
)
from ..models.profile import StudentProfileExtended, PlacementStatus
from ..models.user import User, UserRole
from ..models.file import File
from ..models.circular import Circular  # Academic circulars
from ..models.resume import Resume
from ..models.notification import Notification
from ..models.audit_log import AuditLog
from ..services.audit_service import audit_service
from ..services.file_storage.minio_client import minio_client

logger = logging.getLogger(__name__)

# Pattern signals for candidate test records
TEST_PATTERNS = [
    re.compile(r"\b(test|mock|temp|dummy|sample)\b", re.IGNORECASE),
    re.compile(r"\b\d{10,13}\b"),  # Millisecond timestamps
    re.compile(r"\b\d{6,}\b"),     # General timestamps
]

TEST_STUDENT_PATTERNS = [
    re.compile(r"(test|mock|temp|student_a_|student_b_|multi_offer_)", re.IGNORECASE),
    re.compile(r"\b\d{10,13}\b"),
]


class PlacementCleanupService:
    """Service for safe preview, dependency analysis, and execution of recruitment cleanup."""

    @staticmethod
    def is_candidate_test_name(name: str) -> bool:
        """Evaluate whether a company name contains automated test signals."""
        if not name:
            return False
        return any(pattern.search(name) for pattern in TEST_PATTERNS)

    @staticmethod
    def is_candidate_test_drive(circular: RecruitmentCircular) -> bool:
        """Evaluate whether a recruitment circular contains automated test signals."""
        if not circular:
            return False
        if circular.title and any(pattern.search(circular.title) for pattern in TEST_PATTERNS):
            return True
        if circular.company and any(pattern.search(circular.company.name) for pattern in TEST_PATTERNS):
            return True
        return False

    @staticmethod
    def is_test_student_email(email: str) -> bool:
        """Evaluate whether a student email indicates a synthetic test account."""
        if not email:
            return False
        return any(pattern.search(email) for pattern in TEST_STUDENT_PATTERNS)

    def generate_cleanup_preview(
        self,
        db: Session,
        company_ids: Optional[List[int]] = None,
        circular_ids: Optional[List[int]] = None,
        pattern: Optional[str] = None,
        include_all_candidates: bool = True,
    ) -> Dict[str, Any]:
        """
        Preview candidate companies or recruitment drives for cleanup without modifying any data.
        Returns detailed dependent-record counts, safety classifications, and protection reasons.
        """
        if circular_ids and len(circular_ids) > 0:
            return self.generate_drives_cleanup_preview(
                db=db,
                circular_ids=circular_ids,
                include_all_candidates=include_all_candidates,
            )

        # Query target companies
        query = db.query(Company)
        if company_ids and len(company_ids) > 0:
            query = query.filter(Company.id.in_(company_ids))
        elif pattern and pattern.strip():
            query = query.filter(Company.name.ilike(f"%{pattern.strip()}%"))
        elif include_all_candidates:
            # Load companies to evaluate test signals
            all_comps = db.query(Company).order_by(Company.id.desc()).all()
            candidate_comps = [c for c in all_comps if self.is_candidate_test_name(c.name)]
            return self._build_preview_response(db, candidate_comps)
        else:
            return self._build_preview_response(db, [])

        target_companies = query.order_by(Company.id.desc()).all()
        return self._build_preview_response(db, target_companies)

    def generate_drives_cleanup_preview(
        self,
        db: Session,
        circular_ids: Optional[List[int]] = None,
        status: Optional[str] = None,
        include_all_candidates: bool = True,
    ) -> Dict[str, Any]:
        """Preview recruitment drives for cleanup without mutating any records."""
        query = db.query(RecruitmentCircular)
        if circular_ids and len(circular_ids) > 0:
            query = query.filter(RecruitmentCircular.id.in_(circular_ids))
        elif status and status.lower() != "all":
            query = query.filter(RecruitmentCircular.status == status.lower())
            if include_all_candidates:
                all_status_circs = query.order_by(RecruitmentCircular.id.desc()).all()
                target_circulars = [c for c in all_status_circs if self.is_candidate_test_drive(c)]
                return self._build_drives_preview_response(db, target_circulars)
        elif include_all_candidates:
            all_circs = db.query(RecruitmentCircular).order_by(RecruitmentCircular.id.desc()).all()
            candidate_circs = [c for c in all_circs if self.is_candidate_test_drive(c)]
            return self._build_drives_preview_response(db, candidate_circs)
        else:
            return self._build_drives_preview_response(db, [])

        target_circulars = query.order_by(RecruitmentCircular.id.desc()).all()
        return self._build_drives_preview_response(db, target_circulars)

    def _build_drives_preview_response(
        self, db: Session, circulars: List[RecruitmentCircular]
    ) -> Dict[str, Any]:
        """Analyze dependencies and build the preview payload for a set of recruitment drives."""
        drives: List[Dict[str, Any]] = []

        total_drives_safe_to_purge = 0
        total_drives_requires_archive = 0
        total_drives_protected_genuine = 0

        total_dependent_jobs = 0
        total_dependent_applications = 0
        total_dependent_result_batches = 0
        total_dependent_offers = 0
        total_dependent_accepted_offers = 0
        total_files_identified = 0
        total_shared_files_preserved = 0

        for circ in circulars:
            drive_analysis = self._analyze_drive_dependencies(db, circ)
            drives.append(drive_analysis)

            counts = drive_analysis["dependent_counts"]
            total_dependent_jobs += counts["jobs_count"]
            total_dependent_applications += counts["applications_count"]
            total_dependent_result_batches += counts["result_batches_count"]
            total_dependent_offers += counts["offers_count"]
            total_dependent_accepted_offers += counts["accepted_offers_count"]
            total_files_identified += counts["files_count"]
            total_shared_files_preserved += counts["shared_files_count"]

            classification = drive_analysis["safety_classification"]
            if classification == "SAFE_TO_PURGE":
                total_drives_safe_to_purge += 1
            elif classification == "REQUIRES_ARCHIVE":
                total_drives_requires_archive += 1
            else:
                total_drives_protected_genuine += 1

        orphaned_jobs = self._find_orphaned_jobs(db)

        summary = {
            "total_candidates_flagged": len(drives),
            "total_safe_to_purge": total_drives_safe_to_purge,
            "total_requires_archive": total_drives_requires_archive,
            "total_protected_genuine": total_drives_protected_genuine,
            "total_dependent_jobs": total_dependent_jobs,
            "total_dependent_circulars": len(drives),
            "total_dependent_applications": total_dependent_applications,
            "total_dependent_result_batches": total_dependent_result_batches,
            "total_dependent_offers": total_dependent_offers,
            "total_dependent_accepted_offers": total_dependent_accepted_offers,
            "total_files_identified": total_files_identified,
            "total_shared_files_preserved": total_shared_files_preserved,
            "total_drives_flagged": len(drives),
            "total_drives_safe_to_purge": total_drives_safe_to_purge,
            "total_drives_requires_archive": total_drives_requires_archive,
            "total_drives_protected_genuine": total_drives_protected_genuine,
            "total_orphaned_jobs": len(orphaned_jobs),
        }

        return {
            "summary": summary,
            "drives": drives,
            "orphaned_jobs": orphaned_jobs,
            "candidates": [],
        }

    def _build_preview_response(
        self, db: Session, companies: List[Company]
    ) -> Dict[str, Any]:
        """Analyze dependencies and build the preview payload for a set of companies."""
        candidates: List[Dict[str, Any]] = []

        total_safe_to_purge = 0
        total_requires_archive = 0
        total_protected_genuine = 0

        total_dependent_jobs = 0
        total_dependent_circulars = 0
        total_dependent_applications = 0
        total_dependent_result_batches = 0
        total_dependent_offers = 0
        total_dependent_accepted_offers = 0
        total_files_identified = 0
        total_shared_files_preserved = 0

        for comp in companies:
            comp_analysis = self._analyze_company_dependencies(db, comp)
            candidates.append(comp_analysis)

            # Update summaries
            counts = comp_analysis["dependent_counts"]
            total_dependent_jobs += counts["jobs_count"]
            total_dependent_circulars += counts["circulars_count"]
            total_dependent_applications += counts["applications_count"]
            total_dependent_result_batches += counts["result_batches_count"]
            total_dependent_offers += counts["offers_count"]
            total_dependent_accepted_offers += counts["accepted_offers_count"]
            total_files_identified += counts["files_count"]
            total_shared_files_preserved += counts["shared_files_count"]

            classification = comp_analysis["safety_classification"]
            if classification == "SAFE_TO_PURGE":
                total_safe_to_purge += 1
            elif classification == "REQUIRES_ARCHIVE":
                total_requires_archive += 1
            else:
                total_protected_genuine += 1

        summary = {
            "total_candidates_flagged": len(candidates),
            "total_safe_to_purge": total_safe_to_purge,
            "total_requires_archive": total_requires_archive,
            "total_protected_genuine": total_protected_genuine,
            "total_dependent_jobs": total_dependent_jobs,
            "total_dependent_circulars": total_dependent_circulars,
            "total_dependent_applications": total_dependent_applications,
            "total_dependent_result_batches": total_dependent_result_batches,
            "total_dependent_offers": total_dependent_offers,
            "total_dependent_accepted_offers": total_dependent_accepted_offers,
            "total_files_identified": total_files_identified,
            "total_shared_files_preserved": total_shared_files_preserved,
        }

        return {
            "summary": summary,
            "candidates": candidates,
        }

    def _analyze_company_dependencies(
        self, db: Session, comp: Company
    ) -> Dict[str, Any]:
        """Perform thorough dependency and safety analysis on a single company."""
        flag_reasons = []
        if self.is_candidate_test_name(comp.name):
            if re.search(r"\b\d{6,}\b", comp.name):
                flag_reasons.append("Contains automated test timestamp suffix")
            if re.search(r"\b(test|mock|temp|dummy|sample)\b", comp.name, re.IGNORECASE):
                flag_reasons.append("Contains test/mock/sample keyword")
        else:
            flag_reasons.append("Identified via explicit search or query selection")

        # 1. Job Postings
        jobs = db.query(JobPosting).filter(JobPosting.company_id == comp.id).all()
        job_ids = [j.id for j in jobs]
        jobs_count = len(jobs)
        linked_job_titles = [j.title for j in jobs]

        # 2. Circulars & Links
        circulars = db.query(RecruitmentCircular).filter(RecruitmentCircular.company_id == comp.id).all()
        circular_ids = [c.id for c in circulars]
        circulars_count = len(circulars)
        linked_circular_titles = [c.title for c in circulars]

        circular_job_links_count = 0
        if circular_ids or job_ids:
            circular_job_links_count = db.query(RecruitmentCircularJob).filter(
                or_(
                    RecruitmentCircularJob.circular_id.in_(circular_ids) if circular_ids else False,
                    RecruitmentCircularJob.job_posting_id.in_(job_ids) if job_ids else False,
                )
            ).count()

        # 3. Applications & Shortlists
        applications_count = 0
        application_ids = []
        student_ids_set: Set[int] = set()

        if job_ids:
            apps = db.query(Application).filter(Application.job_posting_id.in_(job_ids)).all()
            applications_count = len(apps)
            application_ids = [a.id for a in apps]
            for a in apps:
                student_ids_set.add(a.student_id)

        shortlists_count = db.query(Shortlist).filter(Shortlist.company_id == comp.id).count()

        # 4. Recruitment Rounds & Outcomes
        rounds_count = 0
        round_ids = []
        if job_ids:
            rounds = db.query(RecruitmentRound).filter(RecruitmentRound.job_posting_id.in_(job_ids)).all()
            rounds_count = len(rounds)
            round_ids = [r.id for r in rounds]

        outcomes_count = 0
        confirmed_outcomes_count = 0
        if round_ids:
            outcomes = db.query(StudentRoundOutcome).filter(StudentRoundOutcome.round_id.in_(round_ids)).all()
            outcomes_count = len(outcomes)
            confirmed_outcomes_count = sum(1 for o in outcomes if o.outcome != RoundOutcome.REJECTED)
            for o in outcomes:
                student_ids_set.add(o.student_id)

        # 5. Result Batches & Items
        batches = db.query(RecruitmentResultBatch).filter(RecruitmentResultBatch.company_id == comp.id).all()
        batch_ids = [b.id for b in batches]
        result_batches_count = len(batches)

        result_items_count = 0
        confirmed_result_items_count = 0
        if batch_ids:
            items = db.query(RecruitmentResultItem).filter(RecruitmentResultItem.batch_id.in_(batch_ids)).all()
            result_items_count = len(items)
            confirmed_result_items_count = sum(
                1 for i in items if i.review_status == RecruitmentResultReviewState.CONFIRMED
            )
            for i in items:
                if i.matched_student_id:
                    student_ids_set.add(i.matched_student_id)

        # 6. Placement Offers
        offers_count = 0
        accepted_offers_count = 0
        active_offers_count = 0
        offer_ids = []
        if job_ids:
            offers = db.query(PlacementOffer).filter(PlacementOffer.job_posting_id.in_(job_ids)).all()
            offers_count = len(offers)
            offer_ids = [o.id for o in offers]
            accepted_offers_count = sum(
                1 for o in offers if o.acceptance_status == OfferAcceptanceStatus.ACCEPTED
            )
            active_offers_count = sum(
                1 for o in offers if o.acceptance_status in [
                    OfferAcceptanceStatus.OFFERED,
                    OfferAcceptanceStatus.ACCEPTED
                ]
            )
            for o in offers:
                student_ids_set.add(o.student_id)

        # 7. File References & Shared Checks
        candidate_file_ids: Set[UUID] = set()

        # Batch files
        for b in batches:
            if b.file_id:
                candidate_file_ids.add(b.file_id)

        # Circular attachment files
        if circular_ids:
            att_files = db.query(RecruitmentCircularAttachment.file_id).filter(
                RecruitmentCircularAttachment.circular_id.in_(circular_ids)
            ).all()
            for (fid,) in att_files:
                if fid:
                    candidate_file_ids.add(fid)

        # Offer letter files
        if job_ids:
            offer_files = db.query(PlacementOffer.offer_letter_file_id).filter(
                PlacementOffer.job_posting_id.in_(job_ids),
                PlacementOffer.offer_letter_file_id.isnot(None),
            ).all()
            for (fid,) in offer_files:
                if fid:
                    candidate_file_ids.add(fid)

        files_count = len(candidate_file_ids)
        shared_files_count = 0

        for fid in candidate_file_ids:
            if self._is_file_shared_outside_context(
                db, fid, excluded_company_ids=[comp.id], excluded_circular_ids=circular_ids, excluded_job_ids=job_ids
            ):
                shared_files_count += 1

        # 8. Student Genuine Account Check
        has_genuine_student_impact = False
        genuine_student_emails = []
        if student_ids_set:
            students = db.query(User).filter(User.id.in_(list(student_ids_set))).all()
            for s in students:
                if not self.is_test_student_email(s.email):
                    has_genuine_student_impact = True
                    genuine_student_emails.append(s.email)

        # 9. Safety Classification & Protection Reasons
        protection_reasons = []

        if accepted_offers_count > 0:
            protection_reasons.append(
                f"Contains {accepted_offers_count} student-accepted placement offer(s) (institutional placement record)"
            )

        if active_offers_count > 0 and accepted_offers_count == 0:
            protection_reasons.append(
                f"Contains {active_offers_count} active pending offer(s) awaiting student response"
            )

        if has_genuine_student_impact:
            protection_reasons.append(
                f"Tied to {len(genuine_student_emails)} genuine student account(s) ({', '.join(genuine_student_emails[:3])})"
            )

        if shared_files_count > 0:
            protection_reasons.append(
                f"References {shared_files_count} file(s) shared with other system records (protected from deletion)"
            )

        # Check if any job of this company is referenced by a drive belonging to another company
        external_circular_links = []
        if job_ids:
            external_circular_links = db.query(RecruitmentCircularJob, RecruitmentCircular).join(
                RecruitmentCircular, RecruitmentCircularJob.circular_id == RecruitmentCircular.id
            ).filter(
                RecruitmentCircularJob.job_posting_id.in_(job_ids),
                RecruitmentCircular.company_id != comp.id,
            ).all()
        if external_circular_links:
            ext_drive_titles = [c.title for _, c in external_circular_links]
            protection_reasons.append(
                f"Contains job(s) referenced by other company drive(s): {', '.join(ext_drive_titles[:2])}"
            )

        if not self.is_candidate_test_name(comp.name):
            protection_reasons.append(
                "Company name lacks test/timestamp patterns and appears genuine"
            )

        # Classification decision
        if external_circular_links:
            safety_classification = "REQUIRES_ARCHIVE"
        elif accepted_offers_count > 0 or has_genuine_student_impact:
            if not self.is_candidate_test_name(comp.name):
                safety_classification = "PROTECTED_GENUINE"
            else:
                safety_classification = "REQUIRES_ARCHIVE"
        elif active_offers_count > 0 or confirmed_outcomes_count > 0 or not self.is_candidate_test_name(comp.name):
            safety_classification = "REQUIRES_ARCHIVE"
        else:
            safety_classification = "SAFE_TO_PURGE"

        records_breakdown = {
            "companies_to_delete": 1,
            "jobs_to_delete": jobs_count,
            "circulars_to_delete": circulars_count,
            "applications_to_delete": applications_count,
            "rounds_to_delete": rounds_count,
            "outcomes_to_delete": outcomes_count,
            "batches_to_delete": result_batches_count,
            "result_items_to_delete": result_items_count,
            "offers_to_delete": offers_count,
            "files_to_delete": max(0, files_count - shared_files_count),
            "shared_files_preserved": shared_files_count,
            "companies_to_archive": 1,
            "jobs_to_close": jobs_count,
            "circulars_to_archive": circulars_count,
            "batches_to_archive": result_batches_count,
        }

        return {
            "company_id": comp.id,
            "company_name": comp.name,
            "is_active": bool(comp.is_active),
            "flag_reasons": flag_reasons,
            "dependent_counts": {
                "jobs_count": jobs_count,
                "circulars_count": circulars_count,
                "circular_job_links_count": circular_job_links_count,
                "applications_count": applications_count,
                "shortlists_count": shortlists_count,
                "rounds_count": rounds_count,
                "outcomes_count": outcomes_count,
                "confirmed_outcomes_count": confirmed_outcomes_count,
                "result_batches_count": result_batches_count,
                "result_items_count": result_items_count,
                "confirmed_result_items_count": confirmed_result_items_count,
                "offers_count": offers_count,
                "accepted_offers_count": accepted_offers_count,
                "active_offers_count": active_offers_count,
                "files_count": files_count,
                "shared_files_count": shared_files_count,
            },
            "safety_classification": safety_classification,
            "protection_reasons": protection_reasons,
            "affected_student_count": len(student_ids_set),
            "can_purge": safety_classification == "SAFE_TO_PURGE",
            "linked_job_titles": linked_job_titles,
            "linked_circular_titles": linked_circular_titles,
            "records_breakdown": records_breakdown,
        }

    def _is_file_shared_outside_context(
        self,
        db: Session,
        file_id: UUID,
        excluded_company_ids: List[int],
        excluded_circular_ids: List[int],
        excluded_job_ids: List[int],
    ) -> bool:
        """
        Check if a file UUID is referenced anywhere outside of the specified company/circular/job scope.
        Protects resumes, academic circulars, other batches, and other companies.
        """
        # 1. Resumes
        if db.query(Resume).filter(Resume.file_id == file_id).first():
            return True

        # 2. Academic Circulars
        if db.query(Circular).filter(Circular.file_id == file_id).first():
            return True

        # 3. Other Recruitment Circular Attachments
        if db.query(RecruitmentCircularAttachment).filter(
            RecruitmentCircularAttachment.file_id == file_id,
            RecruitmentCircularAttachment.circular_id.notin_(excluded_circular_ids) if excluded_circular_ids else True,
        ).first():
            return True

        # 4. Other Result Batches
        if db.query(RecruitmentResultBatch).filter(
            RecruitmentResultBatch.file_id == file_id,
            RecruitmentResultBatch.company_id.notin_(excluded_company_ids) if excluded_company_ids else True,
        ).first():
            return True

        # 5. Other Placement Offers
        if db.query(PlacementOffer).filter(
            PlacementOffer.offer_letter_file_id == file_id,
            PlacementOffer.job_posting_id.notin_(excluded_job_ids) if excluded_job_ids else True,
        ).first():
            return True

        return False

    def _analyze_drive_dependencies(
        self, db: Session, circular: RecruitmentCircular
    ) -> Dict[str, Any]:
        """Perform thorough dependency and safety analysis on a single recruitment drive."""
        flag_reasons = []
        is_test_drive = self.is_candidate_test_drive(circular)
        if is_test_drive:
            if circular.title and any(pattern.search(circular.title) for pattern in TEST_PATTERNS):
                flag_reasons.append("Drive title contains test/mock/timestamp patterns")
            if circular.company and any(pattern.search(circular.company.name) for pattern in TEST_PATTERNS):
                flag_reasons.append("Associated company contains test/mock signals")
        else:
            flag_reasons.append("Identified via explicit drive selection")

        status_str = circular.status.value if hasattr(circular.status, "value") else str(circular.status)
        if status_str.lower() == "draft":
            flag_reasons.append("Drive is currently in Draft status")

        # 1. Linked Job Postings via junction
        links = db.query(RecruitmentCircularJob).filter(
            RecruitmentCircularJob.circular_id == circular.id
        ).all()
        linked_job_ids = [l.job_posting_id for l in links]
        jobs = db.query(JobPosting).filter(JobPosting.id.in_(linked_job_ids)).all() if linked_job_ids else []
        linked_job_titles = [j.title for j in jobs]
        jobs_count = len(jobs)
        circular_job_links_count = len(links)

        # Identify which linked jobs are shared with other circulars
        shared_job_ids: List[int] = []
        exclusive_job_ids: List[int] = []
        for jid in linked_job_ids:
            other_circulars_count = db.query(RecruitmentCircularJob).filter(
                RecruitmentCircularJob.job_posting_id == jid,
                RecruitmentCircularJob.circular_id != circular.id,
            ).count()
            if other_circulars_count > 0:
                shared_job_ids.append(jid)
            else:
                exclusive_job_ids.append(jid)

        jobs_by_id = {j.id: j.title for j in jobs}
        exclusive_job_roles = [jobs_by_id.get(jid, f"Role #{jid}") for jid in exclusive_job_ids]
        shared_job_roles = [jobs_by_id.get(jid, f"Role #{jid}") for jid in shared_job_ids]

        # 2. Applications & Shortlists
        applications_count = 0
        student_ids_set: Set[int] = set()

        if linked_job_ids:
            apps = db.query(Application).filter(Application.job_posting_id.in_(linked_job_ids)).all()
            applications_count = len(apps)
            for a in apps:
                student_ids_set.add(a.student_id)

        shortlists_count = 0
        if linked_job_ids:
            shortlists_count = db.query(Shortlist).filter(Shortlist.job_posting_id.in_(linked_job_ids)).count()

        # 3. Recruitment Rounds & Outcomes
        rounds_count = 0
        round_ids = []
        if linked_job_ids:
            rounds = db.query(RecruitmentRound).filter(RecruitmentRound.job_posting_id.in_(linked_job_ids)).all()
            rounds_count = len(rounds)
            round_ids = [r.id for r in rounds]

        outcomes_count = 0
        confirmed_outcomes_count = 0
        if round_ids:
            outcomes = db.query(StudentRoundOutcome).filter(StudentRoundOutcome.round_id.in_(round_ids)).all()
            outcomes_count = len(outcomes)
            confirmed_outcomes_count = sum(1 for o in outcomes if o.outcome != RoundOutcome.REJECTED)
            for o in outcomes:
                student_ids_set.add(o.student_id)

        # 4. Result Batches & Items
        batches = []
        if linked_job_ids:
            batches = db.query(RecruitmentResultBatch).filter(
                RecruitmentResultBatch.job_posting_id.in_(linked_job_ids)
            ).all()
        batch_ids = [b.id for b in batches]
        result_batches_count = len(batches)

        result_items_count = 0
        confirmed_result_items_count = 0
        if batch_ids:
            items = db.query(RecruitmentResultItem).filter(RecruitmentResultItem.batch_id.in_(batch_ids)).all()
            result_items_count = len(items)
            confirmed_result_items_count = sum(
                1 for i in items if i.review_status == RecruitmentResultReviewState.CONFIRMED
            )
            for i in items:
                if i.matched_student_id:
                    student_ids_set.add(i.matched_student_id)

        # 5. Placement Offers
        offers_count = 0
        accepted_offers_count = 0
        active_offers_count = 0
        if linked_job_ids:
            offers = db.query(PlacementOffer).filter(PlacementOffer.job_posting_id.in_(linked_job_ids)).all()
            offers_count = len(offers)
            accepted_offers_count = sum(
                1 for o in offers if o.acceptance_status == OfferAcceptanceStatus.ACCEPTED
            )
            active_offers_count = sum(
                1 for o in offers if o.acceptance_status in [
                    OfferAcceptanceStatus.OFFERED,
                    OfferAcceptanceStatus.ACCEPTED,
                ]
            )
            for o in offers:
                student_ids_set.add(o.student_id)

        # 6. File References & Shared Checks
        candidate_file_ids: Set[UUID] = set()

        # Circular attachments
        att_files = db.query(RecruitmentCircularAttachment.file_id).filter(
            RecruitmentCircularAttachment.circular_id == circular.id
        ).all()
        for (fid,) in att_files:
            if fid:
                candidate_file_ids.add(fid)

        # Batch files
        for b in batches:
            if b.file_id:
                candidate_file_ids.add(b.file_id)

        # Offer letters
        if linked_job_ids:
            offer_files = db.query(PlacementOffer.offer_letter_file_id).filter(
                PlacementOffer.job_posting_id.in_(linked_job_ids),
                PlacementOffer.offer_letter_file_id.isnot(None),
            ).all()
            for (fid,) in offer_files:
                if fid:
                    candidate_file_ids.add(fid)

        files_count = len(candidate_file_ids)
        shared_files_count = 0
        for fid in candidate_file_ids:
            if self._is_file_shared_outside_context(
                db, fid,
                excluded_company_ids=[circular.company_id] if circular.company_id else [],
                excluded_circular_ids=[circular.id],
                excluded_job_ids=exclusive_job_ids,
            ):
                shared_files_count += 1

        # 7. Genuine Student Account Check
        has_genuine_student_impact = False
        genuine_student_emails = []
        if student_ids_set:
            students = db.query(User).filter(User.id.in_(list(student_ids_set))).all()
            for s in students:
                if not self.is_test_student_email(s.email):
                    has_genuine_student_impact = True
                    genuine_student_emails.append(s.email)

        # 8. Protection Reasons & Safety Classification
        protection_reasons = []

        if accepted_offers_count > 0:
            protection_reasons.append(
                f"Contains {accepted_offers_count} student-accepted placement offer(s) (institutional placement record)"
            )

        if active_offers_count > 0 and accepted_offers_count == 0:
            protection_reasons.append(
                f"Contains {active_offers_count} active pending offer(s) awaiting student response"
            )

        if has_genuine_student_impact:
            protection_reasons.append(
                f"Tied to {len(genuine_student_emails)} genuine student account(s) ({', '.join(genuine_student_emails[:3])})"
            )

        if confirmed_outcomes_count > 0:
            protection_reasons.append(
                f"Contains {confirmed_outcomes_count} confirmed round progression outcome(s)"
            )

        if confirmed_result_items_count > 0:
            protection_reasons.append(
                f"Contains {confirmed_result_items_count} confirmed result item(s)"
            )

        if shared_files_count > 0:
            protection_reasons.append(
                f"References {shared_files_count} file(s) shared with other system records (protected from deletion)"
            )

        if len(shared_job_ids) > 0:
            protection_reasons.append(
                f"Shares {len(shared_job_ids)} role(s) with other drives (role will be unlinked, not deleted)"
            )

        if not is_test_drive and status_str.lower() != "draft":
            protection_reasons.append(
                "Drive title and company appear genuine"
            )

        # Classification decision
        if accepted_offers_count > 0 or has_genuine_student_impact:
            if not is_test_drive:
                safety_classification = "PROTECTED_GENUINE"
            else:
                safety_classification = "REQUIRES_ARCHIVE"
        elif active_offers_count > 0 or confirmed_outcomes_count > 0 or confirmed_result_items_count > 0 or (not is_test_drive and status_str.lower() != "draft"):
            safety_classification = "REQUIRES_ARCHIVE"
        else:
            safety_classification = "SAFE_TO_PURGE"

        return {
            "circular_id": circular.id,
            "title": circular.title,
            "status": status_str,
            "company_id": circular.company_id,
            "company_name": circular.company.name if circular.company else "Unknown Company",
            "drive_date": circular.drive_date,
            "created_at": circular.created_at,
            "flag_reasons": flag_reasons,
            "linked_job_ids": linked_job_ids,
            "linked_job_titles": linked_job_titles,
            "dependent_counts": {
                "jobs_count": jobs_count,
                "circulars_count": 1,
                "circular_job_links_count": circular_job_links_count,
                "applications_count": applications_count,
                "shortlists_count": shortlists_count,
                "rounds_count": rounds_count,
                "outcomes_count": outcomes_count,
                "confirmed_outcomes_count": confirmed_outcomes_count,
                "result_batches_count": result_batches_count,
                "result_items_count": result_items_count,
                "confirmed_result_items_count": confirmed_result_items_count,
                "offers_count": offers_count,
                "accepted_offers_count": accepted_offers_count,
                "active_offers_count": active_offers_count,
                "files_count": files_count,
                "shared_files_count": shared_files_count,
            },
            "safety_classification": safety_classification,
            "protection_reasons": protection_reasons,
            "affected_student_count": len(student_ids_set),
            "can_purge": safety_classification == "SAFE_TO_PURGE",
            "exclusive_job_roles": exclusive_job_roles,
            "shared_job_roles": shared_job_roles,
        }

    def _find_orphaned_jobs(self, db: Session) -> List[Dict[str, Any]]:
        """Identify test-generated jobs not linked to any recruitment circular."""
        linked_job_ids_subq = db.query(RecruitmentCircularJob.job_posting_id).distinct()
        unlinked_jobs = db.query(JobPosting).filter(
            ~JobPosting.id.in_(linked_job_ids_subq)
        ).all()

        orphaned_candidates: List[Dict[str, Any]] = []
        for job in unlinked_jobs:
            is_test_job = (
                any(pattern.search(job.title or "") for pattern in TEST_PATTERNS) or
                (job.company and any(pattern.search(job.company.name or "") for pattern in TEST_PATTERNS))
            )
            if not is_test_job and job.status != JobStatus.DRAFT:
                continue

            apps_count = db.query(Application).filter(Application.job_posting_id == job.id).count()
            offers = db.query(PlacementOffer).filter(PlacementOffer.job_posting_id == job.id).all()
            accepted_offers = sum(1 for o in offers if o.acceptance_status == OfferAcceptanceStatus.ACCEPTED)

            protection_reasons = []
            if accepted_offers > 0:
                safety_classification = "PROTECTED_GENUINE"
                protection_reasons.append("Job has accepted offers")
            elif apps_count > 0:
                safety_classification = "REQUIRES_ARCHIVE"
                protection_reasons.append(f"Job has {apps_count} application(s)")
            else:
                safety_classification = "SAFE_TO_PURGE"

            orphaned_candidates.append({
                "job_id": job.id,
                "title": job.title,
                "company_id": job.company_id,
                "company_name": job.company.name if job.company else "Unknown Company",
                "status": job.status.value if hasattr(job.status, "value") else str(job.status),
                "applications_count": apps_count,
                "safety_classification": safety_classification,
                "protection_reasons": protection_reasons,
            })

        return orphaned_candidates

    def execute_cleanup(
        self,
        db: Session,
        company_ids: Optional[List[int]] = None,
        circular_ids: Optional[List[int]] = None,
        orphaned_job_ids: Optional[List[int]] = None,
        mode: str = "archive",
        confirmation_phrase: Optional[str] = None,
        current_user: Optional[User] = None,
    ) -> Dict[str, Any]:
        """
        Execute explicit cleanup (archive or purge) against explicitly selected targets.
        Dispatches to drive cleanup if circular_ids or orphaned_job_ids are provided,
        or company cleanup if company_ids are provided.
        Re-validates every safety invariant in real-time within an atomic transaction.
        """
        if circular_ids or orphaned_job_ids:
            return self._execute_drives_cleanup_workflow(
                db=db,
                circular_ids=circular_ids or [],
                orphaned_job_ids=orphaned_job_ids or [],
                mode=mode,
                confirmation_phrase=confirmation_phrase,
                current_user=current_user,
            )

        if not company_ids:
            raise ValueError("No targets (company_ids, circular_ids, or orphaned_job_ids) selected for cleanup. Explicit selection is required.")

        # Deduplicate preserving order
        unique_company_ids = list(dict.fromkeys(company_ids))

        mode_clean = mode.strip().lower()
        if mode_clean not in ["archive", "purge"]:
            raise ValueError(f"Invalid cleanup mode '{mode}'. Supported modes are 'archive' or 'purge'.")

        if mode_clean == "purge":
            expected_phrase = "CONFIRM_PURGE_TEST_DATA"
            if not confirmation_phrase or confirmation_phrase.strip() != expected_phrase:
                raise ValueError(
                    f"Destructive purge requires explicit confirmation phrase '{expected_phrase}'."
                )

        # Retrieve companies
        companies = db.query(Company).filter(Company.id.in_(unique_company_ids)).all()
        found_ids = {c.id for c in companies}
        missing_ids = [cid for cid in unique_company_ids if cid not in found_ids]
        if missing_ids:
            raise ValueError(f"One or more company IDs not found: {missing_ids}")

        # Real-time safety validation (never trust client or previous preview)
        for comp in companies:
            analysis = self._analyze_company_dependencies(db, comp)
            counts = analysis["dependent_counts"]

            if mode_clean == "purge":
                if counts["accepted_offers_count"] > 0:
                    raise ValueError(
                        f"Company '{comp.name}' (ID: {comp.id}) cannot be purged because it has "
                        f"{counts['accepted_offers_count']} accepted placement offer(s). "
                        "Accepted offers are permanent institutional records. Use 'archive' mode instead."
                    )
                if counts["active_offers_count"] > 0:
                    raise ValueError(
                        f"Company '{comp.name}' (ID: {comp.id}) has active pending offers. "
                        "Rescind offers or use 'archive' mode."
                    )
                if analysis["safety_classification"] in ["REQUIRES_ARCHIVE", "PROTECTED_GENUINE"]:
                    raise ValueError(
                        f"Company '{comp.name}' (ID: {comp.id}) cannot be purged because it is classified as "
                        f"{analysis['safety_classification']}. "
                        f"Reasons: {'; '.join(analysis['protection_reasons'])}. Use 'archive' mode instead."
                    )

        if mode_clean == "archive":
            return self._execute_archive(db, companies, current_user)
        else:
            return self._execute_purge(db, companies, current_user)

    def _execute_drives_cleanup_workflow(
        self,
        db: Session,
        circular_ids: List[int],
        orphaned_job_ids: List[int],
        mode: str,
        confirmation_phrase: Optional[str] = None,
        current_user: Optional[User] = None,
    ) -> Dict[str, Any]:
        """Validate and dispatch bulk recruitment drive cleanup."""
        unique_circular_ids = list(dict.fromkeys(circular_ids))
        unique_orphaned_job_ids = list(dict.fromkeys(orphaned_job_ids))

        mode_clean = mode.strip().lower()
        if mode_clean not in ["archive", "purge"]:
            raise ValueError(f"Invalid cleanup mode '{mode}'. Supported modes are 'archive' or 'purge'.")

        if mode_clean == "purge":
            expected_phrase = "CONFIRM_PURGE_TEST_DATA"
            if not confirmation_phrase or confirmation_phrase.strip() != expected_phrase:
                raise ValueError(
                    f"Destructive purge requires explicit confirmation phrase '{expected_phrase}'."
                )

        circulars = []
        if unique_circular_ids:
            circulars = db.query(RecruitmentCircular).filter(RecruitmentCircular.id.in_(unique_circular_ids)).all()
            found_ids = {c.id for c in circulars}
            missing_ids = [cid for cid in unique_circular_ids if cid not in found_ids]
            if missing_ids:
                raise ValueError(f"One or more recruitment drive IDs not found: {missing_ids}")

        if unique_orphaned_job_ids:
            orphaned_jobs = db.query(JobPosting).filter(JobPosting.id.in_(unique_orphaned_job_ids)).all()
            found_job_ids = {j.id for j in orphaned_jobs}
            missing_job_ids = [jid for jid in unique_orphaned_job_ids if jid not in found_job_ids]
            if missing_job_ids:
                raise ValueError(f"One or more orphaned job IDs not found: {missing_job_ids}")

        # Real-time safety validation for all drives
        for circ in circulars:
            analysis = self._analyze_drive_dependencies(db, circ)
            counts = analysis["dependent_counts"]

            if mode_clean == "purge":
                if counts["accepted_offers_count"] > 0:
                    raise ValueError(
                        f"Recruitment Drive '{circ.title}' (ID: {circ.id}) cannot be purged because it has "
                        f"{counts['accepted_offers_count']} accepted placement offer(s). "
                        "Accepted offers are permanent institutional records. Use 'archive' mode instead."
                    )
                if counts["active_offers_count"] > 0:
                    raise ValueError(
                        f"Recruitment Drive '{circ.title}' (ID: {circ.id}) has active pending offers. "
                        "Rescind offers or use 'archive' mode."
                    )
                if analysis["safety_classification"] in ["REQUIRES_ARCHIVE", "PROTECTED_GENUINE"]:
                    raise ValueError(
                        f"Recruitment Drive '{circ.title}' (ID: {circ.id}) cannot be purged because it is classified as "
                        f"{analysis['safety_classification']}. "
                        f"Reasons: {'; '.join(analysis['protection_reasons'])}. Use 'archive' mode instead."
                    )

        # Real-time safety validation for orphaned jobs
        if mode_clean == "purge" and unique_orphaned_job_ids:
            for jid in unique_orphaned_job_ids:
                job = db.query(JobPosting).filter(JobPosting.id == jid).first()
                if job:
                    offers = db.query(PlacementOffer).filter(PlacementOffer.job_posting_id == jid).all()
                    accepted = sum(1 for o in offers if o.acceptance_status == OfferAcceptanceStatus.ACCEPTED)
                    if accepted > 0:
                        raise ValueError(f"Orphaned job '{job.title}' (ID: {jid}) has accepted offers and cannot be purged.")

        if mode_clean == "archive":
            return self._execute_archive_drives(db, circulars, current_user)
        else:
            return self._execute_purge_drives(db, circulars, unique_orphaned_job_ids, current_user)

    def _execute_archive_drives(
        self, db: Session, circulars: List[RecruitmentCircular], current_user: Optional[User]
    ) -> Dict[str, Any]:
        """Execute non-destructive archive of selected recruitment drives and close exclusive jobs."""
        circ_ids = [c.id for c in circulars]

        # 1. Archive Recruitment Circulars
        drives_affected = db.query(RecruitmentCircular).filter(
            RecruitmentCircular.id.in_(circ_ids)
        ).update({"status": RecruitmentCircularStatus.ARCHIVED}, synchronize_session=False)

        # 2. Find eligible jobs linked to the archived drives and close them
        # For a job shared by multiple drives, close it only if doing so is safe for every linked drive.
        # Do not alter another drive's active recruitment process without an explicit, safe policy.
        links = db.query(RecruitmentCircularJob).filter(
            RecruitmentCircularJob.circular_id.in_(circ_ids)
        ).all() if circ_ids else []
        linked_job_ids = list(set([l.job_posting_id for l in links]))

        jobs_to_close_ids = []
        shared_jobs_preserved = 0
        for jid in linked_job_ids:
            job = db.query(JobPosting).filter(JobPosting.id == jid).first()
            if not job or job.status == JobStatus.CLOSED:
                continue

            active_ext_drive_count = db.query(RecruitmentCircularJob).join(
                RecruitmentCircular, RecruitmentCircularJob.circular_id == RecruitmentCircular.id
            ).filter(
                RecruitmentCircularJob.job_posting_id == jid,
                ~RecruitmentCircularJob.circular_id.in_(circ_ids),
                RecruitmentCircular.status != RecruitmentCircularStatus.ARCHIVED,
            ).count()

            if active_ext_drive_count > 0:
                shared_jobs_preserved += 1
            else:
                jobs_to_close_ids.append(jid)

        jobs_affected = 0
        if jobs_to_close_ids:
            jobs_affected = db.query(JobPosting).filter(
                JobPosting.id.in_(jobs_to_close_ids)
            ).update({"status": JobStatus.CLOSED}, synchronize_session=False)

        db.flush()

        audit_entry = audit_service.log_action(
            db=db,
            action="RECRUITMENT_DRIVE_TEST_DATA_ARCHIVED",
            actor=current_user,
            target_type="circular_bulk",
            target_id=",".join(str(cid) for cid in circ_ids),
            details={
                "mode": "archive",
                "circular_ids": circ_ids,
                "drives_archived": drives_affected,
                "jobs_closed": jobs_affected,
                "shared_jobs_preserved": shared_jobs_preserved,
            },
        )

        db.commit()

        return {
            "success": True,
            "mode": "archive",
            "drives_processed": drives_affected,
            "circular_ids": circ_ids,
            "records_affected": {
                "drives_archived": drives_affected,
                "jobs_closed": jobs_affected,
                "shared_jobs_preserved": shared_jobs_preserved,
            },
            "audit_log_id": audit_entry.id if audit_entry else None,
            "message": f"Successfully archived {drives_affected} recruitment drive(s) and closed {jobs_affected} exclusive job(s).",
        }

    def _execute_purge_drives(
        self,
        db: Session,
        circulars: List[RecruitmentCircular],
        orphaned_job_ids: List[int],
        current_user: Optional[User],
    ) -> Dict[str, Any]:
        """
        Execute destructive purge of explicitly validated test recruitment drives.
        Applies atomic ordering, student placement-status re-evaluation, polymorphic notification cleanup,
        and post-commit deferred storage deletion.
        """
        circ_ids = [c.id for c in circulars]

        # Determine exclusive vs shared jobs
        links = db.query(RecruitmentCircularJob).filter(
            RecruitmentCircularJob.circular_id.in_(circ_ids)
        ).all() if circ_ids else []
        all_linked_job_ids = list(set([l.job_posting_id for l in links]))

        exclusive_job_ids: List[int] = []
        shared_job_ids: List[int] = []
        for jid in all_linked_job_ids:
            other_count = db.query(RecruitmentCircularJob).filter(
                RecruitmentCircularJob.job_posting_id == jid,
                ~RecruitmentCircularJob.circular_id.in_(circ_ids),
            ).count()
            if other_count > 0:
                shared_job_ids.append(jid)
            else:
                exclusive_job_ids.append(jid)

        if orphaned_job_ids:
            for o_id in orphaned_job_ids:
                if o_id not in exclusive_job_ids:
                    exclusive_job_ids.append(o_id)

        # Gather dependent records on exclusive jobs
        round_ids = []
        app_ids = []
        offer_ids = []
        batch_ids = []

        if exclusive_job_ids:
            rounds = db.query(RecruitmentRound).filter(RecruitmentRound.job_posting_id.in_(exclusive_job_ids)).all()
            round_ids = [r.id for r in rounds]

            apps = db.query(Application).filter(Application.job_posting_id.in_(exclusive_job_ids)).all()
            app_ids = [a.id for a in apps]

            offers = db.query(PlacementOffer).filter(PlacementOffer.job_posting_id.in_(exclusive_job_ids)).all()
            offer_ids = [o.id for o in offers]

            batches = db.query(RecruitmentResultBatch).filter(
                RecruitmentResultBatch.job_posting_id.in_(exclusive_job_ids)
            ).all()
            batch_ids = [b.id for b in batches]

        # Collect files
        candidate_file_ids: Set[UUID] = set()

        if circ_ids:
            att_files = db.query(RecruitmentCircularAttachment.file_id).filter(
                RecruitmentCircularAttachment.circular_id.in_(circ_ids)
            ).all()
            for (fid,) in att_files:
                if fid:
                    candidate_file_ids.add(fid)

        if batch_ids:
            batches_for_files = db.query(RecruitmentResultBatch.file_id).filter(
                RecruitmentResultBatch.id.in_(batch_ids),
                RecruitmentResultBatch.file_id.isnot(None),
            ).all()
            for (fid,) in batches_for_files:
                if fid:
                    candidate_file_ids.add(fid)

        if offer_ids:
            offer_files = db.query(PlacementOffer.offer_letter_file_id).filter(
                PlacementOffer.id.in_(offer_ids),
                PlacementOffer.offer_letter_file_id.isnot(None),
            ).all()
            for (fid,) in offer_files:
                if fid:
                    candidate_file_ids.add(fid)

        unshared_file_ids: List[UUID] = []
        deferred_storage_keys: List[Tuple[str, str]] = []

        for fid in candidate_file_ids:
            if not self._is_file_shared_outside_context(
                db,
                fid,
                excluded_company_ids=[],
                excluded_circular_ids=circ_ids,
                excluded_job_ids=exclusive_job_ids,
            ):
                unshared_file_ids.append(fid)
                f_rec = db.query(File).filter(File.id == fid).first()
                if f_rec and f_rec.bucket and f_rec.object_key:
                    deferred_storage_keys.append((f_rec.bucket, f_rec.object_key))

        # Re-evaluate student placement statuses
        affected_student_ids: Set[int] = set()
        for a in (db.query(Application.student_id).filter(Application.id.in_(app_ids)).all() if app_ids else []):
            affected_student_ids.add(a[0])
        for o in (db.query(PlacementOffer.student_id).filter(PlacementOffer.id.in_(offer_ids)).all() if offer_ids else []):
            affected_student_ids.add(o[0])

        profiles_updated = 0
        for sid in affected_student_ids:
            profile = db.query(StudentProfileExtended).filter(
                StudentProfileExtended.user_id == sid
            ).first()
            if profile and profile.placement_status == PlacementStatus.PLACED:
                other_accepted = db.query(PlacementOffer).filter(
                    PlacementOffer.student_id == sid,
                    PlacementOffer.id.notin_(offer_ids) if offer_ids else True,
                    PlacementOffer.acceptance_status == OfferAcceptanceStatus.ACCEPTED,
                ).first()
                if other_accepted:
                    profile.placement_status = PlacementStatus.PLACED
                else:
                    other_apps = db.query(Application).filter(
                        Application.student_id == sid,
                        Application.id.notin_(app_ids) if app_ids else True,
                    ).all()
                    if any(a.status == ApplicationStatus.SELECTED for a in other_apps):
                        profile.placement_status = PlacementStatus.PLACED
                    elif any(a.status == ApplicationStatus.SHORTLISTED for a in other_apps):
                        profile.placement_status = PlacementStatus.APPLIED
                    elif len(other_apps) > 0:
                        profile.placement_status = PlacementStatus.APPLIED
                    else:
                        profile.placement_status = PlacementStatus.NOT_APPLIED
                profiles_updated += 1

        db.flush()

        # Notifications cleanup
        notif_conditions = []
        if circ_ids:
            notif_conditions.append(
                and_(Notification.type == "recruitment_circular", Notification.reference_id.in_(circ_ids))
            )
        if exclusive_job_ids:
            notif_conditions.append(
                and_(Notification.type == "job_posting", Notification.reference_id.in_(exclusive_job_ids))
            )
        if batch_ids:
            notif_conditions.append(
                and_(Notification.type == "placement_result", Notification.reference_id.in_(batch_ids))
            )

        notifications_deleted = 0
        if notif_conditions:
            notifications_deleted = db.query(Notification).filter(or_(*notif_conditions)).delete(synchronize_session=False)

        # FK-Safe Cascade Order:
        result_items_deleted = 0
        if batch_ids:
            result_items_deleted = db.query(RecruitmentResultItem).filter(
                RecruitmentResultItem.batch_id.in_(batch_ids)
            ).delete(synchronize_session=False)

        outcomes_deleted = 0
        if round_ids:
            outcomes_deleted = db.query(StudentRoundOutcome).filter(
                StudentRoundOutcome.round_id.in_(round_ids)
            ).delete(synchronize_session=False)

        offers_deleted = 0
        if offer_ids:
            offers_deleted = db.query(PlacementOffer).filter(
                PlacementOffer.id.in_(offer_ids)
            ).delete(synchronize_session=False)

        apps_deleted = 0
        if app_ids:
            apps_deleted = db.query(Application).filter(
                Application.id.in_(app_ids)
            ).delete(synchronize_session=False)

        shortlists_deleted = 0
        if exclusive_job_ids:
            shortlists_deleted = db.query(Shortlist).filter(
                Shortlist.job_posting_id.in_(exclusive_job_ids)
            ).delete(synchronize_session=False)

        batches_deleted = 0
        if batch_ids:
            batches_deleted = db.query(RecruitmentResultBatch).filter(
                RecruitmentResultBatch.id.in_(batch_ids)
            ).delete(synchronize_session=False)

        circular_atts_deleted = 0
        if circ_ids:
            circular_atts_deleted = db.query(RecruitmentCircularAttachment).filter(
                RecruitmentCircularAttachment.circular_id.in_(circ_ids)
            ).delete(synchronize_session=False)

        circular_jobs_deleted = 0
        if circ_ids or exclusive_job_ids:
            circular_jobs_deleted = db.query(RecruitmentCircularJob).filter(
                or_(
                    RecruitmentCircularJob.circular_id.in_(circ_ids) if circ_ids else False,
                    RecruitmentCircularJob.job_posting_id.in_(exclusive_job_ids) if exclusive_job_ids else False,
                )
            ).delete(synchronize_session=False)

        circulars_deleted = 0
        if circ_ids:
            circulars_deleted = db.query(RecruitmentCircular).filter(
                RecruitmentCircular.id.in_(circ_ids)
            ).delete(synchronize_session=False)

        rounds_deleted = 0
        if round_ids:
            rounds_deleted = db.query(RecruitmentRound).filter(
                RecruitmentRound.id.in_(round_ids)
            ).delete(synchronize_session=False)

        jobs_deleted = 0
        if exclusive_job_ids:
            jobs_deleted = db.query(JobPosting).filter(
                JobPosting.id.in_(exclusive_job_ids)
            ).delete(synchronize_session=False)

        files_deleted = 0
        if unshared_file_ids:
            files_deleted = db.query(File).filter(
                File.id.in_(unshared_file_ids)
            ).delete(synchronize_session=False)

        db.flush()

        audit_entry = audit_service.log_action(
            db=db,
            action="RECRUITMENT_DRIVE_TEST_DATA_PURGED",
            actor=current_user,
            target_type="circular_bulk",
            target_id=",".join(str(cid) for cid in circ_ids),
            details={
                "mode": "purge",
                "circular_ids": circ_ids,
                "orphaned_job_ids": orphaned_job_ids,
                "drives_deleted": circulars_deleted,
                "exclusive_jobs_deleted": jobs_deleted,
                "shared_jobs_preserved": len(shared_job_ids),
                "circular_jobs_deleted": circular_jobs_deleted,
                "circular_atts_deleted": circular_atts_deleted,
                "batches_deleted": batches_deleted,
                "result_items_deleted": result_items_deleted,
                "rounds_deleted": rounds_deleted,
                "outcomes_deleted": outcomes_deleted,
                "offers_deleted": offers_deleted,
                "applications_deleted": apps_deleted,
                "shortlists_deleted": shortlists_deleted,
                "files_deleted": files_deleted,
                "notifications_deleted": notifications_deleted,
                "student_profiles_updated": profiles_updated,
            },
        )

        db.commit()

        storage_deleted_count = 0
        for bucket, object_key in deferred_storage_keys:
            try:
                minio_client.delete_file(bucket, object_key)
                storage_deleted_count += 1
            except Exception as e:
                logger.warning(
                    f"Deferred MinIO deletion failed for object '{object_key}' in bucket '{bucket}': {e}"
                )

        return {
            "success": True,
            "mode": "purge",
            "drives_processed": circulars_deleted,
            "circular_ids": circ_ids,
            "records_affected": {
                "drives_deleted": circulars_deleted,
                "jobs_deleted": jobs_deleted,
                "shared_jobs_preserved": len(shared_job_ids),
                "circular_jobs_deleted": circular_jobs_deleted,
                "circular_atts_deleted": circular_atts_deleted,
                "batches_deleted": batches_deleted,
                "result_items_deleted": result_items_deleted,
                "rounds_deleted": rounds_deleted,
                "outcomes_deleted": outcomes_deleted,
                "offers_deleted": offers_deleted,
                "applications_deleted": apps_deleted,
                "shortlists_deleted": shortlists_deleted,
                "files_deleted": files_deleted,
                "storage_objects_deleted": storage_deleted_count,
                "notifications_deleted": notifications_deleted,
                "student_profiles_updated": profiles_updated,
            },
            "audit_log_id": audit_entry.id if audit_entry else None,
            "message": (
                f"Successfully purged {circulars_deleted} recruitment drive(s), {jobs_deleted} linked job(s), "
                f"{batches_deleted} result batch(es), and {files_deleted} file(s)."
            ),
        }

    def _execute_archive(
        self, db: Session, companies: List[Company], current_user: Optional[User]
    ) -> Dict[str, Any]:
        """Execute non-destructive archive of selected companies and their recruitment records."""
        comp_ids = [c.id for c in companies]

        # 1. Deactivate companies
        db.query(Company).filter(Company.id.in_(comp_ids)).update(
            {"is_active": False}, synchronize_session=False
        )

        # 2. Close eligible Job Postings
        # For a job shared by multiple drives, close it only if doing so is safe for every linked drive.
        # Do not alter another drive's active recruitment process.
        candidate_jobs = db.query(JobPosting).filter(
            JobPosting.company_id.in_(comp_ids),
            JobPosting.status != JobStatus.CLOSED,
        ).all()

        jobs_to_close_ids = []
        shared_jobs_preserved = 0
        for job in candidate_jobs:
            active_ext_drive_count = db.query(RecruitmentCircularJob).join(
                RecruitmentCircular, RecruitmentCircularJob.circular_id == RecruitmentCircular.id
            ).filter(
                RecruitmentCircularJob.job_posting_id == job.id,
                ~RecruitmentCircular.company_id.in_(comp_ids),
                RecruitmentCircular.status != RecruitmentCircularStatus.ARCHIVED,
            ).count()

            if active_ext_drive_count > 0:
                shared_jobs_preserved += 1
            else:
                jobs_to_close_ids.append(job.id)

        jobs_affected = 0
        if jobs_to_close_ids:
            jobs_affected = db.query(JobPosting).filter(
                JobPosting.id.in_(jobs_to_close_ids)
            ).update({"status": JobStatus.CLOSED}, synchronize_session=False)

        # 3. Archive Recruitment Circulars
        circulars_affected = db.query(RecruitmentCircular).filter(
            RecruitmentCircular.company_id.in_(comp_ids)
        ).update({"status": RecruitmentCircularStatus.ARCHIVED}, synchronize_session=False)

        # 4. Archive Recruitment Result Batches
        batches_affected = db.query(RecruitmentResultBatch).filter(
            RecruitmentResultBatch.company_id.in_(comp_ids)
        ).update({"status": RecruitmentResultBatchStatus.ARCHIVED}, synchronize_session=False)

        db.flush()

        # Audit log in same transaction
        audit_entry = audit_service.log_action(
            db=db,
            action="RECRUITMENT_TEST_DATA_ARCHIVED",
            actor=current_user,
            target_type="company_bulk",
            target_id=",".join(str(cid) for cid in comp_ids),
            details={
                "mode": "archive",
                "company_ids": comp_ids,
                "companies_count": len(comp_ids),
                "jobs_closed": jobs_affected,
                "shared_jobs_preserved": shared_jobs_preserved,
                "circulars_archived": circulars_affected,
                "result_batches_archived": batches_affected,
            },
        )

        db.commit()

        return {
            "success": True,
            "mode": "archive",
            "companies_processed": len(comp_ids),
            "company_ids": comp_ids,
            "records_affected": {
                "companies_deactivated": len(comp_ids),
                "jobs_closed": jobs_affected,
                "shared_jobs_preserved": shared_jobs_preserved,
                "circulars_archived": circulars_affected,
                "result_batches_archived": batches_affected,
            },
            "audit_log_id": audit_entry.id if audit_entry else None,
            "message": f"Successfully archived {len(comp_ids)} company(ies), closed {jobs_affected} job(s), and archived {circulars_affected} recruitment drive(s).",
        }

    def _execute_purge(
        self, db: Session, companies: List[Company], current_user: Optional[User]
    ) -> Dict[str, Any]:
        """
        Execute destructive purge of explicitly validated test data.
        Applies atomic ordering, student placement-status re-evaluation, polymorphic notification cleanup,
        and post-commit deferred storage deletion.
        """
        comp_ids = [c.id for c in companies]

        # Gather all related entity IDs
        jobs = db.query(JobPosting).filter(JobPosting.company_id.in_(comp_ids)).all()
        job_ids = [j.id for j in jobs]

        circulars = db.query(RecruitmentCircular).filter(RecruitmentCircular.company_id.in_(comp_ids)).all()
        circular_ids = [c.id for c in circulars]

        batches = db.query(RecruitmentResultBatch).filter(RecruitmentResultBatch.company_id.in_(comp_ids)).all()
        batch_ids = [b.id for b in batches]

        rounds = db.query(RecruitmentRound).filter(RecruitmentRound.job_posting_id.in_(job_ids)).all() if job_ids else []
        round_ids = [r.id for r in rounds]

        apps = db.query(Application).filter(Application.job_posting_id.in_(job_ids)).all() if job_ids else []
        app_ids = [a.id for a in apps]

        offers = db.query(PlacementOffer).filter(PlacementOffer.job_posting_id.in_(job_ids)).all() if job_ids else []
        offer_ids = [o.id for o in offers]

        # Affected student IDs
        affected_student_ids: Set[int] = set()
        for a in apps:
            affected_student_ids.add(a.student_id)
        for o in offers:
            affected_student_ids.add(o.student_id)

        # -------------------------------------------------------------
        # STEP 1: Safe Student Placement Status Re-evaluation
        # -------------------------------------------------------------
        profiles_updated = 0
        for sid in affected_student_ids:
            profile = db.query(StudentProfileExtended).filter(
                StudentProfileExtended.user_id == sid
            ).first()
            if profile and profile.placement_status == PlacementStatus.PLACED:
                # Check if student has another ACTIVE accepted offer outside these companies
                other_accepted_offer = db.query(PlacementOffer).filter(
                    PlacementOffer.student_id == sid,
                    PlacementOffer.id.notin_(offer_ids) if offer_ids else True,
                    PlacementOffer.acceptance_status == OfferAcceptanceStatus.ACCEPTED,
                ).first()

                if other_accepted_offer:
                    # Still placed via another company offer!
                    profile.placement_status = PlacementStatus.PLACED
                else:
                    # Check if student has any other active applications outside these companies
                    other_apps = db.query(Application).filter(
                        Application.student_id == sid,
                        Application.id.notin_(app_ids) if app_ids else True,
                    ).all()

                    if any(a.status == ApplicationStatus.SELECTED for a in other_apps):
                        profile.placement_status = PlacementStatus.PLACED
                    elif any(a.status == ApplicationStatus.SHORTLISTED for a in other_apps):
                        profile.placement_status = PlacementStatus.APPLIED
                    elif len(other_apps) > 0:
                        profile.placement_status = PlacementStatus.APPLIED
                    else:
                        profile.placement_status = PlacementStatus.NOT_APPLIED

                profiles_updated += 1

        db.flush()

        # -------------------------------------------------------------
        # STEP 2: Polymorphic Notification Cleanup
        # -------------------------------------------------------------
        notif_delete_conditions = []
        if batch_ids:
            notif_delete_conditions.append(
                and_(Notification.type == "placement_result", Notification.reference_id.in_(batch_ids))
            )
        if job_ids:
            notif_delete_conditions.append(
                and_(Notification.type == "placement_result", Notification.reference_id.in_(job_ids))
            )
            notif_delete_conditions.append(
                and_(Notification.type == "job_posting", Notification.reference_id.in_(job_ids))
            )
        if circular_ids:
            notif_delete_conditions.append(
                and_(Notification.type == "recruitment_circular", Notification.reference_id.in_(circular_ids))
            )
        if offer_ids:
            notif_delete_conditions.append(
                and_(Notification.type == "placement_offer", Notification.reference_id.in_(offer_ids))
            )

        notifications_deleted = 0
        if notif_delete_conditions:
            notifications_deleted = db.query(Notification).filter(
                or_(*notif_delete_conditions)
            ).delete(synchronize_session=False)

        # -------------------------------------------------------------
        # STEP 3: File Storage Inspection & Deferred Deletions
        # -------------------------------------------------------------
        candidate_file_ids: Set[UUID] = set()
        for b in batches:
            if b.file_id:
                candidate_file_ids.add(b.file_id)

        if circular_ids:
            att_fids = db.query(RecruitmentCircularAttachment.file_id).filter(
                RecruitmentCircularAttachment.circular_id.in_(circular_ids)
            ).all()
            for (fid,) in att_fids:
                if fid:
                    candidate_file_ids.add(fid)

        if job_ids:
            offer_fids = db.query(PlacementOffer.offer_letter_file_id).filter(
                PlacementOffer.job_posting_id.in_(job_ids),
                PlacementOffer.offer_letter_file_id.isnot(None),
            ).all()
            for (fid,) in offer_fids:
                if fid:
                    candidate_file_ids.add(fid)

        unshared_file_ids: List[UUID] = []
        deferred_storage_keys: List[Tuple[str, str]] = []

        for fid in candidate_file_ids:
            if not self._is_file_shared_outside_context(
                db, fid, excluded_company_ids=comp_ids, excluded_circular_ids=circular_ids, excluded_job_ids=job_ids
            ):
                file_rec = db.query(File).filter(File.id == fid).first()
                if file_rec:
                    unshared_file_ids.append(fid)
                    deferred_storage_keys.append((file_rec.bucket, file_rec.object_key))

        # -------------------------------------------------------------
        # STEP 4: Ordered Cascade Deletions in Database
        # -------------------------------------------------------------
        result_items_deleted = 0
        if batch_ids:
            result_items_deleted = db.query(RecruitmentResultItem).filter(
                RecruitmentResultItem.batch_id.in_(batch_ids)
            ).delete(synchronize_session=False)

        outcomes_deleted = 0
        if round_ids or app_ids:
            outcomes_deleted = db.query(StudentRoundOutcome).filter(
                or_(
                    StudentRoundOutcome.round_id.in_(round_ids) if round_ids else False,
                    StudentRoundOutcome.application_id.in_(app_ids) if app_ids else False,
                )
            ).delete(synchronize_session=False)

        offers_deleted = 0
        if offer_ids:
            offers_deleted = db.query(PlacementOffer).filter(
                PlacementOffer.id.in_(offer_ids)
            ).delete(synchronize_session=False)

        apps_deleted = 0
        if app_ids:
            apps_deleted = db.query(Application).filter(
                Application.id.in_(app_ids)
            ).delete(synchronize_session=False)

        shortlists_deleted = db.query(Shortlist).filter(
            or_(
                Shortlist.company_id.in_(comp_ids),
                Shortlist.job_posting_id.in_(job_ids) if job_ids else False,
            )
        ).delete(synchronize_session=False)

        batches_deleted = 0
        if batch_ids:
            batches_deleted = db.query(RecruitmentResultBatch).filter(
                RecruitmentResultBatch.id.in_(batch_ids)
            ).delete(synchronize_session=False)

        circular_atts_deleted = 0
        if circular_ids:
            circular_atts_deleted = db.query(RecruitmentCircularAttachment).filter(
                RecruitmentCircularAttachment.circular_id.in_(circular_ids)
            ).delete(synchronize_session=False)

        circular_jobs_deleted = 0
        if circular_ids or job_ids:
            circular_jobs_deleted = db.query(RecruitmentCircularJob).filter(
                or_(
                    RecruitmentCircularJob.circular_id.in_(circular_ids) if circular_ids else False,
                    RecruitmentCircularJob.job_posting_id.in_(job_ids) if job_ids else False,
                )
            ).delete(synchronize_session=False)

        circulars_deleted = 0
        if circular_ids:
            circulars_deleted = db.query(RecruitmentCircular).filter(
                RecruitmentCircular.id.in_(circular_ids)
            ).delete(synchronize_session=False)

        rounds_deleted = 0
        if round_ids:
            rounds_deleted = db.query(RecruitmentRound).filter(
                RecruitmentRound.id.in_(round_ids)
            ).delete(synchronize_session=False)

        jobs_deleted = 0
        if job_ids:
            jobs_deleted = db.query(JobPosting).filter(
                JobPosting.id.in_(job_ids)
            ).delete(synchronize_session=False)

        files_deleted = 0
        if unshared_file_ids:
            files_deleted = db.query(File).filter(
                File.id.in_(unshared_file_ids)
            ).delete(synchronize_session=False)

        companies_deleted = db.query(Company).filter(
            Company.id.in_(comp_ids)
        ).delete(synchronize_session=False)

        db.flush()

        # Audit log in same transaction
        audit_entry = audit_service.log_action(
            db=db,
            action="RECRUITMENT_TEST_DATA_PURGED",
            actor=current_user,
            target_type="company_bulk",
            target_id=",".join(str(cid) for cid in comp_ids),
            details={
                "mode": "purge",
                "company_ids": comp_ids,
                "companies_deleted": companies_deleted,
                "jobs_deleted": jobs_deleted,
                "circulars_deleted": circulars_deleted,
                "circular_jobs_deleted": circular_jobs_deleted,
                "circular_atts_deleted": circular_atts_deleted,
                "batches_deleted": batches_deleted,
                "result_items_deleted": result_items_deleted,
                "rounds_deleted": rounds_deleted,
                "outcomes_deleted": outcomes_deleted,
                "offers_deleted": offers_deleted,
                "applications_deleted": apps_deleted,
                "shortlists_deleted": shortlists_deleted,
                "files_deleted": files_deleted,
                "notifications_deleted": notifications_deleted,
                "student_profiles_updated": profiles_updated,
            },
        )

        # Commit DB transaction atomically
        db.commit()

        # -------------------------------------------------------------
        # STEP 5: Deferred MinIO Object Storage Cleanup (Post-Commit)
        # -------------------------------------------------------------
        storage_deleted_count = 0
        for bucket, object_key in deferred_storage_keys:
            try:
                minio_client.delete_file(bucket, object_key)
                storage_deleted_count += 1
            except Exception as e:
                logger.warning(
                    f"Deferred MinIO deletion failed for object '{object_key}' in bucket '{bucket}': {e}"
                )

        return {
            "success": True,
            "mode": "purge",
            "companies_processed": companies_deleted,
            "company_ids": comp_ids,
            "records_affected": {
                "companies_deleted": companies_deleted,
                "jobs_deleted": jobs_deleted,
                "circulars_deleted": circulars_deleted,
                "circular_jobs_deleted": circular_jobs_deleted,
                "circular_atts_deleted": circular_atts_deleted,
                "batches_deleted": batches_deleted,
                "result_items_deleted": result_items_deleted,
                "rounds_deleted": rounds_deleted,
                "outcomes_deleted": outcomes_deleted,
                "offers_deleted": offers_deleted,
                "applications_deleted": apps_deleted,
                "shortlists_deleted": shortlists_deleted,
                "files_deleted": files_deleted,
                "storage_objects_deleted": storage_deleted_count,
                "notifications_deleted": notifications_deleted,
                "student_profiles_updated": profiles_updated,
            },
            "audit_log_id": audit_entry.id if audit_entry else None,
            "message": (
                f"Successfully purged {companies_deleted} companies, {jobs_deleted} jobs, "
                f"{circulars_deleted} circulars, {batches_deleted} result batches, and {files_deleted} files."
            ),
        }


placement_cleanup_service = PlacementCleanupService()
