"""
Test Placement System
"""

import requests

# Test login
print('=' * 60)
print('Testing Placement System')
print('=' * 60)

print('\n🔐 Logging in as Placement Officer...')
response = requests.post(
    'http://localhost:8000/auth/login',
    data={'username': 'placement@gmail.com', 'password': '12345'}
)

if response.status_code != 200:
    print(f'❌ Login failed: {response.text}')
    exit()

token = response.json().get('access_token')
headers = {'Authorization': f'Bearer {token}'}
print('✅ Login successful!')

# Test getting placement stats
print('\n📊 Getting placement stats...')
stats_response = requests.get('http://localhost:8000/placement/stats', headers=headers)

if stats_response.status_code == 200:
    stats = stats_response.json()
    print('✅ Stats retrieved:')
    print(f'   Total Companies: {stats.get("total_companies", 0)}')
    print(f'   Active Companies: {stats.get("active_companies", 0)}')
    print(f'   Total Jobs: {stats.get("total_jobs", 0)}')
    print(f'   Open Jobs: {stats.get("open_jobs", 0)}')
    print(f'   Total Applications: {stats.get("total_applications", 0)}')
    print(f'   Total Shortlists: {stats.get("total_shortlists", 0)}')
else:
    print(f'❌ Failed to get stats: {stats_response.text}')

# Create a company
print('\n🏢 Creating a company...')
company_data = {
    'name': 'Google',
    'description': 'Global technology company focused on AI and cloud computing',
    'website': 'https://google.com',
    'industry': 'Technology',
    'location': 'Bangalore, India',
    'contact_email': 'hr@google.com',
    'contact_phone': '+91 9876543210',
    'is_active': True
}

company_response = requests.post(
    'http://localhost:8000/placement/companies',
    headers=headers,
    json=company_data
)

if company_response.status_code == 200:
    company = company_response.json()
    print('✅ Company created!')
    print(f'   ID: {company.get("id")}')
    print(f'   Name: {company.get("name")}')
    print(f'   Industry: {company.get("industry")}')
    company_id = company.get('id')
else:
    print(f'❌ Failed to create company: {company_response.text}')
    company_id = 1

# Create a job posting
print('\n💼 Creating a job posting...')
job_data = {
    'company_id': company_id or 1,
    'title': 'Software Engineer Intern',
    'description': 'Work on cutting-edge AI and cloud technologies',
    'required_skills': ['Python', 'Java', 'Data Structures', 'Algorithms'],
    'experience_level': 'fresher',
    'cgpa_criteria': 7.5,
    'branch_eligibility': ['CSE', 'IT', 'ECE'],
    'location': 'Bangalore',
    'salary_range': '₹8-12 LPA',
    'status': 'open'
}

job_response = requests.post(
    'http://localhost:8000/placement/jobs',
    headers=headers,
    json=job_data
)

if job_response.status_code == 200:
    job = job_response.json()
    print('✅ Job posting created!')
    print(f'   ID: {job.get("id")}')
    print(f'   Title: {job.get("title")}')
    print(f'   Company: {job.get("company_name")}')
    job_id = job.get('id')
else:
    print(f'❌ Failed to create job: {job_response.text}')
    job_id = 1

# List companies
print('\n📋 Listing companies...')
companies_response = requests.get(
    'http://localhost:8000/placement/companies',
    headers=headers
)

if companies_response.status_code == 200:
    companies = companies_response.json()
    print(f'✅ Found {len(companies)} companies:')
    for c in companies[:5]:
        print(f'   - {c.get("name")} ({c.get("industry")})')
else:
    print(f'❌ Failed to list companies: {companies_response.text}')

# List jobs
print('\n📋 Listing jobs...')
jobs_response = requests.get(
    'http://localhost:8000/placement/jobs',
    headers=headers
)

if jobs_response.status_code == 200:
    jobs = jobs_response.json()
    print(f'✅ Found {len(jobs)} jobs:')
    for j in jobs[:5]:
        print(f'   - {j.get("title")} at {j.get("company_name")}')
else:
    print(f'❌ Failed to list jobs: {jobs_response.text}')

print('\n' + '=' * 60)
print('✅ Placement system test complete!')
print('=' * 60)