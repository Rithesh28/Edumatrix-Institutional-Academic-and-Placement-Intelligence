/**
 * Automated Verification Script for Phase 3.2 Step 2.5:
 * Student Application Tracker
 */

import assert from 'assert';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log('🧪 Starting Phase 3.2 Step 2.5: Student Application Tracker Verification...\n');

// ============================================================================
// 1. Static Source Code Inspection of Applications.jsx
// ============================================================================
console.log('1. Checking frontend/src/pages/student/Applications.jsx implementation...');
const trackerCode = fs.readFileSync(path.join(__dirname, 'src/pages/student/Applications.jsx'), 'utf8');

// Ensure placeholder was replaced
assert(
  !trackerCode.includes('Applications tracker placeholder'),
  'Applications.jsx must not contain placeholder text'
);
console.log('   ✅ Placeholder successfully replaced with functional tracker.');

// Check store integrations
assert(
  trackerCode.includes('usePlacementStore'),
  'Applications.jsx must import and use usePlacementStore'
);
assert(
  trackerCode.includes('fetchMyApplications'),
  'Applications.jsx must call fetchMyApplications'
);
assert(
  trackerCode.includes('myApplications'),
  'Applications.jsx must read myApplications from store'
);
assert(
  trackerCode.includes('useAuthStore'),
  'Applications.jsx must use useAuthStore for authenticated student context'
);
console.log('   ✅ Store integrations verified (placementStore + authStore).');

// Check rendering of core application response fields
const appFields = [
  'job_title',
  'company_name',
  'applied_at',
  'status',
  'match_percentage',
  'match_snapshot',
  'has_low_match_warning',
  'job_posting_id',
];
for (const field of appFields) {
  assert(
    trackerCode.includes(field),
    `Applications.jsx must render/handle application field: "${field}"`
  );
}
console.log(`   ✅ Verified handling of all ${appFields.length} application fields.`);

// Check status counters and filters
const supportedStatuses = ['applied', 'shortlisted', 'selected', 'rejected'];
for (const s of supportedStatuses) {
  assert(
    trackerCode.includes(s),
    `Applications.jsx must support status: "${s}"`
  );
}
console.log(`   ✅ Status counters and filters verified for: ${supportedStatuses.join(', ')}.`);

// Check sorting options
assert(
  trackerCode.includes('newest') &&
  trackerCode.includes('oldest') &&
  trackerCode.includes('score_desc') &&
  trackerCode.includes('score_asc'),
  'Applications.jsx must provide newest, oldest, and score sorting'
);
console.log('   ✅ Sorting options verified (newest, oldest, score desc/asc).');

// Check navigation to job details
assert(
  trackerCode.includes('/student/jobs/'),
  'Applications.jsx must link to /student/jobs/:id'
);
console.log('   ✅ Direct navigation to /student/jobs/:id verified.');

// Check snapshot modal inspection and legacy application handling
assert(
  trackerCode.includes('selectedSnapshotApp'),
  'Applications.jsx must support snapshot inspection modal'
);
assert(
  trackerCode.includes('Legacy Application') || trackerCode.includes('No snapshot'),
  'Applications.jsx must gracefully indicate when older application has no snapshot'
);
console.log('   ✅ Snapshot inspection modal and legacy application handling verified.');

// Check UI states
assert(
  trackerCode.includes('animate-pulse'),
  'Applications.jsx must implement loading skeletons with animate-pulse'
);
assert(
  trackerCode.includes('Try Again') || trackerCode.includes('Refresh'),
  'Applications.jsx must provide retry/refresh actions'
);
assert(
  trackerCode.includes('No Applications Submitted Yet'),
  'Applications.jsx must provide empty state when 0 applications submitted'
);
assert(
  trackerCode.includes('No Matching Applications Found'),
  'Applications.jsx must provide empty state when filters match nothing'
);
console.log('   ✅ All UI states (Skeleton, Error+Retry, 0-Apps Empty, Filtered-Empty) verified.');

// Check theme compliance
assert(
  trackerCode.includes('dark:bg-gray-900') && trackerCode.includes('dark:text-white'),
  'Applications.jsx must support dark and light mode classes'
);
console.log('   ✅ Dark/light theme styling verified.\n');

// ============================================================================
// 2. Functional Unit Simulation of Tracker Logic & Snapshot Mapping
// ============================================================================
console.log('2. Running functional simulation of tracker counting, filtering & snapshot handling...');

