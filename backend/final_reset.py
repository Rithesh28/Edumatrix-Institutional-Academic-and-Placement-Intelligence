import sys
sys.path.insert(0, '.')
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.models import *
import re

DATABASE_URL = 'postgresql://edumatrix:edumatrix123@localhost:5432/edumatrix'
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

db = SessionLocal()

print("=== RESET: Removing test companies and related data ===")

# Step 1: Identify test companies (those with timestamp patterns in name)
test_pattern = re.compile(r'\b\d{10,13}\b')
test_companies = [c for c in db.query(Company).all() if test_pattern.search(c.name)]
print(f"Test companies found: {[c.name for c in test_companies]}")

test_company_ids = [c.id for c in test_companies]

# Step 2: Delete related job postings and their dependent records
from app.models.job_posting import JobPosting
from app.models.application import Application
from app.models.shortlist import Shortlist
from app.models.recruitment_round import RecruitmentRound, StudentRoundOutcome
from app.models.recruitment_result import RecruitmentResultBatch, RecruitmentResultItem
from app.models.job_posting import JobPostingAttachment
from app.models.recruitment_circular import RecruitmentCircularJob
from app.models.recruitment_circular import RecruitmentCircular

# Get jobs belonging to test companies
test_jobs = db.query(JobPosting).filter(JobPosting.company_id.in_(test_company_ids)).all()
print(f"\nTest jobs to delete: {len(test_jobs)}")
for j in test_jobs:
    print(f"  - Job {j.id}: {j.title} (company: {j.company.name})")

# For each test job, delete dependent records in correct order
for job in test_jobs:
    print(f"\nDeleting dependent records for job {job.id}: {job.title}")

    # 1. Delete applications
    app_count = db.query(Application).filter(Application.job_posting_id == job.id).count()
    print(f"  - Deleting {app_count} applications")
    db.query(Application).filter(Application.job_posting_id == job.id).delete(synchronize_session=False)

    # 2. Delete shortlists
    sl_count = db.query(Shortlist).filter(Shortlist.job_posting_id == job.id).count()
    print(f"  - Deleting {sl_count} shortlists")
    db.query(Shortlist).filter(Shortlist.job_posting_id == job.id).delete(synchronize_session=False)

    # 3. Delete student round outcomes via rounds
    rounds = db.query(RecruitmentRound).filter(RecruitmentRound.job_posting_id == job.id).all()
    round_ids = [r.id for r in rounds]
    print(f"  - Deleting {len(rounds)} recruitment rounds and {len(round_ids)} student round outcomes")
    if round_ids:
        db.query(StudentRoundOutcome).filter(StudentRoundOutcome.round_id.in_(round_ids)).delete(synchronize_session=False)
        db.query(RecruitmentRound).filter(RecruitmentRound.id.in_(round_ids)).delete(synchronize_session=False)

    # 4. Delete result items and batches
    batches = db.query(RecruitmentResultBatch).filter(RecruitmentResultBatch.job_posting_id == job.id).all()
    batch_ids = [b.id for b in batches]
    print(f"  - Deleting {len(batches)} result batches and items")
    if batch_ids:
        db.query(RecruitmentResultItem).filter(RecruitmentResultItem.batch_id.in_(batch_ids)).delete(synchronize_session=False)
        db.query(RecruitmentResultBatch).filter(RecruitmentResultBatch.id.in_(batch_ids)).delete(synchronize_session=False)

    # 5. Delete placement offers
    offer_count = db.query(PlacementOffer).filter(PlacementOffer.job_posting_id == job.id).count()
    print(f"  - Deleting {offer_count} placement offers")
    db.query(PlacementOffer).filter(PlacementOffer.job_posting_id == job.id).delete(synchronize_session=False)

    # 6. Delete job attachments
    ja_count = db.query(JobPostingAttachment).filter(JobPostingAttachment.job_posting_id == job.id).count()
    print(f"  - Deleting {ja_count} job attachments")
    db.query(JobPostingAttachment).filter(JobPostingAttachment.job_posting_id == job.id).delete(synchronize_session=False)

    # 7. Delete from recruitment_circular_job junction table
    rcj_count = db.query(RecruitmentCircularJob).filter(RecruitmentCircularJob.job_posting_id == job.id).count()
    print(f"  - Deleting {rcj_count} circular-job links")
    db.query(RecruitmentCircularJob).filter(RecruitmentCircularJob.job_posting_id == job.id).delete(synchronize_session=False)

    # 8. Delete the job
    print(f"  - Deleting job {job.id}")
    db.delete(job)

