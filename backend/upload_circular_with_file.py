"""
Script to upload a circular with file attachment
"""

import requests
import os

# Login as lecturer
login = requests.post(
    'http://localhost:8000/auth/login',
    data={'username': 'lecture1@gmail.com', 'password': '12345'}
)

if login.status_code != 200:
    print(f'❌ Login failed: {login.text}')
    exit()

token = login.json().get('access_token')
headers = {'Authorization': f'Bearer {token}'}

print('✅ Logged in successfully')

# Create a test file
test_content = """This is a test circular with attachment.
Important information for all students.
Please review the attached document.
Date: 2026-08-16
Subject: Important Announcement
"""

with open('/tmp/student_circular.txt', 'w') as f:
    f.write(test_content)

print('📤 Uploading circular with file...')

with open('/tmp/student_circular.txt', 'rb') as f:
    files = {'file': ('student_circular.txt', f, 'text/plain')}
    data = {
        'type': 'general',
        'title': 'Important: Student Announcement',
        'content': 'Please see the attached file for important information.'
    }
    response = requests.post(
        'http://localhost:8000/circulars/upload',
        headers=headers,
        files=files,
        data=data
    )

print(f'Status: {response.status_code}')

if response.status_code == 200:
    result = response.json()
    print('✅ Circular created successfully!')
    print(f'   ID: {result.get("id")}')
    print(f'   Title: {result.get("title")}')
    print(f'   File ID: {result.get("file_id")}')
    print(f'   File Type: {result.get("file_type")}')
    
    file_details = result.get('file_details')
    if file_details:
        print(f'   File Name: {file_details.get("filename")}')
        print(f'   File Size: {file_details.get("file_size")} bytes')
        print(f'   Download URL: {file_details.get("download_url")}')
    else:
        print('   ⚠️ No file details found - file may not be attached')
else:
    print(f'❌ Error: {response.text}')