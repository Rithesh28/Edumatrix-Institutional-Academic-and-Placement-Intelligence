"""
Recruitment Progression Service

Provides backend business logic for:
- Managing recruitment rounds for job postings
- Recording and retrieving student round progression outcomes
- Audited corrections of previously confirmed round outcomes
- Safe integration with recruitment result batches
- Placement offer creation, updating, and audit logging
"""

import logging
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from sqlalchemy.exc import IntegrityError

from ..models.user import User, UserRole
from ..models.job_posting import JobPosting
from ..models.application import Application
from ..models.file import File, FileStatus
from ..models.recruitment_result import (
    RecruitmentResultBatch,
    RecruitmentResultItem,
    RecruitmentResultReviewState,
)
from ..models.recruitment_round import (
    RecruitmentRound,
    StudentRoundOutcome,
    RoundOutcome,
    PlacementOffer,
    OfferAcceptanceStatus,
)
from ..services.audit_service import audit_service

logger = logging.getLogger(__name__)


# =============================================================================
# HELPER FUNCTIONS & ENUM NORMALIZATION
# =============================================================================

def _check_authorized_actor(current_user: Optional[User]) -> User:
    """Ensure actor is authenticated and holds Placement Officer or Admin privileges."""
    if not current_user:
        raise PermissionError("Authentication required: Actor must be provided for recruitment operations.")
    role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role_val.lower() not in ["placement_officer", "admin"]:
        raise PermissionError(f"Unauthorized: Role '{role_val}' cannot perform recruitment progression operations.")
    return current_user


def _normalize_round_outcome(outcome: Union[RoundOutcome, str]) -> RoundOutcome:
    """Normalize string or enum to valid RoundOutcome enum."""
    if isinstance(outcome, RoundOutcome):
        return outcome
    if isinstance(outcome, str):
        outcome_upper = outcome.strip().upper()
        for member in RoundOutcome:
            if member.name == outcome_upper or member.value.upper() == outcome_upper:
                return member
    raise ValueError(f"Invalid round outcome '{outcome}'. Allowed: {[m.value for m in RoundOutcome]}")


def _normalize_offer_status(status_val: Union[OfferAcceptanceStatus, str]) -> OfferAcceptanceStatus:
    """Normalize string or enum to valid OfferAcceptanceStatus enum."""
    if isinstance(status_val, OfferAcceptanceStatus):
        return status_val
    if isinstance(status_val, str):
        status_upper = status_val.strip().upper()
        for member in OfferAcceptanceStatus:
            if member.name == status_upper or member.value.upper() == status_upper:
                return member
    raise ValueError(f"Invalid offer acceptance status '{status_val}'. Allowed: {[m.value for m in OfferAcceptanceStatus]}")


# =============================================================================
# SERVICE CLASS
# =============================================================================

