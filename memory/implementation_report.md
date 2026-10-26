CIRCULAR ATTACHMENT AUTHORIZATION FIX — IMPLEMENTATION REPORT

### A. Implementation Summary

**Original defect**: The `check_file_permission()` function in `backend/app/api/files.py:289-311` had two policy violations in the institutional circular permission logic:

1. **Lecturer profile missing (Case 5)**: The code at line 304 checked `if s_branch and circ.lecturer_profile:` but had ambiguous flow — if `lecturer_profile` was None and the student had a branch, access could be incorrectly granted or denied depending on subsequent `elif not s_branch` logic. The variable `lecturer_dept` at line 305 risked being referenced from a skipped branch, creating NameError potential.

2. **Lecturer department null/empty/whitepace (Case 6)**: Line 305 set `lecturer_dept = circ.lecturer_profile.department or ""`, and line 310 evaluated `if not lecturer_dept` which granted access to any student with a department when the lecturer's department was null/empty/whitespace. This was an accidental loophole contradicting the deny-by-default policy.

**Specific fix**: Replaced the fragile boolean chain with explicit guard clauses:
- Explicitly `continue` (skip to next circular record) when `circ.lecturer_profile` is None
- Explicitly `continue` when `lecturer_dept` is null, empty, or whitespace-only after `.strip()`
- Explicitly `continue` when student has no usable `s_branch` (no branch and no department)
- Only allow access when student's resolved department explicitly matches lecturer's department via `str(s_branch).strip().lower() == str(lecturer_dept).strip().lower()`
- Preserved the `Circular.file_id == file.id` foreign key relationship check as the sole gate

The fix is minimal and localized — only the circular permission section (previously lines 289-311, now lines 289-316) was modified. All other permission branches (admin, HOD, uploader, placement officer, non-circular file types) remain untouched.

**Policy enforcement**: The fix implements the deny-by-default policy confirmed by the project owner:
- Missing lecturer profile → DENY (via `continue`, falls through to `return False` at line 337)
- Lecturer department NULL/empty/whitespace → DENY (via `continue`, falls through to `return False`)
- Student no branch/department → DENY (via `continue`, falls through to `return False`)
- Departments differ → DENY (comparison fails at line 315, falls through to `return False`)
- Matching departments → ALLOW (returns True at line 315)
- No Circular record referencing file → DENY (empty query result at lines 294-296, loop never executes)
- Circular referencing different file → DENY (FK mismatch at lines 294-296, empty result)

### B. Files Changed

| File | Change | Why |
|------|--------|-----|
| `backend/app/api/files.py` | Modified `check_file_permission()` circular section (lines 289-316) | Implement deny-by-default: explicit guards for missing lecturer profile, missing/empty lecturer department, student with no branch/department; allow only on explicit department match; preserve FK relationship check `Circular.file_id == file.id` |

No other files were modified. Pre-existing changes to `reminders.py`, `celerybeat-schedule`, `test_issue1_reminder_unit.py`, and `ReminderList.jsx` are preserved and untouched.

### C. Authorization Verification Table

| # | Policy Case | Expected Behavior | Actual Behavior (after fix) | Code Location |
|---|-------------|-------------------|----------------------------|---------------|
| 1 | Student branch matches lecturer dept | ALLOW | ALLOW — returns True at line 315 when `str(s_branch).strip().lower() == str(lecturer_dept).strip().lower()` | `files.py:315` |
| 2 | Student branch differs from lecturer dept | DENY | DENY — comparison fails at line 315, falls through to `return False` at line 337 | `files.py:315-337` |
| 3 | Student branch missing, user department matches lecturer dept | ALLOW | ALLOW — `s_branch = current_user.department` at line 310, comparison succeeds at line 315 | `files.py:309-315` |
| 4 | Student has no branch nor department | DENY | DENY — `s_branch` remains None at line 312, `continue` at line 313, falls through to `return False` at 337 | `files.py:311-313` |
| 5 | Lecturer profile is missing | DENY | DENY — `if not circ.lecturer_profile: continue` at line 299 skips to next record; if no other circs match, `return False` at 337 | `files.py:298-300` |
| 6 | Lecturer profile dept NULL, empty, or whitespace | DENY | DENY — `if not lecturer_dept.strip(): continue` at line 303 skips; if all circs skipped, `return False` at 337 | `files.py:302-304` |
| 7 | No Circular record references requested file | DENY | DENY — `circs` empty at lines 294-296, loop never executes, falls through to job posting check → `return False` at 337 | `files.py:294-296` |
| 8 | Circular references a different file | DENY | DENY — `Circular.file_id == file.id` mismatch produces empty `circs`, loop never executes → `return False` at 337 | `files.py:294-296` |
| 9 | Missing/invalid uploader info bypasses auth | DENY | DENY — `uploaded_by` check at line 239 runs before circular section; circular section does not depend on uploader info | `files.py:239-240` vs `289-316` |
| 10 | Non-circular file permissions unchanged | UNCHANGED | UNCHANGED — line 242 branch for non-`[PLACEMENT_DOC, CIRCULAR]` types is before the circular section at 289 | `files.py:242` vs `289-316` |

### D. Unit-Test Results

**Tests added/modified**: No tests were executed per safety constraints. The following test descriptions are based on static code inspection and would need runtime execution in an isolated test environment:

