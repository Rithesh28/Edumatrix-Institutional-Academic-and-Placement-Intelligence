# JD Parser Evaluation Report (ISSUE-003 Fixed)

**Date:** 2026-11-03 21:06:12
**Fix Applied:** ISSUE-003 - Corrected field name mapping

## Overall Metrics

### Test-Case Pass Rate

- **Total Cases:** 10
- **Pass (>=70%):** 0
- **Partial (50-70%):** 3
- **Fail (<50%):** 7
- **Pass Rate:** 0.00%

### Field-Level Accuracy

- **Total Fields Evaluated:** 120
- **Correct Fields:** 49
- **Field Accuracy:** 40.83%
- **Average Overall Score:** 40.85%

## Field Name Mapping (ISSUE-003 Fix)

| Check Field | Parser Output Field |
|-------------|---------------------|
| company | company_name |
| job_title | title |
| skills | required_skills |
| experience_years | experience_level |
| academic_requirements | degree_eligibility |
| cgpa_requirement | cgpa_criteria |
| location | location |
| compensation | salary_range |
| selection_rounds | selection_rounds |
| date | application_deadline |
| has_bond | bond_details |
| qualification_required | branch_eligibility |

## Per-Field Accuracy

| Field | Correct | Total | Accuracy |
|-------|---------|-------|----------|
| compensation | 10 | 10 | 100.00% |
| company | 9 | 10 | 90.00% |
| job_title | 9 | 10 | 90.00% |
| date | 9 | 10 | 90.00% |
| location | 8 | 10 | 80.00% |
| skills | 4 | 10 | 40.00% |
| experience_years | 0 | 10 | 0.00% |
| academic_requirements | 0 | 10 | 0.00% |
| cgpa_requirement | 0 | 10 | 0.00% |
| selection_rounds | 0 | 10 | 0.00% |
| has_bond | 0 | 10 | 0.00% |
| qualification_required | 0 | 10 | 0.00% |

## Detailed Results

### TC_JD_001

