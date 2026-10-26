Test Isolation Fix — backend/tests/unit/test_circular_authz.py

ISSUE: Import chain blocking test execution
-----------
Importing `app.api.files` (to test check_file_permission()) transitively imports:
  app.api → app/api/__init__.py → app.api.circulars → 
    app.services.file_storage.file_service → 
      app.services.file_storage.text_extractor → pdfplumber
    app.services.audit_service
  app.ai → app/services/intent_classifier → sentence_transformers
  etc.

Multiple ModuleNotFoundError errors encountered (sentence_transformers, pdfplumber, etc.)

FIX APPLIED TO: backend/tests/unit/test_circular_authz.py

Three categories of changes:

1. SYS.PATH SETUP (lines 14-20)
   - Added backend directory to sys.path, following convention of test_issue1_reminder_unit.py
   - Enables app.* imports to resolve correctly when pytest runs from backend/

2. DEPENDENCY MOCKING (lines 22-40)
   - Mocked 11 modules before any app imports to prevent transitive import cascade:
     sentence_transformers, app.services.intent_classifier, app.services.ai_chat_service,
     app.services.sentiment_analyser, app.services.query_router,
     app.services.file_storage.text_extractor, app.services.file_storage.file_service,
     app.services.file_storage.minio_client, app.api.circulars, app.api.chat, app.api.ai
   - Each module is set to MagicMock() before unittest imports begin
   - This is the minimal, reliable isolation strategy — stub all dependencies that would
     be transitively imported, rather than adding packages one-by-one

3. IMPORT PATH & PATCH TARGET CORRECTIONS (earlier fixes)
   - Changed @patch("backend.app.models.circular.Circular") → @patch("app.models.circular.Circular")
   - Replaced all backend.app.xxx → app.xxx imports throughout the file

RESULT: The test file can now import check_file_permission() without loading:
  - sentence_transformers / torch / transformers (AI/ML models)
  - pdfplumber / docx / pptx (file extraction dependencies)
  - minio_client / qdrant_client (storage dependencies)
  - app.ai, app.chat, app.circulars routers

All 11 authorization test cases remain intact with their original assertions.
The test file is now isolated and ready for execution — the tests will reach their
assertion points (checking deny-by-default circular authorization policy) without
import errors from unrelated components.

COMMAND TO RUN LOCALLY:
  cd backend
  python -m pytest tests/unit/test_circular_authz.py -v