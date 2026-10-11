/**
 * Automated Verification Script for Phase 3.3 Stage 3.3.5:
 * Placement Officer Recruitment Progression UI
 */

import assert from 'assert';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log('🧪 Starting Phase 3.3 Stage 3.3.5: Recruitment Progression UI Verification...\n');

// 1. Verify placementService.js exports & endpoint mappings
console.log('1. Checking placementService.js recruitment progression & offer APIs...');
const placementServiceCode = fs.readFileSync(path.join(__dirname, 'src/services/placementService.js'), 'utf8');

const expectedServices = [
  'getJobRounds',
  'createJobRound',
  'getRoundDetails',
  'getRoundOutcomes',
  'getStudentProgression',
  'correctRoundOutcome',
  'linkBatchToRound',
  'getVerifiedOffers',
  'getOfferDetails',
  'createVerifiedOffer',
  'updateVerifiedOffer',
  'rescindVerifiedOffer',
  'getPlacementAccounting',
];

for (const fn of expectedServices) {
  assert(
    placementServiceCode.includes(`export const ${fn} =`),
    `placementService.js must export function ${fn}`
  );
  console.log(`   ✅ Export ${fn} verified.`);
}

assert(
  placementServiceCode.includes("api.get(`/placement/jobs/${jobId}/rounds`)"),
  'getJobRounds must call GET /placement/jobs/:jobId/rounds'
);
assert(
  placementServiceCode.includes("api.post(`/placement/jobs/${jobId}/rounds`, data)"),
  'createJobRound must call POST /placement/jobs/:jobId/rounds'
);
assert(
  placementServiceCode.includes("api.get(`/placement/rounds/${roundId}/outcomes`"),
  'getRoundOutcomes must call GET /placement/rounds/:roundId/outcomes'
);
assert(
  placementServiceCode.includes("api.get(`/placement/students/${studentId}/progression`"),
  'getStudentProgression must call GET /placement/students/:studentId/progression'
);
assert(
  placementServiceCode.includes("api.post(`/placement/outcomes/${outcomeId}/correct`, data)"),
  'correctRoundOutcome must call POST /placement/outcomes/:outcomeId/correct'
);
assert(
  placementServiceCode.includes("api.post(`/placement/results/batches/${batchId}/link-round`"),
  'linkBatchToRound must call POST /placement/results/batches/:batchId/link-round'
);
assert(
  placementServiceCode.includes("api.get('/placement/offers'"),
  'getVerifiedOffers must call GET /placement/offers'
);
assert(
  placementServiceCode.includes("api.post('/placement/offers'"),
  'createVerifiedOffer must call POST /placement/offers'
);
assert(
  placementServiceCode.includes("api.post(`/placement/offers/${offerId}/rescind`"),
  'rescindVerifiedOffer must call POST /placement/offers/:offerId/rescind'
);
assert(
  placementServiceCode.includes("api.get('/placement/accounting')"),
  'getPlacementAccounting must call GET /placement/accounting'
);
console.log('   ✅ All progression and offer service endpoints correctly mapped.\n');

// 2. Verify placementStore.js state structure & actions
console.log('2. Checking placementStore.js state & action definitions...');
const placementStoreCode = fs.readFileSync(path.join(__dirname, 'src/store/placementStore.js'), 'utf8');

const expectedStateProps = [
  'jobRounds',
  'isRoundsLoading',
  'roundsError',
  'studentProgression',
  'isProgressionLoading',
  'progressionError',
  'verifiedOffers',
  'isOffersLoading',
  'offersError',
  'accountingStats',
];

for (const prop of expectedStateProps) {
  assert(
    placementStoreCode.includes(`${prop}:`),
    `placementStore.js must define state property: ${prop}`
  );
  console.log(`   ✅ State property ${prop} verified.`);
}

