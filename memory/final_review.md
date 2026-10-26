---
name: final_review
description: Final authorization fix review - branch code to department normalization
metadata:
  type: project
---

## Fix Summary

**Problem**: Student branch codes (e.g., "CSE", "AIML") were compared raw against lecturer department names (e.g., "Computer Science", "Artificial Intelligence and Machine Learning") using case-insensitive string equality. This would always deny cross-department access in production because "cse" ≠ "computer science".

**Root Cause**: `backend/app/api/files.py:315` compared `s_branch` (student branch code) directly against `lecturer_dept` (lecturer full department name) without normalization.

**Solution**: Use the existing `get_department_display()` utility to normalize branch codes to full department names before comparison.

### Changes Made

1. **`backend/app/utils/file_utils.py`** — Updated `get_department_display()` with confirmed mappings:
   - AIML → Artificial Intelligence and Machine Learning
   - CD → Data Science
   - CV → Civil
   - CSE → Computer Science
   - EC → Electronics and Communication
   - ME → Mechanical
   - MBA → MBA
   - MCA → MCA
   - Preserved legacy: CS → Computer Science, IT → Information Technology, EE → Electrical Engineering, CE → Civil Engineering
   - Added `.strip()` for whitespace tolerance

2. **`backend/app/api/files.py`** — Integrated normalization into `check_file_permission()`:
   - Import `get_department_display` from `..utils.file_utils`
   - Normalize both `s_branch` and `lecturer_dept` via the utility before comparison
   - Maintain deny-by-default: missing profile, NULL/empty/whitespace department, no branch/dept all deny

3. **`backend/tests/unit/test_circular_authz.py`** — Updated test fixtures:
   - Policy 1 now exercises all 8 confirmed branch code mappings with realistic department names
   - Tests no longer compare identical abbreviations ("CS" = "CS")
   - All 11 tests pass with the normalization path exercised

### Verification

Command: `python -m pytest tests/unit/test_circular_authz.py -v`
Result: **11 passed, 0 failed**

All denial scenarios preserved:
- Missing lecturer profile → deny
- NULL lecturer department → deny
- Missing student branch and department → deny
- Department mismatches → deny
- No circular record referencing file → deny
- Circular referencing different file ID → deny

Non-circular and uploader permissions unchanged.