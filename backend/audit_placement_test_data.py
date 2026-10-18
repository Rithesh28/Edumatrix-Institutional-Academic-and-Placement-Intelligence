"""
Audit Script: Inventory of Companies, Job Postings, and Related Placement Data

Inspects:
- All companies in the database
- All job postings
- All linked recruitment circulars, applications, shortlists, rounds, results, offers
- Student profiles associated with applications
- File attachments associated with circulars/results/offers
- Audit logs for companies and jobs
Outputs detailed JSON and human-readable inventory without modifying anything.
"""

import os
import json
import re
from datetime import datetime
from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.company import Company
from app.models.job_posting import JobPosting
from app.models.recruitment_circular import (
    RecruitmentCircular,
    RecruitmentCircularAttachment,
    RecruitmentCircularJob,
)
from app.models.application import Application
from app.models.shortlist import Shortlist
from app.models.recruitment_round import (
    RecruitmentRound,
    StudentRoundOutcome,
    PlacementOffer,
)
from app.models.recruitment_result import (
    RecruitmentResultBatch,
    RecruitmentResultItem,
)
from app.models.file import File
from app.models.user import User
from app.models.audit_log import AuditLog
from app.services.placement_cleanup_service import TEST_PATTERNS, TEST_STUDENT_PATTERNS


