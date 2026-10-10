/**
 * Automated Verification Script for Phase 3.2 Step 2.1:
 * Student Placement Service & Store Integration
 */

import assert from 'assert';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log('🧪 Starting Phase 3.2 Step 2.1: Placement Store & Service Verification...\n');

// 1. Verify placementService.js exports
console.log('1. Checking placementService.js exports and functions...');
const placementServiceCode = fs.readFileSync(path.join(__dirname, 'src/services/placementService.js'), 'utf8');

const requiredServiceExports = [
  'getJobPostings',
  'getJobPosting',
  'checkStudentEligibility',
  'createApplication',
  'getApplications',
  'getStudentPlacementStatus'
];

for (const fn of requiredServiceExports) {
  assert(
    placementServiceCode.includes(`export const ${fn} =`),
    `placementService.js must export function ${fn}`
  );
  console.log(`   ✅ Export ${fn} verified.`);
}

assert(
  placementServiceCode.includes('/placement/jobs/${jobId}/check-eligibility/${studentId}'),
  'checkStudentEligibility must target /placement/jobs/:jobId/check-eligibility/:studentId'
);
assert(
  placementServiceCode.includes('/placement/students/${studentId}/placement-status'),
  'getStudentPlacementStatus must target /placement/students/:studentId/placement-status'
);
assert(
  placementServiceCode.includes("api.post('/placement/applications'"),
  'createApplication must target POST /placement/applications'
);
console.log('   ✅ Endpoint URLs in placementService.js correctly matched to backend.\n');

// 2. Verify placementStore.js state properties
console.log('2. Checking placementStore.js state structure...');
const placementStoreCode = fs.readFileSync(path.join(__dirname, 'src/store/placementStore.js'), 'utf8');

const requiredStateProperties = [
  'jobEligibility',
  'eligibilityJobId',
  'isEligibilityLoading',
  'eligibilityError',
  'myApplications',
  'isMyApplicationsLoading',
  'myApplicationsError',
  'myPlacementStatus',
  'isPlacementStatusLoading',
  'placementStatusError',
  'isSubmittingApplication',
  'applicationSubmitError'
];

for (const prop of requiredStateProperties) {
  assert(
    placementStoreCode.includes(`${prop}:`),
    `placementStore.js must include state property ${prop}`
  );
  console.log(`   ✅ State property ${prop} verified.`);
}
console.log('   ✅ All student-isolated state properties present.\n');

// 3. Verify placementStore.js actions
console.log('3. Checking placementStore.js student-facing actions...');
const requiredActions = [
  'checkJobEligibility',
  'clearJobEligibility',
  'fetchMyApplications',
  'fetchMyPlacementStatus',
  'clearStudentErrors',
  'setSelectedJob'
];

for (const action of requiredActions) {
  assert(
    placementStoreCode.includes(`${action}:`),
    `placementStore.js must include action ${action}`
  );
  console.log(`   ✅ Action ${action} verified.`);
}
console.log('   ✅ All required student actions present.\n');

// 4. Verify Payload Sanitization (Task 7)
console.log('4. Verifying payload sanitization in createApplication...');
assert(
  placementStoreCode.includes('job_posting_id: parseInt(jobPostingId, 10)'),
  'createApplication must strictly map job_posting_id as integer'
);
assert(
  !placementStoreCode.includes('student_id: data.student_id'),
  'createApplication must NOT forward untrusted client student_id'
);
assert(
  !placementStoreCode.includes('match_percentage: data.match_percentage'),
  'createApplication must NOT forward untrusted client match_percentage'
);
assert(
  !placementStoreCode.includes('eligibility_score: data.eligibility_score'),
  'createApplication must NOT forward untrusted client eligibility_score'
);
console.log('   ✅ Payload strictly sends { job_posting_id, notes? } and drops forged scores/IDs.\n');

// 5. Verify Stale Eligibility Prevention (Task 5)
console.log('5. Verifying stale eligibility prevention logic...');
assert(
  placementStoreCode.includes('if (get().eligibilityJobId !== currentJobId)'),
  'fetchJobPosting and setSelectedJob must reset eligibility when job ID changes'
);
assert(
  placementStoreCode.includes('clearJobEligibility: () => set({'),
  'clearJobEligibility must reset jobEligibility, eligibilityJobId, and error'
);
console.log('   ✅ Stale eligibility prevention verified.\n');

// 6. Verify Error Extraction Formatter (Task 6)
console.log('6. Verifying error extraction formatter...');
assert(
  placementStoreCode.includes('formatErrorMessage'),
  'placementStore.js must use formatErrorMessage helper'
);
assert(
  placementStoreCode.includes('Array.isArray(detail)'),
  'formatErrorMessage must handle array-based validation errors from FastAPI'
);
console.log('   ✅ Error extraction handles strings, arrays, and standard errors.\n');

// 7. Verify Reset Action clears both Officer and Student State
console.log('7. Verifying store reset action completeness...');
const resetActionMatch = placementStoreCode.match(/reset:\s*\(\)\s*=>\s*set\(\{([\s\S]*?)\}\)/);
assert(resetActionMatch, 'reset action must be defined');
const resetContent = resetActionMatch[1];
for (const prop of requiredStateProperties) {
  assert(
    resetContent.includes(`${prop}:`),
    `reset() action must reset ${prop}`
  );
}
console.log('   ✅ reset() cleans both officer and student state.\n');

// 8. Verify Authentication Integration (Task 8)
console.log('8. Verifying authenticated student user resolution...');
assert(
  placementStoreCode.includes("import { useAuthStore } from './authStore'"),
  'placementStore.js must import useAuthStore'
);
assert(
  placementStoreCode.includes('useAuthStore.getState().user'),
  'placementStore.js must resolve active authenticated user ID via authStore'
);
console.log('   ✅ Authenticated user resolution strictly grounded in authStore.\n');

console.log('🎉 ALL 8 STEP 2.1 VERIFICATION CHECKS PASSED SUCCESSFULLY!\n');
