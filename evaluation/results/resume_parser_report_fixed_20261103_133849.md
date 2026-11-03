# Resume Parser Evaluation Report (Fixed)

**Date:** 2026-11-03 13:38:49
**Fix Applied:** BUG-001 - Removed vacuous truth, using real DOCX files

## Overall Metrics

- **Total Resumes:** 5
- **Successful Parses:** 5
- **Failed Parses:** 0
- **Parser Unavailable:** 0
- **Total Fields Evaluated:** 55
- **Correct Fields:** 24
- **Field Accuracy:** 43.64%
- **Average Overall Score:** 41.10%
- **Pass Rate (>=70%):** 0.00%

## Per-Field Accuracy

| Field | Correct | Total | Accuracy |
|-------|---------|-------|----------|
| name | 5 | 5 | 100.00% |
| email | 5 | 5 | 100.00% |
| cgpa | 5 | 5 | 100.00% |
| phone | 4 | 5 | 80.00% |
| skills | 4 | 5 | 80.00% |
| certifications | 1 | 5 | 20.00% |
| education | 0 | 5 | 0.00% |
| companies | 0 | 5 | 0.00% |
| experience | 0 | 5 | 0.00% |
| projects | 0 | 5 | 0.00% |
| location | 0 | 5 | 0.00% |

## Detailed Results

### resume_001_john_smith.docx

