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
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
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
  const [applicantStatusFilter, setApplicantStatusFilter] = useState('all');
  const [progressionModalStudent, setProgressionModalStudent] = useState(null);

  // Results tab filters
  const [batchSearch, setBatchSearch] = useState('');
  const [batchStatusFilter, setBatchStatusFilter] = useState('all');

  useEffect(() => {
    fetchCircular(id).catch(() => {
      toast.error('Failed to load circular details.');
    });
  }, [id, fetchCircular]);

  const circ = selectedCircular;
  const linkedJobs = useMemo(() => circ?.linked_jobs || [], [circ]);
  const activeJob = linkedJobs[selectedRoleIndex] || linkedJobs[0] || null;
  const activeJobPostingId = activeJob?.job_posting_id || activeJob?.id || null;

  // Refresh tab-specific data on tab switch or role switch
  useEffect(() => {
    if (!circ) return;
    if (activeTab === 'applicants' && activeJobPostingId) {
      fetchApplications({ job_posting_id: activeJobPostingId }).catch(() => {});
    } else if (activeTab === 'rounds' && activeJobPostingId) {
      fetchJobRounds(activeJobPostingId).catch(() => {});
    } else if (activeTab === 'offers' && activeJobPostingId) {
      fetchVerifiedOffers({ job_posting_id: activeJobPostingId }).catch(() => {});
    } else if (activeTab === 'results' && circ.company_id) {
      fetchResultBatches({ company_id: circ.company_id }).catch(() => {});
    }
  }, [activeTab, activeJobPostingId, circ?.company_id]);

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

  // Filtered applications for active job
  const filteredApplications = useMemo(() => {
    return applications.filter((app) => {
      const matchesSearch =
        !applicantSearch ||
        app.student_name?.toLowerCase().includes(applicantSearch.toLowerCase()) ||
        app.student_email?.toLowerCase().includes(applicantSearch.toLowerCase()) ||
        app.branch?.toLowerCase().includes(applicantSearch.toLowerCase());

      const matchesStatus =
        applicantStatusFilter === 'all' ||
        app.status?.toLowerCase() === applicantStatusFilter.toLowerCase();

      return matchesSearch && matchesStatus;
    });
  }, [applications, applicantSearch, applicantStatusFilter]);

  // Filtered result batches for active company
  const filteredBatches = useMemo(() => {
    return resultBatches.filter((b) => {
      const matchesSearch =
        !batchSearch ||
        b.round_name?.toLowerCase().includes(batchSearch.toLowerCase()) ||
        b.file_name?.toLowerCase().includes(batchSearch.toLowerCase());

      const matchesStatus =
        batchStatusFilter === 'all' ||
        b.status?.toLowerCase() === batchStatusFilter.toLowerCase();

      return matchesSearch && matchesStatus;
    });
  }, [resultBatches, batchSearch, batchStatusFilter]);

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
                    {circ.drive_date ? new Date(circ.drive_date).toLocaleString() : 'TBD / Multiple Dates'}
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
                      : 'Open Until Drive'}
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
              <span className="text-xs text-gray-400">
                Posters, JDs, Guidelines, and Eligibility Sheets
              </span>
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
                        href={`/api/v1/files/${att.file_id}/download`}
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
          {/* Stage 3.4.3 Integration Notice */}
          <div className="p-3.5 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded-xl text-xs text-blue-800 dark:text-blue-300 flex items-start gap-2.5">
            <Info className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold">Recruitment Drive Applicants Workspace:</span>
              <p className="mt-0.5 text-blue-700 dark:text-blue-300">
                Viewing applicants and candidate skill matching per linked job role. Unified multi-role drive pipeline aggregation and bulk status management will be unified in Stage 3.4.3.
              </p>
            </div>
          </div>

          {/* Role Selector (if multiple roles) */}
          {linkedJobs.length > 1 && (
            <div className="flex items-center gap-2 pb-2 overflow-x-auto">
              <span className="text-xs font-bold text-gray-500 uppercase tracking-wider shrink-0">
                Select Role:
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
              No job roles linked to this circular yet. Link a role in Overview & Roles to manage candidates.
            </div>
          ) : (
            <>
              {/* Candidate Matching Action Header */}
              <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h3 className="text-sm font-bold text-gray-900 dark:text-white flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                    <span>Candidate Matching & Eligibility for {activeJob.title}</span>
                  </h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    Evaluate registered students against CGPA and skill requirements.
                  </p>
                </div>

                <div className="flex items-center gap-2">
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
                        <span>Run Candidate Matching</span>
                      </>
                    )}
                  </button>
                  <button
                    onClick={() => navigate(`/placement/jobs/${activeJobPostingId}`)}
                    className="px-3 py-2 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg text-xs font-semibold flex items-center gap-1 transition-colors cursor-pointer"
                  >
                    <span>Full Job View</span>
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
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <h3 className="text-sm font-bold text-gray-900 dark:text-white flex items-center gap-2">
                    <Users className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                    <span>Registered Applicants ({filteredApplications.length})</span>
                  </h3>

                  {/* Filters */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <div className="relative">
                      <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-gray-400" />
                      <input
                        type="text"
                        placeholder="Search student..."
                        value={applicantSearch}
                        onChange={(e) => setApplicantSearch(e.target.value)}
                        className="pl-8 pr-3 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-white"
                      />
                    </div>
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
                  </div>
                </div>

                {filteredApplications.length === 0 ? (
                  <div className="p-8 text-center bg-gray-50 dark:bg-gray-800/30 rounded-xl text-xs text-gray-500">
                    No student applications recorded for this role yet. Eligible students can apply once published.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-gray-50 dark:bg-gray-800/60 text-gray-500 dark:text-gray-400 uppercase font-semibold">
                        <tr>
                          <th className="py-2.5 px-3">Student</th>
                          <th className="py-2.5 px-3">Branch & CGPA</th>
                          <th className="py-2.5 px-3">Status</th>
                          <th className="py-2.5 px-3 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                        {filteredApplications.map((app) => (
                          <tr key={app.id} className="hover:bg-gray-50/50 dark:hover:bg-gray-800/30 transition-colors">
                            <td className="py-2.5 px-3">
                              <p className="font-semibold text-gray-900 dark:text-white">
                                {app.student_name || `Student #${app.student_id}`}
                              </p>
                              <p className="text-[11px] text-gray-400">{app.student_email}</p>
                            </td>
                            <td className="py-2.5 px-3">
                              <span className="font-medium text-gray-700 dark:text-gray-300">
                                {app.branch || 'N/A'}
                              </span>
                              {app.cgpa !== undefined && (
                                <span className="ml-1.5 text-gray-400">({app.cgpa} CGPA)</span>
                              )}
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
                            <td className="py-2.5 px-3 text-right">
                              <button
                                onClick={() =>
                                  setProgressionModalStudent({
                                    id: app.student_id,
                                    name: app.student_name || `Student #${app.student_id}`,
                                    email: app.student_email || '',
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
          {/* Stage 3.4.3 Integration Notice */}
          <div className="p-3.5 bg-purple-50 dark:bg-purple-950/40 border border-purple-200 dark:border-purple-800 rounded-xl text-xs text-purple-800 dark:text-purple-300 flex items-start gap-2.5">
            <Info className="w-4 h-4 text-purple-600 dark:text-purple-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold">Recruitment Rounds Workspace:</span>
              <p className="mt-0.5 text-purple-700 dark:text-purple-300">
                Authoritative recruitment rounds and progression outcomes are active per linked role. Cross-role synchronized round timelines will be unified in Stage 3.4.3.
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
          {/* Stage 3.4.3 Integration Notice */}
          <div className="p-3.5 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-xl text-xs text-amber-800 dark:text-amber-300 flex items-start gap-2.5">
            <Info className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold">Recruitment Results Workspace:</span>
              <p className="mt-0.5 text-amber-700 dark:text-amber-300">
                Displaying result batches uploaded for {circ.company_name}. In-workspace spreadsheet reconciliation and unified drive results confirmation will be streamlined in Stage 3.4.3.
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
                onClick={() => navigate('/placement/results')}
                className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-sm"
              >
                <span>Upload Results</span>
                <ChevronRight className="w-3.5 h-3.5" />
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
              <p>No result batches found for {circ.company_name}.</p>
              <button
                onClick={() => navigate('/placement/results')}
                className="text-indigo-600 dark:text-indigo-400 font-semibold hover:underline"
              >
                Upload and parse a result document &rarr;
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
          {/* Stage 3.4.3 Integration Notice */}
          <div className="p-3.5 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-xl text-xs text-emerald-800 dark:text-emerald-300 flex items-start gap-2.5">
            <Info className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold">Verified Offers Ledger Workspace:</span>
              <p className="mt-0.5 text-emerald-700 dark:text-emerald-300">
                Verified placement offers, CTC terms, offer letters, and student response tracking are active per linked role. Aggregated drive-level offer rollups will be unified in Stage 3.4.3.
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
              applications={applications}
            />
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 6: DRIVE PLACEMENT REPORT                                            */}
      {/* ========================================================================= */}
      {activeTab === 'reports' && (
        <div className="space-y-6">
          {/* Real Metrics Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 shadow-sm">
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Drive Status</span>
              <p className="text-lg font-bold text-gray-900 dark:text-white capitalize mt-1">
                {circ.status}
              </p>
            </div>
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 shadow-sm">
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Linked Job Roles</span>
              <p className="text-lg font-bold text-indigo-600 dark:text-indigo-400 mt-1">
                {linkedJobs.length} roles
              </p>
            </div>
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 shadow-sm">
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Target Branches</span>
              <p className="text-lg font-bold text-blue-600 dark:text-blue-400 mt-1">
                {circ.branch_eligibility?.length || 0} branches
              </p>
            </div>
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 shadow-sm">
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Attachments</span>
              <p className="text-lg font-bold text-purple-600 dark:text-purple-400 mt-1">
                {circ.attachments?.length || 0} files
              </p>
            </div>
          </div>

          {/* Stage 3.4.3 Unified Report Placeholder Card */}
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-8 shadow-sm space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 rounded-xl">
                <BarChart3 className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-bold text-gray-900 dark:text-white">
                  Unified Drive Placement Analytics & Funnel
                </h3>
                <span className="text-xs font-semibold text-indigo-600 dark:text-indigo-400">
                  Integration Roadmap: Stage 3.4.3
                </span>
              </div>
            </div>

            <p className="text-xs text-gray-600 dark:text-gray-300 leading-relaxed">
              Dedicated drive-level conversion analytics, branch-wise placement breakdown, salary CTC statistics, and downloadable drive PDF/Excel reports will be unified here in Stage 3.4.3 when the drive reporting aggregation backend is connected.
            </p>

            <div className="p-4 bg-gray-50 dark:bg-gray-800/40 rounded-xl border border-gray-100 dark:border-gray-700 space-y-2 text-xs">
              <span className="font-bold text-gray-700 dark:text-gray-300">
                Scheduled Stage 3.4.3 Drive Report Features:
              </span>
              <ul className="list-disc pl-5 space-y-1 text-gray-600 dark:text-gray-400">
                <li>End-to-End Recruitment Funnel (Eligible &rarr; Applicants &rarr; Round Cleared &rarr; Offers &rarr; Accepted).</li>
                <li>Branch-wise diversity and selection conversion percentages.</li>
                <li>CTC and stipend package distribution for {circ.company_name}.</li>
                <li>One-click Drive Summary export in Excel and PDF formats.</li>
              </ul>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => navigate('/placement/reports')}
                className="px-4 py-2 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
              >
                <span>View Institutional Reports</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODALS: ATTACHMENT PREVIEW, PUBLISH REVIEW, STUDENT PROGRESSION           */}
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
                src={`/api/v1/files/${previewFile.file_id}/preview`}
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

      {/* Student Progression Modal */}
      {progressionModalStudent && (
        <StudentProgressionModal
          isOpen={Boolean(progressionModalStudent)}
          onClose={() => setProgressionModalStudent(null)}
          studentId={progressionModalStudent.id}
          studentName={progressionModalStudent.name}
          studentEmail={progressionModalStudent.email}
          jobId={activeJobPostingId}
        />
      )}
    </div>
  );
};

export default CircularDetails;
