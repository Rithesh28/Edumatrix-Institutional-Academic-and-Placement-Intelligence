-- Step 1: Delete test company dependent records
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

-- Reset Alice Candidate's application status (student_id = 1792554360761 based on earlier output)
-- But first let's check the actual student_id
SELECT id, name, email FROM users WHERE email LIKE '%student_a_profile%';

-- Reset the selected application for this student
UPDATE applications
SET status = 'applied'
WHERE student_id = 1792554360761 AND status = 'selected';

-- Reset student profile placement_status for this student
UPDATE student_profiles
SET placement_status = 'not_applied'
WHERE user_id = 1792554360761;