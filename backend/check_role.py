"""
Check the role returned from login
"""

import requests

response = requests.post(
    'http://localhost:8000/auth/login',
    data={'username': 'placement@gmail.com', 'password': '12345'}
)

if response.status_code == 200:
    data = response.json()
    user = data.get('user', {})
    print('=' * 60)
    print('User Info from Login:')
    print('=' * 60)
    print(f'Email: {user.get("email")}')
    print(f'Name: {user.get("name")}')
    print(f'Role: {user.get("role")}')
    print(f'Role Type: {type(user.get("role"))}')
    print(f'Department: {user.get("department")}')
    print(f'Is Active: {user.get("is_active")}')
    print('=' * 60)
    
    # Check if role matches placement officer
    role = user.get("role")
    if role == 'placement_officer':
        print('✅ Role matches "placement_officer"')
    elif role == 'PLACEMENT_OFFICER':
        print('✅ Role matches "PLACEMENT_OFFICER"')
    else:
        print(f'⚠️ Role is: "{role}" - not matching expected')
else:
    print(f'❌ Login failed: {response.text}')