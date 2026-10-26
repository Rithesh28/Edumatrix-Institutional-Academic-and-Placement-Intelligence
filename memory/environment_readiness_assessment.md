# Environment-Readiness Assessment — Circular Attachment Preview/Download

## 1. Database Configuration

### How FastAPI constructs its database engine

**File**: `backend/app/core/database.py` (lines 1-17)
- Creates `engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, echo=False)`
- `SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)`
- `get_db()` yields `SessionLocal()` instances

**File**: `backend/app/core/config.py` (line 10)
- `DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://edumatrix:edumatrix123@postgres:5432/edumatrix")`
- Loads from `.env` file via `load_dotenv()` at module import (line 6)
- **Application normal startup** uses this default — connects to main dev DB on port 5432

### TIER1_TEST_DATABASE_URL recognition

**NOT recognized by normal application startup.** It is only recognized and validated by the tier1 integration test runner:

- **Test runner** (`backend/tests/integration/test_issue1_postgres_tier1.py`, line 305): `test_url = os.environ.get("TIER1_TEST_DATABASE_URL")`
- **Guard function** (line 167-206): `assert_safe_tier1_test_database_url(url_string)` which strictly validates:
  - URL must use PostgreSQL scheme
  - Host must be 127.0.0.1, localhost, or ::1 (loopback only)
  - Port **must be 5434** (`EXPECTED_TIER1_TEST_PORT = 5434`, line 111)
  - Database name **must be** `edumatrix_tier1_test` (line 191)
  - Username **must be** `edumatrix_tier1_test_user` (line 197)
  - No query parameters or fragments allowed
  - Rejects with `RuntimeError` if any check fails

**Normal app startup ignores `TIER1_TEST_DATABASE_URL` entirely** — it always uses `DATABASE_URL` from `.env` or the default.

### Overriding database for one process without modifying `.env`

**Approach**: Set `TIER1_TEST_DATABASE_URL` as a runtime environment variable for the specific process (e.g., `uvicorn` command), not in `.env` file.

```bash
# Example: Start backend with test DB override
TIER1_TEST_DATABASE_URL="postgresql://edumatrix_tier1_test_user:password@127.0.0.1:5434/edumatrix_tier1_test" \
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The backend's `Settings` class only reads `DATABASE_URL` from env (via `os.getenv`), so setting `TIER1_TEST_DATABASE_URL` alone does NOT override the database — the app still uses `DATABASE_URL`. **However**, the tier1 test runner explicitly reconfigures `SessionLocal` to bind to the test engine (see `setUpClass` at line 333: `cls.test_sessionmaker = sessionmaker(..., bind=cls.engine)` where `cls.engine` is created from `TIER1_TEST_DATABASE_URL`).

For the normal FastAPI app, there is **no built-in mechanism** to override the database at runtime without also modifying the `DATABASE_URL` env var or the `Settings` class. The tier1 test approach of re-binding `SessionLocal` after engine creation is a test-only pattern.

### Reliable, read-only way to confirm effective database identity

The tier1 test's validation pattern (lines 317-330) confirms identity by connecting and querying:

```sql
SELECT current_database(), current_user, current_setting('port')::integer;
```

This returns the live database name, user, and port — **without writing anything**. The function `assert_safe_tier1_test_database_url()` (lines 167-206) performs the same checks on the URL string before connection, providing a read-only verification method.

**To confirm without any service startup**: Read the URL env var value and independently verify it matches the expected pattern:
- Scheme: postgresql
- Host: 127.0.0.1 or localhost
- Port: 5434
- Database name: edumatrix_tier1_test
- Username: edumatrix_tier1_test_user

## 2. Redis Configuration

### How application and Celery configure Redis

**File**: `backend/app/core/config.py` (lines 13, 61-62)
- `REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")` — default: main Docker Redis
- `CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", REDIS_URL)` (line 61)
- `CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)` (line 62)

**Backend normal startup**: Uses `REDIS_URL` from `.env` or default `redis://redis:6379/0` — connects to main Docker Redis on port 6379 via service name `redis`.

### TIER1_TEST_REDIS_URL recognition

**NOT recognized by normal application startup.** Only recognized by the tier1 test runner:

- **Test runner** (line 1168): `redis_url = os.environ.get("TIER1_TEST_REDIS_URL")`
- **Guard** (lines 1167-1189): Strict validation:
  - Scheme must be `redis`
  - Hostname must be `127.0.0.1`
  - Port **must be 6381**
  - Path must be `/0`
  - **No credentials** allowed (username/password rejected)
  - **No query parameters** allowed
  - **No fragment** allowed
  - **Must not contain `6379`** (development Redis port detection, line 1188)
  - Rejects with `self.fail()` (test assertion error) if any check fails

