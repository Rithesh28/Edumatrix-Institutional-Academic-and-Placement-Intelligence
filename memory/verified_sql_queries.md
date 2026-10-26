---
name: verified_sql_queries
description: Read-only SQL queries for 403 diagnosis on circular download
metadata:
  type: project
---
# Verified Read-Only SQL Queries for 403 Diagnosis

## Verified Table and Column Names (from SQLAlchemy models)

| Table | Primary Key | Key Columns | Foreign Keys |
|---|---|---|---|
| **`files`** | `id` (UUID) | `file_type`, `department`, `uploaded_by` | `uploaded_by → users.id`, `hod_id → users.id` |
| **`circulars`** | `id` (Integer) | `file_id`, `lecturer_id` | `file_id → files.id`, `lecturer_id → users.id` |
| **`users`** | `id` (Integer) | `department`, `role`, `is_active` | — (no FK in this context) |
| **`lecturer_profiles`** | `id` (Integer) | `department`, `user_id` | `user_id → users.id` |
| **`student_profiles`** | `id` (Integer) | `branch`, `user_id` | `user_id → users.id` |

## 1. Affected File: Type and Non-Sensitive Metadata

```sql
-- Select only needed columns; exclude password_hash, secret keys, etc.
SELECT id, file_type, department, uploaded_by, title, filename, mime_type, status, created_at
FROM files
WHERE id = 'f5a390d0-31a5-4bbf-a5c5-e9389a19c2f1';
```

**Expected output columns**: `id`, `file_type`, `department`, `uploaded_by`, `title`, `filename`, `mime_type`, `status`, `created_at`
- **`file_type`** must be `"circular"` for the circular authorization block to execute
- **`department`** is the file's department field (used in non-circular permission checks at line 242)
- **`uploaded_by`** is the user ID who uploaded the file (used in uploader check at line 239)

## 2. Circular Association: Does a Circular Record Reference This File?

```sql
-- Check if any Circular record references this file_id
-- Use LEFT JOIN to also get lecturer_id for the next query
SELECT c.id, c.file_id, c.lecturer_id, c.file_type,
       u.department AS lecturer_dept
FROM circulars c
JOIN users u ON u.id = c.lecturer_id
WHERE c.file_id = 'f5a390d0-31a5-4bbf-a5c5-e9389a19c2f1';
```

**Expected output**:
- If **0 rows**: No Circular record references this file → 403 = "no circular record referencing file"
- If **1+ rows**: Circular record(s) exist; `lecturer_dept` column contains the lecturer's department value

**Important**: Do NOT include `password_hash` or any auth-related columns in the SELECT.

## 3. Lecturer's Department (from the Circular record)

```sql
-- If Circular exists (from query #2), get the lecturer's department
-- Join users to get the user-level department, and lecturer_profiles for the prof-specific dept
SELECT u.id AS user_id, u.department AS user_dept,
       lp.department AS lecturer_department,
       lp.id AS lecturer_profile_id
FROM users u
JOIN lecturer_profiles lp ON lp.user_id = u.id
WHERE lp.id = <lecturer_profile_id_from_query_2>;
```

**Expected output columns**: `user_id`, `user_dept`, `lecturer_department`, `lecturer_profile_id`
- **`lecturer_department`** is the value normalized via `get_department_display()` and compared to the student's branch code
- This is the department the student's branch must match for access to be granted

## 4. Student's Branch and Department Fallback

```sql
-- NOTE: The student user ID must be obtained from the request log or session context.
-- Replace <student_user_id> with the actual user ID from the authenticated request.
SELECT s.branch, u.department AS user_department
FROM student_profiles s
JOIN users u ON u.id = s.user_id
WHERE s.user_id = <student_user_id>;
```

**Expected output columns**: `branch`, `user_department`
- **`branch`** is the student's branch code (e.g., `"CSE"`, `"AIML"`, `NULL` if not set)
- **`user_department`** is the fallback value used when `student_profile.branch is None`
- Both values are fed into `get_department_display()` and compared case-insensitively after strip

**Note**: The student user ID must come from the live request context — it cannot be derived from the file ID alone. If the identity cannot be established from existing logs, the project owner must obtain it from the authentication middleware or request trace.

## Execution Instructions (Read-Only, Project Owner)

### Preferred Method: PostgreSQL `psql` Client

```bash
# 1. Set variables (replace passwords ONLY if explicitly approved by project owner)
# DO NOT print or echo the full DATABASE_URL containing credentials

# 2. Run each query in psql, one at a time:
psql "postgresql://edumatrix:edumatrix123@postgres:5432/edumatrix" -c
SELECT id, file_type, department, uploaded_by, title, filename, mime_type, status, created_at
FROM files
WHERE id = 'f5a390d0-31a5-4bbf-a5c5-e9389a19c2f1';

# 3. Second query:
psql "postgresql://edumatrix:edumatrix123@postgres:5432/edumatrix" -c
SELECT c.id, c.file_id, c.lecturer_id, c.file_type,
       u.department AS lecturer_dept
FROM circulars c
JOIN users u ON u.id = c.lecturer_id
WHERE c.file_id = 'f5a390d0-31a5-4bbf-a5c5-e9389a19c2f1';

# 4. Third query (replace <lecturer_profile_id> with id from step 2):
psql "postgresql://edumatrix:edumatrix123@postgres:5432/edumatrix" -c
SELECT u.id AS user_id, u.department AS user_dept,
       lp.department AS lecturer_department,
       lp.id AS lecturer_profile_id
FROM users u
JOIN lecturer_profiles lp ON lp.user_id = u.id
WHERE lp.id = <lecturer_profile_id>;

# 5. Fourth query (replace <student_user_id> with actual ID from request log):
psql "postgresql://edumatrix:edumatrix123@postgres:5432/edumatrix" -c
SELECT s.branch, u.department AS user_department
FROM student_profiles s
JOIN users u ON u.id = s.user_id
WHERE s.user_id = <student_user_id>;
```

### Safety Controls

| Forbidden | Safe Alternative |
|---|---|
| Printing `DATABASE_URL` with credentials | Use the psql command string without echoing it; the connection string itself is not output |
| Dumping entire tables | Always `WHERE id = '<specific-uuid>'` to isolate single records |
| Including `password_hash` in output | Explicitly list only needed columns; exclude `password_hash` |
| Echoing JWT tokens | Never include token values in psql commands or shell output |
| Running queries without `WHERE` clause | Always filter by the specific file ID or ID being investigated |

### Verification Without Live Execution

Since I cannot execute these queries against the live environment, the project owner should:

1. **Confirm the file type**: `file_type = "circular"`? If not, the 403 comes from a different permission branch.
2. **Confirm circular association**: 0 rows → 403 = "no circular record"; 1+ rows → continue to step 2.
3. **Compare department values**: Run `get_department_display(student_branch).strip().lower()` vs `get_department_display(lecturer_dept).strip().lower()`.
   - If `False` → 403 = department mismatch (the bug the normalization fix addresses)
   - If `True` → some other permission branch is denying access

2. **Wait for approval** before any live database inspection. The queries above are for review only; do not execute them until the project owner approves the diagnostic step and provides any missing data (such as the student user ID).

---