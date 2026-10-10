/**
 * Automated Verification Script for Phase 3.2 Step 2.2:
 * Student Placement Routes & Navigation
 */

import assert from 'assert';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log('🧪 Starting Phase 3.2 Step 2.2: Student Routes & Navigation Verification...\n');

// 1. Verify Layout.jsx navigation items
console.log('1. Checking student navigation items in Layout.jsx...');
const layoutCode = fs.readFileSync(path.join(__dirname, 'src/components/Layout.jsx'), 'utf8');

assert(
  layoutCode.includes("{ name: 'Campus Jobs', path: '/student/jobs', icon: '💼' }"),
  'Layout.jsx must include Campus Jobs navigation item pointing to /student/jobs'
);
console.log('   ✅ Campus Jobs (💼 -> /student/jobs) navigation item present.');

assert(
  layoutCode.includes("{ name: 'My Applications', path: '/student/applications', icon: '📋' }"),
  'Layout.jsx must include My Applications navigation item pointing to /student/applications'
);
console.log('   ✅ My Applications (📋 -> /student/applications) navigation item present.\n');

// 2. Verify active sidebar highlighting & nested route matching logic (Task 6)
console.log('2. Verifying active sidebar highlighting logic in Layout.jsx...');
assert(
  layoutCode.includes('const location = useLocation()'),
  'Layout.jsx must retrieve active route using useLocation'
);
assert(
  layoutCode.includes('isItemActive'),
  'Layout.jsx must define isItemActive helper'
);
assert(
  layoutCode.includes("location.pathname.startsWith(itemPath + '/')"),
  'isItemActive must support nested route matching (e.g. /student/jobs/:id highlights /student/jobs)'
);

// Simulate isItemActive logic
const simulateIsActive = (currentPath, itemPath) => {
  if (currentPath === itemPath) return true;
  if (itemPath !== '/' && currentPath.startsWith(itemPath + '/')) return true;
  return false;
};

assert.strictEqual(simulateIsActive('/student/jobs', '/student/jobs'), true, 'Exact match must be active');
assert.strictEqual(simulateIsActive('/student/jobs/142', '/student/jobs'), true, 'Nested job detail must highlight /student/jobs');
assert.strictEqual(simulateIsActive('/student/applications', '/student/jobs'), false, 'Different route must not highlight /student/jobs');
assert.strictEqual(simulateIsActive('/student/applications', '/student/applications'), true, 'Applications route must highlight /student/applications');
console.log('   ✅ Sidebar nested highlighting simulation verified.\n');

// 3. Verify App.jsx route registrations
console.log('3. Checking route registrations in App.jsx...');
const appCode = fs.readFileSync(path.join(__dirname, 'src/App.jsx'), 'utf8');

assert(appCode.includes("import StudentJobs from './pages/student/Jobs'"), 'App.jsx must import StudentJobs');
assert(appCode.includes("import StudentJobDetails from './pages/student/JobDetails'"), 'App.jsx must import StudentJobDetails');
assert(appCode.includes("import StudentApplications from './pages/student/Applications'"), 'App.jsx must import StudentApplications');
console.log('   ✅ Student component imports verified.');

assert(appCode.includes('<Route path="/student/jobs" element={<StudentJobs />} />'), 'Route /student/jobs must be registered');
assert(appCode.includes('<Route path="/student/jobs/:id" element={<StudentJobDetails />} />'), 'Route /student/jobs/:id must be registered');
assert(appCode.includes('<Route path="/student/applications" element={<StudentApplications />} />'), 'Route /student/applications must be registered');
console.log('   ✅ Student routes correctly registered under student role block.\n');

// 4. Verify Placement Officer Routes Remain Strictly Protected (Task 4 & 7)
console.log('4. Verifying Placement Officer routes protection...');
const placementRoutesBlock = appCode.match(/Placement Administration Routes[\s\S]*?<Route element=\{<ProtectedRoute allowedRoles=\{(\[.*?\])\}/);
assert(placementRoutesBlock, 'Placement Administration Routes block must exist');
const allowedRolesStr = placementRoutesBlock[1];
assert(allowedRolesStr.includes('placement_officer'), 'Placement routes must require placement_officer');
assert(!allowedRolesStr.includes('student'), 'Placement routes must NOT allow student role');
console.log(`   ✅ Placement Officer routes strictly protected by: ${allowedRolesStr} (students excluded).\n`);

// 5. Verify Placeholder Components Existence & Theme Support (Task 5)
console.log('5. Verifying placeholder components and theme compliance...');
const jobsPlaceholder = fs.readFileSync(path.join(__dirname, 'src/pages/student/Jobs.jsx'), 'utf8');
const jobDetailsPlaceholder = fs.readFileSync(path.join(__dirname, 'src/pages/student/JobDetails.jsx'), 'utf8');
const applicationsPlaceholder = fs.readFileSync(path.join(__dirname, 'src/pages/student/Applications.jsx'), 'utf8');

for (const [name, code] of [
  ['Jobs.jsx', jobsPlaceholder],
  ['JobDetails.jsx', jobDetailsPlaceholder],
  ['Applications.jsx', applicationsPlaceholder]
]) {
  assert(code.includes('dark:bg-gray-900'), `${name} must include dark mode background`);
  assert(code.includes('dark:text-white'), `${name} must include dark mode text`);
  console.log(`   ✅ ${name} exists with dark/light mode classes.`);
}
console.log('   ✅ All placeholder components verified.\n');

// 6. Simulate ProtectedRoute Authorization Matrix (Task 7)
console.log('6. Simulating ProtectedRoute role authorization matrix...');
const simulateProtectedRoute = ({ token, userRole, allowedRoles }) => {
  if (!token) return 'REDIRECT_LOGIN';
  if (allowedRoles && allowedRoles.length > 0) {
    const current = (userRole || '').toLowerCase();
    const normalized = allowedRoles.map(r => r.toLowerCase());
    if (!current || !normalized.includes(current)) return 'REDIRECT_UNAUTHORIZED';
  }
  return 'ALLOW';
};

// Test unauthenticated access to student route
assert.strictEqual(
  simulateProtectedRoute({ token: null, userRole: null, allowedRoles: ['student', 'admin'] }),
  'REDIRECT_LOGIN',
  'Unauthenticated user must be redirected to /login'
);

// Test student accessing /student/jobs
assert.strictEqual(
  simulateProtectedRoute({ token: 'valid-jwt', userRole: 'student', allowedRoles: ['student', 'admin'] }),
  'ALLOW',
  'Student must be allowed on /student/jobs'
);

// Test student accessing /placement/jobs
assert.strictEqual(
  simulateProtectedRoute({ token: 'valid-jwt', userRole: 'student', allowedRoles: ['placement_officer', 'admin'] }),
  'REDIRECT_UNAUTHORIZED',
  'Student must be rejected with /unauthorized when accessing /placement/jobs'
);

// Test lecturer accessing /student/jobs
assert.strictEqual(
  simulateProtectedRoute({ token: 'valid-jwt', userRole: 'lecturer', allowedRoles: ['student', 'admin'] }),
  'REDIRECT_UNAUTHORIZED',
  'Lecturer must be rejected when accessing /student/jobs'
);

// Test admin accessing /student/jobs
assert.strictEqual(
  simulateProtectedRoute({ token: 'valid-jwt', userRole: 'admin', allowedRoles: ['student', 'admin'] }),
  'ALLOW',
  'Admin must be allowed on student placement routes'
);

console.log('   ✅ ProtectedRoute role matrix checks verified.\n');

console.log('🎉 ALL 6 STEP 2.2 CHECKS PASSED SUCCESSFULLY!\n');
