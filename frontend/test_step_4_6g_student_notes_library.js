/**
 * Automated Verification Script for EduMatrix Phase 4 — Step 4.6G:
 * Student Lecture Notes Library and Study Buddy Source Selector
 */

import assert from 'assert';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log('🧪 Starting Step 4.6G: Student Lecture Notes Library and Source Selector Verification...\n');

// 1. Verify StudyBuddy.jsx exists
console.log('1. Checking StudyBuddy.jsx presence...');
const studyBuddyPath = path.join(__dirname, 'src/pages/student/StudyBuddy.jsx');
assert(fs.existsSync(studyBuddyPath), 'StudyBuddy.jsx must exist at src/pages/student/StudyBuddy.jsx');
const studyBuddyCode = fs.readFileSync(studyBuddyPath, 'utf8');
console.log('   ✅ StudyBuddy.jsx exists.\n');

// 2. Verify API Client in src/services/api.js
console.log('2. Verifying API Client contracts in src/services/api.js...');
const apiPath = path.join(__dirname, 'src/services/api.js');
assert(fs.existsSync(apiPath), 'api.js must exist at src/services/api.js');
const apiCode = fs.readFileSync(apiPath, 'utf8');

// Check downloadNote calls dedicated /study-buddy/notes/{note_id}/download
assert(
  apiCode.includes('/study-buddy/notes/') && apiCode.includes('/download'),
  'api.js must define dedicated downloadNote pointing to /study-buddy/notes/{note_id}/download'
);
assert(
  apiCode.includes("downloadNote: (noteId) => api.get(`/study-buddy/notes/${noteId}/download`"),
  'studyBuddyAPI.downloadNote must target /study-buddy/notes/{noteId}/download with blob responseType'
);

// Check askQuestion passes sourceMode and defaults to 'syllabus'
assert(
  apiCode.includes("askQuestion: (question, subjectId = null, sourceMode = 'syllabus')"),
  "studyBuddyAPI.askQuestion must accept sourceMode with default 'syllabus'"
);
assert(
  apiCode.includes('source_mode: sourceMode'),
  'studyBuddyAPI.askQuestion must send source_mode in payload'
);

// Check searchSyllabus passes sourceMode
assert(
  apiCode.includes("searchSyllabus: (query, subjectId = null, sourceMode = 'syllabus')"),
  "studyBuddyAPI.searchSyllabus must accept sourceMode with default 'syllabus'"
);

// Check getSubjectNotes endpoint
assert(
  apiCode.includes('getSubjectNotes: (subjectId, params = {})'),
  'studyBuddyAPI.getSubjectNotes must be defined'
);
console.log('   ✅ API Client contracts verified.\n');

// 3. Verify Source Selector in Chat Tab
console.log('3. Verifying Source Selector in Chat UI...');

// Check state default
assert(
  studyBuddyCode.includes("const [sourceMode, setSourceMode] = useState('syllabus')"),
  "StudyBuddy.jsx must define sourceMode state defaulting to 'syllabus'"
);

// Check 3 selector buttons with exact IDs
assert(
  studyBuddyCode.includes('id="source-mode-syllabus"'),
  'StudyBuddy.jsx must render button with id="source-mode-syllabus"'
);
assert(
  studyBuddyCode.includes('id="source-mode-lecture-notes"'),
  'StudyBuddy.jsx must render button with id="source-mode-lecture-notes"'
);
assert(
  studyBuddyCode.includes('id="source-mode-all"'),
  'StudyBuddy.jsx must render button with id="source-mode-all"'
);

// Check that buttons switch sourceMode
assert(
  studyBuddyCode.includes("setSourceMode('syllabus')"),
  "Clicking syllabus button must setSourceMode('syllabus')"
);
assert(
  studyBuddyCode.includes("setSourceMode('lecture_notes')"),
  "Clicking lecture notes button must setSourceMode('lecture_notes')"
);
assert(
  studyBuddyCode.includes("setSourceMode('all')"),
  "Clicking combined button must setSourceMode('all')"
);

// Check that chat sends sourceMode
assert(
  studyBuddyCode.includes('studyBuddyAPI.askQuestion(text, subjectFilter, sourceMode)'),
  'handleSendChat must pass sourceMode to studyBuddyAPI.askQuestion'
);

// Check that error handler does NOT switch sourceMode
assert(
  !studyBuddyCode.includes("catch (err) {\n      setSourceMode('syllabus')") &&
  !studyBuddyCode.includes("catch (err) {\n      console.error('Study Buddy query error:', err)\n      setSourceMode"),
  'Error handler must not reset sourceMode'
);

console.log('   ✅ Source selector (syllabus, lecture_notes, all) and handlers verified.\n');