- Status: SUCCESS
- Success: True
- Fields: 5/11
- Pass Rate: 45.45%
- Overall Score: 0.41

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| name | [PASS] | 1.00 | JOHN SMITH | John Smith |
| email | [PASS] | 1.00 | john.smith@example.com | john.smith@example.com |
| phone | [PASS] | 1.00 | +91-9876543210 | +91-9876543210 |
| cgpa | [PASS] | 0.95 | 8.5 | 8.5 |
| skills | [PASS] | 0.60 | ['Python', 'Java', 'SQL', 'Node', 'Machine Learnin | ['Python', 'Java', 'C++', 'SQL', 'TensorFlow', 'Pa |
| education | [FAIL] | 0.00 | ['B.Tech (Computer Science)', 'me (Computer Scienc | ['B.Tech Computer Science'] |
| companies | [FAIL] | 0.00 | None | ['Google'] |
| experience | [FAIL] | 0.00 | None | [{'title': 'Software Intern', 'company': 'Google', |
| projects | [FAIL] | 0.00 | [{'name': 'Recommendation System: Built a content- | ['Recommendation System', 'Chat Application'] |
| certifications | [FAIL] | 0.00 | [{'name': 'AWS Certification'}] | ['AWS Cloud Practitioner'] |
| location | [FAIL] | 0.00 | None | Bangalore, India |

### resume_002_priya_sharma.docx

- Status: SUCCESS
- Success: True
- Fields: 4/11
- Pass Rate: 36.36%
- Overall Score: 0.40

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| name | [PASS] | 1.00 | PRIYA SHARMA | Priya Sharma |
| email | [PASS] | 1.00 | priya.sharma@gmail.com | priya.sharma@gmail.com |
| phone | [PASS] | 1.00 | 9876543210 | 9876543210 |
| cgpa | [PASS] | 1.00 | None | None |
| skills | [FAIL] | 0.45 | ['React', 'Node', 'Express', 'GIT', 'Docker', 'AWS | ['React.js', 'Node.js', 'Express', 'MongoDB', 'Red |
| education | [FAIL] | 0.00 | ['B.Tech (Information Technology)', 'me (Informati | ['B.Tech Information Technology'] |
| companies | [FAIL] | 0.00 | None | ['Flipkart'] |
| experience | [FAIL] | 0.00 | ['Developer Role'] | [{'title': 'Frontend Developer', 'company': 'Flipk |
| projects | [FAIL] | 0.00 | [{'name': 'E-commerce Platform: Full-stack applica | ['E-commerce Platform', 'Portfolio Website'] |
| certifications | [FAIL] | 0.00 | [{'name': 'Coursera Certification'}, {'name': 'AWS | ['Meta Frontend Developer Certificate'] |
| location | [FAIL] | 0.00 | None | Pune, Maharashtra |

### resume_003_rahul_verma.docx

- Status: SUCCESS
- Success: True
- Fields: 6/11
- Pass Rate: 54.55%
- Overall Score: 0.50

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| name | [PASS] | 1.00 | RAHUL VERMA | Rahul Verma |
| email | [PASS] | 1.00 | rahul.v@college.edu.in | rahul.v@college.edu.in |
| phone | [PASS] | 1.00 | +91-8765432109 | +91-8765432109 |
| cgpa | [PASS] | 0.95 | 9.1 | 9.1 |
| skills | [PASS] | 0.56 | ['Python', 'Java', 'Javascript', 'AI', 'GIT', 'Git | ['C', 'C++', 'Python', 'Java', 'JavaScript', 'Data |
| education | [FAIL] | 0.00 | ['B.Tech (Computer Science)', 'ME (Computer Scienc | ['B.Tech Computer Science and Engineering'] |
| companies | [FAIL] | 0.00 | None | ['Amazon'] |
| experience | [FAIL] | 0.00 | None | [{'title': 'SDE-1', 'company': 'Amazon', 'dates':  |
| projects | [FAIL] | 0.00 | [{'name': 'Online Judge Platform: Built a competit | ['Online Judge Platform', 'Pathfinding Visualizer' |
| certifications | [PASS] | 1.00 | None | None |
| location | [FAIL] | 0.00 | None | Karnataka |

### resume_004_ananya_patel.docx

- Status: SUCCESS
- Success: True
- Fields: 5/11
- Pass Rate: 45.45%
- Overall Score: 0.41

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| name | [PASS] | 1.00 | ANANYA PATEL | Ananya Patel |
| email | [PASS] | 1.00 | ananya.p@email.com | ananya.p@email.com |
| phone | [PASS] | 1.00 | 9876543210 | 9876543210 |
| cgpa | [PASS] | 0.95 | 8.8 | 8.8 |
| skills | [PASS] | 0.55 | ['Python', 'Docker', 'Kubernetes', 'AWS', 'Bash',  | ['AWS', 'Docker', 'Kubernetes', 'Jenkins', 'Terraf |
| education | [FAIL] | 0.00 | ['B.Tech (Computer Science)', 'me (Computer Scienc | ['B.Tech Computer Science'] |
| companies | [FAIL] | 0.00 | None | ['Microsoft'] |
| experience | [FAIL] | 0.00 | ['Intern Role'] | [{'title': 'DevOps Intern', 'company': 'Microsoft' |
| projects | [FAIL] | 0.00 | [{'name': 'Serverless URL Shortener: Built using A | ['Serverless URL Shortener', 'K8s Dashboard'] |
| certifications | [FAIL] | 0.00 | [{'name': 'AWS Certification'}, {'name': 'Certifie | ['AWS Certified Cloud Practitioner', 'Docker Certi |
| location | [FAIL] | 0.00 | None | Vellore, Tamil Nadu |

### resume_005_arjun_reddy.docx

- Status: SUCCESS
- Success: True
- Fields: 4/11
- Pass Rate: 36.36%
- Overall Score: 0.33

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| name | [PASS] | 1.00 | ARJUN REDDY | Arjun Reddy |
| email | [PASS] | 1.00 | arjun.r@institution.ac.in | arjun.r@institution.ac.in |
| phone | [FAIL] | 0.00 | None | None |
| cgpa | [PASS] | 1.00 | None | None |
| skills | [PASS] | 0.60 | ['Python', 'GIT', 'Docker', 'AWS', 'Mongodb', 'Pos | ['Ruby on Rails', 'PostgreSQL', 'Redis', 'GraphQL' |
| education | [FAIL] | 0.00 | ['B.Tech (Computer Science)', 'me (Computer Scienc | ['B.Tech Computer Science'] |
| companies | [FAIL] | 0.00 | None | ['Zomato'] |
| experience | [FAIL] | 0.00 | ['Engineer Role'] | [{'title': 'Backend Engineer', 'company': 'Zomato' |
| projects | [FAIL] | 0.00 | [{'name': 'Restaurant Management System: Full-stac | ['Restaurant Management System'] |
| certifications | [FAIL] | 0.00 | [{'name': 'AWS Certification'}] | ['MongoDB for Python Developers'] |
| location | [FAIL] | 0.00 | None | Hyderabad, Telangana |

