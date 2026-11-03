# Phase 1 Root-Cause Diagnosis Report
## Resume Parser & JD Parser Field Extraction Improvement

**Date:** 2026-11-03  
**Prepared by:** Agnes (Claude Code)  
**Purpose:** Document root causes for parser improvement (Phase 2)

---

## Executive Summary

| Parser | Current Accuracy | Target | Fields Total | Fields Passing |
|--------|-----------------|--------|-------------|----------------|
| Resume Parser | 43.64% (24/55) | >80% | 55 | ~44 needed |
| JD Parser | 21.67% (26/120) | >80% | 120 | ~96 needed |

**Key Finding:** Both parsers have strong performance on simple scalar fields (name, email, CGPA, compensation) but fail systematically on complex nested fields (education, experience, projects, companies, location). The failures are caused by identifiable, fixable bugs in regex patterns, missing extraction logic, and output formatting issues — NOT by fundamental limitations of the approach.

---

## PART A: RESUME PARSER ROOT CAUSE ANALYSIS

### Current Per-Field Performance

| Field | Correct | Total | Accuracy | Status |
|-------|---------|-------|----------|--------|
| name | 5 | 5 | 100% | ✅ Excellent |
| email | 5 | 5 | 100% | ✅ Excellent |
| cgpa | 5 | 5 | 100% | ✅ Excellent |
| phone | 4 | 5 | 80% | ✅ Good |
| skills | 4 | 5 | 80% | ✅ Good |
| certifications | 1 | 5 | 20% | ❌ Needs Fix |
| education | 0 | 5 | 0% | ❌ Critical |
| companies | 0 | 5 | 0% | ❌ Critical |
| experience | 0 | 5 | 0% | ❌ Critical |
| projects | 0 | 5 | 0% | ❌ Critical |
| location | 0 | 5 | 0% | ❌ Critical |

### ROOT CAUSE #1: Education Extraction — Duplicate Entries + Wrong Format

**File:** `backend/app/services/resume_parser.py`, lines 484-497  
**Severity:** CRITICAL  
**Impact:** 0/5 education fields correct

**Problem:** The regex at line 485 finds EVERY occurrence of degree abbreviations in the entire text, not just in the Education section. This produces:
- Duplicate entries: `"me (Computer Science)"`, `"B.Tech (Computer Science)"` (both from same line)
- Inconsistent casing: `"me"` vs `"Me"` vs `"B.Tech"`
- Wrong format: Returns list of dicts `{"degree": "B.Tech (Computer Science)", "cgpa": 8.5}` but evaluation expects flat strings `["B.Tech Computer Science"]`

**Evidence from resume_001_john_smith.docx:**
- Expected: `["B.Tech Computer Science"]`
- Parsed: `["me (Computer Science)", "B.Tech (Computer Science)"]`
- The text contains "M.E (Computer Science)" and "B.Tech (Computer Science)" as separate lines, both matched.

**Fix Strategy:**
1. Add section-aware extraction: only match degree patterns within "Education" section boundaries
2. Deduplicate by case-insensitive comparison
3. Normalize output format: convert `{"degree": "B.Tech (CS)", "cgpa": 8.5}` → `"B.Tech Computer Science"` (strip parentheses, normalize spacing)
4. Only keep the highest/relevant degree (typically B.Tech for undergrad resumes)

### ROOT CAUSE #2: Companies Field — Zero Extraction Logic

**File:** `backend/app/services/resume_parser.py`, line 433  
**Severity:** CRITICAL  
**Impact:** 0/5 companies fields correct

**Problem:** The `companies` field is initialized as `[]` at line 433 but **never populated** anywhere in the code. There is no extraction logic for company names.

**Evidence:** All 5 resumes have experience entries (Google, Flipkart, Amazon, Microsoft, Zomato) but `companies` remains `[]` in every case.

**Fix Strategy:**
1. Extract company names from experience descriptions using patterns like:
   - `Company Name \| Dates` (e.g., "Google | Jun 2023 - Aug 2023")
   - `at Company Name` (e.g., "at Google")
   - `Company Name, Location` (e.g., "Google, Bangalore")
2. Populate `entities['companies']` from extracted experience data
3. Deduplicate company names

### ROOT CAUSE #3: Experience Extraction — Wrong Title Format + Missing Structure

**File:** `backend/app/services/resume_parser.py`, lines 499-516  
**Severity:** CRITICAL  
**Impact:** 0/5 experience fields correct