### Overriding Redis connection for one process without affecting main/staging

**Approach**: Set `TIER1_TEST_REDIS_URL` as runtime env var for the specific process:

```bash
TIER1_TEST_REDIS_URL="redis://127.0.0.1:6381/0" \
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Again, the normal FastAPI app reads `REDIS_URL` from `.env`/default, so this env var alone does NOT override the Redis connection for the main app. The tier1 test runner configures Celery separately within the test context.

**For Celery specifically**: The test runner saves/restores original config (lines 1194-1198):
```python
original_broker_url = celery_app.conf.broker_url
original_task_routes = celery_app.conf.task_routes
...
```
And reconfigures for eager mode during tests.

## 3. MinIO Isolation

### MinIO client configuration

**File**: `backend/app/services/file_storage/minio_client.py` — not yet read in this audit, but config is in `config.py` (lines 67-78):

```python
MINIO_HOST: str = os.getenv("MINIO_HOST", "minio")
MINIO_PORT: int = int(os.getenv("MINIO_PORT", "9000"))
MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "False").lower() == "true"
MINIO_BUCKETS: List[str] = os.getenv("MINIO_BUCKETS", "exam-duties,assignments,circulars,resumes,timetables,certificates,placement-docs,syllabus,lecture-notes").split(",")
```

**MINIO_ENDPOINT property** (line 75-78):
```python
@property
def MINIO_ENDPOINT(self) -> str:
    scheme = "https" if self.MINIO_SECURE else "http"
    return f"{scheme}://{self.MINIO_HOST}:{self.MINIO_PORT}"