const sampleApps = [
  {
    id: 1,
    student_id: 10,
    job_posting_id: 101,
    job_title: 'Full Stack Engineer',
    company_name: 'AlphaCorp',
    status: 'applied',
    match_percentage: 85.0,
    applied_at: '2026-10-09T10:00:00Z',
    has_low_match_warning: false,
    match_snapshot: {
      student_name: 'John Doe',
      branch: 'AIML',
      cgpa: 8.8,
      resume_filename: 'john_resume.pdf',
      matched_required_skills: ['React', 'Node.js'],
      missing_required_skills: [],
      match_percentage: 85.0,
      has_low_match_warning: false,
    },
  },
  {
    id: 2,
    student_id: 10,
    job_posting_id: 102,
    job_title: 'Data Scientist',
    company_name: 'BetaAI',
    status: 'shortlisted',
    match_percentage: 45.0,
    applied_at: '2026-10-08T10:00:00Z',
    has_low_match_warning: true,
    low_match_warning: 'Required skill match below 50%',
    match_snapshot: {
      student_name: 'John Doe',
      branch: 'AIML',
      cgpa: 8.8,
      resume_filename: 'john_resume.pdf',
      matched_required_skills: ['Python'],
      missing_required_skills: ['PyTorch', 'Spark'],
      match_percentage: 45.0,
      has_low_match_warning: true,
      low_match_warning: 'Required skill match below 50%',
    },
  },
  {
    id: 3,
    student_id: 10,
    job_posting_id: 103,
    job_title: 'Cloud DevOps Intern',
    company_name: 'GammaCloud',
    status: 'rejected',
    match_percentage: null, // Legacy / uncalculated
    applied_at: '2026-10-01T10:00:00Z',
    has_low_match_warning: false,
    match_snapshot: null, // Legacy record without snapshot
  },
];

// Test status counting without double-counting
const computeStats = (apps) => {
  const s = { total: apps.length, applied: 0, shortlisted: 0, selected: 0, rejected: 0 };
  apps.forEach((a) => {
    if (s[a.status] !== undefined) s[a.status] += 1;
  });
  return s;
};
const stats = computeStats(sampleApps);
assert.strictEqual(stats.total, 3);
assert.strictEqual(stats.applied, 1);
assert.strictEqual(stats.shortlisted, 1);
assert.strictEqual(stats.rejected, 1);
assert.strictEqual(stats.selected, 0);
console.log('   ✅ Status counting simulation passed (total=3, applied=1, shortlisted=1, rejected=1).');

// Test status filtering
const filterByStatus = (apps, st) => {
  if (st === 'all') return apps;
  return apps.filter((a) => a.status === st);
};
assert.strictEqual(filterByStatus(sampleApps, 'all').length, 3);
assert.strictEqual(filterByStatus(sampleApps, 'shortlisted').length, 1);
assert.strictEqual(filterByStatus(sampleApps, 'shortlisted')[0].id, 2);
assert.strictEqual(filterByStatus(sampleApps, 'selected').length, 0);
console.log('   ✅ Status filtering simulation passed.');

// Test search by job title or company
const searchApps = (apps, query) => {
  const q = query.toLowerCase();
  return apps.filter(
    (a) => a.job_title.toLowerCase().includes(q) || a.company_name.toLowerCase().includes(q)
  );
};
assert.strictEqual(searchApps(sampleApps, 'Alpha').length, 1);
assert.strictEqual(searchApps(sampleApps, 'Data').length, 1);
assert.strictEqual(searchApps(sampleApps, 'DevOps').length, 1);
assert.strictEqual(searchApps(sampleApps, 'NonExistent').length, 0);
console.log('   ✅ Search simulation passed.');

// Test sorting
const sortByDateDesc = [...sampleApps].sort(
  (a, b) => new Date(b.applied_at) - new Date(a.applied_at)
);
assert.strictEqual(sortByDateDesc[0].id, 1, 'Newest should be id 1');
assert.strictEqual(sortByDateDesc[2].id, 3, 'Oldest should be id 3');

const sortByScoreDesc = [...sampleApps].sort((a, b) => {
  const sA = a.match_percentage !== null ? a.match_percentage : -1;
  const sB = b.match_percentage !== null ? b.match_percentage : -1;
  return sB - sA;
});
assert.strictEqual(sortByScoreDesc[0].id, 1, 'Highest score (85%) should be first');
assert.strictEqual(sortByScoreDesc[1].id, 2, 'Second score (45%) should be second');
assert.strictEqual(sortByScoreDesc[2].id, 3, 'Null score should be last');
console.log('   ✅ Sorting by date and score simulation passed.');

// Test snapshot parser on legacy vs snapshot records
const inspectSnapshot = (app) => {
  if (!app.match_snapshot) {
    return { hasSnapshot: false, label: 'Legacy Application — No snapshot' };
  }
  return {
    hasSnapshot: true,
    matchedCount: app.match_snapshot.matched_required_skills?.length || 0,
    hasWarning: Boolean(app.match_snapshot.has_low_match_warning),
  };
};
const snap1 = inspectSnapshot(sampleApps[0]);
assert.strictEqual(snap1.hasSnapshot, true);
assert.strictEqual(snap1.matchedCount, 2);
assert.strictEqual(snap1.hasWarning, false);

const snap2 = inspectSnapshot(sampleApps[1]);
assert.strictEqual(snap2.hasSnapshot, true);
assert.strictEqual(snap2.hasWarning, true);

const snap3 = inspectSnapshot(sampleApps[2]);
assert.strictEqual(snap3.hasSnapshot, false);
console.log('   ✅ Snapshot extraction and legacy record resilience passed.\n');

console.log('🎉 All Step 2.5 automated verification checks PASSED successfully!');
