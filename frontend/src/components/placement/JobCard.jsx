import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Briefcase, Building2, MapPin, DollarSign, Clock, Eye, Edit2, Trash2 } from 'lucide-react';

const JobCard = ({ job, onDelete }) => {
  const navigate = useNavigate();

  const getStatusColor = (status) => {
    switch (status) {
      case 'open': return 'bg-green-100 text-green-700';
      case 'closed': return 'bg-gray-100 text-gray-600';
      case 'draft': return 'bg-yellow-100 text-yellow-700';
      default: return 'bg-gray-100 text-gray-600';
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center space-x-2">
            <span className={`text-xs px-2 py-0.5 rounded-full ${getStatusColor(job.status)}`}>
              {job.status?.toUpperCase()}
            </span>
            <span className="text-xs text-gray-400">
              {job.created_at ? new Date(job.created_at).toLocaleDateString() : ''}
            </span>
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mt-1">{job.title}</h3>
          <p className="text-sm text-gray-500 flex items-center space-x-1">
            <Building2 className="w-3 h-3" />
            <span>{job.company_name || 'Unknown Company'}</span>
            {job.location && <span>• {job.location}</span>}
          </p>
          <div className="flex flex-wrap gap-4 mt-2 text-sm text-gray-500">
            {job.salary_range && (
              <span className="flex items-center space-x-1">
                <DollarSign className="w-3 h-3" />
                <span>{job.salary_range}</span>
              </span>
            )}
            {job.experience_level && (
              <span className="flex items-center space-x-1">
                <Clock className="w-3 h-3" />
                <span>{job.experience_level}</span>
              </span>
            )}
            {job.cgpa_criteria && (
              <span>CGPA: {job.cgpa_criteria}+</span>
            )}
          </div>
          <div className="flex flex-wrap gap-1 mt-2">
            {job.required_skills?.slice(0, 4).map((skill) => (
              <span key={skill} className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full">
                {skill}
              </span>
            ))}
            {job.required_skills?.length > 4 && (
              <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-400 rounded-full">
                +{job.required_skills.length - 4} more
              </span>
            )}
          </div>
        </div>
        <div className="flex space-x-1">
          <button
            onClick={() => navigate(`/placement/jobs/${job.id}`)}
            className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"
          >
            <Eye className="w-4 h-4" />
          </button>
          <button
            onClick={() => navigate(`/placement/jobs/${job.id}/edit`)}
            className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"
          >
            <Edit2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => onDelete?.(job.id)}
            className="p-1.5 text-gray-400 hover:text-red-600 rounded-lg hover:bg-red-50"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default JobCard;