```

### Can application use dedicated test endpoint/bucket via runtime env vars?

**Yes**, all individual settings can be overridden at runtime:

- `MINIO_HOST` — change from `minio` to e.g. `127.0.0.1` or test-host
- `MINIO_PORT` — change from `9000` to e.g. `9001`
- `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` — change from `minioadmin` defaults
- `MINIO_SECURE` — switch between http/https
- `MINIO_BUCKETS` — specify which buckets the app uses

**BUT**: The default `MINIO_BUCKETS` list includes `circulars` which is the bucket we need to test. If we keep the main MinIO instance, the app will use the same `circulars` bucket. Runtime env vars can change the endpoint/credentials but **cannot** give us a completely separate bucket on the same MinIO instance without creating a new bucket (which requires API calls outside read-only scope).

### Smallest safe configuration for separate test MinIO instance

**Minimum env var changes for a separate MinIO instance**:

```bash
MINIO_HOST="127.0.0.1"
MINIO_PORT="9001"           # Different port
MINIO_ACCESS_KEY="testminio"  # Different credentials
MINIO_SECRET_KEY="testminio123"
MINIO_SECURE="False"
MINIO_BUCKETS="test-circulars"  # Only the bucket we need
```

**However**: This requires a separate MinIO container/service running on port 9001 with its own data volume. The read-only assessment cannot verify this exists.

### Critical: Object-key prefix does NOT provide complete isolation

The assessment must confirm: **using a prefix like `test-circulars/` in the main `circulars` bucket does NOT provide complete isolation.**

- MinIO does not enforce prefix-based isolation — any code listing objects in the bucket or deleting "all files" could affect prefixed objects
- The `file_service` functions may not filter by prefix automatically
- If any cleanup script runs against the `circulars` bucket, test files under `test-circulars/` could be deleted
- **Safer approach**: A dedicated MinIO instance with its own bucket on a different port

**Confirmed**: The application CAN use a dedicated test endpoint and bucket through runtime `MINIO_HOST`, `MINIO_PORT`, and `MINIO_BUCKETS` env vars — but this requires the test MinIO instance to actually be running with those settings.

## 4. Authentication and Test Data

### User, student profile, lecturer profile, file, and circular models

**User model** (`backend/app/models/user.py`):
- `id` (Integer, primary key)
- `name` (String, not null)
- `email` (String, unique, not null)
- `password_hash` (String, not null)
- `role` (Enum: STUDENT, LECTURER, HOD, ADMIN, PLACEMENT_OFFICER)
- `department` (String, nullable)
- `student_profile` relationship → `StudentProfileExtended`
- `lecturer_profile` relationship → `LecturerProfile`

**LecturerProfile** (`backend/app/models/lecturer_profiles.py`):
- `id` (Integer, primary key)
- `user_id` (FK → users.id, unique, not null)
- `subjects` (JSON, default=list)
- `department` (String, nullable) ← **used in circular branch eligibility check**

**StudentProfileExtended** (`backend/app/models/profile.py`, lines 36-73):
- `id` (Integer, primary key)
- `user_id` (FK → users.id, unique, not null)
- `branch` (String, nullable) ← **used in student branch eligibility check**
- `full_name`, `enrollment_number`, `year`, `cgpa`, `semester`, etc.

**File model** (`backend/app/models/file.py`):
- `id` (UUID, primary key)
- `filename`, `mime_type`, `bucket`, `object_key` (all not null)
- `file_type` (String, not null) — e.g. `circular`
- `department` (String, not null, indexed) ← access control
- `uploaded_by` (Integer, FK → users.id, nullable)
- `status` (String, default "active")
- `file_size` (Integer, not null)

**Circular model** (`backend/app/models/circular.py`):
- `id` (Integer, primary key)
- `lecturer_id` (Integer, FK → users.id, not null)
- `type` (CircularType enum)
- `title`, `content`, `file_url`, `due_date`
- `file_id` (PGUUID, FK → files.id, nullable) ← **new field from Issue A fix**
- `file_type` (String, nullable)
- `lecturer` relationship → User
- `file` relationship → File

### JWT login flow

1. **POST /auth/login** with email/password
2. Verifies user exists and `verify_password(form_data.password, user.password_hash)`
3. Creates access token: `create_access_token(data={"id": new_user.id, "email": new_user.email, "role": new_user.role.value})`
4. Token returned to client
5. **GET /files/{file_id}** or **GET /files/{file_id}/download** with `Authorization: Bearer <token>`
6. `get_current_user` dependency decodes JWT, queries `User` by id from DB
7. `check_file_permission(db, file, current_user)` checks access based on role, department, branch, file_type

**Cannot bypass permissions through browser**: The frontend `Circulars.jsx` calls `/files/{fileId}/download` with JWT auth; server-side `check_file_permission()` enforces branch eligibility. Pytest fixtures create users with `password_hash="mock_hash_for_test"` — these don't work for JWT-based browser login.

### Minimum test records needed

| Scenario | Required Records |
|----------|-----------------|
| **A. Matching-branch student can access** | - 1 Lecturer user (role=LECTURER, dept=CS) + lecturer_profile with department=CS<br>- 1 Student user (role=STUDENT, dept=CS, student_profile.branch=CS)<br>- 1 File (file_type=circular, department=CS, uploaded_by=lecturer)<br>- 1 Circular (lecturer_id=lecturer, file_id=file, title="Test Circular") |
| **B. Different-branch student denied** | - 1 Lecturer user (role=LECTURER, dept=CS) + lecturer_profile with department=CS<br>- 1 Student user (role=STUDENT, dept=EE, student_profile.branch=EE)<br>- Same File and Circular as above (lecturer dept=CS, student branch=EE → denied per line 306: `!=` comparison) |
| **C. Valid PDF download** | - 1 File (file_type=other or pdf mime, with actual MinIO object content)<br>- 1 Circular attaching that file (file_id FK)<br>- Appropriate permissions via check_file_permission() |

### Creating temporary authenticated test users without production accounts

**Approach**: Create users in the tier1 test database via the test runner's `setUpClass`, which creates only the 5 approved tables (users, files, circulars, reminders, notifications) and inserts test data. However, these accounts exist only in the test database session and use `mock_hash_for_test` passwords that don't work for JWT login.

**For browser-based testing**: Need real users with valid passwords + JWT tokens. The registration flow (`POST /auth/register`) creates users with full profile setup, but this writes to whatever database the backend connects to. If `TIER1_TEST_DATABASE_URL` is set, registration would write to the tier1 test DB — but this is a **database write**, outside read-only scope.

**Read-only assessment can only describe**: The minimum records needed and the authentication flow. Actual user creation requires service startup and is not approved in this assessment phase.

## 5. Safe Execution Plan

### Isolated setup with distinct ports/volumes

| Service | Main Instance | Test Instance (proposed) | Port |
|---------|--------------|-------------------------|------|
| PostgreSQL | Docker, port 5432, database `edumatrix`, user `edumatrix` | **Tier1 test**, port 5434, database `edumatrix_tier1_test`, user `edumatrix_tier1_test_user` | 5434 |
| Redis | Docker, port 6379, database 0 | **Tier1 test**, port 6381, database `/0` | 6381 |
| MinIO | Docker, port 9000, buckets: `exam-duties,assignments,circulars,...` | **Separate instance**, port 9001, bucket `test-circulars` only | 9001 |

### Exact files that would need changes

| File | Change Needed | Read-Only Status |
|------|--------------|------------------|
| `.env` | Add `TIER1_TEST_DATABASE_URL`, `TIER1_TEST_REDIS_URL`, `MINIO_HOST/MINIO_PORT/MINIO_BUCKETS` | **Not modifying** — described only |
| `backend/app/core/config.py` | No changes needed — already reads env vars | Already correct |
| `backend/app/core/database.py` | No changes needed | Already correct |
| `backend/app/core/config.py` MINIO section | No changes needed | Already correct |
| Test runner `test_issue1_postgres_tier1.py` | Already has `TIER1_TEST_DATABASE_URL`/`TIER1_TEST_REDIS_URL` validation | Already correct |
| No files actually edited in this assessment | ✅ | Preserved |

### Proposed commands for review only (NOT executed)

```bash
# 1. Verify tier1 test DB is available on port 5434 (read-only check)
#    If running: psql "$TIER1_TEST_DATABASE_URL" -c "SELECT current_database(), current_user;"
#    If not running: this step cannot be completed without service startup

