import requests

BASE_URL = 'http://localhost:8000'

# 1. Login as Student 104 (Rakshith R Shetty, AIML)
from app.core.database import SessionLocal
from app.models.user import User
from app.core.security import create_access_token

db = SessionLocal()
u104 = db.query(User).filter(User.id == 104).first()
if not u104:
    u104 = db.query(User).filter(User.email == '4vp23ai037@gmail.com').first()
s104_token = create_access_token(data={"id": u104.id, "sub": str(u104.id), "role": u104.role.value if hasattr(u104.role, 'value') else str(u104.role)})
s104_headers = {'Authorization': f'Bearer {s104_token}'}
s104_user = {"id": u104.id, "name": u104.name, "email": u104.email, "role": u104.role.value if hasattr(u104.role, 'value') else str(u104.role), "department": u104.department}
db.close()

print('=== STUDENT 104 LOGIN ===')
print(f'ID: {s104_user["id"]}, Name: {s104_user["name"]}, Email: {s104_user["email"]}, Role: {s104_user["role"]}, Dept: {s104_user.get("department")}')

# 2. Check Circulars listing for Student 104
circ_resp = requests.get(f'{BASE_URL}/placement/circulars', headers=s104_headers)
assert circ_resp.status_code == 200, f'GET /placement/circulars failed: {circ_resp.text}'
circulars = circ_resp.json()
print(f'\n=== STUDENT 104 CIRCULAR LISTING (/placement/circulars) ===')
print(f'Total Published Circulars Visible: {len(circulars)}')
circ_523 = None
for c in circulars:
    print(f'  - Circular ID: {c["id"]}, Title: "{c["title"]}", Company: "{c.get("company_name")}", Status: {c["status"]}, Branches: {c["branch_eligibility"]}')
    if c["id"] == 523:
        circ_523 = c

assert circ_523 is not None, "Circular 523 must be visible in the listing!"
print(f'>>> VERIFIED: Circular 523 is present in the listing and the count is {len(circulars)}')

# 3. Direct GET for Circular 523
c523_resp = requests.get(f'{BASE_URL}/placement/circulars/523', headers=s104_headers)
print(f'\n=== DIRECT GET /placement/circulars/523 ===')
print(f'Status: {c523_resp.status_code}')
assert c523_resp.status_code == 200
c523 = c523_resp.json()
print(f'Title: {c523["title"]}, Company: {c523.get("company_name")}, Linked Jobs Count: {len(c523.get("linked_jobs", []))}')
for lj in c523.get('linked_jobs', []):
    print(f'   Linked Job #{lj.get("job_posting_id")}: {lj.get("title")} ({lj.get("status")})')

# 4. Check Notifications for Student 104
notif_resp = requests.get(f'{BASE_URL}/notifications/me', headers=s104_headers)
print(f'\n=== NOTIFICATIONS FOR STUDENT 104 (/notifications/me) ===')
print(f'Status: {notif_resp.status_code}')
if notif_resp.status_code == 200:
    notifs = notif_resp.json()
    print(f'Total notifications: {len(notifs)}')
    for n in notifs[:5]:
        print(f'  - ID: {n.get("id")}, Type: {n.get("type")}, Title: {n.get("title")}, Ref: {n.get("reference_id")}')

# 5. Fallback Check: Direct GET for /placement/jobs/523 (legacy notification target simulation)
job523_resp = requests.get(f'{BASE_URL}/placement/jobs/523', headers=s104_headers)
print(f'\n=== LEGACY FALLBACK CHECK /placement/jobs/523 ===')
print(f'Status: {job523_resp.status_code}')
print(f'Response payload: {job523_resp.json()}')
assert job523_resp.status_code == 404
detail = job523_resp.json().get('detail', {})
if isinstance(detail, dict):
    assert 'circular_fallback' in detail
    assert detail['circular_fallback']['circular_id'] == 523
    print('>>> VERIFIED: Structured circular_fallback successfully returned for legacy job route /placement/jobs/523')

# 6. Verify Student 1 (adi01@gmail.com)
s1_login = requests.post(f'{BASE_URL}/auth/login', data={'username': 'adi01@gmail.com', 'password': '54321'})
assert s1_login.status_code == 200
s1_headers = {'Authorization': f'Bearer {s1_login.json()["access_token"]}'}
s1_circ_resp = requests.get(f'{BASE_URL}/placement/circulars', headers=s1_headers)
assert s1_circ_resp.status_code == 200
print(f'\n=== STUDENT 1 (adi01@gmail.com) CIRCULAR LISTING ===')
print(f'Total Published Circulars Visible: {len(s1_circ_resp.json())}')
assert any(c['id'] == 523 for c in s1_circ_resp.json()), "Circular 523 must be visible to Student 1"
print('>>> VERIFIED: Circular 523 is present for Student 1 as well!')
print('\n*** ALL LIVE VERIFICATIONS SUCCEEDED ***')
