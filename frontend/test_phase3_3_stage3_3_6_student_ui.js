/**
 * Automated Verification Script for Phase 3.3 Stage 3.3.6:
 * Student Recruitment Timeline and Verified Offer Response UI
 */

import assert from 'assert';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log('🧪 Starting Phase 3.3 Stage 3.3.6: Student UI Verification...\n');

// =============================================================================
// 1. VERIFY placementService.js EXPORTS & ENDPOINTS
// =============================================================================
console.log('1. Checking placementService.js student offer and progression endpoints...');
const placementServiceCode = fs.readFileSync(path.join(__dirname, 'src/services/placementService.js'), 'utf8');

const expectedServices = [
  'getMyOffers',
  'respondToOffer',
  'getStudentProgression',
  'getVerifiedOffers',
  'getOfferDetails',
];

for (const fn of expectedServices) {
  assert(
    placementServiceCode.includes(`export const ${fn} =`),
    `placementService.js must export function ${fn}`
  );
  console.log(`   ✅ Export ${fn} verified.`);
}

assert(
  placementServiceCode.includes("api.get('/placement/offers/my-offers')"),
  'getMyOffers must call GET /placement/offers/my-offers'
);
assert(
  placementServiceCode.includes("api.post(`/placement/offers/${offerId}/respond`, data)"),
  'respondToOffer must call POST /placement/offers/:offerId/respond'
);
assert(
  placementServiceCode.includes("api.get(`/placement/students/${studentId}/progression`"),
  'getStudentProgression must call GET /placement/students/:studentId/progression'
);
console.log('   ✅ All student offer and progression service endpoints correctly mapped.\n');

// =============================================================================
// 2. VERIFY placementStore.js STATE & ACTIONS
// =============================================================================
console.log('2. Checking placementStore.js student offer state & actions...');
const placementStoreCode = fs.readFileSync(path.join(__dirname, 'src/store/placementStore.js'), 'utf8');

const expectedStateProps = [
  'myOffers',
  'isMyOffersLoading',
  'myOffersError',
  'isRespondingOffer',
  'respondOfferError',
  'studentProgression',
  'isProgressionLoading',
];

for (const prop of expectedStateProps) {
  assert(
    placementStoreCode.includes(`${prop}:`),
    `placementStore.js must declare state property ${prop}`
  );
  console.log(`   ✅ State property ${prop} verified.`);
}

const expectedActions = [
  'fetchMyOffers',
  'respondToOffer',
  'fetchStudentProgression',
];

for (const act of expectedActions) {
  assert(
    placementStoreCode.includes(`${act}: async`),
    `placementStore.js must define async action ${act}`
  );
  console.log(`   ✅ Action ${act} verified.`);
}

// Verify server-side identity & response payload rules
assert(
  !placementStoreCode.includes('student_id: authUser.id') &&
  !placementStoreCode.includes('data.student_id'),
  'respondToOffer must NOT inject client-side student_id into response payload (backend uses authenticated session)'
);
console.log('   ✅ Server-side identity enforcement verified in placementStore.js.\n');

// =============================================================================
// 3. VERIFY StudentVerifiedOfferCard.jsx COMPONENT
// =============================================================================
console.log('3. Checking StudentVerifiedOfferCard.jsx component architecture...');
const offerCardCode = fs.readFileSync(
  path.join(__dirname, 'src/components/placement/StudentVerifiedOfferCard.jsx'),
  'utf8'
);

assert(offerCardCode.includes('StudentVerifiedOfferCard'), 'Must export StudentVerifiedOfferCard component');

// Verify key fields displayed
assert(offerCardCode.includes('offer.company_name'), 'Must display company name');
assert(offerCardCode.includes('offer.designation'), 'Must display designation');
assert(offerCardCode.includes('formatCTC'), 'Must format verified CTC');
assert(offerCardCode.includes('offer.offer_date'), 'Must display offer date');
assert(offerCardCode.includes('offer.response_date'), 'Must display student response date when present');

// Verify status badge handling
assert(offerCardCode.includes("'offered'"), 'Must handle OFFERED status');
assert(offerCardCode.includes("'accepted'"), 'Must handle ACCEPTED status');
assert(offerCardCode.includes("'declined'"), 'Must handle DECLINED status');
assert(offerCardCode.includes("'rescinded'"), 'Must handle RESCINDED status');

// Verify rescinded offer safe presentation
assert(
  offerCardCode.includes('isRescinded') &&
  offerCardCode.includes('rescission_reason'),
  'Must display rescinded status and reason safely without presenting offer as active'
);

// Verify authorized offer letter download link
assert(
  offerCardCode.includes('/files/${offer.offer_letter_file_id}/download') ||
  offerCardCode.includes('offer_letter_file_id'),
  'Must provide link to authorized offer letter document'
);

// Verify Accept and Decline actions only for OFFERED state
assert(
  offerCardCode.includes('isOfferedPending &&') || offerCardCode.includes("status === 'offered'"),
  'Accept and Decline action buttons must only appear for pending OFFERED status'
);
assert(
  offerCardCode.includes('handleOpenConfirm') && offerCardCode.includes('Confirm Offer Acceptance'),
  'Must require explicit confirmation modal before accepting offer'
);
assert(
  offerCardCode.includes('Confirm Declining Offer'),
  'Must require explicit confirmation modal before declining offer'
);
assert(
  offerCardCode.includes('isSubmitting') && offerCardCode.includes('disabled={isSubmitting}'),
  'Must disable buttons and show loading state to prevent duplicate submissions'
);

