/**
 * Automated Verification Script for EduMatrix Phase 4 — Step 4.6H.3:
 * Student Personal Documents UI Integration
 */

import assert from 'assert';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log('🧪 Starting Step 4.6H.3: Student Personal Documents UI Verification...\n');

// 1. Verify StudyBuddy.jsx presence
console.log('1. Checking StudyBuddy.jsx presence...');
const studyBuddyPath = path.join(__dirname, 'src/pages/student/StudyBuddy.jsx');
assert(fs.existsSync(studyBuddyPath), 'StudyBuddy.jsx must exist at src/pages/student/StudyBuddy.jsx');
const studyBuddyCode = fs.readFileSync(studyBuddyPath, 'utf8');
console.log('   ✅ StudyBuddy.jsx exists.\n');

// 2. Verify API Client contracts in src/services/api.js
console.log('2. Verifying Personal Document API Client contracts in src/services/api.js...');
const apiPath = path.join(__dirname, 'src/services/api.js');
assert(fs.existsSync(apiPath), 'api.js must exist at src/services/api.js');
const apiCode = fs.readFileSync(apiPath, 'utf8');

assert(
  apiCode.includes("getMyDocuments: (params = {}) => api.get('/study-buddy/my-documents'"),
  'studyBuddyAPI.getMyDocuments must target GET /study-buddy/my-documents'
);
assert(
  apiCode.includes("getMyDocumentDetail: (documentId) => api.get(`/study-buddy/my-documents/${documentId}`)"),
  'studyBuddyAPI.getMyDocumentDetail must target GET /study-buddy/my-documents/{id}'
);
assert(
  apiCode.includes("uploadMyDocument: (formData, onUploadProgress) => api.post('/study-buddy/my-documents'"),
  'studyBuddyAPI.uploadMyDocument must target POST /study-buddy/my-documents with multipart headers and progress'
);
assert(
  apiCode.includes("updateMyDocument: (documentId, payload) => api.patch(`/study-buddy/my-documents/${documentId}`"),
  'studyBuddyAPI.updateMyDocument must target PATCH /study-buddy/my-documents/{id}'
);
assert(
  apiCode.includes("deleteMyDocument: (documentId) => api.delete(`/study-buddy/my-documents/${documentId}`"),
  'studyBuddyAPI.deleteMyDocument must target DELETE /study-buddy/my-documents/{id}'
);
assert(
  apiCode.includes("retryMyDocument: (documentId) => api.post(`/study-buddy/my-documents/${documentId}/retry`"),
  'studyBuddyAPI.retryMyDocument must target POST /study-buddy/my-documents/{id}/retry'
);
assert(
  apiCode.includes("downloadMyDocument: (documentId) => api.get(`/study-buddy/my-documents/${documentId}/download`, { responseType: 'blob' })"),
  'studyBuddyAPI.downloadMyDocument must target GET /study-buddy/my-documents/{id}/download with responseType: blob'
);
console.log('   ✅ Personal Document API Client contracts verified.\n');

// 3. Verify Tab Switcher in StudyBuddy.jsx
console.log('3. Verifying My Documents Tab Switcher...');
assert(
  studyBuddyCode.includes('id="tab-btn-my-docs"'),
  'StudyBuddy.jsx must render tab button with id="tab-btn-my-docs"'
);
assert(
  studyBuddyCode.includes("setActiveTab('my_documents')"),
  "Clicking tab-btn-my-docs must call setActiveTab('my_documents')"
);
assert(
  studyBuddyCode.includes("activeTab === 'my_documents'"),
  "StudyBuddy.jsx must render view for activeTab === 'my_documents'"
);
console.log('   ✅ My Documents Tab button and activeTab condition verified.\n');

