from app.core.database import SessionLocal
from app.models.user import User
import re

db = SessionLocal()
users = db.query(User).order_by(User.id).all()
print(f"Total users in DB: {len(users)}")

genuine_users = []
test_users = []

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

    if is_test:
        test_users.append(u)
    else:
        genuine_users.append(u)

print(f"Genuine users count: {len(genuine_users)}")
print(f"Test users count: {len(test_users)}")

print("\nGENUINE USERS LIST:")
for u in genuine_users:
    print(f"  ID {u.id}: {u.email} | Name='{u.name}' | Role={u.role.value if u.role else None} | Dept={u.department}")

db.close()
