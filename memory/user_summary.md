Test Fix Summary — backend/tests/unit/test_circular_authz.py

PROBLEM: Importing check_file_permission() triggered ModuleNotFoundError for
sentence_transformers (via AI chat cascade) and pdfplumber (via file storage cascade).

FIX APPLIED (single file: backend/tests/unit/test_circular_authz.py):

1. Lines 14-20: Added sys.path setup — inserts backend dir so app.* imports resolve
2. Lines 22-40: Mocked 11 modules before any app imports — prevents transitive import
   cascade loading sentence_transformers, pdfplumber, torch, transformers, etc.
3. Line 56: Changed @patch target from "backend.app.models.circular.Circular" to
   "app.models.circular.Circular"
4. Throughout file: Replaced all backend.app.* → app.* import paths

11 MOCKED MODULES: sentence_transformers, app.services.intent_classifier,
app.services.ai_chat_service, app.services.sentiment_analyser, app.services.query_router,
app.services.file_storage.text_extractor, app.services.file_storage.file_service,
app.services.file_storage.minio_client, app.api.circulars, app.api.chat, app.api.ai

RESULT: Tests can now run:
  cd backend
  python -m pytest tests/unit/test_circular_authz.py -v

All 11 authorization test cases preserved with original assertions.