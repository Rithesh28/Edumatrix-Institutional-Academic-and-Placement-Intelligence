import React from 'react';
import { useNavigate } from 'react-router-dom';
import { User, Mail, BookOpen, CheckCircle, Clock, UserCheck } from 'lucide-react';

const StudentCard = ({ student }) => {
  const navigate = useNavigate();

  const getStatusInfo = (status) => {
    switch (status) {
      case 'selected':
        return { text: 'Selected', color: 'bg-green-100 text-green-700', icon: <CheckCircle className="w-4 h-4" /> };
      case 'shortlisted':
        return { text: 'Shortlisted', color: 'bg-yellow-100 text-yellow-700', icon: <UserCheck className="w-4 h-4" /> };
      case 'applied':
        return { text: 'Applied', color: 'bg-blue-100 text-blue-700', icon: <Clock className="w-4 h-4" /> };
      default:
        return { text: 'Not Applied', color: 'bg-gray-100 text-gray-500', icon: null };
    }
  };

  const statusInfo = getStatusInfo(student.status);

  return (
    <div
      className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 hover:shadow-md transition-shadow cursor-pointer"
      onClick={() => navigate(`/placement/students/${student.id}`)}
    >
      <div className="flex items-start space-x-3">
        <div className="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 font-semibold flex-shrink-0">
          {student.name?.charAt(0).toUpperCase()}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <h3 className="font-medium text-gray-900 truncate">{student.name}</h3>
            <span className={`text-xs px-2 py-0.5 rounded-full flex items-center space-x-1 ${statusInfo.color}`}>
              {statusInfo.icon}
              <span>{statusInfo.text}</span>
            </span>
          </div>
          <p className="text-sm text-gray-500 truncate flex items-center space-x-1">
            <Mail className="w-3 h-3" />
            <span>{student.email}</span>
          </p>
          {student.branch && (
            <p className="text-sm text-gray-500 flex items-center space-x-1">
              <BookOpen className="w-3 h-3" />
              <span>{student.branch}</span>
            </p>
          )}
          <div className="flex items-center space-x-2 mt-1">
            <span className="text-xs text-gray-400">
              {student.applications?.length || 0} applications
            </span>
            {student.cgpa && (
              <span className="text-xs text-gray-400">• CGPA: {student.cgpa}</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default StudentCard;