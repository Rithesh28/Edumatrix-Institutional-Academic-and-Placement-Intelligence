"""
Placement Offer Service

Provides domain logic for:
- Placement Officer verification and formal offer creation
- Offer term updates and immutable error rollback
- Student offer response (accept / decline) with strict identity enforcement
- Offer rescission by authorized officers with mandatory audit reason
- Atomic audit logging and deduplicated notifications
- Robust placement accounting metrics distinguishing verified offers, accepted offers,
  and legacy placement numbers
"""

import logging
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func
from sqlalchemy.exc import IntegrityError

from ..models.user import User, UserRole
from ..models.job_posting import JobPosting
from ..models.application import Application, ApplicationStatus
from ..models.file import File, FileStatus
from ..models.notification import Notification
from ..models.profile import StudentProfileExtended, PlacementStatus
from ..models.recruitment_round import (
    PlacementOffer,
    OfferAcceptanceStatus,
)
from ..services.audit_service import audit_service

logger = logging.getLogger(__name__)


def _check_authorized_actor(current_user: Optional[User]) -> User:
    """Ensure actor is authenticated and holds Placement Officer or Admin privileges."""
    if not current_user:
        raise PermissionError("Authentication required: Actor must be provided for recruitment operations.")
    role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role_val.lower() not in ["placement_officer", "admin"]:
        raise PermissionError(f"Unauthorized: Role '{role_val}' cannot perform offer verification or management operations.")
    return current_user


def _check_file_access(db: Session, file_id: UUID, current_user: User) -> File:
    """
    Validate that supporting offer-letter file exists, is not deleted,
    and current_user has access to it.
    """
    file_record = db.query(File).filter(File.id == file_id).first()
    if not file_record:
        raise ValueError(f"Offer letter file {file_id} not found in repository.")
    if file_record.status == FileStatus.DELETED:
        raise ValueError(f"Offer letter file {file_id} is marked as deleted.")

    # Lazy-import check_file_permission to avoid circular imports
    try:
        from ..api.files import check_file_permission
        if not check_file_permission(db, file_record, current_user):
            raise PermissionError(f"Unauthorized: Actor does not have access to file {file_id}.")
    except ImportError:
        # Fallback check
        role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
        if role_val.lower() not in ["admin", "placement_officer"] and file_record.uploaded_by != current_user.id:
            raise PermissionError(f"Unauthorized: Actor does not have access to file {file_id}.")

    return file_record


