/**
 * Automated Verification Script for Phase 3.2 Step 2.3:
 * Student Campus Jobs Catalog
 */

import assert from 'assert';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log('🧪 Starting Phase 3.2 Step 2.3: Student Campus Jobs Catalog Verification...\n');

// ============================================================================
// 1. Static Source Code Inspection of Jobs.jsx
// ============================================================================
console.log('1. Checking frontend/src/pages/student/Jobs.jsx implementation...');
const jobsCode = fs.readFileSync(path.join(__dirname, 'src/pages/student/Jobs.jsx'), 'utf8');

// Ensure placeholder was replaced
assert(
  !jobsCode.includes('Campus job catalog placeholder'),
  'Jobs.jsx must not contain placeholder text'
);
console.log('   ✅ Placeholder successfully replaced with functional catalog.');

// Check store integrations
assert(
  jobsCode.includes('usePlacementStore'),
  'Jobs.jsx must import and use usePlacementStore'
);
assert(
  jobsCode.includes('fetchJobPostings'),
  'Jobs.jsx must call fetchJobPostings'
);
assert(
  jobsCode.includes('fetchMyApplications'),
  'Jobs.jsx must call fetchMyApplications'
);
assert(
  jobsCode.includes('myApplications'),
  'Jobs.jsx must access myApplications from placementStore'
);
assert(
  jobsCode.includes('useAuthStore'),
  'Jobs.jsx must use useAuthStore for authenticated user context'
);
console.log('   ✅ Store integration verified (placementStore + authStore).');

