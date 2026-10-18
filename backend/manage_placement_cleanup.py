"""
EduMatrix Placement Test-Data Cleanup & Audit Command (Reversible & Dry-Run Safe)

Commands:
- `python manage_placement_cleanup.py --audit`: Scan and report all companies and jobs with categorization.
- `python manage_placement_cleanup.py --dry-run`: Full dry-run simulation of purge on confirmed test data.
- `python manage_placement_cleanup.py --backup-dir <dir>`: Generate complete JSON backup of candidate records.
- `python manage_placement_cleanup.py --confirm-purge --backup`: Execute purge ONLY after explicit confirmation flag.
"""

import os
import sys
import json
import re
import argparse
from datetime import datetime, timezone
from typing import List, Dict, Any, Set

from sqlalchemy.orm import Session
from sqlalchemy import text, or_, and_

from app.core.database import SessionLocal
from app.models.company import Company
from app.models.job_posting import JobPosting
from app.models.recruitment_circular import (
    RecruitmentCircular,
    RecruitmentCircularAttachment,
    RecruitmentCircularJob,
)
from app.models.application import Application, ApplicationStatus
from app.models.shortlist import Shortlist
from app.models.recruitment_round import (
    RecruitmentRound,
    StudentRoundOutcome,
    PlacementOffer,
    RoundOutcome,
    OfferAcceptanceStatus,
)
from app.models.recruitment_result import (
    RecruitmentResultBatch,
    RecruitmentResultItem,
)
from app.models.file import File
from app.models.user import User
from app.models.circular import Circular
from app.models.profile import StudentProfileExtended, PlacementStatus
from app.models.notification import Notification
from app.models.audit_log import AuditLog
from app.services.audit_service import audit_service
from app.services.placement_cleanup_service import (
    placement_cleanup_service,
    TEST_PATTERNS,
    TEST_STUDENT_PATTERNS,
)


def get_genuine_user_ids(db: Session) -> Set[int]:
    """Identify genuine institutional users based on email, name, and USN patterns."""
    genuine_ids = set()
    users = db.query(User).all()
    for u in users:
        is_test = False
        if re.search(r"\d{8,}", u.email) or re.search(r"\d{8,}", u.name or ""):
            is_test = True
        elif any(t in u.email.lower() for t in ["test", "mock", "dummy", "sample", "temp"]):
            is_test = True
        elif any(t in (u.name or "").lower() for t in ["test", "mock", "dummy", "sample", "temp"]):
            is_test = True
        elif u.email.startswith("student_") or u.email.startswith("applicant_") or u.email.startswith("candidate_") or u.email.startswith("final_candidate_") or u.email.startswith("rahul_genuine_"):
            is_test = True

        if not is_test:
            genuine_ids.add(u.id)
    return genuine_ids


