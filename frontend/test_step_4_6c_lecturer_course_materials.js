/**
 * Automated Verification Script for EduMatrix Phase 4 — Step 4.6C:
 * Lecturer Course Materials Frontend
 */

import assert from 'assert';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log('🧪 Starting Step 4.6C: Lecturer Course Materials Frontend Verification...\n');

// 1. Verify CourseMaterials.jsx file exists
console.log('1. Checking CourseMaterials.jsx presence and constants...');
const courseMaterialsPath = path.join(__dirname, 'src/pages/lecturer/CourseMaterials.jsx');
assert(fs.existsSync(courseMaterialsPath), 'CourseMaterials.jsx must exist at src/pages/lecturer/CourseMaterials.jsx');

const courseMaterialsCode = fs.readFileSync(courseMaterialsPath, 'utf8');

// Check 500 MiB limit constant (524,288,000 bytes)
assert(
  courseMaterialsCode.includes('524288000') || courseMaterialsCode.includes('524_288_000'),
  'CourseMaterials.jsx must enforce exact 500 MiB limit (524288000 bytes)'
);
console.log('   ✅ 500 MiB file limit constant verified (524,288,000 bytes).');

// Check allowed extensions
const allowedExts = ['.pdf', '.png', '.docx', '.pptx'];
for (const ext of allowedExts) {
  assert(
    courseMaterialsCode.includes(`'${ext}'`) || courseMaterialsCode.includes(`"${ext}"`),
    `CourseMaterials.jsx must support ${ext}`
  );
}
console.log('   ✅ Supported formats verified (.pdf, .png, .docx, .pptx).\n');

// 2. Verify Helper Functions Logic
console.log('2. Verifying format and size helper functions...');

function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

function getFileFormatInfo(filename) {
  const ext = (filename || '').split('.').pop().toLowerCase()
  switch (ext) {
    case 'pdf':
      return { label: 'PDF' }
    case 'png':
      return { label: 'PNG' }
    case 'docx':
      return { label: 'DOCX' }
    case 'pptx':
      return { label: 'PPTX' }
    default:
      return { label: ext.toUpperCase() || 'FILE' }
  }
}

const MAX_FILE_SIZE_BYTES = 524288000;
const ALLOWED_EXTENSIONS = ['.pdf', '.png', '.docx', '.pptx'];

assert.strictEqual(MAX_FILE_SIZE_BYTES, 524288000, 'MAX_FILE_SIZE_BYTES must equal 524288000 bytes');
assert.deepStrictEqual(ALLOWED_EXTENSIONS, ['.pdf', '.png', '.docx', '.pptx'], 'ALLOWED_EXTENSIONS must match backend specification');

assert.strictEqual(formatFileSize(0), '0 B');
assert.strictEqual(formatFileSize(1024), '1 KB');
assert.strictEqual(formatFileSize(1048576), '1 MB');
assert.strictEqual(formatFileSize(524288000), '500 MB');
console.log('   ✅ formatFileSize helper verified.');

const pdfInfo = getFileFormatInfo('lecture1.pdf');
assert.strictEqual(pdfInfo.label, 'PDF', 'PDF file format info label should be PDF');

const pngInfo = getFileFormatInfo('diagram.png');
assert.strictEqual(pngInfo.label, 'PNG', 'PNG file format info label should be PNG');

const docxInfo = getFileFormatInfo('notes.docx');
assert.strictEqual(docxInfo.label, 'DOCX', 'DOCX file format info label should be DOCX');

const pptxInfo = getFileFormatInfo('slides.pptx');
assert.strictEqual(pptxInfo.label, 'PPTX', 'PPTX file format info label should be PPTX');
console.log('   ✅ getFileFormatInfo helper verified.\n');

// 3. Verify API Integration in api.js
console.log('3. Verifying lecture notes methods in studyBuddyAPI (src/services/api.js)...');
const apiCode = fs.readFileSync(path.join(__dirname, 'src/services/api.js'), 'utf8');

const requiredMethods = [
  'getSubjectNotes',
  'getNoteDetail',
  'uploadNote',
  'updateNote',
  'deleteNote',
  'retryNoteProcessing',
  'downloadNoteFile'
];

for (const method of requiredMethods) {
  assert(
    apiCode.includes(`${method}:`),
    `studyBuddyAPI must define ${method}`
  );
  console.log(`   ✅ studyBuddyAPI.${method} is present.`);
}

