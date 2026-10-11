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
    def is_test_student_email(email: str) -> bool:
        """Evaluate whether a student email indicates a synthetic test account."""
        if not email:
            return False
        return any(pattern.search(email) for pattern in TEST_STUDENT_PATTERNS)

    def generate_cleanup_preview(
        self,
        db: Session,
        company_ids: Optional[List[int]] = None,
        pattern: Optional[str] = None,
        include_all_candidates: bool = True,
    ) -> Dict[str, Any]:
        """
        Preview candidate companies for cleanup without modifying any data.
        Returns detailed dependent-record counts, safety classifications, and protection reasons.
        """
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

        # 2. Circulars & Links
        circulars = db.query(RecruitmentCircular).filter(RecruitmentCircular.company_id == comp.id).all()
        circular_ids = [c.id for c in circulars]
        circulars_count = len(circulars)

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

        if not self.is_candidate_test_name(comp.name):
            protection_reasons.append(
                "Company name lacks test/timestamp patterns and appears genuine"
            )

        # Classification decision
        if accepted_offers_count > 0 or has_genuine_student_impact:
            if not self.is_candidate_test_name(comp.name):
                safety_classification = "PROTECTED_GENUINE"
            else:
                safety_classification = "REQUIRES_ARCHIVE"
        elif active_offers_count > 0 or confirmed_outcomes_count > 0 or not self.is_candidate_test_name(comp.name):
            safety_classification = "REQUIRES_ARCHIVE"
        else:
            safety_classification = "SAFE_TO_PURGE"

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

    def execute_cleanup(
        self,
        db: Session,
        company_ids: List[int],
        mode: str,
        confirmation_phrase: Optional[str] = None,
        current_user: Optional[User] = None,
    ) -> Dict[str, Any]:
        """
        Execute explicit cleanup (archive or purge) against explicitly selected company IDs.
        Re-validates every safety invariant in real-time within an atomic transaction.
        """
        if not company_ids:
            raise ValueError("No company IDs selected for cleanup. Explicit selection is required.")

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

    def _execute_archive(
        self, db: Session, companies: List[Company], current_user: Optional[User]
    ) -> Dict[str, Any]:
        """Execute non-destructive archive of selected companies and their recruitment records."""
        comp_ids = [c.id for c in companies]

        # 1. Deactivate companies
        db.query(Company).filter(Company.id.in_(comp_ids)).update(
            {"is_active": False}, synchronize_session=False
        )

        # 2. Close Job Postings
        jobs_affected = db.query(JobPosting).filter(JobPosting.company_id.in_(comp_ids)).update(
            {"status": JobStatus.CLOSED}, synchronize_session=False
        )

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
                "circulars_archived": circulars_affected,
                "result_batches_archived": batches_affected,
            },
            "audit_log_id": audit_entry.id if audit_entry else None,
            "message": f"Successfully archived {len(comp_ids)} companies, {jobs_affected} jobs, and {circulars_affected} circulars.",
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
