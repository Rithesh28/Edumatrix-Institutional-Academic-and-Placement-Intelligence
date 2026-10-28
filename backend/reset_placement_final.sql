-- ============================================================
-- PLACEMENT DATA RESET - SQL VERSION
-- Run this directly on the PostgreSQL database
-- ============================================================

-- Step 1: Identify test companies (timestamp patterns in name)
-- Test company IDs: 563, 562, 556, 514

-- First, delete placement offers for test company jobs
DELETE FROM placement_offers
WHERE job_posting_id IN (
    SELECT id FROM job_postings WHERE company_id IN (563, 562, 556, 514)
);

-- Delete applications for test company jobs
DELETE FROM applications
WHERE job_posting_id IN (
    SELECT id FROM job_postings WHERE company_id IN (563, 562, 556, 514)
);

-- Delete shortlists for test company jobs
DELETE FROM shortlists
WHERE job_posting_id IN (
    SELECT id FROM job_postings WHERE company_id IN (563, 562, 556, 514)
);

-- Delete student_round_outcomes for test company jobs
DELETE FROM student_round_outcomes
WHERE round_id IN (
    SELECT id FROM recruitment_rounds WHERE job_posting_id IN (
        SELECT id FROM job_postings WHERE company_id IN (563, 562, 556, 514)
    )
);

-- Delete recruitment_rounds for test company jobs
DELETE FROM recruitment_rounds
WHERE job_posting_id IN (
    SELECT id FROM job_postings WHERE company_id IN (563, 562, 556, 514)
);

-- Delete recruitment_result_items for test company jobs
DELETE FROM recruitment_result_items
WHERE batch_id IN (
    SELECT id FROM recruitment_result_batches WHERE job_posting_id IN (
        SELECT id FROM job_postings WHERE company_id IN (563, 562, 556, 514)
    )
);

-- Delete recruitment_result_batches for test company jobs
DELETE FROM recruitment_result_batches
WHERE job_posting_id IN (
    SELECT id FROM job_postings WHERE company_id IN (563, 562, 556, 514)
);

-- Delete job_posting_attachments for test company jobs
DELETE FROM job_posting_attachments
WHERE job_posting_id IN (
    SELECT id FROM job_postings WHERE company_id IN (563, 562, 556, 514)
);

-- Delete recruitment_circular_job links for test company jobs
DELETE FROM recruitment_circular_jobs
WHERE job_posting_id IN (
    SELECT id FROM job_postings WHERE company_id IN (563, 562, 556, 514)
);

-- Delete test company jobs
DELETE FROM job_postings
WHERE company_id IN (563, 562, 556, 514);

-- Delete recruitment_circular_attachments for test company circulars
DELETE FROM recruitment_circular_attachments
WHERE circular_id IN (
    SELECT id FROM recruitment_circulars WHERE company_id IN (563, 562, 556, 514)
);

-- Delete recruitment_circulars for test companies
DELETE FROM recruitment_circulars
WHERE company_id IN (563, 562, 556, 514);

-- Delete shortlists for test companies
DELETE FROM shortlists WHERE company_id IN (563, 562, 556, 514);

-- Finally, delete the test companies
DELETE FROM companies WHERE id IN (563, 562, 556, 514);

-- Reset ANY student profile placement_status that might be PLACED
UPDATE student_profiles
SET placement_status = 'not_applied'
WHERE placement_status = 'placed';

-- Reset ANY application with SELECTED status to APPLIED
UPDATE applications
SET status = 'applied'
WHERE status = 'selected';

-- Delete ANY placement offer with ACCEPTED status
DELETE FROM placement_offers
WHERE acceptance_status = 'accepted';

-- ============================================================
-- VERIFICATION QUERIES
-- ============================================================

-- Check remaining companies
SELECT id, name, is_active FROM companies ORDER BY id;

-- Check remaining jobs
SELECT id, title, company_id, status FROM job_postings ORDER BY id;

-- Check applications
SELECT id, student_id, job_posting_id, status FROM applications ORDER BY id;

-- Check placement offers
SELECT id, student_id, job_posting_id, acceptance_status FROM placement_offers ORDER BY id;

-- Check student profiles with PLACED status
SELECT sp.id, sp.user_id, sp.placement_status, u.name, u.email
FROM student_profiles sp
JOIN users u ON sp.user_id = u.id
WHERE sp.placement_status = 'placed';

-- Check SELECTED applications
SELECT a.id, a.student_id, a.job_posting_id, a.status, u.name as student_name, j.title as job_title, c.name as company_name
FROM applications a
JOIN users u ON a.student_id = u.id
JOIN job_postings j ON a.job_posting_id = j.id
JOIN companies c ON j.company_id = c.id
WHERE a.status = 'selected';

-- Check ACCEPTED offers
SELECT o.id, o.student_id, o.job_posting_id, o.acceptance_status, u.name as student_name, j.title as job_title, c.name as company_name
FROM placement_offers o
JOIN users u ON o.student_id = u.id
JOIN job_postings j ON o.job_posting_id = j.id
JOIN companies c ON j.company_id = c.id
WHERE o.acceptance_status = 'accepted';