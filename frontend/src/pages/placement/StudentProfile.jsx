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
import { getStudent, getStudentProgression, getVerifiedOffers } from '../../services/placementService';
import StudentProgressionModal from '../../components/placement/StudentProgressionModal';
import toast from 'react-hot-toast';

const StudentProfile = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [student, setStudent] = useState(null);
  const [progression, setProgression] = useState([]);
  const [offers, setOffers] = useState([]);
  const [showProgressionModal, setShowProgressionModal] = useState(false);
  const [selectedProgressionJobId, setSelectedProgressionJobId] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchStudentData();
  }, [id]);

  const fetchStudentData = async () => {
    setIsLoading(true);
    try {
      const [studentData, progData, offersData] = await Promise.all([
        getStudent(id),
        getStudentProgression(id).catch(() => []),
        getVerifiedOffers({ student_id: id }).catch(() => []),
      ]);
      setStudent(studentData);
      setProgression(progData || []);
      setOffers(offersData || []);
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

      {/* Verified Placement Offers Section */}
      {offers.length > 0 && (
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-emerald-200 dark:border-emerald-800/60 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className="p-2 bg-emerald-50 dark:bg-emerald-950/50 rounded-lg text-emerald-600 dark:text-emerald-400">
                <Award className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-gray-900 dark:text-white">
                  Verified Placement Offers ({offers.length})
                </h3>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Official employer offers verified by Placement Officer
                </p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {offers.map((offer) => (
              <div
                key={offer.id}
                className="p-4 rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/40 space-y-3"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h4 className="font-bold text-gray-900 dark:text-white text-sm">
                      {offer.designation}
                    </h4>
                    <p className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1 mt-0.5">
                      <Building2 className="w-3.5 h-3.5" />
                      <span>{offer.company_name}</span>
                    </p>
                  </div>
                  <span
                    className={`text-[11px] px-2.5 py-0.5 rounded-full font-bold uppercase ${
                      offer.status === 'accepted'
                        ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300'
                        : offer.status === 'declined'
                        ? 'bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300'
                        : offer.status === 'rescinded'
                        ? 'bg-gray-200 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                        : 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300'
                    }`}
                  >
                    {offer.status}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2 bg-white dark:bg-gray-800 rounded-lg border border-gray-100 dark:border-gray-700">
                    <span className="text-[10px] text-gray-400 uppercase font-semibold">Compensation (CTC)</span>
                    <p className="font-bold text-emerald-600 dark:text-emerald-400 mt-0.5">
                      ₹{Number(offer.ctc).toLocaleString()} LPA
                    </p>
                  </div>
                  <div className="p-2 bg-white dark:bg-gray-800 rounded-lg border border-gray-100 dark:border-gray-700">
                    <span className="text-[10px] text-gray-400 uppercase font-semibold">Offer Date</span>
                    <p className="font-medium text-gray-700 dark:text-gray-300 mt-0.5">
                      {new Date(offer.offer_date).toLocaleDateString()}
                    </p>
                  </div>
                </div>

                {offer.rescission_reason && (
                  <div className="p-2.5 bg-rose-50 dark:bg-rose-950/30 rounded-lg border border-rose-200 dark:border-rose-800 text-xs text-rose-800 dark:text-rose-300">
                    <strong>Rescission Reason:</strong> {offer.rescission_reason}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recruitment Progression History Section */}
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-purple-50 dark:bg-purple-950/50 rounded-lg text-purple-600 dark:text-purple-400">
              <TrendingUp className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-gray-900 dark:text-white">
                Recruitment Round Progression History ({progression.length} rounds)
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Audited outcomes across recruitment drives
              </p>
            </div>
          </div>
          <button
            onClick={() => {
              setSelectedProgressionJobId(null);
              setShowProgressionModal(true);
            }}
            className="px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <TrendingUp className="w-3.5 h-3.5" />
            <span>Progression Timeline</span>
          </button>
        </div>

        {progression.length === 0 ? (
          <p className="text-gray-400 text-sm text-center py-6">No recruitment round outcomes recorded yet.</p>
        ) : (
          <div className="space-y-2.5">
            {progression.slice(0, 5).map((item, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800/40 rounded-xl border border-gray-100 dark:border-gray-800"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-gray-900 dark:text-white">
                      Round #{item.round_number}: {item.round_name}
                    </span>
                    {item.is_final && (
                      <span className="px-1.5 py-0.2 bg-purple-100 text-purple-800 dark:bg-purple-950/60 dark:text-purple-300 rounded text-[10px] font-bold">
                        FINAL
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    {item.job_title} ({item.company_name})
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`text-xs px-2.5 py-0.5 rounded-full font-bold uppercase ${
                      item.outcome === 'CLEARED'
                        ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300'
                        : item.outcome === 'SELECTED'
                        ? 'bg-purple-100 text-purple-800 dark:bg-purple-950/60 dark:text-purple-300'
                        : item.outcome === 'REJECTED'
                        ? 'bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300'
                        : item.outcome === 'ABSENT'
                        ? 'bg-gray-200 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                        : 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300'
                    }`}
                  >
                    {item.outcome}
                  </span>
                </div>
              </div>
            ))}
            {progression.length > 5 && (
              <button
                onClick={() => {
                  setSelectedProgressionJobId(null);
                  setShowProgressionModal(true);
                }}
                className="w-full py-2 text-xs font-semibold text-purple-600 hover:text-purple-800 text-center cursor-pointer"
              >
                View all {progression.length} round progression entries →
              </button>
            )}
          </div>
        )}
      </div>

      {/* Applications History */}
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800 p-6">
        <h3 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2 mb-4">
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
                className="flex items-center justify-between p-3.5 bg-gray-50 dark:bg-gray-800/40 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800/60 transition-colors"
              >
                <div>
                  <p className="font-semibold text-gray-900 dark:text-white text-sm">{app.job_title}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1 mt-0.5">
                    <Building2 className="w-3.5 h-3.5" />
                    <span>{app.company_name}</span>
                  </p>
                </div>
                <div className="flex items-center space-x-3">
                  <span className={`text-xs px-2.5 py-0.5 rounded-full font-semibold ${getAppStatusColor(app.status)}`}>
                    {app.status?.toUpperCase()}
                  </span>
                  <button
                    onClick={() => {
                      setSelectedProgressionJobId(app.job_id);
                      setShowProgressionModal(true);
                    }}
                    className="px-2.5 py-1 text-xs bg-purple-50 dark:bg-purple-950/50 text-purple-700 dark:text-purple-300 rounded-lg hover:bg-purple-100 dark:hover:bg-purple-900/50 transition-colors border border-purple-200 dark:border-purple-800 flex items-center gap-1 cursor-pointer font-medium"
                  >
                    <TrendingUp className="w-3.5 h-3.5" />
                    <span>Progression</span>
                  </button>
                  <button
                    onClick={() => navigate(`/placement/jobs/${app.job_id}`)}
                    className="px-3 py-1.5 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 shadow-xs font-medium cursor-pointer"
                  >
                    View Job
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Student Progression Modal */}
      {showProgressionModal && (
        <StudentProgressionModal
          studentId={student.id}
          studentName={student.name}
          jobPostingId={selectedProgressionJobId}
          onClose={() => {
            setShowProgressionModal(false);
            setSelectedProgressionJobId(null);
          }}
        />
      )}
    </div>
  );
};

export default StudentProfile;