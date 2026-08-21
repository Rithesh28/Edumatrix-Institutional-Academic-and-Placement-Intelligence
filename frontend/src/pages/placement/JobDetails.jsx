import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Building2,
  MapPin,
  Calendar,
  DollarSign,
  Users,
  Briefcase,
  Clock,
  UserCheck,
  TrendingUp,
  FileText,
  Send,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import toast from 'react-hot-toast';
import BatchFileUpload from '../../components/placement/BatchFileUpload';

const JobDetails = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { selectedJob, isLoading, fetchJobPosting, matchStudents, applications, fetchApplications } = usePlacementStore();
  const [matchedStudents, setMatchedStudents] = useState([]);
  const [showMatchResults, setShowMatchResults] = useState(false);
  const [isMatching, setIsMatching] = useState(false);

  useEffect(() => {
    if (id) {
      fetchJobPosting(id);
      fetchApplications({ job_posting_id: id });
    }
  }, [id]);

  const handleMatchStudents = async () => {
    setIsMatching(true);
    try {
      const result = await matchStudents({ job_posting_id: parseInt(id) });
      setMatchedStudents(result.eligible_students || []);
      setShowMatchResults(true);
      toast.success(`Found ${result.total_eligible} eligible students`);
    } catch (error) {
      toast.error('Failed to match students');
    } finally {
      setIsMatching(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'open': return 'bg-green-100 text-green-700';
      case 'closed': return 'bg-gray-100 text-gray-600';
      case 'draft': return 'bg-yellow-100 text-yellow-700';
      default: return 'bg-gray-100 text-gray-600';
    }
  };

  const getAppStatusColor = (status) => {
    switch (status) {
      case 'shortlisted': return 'bg-yellow-100 text-yellow-700';
      case 'selected': return 'bg-green-100 text-green-700';
      case 'rejected': return 'bg-red-100 text-red-700';
      default: return 'bg-blue-100 text-blue-700';
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-indigo-600 border-t-transparent"></div>
      </div>
    );
  }

  if (!selectedJob) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Job not found</p>
      </div>
    );
  }

  return (
    <div>
      {/* Back Button */}
      <button
        onClick={() => navigate('/placement/jobs')}
        className="flex items-center space-x-2 text-gray-600 hover:text-gray-800 mb-4"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Jobs</span>
      </button>

      {/* Job Info */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center space-x-3">
              <span className={`text-xs px-2 py-0.5 rounded-full ${getStatusColor(selectedJob.status)}`}>
                {selectedJob.status?.toUpperCase()}
              </span>
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mt-2">{selectedJob.title}</h1>
            <p className="text-gray-600 flex items-center space-x-2 mt-1">
              <Building2 className="w-4 h-4" />
              <span>{selectedJob.company_name}</span>
            </p>
          </div>
          <div className="flex space-x-2">
            <button
              onClick={handleMatchStudents}
              disabled={isMatching}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 flex items-center space-x-2"
            >
              <Users className="w-4 h-4" />
              <span>{isMatching ? 'Matching...' : 'Find Candidates'}</span>
            </button>
            <button
              onClick={() => navigate(`/placement/jobs/${id}/edit`)}
              className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
            >
              Edit
            </button>
          </div>
        </div>

        {/* Job Details Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
          <div className="flex items-center space-x-2 text-sm text-gray-600">
            <MapPin className="w-4 h-4 text-gray-400" />
            <span>{selectedJob.location || 'Not specified'}</span>
          </div>
          <div className="flex items-center space-x-2 text-sm text-gray-600">
            <DollarSign className="w-4 h-4 text-gray-400" />
            <span>{selectedJob.salary_range || 'Not specified'}</span>
          </div>
          <div className="flex items-center space-x-2 text-sm text-gray-600">
            <Clock className="w-4 h-4 text-gray-400" />
            <span>{selectedJob.experience_level || 'Any'}</span>
          </div>
          <div className="flex items-center space-x-2 text-sm text-gray-600">
            <TrendingUp className="w-4 h-4 text-gray-400" />
            <span>CGPA: {selectedJob.cgpa_criteria || 'N/A'}+</span>
          </div>
        </div>

        {selectedJob.description && (
          <div className="mt-4 p-4 bg-gray-50 rounded-lg">
            <h3 className="text-sm font-medium text-gray-700 mb-2">Description</h3>
            <p className="text-sm text-gray-600 whitespace-pre-wrap">{selectedJob.description}</p>
          </div>
        )}

        {/* Skills */}
        {selectedJob.required_skills?.length > 0 && (
          <div className="mt-4">
            <h3 className="text-sm font-medium text-gray-700 mb-2">Required Skills</h3>
            <div className="flex flex-wrap gap-2">
              {selectedJob.required_skills.map((skill) => (
                <span key={skill} className="px-2 py-1 bg-indigo-100 text-indigo-700 rounded-full text-sm">
                  {skill}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Eligibility */}
        {selectedJob.branch_eligibility?.length > 0 && (
          <div className="mt-4">
            <h3 className="text-sm font-medium text-gray-700 mb-2">Eligible Branches</h3>
            <div className="flex flex-wrap gap-2">
              {selectedJob.branch_eligibility.map((branch) => (
                <span key={branch} className="px-2 py-1 bg-green-100 text-green-700 rounded-full text-sm">
                  {branch}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Deadlines */}
        <div className="mt-4 flex flex-wrap gap-4 text-sm text-gray-500">
          {selectedJob.application_deadline && (
            <div className="flex items-center space-x-2">
              <Calendar className="w-4 h-4" />
              <span>Apply by: {new Date(selectedJob.application_deadline).toLocaleDateString()}</span>
            </div>
          )}
          {selectedJob.drive_date && (
            <div className="flex items-center space-x-2">
              <Calendar className="w-4 h-4" />
              <span>Drive on: {new Date(selectedJob.drive_date).toLocaleDateString()}</span>
            </div>
          )}
        </div>
      </div>

      {/* Batch File Upload Section */}
      <div className="mt-6">
        <BatchFileUpload 
          jobPostingId={id}
          onUploadComplete={(result) => {
            toast.success(`Processed ${result.processed || 0} files`);
            // Refresh data if needed
          }}
        />
      </div>

      {/* Matched Students Results */}
      {showMatchResults && (
        <div className="mt-6 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center space-x-2">
              <UserCheck className="w-5 h-5 text-indigo-600" />
              <span>Eligible Candidates ({matchedStudents.length})</span>
            </h3>
            <button
              onClick={() => setShowMatchResults(false)}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              Close
            </button>
          </div>

          {matchedStudents.length === 0 ? (
            <p className="text-gray-500 text-center py-4">No eligible students found</p>
          ) : (
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {matchedStudents.slice(0, 10).map((student, index) => (
                <div
                  key={student.student_id}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100"
                >
                  <div className="flex items-center space-x-3">
                    <span className="text-sm font-medium text-gray-500">#{index + 1}</span>
                    <div>
                      <p className="font-medium text-gray-900">{student.student_name}</p>
                      <p className="text-sm text-gray-500">{student.email}</p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-4">
                    <div className="text-right">
                      <p className="text-sm font-medium text-indigo-600">{student.match_score.toFixed(1)}%</p>
                      <p className="text-xs text-gray-400">Match</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-gray-600">{student.cgpa}</p>
                      <p className="text-xs text-gray-400">CGPA</p>
                    </div>
                    <button
                      onClick={() => navigate(`/placement/students/${student.student_id}`)}
                      className="px-3 py-1 text-xs bg-indigo-100 text-indigo-700 rounded-lg hover:bg-indigo-200"
                    >
                      View Profile
                    </button>
                  </div>
                </div>
              ))}
              {matchedStudents.length > 10 && (
                <p className="text-center text-sm text-gray-500">
                  +{matchedStudents.length - 10} more candidates
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Applications */}
      <div className="mt-6 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center space-x-2 mb-4">
          <FileText className="w-5 h-5 text-gray-500" />
          <span>Applications ({applications.length})</span>
        </h3>

        {applications.length === 0 ? (
          <p className="text-gray-500 text-center py-4">No applications yet</p>
        ) : (
          <div className="space-y-3">
            {applications.map((app) => (
              <div
                key={app.id}
                className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
              >
                <div>
                  <p className="font-medium text-gray-900">{app.student_name}</p>
                  <p className="text-sm text-gray-500">{app.student_email}</p>
                </div>
                <div className="flex items-center space-x-4">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${getAppStatusColor(app.status)}`}>
                    {app.status?.toUpperCase()}
                  </span>
                  <span className="text-sm text-gray-500">
                    {app.match_percentage ? `${app.match_percentage.toFixed(1)}% match` : 'N/A'}
                  </span>
                  <button
                    onClick={() => navigate(`/placement/students/${app.student_id}`)}
                    className="px-3 py-1 text-xs bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
                  >
                    View
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default JobDetails;