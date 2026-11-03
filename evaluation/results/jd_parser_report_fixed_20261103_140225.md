# JD Parser Evaluation Report (ISSUE-003 Fixed)

**Date:** 2026-11-03 14:02:25
**Fix Applied:** ISSUE-003 - Corrected field name mapping

## Overall Metrics

### Test-Case Pass Rate

- **Total Cases:** 10
- **Pass (>=70%):** 0
- **Partial (50-70%):** 0
- **Fail (<50%):** 10
- **Pass Rate:** 0.00%

### Field-Level Accuracy

- **Total Fields Evaluated:** 120
- **Correct Fields:** 26
- **Field Accuracy:** 21.67%
- **Average Overall Score:** 21.66%

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
| location | 8 | 10 | 80.00% |
| skills | 4 | 10 | 40.00% |
| company | 3 | 10 | 30.00% |
| job_title | 1 | 10 | 10.00% |
| experience_years | 0 | 10 | 0.00% |
| academic_requirements | 0 | 10 | 0.00% |
| cgpa_requirement | 0 | 10 | 0.00% |
| selection_rounds | 0 | 10 | 0.00% |
| date | 0 | 10 | 0.00% |
| has_bond | 0 | 10 | 0.00% |
| qualification_required | 0 | 10 | 0.00% |

## Detailed Results

### TC_JD_001

