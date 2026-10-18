from app.core.database import SessionLocal
from app.models.company import Company
from app.models.job_posting import JobPosting
from app.models.application import Application
import re

db = SessionLocal()
companies = db.query(Company).order_by(Company.id).all()

print(f"Total companies: {len(companies)}")
print("\nCompanies without numbers/timestamps in name:")
for c in companies:
    if not re.search(r"\d", c.name):
        jobs = db.query(JobPosting).filter(JobPosting.company_id == c.id).all()
        job_titles = [f"[Job {j.id}] {j.title} (status={j.status.value})" for j in jobs]
        apps = db.query(Application).filter(Application.job_posting_id.in_([j.id for j in jobs])).count() if jobs else 0
        print(f"  ID {c.id}: '{c.name}' | Active={c.is_active} | Created={c.created_at} | Jobs={len(jobs)} | TotalApps={apps}")
        for jt in job_titles:
            print(f"      - {jt}")

db.close()
