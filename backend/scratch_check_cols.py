from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
res = db.execute(text("select column_name, is_nullable from information_schema.columns where table_name = 'job_postings' and column_name in ('application_deadline', 'drive_date')")).fetchall()
print(res)
db.close()
