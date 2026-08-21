"""
Test search API
"""

import requests

TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MTUsImVtYWlsIjoiYWRtaW5AZWR1bWF0cml4LmNvbSIsInJvbGUiOiJhZG1pbiIsImV4cCI6MTc4Njk3MjU4OX0.9z2xIK3z3laeBktglbTOCqNemdnerrbIah_75WBqBDQ'
BASE_URL = 'http://localhost:8000'
headers = {'Authorization': f'Bearer {TOKEN}'}

print('=' * 60)
print('Testing Search API')
print('=' * 60)

# Test without department filter
print('\n🔍 Searching without department filter...')
search_data = {
    'query': 'test',
    'limit': 10
}
response = requests.post(f'{BASE_URL}/files/search', headers=headers, json=search_data)

if response.status_code == 200:
    results = response.json()
    total = results.get('total', 0)
    print(f'Found {total} results')
    for r in results.get('results', []):
        title = r.get('title', 'Unknown')
        score = r.get('score', 0)
        dept = r.get('department', 'Unknown')
        print(f'   - {title} (Score: {score:.4f}, Department: {dept})')
else:
    print(f'❌ Error: {response.text}')

# Test with department filter
print('\n🔍 Searching with department filter (CS)...')
search_data = {
    'query': 'test',
    'limit': 10,
    'department': 'CS'
}
response = requests.post(f'{BASE_URL}/files/search', headers=headers, json=search_data)

if response.status_code == 200:
    results = response.json()
    total = results.get('total', 0)
    print(f'Found {total} results')
    for r in results.get('results', []):
        title = r.get('title', 'Unknown')
        score = r.get('score', 0)
        dept = r.get('department', 'Unknown')
        print(f'   - {title} (Score: {score:.4f}, Department: {dept})')
else:
    print(f'❌ Error: {response.text}')