const expectedStoreActions = [
  'fetchJobRounds',
  'createJobRound',
  'fetchStudentProgression',
  'correctRoundOutcome',
  'linkBatchToRound',
  'fetchVerifiedOffers',
  'createVerifiedOffer',
  'updateVerifiedOffer',
  'rescindVerifiedOffer',
  'fetchPlacementAccounting',
];

for (const act of expectedStoreActions) {
  assert(
    placementStoreCode.includes(`${act}: async`),
    `placementStore.js must define action: ${act}`
  );
  console.log(`   ✅ Store action ${act} verified.`);
}
console.log('   ✅ All store actions and state properties verified.\n');

// 3. Verify RecruitmentRoundsTab component
console.log('3. Checking RecruitmentRoundsTab.jsx component logic...');
const roundsTabCode = fs.readFileSync(path.join(__dirname, 'src/components/placement/RecruitmentRoundsTab.jsx'), 'utf8');

assert(roundsTabCode.includes('RecruitmentRoundsTab'), 'RecruitmentRoundsTab component must be exported');
assert(roundsTabCode.includes('createJobRound'), 'Must call createJobRound');
assert(roundsTabCode.includes('round_number'), 'Must display and handle round_number');
assert(roundsTabCode.includes('is_final'), 'Must support is_final round flag');
assert(roundsTabCode.includes('positive integer') || roundsTabCode.includes('num <= 0'), 'Must validate positive round numbers');
console.log('   ✅ RecruitmentRoundsTab component structure and validation verified.\n');

// 4. Verify VerifiedOffersTab component
console.log('4. Checking VerifiedOffersTab.jsx component logic...');
const offersTabCode = fs.readFileSync(path.join(__dirname, 'src/components/placement/VerifiedOffersTab.jsx'), 'utf8');

assert(offersTabCode.includes('VerifiedOffersTab'), 'VerifiedOffersTab component must be exported');
assert(offersTabCode.includes('createVerifiedOffer'), 'Must call createVerifiedOffer');
assert(offersTabCode.includes('updateVerifiedOffer'), 'Must call updateVerifiedOffer');
assert(offersTabCode.includes('rescindVerifiedOffer'), 'Must call rescindVerifiedOffer');
assert(offersTabCode.includes('rescindReason') || offersTabCode.includes('rescission_reason'), 'Must enforce rescission reason');
assert(offersTabCode.includes('ctc') && offersTabCode.includes('designation'), 'Must include CTC and designation');
assert(offersTabCode.includes('offer_date'), 'Must include offer_date');
assert(offersTabCode.includes('isRescinding'), 'Must handle explicit confirmation and submission state for rescission');
console.log('   ✅ VerifiedOffersTab component structure and validation verified.\n');

// 5. Verify StudentProgressionModal component
console.log('5. Checking StudentProgressionModal.jsx component logic...');
const modalCode = fs.readFileSync(path.join(__dirname, 'src/components/placement/StudentProgressionModal.jsx'), 'utf8');

assert(modalCode.includes('StudentProgressionModal'), 'StudentProgressionModal component must be exported');
assert(modalCode.includes('fetchStudentProgression'), 'Must call fetchStudentProgression');
assert(modalCode.includes('correctRoundOutcome'), 'Must support audited outcome correction');
assert(modalCode.includes('CLEARED'), 'Must handle CLEARED outcome');
assert(modalCode.includes('SELECTED'), 'Must handle SELECTED outcome');
assert(modalCode.includes('REJECTED'), 'Must handle REJECTED outcome');
assert(modalCode.includes('ABSENT'), 'Must handle ABSENT outcome');
assert(modalCode.includes('ON_HOLD'), 'Must handle ON_HOLD outcome');
assert(
  modalCode.includes('verified offer') || modalCode.includes('Verified Offers'),
  'Must distinguish final round selection from verified offers'
);
console.log('   ✅ StudentProgressionModal component structure and ledger distinctions verified.\n');

