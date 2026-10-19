import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Briefcase,
  Search,
  Building2,
  Calendar,
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  AlertCircle,
  RefreshCw,
  Filter,
  ArrowRight,
  X,
  ExternalLink,
  Award,
  Layers,
  FileText,
  MapPin,
  Banknote,
  Sparkles,
  ChevronRight,
  Info,
  TrendingUp,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import { useAuthStore } from '../../store/authStore';
import StudentVerifiedOfferCard from '../../components/placement/StudentVerifiedOfferCard';
import StudentRecruitmentTimeline from '../../components/placement/StudentRecruitmentTimeline';

function StudentApplications() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const {
    myApplications,
    isMyApplicationsLoading,
    myApplicationsError,
    fetchMyApplications,
    myOffers,
    isMyOffersLoading,
    fetchMyOffers,
    jobs,
    fetchJobPostings,
  } = usePlacementStore();

  // Search & Filter State
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all'); // 'all' | 'applied' | 'shortlisted' | 'selected' | 'rejected'
  const [sortBy, setSortBy] = useState('newest'); // 'newest' | 'oldest' | 'score_desc' | 'score_asc'
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Snapshot Inspection Modal State
  const [selectedSnapshotApp, setSelectedSnapshotApp] = useState(null);

  // Timeline Inspection Modal State (Stage 3.3.6)
  const [selectedTimelineApp, setSelectedTimelineApp] = useState(null);

  // Fetch applications, verified offers, and job catalog
  const loadData = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await Promise.allSettled([
        fetchMyApplications(user?.id),
        fetchMyOffers(),
        fetchJobPostings(),
      ]);
    } finally {
      setIsRefreshing(false);
    }
  }, [fetchMyApplications, fetchMyOffers, fetchJobPostings, user?.id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Lookup map for parent job postings (provides fallback for location, salary, etc.)
  const jobMap = useMemo(() => {
    const map = new Map();
    if (Array.isArray(jobs)) {
      jobs.forEach((j) => {
        if (j.id) map.set(j.id, j);
      });
    }
    return map;
  }, [jobs]);

  // Derive counts from actual student application data without double counting
  const counts = useMemo(() => {
    const stats = {
      total: 0,
      applied: 0,
      shortlisted: 0,
      selected: 0,
      rejected: 0,
    };

    if (Array.isArray(myApplications)) {
      stats.total = myApplications.length;
      myApplications.forEach((app) => {
        const s = app.status?.toLowerCase();
        if (s === 'applied') stats.applied += 1;
        else if (s === 'shortlisted') stats.shortlisted += 1;
        else if (s === 'selected') stats.selected += 1;
        else if (s === 'rejected') stats.rejected += 1;
      });
    }
    return stats;
  }, [myApplications]);

  // Filter and sort applications without mutating store
  const filteredApplications = useMemo(() => {
    if (!Array.isArray(myApplications)) return [];

    const query = searchTerm.trim().toLowerCase();

    return myApplications
      .filter((app) => {
        const parentJob = jobMap.get(app.job_posting_id);
        const title = app.job_title || parentJob?.title || '';
        const company = app.company_name || parentJob?.company_name || '';

        // Search query
        if (query) {
          const matchTitle = title.toLowerCase().includes(query);
          const matchCompany = company.toLowerCase().includes(query);
          if (!matchTitle && !matchCompany) return false;
        }

        // Status filter
        if (statusFilter !== 'all') {
          if (app.status?.toLowerCase() !== statusFilter.toLowerCase()) {
            return false;
          }
        }

        return true;
      })
      .sort((a, b) => {
        if (sortBy === 'oldest') {
          return new Date(a.applied_at || 0) - new Date(b.applied_at || 0);
        }
        if (sortBy === 'score_desc') {
          const scoreA = a.match_percentage !== null && a.match_percentage !== undefined ? a.match_percentage : -1;
          const scoreB = b.match_percentage !== null && b.match_percentage !== undefined ? b.match_percentage : -1;
          return scoreB - scoreA;
        }
        if (sortBy === 'score_asc') {
          const scoreA = a.match_percentage !== null && a.match_percentage !== undefined ? a.match_percentage : 999;
          const scoreB = b.match_percentage !== null && b.match_percentage !== undefined ? b.match_percentage : 999;
          return scoreA - scoreB;
        }
        // Default: newest first
        return new Date(b.applied_at || 0) - new Date(a.applied_at || 0);
      });
  }, [myApplications, searchTerm, statusFilter, sortBy, jobMap]);

  const hasActiveFilters = Boolean(searchTerm) || statusFilter !== 'all' || sortBy !== 'newest';

  const clearAllFilters = () => {
    setSearchTerm('');
    setStatusFilter('all');
    setSortBy('newest');
  };

  // Helper for status badge presentation
  const getStatusBadge = (status) => {
    const s = status?.toLowerCase();
    switch (s) {
      case 'shortlisted':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 dark:bg-emerald-950/70 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
            <CheckCircle2 className="w-3 h-3" />
            <span>Shortlisted</span>
          </span>
        );
      case 'selected':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-100 dark:bg-purple-950/70 text-purple-800 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
            <Award className="w-3 h-3" />
            <span>Selected</span>
          </span>
        );
      case 'rejected':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 dark:bg-rose-950/70 text-rose-800 dark:text-rose-300 border border-rose-200 dark:border-rose-800">
            <XCircle className="w-3 h-3" />
            <span>Not Selected</span>
          </span>
        );
      case 'applied':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 dark:bg-blue-950/70 text-blue-800 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
            <Clock className="w-3 h-3" />
            <span>Applied</span>
          </span>
        );
    }
  };

  return (
    <div className="space-y-6 pb-16">
      {/* Header Section */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <span>My Placement Applications</span>
            <span className="text-xs font-semibold px-2 py-0.5 bg-blue-100 dark:bg-blue-950/80 text-blue-700 dark:text-blue-300 rounded-full border border-blue-200 dark:border-blue-800">
              Student Tracker
            </span>
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Track the status of your submitted applications and review your application snapshots.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadData}
            disabled={isMyApplicationsLoading || isRefreshing}
            className="px-3 py-2 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
            title="Refresh application status"
          >
            <RefreshCw className={`w-4 h-4 ${isMyApplicationsLoading || isRefreshing ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Verified Placement Offers Section (Stage 3.3.6) */}
      {Array.isArray(myOffers) && myOffers.length > 0 && (
        <div className="space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-emerald-100 dark:bg-emerald-950/70 text-emerald-600 dark:text-emerald-400">
                <Award className="w-5 h-5" />
              </span>
              <div>
                <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
                  <span>Verified Placement Offers</span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-950/70 text-emerald-800 dark:text-emerald-300 font-extrabold">
                    {myOffers.length}
                  </span>
                </h2>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Official employer offers verified by the Placement Cell. Review terms and record your decision below.
                </p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {myOffers.map((offer) => (
              <StudentVerifiedOfferCard
                key={offer.id}
                offer={offer}
                onOfferUpdated={loadData}
              />
            ))}
          </div>
        </div>
      )}

      {/* Status Counters Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <div
          onClick={() => setStatusFilter('all')}
          className={`p-3.5 rounded-xl border transition-all cursor-pointer shadow-xs ${
            statusFilter === 'all'
              ? 'bg-blue-50/70 dark:bg-blue-950/40 border-blue-300 dark:border-blue-800'
              : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 hover:border-gray-300'
          }`}
        >
          <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
            Total Submitted
          </span>
          <p className="text-xl font-bold text-gray-900 dark:text-white mt-0.5">
            {isMyApplicationsLoading ? '...' : counts.total}
          </p>
        </div>

        <div
          onClick={() => setStatusFilter('applied')}
          className={`p-3.5 rounded-xl border transition-all cursor-pointer shadow-xs ${
            statusFilter === 'applied'
              ? 'bg-blue-50/70 dark:bg-blue-950/40 border-blue-300 dark:border-blue-800'
              : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 hover:border-gray-300'
          }`}
        >
          <span className="text-[11px] font-medium text-blue-600 dark:text-blue-400 uppercase tracking-wider">
            Under Review
          </span>
          <p className="text-xl font-bold text-blue-600 dark:text-blue-400 mt-0.5">
            {isMyApplicationsLoading ? '...' : counts.applied}
          </p>
        </div>

        <div
          onClick={() => setStatusFilter('shortlisted')}
          className={`p-3.5 rounded-xl border transition-all cursor-pointer shadow-xs ${
            statusFilter === 'shortlisted'
              ? 'bg-emerald-50/70 dark:bg-emerald-950/40 border-emerald-300 dark:border-emerald-800'
              : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 hover:border-gray-300'
          }`}
        >
          <span className="text-[11px] font-medium text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">
            Shortlisted
          </span>
          <p className="text-xl font-bold text-emerald-600 dark:text-emerald-400 mt-0.5">
            {isMyApplicationsLoading ? '...' : counts.shortlisted}
          </p>
        </div>

        <div
          onClick={() => setStatusFilter('selected')}
          className={`p-3.5 rounded-xl border transition-all cursor-pointer shadow-xs ${
            statusFilter === 'selected'
              ? 'bg-purple-50/70 dark:bg-purple-950/40 border-purple-300 dark:border-purple-800'
              : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 hover:border-gray-300'
          }`}
        >
          <span className="text-[11px] font-medium text-purple-600 dark:text-purple-400 uppercase tracking-wider">
            Selected / Offers
          </span>
          <p className="text-xl font-bold text-purple-600 dark:text-purple-400 mt-0.5">
            {isMyApplicationsLoading ? '...' : counts.selected}
          </p>
        </div>

        <div
          onClick={() => setStatusFilter('rejected')}
          className={`p-3.5 rounded-xl border transition-all cursor-pointer shadow-xs ${
            statusFilter === 'rejected'
              ? 'bg-rose-50/70 dark:bg-rose-950/40 border-rose-300 dark:border-rose-800'
              : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 hover:border-gray-300'
          }`}
        >
          <span className="text-[11px] font-medium text-rose-600 dark:text-rose-400 uppercase tracking-wider">
            Not Selected
          </span>
          <p className="text-xl font-bold text-rose-600 dark:text-rose-400 mt-0.5">
            {isMyApplicationsLoading ? '...' : counts.rejected}
          </p>
        </div>
      </div>

      {/* Search and Filter Controls */}
      <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm space-y-3">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
            <input
              type="text"
              id="student-applications-search"
              placeholder="Search applications by job title or company..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-9 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm('')}
                className="absolute right-3 top-2.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 cursor-pointer"
                title="Clear search"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          <div className="flex gap-2">
            <select
              id="student-applications-status-filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <option value="all">All Statuses ({counts.total})</option>
              <option value="applied">Applied ({counts.applied})</option>
              <option value="shortlisted">Shortlisted ({counts.shortlisted})</option>
              <option value="selected">Selected ({counts.selected})</option>
              <option value="rejected">Not Selected ({counts.rejected})</option>
            </select>

            <select
              id="student-applications-sort-filter"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <option value="newest">Applied: Newest First</option>
              <option value="oldest">Applied: Oldest First</option>
              <option value="score_desc">Match Score: Highest First</option>
              <option value="score_asc">Match Score: Lowest First</option>
            </select>

            {hasActiveFilters && (
              <button
                onClick={clearAllFilters}
                className="px-2.5 py-1.5 text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1 cursor-pointer"
              >
                <X className="w-3.5 h-3.5" />
                <span>Reset</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      {isMyApplicationsLoading && myApplications.length === 0 ? (
        // Loading Skeletons
        <div className="space-y-4">
          {[1, 2, 3].map((idx) => (
            <div
              key={idx}
              className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 p-5 shadow-sm animate-pulse space-y-4"
            >
              <div className="flex justify-between items-start">
                <div className="space-y-2 flex-1">
                  <div className="h-4 bg-gray-200 dark:bg-gray-800 rounded w-1/4"></div>
                  <div className="h-6 bg-gray-300 dark:bg-gray-700 rounded w-1/2"></div>
                </div>
                <div className="h-6 bg-gray-200 dark:bg-gray-800 rounded-full w-20"></div>
              </div>
              <div className="h-4 bg-gray-200 dark:bg-gray-800 rounded w-1/3"></div>
              <div className="h-10 bg-gray-100 dark:bg-gray-800 rounded-xl"></div>
            </div>
          ))}
        </div>
      ) : myApplicationsError ? (
        // Error State with Retry
        <div className="text-center py-16 bg-white dark:bg-gray-900 rounded-2xl border border-red-200 dark:border-red-900/60 p-8 shadow-sm space-y-3">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto" />
          <h2 className="text-lg font-bold text-gray-900 dark:text-white">Failed to Load Applications</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">{myApplicationsError}</p>
          <button
            onClick={loadData}
            className="mt-3 px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-semibold transition-colors inline-flex items-center gap-2 cursor-pointer"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Try Again</span>
          </button>
        </div>
      ) : myApplications.length === 0 ? (
        // Empty State: 0 Applications
        <div className="text-center py-20 bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 p-8 shadow-sm space-y-4">
          <Briefcase className="w-14 h-14 text-gray-300 dark:text-gray-600 mx-auto" />
          <h2 className="text-lg font-bold text-gray-900 dark:text-white">No Applications Submitted Yet</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
            You have not applied to any campus placement drives yet. Browse open drives to review requirements and apply.
          </p>
          <button
            onClick={() => navigate('/student/jobs')}
            className="mt-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-bold transition-all shadow-sm inline-flex items-center gap-2 cursor-pointer"
          >
            <span>Browse Campus Jobs</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      ) : filteredApplications.length === 0 ? (
        // Filtered Empty State
        <div className="text-center py-16 bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 p-8 shadow-sm space-y-3">
          <Search className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto" />
          <h2 className="text-base font-bold text-gray-900 dark:text-white">No Matching Applications Found</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
            None of your applications match your selected filters. Try broadening your keywords or resetting filters.
          </p>
          <button
            onClick={clearAllFilters}
            className="mt-3 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold cursor-pointer"
          >
            Reset Filters
          </button>
        </div>
      ) : (
        // Populated Applications List
        <div className="space-y-4">
          {filteredApplications.map((app) => {
            const parentJob = jobMap.get(app.job_posting_id);
            const title = app.job_title || parentJob?.title || `Position #${app.job_posting_id}`;
            const company = app.company_name || parentJob?.company_name || 'Assigned Company';
            const location = parentJob?.location || app.match_snapshot?.job_criteria?.location;
            const salary = parentJob?.salary_range || app.match_snapshot?.job_criteria?.salary_range;
            const snapshot = app.match_snapshot;
            const hasSnapshot = Boolean(snapshot && typeof snapshot === 'object');

            return (
              <div
                key={app.id}
                className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700 p-5 shadow-xs transition-all space-y-4"
              >
                {/* Header: Company, Title, Status */}
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center gap-2 text-xs font-semibold text-blue-600 dark:text-blue-400">
                      <Building2 className="w-3.5 h-3.5" />
                      <span className="truncate">{company}</span>
                    </div>
                    <h3
                      onClick={() => navigate(`/student/jobs/${app.job_posting_id}`)}
                      className="text-lg font-bold text-gray-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400 cursor-pointer transition-colors"
                      title="View job posting details"
                    >
                      {title}
                    </h3>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 self-start sm:self-auto flex-shrink-0">
                    {/* Official round status */}
                    {getStatusBadge(app.status)}

                    {/* External confirmation badge */}
                    {app.external_applied_at ? (
                      <span
                        className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 dark:bg-emerald-950/50 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800"
                        title={`Student confirmed external submission on ${new Date(app.external_applied_at).toLocaleString()}`}
                      >
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                        <span>External: Confirmed ({new Date(app.external_applied_at).toLocaleDateString()})</span>
                      </span>
                    ) : parentJob?.application_url ? (
                      <span
                        className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 dark:bg-amber-950/50 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800"
                        title="Application created internally on EduMatrix. External company submission not yet confirmed."
                      >
                        <Clock className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
                        <span>External: Pending</span>
                      </span>
                    ) : (
                      <span
                        className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-700"
                        title="Standard campus placement drive application"
                      >
                        <span>Internal Drive</span>
                      </span>
                    )}
                  </div>
                </div>

                {/* Metadata Row: Submission Date, Location, Salary, Authoritative Score */}
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-gray-500 dark:text-gray-400 pt-1">
                  <span className="flex items-center gap-1.5" title="Date of application">
                    <Calendar className="w-3.5 h-3.5 text-gray-400" />
                    <span>
                      Applied:{' '}
                      <strong className="text-gray-700 dark:text-gray-300 font-semibold">
                        {app.applied_at ? new Date(app.applied_at).toLocaleDateString() : 'Recorded'}
                      </strong>
                    </span>
                  </span>

                  {app.external_applied_at && (
                    <span className="flex items-center gap-1.5" title="Date external application was confirmed">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      <span>
                        External Confirmed:{' '}
                        <strong className="text-emerald-800 dark:text-emerald-300 font-semibold">
                          {new Date(app.external_applied_at).toLocaleDateString()}
                        </strong>
                      </span>
                    </span>
                  )}

                  {(app.job_deadline || parentJob?.application_deadline) && (
                    <span className="flex items-center gap-1.5" title="Job Application Deadline">
                      <Clock className="w-3.5 h-3.5 text-gray-400" />
                      <span>
                        Deadline:{' '}
                        <strong className="text-gray-700 dark:text-gray-300 font-semibold">
                          {new Date(app.job_deadline || parentJob.application_deadline).toLocaleDateString()}
                        </strong>
                      </span>
                    </span>
                  )}

                  {(app.job_status || parentJob?.status) && (
                    <span
                      className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                        (app.job_status || parentJob?.status) === 'open'
                          ? 'bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800'
                          : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-700'
                      }`}
                      title={`Job posting status is ${(app.job_status || parentJob?.status)?.toUpperCase()}`}
                    >
                      {(app.job_status || parentJob?.status)?.toUpperCase()}
                    </span>
                  )}

                  {location && (
                    <span className="flex items-center gap-1.5" title="Location">
                      <MapPin className="w-3.5 h-3.5 text-gray-400" />
                      <span>{location}</span>
                    </span>
                  )}

                  {salary && (
                    <span className="flex items-center gap-1.5 text-emerald-700 dark:text-emerald-400 font-semibold" title="Salary / CTC">
                      <Banknote className="w-3.5 h-3.5" />
                      <span>{salary}</span>
                    </span>
                  )}

                  {/* Authoritative Server Match Score */}
                  <span
                    className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800 text-blue-800 dark:text-blue-300 font-semibold"
                    title="Authoritative match score calculated by server"
                  >
                    <Sparkles className="w-3 h-3 text-blue-600 dark:text-blue-400" />
                    <span>
                      Match Score:{' '}
                      {app.match_percentage !== null && app.match_percentage !== undefined
                        ? `${Math.round(app.match_percentage)}%`
                        : snapshot?.match_percentage !== null && snapshot?.match_percentage !== undefined
                        ? `${Math.round(snapshot.match_percentage)}%`
                        : 'Not calculated'}
                    </span>
                  </span>

                  {/* Low Match Warning Badge */}
                  {app.has_low_match_warning && (
                    <span
                      className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-50 dark:bg-amber-950/60 border border-amber-300 dark:border-amber-800 text-amber-800 dark:text-amber-300 font-semibold"
                      title={app.low_match_warning || 'Required skill match was below 50% at submission'}
                    >
                      <AlertTriangle className="w-3 h-3 text-amber-600" />
                      <span>Low Match Advisory</span>
                    </span>
                  )}
                </div>

                {/* Verified Offer or Recruitment Progression Highlights */}
                {app.verified_offer && (
                  <div className="p-3 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-xl flex items-center justify-between text-xs text-emerald-900 dark:text-emerald-200">
                    <div className="flex items-center gap-2">
                      <Award className="w-4 h-4 text-emerald-600 shrink-0" />
                      <span>
                        <strong>Verified Placement Offer Extended:</strong>{' '}
                        {app.verified_offer.designation || 'Offer Available'}
                        {app.verified_offer.ctc_lpa ? ` • ${app.verified_offer.ctc_lpa} LPA` : ''}
                      </span>
                    </div>
                    <span className="uppercase text-[10px] font-bold px-2 py-0.5 bg-emerald-100 dark:bg-emerald-900 text-emerald-800 dark:text-emerald-200 rounded-full">
                      {app.verified_offer.acceptance_status || 'OFFERED'}
                    </span>
                  </div>
                )}

                {Array.isArray(app.recruitment_progression) && app.recruitment_progression.length > 0 && !app.verified_offer && (
                  <div className="p-2.5 bg-purple-50/60 dark:bg-purple-950/30 border border-purple-200/60 dark:border-purple-800/50 rounded-xl flex items-center gap-2 text-xs text-purple-900 dark:text-purple-200">
                    <TrendingUp className="w-3.5 h-3.5 text-purple-600 shrink-0" />
                    <span>
                      <strong>Latest Round Outcome:</strong>{' '}
                      Round {app.recruitment_progression[app.recruitment_progression.length - 1].round_number}:{' '}
                      {app.recruitment_progression[app.recruitment_progression.length - 1].round_name || 'Interview'}{' '}
                      — <span className="font-semibold uppercase">{app.recruitment_progression[app.recruitment_progression.length - 1].outcome}</span>
                    </span>
                  </div>
                )}

                {/* Candidate Notes if any */}
                {app.notes && (
                  <div className="p-2.5 bg-gray-50 dark:bg-gray-800/40 rounded-xl text-xs text-gray-600 dark:text-gray-300 flex items-start gap-2">
                    <FileText className="w-3.5 h-3.5 text-gray-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <span className="font-semibold text-gray-700 dark:text-gray-300">Application Notes:</span>{' '}
                      <span>{app.notes}</span>
                    </div>
                  </div>
                )}

                {/* Snapshot Summary Strip */}
                <div className="pt-2 border-t border-gray-100 dark:border-gray-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
                  {hasSnapshot ? (
                    <div className="flex flex-wrap items-center gap-2 text-gray-500 dark:text-gray-400">
                      <span className="font-semibold text-gray-700 dark:text-gray-300">
                        Snapshot Archive:
                      </span>
                      {snapshot.matched_required_skills?.length > 0 && (
                        <span className="text-emerald-700 dark:text-emerald-400">
                          {snapshot.matched_required_skills.length} matched skills
                        </span>
                      )}
                      {snapshot.missing_required_skills?.length > 0 && (
                        <span className="text-rose-600 dark:text-rose-400">
                          • {snapshot.missing_required_skills.length} missing
                        </span>
                      )}
                      {snapshot.resume_filename && (
                        <span className="text-gray-400 truncate max-w-xs">
                          • {snapshot.resume_filename}
                        </span>
                      )}
                    </div>
                  ) : (
                    <span className="text-gray-400 dark:text-gray-500 italic">
                      Legacy Application — No snapshot breakdown recorded at submission
                    </span>
                  )}

                    {/* Actions: Timeline, View Snapshot & View Job */}
                    <div className="flex items-center gap-2 self-end sm:self-auto flex-wrap">
                      <button
                        onClick={() => setSelectedTimelineApp(app)}
                        className="px-3 py-1.5 text-xs font-semibold bg-purple-50 hover:bg-purple-100 dark:bg-purple-950/50 dark:hover:bg-purple-900/60 text-purple-700 dark:text-purple-300 rounded-lg transition-colors cursor-pointer flex items-center gap-1.5 border border-purple-200 dark:border-purple-800"
                        title="View recruitment rounds progression timeline for this drive"
                      >
                        <TrendingUp className="w-3.5 h-3.5 text-purple-600 dark:text-purple-400" />
                        <span>Recruitment Timeline</span>
                      </button>

                      {parentJob?.application_url && !app.external_applied_at && (
                      <button
                        onClick={() => navigate(`/student/jobs/${app.job_posting_id}`)}
                        className="px-3 py-1.5 text-xs font-semibold bg-amber-50 hover:bg-amber-100 dark:bg-amber-950/50 dark:hover:bg-amber-900/60 text-amber-800 dark:text-amber-300 rounded-lg transition-colors cursor-pointer flex items-center gap-1 border border-amber-200 dark:border-amber-800"
                        title="Complete external submission confirmation"
                      >
                        <Clock className="w-3 h-3 text-amber-600" />
                        <span>Confirm External</span>
                      </button>
                    )}

                    {hasSnapshot && (
                      <button
                        onClick={() => setSelectedSnapshotApp(app)}
                        className="px-3 py-1.5 text-xs font-semibold bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-800 dark:text-gray-200 rounded-lg transition-colors cursor-pointer flex items-center gap-1.5"
                        title="Inspect full application-time snapshot details"
                      >
                        <Layers className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
                        <span>Inspect Snapshot</span>
                      </button>
                    )}

                    <button
                      onClick={() => navigate(`/student/jobs/${app.job_posting_id}`)}
                      className="px-3 py-1.5 text-xs font-semibold bg-blue-50 hover:bg-blue-100 dark:bg-blue-950/50 dark:hover:bg-blue-900/60 text-blue-700 dark:text-blue-300 rounded-lg transition-colors cursor-pointer flex items-center gap-1"
                      title="View original job posting"
                    >
                      <span>View Job</span>
                      <ExternalLink className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Snapshot Inspection Modal */}
      {selectedSnapshotApp && selectedSnapshotApp.match_snapshot && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-2xl w-full p-6 shadow-2xl border border-gray-200 dark:border-gray-800 space-y-5 max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex items-center justify-between pb-3 border-b border-gray-100 dark:border-gray-800">
              <div className="flex items-center gap-2 text-gray-900 dark:text-white font-bold text-lg">
                <Layers className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                <span>Application-Time Snapshot Archive</span>
              </div>
              <button
                onClick={() => setSelectedSnapshotApp(null)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Target Job & Applicant Identification */}
            <div className="p-4 bg-gray-50 dark:bg-gray-800/60 rounded-xl border border-gray-200 dark:border-gray-700/60 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-blue-600 dark:text-blue-400">
                  {selectedSnapshotApp.company_name || 'Assigned Company'}
                </span>
                <span className="text-[11px] text-gray-400">
                  Archived:{' '}
                  {selectedSnapshotApp.match_snapshot.created_at
                    ? new Date(selectedSnapshotApp.match_snapshot.created_at).toLocaleString()
                    : 'At submission'}
                </span>
              </div>
              <h3 className="text-base font-bold text-gray-900 dark:text-white">
                {selectedSnapshotApp.job_title || `Job #${selectedSnapshotApp.job_posting_id}`}
              </h3>
            </div>

            {/* Applicant Profile Record at Submission */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="p-3 bg-gray-50 dark:bg-gray-800/40 rounded-xl">
                <span className="text-gray-400 block">Applicant</span>
                <strong className="text-gray-800 dark:text-gray-200">
                  {selectedSnapshotApp.match_snapshot.student_name || user?.name}
                </strong>
              </div>
              <div className="p-3 bg-gray-50 dark:bg-gray-800/40 rounded-xl">
                <span className="text-gray-400 block">Branch</span>
                <strong className="text-gray-800 dark:text-gray-200">
                  {selectedSnapshotApp.match_snapshot.branch || 'Student'}
                </strong>
              </div>
              <div className="p-3 bg-gray-50 dark:bg-gray-800/40 rounded-xl">
                <span className="text-gray-400 block">Archived CGPA</span>
                <strong className="text-gray-800 dark:text-gray-200">
                  {selectedSnapshotApp.match_snapshot.cgpa || 'N/A'}
                </strong>
              </div>
              <div className="p-3 bg-gray-50 dark:bg-gray-800/40 rounded-xl">
                <span className="text-gray-400 block">Status</span>
                <strong className="text-gray-800 dark:text-gray-200 capitalize">
                  {selectedSnapshotApp.status}
                </strong>
              </div>
            </div>

            {/* Authoritative Scores Hero */}
            <div className="p-4 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/40 dark:to-indigo-950/40 border border-blue-200 dark:border-blue-800/60 rounded-xl">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase">
                    Authoritative Match Score
                  </span>
                  <p className="text-2xl font-black text-gray-900 dark:text-white mt-0.5">
                    {selectedSnapshotApp.match_snapshot.match_percentage !== null &&
                    selectedSnapshotApp.match_snapshot.match_percentage !== undefined
                      ? `${Math.round(selectedSnapshotApp.match_snapshot.match_percentage)}%`
                      : 'Not calculated'}
                  </p>
                </div>
                <div className="text-right text-xs space-y-1">
                  <div>
                    Required Score:{' '}
                    <strong>
                      {selectedSnapshotApp.match_snapshot.required_score !== null &&
                      selectedSnapshotApp.match_snapshot.required_score !== undefined
                        ? `${Math.round(selectedSnapshotApp.match_snapshot.required_score)}%`
                        : 'N/A'}
                    </strong>
                  </div>
                  <div>
                    Preferred Score:{' '}
                    <strong>
                      {selectedSnapshotApp.match_snapshot.preferred_score !== null &&
                      selectedSnapshotApp.match_snapshot.preferred_score !== undefined
                        ? `${Math.round(selectedSnapshotApp.match_snapshot.preferred_score)}%`
                        : 'N/A'}
                    </strong>
                  </div>
                </div>
              </div>

              {selectedSnapshotApp.match_snapshot.resume_filename && (
                <div className="mt-3 pt-2 border-t border-blue-200/60 dark:border-blue-800/60 flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
                  <FileText className="w-3.5 h-3.5 text-blue-500" />
                  <span>
                    Resume Archive:{' '}
                    <strong>{selectedSnapshotApp.match_snapshot.resume_filename}</strong>
                  </span>
                </div>
              )}
            </div>

            {/* Low Match Warning Recorded if Applicable */}
            {selectedSnapshotApp.match_snapshot.has_low_match_warning && (
              <div className="p-3 bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 rounded-xl text-xs text-amber-900 dark:text-amber-200 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                <div>
                  <strong>Low Skill Match Advisory Recorded:</strong>{' '}
                  <span>
                    {selectedSnapshotApp.match_snapshot.low_match_warning ||
                      'Required skill match was below the 50% threshold at submission time.'}
                  </span>
                </div>
              </div>
            )}

            {/* Skills Breakdown Grid */}
            <div className="space-y-3 text-xs">
              <p className="font-bold text-gray-900 dark:text-white uppercase tracking-wider">
                Archived Skill Breakdown
              </p>

              {/* Matched Required Skills */}
              <div className="space-y-1">
                <span className="font-semibold text-emerald-700 dark:text-emerald-400 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>
                    Matched Required Skills (
                    {selectedSnapshotApp.match_snapshot.matched_required_skills?.length || 0})
                  </span>
                </span>
                <div className="flex flex-wrap gap-1">
                  {selectedSnapshotApp.match_snapshot.matched_required_skills?.length > 0 ? (
                    selectedSnapshotApp.match_snapshot.matched_required_skills.map((s, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-0.5 bg-emerald-50 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 rounded-md text-[11px]"
                      >
                        ✓ {s}
                      </span>
                    ))
                  ) : (
                    <span className="text-gray-400 italic">None matched</span>
                  )}
                </div>
              </div>

              {/* Missing Required Skills */}
              <div className="space-y-1">
                <span className="font-semibold text-rose-700 dark:text-rose-400 flex items-center gap-1">
                  <XCircle className="w-3.5 h-3.5" />
                  <span>
                    Missing Required Skills (
                    {selectedSnapshotApp.match_snapshot.missing_required_skills?.length || 0})
                  </span>
                </span>
                <div className="flex flex-wrap gap-1">
                  {selectedSnapshotApp.match_snapshot.missing_required_skills?.length > 0 ? (
                    selectedSnapshotApp.match_snapshot.missing_required_skills.map((s, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-0.5 bg-rose-50 dark:bg-rose-950/60 text-rose-800 dark:text-rose-300 border border-rose-200 dark:border-rose-800 rounded-md text-[11px]"
                      >
                        ✗ {s}
                      </span>
                    ))
                  ) : (
                    <span className="text-emerald-600 font-medium">All matched!</span>
                  )}
                </div>
              </div>

              {/* Preferred Skills */}
              {(selectedSnapshotApp.match_snapshot.matched_preferred_skills?.length > 0 ||
                selectedSnapshotApp.match_snapshot.missing_preferred_skills?.length > 0) && (
                <div className="space-y-1 pt-1">
                  <span className="font-semibold text-teal-700 dark:text-teal-400 flex items-center gap-1">
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Preferred Skills Alignment</span>
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {selectedSnapshotApp.match_snapshot.matched_preferred_skills?.map((s, idx) => (
                      <span
                        key={`sm-p-${idx}`}
                        className="px-2 py-0.5 bg-teal-50 dark:bg-teal-950/60 text-teal-800 dark:text-teal-300 border border-teal-200 dark:border-teal-800 rounded-md text-[11px]"
                      >
                        ✓ {s}
                      </span>
                    ))}
                    {selectedSnapshotApp.match_snapshot.missing_preferred_skills?.map((s, idx) => (
                      <span
                        key={`sm-pm-${idx}`}
                        className="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 text-gray-500 rounded-md text-[11px]"
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Semantic Matches if present */}
              {selectedSnapshotApp.match_snapshot.semantic_matches?.length > 0 && (
                <div className="p-2.5 bg-indigo-50/60 dark:bg-indigo-950/30 rounded-lg border border-indigo-100 dark:border-indigo-900/40 text-[11px] space-y-1 text-indigo-900 dark:text-indigo-200">
                  <p className="font-semibold">Semantic Skill Matches (MiniLM):</p>
                  {selectedSnapshotApp.match_snapshot.semantic_matches.map((sm, i) => (
                    <p key={i} className="text-gray-600 dark:text-gray-300 pl-3">
                      • {sm.required_skill || sm.skill} matched with{' '}
                      <strong>"{sm.matched_with || sm.student_skill}"</strong> ({Math.round((sm.similarity || 0) * 100)}% similarity)
                    </p>
                  ))}
                </div>
              )}
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-end pt-3 border-t border-gray-100 dark:border-gray-800">
              <button
                type="button"
                onClick={() => setSelectedSnapshotApp(null)}
                className="px-5 py-2 text-xs font-semibold bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-800 dark:text-gray-200 rounded-lg transition-colors cursor-pointer"
              >
                Close Snapshot
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Student Recruitment Progression Timeline Modal (Stage 3.3.6) */}
      {selectedTimelineApp && (
        <StudentRecruitmentTimeline
          isOpen={true}
          onClose={() => setSelectedTimelineApp(null)}
          studentId={user?.id}
          jobId={selectedTimelineApp.job_posting_id}
          jobTitle={selectedTimelineApp.job_title}
          companyName={selectedTimelineApp.company_name}
        />
      )}
    </div>
  );
}

export default StudentApplications;
