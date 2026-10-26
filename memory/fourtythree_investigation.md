---
name: fortythree_investigation
description: Investigation of 403 Forbidden on /files/{file_id}/download
metadata:
  type: project
---

## 403 Forbidden Investigation: `GET /files/f5a390d0-31a5-4bbf-a5c5-e9389a19c2f1/download`

### Request Trace

**Endpoint**: `GET /files/{file_id}/download`  
**Handler**: `download_file()` at `backend/app/api/files.py:388`  
**Auth dependency**: `get_current_user_flexible`  
**Authorization**: `check_file_permission(db, file, current_user)` at line 401  
**Result**: HTTP 403 Forbidden with detail `"Access denied. File belongs to another department."`

### Authorization Path in `check_file_permission()`

The function has multiple branches. The 403 originates from `check_file_permission()` returning `False`. The circular authorization block at lines 289-321 is the most likely path, but other branches can also deny access.

#### Circular Authorization Block (lines 289-321)

This block only executes when `file.file_type == FT.CIRCULAR`. The conditions that lead to denial within this block:

| Condition | Code Location | Effect |
|---|---|---|
| File is **not** circular type | Line 293 `if file.file_type == FT.CIRCULAR:` | Block skipped; falls through to other permission branches |
| **No Circular record** references this file | Line 295-296 `db.query(Circular).filter(Circular.file_id == file.id).all()` returns `[]` | `for` loop doesn't execute → falls through → return False at line 347 |
| **Lecturer profile missing** | Line 300 `if not circ.lecturer_profile: continue` | Skips this circular record; if all records skipped → return False |
| **Lecturer department NULL/empty/whitespace** | Lines 302-304 `lecturer_dept = circ.lecturer_profile.department or ""` / `if not lecturer_dept.strip(): continue` | Skips this record → return False |
| **Student has no branch nor department** | Lines 307-313 `s_branch = None` / `if not s_branch: continue` | Skips this record → return False |
| **Department mismatch after normalization** | Lines 317-320 `get_department_display()` comparison | Student branch code and lecturer department normalize to different values → return False |

#### Other Permission Branches (before the circular block at line 289)

These can also produce 403 if they execute first:

| Branch | Line | Condition |
|---|---|---|
| **Admin** | Line 233-234 | `current_user.role == UserRole.ADMIN` → returns True (would NOT cause 403) |
| **HOD** | Line 236-237 | `current_user.role == UserRole.HOD and file.department == current_user.department` → returns True (would NOT cause 403) |
| **Uploader** | Lines 239-240 | `file.uploaded_by == current_user.id` → returns True (would NOT cause 403) |
| **Non-circular department check** | Lines 242-243 | `file.file_type not in [PLACEMENT_DOC, CIRCULAR] and file.department and current_user.department and file.department == current_user.department` → returns True (would NOT cause 403) |
| **Placement Officer** | Lines 245-255 | Various checks — can return True or fall through |
| **Student placement offer** | Lines 257-265 | `PlacementOffer` query — can deny or allow |
| **Student circular (old path)** | Lines 267-345 | The full block we've been analyzing |

### Likely Denial Conditions (Based on the Fix)

Given that the circular authorization was recently updated with `get_department_display()` normalization, the **most likely** denial causes are:

1. **Department mismatch after normalization**: Student branch code (e.g., `"CSE"`) and lecturer department (e.g., `"Computer Science"`) do not normalize to the same value. This would have been the bug before the fix; now it should work correctly IF the mappings are right.

2. **File is not a circular type**: `file.file_type != "circular"`, so the circular block is never entered, and some other permission branch denies access.

3. **No Circular record** references this `file.id`: The SQLAlchemy query returns empty, the `for` loop doesn't execute, function returns False at line 347.

4. **Lecturer profile or department missing**: `circ.lecturer_profile is None` or `department is NULL/empty/whitespace`, causing all circular records to be skipped.

5. **Student has no branch or department**: `s_branch stays None` after the fallback logic at lines 307-313.

### Missing Information (Read-Only Constraints)

Since I cannot access the actual logs, database, or make live API requests, the exact denial condition is **inconclusive**. What's needed:

| Missing Data | Why It Matters |
|---|---|
| `file.file_type` value | Is the file actually a `"circular"` type? If not, the circular block is skipped entirely. |
| `circ.lecturer_profile` status | Does the Circular record have a lecturer profile attached? |
| `circ.lecturer_profile.department` value | What department string is stored? Is it a code or full name? |
| `current_user.student_profile.branch` value | What branch code does the student have? |
| `current_user.department` value | What department is assigned to the user record? |
| Log detail text | The `"Access denied. File belongs to another department."` message is consistent with multiple denial paths. |

### Recommended Smallest Safe Diagnostic Step

**Before any database or API changes**: Verify the file type and circular association.

1. **Confirm file is circular**: Query the File model directly (read-only) to check `file.file_type`. If it's not `"circular"`, the 403 comes from a different permission branch, and the circular fix is irrelevant for this file.

2. **Confirm circular association**: Check if any `Circular` records have `file_id == f5a390d0-31a5-4bbf-a5c5-e9389a19c2f1`. If none exist, the 403 is due to "no circular record referencing file."

3. **If circular exists**: Compare the lecturer department string and student branch code. If they use different naming conventions (e.g., `"CSE"` vs `"Computer Science"`), the normalization fix should resolve it — but verify the mappings in `get_department_display()` are correct for the institution's confirmed codes (AIML, CD, CV, CSE, EC, ME, MBA, MCA).

**No code changes should be made** until the file type and circular association are verified. The investigation should first answer: *Is this file actually a circular attachment, and does it have a Circular record?*

### Next Step (Approval Required)

Wait for the project owner to provide or confirm the following before any changes:

- File type of `f5a390d0-31a5-4bbf-a5c5-e9389a19c2f1`
- Whether a `Circular` record references this file ID
- The student's branch code and the lecturer's department value for this circular

These will determine whether the normalization fix is the relevant factor or if a different permission branch is responsible.