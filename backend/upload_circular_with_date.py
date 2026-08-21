"""
Upload a circular with a file that contains a date
"""

import requests

BASE_URL = 'http://backend:8000'  # Use backend service name

# Login as lecturer
login = requests.post(
    f'{BASE_URL}/auth/login',
    data={'username': 'lecture1@gmail.com', 'password': '12345'}
)

if login.status_code != 200:
    print(f'❌ Login failed: {login.text}')
    exit()

token = login.json().get('access_token')
headers = {'Authorization': f'Bearer {token}'}

print('✅ Logged in as lecturer')

# Create a test file with a future date
test_content = """
This is a test circular with a future date.
The assignment is due on 2026-09-15.
Please submit before the deadline.
"""

with open('/tmp/test_date.txt', 'w') as f:
    f.write(test_content)

print('📤 Uploading circular with file...')

with open('/tmp/test_date.txt', 'rb') as f:
    files = {'file': ('test_date.txt', f, 'text/plain')}
    data = {
        'type': 'general',
        'title': 'Test Circular with Auto Date',
        'content': 'This circular has an auto-detected date.'
    }
    response = requests.post(
        f'{BASE_URL}/circulars/upload',
        headers=headers,
        files=files,
        data=data
    )

print(f'Status: {response.status_code}')

if response.status_code == 200:
    result = response.json()
    print('✅ Circular created!')
    print(f'   ID: {result.get("id")}')
    print(f'   Title: {result.get("title")}')
    print(f'   Due Date: {result.get("due_date")}')
    print(f'   File ID: {result.get("file_id")}')
    
    file_details = result.get('file_details')
    if file_details:
        print(f'   File: {file_details.get("filename")} ({file_details.get("file_size")} bytes)')
        print(f'   Download URL: {file_details.get("download_url")}')
    
    # Check if auto date was detected
    if result.get('due_date'):
        print(f'   📅 Due date set to: {result.get("due_date")}')
else:
    print(f'❌ Error: {response.text}')