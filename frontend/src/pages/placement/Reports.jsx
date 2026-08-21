import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, Download, TrendingUp, Building2, Users, Briefcase, Calendar, ArrowLeft } from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import toast from 'react-hot-toast';

const Reports = () => {
  const navigate = useNavigate();
  const { stats, isLoading, fetchStats } = usePlacementStore();
  const [isExporting, setIsExporting] = useState(false);

  useEffect(() => {
    fetchStats();
  }, []);

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const token = localStorage.getItem('auth-storage') 
        ? JSON.parse(localStorage.getItem('auth-storage')).state?.token 
        : '';
      
      const response = await fetch('http://localhost:8000/placement/reports/export', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `placement_report_${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
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

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-indigo-600 border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div>
      {/* Back Button */}
      <button
        onClick={() => navigate('/placement/dashboard')}
        className="flex items-center space-x-2 text-gray-600 hover:text-gray-800 mb-4 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Dashboard</span>
      </button>

      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Placement Reports</h1>
          <p className="text-gray-500 text-sm">View and export placement statistics</p>
        </div>
        <button
          onClick={handleExport}
          disabled={isExporting}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 flex items-center space-x-2"
        >
          <Download className="w-4 h-4" />
          <span>{isExporting ? 'Generating...' : 'Export Report'}</span>
        </button>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Companies</p>
              <p className="text-2xl font-bold text-gray-900">{stats?.total_companies || 0}</p>
            </div>
            <Building2 className="w-8 h-8 text-blue-500" />
          </div>
          <p className="text-xs text-gray-400 mt-2">{stats?.active_companies || 0} active</p>
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Jobs</p>
              <p className="text-2xl font-bold text-gray-900">{stats?.total_jobs || 0}</p>
            </div>
            <Briefcase className="w-8 h-8 text-green-500" />
          </div>
          <p className="text-xs text-gray-400 mt-2">{stats?.open_jobs || 0} open</p>
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Applications</p>
              <p className="text-2xl font-bold text-gray-900">{stats?.total_applications || 0}</p>
            </div>
            <FileText className="w-8 h-8 text-purple-500" />
          </div>
          <p className="text-xs text-gray-400 mt-2">{stats?.total_shortlists || 0} shortlisted</p>
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Placement Rate</p>
              <p className="text-2xl font-bold text-indigo-600">{stats?.placement_rate?.toFixed(1) || 0}%</p>
            </div>
            <TrendingUp className="w-8 h-8 text-indigo-500" />
          </div>
          <p className="text-xs text-gray-400 mt-2">{stats?.total_students || 0} students</p>
        </div>
      </div>

      {/* Application Status Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Applications by Status</h3>
          <div className="space-y-3">
            {stats?.applications_by_status && Object.entries(stats.applications_by_status).map(([status, count]) => (
              <div key={status} className="flex items-center justify-between">
                <span className="text-sm text-gray-600 capitalize">{status}</span>
                <div className="flex items-center space-x-4">
                  <div className="w-48 bg-gray-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full ${
                        status === 'selected' ? 'bg-green-500' :
                        status === 'shortlisted' ? 'bg-yellow-500' :
                        status === 'rejected' ? 'bg-red-500' :
                        'bg-blue-500'
                      }`}
                      style={{ width: `${Math.min((count / (stats?.total_applications || 1)) * 100, 100)}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium text-gray-700">{count}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Jobs by Status</h3>
          <div className="space-y-3">
            {stats?.jobs_by_status && Object.entries(stats.jobs_by_status).map(([status, count]) => (
              <div key={status} className="flex items-center justify-between">
                <span className="text-sm text-gray-600 capitalize">{status}</span>
                <div className="flex items-center space-x-4">
                  <div className="w-48 bg-gray-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full ${
                        status === 'open' ? 'bg-green-500' :
                        status === 'closed' ? 'bg-gray-500' :
                        'bg-yellow-500'
                      }`}
                      style={{ width: `${Math.min((count / (stats?.total_jobs || 1)) * 100, 100)}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium text-gray-700">{count}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
        <button
          onClick={() => navigate('/placement/companies')}
          className="bg-white p-4 rounded-lg shadow-sm border border-gray-200 hover:shadow-md transition-shadow text-left"
        >
          <Building2 className="w-5 h-5 text-blue-600 mb-2" />
          <h3 className="font-medium text-gray-900">Company Report</h3>
          <p className="text-sm text-gray-500">Detailed company-wise placement report</p>
        </button>
        <button
          onClick={() => navigate('/placement/students')}
          className="bg-white p-4 rounded-lg shadow-sm border border-gray-200 hover:shadow-md transition-shadow text-left"
        >
          <Users className="w-5 h-5 text-purple-600 mb-2" />
          <h3 className="font-medium text-gray-900">Student Report</h3>
          <p className="text-sm text-gray-500">Student-wise placement status</p>
        </button>
        <button
          onClick={() => navigate('/placement/jobs')}
          className="bg-white p-4 rounded-lg shadow-sm border border-gray-200 hover:shadow-md transition-shadow text-left"
        >
          <TrendingUp className="w-5 h-5 text-green-600 mb-2" />
          <h3 className="font-medium text-gray-900">Trend Analysis</h3>
          <p className="text-sm text-gray-500">Placement trends and insights</p>
        </button>
      </div>
    </div>
  );
};

export default Reports;