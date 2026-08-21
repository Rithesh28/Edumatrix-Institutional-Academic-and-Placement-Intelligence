import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  User,
  Mail,
  Phone,
  BookOpen,
  Award,
  Briefcase,
  CheckCircle,
  Clock,
  FileText,
  Building2,
  TrendingUp,
  GraduationCap,
  Sparkles,
  ExternalLink,
} from 'lucide-react';
import { getStudent } from '../../services/placementService';
import toast from 'react-hot-toast';

const StudentProfile = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [student, setStudent] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchStudent();
  }, [id]);

  const fetchStudent = async () => {
    setIsLoading(true);
    try {
      const data = await getStudent(id);
      setStudent(data);
    } catch (error) {
      console.error('Failed to fetch student details:', error);
      toast.error('Failed to fetch student details');
    } finally {
      setIsLoading(false);
    }
  };

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

  const getAppStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'shortlisted': return 'bg-amber-100 text-amber-800';
      case 'selected': return 'bg-emerald-100 text-emerald-800';
      case 'rejected': return 'bg-rose-100 text-rose-800';
      default: return 'bg-blue-100 text-blue-800';
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-indigo-600 border-t-transparent"></div>
      </div>
    );
  }

  if (!student) {
    return (
      <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
        <p className="text-gray-500">Student not found</p>
        <button
          onClick={() => navigate('/placement/students')}
          className="mt-4 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm"
        >
          Back to Students
        </button>
      </div>
    );
  }

  const status = getStatusBadge(student.status || student.placement_status);

  return (
    <div className="space-y-6">
      {/* Back Button */}
      <button
        onClick={() => navigate('/placement/students')}
        className="flex items-center space-x-2 text-gray-600 hover:text-gray-900 transition-colors text-sm"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Student Directory</span>
      </button>

      {/* Main Student Header Card */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center space-x-4">
            <div className="w-16 h-16 rounded-2xl bg-indigo-600 text-white flex items-center justify-center text-2xl font-bold shadow-md">
              {student.name?.charAt(0).toUpperCase() || 'S'}
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{student.name || 'Student Profile'}</h1>
              <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500 mt-1">
                <span className="flex items-center gap-1">
                  <Mail className="w-3.5 h-3.5 text-gray-400" />
                  {student.email}
                </span>
                {student.phone && (
                  <span className="flex items-center gap-1">
                    <Phone className="w-3.5 h-3.5 text-gray-400" />
                    {student.phone}
                  </span>
                )}
                {student.enrollment_number && (
                  <span className="bg-gray-100 px-2 py-0.5 rounded text-gray-600 font-medium">
                    Roll: {student.enrollment_number}
                  </span>
                )}
              </div>
            </div>
          </div>
          <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${status.color}`}>
            {status.text}
          </span>
        </div>

        {/* Academic Overview KPI Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 pt-6 border-t border-gray-100">
          <div className="p-3 bg-gray-50 rounded-xl text-center border border-gray-100">
            <p className="text-xs text-gray-500 uppercase font-semibold">Department / Branch</p>
            <p className="text-sm font-bold text-gray-900 mt-1 truncate">{student.branch || student.department || 'General'}</p>
          </div>
          <div className="p-3 bg-gray-50 rounded-xl text-center border border-gray-100">
            <p className="text-xs text-gray-500 uppercase font-semibold">Year & Semester</p>
            <p className="text-sm font-bold text-indigo-600 mt-1">
              {student.year ? `Year ${student.year}` : 'N/A'} {student.semester ? `• Sem ${student.semester}` : ''}
            </p>
          </div>
          <div className="p-3 bg-gray-50 rounded-xl text-center border border-gray-100">
            <p className="text-xs text-gray-500 uppercase font-semibold">CGPA</p>
            <p className="text-sm font-bold text-emerald-600 mt-1">{student.cgpa ? `${student.cgpa} / 10.0` : 'N/A'}</p>
          </div>
          <div className="p-3 bg-gray-50 rounded-xl text-center border border-gray-100">
            <p className="text-xs text-gray-500 uppercase font-semibold">Applications</p>
            <p className="text-sm font-bold text-purple-600 mt-1">{student.total_applications || student.applications?.length || 0}</p>
          </div>
        </div>
      </div>

      {/* Skills & Resumes Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Skills */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          <h3 className="text-base font-bold text-gray-900 flex items-center gap-2 mb-3">
            <Award className="w-5 h-5 text-indigo-600" />
            Skills & Competencies
          </h3>
          {Array.isArray(student.skills) && student.skills.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {student.skills.map((skill, idx) => (
                <span key={idx} className="px-3 py-1 bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs rounded-lg font-medium">
                  {typeof skill === 'string' ? skill : skill.name || ''}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400">No skills added yet.</p>
          )}
        </div>

        {/* Resumes with ATS Score */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-base font-bold text-gray-900 flex items-center gap-2">
              <FileText className="w-5 h-5 text-purple-600" />
              Resumes & ATS Scores
            </h3>
            <button
              onClick={() => navigate('/placement/resume-analyzer')}
              className="text-xs font-semibold text-purple-600 hover:text-purple-800"
            >
              Analyze in Resume Tool →
            </button>
          </div>

          {Array.isArray(student.resumes) && student.resumes.length > 0 ? (
            <div className="space-y-2.5">
              {student.resumes.map((res) => (
                <div key={res.id} className="p-3 bg-purple-50/50 rounded-xl border border-purple-100 flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold text-gray-900">{res.name || 'Resume Document'}</p>
                    <p className="text-[11px] text-gray-400 mt-0.5">
                      {res.created_at ? new Date(res.created_at).toLocaleDateString() : 'Recent'}
                    </p>
                  </div>
                  {res.ats_score !== null && (
                    <span className="px-2.5 py-1 bg-purple-600 text-white font-bold text-xs rounded-lg shadow-sm">
                      ATS {Math.round(res.ats_score)}%
                    </span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400">No resume uploaded yet.</p>
          )}
        </div>
      </div>

      {/* Projects & Certifications */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Projects */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          <h3 className="text-base font-bold text-gray-900 flex items-center gap-2 mb-3">
            <Briefcase className="w-5 h-5 text-emerald-600" />
            Projects ({student.projects?.length || 0})
          </h3>
          {Array.isArray(student.projects) && student.projects.length > 0 ? (
            <div className="space-y-2.5">
              {student.projects.map((proj) => (
                <div key={proj.id} className="p-3 bg-gray-50 rounded-lg border border-gray-100 text-xs">
                  <p className="font-semibold text-gray-900">{proj.name}</p>
                  {proj.description && <p className="text-gray-500 mt-1">{proj.description}</p>}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400">No projects added.</p>
          )}
        </div>

        {/* Certifications */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          <h3 className="text-base font-bold text-gray-900 flex items-center gap-2 mb-3">
            <GraduationCap className="w-5 h-5 text-amber-600" />
            Certifications ({student.certifications?.length || 0})
          </h3>
          {Array.isArray(student.certifications) && student.certifications.length > 0 ? (
            <div className="space-y-2.5">
              {student.certifications.map((cert) => (
                <div key={cert.id} className="p-3 bg-gray-50 rounded-lg border border-gray-100 text-xs">
                  <p className="font-semibold text-gray-900">{cert.name}</p>
                  <p className="text-gray-500 mt-0.5">{cert.issuing_organization || 'Organization'}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400">No certifications added.</p>
          )}
        </div>
      </div>

      {/* Applications History */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h3 className="text-base font-bold text-gray-900 flex items-center gap-2 mb-4">
          <FileText className="w-5 h-5 text-indigo-600" />
          <span>Job Applications History ({student.applications?.length || 0})</span>
        </h3>

        {!student.applications || student.applications.length === 0 ? (
          <p className="text-gray-400 text-sm text-center py-6">No applications submitted yet.</p>
        ) : (
          <div className="space-y-3">
            {student.applications.map((app) => (
              <div
                key={app.id}
                className="flex items-center justify-between p-3.5 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors"
              >
                <div>
                  <p className="font-semibold text-gray-900 text-sm">{app.job_title}</p>
                  <p className="text-xs text-gray-500 flex items-center gap-1 mt-0.5">
                    <Building2 className="w-3.5 h-3.5" />
                    <span>{app.company_name}</span>
                  </p>
                </div>
                <div className="flex items-center space-x-3">
                  <span className={`text-xs px-2.5 py-0.5 rounded-full font-semibold ${getAppStatusColor(app.status)}`}>
                    {app.status?.toUpperCase()}
                  </span>
                  <button
                    onClick={() => navigate(`/placement/jobs/${app.job_id}`)}
                    className="px-3 py-1.5 text-xs bg-white border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50 shadow-sm font-medium"
                  >
                    View Job
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

export default StudentProfile;