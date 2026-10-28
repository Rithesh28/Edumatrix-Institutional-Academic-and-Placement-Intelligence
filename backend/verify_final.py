import sys
sys.path.insert(0, '.')
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.company import Company
from app.models.job_posting import JobPosting, JobStatus
from app.models.application import Application, ApplicationStatus
from app.models.recruitment_round import PlacementOffer, OfferAcceptanceStatus
from app.models.profile import StudentProfileExtended, PlacementStatus
import re

DATABASE_URL = 'postgresql://edumatrix:edumatrix123@postgres:5432/edumatrix'
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

print('=== FINAL STATE VERIFICATION ===')

# Companies
companies = db.query(Company).all()
test_pattern = re.compile(r'\b\d{10,13}\b')
remaining_test = [c for c in companies if test_pattern.search(c.name)]
remaining_real = [c for c in companies if not test_pattern.search(c.name)]
print(f'Companies: {len(companies)} total, {len(remaining_test)} test remaining (deactivated), {len(remaining_real)} real')
for c in companies:
    is_test = 'TEST' if test_pattern.search(c.name) else 'REAL'
    print(f'  ID {c.id}: {c.name} [{c.is_active}] ({is_test})')

# Jobs
jobs = db.query(JobPosting).all()
print(f'\nJobs: {len(jobs)}')
for j in jobs:
    print(f'  ID {j.id}: {j.title} at {j.company.name} [{j.status}]')

# Student profiles with PLACED status
placed_profiles = db.query(StudentProfileExtended).filter(StudentProfileExtended.placement_status == PlacementStatus.PLACED).all()
print(f'\nPLACED profiles: {len(placed_profiles)}')

# Applications status
selected_apps = db.query(Application).filter(Application.status == ApplicationStatus.SELECTED).all()
print(f'SELECTED applications: {len(selected_apps)}')

# Placement offers with ACCEPTED status
accepted_offers = db.query(PlacementOffer).filter(PlacementOffer.acceptance_status == OfferAcceptanceStatus.ACCEPTED).all()
print(f'ACCEPTED offers: {len(accepted_offers)}')

# Verified metrics
from app.services.placement_offer_service import placement_offer_service
metrics = placement_offer_service.get_placement_accounting_metrics(db)
print(f'\nVerified Metrics:')
print(f'  verified_placed_students_count: {metrics["verified_placed_students_count"]}')
print(f'  legacy_placed_count: {metrics["legacy_placed_count"]}')
print(f'  accepted_offers_count: {metrics["accepted_offers_count"]}')
print(f'  total_verified_offers: {metrics["total_verified_offers"]}')

# Dashboard stats would show
real_company_ids = [c.id for c in remaining_real]
real_jobs = [j for j in jobs if j.company_id in real_company_ids]
real_apps = [a for a in db.query(Application).all() if a.job_posting.company_id in real_company_ids]

print(f'\nDashboard "Students Placed" should now show: 0')
print(f'Dashboard "Total Companies" should now show: {len(remaining_real)} (real companies)')
print(f'Dashboard "Total Jobs" should now show: {len(real_jobs)} (real company jobs)')
print(f'Dashboard "Total Applications" should now show: {len(real_apps)}')

db.close()