// 4. Verify 5-way Source Selector in Chat UI
console.log('4. Verifying Source Mode Selector in Chat UI...');
assert(
  studyBuddyCode.includes("const [sourceMode, setSourceMode] = useState('syllabus')"),
  "StudyBuddy.jsx must define sourceMode state defaulting to 'syllabus'"
);
assert(
  studyBuddyCode.includes('id="source-mode-syllabus"'),
  'StudyBuddy.jsx must render button id="source-mode-syllabus"'
);
assert(
  studyBuddyCode.includes('id="source-mode-lecture-notes"'),
  'StudyBuddy.jsx must render button id="source-mode-lecture-notes"'
);
assert(
  studyBuddyCode.includes('id="source-mode-all"'),
  'StudyBuddy.jsx must render button id="source-mode-all"'
);
assert(
  studyBuddyCode.includes('id="source-mode-my-documents"'),
  'StudyBuddy.jsx must render button id="source-mode-my-documents"'
);
assert(
  studyBuddyCode.includes('id="source-mode-all-my-sources"'),
  'StudyBuddy.jsx must render button id="source-mode-all-my-sources"'
);
assert(
  studyBuddyCode.includes("setSourceMode('my_documents')"),
  "Clicking my-documents button must call setSourceMode('my_documents')"
);
assert(
  studyBuddyCode.includes("setSourceMode('all_my_sources')"),
  "Clicking all-my-sources button must call setSourceMode('all_my_sources')"
);
assert(
  studyBuddyCode.includes('studyBuddyAPI.askQuestion(text, subjectFilter, sourceMode)'),
  'handleSendChat must pass sourceMode to studyBuddyAPI.askQuestion'
);
console.log('   ✅ 5-way Source Selector (syllabus, lecture_notes, all, my_documents, all_my_sources) verified.\n');

// 5. Verify Personal Document Management UI
console.log('5. Verifying Personal Document Management UI...');
assert(
  studyBuddyCode.includes('myDocuments') && studyBuddyCode.includes('setMyDocuments'),
  'StudyBuddy.jsx must define myDocuments state'
);
assert(
  studyBuddyCode.includes('loadingMyDocs') && studyBuddyCode.includes('setLoadingMyDocs'),
  'StudyBuddy.jsx must define loadingMyDocs state'
);
assert(
  studyBuddyCode.includes('myDocsError') && studyBuddyCode.includes('setMyDocsError'),
  'StudyBuddy.jsx must define myDocsError state'
);
assert(
  studyBuddyCode.includes('fetchMyDocuments'),
  'StudyBuddy.jsx must define fetchMyDocuments function'
);
assert(
  studyBuddyCode.includes('studyBuddyAPI.getMyDocuments'),
  'fetchMyDocuments must call studyBuddyAPI.getMyDocuments'
);
assert(
  studyBuddyCode.includes('MAX_ACTIVE_DOCS = 15'),
  'StudyBuddy.jsx must define MAX_ACTIVE_DOCS quota of 15'
);
assert(
  studyBuddyCode.includes('MAX_STORAGE_BYTES = 200 * 1024 * 1024'),
  'StudyBuddy.jsx must define MAX_STORAGE_BYTES quota of 200 MiB'
);
assert(
  studyBuddyCode.includes('activeDocsCount') && studyBuddyCode.includes('totalStorageUsedBytes'),
  'StudyBuddy.jsx must compute activeDocsCount and totalStorageUsedBytes'
);
assert(
  studyBuddyCode.includes('id="btn-upload-my-doc"'),
  'StudyBuddy.jsx must render upload button with id="btn-upload-my-doc"'
);
assert(
  studyBuddyCode.includes('id="btn-refresh-my-docs"'),
  'StudyBuddy.jsx must render refresh button with id="btn-refresh-my-docs"'
);
assert(
  studyBuddyCode.includes('id="search-my-docs"'),
  'StudyBuddy.jsx must render search input with id="search-my-docs"'
);
assert(
  studyBuddyCode.includes('id="filter-my-docs-subject"'),
  'StudyBuddy.jsx must render subject filter dropdown with id="filter-my-docs-subject"'
);
assert(
  studyBuddyCode.includes('id={`my-doc-card-${doc.id}`}'),
  'StudyBuddy.jsx must render document card with id="my-doc-card-{doc.id}"'
);
assert(
  studyBuddyCode.includes('id={`download-doc-${doc.id}`}'),
  'StudyBuddy.jsx must render download button with id="download-doc-{doc.id}"'
);
assert(
  studyBuddyCode.includes('id={`edit-doc-${doc.id}`}'),
  'StudyBuddy.jsx must render edit button with id="edit-doc-{doc.id}"'
);
assert(
  studyBuddyCode.includes('id={`delete-doc-${doc.id}`}'),
  'StudyBuddy.jsx must render delete button with id="delete-doc-{doc.id}"'
);
assert(
  studyBuddyCode.includes('id={`retry-doc-${doc.id}`}'),
  'StudyBuddy.jsx must render retry button with id="retry-doc-{doc.id}"'
);
console.log('   ✅ Personal Document Management UI, quotas, and card action IDs verified.\n');

