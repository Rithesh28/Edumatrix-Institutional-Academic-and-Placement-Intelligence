import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Building2,
  Briefcase,
  Users,
  UserCheck,
  Plus,
  TrendingUp,
  FileText,
  Clock,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import StatsCard from '../../components/placement/StatsCard';
import { API_URL } from '../../services/api';

const Dashboard = () => {
  const navigate = useNavigate();
  const { stats, isLoading, fetchStats } = usePlacementStore();
  const [recentJobs, setRecentJobs] = useState([]);
  const [recentCompanies, setRecentCompanies] = useState([]);
  const [recentShortlists, setRecentShortlists] = useState([]);

  useEffect(() => {
    fetchStats();
    fetchRecentActivity();
  }, []);

  const fetchRecentActivity = async () => {
    try {
      const token = localStorage.getItem('auth-storage') 
        ? JSON.parse(localStorage.getItem('auth-storage')).state?.token 
        : '';
      
      // Fetch recent jobs
      const jobsRes = await fetch(`${API_URL}/placement/jobs?limit=5`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (jobsRes.ok) {
        const jobs = await jobsRes.json();
        setRecentJobs(jobs.slice(0, 3));
      }

      // Fetch recent companies
      const companiesRes = await fetch(`${API_URL}/placement/companies?limit=5`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (companiesRes.ok) {
        const companies = await companiesRes.json();
        setRecentCompanies(companies.slice(0, 3));
      }

      // Fetch recent shortlists
      const shortlistsRes = await fetch(`${API_URL}/placement/shortlist?limit=5`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (shortlistsRes.ok) {
        const shortlists = await shortlistsRes.json();
        setRecentShortlists(shortlists.slice(0, 3));
      }
    } catch (error) {
      console.error('Failed to fetch recent activity:', error);
    }
  };

  // Get real stats for students placed
  const studentsPlaced = stats?.total_students || 0;
  const placementRate = stats?.placement_rate || 0;

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-indigo-600 border-t-transparent"></div>
      </div>
    );
  }

  // Build recent activity items
  const activityItems = [];

  recentJobs.forEach(job => {
    activityItems.push({
      icon: <Briefcase className="w-4 h-4 text-green-600" />,
      bgColor: 'bg-green-100',
      title: 'New job posted',
      description: `${job.title} at ${job.company_name}`,
      time: job.created_at ? new Date(job.created_at).toLocaleDateString() : 'Recently'
    });
  });

  recentCompanies.forEach(company => {
    activityItems.push({
      icon: <Building2 className="w-4 h-4 text-blue-600" />,
      bgColor: 'bg-blue-100',
      title: 'New company added',
      description: company.name,
      time: company.created_at ? new Date(company.created_at).toLocaleDateString() : 'Recently'
    });
  });

  recentShortlists.forEach(shortlist => {
    activityItems.push({
      icon: <UserCheck className="w-4 h-4 text-purple-600" />,
      bgColor: 'bg-purple-100',
      title: 'Student shortlisted',
      description: `${shortlist.student_name} for ${shortlist.job_title}`,
      time: shortlist.created_at ? new Date(shortlist.created_at).toLocaleDateString() : 'Recently'
    });
  });

  // Limit to 5 most recent
  const recentActivity = activityItems.slice(0, 5);

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Placement Dashboard</h1>
          <p className="text-gray-500 text-sm">Manage placements, companies, and student applications</p>
        </div>
        <div className="flex space-x-3">
          <button
            onClick={() => navigate('/placement/resume-analyzer')}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 flex items-center space-x-2 shadow-sm"
          >
            <FileText className="w-4 h-4" />
            <span>AI Resume Analyzer</span>
          </button>
          <button
            onClick={() => navigate('/placement/companies/add')}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 flex items-center space-x-2 shadow-sm"
          >
            <Plus className="w-4 h-4" />
            <span>Add Company</span>
          </button>
          <button
            onClick={() => navigate('/placement/jobs/post')}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center space-x-2 shadow-sm"
          >
            <Plus className="w-4 h-4" />
            <span>Post Job</span>
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
        <StatsCard
          title="Total Companies"
          value={stats?.total_companies || 0}
          icon={<Building2 className="w-5 h-5" />}
          color="blue"
          subtitle={`${stats?.active_companies || 0} active`}
        />
        <StatsCard
          title="Total Jobs"
          value={stats?.total_jobs || 0}
          icon={<Briefcase className="w-5 h-5" />}
          color="green"
          subtitle={`${stats?.open_jobs || 0} open`}
        />
        <StatsCard
          title="Total Applications"
          value={stats?.total_applications || 0}
          icon={<FileText className="w-5 h-5" />}
          color="purple"
          subtitle={`${stats?.total_shortlists || 0} shortlisted`}
        />
        <StatsCard
          title="Students Placed"
          value={studentsPlaced}
          icon={<Users className="w-5 h-5" />}
          color="orange"
          subtitle={`${placementRate.toFixed(0)}% placement rate`}
        />
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-6">
        <button
          onClick={() => navigate('/placement/resume-analyzer')}
          className="bg-gradient-to-br from-purple-50 to-indigo-50 p-4 rounded-lg shadow-sm border border-purple-200 hover:shadow-md hover:border-purple-400 transition-all text-left group"
        >
          <div className="w-10 h-10 bg-purple-600 text-white rounded-lg flex items-center justify-center mb-2 group-hover:scale-110 transition-transform">
            <FileText className="w-5 h-5" />
          </div>
          <h3 className="font-semibold text-gray-900">AI Resume Analyzer</h3>
          <p className="text-xs text-gray-500 mt-1">Upload & score resumes with ATS insights</p>
        </button>
        <button
          onClick={() => navigate('/placement/companies')}
          className="bg-white p-4 rounded-lg shadow-sm border border-gray-200 hover:shadow-md transition-shadow text-left"
        >
          <Building2 className="w-6 h-6 text-blue-600 mb-2" />
          <h3 className="font-medium text-gray-900">Manage Companies</h3>
          <p className="text-sm text-gray-500">Add or view companies</p>
        </button>
        <button
          onClick={() => navigate('/placement/jobs')}
          className="bg-white p-4 rounded-lg shadow-sm border border-gray-200 hover:shadow-md transition-shadow text-left"
        >
          <Briefcase className="w-6 h-6 text-green-600 mb-2" />
          <h3 className="font-medium text-gray-900">Manage Jobs</h3>
          <p className="text-sm text-gray-500">Post or view jobs</p>
        </button>
        <button
          onClick={() => navigate('/placement/students')}
          className="bg-white p-4 rounded-lg shadow-sm border border-gray-200 hover:shadow-md transition-shadow text-left"
        >
          <Users className="w-6 h-6 text-purple-600 mb-2" />
          <h3 className="font-medium text-gray-900">View Students</h3>
          <p className="text-sm text-gray-500">Browse student profiles</p>
        </button>
        <button
          onClick={() => navigate('/placement/shortlist')}
          className="bg-white p-4 rounded-lg shadow-sm border border-gray-200 hover:shadow-md transition-shadow text-left"
        >
          <UserCheck className="w-6 h-6 text-orange-600 mb-2" />
          <h3 className="font-medium text-gray-900">Shortlists</h3>
          <p className="text-sm text-gray-500">View shortlisted students</p>
        </button>
      </div>

      {/* Recent Activity */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Recent Activity</h3>
        {recentActivity.length === 0 ? (
          <p className="text-gray-500 text-center py-4">No recent activity</p>
        ) : (
          <div className="space-y-3">
            {recentActivity.map((item, index) => (
              <div key={index} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                <div className="flex items-center space-x-3">
                  <div className={`p-2 rounded-full ${item.bgColor}`}>
                    {item.icon}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-900">{item.title}</p>
                    <p className="text-xs text-gray-500">{item.description}</p>
                  </div>
                </div>
                <span className="text-xs text-gray-400">{item.time}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;