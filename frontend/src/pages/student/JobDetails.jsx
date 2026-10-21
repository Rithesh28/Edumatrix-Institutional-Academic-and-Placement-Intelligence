import React, { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Building2,
  MapPin,
  Calendar,
  Clock,
  Banknote,
  Award,
  GraduationCap,
  Briefcase,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  AlertCircle,
  Sparkles,
  Send,
  RefreshCw,
  FileText,
  Info,
  ChevronRight,
  ExternalLink,
  X,
  TrendingUp,
  Megaphone,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import { useAuthStore } from '../../store/authStore';
import StudentVerifiedOfferCard from '../../components/placement/StudentVerifiedOfferCard';
import StudentRecruitmentTimeline from '../../components/placement/StudentRecruitmentTimeline';
import { getJobFilePreviewUrl, getJobFileDownloadUrl, downloadJobFileAuth, previewJobFileAuth, getRecruitmentCircular } from '../../services/placementService';
import toast from 'react-hot-toast';

function StudentJobDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const {
    selectedJob,
    isLoading: isJobLoading,
    error: jobError,
    fetchJobPosting,
    jobEligibility,
    eligibilityJobId,
    isEligibilityLoading,
    eligibilityError,
    checkJobEligibility,
    clearJobEligibility,
    myApplications,
    isMyApplicationsLoading,
    fetchMyApplications,
    myOffers,
    fetchMyOffers,
    createApplication,
    confirmExternalApplication,
    confirmExternalJobApplication,
    isSubmittingApplication,
    applicationSubmitError,
  } = usePlacementStore();

  // Modal and submission state
  const [isApplyModalOpen, setIsApplyModalOpen] = useState(false);
  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);
  const [isConfirmingExternal, setIsConfirmingExternal] = useState(false);
  const [isTimelineOpen, setIsTimelineOpen] = useState(false);
  const [candidateNotes, setCandidateNotes] = useState('');
  const [submittedApplication, setSubmittedApplication] = useState(null);
  const [circularFallback, setCircularFallback] = useState(null);
  const [isCheckingFallback, setIsCheckingFallback] = useState(false);

  const handlePreviewJobFile = async (jobId, fid, filename) => {
    const toastId = toast.loading(`Opening preview for ${filename || 'document'}...`);
    try {
      await previewJobFileAuth(jobId, fid);
      toast.success('Preview opened', { id: toastId });
    } catch (err) {
      toast.error(err.message || 'Failed to preview file', { id: toastId });
    }
  };

  const handleDownloadJobFile = async (jobId, fid, filename) => {
    const toastId = toast.loading(`Downloading ${filename || 'document'}...`);
    try {
      const downloadedAs = await downloadJobFileAuth(jobId, fid, filename);
      toast.success(`Downloaded ${downloadedAs || filename}`, { id: toastId });
    } catch (err) {
      toast.error(err.message || 'Failed to download file', { id: toastId });
    }
  };

  const jobIdNum = useMemo(() => (id ? parseInt(id, 10) : null), [id]);

  // Load Job and Eligibility data on mount / ID change
  useEffect(() => {
    if (jobIdNum) {
      // Clear any previous eligibility immediately to prevent stale display
      clearJobEligibility();
      setSubmittedApplication(null);
      setCircularFallback(null);

      // Fetch job details; on 404, check if this ID is a recruitment circular fallback
      fetchJobPosting(jobIdNum).catch(async () => {
        try {
          setIsCheckingFallback(true);
          const circ = await getRecruitmentCircular(jobIdNum);
          if (circ && circ.id) {
            setCircularFallback(circ);
          }
        } catch {
          // not a circular either
        } finally {
          setIsCheckingFallback(false);
        }
      });

      // Fetch eligibility for current authenticated student
      if (user?.id) {
        checkJobEligibility(jobIdNum, user.id).catch(() => {});
      }

      // Fetch current student applications and offers to detect if already applied or offered
      if (user?.id) {
        fetchMyApplications(user.id).catch(() => {});
        fetchMyOffers().catch(() => {});
      }
    }

    return () => {
      clearJobEligibility();
    };
  }, [jobIdNum, user?.id]);

  // Check if student has already applied to this job
  const existingApplication = useMemo(() => {
    if (!jobIdNum || !Array.isArray(myApplications)) return null;
    return myApplications.find((app) => app.job_posting_id === jobIdNum) || null;
  }, [jobIdNum, myApplications]);

  const activeApplication = submittedApplication || existingApplication;
  const isAlreadyApplied = Boolean(activeApplication);
  const isExternalConfirmed = Boolean(
    activeApplication?.external_applied_at || activeApplication?.is_external_confirmed
  );

  // Validate HTTP/HTTPS application URL and prevent sensitive path exposure
  const isValidHttpUrl = (urlString) => {
    if (!urlString || typeof urlString !== 'string') return false;
    const trimmed = urlString.trim();
    if (!/^https?:\/\//i.test(trimmed)) return false;
    if (trimmed.includes('/minio/') || trimmed.includes(':9000/') || trimmed.includes('minio:')) {
      return false;
    }
    try {
      const parsed = new URL(trimmed);
      return parsed.protocol === 'http:' || parsed.protocol === 'https:';
    } catch {
      return false;
    }
  };

  const hasValidExternalUrl = useMemo(() => {
    return isValidHttpUrl(selectedJob?.application_url);
  }, [selectedJob?.application_url]);

  // Check if student has a verified placement offer for this job (Stage 3.3.6)
  const jobVerifiedOffer = useMemo(() => {
    if (!jobIdNum || !Array.isArray(myOffers)) return null;
    return myOffers.find((o) => o.job_posting_id === jobIdNum) || null;
  }, [jobIdNum, myOffers]);

  // Guard: Verify eligibility data belongs to the currently viewed job
  const isEligibilityForCurrentJob =
    jobEligibility && eligibilityJobId === jobIdNum;

  // Deadline calculation helper
  const deadlineMeta = useMemo(() => {
    if (!selectedJob?.application_deadline) return null;
    try {
      const deadline = new Date(selectedJob.application_deadline);
      if (isNaN(deadline.getTime())) return null;

      const now = new Date();
      const diffMs = deadline.getTime() - now.getTime();
      const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

      return {
        formatted: deadline.toLocaleDateString(),
        fullDate: deadline.toLocaleString(),
        diffDays,
        isPassed: diffDays < 0,
        isUrgent: diffDays >= 0 && diffDays <= 3,
        badge:
          diffDays < 0
            ? 'Deadline Passed'
            : diffDays === 0
            ? 'Ends Today'
            : diffDays === 1
            ? '1 day left'
            : `${diffDays} days left`,
      };
    } catch {
      return null;
    }
  }, [selectedJob?.application_deadline]);

  // Handle application submission
  const handleOpenApplyModal = () => {
    if (isAlreadyApplied) {
      navigate('/student/applications');
      return;
    }

    if (isEligibilityForCurrentJob && !jobEligibility.is_eligible) {
      toast.error('You do not meet the minimum academic criteria for this position.');
      return;
    }

    setIsApplyModalOpen(true);
  };

  const handleConfirmSubmit = async () => {
    if (!jobIdNum) return;

    try {
      const payload = {
        job_posting_id: jobIdNum,
        ...(candidateNotes.trim() ? { notes: candidateNotes.trim() } : {}),
      };

      const result = await createApplication(payload);
      setSubmittedApplication(result);
      setIsApplyModalOpen(false);
      setCandidateNotes('');
      toast.success('Application submitted successfully!');
    } catch (err) {
      const errMsg =
        err.response?.data?.detail || err.message || 'Failed to submit application';
      toast.error(typeof errMsg === 'string' ? errMsg : 'Application submission failed');
    }
  };

  const handleConfirmExternal = async () => {
    if (!jobIdNum || !selectedJob?.application_url) {
      toast.error('This job does not have an external application URL to confirm.');
      return;
    }

    if (isEligibilityForCurrentJob && !jobEligibility.is_eligible) {
      toast.error('You do not meet the minimum academic criteria for this position.');
      return;
    }

    setIsConfirmingExternal(true);
    try {
      const confirmedApp = await confirmExternalJobApplication(jobIdNum);
      setSubmittedApplication(confirmedApp);
      setIsConfirmModalOpen(false);
      toast.success("External application confirmed successfully! (Student-Reported)");
    } catch (err) {
      const errMsg =
        err.response?.data?.detail || err.message || 'Failed to confirm external application';
      toast.error(typeof errMsg === 'string' ? errMsg : 'Confirmation failed');
    } finally {
      setIsConfirmingExternal(false);
    }
  };

  // 1. Loading State
  if (isJobLoading && !selectedJob) {
    return (
      <div className="space-y-6 pb-12">
        <button
          onClick={() => navigate('/student/jobs')}
          className="flex items-center space-x-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors text-sm cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Campus Jobs</span>
        </button>
        <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 p-8 shadow-sm animate-pulse space-y-6">
          <div className="h-6 bg-gray-200 dark:bg-gray-800 rounded w-1/4"></div>
          <div className="h-8 bg-gray-300 dark:bg-gray-700 rounded w-1/2"></div>
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <div className="h-16 bg-gray-200 dark:bg-gray-800 rounded-xl"></div>
            <div className="h-16 bg-gray-200 dark:bg-gray-800 rounded-xl"></div>
            <div className="h-16 bg-gray-200 dark:bg-gray-800 rounded-xl"></div>
            <div className="h-16 bg-gray-200 dark:bg-gray-800 rounded-xl"></div>
          </div>
          <div className="h-32 bg-gray-200 dark:bg-gray-800 rounded-xl"></div>
        </div>
      </div>
    );
  }

  // 2. Error / Unavailable Job State
  if (jobError || (!isJobLoading && !selectedJob)) {
    return (
      <div className="space-y-6 pb-12">
        <button
          onClick={() => navigate('/student/jobs')}
          className="flex items-center space-x-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors text-sm cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Campus Jobs</span>
        </button>
        {circularFallback ? (
          <div className="text-center py-12 bg-white dark:bg-gray-900 rounded-2xl border border-blue-200 dark:border-blue-900/60 p-8 shadow-sm max-w-xl mx-auto space-y-4">
            <div className="w-14 h-14 bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400 rounded-2xl flex items-center justify-center mx-auto shadow-sm">
              <Megaphone className="w-7 h-7" />
            </div>
            <span className="inline-block px-3 py-1 rounded-full text-xs font-semibold bg-blue-50 dark:bg-blue-950/70 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
              Recruitment Drive Found
            </span>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">
              {circularFallback.title}
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-300 max-w-md mx-auto">
              This reference corresponds to the recruitment drive for <strong>{circularFallback.company_name || 'Campus Recruiter'}</strong>.
              {circularFallback.linked_jobs?.length > 0 && ` Includes ${circularFallback.linked_jobs.length} linked role(s).`}
            </p>
            <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
              <button
                onClick={() => navigate(`/student/jobs/circulars/${circularFallback.id}`)}
                className="w-full sm:w-auto px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold transition-all cursor-pointer flex items-center justify-center gap-2 shadow-sm"
              >
                <span>View Recruitment Drive & Roles</span>
                <ChevronRight className="w-4 h-4" />
              </button>
              {circularFallback.linked_jobs?.length === 1 && circularFallback.linked_jobs[0].job_posting_id && (
                <button
                  onClick={() => navigate(`/student/jobs/${circularFallback.linked_jobs[0].job_posting_id}`)}
                  className="w-full sm:w-auto px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-sm font-semibold transition-colors cursor-pointer flex items-center justify-center gap-1.5 shadow-sm"
                >
                  <span>View Role: {circularFallback.linked_jobs[0].title}</span>
                </button>
              )}
              <button
                onClick={() => navigate('/student/jobs?tab=circulars')}
                className="w-full sm:w-auto px-4 py-2.5 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-xl text-sm font-medium transition-colors cursor-pointer"
              >
                <span>All Circulars</span>
              </button>
            </div>
          </div>
        ) : (
          <div className="text-center py-16 bg-white dark:bg-gray-900 rounded-2xl border border-red-200 dark:border-red-900/60 p-8 shadow-sm">
            <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-3" />
            <h2 className="text-lg font-bold text-gray-900 dark:text-white">Job Posting Not Found or Unavailable</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 max-w-md mx-auto">
              {typeof jobError === 'string'
                ? jobError
                : 'This campus drive may be closed, in draft state, or does not exist.'}
            </p>
            <button
              onClick={() => navigate('/student/jobs')}
              className="mt-5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-semibold transition-colors cursor-pointer inline-flex items-center gap-1.5"
            >
              <span>Return to Campus Jobs</span>
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-16">
      {/* Back Navigation & Breadcrumb */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate('/student/jobs')}
          className="flex items-center space-x-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors text-sm cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Campus Jobs</span>
        </button>

        <div className="flex items-center gap-2">
          {isAlreadyApplied ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-100 dark:bg-blue-950/70 text-blue-800 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Applied</span>
            </span>
          ) : isEligibilityForCurrentJob && jobEligibility.is_eligible ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 dark:bg-emerald-950/70 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Eligible to Apply</span>
            </span>
          ) : isEligibilityForCurrentJob && !jobEligibility.is_eligible ? (
            <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${
              jobEligibility.eligibility_status === 'incomplete_data'
                ? 'bg-amber-100 dark:bg-amber-950/70 text-amber-800 dark:text-amber-300 border-amber-200 dark:border-amber-800'
                : 'bg-rose-100 dark:bg-rose-950/70 text-rose-800 dark:text-rose-300 border-rose-200 dark:border-rose-800'
            }`}>
              {jobEligibility.eligibility_status === 'incomplete_data' ? (
                <AlertTriangle className="w-3.5 h-3.5" />
              ) : (
                <XCircle className="w-3.5 h-3.5" />
              )}
              <span>{jobEligibility.eligibility_status === 'incomplete_data' ? 'Profile Incomplete' : 'Ineligible'}</span>
            </span>
          ) : null}

          <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ${
            selectedJob.status === 'closed'
              ? 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700'
              : 'bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800'
          }`}>
            {selectedJob.status === 'closed' ? '● Closed Drive' : '● Open Drive'}
          </span>
        </div>
      </div>

      {/* Main Header Card */}
      <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 p-6 sm:p-8 shadow-sm">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
          <div className="flex-1 space-y-2">
            <div className="flex items-center gap-2 text-sm font-semibold text-blue-600 dark:text-blue-400">
              <Building2 className="w-4 h-4" />
              <span>{selectedJob.company_name || 'Assigned Company'}</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 dark:text-white tracking-tight">
              {selectedJob.title}
            </h1>
            <p className="text-xs text-gray-400 dark:text-gray-500">
              Drive Reference #{selectedJob.id} • Posted{' '}
              {selectedJob.created_at ? new Date(selectedJob.created_at).toLocaleDateString() : 'Recently'}
            </p>
          </div>

          {/* Quick CTA on Header */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 w-full lg:w-auto">
            {hasValidExternalUrl ? (
              // EXTERNAL JOB WORKFLOW
              <>
                <a
                  href={selectedJob.application_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold transition-all shadow-sm hover:shadow flex items-center justify-center gap-2 cursor-pointer"
                  title="Open company application website in a new tab"
                  id="apply-on-website-btn"
                >
                  <span>Apply on Website</span>
                  <ExternalLink className="w-4 h-4" />
                </a>

                {isExternalConfirmed ? (
                  <div className="flex items-center gap-2">
                    <span
                      className="px-4 py-2.5 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5"
                      title={`Confirmed: ${activeApplication?.external_applied_at ? new Date(activeApplication.external_applied_at).toLocaleString() : 'Recorded'}`}
                    >
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                      <span>Application Confirmed</span>
                    </span>
                    <button
                      onClick={() => navigate('/student/applications')}
                      className="px-4 py-2.5 bg-blue-50 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-700/60 rounded-xl text-xs font-semibold hover:bg-blue-100 dark:hover:bg-blue-900/60 transition-colors cursor-pointer"
                    >
                      View in My Applications
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <span className="px-3 py-2 bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800 rounded-xl text-xs font-semibold flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5 text-amber-600" />
                      <span>Not Yet Confirmed</span>
                    </span>
                    <button
                      onClick={() => setIsConfirmModalOpen(true)}
                      disabled={isConfirmingExternal || (isEligibilityForCurrentJob && !jobEligibility.is_eligible)}
                      className="px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition-all shadow-sm flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                      id="header-confirm-external-btn"
                      data-testid="mark-as-applied-btn"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>{isConfirmingExternal ? 'Recording...' : "Mark as Applied"}</span>
                    </button>
                  </div>
                )}
              </>
            ) : selectedJob?.application_url ? (
              <div className="px-4 py-2 bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800 rounded-xl text-xs font-medium flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                <span>External URL is invalid or unsupported</span>
              </div>
            ) : (
              // INTERNAL DIRECT JOB WORKFLOW (no external URL)
              isAlreadyApplied ? (
                <button
                  onClick={() => navigate('/student/applications')}
                  className="px-5 py-2.5 bg-blue-50 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-700/60 rounded-xl text-sm font-semibold transition-colors flex items-center justify-center gap-2 cursor-pointer hover:bg-blue-100 dark:hover:bg-blue-900/60"
                >
                  <CheckCircle2 className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                  <span>View in My Applications</span>
                </button>
              ) : isEligibilityForCurrentJob && !jobEligibility.is_eligible ? (
                <button
                  disabled
                  className="px-5 py-2.5 bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-500 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 cursor-not-allowed border border-gray-200 dark:border-gray-700"
                  title="You do not meet the minimum eligibility requirements"
                >
                  <XCircle className="w-4 h-4" />
                  <span>Ineligible to Apply</span>
                </button>
              ) : (
                <button
                  onClick={handleOpenApplyModal}
                  disabled={isSubmittingApplication}
                  className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-bold transition-all shadow-sm hover:shadow flex items-center justify-center gap-2 cursor-pointer"
                >
                  <Send className="w-4 h-4" />
                  <span>{jobEligibility?.has_low_match_warning ? 'Apply with Skill Advisory' : 'Apply Now'}</span>
                </button>
              )
            )}
          </div>
        </div>

        {/* Highlighted Meta Strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 pt-6 border-t border-gray-100 dark:border-gray-800">
          <div className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-800/40 rounded-xl">
            <div className="p-2 bg-blue-100 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400 rounded-lg">
              <MapPin className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <p className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase">Location</p>
              <p className="text-xs font-semibold text-gray-900 dark:text-white truncate">
                {selectedJob.location || 'Not Specified'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-800/40 rounded-xl">
            <div className="p-2 bg-emerald-100 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 rounded-lg">
              <Banknote className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <p className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase">Salary / CTC</p>
              <p className="text-xs font-semibold text-gray-900 dark:text-white truncate">
                {selectedJob.salary_range || 'Not Disclosed'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-800/40 rounded-xl">
            <div className="p-2 bg-amber-100 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400 rounded-lg">
              <Clock className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <p className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase">Deadline</p>
              <p
                className={`text-xs font-semibold truncate ${
                  deadlineMeta?.isUrgent
                    ? 'text-amber-600 dark:text-amber-400'
                    : 'text-gray-900 dark:text-white'
                }`}
                title={deadlineMeta?.fullDate || 'No deadline specified'}
              >
                {deadlineMeta ? deadlineMeta.formatted : 'Not specified'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-800/40 rounded-xl">
            <div className="p-2 bg-purple-100 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400 rounded-lg">
              <Award className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <p className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase">Experience</p>
              <p className="text-xs font-semibold text-gray-900 dark:text-white truncate">
                {selectedJob.experience_level || 'Freshers / Any'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Verified Placement Offer Banner (Stage 3.3.6) */}
      {jobVerifiedOffer && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="p-1 rounded-md bg-emerald-100 dark:bg-emerald-950/70 text-emerald-600 dark:text-emerald-400">
              <Award className="w-4 h-4" />
            </span>
            <h3 className="text-sm font-bold text-gray-900 dark:text-white">
              Official Placement Offer Extended for This Position
            </h3>
          </div>
          <StudentVerifiedOfferCard
            offer={jobVerifiedOffer}
            onOfferUpdated={() => {
              fetchMyOffers().catch(() => {});
              if (user?.id) fetchMyApplications(user.id).catch(() => {});
            }}
          />
        </div>
      )}

      {/* Main Content Layout: 2 Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column (Job Details & Requirements): 7 Columns */}
        <div className="lg:col-span-7 space-y-6">
          {/* Job Description Card */}
          <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 p-6 shadow-sm space-y-3">
            <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <FileText className="w-4 h-4 text-blue-600 dark:text-blue-400" />
              <span>Job Description & Role Overview</span>
            </h2>
            <div className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-line">
              {selectedJob.description && selectedJob.description.trim() ? (
                selectedJob.description
              ) : (
                <p className="italic text-gray-400 dark:text-gray-500">
                  No detailed description has been provided for this drive posting.
                </p>
              )}
            </div>
          </div>

          {/* Official Company Application Portal Card */}
          <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
                <ExternalLink className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                <span>Official Company Application Portal</span>
              </h2>
              {selectedJob.application_url && (
                <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                  External Portal
                </span>
              )}
            </div>

            {selectedJob.application_url ? (
              <div className="space-y-3">
                <p className="text-xs text-gray-600 dark:text-gray-300 leading-relaxed">
                  This recruitment drive requires submitting an application directly on the employer's official career portal or job website.
                </p>

                <div className="p-3.5 bg-blue-50/70 dark:bg-blue-950/30 border border-blue-200/80 dark:border-blue-800/60 rounded-xl text-xs text-blue-900 dark:text-blue-200 flex items-start gap-2.5">
                  <Info className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="font-semibold">Important instructions:</p>
                    <ol className="list-decimal list-inside space-y-0.5 text-blue-800 dark:text-blue-300 text-[11px]">
                      <li>Click <strong>Apply on Website</strong> below to open the official application form in a new tab.</li>
                      <li>Complete and submit your application on the company's website.</li>
                      <li>Return to EduMatrix after applying. Opening the external URL does not automatically record your application.</li>
                    </ol>
                  </div>
                </div>

                <div className="pt-1 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                  <a
                    href={selectedJob.application_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center justify-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-bold transition-all shadow-sm hover:shadow cursor-pointer"
                    id="apply-on-website-body-btn"
                  >
                    <span>Apply on Website</span>
                    <ExternalLink className="w-4 h-4" />
                  </a>

                  {isExternalConfirmed ? (
                    <div className="flex items-center gap-2 px-4 py-2 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300 rounded-xl text-xs font-semibold">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                      <span>
                        Application Confirmed{' '}
                        {activeApplication?.external_applied_at &&
                          `(${new Date(activeApplication.external_applied_at).toLocaleDateString()})`}
                      </span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <span className="px-3 py-2 bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800 rounded-xl text-xs font-semibold flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5 text-amber-600" />
                        <span>Not Yet Confirmed</span>
                      </span>
                      <button
                        onClick={() => setIsConfirmModalOpen(true)}
                        disabled={isConfirmingExternal || (isEligibilityForCurrentJob && !jobEligibility.is_eligible)}
                        className="inline-flex items-center justify-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-sm font-bold transition-all shadow-sm hover:shadow cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                        id="confirm-external-application-btn"
                        data-testid="mark-as-applied-body-btn"
                      >
                        <CheckCircle2 className="w-4 h-4" />
                        <span>{isConfirmingExternal ? 'Recording...' : "Mark as Applied"}</span>
                      </button>
                    </div>
                  )}
                </div>

                {isExternalConfirmed ? (
                  <div className="p-3 bg-emerald-50/60 dark:bg-emerald-950/30 border border-emerald-200/60 dark:border-emerald-800/50 rounded-xl text-xs text-emerald-900 dark:text-emerald-200 flex items-start gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold">Student-confirmed external submission recorded.</p>
                      <p className="text-[11px] text-emerald-800 dark:text-emerald-300 mt-0.5">
                        Your confirmation timestamp ({activeApplication?.external_applied_at ? new Date(activeApplication.external_applied_at).toLocaleString() : 'Recorded'}) is linked to your application record. Placement Cell will be able to view your confirmed status.
                      </p>
                    </div>
                  </div>
                ) : (
                  <p className="text-[11px] text-gray-500 dark:text-gray-400 italic">
                    Click <strong>Mark as Applied</strong> only after completing your submission on the external portal.
                  </p>
                )}
              </div>
            ) : (
              <div className="p-3.5 bg-gray-50 dark:bg-gray-800/40 rounded-xl border border-gray-200 dark:border-gray-800 text-xs text-gray-500 dark:text-gray-400 flex items-center gap-2">
                <Info className="w-4 h-4 text-gray-400 shrink-0" />
                <span>External application link not provided yet. Please check back later or monitor placement cell circulars.</span>
              </div>
            )}
          </div>

          {/* Academic Criteria Card */}
          <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 p-6 shadow-sm space-y-4">
            <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <GraduationCap className="w-4 h-4 text-blue-600 dark:text-blue-400" />
              <span>Academic Eligibility Requirements</span>
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-4 bg-gray-50 dark:bg-gray-800/40 rounded-xl border border-gray-200 dark:border-gray-800">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  Minimum CGPA Cutoff
                </span>
                <p className="text-lg font-bold text-gray-900 dark:text-white mt-1">
                  {selectedJob.cgpa_criteria !== null && selectedJob.cgpa_criteria !== undefined
                    ? `${selectedJob.cgpa_criteria} / 10.0`
                    : 'No CGPA Cutoff (Open)'}
                </p>
                <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5">
                  Your academic record must meet or exceed this value.
                </p>
              </div>

              <div className="p-4 bg-gray-50 dark:bg-gray-800/40 rounded-xl border border-gray-200 dark:border-gray-800">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  Eligible Branches
                </span>
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {selectedJob.branch_eligibility && selectedJob.branch_eligibility.length > 0 ? (
                    selectedJob.branch_eligibility.map((branch, idx) => (
                      <span
                        key={idx}
                        className="text-xs px-2 py-0.5 bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800 rounded-md font-semibold"
                      >
                        {branch}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                      All Academic Branches Eligible
                    </span>
                  )}
                </div>
              </div>
            </div>

            {selectedJob.drive_date && (
              <div className="p-3 bg-blue-50/60 dark:bg-blue-950/30 rounded-xl border border-blue-100 dark:border-blue-900/60 flex items-center gap-2.5 text-xs text-blue-900 dark:text-blue-200">
                <Calendar className="w-4 h-4 text-blue-600 dark:text-blue-400 flex-shrink-0" />
                <span>
                  <strong>On-Campus Drive Date:</strong>{' '}
                  {new Date(selectedJob.drive_date).toLocaleDateString()}
                </span>
              </div>
            )}
          </div>

          {/* Attached Job Documents & Circulars */}
          {(() => {
            const attachmentsList = [...(selectedJob.attachments || [])];
            if (selectedJob.file_id) {
              const exists = attachmentsList.some(
                (a) => String(a.file_id || a.id) === String(selectedJob.file_id)
              );
              if (!exists) {
                attachmentsList.unshift({
                  id: selectedJob.file_id,
                  file_id: selectedJob.file_id,
                  filename: selectedJob.file_name || 'Job Description Document',
                  file_name: selectedJob.file_name || 'Job Description Document',
                  file_size: null,
                });
              }
            }

            if (attachmentsList.length === 0) return null;

            return (
              <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 p-6 shadow-sm space-y-3">
                <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
                  <FileText className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                  <span>Official Job Documents & Criteria ({attachmentsList.length})</span>
                </h2>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Official documents provided by the Placement Cell for this recruitment opening.
                </p>
                <div className="space-y-2 mt-2">
                  {attachmentsList.map((att) => {
                    const fid = att.file_id || att.id;
                    const name = att.filename || att.file_name || 'Attached Document';
                    const previewUrl = getJobFilePreviewUrl(selectedJob.id, fid);
                    const downloadUrl = getJobFileDownloadUrl(selectedJob.id, fid);

                    return (
                      <div
                        key={att.id || fid}
                        className="p-3 bg-gray-50 dark:bg-gray-800/60 rounded-xl border border-gray-200 dark:border-gray-700/60 flex items-center justify-between gap-3"
                      >
                        <div className="flex items-center gap-2.5 min-w-0">
                          <FileText className="w-4 h-4 text-indigo-500 shrink-0" />
                          <div className="min-w-0">
                            <p className="text-xs font-semibold text-gray-900 dark:text-white truncate" title={name}>
                              {name}
                            </p>
                            <p className="text-[10px] text-gray-500">
                              {att.file_size ? `${(att.file_size / 1024).toFixed(1)} KB` : 'Attached Document'}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <button
                            type="button"
                            onClick={() => handlePreviewJobFile(selectedJob.id, fid, name)}
                            className="px-3 py-1 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:text-indigo-600 border border-gray-200 dark:border-gray-700 rounded-lg text-xs font-semibold cursor-pointer transition-colors"
                          >
                            Preview
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDownloadJobFile(selectedJob.id, fid, name)}
                            className="px-3 py-1 bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 border border-indigo-200 dark:border-indigo-800 rounded-lg text-xs font-semibold cursor-pointer transition-colors"
                          >
                            Download
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })()}

          {/* Skill Requirements Catalog Card */}
          <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 p-6 shadow-sm space-y-4">
            <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
              <span>Configured Skill Requirements (80% / 20% Formula)</span>
            </h2>

            {/* Required Skills */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-gray-700 dark:text-gray-300">
                  Required Skills (80% Weightage)
                </span>
                <span className="text-gray-400">
                  {selectedJob.required_skills?.length || 0} skills
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {selectedJob.required_skills && selectedJob.required_skills.length > 0 ? (
                  selectedJob.required_skills.map((skill, idx) => (
                    <span
                      key={idx}
                      className="px-2.5 py-1 bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 rounded-lg text-xs font-medium"
                    >
                      {skill}
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-gray-400 italic">None specified</span>
                )}
              </div>
            </div>

            {/* Preferred Skills */}
            <div className="space-y-2 pt-2 border-t border-gray-100 dark:border-gray-800">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-gray-700 dark:text-gray-300">
                  Preferred / Bonus Skills (20% Weightage)
                </span>
                <span className="text-gray-400">
                  {selectedJob.preferred_skills?.length || 0} skills
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {selectedJob.preferred_skills && selectedJob.preferred_skills.length > 0 ? (
                  selectedJob.preferred_skills.map((skill, idx) => (
                    <span
                      key={idx}
                      className="px-2.5 py-1 bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800 rounded-lg text-xs font-medium"
                    >
                      {skill}
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-gray-400 italic">None specified</span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Right Column (Eligibility & Skill-Match Analysis Card): 5 Columns */}
        <div className="lg:col-span-5 space-y-6">
          {/* Main Analysis Card */}
          <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 p-6 shadow-sm space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                <span>Your Skill-Match & Eligibility</span>
              </h2>

              <button
                onClick={() => {
                  if (jobIdNum && user?.id) {
                    checkJobEligibility(jobIdNum, user.id).catch(() => {});
                  }
                }}
                disabled={isEligibilityLoading}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1 cursor-pointer disabled:opacity-50"
                title="Re-run matching check"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isEligibilityLoading ? 'animate-spin' : ''}`} />
                <span>Re-check</span>
              </button>
            </div>

            {/* Eligibility State: Loading */}
            {isEligibilityLoading && !isEligibilityForCurrentJob ? (
              <div className="py-12 text-center space-y-3">
                <div className="w-9 h-9 border-3 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto" />
                <p className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                  Evaluating skill alignment and criteria...
                </p>
                <p className="text-[11px] text-gray-400">
                  Comparing profile and latest uploaded resume against requirements
                </p>
              </div>
            ) : eligibilityError ? (
              // Eligibility State: Error
              <div className="p-4 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/60 rounded-xl text-center space-y-2">
                <AlertCircle className="w-6 h-6 text-red-500 mx-auto" />
                <p className="text-xs font-semibold text-red-900 dark:text-red-200">
                  Failed to evaluate eligibility
                </p>
                <p className="text-[11px] text-red-700 dark:text-red-300">{eligibilityError}</p>
                <button
                  onClick={() => checkJobEligibility(jobIdNum, user?.id)}
                  className="px-3 py-1 bg-red-600 text-white rounded-md text-xs font-semibold cursor-pointer"
                >
                  Retry Analysis
                </button>
              </div>
            ) : isEligibilityForCurrentJob ? (
              // Eligibility State: Populated
              <div className="space-y-5">
                {/* Score Hero Banner */}
                <div className="p-4 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/40 dark:to-indigo-950/40 border border-blue-200 dark:border-blue-800/60 rounded-xl">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-medium text-gray-600 dark:text-gray-400 uppercase tracking-wider">
                        Overall Match Score
                      </p>
                      <p className="text-3xl font-black text-gray-900 dark:text-white mt-1">
                        {jobEligibility.overall_skill_match !== null &&
                        jobEligibility.overall_skill_match !== undefined
                          ? `${Math.round(jobEligibility.overall_skill_match)}%`
                          : jobEligibility.skill_match !== null &&
                            jobEligibility.skill_match !== undefined
                          ? `${Math.round(jobEligibility.skill_match)}%`
                          : 'Not calculated'}
                      </p>
                    </div>

                    <div className="text-right space-y-1 text-xs">
                      <div className="font-medium text-gray-600 dark:text-gray-300">
                        Required Match:{' '}
                        <span className="font-bold text-indigo-700 dark:text-indigo-300">
                          {jobEligibility.required_score !== null &&
                          jobEligibility.required_score !== undefined
                            ? `${Math.round(jobEligibility.required_score)}%`
                            : 'N/A'}
                        </span>
                      </div>
                      <div className="font-medium text-gray-600 dark:text-gray-300">
                        Preferred Match:{' '}
                        <span className="font-bold text-teal-700 dark:text-teal-300">
                          {jobEligibility.preferred_score !== null &&
                          jobEligibility.preferred_score !== undefined
                            ? `${Math.round(jobEligibility.preferred_score)}%`
                            : 'Not applicable'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {jobEligibility.resume_filename && (
                    <div className="mt-3 pt-2.5 border-t border-blue-200/60 dark:border-blue-800/60 flex items-center gap-1.5 text-[11px] text-gray-500 dark:text-gray-400">
                      <FileText className="w-3.5 h-3.5 text-blue-500" />
                      <span className="truncate">
                        Profile & Resume Source: <strong>{jobEligibility.resume_filename}</strong>
                      </span>
                    </div>
                  )}
                </div>

                {/* Explicit Academic Criteria Status */}
                <div className="space-y-2">
                  <p className="text-xs font-bold text-gray-900 dark:text-white uppercase tracking-wider">
                    Academic Criteria Verification
                  </p>
                  <div className="space-y-2 text-xs">
                    {/* CGPA Check */}
                    <div className="flex items-center justify-between p-2.5 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-100 dark:border-gray-800">
                      <div className="flex items-center gap-2">
                        {jobEligibility.cgpa_match ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                        ) : (
                          <XCircle className="w-4 h-4 text-rose-500 flex-shrink-0" />
                        )}
                        <span className="text-gray-700 dark:text-gray-300">
                          CGPA Criteria ({selectedJob.cgpa_criteria !== null ? selectedJob.cgpa_criteria : 'None'})
                        </span>
                      </div>
                      <span
                        className={`font-semibold ${
                          jobEligibility.cgpa_match
                            ? 'text-emerald-700 dark:text-emerald-400'
                            : 'text-rose-700 dark:text-rose-400'
                        }`}
                      >
                        {jobEligibility.cgpa_match ? `Met (${jobEligibility.cgpa})` : `Failed (${jobEligibility.cgpa})`}
                      </span>
                    </div>

                    {/* Branch Check */}
                    <div className="flex items-center justify-between p-2.5 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-100 dark:border-gray-800">
                      <div className="flex items-center gap-2">
                        {jobEligibility.branch_match ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                        ) : (
                          <XCircle className="w-4 h-4 text-rose-500 flex-shrink-0" />
                        )}
                        <span className="text-gray-700 dark:text-gray-300">
                          Branch Criteria ({selectedJob.branch_eligibility?.length ? selectedJob.branch_eligibility.join(', ') : 'All'})
                        </span>
                      </div>
                      <span
                        className={`font-semibold ${
                          jobEligibility.branch_match
                            ? 'text-emerald-700 dark:text-emerald-400'
                            : 'text-rose-700 dark:text-rose-400'
                        }`}
                      >
                        {jobEligibility.branch_match ? `Eligible (${jobEligibility.branch})` : `Ineligible (${jobEligibility.branch})`}
                      </span>
                    </div>
                  </div>

                  {/* Explicit Eligibility Banner */}
                  {jobEligibility.is_eligible ? (
                    <div className="p-3 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/80 rounded-xl text-xs text-emerald-900 dark:text-emerald-200 flex items-start gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 flex-shrink-0 mt-0.5" />
                      <div>
                        <strong>Eligible to Apply:</strong> You meet all mandatory academic eligibility requirements for this drive.
                      </div>
                    </div>
                  ) : jobEligibility.eligibility_status === 'incomplete_data' ? (
                    <div className="p-3 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/80 rounded-xl text-xs text-amber-900 dark:text-amber-200 flex items-start gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                      <div>
                        <strong>Incomplete Academic Profile:</strong>
                        <ul className="list-disc pl-4 mt-1 space-y-0.5">
                          {jobEligibility.eligibility_reasons?.length > 0 ? (
                            jobEligibility.eligibility_reasons.map((r, i) => <li key={i}>{r}</li>)
                          ) : (
                            <li>Your profile is missing academic criteria needed to determine eligibility. Please update your student profile.</li>
                          )}
                        </ul>
                      </div>
                    </div>
                  ) : (
                    <div className="p-3 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800/80 rounded-xl text-xs text-rose-900 dark:text-rose-200 flex items-start gap-2">
                      <XCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 flex-shrink-0 mt-0.5" />
                      <div>
                        <strong>Ineligible to Apply:</strong>
                        <ul className="list-disc pl-4 mt-1 space-y-0.5">
                          {jobEligibility.eligibility_reasons?.length > 0 ? (
                            jobEligibility.eligibility_reasons.map((r, i) => <li key={i}>{r}</li>)
                          ) : (
                            <li>You do not meet the academic criteria configured for this drive.</li>
                          )}
                        </ul>
                      </div>
                    </div>
                  )}
                </div>

                {/* Low Match Warning Banner (<50% required skill match) */}
                {jobEligibility.has_low_match_warning && (
                  <div className="p-3.5 bg-amber-50 dark:bg-amber-950/50 border border-amber-300 dark:border-amber-800 rounded-xl text-xs text-amber-900 dark:text-amber-200 flex items-start gap-2.5">
                    <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <strong className="block font-bold">Skill Advisory Warning:</strong>
                      <span>
                        {jobEligibility.low_match_warning ||
                          `Your required skill match is currently ${jobEligibility.required_score}%, which is below the 50% threshold.`}
                      </span>
                      <p className="mt-1 text-[11px] text-amber-800 dark:text-amber-300">
                        You meet academic eligibility and <strong>are permitted to apply</strong>, but strengthening your missing skills prior to interviews is strongly recommended.
                      </p>
                    </div>
                  </div>
                )}

                {/* Matched vs Missing Skills Breakdown */}
                <div className="space-y-3 pt-2 border-t border-gray-100 dark:border-gray-800">
                  <p className="text-xs font-bold text-gray-900 dark:text-white uppercase tracking-wider">
                    Skills Breakdown
                  </p>

                  {/* Matched Required Skills */}
                  <div className="space-y-1.5">
                    <span className="text-[11px] font-semibold text-emerald-700 dark:text-emerald-400 flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Matched Required Skills ({jobEligibility.matched_required_skills?.length || 0})</span>
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {jobEligibility.matched_required_skills?.length > 0 ? (
                        jobEligibility.matched_required_skills.map((s, idx) => (
                          <span
                            key={idx}
                            className="px-2 py-0.5 bg-emerald-50 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 rounded-md text-[11px] font-medium"
                          >
                            ✓ {s}
                          </span>
                        ))
                      ) : (
                        <span className="text-[11px] text-gray-400 italic">No required skills matched</span>
                      )}
                    </div>
                  </div>

                  {/* Missing Required Skills */}
                  <div className="space-y-1.5">
                    <span className="text-[11px] font-semibold text-rose-700 dark:text-rose-400 flex items-center gap-1">
                      <XCircle className="w-3.5 h-3.5" />
                      <span>Missing Required Skills ({jobEligibility.missing_required_skills?.length || 0})</span>
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {jobEligibility.missing_required_skills?.length > 0 ? (
                        jobEligibility.missing_required_skills.map((s, idx) => (
                          <span
                            key={idx}
                            className="px-2 py-0.5 bg-rose-50 dark:bg-rose-950/60 text-rose-800 dark:text-rose-300 border border-rose-200 dark:border-rose-800 rounded-md text-[11px] font-medium"
                          >
                            ✗ {s}
                          </span>
                        ))
                      ) : (
                        <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
                          All required skills matched!
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Preferred Skills */}
                  {(jobEligibility.matched_preferred_skills?.length > 0 ||
                    jobEligibility.missing_preferred_skills?.length > 0) && (
                    <div className="space-y-1.5 pt-2">
                      <span className="text-[11px] font-semibold text-teal-700 dark:text-teal-400 flex items-center gap-1">
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>Preferred / Bonus Skills</span>
                      </span>
                      <div className="flex flex-wrap gap-1">
                        {jobEligibility.matched_preferred_skills?.map((s, idx) => (
                          <span
                            key={`p-m-${idx}`}
                            className="px-2 py-0.5 bg-teal-50 dark:bg-teal-950/60 text-teal-800 dark:text-teal-300 border border-teal-200 dark:border-teal-800 rounded-md text-[11px] font-medium"
                          >
                            ✓ {s}
                          </span>
                        ))}
                        {jobEligibility.missing_preferred_skills?.map((s, idx) => (
                          <span
                            key={`p-mis-${idx}`}
                            className="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 rounded-md text-[11px]"
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Semantic Skill Alignments */}
                  {jobEligibility.semantic_matches?.length > 0 && (
                    <div className="mt-2 p-2.5 bg-indigo-50/60 dark:bg-indigo-950/30 rounded-lg border border-indigo-100 dark:border-indigo-900/40 text-[11px] space-y-1 text-indigo-900 dark:text-indigo-200">
                      <p className="font-semibold flex items-center gap-1">
                        <Sparkles className="w-3 h-3 text-indigo-600 dark:text-indigo-400" />
                        <span>Semantic Skill Matches (MiniLM):</span>
                      </p>
                      {jobEligibility.semantic_matches.map((sm, i) => (
                        <p key={i} className="text-gray-600 dark:text-gray-300 pl-4">
                          • {sm.required_skill || sm.skill} matched with{' '}
                          <strong>"{sm.matched_with || sm.student_skill}"</strong> ({Math.round((sm.similarity || 0) * 100)}% similarity)
                        </p>
                      ))}
                    </div>
                  )}

                  {/* Match Explanations */}
                  {jobEligibility.skill_match_explanations?.length > 0 && (
                    <div className="mt-2 p-2.5 bg-gray-50 dark:bg-gray-800/60 rounded-lg border border-gray-200 dark:border-gray-700/60 text-[11px] space-y-1.5 text-gray-800 dark:text-gray-200">
                      <p className="font-semibold flex items-center gap-1 text-gray-900 dark:text-white">
                        <Info className="w-3.5 h-3.5 text-blue-500" />
                        <span>Match Explanations:</span>
                      </p>
                      <div className="space-y-1 pl-1">
                        {jobEligibility.skill_match_explanations.map((exp, idx) => (
                          <div key={idx} className="flex items-start gap-1.5 text-gray-600 dark:text-gray-300">
                            <span className="text-blue-500">•</span>
                            <span>{exp.explanation || `${exp.skill}: matched via ${exp.category}`}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-center py-6 text-xs text-gray-500">
                Click "Re-check" to evaluate your skill alignment.
              </div>
            )}

            {/* Application Action Button (Sticky in sidebar) */}
            <div className="pt-4 border-t border-gray-100 dark:border-gray-800">
              {isAlreadyApplied ? (
                <div className="space-y-2">
                  <div className="p-3 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded-xl text-center">
                    <p className="text-xs font-semibold text-blue-900 dark:text-blue-200">
                      Application Submitted
                    </p>
                    <p className="text-[11px] text-blue-700 dark:text-blue-300 mt-0.5">
                      Status: <strong>{activeApplication.status?.toUpperCase() || 'APPLIED'}</strong>
                    </p>
                  </div>
                  <button
                    onClick={() => setIsTimelineOpen(true)}
                    className="w-full py-2 px-4 bg-purple-50 dark:bg-purple-950/40 hover:bg-purple-100 dark:hover:bg-purple-900/60 border border-purple-200 dark:border-purple-800 text-purple-700 dark:text-purple-300 rounded-xl text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
                    title="View recruitment rounds progression timeline for this drive"
                  >
                    <TrendingUp className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                    <span>Recruitment Timeline</span>
                  </button>

                  <button
                    onClick={() => navigate('/student/applications')}
                    className="w-full py-2 px-4 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-800 dark:text-gray-200 rounded-xl text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
                  >
                    <span>View in Applications</span>
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              ) : isEligibilityForCurrentJob && !jobEligibility.is_eligible ? (
                <div className="space-y-2">
                  <button
                    disabled
                    className="w-full py-2.5 px-4 bg-gray-200 dark:bg-gray-800 text-gray-400 dark:text-gray-500 rounded-xl text-xs font-semibold cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    <XCircle className="w-4 h-4" />
                    <span>Ineligible to Apply</span>
                  </button>
                  <p className="text-[11px] text-gray-400 text-center">
                    Cannot apply due to unmet CGPA or branch requirements.
                  </p>
                </div>
              ) : (
                <button
                  onClick={handleOpenApplyModal}
                  disabled={isSubmittingApplication}
                  className="w-full py-3 px-4 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-bold transition-all shadow-sm hover:shadow flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                >
                  <Send className="w-4 h-4" />
                  <span>
                    {jobEligibility?.has_low_match_warning ? 'Apply with Skill Advisory' : 'Apply for this Job'}
                  </span>
                </button>
              )}
            </div>

            {/* External Application Portal CTA in Sidebar */}
            {selectedJob.application_url ? (
              <div className="pt-3 border-t border-gray-100 dark:border-gray-800 space-y-2">
                <a
                  href={selectedJob.application_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition-all shadow-sm hover:shadow flex items-center justify-center gap-2 cursor-pointer"
                >
                  <ExternalLink className="w-4 h-4" />
                  <span>Apply on Company Website</span>
                </a>
                {isExternalConfirmed ? (
                  <div className="p-2.5 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-xl text-center space-y-0.5">
                    <div className="flex items-center justify-center gap-1.5 text-xs font-bold text-emerald-800 dark:text-emerald-300">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                      <span>External Applied</span>
                    </div>
                    <p className="text-[10px] text-emerald-700 dark:text-emerald-400">
                      Confirmed on{' '}
                      {activeApplication?.external_applied_at
                        ? new Date(activeApplication.external_applied_at).toLocaleDateString()
                        : 'Recorded'}
                    </p>
                  </div>
                ) : (
                  <button
                    onClick={() => setIsConfirmModalOpen(true)}
                    disabled={isConfirmingExternal || (isEligibilityForCurrentJob && !jobEligibility.is_eligible)}
                    className="w-full py-2 px-3 bg-emerald-700 hover:bg-emerald-800 text-white rounded-xl text-xs font-bold transition-all shadow-sm flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>{isConfirmingExternal ? 'Confirming...' : "I've Applied"}</span>
                  </button>
                )}
                <p className="text-[11px] text-gray-500 dark:text-gray-400 text-center leading-normal">
                  Opens external website in a new tab. Remember to confirm after applying.
                </p>
              </div>
            ) : (
              <div className="pt-3 border-t border-gray-100 dark:border-gray-800">
                <p className="text-[11px] text-gray-400 dark:text-gray-500 text-center italic">
                  External application link not provided yet.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Application Submission Confirmation Modal */}
      {isApplyModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-lg w-full p-6 shadow-xl border border-gray-200 dark:border-gray-800 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100 dark:border-gray-800">
              <div className="flex items-center gap-2 text-gray-900 dark:text-white font-bold text-lg">
                <Send className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                <span>Confirm Placement Application</span>
              </div>
              <button
                onClick={() => setIsApplyModalOpen(false)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Target Job Summary */}
            <div className="p-3.5 bg-gray-50 dark:bg-gray-800/60 rounded-xl border border-gray-200 dark:border-gray-700/60 space-y-1">
              <p className="text-xs text-gray-500 dark:text-gray-400 font-medium">Position:</p>
              <p className="text-sm font-bold text-gray-900 dark:text-white">{selectedJob.title}</p>
              <p className="text-xs text-gray-600 dark:text-gray-300">
                Company: <strong>{selectedJob.company_name || 'Assigned Company'}</strong>
              </p>
            </div>

            {/* Student Candidate Identification */}
            <div className="grid grid-cols-2 gap-2 text-xs text-gray-600 dark:text-gray-300 p-3 bg-gray-50 dark:bg-gray-800/40 rounded-xl">
              <div>
                <span className="text-gray-400">Applicant:</span>{' '}
                <strong>{user?.name || 'Current Student'}</strong>
              </div>
              <div>
                <span className="text-gray-400">Branch:</span>{' '}
                <strong>{jobEligibility?.branch || user?.department || 'Student'}</strong>
              </div>
              <div>
                <span className="text-gray-400">CGPA:</span>{' '}
                <strong>{jobEligibility?.cgpa || 'On File'}</strong>
              </div>
              <div>
                <span className="text-gray-400">Preview Match:</span>{' '}
                <strong>
                  {jobEligibility?.overall_skill_match !== null && jobEligibility?.overall_skill_match !== undefined
                    ? `${Math.round(jobEligibility.overall_skill_match)}%`
                    : 'Server authoritative'}
                </strong>
              </div>
            </div>

            {/* Low Match Advisory Box if Applicable */}
            {jobEligibility?.has_low_match_warning && (
              <div className="p-3 bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 rounded-xl text-xs text-amber-900 dark:text-amber-200 space-y-1">
                <div className="flex items-center gap-1.5 font-bold">
                  <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0" />
                  <span>Low Required-Skill Advisory</span>
                </div>
                <p>
                  Your required skill match is <strong>{jobEligibility.required_score}%</strong>, below the 50% threshold.
                  Your application will be submitted and server-scored.
                </p>
              </div>
            )}

            {/* Candidate Notes (Optional) */}
            <div className="space-y-1">
              <label
                htmlFor="student-application-notes"
                className="text-xs font-semibold text-gray-700 dark:text-gray-300"
              >
                Cover Note / Message to Placement Team (Optional)
              </label>
              <textarea
                id="student-application-notes"
                rows={3}
                placeholder="Mention relevant project links, certifications, or key strengths..."
                value={candidateNotes}
                onChange={(e) => setCandidateNotes(e.target.value)}
                className="w-full p-2.5 text-xs border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-end gap-3 pt-3 border-t border-gray-100 dark:border-gray-800">
              <button
                type="button"
                onClick={() => setIsApplyModalOpen(false)}
                disabled={isSubmittingApplication}
                className="px-4 py-2 text-xs font-semibold text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmSubmit}
                disabled={isSubmittingApplication}
                className="px-5 py-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                {isSubmittingApplication ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Submitting Application...</span>
                  </>
                ) : (
                  <>
                    <Send className="w-3.5 h-3.5" />
                    <span>Confirm & Apply</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* External Application Confirmation Modal */}
      {isConfirmModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-lg w-full p-6 shadow-xl border border-gray-200 dark:border-gray-800 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100 dark:border-gray-800">
              <div className="flex items-center gap-2 text-gray-900 dark:text-white font-bold text-lg">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                <span>Confirm External Application</span>
              </div>
              <button
                onClick={() => setIsConfirmModalOpen(false)}
                disabled={isConfirmingExternal}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-3.5 bg-gray-50 dark:bg-gray-800/60 rounded-xl border border-gray-200 dark:border-gray-700/60 space-y-1">
              <p className="text-xs text-gray-500 dark:text-gray-400 font-medium">Opportunity:</p>
              <p className="text-sm font-bold text-gray-900 dark:text-white">{selectedJob.title}</p>
              <p className="text-xs text-gray-600 dark:text-gray-300">
                Company: <strong>{selectedJob.company_name || 'Assigned Company'}</strong>
              </p>
            </div>

            <div className="p-3.5 bg-blue-50/70 dark:bg-blue-950/40 border border-blue-200/80 dark:border-blue-800/60 rounded-xl text-xs text-blue-900 dark:text-blue-200 space-y-2">
              <div className="flex items-center gap-1.5 font-bold">
                <Info className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0" />
                <span>Student-Reported Confirmation Notice</span>
              </div>
              <p className="text-[11px] leading-relaxed text-blue-800 dark:text-blue-300">
                <strong>Important:</strong> This is a student-reported confirmation and does <em>not</em> verify your application with the employer.
              </p>
              <p className="text-[11px] text-blue-700 dark:text-blue-400">
                Confirm only after you have finished applying on the company website. EduMatrix will record your official confirmation timestamp and link your profile to this recruitment drive.
              </p>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-gray-100 dark:border-gray-800">
              <button
                type="button"
                onClick={() => setIsConfirmModalOpen(false)}
                disabled={isConfirmingExternal}
                className="px-4 py-2 text-xs font-semibold text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmExternal}
                disabled={isConfirmingExternal}
                className="px-5 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                id="modal-confirm-external-btn"
                data-testid="modal-mark-as-applied-btn"
              >
                {isConfirmingExternal ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Recording Application...</span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Mark as Applied</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Post-Submission Confirmation Card / Banner */}
      {submittedApplication && (
        <div className="fixed bottom-6 right-6 z-40 max-w-md w-full bg-white dark:bg-gray-900 rounded-2xl border border-emerald-300 dark:border-emerald-800 p-5 shadow-2xl animate-in slide-in-from-bottom duration-300 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-400 font-bold text-sm">
              <CheckCircle2 className="w-5 h-5" />
              <span>Application Successfully Recorded</span>
            </div>
            <button
              onClick={() => setSubmittedApplication(null)}
              className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <p className="text-xs text-gray-600 dark:text-gray-300">
            Application ID <strong>#{submittedApplication.id}</strong> recorded. Authoritative server match score:{' '}
            <strong>
              {submittedApplication.match_percentage !== null && submittedApplication.match_percentage !== undefined
                ? `${Math.round(submittedApplication.match_percentage)}%`
                : 'Recorded'}
            </strong>
          </p>

          <div className="flex items-center gap-2 pt-1">
            <button
              onClick={() => navigate('/student/applications')}
              className="flex-1 py-1.5 px-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold transition-colors flex items-center justify-center gap-1 cursor-pointer"
            >
              <span>View in Applications</span>
              <ExternalLink className="w-3 h-3" />
            </button>
            <button
              onClick={() => setSubmittedApplication(null)}
              className="py-1.5 px-3 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-lg text-xs font-medium cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Student Recruitment Progression Timeline Modal (Stage 3.3.6) */}
      {isTimelineOpen && (
        <StudentRecruitmentTimeline
          isOpen={true}
          onClose={() => setIsTimelineOpen(false)}
          studentId={user?.id}
          jobId={jobIdNum}
          jobTitle={selectedJob?.title}
          companyName={selectedJob?.company?.name || selectedJob?.company_name}
        />
      )}
    </div>
  );
}

export default StudentJobDetails;