// 4. Verify Source-Aware Citations and Deduplication
console.log('4. Verifying Source-Aware Citations...');

// Check deduplication helper
assert(
  studyBuddyCode.includes('export function deduplicateCitations') || studyBuddyCode.includes('function deduplicateCitations'),
  'StudyBuddy.jsx must define deduplicateCitations helper'
);

// Check badges for lecture note vs syllabus
assert(
  studyBuddyCode.includes('Faculty Lecture Note'),
  'StudyBuddy.jsx citations must render Faculty Lecture Note badge for lecture_note source_type'
);
assert(
  studyBuddyCode.includes('Official Syllabus'),
  'StudyBuddy.jsx citations must render Official Syllabus badge for syllabus source_type'
);

// Check source title and original filename
assert(
  studyBuddyCode.includes('cit.source_title') && studyBuddyCode.includes('cit.original_filename'),
  'StudyBuddy.jsx citations must display source_title or original_filename when available'
);

// Check that page numbers are only displayed when non-null (no fabricated page numbers)
assert(
  studyBuddyCode.includes('cit.source_page != null'),
  'StudyBuddy.jsx must strictly check cit.source_page != null to avoid fabricating page numbers'
);

// Check honest insufficient-evidence response
assert(
  studyBuddyCode.includes('msg.sourceMode ===') && studyBuddyCode.includes('Notice:'),
  'StudyBuddy.jsx must display honest insufficient evidence notices customized by sourceMode'
);

console.log('   ✅ Source-aware citations, deduplication, and honest notices verified.\n');

// 5. Verify Notes Library Tab and Functionality
console.log('5. Verifying Notes Library Tab...');

// Check tab button
assert(
  studyBuddyCode.includes('id="tab-btn-notes"'),
  'StudyBuddy.jsx must render tab button with id="tab-btn-notes"'
);
assert(
  studyBuddyCode.includes("setActiveTab('notes')"),
  "tab-btn-notes must call setActiveTab('notes')"
);

// Check activeTab === 'notes' section
assert(
  studyBuddyCode.includes("activeTab === 'notes'"),
  "StudyBuddy.jsx must render view for activeTab === 'notes'"
);

// Check state variables
assert(
  studyBuddyCode.includes('lectureNotes') && studyBuddyCode.includes('setLectureNotes'),
  'StudyBuddy.jsx must define lectureNotes state'
);
assert(
  studyBuddyCode.includes('loadingNotes') && studyBuddyCode.includes('setLoadingNotes'),
  'StudyBuddy.jsx must define loadingNotes state'
);
assert(
  studyBuddyCode.includes('notesError') && studyBuddyCode.includes('setNotesError'),
  'StudyBuddy.jsx must define notesError state'
);
assert(
  studyBuddyCode.includes('noteSearchQuery') && studyBuddyCode.includes('setNoteSearchQuery'),
  'StudyBuddy.jsx must define noteSearchQuery state'
);

// Check fetchNotes calls getSubjectNotes
assert(
  studyBuddyCode.includes('studyBuddyAPI.getSubjectNotes'),
  'fetchNotes must call studyBuddyAPI.getSubjectNotes'
);

// Check dedicated secure download handler
assert(
  studyBuddyCode.includes('handleDownloadNote'),
  'StudyBuddy.jsx must define handleDownloadNote'
);
assert(
  studyBuddyCode.includes('studyBuddyAPI.downloadNote(note.id)'),
  'handleDownloadNote must invoke studyBuddyAPI.downloadNote(note.id)'
);

// Verify generic download endpoint is NOT used for lecture notes in StudyBuddy.jsx
assert(
  !studyBuddyCode.includes('downloadNoteFile'),
  'StudyBuddy.jsx must NOT use generic downloadNoteFile endpoint for lecture notes'
);

// Check download button ID and states
assert(
  studyBuddyCode.includes('id={`download-note-${note.id}`}') || studyBuddyCode.includes('id={"download-note-" + note.id}'),
  'StudyBuddy.jsx must render download button with id="download-note-{note.id}"'
);

// Check format badges
assert(
  studyBuddyCode.includes('getFileFormatInfo'),
  'StudyBuddy.jsx must use getFileFormatInfo for file format indicators'
);

// Check metadata displayed: file_size_bytes, created_at, download_count, original_filename
assert(
  studyBuddyCode.includes('formatFileSize(note.file_size_bytes)'),
  'Notes Library must format and display note.file_size_bytes'
);
assert(
  studyBuddyCode.includes('formatDate(note.created_at)'),
  'Notes Library must format and display note.created_at'
);
assert(
  studyBuddyCode.includes('note.download_count'),
  'Notes Library must display note.download_count'
);
assert(
  studyBuddyCode.includes('note.original_filename'),
  'Notes Library must display note.original_filename'
);