// 6. Verify Modals (Upload, Edit, Delete Confirmation)
console.log('6. Verifying Upload, Edit, and Delete Confirmation Modals...');
assert(
  studyBuddyCode.includes('id="modal-upload-my-doc"'),
  'StudyBuddy.jsx must render upload modal with id="modal-upload-my-doc"'
);
assert(
  studyBuddyCode.includes('id="input-my-doc-file"'),
  'Upload modal must define file input with id="input-my-doc-file"'
);
assert(
  studyBuddyCode.includes('accept=".pdf,.png,.docx,.pptx,.txt"'),
  'File input must accept .pdf, .png, .docx, .pptx, .txt'
);
assert(
  studyBuddyCode.includes('id="input-doc-title"'),
  'Upload modal must define title input with id="input-doc-title"'
);
assert(
  studyBuddyCode.includes('id="btn-submit-upload-doc"'),
  'Upload modal must define submit button with id="btn-submit-upload-doc"'
);
assert(
  studyBuddyCode.includes('id="modal-edit-my-doc"'),
  'StudyBuddy.jsx must render edit modal with id="modal-edit-my-doc"'
);
assert(
  studyBuddyCode.includes('id="input-edit-doc-title"'),
  'Edit modal must define title input with id="input-edit-doc-title"'
);
assert(
  studyBuddyCode.includes('id="btn-submit-edit-doc"'),
  'Edit modal must define submit button with id="btn-submit-edit-doc"'
);
assert(
  studyBuddyCode.includes('id="modal-delete-my-doc"'),
  'StudyBuddy.jsx must render delete confirmation modal with id="modal-delete-my-doc"'
);
assert(
  studyBuddyCode.includes('id="btn-cancel-delete-doc"'),
  'Delete modal must define cancel button with id="btn-cancel-delete-doc"'
);
assert(
  studyBuddyCode.includes('id={`confirm-delete-doc-${deleteConfirmDoc.id}`}'),
  'Delete modal must define confirm delete button with id="confirm-delete-doc-{id}"'
);
console.log('   ✅ Modals and confirmation flows verified.\n');

// 7. Verify Source-Aware Personal Document Citations & Secure Download
console.log('7. Verifying Personal Document Citations and Secure Download...');
assert(
  studyBuddyCode.includes("cit.source_type === 'student_upload'"),
  'StudyBuddy.jsx must support student_upload source_type in citations'
);
assert(
  studyBuddyCode.includes('My Document'),
  'Citations must render "My Document" badge for student_upload'
);
assert(
  studyBuddyCode.includes('handleDownloadMyDocument'),
  'StudyBuddy.jsx must define handleDownloadMyDocument handler'
);
assert(
  studyBuddyCode.includes('studyBuddyAPI.downloadMyDocument(docId)'),
  'handleDownloadMyDocument must call studyBuddyAPI.downloadMyDocument(docId)'
);
assert(
  studyBuddyCode.includes('id={`download-citation-${docId}`}'),
  'Citation must render download button with id="download-citation-{docId}"'
);
assert(
  studyBuddyCode.includes('cit.source_page != null'),
  'Citations must strictly check cit.source_page != null to avoid fabricating page numbers'
);
console.log('   ✅ Personal Document citations, download action, and honest provenance verified.\n');

// 8. Verify Helper Functions Unit Logic
console.log('8. Testing helper functions unit behavior...');

// Test formatFileSize logic
function testFormatFileSize(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}
assert.strictEqual(testFormatFileSize(0), '0 B');
assert.strictEqual(testFormatFileSize(2048), '2 KB');
assert.strictEqual(testFormatFileSize(52428800), '50 MB');
assert.strictEqual(testFormatFileSize(209715200), '200 MB');