db.flush()
print("\nAll test jobs and dependent records deleted.")

# Step 3: Delete test recruitment circulars for test companies
from app.models.recruitment_circular import RecruitmentCircular
test_circulars = db.query(RecruitmentCircular).filter(RecruitmentCircular.company_id.in_(test_company_ids)).all()
print(f"\nTest circulars to delete: {len(test_circulars)}")
for circ in test_circulars:
    print(f"  - Circular {circ.id}: {circ.title}")
    # Delete attachments
    att_count = db.query(RecruitmentCircularAttachment).filter(RecruitmentCircularAttachment.circular_id == circ.id).count()
    if att_count > 0:
        print(f"    - Deleting {att_count} attachments")
        db.query(RecruitmentCircularAttachment).filter(RecruitmentCircularAttachment.circular_id == circ.id).delete(synchronize_session=False)
    db.delete(circ)

db.flush()
print("All test circulars deleted.")

# Step 4: Delete test companies
print(f"\nDeleting test companies: {test_company_ids}")
for comp_id in test_company_ids:
    # Delete any remaining shortlists for this company
    sc_count = db.query(Shortlist).filter(Shortlist.company_id == comp_id).count()
    if sc_count > 0:
        print(f"  - Deleting {sc_count} shortlists for company {comp_id}")
        db.query(Shortlist).filter(Shortlist.company_id == comp_id).delete(synchronize_session=False)

    # Delete remaining circular-job links
    rcj_count = db.query(RecruitmentCircularJob).filter(
        RecruitmentCircularJob.circular_id.in_(
            db.query(RecruitmentCircular.id).filter(RecruitmentCircular.company_id == comp_id)
        )
    ).count()
    if rcj_count > 0:
        print(f"  - Deleting {rcj_count} circular-job links")
        db.query(RecruitmentCircularJob).filter(
            RecruitmentCircularJob.circular_id.in_(
                db.query(RecruitmentCircular.id).filter(RecruitmentCircular.company_id == comp_id)
            )
        ).delete(synchronize_session=False)

    print(f"  - Deleting company {comp_id}")
    db.delete(db.query(Company).filter(Company.id == comp_id).first())

db.flush()
print("All test companies deleted.")

# Step 5: Reset Alice Candidate's placement status and application
from app.models.profile import StudentProfileExtended
from app.models.application import ApplicationStatus

# Find Alice Candidate's profile
alice_profiles = db.query(StudentProfileExtended).filter(
    StudentProfileExtended.user_id == 1792554360761  # Alice's user_id based on earlier output
).all()
print(f"\nAlice profiles found: {len(alice_profiles)}")
for p in alice_profiles:
    print(f"  - {p.user.name}: placement_status = {p.placement_status}")
    p.placement_status = PlacementStatus.NOT_APPLIED
    print(f"    -> Reset to NOT_APPLIED")

# Reset the SELECTED application to APPLIED
selected_app = db.query(Application).filter(
    Application.status == ApplicationStatus.SELECTED,
    Application.student_id == 1792554360761
).first()
if selected_app:
    print(f"\nResetting application {selected_app.id} from SELECTED to APPLIED")
    selected_app.status = ApplicationStatus.APPLIED

db.flush()

# Commit all changes
db.commit()
print("\n=== All changes committed successfully! ===")

# Final verification
print("\n=== FINAL VERIFICATION ===")
from app.services.placement_offer_service import placement_offer_service
metrics = placement_offer_service.get_placement_accounting_metrics(db)
print(f"Verified Metrics:")
print(f"  verified_placed_students_count: {metrics['verified_placed_students_count']}")
print(f"  accepted_offers_count: {metrics['accepted_offers_count']}")
print(f"  verified_placement_rate: {metrics['verified_placement_rate']}")
print(f"  total_verified_offers: {metrics['total_verified_offers']}")

# Companies remaining
remaining_companies = db.query(Company).all()
print(f"\nRemaining companies ({len(remaining_companies)}):")
for c in remaining_companies:
    active = "ACTIVE" if c.is_active else "DEACTIVATED"
    print(f"  - {c.name} [{active}]")

# Student profiles
profiles = db.query(StudentProfileExtended).all()
placed = [p for p in profiles if p.placement_status == PlacementStatus.PLACED]
print(f"\nStudent Profiles: Total={len(profiles)}, PLACED={len(placed)}")

db.close()
print("\n=== Reset Complete ===")