**Problem:** Multiple issues:
1. **Section detection fails:** Regex at line 505 looks for "Work Experience|Experience|Internship|Professional Experience" but resumes may use "Experience" as a section header followed by bullet points, not a contiguous block.
2. **Generic titles:** Line 510 creates `{"title": r.strip() + " Role"}` producing "Intern Role", "Developer Role" instead of actual titles like "Software Intern", "Frontend Developer".
3. **Missing company/dates:** Experience entries lack `company` and `dates` fields — only `title` and `description`.
4. **Fallback too broad:** Line 512 matches any occurrence of "Software Engineer" etc. anywhere in text, not just in experience context.

**Evidence from resume_001_john_smith.docx:**
- Expected: `[{"title": "Software Intern", "company": "Google", "dates": "Jun 2023 - Aug 2023"}]`
- Parsed: `[]` (empty — section detection failed)

**Evidence from resume_002_priya_sharma.docx:**
- Expected: `[{"title": "Frontend Developer", "company": "Flipkart", "dates": "Jan 2023 - Present"}]`
- Parsed: `[{"title": "Developer Role", "description": "Frontend Developer, Flipkart | Jan 2023 - Present..."}]`

**Fix Strategy:**
1. Improve section detection: Look for "Experience" header, then capture all bullet points until next section
2. Parse individual experience entries: Extract title, company, and dates from each entry using patterns like:
   - `Title, Company \| Dates`
   - `Title at Company (Dates)`
   - `Title — Company, Dates`
3. Store structured data: `{"title": "...", "company": "...", "dates": "..."}`

### ROOT CAUSE #4: Projects Extraction — Captures Descriptions as Names

**File:** `backend/app/services/resume_parser.py`, lines 518-531  
**Severity:** MAJOR  
**Impact:** 0/5 projects fields correct

**Problem:**
1. **Overly broad capture:** Regex at line 520 captures up to 600 characters after "Projects" header, including descriptions.
2. **Wrong field assignment:** Line 525 sets `"name": l[:40]` but the line `l` is the FULL line including description, so names are truncated mid-sentence.
3. **Picks up non-project content:** Captures "ACHIEVEMENTS" section content as projects (see resume_003).
4. **Fallback too aggressive:** Line 527 matches any "Project: ...", "System: ...", "Application: ..." pattern anywhere in text.

**Evidence from resume_001_john_smith.docx:**
- Expected: `["Recommendation System", "Chat Application"]`
- Parsed: `[{"name": "Recommendation System: Built a content-b", "description": "..."}]`
- The name is truncated at 40 chars and includes the description prefix.

**Fix Strategy:**
1. Extract only the project name (first line after header or after "Project:" label)
2. Truncate to reasonable length (20-30 chars) without cutting mid-word
3. Exclude non-project sections (Achievements, Publications)
4. Return flat list of strings `["Project Name", "Project Name 2"]` to match expected format

### ROOT CAUSE #5: Certifications — Generic Names + False Matches

**File:** `backend/app/services/resume_parser.py`, lines 533-539  
**Severity:** MAJOR  
**Impact:** 1/5 certifications correct (20%)

**Problem:**
1. **Matches standalone "Certified":** Line 535 matches the word "Certified" as a certification, producing `"Certified Certification"`.
2. **Generic naming:** All certifications get suffix " Certification" appended, even when the actual cert name is specific (e.g., "AWS Cloud Practitioner" becomes "AWS Certification").
3. **Missing specific cert names:** Doesn't capture full cert names like "AWS Cloud Practitioner", "Docker Certified Associate", "Meta Frontend Developer Certificate".

**Evidence from resume_004_ananya_patel.docx:**
- Expected: `["AWS Certified Cloud Practitioner", "Docker Certified Associate"]`
- Parsed: `["Certified Certification", "AWS Certification"]`

**Fix Strategy:**
1. Add specific certification patterns: "AWS Certified Cloud Practitioner", "Docker Certified Associate", "Google Cloud Professional", etc.
2. Avoid matching standalone "Certified" — require it to be part of a known cert name
3. Extract full cert names, not just the provider

### ROOT CAUSE #6: Location — Zero Extraction Logic

**File:** `backend/app/services/resume_parser.py`  
**Severity:** MAJOR  
**Impact:** 0/5 location fields correct