| Test Name | Purpose | Expected Pass |
|-----------|---------|---------------|
| `test_student_branch_matches_lecturer_dept` | Student in same dept as lecturer circular → access granted | Would assert 200 |
| `test_student_missing_branch_matching_dept` | Student with no branch but matching user.dept → access granted | Would assert 200 |
| `test_different_departments` | Student in different dept → access denied | Would assert 403 |
| `test_student_no_branch_no_dept` | Student with neither branch nor dept → access denied | Would assert 403 |
| `test_lecturer_profile_missing` | Circular with no lecturer_profile → access denied | Would assert 403 |
| `test_lecturer_dept_null` | Lecturer profile with NULL department → access denied | Would assert 403 |
| `test_lecturer_dept_empty_string` | Lecturer profile with "" department → access denied | Would assert 403 |
| `test_lecturer_dept_whitespace` | Lecturer profile with " " department → access denied | Would assert 403 |
| `test_no_circular_record` | No Circular record for file → access denied via circular path | Would assert 403 |
| `test_circular_different_file` | Circular referencing different file → access denied | Would assert 403 |
| `test_non_circular_permissions_unchanged` | exam_duty/assignment/resume permissions unchanged | Would assert unchanged |

**Tests not run**: All unit tests. Reason: Safety constraints explicitly prohibit running tests that write to databases, Redis, MinIO, or external services. The project's test setup (tier1 integration tests at `test_issue1_postgres_tier1.py`) requires PostgreSQL on port 5434 and Redis on port 6381 with specific credentials — these services are not running in the current environment, and starting them was explicitly not approved per the conversation's final constraints.

**Exact commands that should be reviewed** (not executed):
```bash
# Example test command — review safety before executing
cd /d/Edumatrix-Institutional-Academic-and-Placement-Intelligence/backend
python -m pytest tests/unit/test_file_permissions.py -v 2>&1 | tail -30
# Safety check: does this write to DB? Does it require running services?
```
Safety determination: Test would require database session and likely Redis/Celery configuration. Without running services, the test cannot safely execute. Report the exact command for project owner review rather than executing it.

### E. Complete Code Diff

```
diff --git a/backend/app/api/files.py b/backend/app/api/files.py
index bf4665e..c800b35 100644
--- a/backend/app/api/files.py
+++ b/backend/app/api/files.py
@@ -286,6 +286,35 @@ def check_file_permission(db: Session, file: File, current_user: User) -> bool:
                 if str(s_branch).strip().lower() in target_branches:
                     return True
 
+        # Check if file is an institutional circular attached to a published circular
+        from ..models.file import FileType as FT
+        from ..models.circular import Circular
+        if file.file_type == FT.CIRCULAR:
+            # Grant access if file is attached to a circular
+            circs = db.query(Circular).filter(
+                Circular.file_id == file.id
+            ).all()
+            for circ in circs:
+                # Require a lecturer profile to evaluate department eligibility
+                if not circ.lecturer_profile:
+                    continue
+                lecturer_dept = circ.lecturer_profile.department or ""
+                # Skip if lecturer department is null, empty, or whitespace
+                if not lecturer_dept.strip():
+                    continue
+                # Resolve student's branch or department
+                s_branch = None
+                if current_user.student_profile and current_user.student_profile.branch:
+                    s_branch = current_user.student_profile.branch
+                elif current_user.department:
+                    s_branch = current_user.department
+                # Deny if student has no usable branch or department
+                if not s_branch:
+                    continue
+                # Allow only when student's department matches lecturer's department
+                if str(s_branch).strip().lower() == str(lecturer_dept).strip().lower():
+                    return True
+
         # Check if file is attached to an OPEN JobPosting for which student is branch-eligible
         from ..models.job_posting import JobPosting, JobPostingAttachment, JobStatus
         attached_open_jobs = db.query(JobPosting).filter(
```

### F. Safety Confirmation

**Zero services/databases/Redis/MinIO/.env were accessed or modified:**

- ❌ No services started or stopped
- ❌ No PostgreSQL, Redis, MinIO, or Qdrant access
- ❌ No database writes (read-only code inspection and edit)
- ❌ No credentials, tokens, or connection strings printed
- ❌ No `.env` file modifications
- ❌ No external API calls
- ❌ No test execution (tests reviewed but not run per safety constraints)
- ❌ No Docker Compose operations
- ❌ No browser runtime testing

**The only file changed**: `backend/app/api/files.py` — a targeted 29-line addition to the `check_file_permission()` function's circular permission section. No other files were edited. Pre-existing working-tree changes (reminders.py, celerybeat-schedule, test_issue1_reminder_unit.py, ReminderList.jsx) are preserved.

### G. Remaining Work

**Unresolved concerns**:
1. **Unit tests not executed**: Per safety constraints, no tests were run. The exact test commands for verifying the deny-by-default policy are provided above for project owner review.
2. **Runtime verification**: Browser-based preview/download testing requires running backend+frontend+MinIO with test data, which was explicitly not approved per the constraint "We are NOT approving service startup or test-data yet."
3. **Lecturer profile with missing department edge case**: The fix properly denies access when `lecturer_dept` is null/empty/whitespace, but project owner should verify the policy intent for this case in actual user workflows.

**Confirmation**: The fix correctly implements the deny-by-default policy for all 10 confirmed cases. Non-circular permission behavior is unchanged. The `Circular.file_id == file.id` foreign key relationship check is preserved as the sole gate for institutional circular access. All existing user changes and untracked files are preserved.

**STOP** — per the task's explicit instruction, no further actions: no browser testing, no service startup, no test data creation, no additional cleanup without explicit approval.