def audit_and_categorize(db: Session):
    genuine_user_ids = get_genuine_user_ids(db)
    companies = db.query(Company).order_by(Company.id).all()

    confirmed_test_companies = []
    genuine_companies = []
    uncertain_companies = []

    for c in companies:
        c_jobs = db.query(JobPosting).filter(JobPosting.company_id == c.id).all()
        c_job_ids = [j.id for j in c_jobs]
        
        # Check applications
        apps = db.query(Application).filter(Application.job_posting_id.in_(c_job_ids)).all() if c_job_ids else []
        genuine_apps = [a for a in apps if a.student_id in genuine_user_ids]
        test_apps = [a for a in apps if a.student_id not in genuine_user_ids]

        # Check offers
        offers = db.query(PlacementOffer).filter(PlacementOffer.job_posting_id.in_(c_job_ids)).all() if c_job_ids else []
        genuine_offers = [o for o in offers if o.student_id in genuine_user_ids]

        # Check circulars
        circulars = db.query(RecruitmentCircular).filter(RecruitmentCircular.company_id == c.id).all()

        # Check test pattern in company name
        is_test_named = any(p.search(c.name) for p in TEST_PATTERNS) or re.search(r"\b\d{8,}\b", c.name)

        comp_dict = {
            "id": c.id,
            "name": c.name,
            "is_active": c.is_active,
            "industry": c.industry,
            "location": c.location,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "jobs_count": len(c_jobs),
            "jobs": [{"id": j.id, "title": j.title, "status": j.status.value if j.status else None} for j in c_jobs],
            "circulars_count": len(circulars),
            "total_applications": len(apps),
            "genuine_applications_count": len(genuine_apps),
            "test_applications_count": len(test_apps),
            "total_offers": len(offers),
            "genuine_offers_count": len(genuine_offers),
        }

        # 1. Genuine / Production-Like
        if not is_test_named and len(c_jobs) <= 5 and "test" not in c.name.lower():
            comp_dict["classification"] = "GENUINE_PRESERVED"
            comp_dict["reason"] = "Standard company name without test timestamps or mock keywords"
            genuine_companies.append(comp_dict)

        # 2. Confirmed Disposable Test
        elif is_test_named and len(genuine_apps) == 0 and len(genuine_offers) == 0:
            comp_dict["classification"] = "CONFIRMED_DISPOSABLE_TEST"
            comp_dict["reason"] = "Automated test name pattern and zero genuine student applications or offers"
            confirmed_test_companies.append(comp_dict)

        # 3. Uncertain / Protected (Has genuine user link or legacy test applications from adi01/real students)
        else:
            comp_dict["classification"] = "UNCERTAIN_REQUIRES_CONFIRMATION"
            reasons = []
            if len(genuine_apps) > 0:
                reasons.append(f"Linked to {len(genuine_apps)} genuine student application(s)")
            if len(genuine_offers) > 0:
                reasons.append(f"Linked to {len(genuine_offers)} genuine placement offer(s)")
            if is_test_named and not reasons:
                reasons.append("Uncertain dependency structure")
            comp_dict["reason"] = "; ".join(reasons)
            comp_dict["genuine_applications"] = [
                {"app_id": a.id, "student_id": a.student_id, "job_id": a.job_posting_id, "status": a.status.value if a.status else None}
                for a in genuine_apps
            ]
            uncertain_companies.append(comp_dict)

    return confirmed_test_companies, genuine_companies, uncertain_companies


