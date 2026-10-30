# Placement Intelligence Fixes - Verification Report

## URL Extraction
- Prefix filtering at jd_parser_service.py:2121-2130 only discards strict prefixes (e.g., shorter URL that is prefix of longer unique URL). Valid URLs with distinct paths/query params are never discarded.
- Query parameters and paths preserved: _clean_and_validate_candidate_url() at line 1949-2019 uses urlparse and only strips trailing punctuation/brackets, not ? or & parameters.
- Manual URL not overwritten: create_job_posting() at api/placement.py:276 persists the API-provided URL; extraction only populates JdParseResult fields, not the DB-persisted value.
- Saved URL matches API return: JobDetails.jsx displays selectedJob.application_url (DB value); candidates section shows extracted candidates separately as traceability.

## Skill Extraction
- Valid skills under "Technical Skills" heading extracted if they have context keywords (knowledge, proficient, experience, required, etc.). _find_skills_in_segment() at jd_parser_service.py:1583-1610.
- GLiNER restriction (only run when req_skills or pref_skills non-empty) at jd_parser_service.py:1542-1546 prevents noise when baseline is empty, but may omit skills if truly zero baseline exists.
- Filenames, company names, product names, academic criteria filtered out by noise checks and word-boundary regex. Academic criteria explicitly filtered by noise phrases (10th, 12th, percentage) and early return if noise_score >= 2.

## Candidate Matching
- student_skill_cache dict at placement_service.py:1178 caches (student_skills, skill_sources) per student.id, preventing re-query after first iteration.
- check_student_eligibility() still runs per student for CGPA/branch validation (authoritative rules, unavoidable).
- Inactive students filtered at both frontend (JobDetails.jsx:1166) and backend (match_students_for_job() line 1168).
- Button disabled={isMatching} at JobDetails.jsx:390-391 prevents duplicate clicks during active match; no guard against rapid double-clicks before state updates.
- No persistent cache — student_skill_cache is scoped to single match_students_for_job() call, built fresh from DB each time.

## Verification
- py_compile passed for jd_parser_service.py and placement_service.py
- npm run build succeeded (2012 modules, 19-24s)
- No existing tests modified; no before/after performance timings claimed
- Smallest targeted tests: URL extraction with/without query params; skill extraction with academic criteria noise; matching profiling on subset of students