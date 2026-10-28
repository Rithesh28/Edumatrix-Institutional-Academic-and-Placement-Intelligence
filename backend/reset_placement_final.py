import sys
sys.path.insert(0, '.')
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.company import Company
from app.models.job_posting import JobPosting, JobStatus, JobPostingAttachment
from app.models.application import Application, ApplicationStatus
from app.models.recruitment_round import PlacementOffer, OfferAcceptanceStatus, RecruitmentRound, StudentRoundOutcome
from app.models.profile import StudentProfileExtended, PlacementStatus
from app.models.shortlist import Shortlist
from app.models.recruitment_result import RecruitmentResultBatch, RecruitmentResultItem
from app.models.recruitment_circular import RecruitmentCircular, RecruitmentCircularJob, RecruitmentCircularAttachment
import re

DATABASE_URL = 'postgresql://edumatrix:edumatrix123@localhost:5432/edumatrix'
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

print('=== BEFORE RESET ===')

# Identify test companies (timestamp patterns in name)
test_pattern = re.compile(r'\b\d{10,13}\b')
test_companies = [c for c in db.query(Company).all() if test_pattern.search(c.name)]
print(f'Test companies: {[(c.id, c.name) for c in test_companies]}')
test_company_ids = [c.id for c in test_companies]

# Get test jobs
test_jobs = db.query(JobPosting).filter(JobPosting.company_id.in_(test_company_ids)).all() if test_company_ids else []
print(f'Test job IDs: {[j.id for j in test_jobs]}')
test_job_ids = [j.id for j in test_jobs]

# Get test applications
test_apps = db.query(Application).filter(Application.job_posting_id.in_(test_job_ids)).all() if test_job_ids else []
print(f'Test applications: {len(test_apps)}')

# Get test offers
test_offers = db.query(PlacementOffer).filter(PlacementOffer.job_posting_id.in_(test_job_ids)).all() if test_job_ids else []
print(f'Test offers: {len(test_offers)}')

# Get test students
test_student_ids = set()
for app in test_apps:
    test_student_ids.add(app.student_id)
for offer in test_offers:
    test_student_ids.add(offer.student_id)
print(f'Test student IDs: {test_student_ids}')

# Show placed students
placed_profiles = db.query(StudentProfileExtended).filter(StudentProfileExtended.placement_status == PlacementStatus.PLACED).all()
print(f'PLACED profiles: {len(placed_profiles)}')
for p in placed_profiles:
    print(f'  - {p.user.name} ({p.user.email})')

# Show SELECTED applications
selected_apps = db.query(Application).filter(Application.status == ApplicationStatus.SELECTED).all()
print(f'SELECTED applications: {len(selected_apps)}')
for a in selected_apps:
    print(f'  - App {a.id}: {a.student.name} -> {a.job_posting.title} ({a.job_posting.company.name if a.job_posting.company else "No company"})')

# Show ACCEPTED offers
accepted_offers = db.query(PlacementOffer).filter(PlacementOffer.acceptance_status == OfferAcceptanceStatus.ACCEPTED).all()
print(f'ACCEPTED offers: {len(accepted_offers)}')
for o in accepted_offers:
    print(f'  - Offer {o.id}: {o.student.name} -> {o.job_posting.title} ({o.job_posting.company.name if o.job_posting.company else "No company"})')

print("\n=== EXECUTING RESET ===")

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

# 4. Also check and reset ANY application with SELECTED status regardless of test job
# (in case there are SELECTED apps not linked to test companies)
all_selected = db.query(Application).filter(Application.status == ApplicationStatus.SELECTED).all()
for app in all_selected:
    print(f"Resetting SELECTED application {app.id} for student {app.student.name} to APPLIED")
    app.status = ApplicationStatus.APPLIED
db.flush()

# 5. Also delete ANY PlacementOffer with ACCEPTED status
all_accepted = db.query(PlacementOffer).filter(PlacementOffer.acceptance_status == OfferAcceptanceStatus.ACCEPTED).all()
if all_accepted:
    accepted_ids = [o.id for o in all_accepted]
    print(f"Deleting ALL ACCEPTED offers: {accepted_ids}")
    db.query(PlacementOffer).filter(PlacementOffer.id.in_(accepted_ids)).delete(synchronize_session=False)