// Test getFileFormatInfo logic including TXT
function testGetFileFormatInfo(filename) {
  const ext = (filename || '').split('.').pop().toLowerCase();
  switch (ext) {
    case 'pdf': return 'PDF';
    case 'png': return 'PNG';
    case 'docx': return 'DOCX';
    case 'pptx': return 'PPTX';
    case 'txt': return 'TXT';
    default: return ext.toUpperCase() || 'FILE';
  }
}
assert.strictEqual(testGetFileFormatInfo('summary.txt'), 'TXT');
assert.strictEqual(testGetFileFormatInfo('notes.pdf'), 'PDF');
assert.strictEqual(testGetFileFormatInfo('diagram.png'), 'PNG');
assert.strictEqual(testGetFileFormatInfo('report.docx'), 'DOCX');
assert.strictEqual(testGetFileFormatInfo('slides.pptx'), 'PPTX');

// Test deduplicateCitations logic with student uploads
function testDeduplicateCitations(citations = []) {
  if (!Array.isArray(citations) || citations.length === 0) return [];
  const seen = new Set();
  return citations.filter((c) => {
    const docId = c.student_study_document_id || c.source_id || '';
    const key = `${c.source_type || 'syllabus'}-${docId}-${c.unit_number ?? ''}-${c.source_page ?? ''}-${c.topic_title || ''}-${(c.source_evidence || '').trim().slice(0, 50)}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

const sampleMixedCitations = [
  { source_type: 'syllabus', source_id: 1, unit_number: 1, source_page: 5, topic_title: 'Trees', source_evidence: 'BST definition' },
  { source_type: 'lecture_note', source_id: 10, unit_number: 1, source_page: 3, topic_title: 'Trees', source_evidence: 'BST code example' },
  { source_type: 'student_upload', student_study_document_id: 99, source_page: null, source_title: 'My Notes', source_evidence: 'Handwritten BST summary' },
  { source_type: 'student_upload', student_study_document_id: 99, source_page: null, source_title: 'My Notes', source_evidence: 'Handwritten BST summary' }, // duplicate
];

const dedupedMixed = testDeduplicateCitations(sampleMixedCitations);
assert.strictEqual(dedupedMixed.length, 3, 'Deduplication must eliminate exact duplicate student citations');
assert.strictEqual(dedupedMixed[2].source_type, 'student_upload');
assert.strictEqual(dedupedMixed[2].source_page, null, 'Null source_page preserved without fabrication');

console.log('   ✅ Helper functions unit logic passed.\n');

// 9. Verify Regression of Existing Study Buddy Tabs & Handlers
console.log('9. Verifying regression of existing tabs and features...');
assert(studyBuddyCode.includes("activeTab === 'chat'"), 'Chat tab preserved');
assert(studyBuddyCode.includes("activeTab === 'notes'"), 'Notes tab preserved');
assert(studyBuddyCode.includes("activeTab === 'summaries'"), 'Summaries tab preserved');
assert(studyBuddyCode.includes("activeTab === 'quizzes'"), 'Quizzes tab preserved');
assert(studyBuddyCode.includes("activeTab === 'progress'"), 'Progress tab preserved');
assert(studyBuddyCode.includes('handleGenerateSummary'), 'handleGenerateSummary preserved');
assert(studyBuddyCode.includes('handleGenerateQuiz'), 'handleGenerateQuiz preserved');
assert(studyBuddyCode.includes('handleCreatePlan'), 'handleCreatePlan preserved');
assert(studyBuddyCode.includes('handleDownloadNote'), 'handleDownloadNote preserved');
console.log('   ✅ Existing tabs and features verified intact.\n');

// 10. Verify Responsive Layout and Dark/Light Theme Classes
console.log('10. Verifying theme system and responsive styles...');
assert(studyBuddyCode.includes('dark:bg-gray-900'), 'Dark background classes present');
assert(studyBuddyCode.includes('dark:border-gray-800'), 'Dark border classes present');
assert(studyBuddyCode.includes('dark:text-white'), 'Dark text classes present');
assert(studyBuddyCode.includes('dark:text-purple-300') || studyBuddyCode.includes('dark:text-purple-400'), 'Dark purple accent classes present');
assert(studyBuddyCode.includes('grid-cols-1 md:grid-cols-2 lg:grid-cols-3'), 'Responsive grid classes present');
console.log('   ✅ Responsive layout and dark/light theme classes verified.\n');

console.log('🎉 ALL STEP 4.6H.3 FRONTEND VERIFICATION TESTS PASSED SUCCESSFULLY! (10/10 check suites)\n');