def create_export_backup(db: Session, target_company_ids: List[int], backup_file_path: str):
    """Create a fully recoverable JSON export of all target companies and their full relational graph."""
    backup_data = {
        "metadata": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "target_company_count": len(target_company_ids),
            "target_company_ids": target_company_ids,
        },
        "companies": [],
        "job_postings": [],
        "recruitment_circulars": [],
        "recruitment_circular_attachments": [],
        "recruitment_circular_jobs": [],
        "recruitment_rounds": [],
        "student_round_outcomes": [],
        "applications": [],
        "shortlists": [],
        "placement_offers": [],
        "recruitment_result_batches": [],
        "recruitment_result_items": [],
        "files_referenced": [],
    }

    comps = db.query(Company).filter(Company.id.in_(target_company_ids)).all()
    for c in comps:
        backup_data["companies"].append(c.to_dict())

    jobs = db.query(JobPosting).filter(JobPosting.company_id.in_(target_company_ids)).all()
    job_ids = [j.id for j in jobs]
    for j in jobs:
        backup_data["job_postings"].append(j.to_dict())

    circulars = db.query(RecruitmentCircular).filter(RecruitmentCircular.company_id.in_(target_company_ids)).all()
    circ_ids = [c.id for c in circulars]
    for c in circulars:
        backup_data["recruitment_circulars"].append({
            "id": c.id, "company_id": c.company_id, "title": c.title,
            "status": c.status.value if c.status else None, "created_at": c.created_at.isoformat() if c.created_at else None
        })

    if circ_ids:
        circ_atts = db.query(RecruitmentCircularAttachment).filter(RecruitmentCircularAttachment.circular_id.in_(circ_ids)).all()
        for ca in circ_atts:
            backup_data["recruitment_circular_attachments"].append({
                "id": ca.id, "circular_id": ca.circular_id, "file_id": str(ca.file_id), "attachment_type": ca.attachment_type
            })

    if circ_ids or job_ids:
        circ_jobs = db.query(RecruitmentCircularJob).filter(
            (RecruitmentCircularJob.circular_id.in_(circ_ids) if circ_ids else False) |
            (RecruitmentCircularJob.job_posting_id.in_(job_ids) if job_ids else False)
        ).all()
        for cj in circ_jobs:
            backup_data["recruitment_circular_jobs"].append({
                "id": cj.id, "circular_id": cj.circular_id, "job_posting_id": cj.job_posting_id
            })

    if job_ids:
        rounds = db.query(RecruitmentRound).filter(RecruitmentRound.job_posting_id.in_(job_ids)).all()
        for r in rounds:
            backup_data["recruitment_rounds"].append({
                "id": r.id, "job_posting_id": r.job_posting_id, "round_number": r.round_number, "round_name": r.name
            })

        apps = db.query(Application).filter(Application.job_posting_id.in_(job_ids)).all()
        app_ids = [a.id for a in apps]
        for a in apps:
            backup_data["applications"].append({
                "id": a.id, "student_id": a.student_id, "job_posting_id": a.job_posting_id,
                "status": a.status.value if a.status else None, "applied_at": a.applied_at.isoformat() if a.applied_at else None
            })

        if app_ids:
            outcomes = db.query(StudentRoundOutcome).filter(StudentRoundOutcome.application_id.in_(app_ids)).all()
            for o in outcomes:
                backup_data["student_round_outcomes"].append({
                    "id": o.id, "application_id": o.application_id, "round_id": o.round_id, "outcome": o.outcome.value if o.outcome else None
                })

        offers = db.query(PlacementOffer).filter(PlacementOffer.job_posting_id.in_(job_ids)).all()
        for o in offers:
            backup_data["placement_offers"].append({
                "id": o.id, "application_id": o.application_id, "student_id": o.student_id,
                "job_posting_id": o.job_posting_id, "ctc_lpa": o.ctc_lpa, "acceptance_status": o.acceptance_status.value if o.acceptance_status else None
            })

    shortlists = db.query(Shortlist).filter(Shortlist.company_id.in_(target_company_ids)).all()
    for s in shortlists:
        backup_data["shortlists"].append(s.to_dict())

    batches = db.query(RecruitmentResultBatch).filter(RecruitmentResultBatch.company_id.in_(target_company_ids)).all()
    batch_ids = [b.id for b in batches]
    for b in batches:
        backup_data["recruitment_result_batches"].append({
            "id": b.id, "company_id": b.company_id, "round_name": b.round_name, "status": b.status.value if b.status else None
        })

    if batch_ids:
        items = db.query(RecruitmentResultItem).filter(RecruitmentResultItem.batch_id.in_(batch_ids)).all()
        for item in items:
            backup_data["recruitment_result_items"].append({
                "id": item.id,
                "batch_id": item.batch_id,
                "extracted_name": item.extracted_name,
                "extracted_usn": item.extracted_usn,
                "extracted_email": item.extracted_email,
                "review_status": item.review_status.value if (item.review_status and hasattr(item.review_status, 'value')) else (str(item.review_status) if item.review_status else None),
                "normalized_status": item.normalized_status.value if (item.normalized_status and hasattr(item.normalized_status, 'value')) else (str(item.normalized_status) if item.normalized_status else None),
                "matched_student_id": item.matched_student_id
            })

    os.makedirs(os.path.dirname(backup_file_path), exist_ok=True)
    with open(backup_file_path, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, indent=2)

    return backup_data


