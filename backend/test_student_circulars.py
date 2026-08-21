"""
Test student circulars with file attachments
"""

import requests

# Login as student
login = requests.post(
    'http://localhost:8000/auth/login',
    data={'username': 'adi01@gmail.com', 'password': '54321'}
)

if login.status_code != 200:
    print(f'❌ Login failed: {login.text}')
    exit()

token = login.json().get('access_token')
headers = {'Authorization': f'Bearer {token}'}

print('✅ Logged in as student')

# Fetch circulars
response = requests.get('http://localhost:8000/circulars/', headers=headers)

if response.status_code != 200:
    print(f'❌ Error fetching circulars: {response.text}')
    exit()

circulars = response.json()
print(f'\n📢 Found {len(circulars)} circulars for student:')
print('=' * 60)

for c in circulars:
    print(f'\n📌 Title: {c.get("title")}')
    print(f'   Type: {c.get("type")}')
    print(f'   Content: {c.get("content")[:100]}...')
    print(f'   File ID: {c.get("file_id")}')
    
    file_details = c.get('file_details')
    if file_details:
        print(f'   📎 File Name: {file_details.get("filename")}')
        print(f'   📏 File Size: {file_details.get("file_size")} bytes')
        print(f'   🔗 Download URL: {file_details.get("download_url")}')
        
        # Test download
        download_response = requests.get(
            f'http://localhost:8000{file_details.get("download_url")}',
            headers=headers
        )
        if download_response.status_code == 200:
            print(f'   ✅ Download successful! Size: {len(download_response.content)} bytes')
        else:
            print(f'   ❌ Download failed: {download_response.status_code}')
    else:
        print('   ⚠️ No file attached')

print('\n' + '=' * 60)