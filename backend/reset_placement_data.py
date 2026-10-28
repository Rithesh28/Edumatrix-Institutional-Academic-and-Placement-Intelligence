import sys
sys.path.insert(0, '.')
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import *
from app.models.profile import PlacementStatus
from app.models.application import ApplicationStatus
from app.models.recruitment_round import OfferAcceptanceStatus
from app.models.job_posting import JobStatus
from app.models.recruitment_circular import RecruitmentCircularStatus

DATABASE_URL = 'postgresql://edumatrix:edumatrix123@localhost:5432/edumatrix'
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

print("=" * 70)
print("PLACEMENT DATA RESET - BEFORE STATE")
print("=" * 70)

# Before counts
from app.models.company import Company
from app.models.job_posting import JobPosting
from app.models.application import Application
from app.models.recruitment_round import PlacementOffer
from app.models.profile import StudentProfileExtended

companies_before = db.query(Company).count()
jobs_before = db.query(JobPosting).count()
apps_before = db.query(Application).count()
offers_before = db.query(PlacementOffer).count()
placed_students_before = db.query(StudentProfileExtended).filter(
    StudentProfileExtended.placement_status == PlacementStatus.PLACED
).count()
accepted_offers_before = db.query(PlacementOffer).filter(
    PlacementOffer.acceptance_status == OfferAcceptanceStatus.ACCEPTED
).count()
selected_apps_before = db.query(Application).filter(
    Application.status == ApplicationStatus.SELECTED
).count()

print(f"Companies: {companies_before}")
print(f"Jobs: {jobs_before}")
print(f"Applications: {apps_before}")
print(f"Placement Offers: {offers_before}")
print(f"Students with PLACED profile status: {placed_students_before}")
print(f"Accepted Offers: {accepted_offers_before}")
print(f"SELECTED Applications: {selected_apps_before}")

# Identify test companies (timestamp patterns)
import re
test_pattern = re.compile(r'\b\d{10,13}\b')
test_companies = [c for c in db.query(Company).all() if test_pattern.search(c.name)]
print(f"\nTest companies identified: {[c.name for c in test_companies]}")
test_company_ids = [c.id for c in test_companies]

# Get test jobs (jobs belonging to test companies)
test_jobs = db.query(JobPosting).filter(JobPosting.company_id.in_(test_company_ids)).all() if test_company_ids else []
test_job_ids = [j.id for j in test_jobs]
print(f"Test job IDs: {test_job_ids}")

# Get test applications (applications to test jobs)
test_apps = db.query(Application).filter(Application.job_posting_id.in_(test_job_ids)).all() if test_job_ids else []
print(f"Test applications count: {len(test_apps)}")

# Get test offers (offers for test jobs)
test_offers = db.query(PlacementOffer).filter(PlacementOffer.job_posting_id.in_(test_job_ids)).all() if test_job_ids else []
print(f"Test offers count: {len(test_offers)}")

# Get test students (students who applied to test jobs or got test offers)
test_student_ids = set()
for app in test_apps:
    test_student_ids.add(app.student_id)
for offer in test_offers:
    test_student_ids.add(offer.student_id)
print(f"Test student IDs: {test_student_ids}")

# Now perform the reset
print("\n" + "=" * 70)
print("EXECUTING RESET")
print("=" * 70)

# 1. Reset student placement status for test students
if test_student_ids:
    profiles = db.query(StudentProfileExtended).filter(
        StudentProfileExtended.user_id.in_(list(test_student_ids))
    ).all()
    for p in profiles:
        print(f"Resetting placement status for {p.user.name} ({p.user.email}) from {p.placement_status} to NOT_APPLIED")
        p.placement_status = PlacementStatus.NOT_APPLIED
    db.flush()

# 2. Delete test offers (which will remove the ACCEPTED offer causing "Students Placed: 1")
if test_offers:
    offer_ids = [o.id for o in test_offers]
    print(f"Deleting test offers: {offer_ids}")
    db.query(PlacementOffer).filter(PlacementOffer.id.in_(offer_ids)).delete(synchronize_session=False)

# 3. Reset test applications status from SELECTED to APPLIED (or delete)
if test_apps:
    for app in test_apps:
        print(f"Resetting application {app.id} for student {app.student.name} from {app.status} to APPLIED")
        app.status = ApplicationStatus.APPLIED
    db.flush()

