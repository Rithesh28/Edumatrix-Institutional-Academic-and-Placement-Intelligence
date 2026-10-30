# Placement Intelligence Module Fixes

## Summary of fixes applied to Issues 1-3:

### Issue 1: Official Application URL Extraction/Form Display Mismatch

**Backend (`backend/app/services/jd_parser_service.py`):**
- Enhanced `_extract_all_application_urls()` to collect URL candidates from multiple patterns (explicit apply phrases, raw http/https URLs, www. domains)
- Improved `_extract_application_url_and_instructions()` to:
  - Deduplicate candidates while preserving order
  - Validate URL schemes (prepend https:// for domain-like URLs without scheme)
  - Reject truncated prefixes (discard shorter URLs that are strict prefixes of longer valid ones)
  - Score candidates based on form provider intrinsic weight, portal/path intrinsic weight, and context signals
  - Store URL candidates in evidence for traceability (`application_url_candidates`)
- Added `_preprocess_text_for_urls()` improvements for OCR artifact repair (protocol spacing, domain spacing, line-break reconstruction, OCR spacing repairs)

**Frontend (`frontend/src/pages/placement/JobDetails.jsx`):**
- Added `Code` icon import from lucide-react
- Added `showCandidates` state for URL candidates visibility toggle
- Updated application URL display to show truncated URL with character count
- Added "Open Link" anchor button with proper `target="_blank"` and `rel="noopener noreferrer"`
- Added URL candidates traceability section showing found candidates with copyable text
- Enhanced "Open Link" button tooltip

### Issue 2: Incorrect Required-Skill Extraction/Classification Noise

**Backend (`backend/app/services/jd_parser_service.py`):**
- Rewrote `_find_skills_in_segment()` with noise reduction:
  - Added noise phrase filtering for academic criteria (10th, 12th, percentages, batch years, arrears/backlogs)
  - Early return if noise score >= 2 (too much academic context)
  - Context-aware matching: only extract skills near skill-relevant terms (knowledge, proficient, experience, skills, required, optional, bonus, desired, must, nice, good)
  - Additional check: ensure skill isn't part of an academic percentage pattern (e.g., "60% python" should not extract "python")
- Restricted GLiNER enrichment to only run when there are already baseline skills (`req_skills or pref_skills`), preventing noise from empty extractions

### Issue 3: Extremely Slow Candidate Matching (~10 min for ~361 students)

**Backend (`backend/app/services/placement_service.py`):**
- Optimized `match_students_for_job()` with:
  - Eager loading of student profiles with `joinedload(User.student_profile)` to avoid N+1 queries
  - Pre-computation of job skill normalization once before the student loop
  - Student skill caching per `student_id` using `student_skill_cache` dict to avoid re-querying `get_student_skills()` for each student
  - Reduced redundant eligibility checks by caching resolved skill data

## Verification:
- Python compile: `py_compile` passed for both `jd_parser_service.py` and `placement_service.py`
- Frontend build: `npm run build` completed successfully (23.86s, 2012 modules transformed)
- All 12 preservation rules from original instructions are maintained