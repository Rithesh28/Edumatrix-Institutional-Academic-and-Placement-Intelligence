"""
Upload file with embedding test
"""

import requests
import time
import json
import os

TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MTUsImVtYWlsIjoiYWRtaW5AZWR1bWF0cml4LmNvbSIsInJvbGUiOiJhZG1pbiIsImV4cCI6MTc4Njk3MjU4OX0.9z2xIK3z3laeBktglbTOCqNemdnerrbIah_75WBqBDQ'
BASE_URL = 'http://localhost:8000'
headers = {'Authorization': f'Bearer {TOKEN}'}

print('=' * 60)
print('Upload with Embedding Test')
print('=' * 60)

# Create a test file with clear content
content = """This is a test document for the EduMatrix file storage system.
It contains information about artificial intelligence and machine learning.
The document is being uploaded to test the semantic search functionality.

Topics covered:
1. Artificial Intelligence - AI is the simulation of human intelligence in machines
2. Machine Learning - ML is a subset of AI that enables systems to learn from data
3. Neural Networks - Computing systems inspired by biological neural networks
4. Deep Learning - A subset of ML using multi-layer neural networks
5. Natural Language Processing - NLP enables computers to understand human language

Keywords: AI, machine learning, neural networks, deep learning, NLP, computer science.
"""

with open('/tmp/test_doc.txt', 'w') as f:
    f.write(content)

print('\n📤 Uploading document...')

with open('/tmp/test_doc.txt', 'rb') as f:
    files = {'file': ('test_doc.txt', f, 'text/plain')}
    params = {
        'file_type': 'assignment',
        'department': 'CS',
        'title': 'AI and Machine Learning Document',
        'description': 'Test document for semantic search'
    }
    response = requests.post(f'{BASE_URL}/files/upload', headers=headers, files=files, params=params)

if response.status_code != 200:
    print(f'❌ Upload failed: {response.text}')
    exit()

result = response.json()
file_id = result.get('file_id')
print(f'✅ Upload successful!')
print(f'   File ID: {file_id}')
print(f'   Filename: {result.get("file", {}).get("filename")}')

# Wait for Celery to process
print('\n⏳ Waiting for embedding generation (15 seconds)...')
time.sleep(15)

# Check if vector exists
print('\n🔍 Checking if vector was created...')
from app.services.file_storage.qdrant_client import qdrant_client
vector = qdrant_client.get_vector(file_id)
if vector:
    print(f'✅ Vector found! Length: {len(vector)}')
else:
    print('❌ No vector found')

# Test search
print('\n🔍 Testing semantic search...')
search_data = {
    'query': 'artificial intelligence machine learning',
    'limit': 10,
    'department': 'CS'
}
search_response = requests.post(f'{BASE_URL}/files/search', headers=headers, json=search_data)

if search_response.status_code == 200:
    results = search_response.json()
    print(f'Found {results.get("total")} results')
    for r in results.get('results', []):
        print(f'   - {r.get("title")} (Score: {r.get("score", 0):.4f})')
else:
    print(f'❌ Search failed: {search_response.text}')