// 6. Verify JobDetails.jsx tab integration
console.log('6. Checking JobDetails.jsx tab integration...');
const jobDetailsCode = fs.readFileSync(path.join(__dirname, 'src/pages/placement/JobDetails.jsx'), 'utf8');

assert(jobDetailsCode.includes('RecruitmentRoundsTab'), 'JobDetails must import and render RecruitmentRoundsTab');
assert(jobDetailsCode.includes('VerifiedOffersTab'), 'JobDetails must import and render VerifiedOffersTab');
assert(jobDetailsCode.includes('StudentProgressionModal'), 'JobDetails must import and render StudentProgressionModal');
assert(jobDetailsCode.includes("activeTab === 'rounds'"), 'JobDetails must support rounds tab');
assert(jobDetailsCode.includes("activeTab === 'offers'"), 'JobDetails must support offers tab');
assert(jobDetailsCode.includes("activeTab === 'applications'"), 'JobDetails must support applications tab');
assert(jobDetailsCode.includes('setProgressionModalStudent'), 'JobDetails applications list must have progression action');
console.log('   ✅ JobDetails.jsx tab integration verified.\n');

// 7. Verify Results.jsx round integration
console.log('7. Checking Results.jsx round integration...');
const resultsCode = fs.readFileSync(path.join(__dirname, 'src/pages/placement/Results.jsx'), 'utf8');

assert(resultsCode.includes('getJobRounds'), 'Results must fetch job rounds when job is selected');
assert(resultsCode.includes('availableRounds'), 'Results must maintain availableRounds state');
assert(resultsCode.includes('selectedRoundId'), 'Results must maintain selectedRoundId state');
assert(resultsCode.includes("formData.append('round_id'"), 'Results upload must pass round_id');
assert(resultsCode.includes('batch.round_id') || resultsCode.includes('batch.round_number'), 'Results batch card must show round badge');
console.log('   ✅ Results.jsx round upload integration verified.\n');

// 8. Verify ResultBatchDetails.jsx confirmation & match enforcement
console.log('8. Checking ResultBatchDetails.jsx match enforcement & confirmation summary...');
const batchDetailsCode = fs.readFileSync(path.join(__dirname, 'src/pages/placement/ResultBatchDetails.jsx'), 'utf8');

assert(
  batchDetailsCode.includes('unresolved') && batchDetailsCode.includes('matched_student_id'),
  'Must validate that all candidate identities are matched or ignored before confirmation'
);
assert(batchDetailsCode.includes('linkBatchToRound'), 'Must support linking batch to authoritative round');
assert(batchDetailsCode.includes('showLinkRoundModal'), 'Must provide link round modal');
assert(
  batchDetailsCode.includes('Verified Offers') || batchDetailsCode.includes('does NOT automatically issue'),
  'Confirmation modal must remind officer that final selection does not auto-create verified offers'
);
console.log('   ✅ ResultBatchDetails.jsx match enforcement and confirmation summary verified.\n');

// 9. Verify StudentProfile.jsx progression & offers cards
console.log('9. Checking StudentProfile.jsx progression & verified offers display...');
const profileCode = fs.readFileSync(path.join(__dirname, 'src/pages/placement/StudentProfile.jsx'), 'utf8');

assert(profileCode.includes('getStudentProgression'), 'StudentProfile must fetch progression');
assert(profileCode.includes('getVerifiedOffers'), 'StudentProfile must fetch verified offers');
assert(profileCode.includes('Verified Placement Offers'), 'Must display verified placement offers card');
assert(profileCode.includes('Recruitment Round Progression History'), 'Must display round progression history card');
assert(profileCode.includes('StudentProgressionModal'), 'Must render StudentProgressionModal for full interactive timeline');
console.log('   ✅ StudentProfile.jsx progression & verified offers display verified.\n');

console.log('🎉 ALL STAGE 3.3.5 FRONTEND VERIFICATIONS PASSED!\n');