**Problem:** No location extraction logic exists anywhere in the parser. The `entities` dict has a `'location': ''` key (actually not present — it's not in the init dict at line 424-436), but there's no code to populate it.

**Wait — actually:** Looking at line 424-436, `location` is NOT in the entities dict. It's only checked in the evaluation script at line 188. The parser never extracts location.

**Fix Strategy:**
1. Add location extraction using regex patterns for Indian cities/states
2. Look for patterns like "Location: Bangalore", "Bangalore, India", "Based in Chennai"
3. Add to entities dict initialization

### ROOT CAUSE #7: Phone — 20% Failure (1/5)

**File:** `backend/app/services/resume_parser.py`, lines 444-447  
**Severity:** MINOR  
**Impact:** 1/5 phone fields incorrect

**Problem:** The phone regex at line 445 requires a specific pattern that may not match all Indian phone formats. Resume_005 (Arjun Reddy) has phone as `""` (empty string) instead of null, suggesting the regex didn't match.

**Evidence:** Arjun Reddy's resume has phone as null in ground truth, but the parser returns `""` (empty string) which the evaluation treats as a mismatch.

**Fix Strategy:**
1. Ensure empty phone values are stored as `None` not `""`
2. Improve phone regex to handle more Indian formats

---

## PART B: JD PARSER ROOT CAUSE ANALYSIS

### Current Per-Field Performance

| Field | Correct | Total | Accuracy | Status |
|-------|---------|-------|----------|--------|
| compensation | 10 | 10 | 100% | ✅ Excellent |
| location | 8 | 10 | 80% | ✅ Good |
| skills | 4 | 10 | 40% | ⚠️ Partial |
| company | 3 | 10 | 30% | ❌ Needs Fix |
| job_title | 1 | 10 | 10% | ❌ Critical |
| experience_years | 0 | 10 | 0% | ⚠️ Eval Mismatch |
| academic_requirements | 0 | 10 | 0% | ⚠️ Eval Mismatch |
| cgpa_requirement | 0 | 10 | 0% | ⚠️ Eval Mismatch |
| selection_rounds | 0 | 10 | 0% | ❌ Needs Fix |
| date | 0 | 10 | 0% | ⚠️ Format Mismatch |
| has_bond | 0 | 10 | 0% | ⚠️ Eval Mismatch |
| qualification_required | 0 | 10 | 0% | ⚠️ Eval Mismatch |

### ROOT CAUSE #1: Company Extraction — Captures Too Much Text

**File:** `backend/app/services/jd_parser_service.py`, lines 636-654  
**Severity:** CRITICAL  
**Impact:** 7/10 company fields incorrect

**Problem:** The regex pattern at line 639:
```python
r'(?:company(?:\s*name)?|client|organization|recruiter)[\s:\-–—|]+([A-Za-z0-9\s\.\,\&\'\-]+)'
```
Captures everything after "Company" until punctuation. For input "Company Amazon Location Hyderabad", it captures "Amazon Location Hyderabad" instead of just "Amazon".

**Evidence from TC_JD_001:**
- Expected: `"TCS"`
- Parsed: `"TCS ROLE"` (score 0.8 — partial match)

**Evidence from TC_JD_002:**
- Expected: `"Amazon"`
- Parsed: `"Amazon Location Hyderabad Eligibility B.Tech 80"` (score 0.0 — too long)

**Fix Strategy:**
1. Limit capture to 2-5 words after "Company" label
2. Use word boundaries and stop at known non-company words (Location, Role, Eligibility, etc.)
3. Add pattern for "Company <Name>" format specifically

### ROOT CAUSE #2: Job Title Extraction — Pattern Mismatch

**File:** `backend/app/services/jd_parser_service.py`, lines 561-634  
**Severity:** CRITICAL  
**Impact:** 9/10 job_title fields incorrect

**Problem:** The title extraction patterns at lines 565-568 look for labels like "job title:", "designation:", "role:" but many test cases use "ROLE:" format which should match. However, the main issue is:
1. Pattern `r'(?:job\s*title|designation|position|role|profile|hiring\s*for|opening\s*for)[\s:\-–—|]+([^\n\r,;|\t]+)'` — the "role:" prefix should match "ROLE: Software Trainee" but the capture group includes everything to end of line.
2. The cleanup at lines 575-576 removes prefixes but the candidate text still includes trailing noise.
3. For TC_JD_010, the parser returns "SWE" instead of "SWE Intern" — the title cleanup is too aggressive.

**Evidence from TC_JD_001:**
- Expected: `"Software Trainee"`
- Parsed: `null` (no match found — pattern didn't trigger)

**Evidence from TC_JD_010:**
- Expected: `"SWE Intern"`
- Parsed: `"SWE"` (score 0.8)

**Fix Strategy:**
1. Fix the regex to properly capture after "ROLE:" or "Role:"
2. Reduce aggressiveness of title cleanup (don't strip "Intern" suffix)
3. Add pattern for "Position <Title>" format

### ROOT CAUSE #3: Location Extraction — Captures Trailing Noise

**File:** `backend/app/services/jd_parser_service.py`, lines 1041-1082  
**Severity:** MAJOR  
**Impact:** 2/10 location fields have noise (score 0.8 instead of 1.0)

**Problem:** Location regex at line 1062 captures too much:
```python
r'(?:job\s*location|location|work\s*location)[\s:\-–—|]+([A-Za-z\s,/\-]+)'
```
For input "LOCATION: Pune REQUIREMENTS", it captures "Pune REQUIREMENTS" instead of just "Pune".

**Evidence:**
- TC_JD_001: Parsed `"Pune REQUIREMENTS"` (expected `"Pune"`)
- TC_JD_002: Parsed `"Hyderabad Eligibility B"` (expected `"Hyderabad"`)
- TC_JD_003: Parsed `"Work from Home Eligibility"` (expected `"Work from Home"`)

**Fix Strategy:**
1. Add stop words to location capture (Requirements, Eligibility, Skills, etc.)
2. Limit capture to reasonable length (max 30 chars)
3. Clean trailing noise with regex

### ROOT CAUSE #4: Selection Rounds — No Extraction

**File:** `backend/app/services/jd_parser_service.py`, lines 1455-1487  
**Severity:** MAJOR  
**Impact:** 0/10 selection_rounds correct

**Problem:** The selection rounds extractor looks for "Round 1", "Step 1" patterns but test cases describe processes inline:
- "Online Assessment Technical Interview HR"
- "Coding Round Technical Interview Managerial Round HR Round"
- "Written Test Technical HR"

The regex at line 1462-1465 requires explicit "Round N" or "Step N" prefixes which don't exist in test data.

**Fix Strategy:**
1. Add pattern to detect "Process:" or "Selection:" section headers
2. Split by common delimiters (space, comma) to extract individual rounds
3. Match known round types: "Online Assessment", "Technical Interview", "HR Round", etc.

### ROOT CAUSE #5: Date Extraction — ISO Format vs Human-Readable

**File:** `backend/app/services/jd_parser_service.py`, lines 1248-1336  
**Severity:** MAJOR  
**Impact:** 0/10 date fields correct (format mismatch)

**Problem:** The parser converts dates to ISO format (e.g., "2024-03-15T00:00") but the evaluation expects human-readable format (e.g., "15th March 2024"). The fuzzy matching in `compare_values` checks `if p in e or e in p` but "2024-03-15T00:00" is not contained in "15th March 2024" and vice versa.

**Evidence:**
- TC_JD_001: Parsed `"2024-03-15T00:00"`, Expected `"15th March 2024"`
- TC_JD_003: Parsed `"2024-02-20T00:00"`, Expected `"20th February 2024"`

**Fix Strategy:**
1. Store original human-readable date in addition to ISO format
2. Or: Update evaluation to normalize both formats before comparison
3. Best approach: Keep both formats in output, evaluate against the human-readable one

### EVALUATION MISMATCH ISSUES (Not Parser Bugs)

The following fields show 0% accuracy but the parser is actually extracting correct data — the issue is in the evaluation's expected values:

| Field | Parser Output | Expected | Issue |
|-------|--------------|----------|-------|
| experience_years | "2+ years experience" (TC_002), "1-3 years" (TC_006) | null | Test cases don't expect experience for most JDs |
| academic_requirements | ["B.Tech"] (multiple) | null | Parser extracts degree eligibility, eval expects null |
| cgpa_requirement | 7.5 (TC_005), 8.0 (TC_010) | "CGPA 8.0" (TC_010), null (others) | Format mismatch + eval expects null |
| has_bond | "Bond 2 years..." (TC_002) | null | Parser correctly finds bond, eval doesn't expect it |
| qualification_required | ["CSE", "ECE", "IT"] (TC_001) | null | Parser extracts branches, eval expects null |

**These are evaluation design issues, not parser bugs.** The parser is correctly extracting information that exists in the JD text. The test cases' `expected_fields` column doesn't always account for all extractable information.

However, to improve the field accuracy metric, we need to either:
1. Fix the parser to not extract these fields when not explicitly requested (conservative extraction)
2. OR improve the evaluation to recognize correct extractions

For the >80% target, the most impactful fixes are on the clear parser bugs (Company, Title, Location, Selection Rounds, Date format).

---

## PART C: PRIORITY MATRIX FOR PHASE 2

### High Impact Fixes (Resume Parser)

| Priority | Root Cause | Estimated Impact | Difficulty |
|----------|-----------|-----------------|------------|
| 1 | Education: dedup + normalize | +10 points (0→100%) | Medium |
| 2 | Companies: add extraction | +10 points (0→100%) | Medium |
| 3 | Experience: structured extraction | +10 points (0→100%) | Hard |
| 4 | Projects: name-only extraction | +10 points (0→100%) | Medium |
| 5 | Certifications: specific names | +5 points (20→40%) | Easy |
| 6 | Location: add extraction | +10 points (0→100%) | Easy |

**Total potential gain: +55 points → 99/55 = 180% (theoretical max)**

### High Impact Fixes (JD Parser)

| Priority | Root Cause | Estimated Impact | Difficulty |
|----------|-----------|-----------------|------------|
| 1 | Company: limit capture | +6 points (30→90%) | Easy |
| 2 | Job Title: fix patterns | +6 points (10→70%) | Medium |
| 3 | Location: trim noise | +2 points (80→100%) | Easy |
| 4 | Selection Rounds: add patterns | +6 points (0→60%) | Medium |
| 5 | Date: keep original format | +6 points (0→60%) | Easy |
| 6 | Skills: include process items | +2 points (40→60%) | Medium |

**Total potential gain: +28 points → 49/120 = 40.8% (from current 21.67%)**

### Combined Impact Projection

If all high-priority fixes are implemented:
- Resume Parser: ~80-90% field accuracy (target: >80%)
- JD Parser: ~55-65% field accuracy (target: >80% — may need additional work)

**Note:** The JD Parser target of >80% is ambitious given that many "failures" are evaluation mismatches. We should aim for genuine parser improvements and transparently report the evaluation methodology.

---

## APPENDIX A: File Locations

| Component | File Path | Key Lines |
|-----------|-----------|-----------|
| Resume Parser | `backend/app/services/resume_parser.py` | 422-544 (entity extraction) |
| JD Parser | `backend/app/services/jd_parser_service.py` | 454-1700 (full pipeline) |
| Resume Eval Script | `evaluation/scripts/evaluate_resume_parser_fixed.py` | Full file |
| JD Eval Script | `evaluation/scripts/evaluate_jd_parser_fixed.py` | Full file |
| Resume Ground Truth | `evaluation/test_cases/resumes/ground_truth/*.json` | 5 files |
| JD Test Cases | `evaluation/test_cases/jd_parser_cases.csv` | 10 rows |

---

## APPENDIX B: Test Data Summary

### Resume Test Cases (5 DOCX files)
1. resume_001_john_smith.docx — Software Engineer, Google intern, CGPA 8.5
2. resume_002_priya_sharma.docx — Frontend Developer, Flipkart, CGPA null
3. resume_003_rahul_verma.docx — SDE at Amazon, CGPA 9.1
4. resume_004_ananya_patel.docx — DevOps Intern, Microsoft, CGPA 8.8
5. resume_005_arjun_reddy.docx — Backend Engineer, Zomato, CGPA null

### JD Test Cases (10 CSV rows)
1. TC_JD_001 — TCS Service Based
2. TC_JD_002 — Amazon Product Company
3. TC_JD_003 — Infosys Springboard
4. TC_JD_004 — Wipro Campus Drive
5. TC_JD_005 — Deloitte Big 4
6. TC_JD_006 — Flipkart Data Science
7. TC_JD_007 — Capgemini Walk-in
8. TC_JD_008 — Adobe Frontend
9. TC_JD_009 — Mega Drive (multiple companies)
10. TC_JD_010 — Google Internship

---

**END OF DIAGNOSIS REPORT**
