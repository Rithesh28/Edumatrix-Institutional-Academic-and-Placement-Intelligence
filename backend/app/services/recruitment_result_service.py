"""
Recruitment Result Service

Orchestrates recruitment result file extraction, student identity matching,
officer review, transactional confirmation, and deduplicated notification delivery.
"""

import re
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from ..models.user import User, UserRole
from ..models.company import Company
from ..models.job_posting import JobPosting, JobStatus
from ..models.recruitment_circular import RecruitmentCircular
from ..models.file import File
from ..models.application import Application, ApplicationStatus
from ..models.profile import StudentProfileExtended, PlacementStatus
from ..models.notification import Notification
from ..models.recruitment_result import (
    RecruitmentResultBatch,
    RecruitmentResultBatchStatus,
    RecruitmentResultItem,
    RecruitmentResultItemStatus,
    RecruitmentResultReviewState,
)
from ..models.recruitment_round import (
    RecruitmentRound,
    StudentRoundOutcome,
    RoundOutcome,
)
from ..services.file_storage.minio_client import minio_client
from ..services.recruitment_result_extractor import recruitment_result_extractor
from ..services.recruitment_result_matcher import recruitment_result_matcher
from ..services.audit_service import audit_service
from ..services.recruitment_progression_service import recruitment_progression_service

logger = logging.getLogger(__name__)


