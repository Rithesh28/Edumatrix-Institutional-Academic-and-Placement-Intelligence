import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText,
  Download,
  TrendingUp,
  Building2,
  Users,
  Briefcase,
  Calendar,
  ArrowLeft,
  Megaphone,
  Layers,
  Award,
  CheckCircle2,
  Filter,
  RotateCcw,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import { getCompanies } from '../../services/placementService';
import toast from 'react-hot-toast';
import { API_URL } from '../../services/api';

const Reports = () => {
  const navigate = useNavigate();
  const { stats, isLoading, fetchStats } = usePlacementStore();
  const [isExporting, setIsExporting] = useState(false);

  // Filter State
  const [companyId, setCompanyId] = useState('');
  const [branch, setBranch] = useState('');
  const [status, setStatus] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  // Dropdown options
  const [companiesList, setCompaniesList] = useState([]);

  useEffect(() => {
    getCompanies({ limit: 100 })
      .then((data) => {
        const list = Array.isArray(data) ? data : data?.items || [];
        setCompaniesList(list);
      })
      .catch(() => setCompaniesList([]));
  }, []);

  const loadFilteredStats = useCallback(() => {
    const filters = {};
    if (companyId) filters.company_id = companyId;
    if (branch) filters.branch = branch;
    if (status) filters.status = status;
    if (startDate) filters.start_date = startDate;
    if (endDate) filters.end_date = endDate;
    fetchStats(filters);
  }, [companyId, branch, status, startDate, endDate, fetchStats]);

  useEffect(() => {
    loadFilteredStats();
  }, [loadFilteredStats]);

  const handleResetFilters = () => {
    setCompanyId('');
    setBranch('');
    setStatus('');
    setStartDate('');
    setEndDate('');
  };

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const token = localStorage.getItem('auth-storage')
        ? JSON.parse(localStorage.getItem('auth-storage')).state?.token
        : '';

      const queryParams = new URLSearchParams();
      if (companyId) queryParams.append('company_id', companyId);
      if (branch) queryParams.append('branch', branch);
      if (status) queryParams.append('status', status);
      if (startDate) queryParams.append('start_date', startDate);
      if (endDate) queryParams.append('end_date', endDate);

      const queryString = queryParams.toString();
      const exportUrl = `${API_URL}/placement/reports/export${queryString ? `?${queryString}` : ''}`;

      const response = await fetch(exportUrl, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `placement_report_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
        toast.success('Report downloaded successfully!');
      } else {
        toast.error('Failed to generate report');
      }
    } catch (error) {
      toast.error('Failed to export report');
    } finally {
      setIsExporting(false);
    }
  };

  const branches = [
    'Computer Science and Engineering',
    'Information Science and Engineering',
    'Electronics and Communication Engineering',
    'Mechanical Engineering',
    'Civil Engineering',
    'Electrical and Electronics Engineering',
    'Artificial Intelligence and Machine Learning',
  ];

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <button
            onClick={() => navigate('/placement/dashboard')}
            className="flex items-center space-x-2 text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200 mb-2 transition-colors cursor-pointer text-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Dashboard</span>
          </button>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Placement Reports & Analytics</h1>
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            Institutional metrics, round outcomes, verified offers, and exportable reports
          </p>
        </div>
        <button
          onClick={handleExport}
          disabled={isExporting}
          className="inline-flex items-center justify-center px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-sm font-semibold shadow-sm transition-colors cursor-pointer"
        >
          <Download className="w-4 h-4 mr-2" />
          <span>{isExporting ? 'Generating CSV...' : 'Export Filtered CSV'}</span>
        </button>
      </div>

      {/* Filter Controls Bar */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4">
        <div className="flex items-center gap-2 mb-3 text-sm font-semibold text-gray-700 dark:text-gray-200">
          <Filter className="w-4 h-4 text-indigo-500" />
          <span>Filter Report Data</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {/* Company Filter */}
          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Company</label>
            <select
              value={companyId}
              onChange={(e) => setCompanyId(e.target.value)}
              className="w-full text-xs rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 py-2 px-2.5 focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">All Companies</option>
              {companiesList.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          {/* Branch Filter */}
          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Branch / Dept</label>
            <select
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
              className="w-full text-xs rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 py-2 px-2.5 focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">All Branches</option>
              {branches.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>
          </div>

          {/* Application Status */}
          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Status</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="w-full text-xs rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 py-2 px-2.5 focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">All Statuses</option>
              <option value="applied">Applied</option>
              <option value="shortlisted">Shortlisted</option>
              <option value="selected">Selected</option>
              <option value="placed">Placed</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>

          {/* Start Date */}
          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">From Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full text-xs rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 py-2 px-2.5 focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* End Date */}
          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">To Date</label>
            <div className="flex items-center gap-2">
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full text-xs rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 py-2 px-2.5 focus:ring-2 focus:ring-indigo-500"
              />
              {(companyId || branch || status || startDate || endDate) && (
                <button
                  onClick={handleResetFilters}
                  title="Reset Filters"
                  className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
                >
                  <RotateCcw className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center items-center h-48">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-indigo-600 border-t-transparent"></div>
        </div>
      ) : (
        <>
          {/* Key Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Total Companies</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">
                    {stats?.total_companies || 0}
                  </p>
                </div>
                <Building2 className="w-7 h-7 text-blue-500" />
              </div>
              <p className="text-xs text-gray-400 mt-2">{stats?.active_companies || 0} active</p>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Total Jobs</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">
                    {stats?.total_jobs || 0}
                  </p>
                </div>
                <Briefcase className="w-7 h-7 text-green-500" />
              </div>
              <p className="text-xs text-gray-400 mt-2">{stats?.open_jobs || 0} open postings</p>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Recruitment Drives</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">
                    {stats?.total_recruitment_drives || 0}
                  </p>
                </div>
                <Megaphone className="w-7 h-7 text-purple-500" />
              </div>
              <p className="text-xs text-gray-400 mt-2">{stats?.total_rounds || 0} rounds configured</p>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Applications</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">
                    {stats?.total_applications || 0}
                  </p>
                </div>
                <FileText className="w-7 h-7 text-indigo-500" />
              </div>
              <p className="text-xs text-gray-400 mt-2">{stats?.students_shortlisted || 0} shortlisted</p>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Placement Rate</p>
                  <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
                    {stats?.placement_rate?.toFixed(1) || 0}%
                  </p>
                </div>
                <TrendingUp className="w-7 h-7 text-emerald-500" />
              </div>
              <p className="text-xs text-gray-400 mt-2">{stats?.total_students || 0} eligible students</p>
            </div>
          </div>

          {/* Secondary Stats Row: Outcomes & Offers */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-lg bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400">
                  <Layers className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Total Round Outcomes</p>
                  <p className="text-xl font-bold text-gray-900 dark:text-gray-100">
                    {stats?.total_outcomes || 0}
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-lg bg-purple-50 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400">
                  <Users className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Selected Candidates</p>
                  <p className="text-xl font-bold text-purple-600 dark:text-purple-400">
                    {stats?.students_selected || 0}
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-lg bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400">
                  <Award className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Verified Offers</p>
                  <p className="text-xl font-bold text-emerald-600 dark:text-emerald-400">
                    {stats?.total_verified_offers || stats?.verified_offers_count || 0}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Breakdown Charts / Progress Lists */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Applications by Status */}
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
              <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100 mb-4">
                Applications by Status
              </h3>
              {!stats?.applications_by_status || Object.keys(stats.applications_by_status).length === 0 ? (
                <p className="text-xs text-gray-400 py-6 text-center">No application records found.</p>
              ) : (
                <div className="space-y-3">
                  {Object.entries(stats.applications_by_status).map(([st, count]) => (
                    <div key={st} className="flex items-center justify-between">
                      <span className="text-sm text-gray-600 dark:text-gray-300 capitalize">{st}</span>
                      <div className="flex items-center space-x-4">
                        <div className="w-36 sm:w-48 bg-gray-100 dark:bg-gray-700 rounded-full h-2">
                          <div
                            className={`h-2 rounded-full ${
                              st === 'selected'
                                ? 'bg-emerald-500'
                                : st === 'shortlisted'
                                ? 'bg-amber-500'
                                : st === 'rejected'
                                ? 'bg-red-500'
                                : 'bg-indigo-500'
                            }`}
                            style={{
                              width: `${Math.min((count / (stats?.total_applications || 1)) * 100, 100)}%`,
                            }}
                          />
                        </div>
                        <span className="text-sm font-semibold text-gray-800 dark:text-gray-200 w-8 text-right">
                          {count}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Jobs by Status */}
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
              <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100 mb-4">Jobs by Status</h3>
              {!stats?.jobs_by_status || Object.keys(stats.jobs_by_status).length === 0 ? (
                <p className="text-xs text-gray-400 py-6 text-center">No job postings recorded.</p>
              ) : (
                <div className="space-y-3">
                  {Object.entries(stats.jobs_by_status).map(([jStatus, count]) => (
                    <div key={jStatus} className="flex items-center justify-between">
                      <span className="text-sm text-gray-600 dark:text-gray-300 capitalize">{jStatus}</span>
                      <div className="flex items-center space-x-4">
                        <div className="w-36 sm:w-48 bg-gray-100 dark:bg-gray-700 rounded-full h-2">
                          <div
                            className={`h-2 rounded-full ${
                              jStatus === 'open'
                                ? 'bg-emerald-500'
                                : jStatus === 'closed'
                                ? 'bg-gray-400'
                                : 'bg-amber-500'
                            }`}
                            style={{
                              width: `${Math.min((count / (stats?.total_jobs || 1)) * 100, 100)}%`,
                            }}
                          />
                        </div>
                        <span className="text-sm font-semibold text-gray-800 dark:text-gray-200 w-8 text-right">
                          {count}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* Navigation Quick Links */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
        <button
          onClick={() => navigate('/placement/companies')}
          className="bg-white dark:bg-gray-800 p-4 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 hover:shadow-md hover:border-blue-300 dark:hover:border-blue-600 transition-all text-left cursor-pointer"
        >
          <Building2 className="w-5 h-5 text-blue-600 mb-2" />
          <h3 className="font-semibold text-gray-900 dark:text-white text-sm">Company Directory</h3>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Explore institutional corporate partners</p>
        </button>
        <button
          onClick={() => navigate('/placement/students')}
          className="bg-white dark:bg-gray-800 p-4 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 hover:shadow-md hover:border-purple-300 dark:hover:border-purple-600 transition-all text-left cursor-pointer"
        >
          <Users className="w-5 h-5 text-purple-600 mb-2" />
          <h3 className="font-semibold text-gray-900 dark:text-white text-sm">Student Directory</h3>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Student-wise placement profiles and resumes</p>
        </button>
        <button
          onClick={() => navigate('/placement/circulars')}
          className="bg-white dark:bg-gray-800 p-4 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 hover:shadow-md hover:border-emerald-300 dark:hover:border-emerald-600 transition-all text-left cursor-pointer"
        >
          <Megaphone className="w-5 h-5 text-emerald-600 mb-2" />
          <h3 className="font-semibold text-gray-900 dark:text-white text-sm">Recruitment Drives</h3>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Circulars, rounds, and shortlist processing</p>
        </button>
      </div>
    </div>
  );
};

export default Reports;