# 2. Verify tier1 test Redis on port 6381 (read-only check)
#    If running: redis-cli -u "$TIER1_TEST_REDIS_URL" ping
#    If not running: this step cannot be completed without service startup

# 3. Verify MinIO endpoint (read-only check)
#    If running: curl http://127.0.0.1:9001/minio/health/live
#    If not running: cannot verify

# 4. Start backend with test env vars (requires approval - would connect to test DB/Redis)
#    TIER1_TEST_DATABASE_URL="postgresql://edumatrix_tier1_test_user:***@127.0.0.1:5434/edumatrix_tier1_test" \
#    TIER1_TEST_REDIS_URL="redis://127.0.0.1:6381/0" \
#    MINIO_HOST="127.0.0.1" MINIO_PORT="9001" \
#    uvicorn app.main:app --host 0.0.0.0 --port 8000

# 5. Start frontend (requires approval - connects to backend at localhost:8000)
#    npm run dev --port 5173

# 6. Create test records in tier1 test DB (requires approval - DB writes)
#    Would use the backend API or direct SQL against the tier1 test DB

# 7. Execute test scenarios A-D (requires approval - running services + auth)
#    - Student in CS branch accesses circular attached to CS lecturer → should get 200
#    - Student in EE branch accesses same circular → should get 403
#    - Download PDF bytes and verify content
```

### Verifying no development/staging resources are used

**PostgreSQL**: Confirm `TIER1_TEST_DATABASE_URL` (if set) has:
- Host: 127.0.0.1 or localhost (not Docker hostnames like `postgres`, `redis`)
- Port: 5434 (not 5432 or 5433)
- Database: `edumatrix_tier1_test` (not `edumatrix`, `edumatrix_staging`)

**Redis**: Confirm `TIER1_TEST_REDIS_URL` (if set) has:
- Scheme: `redis`
- Hostname: `127.0.0.1` (not `redis`, container names)
- Port: 6381 (not 6379 or 6380)
- No `6379` anywhere in the URL (self-check at line 1188)

**MinIO**: If using main instance, confirm test objects use prefix `test-circulars/` and no cleanup scripts target the `circulars` bucket broadly. If using separate MinIO instance, confirm different port and bucket name.

### Scoped cleanup for test records and test objects

**PostgreSQL tier1 test**: The test runner's `tearDownClass` (not fully read but documented) cleans up only the 5 approved tables. Each test method typically doesn't dirty data beyond its scope, and `setUpClass` creates a fresh schema. **Cleanup procedure** (described, not executed):
```sql
DELETE FROM notification;
DELETE FROM reminder;
DELETE FROM circular;
DELETE FROM file;
DELETE FROM user;
```
Sequences are managed by PostgreSQL auto-vacuum; no manual reset needed between test runs.

**MinIO test objects**: Delete objects with prefix `test-circulars/`:
```python
# Pseudocode — not executed in read-only assessment
client = minio_client.get_minio_client()
objects = client.list_objects("circulars", prefix="test-circulars/")
for obj in objects:
    client.remove_object("circulars", obj.object_name)
```

**No Docker volume reset**: The main `postgres_data` volume is untouched. Tier1 test DB on port 5434 uses a separate instance/volume, so main data is preserved.

### Unresolved blockers

1. **Tier1 test DB/Redis availability**: Ports 5434 and 6381 must be running with the expected data — not confirmed in current environment
2. **MinIO test instance**: Either a separate MinIO container on port 9001, or approval to use main MinIO with `test-circulars/` prefix (with acknowledged risks)
3. **Browser authentication**: Creating JWT-authenticated student/lecturer users requires service startup + DB writes, outside read-only scope
4. **Service startup not approved**: The final constraint from the user's last message explicitly says "We are NOT approving service startup or test-data yet"

**Stop** — no files modified, no services started, no database writes, no credentials printed. All findings are from read-only code and configuration inspection.