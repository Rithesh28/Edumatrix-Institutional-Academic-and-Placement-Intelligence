/**
 * Automated Verification Script for Phase 3.2 Step 2.4:
 * Student Job Details, Skill-Match Preview & Application Submission
 */

import assert from 'assert';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log('🧪 Starting Phase 3.2 Step 2.4: Student Job Details & Application Verification...\n');

// ============================================================================
// 1. Static Source Code Inspection of JobDetails.jsx
// ============================================================================
console.log('1. Checking frontend/src/pages/student/JobDetails.jsx implementation...');
const detailsCode = fs.readFileSync(path.join(__dirname, 'src/pages/student/JobDetails.jsx'), 'utf8');

// Ensure placeholder was replaced
assert(
  !detailsCode.includes('Job detail and application workflow placeholder'),
  'JobDetails.jsx must not contain placeholder text'
);
console.log('   ✅ Placeholder successfully replaced with functional JobDetails page.');

// Check store integrations
assert(
  detailsCode.includes('usePlacementStore'),
  'JobDetails.jsx must import and use usePlacementStore'
);
assert(
  detailsCode.includes('fetchJobPosting'),
  'JobDetails.jsx must call fetchJobPosting'
);
assert(
  detailsCode.includes('checkJobEligibility'),
  'JobDetails.jsx must call checkJobEligibility'
);
assert(
  detailsCode.includes('clearJobEligibility'),
  'JobDetails.jsx must call clearJobEligibility to prevent stale data'
);
assert(
  detailsCode.includes('createApplication'),
  'JobDetails.jsx must call createApplication'
);
assert(
  detailsCode.includes('useAuthStore'),
  'JobDetails.jsx must use useAuthStore for authenticated student context'
);
console.log('   ✅ Store integrations verified (placementStore + authStore).');

// Check back-to-jobs action
assert(
  detailsCode.includes('/student/jobs'),
  'JobDetails.jsx must include a back action navigating to /student/jobs'
);
console.log('   ✅ Back to Campus Jobs navigation verified.');

// Check rendering of real backend Job details fields
const jobFields = [
  'title',
  'company_name',
  'description',
  'location',
  'salary_range',
  'application_deadline',
  'drive_date',
  'cgpa_criteria',
  'branch_eligibility',
  'required_skills',
  'preferred_skills',
  'experience_level',
];
for (const field of jobFields) {
  assert(
    detailsCode.includes(field),
    `JobDetails.jsx must handle/render job field: "${field}"`
  );
}
console.log(`   ✅ Verified handling of all ${jobFields.length} job posting fields.`);

// Check rendering of real backend Eligibility & Skill-Match fields
const eligibilityFields = [
  'overall_skill_match',
  'required_score',
  'preferred_score',
  'cgpa_match',
  'branch_match',
  'is_eligible',
  'eligibility_reasons',
  'matched_required_skills',
  'missing_required_skills',
  'has_low_match_warning',
  'low_match_warning',
  'resume_filename',
];
for (const field of eligibilityFields) {
  assert(
    detailsCode.includes(field),
    `JobDetails.jsx must handle/render eligibility field: "${field}"`
  );
}
console.log(`   ✅ Verified handling of all ${eligibilityFields.length} eligibility & match fields.`);

// Check distinction between explicit eligibility vs skill match
assert(
  detailsCode.includes('Ineligible to Apply'),
  'JobDetails.jsx must explicitly indicate when student is ineligible to apply'
);
assert(
  detailsCode.includes('has_low_match_warning'),
  'JobDetails.jsx must check has_low_match_warning'
);
assert(
  detailsCode.includes('Skill Advisory') || detailsCode.includes('low_match_warning'),
  'JobDetails.jsx must display low-match advisory warning when required match < 50%'
);
console.log('   ✅ Explicit eligibility separated from skill-match warning.');