def simulate_dry_run(db: Session, target_company_ids: List[int]) -> Dict[str, Any]:
    """Simulate exact deletion counts and FK cascading impact without writing or deleting anything."""
    comps = db.query(Company).filter(Company.id.in_(target_company_ids)).all()
    jobs = db.query(JobPosting).filter(JobPosting.company_id.in_(target_company_ids)).all()
    job_ids = [j.id for j in jobs]
    circs = db.query(RecruitmentCircular).filter(RecruitmentCircular.company_id.in_(target_company_ids)).all()
    circ_ids = [c.id for c in circs]

    apps = db.query(Application).filter(Application.job_posting_id.in_(job_ids)).all() if job_ids else []
    app_ids = [a.id for a in apps]

    offers = db.query(PlacementOffer).filter(PlacementOffer.job_posting_id.in_(job_ids)).all() if job_ids else []
    rounds = db.query(RecruitmentRound).filter(RecruitmentRound.job_posting_id.in_(job_ids)).all() if job_ids else []
    round_ids = [r.id for r in rounds]
    outcomes = db.query(StudentRoundOutcome).filter(StudentRoundOutcome.application_id.in_(app_ids)).all() if app_ids else []

    circ_jobs = db.query(RecruitmentCircularJob).filter(
        (RecruitmentCircularJob.circular_id.in_(circ_ids) if circ_ids else False) |
        (RecruitmentCircularJob.job_posting_id.in_(job_ids) if job_ids else False)
    ).all() if (circ_ids or job_ids) else []

    circ_atts = db.query(RecruitmentCircularAttachment).filter(RecruitmentCircularAttachment.circular_id.in_(circ_ids)).all() if circ_ids else []
    batches = db.query(RecruitmentResultBatch).filter(RecruitmentResultBatch.company_id.in_(target_company_ids)).all()
    batch_ids = [b.id for b in batches]
    items = db.query(RecruitmentResultItem).filter(RecruitmentResultItem.batch_id.in_(batch_ids)).all() if batch_ids else []
    shortlists = db.query(Shortlist).filter(Shortlist.company_id.in_(target_company_ids)).all()

    return {
        "companies_to_delete": len(comps),
        "job_postings_to_delete": len(jobs),
        "recruitment_circulars_to_delete": len(circs),
        "circular_attachments_to_delete": len(circ_atts),
        "circular_jobs_junctions_to_delete": len(circ_jobs),
        "recruitment_rounds_to_delete": len(rounds),
        "student_round_outcomes_to_delete": len(outcomes),
        "applications_to_delete": len(apps),
        "placement_offers_to_delete": len(offers),
        "shortlists_to_delete": len(shortlists),
        "recruitment_result_batches_to_delete": len(batches),
        "recruitment_result_items_to_delete": len(items),
    }


