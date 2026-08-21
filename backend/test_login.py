"""
Test Placement Officer Login
"""

import requests

print('=' * 60)
print('Testing Placement Officer Login')
print('=' * 60)

print('\n🔐 Logging in...')
response = requests.post(
    'http://localhost:8000/auth/login',
    data={'username': 'placement@gmail.com', 'password': '12345'},
    timeout=10
)

print(f'Status: {response.status_code}')

if response.status_code == 200:
    data = response.json()
    user = data.get('user', {})
    print('✅ Login successful!')
    print(f'   User: {user.get("email")}')
    print(f'   Role: {user.get("role")}')
    print(f'   Name: {user.get("name")}')
    
    # Test placement API
    token = data.get('access_token')
    headers = {'Authorization': f'Bearer {token}'}
    
    print('\n📊 Testing placement stats...')
    stats_response = requests.get(
        'http://localhost:8000/placement/stats',
        headers=headers,
        timeout=10
    )
    
    print(f'Stats endpoint: {stats_response.status_code}')
    if stats_response.status_code == 200:
        stats = stats_response.json()
        print('✅ Stats retrieved!')
        print(f'   Total Companies: {stats.get("total_companies", 0)}')
        print(f'   Total Jobs: {stats.get("total_jobs", 0)}')
    else:
        print(f'❌ Error: {stats_response.text}')
else:
    print(f'❌ Login failed: {response.text}')

print('\n' + '=' * 60)