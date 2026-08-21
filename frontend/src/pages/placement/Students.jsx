import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Users, Search, Filter, UserCheck, ArrowLeft, RefreshCw, FileText, Award, GraduationCap, ChevronRight } from 'lucide-react';
import { getStudents } from '../../services/placementService';
import toast from 'react-hot-toast';

const Students = () => {
  const navigate = useNavigate();
  const [students, setStudents] = useState([]);
  const [filteredStudents, setFilteredStudents] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    fetchStudents();
  }, []);

  const fetchStudents = async () => {
    setIsLoading(true);
    try {
      const data = await getStudents();
      const studentList = Array.isArray(data) ? data : [];
      setStudents(studentList);
      setFilteredStudents(studentList);
    } catch (error) {
      console.error('Failed to fetch students:', error);
      toast.error('Failed to fetch students');
    } finally {
      setIsLoading(false);
    }
  };

  // Search and filter logic
  useEffect(() => {
    let filtered = students;

    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      filtered = filtered.filter(s =>
        s.name?.toLowerCase().includes(term) ||
        s.email?.toLowerCase().includes(term) ||
        s.department?.toLowerCase().includes(term) ||
        s.branch?.toLowerCase().includes(term) ||
        (Array.isArray(s.skills) && s.skills.some(sk => sk.toLowerCase().includes(term)))
      );
    }

    if (filter !== 'all') {
      filtered = filtered.filter(s => s.status?.toLowerCase() === filter.toLowerCase() || s.placement_status?.toLowerCase() === filter.toLowerCase());
    }

    setFilteredStudents(filtered);
  }, [searchTerm, filter, students]);

  const getStatusBadge = (statusStr) => {
    const s = statusStr?.toLowerCase();
    switch (s) {
      case 'selected':
      case 'placed':
        return { text: 'Placed / Selected', color: 'bg-emerald-100 text-emerald-800 border-emerald-200' };
      case 'shortlisted':
        return { text: 'Shortlisted', color: 'bg-amber-100 text-amber-800 border-amber-200' };
      case 'applied':
        return { text: 'Applied', color: 'bg-blue-100 text-blue-800 border-blue-200' };
      default:
        return { text: 'Not Applied', color: 'bg-gray-100 text-gray-700 border-gray-200' };
    }
  };

  const getScoreBadge = (score) => {
    if (score === null || score === undefined) return null;
    if (score >= 75) return <span className="px-2 py-0.5 text-xs bg-green-100 text-green-800 rounded-md font-semibold">ATS {Math.round(score)}%</span>;
    if (score >= 50) return <span className="px-2 py-0.5 text-xs bg-amber-100 text-amber-800 rounded-md font-semibold">ATS {Math.round(score)}%</span>;
    return <span className="px-2 py-0.5 text-xs bg-rose-100 text-rose-800 rounded-md font-semibold">ATS {Math.round(score)}%</span>;
  };

  return (
    <div className="space-y-6">
      {/* Back Button & Header */}
      <div>
        <button
          onClick={() => navigate('/placement/dashboard')}
          className="flex items-center space-x-2 text-gray-500 hover:text-gray-800 text-sm mb-3 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Placement Dashboard</span>
        </button>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Users className="w-7 h-7 text-indigo-600" />
              Student Profiles & Placement Directory
            </h1>
            <p className="text-gray-500 text-sm mt-0.5">
              View registered students, academic performance, skills, ATS score, and job applications.
            </p>
          </div>
          <button
            onClick={fetchStudents}
            className="self-start sm:self-auto px-4 py-2 bg-white border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50 flex items-center gap-2 shadow-sm text-sm"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Search & Filters Bar */}
      <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm flex flex-col md:flex-row gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by student name, email, department, or skill (e.g. Python, React)..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
          />
        </div>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="px-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none bg-white"
        >
          <option value="all">All Placement Statuses</option>
          <option value="selected">Placed / Selected</option>
          <option value="shortlisted">Shortlisted</option>
          <option value="applied">Applied</option>
          <option value="not_applied">Not Applied</option>
        </select>
      </div>

      {/* Students List */}
      {isLoading ? (
        <div className="flex justify-center items-center py-16">
          <RefreshCw className="w-8 h-8 text-indigo-600 animate-spin" />
          <span className="ml-3 text-sm font-medium text-gray-600">Loading student directory...</span>
        </div>
      ) : filteredStudents.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
          <Users className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-base font-semibold text-gray-700">No students found</p>
          <p className="text-xs text-gray-400 mt-1">
            {searchTerm ? 'Try adjusting your search criteria' : 'Students will appear here once registered'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredStudents.map((student) => {
            const badge = getStatusBadge(student.status || student.placement_status);
            return (
              <div
                key={student.id}
                onClick={() => navigate(`/placement/students/${student.id}`)}
                className="bg-white rounded-xl border border-gray-200 hover:border-indigo-400 p-5 shadow-sm hover:shadow-md transition-all cursor-pointer flex flex-col justify-between group"
              >
                <div>
                  {/* Top Row: Avatar + Name + Status */}
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center space-x-3 min-w-0">
                      <div className="w-12 h-12 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 font-bold text-lg flex-shrink-0 group-hover:bg-indigo-600 group-hover:text-white transition-colors">
                        {student.name?.charAt(0).toUpperCase() || 'S'}
                      </div>
                      <div className="min-w-0">
                        <h3 className="font-bold text-gray-900 truncate group-hover:text-indigo-600 transition-colors">
                          {student.name || 'Student Candidate'}
                        </h3>
                        <p className="text-xs text-gray-500 truncate">{student.email}</p>
                      </div>
                    </div>
                    <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border flex-shrink-0 ${badge.color}`}>
                      {badge.text}
                    </span>
                  </div>

                  {/* Academic Stats */}
                  <div className="mt-4 grid grid-cols-2 gap-2 bg-gray-50/70 p-3 rounded-lg border border-gray-100 text-xs text-gray-600">
                    <div>
                      <span className="text-gray-400 block text-[10px] uppercase font-semibold">Department</span>
                      <span className="font-medium text-gray-800 truncate block">{student.branch || student.department || 'General'}</span>
                    </div>
                    <div>
                      <span className="text-gray-400 block text-[10px] uppercase font-semibold">CGPA / Year</span>
                      <span className="font-medium text-gray-800">
                        {student.cgpa ? `${student.cgpa} CGPA` : 'N/A'} {student.year ? `• Yr ${student.year}` : ''}
                      </span>
                    </div>
                  </div>

                  {/* Skills badges */}
                  {Array.isArray(student.skills) && student.skills.length > 0 && (
                    <div className="mt-3">
                      <p className="text-[10px] font-semibold uppercase text-gray-400 mb-1">Key Skills</p>
                      <div className="flex flex-wrap gap-1">
                        {student.skills.slice(0, 3).map((sk, idx) => (
                          <span key={idx} className="px-2 py-0.5 bg-indigo-50/60 text-indigo-700 text-[11px] rounded-md font-medium">
                            {typeof sk === 'string' ? sk : sk.name || ''}
                          </span>
                        ))}
                        {student.skills.length > 3 && (
                          <span className="text-[11px] text-gray-400 self-center">+{student.skills.length - 3}</span>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                {/* Bottom Footer: ATS & Profile link */}
                <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-1.5">
                    {getScoreBadge(student.ats_score)}
                    {student.total_applications > 0 && (
                      <span className="text-gray-500 text-[11px]">
                        {student.total_applications} {student.total_applications === 1 ? 'app' : 'apps'}
                      </span>
                    )}
                  </div>
                  <span className="text-indigo-600 font-semibold flex items-center group-hover:translate-x-0.5 transition-transform">
                    View Profile <ChevronRight className="w-3.5 h-3.5 ml-0.5" />
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default Students;