# 6. Delete test jobs and their related records
if test_jobs:
    for job in test_jobs:
        print(f"Deleting test job: {job.title} (ID: {job.id})")
        db.query(Application).filter(Application.job_posting_id == job.id).delete(synchronize_session=False)
        db.query(PlacementOffer).filter(PlacementOffer.job_posting_id == job.id).delete(synchronize_session=False)
        db.query(Shortlist).filter(Shortlist.job_posting_id == job.id).delete(synchronize_session=False)
        rounds = db.query(RecruitmentRound).filter(RecruitmentRound.job_posting_id == job.id).all()
        round_ids = [r.id for r in rounds]
        if round_ids:
            db.query(StudentRoundOutcome).filter(StudentRoundOutcome.round_id.in_(round_ids)).delete(synchronize_session=False)
            db.query(RecruitmentRound).filter(RecruitmentRound.id.in_(round_ids)).delete(synchronize_session=False)
        batches = db.query(RecruitmentResultBatch).filter(RecruitmentResultBatch.job_posting_id == job.id).all()
        batch_ids = [b.id for b in batches]
        if batch_ids:
            db.query(RecruitmentResultItem).filter(RecruitmentResultItem.batch_id.in_(batch_ids)).delete(synchronize_session=False)
            db.query(RecruitmentResultBatch).filter(RecruitmentResultBatch.id.in_(batch_ids)).delete(synchronize_session=False)
        db.query(RecruitmentCircularJob).filter(RecruitmentCircularJob.job_posting_id == job.id).delete(synchronize_session=False)
        db.query(JobPostingAttachment).filter(JobPostingAttachment.job_posting_id == job.id).delete(synchronize_session=False)
        db.delete(job)
    db.flush()

# 7. Delete test recruitment circulars for test companies
if test_company_ids:
    test_circulars = db.query(RecruitmentCircular).filter(RecruitmentCircular.company_id.in_(test_company_ids)).all()
    for circ in test_circulars:
        print(f"Deleting test circular: {circ.title} (ID: {circ.id})")
        db.query(RecruitmentCircularAttachment).filter(RecruitmentCircularAttachment.circular_id == circ.id).delete(synchronize_session=False)
        db.delete(circ)
    db.flush()

# 8. Delete test companies
if test_companies:
    for comp in test_companies:
        print(f"Deleting test company: {comp.name} (ID: {comp.id})")
        db.delete(comp)
    db.flush()

# Commit all changes
db.commit()
print("\nAll changes committed successfully!")

print("\n=== AFTER RESET ===")

# After counts
from app.services.placement_offer_service import placement_offer_service

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

print(f"Companies: {companies_after}")
print(f"Jobs: {jobs_after}")
print(f"Applications: {apps_after}")
print(f"Placement Offers: {offers_after}")
print(f"Students with PLACED profile status: {placed_students_after}")
print(f"Accepted Offers: {accepted_offers_after}")
print(f"SELECTED Applications: {selected_apps_after}")

# Verify with placement_offer_service
metrics = placement_offer_service.get_placement_accounting_metrics(db)
print(f"\nVerified Metrics:")
print(f"  verified_placed_students_count: {metrics['verified_placed_students_count']}")
print(f"  accepted_offers_count: {metrics['accepted_offers_count']}")
print(f"  verified_placement_rate: {metrics['verified_placement_rate']}")
print(f"  total_verified_offers: {metrics['total_verified_offers']}")
print(f"  legacy_placed_count: {metrics['legacy_placed_count']}")

# List remaining companies
remaining_companies = db.query(Company).all()
print(f"\nRemaining companies ({len(remaining_companies)}):")
for c in remaining_companies:
    print(f"  - {c.name} [{'ACTIVE' if c.is_active else 'DEACTIVATED'}]")

# List remaining jobs
remaining_jobs = db.query(JobPosting).all()
print(f"\nRemaining jobs ({len(remaining_jobs)}):")
for j in remaining_jobs:
    print(f"  - {j.title} at {j.company.name} [{j.status}]")

db.close()