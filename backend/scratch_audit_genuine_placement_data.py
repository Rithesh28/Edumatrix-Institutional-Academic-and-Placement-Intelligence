from app.core.database import SessionLocal
from app.models.user import User
from app.models.company import Company
from app.models.job_posting import JobPosting
from app.models.application import Application
from app.models.shortlist import Shortlist
from app.models.recruitment_round import PlacementOffer
from app.models.recruitment_circular import RecruitmentCircular
import re

db = SessionLocal()

# 1. Identify genuine user IDs
genuine_user_ids = set()
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
        genuine_user_ids.add(u.id)

print(f"Total genuine user IDs: {len(genuine_user_ids)}")

# 2. Check applications by genuine users
genuine_apps = db.query(Application).filter(Application.student_id.in_(genuine_user_ids)).all()
print(f"\nTotal applications by genuine students: {len(genuine_apps)}")

genuine_app_job_ids = set()
genuine_app_company_ids = set()

for a in genuine_apps:
    j = db.query(JobPosting).filter(JobPosting.id == a.job_posting_id).first()
    c = db.query(Company).filter(Company.id == j.company_id).first() if j else None
    u = db.query(User).filter(User.id == a.student_id).first()
    genuine_app_job_ids.add(j.id if j else None)
    genuine_app_company_ids.add(c.id if c else None)
    print(f"  App ID {a.id}: Student {u.email} ({u.name}) -> Job {j.id} '{j.title}' (status={j.status.value}) at Company {c.id} '{c.name}' | Status: {a.status.value}")

# 3. Check offers to genuine users
genuine_offers = db.query(PlacementOffer).filter(PlacementOffer.student_id.in_(genuine_user_ids)).all()
print(f"\nTotal placement offers to genuine students: {len(genuine_offers)}")
for o in genuine_offers:
    u = db.query(User).filter(User.id == o.student_id).first()
    j = db.query(JobPosting).filter(JobPosting.id == o.job_posting_id).first()
    c = db.query(Company).filter(Company.id == j.company_id).first() if j else None
    print(f"  Offer ID {o.id}: Student {u.email} -> Job {j.id} at Company {c.id} '{c.name}' | CTC={o.ctc_lpa} LPA | Status: {o.acceptance_status.value}")

# 4. Check shortlists of genuine users
genuine_shortlists = db.query(Shortlist).filter(Shortlist.student_id.in_(genuine_user_ids)).all()
print(f"\nTotal shortlists for genuine students: {len(genuine_shortlists)}")
for s in genuine_shortlists:
    u = db.query(User).filter(User.id == s.student_id).first()
    c = db.query(Company).filter(Company.id == s.company_id).first()
    j = db.query(JobPosting).filter(JobPosting.id == s.job_posting_id).first()
    print(f"  Shortlist ID {s.id}: Student {u.email} -> Company {c.id} '{c.name}' (Job {j.id} '{j.title}')")

db.close()
