---
name: diagnostic_procedure
description: Read-only diagnostic for 403 Forbidden on circular download
metadata:
  type: project
---
# Diagnostic Procedure for `GET /files/{file_id}/download` → 403 Forbidden

## Identified Configuration

| Item | Value |
|---|---|
| **Database type** | PostgreSQL (per `backend/app/core/config.py:10`) |
| **Database URL** | `postgresql://edumatrix:edumatrix123@postgres:5432/edumatrix` (from env, do not print) |
| **MinIO buckets** | `exam-duties,assignments,circulars,resumes,timetables,certificates,placement-docs,syllabus,lecture-notes` |
| **Authorization** | `check_file_permission(db, file, current_user)` in `backend/app/api/files.py` |
| **Circular model** | `backend/app/models/circular.py` — `file_id` FK to `files.id` |
| **Student model** | `backend/app/models/student_profiles.py` — `branch` column (abbreviation) |
| **Lecturer model** | `backend/app/models/lecturer_profiles.py` — `department` column (full name) |
| **Normalization** | `backend/app/utils/file_utils.py:get_department_display()` — maps branch codes to full names |

## Minimum Fields Required (Non-Sensitive)

| Field | Source | Purpose |
|---|---|---|
| `file.file_type` | `files` table | Must be `"circular"` for the circular authorization block to execute |
| `Circular.file_id` | `circulars` table | Must match the requested `file.id` for the FK relationship to work |
| `LecturerProfile.department` | `lecturer_profiles` table | Normalized via `get_department_display()` and compared to student's branch |
| `StudentProfile.branch` | `student_profiles` table | The student's branch code (e.g., `"CSE"`, `"AIML"`) |
| `User.department` | `users` table | Fallback value when `student_profile.branch is None` |

## Safest Read-Only Diagnostic Step (Project Owner Execution)

### Option A: PostgreSQL `psql` Command (if database access available)

```bash
# 1. Check the file record (read-only)
psql "postgresql://edumatrix:edumatrix123@postgres:5432/edumatrix" -c
SELECT id, file_type, department, uploaded_by FROM files WHERE id = 'f5a390d0-31a5-4bbf-a5c5-e9389a19c2f1';

# 2. Check if a Circular record references this file
psql "postgresql://edumatrix:edumatrix123@postgres:5432/edumatrix" -c
SELECT id, lecturer_id, department FROM circulars WHERE file_id = 'f5a390d0-31a5-4bbf-a5c5-e9389a19c2f1';

# 3. If Circular exists, get lecturer department
psql "postgresql://edumatrix:edumatrix123@postgres:5432/edumatrix" -c
SELECT u.id, u.department, lp.department AS lecturer_dept
FROM users u
JOIN lecturer_profiles lp ON lp.user_id = u.id
WHERE lp.id = <lecturer_id_from_step_2>;

# 4. Get the student's branch and department
psql "postgresql://edumatrix:edumatrix123@postgres:5432/edumatrix" -c
SELECT s.branch, u.department
FROM student_profiles s
JOIN users u ON u.id = s.user_id
WHERE s.user_id = <student_user_id_from_request_log>;
```

### Option B: Read-Only API Shell (no database access needed)

```powershell
# 1. Get file metadata — this triggers check_file_permission() and returns file details
$baseUrl = "https://<your-api-host>"
$fileId = "f5a390d0-31a5-4bbf-a5c5-e9389a19c2f1"
$token = "<valid-jwt-token>"

# Use the GET /files/{file_id} endpoint — it's safer than download because
# it returns metadata without transferring file content
$response = Invoke-WebRequest -Method Get -Uri "$baseUrl/api/files/$fileId?token=$token" -Headers @{
    "Accept" = "application/json"
}

# Examine:
# - $response.StatusCode  (200 = file found, 404 = not found)
# - $response.department  (the file's department field)
# - $response.file_type   (should be "circular" if this is a circular attachment)
# - $response.uploader_name (who uploaded it)

# 2. If file_type is "circular" and StatusCode is 200, then check:
#    Does the output include any circular-specific hints?

# 3. For the student user, repeat with their token and examine the same fields.
```

### What to Look For (Read-Only Inspection)

| Diagnostic Question | Expected Data | Meaning if Missing/Different |
|---|---|---|
| **Is the file actually circular?** | `file.file_type == "circular"` | If not, the 403 comes from a different permission branch (uploader/HOD/etc.), and the circular normalization fix is irrelevant for this file. |
| **Does a Circular record reference this file?** | `SELECT COUNT(*) FROM circulars WHERE file_id = 'f5a390d0-...'` ≥ 1 | If zero, the 403 is due to "no circular record referencing file" → the circular authorization block is bypassed entirely. |
| **What is the lecturer department value?** | `SELECT department FROM lecturer_profiles WHERE ...` | If it's a code like `"CSE"` vs full name `"Computer Science"`, the `get_department_display()` normalization is the key factor. |
| **What is the student's branch code?** | `SELECT branch FROM student_profiles WHERE user_id = ...` | If it's `"CSE"` or `"AIML"` etc., compare against the confirmed mappings. |
| **What is the student's `current_user.department` fallback?** | `SELECT department FROM users WHERE id = ...` | If the student has no branch, this fallback is used — must also normalize. |
| **Do normalized values match?** | `get_department_display(student_branch).lower() == get_department_display(lecturer_dept).lower()` | If `False` → 403 due to department mismatch (the bug the fix addresses). If `True` → some other branch is denying access. |

## How to Avoid Exposing Secrets in Terminal Output

| Forbidden | Safe Alternative |
|---|---|
| `SELECT * FROM users` | `SELECT id, email, role, department, is_active FROM users WHERE id = <id>` (only needed columns) |
| Printing JWT tokens | Never echo the token value; only reference its existence/expiry |
| Dumping entire tables | Always use `WHERE` clauses to isolate the single file/circular/student |
| Exposing `DATABASE_URL` | The config already has it; only use via the psql command string, don't print the value itself |
| Printing password hashes | The `users` table has `password_hash` — exclude it with explicit column list |

## Recommended Next Step (Wait for Approval)

**The project owner should execute Option A or B above and report:**

1. `file.file_type` value — is it `"circular"`?
2. Whether any `Circular` record references this `file_id`
3. The lecturer's `department` value stored in the `Circular`/`LecturerProfile`
4. The student's `branch` code and `User.department` fallback
5. Whether `get_department_display()` normalization makes them match

**Based on those findings**, the exact denial condition can be determined:
- If file is circular but no Circular record → 403 = "no circular record referencing file"
- If circular exists and normalized departments don't match → 403 = department mismatch (fix: verify mapping)
- If normalized departments match but 403 still occurs → some other permission branch is denying access

**No code changes, file edits, or database modifications should be made until the project owner provides these data points and approves the next action.**