- Status: FAIL
- Fields: 5/12
- Score: 0.42
- Category: Service Based JD

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| company | [PASS] | 1.00 | TCS | TCS |
| job_title | [PASS] | 1.00 | Software Trainee | Software Trainee |
| skills | [FAIL] | 0.00 | [] | ['B.Tech', 'Online Assessment', 'Technic |
| experience_years | [FAIL] | 0.00 | None | None |
| academic_requirements | [FAIL] | 0.00 | ['B.Tech'] | None |
| cgpa_requirement | [FAIL] | 0.00 | None | None |
| location | [PASS] | 1.00 | Pune | Pune |
| compensation | [PASS] | 1.00 | 3.36 LPA | 3.36 LPA |
| selection_rounds | [FAIL] | 0.00 | ['Online Assessment Technical Interview  | None |
| date | [PASS] | 1.00 | 15th March 2024 | 15th March 2024 |
| has_bond | [FAIL] | 0.00 | None | None |
| qualification_required | [FAIL] | 0.00 | ['CSE', 'ECE', 'IT'] | None |

### TC_JD_002

- Status: PARTIAL
- Fields: 6/12
- Score: 0.50
- Category: Product Company JD

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| company | [PASS] | 1.00 | Amazon | Amazon |
| job_title | [PASS] | 1.00 | Senior Software Engineer | Senior Software Engineer |
| skills | [PASS] | 0.50 | ['Python', 'AWS', 'DSA', 'System Design' | ['Python', 'AWS', 'Bond Yes'] |
| experience_years | [FAIL] | 0.00 | 2+ years experience | None |
| academic_requirements | [FAIL] | 0.00 | ['B.Tech'] | None |
| cgpa_requirement | [FAIL] | 0.00 | None | None |
| location | [PASS] | 1.00 | Hyderabad | Hyderabad |
| compensation | [PASS] | 1.00 | 25-35 LPA | 25-35 LPA |
| selection_rounds | [FAIL] | 0.00 | [] | None |
| date | [PASS] | 1.00 | 30th Jan 2024 | 30th Jan 2024 |
| has_bond | [FAIL] | 0.00 | Bond 2 years Last Date 30th Jan 2024 | None |
| qualification_required | [FAIL] | 0.00 | [] | None |

### TC_JD_003

- Status: FAIL
- Fields: 5/12
- Score: 0.42
- Category: Infosys JD

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| company | [PASS] | 1.00 | Infosys | Infosys |
| job_title | [PASS] | 1.00 | Python Developer | Python Developer |
| skills | [FAIL] | 0.00 | [] | ['Python', 'Django'] |
| experience_years | [FAIL] | 0.00 | None | None |
| academic_requirements | [FAIL] | 0.00 | [] | None |
| cgpa_requirement | [FAIL] | 0.00 | None | None |
| location | [PASS] | 1.00 | Work from Home | Work from Home |
| compensation | [PASS] | 1.00 | 3.5 LPA | 3.5 LPA |
| selection_rounds | [FAIL] | 0.00 | ['OA Technical HR'] | None |
| date | [PASS] | 1.00 | 20th February 2024 | 20th February 2024 |
| has_bond | [FAIL] | 0.00 | None | None |
| qualification_required | [FAIL] | 0.00 | [] | None |

### TC_JD_004

- Status: FAIL
- Fields: 5/12
- Score: 0.42
- Category: Wipro JD

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| company | [PASS] | 1.00 | Wipro | Wipro |
| job_title | [PASS] | 1.00 | Systems Engineer | Systems Engineer |
| skills | [FAIL] | 0.00 | [] | ['Aptitude Test', 'Technical', 'Group Di |
| experience_years | [FAIL] | 0.00 | None | None |
| academic_requirements | [FAIL] | 0.00 | [] | None |
| cgpa_requirement | [FAIL] | 0.00 | None | None |
| location | [PASS] | 1.00 | Mumbai | Mumbai |
| compensation | [PASS] | 1.00 | 3.0 LPA | 3.0 LPA |
| selection_rounds | [FAIL] | 0.00 | [] | None |
| date | [PASS] | 1.00 | 10th March 2024 | 10th March 2024 |
| has_bond | [FAIL] | 0.00 | None | None |
| qualification_required | [FAIL] | 0.00 | [] | None |

### TC_JD_005

- Status: FAIL
- Fields: 4/12
- Score: 0.33
- Category: Big 4 JD

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| company | [PASS] | 1.00 | Deloitte | Deloitte |
| job_title | [PASS] | 0.80 | Analyst Technology | Analyst |
| skills | [FAIL] | 0.25 | ['Python', 'Java', 'C'] | ['Technology', 'B.Tech', 'M.Tech', 'MCA' |
| experience_years | [FAIL] | 0.00 | None | None |
| academic_requirements | [FAIL] | 0.00 | ['B.Tech', 'M.Tech', 'MCA'] | None |
| cgpa_requirement | [FAIL] | 0.00 | 7.5 | None |
| location | [FAIL] | 0.00 | None | None |
| compensation | [PASS] | 0.80 | n 8-10 LPA | 8-10 LPA |
| selection_rounds | [FAIL] | 0.00 | ['Coding Round Technical Interview Manag | None |
| date | [PASS] | 1.00 | 5th April 2024 | 5th April 2024 |
| has_bond | [FAIL] | 0.00 | None | None |
| qualification_required | [FAIL] | 0.00 | [] | None |

### TC_JD_006

- Status: PARTIAL
- Fields: 6/12
- Score: 0.50
- Category: Data Science JD

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| company | [PASS] | 1.00 | Flipkart | Flipkart |
| job_title | [PASS] | 1.00 | DATA SCIENTIST | Data Scientist |
| skills | [PASS] | 0.71 | ['Python', 'R', 'SQL', 'Machine Learning | ['Python', 'R', 'SQL', 'Machine Learning |
| experience_years | [FAIL] | 0.00 | 1-3 years | None |
| academic_requirements | [FAIL] | 0.00 | ['B.Tech', 'M.Tech'] | None |
| cgpa_requirement | [FAIL] | 0.00 | None | None |
| location | [PASS] | 1.00 | Bangalore | Bangalore |
| compensation | [PASS] | 1.00 | 12-18 LPA | 12-18 LPA |
| selection_rounds | [FAIL] | 0.00 | [] | None |
| date | [PASS] | 1.00 | 25th March 2024 | 25th March 2024 |
| has_bond | [FAIL] | 0.00 | None | None |
| qualification_required | [FAIL] | 0.00 | ['AIDS', 'CSE'] | None |

### TC_JD_007

- Status: FAIL
- Fields: 5/12
- Score: 0.42
- Category: Capgemini JD

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| company | [PASS] | 1.00 | Capgemini | Capgemini |
| job_title | [PASS] | 1.00 | Programmer Trainee | Programmer Trainee |
| skills | [FAIL] | 0.00 | [] | ['Written Test', 'Technical', 'HR'] |
| experience_years | [FAIL] | 0.00 | None | None |
| academic_requirements | [FAIL] | 0.00 | ['B.E', 'B.Tech'] | None |
| cgpa_requirement | [FAIL] | 0.00 | None | None |
| location | [PASS] | 1.00 | Chennai | Chennai |
| compensation | [PASS] | 1.00 | 3.36 LPA | 3.36 LPA |
| selection_rounds | [FAIL] | 0.00 | ['Written Test Technical HR'] | None |
| date | [PASS] | 0.80 | 18th January 2024 Time 10 AM | 18th January 2024 |
| has_bond | [FAIL] | 0.00 | None | None |
| qualification_required | [FAIL] | 0.00 | [] | None |

### TC_JD_008

- Status: PARTIAL
- Fields: 6/12
- Score: 0.50
- Category: Adobe JD

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| company | [PASS] | 1.00 | Adobe | Adobe |
| job_title | [PASS] | 0.80 | SOFTWARE ENGINEER FRONTEND | Software Engineer |
| skills | [PASS] | 0.75 | ['JavaScript', 'TypeScript', 'React', 'R | ['Frontend', 'JavaScript', 'React', 'Typ |
| experience_years | [FAIL] | 0.00 | None | None |
| academic_requirements | [FAIL] | 0.00 | ['B.Tech'] | None |
| cgpa_requirement | [FAIL] | 0.00 | None | None |
| location | [PASS] | 1.00 | Noida | Noida |
| compensation | [PASS] | 1.00 | 15-22 LPA | 15-22 LPA |
| selection_rounds | [FAIL] | 0.00 | [] | None |
| date | [PASS] | 1.00 | 28th Feb 2024 | 28th Feb 2024 |
| has_bond | [FAIL] | 0.00 | None | None |
| qualification_required | [FAIL] | 0.00 | [] | None |

### TC_JD_009

- Status: FAIL
- Fields: 2/12
- Score: 0.17
- Category: Mega Drive JD

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| company | [FAIL] | 0.00 | Accenture | Wipro |
| job_title | [FAIL] | 0.00 | throughout No backlogs | None |
| skills | [FAIL] | 0.00 | [] | None |
| experience_years | [FAIL] | 0.00 | None | None |
| academic_requirements | [FAIL] | 0.00 | [] | None |
| cgpa_requirement | [FAIL] | 0.00 | None | None |
| location | [FAIL] | 0.00 | None | None |
| compensation | [PASS] | 0.80 | 3.0 to 6.0 LPA | 6.0 LPA |
| selection_rounds | [FAIL] | 0.00 | ['varies by company'] | None |
| date | [PASS] | 0.80 | 12th March 2024 Venue Main Auditorium | 12th March 2024 |
| has_bond | [FAIL] | 0.00 | None | None |
| qualification_required | [FAIL] | 0.00 | [] | None |

### TC_JD_010

- Status: FAIL
- Fields: 5/12
- Score: 0.42
- Category: Google Internship

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| company | [PASS] | 1.00 | Google | Google |
| job_title | [PASS] | 1.00 | SWE Intern | SWE Intern |
| skills | [PASS] | 0.60 | ['Python', 'Java', 'C', 'Data Structures | ['C++', 'Java', 'Python', 'DSA'] |
| experience_years | [FAIL] | 0.00 | None | None |
| academic_requirements | [FAIL] | 0.00 | ['B.Tech'] | None |
| cgpa_requirement | [FAIL] | 0.00 | 8.0 | CGPA 8.0 |
| location | [PASS] | 1.00 | Bangalore | Bangalore |
| compensation | [PASS] | 1.00 | 1 LPA | 1 LPA |
| selection_rounds | [FAIL] | 0.00 | [] | None |
| date | [FAIL] | 0.00 | None | 5th April 2024 |
| has_bond | [FAIL] | 0.00 | None | None |
| qualification_required | [FAIL] | 0.00 | [] | None |

