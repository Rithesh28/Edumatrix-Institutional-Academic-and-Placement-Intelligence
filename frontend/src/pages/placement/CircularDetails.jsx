import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Building2,
  Calendar,
  Clock,
  Briefcase,
  Paperclip,
  Eye,
  Download,
  Edit2,
  Archive,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  ExternalLink,
  GraduationCap,
  X,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import toast from 'react-hot-toast';

const CircularDetails = () => {
  const { id } = useParams();
  const navigate = useNavigate();

  const {
    selectedCircular,
    isCircularsLoading,
    fetchCircular,
    publishCircular,
    archiveCircular,
  } = usePlacementStore();

  const [previewFile, setPreviewFile] = useState(null);

  // Publish review modal state
  const [publishModal, setPublishModal] = useState({
    isOpen: false,
    isPublishing: false,
    confirmNoSkills: false,
    errorMessage: null,
    showSkillBypass: false,
  });

  useEffect(() => {
    fetchCircular(id).catch((err) => {
      toast.error('Failed to load circular details.');
    });
  }, [id, fetchCircular]);

  const handleOpenPublish = () => {
    if (!selectedCircular.linked_jobs || selectedCircular.linked_jobs.length === 0) {
      toast.error('At least one linked job role is required to publish this circular.');
      return;
    }
    setPublishModal({
      isOpen: true,
      isPublishing: false,
      confirmNoSkills: false,
      errorMessage: null,
      showSkillBypass: false,
    });
  };

  const handleConfirmPublish = async () => {
    setPublishModal((prev) => ({ ...prev, isPublishing: true, errorMessage: null }));
    try {
      const response = await publishCircular(id, {
        confirm_no_skills: publishModal.confirmNoSkills,
      });
      toast.success(response.message || 'Recruitment circular published successfully!');
      setPublishModal({
        isOpen: false,
        isPublishing: false,
        confirmNoSkills: false,
        errorMessage: null,
        showSkillBypass: false,
      });
      fetchCircular(id);
    } catch (error) {
      const msg = error.response?.data?.detail || error.message || 'Failed to publish circular.';
      if (msg.includes('confirm_no_skills=True')) {
        setPublishModal((prev) => ({
          ...prev,
          isPublishing: false,
          errorMessage: msg,
          showSkillBypass: true,
        }));
      } else {
        toast.error(msg);
        setPublishModal((prev) => ({ ...prev, isPublishing: false, errorMessage: msg }));
      }
    }
  };

  const handleArchive = async () => {
    if (window.confirm('Are you sure you want to archive this recruitment circular?')) {
      try {
        await archiveCircular(id);
        toast.success('Circular archived successfully.');
        fetchCircular(id);
      } catch (err) {
        toast.error('Failed to archive circular.');
      }
    }
  };

  if (isCircularsLoading && !selectedCircular) {
    return (
      <div className="p-12 text-center text-gray-500 dark:text-gray-400">
        <div className="animate-spin w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full mx-auto mb-3" />
        <p>Loading circular details...</p>
      </div>
    );
  }

  if (!selectedCircular) {
    return (
      <div className="p-8 text-center bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
        <p className="text-gray-500">Recruitment circular not found.</p>
        <button
          onClick={() => navigate('/placement/circulars')}
          className="mt-3 text-indigo-600 text-sm font-semibold cursor-pointer"
        >
          &larr; Back to Circulars
        </button>
      </div>
    );
  }

  const circ = selectedCircular;

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-16">
      {/* Top Navigation & Status Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/placement/circulars')}
            className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors cursor-pointer"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{circ.title}</h1>
              <span
                className={`px-2.5 py-1 text-xs font-semibold rounded-full uppercase ${
                  circ.status === 'published'
                    ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300'
                    : circ.status === 'draft'
                    ? 'bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300'
                    : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
                }`}
              >
                {circ.status}
              </span>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 flex items-center gap-2">
              <span>{circ.company_name}</span>
              {circ.created_at && (
                <span>• Created: {new Date(circ.created_at).toLocaleDateString()}</span>
              )}
              {circ.published_at && (
                <span>• Published: {new Date(circ.published_at).toLocaleDateString()}</span>
              )}
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          {circ.status === 'draft' && (
            <>
              <button
                onClick={() => navigate(`/placement/circulars/${circ.id}/edit`)}
                className="px-3.5 py-2 text-xs font-semibold bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 rounded-lg flex items-center gap-1.5 cursor-pointer transition-colors"
              >
                <Edit2 className="w-3.5 h-3.5" />
                <span>Edit Draft</span>
              </button>
              <button
                onClick={handleOpenPublish}
                className="px-4 py-2 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg flex items-center gap-1.5 cursor-pointer transition-colors shadow-sm"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Publish Circular</span>
              </button>
            </>
          )}

          {circ.status === 'published' && (
            <button
              onClick={handleArchive}
              className="px-3.5 py-2 text-xs font-semibold bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 rounded-lg flex items-center gap-1.5 cursor-pointer transition-colors"
            >
              <Archive className="w-3.5 h-3.5" />
              <span>Archive</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Details Card */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 space-y-6 shadow-sm">
        {/* Drive Key Metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pb-4 border-b border-gray-100 dark:border-gray-800 text-xs">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-indigo-50 dark:bg-indigo-950/50 rounded-lg text-indigo-600 dark:text-indigo-400">
              <Calendar className="w-5 h-5" />
            </div>
            <div>
              <span className="text-gray-400 font-medium">Drive Date</span>
              <p className="font-semibold text-gray-900 dark:text-white mt-0.5">
                {circ.drive_date ? new Date(circ.drive_date).toLocaleString() : 'TBD / Multiple'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-amber-50 dark:bg-amber-950/50 rounded-lg text-amber-600 dark:text-amber-400">
              <Clock className="w-5 h-5" />
            </div>
            <div>
              <span className="text-gray-400 font-medium">Application Deadline</span>
              <p className="font-semibold text-gray-900 dark:text-white mt-0.5">
                {circ.application_deadline
                  ? new Date(circ.application_deadline).toLocaleString()
                  : 'Open Until Drive'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-blue-50 dark:bg-blue-950/50 rounded-lg text-blue-600 dark:text-blue-400">
              <Building2 className="w-5 h-5" />
            </div>
            <div>
              <span className="text-gray-400 font-medium">Recruiting Company</span>
              <p className="font-semibold text-gray-900 dark:text-white mt-0.5">
                {circ.company_name}
              </p>
            </div>
          </div>
        </div>

        {/* Branch Eligibility */}
        {circ.branch_eligibility && circ.branch_eligibility.length > 0 && (
          <div className="space-y-1.5">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
              <GraduationCap className="w-4 h-4 text-indigo-500" />
              <span>Eligible Engineering Branches</span>
            </h3>
            <div className="flex flex-wrap gap-1.5 pt-1">
              {circ.branch_eligibility.map((b, i) => (
                <span
                  key={i}
                  className="px-2.5 py-1 bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 rounded-md text-xs font-medium"
                >
                  {b}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Summary */}
        {circ.summary && (
          <div className="space-y-1.5">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">
              Drive Overview
            </h3>
            <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-line">
              {circ.summary}
            </p>
          </div>
        )}

        {/* Instructions */}
        {circ.instructions && (
          <div className="space-y-1.5 p-4 bg-gray-50 dark:bg-gray-800/40 rounded-xl border border-gray-200 dark:border-gray-700">
            <h3 className="text-xs font-bold text-gray-900 dark:text-white uppercase tracking-wider">
              Registration & Drive Guidelines
            </h3>
            <p className="text-xs text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-line mt-1">
              {circ.instructions}
            </p>
          </div>
        )}
      </div>

      {/* Linked Job Roles */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 space-y-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Briefcase className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            <span>Linked Job Roles ({circ.linked_jobs?.length || 0})</span>
          </h2>
          <span className="text-xs text-gray-400">
            Roles activated together upon circular publication
          </span>
        </div>

        {!circ.linked_jobs || circ.linked_jobs.length === 0 ? (
          <div className="p-6 bg-gray-50 dark:bg-gray-800/40 rounded-xl text-center text-xs text-gray-500">
            No job roles linked yet. Edit this circular to link roles for {circ.company_name}.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {circ.linked_jobs.map((job) => (
              <div
                key={job.id}
                className="p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/30 hover:border-indigo-300 dark:hover:border-indigo-700 transition-all space-y-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <h4 className="font-bold text-sm text-gray-900 dark:text-white">{job.title}</h4>
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

                <div className="text-xs text-gray-500 dark:text-gray-400 space-y-0.5">
                  {job.salary_range && <p>Salary: {job.salary_range}</p>}
                  {job.location && <p>Location: {job.location}</p>}
                  {job.experience_level && <p>Experience: {job.experience_level}</p>}
                </div>

                {job.required_skills && job.required_skills.length > 0 && (
                  <div className="flex flex-wrap gap-1 pt-1">
                    {job.required_skills.slice(0, 4).map((skill, idx) => (
                      <span
                        key={idx}
                        className="px-1.5 py-0.5 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded text-[10px]"
                      >
                        {skill}
                      </span>
                    ))}
                    {job.required_skills.length > 4 && (
                      <span className="text-[10px] text-gray-400 self-center">
                        +{job.required_skills.length - 4} more
                      </span>
                    )}
                  </div>
                )}

                <div className="pt-2 border-t border-gray-100 dark:border-gray-700 flex justify-end">
                  <button
                    onClick={() => navigate(`/placement/jobs/${job.job_posting_id}`)}
                    className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-1 cursor-pointer"
                  >
                    <span>View Role Details</span>
                    <ExternalLink className="w-3 h-3" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Attachments Section */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 space-y-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Paperclip className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            <span>Drive Attachments ({circ.attachments?.length || 0})</span>
          </h2>
          <span className="text-xs text-gray-400">
            Posters, JDs, and Guidelines
          </span>
        </div>

        {!circ.attachments || circ.attachments.length === 0 ? (
          <div className="p-6 bg-gray-50 dark:bg-gray-800/40 rounded-xl text-center text-xs text-gray-500">
            No attachments added to this circular.
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {circ.attachments.map((att) => (
              <div
                key={att.id}
                className="p-3 bg-gray-50 dark:bg-gray-800/40 rounded-xl border border-gray-200 dark:border-gray-700 flex items-center justify-between gap-3 text-xs"
              >
                <div className="flex items-center gap-2.5 overflow-hidden">
                  <div className="p-2 bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 rounded-lg flex-shrink-0">
                    <Paperclip className="w-4 h-4" />
                  </div>
                  <div className="truncate">
                    <p className="font-semibold text-gray-900 dark:text-white truncate">
                      {att.filename || 'Document'}
                    </p>
                    <p className="text-[10px] text-gray-400 uppercase font-bold mt-0.5">
                      {att.attachment_type?.replace('_', ' ')}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 flex-shrink-0">
                  <button
                    onClick={() => setPreviewFile(att)}
                    className="p-1.5 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors cursor-pointer"
                    title="Preview attachment"
                  >
                    <Eye className="w-4 h-4" />
                  </button>
                  <a
                    href={`/api/v1/files/${att.file_id}/download`}
                    target="_blank"
                    rel="noreferrer"
                    download
                    className="p-1.5 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/50 rounded-lg transition-colors cursor-pointer"
                    title="Download attachment"
                  >
                    <Download className="w-4 h-4" />
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Attachment Preview Modal */}
      {previewFile && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-4xl w-full max-h-[90vh] flex flex-col border border-gray-200 dark:border-gray-800 shadow-2xl overflow-hidden">
            <div className="p-4 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
              <div>
                <h3 className="font-bold text-sm text-gray-900 dark:text-white">
                  {previewFile.filename}
                </h3>
                <span className="text-[10px] uppercase font-bold text-gray-400">
                  {previewFile.attachment_type}
                </span>
              </div>
              <button
                onClick={() => setPreviewFile(null)}
                className="p-1.5 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-auto p-4 flex items-center justify-center bg-gray-50 dark:bg-gray-950">
              <iframe
                src={`/api/v1/files/${previewFile.file_id}/preview`}
                title={previewFile.filename}
                className="w-full h-[65vh] rounded-lg border border-gray-200 dark:border-gray-800"
              />
            </div>
          </div>
        </div>
      )}

      {/* Publish Review Modal */}
      {publishModal.isOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-lg w-full p-6 border border-gray-200 dark:border-gray-800 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-emerald-100 dark:bg-emerald-950/80 text-emerald-600 dark:text-emerald-400 rounded-xl">
                <Sparkles className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                  Publish Recruitment Circular
                </h3>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Atomic Drive & Roles Activation
                </p>
              </div>
            </div>

            <div className="p-3 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded-lg text-xs text-blue-800 dark:text-blue-300 space-y-1">
              <p className="font-semibold">⚡ Action Checklist:</p>
              <ul className="list-disc pl-4 space-y-0.5">
                <li>Transition circular status from DRAFT to PUBLISHED.</li>
                <li>Activate all {circ.linked_jobs?.length || 0} linked draft roles to OPEN.</li>
                <li>Deliver single aggregated announcement to active, eligible students.</li>
                <li>Individual job publication alerts suppressed to avoid duplicates.</li>
              </ul>
            </div>

            {publishModal.errorMessage && (
              <div className="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-lg text-xs text-red-700 dark:text-red-300">
                {publishModal.errorMessage}
              </div>
            )}

            {publishModal.showSkillBypass && (
              <label className="flex items-center gap-2 p-3 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-lg cursor-pointer">
                <input
                  type="checkbox"
                  checked={publishModal.confirmNoSkills}
                  onChange={(e) =>
                    setPublishModal((prev) => ({
                      ...prev,
                      confirmNoSkills: e.target.checked,
                    }))
                  }
                  className="rounded text-amber-600 focus:ring-amber-500"
                />
                <span className="text-xs text-amber-900 dark:text-amber-200">
                  Confirm publication despite missing skill requirements.
                </span>
              </label>
            )}

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() =>
                  setPublishModal({
                    isOpen: false,
                    isPublishing: false,
                    confirmNoSkills: false,
                    errorMessage: null,
                    showSkillBypass: false,
                  })
                }
                disabled={publishModal.isPublishing}
                className="px-4 py-2 text-xs font-semibold text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmPublish}
                disabled={publishModal.isPublishing}
                className="px-5 py-2 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors cursor-pointer flex items-center gap-1.5 shadow-sm disabled:opacity-50"
              >
                {publishModal.isPublishing ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Publishing...</span>
                  </>
                ) : (
                  <span>Confirm & Publish</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CircularDetails;