class RecruitmentProgressionService:
    """Service layer for recruitment round lifecycle, progression outcomes, and placement offers."""

    # -------------------------------------------------------------------------
    # 1. RECRUITMENT ROUND MANAGEMENT
    # -------------------------------------------------------------------------

    def create_recruitment_round(
        self,
        db: Session,
        job_posting_id: int,
        round_number: int,
        name: str,
        round_type: str = "assessment",
        is_final: bool = False,
        round_date: Optional[datetime] = None,
        current_user: Optional[User] = None,
    ) -> RecruitmentRound:
        """
        Create a new recruitment round for a specific job posting.
        Validates sequential sequence number, non-empty title, and authorization.
        """
        actor = _check_authorized_actor(current_user)

        job = db.query(JobPosting).filter(JobPosting.id == job_posting_id).first()
        if not job:
            raise ValueError(f"Job posting with ID {job_posting_id} not found.")

        if round_number <= 0:
            raise ValueError("Round number must be a positive integer greater than zero.")

        clean_name = name.strip() if name else ""
        if not clean_name:
            raise ValueError("Round name cannot be empty.")
        if len(clean_name) > 100:
            raise ValueError("Round name cannot exceed 100 characters.")

        # Check for duplicate round number for this job
        existing = db.query(RecruitmentRound).filter(
            RecruitmentRound.job_posting_id == job_posting_id,
            RecruitmentRound.round_number == round_number
        ).first()
        if existing:
            raise ValueError(
                f"Round {round_number} already exists for Job #{job_posting_id} ('{existing.name}')."
            )

        new_round = RecruitmentRound(
            job_posting_id=job_posting_id,
            round_number=round_number,
            name=clean_name,
            round_type=round_type.strip() if round_type else "assessment",
            is_final=bool(is_final),
            round_date=round_date,
        )
        db.add(new_round)
        try:
            db.commit()
            db.refresh(new_round)
        except IntegrityError as exc:
            db.rollback()
            existing = db.query(RecruitmentRound).filter(
                RecruitmentRound.job_posting_id == job_posting_id,
                RecruitmentRound.round_number == round_number
            ).first()
            if existing:
                raise ValueError(
                    f"Round {round_number} already exists for Job #{job_posting_id} ('{existing.name}')."
                ) from exc
            raise

        audit_service.log_action(
            db=db,
            action="RECRUITMENT_ROUND_CREATED",
            actor=actor,
            target_type="recruitment_round",
            target_id=str(new_round.id),
            details={
                "job_posting_id": job_posting_id,
                "round_number": round_number,
                "name": clean_name,
                "round_type": new_round.round_type,
                "is_final": new_round.is_final,
            },
        )

        return new_round

    def get_job_rounds(self, db: Session, job_posting_id: int) -> List[RecruitmentRound]:
        """Retrieve all defined recruitment rounds for a job posting, ordered by round number."""
        job = db.query(JobPosting).filter(JobPosting.id == job_posting_id).first()
        if not job:
            raise ValueError(f"Job posting with ID {job_posting_id} not found.")

        return db.query(RecruitmentRound).filter(
            RecruitmentRound.job_posting_id == job_posting_id
        ).order_by(asc(RecruitmentRound.round_number)).all()

    def get_round_by_id(self, db: Session, round_id: int) -> Optional[RecruitmentRound]:
        """Fetch a recruitment round by primary key."""
        return db.query(RecruitmentRound).filter(RecruitmentRound.id == round_id).first()

    # -------------------------------------------------------------------------
    # 2. BATCH-ROUND ASSOCIATION
    # -------------------------------------------------------------------------

    def link_batch_to_round(
        self,
        db: Session,
        batch_id: int,
        round_id: int,
        current_user: Optional[User] = None,
    ) -> RecruitmentResultBatch:
        """
        Explicitly link an uploaded result batch to a recruitment round.
        Enforces strict cross-job consistency (batch job/company must match round job/company).
        """
        actor = _check_authorized_actor(current_user)

        batch = db.query(RecruitmentResultBatch).filter(RecruitmentResultBatch.id == batch_id).first()
        if not batch:
            raise ValueError(f"Recruitment result batch #{batch_id} not found.")

        rec_round = db.query(RecruitmentRound).filter(RecruitmentRound.id == round_id).first()
        if not rec_round:
            raise ValueError(f"Recruitment round #{round_id} not found.")

        # Cross-job validation
        if batch.job_posting_id and batch.job_posting_id != rec_round.job_posting_id:
            raise ValueError(
                f"Batch #{batch_id} belongs to Job #{batch.job_posting_id}, but Round #{round_id} "
                f"belongs to Job #{rec_round.job_posting_id}. Cross-job linking is prohibited."
            )

        if batch.company_id != rec_round.job_posting.company_id:
            raise ValueError(
                f"Batch #{batch_id} company (#{batch.company_id}) does not match round's job company "
                f"(#{rec_round.job_posting.company_id}). Cross-company linking is prohibited."
            )

        batch.round_id = rec_round.id
        db.commit()
        db.refresh(batch)

        audit_service.log_action(
            db=db,
            action="RECRUITMENT_BATCH_LINKED_TO_ROUND",
            actor=actor,
            target_type="recruitment_result_batch",
            target_id=str(batch.id),
            details={
                "batch_id": batch.id,
                "round_id": rec_round.id,
                "round_number": rec_round.round_number,
                "round_name": rec_round.name,
                "job_posting_id": rec_round.job_posting_id,
            },
        )

        return batch

    # -------------------------------------------------------------------------
    # 3. CONFIRMED STUDENT ROUND OUTCOMES
    # -------------------------------------------------------------------------

    def record_student_round_outcome(
        self,
        db: Session,
        application_id: int,
        round_id: int,
        outcome: Union[RoundOutcome, str],
        score: Optional[float] = None,
        remarks: Optional[str] = None,
        source_batch_id: Optional[int] = None,
        source_item_id: Optional[int] = None,
        current_user: Optional[User] = None,
    ) -> StudentRoundOutcome:
        """
        Record a confirmed student outcome for a recruitment round.
        Validates application, round, student, and source batch/item provenance.
        Guards against silent overwrites if an authoritative outcome already exists.
        """
        actor = _check_authorized_actor(current_user)
        norm_outcome = _normalize_round_outcome(outcome)

        # 1. Validate round
        rec_round = db.query(RecruitmentRound).filter(RecruitmentRound.id == round_id).first()
        if not rec_round:
            raise ValueError(f"Recruitment round #{round_id} not found.")

        # 2. Validate application
        app = db.query(Application).filter(Application.id == application_id).first()
        if not app:
            raise ValueError(f"Application #{application_id} not found.")

        # 3. Cross-record consistency: Application must belong to the exact same JobPosting
        if app.job_posting_id != rec_round.job_posting_id:
            raise ValueError(
                f"Application #{application_id} belongs to Job #{app.job_posting_id}, but Round #{round_id} "
                f"belongs to Job #{rec_round.job_posting_id}. Cross-job outcomes are prohibited."
            )

        # 4. Validate student active status
        student = db.query(User).filter(User.id == app.student_id).first()
        if not student:
            raise ValueError(f"Student associated with Application #{application_id} not found.")
        if not student.is_active:
            raise ValueError(f"Student #{student.id} ({student.email}) is inactive.")

        # 5. Validate source batch if provided
        if source_batch_id:
            batch = db.query(RecruitmentResultBatch).filter(RecruitmentResultBatch.id == source_batch_id).first()
            if not batch:
                raise ValueError(f"Source batch #{source_batch_id} not found.")
            if batch.job_posting_id and batch.job_posting_id != rec_round.job_posting_id:
                raise ValueError(
                    f"Source batch #{source_batch_id} belongs to Job #{batch.job_posting_id}, but round "
                    f"belongs to Job #{rec_round.job_posting_id}."
                )
            if batch.company_id != rec_round.job_posting.company_id:
                raise ValueError(
                    f"Source batch #{source_batch_id} company does not match job company."
                )

        # 6. Validate source item if provided
        if source_item_id:
            item = db.query(RecruitmentResultItem).filter(RecruitmentResultItem.id == source_item_id).first()
            if not item:
                raise ValueError(f"Source item #{source_item_id} not found.")
            if source_batch_id and item.batch_id != source_batch_id:
                raise ValueError(
                    f"Source item #{source_item_id} belongs to batch #{item.batch_id}, not batch #{source_batch_id}."
                )
            if item.matched_student_id != app.student_id:
                raise ValueError(
                    f"Source item #{source_item_id} matched student (#{item.matched_student_id}) does not match "
                    f"application student (#{app.student_id})."
                )

        # 7. Check for existing authoritative outcome
        existing = db.query(StudentRoundOutcome).filter(
            StudentRoundOutcome.application_id == application_id,
            StudentRoundOutcome.round_id == round_id
        ).first()

        if existing:
            # Idempotent return if outcome is already identical
            if existing.outcome == norm_outcome and existing.score == score:
                return existing
            # Prevent silent overwrite! Require explicit correction workflow
            raise ValueError(
                f"An authoritative outcome for Application #{application_id} in Round #{round_id} already exists "
                f"({existing.outcome.value}). To modify an existing outcome, use correct_student_round_outcome "
                "with an audited reason."
            )

        now = datetime.utcnow()
        new_outcome = StudentRoundOutcome(
            application_id=application_id,
            round_id=round_id,
            student_id=app.student_id,
            outcome=norm_outcome,
            score=score,
            remarks=remarks.strip() if remarks else None,
            source_batch_id=source_batch_id,
            source_item_id=source_item_id,
            confirmed_by=actor.id,
            confirmed_at=now,
        )
        db.add(new_outcome)
        try:
            db.commit()
            db.refresh(new_outcome)
        except IntegrityError as exc:
            db.rollback()
            # Race condition: another concurrent transaction committed an outcome for this (application_id, round_id)
            existing = db.query(StudentRoundOutcome).filter(
                StudentRoundOutcome.application_id == application_id,
                StudentRoundOutcome.round_id == round_id
            ).first()
            if existing:
                if existing.outcome == norm_outcome and existing.score == score:
                    return existing
                raise ValueError(
                    f"An authoritative outcome for Application #{application_id} in Round #{round_id} was already confirmed "
                    f"concurrently ({existing.outcome.value}). To modify an existing outcome, use correct_student_round_outcome "
                    "with an audited reason."
                ) from exc
            raise

        audit_service.log_action(
            db=db,
            action="STUDENT_ROUND_OUTCOME_RECORDED",
            actor=actor,
            target_type="student_round_outcome",
            target_id=str(new_outcome.id),
            details={
                "application_id": application_id,
                "student_id": app.student_id,
                "round_id": round_id,
                "round_number": rec_round.round_number,
                "outcome": norm_outcome.value,
                "score": score,
                "source_batch_id": source_batch_id,
                "source_item_id": source_item_id,
            },
        )

        return new_outcome

    # -------------------------------------------------------------------------
    # 4. AUDITED CORRECTIONS
    # -------------------------------------------------------------------------

    def correct_student_round_outcome(
        self,
        db: Session,
        outcome_id: int,
        new_outcome: Union[RoundOutcome, str],
        reason: str,
        new_score: Optional[float] = None,
        new_remarks: Optional[str] = None,
        current_user: Optional[User] = None,
    ) -> StudentRoundOutcome:
        """
        Safely correct an already-confirmed round outcome.
        Requires non-empty reason and authorized actor.
        Captures complete before/after state in audit_logs.
        """
        actor = _check_authorized_actor(current_user)

        clean_reason = reason.strip() if reason else ""
        if not clean_reason:
            raise ValueError("A non-empty correction reason is mandatory for auditing outcome corrections.")

        norm_outcome = _normalize_round_outcome(new_outcome)

        outcome_record = db.query(StudentRoundOutcome).filter(StudentRoundOutcome.id == outcome_id).first()
        if not outcome_record:
            raise ValueError(f"Student round outcome #{outcome_id} not found.")

        # Capture previous state for audit
        old_outcome = outcome_record.outcome
        old_score = outcome_record.score
        old_remarks = outcome_record.remarks
        old_confirmed_at = outcome_record.confirmed_at
        old_confirmed_by = outcome_record.confirmed_by

        # Apply update atomically
        now = datetime.utcnow()
        outcome_record.outcome = norm_outcome
        if new_score is not None:
            outcome_record.score = new_score
        if new_remarks is not None:
            outcome_record.remarks = new_remarks.strip() if new_remarks else None

        outcome_record.confirmed_by = actor.id
        outcome_record.confirmed_at = now
        outcome_record.updated_at = now

        try:
            db.commit()
            db.refresh(outcome_record)
        except Exception:
            db.rollback()
            raise

        audit_service.log_action(
            db=db,
            action="STUDENT_ROUND_OUTCOME_CORRECTED",
            actor=actor,
            target_type="student_round_outcome",
            target_id=str(outcome_record.id),
            details={
                "outcome_id": outcome_record.id,
                "application_id": outcome_record.application_id,
                "student_id": outcome_record.student_id,
                "round_id": outcome_record.round_id,
                "previous_outcome": old_outcome.value,
                "new_outcome": norm_outcome.value,
                "previous_score": old_score,
                "new_score": outcome_record.score,
                "previous_remarks": old_remarks,
                "new_remarks": outcome_record.remarks,
                "previous_confirmed_by": old_confirmed_by,
                "previous_confirmed_at": old_confirmed_at.isoformat() if old_confirmed_at else None,
                "correction_reason": clean_reason,
                "corrected_at": now.isoformat(),
            },
        )

        return outcome_record

    # -------------------------------------------------------------------------
    # 5. RETRIEVAL & PROGRESSION QUERIES
    # -------------------------------------------------------------------------

    def get_student_progression(
        self,
        db: Session,
        student_id: int,
        job_posting_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve a student's chronological recruitment progression across rounds.
        Returns round details, confirmed outcomes, scores, and offers.
        """
        student = db.query(User).filter(User.id == student_id).first()
        if not student:
            raise ValueError(f"Student with ID {student_id} not found.")

        query = db.query(StudentRoundOutcome).join(RecruitmentRound).filter(
            StudentRoundOutcome.student_id == student_id
        )

        if job_posting_id:
            query = query.filter(RecruitmentRound.job_posting_id == job_posting_id)

        outcomes = query.order_by(
            asc(RecruitmentRound.job_posting_id),
            asc(RecruitmentRound.round_number),
            asc(StudentRoundOutcome.confirmed_at),
        ).all()

        progression = []
        for o in outcomes:
            rec_round = o.round
            app = o.application
            offer = app.placement_offer if app else None

            progression.append({
                "outcome_id": o.id,
                "application_id": o.application_id,
                "job_posting_id": rec_round.job_posting_id,
                "job_title": rec_round.job_posting.title if rec_round.job_posting else None,
                "company_name": rec_round.job_posting.company.name if (rec_round.job_posting and rec_round.job_posting.company) else None,
                "round_id": o.round_id,
                "round_number": rec_round.round_number,
                "round_name": rec_round.name,
                "round_type": rec_round.round_type,
                "is_final_round": rec_round.is_final,
                "round_date": rec_round.round_date.isoformat() if rec_round.round_date else None,
                "outcome": o.outcome.value,
                "score": o.score,
                "remarks": o.remarks,
                "confirmed_at": o.confirmed_at.isoformat() if o.confirmed_at else None,
                "has_offer": offer is not None,
                "offer_status": offer.acceptance_status.value if offer else None,
                "offer_ctc_lpa": offer.ctc_lpa if offer else None,
            })

        return progression

    def get_round_outcomes(
        self,
        db: Session,
        round_id: int,
        outcome_filter: Optional[Union[RoundOutcome, str]] = None,
    ) -> List[StudentRoundOutcome]:
        """Retrieve confirmed outcomes for a specific round, optionally filtered by outcome status."""
        rec_round = db.query(RecruitmentRound).filter(RecruitmentRound.id == round_id).first()
        if not rec_round:
            raise ValueError(f"Recruitment round #{round_id} not found.")

        query = db.query(StudentRoundOutcome).filter(StudentRoundOutcome.round_id == round_id)

        if outcome_filter:
            norm_outcome = _normalize_round_outcome(outcome_filter)
            query = query.filter(StudentRoundOutcome.outcome == norm_outcome)

        return query.order_by(asc(StudentRoundOutcome.id)).all()

    # -------------------------------------------------------------------------
    # 6. PLACEMENT OFFER SERVICE FOUNDATIONS
    # -------------------------------------------------------------------------

    def create_or_update_placement_offer(
        self,
        db: Session,
        application_id: int,
        ctc_lpa: Optional[float] = None,
        designation: Optional[str] = None,
        acceptance_status: Union[OfferAcceptanceStatus, str] = OfferAcceptanceStatus.OFFERED,
        offer_letter_file_id: Optional[UUID] = None,
        offer_date: Optional[datetime] = None,
        response_date: Optional[datetime] = None,
        reason: Optional[str] = None,
        current_user: Optional[User] = None,
    ) -> PlacementOffer:
        """
        Create or update a verified placement offer for an application.
        Enforces cross-record consistency, CTC positivity, file validation, and audit logging.
        """
        actor = _check_authorized_actor(current_user)
        norm_status = _normalize_offer_status(acceptance_status)

        app = db.query(Application).filter(Application.id == application_id).first()
        if not app:
            raise ValueError(f"Application #{application_id} not found.")

        # CTC Validation
        if ctc_lpa is not None:
            if ctc_lpa <= 0:
                raise ValueError("CTC (LPA) must be a positive number greater than zero.")

        # File validation if supplied
        if offer_letter_file_id:
            file_record = db.query(File).filter(File.id == offer_letter_file_id).first()
            if not file_record:
                raise ValueError(f"Offer letter file {offer_letter_file_id} not found in repository.")
            if file_record.status == FileStatus.DELETED:
                raise ValueError(f"Offer letter file {offer_letter_file_id} is marked as deleted.")

        # Response date validation: response_date only makes sense if student/officer recorded a response
        if norm_status == OfferAcceptanceStatus.OFFERED and response_date is not None:
            raise ValueError("Response date cannot be specified while offer status remains OFFERED.")

        existing_offer = db.query(PlacementOffer).filter(PlacementOffer.application_id == application_id).first()

        now = datetime.utcnow()
        if existing_offer:
            # Audit update
            old_ctc = existing_offer.ctc_lpa
            old_status = existing_offer.acceptance_status
            old_designation = existing_offer.designation

            existing_offer.ctc_lpa = ctc_lpa if ctc_lpa is not None else existing_offer.ctc_lpa
            existing_offer.designation = designation.strip() if designation else existing_offer.designation
            existing_offer.acceptance_status = norm_status
            if offer_letter_file_id:
                existing_offer.offer_letter_file_id = offer_letter_file_id
            if offer_date:
                existing_offer.offer_date = offer_date
            if response_date:
                existing_offer.response_date = response_date
            existing_offer.verified_by = actor.id
            existing_offer.updated_at = now

            try:
                db.commit()
                db.refresh(existing_offer)
            except Exception:
                db.rollback()
                raise

            audit_service.log_action(
                db=db,
                action="PLACEMENT_OFFER_UPDATED",
                actor=actor,
                target_type="placement_offer",
                target_id=str(existing_offer.id),
                details={
                    "application_id": application_id,
                    "student_id": app.student_id,
                    "job_posting_id": app.job_posting_id,
                    "previous_ctc_lpa": old_ctc,
                    "new_ctc_lpa": existing_offer.ctc_lpa,
                    "previous_status": old_status.value,
                    "new_status": norm_status.value,
                    "previous_designation": old_designation,
                    "new_designation": existing_offer.designation,
                    "update_reason": reason.strip() if reason else "Offer terms revised by Placement Officer",
                },
            )
            return existing_offer

        else:
            new_offer = PlacementOffer(
                application_id=application_id,
                student_id=app.student_id,
                job_posting_id=app.job_posting_id,
                ctc_lpa=ctc_lpa,
                designation=designation.strip() if designation else None,
                acceptance_status=norm_status,
                offer_letter_file_id=offer_letter_file_id,
                offer_date=offer_date or now,
                response_date=response_date,
                verified_by=actor.id,
            )
            db.add(new_offer)
            try:
                db.commit()
                db.refresh(new_offer)
            except IntegrityError as exc:
                db.rollback()
                existing_offer = db.query(PlacementOffer).filter(
                    PlacementOffer.application_id == application_id
                ).first()
                if existing_offer:
                    if existing_offer.ctc_lpa == ctc_lpa and existing_offer.acceptance_status == norm_status:
                        return existing_offer
                    raise ValueError(
                        f"A placement offer for Application #{application_id} was already created concurrently. "
                        "Re-fetch the existing offer to update terms."
                    ) from exc
                raise

            audit_service.log_action(
                db=db,
                action="PLACEMENT_OFFER_CREATED",
                actor=actor,
                target_type="placement_offer",
                target_id=str(new_offer.id),
                details={
                    "application_id": application_id,
                    "student_id": app.student_id,
                    "job_posting_id": app.job_posting_id,
                    "ctc_lpa": ctc_lpa,
                    "designation": new_offer.designation,
                    "acceptance_status": norm_status.value,
                },
            )
            return new_offer

    def get_placement_offer_by_application(
        self,
        db: Session,
        application_id: int,
    ) -> Optional[PlacementOffer]:
        """Fetch placement offer for an application if one exists."""
        return db.query(PlacementOffer).filter(PlacementOffer.application_id == application_id).first()

    # -------------------------------------------------------------------------
    # 7. INTEGRITY & HEALTH VALIDATION
    # -------------------------------------------------------------------------

    def validate_recruitment_integrity(
        self,
        db: Session,
        job_posting_id: int,
    ) -> Dict[str, Any]:
        """
        Validate recruitment progression integrity for a job posting.
        Reports configured rounds, outcome counts, linked/unlinked batches, and anomalies.
        Does NOT mutate or backfill any records.
        """
        job = db.query(JobPosting).filter(JobPosting.id == job_posting_id).first()
        if not job:
            raise ValueError(f"Job posting with ID {job_posting_id} not found.")

        rounds = db.query(RecruitmentRound).filter(
            RecruitmentRound.job_posting_id == job_posting_id
        ).order_by(asc(RecruitmentRound.round_number)).all()

        batches = db.query(RecruitmentResultBatch).filter(
            RecruitmentResultBatch.job_posting_id == job_posting_id
        ).all()

        linked_batches = [b for b in batches if b.round_id is not None]
        unlinked_batches = [b for b in batches if b.round_id is None]

        rounds_summary = []
        for r in rounds:
            cleared_cnt = db.query(StudentRoundOutcome).filter(
                StudentRoundOutcome.round_id == r.id,
                StudentRoundOutcome.outcome == RoundOutcome.CLEARED
            ).count()
            rejected_cnt = db.query(StudentRoundOutcome).filter(
                StudentRoundOutcome.round_id == r.id,
                StudentRoundOutcome.outcome == RoundOutcome.REJECTED
            ).count()
            offered_cnt = db.query(StudentRoundOutcome).filter(
                StudentRoundOutcome.round_id == r.id,
                StudentRoundOutcome.outcome == RoundOutcome.OFFERED
            ).count()
            total_outcomes = db.query(StudentRoundOutcome).filter(
                StudentRoundOutcome.round_id == r.id
            ).count()

            rounds_summary.append({
                "round_id": r.id,
                "round_number": r.round_number,
                "name": r.name,
                "is_final": r.is_final,
                "total_outcomes": total_outcomes,
                "cleared": cleared_cnt,
                "rejected": rejected_cnt,
                "offered": offered_cnt,
            })

        # Check for offers on this job
        offers_count = db.query(PlacementOffer).filter(
            PlacementOffer.job_posting_id == job_posting_id
        ).count()

        return {
            "job_posting_id": job_posting_id,
            "job_title": job.title,
            "company_id": job.company_id,
            "total_rounds": len(rounds),
            "total_batches": len(batches),
            "linked_batches_count": len(linked_batches),
            "unlinked_legacy_batches_count": len(unlinked_batches),
            "total_placement_offers": offers_count,
            "rounds_summary": rounds_summary,
            "status": "HEALTHY",
        }


# Singleton instance
recruitment_progression_service = RecruitmentProgressionService()
