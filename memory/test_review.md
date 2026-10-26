Test Fixes Summary — backend/tests/unit/test_circular_authz.py

Three categories of fixes applied to resolve ModuleNotFoundError and import path issues:

1. SYS.PATH SETUP (lines 14-20)
   - Added backend directory to sys.path, following the same convention as test_issue1_reminder_unit.py
   - Enables app.* imports to resolve correctly when pytest runs from backend/

2. AI/ML DEPENDENCY MOCKING (lines 22-26)
   - Mocked modules before unittest import to prevent import cascade:
     sentence_transformers, app.services.intent_classifier,
     app.services.ai_chat_service, app.services.sentiment_analyser,
     app.services.query_router
   - This was the root cause: importing check_file_permission → app.api.files → chat router → ai_chat_service → intent_classifier → sentence_transformers

3. IMPORT PATH CORRECTIONS
   - Changed @patch("backend.app.models.circular.Circular") → @patch("app.models.circular.Circular") (line 51)
   - Replaced all backend.app.xxx → app.xxx imports throughout the file
   - Follows the import convention used by test_issue1_reminder_unit.py and test_issue1_postgres_tier1.py

4. TEST FILE LOGIC FIXES (from earlier review):
   - Fixed mock_circ.file_id setup in each test to properly test Circular.file_id == file.id filtering
   - Fixed test_circular_different_file to configure a circular with different file_id so FK mismatch is visible
   - Fixed test_lecturer_dept_empty_or_whitespace expectations (whitespace-around values strip to non-empty)
   - Removed no-op _reaches_circular_section helper
   - Fixed MockCircular.file_id == "some_file_id" no-op in test_student_branch_matches_lecturer_dept
   - Simplified test_missing_uploader_does_not_bypass to test_uploader_check_before_circular

FILES CHANGED:
- backend/tests/unit/test_circular_authz.py (import paths, patch target, mock setup, logic fixes)

The import issue is now resolved. Tests can execute their authorization assertions without loading sentence_transformers or other AI/ML dependencies.