- Status: FAIL
- Fields: 3/12
- Score: 0.25
- Category: Service Based JD

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| company | [PASS] | 0.80 | TCS ROLE | TCS |
| job_title | [FAIL] | 0.00 | None | Software Trainee |
| skills | [FAIL] | 0.00 | [] | ['B.Tech', 'Online Assessment', 'Technic |
| experience_years | [FAIL] | 0.00 | None | None |
| academic_requirements | [FAIL] | 0.00 | ['B.Tech'] | None |
| cgpa_requirement | [FAIL] | 0.00 | None | None |
| location | [PASS] | 0.80 | Pune REQUIREMENTS | Pune |
| compensation | [PASS] | 1.00 | 3.36 LPA | 3.36 LPA |
| selection_rounds | [FAIL] | 0.00 | [] | None |
| date | [FAIL] | 0.00 | 2024-03-15T00:00 | 15th March 2024 |
| has_bond | [FAIL] | 0.00 | None | None |
| qualification_required | [FAIL] | 0.00 | ['CSE', 'ECE', 'IT'] | None |

### TC_JD_002

- Status: FAIL
- Fields: 4/12
- Score: 0.33
- Category: Product Company JD

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| company | [PASS] | 0.80 | Amazon Location Hyderabad Eligibility B. | Amazon |
| job_title | [FAIL] | 0.00 | None | Senior Software Engineer |
| skills | [PASS] | 0.50 | ['Python', 'AWS', 'DSA', 'System Design' | ['Python', 'AWS', 'Bond Yes'] |
| experience_years | [FAIL] | 0.00 | 2+ years experience | None |
| academic_requirements | [FAIL] | 0.00 | ['B.Tech'] | None |
| cgpa_requirement | [FAIL] | 0.00 | None | None |
| location | [PASS] | 0.80 | Hyderabad Eligibility B | Hyderabad |
| compensation | [PASS] | 1.00 | 25-35 LPA | 25-35 LPA |
| selection_rounds | [FAIL] | 0.00 | [] | None |
| date | [FAIL] | 0.00 | None | 30th Jan 2024 |
| has_bond | [FAIL] | 0.00 | Bond 2 years Last Date 30th Jan 2024 | None |
| qualification_required | [FAIL] | 0.00 | [] | None |

### TC_JD_003

- Status: FAIL
- Fields: 2/12
- Score: 0.17
- Category: Infosys JD

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| company | [FAIL] | 0.00 | None | Infosys |
| job_title | [FAIL] | 0.00 | None | Python Developer |
| skills | [FAIL] | 0.00 | [] | ['Python', 'Django'] |
| experience_years | [FAIL] | 0.00 | None | None |
| academic_requirements | [FAIL] | 0.00 | [] | None |
| cgpa_requirement | [FAIL] | 0.00 | None | None |
| location | [PASS] | 0.80 | Work from Home Eligibility | Work from Home |
| compensation | [PASS] | 1.00 | 3.5 LPA | 3.5 LPA |
| selection_rounds | [FAIL] | 0.00 | [] | None |
| date | [FAIL] | 0.00 | None | 20th February 2024 |
| has_bond | [FAIL] | 0.00 | None | None |
| qualification_required | [FAIL] | 0.00 | [] | None |

### TC_JD_004

- Status: FAIL
- Fields: 2/12
- Score: 0.17
- Category: Wipro JD

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| company | [FAIL] | 0.00 | None | Wipro |
| job_title | [FAIL] | 0.00 | None | Systems Engineer |
| skills | [FAIL] | 0.00 | [] | ['Aptitude Test', 'Technical', 'Group Di |
| experience_years | [FAIL] | 0.00 | None | None |
| academic_requirements | [FAIL] | 0.00 | [] | None |
| cgpa_requirement | [FAIL] | 0.00 | None | None |
| location | [PASS] | 1.00 | Mumbai | Mumbai |
| compensation | [PASS] | 1.00 | 3.0 LPA | 3.0 LPA |
| selection_rounds | [FAIL] | 0.00 | [] | None |
| date | [FAIL] | 0.00 | None | 10th March 2024 |
| has_bond | [FAIL] | 0.00 | None | None |
| qualification_required | [FAIL] | 0.00 | [] | None |

### TC_JD_005

- Status: FAIL
- Fields: 1/12
- Score: 0.08
- Category: Big 4 JD

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| company | [FAIL] | 0.00 | None | Deloitte |
| job_title | [FAIL] | 0.00 | None | Analyst |
| skills | [FAIL] | 0.25 | ['Python', 'Java', 'C'] | ['Technology', 'B.Tech', 'M.Tech', 'MCA' |
| experience_years | [FAIL] | 0.00 | None | None |
| academic_requirements | [FAIL] | 0.00 | ['B.Tech', 'M.Tech', 'MCA'] | None |
| cgpa_requirement | [FAIL] | 0.00 | 7.5 | None |
| location | [FAIL] | 0.00 | None | None |
| compensation | [PASS] | 0.80 | n 8-10 LPA | 8-10 LPA |
| selection_rounds | [FAIL] | 0.00 | [] | None |
| date | [FAIL] | 0.00 | 2024-04-05T00:00 | 5th April 2024 |
| has_bond | [FAIL] | 0.00 | None | None |
| qualification_required | [FAIL] | 0.00 | [] | None |

### TC_JD_006

- Status: FAIL
- Fields: 3/12
- Score: 0.25
- Category: Data Science JD

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| company | [FAIL] | 0.00 | None | Flipkart |
| job_title | [FAIL] | 0.00 | None | Data Scientist |
| skills | [PASS] | 0.71 | ['Python', 'R', 'SQL', 'Machine Learning | ['Python', 'R', 'SQL', 'Machine Learning |
| experience_years | [FAIL] | 0.00 | 1-3 years | None |
| academic_requirements | [FAIL] | 0.00 | ['B.Tech', 'M.Tech'] | None |
| cgpa_requirement | [FAIL] | 0.00 | None | None |
| location | [PASS] | 0.80 | Bangalore Criteria B | Bangalore |
| compensation | [PASS] | 1.00 | 12-18 LPA | 12-18 LPA |
| selection_rounds | [FAIL] | 0.00 | [] | None |
| date | [FAIL] | 0.00 | 2024-03-25T00:00 | 25th March 2024 |
| has_bond | [FAIL] | 0.00 | None | None |
| qualification_required | [FAIL] | 0.00 | ['AIDS', 'CSE'] | None |

### TC_JD_007

- Status: FAIL
- Fields: 2/12
- Score: 0.17
- Category: Capgemini JD

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| company | [FAIL] | 0.00 | None | Capgemini |
| job_title | [FAIL] | 0.00 | None | Programmer Trainee |
| skills | [FAIL] | 0.00 | [] | ['Written Test', 'Technical', 'HR'] |
| experience_years | [FAIL] | 0.00 | None | None |
| academic_requirements | [FAIL] | 0.00 | ['B.E', 'B.Tech'] | None |
| cgpa_requirement | [FAIL] | 0.00 | None | None |
| location | [PASS] | 0.80 | Chennai Eligibility | Chennai |
| compensation | [PASS] | 1.00 | 3.36 LPA | 3.36 LPA |
| selection_rounds | [FAIL] | 0.00 | [] | None |
| date | [FAIL] | 0.00 | None | 18th January 2024 |
| has_bond | [FAIL] | 0.00 | None | None |
| qualification_required | [FAIL] | 0.00 | [] | None |

### TC_JD_008

- Status: FAIL
- Fields: 4/12
- Score: 0.33
- Category: Adobe JD

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| company | [PASS] | 0.80 | Adobe Location Noida Requirements B.Tech | Adobe |
| job_title | [FAIL] | 0.00 | None | Software Engineer |
| skills | [PASS] | 0.75 | ['JavaScript', 'TypeScript', 'React', 'R | ['Frontend', 'JavaScript', 'React', 'Typ |
| experience_years | [FAIL] | 0.00 | None | None |
| academic_requirements | [FAIL] | 0.00 | ['B.Tech'] | None |
| cgpa_requirement | [FAIL] | 0.00 | None | None |
| location | [PASS] | 0.80 | Noida Requirements B | Noida |
| compensation | [PASS] | 1.00 | 15-22 LPA | 15-22 LPA |
| selection_rounds | [FAIL] | 0.00 | [] | None |
| date | [FAIL] | 0.00 | 2024-02-28T00:00 | 28th Feb 2024 |
| has_bond | [FAIL] | 0.00 | None | None |
| qualification_required | [FAIL] | 0.00 | [] | None |

### TC_JD_009

- Status: FAIL
- Fields: 1/12
- Score: 0.08
- Category: Mega Drive JD

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| company | [FAIL] | 0.00 | None | Wipro |
| job_title | [FAIL] | 0.00 | None | None |
| skills | [FAIL] | 0.00 | [] | None |
| experience_years | [FAIL] | 0.00 | None | None |
| academic_requirements | [FAIL] | 0.00 | [] | None |
| cgpa_requirement | [FAIL] | 0.00 | None | None |
| location | [FAIL] | 0.00 | None | None |
| compensation | [PASS] | 0.80 | 3.0 to 6.0 LPA | 6.0 LPA |
| selection_rounds | [FAIL] | 0.00 | ['varies by company Package range 3.0 to | None |
| date | [FAIL] | 0.00 | None | 12th March 2024 |
| has_bond | [FAIL] | 0.00 | None | None |
| qualification_required | [FAIL] | 0.00 | [] | None |

### TC_JD_010

- Status: FAIL
- Fields: 4/12
- Score: 0.33
- Category: Google Internship

| Field | Correct | Score | Parsed | Expected |
|-------|---------|-------|--------|----------|
| company | [FAIL] | 0.00 | None | Google |
| job_title | [PASS] | 0.80 | SWE | SWE Intern |
| skills | [PASS] | 0.60 | ['Python', 'Java', 'C', 'Data Structures | ['C++', 'Java', 'Python', 'DSA'] |
| experience_years | [FAIL] | 0.00 | None | None |
| academic_requirements | [FAIL] | 0.00 | ['B.Tech'] | None |
| cgpa_requirement | [FAIL] | 0.00 | 8.0 | CGPA 8.0 |
| location | [PASS] | 0.80 | Bangalore Hybrid Eligibility B | Bangalore |
| compensation | [PASS] | 1.00 | 1 LPA | 1 LPA |
| selection_rounds | [FAIL] | 0.00 | [] | None |
| date | [FAIL] | 0.00 | None | 5th April 2024 |
| has_bond | [FAIL] | 0.00 | None | None |
| qualification_required | [FAIL] | 0.00 | [] | None |

