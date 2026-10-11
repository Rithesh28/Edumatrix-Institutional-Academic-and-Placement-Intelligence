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
  ExternalLink,
  GraduationCap,
  Sparkles,
  AlertTriangle,
  X,
  Send,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import toast from 'react-hot-toast';

const StudentRecruitmentCircularDetails = () => {
  const { id } = useParams();
  const navigate = useNavigate();

  const {
    selectedCircular,
    isCircularsLoading,
    fetchCircular,
  } = usePlacementStore();

  const [previewFile, setPreviewFile] = useState(null);

  useEffect(() => {
    fetchCircular(id).catch((err) => {
      toast.error('Could not load recruitment circular or you are not eligible.');
    });
  }, [id, fetchCircular]);

  if (isCircularsLoading && !selectedCircular) {
    return (
      <div className="p-12 text-center text-gray-500 dark:text-gray-400">
        <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-3" />
        <p>Loading recruitment circular...</p>
      </div>
    );
  }

  if (!selectedCircular) {
    return (
      <div className="p-8 text-center bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
        <p className="text-gray-500">Recruitment circular not found or restricted.</p>
        <button
          onClick={() => navigate('/student/jobs?tab=circulars')}
          className="mt-3 text-blue-600 text-sm font-semibold cursor-pointer"
        >
          &larr; Back to Campus Jobs
        </button>
      </div>
    );
  }

  const circ = selectedCircular;
  const isDeadlinePassed =
    circ.application_deadline && new Date(circ.application_deadline) < new Date();

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-16">
      {/* Back button and banner */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/student/jobs?tab=circulars')}
          className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors cursor-pointer"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{circ.title}</h1>
            <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-blue-100 dark:bg-blue-950/80 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
              Recruitment Drive
            </span>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 flex items-center gap-2">
            <span className="font-semibold text-gray-700 dark:text-gray-300">
              {circ.company_name}
            </span>
            {circ.published_at && (
              <span>• Announced: {new Date(circ.published_at).toLocaleDateString()}</span>
            )}
          </p>
        </div>
      </div>

      {/* Main Highlights Card */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 space-y-5 shadow-sm">
        {/* Key Info Tiles */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pb-4 border-b border-gray-100 dark:border-gray-800 text-xs">
          <div className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-xl">
            <Calendar className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0" />
            <div>
              <span className="text-gray-400 font-medium">Drive / Interview Date</span>
              <p className="font-semibold text-gray-900 dark:text-white mt-0.5">
                {circ.drive_date ? new Date(circ.drive_date).toLocaleString() : 'TBD / Multi-stage'}
              </p>
            </div>
          </div>

          <div
            className={`flex items-center gap-3 p-3 rounded-xl ${
              isDeadlinePassed
                ? 'bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300'
                : 'bg-gray-50 dark:bg-gray-800/50'
            }`}
          >
            <Clock
              className={`w-5 h-5 flex-shrink-0 ${
                isDeadlinePassed
                  ? 'text-red-600 dark:text-red-400'
                  : 'text-amber-600 dark:text-amber-400'
              }`}
            />
            <div>
              <span className="text-gray-400 font-medium">Application Deadline</span>
              <p className="font-semibold text-gray-900 dark:text-white mt-0.5">
                {circ.application_deadline
                  ? new Date(circ.application_deadline).toLocaleString()
                  : 'Open Until Drive'}
                {isDeadlinePassed && ' (Expired)'}
              </p>
            </div>
          </div>
        </div>

        {/* Branch Eligibility */}
        {circ.branch_eligibility && circ.branch_eligibility.length > 0 && (
          <div className="space-y-1.5">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
              <GraduationCap className="w-4 h-4 text-blue-500" />
              <span>Target Engineering Branches</span>
            </h3>
            <div className="flex flex-wrap gap-1.5 pt-1">
              {circ.branch_eligibility.map((b, i) => (
                <span
                  key={i}
                  className="px-2.5 py-1 bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800 rounded-md text-xs font-medium"
                >
                  {b}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Drive Overview */}
        {circ.summary && (
          <div className="space-y-1.5">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">
              Drive Summary
            </h3>
            <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-line">
              {circ.summary}
            </p>
          </div>
        )}

        {/* Registration Instructions */}
        {circ.instructions && (
          <div className="space-y-1.5 p-4 bg-blue-50/60 dark:bg-blue-950/30 rounded-xl border border-blue-100 dark:border-blue-900">
            <h3 className="text-xs font-bold text-blue-900 dark:text-blue-200 uppercase tracking-wider flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-blue-600 dark:text-blue-400" />
              <span>Drive & Registration Instructions</span>
            </h3>
            <p className="text-xs text-blue-950 dark:text-blue-200 leading-relaxed whitespace-pre-line mt-1">
              {circ.instructions}
            </p>
          </div>
        )}
      </div>

      {/* Linked Job Opportunities */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 space-y-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Briefcase className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            <span>Available Job Roles ({circ.linked_jobs?.length || 0})</span>
          </h2>
          <span className="text-xs text-gray-400">
            Select a role to check skill match and submit application
          </span>
        </div>

        {!circ.linked_jobs || circ.linked_jobs.length === 0 ? (
          <div className="p-6 bg-gray-50 dark:bg-gray-800/40 rounded-xl text-center text-xs text-gray-500">
            No specific roles listed for this drive announcement.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {circ.linked_jobs.map((job) => (
              <div
                key={job.id}
                className="p-5 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/30 hover:border-blue-300 dark:hover:border-blue-700 transition-all flex flex-col justify-between space-y-3"
              >
                <div>
                  <h4 className="font-bold text-base text-gray-900 dark:text-white">
                    {job.title}
                  </h4>
                  <p className="text-xs font-medium text-gray-500 mt-0.5">
                    {circ.company_name}
                  </p>

                  <div className="text-xs text-gray-500 dark:text-gray-400 space-y-1 mt-2">
                    {job.salary_range && <p>💰 Salary: {job.salary_range}</p>}
                    {job.location && <p>📍 Location: {job.location}</p>}
                    {job.experience_level && <p>🎓 Experience: {job.experience_level}</p>}
                  </div>

                  {job.required_skills && job.required_skills.length > 0 && (
                    <div className="flex flex-wrap gap-1 pt-2.5">
                      {job.required_skills.slice(0, 5).map((skill, idx) => (
                        <span
                          key={idx}
                          className="px-2 py-0.5 bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300 rounded text-[11px] font-medium"
                        >
                          {skill}
                        </span>
                      ))}
                      {job.required_skills.length > 5 && (
                        <span className="text-[11px] text-gray-400 self-center">
                          +{job.required_skills.length - 5} more
                        </span>
                      )}
                    </div>
                  )}
                </div>

                <div className="pt-3 border-t border-gray-200 dark:border-gray-700 flex justify-end">
                  <button
                    onClick={() => navigate(`/student/jobs/${job.job_posting_id}`)}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-sm"
                  >
                    <span>View Role & Apply</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Official Attachments */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 space-y-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Paperclip className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            <span>Drive Attachments ({circ.attachments?.length || 0})</span>
          </h2>
          <span className="text-xs text-gray-400">
            Preview posters, JDs, or spreadsheets
          </span>
        </div>

        {!circ.attachments || circ.attachments.length === 0 ? (
          <div className="p-6 bg-gray-50 dark:bg-gray-800/40 rounded-xl text-center text-xs text-gray-500">
            No official attachments for this recruitment circular.
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {circ.attachments.map((att) => (
              <div
                key={att.id}
                className="p-3 bg-gray-50 dark:bg-gray-800/40 rounded-xl border border-gray-200 dark:border-gray-700 flex items-center justify-between gap-3 text-xs"
              >
                <div className="flex items-center gap-2.5 overflow-hidden">
                  <div className="p-2 bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400 rounded-lg flex-shrink-0">
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
                    className="p-1.5 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950/50 rounded-lg transition-colors cursor-pointer"
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
    </div>
  );
};

export default StudentRecruitmentCircularDetails;
