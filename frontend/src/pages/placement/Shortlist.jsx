import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { UserCheck, Building2, Briefcase, X, Search, ArrowLeft } from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import toast from 'react-hot-toast';

const Shortlist = () => {
  const navigate = useNavigate();
  const { shortlists, isLoading, fetchShortlists, removeFromShortlist } = usePlacementStore();
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    fetchShortlists();
  }, []);

  const handleRemove = async (id, name) => {
    if (window.confirm(`Remove ${name} from shortlist?`)) {
      try {
        await removeFromShortlist(id);
        toast.success('Student removed from shortlist');
      } catch (error) {
        toast.error('Failed to remove');
      }
    }
  };

  const filteredShortlists = shortlists.filter((s) =>
    s.student_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    s.company_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    s.job_title?.toLowerCase().includes(searchTerm.toLowerCase())
  );

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
          <h1 className="text-2xl font-bold text-gray-900">Shortlisted Students</h1>
          <p className="text-gray-500 text-sm">Manage shortlisted candidates</p>
        </div>
        <div className="text-sm text-gray-500">
          {filteredShortlists.length} candidates
        </div>
      </div>

      {/* Search */}
      <div className="relative mb-6">
        <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
        <input
          type="text"
          placeholder="Search shortlisted candidates..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
        />
      </div>

      {filteredShortlists.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <UserCheck className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500">No shortlisted candidates</p>
          <p className="text-sm text-gray-400">Shortlist students from job details page</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredShortlists.map((shortlist) => (
            <div
              key={shortlist.id}
              className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 hover:shadow-md transition-shadow"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <div className="w-10 h-10 rounded-full bg-yellow-100 flex items-center justify-center">
                    <UserCheck className="w-5 h-5 text-yellow-600" />
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <h3 className="font-semibold text-gray-900">{shortlist.student_name}</h3>
                      <span className="text-xs text-gray-400">{shortlist.student_email}</span>
                    </div>
                    <div className="flex items-center space-x-2 text-sm text-gray-500">
                      <Building2 className="w-3 h-3" />
                      <span>{shortlist.company_name}</span>
                      <span className="text-gray-300">•</span>
                      <Briefcase className="w-3 h-3" />
                      <span>{shortlist.job_title}</span>
                    </div>
                    {shortlist.reason && (
                      <p className="text-xs text-gray-400 mt-1">Reason: {shortlist.reason}</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => navigate(`/placement/students/${shortlist.student_id}`)}
                    className="px-3 py-1 text-xs bg-indigo-100 text-indigo-700 rounded-lg hover:bg-indigo-200"
                  >
                    View Profile
                  </button>
                  <button
                    onClick={() => handleRemove(shortlist.id, shortlist.student_name)}
                    className="p-1.5 text-gray-400 hover:text-red-600 rounded-lg hover:bg-red-50"
                    title="Remove from shortlist"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <div className="mt-2 text-xs text-gray-400">
                Shortlisted: {shortlist.created_at ? new Date(shortlist.created_at).toLocaleDateString() : 'N/A'}
                {shortlist.shortlister_name && ` by ${shortlist.shortlister_name}`}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Shortlist;