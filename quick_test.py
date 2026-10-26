import sys
import os

# Setup like the test file
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Mock all the dependencies
from unittest.mock import MagicMock
for _mod in (
    "sentence_transformers",
    "app.services.intent_classifier",
    "app.services.ai_chat_service",
    "app.services.sentiment_analyser",
    "app.services.query_router",
    "app.services.file_storage.text_extractor",
    "app.services.file_storage.file_service",
    "app.services.file_storage.minio_client",
    "app.api.circulars",
    "app.api.chat",
    "app.api.ai",
):
    sys.modules[_mod] = MagicMock()

# Now try importing check_file_permission
try:
    from app.api.files import check_file_permission
    print("SUCCESS: check_file_permission imported without errors")
    print("Module imported successfully - tests can now execute assertions")
except ModuleNotFoundError as e:
    print(f"FAILED: ModuleNotFoundError: {e}")
    # Show what's missing
    print(f"Missing module: {e.name}")
except Exception as e:
    print(f"OTHER ERROR: {type(e).__name__}: {e}")