import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Briefcase,
  Search,
  Building2,
  MapPin,
  Calendar,
  Clock,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Filter,
  ArrowRight,
  X,
  Sparkles,
  Award,
  Layers,
  GraduationCap,
  Banknote,
  Send,
  Megaphone,
  Paperclip,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import { useAuthStore } from '../../store/authStore';

function StudentJobs() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get('tab') === 'circulars' ? 'circulars' : 'jobs';

  const { user } = useAuthStore();
  const {
    jobs,
    isLoading,
    error,
    fetchJobPostings,
    myApplications,
    isMyApplicationsLoading,
    myApplicationsError,
    fetchMyApplications,
    circulars,
    isCircularsLoading,
    circularsError,
    fetchCirculars,
  } = usePlacementStore();

  // Search and filter state
  const [searchTerm, setSearchTerm] = useState('');
  const [applicationFilter, setApplicationFilter] = useState('all'); // 'all' | 'not_applied' | 'applied'
  const [locationFilter, setLocationFilter] = useState('all');
  const [branchFilter, setBranchFilter] = useState('all');
  const [sortBy, setSortBy] = useState('newest'); // 'newest' | 'deadline' | 'cgpa_asc' | 'cgpa_desc'
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Initial load
  const loadData = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await Promise.allSettled([
        fetchJobPostings(),
        fetchMyApplications(user?.id),
        fetchCirculars(),
      ]);
    } finally {
      setIsRefreshing(false);
    }
  }, [fetchJobPostings, fetchMyApplications, fetchCirculars, user?.id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Map student's applications by job_posting_id for instant lookup
  const appliedJobMap = useMemo(() => {
    const map = new Map();
    if (Array.isArray(myApplications)) {
      myApplications.forEach((app) => {
        if (app.job_posting_id) {
          map.set(app.job_posting_id, app);
        }
      });
    }
    return map;
  }, [myApplications]);

  // Extract unique locations and branches from the actual published jobs
  const availableLocations = useMemo(() => {
    const locSet = new Set();
    jobs.forEach((j) => {
      if (j.location && typeof j.location === 'string' && j.location.trim()) {
        locSet.add(j.location.trim());
      }
    });
    return Array.from(locSet).sort();
  }, [jobs]);

  const availableBranches = useMemo(() => {
    const branchSet = new Set();
    jobs.forEach((j) => {
      if (Array.isArray(j.branch_eligibility)) {
        j.branch_eligibility.forEach((b) => {
          if (b && typeof b === 'string' && b.trim()) {
            branchSet.add(b.trim());
          }
        });
      }
    });
    return Array.from(branchSet).sort();
  }, [jobs]);

  // Filter and sort jobs without mutating store
  const filteredJobs = useMemo(() => {
    const query = searchTerm.trim().toLowerCase();

    return jobs
      .filter((job) => {
        // Backend restricts student to 'open' jobs, but guard against inactive ones
        if (job.status && job.status !== 'open') return false;

        // Search query: title or company_name
        if (query) {
          const titleMatch = job.title?.toLowerCase().includes(query);
          const companyMatch = job.company_name?.toLowerCase().includes(query);
          const skillMatch = job.required_skills?.some((s) =>
            s?.toLowerCase().includes(query)
          );
          if (!titleMatch && !companyMatch && !skillMatch) return false;
        }

        // Application status filter
        const isApplied = appliedJobMap.has(job.id);
        if (applicationFilter === 'applied' && !isApplied) return false;
        if (applicationFilter === 'not_applied' && isApplied) return false;

        // Location filter
        if (locationFilter !== 'all' && job.location !== locationFilter) {
          return false;
        }

        // Branch filter
        if (branchFilter !== 'all') {
          const branches = job.branch_eligibility || [];
          if (branches.length > 0 && !branches.includes(branchFilter)) {
            return false;
          }
        }

        return true;
      })
      .sort((a, b) => {
        if (sortBy === 'deadline') {
          if (!a.application_deadline) return 1;
          if (!b.application_deadline) return -1;
          return new Date(a.application_deadline) - new Date(b.application_deadline);
        }
        if (sortBy === 'cgpa_asc') {
          return (a.cgpa_criteria || 0) - (b.cgpa_criteria || 0);
        }
        if (sortBy === 'cgpa_desc') {
          return (b.cgpa_criteria || 0) - (a.cgpa_criteria || 0);
        }
        // default 'newest'
        return new Date(b.created_at || 0) - new Date(a.created_at || 0);
      });
  }, [jobs, searchTerm, applicationFilter, locationFilter, branchFilter, sortBy, appliedJobMap]);

  const hasActiveFilters =
    Boolean(searchTerm) ||
    applicationFilter !== 'all' ||
    locationFilter !== 'all' ||
    branchFilter !== 'all' ||
    sortBy !== 'newest';

  const clearAllFilters = () => {
    setSearchTerm('');
    setApplicationFilter('all');
    setLocationFilter('all');
    setBranchFilter('all');
    setSortBy('newest');
  };

  const filteredCirculars = useMemo(() => {
    return (circulars || []).filter((circ) => {
      return (
        !searchTerm ||
        circ.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        circ.company_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        circ.summary?.toLowerCase().includes(searchTerm.toLowerCase())
      );
    });
  }, [circulars, searchTerm]);

  // Helper for deadline calculation
  const getDeadlineMeta = (deadlineStr) => {
    if (!deadlineStr) return null;
    try {
      const deadline = new Date(deadlineStr);
      if (isNaN(deadline.getTime())) return null;

      const now = new Date();
      const diffMs = deadline.getTime() - now.getTime();
      const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

      if (diffDays < 0) {
        return {
          formatted: deadline.toLocaleDateString(),
          badge: 'Closed',
          isUrgent: false,
          isPassed: true,
        };
      }
      if (diffDays === 0) {
        return {
          formatted: 'Today',
          badge: 'Ends Today',
          isUrgent: true,
          isPassed: false,
        };
      }
      if (diffDays === 1) {
        return {
          formatted: 'Tomorrow',
          badge: '1 day left',
          isUrgent: true,
          isPassed: false,
        };
      }
      if (diffDays <= 3) {
        return {
          formatted: deadline.toLocaleDateString(),
          badge: `${diffDays} days left`,
          isUrgent: true,
          isPassed: false,
        };
      }
      return {
        formatted: deadline.toLocaleDateString(),
        badge: `${diffDays}d left`,
        isUrgent: false,
        isPassed: false,
      };
    } catch {
      return null;
    }
  };

  // Helper for application status label formatting
  const getApplicationStatusBadge = (app) => {
    if (!app) return null;
    const isExtConfirmed = Boolean(app.external_applied_at || app.is_external_confirmed);

    if (isExtConfirmed && app.status === 'applied') {
      return (
        <span
          className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border bg-emerald-100 dark:bg-emerald-950/70 text-emerald-800 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800"
          title={`External Application Confirmed (Student-Reported): ${app.external_applied_at ? new Date(app.external_applied_at).toLocaleString() : 'Recorded'}`}
        >
          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
          <span>CONFIRMED (EXTERNAL)</span>
        </span>
      );
    }

    const statusText = app.status ? app.status.replace(/_/g, ' ').toUpperCase() : 'APPLIED';

    let colorClasses = 'bg-blue-100 dark:bg-blue-950/70 text-blue-800 dark:text-blue-300 border-blue-200 dark:border-blue-800';
    if (app.status === 'shortlisted') {
      colorClasses = 'bg-emerald-100 dark:bg-emerald-950/70 text-emerald-800 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800';
    } else if (app.status === 'rejected') {
      colorClasses = 'bg-rose-100 dark:bg-rose-950/70 text-rose-800 dark:text-rose-300 border-rose-200 dark:border-rose-800';
    } else if (app.status === 'interview_scheduled') {
      colorClasses = 'bg-purple-100 dark:bg-purple-950/70 text-purple-800 dark:text-purple-300 border-purple-200 dark:border-purple-800';
    }

    return (
      <span
        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${colorClasses}`}
        title={`Application Status: ${statusText}`}
      >
        <CheckCircle2 className="w-3 h-3" />
        <span>{statusText}</span>
      </span>
    );
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Header Section */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <span>Campus Placements & Drives</span>
            <span className="text-xs font-semibold px-2 py-0.5 bg-blue-100 dark:bg-blue-950/80 text-blue-700 dark:text-blue-300 rounded-full border border-blue-200 dark:border-blue-800">
              Student Portal
            </span>
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Browse published campus drives, review skill requirements, and verify your eligibility.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadData}
            disabled={isLoading || isRefreshing || isCircularsLoading}
            className="px-3 py-2 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
            title="Refresh listings"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading || isRefreshing || isCircularsLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Tab Switcher */}
      <div className="flex items-center gap-2 border-b border-gray-200 dark:border-gray-800 pb-2">
        <button
          onClick={() => setSearchParams({ tab: 'jobs' })}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all cursor-pointer ${
            activeTab === 'jobs'
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
          }`}
        >
          <Briefcase className="w-4 h-4" />
          <span>Campus Jobs ({jobs.length})</span>
        </button>

        <button
          onClick={() => setSearchParams({ tab: 'circulars' })}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all cursor-pointer ${
            activeTab === 'circulars'
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
          }`}
        >
          <Megaphone className="w-4 h-4" />
          <span>Recruitment Circulars ({circulars.length})</span>
        </button>
      </div>

      {activeTab === 'circulars' ? (
        /* Recruitment Circulars View */
        <div className="space-y-6">
          {/* Circulars Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search circulars by company name, title, or summary..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2.5 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm dark:text-white"
            />
          </div>

          {isCircularsLoading && circulars.length === 0 ? (
            <div className="p-12 text-center text-gray-500 dark:text-gray-400">
              <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-3" />
              <p>Loading eligible recruitment circulars...</p>
            </div>
          ) : circularsError ? (
            <div className="p-6 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-xl text-center text-red-700 dark:text-red-300">
              <p>{circularsError}</p>
            </div>
          ) : filteredCirculars.length === 0 ? (
            <div className="p-12 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 text-center">
              <Megaphone className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
              <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                No recruitment circulars found
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                {searchTerm
                  ? 'No circulars match your search query.'
                  : 'There are currently no active recruitment drive circulars for your department.'}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredCirculars.map((circ) => {
                const isPassed =
                  circ.application_deadline && new Date(circ.application_deadline) < new Date();
                return (
                  <div
                    key={circ.id}
                    className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5 shadow-sm hover:border-blue-300 dark:hover:border-blue-700 transition-all flex flex-col justify-between space-y-4"
                  >
                    <div className="space-y-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <span className="text-xs font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wider flex items-center gap-1">
                            <Building2 className="w-3.5 h-3.5" />
                            {circ.company_name}
                          </span>
                          <h3
                            onClick={() => navigate(`/student/jobs/circulars/${circ.id}`)}
                            className="text-base font-bold text-gray-900 dark:text-white mt-0.5 hover:text-blue-600 dark:hover:text-blue-400 cursor-pointer"
                          >
                            {circ.title}
                          </h3>
                        </div>

                        {circ.published_at && (
                          <span className="text-[10px] text-gray-400 font-medium whitespace-nowrap">
                            {new Date(circ.published_at).toLocaleDateString()}
                          </span>
                        )}
                      </div>

                      {circ.summary && (
                        <p className="text-xs text-gray-600 dark:text-gray-300 line-clamp-2">
                          {circ.summary}
                        </p>
                      )}

                      <div className="grid grid-cols-2 gap-2 text-xs text-gray-500 dark:text-gray-400 pt-1">
                        <div className="flex items-center gap-1.5">
                          <Calendar className="w-3.5 h-3.5 text-gray-400" />
                          <span>
                            Drive: {circ.drive_date ? new Date(circ.drive_date).toLocaleDateString() : 'TBD'}
                          </span>
                        </div>

                        <div className="flex items-center gap-1.5">
                          <Clock
                            className={`w-3.5 h-3.5 ${
                              isPassed ? 'text-red-500' : 'text-gray-400'
                            }`}
                          />
                          <span className={isPassed ? 'text-red-600 dark:text-red-400 font-semibold' : ''}>
                            {isPassed
                              ? 'Deadline Passed'
                              : circ.application_deadline
                              ? `Deadline: ${new Date(circ.application_deadline).toLocaleDateString()}`
                              : 'Open'}
                          </span>
                        </div>

                        <div className="flex items-center gap-1.5">
                          <Briefcase className="w-3.5 h-3.5 text-gray-400" />
                          <span>{circ.linked_jobs_count || circ.linked_jobs?.length || 0} Roles</span>
                        </div>

                        <div className="flex items-center gap-1.5">
                          <Paperclip className="w-3.5 h-3.5 text-gray-400" />
                          <span>{circ.attachments_count || circ.attachments?.length || 0} Attachments</span>
                        </div>
                      </div>

                      {circ.branch_eligibility && circ.branch_eligibility.length > 0 && (
                        <div className="flex flex-wrap gap-1 pt-1">
                          {circ.branch_eligibility.slice(0, 3).map((branch, idx) => (
                            <span
                              key={idx}
                              className="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 rounded text-[10px]"
                            >
                              {branch}
                            </span>
                          ))}
                          {circ.branch_eligibility.length > 3 && (
                            <span className="text-[10px] text-gray-400 self-center">
                              +{circ.branch_eligibility.length - 3} more
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    <div className="pt-3 border-t border-gray-100 dark:border-gray-800">
                      <button
                        onClick={() => navigate(`/student/jobs/circulars/${circ.id}`)}
                        className="w-full py-2 px-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 cursor-pointer shadow-xs"
                      >
                        <span>View Drive Details & Roles</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ) : (
        <>
          {/* Metrics Row */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Active Drives
            </span>
            <Briefcase className="w-4 h-4 text-blue-600 dark:text-blue-400" />
          </div>
          <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
            {isLoading && jobs.length === 0 ? '...' : jobs.length}
          </p>
        </div>

        <div
          onClick={() => setApplicationFilter('applied')}
          className={`p-4 rounded-xl border transition-all cursor-pointer shadow-sm ${
            applicationFilter === 'applied'
              ? 'bg-blue-50/70 dark:bg-blue-950/40 border-blue-300 dark:border-blue-800'
              : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 hover:border-gray-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              My Applications
            </span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
          </div>
          <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
            {isMyApplicationsLoading && myApplications.length === 0 ? '...' : appliedJobMap.size}
          </p>
        </div>

        <div
          onClick={() => setApplicationFilter('not_applied')}
          className={`p-4 rounded-xl border transition-all cursor-pointer shadow-sm ${
            applicationFilter === 'not_applied'
              ? 'bg-indigo-50/70 dark:bg-indigo-950/40 border-indigo-300 dark:border-indigo-800'
              : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 hover:border-gray-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Open to Apply
            </span>
            <Send className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
          </div>
          <p className="text-2xl font-bold text-indigo-600 dark:text-indigo-400 mt-1">
            {isLoading ? '...' : Math.max(0, jobs.length - appliedJobMap.size)}
          </p>
        </div>
      </div>

      {/* Warning if application history failed to load independently */}
      {myApplicationsError && (
        <div className="p-3 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-lg flex items-center justify-between text-xs text-amber-800 dark:text-amber-300">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0" />
            <span>Could not load application history: {myApplicationsError}. Job catalog is still available.</span>
          </div>
          <button
            onClick={() => fetchMyApplications(user?.id)}
            className="underline font-semibold hover:text-amber-900 dark:hover:text-amber-200 cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}

      {/* Search and Filters Bar */}
      <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm space-y-3">
        <div className="flex flex-col lg:flex-row items-stretch lg:items-center gap-3">
          {/* Search Box */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
            <input
              type="text"
              id="student-jobs-search-input"
              placeholder="Search by job title, company name, or required skill..."
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

          {/* Quick Application Filter Buttons */}
          <div className="inline-flex rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 p-0.5 self-start lg:self-auto">
            <button
              onClick={() => setApplicationFilter('all')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer ${
                applicationFilter === 'all'
                  ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-xs'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              All Drives
            </button>
            <button
              onClick={() => setApplicationFilter('not_applied')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer ${
                applicationFilter === 'not_applied'
                  ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-xs'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              Not Applied
            </button>
            <button
              onClick={() => setApplicationFilter('applied')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer ${
                applicationFilter === 'applied'
                  ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-xs'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              Applied ({appliedJobMap.size})
            </button>
          </div>
        </div>

        {/* Dropdown Filters Row */}
        <div className="flex flex-wrap items-center gap-2.5 pt-1 text-xs">
          <div className="flex items-center gap-1 text-gray-500 dark:text-gray-400">
            <Filter className="w-3.5 h-3.5" />
            <span className="font-medium">Filters:</span>
          </div>

          {/* Location Filter */}
          <select
            id="student-jobs-location-filter"
            value={locationFilter}
            onChange={(e) => setLocationFilter(e.target.value)}
            className="px-2.5 py-1.5 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-blue-500 focus:outline-none"
          >
            <option value="all">All Locations</option>
            {availableLocations.map((loc) => (
              <option key={loc} value={loc}>
                {loc}
              </option>
            ))}
          </select>

          {/* Branch Filter */}
          <select
            id="student-jobs-branch-filter"
            value={branchFilter}
            onChange={(e) => setBranchFilter(e.target.value)}
            className="px-2.5 py-1.5 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-blue-500 focus:outline-none"
          >
            <option value="all">All Branches</option>
            {availableBranches.map((br) => (
              <option key={br} value={br}>
                Branch: {br}
              </option>
            ))}
          </select>

          {/* Sort By */}
          <select
            id="student-jobs-sort-filter"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="px-2.5 py-1.5 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-lg text-xs focus:ring-2 focus:ring-blue-500 focus:outline-none ml-auto"
          >
            <option value="newest">Sort: Newest First</option>
            <option value="deadline">Sort: Deadline (Closing Soonest)</option>
            <option value="cgpa_asc">Sort: Min CGPA (Lowest First)</option>
            <option value="cgpa_desc">Sort: Min CGPA (Highest First)</option>
          </select>

          {/* Clear Filters Button */}
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

      {/* Main Content Area: Loading, Error, Empty, or Populated */}
      {isLoading && jobs.length === 0 ? (
        // Loading Skeleton
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {[1, 2, 3, 4, 5, 6].map((idx) => (
            <div
              key={idx}
              className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5 shadow-sm animate-pulse space-y-4"
            >
              <div className="flex justify-between items-start">
                <div className="space-y-2 flex-1">
                  <div className="h-4 bg-gray-200 dark:bg-gray-800 rounded w-1/3"></div>
                  <div className="h-5 bg-gray-300 dark:bg-gray-700 rounded w-3/4"></div>
                </div>
                <div className="h-5 bg-gray-200 dark:bg-gray-800 rounded-full w-16"></div>
              </div>
              <div className="space-y-2">
                <div className="h-3 bg-gray-200 dark:bg-gray-800 rounded w-1/2"></div>
                <div className="h-3 bg-gray-200 dark:bg-gray-800 rounded w-2/3"></div>
              </div>
              <div className="flex gap-2">
                <div className="h-6 bg-gray-200 dark:bg-gray-800 rounded-full w-16"></div>
                <div className="h-6 bg-gray-200 dark:bg-gray-800 rounded-full w-20"></div>
              </div>
              <div className="h-9 bg-gray-200 dark:bg-gray-800 rounded-lg w-full"></div>
            </div>
          ))}
        </div>
      ) : error ? (
        // Error State with Retry
        <div className="text-center py-16 bg-white dark:bg-gray-900 rounded-xl border border-red-200 dark:border-red-900/60 p-8 shadow-sm">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-3" />
          <h3 className="text-lg font-bold text-gray-900 dark:text-white">Failed to Load Campus Jobs</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 max-w-md mx-auto">
            {typeof error === 'string' ? error : 'An unexpected error occurred while fetching campus jobs.'}
          </p>
          <button
            onClick={loadData}
            className="mt-5 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-semibold transition-colors flex items-center gap-2 mx-auto cursor-pointer"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Try Again</span>
          </button>
        </div>
      ) : jobs.length === 0 ? (
        // Empty State: No jobs available from placement cell
        <div className="text-center py-20 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-8 shadow-sm">
          <Briefcase className="w-14 h-14 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
          <h3 className="text-lg font-bold text-gray-900 dark:text-white">No Active Campus Drives</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 max-w-md mx-auto">
            There are currently no active placement drives published. Placement drives will appear here once announced by the Placement Cell.
          </p>
          <button
            onClick={loadData}
            className="mt-5 px-4 py-2 bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg text-xs font-semibold transition-colors inline-flex items-center gap-1.5 cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Check for Updates</span>
          </button>
        </div>
      ) : filteredJobs.length === 0 ? (
        // No Results State: Filter matched nothing
        <div className="text-center py-16 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-8 shadow-sm">
          <Search className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
          <h3 className="text-base font-bold text-gray-900 dark:text-white">No Matching Jobs Found</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 max-w-md mx-auto">
            None of the published jobs match your selected filters. Try broadening your keywords or resetting filters.
          </p>
          <button
            onClick={clearAllFilters}
            className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer"
          >
            Reset Filters
          </button>
        </div>
      ) : (
        // Populated Jobs Grid
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredJobs.map((job) => {
            const application = appliedJobMap.get(job.id);
            const isApplied = Boolean(application);
            const deadlineMeta = getDeadlineMeta(job.application_deadline);

            return (
              <div
                key={job.id}
                className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 hover:border-blue-400 dark:hover:border-blue-600 shadow-xs hover:shadow-md transition-all flex flex-col justify-between p-5 group"
              >
                <div>
                  {/* Card Header: Company, Applied Badge, Status Badge */}
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400 font-medium truncate">
                      <Building2 className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                      <span className="truncate">{job.company_name || 'Assigned Company'}</span>
                    </div>

                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      {isApplied && getApplicationStatusBadge(application)}
                      {job.application_url && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                          External Portal
                        </span>
                      )}
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                        ● Open
                      </span>
                    </div>
                  </div>

                  {/* Job Title */}
                  <h3
                    onClick={() => navigate(`/student/jobs/${job.id}`)}
                    className="text-lg font-bold text-gray-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors cursor-pointer line-clamp-1"
                    title={job.title}
                  >
                    {job.title}
                  </h3>

                  {/* Metadata Row: Location, Salary */}
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 mt-2.5 text-xs text-gray-500 dark:text-gray-400">
                    {job.location && (
                      <span className="flex items-center gap-1" title="Location">
                        <MapPin className="w-3.5 h-3.5 text-gray-400" />
                        <span>{job.location}</span>
                      </span>
                    )}

                    {job.salary_range && (
                      <span className="flex items-center gap-1 text-emerald-700 dark:text-emerald-400 font-semibold" title="Salary / CTC">
                        <Banknote className="w-3.5 h-3.5" />
                        <span>{job.salary_range}</span>
                      </span>
                    )}

                    {job.experience_level && (
                      <span className="flex items-center gap-1" title="Experience requirement">
                        <Award className="w-3.5 h-3.5 text-gray-400" />
                        <span>{job.experience_level}</span>
                      </span>
                    )}
                  </div>

                  {/* Deadlines and Drive Dates */}
                  {(deadlineMeta || job.drive_date) && (
                    <div className="mt-3 pt-2.5 border-t border-gray-100 dark:border-gray-800/80 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                      {deadlineMeta && (
                        <div
                          className={`flex items-center gap-1 ${
                            deadlineMeta.isUrgent
                              ? 'text-amber-700 dark:text-amber-400 font-semibold'
                              : deadlineMeta.isPassed
                              ? 'text-gray-400 dark:text-gray-500'
                              : 'text-gray-500 dark:text-gray-400'
                          }`}
                          title={`Application Deadline: ${new Date(job.application_deadline).toLocaleString()}`}
                        >
                          <Clock className="w-3.5 h-3.5" />
                          <span>Deadline: {deadlineMeta.formatted}</span>
                          {deadlineMeta.badge && (
                            <span
                              className={`text-[10px] px-1.5 py-0.2 rounded font-bold ${
                                deadlineMeta.isUrgent
                                  ? 'bg-amber-100 dark:bg-amber-950/70 text-amber-800 dark:text-amber-300'
                                  : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400'
                              }`}
                            >
                              {deadlineMeta.badge}
                            </span>
                          )}
                        </div>
                      )}

                      {job.drive_date && (
                        <div
                          className="flex items-center gap-1 text-gray-500 dark:text-gray-400"
                          title={`Drive Date: ${new Date(job.drive_date).toLocaleDateString()}`}
                        >
                          <Calendar className="w-3.5 h-3.5 text-gray-400" />
                          <span>Drive: {new Date(job.drive_date).toLocaleDateString()}</span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Academic Eligibility: Min CGPA & Branches */}
                  <div className="mt-3 p-2.5 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-100 dark:border-gray-800 text-xs space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-gray-500 dark:text-gray-400 flex items-center gap-1">
                        <GraduationCap className="w-3.5 h-3.5" />
                        <span>Min CGPA:</span>
                      </span>
                      <span className="font-semibold text-gray-800 dark:text-gray-200">
                        {job.cgpa_criteria !== null && job.cgpa_criteria !== undefined
                          ? job.cgpa_criteria
                          : 'No cutoff'}
                      </span>
                    </div>

                    <div className="flex items-start justify-between gap-2">
                      <span className="text-gray-500 dark:text-gray-400 flex-shrink-0">Branches:</span>
                      <span className="font-medium text-gray-700 dark:text-gray-300 text-right truncate">
                        {job.branch_eligibility?.length > 0
                          ? job.branch_eligibility.join(', ')
                          : 'All Eligible'}
                      </span>
                    </div>
                  </div>

                  {/* Required & Preferred Skills */}
                  <div className="mt-3 space-y-1.5">
                    {/* Required Skills */}
                    <div className="flex flex-wrap items-center gap-1">
                      {job.required_skills?.slice(0, 4).map((skill, idx) => (
                        <span
                          key={idx}
                          className="text-[11px] px-2 py-0.5 bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800/80 rounded-md font-medium"
                          title={`Required: ${skill}`}
                        >
                          {skill}
                        </span>
                      ))}
                      {job.required_skills?.length > 4 && (
                        <span className="text-[10px] px-1.5 py-0.5 bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 rounded">
                          +{job.required_skills.length - 4} req
                        </span>
                      )}

                      {/* Preferred Skills */}
                      {job.preferred_skills?.slice(0, 2).map((skill, idx) => (
                        <span
                          key={`pref-${idx}`}
                          className="text-[11px] px-2 py-0.5 bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800/80 rounded-md font-medium"
                          title={`Preferred: ${skill}`}
                        >
                          {skill} (pref)
                        </span>
                      ))}
                      {job.preferred_skills?.length > 2 && (
                        <span className="text-[10px] px-1.5 py-0.5 bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 rounded">
                          +{job.preferred_skills.length - 2} pref
                        </span>
                      )}

                      {(!job.required_skills || job.required_skills.length === 0) &&
                        (!job.preferred_skills || job.preferred_skills.length === 0) && (
                          <span className="text-[11px] text-gray-400 dark:text-gray-500 italic">
                            No specific skills listed
                          </span>
                        )}
                    </div>
                  </div>
                </div>

                {/* Card Action Button */}
                <div className="mt-5 pt-3 border-t border-gray-100 dark:border-gray-800">
                  <button
                    onClick={() => navigate(`/student/jobs/${job.id}`)}
                    className="w-full py-2 px-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 shadow-xs cursor-pointer group-hover:bg-blue-700"
                  >
                    <span>{isApplied ? 'View Details & Status' : 'View Details & Eligibility'}</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
        </>
      )}
    </div>
  );
}

export default StudentJobs;
