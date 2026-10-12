import React, { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Mail,
  Phone,
  Award,
  Briefcase,
  CheckCircle,
  CheckCircle2,
  XCircle,
  Clock,
  FileText,
  Building2,
  TrendingUp,
  GraduationCap,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  ShieldCheck,
  Search,
  Filter,
  Layers,
  Download,
  Calendar,
  MapPin,
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
  const [error, setError] = useState(null);

  // Grouped Recruitment History State
  const [collapsedCompanies, setCollapsedCompanies] = useState({});
  const [collapsedDrives, setCollapsedDrives] = useState({});
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    fetchStudentData();
  }, [id]);

  const fetchStudentData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [studentData, progData, offersData] = await Promise.all([
        getStudent(id),
        getStudentProgression(id).catch(() => []),
        getVerifiedOffers({ student_id: id }).catch(() => []),
      ]);
      setStudent(studentData);
      setProgression(progData || []);
      setOffers(offersData || []);
    } catch (err) {
      console.error('Failed to fetch student details:', err);
      const msg = err.response?.data?.detail || 'Failed to fetch student details';
      setError(msg);
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const getStatusBadge = (statusStr) => {
    const s = statusStr?.toLowerCase();
    switch (s) {
      case 'selected':
      case 'placed':
        return { text: 'Placed / Selected', color: 'bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800' };
      case 'shortlisted':
        return { text: 'Shortlisted', color: 'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800' };
      case 'applied':
        return { text: 'Applied', color: 'bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-950/60 dark:text-blue-300 dark:border-blue-800' };
      default:
        return { text: 'Not Applied', color: 'bg-gray-100 text-gray-700 border-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-700' };
    }
  };

  const getAppStatusBadge = (status) => {
    const s = status?.toLowerCase();
    switch (s) {
      case 'shortlisted':
        return { text: 'SHORTLISTED', className: 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border-amber-200 dark:border-amber-800' };
      case 'selected':
        return { text: 'SELECTED', className: 'bg-purple-100 text-purple-800 dark:bg-purple-950/60 dark:text-purple-300 border-purple-200 dark:border-purple-800' };
      case 'rejected':
        return { text: 'NOT SELECTED', className: 'bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300 border-rose-200 dark:border-rose-800' };
      default:
        return { text: 'APPLIED', className: 'bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300 border-blue-200 dark:border-blue-800' };
    }
  };

  const getOfferStatusBadge = (status) => {
    const s = status?.toLowerCase();
    switch (s) {
      case 'accepted':
        return { text: 'Accepted', className: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-300 dark:border-emerald-700' };
      case 'declined':
        return { text: 'Declined', className: 'bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300 border-rose-300 dark:border-rose-700' };
      case 'rescinded':
        return { text: 'Rescinded', className: 'bg-gray-200 text-gray-800 dark:bg-gray-700 dark:text-gray-200 border-gray-300 dark:border-gray-600' };
      default:
        return { text: 'Offered / Pending Response', className: 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border-amber-300 dark:border-amber-700' };
    }
  };

  const toggleCompanyCollapse = (companyKey) => {
    setCollapsedCompanies((prev) => ({
      ...prev,
      [companyKey]: !prev[companyKey],
    }));
  };

  const toggleDriveCollapse = (driveKey) => {
    setCollapsedDrives((prev) => ({
      ...prev,
      [driveKey]: !prev[driveKey],
    }));
  };

  const handleExpandAll = () => {
    setCollapsedCompanies({});
    setCollapsedDrives({});
  };

  const handleCollapseAll = () => {
    const allComp = {};
    const allDrv = {};
    companyGroups.forEach((comp) => {
      allComp[comp.key] = true;
      comp.drives.forEach((drv) => {
        allDrv[drv.key] = true;
      });
    });
    setCollapsedCompanies(allComp);
    setCollapsedDrives(allDrv);
  };

  // Group applications by Company -> Recruitment Drive/Circular -> Job Role
  const companyGroups = useMemo(() => {
    if (!student?.applications || !Array.isArray(student.applications)) return [];

    const compMap = new Map();

    student.applications.forEach((rawApp) => {
      // Find matching offer from offers state if not already populated
      const matchedOffer =
        rawApp.offer ||
        offers.find(
          (o) =>
            o.application_id === rawApp.id ||
            o.job_posting_id === rawApp.job_id ||
            o.job_posting_id === rawApp.job_posting_id
        ) ||
        null;

      // Find matching round outcomes from progression state if not populated
      const matchedOutcomes =
        rawApp.round_outcomes && rawApp.round_outcomes.length > 0
          ? rawApp.round_outcomes
          : progression.filter(
              (p) =>
                p.application_id === rawApp.id ||
                p.job_posting_id === rawApp.job_id ||
                p.job_posting_id === rawApp.job_posting_id
            );

      const app = {
        ...rawApp,
        offer: matchedOffer,
        round_outcomes: matchedOutcomes,
      };

      const compName = app.company_name || 'Independent Recruiter';
      const compKey = app.company_id ? `comp_${app.company_id}` : `comp_${compName}`;

      if (!compMap.has(compKey)) {
        compMap.set(compKey, {
          key: compKey,
          id: app.company_id || null,
          name: compName,
          drives: new Map(),
        });
      }

      const compGroup = compMap.get(compKey);
      const circ = app.circular;
      const isLegacy = !circ || !circ.id;
      const driveKey = isLegacy ? `${compKey}_legacy_unlinked` : `circ_${circ.id}`;

      if (!compGroup.drives.has(driveKey)) {
        compGroup.drives.set(driveKey, {
          key: driveKey,
          isLegacy,
          circularId: circ?.id || null,
          title: isLegacy ? 'Legacy application — drive not linked' : circ.title,
          summary: circ?.summary || null,
          driveDate: circ?.drive_date || app.job_drive_date || null,
          deadline: circ?.application_deadline || app.job_deadline || null,
          status: circ?.status || null,
          branchEligibility: circ?.branch_eligibility || [],
          applications: [],
        });
      }

      const driveGroup = compGroup.drives.get(driveKey);
      driveGroup.applications.push(app);
    });

    return Array.from(compMap.values()).map((comp) => ({
      ...comp,
      drives: Array.from(comp.drives.values()),
    }));
  }, [student?.applications, offers, progression]);

  // Filtered Company Groups based on Search and Status Filter
  const filteredCompanyGroups = useMemo(() => {
    return companyGroups
      .map((comp) => {
        const matchingDrives = comp.drives
          .map((drive) => {
            const matchingApps = drive.applications.filter((app) => {
              const matchesStatus =
                statusFilter === 'all' ||
                app.status?.toLowerCase() === statusFilter.toLowerCase();

              const search = searchQuery.trim().toLowerCase();
              const matchesSearch =
                !search ||
                app.job_title?.toLowerCase().includes(search) ||
                comp.name?.toLowerCase().includes(search) ||
                drive.title?.toLowerCase().includes(search) ||
                (app.job_location && app.job_location.toLowerCase().includes(search));

              return matchesStatus && matchesSearch;
            });

            return {
              ...drive,
              applications: matchingApps,
            };
          })
          .filter((drive) => drive.applications.length > 0);

        return {
          ...comp,
          drives: matchingDrives,
        };
      })
      .filter((comp) => comp.drives.length > 0);
  }, [companyGroups, statusFilter, searchQuery]);

  if (isLoading) {
    return (
      <div className="flex flex-col justify-center items-center h-80 space-y-4">
        <div className="animate-spin rounded-full h-10 w-10 border-3 border-indigo-600 border-t-transparent"></div>
        <p className="text-sm text-gray-500 dark:text-gray-400 font-medium">Loading candidate placement profile...</p>
      </div>
    );
  }

  if (error || !student) {
    return (
      <div className="text-center py-12 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-8 max-w-lg mx-auto shadow-sm">
        <div className="w-12 h-12 rounded-full bg-rose-50 dark:bg-rose-950/60 text-rose-600 mx-auto flex items-center justify-center mb-3">
          <AlertTriangle className="w-6 h-6" />
        </div>
        <h3 className="text-lg font-bold text-gray-900 dark:text-white">Profile Unavailable</h3>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{error || 'Student record could not be loaded.'}</p>
        <div className="mt-5 flex items-center justify-center gap-3">
          <button
            onClick={() => fetchStudentData()}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-xs cursor-pointer"
          >
            Retry Loading
          </button>
          <button
            onClick={() => navigate('/placement/students')}
            className="px-4 py-2 border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-300 rounded-lg text-xs font-semibold hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
          >
            Back to Directory
          </button>
        </div>
      </div>
    );
  }

  const status = getStatusBadge(student.status || student.placement_status);
  const totalAppsCount = student.total_applications || student.applications?.length || 0;
  const uniqueCompaniesCount = companyGroups.length;
  const totalDrivesCount = companyGroups.reduce((acc, c) => acc + c.drives.length, 0);

  return (
    <div className="space-y-6 pb-12">
      {/* Back Button */}
      <button
        onClick={() => navigate('/placement/students')}
        className="flex items-center space-x-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors text-sm font-medium cursor-pointer"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Student Directory</span>
      </button>

      {/* Main Student Header Card */}
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800 p-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center space-x-4">
            <div className="w-16 h-16 rounded-2xl bg-indigo-600 text-white flex items-center justify-center text-2xl font-bold shadow-md">
              {student.name?.charAt(0).toUpperCase() || 'S'}
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{student.name || 'Student Profile'}</h1>
              <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500 dark:text-gray-400 mt-1">
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
                  <span className="bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded text-gray-600 dark:text-gray-300 font-medium">
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
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 pt-6 border-t border-gray-100 dark:border-gray-800">
          <div className="p-3 bg-gray-50 dark:bg-gray-800/40 rounded-xl text-center border border-gray-100 dark:border-gray-800">
            <p className="text-xs text-gray-500 dark:text-gray-400 uppercase font-semibold">Department / Branch</p>
            <p className="text-sm font-bold text-gray-900 dark:text-white mt-1 truncate">{student.branch || student.department || 'General'}</p>
          </div>
          <div className="p-3 bg-gray-50 dark:bg-gray-800/40 rounded-xl text-center border border-gray-100 dark:border-gray-800">
            <p className="text-xs text-gray-500 dark:text-gray-400 uppercase font-semibold">Year & Semester</p>
            <p className="text-sm font-bold text-indigo-600 dark:text-indigo-400 mt-1">
              {student.year ? `Year ${student.year}` : 'N/A'} {student.semester ? `• Sem ${student.semester}` : ''}
            </p>
          </div>
          <div className="p-3 bg-gray-50 dark:bg-gray-800/40 rounded-xl text-center border border-gray-100 dark:border-gray-800">
            <p className="text-xs text-gray-500 dark:text-gray-400 uppercase font-semibold">CGPA</p>
            <p className="text-sm font-bold text-emerald-600 dark:text-emerald-400 mt-1">{student.cgpa ? `${student.cgpa} / 10.0` : 'N/A'}</p>
          </div>
          <div className="p-3 bg-gray-50 dark:bg-gray-800/40 rounded-xl text-center border border-gray-100 dark:border-gray-800">
            <p className="text-xs text-gray-500 dark:text-gray-400 uppercase font-semibold">Applications</p>
            <p className="text-sm font-bold text-purple-600 dark:text-purple-400 mt-1">{totalAppsCount}</p>
          </div>
        </div>
      </div>

      {/* Skills & Resumes Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Skills */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 shadow-sm">
          <h3 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2 mb-3">
            <Award className="w-5 h-5 text-indigo-600" />
            Skills & Competencies
          </h3>
          {Array.isArray(student.skills) && student.skills.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {student.skills.map((skill, idx) => (
                <span key={idx} className="px-3 py-1 bg-indigo-50 dark:bg-indigo-950/50 border border-indigo-200 dark:border-indigo-800 text-indigo-700 dark:text-indigo-300 text-xs rounded-lg font-medium">
                  {typeof skill === 'string' ? skill : skill.name || ''}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400">No skills added yet.</p>
          )}
        </div>

        {/* Resumes with ATS Score */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <FileText className="w-5 h-5 text-purple-600" />
              Resumes & ATS Scores
            </h3>
            <button
              onClick={() => navigate('/placement/resume-analyzer')}
              className="text-xs font-semibold text-purple-600 hover:text-purple-800 dark:text-purple-400 dark:hover:text-purple-300 cursor-pointer"
            >
              Analyze in Resume Tool →
            </button>
          </div>

          {Array.isArray(student.resumes) && student.resumes.length > 0 ? (
            <div className="space-y-2.5">
              {student.resumes.map((res) => (
                <div key={res.id} className="p-3 bg-purple-50/50 dark:bg-purple-950/20 rounded-xl border border-purple-100 dark:border-purple-800/40 flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold text-gray-900 dark:text-white">{res.name || 'Resume Document'}</p>
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
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 shadow-sm">
          <h3 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2 mb-3">
            <Briefcase className="w-5 h-5 text-emerald-600" />
            Projects ({student.projects?.length || 0})
          </h3>
          {Array.isArray(student.projects) && student.projects.length > 0 ? (
            <div className="space-y-2.5">
              {student.projects.map((proj) => (
                <div key={proj.id} className="p-3 bg-gray-50 dark:bg-gray-800/40 rounded-lg border border-gray-100 dark:border-gray-800 text-xs">
                  <p className="font-semibold text-gray-900 dark:text-white">{proj.name}</p>
                  {proj.description && <p className="text-gray-500 dark:text-gray-400 mt-1">{proj.description}</p>}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400">No projects added.</p>
          )}
        </div>

        {/* Certifications */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 shadow-sm">
          <h3 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2 mb-3">
            <GraduationCap className="w-5 h-5 text-amber-600" />
            Certifications ({student.certifications?.length || 0})
          </h3>
          {Array.isArray(student.certifications) && student.certifications.length > 0 ? (
            <div className="space-y-2.5">
              {student.certifications.map((cert) => (
                <div key={cert.id} className="p-3 bg-gray-50 dark:bg-gray-800/40 rounded-lg border border-gray-100 dark:border-gray-800 text-xs">
                  <p className="font-semibold text-gray-900 dark:text-white">{cert.name}</p>
                  <p className="text-gray-500 dark:text-gray-400 mt-0.5">{cert.issuing_organization || cert.issuer || 'Organization'}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400">No certifications added.</p>
          )}
        </div>
      </div>

      {/* ========================================================================= */}
      {/* GROUPED RECRUITMENT HISTORY SECTION (STAGE 3.4.4)                         */}
      {/* Hierarchy: Company -> Recruitment Drive -> Job Role -> Progression -> Offer */}
      {/* ========================================================================= */}
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800 p-6 space-y-6">
        {/* Header & Controls */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-gray-100 dark:border-gray-800">
          <div>
            <h2 className="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <Layers className="w-5 h-5 text-indigo-600" />
              <span>Grouped Recruitment Drive & Application Tracking</span>
            </h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              Recruitment drives, multi-role applications, student self-reported submissions, verified round outcomes, and offer ledger
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handleExpandAll}
              className="px-2.5 py-1 text-xs font-semibold bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg cursor-pointer transition-colors"
            >
              Expand All
            </button>
            <button
              onClick={handleCollapseAll}
              className="px-2.5 py-1 text-xs font-semibold bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg cursor-pointer transition-colors"
            >
              Collapse All
            </button>
            <button
              onClick={() => {
                setSelectedProgressionJobId(null);
                setShowProgressionModal(true);
              }}
              className="px-3 py-1 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <TrendingUp className="w-3.5 h-3.5" />
              <span>All Progression Rounds ({progression.length})</span>
            </button>
          </div>
        </div>

        {/* Filter & Search Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-gray-50 dark:bg-gray-800/40 p-3 rounded-xl border border-gray-100 dark:border-gray-800">
          <div className="relative w-full sm:w-72">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search role, company, drive..."
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-gray-900 dark:text-white placeholder-gray-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Filter className="w-3.5 h-3.5 text-gray-400" />
            <span className="text-xs text-gray-500 dark:text-gray-400 font-medium">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-2.5 py-1 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-gray-700 dark:text-gray-300 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
            >
              <option value="all">All Application Statuses</option>
              <option value="applied">Applied</option>
              <option value="shortlisted">Shortlisted</option>
              <option value="selected">Selected</option>
              <option value="rejected">Not Selected / Rejected</option>
            </select>
          </div>
        </div>

        {/* Hierarchy Overview Counters */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3 rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/30">
            <span className="text-[10px] uppercase font-bold text-gray-400 tracking-wider">Companies</span>
            <p className="text-base font-extrabold text-gray-900 dark:text-white mt-0.5">{uniqueCompaniesCount}</p>
          </div>
          <div className="p-3 rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/30">
            <span className="text-[10px] uppercase font-bold text-gray-400 tracking-wider">Recruitment Drives</span>
            <p className="text-base font-extrabold text-indigo-600 dark:text-indigo-400 mt-0.5">{totalDrivesCount}</p>
          </div>
          <div className="p-3 rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/30">
            <span className="text-[10px] uppercase font-bold text-gray-400 tracking-wider">Total Applications</span>
            <p className="text-base font-extrabold text-purple-600 dark:text-purple-400 mt-0.5">{totalAppsCount}</p>
          </div>
          <div className="p-3 rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/30">
            <span className="text-[10px] uppercase font-bold text-gray-400 tracking-wider">Verified Offers</span>
            <p className="text-base font-extrabold text-emerald-600 dark:text-emerald-400 mt-0.5">{offers.length}</p>
          </div>
        </div>

        {/* Grouped Applications Tree */}
        {filteredCompanyGroups.length === 0 ? (
          <div className="text-center py-12 border-2 border-dashed border-gray-200 dark:border-gray-800 rounded-xl p-6">
            <Briefcase className="w-10 h-10 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
            <h4 className="text-sm font-bold text-gray-700 dark:text-gray-300">No matching applications found</h4>
            <p className="text-xs text-gray-400 mt-1">
              {totalAppsCount === 0
                ? 'This student has not submitted any job applications yet.'
                : 'No recruitment records match the selected status or search filter.'}
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {filteredCompanyGroups.map((comp) => {
              const isCompCollapsed = !!collapsedCompanies[comp.key];
              const totalCompApps = comp.drives.reduce((sum, d) => sum + d.applications.length, 0);

              return (
                <div
                  key={comp.key}
                  className="rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden shadow-xs transition-shadow hover:shadow-sm"
                >
                  {/* Company Level Header */}
                  <div
                    onClick={() => toggleCompanyCollapse(comp.key)}
                    className="p-4 bg-gray-50 dark:bg-gray-800/70 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between cursor-pointer select-none"
                  >
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-400">
                        <Building2 className="w-5 h-5" />
                      </div>
                      <div>
                        <h3 className="font-bold text-gray-900 dark:text-white text-base flex items-center gap-2">
                          <span>{comp.name}</span>
                          <span className="text-xs font-normal text-gray-500 dark:text-gray-400">
                            ({comp.drives.length} {comp.drives.length === 1 ? 'drive' : 'drives'} • {totalCompApps} {totalCompApps === 1 ? 'application' : 'applications'})
                          </span>
                        </h3>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500 dark:text-gray-400 font-medium">
                        {isCompCollapsed ? 'Show Details' : 'Hide Details'}
                      </span>
                      {isCompCollapsed ? (
                        <ChevronRight className="w-4 h-4 text-gray-400" />
                      ) : (
                        <ChevronDown className="w-4 h-4 text-gray-400" />
                      )}
                    </div>
                  </div>

                  {/* Drives inside Company */}
                  {!isCompCollapsed && (
                    <div className="p-4 space-y-4 bg-white dark:bg-gray-900">
                      {comp.drives.map((drive) => {
                        const isDriveCollapsed = !!collapsedDrives[drive.key];

                        return (
                          <div
                            key={drive.key}
                            className={`rounded-xl border ${
                              drive.isLegacy
                                ? 'border-amber-200 dark:border-amber-900/50 bg-amber-50/20 dark:bg-amber-950/10'
                                : 'border-indigo-100 dark:border-indigo-950/50 bg-indigo-50/20 dark:bg-indigo-950/10'
                            } overflow-hidden`}
                          >
                            {/* Drive / Circular Level Header */}
                            <div
                              onClick={() => toggleDriveCollapse(drive.key)}
                              className="p-3.5 bg-gray-50/80 dark:bg-gray-800/40 border-b border-gray-200/70 dark:border-gray-800 flex flex-col sm:flex-row sm:items-center justify-between gap-2 cursor-pointer select-none"
                            >
                              <div className="flex items-center gap-2.5">
                                <div
                                  className={`p-1.5 rounded-md ${
                                    drive.isLegacy
                                      ? 'bg-amber-100 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400'
                                      : 'bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-400'
                                  }`}
                                >
                                  <Layers className="w-4 h-4" />
                                </div>

                                <div>
                                  <div className="flex flex-wrap items-center gap-2">
                                    <h4 className="font-semibold text-gray-900 dark:text-white text-sm">
                                      {drive.title}
                                    </h4>

                                    {drive.isLegacy ? (
                                      <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                                        Legacy Application — Drive Not Linked
                                      </span>
                                    ) : (
                                      <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-indigo-100 dark:bg-indigo-950/60 text-indigo-800 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                                        Recruitment Circular #{drive.circularId}
                                      </span>
                                    )}

                                    {drive.status && (
                                      <span className="px-1.5 py-0.2 rounded text-[10px] font-semibold uppercase bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400">
                                        {drive.status}
                                      </span>
                                    )}
                                  </div>

                                  <div className="flex flex-wrap items-center gap-3 text-[11px] text-gray-500 dark:text-gray-400 mt-1">
                                    {drive.driveDate && (
                                      <span className="flex items-center gap-1">
                                        <Calendar className="w-3 h-3 text-gray-400" />
                                        Drive: {new Date(drive.driveDate).toLocaleDateString()}
                                      </span>
                                    )}
                                    {drive.deadline && (
                                      <span className="flex items-center gap-1">
                                        <Clock className="w-3 h-3 text-gray-400" />
                                        Deadline: {new Date(drive.deadline).toLocaleDateString()}
                                      </span>
                                    )}
                                    <span>
                                      • {drive.applications.length} {drive.applications.length === 1 ? 'Job Role Applied' : 'Job Roles Applied'}
                                    </span>
                                  </div>
                                </div>
                              </div>

                              <div className="flex items-center gap-3 self-end sm:self-center">
                                {!drive.isLegacy && drive.circularId && (
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      navigate(`/placement/circulars/${drive.circularId}`);
                                    }}
                                    className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 flex items-center gap-1 cursor-pointer"
                                  >
                                    <span>Drive Workspace</span>
                                    <ExternalLink className="w-3 h-3" />
                                  </button>
                                )}

                                {isDriveCollapsed ? (
                                  <ChevronRight className="w-4 h-4 text-gray-400" />
                                ) : (
                                  <ChevronDown className="w-4 h-4 text-gray-400" />
                                )}
                              </div>
                            </div>

                            {/* Applications inside Drive */}
                            {!isDriveCollapsed && (
                              <div className="p-3.5 space-y-4">
                                {drive.applications.map((app) => {
                                  const appStatus = getAppStatusBadge(app.status);
                                  const offerStatus = app.offer ? getOfferStatusBadge(app.offer.acceptance_status) : null;
                                  const hasExternalConfirmed = !!app.external_applied_at;
                                  const hasPortalUrl = !!app.application_url;
                                  const roundOutcomes = app.round_outcomes || [];

                                  return (
                                    <div
                                      key={app.id}
                                      className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 space-y-4 shadow-xs"
                                    >
                                      {/* Job Role Banner */}
                                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-gray-100 dark:border-gray-800">
                                        <div>
                                          <div className="flex flex-wrap items-center gap-2">
                                            <h5 className="font-bold text-gray-900 dark:text-white text-sm">
                                              {app.job_title}
                                            </h5>
                                            <span
                                              className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${appStatus.className}`}
                                            >
                                              {appStatus.text}
                                            </span>
                                            {app.match_percentage !== null && app.match_percentage !== undefined && (
                                              <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                                                Match {Math.round(app.match_percentage)}%
                                              </span>
                                            )}
                                          </div>

                                          <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500 dark:text-gray-400 mt-1">
                                            {app.job_location && (
                                              <span className="flex items-center gap-1">
                                                <MapPin className="w-3 h-3 text-gray-400" />
                                                {app.job_location}
                                              </span>
                                            )}
                                            {app.salary_range && (
                                              <span>• CTC Range: {app.salary_range}</span>
                                            )}
                                            {app.applied_at && (
                                              <span>
                                                • Applied on: {new Date(app.applied_at).toLocaleDateString()}
                                              </span>
                                            )}
                                            {app.cgpa_criteria && (
                                              <span className="text-gray-600 dark:text-gray-400">
                                                • Criteria: CGPA ≥ {app.cgpa_criteria}
                                              </span>
                                            )}
                                          </div>
                                        </div>

                                        <div className="flex items-center gap-2 self-end sm:self-center">
                                          <button
                                            onClick={() => {
                                              setSelectedProgressionJobId(app.job_id || app.job_posting_id);
                                              setShowProgressionModal(true);
                                            }}
                                            className="px-2.5 py-1 text-xs bg-purple-50 dark:bg-purple-950/50 text-purple-700 dark:text-purple-300 rounded-lg hover:bg-purple-100 dark:hover:bg-purple-900/50 transition-colors border border-purple-200 dark:border-purple-800 flex items-center gap-1 cursor-pointer font-medium"
                                          >
                                            <TrendingUp className="w-3.5 h-3.5" />
                                            <span>Rounds Audit</span>
                                          </button>
                                          {app.job_id && (
                                            <button
                                              onClick={() => navigate(`/placement/jobs/${app.job_id}`)}
                                              className="px-2.5 py-1 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 font-medium cursor-pointer"
                                            >
                                              Job Posting
                                            </button>
                                          )}
                                        </div>
                                      </div>

                                      {/* Application Evidence Hierarchy Grid */}
                                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                        {/* Column 1: External Application Evidence */}
                                        <div className="p-3 rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/20 space-y-2">
                                          <div className="flex items-center justify-between">
                                            <span className="text-[10px] uppercase font-bold text-gray-400 tracking-wider">
                                              1. External Application
                                            </span>
                                            {hasExternalConfirmed ? (
                                              <span className="flex items-center gap-1 text-[11px] font-bold text-emerald-600 dark:text-emerald-400">
                                                <CheckCircle className="w-3.5 h-3.5" />
                                                Reported
                                              </span>
                                            ) : hasPortalUrl ? (
                                              <span className="flex items-center gap-1 text-[11px] font-semibold text-amber-600 dark:text-amber-400">
                                                <Clock className="w-3.5 h-3.5" />
                                                Unconfirmed
                                              </span>
                                            ) : (
                                              <span className="text-[11px] font-medium text-gray-400">
                                                Internal
                                              </span>
                                            )}
                                          </div>

                                          {hasExternalConfirmed ? (
                                            <div className="p-2.5 bg-emerald-50 dark:bg-emerald-950/40 rounded-lg border border-emerald-200 dark:border-emerald-800/60 text-xs text-emerald-900 dark:text-emerald-200 space-y-1">
                                              <p className="font-bold flex items-center gap-1">
                                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                                                Student reported applying on company portal
                                              </p>
                                              <p className="text-[11px] text-emerald-700 dark:text-emerald-300">
                                                Confirmed: {new Date(app.external_applied_at).toLocaleString()}
                                              </p>
                                              <p className="text-[10px] text-emerald-600/80 dark:text-emerald-400/80 italic">
                                                *Student self-reported submission (not employer-verified)
                                              </p>
                                            </div>
                                          ) : hasPortalUrl ? (
                                            <div className="p-2.5 bg-amber-50 dark:bg-amber-950/40 rounded-lg border border-amber-200 dark:border-amber-800/60 text-xs text-amber-900 dark:text-amber-200 space-y-1.5">
                                              <p className="font-bold flex items-center gap-1 text-amber-800 dark:text-amber-300">
                                                <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                                                External application not confirmed
                                              </p>
                                              <p className="text-[11px] text-amber-700 dark:text-amber-300">
                                                Official portal link provided but student has not yet confirmed submission.
                                              </p>
                                              <a
                                                href={app.application_url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="inline-flex items-center gap-1 text-[11px] font-semibold text-indigo-600 dark:text-indigo-400 hover:underline"
                                              >
                                                <span>Visit Company Portal</span>
                                                <ExternalLink className="w-3 h-3" />
                                              </a>
                                            </div>
                                          ) : (
                                            <div className="p-2.5 bg-gray-100 dark:bg-gray-800 rounded-lg text-xs text-gray-600 dark:text-gray-400 space-y-1">
                                              <p className="font-medium text-gray-700 dark:text-gray-300">
                                                Direct Campus Drive Submission
                                              </p>
                                              <p className="text-[11px] text-gray-500">
                                                Managed internally via Placement Cell circular.
                                              </p>
                                            </div>
                                          )}
                                        </div>

                                        {/* Column 2: Round Progression Evidence */}
                                        <div className="p-3 rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/20 space-y-2">
                                          <div className="flex items-center justify-between">
                                            <span className="text-[10px] uppercase font-bold text-gray-400 tracking-wider">
                                              2. Round Progression
                                            </span>
                                            <span className="inline-flex items-center gap-1 text-[10px] font-bold text-purple-700 dark:text-purple-300 bg-purple-100 dark:bg-purple-950/60 px-1.5 py-0.5 rounded border border-purple-200 dark:border-purple-800">
                                              <ShieldCheck className="w-3 h-3" />
                                              Verified by Placement Cell
                                            </span>
                                          </div>

                                          {roundOutcomes.length === 0 ? (
                                            <div className="p-2.5 bg-gray-50 dark:bg-gray-800/50 rounded-lg text-xs text-gray-400 dark:text-gray-500 text-center py-4">
                                              No round progression outcomes verified yet for this role.
                                            </div>
                                          ) : (
                                            <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
                                              {roundOutcomes.map((ro, rIdx) => (
                                                <div
                                                  key={ro.id || rIdx}
                                                  className="p-2 bg-white dark:bg-gray-800 rounded border border-gray-100 dark:border-gray-700 flex items-center justify-between text-xs"
                                                >
                                                  <div>
                                                    <p className="font-semibold text-gray-900 dark:text-white text-[11px]">
                                                      {ro.round_name || `Round #${ro.round_number || rIdx + 1}`}
                                                      {ro.is_final && (
                                                        <span className="ml-1 text-[9px] px-1 bg-purple-100 text-purple-800 rounded font-bold">
                                                          FINAL
                                                        </span>
                                                      )}
                                                    </p>
                                                    {ro.confirmed_at && (
                                                      <p className="text-[10px] text-gray-400">
                                                        {new Date(ro.confirmed_at).toLocaleDateString()}
                                                      </p>
                                                    )}
                                                  </div>
                                                  <span
                                                    className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                                                      ro.outcome === 'CLEARED'
                                                        ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300'
                                                        : ro.outcome === 'SELECTED'
                                                        ? 'bg-purple-100 text-purple-800 dark:bg-purple-950/60 dark:text-purple-300'
                                                        : ro.outcome === 'REJECTED'
                                                        ? 'bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300'
                                                        : 'bg-gray-200 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                                                    }`}
                                                  >
                                                    {ro.outcome}
                                                  </span>
                                                </div>
                                              ))}
                                            </div>
                                          )}
                                        </div>

                                        {/* Column 3: Verified Offer */}
                                        <div className="p-3 rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/20 space-y-2">
                                          <div className="flex items-center justify-between">
                                            <span className="text-[10px] uppercase font-bold text-gray-400 tracking-wider">
                                              3. Verified Placement Offer
                                            </span>
                                            {app.offer && (
                                              <span
                                                className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase border ${offerStatus.className}`}
                                              >
                                                {offerStatus.text}
                                              </span>
                                            )}
                                          </div>

                                          {app.offer ? (
                                            <div className="p-2.5 bg-emerald-50/60 dark:bg-emerald-950/30 rounded-lg border border-emerald-200 dark:border-emerald-800 text-xs space-y-2">
                                              <div>
                                                <h6 className="font-bold text-gray-900 dark:text-white text-xs">
                                                  {app.offer.designation || app.job_title}
                                                </h6>
                                                <p className="text-emerald-700 dark:text-emerald-400 font-extrabold text-sm mt-0.5">
                                                  ₹{app.offer.ctc_lpa || app.offer.ctc} LPA
                                                </p>
                                              </div>

                                              <div className="text-[11px] text-gray-600 dark:text-gray-400 space-y-0.5">
                                                {app.offer.offer_date && (
                                                  <p>Offered: {new Date(app.offer.offer_date).toLocaleDateString()}</p>
                                                )}
                                                {app.offer.response_date && (
                                                  <p>Student Response: {new Date(app.offer.response_date).toLocaleDateString()}</p>
                                                )}
                                              </div>

                                              {app.offer.rescission_reason && (
                                                <div className="p-1.5 rounded bg-rose-50 dark:bg-rose-950/60 border border-rose-200 dark:border-rose-800 text-[11px] text-rose-800 dark:text-rose-300">
                                                  <strong>Rescission Reason:</strong> {app.offer.rescission_reason}
                                                </div>
                                              )}

                                              {app.offer.offer_letter_file_id && (
                                                <a
                                                  href={`/api/v1/files/${app.offer.offer_letter_file_id}/download`}
                                                  target="_blank"
                                                  rel="noopener noreferrer"
                                                  className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-white dark:bg-gray-800 border border-emerald-300 dark:border-emerald-700 rounded-lg text-emerald-800 dark:text-emerald-300 text-[11px] font-semibold hover:bg-emerald-50 dark:hover:bg-emerald-900/40 transition-colors shadow-xs"
                                                >
                                                  <Download className="w-3 h-3" />
                                                  <span>Official Offer Letter</span>
                                                </a>
                                              )}
                                            </div>
                                          ) : (
                                            <div className="p-2.5 bg-gray-50 dark:bg-gray-800/40 rounded-lg border border-gray-100 dark:border-gray-800 text-xs text-gray-500 dark:text-gray-400 space-y-1">
                                              <p className="font-semibold text-gray-700 dark:text-gray-300">
                                                No verified offer recorded
                                              </p>
                                              <p className="text-[10px] text-gray-400">
                                                *Round clearance or selection does not constitute a formal verified placement offer.
                                              </p>
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Student Progression Modal */}
      {showProgressionModal && (
        <StudentProgressionModal
          studentId={student.id}
          studentName={student.name}
          studentEmail={student.email}
          jobId={selectedProgressionJobId}
          onClose={() => {
            setShowProgressionModal(false);
            setSelectedProgressionJobId(null);
            fetchStudentData();
          }}
        />
      )}
    </div>
  );
};

export default StudentProfile;