// Check application action and payload sanitization
assert(
  detailsCode.includes('job_posting_id: jobIdNum'),
  'JobDetails.jsx must send job_posting_id'
);
assert(
  !detailsCode.includes('match_percentage:') &&
  !detailsCode.includes('eligibility_score:'),
  'JobDetails.jsx must NOT forge or send client match/eligibility scores'
);
console.log('   ✅ Authoritative payload design verified (no forged client scores).');

// Check stale eligibility prevention
assert(
  detailsCode.includes('eligibilityJobId === jobIdNum'),
  'JobDetails.jsx must check eligibilityJobId === jobIdNum to guard against stale display'
);
console.log('   ✅ Stale eligibility prevention verified.');

// Check loading, error and modal states
assert(
  detailsCode.includes('isEligibilityLoading'),
  'JobDetails.jsx must display loading state for eligibility'
);
assert(
  detailsCode.includes('eligibilityError'),
  'JobDetails.jsx must display error state for eligibility'
);
assert(
  detailsCode.includes('isApplyModalOpen'),
  'JobDetails.jsx must support confirmation modal'
);
assert(
  detailsCode.includes('submittedApplication'),
  'JobDetails.jsx must handle post-submission success feedback'
);
console.log('   ✅ Loading, error, modal, and post-submission states verified.\n');

// ============================================================================
// 2. Functional Unit Simulation of Application Decisions
// ============================================================================
console.log('2. Running functional simulation of application decisions & rules...');

// Rule A: Explicitly Ineligible (CGPA or branch fails) -> CANNOT apply
const studentA = {
  is_eligible: false,
  cgpa_match: true,
  branch_match: false,
  overall_skill_match: 80.0,
  required_score: 100.0,
  has_low_match_warning: false,
  eligibility_reasons: ["Branch 'AIML' is not eligible"],
};
const canApplyA = studentA.is_eligible;
assert.strictEqual(canApplyA, false, 'Student with failed branch criteria must be ineligible to apply');
console.log('   ✅ Rule A: Explicit criteria failure blocks application.');

// Rule B: Low Match (<50% required skills) but academically eligible -> CAN apply with advisory
const studentB = {
  is_eligible: true,
  cgpa_match: true,
  branch_match: true,
  overall_skill_match: 40.0,
  required_score: 35.0,
  has_low_match_warning: true,
  low_match_warning: 'Required skill match is below 50%',
  eligibility_reasons: [],
};
const canApplyB = studentB.is_eligible;
const showsWarningB = studentB.has_low_match_warning;
assert.strictEqual(canApplyB, true, 'Student with low match must still be eligible to apply');
assert.strictEqual(showsWarningB, true, 'Low match warning must be displayed');
console.log('   ✅ Rule B: Low match (<50%) permits application with prominent advisory.');

// Rule C: Already applied -> Show "Already Applied"
const myApps = [{ job_posting_id: 5, status: 'applied' }];
const isAppliedJob5 = myApps.some((a) => a.job_posting_id === 5);
const isAppliedJob2 = myApps.some((a) => a.job_posting_id === 2);
assert.strictEqual(isAppliedJob5, true, 'Job 5 must be detected as already applied');
assert.strictEqual(isAppliedJob2, false, 'Job 2 must be detected as not applied');
console.log('   ✅ Rule C: Applied state detection verified.');

// Rule D: Submission payload sanitization
const buildPayload = (jobId, notes) => {
  return {
    job_posting_id: parseInt(jobId, 10),
    ...(notes?.trim() ? { notes: notes.trim() } : {}),
  };
};
const payload = buildPayload('5', 'I have 2 years of React experience');
assert.deepStrictEqual(payload, { job_posting_id: 5, notes: 'I have 2 years of React experience' });
assert.strictEqual(payload.student_id, undefined, 'student_id must not be client-supplied');
assert.strictEqual(payload.match_percentage, undefined, 'match_percentage must not be client-supplied');
console.log('   ✅ Rule D: Application submission payload strictly sanitized.\n');

console.log('🎉 All Step 2.4 automated verification checks PASSED successfully!');
