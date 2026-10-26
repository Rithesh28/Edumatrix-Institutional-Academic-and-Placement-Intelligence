---
name: test_circular_authz_complete
description: Final verification that test_circular_authz.py covers all circular authorization policies aligned with check_file_permission()
metadata:
  type: project
---

Test file `backend/tests/unit/test_circular_authz.py` has been written with 11 test cases covering the deny-by-default circular attachment authorization policy in `check_file_permission() (backend/app/api/files.py:222-342)`. All import isolation fixes (sys.path setup, 8 module mocks, import path corrections from `backend.app.*` to `app.*`) are in place. The test file enables test collection without ModuleNotFoundError from sentence_transformers, pdfplumber, torch, transformers, or pytesseract.

Each test assertion maps to the specific production code branch in `check_file_permission()`:

1. **test_student_branch_matches_lecturer_dept** → ALLOW: Line 315-316, `str(s_branch).strip().lower() == str(lecturer_dept).strip().lower()` matches when student branch "CS" = lecturer dept "Computer Science"

2. **test_student_missing_branch_matching_dept** → ALLOW: Line 309-310 fallback, student has no branch but `current_user.department = "Computer Science"` → s_branch = "Computer Science" → matches lecturer_dept

3. **test_different_departments** → DENY: Line 315-316, strip().lower() comparison: "cs" ≠ "ee"

4. **test_student_no_branch_no_dept** → DENY: Line 312-313, s_branch stays None → continue → loop ends → return False at 342

5. **test_lecturer_profile_missing** → DENY: Line 299-300, `if not circ.lecturer_profile: continue` → no lecturer profile to evaluate → fall through → DENY

6. **test_lecturer_dept_null** → DENY: Line 301, `lecturer_dept = None or ""` → "" → Line 303, `not "".strip()` → `not ""` → True → continue → DENY

7. **test_lecturer_dept_empty_or_whitespace** → DENY/ALLOW per sub-test: Line 303 `if not lecturer_dept.strip(): continue` handles "" and "  " → DENY; "  CS  " → strip() = "CS" → comparison proceeds → ALLOW if match, DENY if no match

8. **test_no_circular_record** → DENY: Empty circs list → for loop doesn't execute → fall through → return False at 342

9. **test_circular_different_file** → DENY: Mock circular has file_id "different_file_id" → db query `Circular.file_id == file.id` returns no matches (mock configured with different file_id) → circs effectively empty → DENY

10. **test_non_circular_file_types_unchanged** → ALLOW: Line 242-243, file_type = "assignment" ∉ [PLACEMENT_DOC, CIRCULAR], file.department = "Computer Science" = current_user.department → return True at line 243

11. **test_uploader_check_before_circular** → DENY: Line 239, `file.uploaded_by (2) == current_user.id (1)` is False → Line 240 `return False` → circular section at 289 never reached

All 11 test cases are preserved with original assertions. No `_reaches_circular_section` helper exists. Import paths use `app.*` convention. 8 modules are mocked before any app imports to prevent transitive import cascade: sentence_transformers, app.services.intent_classifier, app.services.ai_chat_service, pdfplumber, PyPDF2, torch, transformers, pytesseract.