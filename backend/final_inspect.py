import sys
sys.path.insert(0, '.')
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.models import *

DATABASE_URL = 'postgresql://edumatrix:edumatrix123@localhost:5432/edumatrix'
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

db = SessionLocal()

print("=== Current Database State ===")

# Companies
from app.models.company import Company
companies = db.query(Company).order_by(Company.created_at.desc()).all()
print(f"\nCompanies ({len(companies)}):")
for c in companies:
    # Check if timestamp pattern
    import re
    is_test = bool(re.search(r'\b\d{10,13}\b', c.name))
    active = "ACTIVE" if c.is_active else "DEACTIVATED"
    print(f"  ID {c.id}: {c.name} [{active}] (test: {is_test})")

# Student profiles
from app.models.profile import StudentProfileExtended, PlacementStatus
profiles = db.query(StudentProfileExtended).all()
placed = [p for p in profiles if p.placement_status == PlacementStatus.PLACED]
not_applied = [p for p in profiles if p.placement_status == PlacementStatus.NOT_APPLIED]
print(f"\nStudent Profiles: Total={len(profiles)}, PLACED={len(placed)}, NOT_APPLIED={len(not_applied)}")
for p in placed:
    print(f"  - {p.user.name} ({p.user.email}): {p.placement_status}")

# Applications
from app.models.application import Application, ApplicationStatus
apps = db.query(Application).all()
selected = [a for a in apps if a.status == ApplicationStatus.SELECTED]
print(f"\nApplications: Total={len(apps)}, SELECTED={len(selected)}")
for s in selected:
    print(f"  - App {s.id}: {s.student.name} -> {s.job_posting.title} ({s.job_posting.company.name})")

# Placement offers
from app.models.recruitment_round import PlacementOffer, OfferAcceptanceStatus
offers = db.query(PlacementOffer).all()
accepted = [o for o in offers if o.acceptance_status == OfferAcceptanceStatus.ACCEPTED]
print(f"\nPlacement Offers: Total={len(offers)}, ACCEPTED={len(accepted)}")
for o in accepted:
    print(f"  - Offer {o.id}: {o.student.name} -> {o.job_posting.title} ({o.job_posting.company.name})")

# Shortlists
from app.models.shortlist import Shortlist
shortlists = db.query(Shortlist).all()
print(f"\nShortlists: Total={len(shortlists)}")

# Job postings
from app.models.job_posting import JobPosting
jobs = db.query(JobPosting).all()
print(f"\nJob Postings: Total={len(jobs)}")
for j in jobs:
    print(f"  - {j.title} at {j.company.name} [{j.status}]")

db.close()
print("\n=== Done ===")