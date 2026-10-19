import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Building2,
  Calendar,
  Briefcase,
  Paperclip,
  Upload,
  Trash2,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  GraduationCap,
  FileText,
  Users,
  Check,
  X,
  RefreshCw,
  Send,
  Eye,
  FileSpreadsheet,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import {
  parseShortlist,
  createAndPostDrive,
  getCircularAttachmentPreviewUrl,
  getCircularAttachmentDownloadUrl,
} from '../../services/placementService';
import toast from 'react-hot-toast';

const AVAILABLE_BRANCHES = [
  'Computer Science (CSE)',
  'Information Technology (IT)',
  'Electronics & Communication (ECE)',
  'Electrical & Electronics (EEE)',
  'Mechanical Engineering (MECH)',
  'Civil Engineering (CIVIL)',
  'AI & Machine Learning (AIML)',
  'Data Science (AIDS)',
];

const CircularForm = () => {
  const { id } = useParams();
  const isEditMode = Boolean(id);
  const navigate = useNavigate();

  const {
    companies,
    fetchCompanies,
    jobs,
    fetchJobPostings,
    fetchCircular,
    updateCircular,
  } = usePlacementStore();

  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(isEditMode);

  // Business Form Fields (strictly the 6 required fields)
  // 1. Company (required)
  const [companyId, setCompanyId] = useState('');
  // 2. File attachments (uploaded shortlist / circular docs)
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [uploadedAttachments, setUploadedAttachments] = useState([]);
  // 3. Description (auto-extracted, editable)
  const [description, setDescription] = useState('');
  // 4. Branch eligibility (multi-select)
  const [selectedBranches, setSelectedBranches] = useState([]);
  // 5. Linked job roles (multi-select for selected company)
  const [selectedJobIds, setSelectedJobIds] = useState([]);
  // 6. Drive date (optional)
  const [driveDate, setDriveDate] = useState('');

  // Optional circular title (for edit mode or custom override)
  const [title, setTitle] = useState('');

  // Shortlist Extraction & Candidate Review State
  const [isParsing, setIsParsing] = useState(false);
  const [parseStatus, setParseStatus] = useState(null); // { message, error }
  const [candidates, setCandidates] = useState([]);
  const [candidateSummary, setCandidateSummary] = useState(null);
  const [candidateFilter, setCandidateFilter] = useState('all'); // 'all' | 'confirmed' | 'ambiguous' | 'duplicate' | 'unmatched'

  // Initial data loading
  useEffect(() => {
    const init = async () => {
      try {
        await Promise.all([fetchCompanies(), fetchJobPostings()]);

        if (isEditMode) {
          const circ = await fetchCircular(id);
          setCompanyId(String(circ.company_id));
          setTitle(circ.title || '');
          setDescription(circ.summary || circ.instructions || '');
          if (circ.drive_date) {
            setDriveDate(new Date(circ.drive_date).toISOString().slice(0, 16));
          }
          setSelectedBranches(circ.branch_eligibility || []);
          setSelectedJobIds((circ.linked_jobs || []).map((j) => j.job_posting_id));
          setUploadedAttachments(
            (circ.attachments || []).map((att) => ({
              file_id: att.file_id,
              filename: att.filename,
              id: att.id,
            }))
          );
        }
      } catch (err) {
        toast.error('Failed to load required recruitment data.');
      } finally {
        setInitialLoading(false);
      }
    };
    init();
  }, [id, isEditMode, fetchCompanies, fetchJobPostings, fetchCircular]);

  // Jobs belonging exclusively to the selected company
  const availableCompanyJobs = useMemo(() => {
    if (!companyId) return [];
    return jobs.filter((j) => String(j.company_id) === String(companyId));
  }, [jobs, companyId]);

  // Selected company object
  const selectedCompany = useMemo(() => {
    return companies.find((c) => String(c.id) === String(companyId));
  }, [companies, companyId]);

  // Handle local file selection
  const handleFileChange = (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setSelectedFiles((prev) => [...prev, ...files]);
  };

  const handleRemoveLocalFile = (index) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  // Trigger Shortlist & Candidate Extraction
  const handleExtractShortlist = async () => {
    if (!selectedFiles.length) {
      toast.error('Please select at least one document to extract.');
      return;
    }

    setIsParsing(true);
    setParseStatus(null);
    try {
      const formData = new FormData();
      selectedFiles.forEach((file) => {
        formData.append('files', file);
      });
      if (companyId) {
        formData.append('company_id', companyId);
      }

      const result = await parseShortlist(formData);

      // Auto-populate description if currently empty or confirm update
      if (!description || description.trim() === '') {
        setDescription(result.description || '');
      } else {
        toast((t) => (
          <div className="flex flex-col gap-2 text-xs">
            <span className="font-semibold">Extracted content ready!</span>
            <span>Would you like to replace your description with the extracted content?</span>
            <div className="flex gap-2 mt-1">
              <button
                onClick={() => {
                  setDescription(result.description || '');
                  toast.dismiss(t.id);
                }}
                className="px-2 py-1 bg-indigo-600 text-white rounded font-medium cursor-pointer"
              >
                Replace
              </button>
              <button
                onClick={() => toast.dismiss(t.id)}
                className="px-2 py-1 bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded cursor-pointer"
              >
                Keep Current
              </button>
            </div>
          </div>
        ), { duration: 8000 });
      }

      setCandidates(result.candidates || []);
      setCandidateSummary(result.candidate_summary || null);
      setUploadedAttachments(result.attachment_files || []);
      setParseStatus({
        message: `Extracted ${result.candidates?.length || 0} candidate(s) across ${selectedFiles.length} file(s). Review matches below.`,
        error: false,
      });
      toast.success('Document extraction and candidate matching complete!');
    } catch (err) {
      const errMsg = err.response?.data?.detail || err.message || 'Failed to extract shortlist documents.';
      setParseStatus({ message: errMsg, error: true });
      toast.error(errMsg);
    } finally {
      setIsParsing(false);
    }
  };

  // Toggle branch selection
  const handleToggleBranch = (branch) => {
    setSelectedBranches((prev) =>
      prev.includes(branch) ? prev.filter((b) => b !== branch) : [...prev, branch]
    );
  };

  const handleSelectAllBranches = () => {
    setSelectedBranches([...AVAILABLE_BRANCHES]);
  };

  const handleClearBranches = () => {
    setSelectedBranches([]);
  };

  // Toggle linked job role
  const handleToggleJob = (jobId) => {
    setSelectedJobIds((prev) =>
      prev.includes(jobId) ? prev.filter((id) => id !== jobId) : [...prev, jobId]
    );
  };

  // Candidate Match Action Handlers
  const handleConfirmCandidate = (rowIndex) => {
    setCandidates((prev) =>
      prev.map((c) =>
        c.row_index === rowIndex
          ? { ...c, is_confirmed: true }
          : c
      )
    );
  };

  const handleExcludeCandidate = (rowIndex) => {
    setCandidates((prev) =>
      prev.map((c) =>
        c.row_index === rowIndex
          ? { ...c, is_confirmed: false }
          : c
      )
    );
  };

  const handleConfirmAllMatched = () => {
    setCandidates((prev) =>
      prev.map((c) =>
        c.matched_student_id && !c.is_duplicate
          ? { ...c, is_confirmed: true }
          : c
      )
    );
    toast.success('Confirmed all non-duplicate matched candidates.');
  };

  const handleExcludeAllAmbiguous = () => {
    setCandidates((prev) =>
      prev.map((c) =>
        c.review_status === 'ambiguous' || c.is_duplicate || !c.matched_student_id
          ? { ...c, is_confirmed: false }
          : c
      )
    );
    toast.success('Excluded all ambiguous and duplicate entries.');
  };

  // Filtered candidate list for review table
  const filteredCandidates = useMemo(() => {
    return candidates.filter((c) => {
      if (candidateFilter === 'confirmed') return c.is_confirmed;
      if (candidateFilter === 'ambiguous') return c.review_status === 'ambiguous';
      if (candidateFilter === 'duplicate') return c.is_duplicate;
      if (candidateFilter === 'unmatched') return c.review_status === 'unmatched';
      return true;
    });
  }, [candidates, candidateFilter]);

  // Confirmed recipients count
  const confirmedCount = useMemo(() => {
    return candidates.filter((c) => c.is_confirmed && c.matched_student_id).length;
  }, [candidates]);

  // Submission / Posting
  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!companyId) {
      toast.error('Please select a company for this recruitment drive.');
      return;
    }
    if (!description || description.trim() === '') {
      toast.error('Please provide a description or extract content from uploaded documents.');
      return;
    }

    setLoading(true);
    try {
      if (isEditMode) {
        // Standard edit mode update
        await updateCircular(id, {
          company_id: parseInt(companyId, 10),
          title: title.trim() || undefined,
          summary: description.trim(),
          drive_date: driveDate ? new Date(driveDate).toISOString() : null,
          branch_eligibility: selectedBranches,
        });
        toast.success('Recruitment drive updated successfully.');
        navigate(`/placement/circulars/${id}`);
      } else {
        // Redesigned Create & Post Drive workflow
        const payload = {
          company_id: parseInt(companyId, 10),
          title: title.trim() || undefined,
          description: description.trim(),
          branch_eligibility: selectedBranches,
          linked_job_ids: selectedJobIds,
          drive_date: driveDate ? new Date(driveDate).toISOString() : null,
          attachment_file_ids: uploadedAttachments.map((att) => att.file_id),
          candidates: candidates.map((c) => ({
            row_index: c.row_index,
            source_filename: c.source_filename,
            extracted_usn: c.extracted_usn,
            extracted_name: c.extracted_name,
            extracted_email: c.extracted_email,
            extracted_branch: c.extracted_branch,
            matched_student_id: c.matched_student_id,
            matched_student_name: c.matched_student_name,
            matched_student_usn: c.matched_student_usn,
            matched_student_email: c.matched_student_email,
            matched_student_branch: c.matched_student_branch,
            match_confidence: c.match_confidence,
            match_method: c.match_method,
            match_evidence: c.match_evidence,
            review_status: c.review_status,
            is_duplicate: c.is_duplicate,
            is_confirmed: c.is_confirmed,
          })),
        };

        const result = await createAndPostDrive(payload);
        toast.success(
          result.message ||
            `Recruitment drive posted! ${result.notified_students_count} shortlisted students notified.`
        );
        navigate('/placement/circulars');
      }
    } catch (err) {
      const errMsg = err.response?.data?.detail || err.message || 'Failed to post recruitment drive.';
      toast.error(errMsg);
    } finally {
      setLoading(false);
    }
  };

  if (initialLoading) {
    return (
      <div className="p-12 text-center text-gray-500">
        <div className="animate-spin w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full mx-auto mb-3" />
        <p>Loading recruitment drive data...</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-16">
      {/* Top Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/placement/circulars')}
          className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors cursor-pointer"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            {isEditMode ? 'Edit Recruitment Drive' : 'Create Recruitment Drive'}
          </h1>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            Select company, attach shortlist documents, review candidate matches, and post the announcement.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* ========================================================================= */}
        {/* CARD 1: CORE RECRUITMENT DETAILS (Company, Date, Roles, Branches)        */}
        {/* ========================================================================= */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 space-y-5 shadow-sm">
          <h2 className="text-sm font-bold text-gray-900 dark:text-white uppercase tracking-wider flex items-center gap-2">
            <Building2 className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            <span>Drive Overview</span>
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Field 1: Company (Required) */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                Company <span className="text-red-500">*</span>
              </label>
              <select
                required
                value={companyId}
                onChange={(e) => {
                  setCompanyId(e.target.value);
                  setSelectedJobIds([]);
                }}
                className="w-full px-3 py-2 text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">-- Select Company --</option>
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Field 6: Drive Date (Optional) */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                Placement Drive Date <span className="text-gray-400 font-normal">(Optional)</span>
              </label>
              <input
                type="datetime-local"
                value={driveDate}
                onChange={(e) => setDriveDate(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500"
              />
              <span className="text-[11px] text-gray-400">Leave blank if date is not yet announced.</span>
            </div>
          </div>

          {/* Field 5: Linked Job Roles (Filtered by selected company) */}
          <div className="space-y-1.5 pt-2 border-t border-gray-100 dark:border-gray-800">
            <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300">
              Linked Job Roles
            </label>
            {!companyId ? (
              <p className="text-xs text-gray-400 italic">
                Select a company first to link relevant job openings.
              </p>
            ) : availableCompanyJobs.length === 0 ? (
              <p className="text-xs text-gray-400">
                No active job postings found for {selectedCompany?.name || 'this company'}.
              </p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                {availableCompanyJobs.map((job) => {
                  const isChecked = selectedJobIds.includes(job.id);
                  return (
                    <label
                      key={job.id}
                      className={`flex items-start gap-2.5 p-2.5 rounded-lg border text-xs cursor-pointer transition-all ${
                        isChecked
                          ? 'border-indigo-400 bg-indigo-50/40 dark:bg-indigo-950/30 text-indigo-950 dark:text-indigo-200'
                          : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 bg-gray-50/50 dark:bg-gray-800/40 text-gray-700 dark:text-gray-300'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => handleToggleJob(job.id)}
                        className="mt-0.5 rounded text-indigo-600 focus:ring-indigo-500"
                      />
                      <div className="truncate">
                        <span className="font-semibold block truncate">{job.title}</span>
                        <span className="text-[11px] text-gray-500 dark:text-gray-400">
                          {job.salary_range ? `${job.salary_range} • ` : ''}
                          {job.location || 'Location flexible'}
                        </span>
                      </div>
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          {/* Field 4: Branch Eligibility */}
          <div className="space-y-2 pt-2 border-t border-gray-100 dark:border-gray-800">
            <div className="flex items-center justify-between">
              <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-1.5">
                <GraduationCap className="w-3.5 h-3.5 text-indigo-500" />
                <span>Eligible Branches</span>
              </label>
              <div className="flex items-center gap-2 text-[11px]">
                <button
                  type="button"
                  onClick={handleSelectAllBranches}
                  className="text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer"
                >
                  Select All
                </button>
                <span className="text-gray-300 dark:text-gray-700">•</span>
                <button
                  type="button"
                  onClick={handleClearBranches}
                  className="text-gray-500 hover:underline cursor-pointer"
                >
                  Clear
                </button>
              </div>
            </div>

            <div className="flex flex-wrap gap-2 pt-1">
              {AVAILABLE_BRANCHES.map((b) => {
                const isSelected = selectedBranches.includes(b);
                return (
                  <button
                    key={b}
                    type="button"
                    onClick={() => handleToggleBranch(b)}
                    className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors cursor-pointer ${
                      isSelected
                        ? 'bg-indigo-600 text-white border-indigo-600'
                        : 'bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-700 hover:border-gray-300'
                    }`}
                  >
                    {b}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* CARD 2: FILE ATTACHMENTS & SHORTLIST EXTRACTION                           */}
        {/* ========================================================================= */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 space-y-4 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-gray-900 dark:text-white uppercase tracking-wider flex items-center gap-2">
              <Paperclip className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
              <span>Shortlist & Circular Attachments</span>
            </h2>
            <span className="text-[11px] text-gray-400">PDF, XLSX, DOCX, CSV, TXT, Images</span>
          </div>

          {/* Dropzone / Upload area */}
          <div className="border-2 border-dashed border-gray-200 dark:border-gray-700 hover:border-indigo-400 dark:hover:border-indigo-600 rounded-xl p-5 text-center bg-gray-50/50 dark:bg-gray-800/30 transition-colors">
            <Upload className="w-8 h-8 text-gray-400 dark:text-gray-500 mx-auto mb-2" />
            <p className="text-xs font-semibold text-gray-700 dark:text-gray-300">
              Drag & drop shortlist files, or click to browse
            </p>
            <p className="text-[11px] text-gray-400 mt-1">
              Supports shortlist spreadsheets, company notices, PDFs, and scanned candidate lists
            </p>
            <input
              type="file"
              multiple
              accept=".pdf,.xlsx,.xls,.docx,.csv,.txt,image/*"
              onChange={handleFileChange}
              className="mt-3 text-xs text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-indigo-50 file:text-indigo-700 dark:file:bg-indigo-950/50 dark:file:text-indigo-300 hover:file:bg-indigo-100 cursor-pointer"
            />
          </div>

          {/* Selected local files list */}
          {selectedFiles.length > 0 && (
            <div className="space-y-2 pt-2">
              <div className="flex items-center justify-between text-xs font-semibold text-gray-700 dark:text-gray-300">
                <span>Selected Documents ({selectedFiles.length})</span>
                <button
                  type="button"
                  onClick={handleExtractShortlist}
                  disabled={isParsing}
                  className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-semibold flex items-center gap-1.5 shadow-sm transition-colors cursor-pointer disabled:opacity-50"
                >
                  {isParsing ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Extracting Candidates & Text...</span>
                    </>
                  ) : (
                    <>
                      <FileSpreadsheet className="w-3.5 h-3.5" />
                      <span>Extract Candidates & Description</span>
                    </>
                  )}
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {selectedFiles.map((file, idx) => (
                  <div
                    key={idx}
                    className="p-2.5 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 flex items-center justify-between gap-2 text-xs"
                  >
                    <div className="flex items-center gap-2 truncate">
                      <Paperclip className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
                      <span className="truncate font-medium text-gray-900 dark:text-white">
                        {file.name}
                      </span>
                      <span className="text-[10px] text-gray-400 shrink-0">
                        ({(file.size / 1024).toFixed(0)} KB)
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveLocalFile(idx)}
                      className="p-1 text-gray-400 hover:text-red-500 cursor-pointer"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Uploaded attachments preview list (if already parsed or in edit mode) */}
          {uploadedAttachments.length > 0 && (
            <div className="space-y-1.5 pt-2 border-t border-gray-100 dark:border-gray-800">
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider block">
                Saved Attachments ({uploadedAttachments.length})
              </span>
              <div className="flex flex-wrap gap-2">
                {uploadedAttachments.map((att, i) => (
                  <div
                    key={i}
                    className="px-2.5 py-1 bg-gray-100 dark:bg-gray-800 rounded-md text-xs flex items-center gap-2 border border-gray-200 dark:border-gray-700"
                  >
                    <FileText className="w-3.5 h-3.5 text-gray-500" />
                    <span className="text-gray-800 dark:text-gray-200">{att.filename}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Extraction status notice */}
          {parseStatus && (
            <div
              className={`p-3 rounded-lg text-xs flex items-start gap-2 ${
                parseStatus.error
                  ? 'bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800'
                  : 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-200 border border-emerald-200 dark:border-emerald-800'
              }`}
            >
              {parseStatus.error ? (
                <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
              ) : (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
              )}
              <span>{parseStatus.message}</span>
            </div>
          )}
        </div>

        {/* ========================================================================= */}
        {/* CARD 3: DESCRIPTION (Field 3: auto-populated, editable)                   */}
        {/* ========================================================================= */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 space-y-3 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-gray-900 dark:text-white uppercase tracking-wider flex items-center gap-2">
              <FileText className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
              <span>Drive Description & Circular Notice <span className="text-red-500">*</span></span>
            </h2>
            <span className="text-[11px] text-gray-400">
              Auto-populated from documents, editable before posting
            </span>
          </div>

          <textarea
            required
            rows={6}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Announce the shortlist, recruitment instructions, interview schedules, or candidate guidelines..."
            className="w-full px-3 py-2 text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-white font-mono focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        {/* ========================================================================= */}
        {/* CARD 4: CANDIDATE-MATCH REVIEW (Inline before posting)                    */}
        {/* ========================================================================= */}
        {candidates.length > 0 && (
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 space-y-4 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h2 className="text-sm font-bold text-gray-900 dark:text-white uppercase tracking-wider flex items-center gap-2">
                  <Users className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                  <span>Candidate Shortlist Review ({candidates.length})</span>
                </h2>
                <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5">
                  Confirm matched students before posting. Only confirmed candidates receive direct shortlist notifications.
                </p>
              </div>

              {/* Bulk Review Action Controls */}
              <div className="flex items-center gap-2 text-xs">
                <button
                  type="button"
                  onClick={handleConfirmAllMatched}
                  className="px-2.5 py-1 bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 rounded-md font-semibold hover:bg-emerald-100 cursor-pointer"
                >
                  Confirm Matched
                </button>
                <button
                  type="button"
                  onClick={handleExcludeAllAmbiguous}
                  className="px-2.5 py-1 bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800 rounded-md font-semibold hover:bg-amber-100 cursor-pointer"
                >
                  Exclude Ambiguous
                </button>
              </div>
            </div>

            {/* Candidate Summary Metric Chips */}
            <div className="flex flex-wrap gap-2 text-xs">
              <button
                type="button"
                onClick={() => setCandidateFilter('all')}
                className={`px-3 py-1 rounded-lg border font-medium cursor-pointer ${
                  candidateFilter === 'all'
                    ? 'bg-indigo-600 text-white border-indigo-600'
                    : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-700'
                }`}
              >
                All ({candidates.length})
              </button>
              <button
                type="button"
                onClick={() => setCandidateFilter('confirmed')}
                className={`px-3 py-1 rounded-lg border font-medium cursor-pointer ${
                  candidateFilter === 'confirmed'
                    ? 'bg-emerald-600 text-white border-emerald-600'
                    : 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
                }`}
              >
                Confirmed to Notify ({confirmedCount})
              </button>
              <button
                type="button"
                onClick={() => setCandidateFilter('ambiguous')}
                className={`px-3 py-1 rounded-lg border font-medium cursor-pointer ${
                  candidateFilter === 'ambiguous'
                    ? 'bg-amber-600 text-white border-amber-600'
                    : 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800'
                }`}
              >
                Ambiguous ({candidates.filter((c) => c.review_status === 'ambiguous').length})
              </button>
              <button
                type="button"
                onClick={() => setCandidateFilter('duplicate')}
                className={`px-3 py-1 rounded-lg border font-medium cursor-pointer ${
                  candidateFilter === 'duplicate'
                    ? 'bg-orange-600 text-white border-orange-600'
                    : 'bg-orange-50 dark:bg-orange-950/40 text-orange-700 dark:text-orange-300 border-orange-200 dark:border-orange-800'
                }`}
              >
                Duplicates ({candidates.filter((c) => c.is_duplicate).length})
              </button>
              <button
                type="button"
                onClick={() => setCandidateFilter('unmatched')}
                className={`px-3 py-1 rounded-lg border font-medium cursor-pointer ${
                  candidateFilter === 'unmatched'
                    ? 'bg-gray-600 text-white border-gray-600'
                    : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-700'
                }`}
              >
                Unmatched ({candidates.filter((c) => c.review_status === 'unmatched').length})
              </button>
            </div>

            {/* Candidate Review Table */}
            <div className="overflow-x-auto border border-gray-200 dark:border-gray-800 rounded-lg">
              <table className="w-full text-left text-xs">
                <thead className="bg-gray-50 dark:bg-gray-800/60 text-gray-500 font-semibold border-b border-gray-200 dark:border-gray-800">
                  <tr>
                    <th className="p-2.5">Extracted Details</th>
                    <th className="p-2.5">Matched Institutional Record</th>
                    <th className="p-2.5">Match Method & Confidence</th>
                    <th className="p-2.5">Status</th>
                    <th className="p-2.5 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {filteredCandidates.map((cand) => (
                    <tr
                      key={cand.row_index}
                      className={`hover:bg-gray-50/50 dark:hover:bg-gray-800/40 ${
                        cand.is_duplicate
                          ? 'bg-orange-50/20 dark:bg-orange-950/10'
                          : cand.review_status === 'ambiguous'
                          ? 'bg-amber-50/20 dark:bg-amber-950/10'
                          : ''
                      }`}
                    >
                      {/* Extracted Details */}
                      <td className="p-2.5">
                        <div className="font-semibold text-gray-900 dark:text-white">
                          {cand.extracted_name || 'Name not listed'}
                        </div>
                        <div className="text-[11px] text-gray-500 dark:text-gray-400">
                          {cand.extracted_usn && <span className="font-mono">{cand.extracted_usn}</span>}
                          {cand.extracted_email && <span> • {cand.extracted_email}</span>}
                        </div>
                        <div className="text-[10px] text-gray-400 mt-0.5">
                          Source: {cand.source_filename}
                        </div>
                      </td>

                      {/* Matched Student Record */}
                      <td className="p-2.5">
                        {cand.matched_student_id ? (
                          <div>
                            <div className="font-semibold text-gray-900 dark:text-white">
                              {cand.matched_student_name}
                            </div>
                            <div className="text-[11px] text-gray-500 dark:text-gray-400">
                              <span className="font-mono">{cand.matched_student_usn}</span>
                              {cand.matched_student_branch && (
                                <span> • {cand.matched_student_branch}</span>
                              )}
                            </div>
                          </div>
                        ) : (
                          <span className="text-gray-400 italic">No matching student found</span>
                        )}
                      </td>

                      {/* Confidence & Method */}
                      <td className="p-2.5">
                        <div className="flex items-center gap-1.5">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              cand.match_confidence >= 0.95
                                ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                                : cand.match_confidence >= 0.7
                                ? 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                                : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
                            }`}
                          >
                            {(cand.match_confidence * 100).toFixed(0)}%
                          </span>
                          <span className="text-[11px] text-gray-500 dark:text-gray-400 capitalize">
                            {cand.match_method || 'none'}
                          </span>
                        </div>
                        {cand.is_duplicate && (
                          <span className="text-[10px] font-bold text-orange-600 dark:text-orange-400 block mt-0.5">
                            Duplicate Candidate
                          </span>
                        )}
                      </td>

                      {/* Confirmation Status */}
                      <td className="p-2.5">
                        {cand.is_confirmed ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300">
                            <Check className="w-3 h-3" /> Confirmed
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                            Excluded
                          </span>
                        )}
                      </td>

                      {/* Action buttons */}
                      <td className="p-2.5 text-right">
                        {cand.matched_student_id ? (
                          cand.is_confirmed ? (
                            <button
                              type="button"
                              onClick={() => handleExcludeCandidate(cand.row_index)}
                              className="px-2 py-1 text-[11px] font-semibold text-gray-600 dark:text-gray-400 hover:text-red-600 dark:hover:text-red-400 border border-gray-200 dark:border-gray-700 hover:border-red-300 rounded cursor-pointer"
                            >
                              Exclude
                            </button>
                          ) : (
                            <button
                              type="button"
                              onClick={() => handleConfirmCandidate(cand.row_index)}
                              className="px-2 py-1 text-[11px] font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded cursor-pointer shadow-sm"
                            >
                              Confirm
                            </button>
                          )
                        ) : (
                          <span className="text-[11px] text-gray-400">Unmatched</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* SUBMISSION BUTTONS                                                        */}
        {/* ========================================================================= */}
        <div className="flex items-center justify-between pt-4 border-t border-gray-200 dark:border-gray-800">
          <button
            type="button"
            onClick={() => navigate('/placement/circulars')}
            className="px-4 py-2 text-xs font-semibold text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors cursor-pointer"
          >
            Cancel
          </button>

          <button
            type="submit"
            disabled={loading}
            className="px-6 py-2.5 text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg shadow-sm transition-colors cursor-pointer flex items-center gap-2 disabled:opacity-50"
          >
            {loading ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Posting Recruitment Drive...</span>
              </>
            ) : (
              <>
                <Send className="w-3.5 h-3.5" />
                <span>
                  {isEditMode
                    ? 'Save Changes'
                    : confirmedCount > 0
                    ? `Post Drive & Notify ${confirmedCount} Students`
                    : 'Post Recruitment Drive'}
                </span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};

export default CircularForm;