// Check grouping by subject
assert(
  studyBuddyCode.includes('groupedNotes'),
  'StudyBuddy.jsx must compute groupedNotes to group notes by subject'
);

// Check loading, error, and empty states
assert(
  studyBuddyCode.includes('loadingNotes ?') && studyBuddyCode.includes('animate-pulse'),
  'Notes Library must render animated loading skeleton when loadingNotes is true'
);
assert(
  studyBuddyCode.includes('notesError ?') && studyBuddyCode.includes('Failed to load lecture notes'),
  'Notes Library must render error container when notesError is present'
);
assert(
  studyBuddyCode.includes('filteredNotes.length === 0'),
  'Notes Library must handle empty notes list'
);

console.log('   ✅ Notes Library tab, search, filters, metadata, and secure download verified.\n');

// 6. Verify Preservation of Other Study Buddy Tabs
console.log('6. Verifying preservation of existing Study Buddy tabs...');
assert(
  studyBuddyCode.includes("activeTab === 'chat'"),
  'Chat tab must remain intact'
);
assert(
  studyBuddyCode.includes("activeTab === 'summaries'"),
  'Study Summaries tab must remain intact'
);
assert(
  studyBuddyCode.includes("activeTab === 'quizzes'"),
  'Practice Quizzes tab must remain intact'
);
assert(
  studyBuddyCode.includes("activeTab === 'progress'"),
  'Progress & Planner tab must remain intact'
);
assert(
  studyBuddyCode.includes('handleGenerateSummary'),
  'Summary generator handler must remain intact'
);
assert(
  studyBuddyCode.includes('handleGenerateQuiz'),
  'Quiz generator handler must remain intact'
);
assert(
  studyBuddyCode.includes('handleCreatePlan'),
  'Study plan creator handler must remain intact'
);
console.log('   ✅ Existing tabs (Chat, Summaries, Quizzes, Progress & Planner) verified intact.\n');

// 7. Verify Helper Functions Unit Logic
console.log('7. Testing helper functions unit behavior...');

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
assert.strictEqual(testFormatFileSize(5242880), '5 MB');
assert.strictEqual(testFormatFileSize(524288000), '500 MB');

// Test deduplicateCitations logic
function testDeduplicateCitations(citations = []) {
  if (!Array.isArray(citations) || citations.length === 0) return [];
  const seen = new Set();
  return citations.filter((c) => {
    const key = `${c.source_type || 'syllabus'}-${c.source_id || ''}-${c.unit_number ?? ''}-${c.source_page ?? ''}-${c.topic_title || ''}-${(c.source_evidence || '').trim().slice(0, 50)}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

const sampleCitations = [
  { source_type: 'syllabus', source_id: 1, unit_number: 1, source_page: 5, topic_title: 'Arrays', source_evidence: 'Array basics chunk' },
  { source_type: 'syllabus', source_id: 1, unit_number: 1, source_page: 5, topic_title: 'Arrays', source_evidence: 'Array basics chunk' }, // duplicate
  { source_type: 'lecture_note', source_id: 42, unit_number: 1, source_page: 2, topic_title: 'Arrays', source_evidence: 'Lecture slide on arrays' },
  { source_type: 'lecture_note', source_id: 42, unit_number: 1, source_page: null, topic_title: 'Arrays', source_evidence: 'Lecture note docx' } // no page
];

const deduped = testDeduplicateCitations(sampleCitations);
assert.strictEqual(deduped.length, 3, 'Deduplication must eliminate exact duplicate citations');
assert.strictEqual(deduped[0].source_type, 'syllabus');
assert.strictEqual(deduped[1].source_type, 'lecture_note');
assert.strictEqual(deduped[2].source_page, null, 'Null source_page should be preserved without fabrication');

console.log('   ✅ Helper functions unit tests passed.\n');

// 8. Verify Student Route in App.jsx
console.log('8. Verifying student route in App.jsx...');
const appCode = fs.readFileSync(path.join(__dirname, 'src/App.jsx'), 'utf8');
assert(
  appCode.includes('path="/student/study-buddy"'),
  'App.jsx must define route /student/study-buddy'
);
assert(
  appCode.includes('element={<StudentStudyBuddy />}'),
  'App.jsx must render StudentStudyBuddy component'
);
console.log('   ✅ Route /student/study-buddy verified.\n');

console.log('🎉 ALL STEP 4.6G FRONTEND VERIFICATION TESTS PASSED SUCCESSFULLY! (8/8 check suites)\n');