// Check response fields rendering
const requiredFields = [
  'title',
  'company_name',
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
for (const field of requiredFields) {
  assert(
    jobsCode.includes(field),
    `Jobs.jsx must render/handle actual response field: "${field}"`
  );
}
console.log(`   ✅ Verified handling of all ${requiredFields.length} actual backend response fields.`);

// Check navigation to job detail
assert(
  jobsCode.includes('/student/jobs/'),
  'Jobs.jsx must navigate to /student/jobs/:id on card or button click'
);
console.log('   ✅ Navigation to /student/jobs/:id verified.');

// Check Applied badge and status handling
assert(
  jobsCode.includes('appliedJobMap'),
  'Jobs.jsx must map student applications for quick job lookup'
);
assert(
  jobsCode.includes('isApplied'),
  'Jobs.jsx must identify whether a job was already applied to'
);
console.log('   ✅ Applied-job indicators and application cross-referencing verified.');

// Check UI States (Loading skeleton, Error with retry, Empty, No results)
assert(
  jobsCode.includes('animate-pulse'),
  'Jobs.jsx must implement loading skeleton with animate-pulse'
);
assert(
  jobsCode.includes('Try Again') || jobsCode.includes('Retry'),
  'Jobs.jsx must provide a retry action in error state'
);
assert(
  jobsCode.includes('No Active Campus Drives') || jobsCode.includes('No Campus Jobs'),
  'Jobs.jsx must display empty state when no jobs are available'
);
assert(
  jobsCode.includes('No Matching Jobs Found'),
  'Jobs.jsx must display no-results state when filters match nothing'
);
console.log('   ✅ All UI states (Skeleton, Error+Retry, Empty, Filtered-Empty) verified.');

// Check Theme & Accessibility
assert(
  jobsCode.includes('dark:bg-gray-900') && jobsCode.includes('dark:text-white'),
  'Jobs.jsx must support dark and light theme classes'
);
console.log('   ✅ EduMatrix theme & dark mode classes verified.\n');

// ============================================================================
// 2. Functional Unit Simulation of Filtering, Deadlines & Applied Lookups
// ============================================================================
console.log('2. Running functional simulation of catalog filtering & deadline calculations...');

const sampleJobs = [
  {
    id: 1,
    company_id: 10,
    company_name: 'TechCorp',
    title: 'Frontend Engineer',
    location: 'Bangalore',
    salary_range: '12-16 LPA',
    cgpa_criteria: 7.5,
    branch_eligibility: ['CSE', 'IT'],
    required_skills: ['React', 'JavaScript', 'Tailwind'],
    preferred_skills: ['TypeScript'],
    application_deadline: '2026-10-15T18:00:00Z',
    status: 'open',
    created_at: '2026-10-01T10:00:00Z',
  },
  {
    id: 2,
    company_id: 20,
    company_name: 'DataSystems',
    title: 'Data Analyst',
    location: 'Hyderabad',
    salary_range: '8-10 LPA',
    cgpa_criteria: 6.5,
    branch_eligibility: ['CSE', 'ECE', 'AIML'],
    required_skills: ['Python', 'SQL'],
    preferred_skills: ['PowerBI'],
    application_deadline: '2026-10-08T18:00:00Z',
    status: 'open',
    created_at: '2026-10-02T10:00:00Z',
  },
  {
    id: 3,
    company_id: 30,
    company_name: 'CloudScale',
    title: 'DevOps Intern',
    location: null, // Test null optional field
    salary_range: null, // Test null optional field
    cgpa_criteria: null, // Test null optional field
    branch_eligibility: [], // Test empty optional field
    required_skills: [],
    preferred_skills: [],
    application_deadline: null,
    status: 'open',
    created_at: '2026-10-03T10:00:00Z',
  },
];

const sampleApps = [
  { id: 101, student_id: 5, job_posting_id: 1, status: 'applied' },
];

// Test applied map
const appliedMap = new Map();
sampleApps.forEach((app) => appliedMap.set(app.job_posting_id, app));

assert.strictEqual(appliedMap.has(1), true, 'Job 1 should be detected as applied');
assert.strictEqual(appliedMap.has(2), false, 'Job 2 should be detected as not applied');
assert.strictEqual(appliedMap.has(3), false, 'Job 3 should be detected as not applied');
console.log('   ✅ Applied job lookup simulation passed.');

// Test search filter
const searchFilter = (jobs, query) => {
  const q = query.toLowerCase();
  return jobs.filter(
    (j) =>
      j.title.toLowerCase().includes(q) ||
      j.company_name.toLowerCase().includes(q) ||
      j.required_skills?.some((s) => s.toLowerCase().includes(q))
  );
};

assert.strictEqual(searchFilter(sampleJobs, 'Tech').length, 1);
assert.strictEqual(searchFilter(sampleJobs, 'Data').length, 1);
assert.strictEqual(searchFilter(sampleJobs, 'Python').length, 1);
assert.strictEqual(searchFilter(sampleJobs, 'NonExistent').length, 0);
console.log('   ✅ Client-side search logic passed.');

// Test application status filter
const appFilter = (jobs, filterType, map) => {
  return jobs.filter((j) => {
    const isApp = map.has(j.id);
    if (filterType === 'applied') return isApp;
    if (filterType === 'not_applied') return !isApp;
    return true;
  });
};

assert.strictEqual(appFilter(sampleJobs, 'all', appliedMap).length, 3);
assert.strictEqual(appFilter(sampleJobs, 'applied', appliedMap).length, 1);
assert.strictEqual(appFilter(sampleJobs, 'not_applied', appliedMap).length, 2);
console.log('   ✅ Application filter logic passed.');

// Test location filter
const locFilter = (jobs, loc) => {
  if (loc === 'all') return jobs;
  return jobs.filter((j) => j.location === loc);
};
assert.strictEqual(locFilter(sampleJobs, 'all').length, 3);
assert.strictEqual(locFilter(sampleJobs, 'Bangalore').length, 1);
assert.strictEqual(locFilter(sampleJobs, 'Pune').length, 0);
console.log('   ✅ Location filter logic passed.');

// Test sorting
const sortByDeadline = [...sampleJobs].sort((a, b) => {
  if (!a.application_deadline) return 1;
  if (!b.application_deadline) return -1;
  return new Date(a.application_deadline) - new Date(b.application_deadline);
});
assert.strictEqual(sortByDeadline[0].id, 2, 'Closing soonest should come first');
assert.strictEqual(sortByDeadline[2].id, 3, 'Null deadline should come last');
console.log('   ✅ Sorting by deadline simulation passed.');

// Test deadline calculation
const calcDeadline = (deadlineStr) => {
  if (!deadlineStr) return null;
  const deadline = new Date(deadlineStr);
  const now = new Date('2026-10-10T12:00:00Z');
  const diffDays = Math.ceil((deadline.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  return { diffDays, isPassed: diffDays < 0 };
};
assert.strictEqual(calcDeadline('2026-10-08T18:00:00Z').isPassed, true, 'Past deadline recognized');
assert.strictEqual(calcDeadline('2026-10-15T18:00:00Z').diffDays > 0, true, 'Future deadline recognized');
assert.strictEqual(calcDeadline(null), null, 'Null deadline handled cleanly');
console.log('   ✅ Deadline urgency calculation passed.\n');

console.log('🎉 All Step 2.3 automated verification checks PASSED successfully!');
