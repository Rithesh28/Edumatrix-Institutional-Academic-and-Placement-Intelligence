---
name: circular-permission-review
description: Review of the Issue A circular preview/download permission fix
metadata:
  type: reference
---
## Issue A: Circular Preview/Download Permission Fix

### Current Implementation (backend/app/api/files.py lines 289-311)

The student access section checks institutional circulars by querying `Circular.file_id == file.id`. The `Circular` model has these fields:
- `id`, `lecturer_id`, `type`, `title`, `content`, `file_url`, `due_date`, `created_at`, `updated_at`
- `file_id` (new: ForeignKey to Files.id, nullable)
- `file_type` (String(50), nullable)

There is **no `status` field** on the Circular model.

### Permission Logic Analysis

1. **File Type Check** (line 292): `if file.file_type == FT.CIRCULAR:` — correctly identifies circular files.

2. **Attachment Query** (lines 294-296): `Circular.file_id == file.id` — links circular records to their attached file. This is the correct relationship since Circular has a `file_id` ForeignKey.

3. **Branch Eligibility** (lines 299-311): Checks if student's branch (from `student_profile.branch` or `department`) matches the circular's lecturer's department (`lecturer_profile.department`). 

4. **Missing Student Profile Safety** (lines 300-303, 308-310): Handles cases where `student_profile` or `department` may be None — falls through to no-restriction mode if neither is available.

### Defects and Risks

**Risk: Branch eligibility fails silently when lecturer_profile is None**
- Line 304: `if s_branch and circ.lecturer_profile:` — if `circ.lecturer_profile` is None, the student gets no access even if they have a branch. This could be a legitimate denial (circular with no lecturer dept) or a data gap.

**Risk: No department on circular = unrestricted access**
- Lines 308-311: If student has no branch (`not s_branch`) and circular has no department (`not lecturer_dept`), access is granted unconditionally. This is intentional for cross-departmental circulars but could be overly permissive if lecturer_profile.department is frequently null.

**Risk: Student with only department, no branch**
- Line 302-303: If `current_user.department` exists but `student_profile.branch` doesn't, the department is used for comparison. This assumes department alone is sufficient, which may not match the branch-based system.

**Preview vs Download**: The `check_file_permission()` function is used for both preview and download endpoints (lines 341+). The same permission logic applies to both, which is correct — a file should be either previewable/downloadable or not, without separate rules.

### Frontend Usage

The frontend (`frontend/src/pages/student/Circulars.jsx`) uses the `/files/{fileId}/download` endpoint (line 43, 77) for both preview and download. The permission check happens server-side in `check_file_permission()`. The frontend does not implement separate preview/download authorization — it relies entirely on the endpoint returning 200 or 401/403.

### Recommendations

1. **The current fix is safe** — removing the `Circular.status == "published"` check (which referenced a non-existent field) and using `Circular.file_id == file.id` instead is the correct approach.

2. **Consider adding a guard for missing lecturer_profile.department** — if `circ.lecturer_profile` exists but has no department, currently access falls through to the `not s_branch` branch (lines 308-311). This could be made more explicit.

3. **The frontend correctly uses a single download endpoint** for both preview and download, which aligns with the server-side permission logic.

4. **No changes needed to the fix** unless lecturer_profile.department null-handling is observed to cause real user issues.