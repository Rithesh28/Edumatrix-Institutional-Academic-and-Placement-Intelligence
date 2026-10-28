import sys
sys.path.insert(0, '.')
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from app.models import *
from app.core.config import settings

# Use localhost since we're running outside Docker
DATABASE_URL = "postgresql://edumatrix:edumatrix123@localhost:5432/edumatrix"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

db = SessionLocal()

# Inspect companies count
from app.models.company import Company
company_count = db.query(Company).count()
print(f'Companies count: {company_count}')

# Inspect all companies
companies = db.query(Company).all()
print(f'Companies: {[c.name for c in companies]}')

# Inspect student profiles with placement status
from app.models.profile import StudentProfileExtended, PlacementStatus
profiles = db.query(StudentProfileExtended).all()
print(f'\nTotal student profiles: {len(profiles)}')
placed = [p for p in profiles if p.placement_status == PlacementStatus.PLACED]
print(f'Students with PLACED status: {len(placed)}')
for p in placed:
    print(f'  - {p.user.full_name}: {p.placement_status}')

# Count students NOT APPLIED
not_applied = [p for p in profiles if p.placement_status == PlacementStatus.NOT_APPLIED]
print(f'Students with NOT_APPLIED status: {len(not_applied)}')

# Inspect applications
from app.models.application import Application, ApplicationStatus
total_apps = db.query(Application).count()
print(f'\nTotal applications: {total_apps}')

selected_apps = db.query(Application).filter(Application.status == ApplicationStatus.SELECTED).count()
print(f'Applications with SELECTED status: {selected_apps}')

shortlisted_apps = db.query(Application).filter(Application.status == ApplicationStatus.SHORTLISTED).count()
print(f'Applications with SHORTLISTED status: {shortlisted_apps}')

# Inspect placement offers
from app.models.recruitment_round import PlacementOffer, OfferAcceptanceStatus
total_offers = db.query(PlacementOffer).count()
print(f'\nTotal placement offers: {total_offers}')

accepted_offers = db.query(PlacementOffer).filter(PlacementOffer.acceptance_status == OfferAcceptanceStatus.ACCEPTED).count()
print(f'Accepted placement offers: {accepted_offers}')

# Check if there's a verified column
verified = db.query(PlacementOffer).filter(
    PlacementOffer.acceptance_status == OfferAcceptanceStatus.ACCEPTED,
    PlacementOffer.verified == True
).count() if hasattr(PlacementOffer, 'verified') else 'N/A'
print(f'Verified offers (if column exists): {verified}')

db.close()