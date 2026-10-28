import sys
sys.path.insert(0, '.')
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from app.models import *
from app.core.config import settings

DATABASE_URL = "postgresql://edumatrix:edumatrix123@localhost:5432/edumatrix"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

db = SessionLocal()

# Inspect the SELECTED application
from app.models.application import Application, ApplicationStatus
selected_apps = db.query(Application).filter(Application.status == ApplicationStatus.SELECTED).all()
print("=== SELECTED Applications ===")
for app in selected_apps:
    print(f"  App ID: {app.id}, Student: {app.student.name} ({app.student.email}), Job: {app.job_posting.title}, Company: {app.job_posting.company.name}")

# Inspect the accepted offer
from app.models.recruitment_round import PlacementOffer, OfferAcceptanceStatus
accepted_offers = db.query(PlacementOffer).filter(PlacementOffer.acceptance_status == OfferAcceptanceStatus.ACCEPTED).all()
print("\n=== ACCEPTED Offers ===")
for offer in accepted_offers:
    print(f"  Offer ID: {offer.id}, Student: {offer.student.name} ({offer.student.email}), Job: {offer.job_posting.title}, Company: {offer.job_posting.company.name}")

# Check the student profiles that might be PLACED
from app.models.profile import StudentProfileExtended, PlacementStatus
all_profiles = db.query(StudentProfileExtended).all()
for p in all_profiles:
    if p.placement_status != PlacementStatus.NOT_APPLIED:
        print(f"\nStudent Profile: {p.user.name} ({p.user.email}), Status: {p.placement_status}")

# Check shortlisted applications
shortlisted_apps = db.query(Application).filter(Application.status == ApplicationStatus.SHORTLISTED).all()
print("\n=== SHORTLISTED Applications ===")
for app in shortlisted_apps:
    print(f"  App ID: {app.id}, Student: {app.student.name} ({app.student.email}), Job: {app.job_posting.title}")

# Check companies that look like test data
from app.models.company import Company
companies = db.query(Company).all()
print("\n=== All Companies ===")
for c in companies:
    print(f"  ID: {c.id}, Name: '{c.name}', Active: {c.is_active}, Created: {c.created_at}")

# Check jobs
from app.models.job_posting import JobPosting
jobs = db.query(JobPosting).all()
print("\n=== All Jobs ===")
for j in jobs:
    print(f"  ID: {j.id}, Title: '{j.title}', Company: {j.company.name}, Status: {j.status}")

# Check shortlists
from app.models.shortlist import Shortlist
shortlists = db.query(Shortlist).all()
print("\n=== All Shortlists ===")
for s in shortlists:
    print(f"  ID: {s.id}, Student: {s.student.name} ({s.student.email}), Company: {s.company.name}, Job: {s.job_posting.title}")

db.close()