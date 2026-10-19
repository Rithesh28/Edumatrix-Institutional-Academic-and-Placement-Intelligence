import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft,
  Building2,
  Calendar,
  Clock,
  Briefcase,
  Paperclip,
  Eye,
  Download,
  Edit2,
  Archive,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  ExternalLink,
  GraduationCap,
  X,
  Users,
  Layers,
  Award,
  FileSpreadsheet,
  BarChart3,
  Search,
  Filter,
  CheckCircle,
  TrendingUp,
  Info,
  ChevronRight,
  RefreshCw,
  Upload,
  UploadCloud,
  FileCheck,
  Check,
  CheckCheck,
  FileText,
  AlertTriangle,
  ShieldCheck,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import {
  getJobRounds,
  getCircularAttachmentDownloadUrl,
  getCircularAttachmentPreviewUrl,
} from '../../services/placementService';
import RecruitmentRoundsTab from '../../components/placement/RecruitmentRoundsTab';
import VerifiedOffersTab from '../../components/placement/VerifiedOffersTab';
import StudentProgressionModal from '../../components/placement/StudentProgressionModal';
import toast from 'react-hot-toast';

const WORKSPACE_TABS = [
  { id: 'overview', label: 'Overview & Roles', icon: Briefcase },
  { id: 'applicants', label: 'Applicants & Matching', icon: Users },
  { id: 'rounds', label: 'Rounds & Progression', icon: Layers },
  { id: 'results', label: 'Results & Review', icon: FileSpreadsheet },
  { id: 'offers', label: 'Verified Offers', icon: Award },
  { id: 'reports', label: 'Drive Placement Report', icon: BarChart3 },
];

