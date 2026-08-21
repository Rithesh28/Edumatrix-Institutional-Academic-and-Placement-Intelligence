import React, { useState, useEffect } from 'react';
import { Search, Filter, Eye, Download, Trash2, RefreshCw, Loader2 } from 'lucide-react';
import resumeService from '../../services/resumeService';
import toast from 'react-hot-toast';

const ResumeList = ({ onSelectResume, studentId = null }) => {
  const [resumes, setResumes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    status: '',
    minScore: '',
    maxScore: '',
    limit: 20,
    offset: 0,
  });
  const [total, setTotal] = useState(0);
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    fetchResumes();
  }, [filters, studentId]);

  const fetchResumes = async () => {
    setLoading(true);
    try {
      const params = { ...filters };
      if (studentId) params.studentId = studentId;
      
      const response = await resumeService.getResumes(params);
      setResumes(response.resumes || []);
      setTotal(response.total || 0);
    } catch (error) {
      console.error('Error fetching resumes:', error);
      toast.error('Failed to load resumes');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (resumeId) => {
    if (!confirm('Are you sure you want to delete this resume?')) return;
    
    try {
      await resumeService.deleteResume(resumeId);
      toast.success('Resume deleted successfully');
      fetchResumes();
    } catch (error) {
      console.error('Error deleting resume:', error);
      toast.error('Failed to delete resume');
    }
  };

  const handleExport = async (resumeId, format) => {
    try {
      const data = await resumeService.exportResume(resumeId, format);
      const url = window.URL.createObjectURL(new Blob([data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `resume_${resumeId}.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      toast.success(`Resume exported as ${format.toUpperCase()}`);
    } catch (error) {
      console.error('Error exporting resume:', error);
      toast.error('Failed to export resume');
    }
  };

  const getStatusBadge = (status) => {
    const colors = {
      completed: 'bg-green-100 text-green-800',
      processing: 'bg-yellow-100 text-yellow-800',
      pending: 'bg-blue-100 text-blue-800',
      failed: 'bg-red-100 text-red-800',
    };
    return colors[status?.toLowerCase()] || 'bg-gray-100 text-gray-800';
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-800">
          Resumes ({total})
        </h3>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <Filter className="w-5 h-5" />
          </button>
          <button
            onClick={fetchResumes}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Filters */}
      {showFilters && (
        <div className="mb-4 p-4 bg-gray-50 rounded-lg grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <label className="block text-sm text-gray-600 mb-1">Status</label>
            <select
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              value={filters.status}
              onChange={(e) => setFilters({ ...filters, status: e.target.value })}
            >
              <option value="">All</option>
              <option value="pending">Pending</option>
              <option value="processing">Processing</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">Min Score</label>
            <input
              type="number"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              placeholder="0"
              value={filters.minScore}
              onChange={(e) => setFilters({ ...filters, minScore: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">Max Score</label>
            <input
              type="number"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              placeholder="100"
              value={filters.maxScore}
              onChange={(e) => setFilters({ ...filters, maxScore: e.target.value })}
            />
          </div>
          <div className="flex items-end">
            <button
              onClick={() => setFilters({ status: '', minScore: '', maxScore: '', limit: 20, offset: 0 })}
              className="w-full px-4 py-2 bg-gray-200 hover:bg-gray-300 rounded-lg font-medium transition-colors"
            >
              Clear Filters
            </button>
          </div>
        </div>
      )}

      {/* Resume List */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-indigo-600 animate-spin" />
        </div>
      ) : resumes.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500">No resumes found</p>
          <p className="text-sm text-gray-400">Upload a resume to get started</p>
        </div>
      ) : (
        <div className="space-y-3">
          {resumes.map((resume) => (
            <div
              key={resume.id}
              className="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:border-indigo-300 transition-colors"
            >
              <div className="flex items-center gap-4 flex-1 min-w-0">
                <div className="flex-shrink-0">
                  <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center">
                    <span className="text-lg">📄</span>
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-800 truncate">
                    {resume.name || 'Unnamed Resume'}
                  </p>
                  <div className="flex items-center gap-3 text-sm text-gray-500 flex-wrap">
                    <span>{resume.student_name || `Student #${resume.student_id}`}</span>
                    <span>•</span>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getStatusBadge(resume.status)}`}>
                      {resume.status || 'pending'}
                    </span>
                    {resume.ats_score !== null && (
                      <>
                        <span>•</span>
                        <span className="font-medium text-indigo-600">
                          ATS: {Math.round(resume.ats_score)}%
                        </span>
                      </>
                    )}
                    <span>•</span>
                    <span>{new Date(resume.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 flex-shrink-0 ml-4">
                <button
                  onClick={() => onSelectResume?.(resume.id)}
                  className="p-2 text-gray-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                  title="View Details"
                >
                  <Eye className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleExport(resume.id, 'json')}
                  className="p-2 text-gray-500 hover:text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                  title="Export JSON"
                >
                  <Download className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleDelete(resume.id)}
                  className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  title="Delete"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ResumeList;