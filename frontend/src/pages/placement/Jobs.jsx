import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Briefcase,
  Plus,
  Search,
  Eye,
  Edit2,
  Trash2,
  Building2,
  ArrowLeft,
  Users,
  Send,
  AlertTriangle,
  CheckCircle2,
  Calendar,
  Sparkles,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import toast from 'react-hot-toast';

const Jobs = () => {
  const navigate = useNavigate();
  const { jobs, isLoading, fetchJobPostings, deleteJobPosting, publishJobPosting } = usePlacementStore();
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // Publish confirmation modal state
  const [publishModal, setPublishModal] = useState({
    isOpen: false,
    job: null,
    isPublishing: false,
    needsEmptySkillsConfirmation: false,
  });

  useEffect(() => {
    fetchJobPostings();
  }, []);

  const handleDelete = async (id, title) => {
    if (window.confirm(`Are you sure you want to delete "${title}"?`)) {
      try {
        await deleteJobPosting(id);
        toast.success('Job deleted successfully');
      } catch (error) {
        toast.error('Failed to delete job');
      }
    }
  };

  const handleOpenPublishModal = (job) => {
    setPublishModal({
      isOpen: true,
      job,
      isPublishing: false,
      needsEmptySkillsConfirmation: false,
    });
  };

  const handleClosePublishModal = () => {
    setPublishModal({
      isOpen: false,
      job: null,
      isPublishing: false,
      needsEmptySkillsConfirmation: false,
    });
  };

  const handleConfirmPublish = async (confirmNoSkills = false) => {
    if (!publishModal.job) return;
    setPublishModal((prev) => ({ ...prev, isPublishing: true }));

    try {
      await publishJobPosting(publishModal.job.id, confirmNoSkills);
      toast.success(`Job "${publishModal.job.title}" published successfully!`);
      handleClosePublishModal();
      fetchJobPostings();
    } catch (error) {
      const errMsg = error.response?.data?.detail || error.message || '';
      // Check if backend rejected due to missing skills
      if (
        typeof errMsg === 'string' &&
        (errMsg.toLowerCase().includes('no required or preferred skills') ||
          errMsg.toLowerCase().includes('confirm_no_skills'))
      ) {
        setPublishModal((prev) => ({
          ...prev,
          isPublishing: false,
          needsEmptySkillsConfirmation: true,
        }));
      } else {
        toast.error(errMsg || 'Failed to publish job');
        setPublishModal((prev) => ({ ...prev, isPublishing: false }));
      }
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'open':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
            ● OPEN
          </span>
        );
      case 'draft':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
            ○ DRAFT
          </span>
        );
      case 'closed':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
            ✕ CLOSED
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-600">
            {status?.toUpperCase()}
          </span>
        );
    }
  };

  const filteredJobs = jobs.filter((job) => {
    const matchesSearch =
      job.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      job.company_name?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = !statusFilter || job.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const draftJobsCount = jobs.filter((j) => j.status === 'draft').length;
  const openJobsCount = jobs.filter((j) => j.status === 'open').length;

  if (isLoading && jobs.length === 0) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-indigo-600 border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="pb-12">
      {/* Back Button */}
      <button
        onClick={() => navigate('/placement/dashboard')}
        className="flex items-center space-x-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white mb-4 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Dashboard</span>
      </button>

      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Briefcase className="w-6 h-6 text-indigo-600 dark:text-indigo-400" />
            Job Postings & Management
          </h1>
          <p className="text-gray-500 dark:text-gray-400 text-sm mt-0.5">
            Manage company openings, parse JDs, publish drafts, and run AI candidate skill matching
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/placement/jobs/post')}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg flex items-center space-x-2 shadow-sm transition-colors cursor-pointer font-medium text-sm"
          >
            <Plus className="w-4 h-4" />
            <span>Post / Import Job</span>
          </button>
        </div>
      </div>

      {/* Status Highlights */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div
          onClick={() => setStatusFilter('')}
          className={`p-4 rounded-xl border transition-all cursor-pointer ${
            statusFilter === ''
              ? 'bg-indigo-50/70 dark:bg-indigo-950/40 border-indigo-300 dark:border-indigo-800 shadow-sm'
              : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 hover:border-gray-300'
          }`}
        >
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Total Postings</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">{jobs.length}</p>
        </div>
        <div
          onClick={() => setStatusFilter('open')}
          className={`p-4 rounded-xl border transition-all cursor-pointer ${
            statusFilter === 'open'
              ? 'bg-emerald-50/70 dark:bg-emerald-950/40 border-emerald-300 dark:border-emerald-800 shadow-sm'
              : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 hover:border-gray-300'
          }`}
        >
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Open (Active)</p>
          <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">{openJobsCount}</p>
        </div>
        <div
          onClick={() => setStatusFilter('draft')}
          className={`p-4 rounded-xl border transition-all cursor-pointer ${
            statusFilter === 'draft'
              ? 'bg-amber-50/70 dark:bg-amber-950/40 border-amber-300 dark:border-amber-800 shadow-sm'
              : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 hover:border-gray-300'
          }`}
        >
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Drafts (Pending Publish)</p>
          <p className="text-2xl font-bold text-amber-600 dark:text-amber-400 mt-1">{draftJobsCount}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-4 mb-6">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by job title or company name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-4 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
        >
          <option value="">All Statuses</option>
          <option value="open">Open Only</option>
          <option value="draft">Drafts Only</option>
          <option value="closed">Closed Only</option>
        </select>
      </div>

      {/* Jobs List */}
      {filteredJobs.length === 0 ? (
        <div className="text-center py-16 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
          <Briefcase className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
          <p className="text-gray-500 dark:text-gray-400 font-medium">No job postings found</p>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            {searchTerm || statusFilter ? 'Try clearing your filters' : 'Create your first job posting or parse a JD document'}
          </p>
          <button
            onClick={() => navigate('/placement/jobs/post')}
            className="mt-4 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-colors cursor-pointer"
          >
            Post / Import Job
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredJobs.map((job) => (
            <div
              key={job.id}
              className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800 p-5 hover:shadow-md transition-shadow"
            >
              <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center space-x-3 mb-1.5">
                    {getStatusBadge(job.status)}
                    <span className="text-xs text-gray-400 dark:text-gray-500 flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      {job.created_at ? new Date(job.created_at).toLocaleDateString() : 'Recently'}
                    </span>
                    {job.status === 'draft' && (
                      <span className="text-xs text-amber-600 dark:text-amber-400 font-medium">
                        (Draft — Review and publish to activate)
                      </span>
                    )}
                  </div>

                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white hover:text-indigo-600 dark:hover:text-indigo-400 cursor-pointer transition-colors"
                      onClick={() => navigate(`/placement/jobs/${job.id}`)}>
                    {job.title}
                  </h3>

                  <p className="text-sm text-gray-600 dark:text-gray-300 flex items-center space-x-2 mt-1">
                    <Building2 className="w-4 h-4 text-gray-400" />
                    <span className="font-medium">{job.company_name || 'Assigned Company'}</span>
                    {job.location && <span className="text-gray-400 dark:text-gray-500">• {job.location}</span>}
                    {job.salary_range && <span className="text-gray-400 dark:text-gray-500">• {job.salary_range}</span>}
                  </p>

                  {/* Skills badges */}
                  <div className="flex flex-wrap items-center gap-1.5 mt-3">
                    {job.required_skills?.slice(0, 5).map((skill, idx) => (
                      <span
                        key={idx}
                        className="text-xs px-2.5 py-0.5 bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 rounded-full font-medium"
                      >
                        {skill}
                      </span>
                    ))}
                    {job.required_skills?.length > 5 && (
                      <span className="text-xs px-2 py-0.5 bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 rounded-full">
                        +{job.required_skills.length - 5} required
                      </span>
                    )}

                    {job.preferred_skills?.slice(0, 3).map((skill, idx) => (
                      <span
                        key={`pref-${idx}`}
                        className="text-xs px-2.5 py-0.5 bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800 rounded-full font-medium"
                      >
                        {skill} (pref)
                      </span>
                    ))}
                    {job.preferred_skills?.length > 3 && (
                      <span className="text-xs px-2 py-0.5 bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 rounded-full">
                        +{job.preferred_skills.length - 3} pref
                      </span>
                    )}

                    {(!job.required_skills || job.required_skills.length === 0) &&
                      (!job.preferred_skills || job.preferred_skills.length === 0) && (
                        <span className="text-xs text-amber-500 dark:text-amber-400 italic">
                          No skill requirements defined yet
                        </span>
                      )}
                  </div>

                  {/* Criteria row */}
                  <div className="flex flex-wrap items-center gap-4 text-xs text-gray-500 dark:text-gray-400 mt-2.5">
                    {job.cgpa_criteria !== null && job.cgpa_criteria !== undefined && (
                      <span>📊 Min CGPA: <strong className="text-gray-700 dark:text-gray-200">{job.cgpa_criteria}</strong></span>
                    )}
                    {job.branch_eligibility?.length > 0 && (
                      <span>🎓 Branches: <strong className="text-gray-700 dark:text-gray-200">{job.branch_eligibility.join(', ')}</strong></span>
                    )}
                    {job.experience_level && (
                      <span>⏳ Exp: <strong className="text-gray-700 dark:text-gray-200">{job.experience_level}</strong></span>
                    )}
                  </div>
                </div>

                {/* Actions Button Group */}
                <div className="flex flex-wrap items-center gap-2 self-start lg:self-center">
                  {/* Publish button if draft */}
                  {job.status === 'draft' && (
                    <button
                      onClick={() => handleOpenPublishModal(job)}
                      className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold flex items-center space-x-1.5 shadow-sm transition-colors cursor-pointer"
                      title="Publish this job posting"
                    >
                      <Send className="w-3.5 h-3.5" />
                      <span>Publish</span>
                    </button>
                  )}

                  {/* View Matches button */}
                  <button
                    onClick={() => navigate(`/placement/jobs/${job.id}?tab=matches`)}
                    className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold flex items-center space-x-1.5 shadow-sm transition-colors cursor-pointer"
                    title="View candidate skill match analysis"
                  >
                    <Users className="w-3.5 h-3.5" />
                    <span>View Matches</span>
                  </button>

                  {/* View Details */}
                  <button
                    onClick={() => navigate(`/placement/jobs/${job.id}`)}
                    className="p-2 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                    title="View Details"
                  >
                    <Eye className="w-4 h-4" />
                  </button>

                  {/* Edit */}
                  <button
                    onClick={() => navigate(`/placement/jobs/${job.id}/edit`)}
                    className="p-2 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                    title="Edit Job"
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>

                  {/* Delete */}
                  <button
                    onClick={() => handleDelete(job.id, job.title)}
                    className="p-2 text-gray-400 hover:text-rose-600 dark:hover:text-rose-400 rounded-lg hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors"
                    title="Delete Job"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Publish Confirmation Modal */}
      {publishModal.isOpen && publishModal.job && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-md w-full p-6 shadow-xl border border-gray-200 dark:border-gray-800">
            {publishModal.needsEmptySkillsConfirmation ? (
              // Empty skills warning modal
              <div>
                <div className="w-12 h-12 rounded-full bg-amber-100 dark:bg-amber-950/50 text-amber-600 dark:text-amber-400 flex items-center justify-center mb-4">
                  <AlertTriangle className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                  Publish Without Skills?
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
                  Job <span className="font-semibold text-gray-900 dark:text-white">"{publishModal.job.title}"</span> has no required or preferred skills defined.
                </p>
                <div className="mt-3 p-3 bg-amber-50 dark:bg-amber-950/30 rounded-xl border border-amber-200 dark:border-amber-800 text-xs text-amber-800 dark:text-amber-300">
                  ⚠️ Candidate match scores will be marked as <strong>"Not calculated"</strong> because no skill overlap can be evaluated.
                </div>
                <div className="mt-6 flex space-x-3">
                  <button
                    type="button"
                    disabled={publishModal.isPublishing}
                    onClick={() => handleConfirmPublish(true)}
                    className="flex-1 px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-sm font-medium transition-colors cursor-pointer"
                  >
                    {publishModal.isPublishing ? 'Publishing...' : 'Yes, Publish Anyway'}
                  </button>
                  <button
                    type="button"
                    disabled={publishModal.isPublishing}
                    onClick={handleClosePublishModal}
                    className="px-4 py-2 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg text-sm font-medium transition-colors cursor-pointer"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              // Standard publish confirmation modal
              <div>
                <div className="w-12 h-12 rounded-full bg-emerald-100 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mb-4">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                  Publish Job Posting
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
                  Are you sure you want to publish <span className="font-semibold text-gray-900 dark:text-white">"{publishModal.job.title}"</span>?
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  This will transition its status from <strong>DRAFT</strong> to <strong>OPEN</strong> and enable student skill matching.
                </p>
                <div className="mt-6 flex space-x-3">
                  <button
                    type="button"
                    disabled={publishModal.isPublishing}
                    onClick={() => handleConfirmPublish(false)}
                    className="flex-1 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-medium transition-colors cursor-pointer"
                  >
                    {publishModal.isPublishing ? 'Publishing...' : 'Publish Job'}
                  </button>
                  <button
                    type="button"
                    disabled={publishModal.isPublishing}
                    onClick={handleClosePublishModal}
                    className="px-4 py-2 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg text-sm font-medium transition-colors cursor-pointer"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default Jobs;