import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText,
  Search,
  Building2,
  Briefcase,
  GraduationCap,
  Calendar,
  CheckCircle2,
  Clock,
  ExternalLink,
  ChevronRight,
  Filter,
  AlertCircle,
  RefreshCw,
  Award,
  Sparkles,
  User,
  ArrowUpDown,
  X,
  Eye
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import toast from 'react-hot-toast';

const STATUS_OPTIONS = [
  { value: 'all', label: 'All Statuses' },
  { value: 'applied', label: 'Applied' },
  { value: 'shortlisted', label: 'Shortlisted' },
  { value: 'interviewing', label: 'Interviewing' },
  { value: 'offered', label: 'Offered' },
  { value: 'rejected', label: 'Rejected' },
];

const getStatusBadgeClass = (status) => {
  switch (status?.toLowerCase()) {
    case 'applied':
      return 'bg-blue-50 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300 border border-blue-200 dark:border-blue-800';
    case 'shortlisted':
      return 'bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300 border border-amber-200 dark:border-amber-800';
    case 'interviewing':
      return 'bg-purple-50 text-purple-700 dark:bg-purple-950/50 dark:text-purple-300 border border-purple-200 dark:border-purple-800';
    case 'offered':
    case 'selected':
      return 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800';
    case 'rejected':
      return 'bg-rose-50 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300 border border-rose-200 dark:border-rose-800';
    default:
      return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300';
  }
};