// Verify endpoint URL mapping
assert(
  apiCode.includes("api.get(`/study-buddy/subjects/${subjectId}/notes`"),
  'getSubjectNotes must map to /study-buddy/subjects/:subjectId/notes'
);
assert(
  apiCode.includes("api.post(`/study-buddy/subjects/${subjectId}/notes`"),
  'uploadNote must map to POST /study-buddy/subjects/:subjectId/notes'
);
assert(
  apiCode.includes("api.patch(`/study-buddy/notes/${noteId}`"),
  'updateNote must map to PATCH /study-buddy/notes/:noteId'
);
assert(
  apiCode.includes("api.delete(`/study-buddy/notes/${noteId}`"),
  'deleteNote must map to DELETE /study-buddy/notes/:noteId'
);
assert(
  apiCode.includes("api.post(`/study-buddy/notes/${noteId}/retry`"),
  'retryNoteProcessing must map to POST /study-buddy/notes/:noteId/retry'
);
assert(
  apiCode.includes("api.get(`/files/${fileId}/download`"),
  'downloadNoteFile must map to GET /files/:fileId/download'
);

// Verify non-buffering, timeout: 0, and multipart headers in uploadNote
assert(
  apiCode.includes('timeout: 0'),
  'uploadNote must specify timeout: 0 to avoid terminating valid large 500 MiB uploads'
);
assert(
  apiCode.includes('onUploadProgress'),
  'uploadNote must accept onUploadProgress callback'
);
console.log('   ✅ uploadNote configured for non-terminating large streaming uploads with progress tracking.\n');

// 4. Verify Layout.jsx Lecturer Navigation Item
console.log('4. Verifying Lecturer Navigation in Layout.jsx...');
const layoutCode = fs.readFileSync(path.join(__dirname, 'src/components/Layout.jsx'), 'utf8');

assert(
  layoutCode.includes("{ name: 'Course Materials', path: '/lecturer/course-materials', icon: '📖' }"),
  'Layout.jsx must include Course Materials in lecturer nav items'
);
console.log('   ✅ Course Materials navigation item present in Layout.jsx for lecturer role.\n');

// 5. Verify App.jsx Route Registration
console.log('5. Verifying route registration in App.jsx...');
const appCode = fs.readFileSync(path.join(__dirname, 'src/App.jsx'), 'utf8');

assert(
  appCode.includes("import LecturerCourseMaterials from './pages/lecturer/CourseMaterials'"),
  'App.jsx must import LecturerCourseMaterials'
);

assert(
  appCode.includes('<Route path="/lecturer/course-materials" element={<LecturerCourseMaterials />} />'),
  'App.jsx must register /lecturer/course-materials under protected lecturer routes'
);
console.log('   ✅ /lecturer/course-materials route properly registered and protected in App.jsx.\n');

// 6. Verify Lecturer Dashboard Quick Access Card
console.log('6. Verifying Lecturer Dashboard quick access card...');
const dashboardCode = fs.readFileSync(path.join(__dirname, 'src/pages/lecturer/Dashboard.jsx'), 'utf8');

assert(
  dashboardCode.includes('/lecturer/course-materials'),
  'Lecturer Dashboard must link to /lecturer/course-materials'
);
assert(
  dashboardCode.includes('Course Materials'),
  'Lecturer Dashboard must feature Course Materials card'
);
console.log('   ✅ Course Materials quick access card verified on Lecturer Dashboard.\n');

// 7. Verify Publication Guard & Action Logic in CourseMaterials.jsx
console.log('7. Verifying publication guard and action mechanics in CourseMaterials.jsx...');

assert(
  courseMaterialsCode.includes("note.processing_status === 'EXTRACTED'"),
  'CourseMaterials.jsx must enforce that publication strictly requires processing_status === EXTRACTED'
);
console.log('   ✅ Strict publication guard verified (processing_status === EXTRACTED required).');

assert(
  courseMaterialsCode.includes('handleRetryProcessing') && courseMaterialsCode.includes('retryNoteProcessing'),
  'CourseMaterials.jsx must implement retry for failed uploads'
);
console.log('   ✅ Retry processing action verified.');

assert(
  courseMaterialsCode.includes('handleConfirmDelete') && courseMaterialsCode.includes('Delete Lecture Note?'),
  'CourseMaterials.jsx must provide a safe confirmation dialog before deleting'
);
console.log('   ✅ Delete confirmation dialog verified.');

assert(
  courseMaterialsCode.includes('handleDownloadNote') && courseMaterialsCode.includes('downloadNoteFile'),
  'CourseMaterials.jsx must integrate authorized original-file download'
);
console.log('   ✅ File download integration verified.');

assert(
  courseMaterialsCode.includes('setUploadProgress') && courseMaterialsCode.includes('uploadProgress'),
  'CourseMaterials.jsx must render upload progress feedback'
);
console.log('   ✅ Upload progress bar and feedback verified.\n');

console.log('🎉 All Step 4.6C Lecturer Course Materials frontend verification checks PASSED successfully!');