// Verify no student edit controls for terms
assert(
  !offerCardCode.includes('name="ctc_lpa"') &&
  !offerCardCode.includes('name="designation"') &&
  !offerCardCode.includes('name="company_name"'),
  'Student must not have input controls to edit CTC, designation, or company terms'
);
console.log('   ✅ StudentVerifiedOfferCard.jsx terms, status badges, actions, and safety guards verified.\n');

// =============================================================================
// 4. VERIFY StudentRecruitmentTimeline.jsx COMPONENT
// =============================================================================
console.log('4. Checking StudentRecruitmentTimeline.jsx component architecture...');
const timelineCode = fs.readFileSync(
  path.join(__dirname, 'src/components/placement/StudentRecruitmentTimeline.jsx'),
  'utf8'
);

assert(timelineCode.includes('StudentRecruitmentTimeline'), 'Must export StudentRecruitmentTimeline component');

// Verify chronological ordering
assert(
  timelineCode.includes('round_number') && timelineCode.includes('.sort('),
  'Must sort rounds chronologically/numerically by round_number'
);

// Verify round outcomes
assert(timelineCode.includes("'cleared'"), 'Must support CLEARED outcome');
assert(timelineCode.includes("'selected'"), 'Must support SELECTED outcome');
assert(timelineCode.includes("'rejected'"), 'Must support REJECTED outcome');
assert(timelineCode.includes("'on_hold'"), 'Must support ON_HOLD outcome');
assert(timelineCode.includes("'absent'"), 'Must support ABSENT outcome');

// Verify distinction between process selection and formal verified offer
assert(
  timelineCode.includes('Recruitment Milestones vs. Formal Offers') ||
  timelineCode.includes('Process Selection Recorded'),
  'Must explicitly explain that interview round selection does not equal a verified offer'
);

// Verify linked offer display
assert(
  timelineCode.includes('item.has_offer') && timelineCode.includes('Verified Placement Offer Issued!'),
  'Must display linked verified offer badge when an offer has been issued'
);

// Verify graceful handling of empty and inline modes
assert(
  timelineCode.includes('No Round Progression Outcomes Recorded Yet'),
  'Must handle empty/legacy application progression gracefully'
);
assert(
  timelineCode.includes('inline'),
  'Must support inline presentation mode for tab/accordion embedding'
);
console.log('   ✅ StudentRecruitmentTimeline.jsx ordering, outcomes, selection distinctions verified.\n');

// =============================================================================
// 5. VERIFY Applications.jsx INTEGRATION
// =============================================================================
console.log('5. Checking student Applications.jsx integration...');
const applicationsCode = fs.readFileSync(
  path.join(__dirname, 'src/pages/student/Applications.jsx'),
  'utf8'
);

assert(
  applicationsCode.includes('StudentVerifiedOfferCard'),
  'Applications.jsx must import and use StudentVerifiedOfferCard'
);
assert(
  applicationsCode.includes('StudentRecruitmentTimeline'),
  'Applications.jsx must import and use StudentRecruitmentTimeline'
);
assert(
  applicationsCode.includes('fetchMyOffers'),
  'Applications.jsx must fetch student verified offers'
);
assert(
  applicationsCode.includes('Verified Placement Offers'),
  'Applications.jsx must render Verified Placement Offers section'
);
assert(
  applicationsCode.includes('Recruitment Timeline'),
  'Applications.jsx application card must have Recruitment Timeline action'
);
console.log('   ✅ Applications.jsx offers banner and progression timeline modal verified.\n');

// =============================================================================
// 6. VERIFY JobDetails.jsx INTEGRATION
// =============================================================================
console.log('6. Checking student JobDetails.jsx integration...');
const jobDetailsCode = fs.readFileSync(
  path.join(__dirname, 'src/pages/student/JobDetails.jsx'),
  'utf8'
);

assert(
  jobDetailsCode.includes('StudentVerifiedOfferCard'),
  'JobDetails.jsx must import StudentVerifiedOfferCard'
);
assert(
  jobDetailsCode.includes('StudentRecruitmentTimeline'),
  'JobDetails.jsx must import StudentRecruitmentTimeline'
);
assert(
  jobDetailsCode.includes('jobVerifiedOffer'),
  'JobDetails.jsx must match verified offer for the viewed job'
);
assert(
  jobDetailsCode.includes('Recruitment Timeline'),
  'JobDetails.jsx must offer Recruitment Timeline button when student has applied'
);
console.log('   ✅ JobDetails.jsx offer card and timeline modal verified.\n');

// =============================================================================
// 7. VERIFY Profile.jsx INTEGRATION
// =============================================================================
console.log('7. Checking student Profile.jsx integration...');
const profileCode = fs.readFileSync(
  path.join(__dirname, 'src/pages/student/Profile.jsx'),
  'utf8'
);

assert(
  profileCode.includes("id: 'placement'") && profileCode.includes('Offers & Progression'),
  'Profile.jsx must include Offers & Progression tab'
);
assert(
  profileCode.includes('StudentVerifiedOfferCard'),
  'Profile.jsx must render StudentVerifiedOfferCard'
);
assert(
  profileCode.includes('StudentRecruitmentTimeline'),
  'Profile.jsx must render StudentRecruitmentTimeline'
);
assert(
  profileCode.includes('Placement Status:'),
  'Profile.jsx must display authoritative placement status badge'
);
console.log('   ✅ Profile.jsx Offers & Progression tab verified.\n');

console.log('🎉 Phase 3.3 Stage 3.3.6: All Student UI verification checks passed successfully!\n');