export default function PlacementApplications() {
  const navigate = useNavigate();
  const {
    applications,
    fetchApplications,
    updateApplication,
    companies,
    fetchCompanies,
    jobs,
    fetchJobPostings,
    isLoading,
  } = usePlacementStore();

  // Filters & State
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCompany, setSelectedCompany] = useState('all');
  const [selectedJob, setSelectedJob] = useState('all');
  const [selectedBranch, setSelectedBranch] = useState('all');
  const [selectedStatus, setSelectedStatus] = useState('all');
  const [updatingAppId, setUpdatingAppId] = useState(null);
  const [activeSnapshot, setActiveSnapshot] = useState(null);

  // Initial load
  useEffect(() => {
    fetchApplications();
    fetchCompanies();
    fetchJobPostings();
  }, [fetchApplications, fetchCompanies, fetchJobPostings]);

  // Derived filter options
  const uniqueBranches = useMemo(() => {
    if (!Array.isArray(applications)) return [];
    const set = new Set();
    applications.forEach((app) => {
      const b = app.student_branch || app.match_snapshot?.branch;
      if (b) set.add(b);
    });
    return Array.from(set).sort();
  }, [applications]);

  // Filtered applications
  const filteredApplications = useMemo(() => {
    if (!Array.isArray(applications)) return [];
    return applications.filter((app) => {
      // Search
      if (searchTerm.trim()) {
        const query = searchTerm.toLowerCase();
        const studentName = (app.student_name || '').toLowerCase();
        const studentEmail = (app.student_email || '').toLowerCase();
        const studentUsn = (app.student_usn || '').toLowerCase();
        const jobTitle = (app.job_title || '').toLowerCase();
        const companyName = (app.company_name || '').toLowerCase();
        if (
          !studentName.includes(query) &&
          !studentEmail.includes(query) &&
          !studentUsn.includes(query) &&
          !jobTitle.includes(query) &&
          !companyName.includes(query)
        ) {
          return false;
        }
      }

      // Company
      if (selectedCompany !== 'all') {
        const cId = Number(selectedCompany);
        if (app.company_id !== cId && app.job_posting?.company_id !== cId) {
          return false;
        }
      }

      // Job
      if (selectedJob !== 'all') {
        if (app.job_posting_id !== Number(selectedJob)) {
          return false;
        }
      }

      // Branch
      if (selectedBranch !== 'all') {
        const branch = app.student_branch || app.match_snapshot?.branch;
        if (branch !== selectedBranch) {
          return false;
        }
      }

      // Status
      if (selectedStatus !== 'all') {
        if (app.status?.toLowerCase() !== selectedStatus.toLowerCase()) {
          return false;
        }
      }

      return true;
    });
  }, [applications, searchTerm, selectedCompany, selectedJob, selectedBranch, selectedStatus]);

  // Summary Metrics
  const metrics = useMemo(() => {
    if (!Array.isArray(applications)) {
      return { total: 0, externalApplied: 0, shortlisted: 0, offered: 0 };
    }
    return {
      total: applications.length,
      externalApplied: applications.filter((a) => a.external_applied_at).length,
      shortlisted: applications.filter((a) => ['shortlisted', 'selected'].includes(a.status?.toLowerCase())).length,
      offered: applications.filter((a) => a.verified_offer || a.status?.toLowerCase() === 'offered').length,
    };
  }, [applications]);

  // Status update handler
  const handleStatusChange = async (appId, newStatus) => {
    setUpdatingAppId(appId);
    try {
      await updateApplication(appId, { status: newStatus });
      toast.success(`Application updated to ${newStatus}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to update application status');
    } finally {
      setUpdatingAppId(null);
    }
  };

  const handleRefresh = async () => {
    try {
      await fetchApplications();
      toast.success('Applications refreshed');
    } catch {
      toast.error('Failed to refresh applications');
    }
  };

  const resetFilters = () => {
    setSearchTerm('');
    setSelectedCompany('all');
    setSelectedJob('all');
    setSelectedBranch('all');
    setSelectedStatus('all');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 bg-indigo-50 dark:bg-indigo-950/50 rounded-lg text-indigo-600 dark:text-indigo-400">
              <FileText className="w-5 h-5" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Student Application Tracking
            </h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Track student applications across all recruitment drives, review self-reported external submissions, and manage candidate progression.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleRefresh}
            disabled={isLoading}
            className="px-3.5 py-2 border border-gray-300 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-gray-900 rounded-xl p-4 border border-gray-200 dark:border-gray-800 shadow-xs">
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Total Applications</p>
          <div className="flex items-baseline justify-between mt-2">
            <span className="text-2xl font-bold text-gray-900 dark:text-white" id="officer-metric-total-apps">
              {metrics.total}
            </span>
            <FileText className="w-4 h-4 text-indigo-500" />
          </div>
        </div>

        <div className="bg-white dark:bg-gray-900 rounded-xl p-4 border border-gray-200 dark:border-gray-800 shadow-xs">
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Marked as Applied</p>
          <div className="flex items-baseline justify-between mt-2">
            <span className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
              {metrics.externalApplied}
            </span>
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          </div>
        </div>

        <div className="bg-white dark:bg-gray-900 rounded-xl p-4 border border-gray-200 dark:border-gray-800 shadow-xs">
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Shortlisted</p>
          <div className="flex items-baseline justify-between mt-2">
            <span className="text-2xl font-bold text-amber-600 dark:text-amber-400">
              {metrics.shortlisted}
            </span>
            <Sparkles className="w-4 h-4 text-amber-500" />
          </div>
        </div>

        <div className="bg-white dark:bg-gray-900 rounded-xl p-4 border border-gray-200 dark:border-gray-800 shadow-xs">
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Verified Offers</p>
          <div className="flex items-baseline justify-between mt-2">
            <span className="text-2xl font-bold text-purple-600 dark:text-purple-400">
              {metrics.offered}
            </span>
            <Award className="w-4 h-4 text-purple-500" />
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white dark:bg-gray-900 rounded-xl p-4 border border-gray-200 dark:border-gray-800 shadow-xs space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-700 dark:text-gray-300">
            <Filter className="w-3.5 h-3.5 text-indigo-500" />
            <span>Filter Applications</span>
          </div>
          {(searchTerm || selectedCompany !== 'all' || selectedJob !== 'all' || selectedBranch !== 'all' || selectedStatus !== 'all') && (
            <button
              onClick={resetFilters}
              className="text-xs text-indigo-600 dark:text-indigo-400 font-semibold hover:underline flex items-center gap-1 cursor-pointer"
            >
              <X className="w-3 h-3" />
              <span>Reset Filters</span>
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
            <input
              type="text"
              id="officer-applications-search"
              placeholder="Search student, USN, job..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            />
          </div>

          {/* Company Filter */}
          <div>
            <select
              id="officer-applications-company-filter"
              value={selectedCompany}
              onChange={(e) => setSelectedCompany(e.target.value)}
              className="w-full px-3 py-1.5 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            >
              <option value="all">All Companies</option>
              {companies?.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>

          {/* Job Filter */}
          <div>
            <select
              id="officer-applications-job-filter"
              value={selectedJob}
              onChange={(e) => setSelectedJob(e.target.value)}
              className="w-full px-3 py-1.5 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            >
              <option value="all">All Job Postings</option>
              {jobs?.map((j) => (
                <option key={j.id} value={j.id}>{j.title}</option>
              ))}
            </select>
          </div>

          {/* Branch Filter */}
          <div>
            <select
              id="officer-applications-branch-filter"
              value={selectedBranch}
              onChange={(e) => setSelectedBranch(e.target.value)}
              className="w-full px-3 py-1.5 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            >
              <option value="all">All Branches</option>
              {uniqueBranches.map((b) => (
                <option key={b} value={b}>{b}</option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div>
            <select
              id="officer-applications-status-filter"
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="w-full px-3 py-1.5 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Applications List */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-xs overflow-hidden">
        {filteredApplications.length === 0 ? (
          <div className="text-center py-16 px-4">
            <FileText className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
              No applications match your criteria
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 max-w-sm mx-auto">
              Try adjusting your search keywords, company, job, or branch filters.
            </p>
            <button
              onClick={resetFilters}
              className="mt-4 px-4 py-2 bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
            >
              Reset All Filters
            </button>
          </div>
        ) : (
          <div className="divide-y divide-gray-100 dark:divide-gray-800">
            {filteredApplications.map((app) => (
              <div
                key={app.id}
                className="p-5 hover:bg-gray-50/75 dark:hover:bg-gray-800/40 transition-colors"
              >
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                  {/* Student & Job Details */}
                  <div className="space-y-1.5 flex-1 min-w-0">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <button
                        onClick={() => navigate(`/placement/students/${app.student_id}`)}
                        className="font-bold text-gray-900 dark:text-white text-sm hover:text-indigo-600 dark:hover:text-indigo-400 hover:underline flex items-center gap-1.5 text-left cursor-pointer"
                        title="Click to view candidate profile"
                      >
                        <User className="w-3.5 h-3.5 text-gray-400" />
                        <span>{app.student_name}</span>
                      </button>

                      {app.student_usn && (
                        <span className="px-2 py-0.5 rounded font-mono text-[11px] font-semibold bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700" title="University Seat Number (USN)">
                          {app.student_usn}
                        </span>
                      )}

                      {(app.student_branch || app.match_snapshot?.branch) && (
                        <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                          {app.student_branch || app.match_snapshot?.branch}
                        </span>
                      )}

                      {(app.student_cgpa || app.match_snapshot?.cgpa) && (
                        <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                          CGPA: {Number(app.student_cgpa || app.match_snapshot?.cgpa).toFixed(2)}
                        </span>
                      )}

                      <span className="text-xs text-gray-400">•</span>
                      <span className="text-xs text-gray-500 dark:text-gray-400">{app.student_email}</span>
                    </div>

                    {/* Job & Company Line */}
                    <div className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400 flex-wrap">
                      <span className="font-semibold text-gray-800 dark:text-gray-200 flex items-center gap-1">
                        <Briefcase className="w-3.5 h-3.5 text-indigo-500" />
                        {app.job_title || `Job #${app.job_posting_id}`}
                      </span>
                      <span>at</span>
                      <span className="font-semibold text-gray-800 dark:text-gray-200 flex items-center gap-1">
                        <Building2 className="w-3.5 h-3.5 text-gray-500" />
                        {app.company_name || 'Organization'}
                      </span>
                      <span>•</span>
                      <span>Applied: {app.applied_at ? new Date(app.applied_at).toLocaleDateString() : 'Recorded'}</span>
                    </div>

                    {/* Badges and Signals */}
                    <div className="flex items-center gap-2 flex-wrap pt-1">
                      {/* External Confirmation Badge */}
                      {app.external_applied_at ? (
                        <span
                          className="text-[11px] font-semibold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/50 px-2.5 py-0.5 rounded-full border border-emerald-200 dark:border-emerald-800 flex items-center gap-1"
                          title={`External confirmation recorded on ${new Date(app.external_applied_at).toLocaleString()}`}
                        >
                          <CheckCircle2 className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                          <span>Marked as Applied ({new Date(app.external_applied_at).toLocaleDateString()})</span>
                        </span>
                      ) : (
                        <span className="text-[10px] text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded-full">
                          Internal Drive Submission
                        </span>
                      )}

                      {/* Verified Offer */}
                      {app.verified_offer && (
                        <span className="text-[11px] font-bold text-purple-700 dark:text-purple-300 bg-purple-50 dark:bg-purple-950/50 px-2.5 py-0.5 rounded-full border border-purple-200 dark:border-purple-800 flex items-center gap-1">
                          <Award className="w-3 h-3 text-purple-600" />
                          <span>Offer: {app.verified_offer.designation || 'Verified Offer'}</span>
                        </span>
                      )}

                      {/* Match Score */}
                      {app.match_percentage !== null && app.match_percentage !== undefined && (
                        <span className="text-[11px] font-semibold text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/50 px-2 py-0.5 rounded-full border border-indigo-200 dark:border-indigo-800">
                          {Math.round(app.match_percentage)}% Match
                        </span>
                      )}

                      {/* Low match warning */}
                      {(app.has_low_match_warning || app.match_snapshot?.has_low_match_warning) && (
                        <span className="text-[10px] font-semibold text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/50 px-2 py-0.5 rounded-full border border-amber-200 dark:border-amber-800 flex items-center gap-1">
                          <AlertCircle className="w-3 h-3 text-amber-500" />
                          <span>Low match (&lt;50%)</span>
                        </span>
                      )}

                      {/* Snapshot Viewer Button */}
                      {app.match_snapshot && (
                        <button
                          onClick={() => setActiveSnapshot(app)}
                          className="text-[11px] font-medium text-gray-600 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 flex items-center gap-1 px-2 py-0.5 rounded border border-gray-200 dark:border-gray-700 hover:border-indigo-300 cursor-pointer"
                        >
                          <Eye className="w-3 h-3" />
                          <span>View Snapshot</span>
                        </button>
                      )}
                    </div>

                    {/* Recruitment Progression Timeline */}
                    {app.recruitment_progression && app.recruitment_progression.length > 0 && (
                      <div className="pt-2">
                        <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs">
                          <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">Progression:</span>
                          {app.recruitment_progression.map((r, idx) => (
                            <span
                              key={idx}
                              className={`px-2 py-0.5 rounded text-[10px] font-medium whitespace-nowrap ${
                                r.status === 'qualified'
                                  ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300'
                                  : r.status === 'eliminated'
                                  ? 'bg-rose-50 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300'
                                  : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
                              }`}
                            >
                              Round {r.round_order || idx + 1}: {r.round_name} ({r.status})
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Actions & Status Control */}
                  <div className="flex flex-row lg:flex-col items-end justify-between lg:justify-center gap-3 shrink-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500 dark:text-gray-400">Status:</span>
                      <select
                        value={app.status || 'applied'}
                        onChange={(e) => handleStatusChange(app.id, e.target.value)}
                        disabled={updatingAppId === app.id}
                        className={`text-xs font-semibold px-2.5 py-1 rounded-lg border cursor-pointer focus:ring-2 focus:ring-indigo-500 focus:outline-none ${getStatusBadgeClass(app.status)}`}
                      >
                        <option value="applied">Applied</option>
                        <option value="shortlisted">Shortlisted</option>
                        <option value="interviewing">Interviewing</option>
                        <option value="selected">Selected</option>
                        <option value="rejected">Rejected</option>
                      </select>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => navigate(`/placement/jobs/${app.job_posting_id}`)}
                        className="text-xs text-gray-600 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 flex items-center gap-1 px-2.5 py-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer"
                      >
                        <span>View Job</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Application Snapshot Modal */}
      {activeSnapshot && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-lg w-full p-6 shadow-xl border border-gray-200 dark:border-gray-800 space-y-4">
            <div className="flex items-center justify-between border-b border-gray-100 dark:border-gray-800 pb-3">
              <div>
                <h3 className="font-bold text-gray-900 dark:text-white text-base">
                  Application Snapshot
                </h3>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {activeSnapshot.student_name} • {activeSnapshot.job_title}
                </p>
              </div>
              <button
                onClick={() => setActiveSnapshot(null)}
                className="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-xl">
                <div>
                  <p className="text-gray-500 dark:text-gray-400 font-medium">Recorded CGPA</p>
                  <p className="font-bold text-gray-900 dark:text-white mt-0.5">
                    {Number(activeSnapshot.match_snapshot?.cgpa || activeSnapshot.student_cgpa || 0).toFixed(2)}
                  </p>
                </div>
                <div>
                  <p className="text-gray-500 dark:text-gray-400 font-medium">Recorded Branch</p>
                  <p className="font-bold text-gray-900 dark:text-white mt-0.5">
                    {activeSnapshot.match_snapshot?.branch || activeSnapshot.student_branch || 'Not recorded'}
                  </p>
                </div>
                <div>
                  <p className="text-gray-500 dark:text-gray-400 font-medium">Academic Eligibility</p>
                  <p className="font-bold mt-0.5">
                    {activeSnapshot.match_snapshot?.is_eligible ? (
                      <span className="text-emerald-600 dark:text-emerald-400">✓ Met Cutoffs</span>
                    ) : (
                      <span className="text-rose-600 dark:text-rose-400">✗ Ineligible</span>
                    )}
                  </p>
                </div>
                <div>
                  <p className="text-gray-500 dark:text-gray-400 font-medium">Match Score</p>
                  <p className="font-bold text-indigo-600 dark:text-indigo-400 mt-0.5">
                    {activeSnapshot.match_percentage !== null ? `${Math.round(activeSnapshot.match_percentage)}%` : 'N/A'}
                  </p>
                </div>
              </div>

              {activeSnapshot.match_snapshot?.required_skills_matched && (
                <div>
                  <p className="font-semibold text-gray-700 dark:text-gray-300 mb-1">Required Skills Matched</p>
                  <div className="flex flex-wrap gap-1">
                    {activeSnapshot.match_snapshot.required_skills_matched.map((s, i) => (
                      <span key={i} className="px-2 py-0.5 bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 rounded text-[11px] font-medium">
                        ✓ {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {activeSnapshot.match_snapshot?.required_skills_missing && activeSnapshot.match_snapshot.required_skills_missing.length > 0 && (
                <div>
                  <p className="font-semibold text-gray-700 dark:text-gray-300 mb-1">Required Skills Missing</p>
                  <div className="flex flex-wrap gap-1">
                    {activeSnapshot.match_snapshot.required_skills_missing.map((s, i) => (
                      <span key={i} className="px-2 py-0.5 bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300 rounded text-[11px] font-medium">
                        ✗ {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="pt-3 border-t border-gray-100 dark:border-gray-800 flex justify-end">
              <button
                onClick={() => setActiveSnapshot(null)}
                className="px-4 py-1.5 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-lg text-xs font-semibold hover:bg-gray-200 cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
