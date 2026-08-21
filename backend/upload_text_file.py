"""
Upload a text file and test search
"""

import requests
import json

TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MTUsImVtYWlsIjoiYWRtaW5AZWR1bWF0cml4LmNvbSIsInJvbGUiOiJhZG1pbiIsImV4cCI6MTc4Njk3MjU4OX0.9z2xIK3z3laeBktglbTOCqNemdnerrbIah_75WBqBDQ'
BASE_URL = 'http://localhost:8000'
headers = {'Authorization': f'Bearer {TOKEN}'}

print('=' * 60)
print('Upload Text File & Test Search')
print('=' * 60)

# Create text file content
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

with open('/tmp/search_test.txt', 'w') as f:
    f.write(content)

print('\n📤 Uploading text file...')

with open('/tmp/search_test.txt', 'rb') as f:
    files = {'file': ('search_test.txt', f, 'text/plain')}
    params = {
        'file_type': 'assignment',
        'department': 'CS',
        'title': 'AI and Machine Learning Document',
        'description': 'Test document for semantic search functionality'
    }
    response = requests.post(f'{BASE_URL}/files/upload', headers=headers, files=files, params=params)

if response.status_code != 200:
    print(f'❌ Upload failed: {response.text}')
    sys.exit(1)

result = response.json()
file_id = result.get('file_id')
print(f'✅ Upload successful!')
print(f'   File ID: {file_id}')
print(f'   Filename: {result.get("file", {}).get("filename")}')
print(f'   Title: {result.get("file", {}).get("title")}')

# Wait a moment for embedding generation
import time
print('\n⏳ Waiting for embedding generation...')
time.sleep(3)

# Test search with different queries
print('\n🔍 Testing semantic search...')
print('=' * 60)

queries = [
    'artificial intelligence machine learning',
    'neural networks deep learning',
    'NLP natural language processing',
    'computer science AI'
]

for query in queries:
    search_data = {
        'query': query,
        'limit': 5,
        'department': 'CS'
    }
    response = requests.post(f'{BASE_URL}/files/search', headers=headers, json=search_data)
    
    if response.status_code == 200:
        results = response.json()
        total = results.get('total', 0)
        if total > 0:
            print(f'✅ "{query}" → Found {total} results')
            for r in results.get('results', []):
                print(f'      - {r.get("title")} (Score: {r.get("score", 0):.4f})')
        else:
            print(f'❌ "{query}" → No results found')
    else:
        print(f'❌ Search failed: {response.text}')

print('\n' + '=' * 60)
print('Test complete!')