# 4. Delete test jobs
if test_jobs:
    for job in test_jobs:
        print(f"Deleting test job: {job.title} (ID: {job.id})")
        # First delete related records
        db.query(Application).filter(Application.job_posting_id == job.id).delete(synchronize_session=False)
        db.query(PlacementOffer).filter(PlacementOffer.job_posting_id == job.id).delete(synchronize_session=False)
        from app.models.shortlist import Shortlist
        db.query(Shortlist).filter(Shortlist.job_posting_id == job.id).delete(synchronize_session=False)
        from app.models.recruitment_round import RecruitmentRound, StudentRoundOutcome
        rounds = db.query(RecruitmentRound).filter(RecruitmentRound.job_posting_id == job.id).all()
        round_ids = [r.id for r in rounds]
        if round_ids:
            db.query(StudentRoundOutcome).filter(StudentRoundOutcome.round_id.in_(round_ids)).delete(synchronize_session=False)
            db.query(RecruitmentRound).filter(RecruitmentRound.id.in_(round_ids)).delete(synchronize_session=False)
        from app.models.recruitment_result import RecruitmentResultBatch, RecruitmentResultItem
        batches = db.query(RecruitmentResultBatch).filter(RecruitmentResultBatch.job_posting_id == job.id).all()
        batch_ids = [b.id for b in batches]
        if batch_ids:
            db.query(RecruitmentResultItem).filter(RecruitmentResultItem.batch_id.in_(batch_ids)).delete(synchronize_session=False)
            db.query(RecruitmentResultBatch).filter(RecruitmentResultBatch.id.in_(batch_ids)).delete(synchronize_session=False)
        from app.models.recruitment_circular import RecruitmentCircularJob
        db.query(RecruitmentCircularJob).filter(RecruitmentCircularJob.job_posting_id == job.id).delete(synchronize_session=False)
        from app.models.job_posting import JobPostingAttachment
        db.query(JobPostingAttachment).filter(JobPostingAttachment.job_posting_id == job.id).delete(synchronize_session=False)
        db.delete(job)
    db.flush()

# 5. Delete test recruitment circulars for test companies
if test_company_ids:
    from app.models.recruitment_circular import RecruitmentCircular, RecruitmentCircularAttachment
    test_circulars = db.query(RecruitmentCircular).filter(RecruitmentCircular.company_id.in_(test_company_ids)).all()
    for circ in test_circulars:
        print(f"Deleting test circular: {circ.title} (ID: {circ.id})")
        db.query(RecruitmentCircularAttachment).filter(RecruitmentCircularAttachment.circular_id == circ.id).delete(synchronize_session=False)
        db.delete(circ)
    db.flush()

# 6. Delete test companies
if test_companies:
    for comp in test_companies:
        print(f"Deleting test company: {comp.name} (ID: {comp.id})")
        db.delete(comp)
    db.flush()

# Commit all changes
db.commit()
print("\nAll changes committed successfully!")

print("\n" + "=" * 70)
print("AFTER STATE")
print("=" * 70)

# After counts
companies_after = db.query(Company).count()
jobs_after = db.query(JobPosting).count()
apps_after = db.query(Application).count()
offers_after = db.query(PlacementOffer).count()
placed_students_after = db.query(StudentProfileExtended).filter(
    StudentProfileExtended.placement_status == PlacementStatus.PLACED
).count()
accepted_offers_after = db.query(PlacementOffer).filter(
    PlacementOffer.acceptance_status == OfferAcceptanceStatus.ACCEPTED
).count()
selected_apps_after = db.query(Application).filter(
    Application.status == ApplicationStatus.SELECTED
).count()

print(f"Companies: {companies_after} (was {companies_before})")
print(f"Jobs: {jobs_after} (was {jobs_before})")
print(f"Applications: {apps_after} (was {apps_before})")
print(f"Placement Offers: {offers_after} (was {offers_before})")
print(f"Students with PLACED profile status: {placed_students_after} (was {placed_students_before})")
print(f"Accepted Offers: {accepted_offers_after} (was {accepted_offers_before})")
print(f"SELECTED Applications: {selected_apps_after} (was {selected_apps_before})")

# Verify with placement_offer_service
from app.services.placement_offer_service import placement_offer_service
metrics = placement_offer_service.get_placement_accounting_metrics(db)
print(f"\nVerified Metrics:")
print(f"  verified_placed_students_count: {metrics['verified_placed_students_count']}")
print(f"  accepted_offers_count: {metrics['accepted_offers_count']}")
print(f"  verified_placement_rate: {metrics['verified_placement_rate']}")
print(f"  total_verified_offers: {metrics['total_verified_offers']}")

# List remaining companies
remaining_companies = db.query(Company).all()
print(f"\nRemaining companies ({len(remaining_companies)}):")
for c in remaining_companies:
    print(f"  - {c.name}")

# List remaining jobs
remaining_jobs = db.query(JobPosting).all()
print(f"\nRemaining jobs ({len(remaining_jobs)}):")
for j in remaining_jobs:
    print(f"  - {j.title} at {j.company.name} [{j.status}]")

db.close()