"""
Test search functionality
"""

import requests

TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MTUsImVtYWlsIjoiYWRtaW5AZWR1bWF0cml4LmNvbSIsInJvbGUiOiJhZG1pbiIsImV4cCI6MTc4Njk3MjU4OX0.9z2xIK3z3laeBktglbTOCqNemdnerrbIah_75WBqBDQ'
BASE_URL = 'http://localhost:8000'
headers = {'Authorization': f'Bearer {TOKEN}'}

print('=' * 60)
print('Testing Search')
print('=' * 60)

search_data = {
    'query': 'artificial intelligence machine learning',
    'limit': 10,
    'department': 'CS'
}

print(f'\n🔍 Query: {search_data["query"]}')
response = requests.post(f'{BASE_URL}/files/search', headers=headers, json=search_data)

if response.status_code == 200:
    results = response.json()
    total = results.get('total', 0)
    print(f'Found {total} results')
    for r in results.get('results', []):
        print(f'   - {r.get("title")} (Score: {r.get("score", 0):.4f})')
        print(f'     File ID: {r.get("file_id")}')
        print(f'     Type: {r.get("file_type")}')
else:
    print(f'❌ Search failed: {response.text}')