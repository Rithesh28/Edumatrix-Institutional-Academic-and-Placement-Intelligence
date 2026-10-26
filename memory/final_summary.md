FINAL SUMMARY — Test Isolation for backend/tests/unit/test_circular_authz.py

PROBLEM: Importing app.api.files to test check_file_permission() triggered
ModuleNotFoundError for multiple unrelated packages:
- sentence_transformers (via app.ai → intent_classifier)
- pdfplumber (via app.api.circulars → file_service → text_extractor)
- Plus other transitive dependencies (torch, transformers, docx, pptx, minio, qdrant)

ROOT CAUSE: Python's import system transitively imports all modules declared
in __init__.py files and service files. The test infrastructure cannot install
packages, so the only reliable fix is to stub modules before they are imported.

SOLUTION: Added module mocking at the top of test_circular_authz.py, before
any application imports occur. This is the minimal, reliable isolation strategy.

CHANGES MADE (all in backend/tests/unit/test_circular_authz.py):

1. Lines 14-20: sys.path setup — ensures app.* imports resolve
2. Lines 22-40: 11 module mocks — stubs all dependencies that would be
   transitively imported; prevents any ModuleNotFoundError
3. Line 56: Changed @patch target from "backend.app.models.circular.Circular"
   to "app.models.circular.Circular" — matches corrected import convention
4. Throughout file: Replaced all "backend.app." → "app." import paths

MOCKED MODULES (11 total):
- sentence_transformers
- app.services.intent_classifier
- app.services.ai_chat_service
- app.services.sentiment_analyser
- app.services.query_router
- app.services.file_storage.text_extractor
- app.services.file_storage.file_service
- app.services.file_storage.minio_client
- app.api.circulars
- app.api.chat
- app.api.ai

PRESERVED: All 11 authorization test cases with their original assertions:
- test_student_branch_matches_lecturer_dept (ALLOW)
- test_student_missing_branch_matching_dept (ALLOW)
- test_different_departments (DENY)
- test_student_no_branch_no_dept (DENY)
- test_lecturer_profile_missing (DENY)
- test_lecturer_dept_null (DENY)
- test_lecturer_dept_empty_or_whitespace (DENY/ALLOW per sub-test)
- test_no_circular_record (DENY)
- test_circular_different_file (DENY)
- test_non_circular_file_types_unchanged (ALLOW)
- test_uploader_check_before_circular (DENY — uploader short-circuits)

RESULT: Tests can now be executed with:
  cd backend
  python -m pytest tests/unit/test_circular_authz.py -v