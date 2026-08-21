"""
Test direct upload and embedding
"""

import requests
import time

TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MTUsImVtYWlsIjoiYWRtaW5AZWR1bWF0cml4LmNvbSIsInJvbGUiOiJhZG1pbiIsImV4cCI6MTc4Njk3MjU4OX0.9z2xIK3z3laeBktglbTOCqNemdnerrbIah_75WBqBDQ'
BASE_URL = 'http://localhost:8000'
headers = {'Authorization': f'Bearer {TOKEN}'}

print('=' * 60)
print('Test Direct Upload and Embedding')
print('=' * 60)

# Create test content
content = 'This is a test document for testing the direct embedding generation.'
with open('/tmp/direct_test.txt', 'w') as f:
    f.write(content)

print('\n📤 Uploading file...')

with open('/tmp/direct_test.txt', 'rb') as f:
    files = {'file': ('direct_test.txt', f, 'text/plain')}
    params = {
        'file_type': 'assignment',
        'department': 'CS',
        'title': 'Direct Embedding Test'
    }
    response = requests.post(f'{BASE_URL}/files/upload', headers=headers, files=files, params=params)

print(f'Status: {response.status_code}')

if response.status_code == 200:
    result = response.json()
    file_id = result.get('file_id')
    print(f'✅ Upload successful! File ID: {file_id}')
    print(f'   Filename: {result.get("file", {}).get("filename")}')
    
    # Wait a moment for processing
    print('\n⏳ Waiting for embedding generation...')
    time.sleep(3)
    
    # Search for the file
    print('\n🔍 Searching for: test document')
    search_data = {
        'query': 'test document',
        'limit': 5,
        'department': 'CS'
    }
    search_response = requests.post(
        f'{BASE_URL}/files/search',
        headers=headers,
        json=search_data
    )
    
    if search_response.status_code == 200:
        results = search_response.json()
        total = results.get('total', 0)
        print(f'Found {total} results:')
        for r in results.get('results', []):
            print(f'   - {r.get("title")} (Score: {r.get("score", 0):.4f})')
            print(f'     File ID: {r.get("file_id")}')
    else:
        print(f'❌ Search failed: {search_response.text}')
else:
    print(f'❌ Upload failed: {response.text}')