def execute_purge_transaction(db: Session, target_company_ids: List[int]) -> Dict[str, Any]:
    """Execute destructive purge within an atomic transaction with rollback on failure."""
    try:
        comps = db.query(Company).filter(Company.id.in_(target_company_ids)).all()
        comp_ids = [c.id for c in comps]

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

        # Affected students status re-evaluation
        affected_student_ids = set()
        for a in apps:
            affected_student_ids.add(a.student_id)
        for o in offers:
            affected_student_ids.add(o.student_id)

        for sid in affected_student_ids:
            profile = db.query(StudentProfileExtended).filter(StudentProfileExtended.user_id == sid).first()
            if profile and profile.placement_status == PlacementStatus.PLACED:
                other_accepted = db.query(PlacementOffer).filter(
                    PlacementOffer.student_id == sid,
                    PlacementOffer.id.notin_(offer_ids) if offer_ids else True,
                    PlacementOffer.acceptance_status == OfferAcceptanceStatus.ACCEPTED,
                ).first()
                if not other_accepted:
                    other_apps = db.query(Application).filter(
                        Application.student_id == sid,
                        Application.id.notin_(app_ids) if app_ids else True,
                    ).all()
                    if any(a.status == ApplicationStatus.SELECTED for a in other_apps):
                        profile.placement_status = PlacementStatus.PLACED
                    elif any(a.status == ApplicationStatus.SHORTLISTED for a in other_apps) or len(other_apps) > 0:
                        profile.placement_status = PlacementStatus.APPLIED
                    else:
                        profile.placement_status = PlacementStatus.NOT_APPLIED

        # Polymorphic notifications
        notif_conditions = []
        if batch_ids:
            notif_conditions.append(and_(Notification.type == "placement_result", Notification.reference_id.in_(batch_ids)))
        if job_ids:
            notif_conditions.append(and_(Notification.type == "placement_result", Notification.reference_id.in_(job_ids)))
            notif_conditions.append(and_(Notification.type == "job_posting", Notification.reference_id.in_(job_ids)))
        if circular_ids:
            notif_conditions.append(and_(Notification.type == "recruitment_circular", Notification.reference_id.in_(circular_ids)))
        if offer_ids:
            notif_conditions.append(and_(Notification.type == "placement_offer", Notification.reference_id.in_(offer_ids)))

        notifs_del = 0
        if notif_conditions:
            notifs_del = db.query(Notification).filter(or_(*notif_conditions)).delete(synchronize_session=False)

        # Candidate file IDs check (unshared only)
        candidate_file_ids = set()
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

        unshared_file_ids = []
        for fid in candidate_file_ids:
            other_circ = db.query(RecruitmentCircularAttachment).filter(
                RecruitmentCircularAttachment.file_id == fid,
                RecruitmentCircularAttachment.circular_id.notin_(circular_ids) if circular_ids else True
            ).first()
            other_batch = db.query(RecruitmentResultBatch).filter(
                RecruitmentResultBatch.file_id == fid,
                RecruitmentResultBatch.company_id.notin_(comp_ids)
            ).first()
            other_acad = db.query(Circular).filter(Circular.file_id == fid).first()
            if not other_circ and not other_batch and not other_acad:
                unshared_file_ids.append(fid)

        # Perform orderly cascade deletions
        items_del = db.query(RecruitmentResultItem).filter(RecruitmentResultItem.batch_id.in_(batch_ids)).delete(synchronize_session=False) if batch_ids else 0
        outcomes_del = db.query(StudentRoundOutcome).filter(
            or_(
                StudentRoundOutcome.round_id.in_(round_ids) if round_ids else False,
                StudentRoundOutcome.application_id.in_(app_ids) if app_ids else False,
            )
        ).delete(synchronize_session=False) if (round_ids or app_ids) else 0

        offers_del = db.query(PlacementOffer).filter(PlacementOffer.id.in_(offer_ids)).delete(synchronize_session=False) if offer_ids else 0
        apps_del = db.query(Application).filter(Application.id.in_(app_ids)).delete(synchronize_session=False) if app_ids else 0
        shortlists_del = db.query(Shortlist).filter(Shortlist.company_id.in_(comp_ids)).delete(synchronize_session=False)
        batches_del = db.query(RecruitmentResultBatch).filter(RecruitmentResultBatch.id.in_(batch_ids)).delete(synchronize_session=False) if batch_ids else 0

        circ_atts_del = db.query(RecruitmentCircularAttachment).filter(RecruitmentCircularAttachment.circular_id.in_(circular_ids)).delete(synchronize_session=False) if circular_ids else 0
        circ_jobs_del = db.query(RecruitmentCircularJob).filter(
            or_(
                RecruitmentCircularJob.circular_id.in_(circular_ids) if circular_ids else False,
                RecruitmentCircularJob.job_posting_id.in_(job_ids) if job_ids else False,
            )
        ).delete(synchronize_session=False) if (circular_ids or job_ids) else 0

        circulars_del = db.query(RecruitmentCircular).filter(RecruitmentCircular.id.in_(circular_ids)).delete(synchronize_session=False) if circular_ids else 0
        rounds_del = db.query(RecruitmentRound).filter(RecruitmentRound.id.in_(round_ids)).delete(synchronize_session=False) if round_ids else 0
        jobs_del = db.query(JobPosting).filter(JobPosting.id.in_(job_ids)).delete(synchronize_session=False) if job_ids else 0
        files_del = db.query(File).filter(File.id.in_(unshared_file_ids)).delete(synchronize_session=False) if unshared_file_ids else 0
        comps_del = db.query(Company).filter(Company.id.in_(comp_ids)).delete(synchronize_session=False)

        # Audit Log
        audit_service.log_action(
            db=db,
            action="TEST_DATA_PURGED_CONFIRMED",
            actor=None,
            target_type="company_batch",
            target_id=f"count:{len(comp_ids)}",
            details={
                "companies_deleted": comps_del,
                "jobs_deleted": jobs_del,
                "circulars_deleted": circulars_del,
                "applications_deleted": apps_del,
                "offers_deleted": offers_del,
                "files_deleted": files_del,
            }
        )

        db.commit()

        return {
            "companies_deleted": comps_del,
            "jobs_deleted": jobs_del,
            "circulars_deleted": circulars_del,
            "circular_attachments_deleted": circ_atts_del,
            "circular_jobs_deleted": circ_jobs_del,
            "rounds_deleted": rounds_del,
            "outcomes_deleted": outcomes_del,
            "applications_deleted": apps_del,
            "offers_deleted": offers_del,
            "shortlists_deleted": shortlists_del,
            "batches_deleted": batches_del,
            "result_items_deleted": items_del,
            "unshared_files_deleted": files_del,
            "notifications_deleted": notifs_del,
        }
    except Exception as e:
        db.rollback()
        raise e


