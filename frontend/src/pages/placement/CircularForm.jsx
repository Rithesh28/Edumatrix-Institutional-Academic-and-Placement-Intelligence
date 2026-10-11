import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Building2,
  Calendar,
  Clock,
  Briefcase,
  Paperclip,
  Upload,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  Info,
  GraduationCap,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import api from '../../services/api';
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

const ATTACHMENT_TYPES = [
  { value: 'poster', label: 'Drive Poster' },
  { value: 'job_description', label: 'Job Description (JD)' },
  { value: 'eligibility_sheet', label: 'Eligibility Sheet' },
  { value: 'guidelines', label: 'Interview Guidelines' },
  { value: 'other', label: 'Other Document' },
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
    createCircular,
    updateCircular,
    fetchCircular,
    publishCircular,
    addCircularAttachment,
    removeCircularAttachment,
    linkCircularJobs,
    unlinkCircularJob,
  } = usePlacementStore();

  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(isEditMode);

  // Form State
  const [companyId, setCompanyId] = useState('');
  const [title, setTitle] = useState('');
  const [summary, setSummary] = useState('');
  const [instructions, setInstructions] = useState('');
  const [driveDate, setDriveDate] = useState('');
  const [applicationDeadline, setApplicationDeadline] = useState('');
  const [selectedBranches, setSelectedBranches] = useState([]);
  const [selectedJobIds, setSelectedJobIds] = useState([]);

  // Existing circular data in edit mode
  const [existingCircular, setExistingCircular] = useState(null);

  // Attachment Upload State
  const [attachments, setAttachments] = useState([]);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadType, setUploadType] = useState('poster');
  const [uploadOrder, setUploadOrder] = useState(0);
  const [isUploading, setIsUploading] = useState(false);

  // Initial data loading
  useEffect(() => {
    const init = async () => {
      try {
        await Promise.all([fetchCompanies(), fetchJobPostings()]);

        if (isEditMode) {
          const circ = await fetchCircular(id);
          setExistingCircular(circ);
          setCompanyId(String(circ.company_id));
          setTitle(circ.title || '');
          setSummary(circ.summary || '');
          setInstructions(circ.instructions || '');
          if (circ.drive_date) {
            setDriveDate(new Date(circ.drive_date).toISOString().slice(0, 16));
          }
          if (circ.application_deadline) {
            setApplicationDeadline(new Date(circ.application_deadline).toISOString().slice(0, 16));
          }
          setSelectedBranches(circ.branch_eligibility || []);
          setSelectedJobIds((circ.linked_jobs || []).map((j) => j.job_posting_id));
          setAttachments(circ.attachments || []);
        }
      } catch (err) {
        toast.error('Failed to load required data.');
      } finally {
        setInitialLoading(false);
      }
    };
    init();
  }, [id, isEditMode]);

  // Jobs belonging exclusively to the selected company
  const availableCompanyJobs = useMemo(() => {
    if (!companyId) return [];
    return jobs.filter((j) => String(j.company_id) === String(companyId));
  }, [jobs, companyId]);

  const handleBranchToggle = (branch) => {
    setSelectedBranches((prev) =>
      prev.includes(branch) ? prev.filter((b) => b !== branch) : [...prev, branch]
    );
  };

  const handleJobToggle = (jobId) => {
    setSelectedJobIds((prev) =>
      prev.includes(jobId) ? prev.filter((j) => j !== jobId) : [...prev, jobId]
    );
  };

  // Upload attachment via standard files API
  const handleFileUpload = async () => {
    if (!uploadFile) {
      toast.error('Please select a file to upload.');
      return;
    }
    setIsUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', uploadFile);
      formData.append('file_type', 'placement_doc');
      formData.append('department', 'Placement');
      formData.append('description', `Recruitment Circular attachment: ${uploadType}`);

      const uploadRes = await api.post('/files/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      const uploadedFileObj = uploadRes.data;

      if (isEditMode) {
        // In edit mode, link immediately via API
        const updated = await addCircularAttachment(id, {
          file_id: uploadedFileObj.file_id || uploadedFileObj.id,
          attachment_type: uploadType,
          display_order: Number(uploadOrder),
        });
        setAttachments(updated.attachments || []);
        toast.success('Attachment added successfully.');
      } else {
        // In create mode, track for creation
        const newAtt = {
          id: `temp-${Date.now()}`,
          file_id: uploadedFileObj.file_id || uploadedFileObj.id,
          filename: uploadedFileObj.filename || uploadedFileObj.original_filename || uploadFile.name,
          attachment_type: uploadType,
          display_order: Number(uploadOrder),
          file_size: uploadFile.size,
        };
        setAttachments((prev) => [...prev, newAtt]);
        toast.success('File uploaded and queued for circular.');
      }

      setUploadFile(null);
      setUploadOrder((prev) => prev + 1);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to upload attachment.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleRemoveAttachment = async (att) => {
    if (isEditMode && typeof att.id === 'number') {
      try {
        const updated = await removeCircularAttachment(id, att.id);
        setAttachments(updated.attachments || []);
        toast.success('Attachment removed.');
      } catch (err) {
        toast.error('Failed to remove attachment.');
      }
    } else {
      setAttachments((prev) => prev.filter((a) => a.id !== att.id));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!companyId) {
      toast.error('Please select a company.');
      return;
    }
    if (!title.trim()) {
      toast.error('Please enter a circular title.');
      return;
    }

    setLoading(true);
    try {
      if (isEditMode) {
        await updateCircular(id, {
          company_id: Number(companyId),
          title: title.trim(),
          summary: summary.trim() || null,
          instructions: instructions.trim() || null,
          drive_date: driveDate ? new Date(driveDate).toISOString() : null,
          application_deadline: applicationDeadline
            ? new Date(applicationDeadline).toISOString()
            : null,
          branch_eligibility: selectedBranches,
        });

        // Update linked jobs
        const currentLinked = (existingCircular?.linked_jobs || []).map((j) => j.job_posting_id);
        const toAdd = selectedJobIds.filter((jId) => !currentLinked.includes(jId));
        const toRemove = currentLinked.filter((jId) => !selectedJobIds.includes(jId));

        if (toAdd.length > 0) {
          await linkCircularJobs(id, { job_posting_ids: toAdd });
        }
        for (const remId of toRemove) {
          await unlinkCircularJob(id, remId);
        }

        toast.success('Recruitment circular updated successfully!');
        navigate(`/placement/circulars/${id}`);
      } else {
        const payload = {
          company_id: Number(companyId),
          title: title.trim(),
          summary: summary.trim() || null,
          instructions: instructions.trim() || null,
          drive_date: driveDate ? new Date(driveDate).toISOString() : null,
          application_deadline: applicationDeadline
            ? new Date(applicationDeadline).toISOString()
            : null,
          branch_eligibility: selectedBranches,
          job_posting_ids: selectedJobIds,
          attachments: attachments.map((a) => ({
            file_id: a.file_id,
            attachment_type: a.attachment_type,
            display_order: a.display_order,
          })),
        };

        const created = await createCircular(payload);
        toast.success('Recruitment circular draft created successfully!');
        navigate(`/placement/circulars/${created.id}`);
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || 'Failed to save circular.');
    } finally {
      setLoading(false);
    }
  };

  if (initialLoading) {
    return (
      <div className="p-12 text-center text-gray-500 dark:text-gray-400">
        <div className="animate-spin w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full mx-auto mb-3" />
        <p>Loading circular editor...</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-16">
      {/* Top Nav */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/placement/circulars')}
          className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors cursor-pointer"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            {isEditMode ? 'Edit Recruitment Circular' : 'Create Recruitment Circular Draft'}
          </h1>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            Configure company placement details, multi-select linked job roles, and attach drive documents.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Section 1: Company & Basic Info */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 space-y-5 shadow-sm">
          <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Building2 className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            <span>Drive Overview</span>
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Company Select */}
            <div className="space-y-1.5 md:col-span-2">
              <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                Company <span className="text-red-500">*</span>
              </label>
              <select
                value={companyId}
                onChange={(e) => {
                  setCompanyId(e.target.value);
                  setSelectedJobIds([]); // Reset jobs to prevent cross-company linkage
                }}
                disabled={isEditMode && existingCircular?.status !== 'draft'}
                className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:text-white"
                required
              >
                <option value="">Select recruiting company...</option>
                {companies.map((comp) => (
                  <option key={comp.id} value={comp.id}>
                    {comp.name} {comp.industry ? `(${comp.industry})` : ''}
                  </option>
                ))}
              </select>
              <p className="text-[11px] text-gray-400">
                Linked roles will be strictly validated to match this recruiting company.
              </p>
            </div>

            {/* Title */}
            <div className="space-y-1.5 md:col-span-2">
              <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                Circular Title <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                placeholder="e.g. Google Campus Hiring Drive 2026 - Engineering Roles"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:text-white"
                required
              />
            </div>

            {/* Drive Date */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 text-gray-400" />
                <span>Drive Date</span>
              </label>
              <input
                type="datetime-local"
                value={driveDate}
                onChange={(e) => setDriveDate(e.target.value)}
                className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:text-white"
              />
            </div>

            {/* Application Deadline */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-gray-400" />
                <span>Application Deadline</span>
              </label>
              <input
                type="datetime-local"
                value={applicationDeadline}
                onChange={(e) => setApplicationDeadline(e.target.value)}
                className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:text-white"
              />
            </div>

            {/* Summary */}
            <div className="space-y-1.5 md:col-span-2">
              <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                Drive Summary / Highlights
              </label>
              <textarea
                rows={3}
                placeholder="Brief overview of the drive, package tiers, and hiring team visit details..."
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
                className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:text-white"
              />
            </div>

            {/* Instructions */}
            <div className="space-y-1.5 md:col-span-2">
              <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                Registration & Test Instructions
              </label>
              <textarea
                rows={4}
                placeholder="Specific instructions for students regarding registration portals, dress code, documents to bring, and test links..."
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
                className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:text-white"
              />
            </div>
          </div>
        </div>

        {/* Section 2: Branch Eligibility */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 space-y-4 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <GraduationCap className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
              <span>Branch Eligibility</span>
            </h2>
            <span className="text-xs text-gray-400">
              Leave empty to permit all branches
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {AVAILABLE_BRANCHES.map((branch) => {
              const isChecked = selectedBranches.includes(branch);
              return (
                <label
                  key={branch}
                  className={`flex items-center gap-2 p-2.5 rounded-lg border text-xs cursor-pointer transition-colors ${
                    isChecked
                      ? 'bg-indigo-50/80 dark:bg-indigo-950/40 border-indigo-300 dark:border-indigo-800 text-indigo-900 dark:text-indigo-200 font-medium'
                      : 'bg-gray-50 dark:bg-gray-800/50 border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-100'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => handleBranchToggle(branch)}
                    className="rounded text-indigo-600 focus:ring-indigo-500"
                  />
                  <span>{branch}</span>
                </label>
              );
            })}
          </div>
        </div>

        {/* Section 3: Linked Job Postings */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 space-y-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
                <Briefcase className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                <span>Linked Job Roles</span>
              </h2>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                Select one or more roles offered by this company in this drive.
              </p>
            </div>
            <span className="text-xs font-semibold px-2 py-0.5 bg-indigo-50 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300 rounded border border-indigo-200 dark:border-indigo-800">
              {selectedJobIds.length} Selected
            </span>
          </div>

          {!companyId ? (
            <div className="p-4 bg-gray-50 dark:bg-gray-800/50 border border-dashed border-gray-300 dark:border-gray-700 rounded-lg text-center text-xs text-gray-500">
              Please select a recruiting company above to view available job roles.
            </div>
          ) : availableCompanyJobs.length === 0 ? (
            <div className="p-4 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-lg text-center text-xs text-amber-800 dark:text-amber-300">
              No job postings found for this company. You can create jobs under{' '}
              <button
                type="button"
                onClick={() => navigate('/placement/jobs/post')}
                className="underline font-semibold cursor-pointer"
              >
                Jobs &gt; Post Job
              </button>{' '}
              and link them here.
            </div>
          ) : (
            <div className="space-y-2">
              {availableCompanyJobs.map((job) => {
                const isSelected = selectedJobIds.includes(job.id);
                return (
                  <div
                    key={job.id}
                    onClick={() => handleJobToggle(job.id)}
                    className={`p-3 rounded-lg border text-xs cursor-pointer transition-all flex items-center justify-between gap-3 ${
                      isSelected
                        ? 'bg-indigo-50/70 dark:bg-indigo-950/40 border-indigo-300 dark:border-indigo-800'
                        : 'bg-gray-50 dark:bg-gray-800/40 border-gray-200 dark:border-gray-700 hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => {}} // handled by parent div
                        className="rounded text-indigo-600 focus:ring-indigo-500"
                      />
                      <div>
                        <h4 className="font-semibold text-gray-900 dark:text-white">
                          {job.title}
                        </h4>
                        <div className="flex items-center gap-2 text-[11px] text-gray-500 mt-0.5">
                          {job.experience_level && <span>Exp: {job.experience_level}</span>}
                          {job.salary_range && <span>• Salary: {job.salary_range}</span>}
                          {job.location && <span>• Location: {job.location}</span>}
                        </div>
                      </div>
                    </div>

                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                        job.status === 'open'
                          ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300'
                          : 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300'
                      }`}
                    >
                      {job.status}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Section 4: Attachments */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 space-y-4 shadow-sm">
          <div>
            <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <Paperclip className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
              <span>Drive Attachments</span>
            </h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              Upload posters, JDs, or guidelines stored securely via institutional MinIO storage.
            </p>
          </div>

          {/* Upload inputs */}
          <div className="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-gray-200 dark:border-gray-700 space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="sm:col-span-1 space-y-1">
                <label className="text-[11px] font-semibold text-gray-600 dark:text-gray-400">
                  Attachment Type
                </label>
                <select
                  value={uploadType}
                  onChange={(e) => setUploadType(e.target.value)}
                  className="w-full px-2.5 py-1.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-xs dark:text-white"
                >
                  {ATTACHMENT_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="sm:col-span-1 space-y-1">
                <label className="text-[11px] font-semibold text-gray-600 dark:text-gray-400">
                  Display Order
                </label>
                <input
                  type="number"
                  min="0"
                  value={uploadOrder}
                  onChange={(e) => setUploadOrder(e.target.value)}
                  className="w-full px-2.5 py-1.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-xs dark:text-white"
                />
              </div>

              <div className="sm:col-span-1 space-y-1">
                <label className="text-[11px] font-semibold text-gray-600 dark:text-gray-400">
                  Select File
                </label>
                <input
                  type="file"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  className="w-full text-xs text-gray-500 file:mr-2 file:py-1 file:px-2.5 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-indigo-50 file:text-indigo-700 dark:file:bg-indigo-950/50 dark:file:text-indigo-300"
                />
              </div>
            </div>

            <button
              type="button"
              onClick={handleFileUpload}
              disabled={!uploadFile || isUploading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50"
            >
              <Upload className="w-3.5 h-3.5" />
              <span>{isUploading ? 'Uploading...' : 'Upload & Add Attachment'}</span>
            </button>
          </div>

          {/* Current attachments list */}
          {attachments.length === 0 ? (
            <p className="text-xs text-gray-400 text-center py-2">
              No attachments added yet.
            </p>
          ) : (
            <div className="space-y-2">
              {attachments.map((att) => (
                <div
                  key={att.id}
                  className="flex items-center justify-between p-2.5 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 text-xs"
                >
                  <div className="flex items-center gap-2">
                    <Paperclip className="w-4 h-4 text-indigo-500" />
                    <div>
                      <span className="font-semibold text-gray-900 dark:text-white">
                        {att.filename || 'Attachment'}
                      </span>
                      <span className="ml-2 text-[10px] uppercase font-bold text-gray-500 bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded">
                        {att.attachment_type}
                      </span>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleRemoveAttachment(att)}
                    className="p-1 text-red-500 hover:bg-red-50 dark:hover:bg-red-950/40 rounded transition-colors cursor-pointer"
                    title="Remove attachment"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Form Actions */}
        <div className="flex items-center justify-end gap-3 pt-4">
          <button
            type="button"
            onClick={() => navigate('/placement/circulars')}
            className="px-5 py-2 text-sm font-semibold text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors cursor-pointer"
          >
            Cancel
          </button>

          <button
            type="submit"
            disabled={loading}
            className="px-6 py-2.5 text-sm font-semibold bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors cursor-pointer flex items-center gap-2 shadow-sm disabled:opacity-50"
          >
            {loading ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Saving...</span>
              </>
            ) : (
              <span>{isEditMode ? 'Update Circular' : 'Save as Draft'}</span>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};

export default CircularForm;