const CircularDetails = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get('tab') || 'overview';

  const {
    selectedCircular,
    isCircularsLoading,
    fetchCircular,
    publishCircular,
    archiveCircular,
    applications,
    fetchApplications,
    matchStudents,
    jobRounds,
    fetchJobRounds,
    verifiedOffers,
    fetchVerifiedOffers,
    resultBatches,
    isResultsLoading,
    fetchResultBatches,
    uploadResultDocument,
    driveReport,
    isDriveReportLoading,
    fetchCircularDriveReport,
  } = usePlacementStore();

  const [previewFile, setPreviewFile] = useState(null);
  const [selectedRoleIndex, setSelectedRoleIndex] = useState(0);

  // Publish review modal state
  const [publishModal, setPublishModal] = useState({
    isOpen: false,
    isPublishing: false,
    confirmNoSkills: false,
    errorMessage: null,
    showSkillBypass: false,
  });

  // Applicants & Matching state
  const [matchData, setMatchData] = useState(null);
  const [isMatching, setIsMatching] = useState(false);
  const [applicantSearch, setApplicantSearch] = useState('');
  const [applicantRoleFilter, setApplicantRoleFilter] = useState('all');
  const [applicantBranchFilter, setApplicantBranchFilter] = useState('all');
  const [applicantStatusFilter, setApplicantStatusFilter] = useState('all');
  const [applicantConfirmFilter, setApplicantConfirmFilter] = useState('all');
  const [applicantSort, setApplicantSort] = useState('date_desc');
  const [progressionModalStudent, setProgressionModalStudent] = useState(null);

  // Results tab state & upload modal
  const [batchSearch, setBatchSearch] = useState('');
  const [batchStatusFilter, setBatchStatusFilter] = useState('all');
  const [showResultUploadModal, setShowResultUploadModal] = useState(false);
  const [resultUploadJobId, setResultUploadJobId] = useState('');
  const [resultUploadRoundId, setResultUploadRoundId] = useState('');
  const [resultUploadRoundName, setResultUploadRoundName] = useState('');
  const [resultUploadRoundType, setResultUploadRoundType] = useState('assessment');
  const [resultUploadIsFinal, setResultUploadIsFinal] = useState(false);
  const [resultUploadFile, setResultUploadFile] = useState(null);
  const [isResultUploading, setIsResultUploading] = useState(false);
  const [availableJobRounds, setAvailableJobRounds] = useState([]);

  useEffect(() => {
    fetchCircular(id).catch(() => {
      toast.error('Failed to load circular details.');
    });
  }, [id, fetchCircular]);

  const circ = selectedCircular;
  const linkedJobs = useMemo(() => circ?.linked_jobs || [], [circ]);
  const activeJob = linkedJobs[selectedRoleIndex] || linkedJobs[0] || null;
  const activeJobPostingId = activeJob?.job_posting_id || activeJob?.id || null;

  // Fetch available recruitment rounds when role is selected in results upload modal
  useEffect(() => {
    if (resultUploadJobId) {
      getJobRounds(resultUploadJobId)
        .then((rounds) => setAvailableJobRounds(rounds || []))
        .catch(() => setAvailableJobRounds([]));
    } else {
      setAvailableJobRounds([]);
      setResultUploadRoundId('');
    }
  }, [resultUploadJobId]);

  // Refresh tab-specific data on tab switch or role switch
  useEffect(() => {
    if (!circ) return;
    if (activeTab === 'applicants') {
      fetchApplications({ circular_id: id }).catch(() => {});
    } else if (activeTab === 'rounds' && activeJobPostingId) {
      fetchJobRounds(activeJobPostingId).catch(() => {});
    } else if (activeTab === 'offers' && activeJobPostingId) {
      fetchVerifiedOffers({ job_posting_id: activeJobPostingId }).catch(() => {});
    } else if (activeTab === 'results') {
      fetchResultBatches({ circular_id: id }).catch(() => {});
    } else if (activeTab === 'reports') {
      fetchCircularDriveReport(id).catch(() => {});
    }
  }, [activeTab, activeJobPostingId, id, circ]);

  const handleTabChange = (tabId) => {
    setSearchParams({ tab: tabId });
  };

  const handleOpenPublish = () => {
    if (!circ.linked_jobs || circ.linked_jobs.length === 0) {
      toast.error('At least one linked job role is required to publish this circular.');
      return;
    }
    setPublishModal({
      isOpen: true,
      isPublishing: false,
      confirmNoSkills: false,
      errorMessage: null,
      showSkillBypass: false,
    });
  };

  const handleConfirmPublish = async () => {
    setPublishModal((prev) => ({ ...prev, isPublishing: true, errorMessage: null }));
    try {
      const response = await publishCircular(id, {
        confirm_no_skills: publishModal.confirmNoSkills,
      });
      toast.success(response.message || 'Recruitment circular published successfully!');
      setPublishModal({
        isOpen: false,
        isPublishing: false,
        confirmNoSkills: false,
        errorMessage: null,
        showSkillBypass: false,
      });
      fetchCircular(id);
    } catch (error) {
      const msg = error.response?.data?.detail || error.message || 'Failed to publish circular.';
      if (msg.includes('confirm_no_skills=True')) {
        setPublishModal((prev) => ({
          ...prev,
          isPublishing: false,
          errorMessage: msg,
          showSkillBypass: true,
        }));
      } else {
        toast.error(msg);
        setPublishModal((prev) => ({ ...prev, isPublishing: false, errorMessage: msg }));
      }
    }
  };

  const handleArchive = async () => {
    if (window.confirm('Are you sure you want to archive this recruitment circular?')) {
      try {
        await archiveCircular(id);
        toast.success('Circular archived successfully.');
        fetchCircular(id);
      } catch (err) {
        toast.error('Failed to archive circular.');
      }
    }
  };

  const handleMatchCandidates = async () => {
    if (!activeJobPostingId) return;
    setIsMatching(true);
    try {
      const result = await matchStudents({ job_posting_id: activeJobPostingId });
      setMatchData(result);
      toast.success(
        `Skill matching complete: evaluated ${
          (result.all_candidates || result.eligible_students || []).length
        } candidates (${result.total_eligible || 0} eligible)`
      );
    } catch (error) {
      toast.error(error.response?.data?.detail || error.message || 'Failed to match candidates');
    } finally {
      setIsMatching(false);
    }
  };

  // Unique branches extracted from aggregated applications
  const uniqueBranches = useMemo(() => {
    const branches = new Set();
    applications.forEach((app) => {
      const b = app.student_branch || app.branch;
      if (b) branches.add(b);
    });
    return Array.from(branches).sort();
  }, [applications]);

  // Aggregated & sorted applications across all linked roles in this drive
  const sortedAndFilteredApplications = useMemo(() => {
    let list = applications.filter((app) => {
      const matchesSearch =
        !applicantSearch ||
        app.student_name?.toLowerCase().includes(applicantSearch.toLowerCase()) ||
        app.student_email?.toLowerCase().includes(applicantSearch.toLowerCase()) ||
        (app.student_branch || app.branch || '').toLowerCase().includes(applicantSearch.toLowerCase()) ||
        (app.job_title || '').toLowerCase().includes(applicantSearch.toLowerCase());

      const matchesRole =
        applicantRoleFilter === 'all' ||
        String(app.job_posting_id) === String(applicantRoleFilter);

      const matchesBranch =
        applicantBranchFilter === 'all' ||
        (app.student_branch || app.branch) === applicantBranchFilter;

      const matchesStatus =
        applicantStatusFilter === 'all' ||
        app.status?.toLowerCase() === applicantStatusFilter.toLowerCase();

      const matchesConfirm =
        applicantConfirmFilter === 'all' ||
        (applicantConfirmFilter === 'confirmed' && (app.is_external_confirmed || app.external_applied_at)) ||
        (applicantConfirmFilter === 'pending' && !(app.is_external_confirmed || app.external_applied_at));

      return matchesSearch && matchesRole && matchesBranch && matchesStatus && matchesConfirm;
    });

    list.sort((a, b) => {
      if (applicantSort === 'match_desc') {
        return (b.match_percentage || 0) - (a.match_percentage || 0);
      }
      if (applicantSort === 'cgpa_desc') {
        return (b.student_cgpa || b.cgpa || 0) - (a.student_cgpa || a.cgpa || 0);
      }
      if (applicantSort === 'name_asc') {
        return (a.student_name || '').localeCompare(b.student_name || '');
      }
      if (applicantSort === 'date_asc') {
        return new Date(a.applied_at || 0) - new Date(b.applied_at || 0);
      }
      return new Date(b.applied_at || 0) - new Date(a.applied_at || 0);
    });

    return list;
  }, [
    applications,
    applicantSearch,
    applicantRoleFilter,
    applicantBranchFilter,
    applicantStatusFilter,
    applicantConfirmFilter,
    applicantSort,
  ]);

  // Filtered result batches for this recruitment drive
  const filteredBatches = useMemo(() => {
    return resultBatches.filter((b) => {
      const matchesSearch =
        !batchSearch ||
        b.round_name?.toLowerCase().includes(batchSearch.toLowerCase()) ||
        b.filename?.toLowerCase().includes(batchSearch.toLowerCase()) ||
        b.file_name?.toLowerCase().includes(batchSearch.toLowerCase()) ||
        b.job_title?.toLowerCase().includes(batchSearch.toLowerCase());

      const matchesStatus =
        batchStatusFilter === 'all' ||
        b.status?.toLowerCase() === batchStatusFilter.toLowerCase();

      return matchesSearch && matchesStatus;
    });
  }, [resultBatches, batchSearch, batchStatusFilter]);

  const handleOpenResultUpload = () => {
    setResultUploadJobId(
      activeJobPostingId
        ? String(activeJobPostingId)
        : linkedJobs[0]?.job_posting_id
        ? String(linkedJobs[0].job_posting_id)
        : ''
    );
    setResultUploadRoundId('');
    setResultUploadRoundName('');
    setResultUploadRoundType('assessment');
    setResultUploadIsFinal(false);
    setResultUploadFile(null);
    setShowResultUploadModal(true);
  };

  const handleSelectUploadRound = (roundId) => {
    setResultUploadRoundId(roundId);
    if (!roundId) return;
    const r = availableJobRounds.find((round) => String(round.id) === String(roundId));
    if (r) {
      setResultUploadRoundName(r.round_name || '');
      setResultUploadRoundType(r.round_type || 'assessment');
      setResultUploadIsFinal(Boolean(r.is_final));
    }
  };

  const handleSubmitResultUpload = async (e) => {
    e.preventDefault();
    if (!resultUploadFile) {
      toast.error('Please select a result document to upload (.csv, .xlsx, .xls, .pdf).');
      return;
    }
    if (!resultUploadRoundName.trim()) {
      toast.error('Round name is required.');
      return;
    }

    setIsResultUploading(true);
    try {
      const formData = new FormData();
      formData.append('company_id', circ.company_id);
      formData.append('circular_id', circ.id);
      formData.append('round_name', resultUploadRoundName.trim());
      formData.append('round_type', resultUploadRoundType);
      formData.append('is_final_round', resultUploadIsFinal ? 'true' : 'false');
      if (resultUploadJobId) {
        formData.append('job_posting_id', resultUploadJobId);
      }
      if (resultUploadRoundId) {
        formData.append('round_id', resultUploadRoundId);
      }
      formData.append('file', resultUploadFile);

      await uploadResultDocument(formData);
      toast.success('Result document parsed and batch created successfully!');
      setShowResultUploadModal(false);
      fetchResultBatches({ circular_id: id });
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || 'Failed to upload result document.');
    } finally {
      setIsResultUploading(false);
    }
  };

  if (isCircularsLoading && !selectedCircular) {
    return (
      <div className="p-12 text-center text-gray-500 dark:text-gray-400">
        <div className="animate-spin w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full mx-auto mb-3" />
        <p>Loading Recruitment Drive Workspace...</p>
      </div>
    );
  }

  if (!selectedCircular) {
    return (
      <div className="p-8 text-center bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 max-w-xl mx-auto mt-8">
        <p className="text-gray-500">Recruitment drive circular not found.</p>
        <button
          onClick={() => navigate('/placement/circulars')}
          className="mt-3 text-indigo-600 dark:text-indigo-400 text-sm font-semibold cursor-pointer"
        >
          &larr; Back to Circulars
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-20">
      {/* Workspace Top Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/placement/circulars')}
            className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors cursor-pointer"
            title="Back to Circulars list"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{circ.title}</h1>
              <span
                className={`px-2.5 py-1 text-xs font-semibold rounded-full uppercase tracking-wider ${
                  circ.status === 'published'
                    ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300'
                    : circ.status === 'draft'
                    ? 'bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300'
                    : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
                }`}
              >
                {circ.status}
              </span>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 flex items-center gap-2 flex-wrap">
              <span className="font-semibold text-gray-700 dark:text-gray-300">{circ.company_name}</span>
              {circ.created_at && (
                <span>• Created: {new Date(circ.created_at).toLocaleDateString()}</span>
              )}
              {circ.published_at && (
                <span>• Published: {new Date(circ.published_at).toLocaleDateString()}</span>
              )}
            </p>
          </div>
        </div>

        {/* Header Action Buttons */}
        <div className="flex items-center gap-2">
          {circ.status === 'draft' && (
            <>
              <button
                onClick={() => navigate(`/placement/circulars/${circ.id}/edit`)}
                className="px-3.5 py-2 text-xs font-semibold bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 rounded-lg flex items-center gap-1.5 cursor-pointer transition-colors"
              >
                <Edit2 className="w-3.5 h-3.5" />
                <span>Edit Draft</span>
              </button>
              <button
                onClick={handleOpenPublish}
                className="px-4 py-2 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg flex items-center gap-1.5 cursor-pointer transition-colors shadow-sm"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Publish Circular</span>
              </button>
            </>
          )}

          {circ.status === 'published' && (
            <button
              onClick={handleArchive}
              className="px-3.5 py-2 text-xs font-semibold bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 rounded-lg flex items-center gap-1.5 cursor-pointer transition-colors"
            >
              <Archive className="w-3.5 h-3.5" />
              <span>Archive</span>
            </button>
          )}
        </div>
      </div>

      {/* Workspace Navigation Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 rounded-xl px-2 shadow-sm">
        <div className="flex items-center space-x-1 sm:space-x-2 overflow-x-auto py-1">
          {WORKSPACE_TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => handleTabChange(tab.id)}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-all cursor-pointer whitespace-nowrap ${
                  isActive
                    ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 font-semibold'
                    : 'border-transparent text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200 hover:border-gray-300 dark:hover:border-gray-700'
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span>{tab.label}</span>
                {tab.id === 'overview' && linkedJobs.length > 0 && (
                  <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
                    {linkedJobs.length}
                  </span>
                )}
                {tab.id === 'applicants' && applications.length > 0 && (
                  <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400">
                    {applications.length}
                  </span>
                )}
                {tab.id === 'rounds' && jobRounds.length > 0 && (
                  <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-purple-50 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400">
                    {jobRounds.length}
                  </span>
                )}
                {tab.id === 'results' && resultBatches.length > 0 && (
                  <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400">
                    {resultBatches.length}
                  </span>
                )}
                {tab.id === 'offers' && verifiedOffers.length > 0 && (
                  <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
                    {verifiedOffers.length}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: OVERVIEW & ROLES                                                  */}
      {/* ========================================================================= */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Main Drive Details Card */}
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 space-y-6 shadow-sm">
            {/* Drive Key Metrics */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pb-4 border-b border-gray-100 dark:border-gray-800 text-xs">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-indigo-50 dark:bg-indigo-950/50 rounded-lg text-indigo-600 dark:text-indigo-400">
                  <Calendar className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-gray-400 font-medium">Drive Date</span>
                  <p className="font-semibold text-gray-900 dark:text-white mt-0.5">
                    {circ.drive_date ? new Date(circ.drive_date).toLocaleString() : 'Not specified'}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-amber-50 dark:bg-amber-950/50 rounded-lg text-amber-600 dark:text-amber-400">
                  <Clock className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-gray-400 font-medium">Application Deadline</span>
                  <p className="font-semibold text-gray-900 dark:text-white mt-0.5">
                    {circ.application_deadline
                      ? new Date(circ.application_deadline).toLocaleString()
                      : 'Not specified'}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-blue-50 dark:bg-blue-950/50 rounded-lg text-blue-600 dark:text-blue-400">
                  <Building2 className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-gray-400 font-medium">Recruiting Company</span>
                  <p className="font-semibold text-gray-900 dark:text-white mt-0.5">
                    {circ.company_name}
                  </p>
                </div>
              </div>
            </div>

            {/* Branch Eligibility */}
            {circ.branch_eligibility && circ.branch_eligibility.length > 0 && (
              <div className="space-y-1.5">
                <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                  <GraduationCap className="w-4 h-4 text-indigo-500" />
                  <span>Eligible Engineering Branches</span>
                </h3>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {circ.branch_eligibility.map((b, i) => (
                    <span
                      key={i}
                      className="px-2.5 py-1 bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 rounded-md text-xs font-medium"
                    >
                      {b}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Summary */}
            {circ.summary && (
              <div className="space-y-1.5">
                <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">
                  Drive Overview
                </h3>
                <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-line">
                  {circ.summary}
                </p>
              </div>
            )}

            {/* Instructions */}
            {circ.instructions && (
              <div className="space-y-1.5 p-4 bg-gray-50 dark:bg-gray-800/40 rounded-xl border border-gray-200 dark:border-gray-700">
                <h3 className="text-xs font-bold text-gray-900 dark:text-white uppercase tracking-wider">
                  Registration & Drive Guidelines
                </h3>
                <p className="text-xs text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-line mt-1">
                  {circ.instructions}
                </p>
              </div>
            )}
          </div>

          {/* Linked Job Roles Section */}
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
                <Briefcase className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                <span>Linked Job Roles ({circ.linked_jobs?.length || 0})</span>
              </h2>
              <span className="text-xs text-gray-400">
                Roles published and synchronized with this drive
              </span>
            </div>

            {!circ.linked_jobs || circ.linked_jobs.length === 0 ? (
              <div className="p-6 bg-gray-50 dark:bg-gray-800/40 rounded-xl text-center text-xs text-gray-500">
                No job roles linked yet. Edit this circular to link positions for {circ.company_name}.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {circ.linked_jobs.map((job) => (
                  <div
                    key={job.id}
                    className="p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/30 hover:border-indigo-300 dark:hover:border-indigo-700 transition-all space-y-2"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="font-bold text-sm text-gray-900 dark:text-white">{job.title}</h4>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                          job.status === 'open'
                            ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300'
                            : 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300'
                        }`}
                      >
                        {job.status}
                      </span>
                    </div>

                    <div className="text-xs text-gray-500 dark:text-gray-400 space-y-0.5">
                      {job.salary_range && <p>Salary: {job.salary_range}</p>}
                      {job.location && <p>Location: {job.location}</p>}
                      {job.experience_level && <p>Experience: {job.experience_level}</p>}
                      {job.application_url && (
                        <p className="truncate">
                          URL: <a href={job.application_url} target="_blank" rel="noreferrer" className="text-indigo-600 hover:underline">{job.application_url}</a>
                        </p>
                      )}
                    </div>

                    {job.required_skills && job.required_skills.length > 0 && (
                      <div className="flex flex-wrap gap-1 pt-1">
                        {job.required_skills.slice(0, 4).map((skill, idx) => (
                          <span
                            key={idx}
                            className="px-1.5 py-0.5 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded text-[10px]"
                          >
                            {skill}
                          </span>
                        ))}
                        {job.required_skills.length > 4 && (
                          <span className="text-[10px] text-gray-400 self-center">
                            +{job.required_skills.length - 4} more
                          </span>
                        )}
                      </div>
                    )}

                    <div className="pt-2 border-t border-gray-100 dark:border-gray-700 flex justify-end">
                      <button
                        onClick={() => navigate(`/placement/jobs/${job.job_posting_id}`)}
                        className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-1 cursor-pointer"
                      >
                        <span>View Role Details</span>
                        <ExternalLink className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Drive Attachments Section */}
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
                <Paperclip className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                <span>Drive Attachments ({circ.attachments?.length || 0})</span>
              </h2>
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-400 hidden sm:inline">
                  Posters, JDs, Guidelines, and Eligibility Sheets
                </span>
                <button
                  onClick={() => navigate('/placement/results')}
                  className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-1 font-semibold cursor-pointer"
                  title="Process recruitment round results and shortlists"
                >
                  <span>Shortlists & Results →</span>
                </button>
              </div>
            </div>

            {!circ.attachments || circ.attachments.length === 0 ? (
              <div className="p-6 bg-gray-50 dark:bg-gray-800/40 rounded-xl text-center text-xs text-gray-500">
                No attachments added to this circular.
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {circ.attachments.map((att) => (
                  <div
                    key={att.id}
                    className="p-3 bg-gray-50 dark:bg-gray-800/40 rounded-xl border border-gray-200 dark:border-gray-700 flex items-center justify-between gap-3 text-xs"
                  >
                    <div className="flex items-center gap-2.5 overflow-hidden">
                      <div className="p-2 bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 rounded-lg shrink-0">
                        <Paperclip className="w-4 h-4" />
                      </div>
                      <div className="truncate">
                        <p className="font-semibold text-gray-900 dark:text-white truncate">
                          {att.filename || 'Document'}
                        </p>
                        <p className="text-[10px] text-gray-400 uppercase font-bold mt-0.5">
                          {att.attachment_type?.replace('_', ' ')}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      <button
                        onClick={() => setPreviewFile(att)}
                        className="p-1.5 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors cursor-pointer"
                        title="Preview attachment"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      <a
                        href={getCircularAttachmentDownloadUrl(circ.id, att.id)}
                        target="_blank"
                        rel="noreferrer"
                        download
                        className="p-1.5 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/50 rounded-lg transition-colors cursor-pointer"
                        title="Download attachment"
                      >
                        <Download className="w-4 h-4" />
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: APPLICANTS & MATCHING                                             */}
      {/* ========================================================================= */}
      {activeTab === 'applicants' && (
        <div className="space-y-6">
          {/* Drive Applicants Header Notice */}
          <div className="p-3.5 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded-xl text-xs text-blue-800 dark:text-blue-300 flex items-start gap-2.5">
            <Info className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold">Recruitment Drive Applicants & Multi-Role Pipeline:</span>
              <p className="mt-0.5 text-blue-700 dark:text-blue-300">
                Aggregated applications across all {linkedJobs.length} linked roles. Review candidate qualifications, server-authoritative match %, student-reported external confirmation status, and individual progression.
              </p>
            </div>
          </div>

          {!activeJob ? (
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-8 text-center text-xs text-gray-500">
              No job roles linked to this circular yet. Link a role in Overview & Roles to manage candidates.
            </div>
          ) : (
            <>
              {/* Candidate Matching Action Header */}
              <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h3 className="text-sm font-bold text-gray-900 dark:text-white flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                    <span>Server-Authoritative Candidate Matching ({activeJob.title})</span>
                  </h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    Evaluate registered students against CGPA and skill criteria on the server.
                  </p>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  {linkedJobs.length > 1 && (
                    <select
                      value={selectedRoleIndex}
                      onChange={(e) => setSelectedRoleIndex(Number(e.target.value))}
                      className="px-2.5 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
                    >
                      {linkedJobs.map((j, idx) => (
                        <option key={j.id || idx} value={idx}>
                          Role: {j.title}
                        </option>
                      ))}
                    </select>
                  )}
                  <button
                    onClick={handleMatchCandidates}
                    disabled={isMatching}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-sm disabled:opacity-50"
                  >
                    {isMatching ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>Matching...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>Run Matching for {activeJob.title}</span>
                      </>
                    )}
                  </button>
                  <button
                    onClick={() => navigate(`/placement/jobs/${activeJobPostingId}`)}
                    className="px-3 py-2 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg text-xs font-semibold flex items-center gap-1 transition-colors cursor-pointer"
                  >
                    <span>Job View</span>
                    <ExternalLink className="w-3 h-3" />
                  </button>
                </div>
              </div>

              {/* Match Results Summary (if matching was triggered) */}
              {matchData && (
                <div className="bg-indigo-50/50 dark:bg-indigo-950/20 border border-indigo-200 dark:border-indigo-800 rounded-xl p-4 grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Total Evaluated</span>
                    <p className="text-base font-bold text-gray-900 dark:text-white mt-0.5">
                      {(matchData.all_candidates || matchData.eligible_students || []).length} candidates
                    </p>
                  </div>
                  <div>
                    <span className="text-emerald-600 dark:text-emerald-400 font-semibold">Eligible</span>
                    <p className="text-base font-bold text-emerald-700 dark:text-emerald-300 mt-0.5">
                      {matchData.total_eligible || 0}
                    </p>
                  </div>
                  <div>
                    <span className="text-amber-600 dark:text-amber-400 font-semibold">Ineligible</span>
                    <p className="text-base font-bold text-amber-700 dark:text-amber-300 mt-0.5">
                      {matchData.total_ineligible || 0}
                    </p>
                  </div>
                </div>
              )}

              {/* Registered Applications List */}
              <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5 space-y-4 shadow-sm">
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-bold text-gray-900 dark:text-white flex items-center gap-2">
                      <Users className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                      <span>Aggregated Drive Applications ({sortedAndFilteredApplications.length} of {applications.length})</span>
                    </h3>
                    <p className="text-[11px] text-gray-400 mt-0.5">
                      Each role application is preserved distinctly. Filter or sort across the recruitment drive pipeline.
                    </p>
                  </div>

                  {/* Comprehensive Filters & Sorters */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <div className="relative">
                      <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-gray-400" />
                      <input
                        type="text"
                        placeholder="Search student, email, branch..."
                        value={applicantSearch}
                        onChange={(e) => setApplicantSearch(e.target.value)}
                        className="pl-8 pr-3 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-white"
                      />
                    </div>

                    {/* Role Filter */}
                    <select
                      value={applicantRoleFilter}
                      onChange={(e) => setApplicantRoleFilter(e.target.value)}
                      className="px-2.5 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
                    >
                      <option value="all">All Roles ({applications.length})</option>
                      {linkedJobs.map((j) => (
                        <option key={j.id || j.job_posting_id} value={j.job_posting_id || j.id}>
                          {j.title}
                        </option>
                      ))}
                    </select>

                    {/* Branch Filter */}
                    {uniqueBranches.length > 0 && (
                      <select
                        value={applicantBranchFilter}
                        onChange={(e) => setApplicantBranchFilter(e.target.value)}
                        className="px-2.5 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
                      >
                        <option value="all">All Branches</option>
                        {uniqueBranches.map((b) => (
                          <option key={b} value={b}>
                            {b}
                          </option>
                        ))}
                      </select>
                    )}

                    {/* Status Filter */}
                    <select
                      value={applicantStatusFilter}
                      onChange={(e) => setApplicantStatusFilter(e.target.value)}
                      className="px-2.5 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
                    >
                      <option value="all">All Statuses</option>
                      <option value="applied">Applied</option>
                      <option value="shortlisted">Shortlisted</option>
                      <option value="selected">Selected</option>
                      <option value="rejected">Rejected</option>
                    </select>

                    {/* External Confirmation Filter */}
                    <select
                      value={applicantConfirmFilter}
                      onChange={(e) => setApplicantConfirmFilter(e.target.value)}
                      className="px-2.5 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
                    >
                      <option value="all">All Submissions</option>
                      <option value="confirmed">Externally Confirmed</option>
                      <option value="pending">Pending Confirmation</option>
                    </select>

                    {/* Sort */}
                    <select
                      value={applicantSort}
                      onChange={(e) => setApplicantSort(e.target.value)}
                      className="px-2.5 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
                    >
                      <option value="date_desc">Newest Applied</option>
                      <option value="date_asc">Oldest Applied</option>
                      <option value="match_desc">Highest Match %</option>
                      <option value="cgpa_desc">Highest CGPA</option>
                      <option value="name_asc">Student Name (A-Z)</option>
                    </select>
                  </div>
                </div>

                {sortedAndFilteredApplications.length === 0 ? (
                  <div className="p-8 text-center bg-gray-50 dark:bg-gray-800/30 rounded-xl text-xs text-gray-500">
                    No student applications match the selected criteria for this drive.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-gray-50 dark:bg-gray-800/60 text-gray-500 dark:text-gray-400 uppercase font-semibold">
                        <tr>
                          <th className="py-2.5 px-3">Student</th>
                          <th className="py-2.5 px-3">Branch & CGPA</th>
                          <th className="py-2.5 px-3">Job Role</th>
                          <th className="py-2.5 px-3">Status</th>
                          <th className="py-2.5 px-3">External Submission</th>
                          <th className="py-2.5 px-3">Match %</th>
                          <th className="py-2.5 px-3 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                        {sortedAndFilteredApplications.map((app) => (
                          <tr key={app.id} className="hover:bg-gray-50/50 dark:hover:bg-gray-800/30 transition-colors">
                            <td className="py-2.5 px-3">
                              <p className="font-semibold text-gray-900 dark:text-white">
                                {app.student_name || `Student #${app.student_id}`}
                              </p>
                              <p className="text-[11px] text-gray-400">{app.student_email}</p>
                            </td>
                            <td className="py-2.5 px-3">
                              <span className="font-medium text-gray-700 dark:text-gray-300">
                                {app.student_branch || app.branch || 'N/A'}
                              </span>
                              {(app.student_cgpa !== undefined && app.student_cgpa !== null) ? (
                                <span className="ml-1.5 text-gray-400 font-mono">({app.student_cgpa} CGPA)</span>
                              ) : app.cgpa !== undefined ? (
                                <span className="ml-1.5 text-gray-400 font-mono">({app.cgpa} CGPA)</span>
                              ) : null}
                            </td>
                            <td className="py-2.5 px-3">
                              <span className="inline-block px-2 py-0.5 rounded text-[11px] font-medium bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200">
                                {app.job_title || 'Role'}
                              </span>
                            </td>
                            <td className="py-2.5 px-3">
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                                  app.status === 'selected'
                                    ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300'
                                    : app.status === 'shortlisted'
                                    ? 'bg-blue-100 text-blue-800 dark:bg-blue-950/80 dark:text-blue-300'
                                    : app.status === 'rejected'
                                    ? 'bg-red-100 text-red-800 dark:bg-red-950/80 dark:text-red-300'
                                    : 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300'
                                }`}
                              >
                                {app.status}
                              </span>
                            </td>
                            <td className="py-2.5 px-3">
                              {app.is_external_confirmed || app.external_applied_at ? (
                                <div className="flex flex-col">
                                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300 w-fit">
                                    <CheckCircle2 className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                                    <span>Confirmed</span>
                                  </span>
                                  <span className="text-[10px] text-gray-400 mt-0.5">
                                    {app.external_applied_at
                                      ? new Date(app.external_applied_at).toLocaleDateString()
                                      : 'Student reported'}
                                  </span>
                                </div>
                              ) : (
                                <span className="inline-block px-2 py-0.5 rounded text-[10px] font-semibold bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                                  Pending
                                </span>
                              )}
                            </td>
                            <td className="py-2.5 px-3">
                              {app.match_percentage !== null && app.match_percentage !== undefined ? (
                                <div className="flex items-center gap-1.5">
                                  <span
                                    className={`font-bold font-mono ${
                                      app.match_percentage >= 70
                                        ? 'text-emerald-600 dark:text-emerald-400'
                                        : app.match_percentage >= 50
                                        ? 'text-indigo-600 dark:text-indigo-400'
                                        : 'text-amber-600 dark:text-amber-400'
                                    }`}
                                  >
                                    {Math.round(app.match_percentage)}%
                                  </span>
                                  {app.has_low_match_warning && (
                                    <span
                                      title={app.low_match_warning || 'Low match warning'}
                                      className="text-amber-500 shrink-0"
                                    >
                                      <AlertCircle className="w-3.5 h-3.5" />
                                    </span>
                                  )}
                                </div>
                              ) : (
                                <span className="text-gray-400">N/A</span>
                              )}
                            </td>
                            <td className="py-2.5 px-3 text-right">
                              <button
                                onClick={() =>
                                  setProgressionModalStudent({
                                    id: app.student_id,
                                    name: app.student_name || `Student #${app.student_id}`,
                                    email: app.student_email || '',
                                    jobPostingId: app.job_posting_id,
                                  })
                                }
                                className="px-2.5 py-1 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/50 rounded-lg inline-flex items-center gap-1 cursor-pointer transition-colors"
                              >
                                <TrendingUp className="w-3.5 h-3.5" />
                                <span>Progression</span>
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 3: ROUNDS & PROGRESSION                                              */}
      {/* ========================================================================= */}
      {activeTab === 'rounds' && (
        <div className="space-y-6">
          {/* Active Drive Rounds Guidance */}
          <div className="p-3.5 bg-purple-50 dark:bg-purple-950/40 border border-purple-200 dark:border-purple-800 rounded-xl text-xs text-purple-800 dark:text-purple-300 flex items-start gap-2.5">
            <Info className="w-4 h-4 text-purple-600 dark:text-purple-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold">Recruitment Rounds & Progression Ledger:</span>
              <p className="mt-0.5 text-purple-700 dark:text-purple-300">
                Authoritative recruitment rounds and candidate progression are managed per linked job role for {circ.company_name}. Switch between roles to define rounds, view participant funnels, and record round progression.
              </p>
            </div>
          </div>

          {/* Role Selector (if multiple roles) */}
          {linkedJobs.length > 1 && (
            <div className="flex items-center gap-2 pb-2 overflow-x-auto">
              <span className="text-xs font-bold text-gray-500 uppercase tracking-wider shrink-0">
                Configure Rounds For Role:
              </span>
              {linkedJobs.map((job, idx) => (
                <button
                  key={job.id || idx}
                  onClick={() => setSelectedRoleIndex(idx)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-colors whitespace-nowrap ${
                    selectedRoleIndex === idx
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                  }`}
                >
                  {job.title}
                  <span className="ml-1.5 text-[10px] opacity-80 uppercase">({job.status})</span>
                </button>
              ))}
            </div>
          )}

          {!activeJob ? (
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-8 text-center text-xs text-gray-500">
              No job roles linked to this circular yet. Link at least one role to configure recruitment rounds.
            </div>
          ) : (
            <RecruitmentRoundsTab
              jobId={activeJobPostingId}
              jobTitle={activeJob.title}
              companyName={circ.company_name}
            />
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 4: RESULTS & REVIEW                                                   */}
      {/* ========================================================================= */}
      {activeTab === 'results' && (
        <div className="space-y-6">
          {/* Results Drive Scoped Notice */}
          <div className="p-3.5 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-xl text-xs text-amber-800 dark:text-amber-300 flex items-start gap-2.5">
            <Info className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold">Drive Result Document Batches:</span>
              <p className="mt-0.5 text-amber-700 dark:text-amber-300">
                Displaying result batches scoped to this recruitment drive (Circular #{circ.id}) and its linked roles. Upload XLSX, CSV, or PDF result files to auto-match candidate identities, review scores, and commit round progression.
              </p>
            </div>
          </div>

          {/* Results Action Bar */}
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h3 className="text-sm font-bold text-gray-900 dark:text-white flex items-center gap-2">
                <FileSpreadsheet className="w-4 h-4 text-amber-600 dark:text-amber-400" />
                <span>Result Batches for {circ.company_name} ({filteredBatches.length})</span>
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                Inspect candidate rows, match identities, and commit round outcomes.
              </p>
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search batches..."
                  value={batchSearch}
                  onChange={(e) => setBatchSearch(e.target.value)}
                  className="pl-8 pr-3 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-white"
                />
              </div>
              <select
                value={batchStatusFilter}
                onChange={(e) => setBatchStatusFilter(e.target.value)}
                className="px-2.5 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
              >
                <option value="all">All Review States</option>
                <option value="pending">Pending Review</option>
                <option value="confirmed">Confirmed</option>
                <option value="archived">Archived</option>
              </select>
              <button
                onClick={handleOpenResultUpload}
                className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-sm"
              >
                <UploadCloud className="w-3.5 h-3.5" />
                <span>Upload Drive Results</span>
              </button>
            </div>
          </div>

          {/* Batches Cards */}
          {isResultsLoading && resultBatches.length === 0 ? (
            <div className="p-8 text-center text-xs text-gray-500">
              <div className="animate-spin w-6 h-6 border-2 border-indigo-600 border-t-transparent rounded-full mx-auto mb-2" />
              <p>Loading result batches...</p>
            </div>
          ) : filteredBatches.length === 0 ? (
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-8 text-center text-xs text-gray-500 space-y-2">
              <p>No result batches found for this recruitment drive.</p>
              <button
                onClick={handleOpenResultUpload}
                className="text-indigo-600 dark:text-indigo-400 font-semibold hover:underline cursor-pointer"
              >
                Upload and parse a drive result document &rarr;
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredBatches.map((batch) => (
                <div
                  key={batch.id}
                  className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 space-y-3 hover:border-indigo-300 dark:hover:border-indigo-700 transition-all shadow-sm"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h4 className="font-bold text-sm text-gray-900 dark:text-white">
                        {batch.round_name}
                      </h4>
                      <p className="text-[11px] text-gray-400 mt-0.5">
                        Batch #{batch.id} • {batch.created_at ? new Date(batch.created_at).toLocaleDateString() : 'Recent'}
                      </p>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                        batch.status === 'confirmed'
                          ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300'
                          : batch.status === 'pending'
                          ? 'bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300'
                          : 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300'
                      }`}
                    >
                      {batch.status}
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-2 p-2.5 bg-gray-50 dark:bg-gray-800/40 rounded-lg text-center text-xs">
                    <div>
                      <span className="text-[10px] text-gray-400">Total Rows</span>
                      <p className="font-bold text-gray-900 dark:text-white mt-0.5">
                        {batch.total_items || 0}
                      </p>
                    </div>
                    <div>
                      <span className="text-[10px] text-gray-400">Matched</span>
                      <p className="font-bold text-blue-600 dark:text-blue-400 mt-0.5">
                        {batch.matched_count || 0}
                      </p>
                    </div>
                    <div>
                      <span className="text-[10px] text-gray-400">Confirmed</span>
                      <p className="font-bold text-emerald-600 dark:text-emerald-400 mt-0.5">
                        {batch.confirmed_count || 0}
                      </p>
                    </div>
                  </div>

                  <div className="flex justify-end pt-1">
                    <button
                      onClick={() => navigate(`/placement/results/${batch.id}`)}
                      className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-1 cursor-pointer"
                    >
                      <span>Inspect Candidate Rows & Confirm</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 5: VERIFIED OFFERS                                                   */}
      {/* ========================================================================= */}
      {activeTab === 'offers' && (
        <div className="space-y-6">
          {/* Institutional Offer Accounting Notice */}
          <div className="p-3.5 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-xl text-xs text-emerald-800 dark:text-emerald-300 flex items-start gap-2.5">
            <Info className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold">Verified Placement Offers Ledger:</span>
              <p className="mt-0.5 text-emerald-700 dark:text-emerald-300">
                Audited institutional placement offers, compensation terms, offer letters, and student acceptance tracking for {circ.company_name}. In compliance with institutional reporting standards, only students with active accepted offers are counted as officially placed.
              </p>
            </div>
          </div>

          {/* Role Selector (if multiple roles) */}
          {linkedJobs.length > 1 && (
            <div className="flex items-center gap-2 pb-2 overflow-x-auto">
              <span className="text-xs font-bold text-gray-500 uppercase tracking-wider shrink-0">
                Offers For Role:
              </span>
              {linkedJobs.map((job, idx) => (
                <button
                  key={job.id || idx}
                  onClick={() => setSelectedRoleIndex(idx)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-colors whitespace-nowrap ${
                    selectedRoleIndex === idx
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                  }`}
                >
                  {job.title}
                  <span className="ml-1.5 text-[10px] opacity-80 uppercase">({job.status})</span>
                </button>
              ))}
            </div>
          )}

          {!activeJob ? (
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-8 text-center text-xs text-gray-500">
              No job roles linked to this circular yet. Link a role in Overview & Roles to issue verified offers.
            </div>
          ) : (
            <VerifiedOffersTab
              jobId={activeJobPostingId}
              jobTitle={activeJob.title}
              companyName={circ.company_name}
              applications={applications.filter((a) => String(a.job_posting_id) === String(activeJobPostingId))}
            />
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 6: DRIVE PLACEMENT REPORT                                            */}
      {/* ========================================================================= */}
      {activeTab === 'reports' && (
        <div className="space-y-6">
          {/* Header Action / Refresh Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 shadow-sm">
            <div>
              <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                <span>Drive Placement Intelligence & Conversion Funnel</span>
              </h2>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                Authoritative recruitment drive report for {circ.company_name} • Circular #{circ.id}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => fetchCircularDriveReport(id)}
                disabled={isDriveReportLoading}
                className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isDriveReportLoading ? 'animate-spin' : ''}`} />
                <span>Refresh Report</span>
              </button>
            </div>
          </div>

          {/* Institutional Accounting Standard Notice */}
          <div className="p-4 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-xl text-xs text-emerald-900 dark:text-emerald-200 flex items-start gap-3 shadow-sm">
            <ShieldCheck className="w-5 h-5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <span className="font-bold text-emerald-800 dark:text-emerald-300">
                Institutional Placement Accounting Standard Compliant
              </span>
              <p className="text-emerald-700 dark:text-emerald-300/90 leading-relaxed">
                Unique Placed count strictly records students with verified active accepted offers (<code className="px-1 py-0.5 bg-emerald-100 dark:bg-emerald-900/60 rounded font-mono">acceptance_status = 'accepted'</code>). Candidates in shortlist, selection, or offer stages prior to signed/binding student acceptance are classified as in-pipeline conversions and never conflated with confirmed institutional placements.
              </p>
            </div>
          </div>

          {isDriveReportLoading && !driveReport ? (
            <div className="p-12 text-center text-gray-500 dark:text-gray-400">
              <div className="animate-spin w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full mx-auto mb-3" />
              <p className="text-xs">Generating Drive Placement Report...</p>
            </div>
          ) : !driveReport ? (
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-8 text-center text-xs text-gray-500">
              Report data is currently unavailable. Click "Refresh Report" to regenerate.
            </div>
          ) : (
            <>
              {/* Executive Metrics Overview */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* Unique Applicants */}
                <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 shadow-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Unique Applicants</span>
                    <div className="p-2 bg-blue-50 dark:bg-blue-950/50 rounded-lg text-blue-600 dark:text-blue-400">
                      <Users className="w-4 h-4" />
                    </div>
                  </div>
                  <p className="text-2xl font-black text-gray-900 dark:text-white mt-2">
                    {driveReport.unique_applicants_count}
                  </p>
                  <p className="text-[11px] text-gray-400 mt-1">
                    Across {driveReport.total_applications_count} total role submissions
                  </p>
                </div>

                {/* External Confirmations */}
                <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 shadow-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-gray-500 dark:text-gray-400">External Confirmations</span>
                    <div className="p-2 bg-emerald-50 dark:bg-emerald-950/50 rounded-lg text-emerald-600 dark:text-emerald-400">
                      <CheckCheck className="w-4 h-4" />
                    </div>
                  </div>
                  <p className="text-2xl font-black text-emerald-600 dark:text-emerald-400 mt-2">
                    {driveReport.external_confirmations_count}
                  </p>
                  <p className="text-[11px] text-gray-400 mt-1">
                    Student-verified external portal applications
                  </p>
                </div>

                {/* Total Verified Offers */}
                <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 shadow-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Verified Offers Issued</span>
                    <div className="p-2 bg-purple-50 dark:bg-purple-950/50 rounded-lg text-purple-600 dark:text-purple-400">
                      <Award className="w-4 h-4" />
                    </div>
                  </div>
                  <p className="text-2xl font-black text-purple-600 dark:text-purple-400 mt-2">
                    {driveReport.total_verified_offers_count}
                  </p>
                  <p className="text-[11px] text-gray-400 mt-1">
                    Issued to {driveReport.offers_summary?.unique_students_with_offers || 0} unique students
                  </p>
                </div>

                {/* Placed Students (Institutional Metric) */}
                <div className="bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-950/40 dark:to-teal-950/30 rounded-xl border border-emerald-200 dark:border-emerald-800 p-4 shadow-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-emerald-900 dark:text-emerald-300">Confirmed Placed Students</span>
                    <div className="p-2 bg-emerald-500 text-white rounded-lg shadow-sm">
                      <GraduationCap className="w-4 h-4" />
                    </div>
                  </div>
                  <p className="text-2xl font-black text-emerald-700 dark:text-emerald-400 mt-2">
                    {driveReport.verified_placed_students_count}
                  </p>
                  <p className="text-[11px] text-emerald-800 dark:text-emerald-300 font-medium mt-1">
                    Holding active accepted offers
                  </p>
                </div>
              </div>

              {/* Drive Offers Breakdown Grid */}
              <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5 shadow-sm space-y-4">
                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider flex items-center gap-2">
                  <Award className="w-4 h-4 text-indigo-500" />
                  <span>Offer Acceptance Ledger Breakdown</span>
                </h3>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="p-3 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-100 dark:border-emerald-900/50 rounded-xl text-center">
                    <span className="text-[10px] font-semibold uppercase text-emerald-700 dark:text-emerald-400">Accepted (Official)</span>
                    <p className="text-xl font-bold text-emerald-700 dark:text-emerald-300 mt-1">
                      {driveReport.offers_summary?.accepted_count || 0}
                    </p>
                  </div>
                  <div className="p-3 bg-blue-50 dark:bg-blue-950/30 border border-blue-100 dark:border-blue-900/50 rounded-xl text-center">
                    <span className="text-[10px] font-semibold uppercase text-blue-700 dark:text-blue-400">Decision Pending</span>
                    <p className="text-xl font-bold text-blue-700 dark:text-blue-300 mt-1">
                      {driveReport.offers_summary?.offered_count || 0}
                    </p>
                  </div>
                  <div className="p-3 bg-amber-50 dark:bg-amber-950/30 border border-amber-100 dark:border-amber-900/50 rounded-xl text-center">
                    <span className="text-[10px] font-semibold uppercase text-amber-700 dark:text-amber-400">Declined by Student</span>
                    <p className="text-xl font-bold text-amber-700 dark:text-amber-300 mt-1">
                      {driveReport.offers_summary?.declined_count || 0}
                    </p>
                  </div>
                  <div className="p-3 bg-red-50 dark:bg-red-950/30 border border-red-100 dark:border-red-900/50 rounded-xl text-center">
                    <span className="text-[10px] font-semibold uppercase text-red-700 dark:text-red-400">Rescinded</span>
                    <p className="text-xl font-bold text-red-700 dark:text-red-300 mt-1">
                      {driveReport.offers_summary?.rescinded_count || 0}
                    </p>
                  </div>
                </div>
              </div>

              {/* Applications Breakdown By Role */}
              <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5 shadow-sm space-y-4">
                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider flex items-center gap-2">
                  <Briefcase className="w-4 h-4 text-indigo-500" />
                  <span>Applications & Pipeline per Linked Role ({driveReport.applications_by_role?.length || 0})</span>
                </h3>

                {(!driveReport.applications_by_role || driveReport.applications_by_role.length === 0) ? (
                  <p className="text-xs text-gray-400">No role applications recorded.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-gray-50 dark:bg-gray-800/60 text-gray-500 dark:text-gray-400 uppercase font-semibold">
                        <tr>
                          <th className="py-2.5 px-3">Role Title</th>
                          <th className="py-2.5 px-3 text-center">Total Apps</th>
                          <th className="py-2.5 px-3 text-center">Ext. Confirmed</th>
                          <th className="py-2.5 px-3 text-center">Applied</th>
                          <th className="py-2.5 px-3 text-center">Shortlisted</th>
                          <th className="py-2.5 px-3 text-center">Selected</th>
                          <th className="py-2.5 px-3 text-center">Rejected</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                        {driveReport.applications_by_role.map((r) => (
                          <tr key={r.job_posting_id} className="hover:bg-gray-50/50 dark:hover:bg-gray-800/30 transition-colors">
                            <td className="py-2.5 px-3 font-semibold text-gray-900 dark:text-white">
                              {r.job_title}
                            </td>
                            <td className="py-2.5 px-3 text-center font-bold text-gray-900 dark:text-white">
                              {r.total_applications}
                            </td>
                            <td className="py-2.5 px-3 text-center text-emerald-600 dark:text-emerald-400 font-semibold">
                              {r.external_confirmed_count}
                            </td>
                            <td className="py-2.5 px-3 text-center text-gray-600 dark:text-gray-300">
                              {r.applications_by_status?.applied || 0}
                            </td>
                            <td className="py-2.5 px-3 text-center text-blue-600 dark:text-blue-400 font-semibold">
                              {r.applications_by_status?.shortlisted || 0}
                            </td>
                            <td className="py-2.5 px-3 text-center text-emerald-600 dark:text-emerald-400 font-semibold">
                              {r.applications_by_status?.selected || 0}
                            </td>
                            <td className="py-2.5 px-3 text-center text-red-600 dark:text-red-400">
                              {r.applications_by_status?.rejected || 0}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Recruitment Rounds Outcomes Funnel */}
              <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5 shadow-sm space-y-4">
                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider flex items-center gap-2">
                  <Layers className="w-4 h-4 text-purple-500" />
                  <span>Recruitment Rounds Progression Outcomes</span>
                </h3>

                {(!driveReport.rounds_summary || driveReport.rounds_summary.length === 0) ? (
                  <p className="text-xs text-gray-400">No recruitment round outcomes recorded yet for this drive.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-gray-50 dark:bg-gray-800/60 text-gray-500 dark:text-gray-400 uppercase font-semibold">
                        <tr>
                          <th className="py-2.5 px-3">Role</th>
                          <th className="py-2.5 px-3">Round</th>
                          <th className="py-2.5 px-3">Type</th>
                          <th className="py-2.5 px-3 text-center">Cleared</th>
                          <th className="py-2.5 px-3 text-center">Rejected</th>
                          <th className="py-2.5 px-3 text-center">Absent</th>
                          <th className="py-2.5 px-3 text-center">On Hold</th>
                          <th className="py-2.5 px-3 text-center">Total Audited</th>
                          <th className="py-2.5 px-3 text-right">Pass Rate</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                        {driveReport.rounds_summary.map((rd) => {
                          const passRate = rd.total_outcomes > 0
                            ? Math.round((rd.cleared_count / rd.total_outcomes) * 100)
                            : 0;
                          return (
                            <tr key={rd.round_id} className="hover:bg-gray-50/50 dark:hover:bg-gray-800/30 transition-colors">
                              <td className="py-2.5 px-3 font-medium text-gray-700 dark:text-gray-300">
                                {rd.job_title}
                              </td>
                              <td className="py-2.5 px-3 font-semibold text-gray-900 dark:text-white">
                                #{rd.round_number} {rd.round_name}
                              </td>
                              <td className="py-2.5 px-3 capitalize text-gray-500">
                                {rd.round_type?.replace(/_/g, ' ')}
                              </td>
                              <td className="py-2.5 px-3 text-center font-bold text-emerald-600 dark:text-emerald-400">
                                {rd.cleared_count}
                              </td>
                              <td className="py-2.5 px-3 text-center text-red-600 dark:text-red-400">
                                {rd.rejected_count}
                              </td>
                              <td className="py-2.5 px-3 text-center text-gray-400">
                                {rd.absent_count}
                              </td>
                              <td className="py-2.5 px-3 text-center text-amber-500">
                                {rd.on_hold_count}
                              </td>
                              <td className="py-2.5 px-3 text-center font-semibold text-gray-700 dark:text-gray-300">
                                {rd.total_outcomes}
                              </td>
                              <td className="py-2.5 px-3 text-right font-mono font-bold text-indigo-600 dark:text-indigo-400">
                                {passRate}%
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Branch Representation */}
              {driveReport.branch_breakdown && Object.keys(driveReport.branch_breakdown).length > 0 && (
                <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5 shadow-sm space-y-3">
                  <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider flex items-center gap-2">
                    <GraduationCap className="w-4 h-4 text-indigo-500" />
                    <span>Applicant Branch Distribution</span>
                  </h3>
                  <div className="flex flex-wrap gap-2 pt-1">
                    {Object.entries(driveReport.branch_breakdown).map(([branch, count]) => (
                      <div
                        key={branch}
                        className="px-3 py-1.5 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-xs flex items-center gap-2"
                      >
                        <span className="font-semibold text-gray-800 dark:text-gray-200">{branch}</span>
                        <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-indigo-100 dark:bg-indigo-950/80 text-indigo-700 dark:text-indigo-300">
                          {count}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODALS: ATTACHMENT PREVIEW, PUBLISH REVIEW, RESULT UPLOAD, PROGRESSION     */}
      {/* ========================================================================= */}

      {/* Attachment Preview Modal */}
      {previewFile && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-4xl w-full max-h-[90vh] flex flex-col border border-gray-200 dark:border-gray-800 shadow-2xl overflow-hidden">
            <div className="p-4 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
              <div>
                <h3 className="font-bold text-sm text-gray-900 dark:text-white">
                  {previewFile.filename}
                </h3>
                <span className="text-[10px] uppercase font-bold text-gray-400">
                  {previewFile.attachment_type}
                </span>
              </div>
              <button
                onClick={() => setPreviewFile(null)}
                className="p-1.5 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-auto p-4 flex items-center justify-center bg-gray-50 dark:bg-gray-950">
              <iframe
                src={getCircularAttachmentPreviewUrl(circ.id, previewFile.id)}
                title={previewFile.filename}
                className="w-full h-[65vh] rounded-lg border border-gray-200 dark:border-gray-800"
              />
            </div>
          </div>
        </div>
      )}

      {/* Publish Review Modal */}
      {publishModal.isOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-lg w-full p-6 border border-gray-200 dark:border-gray-800 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-emerald-100 dark:bg-emerald-950/80 text-emerald-600 dark:text-emerald-400 rounded-xl">
                <Sparkles className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                  Publish Recruitment Circular
                </h3>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Atomic Drive & Roles Activation
                </p>
              </div>
            </div>

            <div className="p-3 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded-lg text-xs text-blue-800 dark:text-blue-300 space-y-1">
              <p className="font-semibold">⚡ Action Checklist:</p>
              <ul className="list-disc pl-4 space-y-0.5">
                <li>Transition circular status from DRAFT to PUBLISHED.</li>
                <li>Activate all {circ.linked_jobs?.length || 0} linked draft roles to OPEN.</li>
                <li>Deliver single aggregated announcement to active, eligible students.</li>
                <li>Individual job publication alerts suppressed to avoid duplicates.</li>
              </ul>
            </div>

            {publishModal.errorMessage && (
              <div className="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-lg text-xs text-red-700 dark:text-red-300">
                {publishModal.errorMessage}
              </div>
            )}

            {publishModal.showSkillBypass && (
              <label className="flex items-center gap-2 p-3 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-lg cursor-pointer">
                <input
                  type="checkbox"
                  checked={publishModal.confirmNoSkills}
                  onChange={(e) =>
                    setPublishModal((prev) => ({
                      ...prev,
                      confirmNoSkills: e.target.checked,
                    }))
                  }
                  className="rounded text-amber-600 focus:ring-amber-500"
                />
                <span className="text-xs text-amber-900 dark:text-amber-200">
                  Confirm publication despite missing skill requirements.
                </span>
              </label>
            )}

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() =>
                  setPublishModal({
                    isOpen: false,
                    isPublishing: false,
                    confirmNoSkills: false,
                    errorMessage: null,
                    showSkillBypass: false,
                  })
                }
                disabled={publishModal.isPublishing}
                className="px-4 py-2 text-xs font-semibold text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmPublish}
                disabled={publishModal.isPublishing}
                className="px-5 py-2 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors cursor-pointer flex items-center gap-1.5 shadow-sm disabled:opacity-50"
              >
                {publishModal.isPublishing ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Publishing...</span>
                  </>
                ) : (
                  <span>Confirm & Publish</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Result Document Upload Modal */}
      {showResultUploadModal && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-lg w-full p-6 border border-gray-200 dark:border-gray-800 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-gray-100 dark:border-gray-800 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2.5 bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400 rounded-xl">
                  <UploadCloud className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-gray-900 dark:text-white">
                    Upload Recruitment Drive Results
                  </h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Drive: {circ.title} ({circ.company_name})
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowResultUploadModal(false)}
                className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded-lg cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmitResultUpload} className="space-y-4 text-xs">
              {/* Job Role Selection */}
              <div>
                <label className="block font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Target Job Role
                </label>
                <select
                  value={resultUploadJobId}
                  onChange={(e) => setResultUploadJobId(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-white"
                >
                  <option value="">All Drive Roles (Drive-Level Batch)</option>
                  {linkedJobs.map((j) => (
                    <option key={j.id} value={j.job_posting_id || j.id}>
                      {j.title}
                    </option>
                  ))}
                </select>
              </div>

              {/* Recruitment Round Selection / Input */}
              {availableJobRounds.length > 0 && (
                <div>
                  <label className="block font-semibold text-gray-700 dark:text-gray-300 mb-1">
                    Link To Existing Round (Optional)
                  </label>
                  <select
                    value={resultUploadRoundId}
                    onChange={(e) => handleSelectUploadRound(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-white"
                  >
                    <option value="">Custom Round Name / New Round</option>
                    {availableJobRounds.map((r) => (
                      <option key={r.id} value={r.id}>
                        Round {r.round_number}: {r.round_name} ({r.round_type})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Round Name */}
              <div>
                <label className="block font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Round Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g., Online Assessment, Technical Interview 1"
                  value={resultUploadRoundName}
                  onChange={(e) => setResultUploadRoundName(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-white"
                />
              </div>

              {/* Round Type */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-gray-700 dark:text-gray-300 mb-1">
                    Round Type
                  </label>
                  <select
                    value={resultUploadRoundType}
                    onChange={(e) => setResultUploadRoundType(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-white"
                  >
                    <option value="assessment">Assessment / Test</option>
                    <option value="aptitude">Aptitude Test</option>
                    <option value="technical_test">Technical Test</option>
                    <option value="coding">Coding Round</option>
                    <option value="technical_interview">Technical Interview</option>
                    <option value="hr_interview">HR Interview</option>
                    <option value="group_discussion">Group Discussion</option>
                    <option value="other">Other</option>
                  </select>
                </div>

                <div className="flex items-end pb-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={resultUploadIsFinal}
                      onChange={(e) => setResultUploadIsFinal(e.target.checked)}
                      className="rounded text-indigo-600 focus:ring-indigo-500"
                    />
                    <span className="font-semibold text-gray-700 dark:text-gray-300">
                      Final Selection Round
                    </span>
                  </label>
                </div>
              </div>

              {/* Document File Input */}
              <div>
                <label className="block font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Upload Result Spreadsheet / PDF <span className="text-red-500">*</span>
                </label>
                <input
                  type="file"
                  required
                  accept=".csv, .xlsx, .xls, .pdf"
                  onChange={(e) => setResultUploadFile(e.target.files[0] || null)}
                  className="w-full text-xs text-gray-500 dark:text-gray-400 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-indigo-50 file:text-indigo-700 dark:file:bg-indigo-950/50 dark:file:text-indigo-300 hover:file:bg-indigo-100 cursor-pointer"
                />
                <p className="text-[11px] text-gray-400 mt-1">
                  Supported formats: CSV, XLSX, XLS, PDF. System automatically normalizes headers and matches candidate roll numbers/emails.
                </p>
              </div>

              {/* Modal Buttons */}
              <div className="flex items-center justify-end gap-3 pt-3 border-t border-gray-100 dark:border-gray-800">
                <button
                  type="button"
                  onClick={() => setShowResultUploadModal(false)}
                  disabled={isResultUploading}
                  className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isResultUploading}
                  className="px-5 py-2 font-semibold bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors cursor-pointer flex items-center gap-1.5 shadow-sm disabled:opacity-50"
                >
                  {isResultUploading ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Parsing Results...</span>
                    </>
                  ) : (
                    <>
                      <Upload className="w-3.5 h-3.5" />
                      <span>Upload & Parse</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Student Progression Modal */}
      {progressionModalStudent && (
        <StudentProgressionModal
          isOpen={Boolean(progressionModalStudent)}
          onClose={() => setProgressionModalStudent(null)}
          studentId={progressionModalStudent.id}
          studentName={progressionModalStudent.name}
          studentEmail={progressionModalStudent.email}
          jobId={progressionModalStudent.jobPostingId || activeJobPostingId}
        />
      )}
    </div>
  );
};

export default CircularDetails;