class RecruitmentResultService:
    """Service handling recruitment result workflows."""

    @staticmethod
    def map_result_status_to_round_outcome(
        status: RecruitmentResultItemStatus,
        is_final_round: bool = False,
        legacy_offered: bool = False,
    ) -> RoundOutcome:
        """
        Maps tabular RecruitmentResultItemStatus to authoritative RoundOutcome.
        
        Mapping rules (Phase 3.3.4 verified event semantics):
        - REJECTED -> RoundOutcome.REJECTED
        - ABSENT -> RoundOutcome.ABSENT
        - ON_HOLD -> RoundOutcome.ON_HOLD
        - SHORTLISTED -> RoundOutcome.CLEARED (passed/shortlisted for next stage)
        - SELECTED in intermediate round -> RoundOutcome.CLEARED (cleared intermediate stage)
        - SELECTED in final round -> RoundOutcome.CLEARED (cleared final recruitment round).
          Ordinary final-round clearance does not assume an employer-issued offer has been verified.
          If legacy_offered=True is explicitly passed, returns RoundOutcome.OFFERED for backwards
          compatibility with historical test expectations.
        """
        if status == RecruitmentResultItemStatus.REJECTED:
            return RoundOutcome.REJECTED
        elif status == RecruitmentResultItemStatus.ABSENT:
            return RoundOutcome.ABSENT
        elif status == RecruitmentResultItemStatus.ON_HOLD:
            return RoundOutcome.ON_HOLD
        elif status == RecruitmentResultItemStatus.SHORTLISTED:
            return RoundOutcome.CLEARED
        elif status == RecruitmentResultItemStatus.SELECTED:
            if is_final_round and legacy_offered:
                return RoundOutcome.OFFERED
            return RoundOutcome.CLEARED
        else:
            raise ValueError(f"Unknown or unsupported candidate status '{status}'. Cannot map to RoundOutcome.")


    # =========================================================================
    # BATCH CREATION & EXTRACTION (UPLOAD STEP)
    # =========================================================================
    def upload_and_process_result_file(
        self,
        db: Session,
        company_id: int,
        file_id: UUID,
        round_name: str,
        round_type: str = "assessment",
        is_final_round: bool = False,
        job_posting_id: Optional[int] = None,
        circular_id: Optional[int] = None,
        round_id: Optional[int] = None,
        current_user: Optional[User] = None,
    ) -> RecruitmentResultBatch:
        """
        Processes an uploaded result document:
        1. Validates company, job, round, and circular consistency
        2. Downloads file from MinIO
        3. Extracts structured candidate rows via recruitment_result_extractor
        4. Matches each row conservatively against active students
        5. Persists batch and items with review state (does NOT confirm or notify)
        """
        # 1. Company check
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise ValueError(f"Company ID {company_id} not found.")

        # 2. Round consistency if specified
        rec_round: Optional[RecruitmentRound] = None
        if round_id:
            rec_round = db.query(RecruitmentRound).filter(RecruitmentRound.id == round_id).first()
            if not rec_round:
                raise ValueError(f"Recruitment round #{round_id} not found.")
            if job_posting_id and job_posting_id != rec_round.job_posting_id:
                raise ValueError(
                    f"Round #{round_id} belongs to Job #{rec_round.job_posting_id}, but batch specified Job #{job_posting_id}. Cross-job linking is prohibited."
                )
            if not job_posting_id:
                job_posting_id = rec_round.job_posting_id
            if rec_round.job_posting and rec_round.job_posting.company_id != company_id:
                raise ValueError(
                    f"Round #{round_id} company (#{rec_round.job_posting.company_id}) does not match batch company (#{company_id}). Cross-company linking is prohibited."
                )

        # 3. Job consistency
        job: Optional[JobPosting] = None
        if job_posting_id:
            job = db.query(JobPosting).filter(JobPosting.id == job_posting_id).first()
            if not job:
                raise ValueError(f"JobPosting ID {job_posting_id} not found.")
            if job.company_id != company_id:
                raise ValueError(f"JobPosting ID {job_posting_id} belongs to a different company.")

        # 4. Circular consistency
        circular: Optional[RecruitmentCircular] = None
        if circular_id:
            circular = db.query(RecruitmentCircular).filter(RecruitmentCircular.id == circular_id).first()
            if not circular:
                raise ValueError(f"RecruitmentCircular ID {circular_id} not found.")
            if circular.company_id != company_id:
                raise ValueError(f"RecruitmentCircular ID {circular_id} belongs to a different company.")

        # 5. Retrieve File metadata and download bytes
        file_record = db.query(File).filter(File.id == file_id).first()
        if not file_record:
            raise ValueError(f"File ID {file_id} not found.")

        try:
            file_bytes = minio_client.download_file(file_record.bucket, file_record.object_key)
        except Exception as e:
            logger.error(f"Failed to retrieve file {file_id} from storage: {e}", exc_info=True)
            raise ValueError(f"Could not retrieve file content from storage: {str(e)}")

        # 6. Extract structured candidate rows
        extracted = recruitment_result_extractor.extract_candidates_from_bytes(
            file_bytes=file_bytes, filename=file_record.filename
        )

        rows = extracted.get("rows", [])
        if not rows:
            raise ValueError("No candidate records found in the uploaded file.")

        # Gather branch eligibility hints
        job_branches: Optional[List[str]] = None
        if job and job.branch_eligibility and isinstance(job.branch_eligibility, (list, tuple)):
            job_branches = [str(b) for b in job.branch_eligibility if b]
        elif circular and circular.branch_eligibility and isinstance(circular.branch_eligibility, (list, tuple)):
            job_branches = [str(b) for b in circular.branch_eligibility if b]

        # 7. Create Batch record
        batch = RecruitmentResultBatch(
            company_id=company_id,
            job_posting_id=job_posting_id,
            circular_id=circular_id,
            file_id=file_id,
            round_id=round_id,
            round_name=round_name.strip(),
            round_type=round_type.strip().lower(),
            is_final_round=bool(rec_round.is_final) if rec_round else bool(is_final_round),
            status=RecruitmentResultBatchStatus.IN_REVIEW,
            total_rows=len(rows),
            matched_count=0,
            ambiguous_count=0,
            confirmed_count=0,
            uploaded_by=current_user.id if current_user else None,
        )
        db.add(batch)
        db.flush()  # assign batch.id

        matched_count = 0
        ambiguous_count = 0

        # 7. Match candidate rows against students
        for row in rows:
            match_res = recruitment_result_matcher.match_row(
                db=db,
                extracted_usn=row.get("extracted_usn"),
                extracted_email=row.get("extracted_email"),
                extracted_name=row.get("extracted_name"),
                extracted_branch=row.get("extracted_branch"),
                job_branches=job_branches,
            )

            rev_status = match_res["review_status"]
            if rev_status == RecruitmentResultReviewState.MATCHED:
                matched_count += 1
            elif rev_status == RecruitmentResultReviewState.AMBIGUOUS:
                ambiguous_count += 1

            # Map normalized status enum
            raw_norm_status = row.get("normalized_status", "shortlisted").lower()
            try:
                norm_status_enum = RecruitmentResultItemStatus(raw_norm_status)
            except ValueError:
                norm_status_enum = RecruitmentResultItemStatus.SHORTLISTED

            item = RecruitmentResultItem(
                batch_id=batch.id,
                row_index=row["row_index"],
                source_page=row.get("source_page", 1),
                raw_data=row.get("raw_data", {}),
                extracted_usn=row.get("extracted_usn"),
                extracted_name=row.get("extracted_name"),
                extracted_email=row.get("extracted_email"),
                extracted_status_raw=row.get("extracted_status_raw"),
                extracted_remarks=row.get("extracted_remarks"),
                normalized_status=norm_status_enum,
                matched_student_id=match_res.get("matched_student_id"),
                match_confidence=match_res.get("match_confidence", 0.0),
                match_method=match_res.get("match_method"),
                match_evidence=match_res.get("match_evidence"),
                review_status=rev_status,
                notification_sent=False,
            )
            db.add(item)

        batch.matched_count = matched_count
        batch.ambiguous_count = ambiguous_count

        db.commit()
        db.refresh(batch)

        logger.info(
            f"✅ Created result batch ID {batch.id} for {company.name}: "
            f"{len(rows)} rows ({matched_count} matched, {ambiguous_count} ambiguous)"
        )

        # Audit logging
        audit_service.log_action(
            db=db,
            action="RECRUITMENT_RESULT_BATCH_UPLOADED",
            actor=current_user,
            target_type="recruitment_result_batch",
            target_id=str(batch.id),
            details={
                "company_id": company_id,
                "company_name": company.name,
                "round_name": round_name,
                "total_rows": len(rows),
                "matched_count": matched_count,
                "ambiguous_count": ambiguous_count,
                "is_final_round": is_final_round,
            },
        )

        return batch

    # =========================================================================
    # QUERY BATCHES & ITEMS
    # =========================================================================
    def get_batches(
        self,
        db: Session,
        company_id: Optional[int] = None,
        job_posting_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List result batches with rich relational summaries."""
        query = db.query(RecruitmentResultBatch).options(
            joinedload(RecruitmentResultBatch.company),
            joinedload(RecruitmentResultBatch.job_posting),
            joinedload(RecruitmentResultBatch.circular),
            joinedload(RecruitmentResultBatch.file),
            joinedload(RecruitmentResultBatch.round),
            joinedload(RecruitmentResultBatch.uploader),
        )

        if company_id:
            query = query.filter(RecruitmentResultBatch.company_id == company_id)
        if job_posting_id:
            query = query.filter(RecruitmentResultBatch.job_posting_id == job_posting_id)
        if status:
            query = query.filter(RecruitmentResultBatch.status == status)

        batches = query.order_by(RecruitmentResultBatch.created_at.desc()).offset(skip).limit(limit).all()
        return [self._serialize_batch(b, include_items=False) for b in batches]

    def get_batch_by_id(
        self, db: Session, batch_id: int, include_items: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Retrieve batch detail and all candidate items."""
        batch = (
            db.query(RecruitmentResultBatch)
            .options(
                joinedload(RecruitmentResultBatch.company),
                joinedload(RecruitmentResultBatch.job_posting),
                joinedload(RecruitmentResultBatch.circular),
                joinedload(RecruitmentResultBatch.file),
                joinedload(RecruitmentResultBatch.round),
                joinedload(RecruitmentResultBatch.uploader),
                joinedload(RecruitmentResultBatch.items).joinedload(RecruitmentResultItem.matched_student).joinedload(User.student_profile),
            )
            .filter(RecruitmentResultBatch.id == batch_id)
            .first()
        )
        if not batch:
            return None
        return self._serialize_batch(batch, include_items=include_items)

    def _serialize_batch(
        self, batch: RecruitmentResultBatch, include_items: bool = False
    ) -> Dict[str, Any]:
        """Convert RecruitmentResultBatch to serializable dictionary."""
        data = {
            "id": batch.id,
            "company_id": batch.company_id,
            "company_name": batch.company.name if batch.company else None,
            "job_posting_id": batch.job_posting_id,
            "job_title": batch.job_posting.title if batch.job_posting else None,
            "circular_id": batch.circular_id,
            "circular_title": batch.circular.title if batch.circular else None,
            "file_id": batch.file_id,
            "filename": batch.file.filename if batch.file else None,
            "round_id": batch.round_id,
            "round_number": batch.round.round_number if batch.round else None,
            "round_name": batch.round_name,
            "round_type": batch.round_type,
            "is_final_round": batch.is_final_round,
            "status": batch.status.value if hasattr(batch.status, "value") else str(batch.status),
            "total_rows": batch.total_rows,
            "matched_count": batch.matched_count,
            "ambiguous_count": batch.ambiguous_count,
            "confirmed_count": batch.confirmed_count,
            "uploaded_by": batch.uploaded_by,
            "uploader_name": batch.uploader.name if batch.uploader else None,
            "created_at": batch.created_at,
            "updated_at": batch.updated_at,
            "items": [],
        }

        if include_items and batch.items:
            items_list = []
            for item in batch.items:
                matched_user = item.matched_student
                profile = matched_user.student_profile if matched_user else None
                items_list.append({
                    "id": item.id,
                    "batch_id": item.batch_id,
                    "row_index": item.row_index,
                    "source_page": item.source_page,
                    "raw_data": item.raw_data or {},
                    "extracted_usn": item.extracted_usn,
                    "extracted_name": item.extracted_name,
                    "extracted_email": item.extracted_email,
                    "extracted_status_raw": item.extracted_status_raw,
                    "extracted_remarks": item.extracted_remarks,
                    "normalized_status": item.normalized_status.value if hasattr(item.normalized_status, "value") else str(item.normalized_status),
                    "matched_student_id": item.matched_student_id,
                    "matched_student_name": matched_user.name if matched_user else None,
                    "matched_student_email": matched_user.email if matched_user else None,
                    "matched_student_usn": profile.enrollment_number if profile else None,
                    "matched_student_branch": profile.branch if profile else (matched_user.department if matched_user else None),
                    "matched_student": {
                        "id": matched_user.id,
                        "name": matched_user.name,
                        "full_name": profile.full_name if (profile and profile.full_name) else matched_user.name,
                        "email": matched_user.email,
                        "usn": profile.enrollment_number if profile else None,
                        "department": profile.branch if profile else matched_user.department,
                    } if matched_user else None,
                    "match_confidence": item.match_confidence,
                    "match_method": item.match_method,
                    "match_evidence": item.match_evidence,
                    "review_status": item.review_status.value if hasattr(item.review_status, "value") else str(item.review_status),
                    "confirmed_by": item.confirmed_by,
                    "confirmed_at": item.confirmed_at,
                    "notification_sent": item.notification_sent,
                })
            data["items"] = items_list

        return data

    # =========================================================================
    # MANUAL MATCH OVERRIDE & STATUS UPDATE
    # =========================================================================
    def update_item_match(
        self,
        db: Session,
        item_id: int,
        student_id: Optional[int] = None,
        review_status: Optional[str] = None,
        current_user: Optional[User] = None,
    ) -> Dict[str, Any]:
        """
        Manually assign, override, or clear student identity for a candidate item.
        Records an audit log entry for provenance.
        """
        item = db.query(RecruitmentResultItem).filter(RecruitmentResultItem.id == item_id).first()
        if not item:
            raise ValueError(f"RecruitmentResultItem ID {item_id} not found.")

        batch = db.query(RecruitmentResultBatch).filter(RecruitmentResultBatch.id == item.batch_id).first()

        old_student_id = item.matched_student_id
        old_review_status = item.review_status.value if hasattr(item.review_status, "value") else str(item.review_status)

        if student_id is not None:
            # Assign student
            student = db.query(User).options(joinedload(User.student_profile)).filter(
                User.id == student_id,
                User.role == UserRole.STUDENT,
                User.is_active == True
            ).first()
            if not student:
                raise ValueError(f"Active student with ID {student_id} not found.")

            item.matched_student_id = student.id
            item.match_confidence = 1.00
            item.match_method = "MANUAL_OVERRIDE"
            item.review_status = RecruitmentResultReviewState.MATCHED

            evidence = dict(item.match_evidence or {})
            evidence["manual_override"] = {
                "assigned_by": current_user.email if current_user else "officer",
                "assigned_at": datetime.utcnow().isoformat(),
                "previous_student_id": old_student_id,
                "student": {
                    "id": student.id,
                    "name": student.name,
                    "email": student.email,
                    "usn": student.student_profile.enrollment_number if student.student_profile else None,
                }
            }
            item.match_evidence = evidence

            # Clear or update state
            if review_status:
                norm_rev = review_status.lower()
                if norm_rev in ["unmatched", "unresolved"]:
                    rev_enum = RecruitmentResultReviewState.UNRESOLVED
                elif norm_rev in ["resolved", "matched"]:
                    rev_enum = RecruitmentResultReviewState.MATCHED
                else:
                    try:
                        rev_enum = RecruitmentResultReviewState(norm_rev)
                    except ValueError:
                        raise ValueError(f"Invalid review state '{review_status}'.")
                item.review_status = rev_enum
                if rev_enum in [RecruitmentResultReviewState.UNRESOLVED, RecruitmentResultReviewState.IGNORED]:
                    item.matched_student_id = None
                    item.match_confidence = 0.0
                    item.match_method = "MANUAL_CLEARED"
            else:
                item.matched_student_id = None
                item.match_confidence = 0.0
                item.match_method = "MANUAL_CLEARED"
                item.review_status = RecruitmentResultReviewState.UNRESOLVED

        # Recompute batch counts
        if batch:
            batch.matched_count = db.query(RecruitmentResultItem).filter(
                RecruitmentResultItem.batch_id == batch.id,
                RecruitmentResultItem.review_status == RecruitmentResultReviewState.MATCHED
            ).count()
            batch.ambiguous_count = db.query(RecruitmentResultItem).filter(
                RecruitmentResultItem.batch_id == batch.id,
                RecruitmentResultItem.review_status == RecruitmentResultReviewState.AMBIGUOUS
            ).count()

        db.commit()
        db.refresh(item)

        # Audit log
        audit_service.log_action(
            db=db,
            action="RECRUITMENT_RESULT_MATCH_OVERRIDDEN",
            actor=current_user,
            target_type="recruitment_result_item",
            target_id=str(item.id),
            details={
                "batch_id": item.batch_id,
                "old_student_id": old_student_id,
                "new_student_id": item.matched_student_id,
                "old_review_status": old_review_status,
                "new_review_status": item.review_status.value,
            }
        )

        return self.get_batch_by_id(db, item.batch_id, include_items=True)

    # =========================================================================
    # TRANSACTIONAL CONFIRMATION & NOTIFICATIONS
    # =========================================================================
    def _confirm_round_linked_batch(
        self,
        db: Session,
        batch: RecruitmentResultBatch,
        items_to_confirm: List[RecruitmentResultItem],
        officer_id: Optional[int],
        current_user: Optional[User],
        now: datetime,
    ) -> Dict[str, Any]:
        """
        Executes atomic confirmation for a batch explicitly linked to a RecruitmentRound.
        Integrates with RecruitmentProgressionService ledger, enforces cross-job/company boundaries,
        emits contextual round notifications, and leaves profile placement status untouched.
        """
        rec_round = db.query(RecruitmentRound).filter(RecruitmentRound.id == batch.round_id).first()
        if not rec_round:
            raise ValueError(f"Linked RecruitmentRound #{batch.round_id} not found.")

        # Cross-job boundary verification
        if batch.job_posting_id and rec_round.job_posting_id != batch.job_posting_id:
            raise ValueError(
                f"Batch #{batch.id} belongs to Job #{batch.job_posting_id}, but linked Round #{rec_round.id} "
                f"belongs to Job #{rec_round.job_posting_id}. Cross-job confirmation is prohibited."
            )

        # Cross-company boundary verification
        if rec_round.job_posting and batch.company_id != rec_round.job_posting.company_id:
            raise ValueError(
                f"Batch #{batch.id} company (#{batch.company_id}) does not match round company "
                f"(#{rec_round.job_posting.company_id}). Cross-company confirmation is prohibited."
            )

        seen_students_in_batch = set()
        confirmed_count = 0
        notifications_dispatched = 0
        outcomes_recorded = 0

        try:
            for item in items_to_confirm:
                student_id = item.matched_student_id
                norm_status = item.normalized_status

                # 1. Validate student active status
                student = db.query(User).filter(User.id == student_id).first()
                if not student:
                    raise ValueError(f"Student #{student_id} not found.")
                if not student.is_active:
                    raise ValueError(f"Student #{student_id} ({student.email}) is inactive.")

                # 2. Find or create application for this job posting
                target_job_id = batch.job_posting_id or rec_round.job_posting_id
                application = (
                    db.query(Application)
                    .filter(
                        Application.student_id == student_id,
                        Application.job_posting_id == target_job_id,
                    )
                    .first()
                )
                if not application:
                    application = Application(
                        student_id=student_id,
                        job_posting_id=target_job_id,
                        status=ApplicationStatus.APPLIED,
                        notes=f"Auto-registered via recruitment result batch {batch.id} ({rec_round.name})",
                    )
                    db.add(application)
                    db.flush()

                # 3. Map tabular status to authoritative RoundOutcome
                is_final = bool(rec_round.is_final) or bool(batch.is_final_round)
                outcome = self.map_result_status_to_round_outcome(norm_status, is_final_round=is_final)

                # 4. Record progression outcome (atomic flush inside session)
                recruitment_progression_service.record_student_round_outcome(
                    db=db,
                    application_id=application.id,
                    round_id=rec_round.id,
                    outcome=outcome,
                    score=None,
                    remarks=item.extracted_remarks,
                    source_batch_id=batch.id,
                    source_item_id=item.id,
                    current_user=current_user,
                    auto_commit=False,
                )
                outcomes_recorded += 1

                # 5. Mark item as CONFIRMED
                item.review_status = RecruitmentResultReviewState.CONFIRMED
                item.confirmed_by = officer_id
                item.confirmed_at = now
                confirmed_count += 1

                # 6. Status Semantics (Application status only, NEVER profile placement status!)
                is_final_stage = bool(rec_round.is_final) or bool(batch.is_final_round)
                if outcome == RoundOutcome.CLEARED:
                    if is_final_stage:
                        application.status = ApplicationStatus.SELECTED
                        if not application.notes or application.notes.startswith("Auto-registered"):
                            application.notes = f"Final selection confirmed: Round {rec_round.round_number} ({rec_round.name}) at {batch.company.name}"
                    else:
                        application.status = ApplicationStatus.SHORTLISTED
                        if not application.notes or application.notes.startswith("Auto-registered"):
                            application.notes = f"Progressed: Round {rec_round.round_number} ({rec_round.name}) at {batch.company.name}"
                elif outcome == RoundOutcome.REJECTED:
                    application.status = ApplicationStatus.REJECTED
                    if not application.notes or application.notes.startswith("Auto-registered"):
                        application.notes = f"Round result: Round {rec_round.round_number} ({rec_round.name}) - Not Selected"
                elif outcome == RoundOutcome.OFFERED:
                    # Backward compatibility for legacy/historical records
                    application.status = ApplicationStatus.SELECTED
                    if not application.notes or application.notes.startswith("Auto-registered"):
                        application.notes = f"Final selection confirmed: Round {rec_round.round_number} ({rec_round.name}) at {batch.company.name}"
                elif outcome in [RoundOutcome.ABSENT, RoundOutcome.ON_HOLD]:
                    if not application.notes or application.notes.startswith("Auto-registered"):
                        application.notes = f"Round result: Round {rec_round.round_number} ({rec_round.name}) ({outcome.value})"

                # 7. Deduplicated Notification Delivery
                if student_id not in seen_students_in_batch:
                    seen_students_in_batch.add(student_id)
                    event_key = f"recruitment_round:{rec_round.id}:student:{student_id}:batch:{batch.id}"
                    existing_notif = db.query(Notification).filter(Notification.event_key == event_key).first()

                    if not existing_notif:
                        company_name = batch.company.name if batch.company else "Campus Recruiter"
                        job_title = (
                            batch.job_posting.title
                            if batch.job_posting
                            else (rec_round.job_posting.title if rec_round.job_posting else "Campus Role")
                        )
                        round_label = f"Round {rec_round.round_number} ({rec_round.name})"

                        if outcome == RoundOutcome.OFFERED or (outcome == RoundOutcome.CLEARED and is_final_stage):
                            title = f"🎉 Final Selection: {round_label} at {company_name}"
                            message = (
                                f"Congratulations! You have been selected in {round_label} "
                                f"for {job_title} at {company_name}."
                            )
                        elif outcome == RoundOutcome.CLEARED:
                            title = f"⭐ Cleared: {round_label} at {company_name}"
                            message = (
                                f"You have cleared {round_label} "
                                f"for {job_title} at {company_name}. Check Campus Jobs for updates."
                            )

                        elif outcome == RoundOutcome.REJECTED:
                            title = f"Update: {round_label} at {company_name}"
                            message = f"Results for {round_label} for {job_title} at {company_name} have been published."
                        elif outcome == RoundOutcome.ON_HOLD:
                            title = f"On Hold: {round_label} at {company_name}"
                            message = f"Your result for {round_label} at {company_name} is currently on hold."
                        else:
                            title = f"Placement Result Update: {company_name}"
                            message = (
                                f"Your status for {round_label} at {company_name} is updated: {outcome.value}."
                            )

                        notif = Notification(
                            user_id=student_id,
                            type="placement_result",
                            title=title,
                            message=message,
                            reference_id=target_job_id or batch.id,
                            event_key=event_key,
                            is_read=False,
                        )
                        db.add(notif)
                        item.notification_sent = True
                        item.notification_event_key = event_key
                        notifications_dispatched += 1
                    else:
                        item.notification_sent = True
                        item.notification_event_key = existing_notif.event_key
                else:
                    item.notification_sent = True

            # Flush pending changes to session before calculating summary counts
            db.flush()

            # Update batch summary counts
            total_confirmed = db.query(RecruitmentResultItem).filter(
                RecruitmentResultItem.batch_id == batch.id,
                RecruitmentResultItem.review_status == RecruitmentResultReviewState.CONFIRMED,
            ).count()
            batch.confirmed_count = total_confirmed
            if total_confirmed >= batch.total_rows:
                batch.status = RecruitmentResultBatchStatus.FULLY_CONFIRMED
            else:
                batch.status = RecruitmentResultBatchStatus.PARTIALLY_CONFIRMED
            batch.updated_at = now

            db.commit()

        except Exception:
            db.rollback()
            raise

        # Audit log
        audit_service.log_action(
            db=db,
            action="RECRUITMENT_RESULT_BATCH_CONFIRMED",
            actor=current_user,
            target_type="recruitment_result_batch",
            target_id=str(batch.id),
            details={
                "confirmed_count": confirmed_count,
                "notifications_dispatched": notifications_dispatched,
                "outcomes_recorded": outcomes_recorded,
                "is_final_round": is_final,
                "round_id": rec_round.id,
                "round_number": rec_round.round_number,
                "round_name": rec_round.name,
            },
        )

        return {
            "batch_id": batch.id,
            "confirmed_count": confirmed_count,
            "notifications_dispatched": notifications_dispatched,
            "skipped_count": len(items_to_confirm) - confirmed_count,
            "is_final_round": is_final,
            "batch_status": batch.status.value,
            "round_id": rec_round.id,
            "outcomes_recorded": outcomes_recorded,
            "message": f"Successfully confirmed {confirmed_count} records into Round #{rec_round.round_number} ({rec_round.name}). Sent {notifications_dispatched} notifications.",
        }

    def confirm_batch_results(
        self,
        db: Session,
        batch_id: int,
        item_ids: Optional[List[int]] = None,
        current_user: Optional[User] = None,
    ) -> Dict[str, Any]:
        """
        Explicitly confirms matched candidate records:
        1. Validates selected items (must have matched_student_id and cannot be ambiguous).
        2. Transactionally marks items as CONFIRMED with officer timestamp.
        3. Updates student application/profile status strictly according to round semantics:
           - Intermediate round: updates Application.status to SHORTLISTED/REJECTED (NEVER sets SELECTED or PLACED!).
           - Final offer round (is_final_round=True AND item.normalized_status=SELECTED):
             sets Application.status = SELECTED and StudentProfileExtended.placement_status = PLACED.
        4. Dispatches deduplicated student notifications using unique event_key.
        """
        batch = (
            db.query(RecruitmentResultBatch)
            .options(
                joinedload(RecruitmentResultBatch.company),
                joinedload(RecruitmentResultBatch.job_posting),
                joinedload(RecruitmentResultBatch.round),
            )
            .filter(RecruitmentResultBatch.id == batch_id)
            .first()
        )
        if not batch:
            raise ValueError(f"RecruitmentResultBatch ID {batch_id} not found.")

        # Determine target items
        items_query = db.query(RecruitmentResultItem).filter(
            RecruitmentResultItem.batch_id == batch_id,
            RecruitmentResultItem.review_status != RecruitmentResultReviewState.CONFIRMED,
        )
        if item_ids and len(item_ids) > 0:
            items_query = items_query.filter(RecruitmentResultItem.id.in_(item_ids))
        else:
            # Default to all matched items
            items_query = items_query.filter(
                RecruitmentResultItem.review_status == RecruitmentResultReviewState.MATCHED
            )

        items_to_confirm = items_query.all()
        if not items_to_confirm:
            return {
                "batch_id": batch.id,
                "confirmed_count": 0,
                "notifications_dispatched": 0,
                "skipped_count": 0,
                "is_final_round": batch.is_final_round,
                "batch_status": batch.status.value if hasattr(batch.status, "value") else str(batch.status),
                "message": "All selected candidate items are already confirmed or none eligible.",
            }

        # Check for unlinked or ambiguous items in explicit selection
        for item in items_to_confirm:
            if not item.matched_student_id:
                raise ValueError(
                    f"Row {item.row_index} cannot be confirmed because it has no matched student. "
                    "Assign a student or uncheck this item before confirming."
                )
            if item.review_status == RecruitmentResultReviewState.AMBIGUOUS:
                raise ValueError(
                    f"Row {item.row_index} is flagged as AMBIGUOUS. "
                    "Please review and verify the student match before confirmation."
                )
            if item.review_status in [
                RecruitmentResultReviewState.UNRESOLVED,
                RecruitmentResultReviewState.IGNORED,
                RecruitmentResultReviewState.PENDING,
            ]:
                raise ValueError(
                    f"Row {item.row_index} has review state '{item.review_status.value}' and cannot be confirmed. "
                    "Only matched rows can be confirmed."
                )

        now = datetime.utcnow()
        officer_id = current_user.id if current_user else None

        # ---------------------------------------------------------------------
        # ROUTE ROUND-LINKED BATCH TO PROGRESSION LEDGER SERVICE
        # ---------------------------------------------------------------------
        if batch.round_id is not None:
            return self._confirm_round_linked_batch(
                db=db,
                batch=batch,
                items_to_confirm=items_to_confirm,
                officer_id=officer_id,
                current_user=current_user,
                now=now,
            )

        # ---------------------------------------------------------------------
        # LEGACY CONFIRMATION WORKFLOW (FOR BATCHES WITH round_id = NULL)
        # ---------------------------------------------------------------------
        confirmed_count = 0
        notifications_dispatched = 0

        round_slug = re.sub(r"[^a-zA-Z0-9]+", "_", batch.round_name.lower()).strip("_")

        for item in items_to_confirm:
            student_id = item.matched_student_id
            norm_status = item.normalized_status

            # Mark item as CONFIRMED
            item.review_status = RecruitmentResultReviewState.CONFIRMED
            item.confirmed_by = officer_id
            item.confirmed_at = now
            confirmed_count += 1

            # -------------------------------------------------------------
            # STATUS SEMANTICS (CRITICAL ACCURACY GUARD)
            # -------------------------------------------------------------
            if batch.job_posting_id:
                # Find or create application
                application = (
                    db.query(Application)
                    .filter(
                        Application.student_id == student_id,
                        Application.job_posting_id == batch.job_posting_id,
                    )
                    .first()
                )
                if not application:
                    application = Application(
                        student_id=student_id,
                        job_posting_id=batch.job_posting_id,
                        status=ApplicationStatus.APPLIED,
                        notes=f"Auto-registered via recruitment result batch {batch.id} ({batch.round_name})",
                    )
                    db.add(application)
                    db.flush()

                if batch.is_final_round and norm_status == RecruitmentResultItemStatus.SELECTED:
                    # FINAL PLACEMENT OFFER
                    application.status = ApplicationStatus.SELECTED
                    application.notes = f"Final selection confirmed: {batch.round_name} at {batch.company.name}"

                    # Update profile placement status to PLACED
                    profile = db.query(StudentProfileExtended).filter(
                        StudentProfileExtended.user_id == student_id
                    ).first()
                    if profile:
                        profile.placement_status = PlacementStatus.PLACED

                else:
                    # INTERMEDIATE ROUND (or non-final selection)
                    # NEVER update placement stats or set to SELECTED / PLACED!
                    if norm_status == RecruitmentResultItemStatus.SHORTLISTED:
                        application.status = ApplicationStatus.SHORTLISTED
                        application.notes = f"Progressed: {batch.round_name} at {batch.company.name}"
                    elif norm_status == RecruitmentResultItemStatus.REJECTED:
                        application.status = ApplicationStatus.REJECTED
                        application.notes = f"Round result: {batch.round_name} - Not Selected"
                    else:
                        application.notes = f"Round result: {batch.round_name} ({norm_status.value})"

            # -------------------------------------------------------------
            # DEDUPLICATED NOTIFICATION DELIVERY
            # -------------------------------------------------------------
            event_key = f"recruitment_result:{batch.id}:student:{student_id}:round:{round_slug}"
            existing_notif = db.query(Notification).filter(Notification.event_key == event_key).first()

            if not existing_notif:
                company_name = batch.company.name if batch.company else "Campus Recruiter"
                if batch.is_final_round and norm_status == RecruitmentResultItemStatus.SELECTED:
                    title = f"🎉 Selected! Placement Offer from {company_name}"
                    message = (
                        f"Congratulations! Your final selection for {batch.round_name} "
                        f"at {company_name} has been confirmed by the Placement Cell."
                    )
                elif norm_status == RecruitmentResultItemStatus.SHORTLISTED:
                    title = f"⭐ Shortlisted: {batch.round_name} at {company_name}"
                    message = (
                        f"You have been shortlisted for {batch.round_name} "
                        f"at {company_name}. Check Campus Jobs for drive updates."
                    )
                elif norm_status == RecruitmentResultItemStatus.REJECTED:
                    title = f"Update: {batch.round_name} at {company_name}"
                    message = f"Results for {batch.round_name} at {company_name} have been updated."
                else:
                    title = f"Placement Result Update: {company_name}"
                    message = f"Your status for {batch.round_name} at {company_name} is updated: {norm_status.value}."

                notif = Notification(
                    user_id=student_id,
                    type="placement_result",
                    title=title,
                    message=message,
                    reference_id=batch.job_posting_id or batch.circular_id or batch.id,
                    event_key=event_key,
                    is_read=False,
                )
                db.add(notif)
                item.notification_sent = True
                item.notification_event_key = event_key
                notifications_dispatched += 1

        # Flush pending changes to session before calculating summary counts
        db.flush()

        # Update batch summary counts
        total_confirmed = db.query(RecruitmentResultItem).filter(
            RecruitmentResultItem.batch_id == batch.id,
            RecruitmentResultItem.review_status == RecruitmentResultReviewState.CONFIRMED,
        ).count()
        batch.confirmed_count = total_confirmed

        if total_confirmed >= batch.total_rows:
            batch.status = RecruitmentResultBatchStatus.FULLY_CONFIRMED
        else:
            batch.status = RecruitmentResultBatchStatus.PARTIALLY_CONFIRMED

        batch.updated_at = now

        db.commit()

        # Audit log
        audit_service.log_action(
            db=db,
            action="RECRUITMENT_RESULT_BATCH_CONFIRMED",
            actor=current_user,
            target_type="recruitment_result_batch",
            target_id=str(batch.id),
            details={
                "confirmed_count": confirmed_count,
                "notifications_dispatched": notifications_dispatched,
                "is_final_round": batch.is_final_round,
                "round_name": batch.round_name,
            },
        )

        return {
            "batch_id": batch.id,
            "confirmed_count": confirmed_count,
            "notifications_dispatched": notifications_dispatched,
            "skipped_count": len(items_to_confirm) - confirmed_count,
            "is_final_round": batch.is_final_round,
            "batch_status": batch.status.value,
            "message": f"Successfully confirmed {confirmed_count} records. Sent {notifications_dispatched} notifications.",
        }

    # =========================================================================
    # STUDENT LOOKUP FOR MANUAL MATCHING UI
    # =========================================================================
    def search_students(
        self, db: Session, query: str, limit: int = 15
    ) -> List[Dict[str, Any]]:
        """Typeahead search across USN, name, and email for officer review."""
        if not query or len(query.strip()) < 2:
            return []

        q_clean = query.strip()
        q_norm_usn = re.sub(r"[\s\-\/\.]+", "", q_clean).upper()

        students = (
            db.query(User)
            .options(joinedload(User.student_profile))
            .join(StudentProfileExtended, User.id == StudentProfileExtended.user_id, isouter=True)
            .filter(
                User.role == UserRole.STUDENT,
                User.is_active == True,
            )
            .filter(
                (User.name.ilike(f"%{q_clean}%"))
                | (User.email.ilike(f"%{q_clean}%"))
                | (StudentProfileExtended.enrollment_number.ilike(f"%{q_clean}%"))
                | (StudentProfileExtended.full_name.ilike(f"%{q_clean}%"))
            )
            .limit(limit)
            .all()
        )

        results = []
        for s in students:
            p = s.student_profile
            results.append({
                "id": s.id,
                "name": s.name,
                "full_name": p.full_name if (p and p.full_name) else s.name,
                "email": s.email,
                "usn": p.enrollment_number if p else None,
                "branch": p.branch if p else s.department,
                "cgpa": p.cgpa if p else None,
                "year": p.year if p else None,
            })
        return results


# Global singleton instance
recruitment_result_service = RecruitmentResultService()
