# Resume Parser Evaluation Report (Fixed)

**Date:** 2026-11-03 19:23:30
**Fix Applied:** BUG-001 - Removed vacuous truth, using real DOCX files

## Overall Metrics

- **Total Resumes:** 5
- **Successful Parses:** 5
- **Failed Parses:** 0
- **Parser Unavailable:** 0
- **Total Fields Evaluated:** 55
- **Correct Fields:** 41
- **Field Accuracy:** 74.55%
- **Average Overall Score:** 68.68%
- **Pass Rate (>=70%):** 80.00%

## Per-Field Accuracy

| Field | Correct | Total | Accuracy |
|-------|---------|-------|----------|
| name | 5 | 5 | 100.00% |
| email | 5 | 5 | 100.00% |
| phone | 5 | 5 | 100.00% |
| cgpa | 5 | 5 | 100.00% |
| projects | 5 | 5 | 100.00% |
| skills | 4 | 5 | 80.00% |
| companies | 4 | 5 | 80.00% |
| certifications | 4 | 5 | 80.00% |
| location | 4 | 5 | 80.00% |
| education | 0 | 5 | 0.00% |
| experience | 0 | 5 | 0.00% |

## Detailed Results

### resume_001_john_smith.docx

- Status: SUCCESS
- Success: True
- Fields: 9/11
- Pass Rate: 81.82%
- Overall Score: 0.73

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| name | [PASS] | 1.00 | JOHN SMITH | John Smith |
| email | [PASS] | 1.00 | john.smith@example.com | john.smith@example.com |
| phone | [PASS] | 1.00 | +91-9876543210 | +91-9876543210 |
| cgpa | [PASS] | 0.95 | 8.5 | 8.5 |
| skills | [PASS] | 0.60 | ['Python', 'Java', 'SQL', 'Node', 'Machine Learnin | ['Python', 'Java', 'C++', 'SQL', 'TensorFlow', 'Pa |
| education | [FAIL] | 0.00 | None | ['B.Tech Computer Science'] |
| companies | [PASS] | 1.00 | ['Google'] | ['Google'] |
| experience | [FAIL] | 0.00 | ['Software Intern'] | [{'title': 'Software Intern', 'company': 'Google', |
| projects | [PASS] | 0.50 | ['Chat Application'] | ['Recommendation System', 'Chat Application'] |
| certifications | [PASS] | 1.00 | ['AWS Cloud Practitioner'] | ['AWS Cloud Practitioner'] |
| location | [PASS] | 1.00 | Bangalore, India | Bangalore, India |

### resume_002_priya_sharma.docx

- Status: SUCCESS
- Success: True
- Fields: 8/11
- Pass Rate: 72.73%
- Overall Score: 0.72

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| name | [PASS] | 1.00 | PRIYA SHARMA | Priya Sharma |
| email | [PASS] | 1.00 | priya.sharma@gmail.com | priya.sharma@gmail.com |
| phone | [PASS] | 1.00 | 9876543210 | 9876543210 |
| cgpa | [PASS] | 1.00 | None | None |
| skills | [FAIL] | 0.45 | ['React', 'Node', 'Express', 'GIT', 'Docker', 'AWS | ['React.js', 'Node.js', 'Express', 'MongoDB', 'Red |
| education | [FAIL] | 0.00 | None | ['B.Tech Information Technology'] |
| companies | [PASS] | 1.00 | ['Flipkart'] | ['Flipkart'] |
| experience | [FAIL] | 0.00 | ['Frontend Developer'] | [{'title': 'Frontend Developer', 'company': 'Flipk |
| projects | [PASS] | 0.50 | ['Portfolio Website'] | ['E-commerce Platform', 'Portfolio Website'] |
| certifications | [PASS] | 1.00 | ['Meta Frontend Developer Certificate'] | ['Meta Frontend Developer Certificate'] |
| location | [PASS] | 1.00 | Pune, Maharashtra | Pune, Maharashtra |

### resume_003_rahul_verma.docx

- Status: SUCCESS
- Success: True
- Fields: 7/11
- Pass Rate: 63.64%
- Overall Score: 0.55

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| name | [PASS] | 1.00 | RAHUL VERMA | Rahul Verma |
| email | [PASS] | 1.00 | rahul.v@college.edu.in | rahul.v@college.edu.in |
| phone | [PASS] | 1.00 | +91-8765432109 | +91-8765432109 |
| cgpa | [PASS] | 0.95 | 9.1 | 9.1 |
| skills | [PASS] | 0.56 | ['Python', 'Java', 'Javascript', 'AI', 'GIT', 'Git | ['C', 'C++', 'Python', 'Java', 'JavaScript', 'Data |
| education | [FAIL] | 0.00 | None | ['B.Tech Computer Science and Engineering'] |
| companies | [FAIL] | 0.00 | None | ['Amazon'] |
| experience | [FAIL] | 0.00 | None | [{'title': 'SDE-1', 'company': 'Amazon', 'dates':  |
| projects | [PASS] | 0.50 | ['Pathfinding Visualizer'] | ['Online Judge Platform', 'Pathfinding Visualizer' |
| certifications | [PASS] | 1.00 | None | None |
| location | [FAIL] | 0.00 | None | Karnataka |

### resume_004_ananya_patel.docx

- Status: SUCCESS
- Success: True
- Fields: 9/11
- Pass Rate: 81.82%
- Overall Score: 0.74

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| name | [PASS] | 1.00 | ANANYA PATEL | Ananya Patel |
| email | [PASS] | 1.00 | ananya.p@email.com | ananya.p@email.com |
| phone | [PASS] | 1.00 | 9876543210 | 9876543210 |
| cgpa | [PASS] | 0.95 | 8.8 | 8.8 |
| skills | [PASS] | 0.55 | ['Python', 'Docker', 'Kubernetes', 'AWS', 'Bash',  | ['AWS', 'Docker', 'Kubernetes', 'Jenkins', 'Terraf |
| education | [FAIL] | 0.00 | None | ['B.Tech Computer Science'] |
| companies | [PASS] | 1.00 | ['Microsoft'] | ['Microsoft'] |
| experience | [FAIL] | 0.00 | ['DevOps Intern'] | [{'title': 'DevOps Intern', 'company': 'Microsoft' |
| projects | [PASS] | 1.00 | ['Serverless URL Shortener', 'K8s Dashboard'] | ['Serverless URL Shortener', 'K8s Dashboard'] |
| certifications | [PASS] | 0.67 | ['AWS Certified Cloud Practitioner', 'Docker Certi | ['AWS Certified Cloud Practitioner', 'Docker Certi |
| location | [PASS] | 1.00 | Vellore, Tamil Nadu | Vellore, Tamil Nadu |

### resume_005_arjun_reddy.docx

- Status: SUCCESS
- Success: True
- Fields: 8/11
- Pass Rate: 72.73%
- Overall Score: 0.69

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| name | [PASS] | 1.00 | ARJUN REDDY | Arjun Reddy |
| email | [PASS] | 1.00 | arjun.r@institution.ac.in | arjun.r@institution.ac.in |
| phone | [PASS] | 1.00 | None | None |
| cgpa | [PASS] | 1.00 | None | None |
| skills | [PASS] | 0.60 | ['Python', 'GIT', 'Docker', 'AWS', 'Mongodb', 'Pos | ['Ruby on Rails', 'PostgreSQL', 'Redis', 'GraphQL' |
| education | [FAIL] | 0.00 | None | ['B.Tech Computer Science'] |
| companies | [PASS] | 1.00 | ['Zomato'] | ['Zomato'] |
| experience | [FAIL] | 0.00 | ['Backend Engineer'] | [{'title': 'Backend Engineer', 'company': 'Zomato' |
| projects | [PASS] | 1.00 | ['Restaurant Management System'] | ['Restaurant Management System'] |
| certifications | [FAIL] | 0.00 | ['MongoDB for Python'] | ['MongoDB for Python Developers'] |
| location | [PASS] | 1.00 | Hyderabad, Telangana | Hyderabad, Telangana |

