"""
Test search API without department filter
"""

import requests

TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MTUsImVtYWlsIjoiYWRtaW5AZWR1bWF0cml4LmNvbSIsInJvbGUiOiJhZG1pbiIsImV4cCI6MTc4Njk3MjU4OX0.9z2xIK3z3laeBktglbTOCqNemdnerrbIah_75WBqBDQ'
BASE_URL = 'http://localhost:8000'
headers = {'Authorization': f'Bearer {TOKEN}'}

print('=' * 60)
print('Testing Search API (No Department Filter)')
print('=' * 60)

search_data = {
    'query': 'test document',
    'limit': 10
}

print(f'\n🔍 Query: {search_data["query"]}')
response = requests.post(f'{BASE_URL}/files/search', headers=headers, json=search_data)

if response.status_code == 200:
    results = response.json()
    total = results.get('total', 0)
    print(f'Found {total} results:')
    for r in results.get('results', []):
        title = r.get('title', 'Unknown')
        score = r.get('score', 0)
        file_type = r.get('file_type', 'Unknown')
        department = r.get('department', 'Unknown')
        file_id = r.get('file_id', 'Unknown')
        print(f'   - {title} (Score: {score:.4f})')
        print(f'     Department: {department}')
        print(f'     Type: {file_type}')
        print(f'     File ID: {file_id}')
else:
    print(f'❌ Search failed: {response.text}')
    print(f'Status: {response.status_code}')