with open('D:/Edumatrix-Institutional-Academic-and-Placement-Intelligence/backend/tests/unit/test_circular_authz.py', 'r') as f:
    content = f.read()
# Check all mock modules are present
mock_modules = [
    'sentence_transformers',
    'app.services.intent_classifier',
    'app.services.ai_chat_service',
    'app.services.sentiment_analyser',
    'app.services.query_router',
    'app.services.file_storage.text_extractor',
    'app.services.file_storage.file_service',
    'app.services.file_storage.minio_client',
    'app.api.circulars',
    'app.api.chat',
    'app.api.ai',
]
for m in mock_modules:
    if f'sys.modules["{m}"]' in content:
        print(f'OK: {m} mocked')
    else:
        print(f'MISSING: {m}')
# Check no pdfplumber in file
if 'pdfplumber' in content:
    print('WARNING: pdfplumber still in file')
else:
    print('OK: No pdfplumber references')