def audit_placement_data():
    db = SessionLocal()
    try:
        companies = db.query(Company).order_by(Company.id).all()
        print(f"==================================================")
        print(f"TOTAL COMPANIES IN DATABASE: {len(companies)}")
        print(f"==================================================")

        jobs = db.query(JobPosting).order_by(JobPosting.id).all()
        print(f"TOTAL JOB POSTINGS IN DATABASE: {len(jobs)}")
        print(f"==================================================\n")

        company_inventory = []

        for c in companies:
            c_jobs = db.query(JobPosting).filter(JobPosting.company_id == c.id).all()
            c_circulars = db.query(RecruitmentCircular).filter(RecruitmentCircular.company_id == c.id).all()
            c_shortlists = db.query(Shortlist).filter(Shortlist.company_id == c.id).all()
            c_result_batches = db.query(RecruitmentResultBatch).filter(RecruitmentResultBatch.company_id == c.id).all()

            # Jobs breakdown
            jobs_info = []
            total_apps = 0
            genuine_apps = 0
            test_apps = 0
            total_offers = 0
            genuine_offers = 0
            total_rounds = 0
            total_outcomes = 0

            for j in c_jobs:
                j_apps = db.query(Application).filter(Application.job_posting_id == j.id).all()
                j_rounds = db.query(RecruitmentRound).filter(RecruitmentRound.job_posting_id == j.id).all()
                j_offers = db.query(PlacementOffer).filter(PlacementOffer.job_posting_id == j.id).all()
                j_circ_links = db.query(RecruitmentCircularJob).filter(RecruitmentCircularJob.job_posting_id == j.id).all()

                apps_detail = []
                for a in j_apps:
                    student = db.query(User).filter(User.id == a.student_id).first()
                    email = student.email if student else "unknown"
                    is_test_student = any(p.search(email) for p in TEST_STUDENT_PATTERNS) or "test" in (student.name or "").lower()
                    if is_test_student:
                        test_apps += 1
                    else:
                        genuine_apps += 1
                    apps_detail.append({
                        "app_id": a.id,
                        "student_id": a.student_id,
                        "student_email": email,
                        "student_name": student.name if student else None,
                        "is_test_student": is_test_student,
                        "status": a.status.value if a.status else None,
                        "applied_at": a.applied_at.isoformat() if a.applied_at else None,
                    })

                offers_detail = []
                for o in j_offers:
                    student = db.query(User).filter(User.id == o.student_id).first()
                    email = student.email if student else "unknown"
                    is_test_student = any(p.search(email) for p in TEST_STUDENT_PATTERNS) or "test" in (student.name or "").lower()
                    if not is_test_student:
                        genuine_offers += 1
                    offers_detail.append({
                        "offer_id": o.id,
                        "student_id": o.student_id,
                        "student_email": email,
                        "ctc_lpa": o.ctc_lpa,
                        "status": o.acceptance_status.value if o.acceptance_status else None,
                        "has_letter_file": bool(o.offer_letter_file_id),
                    })

                total_apps += len(j_apps)
                total_offers += len(j_offers)
                total_rounds += len(j_rounds)

                jobs_info.append({
                    "job_id": j.id,
                    "title": j.title,
                    "status": j.status.value if j.status else None,
                    "created_at": j.created_at.isoformat() if j.created_at else None,
                    "applications_count": len(j_apps),
                    "applications": apps_detail,
                    "rounds_count": len(j_rounds),
                    "offers_count": len(j_offers),
                    "offers": offers_detail,
                    "circular_links_count": len(j_circ_links),
                })

            # Circulars detail
            circulars_info = []
            for circ in c_circulars:
                attachments = db.query(RecruitmentCircularAttachment).filter(RecruitmentCircularAttachment.circular_id == circ.id).all()
                circ_jobs = db.query(RecruitmentCircularJob).filter(RecruitmentCircularJob.circular_id == circ.id).all()
                circulars_info.append({
                    "circular_id": circ.id,
                    "title": circ.title,
                    "status": circ.status.value if circ.status else None,
                    "created_at": circ.created_at.isoformat() if circ.created_at else None,
                    "attachments_count": len(attachments),
                    "linked_jobs_count": len(circ_jobs),
                })

            # Check test signals
            is_test_name = any(p.search(c.name) for p in TEST_PATTERNS)
            has_test_contact = bool(c.contact_email and ("test" in c.contact_email or "example.com" in c.contact_email))
            
            # Classification
            classification = "UNCERTAIN"
            classification_reason = []

            # Genuine criteria: Real company names without timestamps/test markers, having genuine students or genuine profiles
            is_obviously_test = False
            if is_test_name:
                is_obviously_test = True
                classification_reason.append("Name matches automated test regex (contains test/temp/dummy or timestamp)")
            
            if re.search(r"\b\d{10,13}\b", c.name):
                is_obviously_test = True
                classification_reason.append("Name contains Unix millisecond timestamp")

            if genuine_apps > 0:
                classification = "GENUINE_OR_HAS_GENUINE_DEPENDENTS"
                classification_reason.append(f"Has {genuine_apps} genuine student application(s)")
            elif genuine_offers > 0:
                classification = "GENUINE_OR_HAS_GENUINE_DEPENDENTS"
                classification_reason.append(f"Has {genuine_offers} genuine placement offer(s)")
            elif is_obviously_test and genuine_apps == 0 and genuine_offers == 0:
                classification = "CONFIRMED_TEST"
                classification_reason.append("Test markers present and zero genuine student applications or offers")
            elif not is_obviously_test and total_apps == 0:
                classification = "GENUINE_OR_PRODUCTION_LIKE"
                classification_reason.append("Standard company name without test markers")
            else:
                classification = "UNCERTAIN"
                classification_reason.append("Requires manual review")

            comp_record = {
                "id": c.id,
                "name": c.name,
                "is_active": c.is_active,
                "industry": c.industry,
                "location": c.location,
                "contact_email": c.contact_email,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "jobs_count": len(c_jobs),
                "jobs": jobs_info,
                "circulars_count": len(c_circulars),
                "circulars": circulars_info,
                "shortlists_count": len(c_shortlists),
                "result_batches_count": len(c_result_batches),
                "total_applications": total_apps,
                "genuine_applications": genuine_apps,
                "test_applications": test_apps,
                "total_offers": total_offers,
                "genuine_offers": genuine_offers,
                "classification": classification,
                "classification_reasons": classification_reason,
            }
            company_inventory.append(comp_record)

        # Standalone or orphaned jobs (if any)
        all_job_ids_in_comps = {j["job_id"] for c in company_inventory for j in c["jobs"]}
        orphaned_jobs = [j for j in jobs if j.id not in all_job_ids_in_comps]

        inventory_summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_companies": len(companies),
            "total_jobs": len(jobs),
            "orphaned_jobs_count": len(orphaned_jobs),
            "companies": company_inventory,
        }

        output_path = "/tmp/placement_cleanup_audit_inventory.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(inventory_summary, f, indent=2)

        print(f"Inventory saved to {output_path}")

        # Print summary breakdown
        confirmed_tests = [c for c in company_inventory if c["classification"] == "CONFIRMED_TEST"]
        genuine_comps = [c for c in company_inventory if c["classification"] == "GENUINE_OR_PRODUCTION_LIKE"]
        protected_comps = [c for c in company_inventory if c["classification"] == "GENUINE_OR_HAS_GENUINE_DEPENDENTS"]
        uncertain_comps = [c for c in company_inventory if c["classification"] == "UNCERTAIN"]

        print("\n================ CLASSIFICATION BREAKDOWN ================")
        print(f"1. Confirmed Test Companies: {len(confirmed_tests)}")
        for c in confirmed_tests:
            print(f"   - [ID {c['id']}] {c['name']} (Jobs: {c['jobs_count']}, Apps: {c['total_applications']}, Circulars: {c['circulars_count']})")
            for j in c["jobs"]:
                print(f"       * Job [ID {j['job_id']}] {j['title']} (Apps: {j['applications_count']}, Rounds: {j['rounds_count']}, Offers: {j['offers_count']})")

        print(f"\n2. Genuine / Production-Like Companies (To Preserve): {len(genuine_comps)}")
        for c in genuine_comps:
            print(f"   - [ID {c['id']}] {c['name']} (Jobs: {c['jobs_count']}, Apps: {c['total_applications']}, Created: {c['created_at']})")
            for j in c["jobs"]:
                print(f"       * Job [ID {j['job_id']}] {j['title']} (Status: {j['status']}, Apps: {j['applications_count']})")

        print(f"\n3. Protected Companies (Has Genuine Student Apps/Offers): {len(protected_comps)}")
        for c in protected_comps:
            print(f"   - [ID {c['id']}] {c['name']} (Genuine Apps: {c['genuine_applications']}, Genuine Offers: {c['genuine_offers']})")

        print(f"\n4. Uncertain Companies (Requires User Confirmation): {len(uncertain_comps)}")
        for c in uncertain_comps:
            print(f"   - [ID {c['id']}] {c['name']} (Reasons: {c['classification_reasons']})")

    finally:
        db.close()


if __name__ == "__main__":
    audit_placement_data()