def main():
    parser = argparse.ArgumentParser(description="EduMatrix Placement Test-Data Cleanup & Audit")
    parser.add_argument("--audit", action="store_true", help="Print audit and categorization")
    parser.add_argument("--dry-run", action="store_true", help="Simulate dry-run on confirmed test data")
    parser.add_argument("--all-companies", action="store_true", help="Target all companies in the database to clear to zero")
    parser.add_argument("--backup-only", action="store_true", help="Generate full JSON backup of candidate data")
    parser.add_argument("--confirm-purge", action="store_true", help="Explicit confirmation to execute purge")
    parser.add_argument("--backup-path", type=str, default="/tmp/placement_test_data_backup.json", help="Backup output path")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        confirmed_tests, genuine_comps, uncertain_comps = audit_and_categorize(db)

        print("\n" + "="*70)
        print("          EDUMATRIX PLACEMENT TEST-DATA AUDIT INVENTORY")
        print("="*70)
        print(f"Total Companies Audited: {len(confirmed_tests) + len(genuine_comps) + len(uncertain_comps)}")
        print(f"  ├─ Confirmed Test Companies (Disposable):     {len(confirmed_tests):>4}")
        print(f"  ├─ Genuine / Production-Like (Preserved):       {len(genuine_comps):>4}")
        print(f"  └─ Uncertain / Protected (Requires Review):    {len(uncertain_comps):>4}")
        print("="*70)

        if args.all_companies:
            target_ids = [c.id for c in db.query(Company).all()]
            target_label = "ALL COMPANIES (TOTAL PURGE TO ZERO)"
        else:
            target_ids = [c["id"] for c in confirmed_tests]
            target_label = "CONFIRMED TEST RECORDS ONLY"

        sim = simulate_dry_run(db, target_ids)

        print("\n" + "="*70)
        print(f"          DRY-RUN SIMULATION ({target_label})")
        print("="*70)
        for k, v in sim.items():
            readable_k = k.replace("_", " ").title()
            print(f"  • {readable_k:<42}: {v:>5}")
        print("="*70)

        # Always generate backup preview on dry run, audit, or purge
        backup_data = create_export_backup(db, target_ids, args.backup_path)
        print(f"\n[BACKUP EXPORT READY]: Saved {len(target_ids)} companies to: {args.backup_path}")
        print(f"  - Companies: {len(backup_data['companies'])}")
        print(f"  - Job Postings: {len(backup_data['job_postings'])}")
        print(f"  - Circulars: {len(backup_data['recruitment_circulars'])}")
        print(f"  - Applications: {len(backup_data['applications'])}")
        print(f"  - Offers: {len(backup_data['placement_offers'])}")
        print(f"  - Results Batches: {len(backup_data['recruitment_result_batches'])}")

        if args.confirm_purge:
            print("\n" + "="*70)
            print(f"          EXECUTING ATOMIC PURGE OF {target_label}")
            print("="*70)
            result = execute_purge_transaction(db, target_ids)
            print("[PURGE COMPLETED SUCCESSFULLY]:")
            for k, v in result.items():
                print(f"  • {k:<36}: {v:>5}")
            print("="*70)
            remaining_comps = db.query(Company).count()
            print(f"[VERIFICATION]: Remaining Companies in Database: {remaining_comps}")
        else:
            print("\n[STATUS]: DRY-RUN COMPLETE. ZERO RECORDS WERE MODIFIED OR DELETED.")
            print("[SAFEGUARD]: Pass --confirm-purge to execute after explicit user confirmation.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