class PlacementOfferService:
    """Service handling formal placement offer lifecycle and placement accounting."""

    # =========================================================================
    # 1. OFFER CREATION & VERIFICATION
    # =========================================================================

    def create_placement_offer(
        self,
        db: Session,
        application_id: int,
        ctc_lpa: Optional[float] = None,
        designation: Optional[str] = None,
        offer_letter_file_id: Optional[UUID] = None,
        offer_date: Optional[datetime] = None,
        student_id: Optional[int] = None,
        job_posting_id: Optional[int] = None,
        current_user: Optional[User] = None,
        auto_commit: bool = True,
    ) -> PlacementOffer:
        """
        Create a verified placement offer after an authorized Placement Officer verifies details.
        
        Validates:
        - Actor is an authorized Placement Officer or Admin.
        - Application exists, and student and job posting belong together.
        - CTC is positive if provided.
        - Supporting offer letter file exists, is not deleted, and is accessible.
        - Prevents duplicate offer creation for the same application.
        - Commits offer, audit log, and student notification within the same atomic transaction.
        """
        actor = _check_authorized_actor(current_user)

        # 1. Fetch and validate application
        app = db.query(Application).filter(Application.id == application_id).first()
        if not app:
            raise ValueError(f"Application #{application_id} not found.")

        # 2. Validate cross-record consistency
        if student_id is not None and app.student_id != student_id:
            raise ValueError(
                f"Application #{application_id} belongs to student #{app.student_id}, not student #{student_id}."
            )
        if job_posting_id is not None and app.job_posting_id != job_posting_id:
            raise ValueError(
                f"Application #{application_id} belongs to job posting #{app.job_posting_id}, not job #{job_posting_id}."
            )

        student = db.query(User).filter(User.id == app.student_id).first()
        if not student:
            raise ValueError(f"Student user #{app.student_id} not found.")

        job = db.query(JobPosting).filter(JobPosting.id == app.job_posting_id).first()
        if not job:
            raise ValueError(f"Job posting #{app.job_posting_id} not found.")

        # 3. CTC Validation
        if ctc_lpa is not None:
            if ctc_lpa <= 0:
                raise ValueError("CTC (LPA) must be a positive number greater than zero.")

        # 4. File access validation
        if offer_letter_file_id is not None:
            _check_file_access(db, offer_letter_file_id, actor)

        # 5. Prevent duplicate offer creation for the same application
        existing_offer = db.query(PlacementOffer).filter(
            PlacementOffer.application_id == application_id
        ).first()
        if existing_offer:
            raise ValueError(
                f"A placement offer already exists for Application #{application_id} (Offer #{existing_offer.id}). "
                "Duplicate offer creation is rejected. Use update operation to modify terms."
            )

        now = datetime.utcnow()
        new_offer = PlacementOffer(
            application_id=application_id,
            student_id=app.student_id,
            job_posting_id=app.job_posting_id,
            ctc_lpa=ctc_lpa,
            designation=designation.strip() if designation else None,
            acceptance_status=OfferAcceptanceStatus.OFFERED,
            offer_letter_file_id=offer_letter_file_id,
            offer_date=offer_date or now,
            response_date=None,
            verified_by=actor.id,
            created_at=now,
        )
        db.add(new_offer)
        db.flush()

        # 6. Audit write within the same transaction (auto_commit=False)
        audit_entry = audit_service.log_action(
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
                "acceptance_status": OfferAcceptanceStatus.OFFERED.value,
                "offer_letter_file_id": str(offer_letter_file_id) if offer_letter_file_id else None,
                "verified_by": actor.id,
            },
            auto_commit=False,
        )
        if audit_entry is None:
            db.rollback()
            raise RuntimeError("Audit logging failed during placement offer creation; transaction aborted.")

        # 7. Deduplicated notification to student within the transaction
        event_key = f"placement_offer:{new_offer.id}:verified"
        existing_notif = db.query(Notification).filter(Notification.event_key == event_key).first()
        if not existing_notif:
            company_name = job.company.name if (job and job.company) else "Campus Recruiter"
            notif = Notification(
                user_id=app.student_id,
                type="placement_offer",
                title=f"🎉 Offer Verified: {job.title} at {company_name}",
                message=(
                    f"Congratulations! Your formal placement offer for "
                    f"'{new_offer.designation or job.title}' at {company_name} "
                    f"with CTC {ctc_lpa or 'N/A'} LPA has been verified by the Placement Cell."
                ),
                reference_id=new_offer.id,
                event_key=event_key,
            )
            db.add(notif)

        if auto_commit:
            try:
                db.commit()
                db.refresh(new_offer)
            except IntegrityError as exc:
                db.rollback()
                raise ValueError(
                    f"A placement offer for Application #{application_id} already exists (concurrent conflict)."
                ) from exc
            except Exception:
                db.rollback()
                raise

        return new_offer

    # =========================================================================
    # 2. OFFER TERM UPDATES
    # =========================================================================

    def update_placement_offer(
        self,
        db: Session,
        offer_id: int,
        ctc_lpa: Optional[float] = None,
        designation: Optional[str] = None,
        offer_letter_file_id: Optional[UUID] = None,
        offer_date: Optional[datetime] = None,
        reason: Optional[str] = None,
        current_user: Optional[User] = None,
        auto_commit: bool = True,
    ) -> PlacementOffer:
        """
        Update terms of an existing verified placement offer.
        
        Validates:
        - Actor is an authorized Placement Officer or Admin.
        - Offer exists.
        - CTC is positive if supplied.
        - Supporting file exists and is accessible.
        - Preserves existing offer data untouched if update validation or audit fails.
        """
        actor = _check_authorized_actor(current_user)

        offer = db.query(PlacementOffer).filter(PlacementOffer.id == offer_id).first()
        if not offer:
            raise ValueError(f"Placement offer #{offer_id} not found.")

        # CTC Validation
        if ctc_lpa is not None:
            if ctc_lpa <= 0:
                raise ValueError("CTC (LPA) must be a positive number greater than zero.")

        # File validation if supplied
        if offer_letter_file_id is not None:
            _check_file_access(db, offer_letter_file_id, actor)

        # Record old values for audit
        old_ctc = offer.ctc_lpa
        old_designation = offer.designation
        old_file_id = str(offer.offer_letter_file_id) if offer.offer_letter_file_id else None

        # Apply mutations
        if ctc_lpa is not None:
            offer.ctc_lpa = ctc_lpa
        if designation is not None:
            offer.designation = designation.strip() if designation else None
        if offer_letter_file_id is not None:
            offer.offer_letter_file_id = offer_letter_file_id
        if offer_date is not None:
            offer.offer_date = offer_date

        now = datetime.utcnow()
        offer.verified_by = actor.id
        offer.updated_at = now

        db.flush()

        # Audit log in same transaction
        audit_entry = audit_service.log_action(
            db=db,
            action="PLACEMENT_OFFER_UPDATED",
            actor=actor,
            target_type="placement_offer",
            target_id=str(offer.id),
            details={
                "application_id": offer.application_id,
                "student_id": offer.student_id,
                "job_posting_id": offer.job_posting_id,
                "previous_ctc_lpa": old_ctc,
                "new_ctc_lpa": offer.ctc_lpa,
                "previous_designation": old_designation,
                "new_designation": offer.designation,
                "previous_offer_letter_file_id": old_file_id,
                "new_offer_letter_file_id": str(offer.offer_letter_file_id) if offer.offer_letter_file_id else None,
                "update_reason": reason.strip() if reason else "Offer terms revised by Placement Officer",
            },
            auto_commit=False,
        )
        if audit_entry is None:
            db.rollback()
            raise RuntimeError("Audit logging failed during placement offer update; transaction aborted.")

        if auto_commit:
            try:
                db.commit()
                db.refresh(offer)
            except Exception:
                db.rollback()
                raise

        return offer

    # =========================================================================
    # 3. STUDENT OFFER RESPONSE (ACCEPT / DECLINE)
    # =========================================================================

    def respond_to_placement_offer(
        self,
        db: Session,
        offer_id: int,
        decision: str,
        remarks: Optional[str] = None,
        current_user: Optional[User] = None,
        auto_commit: bool = True,
    ) -> PlacementOffer:
        """
        Record a student's response to their own verified placement offer.
        
        Requirements:
        - Authenticated server-side identity (must be student recipient or Admin).
        - Rejects responses from unauthorized users on another student's behalf.
        - Rejects non-decision parameters (cannot alter CTC, designation, employer, or file).
        - State rules:
            - Only offers currently in OFFERED status can receive a response.
            - Rescinded offers cannot receive a response.
            - Repeated identical responses are idempotent.
            - Conflicting repeat responses (ACCEPT after DECLINE, or DECLINE after ACCEPT) are rejected.
        - Never infers acceptance from round results or absence of response.
        - If ACCEPTED, updates student's profile placement status to PLACED according to institutional policy.
        - Persists offer update, audit log, and confirmation notification within one atomic transaction.
        """
        if not current_user:
            raise PermissionError("Authentication required: Actor must be authenticated to respond to an offer.")

        role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
        is_admin = role_val.lower() == "admin"

        offer = db.query(PlacementOffer).filter(PlacementOffer.id == offer_id).first()
        if not offer:
            raise ValueError(f"Placement offer #{offer_id} not found.")

        # Strict identity check: student responding must be the owner
        if not is_admin:
            if role_val.lower() != "student":
                raise PermissionError("Only the student recipient can submit an offer response.")
            if offer.student_id != current_user.id:
                raise PermissionError(
                    f"Forbidden: You cannot respond to offer #{offer_id} belonging to another student."
                )

        clean_decision = decision.strip().upper() if decision else ""
        if clean_decision not in ["ACCEPTED", "DECLINED"]:
            raise ValueError(
                f"Invalid offer response decision '{decision}'. Allowed decisions: 'ACCEPTED', 'DECLINED'."
            )

        target_status = (
            OfferAcceptanceStatus.ACCEPTED
            if clean_decision == "ACCEPTED"
            else OfferAcceptanceStatus.DECLINED
        )

        # 1. Rescinded offer guard
        if offer.acceptance_status == OfferAcceptanceStatus.RESCINDED:
            raise ValueError(
                f"Cannot respond to offer #{offer_id}: This offer has been rescinded by the employer/institution."
            )

        # 2. Idempotency: repeated identical response returns existing offer
        if offer.acceptance_status == target_status:
            logger.info(
                f"Idempotent offer response: Offer #{offer_id} is already in state '{target_status.value}'."
            )
            return offer

        # 3. Conflicting repeat response guard
        if offer.acceptance_status != OfferAcceptanceStatus.OFFERED:
            raise ValueError(
                f"Cannot change offer response from '{offer.acceptance_status.value}' to '{target_status.value}'. "
                "Conflicting repeat responses are rejected without an authorized administrative correction workflow."
            )

        # 4. Apply response
        now = datetime.utcnow()
        old_status = offer.acceptance_status
        offer.acceptance_status = target_status
        offer.response_date = now
        offer.updated_at = now

        # 5. Institutional placement policy:
        # Upon explicit student acceptance of a verified offer, set StudentProfileExtended.placement_status = PLACED
        if target_status == OfferAcceptanceStatus.ACCEPTED:
            profile = db.query(StudentProfileExtended).filter(
                StudentProfileExtended.user_id == offer.student_id
            ).first()
            if profile:
                profile.placement_status = PlacementStatus.PLACED

        db.flush()

        # 6. Audit log in same transaction
        action_name = (
            "PLACEMENT_OFFER_ACCEPTED"
            if target_status == OfferAcceptanceStatus.ACCEPTED
            else "PLACEMENT_OFFER_DECLINED"
        )
        audit_entry = audit_service.log_action(
            db=db,
            action=action_name,
            actor=current_user,
            target_type="placement_offer",
            target_id=str(offer.id),
            details={
                "application_id": offer.application_id,
                "student_id": offer.student_id,
                "job_posting_id": offer.job_posting_id,
                "previous_status": old_status.value,
                "new_status": target_status.value,
                "response_decision": clean_decision,
                "response_remarks": remarks.strip() if remarks else None,
                "response_date": now.isoformat(),
            },
            auto_commit=False,
        )
        if audit_entry is None:
            db.rollback()
            raise RuntimeError("Audit logging failed during student offer response; transaction aborted.")

        # 7. Deduplicated student notification
        event_key = f"placement_offer:{offer.id}:{clean_decision.lower()}"
        existing_notif = db.query(Notification).filter(Notification.event_key == event_key).first()
        if not existing_notif:
            job = offer.job_posting
            company_name = job.company.name if (job and job.company) else "Campus Recruiter"
            if target_status == OfferAcceptanceStatus.ACCEPTED:
                notif_title = f"✅ Offer Accepted: {job.title} at {company_name}"
                notif_msg = (
                    f"You have successfully accepted the placement offer for "
                    f"'{offer.designation or job.title}' at {company_name}."
                )
            else:
                notif_title = f"ℹ️ Offer Declined: {job.title} at {company_name}"
                notif_msg = (
                    f"You have recorded your response declining the placement offer for "
                    f"'{offer.designation or job.title}' at {company_name}."
                )

            notif = Notification(
                user_id=offer.student_id,
                type="placement_offer",
                title=notif_title,
                message=notif_msg,
                reference_id=offer.id,
                event_key=event_key,
            )
            db.add(notif)

        if auto_commit:
            try:
                db.commit()
                db.refresh(offer)
            except Exception:
                db.rollback()
                raise

        return offer

    # =========================================================================
    # 4. AUTHORIZED OFFER RESCISSION
    # =========================================================================

    def rescind_placement_offer(
        self,
        db: Session,
        offer_id: int,
        reason: str,
        current_user: Optional[User] = None,
        auto_commit: bool = True,
    ) -> PlacementOffer:
        """
        Rescind a placement offer by an authorized Placement Officer or Admin.
        
        Requirements:
        - Only Placement Officers and Admins are authorized. Students cannot rescind.
        - Mandatory non-empty reason for audit trail.
        - Idempotent on repeated calls.
        - Re-evaluates student's profile placement_status if no other accepted offers remain.
        - Persists mutation, audit log, and student notification atomically.
        """
        actor = _check_authorized_actor(current_user)

        clean_reason = reason.strip() if reason else ""
        if not clean_reason:
            raise ValueError("A clear, non-empty audit reason is required to rescind a placement offer.")

        offer = db.query(PlacementOffer).filter(PlacementOffer.id == offer_id).first()
        if not offer:
            raise ValueError(f"Placement offer #{offer_id} not found.")

        # Idempotency
        if offer.acceptance_status == OfferAcceptanceStatus.RESCINDED:
            logger.info(f"Idempotent rescission: Offer #{offer_id} is already marked RESCINDED.")
            return offer

        old_status = offer.acceptance_status
        now = datetime.utcnow()
        offer.acceptance_status = OfferAcceptanceStatus.RESCINDED
        offer.updated_at = now

        # Re-evaluate profile placement status:
        # If student's profile was marked PLACED, verify if they have any other ACTIVE accepted offer
        profile = db.query(StudentProfileExtended).filter(
            StudentProfileExtended.user_id == offer.student_id
        ).first()
        if profile and profile.placement_status == PlacementStatus.PLACED:
            other_active_accepted = db.query(PlacementOffer).filter(
                PlacementOffer.student_id == offer.student_id,
                PlacementOffer.id != offer.id,
                PlacementOffer.acceptance_status == OfferAcceptanceStatus.ACCEPTED,
            ).first()
            if not other_active_accepted:
                # Revert to SHORTLISTED or APPLIED based on application presence
                has_apps = db.query(Application).filter(Application.student_id == offer.student_id).count() > 0
                profile.placement_status = PlacementStatus.APPLIED if has_apps else PlacementStatus.NOT_APPLIED

        db.flush()

        # Audit log in same transaction
        audit_entry = audit_service.log_action(
            db=db,
            action="PLACEMENT_OFFER_RESCINDED",
            actor=actor,
            target_type="placement_offer",
            target_id=str(offer.id),
            details={
                "application_id": offer.application_id,
                "student_id": offer.student_id,
                "job_posting_id": offer.job_posting_id,
                "previous_status": old_status.value,
                "rescission_reason": clean_reason,
                "rescinded_by": actor.id,
            },
            auto_commit=False,
        )
        if audit_entry is None:
            db.rollback()
            raise RuntimeError("Audit logging failed during offer rescission; transaction aborted.")

        # Notification to student
        event_key = f"placement_offer:{offer.id}:rescinded"
        existing_notif = db.query(Notification).filter(Notification.event_key == event_key).first()
        if not existing_notif:
            job = offer.job_posting
            company_name = job.company.name if (job and job.company) else "Campus Recruiter"
            notif = Notification(
                user_id=offer.student_id,
                type="placement_offer",
                title=f"⚠️ Offer Rescinded: {job.title} at {company_name}",
                message=(
                    f"Your offer for '{offer.designation or job.title}' at {company_name} "
                    f"has been rescinded by the Placement Cell. Reason: {clean_reason}"
                ),
                reference_id=offer.id,
                event_key=event_key,
            )
            db.add(notif)

        if auto_commit:
            try:
                db.commit()
                db.refresh(offer)
            except Exception:
                db.rollback()
                raise

        return offer

    # =========================================================================
    # 5. RETRIEVAL QUERIES
    # =========================================================================

    def get_placement_offer_by_id(
        self,
        db: Session,
        offer_id: int,
        current_user: Optional[User] = None,
    ) -> PlacementOffer:
        """Fetch offer by ID with access control (authorized officer or recipient student)."""
        offer = db.query(PlacementOffer).filter(PlacementOffer.id == offer_id).first()
        if not offer:
            raise ValueError(f"Placement offer #{offer_id} not found.")

        if current_user:
            role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
            if role_val.lower() == "student" and offer.student_id != current_user.id:
                raise PermissionError("Access denied: You can only view your own placement offers.")

        return offer

    def get_student_offers(
        self,
        db: Session,
        student_id: int,
        current_user: Optional[User] = None,
    ) -> List[PlacementOffer]:
        """Fetch all placement offers for a specific student."""
        if current_user:
            role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
            if role_val.lower() == "student" and student_id != current_user.id:
                raise PermissionError("Access denied: You can only view your own placement offers.")

        return db.query(PlacementOffer).filter(
            PlacementOffer.student_id == student_id
        ).order_by(desc(PlacementOffer.created_at)).all()

    def list_placement_offers(
        self,
        db: Session,
        job_posting_id: Optional[int] = None,
        student_id: Optional[int] = None,
        acceptance_status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        current_user: Optional[User] = None,
    ) -> List[PlacementOffer]:
        """List offers with filtering. Accessible by Placement Officers and Admins."""
        _check_authorized_actor(current_user)

        query = db.query(PlacementOffer)

        if job_posting_id is not None:
            query = query.filter(PlacementOffer.job_posting_id == job_posting_id)
        if student_id is not None:
            query = query.filter(PlacementOffer.student_id == student_id)
        if acceptance_status is not None:
            status_upper = acceptance_status.strip().upper()
            query = query.filter(PlacementOffer.acceptance_status == status_upper)

        return query.order_by(desc(PlacementOffer.created_at)).offset(skip).limit(limit).all()

    # =========================================================================
    # 6. PLACEMENT ACCOUNTING METRICS
    # =========================================================================

    def get_placement_accounting_metrics(self, db: Session) -> Dict[str, Any]:
        """
        Compute precise placement accounting metrics distinguishing:
        1. Legacy placed student count (ApplicationStatus.SELECTED or profile.placement_status == PLACED).
        2. Verified offers count (formal PlacementOffer records).
        3. Accepted offers count (PlacementOffer.acceptance_status == ACCEPTED).
        4. Final verified placed students count (unique students with at least 1 ACCEPTED offer).
        5. Students with multiple verified active offers.
        
        Rules:
        - Round cleared, final-round selection, unverified offer, declined offer, or rescinded
          offer are NOT counted as verified placements.
        - A student with multiple accepted offers is counted exactly once in unique placed metrics.
        - Multiple offers do NOT automatically cancel each other.
        """
        total_students = db.query(User).filter(User.role == UserRole.STUDENT).count()

        # 1. Legacy placed calculation
        selected_student_ids = set(
            r[0] for r in db.query(Application.student_id).filter(
                Application.status == ApplicationStatus.SELECTED
            ).all()
        )
        profile_placed_ids = set(
            r[0] for r in db.query(StudentProfileExtended.user_id).filter(
                StudentProfileExtended.placement_status == PlacementStatus.PLACED
            ).all()
        )
        legacy_placed_ids = selected_student_ids.union(profile_placed_ids)
        legacy_placed_count = len(legacy_placed_ids)
        legacy_placement_rate = (legacy_placed_count / total_students * 100.0) if total_students > 0 else 0.0

        # 2. Verified offer metrics
        total_verified_offers = db.query(PlacementOffer).count()
        accepted_offers_count = db.query(PlacementOffer).filter(
            PlacementOffer.acceptance_status == OfferAcceptanceStatus.ACCEPTED
        ).count()
        declined_offers_count = db.query(PlacementOffer).filter(
            PlacementOffer.acceptance_status == OfferAcceptanceStatus.DECLINED
        ).count()
        rescinded_offers_count = db.query(PlacementOffer).filter(
            PlacementOffer.acceptance_status == OfferAcceptanceStatus.RESCINDED
        ).count()
        pending_offers_count = db.query(PlacementOffer).filter(
            PlacementOffer.acceptance_status == OfferAcceptanceStatus.OFFERED
        ).count()

        # 3. Final verified placed students count (unique students with >= 1 ACCEPTED offer)
        verified_placed_student_ids = set(
            r[0] for r in db.query(PlacementOffer.student_id).filter(
                PlacementOffer.acceptance_status == OfferAcceptanceStatus.ACCEPTED
            ).all()
        )
        verified_placed_students_count = len(verified_placed_student_ids)
        verified_placement_rate = (
            (verified_placed_students_count / total_students * 100.0) if total_students > 0 else 0.0
        )

        # 4. Students with multiple verified active offers (excluding RESCINDED)
        multi_offer_rows = (
            db.query(PlacementOffer.student_id)
            .filter(PlacementOffer.acceptance_status != OfferAcceptanceStatus.RESCINDED)
            .group_by(PlacementOffer.student_id)
            .having(func.count(PlacementOffer.id) > 1)
            .all()
        )
        students_with_multiple_offers_count = len(multi_offer_rows)

        return {
            "total_students": total_students,
            # Legacy metrics
            "legacy_placed_count": legacy_placed_count,
            "legacy_placement_rate": round(legacy_placement_rate, 2),
            "total_placed": legacy_placed_count,  # backward compatibility alias
            "placement_rate": round(legacy_placement_rate, 2),  # backward compatibility alias
            # Verified accounting metrics
            "total_verified_offers": total_verified_offers,
            "accepted_offers_count": accepted_offers_count,
            "declined_offers_count": declined_offers_count,
            "rescinded_offers_count": rescinded_offers_count,
            "pending_offers_count": pending_offers_count,
            "verified_placed_students_count": verified_placed_students_count,
            "students_with_multiple_offers_count": students_with_multiple_offers_count,
            "verified_placement_rate": round(verified_placement_rate, 2),
        }


# Singleton instance
placement_offer_service = PlacementOfferService()
