import React, { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
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
  CheckCircle2,
  XCircle,
  AlertTriangle,
  AlertCircle,
  Search,
  Filter,
  Sparkles,
  ChevronRight,
  Info,
  Layers,
  Award,
  BookOpen,
  X,
  FileCheck,
  ExternalLink
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import toast from 'react-hot-toast';
import BatchFileUpload from '../../components/placement/BatchFileUpload';

const JobDetails = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const {
    selectedJob,
    isLoading,
    fetchJobPosting,
    matchStudents,
    applications,
    fetchApplications,
    publishJobPosting,
    shortlists,
    fetchShortlists,
  } = usePlacementStore();

  // Match state
  const [matchData, setMatchData] = useState(null);
  const [isMatching, setIsMatching] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState(null);

  // Filters & Sorting state
  const [candidateSearch, setCandidateSearch] = useState('');
  const [eligibilityFilter, setEligibilityFilter] = useState('all'); // 'all' | 'eligible' | 'ineligible'
  const [sortBy, setSortBy] = useState('match_desc'); // 'match_desc' | 'match_asc' | 'cgpa_desc' | 'req_desc'

  // Publish modal state
  const [publishModal, setPublishModal] = useState({
    isOpen: false,
    isPublishing: false,
    needsEmptySkillsConfirmation: false,
  });

  useEffect(() => {
    if (id) {
      fetchJobPosting(id);
      fetchApplications({ job_posting_id: id });
      fetchShortlists({ job_posting_id: id });
    }
  }, [id]);

  // If query string has ?tab=matches or user came from "View Matches", trigger match
  useEffect(() => {
    if (id && location.search.includes('tab=matches')) {
      handleMatchStudents();
    }
  }, [id, location.search]);

  const handleMatchStudents = async () => {
    setIsMatching(true);
    try {
      const result = await matchStudents({ job_posting_id: parseInt(id) });
      setMatchData(result);
      toast.success(
        `Skill matching complete: evaluated ${
          (result.all_candidates || result.eligible_students || []).length
        } candidates (${result.total_eligible} eligible)`
      );
    } catch (error) {
      toast.error(error.response?.data?.detail || error.message || 'Failed to match candidates');
    } finally {
      setIsMatching(false);
    }
  };

  const handleConfirmPublish = async (confirmNoSkills = false) => {
    if (!selectedJob) return;
    setPublishModal((prev) => ({ ...prev, isPublishing: true }));

    try {
      await publishJobPosting(selectedJob.id, confirmNoSkills);
      toast.success(`Job "${selectedJob.title}" published successfully!`);
      setPublishModal({ isOpen: false, isPublishing: false, needsEmptySkillsConfirmation: false });
      fetchJobPosting(id);
    } catch (error) {
      const errMsg = error.response?.data?.detail || error.message || '';
      if (
        typeof errMsg === 'string' &&
        (errMsg.toLowerCase().includes('no required or preferred skills') ||
          errMsg.toLowerCase().includes('confirm_no_skills'))
      ) {
        setPublishModal((prev) => ({
          ...prev,
          isPublishing: false,
          needsEmptySkillsConfirmation: true,
        }));
      } else {
        toast.error(errMsg || 'Failed to publish job');
        setPublishModal((prev) => ({ ...prev, isPublishing: false }));
      }
    }
  };

  const isCandidateShortlisted = useMemo(() => {
    const shortlistedSet = new Set(
      (shortlists || [])
        .filter((s) => s.job_posting_id === parseInt(id))
        .map((s) => s.student_id)
    );
    return (studentId) => shortlistedSet.has(studentId);
  }, [shortlists, id]);

  // Build full candidate list from backend response
  const candidateList = useMemo(() => {
    if (!matchData) return [];
    // Prioritize all_candidates if returned by backend, otherwise use eligible_students
    const list = matchData.all_candidates || matchData.eligible_students || [];
    return list;
  }, [matchData]);

  // Filtered and sorted candidates
  const processedCandidates = useMemo(() => {
    let result = [...candidateList];

    // Search filter
    if (candidateSearch.trim()) {
      const q = candidateSearch.toLowerCase();
      result = result.filter(
        (c) =>
          c.student_name?.toLowerCase().includes(q) ||
          c.email?.toLowerCase().includes(q) ||
          c.branch?.toLowerCase().includes(q)
      );
    }

    // Eligibility filter
    if (eligibilityFilter === 'eligible') {
      result = result.filter((c) => c.is_eligible);
    } else if (eligibilityFilter === 'ineligible') {
      result = result.filter((c) => !c.is_eligible);
    }

    // Sorting
    result.sort((a, b) => {
      if (sortBy === 'match_desc') {
        const scoreA = a.match_score !== null ? a.match_score : -1;
        const scoreB = b.match_score !== null ? b.match_score : -1;
        return scoreB - scoreA;
      }
      if (sortBy === 'match_asc') {
        const scoreA = a.match_score !== null ? a.match_score : 999;
        const scoreB = b.match_score !== null ? b.match_score : 999;
        return scoreA - scoreB;
      }
      if (sortBy === 'cgpa_desc') {
        return (b.cgpa || 0) - (a.cgpa || 0);
      }
      if (sortBy === 'req_desc') {
        return (b.required_matched || 0) - (a.required_matched || 0);
      }
      return 0;
    });

    return result;
  }, [candidateList, candidateSearch, eligibilityFilter, sortBy]);

  const getStatusBadge = (status) => {
    switch (status) {
      case 'open':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
            ● OPEN
          </span>
        );
      case 'draft':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
            ○ DRAFT
          </span>
        );
      case 'closed':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
            ✕ CLOSED
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-600">
            {status?.toUpperCase()}
          </span>
        );
    }
  };

  const getAppStatusColor = (status) => {
    switch (status) {
      case 'shortlisted':
        return 'bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800';
      case 'selected':
        return 'bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800';
      case 'rejected':
        return 'bg-rose-100 dark:bg-rose-950/60 text-rose-800 dark:text-rose-300 border border-rose-200 dark:border-rose-800';
      default:
        return 'bg-blue-100 dark:bg-blue-950/60 text-blue-800 dark:text-blue-300 border border-blue-200 dark:border-blue-800';
    }
  };

  if (isLoading && !selectedJob) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-indigo-600 border-t-transparent"></div>
      </div>
    );
  }

  if (!selectedJob) {
    return (
      <div className="text-center py-16 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
        <Briefcase className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
        <p className="text-gray-500 dark:text-gray-400 font-medium">Job posting not found</p>
        <button
          onClick={() => navigate('/placement/jobs')}
          className="mt-4 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm"
        >
          Return to Jobs List
        </button>
      </div>
    );
  }

  return (
    <div className="pb-16 max-w-7xl mx-auto">
      {/* Back Button */}
      <button
        onClick={() => navigate('/placement/jobs')}
        className="flex items-center space-x-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white mb-4 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Jobs</span>
      </button>

      {/* Job Header Card */}
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800 p-6 mb-6">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-3">
              {getStatusBadge(selectedJob.status)}
              <span className="text-xs text-gray-400 dark:text-gray-500">
                Job ID #{selectedJob.id}
              </span>
              {selectedJob.status === 'draft' && (
                <span className="text-xs font-medium text-amber-600 dark:text-amber-400">
                  (Draft posting — Review before publishing)
                </span>
              )}
            </div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white mt-2">
              {selectedJob.title}
            </h1>
            <p className="text-gray-600 dark:text-gray-300 flex items-center space-x-2 mt-1">
              <Building2 className="w-4 h-4 text-indigo-500" />
              <span className="font-medium">{selectedJob.company_name}</span>
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Publish button if draft */}
            {selectedJob.status === 'draft' && (
              <button
                onClick={() => setPublishModal({ isOpen: true, isPublishing: false, needsEmptySkillsConfirmation: false })}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-semibold flex items-center space-x-1.5 shadow-sm transition-colors cursor-pointer"
              >
                <Send className="w-4 h-4" />
                <span>Publish Job</span>
              </button>
            )}

            {/* Run Match Button */}
            <button
              onClick={handleMatchStudents}
              disabled={isMatching}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-sm font-semibold flex items-center space-x-2 shadow-sm transition-colors cursor-pointer"
            >
              {isMatching ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Calculating Matches...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Run Candidate Match</span>
                </>
              )}
            </button>

            <button
              onClick={() => navigate(`/placement/jobs/${id}/edit`)}
              className="px-3 py-2 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg text-sm font-medium transition-colors"
            >
              Edit Job
            </button>
          </div>
        </div>

        {/* Job Details Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6 pt-6 border-t border-gray-100 dark:border-gray-800">
          <div className="flex items-center space-x-2 text-sm text-gray-600 dark:text-gray-400">
            <MapPin className="w-4 h-4 text-gray-400" />
            <span>{selectedJob.location || 'Location Not specified'}</span>
          </div>
          <div className="flex items-center space-x-2 text-sm text-gray-600 dark:text-gray-400">
            <DollarSign className="w-4 h-4 text-gray-400" />
            <span>{selectedJob.salary_range || 'Salary Not specified'}</span>
          </div>
          <div className="flex items-center space-x-2 text-sm text-gray-600 dark:text-gray-400">
            <Clock className="w-4 h-4 text-gray-400" />
            <span>Exp: {selectedJob.experience_level || 'Any experience'}</span>
          </div>
          <div className="flex items-center space-x-2 text-sm text-gray-600 dark:text-gray-400">
            <TrendingUp className="w-4 h-4 text-gray-400" />
            <span>
              Min CGPA:{' '}
              {selectedJob.cgpa_criteria !== null && selectedJob.cgpa_criteria !== undefined
                ? `${selectedJob.cgpa_criteria}+`
                : 'None'}
            </span>
          </div>
        </div>

        {/* Description */}
        {selectedJob.description && (
          <div className="mt-5 p-4 bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-gray-200 dark:border-gray-800">
            <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
              Role & Responsibilities
            </h3>
            <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap leading-relaxed">
              {selectedJob.description}
            </p>
          </div>
        )}

        {/* Skills Requirements Breakdown */}
        <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Required Skills (80%) */}
          <div className="p-4 bg-indigo-50/50 dark:bg-indigo-950/20 rounded-xl border border-indigo-100 dark:border-indigo-900/40">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-semibold text-indigo-900 dark:text-indigo-300 uppercase tracking-wider flex items-center gap-1.5">
                <Award className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                Required Skills (Core)
              </h3>
              <span className="text-xs font-medium text-indigo-600 dark:text-indigo-400">
                80% Weight
              </span>
            </div>
            {selectedJob.required_skills?.length > 0 ? (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {selectedJob.required_skills.map((skill) => (
                  <span
                    key={skill}
                    className="px-2.5 py-0.5 bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 rounded-full text-xs font-medium"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-amber-600 dark:text-amber-400 italic mt-1">
                ⚠️ No required skills defined
              </p>
            )}
          </div>

          {/* Preferred Skills (20%) */}
          <div className="p-4 bg-teal-50/50 dark:bg-teal-950/20 rounded-xl border border-teal-100 dark:border-teal-900/40">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-semibold text-teal-900 dark:text-teal-300 uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-teal-600 dark:text-teal-400" />
                Preferred Skills (Bonus)
              </h3>
              <span className="text-xs font-medium text-teal-600 dark:text-teal-400">
                20% Weight
              </span>
            </div>
            {selectedJob.preferred_skills?.length > 0 ? (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {selectedJob.preferred_skills.map((skill) => (
                  <span
                    key={skill}
                    className="px-2.5 py-0.5 bg-teal-100 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800 rounded-full text-xs font-medium"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-400 dark:text-gray-500 italic mt-1">
                No preferred bonus skills defined
              </p>
            )}
          </div>
        </div>

        {/* Branch Eligibility */}
        {selectedJob.branch_eligibility?.length > 0 && (
          <div className="mt-4">
            <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
              Eligible Academic Branches
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {selectedJob.branch_eligibility.map((branch) => (
                <span
                  key={branch}
                  className="px-2.5 py-0.5 bg-green-50 dark:bg-green-950/50 text-green-700 dark:text-green-300 border border-green-200 dark:border-green-800 rounded-full text-xs font-medium"
                >
                  {branch}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Deadlines */}
        <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-800 flex flex-wrap gap-6 text-xs text-gray-500 dark:text-gray-400">
          {selectedJob.application_deadline && (
            <div className="flex items-center space-x-1.5">
              <Calendar className="w-4 h-4 text-gray-400" />
              <span>
                Application Deadline: <strong>{new Date(selectedJob.application_deadline).toLocaleDateString()}</strong>
              </span>
            </div>
          )}
          {selectedJob.drive_date && (
            <div className="flex items-center space-x-1.5">
              <Calendar className="w-4 h-4 text-gray-400" />
              <span>
                Campus Drive Date: <strong>{new Date(selectedJob.drive_date).toLocaleDateString()}</strong>
              </span>
            </div>
          )}
        </div>

        {/* Official External Application Link */}
        {selectedJob.application_url && (
          <div className="mt-4 p-3 bg-blue-50/60 dark:bg-blue-950/30 rounded-xl border border-blue-100 dark:border-blue-900/40 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
            <div className="flex items-center gap-2 text-blue-900 dark:text-blue-200 min-w-0">
              <ExternalLink className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0" />
              <span className="truncate">
                <strong>Official Application URL:</strong>{' '}
                <span className="font-mono text-blue-700 dark:text-blue-300">{selectedJob.application_url}</span>
              </span>
            </div>
            <a
              href={selectedJob.application_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 px-3 py-1 bg-white dark:bg-gray-800 text-blue-600 dark:text-blue-400 hover:text-blue-800 border border-blue-200 dark:border-blue-800 rounded-lg font-semibold shrink-0"
            >
              <span>Open Link</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        )}
      </div>

      {/* Candidate Skill Matching Section */}
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800 p-6 mb-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <div className="flex items-center gap-2">
              <div className="p-2 bg-indigo-50 dark:bg-indigo-950/50 rounded-lg text-indigo-600 dark:text-indigo-400">
                <Users className="w-5 h-5" />
              </div>
              <h2 className="text-lg font-bold text-gray-900 dark:text-white">
                Candidate Skill Matching & Eligibility
              </h2>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Evaluates candidates against 80/20 skill requirements + academic criteria (CGPA & Branch)
            </p>
          </div>

          <button
            onClick={handleMatchStudents}
            disabled={isMatching}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center space-x-2 transition-colors cursor-pointer self-start sm:self-auto"
          >
            {isMatching ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Running Matching...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5" />
                <span>{matchData ? 'Re-Run Match' : 'Run Matching Engine'}</span>
              </>
            )}
          </button>
        </div>

        {/* Empty state when match hasn't been run */}
        {!matchData && !isMatching && (
          <div className="text-center py-12 bg-gray-50 dark:bg-gray-800/40 rounded-xl border border-dashed border-gray-200 dark:border-gray-800">
            <Sparkles className="w-10 h-10 text-indigo-400 mx-auto mb-2" />
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
              Candidate Skill Matching Not Yet Executed
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 max-w-md mx-auto mt-1 mb-4">
              Click the button below to match students against this job posting's required and preferred skills, extract resume competencies, and check CGPA/branch cutoffs.
            </p>
            <button
              onClick={handleMatchStudents}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors cursor-pointer"
            >
              Analyze & Match Candidates Now
            </button>
          </div>
        )}

        {/* Loading State */}
        {isMatching && (
          <div className="text-center py-16 bg-gray-50 dark:bg-gray-800/40 rounded-xl">
            <div className="w-10 h-10 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm font-semibold text-gray-900 dark:text-white">
              Running Semantic & Exact Skill Matching...
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Matching resume extractions, evaluating 80/20 score formula, and checking eligibility
            </p>
          </div>
        )}

        {/* Results Overview & Filter Bar */}
        {matchData && !isMatching && (
          <div>
            {/* Match Metrics Summary Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 mb-6">
              <div className="p-3.5 bg-gray-50 dark:bg-gray-800/60 rounded-xl border border-gray-200 dark:border-gray-700/60">
                <p className="text-xs text-gray-500 dark:text-gray-400">Total Evaluated</p>
                <p className="text-xl font-bold text-gray-900 dark:text-white mt-0.5">
                  {candidateList.length}
                </p>
              </div>
              <div className="p-3.5 bg-emerald-50 dark:bg-emerald-950/30 rounded-xl border border-emerald-200 dark:border-emerald-800/60">
                <p className="text-xs text-emerald-700 dark:text-emerald-400 font-medium">Eligible Candidates</p>
                <p className="text-xl font-bold text-emerald-600 dark:text-emerald-400 mt-0.5">
                  {matchData.total_eligible}
                </p>
              </div>
              <div className="p-3.5 bg-rose-50 dark:bg-rose-950/30 rounded-xl border border-rose-200 dark:border-rose-800/60">
                <p className="text-xs text-rose-700 dark:text-rose-400 font-medium">Ineligible</p>
                <p className="text-xl font-bold text-rose-600 dark:text-rose-400 mt-0.5">
                  {Math.max(0, candidateList.length - matchData.total_eligible)}
                </p>
              </div>
              <div className="p-3.5 bg-indigo-50 dark:bg-indigo-950/30 rounded-xl border border-indigo-200 dark:border-indigo-800/60">
                <p className="text-xs text-indigo-700 dark:text-indigo-400 font-medium">Skill Criteria</p>
                <p className="text-xs font-semibold text-indigo-900 dark:text-indigo-200 mt-1">
                  {(selectedJob.required_skills?.length || 0)} Req • {(selectedJob.preferred_skills?.length || 0)} Pref
                </p>
              </div>
            </div>

            {/* Filters Bar */}
            <div className="flex flex-col sm:flex-row gap-3 mb-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search by student name, email, or branch..."
                  value={candidateSearch}
                  onChange={(e) => setCandidateSearch(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 text-sm border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
              </div>

              <div className="flex gap-2">
                <select
                  value={eligibilityFilter}
                  onChange={(e) => setEligibilityFilter(e.target.value)}
                  className="px-3 py-2 text-xs border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                >
                  <option value="all">All Statuses ({candidateList.length})</option>
                  <option value="eligible">Eligible Only ({matchData.total_eligible})</option>
                  <option value="ineligible">Ineligible Only ({Math.max(0, candidateList.length - matchData.total_eligible)})</option>
                </select>

                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="px-3 py-2 text-xs border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                >
                  <option value="match_desc">Match Score: Highest First</option>
                  <option value="match_asc">Match Score: Lowest First</option>
                  <option value="cgpa_desc">CGPA: Highest First</option>
                  <option value="req_desc">Required Skills Matched</option>
                </select>
              </div>
            </div>

            {/* Candidate List */}
            {processedCandidates.length === 0 ? (
              <div className="text-center py-12 bg-gray-50 dark:bg-gray-800/40 rounded-xl">
                <Users className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                <p className="text-sm font-medium text-gray-600 dark:text-gray-300">
                  No candidates match the selected filters
                </p>
                <button
                  onClick={() => {
                    setCandidateSearch('');
                    setEligibilityFilter('all');
                  }}
                  className="mt-2 text-xs text-indigo-600 dark:text-indigo-400 font-medium hover:underline"
                >
                  Clear filters
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {processedCandidates.map((candidate, idx) => (
                  <div
                    key={candidate.student_id || idx}
                    className="p-4 bg-gray-50/70 dark:bg-gray-800/50 rounded-xl border border-gray-200 dark:border-gray-700/70 hover:border-indigo-300 dark:hover:border-indigo-800 transition-all"
                  >
                    <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
                      {/* Candidate Identity */}
                      <div className="flex-1">
                        <div className="flex items-center space-x-2.5 mb-1">
                          <span className="text-xs font-bold text-gray-400 dark:text-gray-500">
                            #{idx + 1}
                          </span>
                          <h4 className="text-sm font-bold text-gray-900 dark:text-white">
                            {candidate.student_name}
                          </h4>

                          {/* Eligibility Badge */}
                          {candidate.is_eligible ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                              ✓ Eligible
                            </span>
                          ) : (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-100 dark:bg-rose-950/60 text-rose-800 dark:text-rose-300 border border-rose-200 dark:border-rose-800">
                              ✕ Ineligible
                            </span>
                          )}

                          {/* Resume Indicator */}
                          {candidate.resume_filename ? (
                            <span className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1">
                              <FileCheck className="w-3.5 h-3.5 text-indigo-500" />
                              <span className="truncate max-w-[140px]">{candidate.resume_filename}</span>
                            </span>
                          ) : (
                            <span className="text-xs text-gray-400 italic">Profile skills only</span>
                          )}
                        </div>

                        {/* Ineligibility reasons banner */}
                        {!candidate.is_eligible && candidate.eligibility_reasons?.length > 0 && (
                          <div className="mb-2 text-xs text-rose-600 dark:text-rose-400 flex items-start gap-1">
                            <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                            <span>Ineligible: {candidate.eligibility_reasons.join(', ')}</span>
                          </div>
                        )}

                        <div className="flex flex-wrap items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
                          <span>Email: <strong className="text-gray-700 dark:text-gray-300">{candidate.email}</strong></span>
                          <span>Branch: <strong className="text-gray-700 dark:text-gray-300">{candidate.branch || 'N/A'}</strong></span>
                          <span>CGPA: <strong className="text-gray-700 dark:text-gray-300">{candidate.cgpa !== null && candidate.cgpa !== undefined ? candidate.cgpa : 'N/A'}</strong></span>
                        </div>

                        {/* Matched vs Missing Skills Summary */}
                        <div className="mt-2.5 flex flex-wrap items-center gap-2 text-xs">
                          <span className="text-gray-500 dark:text-gray-400">
                            Required Skills:
                          </span>
                          <span className="px-2 py-0.5 rounded-md bg-indigo-50 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300 font-medium">
                            {candidate.required_matched || 0}/{candidate.required_total || 0} matched
                          </span>

                          <span className="text-gray-400 dark:text-gray-600">•</span>

                          <span className="text-gray-500 dark:text-gray-400">
                            Preferred Skills:
                          </span>
                          <span className="px-2 py-0.5 rounded-md bg-teal-50 dark:bg-teal-950/50 text-teal-700 dark:text-teal-300 font-medium">
                            {candidate.preferred_matched || 0}/{candidate.preferred_total || 0} matched
                          </span>

                          {candidate.semantic_matches?.length > 0 && (
                            <span className="px-2 py-0.5 rounded-md bg-purple-50 dark:bg-purple-950/50 text-purple-700 dark:text-purple-300 font-medium">
                              ✨ {candidate.semantic_matches.length} semantic matches
                            </span>
                          )}

                          {candidate.has_low_match_warning && (
                            <span className="px-2 py-0.5 rounded-md bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-400 font-medium border border-amber-200 dark:border-amber-800">
                              ⚠️ Low Match (&lt;50%)
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Match Score Display */}
                      <div className="flex items-center gap-4 self-end lg:self-center">
                        <div className="text-right">
                          <div className="text-xs text-gray-400 dark:text-gray-500">Skill Match Score</div>
                          {candidate.match_score !== null && candidate.match_score !== undefined ? (
                            <div className="text-xl font-extrabold text-indigo-600 dark:text-indigo-400">
                              {candidate.match_score.toFixed(1)}%
                            </div>
                          ) : (
                            <div className="text-xs font-semibold text-gray-500 dark:text-gray-400 bg-gray-200 dark:bg-gray-700 px-2 py-1 rounded">
                              Not calculated
                            </div>
                          )}
                          <div className="text-[10px] text-gray-400">80% Req / 20% Pref</div>
                        </div>

                        <div className="flex flex-col gap-1.5">
                          <button
                            onClick={() => setSelectedCandidate(candidate)}
                            className="px-3 py-1.5 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 rounded-lg text-xs font-medium transition-colors cursor-pointer flex items-center gap-1 shadow-xs"
                          >
                            <span>Inspect Match</span>
                            <ChevronRight className="w-3.5 h-3.5" />
                          </button>
                          {candidate.is_eligible && isCandidateShortlisted(candidate.student_id) && (
                            <span className="px-3 py-1.5 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 rounded-lg text-xs font-semibold flex items-center justify-center gap-1 shadow-xs">
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              Shortlisted
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Candidate Deep Inspection Modal */}
      {selectedCandidate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6 shadow-2xl border border-gray-200 dark:border-gray-800">
            {/* Header */}
            <div className="flex items-start justify-between pb-4 border-b border-gray-100 dark:border-gray-800">
              <div>
                <div className="flex items-center space-x-2">
                  <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                    {selectedCandidate.student_name}
                  </h3>
                  {selectedCandidate.is_eligible ? (
                    <span className="px-2 py-0.5 bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 text-xs font-semibold rounded-full">
                      ✓ Eligible
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 text-xs font-semibold rounded-full">
                      ✕ Ineligible
                    </span>
                  )}
                  {selectedCandidate.isSnapshot && (
                    <span className="px-2 py-0.5 bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 text-xs font-semibold rounded-full">
                      📷 Stored Snapshot
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  {selectedCandidate.email} • {selectedCandidate.branch} • CGPA {selectedCandidate.cgpa}
                </p>
              </div>
              <button
                onClick={() => setSelectedCandidate(null)}
                className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Ineligibility Warning if any */}
            {!selectedCandidate.is_eligible && (
              <div className="mt-4 p-3 bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 rounded-xl text-xs text-rose-800 dark:text-rose-300 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600 mt-0.5" />
                <div>
                  <strong>Ineligible Candidate:</strong> {selectedCandidate.eligibility_reasons?.join(', ')}
                </div>
              </div>
            )}

            {/* Low Match Warning if any */}
            {selectedCandidate.has_low_match_warning && (
              <div className="mt-3 p-3 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-xl text-xs text-amber-800 dark:text-amber-300 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0 text-amber-600 mt-0.5" />
                <div>
                  <strong>Low Match Warning:</strong> {selectedCandidate.low_match_warning || 'Required skill match is below 50%. The candidate meets explicit academic criteria and is eligible to apply, but may need skill development.'}
                </div>
              </div>
            )}

            {/* Note: Match score vs eligibility */}
            <div className="mt-3 p-3 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-xl text-xs text-blue-800 dark:text-blue-300 flex items-start gap-2">
              <Info className="w-4 h-4 shrink-0 text-blue-600 mt-0.5" />
              <div>
                <strong>Deterministic Evaluation:</strong> Match score reflects candidate skill alignment (80% core required + 20% bonus preferred). Academic eligibility (CGPA & branch) is evaluated independently.
              </div>
            </div>

            {/* Scores Breakdown */}
            <div className="grid grid-cols-3 gap-3 my-4">
              <div className="p-3 bg-indigo-50/60 dark:bg-indigo-950/30 rounded-xl text-center border border-indigo-100 dark:border-indigo-900/40">
                <p className="text-[11px] text-indigo-700 dark:text-indigo-400 font-medium">Overall Skill Match</p>
                <p className="text-lg font-bold text-indigo-600 dark:text-indigo-400 mt-0.5">
                  {selectedCandidate.match_score !== null && selectedCandidate.match_score !== undefined
                    ? `${selectedCandidate.match_score.toFixed(1)}%`
                    : 'Not calculated'}
                </p>
              </div>
              <div className="p-3 bg-purple-50/60 dark:bg-purple-950/30 rounded-xl text-center border border-purple-100 dark:border-purple-900/40">
                <p className="text-[11px] text-purple-700 dark:text-purple-400 font-medium">Required Skills (80%)</p>
                <p className="text-lg font-bold text-purple-600 dark:text-purple-400 mt-0.5">
                  {selectedCandidate.required_score !== null && selectedCandidate.required_score !== undefined
                    ? `${selectedCandidate.required_score.toFixed(1)}%`
                    : `${selectedCandidate.required_matched || 0}/${selectedCandidate.required_total || 0}`}
                </p>
              </div>
              <div className="p-3 bg-teal-50/60 dark:bg-teal-950/30 rounded-xl text-center border border-teal-100 dark:border-teal-900/40">
                <p className="text-[11px] text-teal-700 dark:text-teal-400 font-medium">Preferred Skills (20%)</p>
                <p className="text-lg font-bold text-teal-600 dark:text-teal-400 mt-0.5">
                  {selectedCandidate.preferred_score !== null && selectedCandidate.preferred_score !== undefined
                    ? `${selectedCandidate.preferred_score.toFixed(1)}%`
                    : `${selectedCandidate.preferred_matched || 0}/${selectedCandidate.preferred_total || 0}`}
                </p>
              </div>
            </div>

            {/* Required Skills Analysis */}
            <div className="mb-4">
              <h4 className="text-xs font-bold text-gray-900 dark:text-white uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Award className="w-4 h-4 text-indigo-600" />
                Required Skills Analysis
              </h4>
              <div className="space-y-2">
                <div>
                  <p className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold mb-1">
                    ✓ Matched Required Skills:
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedCandidate.matched_skills?.filter((s) =>
                      selectedJob.required_skills?.some((req) => req.toLowerCase() === s.toLowerCase())
                    ).length > 0 ? (
                      selectedCandidate.matched_skills
                        ?.filter((s) =>
                          selectedJob.required_skills?.some((req) => req.toLowerCase() === s.toLowerCase())
                        )
                        .map((skill) => (
                          <span
                            key={skill}
                            className="px-2.5 py-0.5 bg-emerald-100 dark:bg-emerald-950/50 text-emerald-800 dark:text-emerald-300 rounded-full text-xs font-medium"
                          >
                            ✓ {skill}
                          </span>
                        ))
                    ) : (
                      <span className="text-xs text-gray-400 italic">No required skills matched</span>
                    )}
                  </div>
                </div>

                <div>
                  <p className="text-[11px] text-rose-600 dark:text-rose-400 font-semibold mb-1">
                    ✕ Missing Required Skills:
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedCandidate.missing_required_skills?.length > 0 ? (
                      selectedCandidate.missing_required_skills.map((skill) => (
                        <span
                          key={skill}
                          className="px-2.5 py-0.5 bg-rose-100 dark:bg-rose-950/50 text-rose-800 dark:text-rose-300 rounded-full text-xs font-medium"
                        >
                          ✕ {skill}
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                        ✓ All required skills satisfied!
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Preferred Skills Analysis */}
            <div className="mb-4">
              <h4 className="text-xs font-bold text-gray-900 dark:text-white uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-teal-600" />
                Preferred Bonus Skills Analysis
              </h4>
              <div className="space-y-2">
                <div>
                  <p className="text-[11px] text-teal-600 dark:text-teal-400 font-semibold mb-1">
                    ✓ Matched Preferred Skills:
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedCandidate.matched_skills?.filter((s) =>
                      selectedJob.preferred_skills?.some((pref) => pref.toLowerCase() === s.toLowerCase())
                    ).length > 0 ? (
                      selectedCandidate.matched_skills
                        ?.filter((s) =>
                          selectedJob.preferred_skills?.some((pref) => pref.toLowerCase() === s.toLowerCase())
                        )
                        .map((skill) => (
                          <span
                            key={skill}
                            className="px-2.5 py-0.5 bg-teal-100 dark:bg-teal-950/50 text-teal-800 dark:text-teal-300 rounded-full text-xs font-medium"
                          >
                            ✓ {skill}
                          </span>
                        ))
                    ) : (
                      <span className="text-xs text-gray-400 italic">No preferred skills matched</span>
                    )}
                  </div>
                </div>

                <div>
                  <p className="text-[11px] text-gray-500 dark:text-gray-400 font-semibold mb-1">
                    Missing Preferred Skills:
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedCandidate.missing_preferred_skills?.length > 0 ? (
                      selectedCandidate.missing_preferred_skills.map((skill) => (
                        <span
                          key={skill}
                          className="px-2.5 py-0.5 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded-full text-xs"
                        >
                          {skill}
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-teal-600 dark:text-teal-400 font-medium">
                        ✓ All preferred skills satisfied!
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Semantic AI Matches */}
            {selectedCandidate.semantic_matches?.length > 0 && (
              <div className="mb-4 p-3 bg-purple-50/60 dark:bg-purple-950/30 rounded-xl border border-purple-200 dark:border-purple-800">
                <h4 className="text-xs font-bold text-purple-900 dark:text-purple-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4 text-purple-600" />
                  Semantic Skill Matches (AI Embedding Similarity ≥ 78%)
                </h4>
                <div className="space-y-1.5 text-xs">
                  {selectedCandidate.semantic_matches.map((sm, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between p-2 bg-white dark:bg-gray-800 rounded-lg border border-purple-100 dark:border-purple-900/50"
                    >
                      <span>
                        Job Skill: <strong className="text-indigo-600">{sm.job_skill}</strong> ≈ Student Competency:{' '}
                        <strong className="text-purple-600">{sm.student_skill}</strong>
                      </span>
                      <span className="px-2 py-0.5 bg-purple-100 dark:bg-purple-900 text-purple-800 dark:text-purple-200 rounded text-[11px] font-semibold">
                        {(sm.similarity_score * 100).toFixed(1)}% match
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Provenance: Skill Sources */}
            {selectedCandidate.skill_sources && Object.keys(selectedCandidate.skill_sources).length > 0 && (
              <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-800/40 rounded-xl border border-gray-200 dark:border-gray-700">
                <h4 className="text-xs font-bold text-gray-700 dark:text-gray-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Layers className="w-4 h-4 text-gray-500" />
                  Skill Extraction Provenance
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                  {selectedCandidate.skill_sources.resume_skills?.length > 0 && (
                    <div className="p-2 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                      <p className="font-semibold text-gray-800 dark:text-gray-200 mb-1">
                        📄 Extracted from Resume ({selectedCandidate.resume_filename || 'PDF'}):
                      </p>
                      <p className="text-gray-600 dark:text-gray-400">
                        {selectedCandidate.skill_sources.resume_skills.join(', ')}
                      </p>
                    </div>
                  )}
                  {selectedCandidate.skill_sources.profile_skills?.length > 0 && (
                    <div className="p-2 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                      <p className="font-semibold text-gray-800 dark:text-gray-200 mb-1">
                        👤 Verified Profile Skills:
                      </p>
                      <p className="text-gray-600 dark:text-gray-400">
                        {selectedCandidate.skill_sources.profile_skills.join(', ')}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Modal Actions */}
            <div className="mt-6 pt-4 border-t border-gray-100 dark:border-gray-800 flex justify-end space-x-3">
              <button
                onClick={() => navigate(`/placement/students/${selectedCandidate.student_id}`)}
                className="px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 rounded-lg text-xs font-medium transition-colors"
              >
                View Full Student Profile
              </button>
              {selectedCandidate.is_eligible && isCandidateShortlisted(selectedCandidate.student_id) && (
                <span className="px-4 py-2 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-xs">
                  <CheckCircle2 className="w-4 h-4" />
                  Already Shortlisted
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Batch File Upload Section (Phase 1 preserved) */}
      <div className="mt-6">
        <BatchFileUpload
          jobPostingId={id}
          onUploadComplete={(result) => {
            toast.success(`Processed ${result.processed || 0} files`);
          }}
        />
      </div>

      {/* Applications Section (Phase 1 preserved) */}
      <div className="mt-6 bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800 p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center space-x-2 mb-4">
          <FileText className="w-5 h-5 text-gray-500" />
          <span>Applications Submitted ({applications.length})</span>
        </h3>

        {applications.length === 0 ? (
          <p className="text-gray-500 dark:text-gray-400 text-center py-6">No applications submitted yet</p>
        ) : (
          <div className="space-y-3">
            {applications.map((app) => (
              <div
                key={app.id}
                className="flex items-center justify-between p-3.5 bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-gray-100 dark:border-gray-800"
              >
                <div>
                  <p className="font-medium text-gray-900 dark:text-white text-sm">{app.student_name}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{app.student_email}</p>
                </div>
                <div className="flex items-center space-x-3">
                  <span className={`text-xs px-2.5 py-0.5 rounded-full font-semibold ${getAppStatusColor(app.status)}`}>
                    {app.status?.toUpperCase()}
                  </span>
                  {app.external_applied_at ? (
                    <span
                      className="text-[10px] font-semibold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/50 px-2 py-0.5 rounded-full border border-emerald-200 dark:border-emerald-800"
                      title={`Student confirmed external submission on ${new Date(app.external_applied_at).toLocaleString()}`}
                    >
                      ✓ External Confirmed ({new Date(app.external_applied_at).toLocaleDateString()})
                    </span>
                  ) : selectedJob?.application_url ? (
                    <span className="text-[10px] font-medium text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/50 px-2 py-0.5 rounded-full border border-amber-200 dark:border-amber-800">
                      External: Pending
                    </span>
                  ) : null}
                  {(app.has_low_match_warning || app.match_snapshot?.has_low_match_warning) && (
                    <span className="text-[10px] font-semibold text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/50 px-2 py-0.5 rounded-full border border-amber-200 dark:border-amber-800" title={app.low_match_warning || app.match_snapshot?.low_match_warning || 'Required skill match < 50%'}>
                      ⚠️ Low match (&lt;50%)
                    </span>
                  )}
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {app.match_percentage !== null && app.match_percentage !== undefined ? `${app.match_percentage.toFixed(1)}% match` : 'Score N/A'}
                  </span>
                  {app.match_snapshot && (
                    <button
                      onClick={() => setSelectedCandidate({
                        student_name: app.student_name,
                        email: app.student_email,
                        branch: app.match_snapshot.branch,
                        cgpa: app.match_snapshot.cgpa,
                        is_eligible: app.match_snapshot.is_eligible,
                        eligibility_reasons: app.match_snapshot.eligibility_reasons || [],
                        match_score: app.match_snapshot.match_percentage,
                        required_score: app.match_snapshot.required_score,
                        preferred_score: app.match_snapshot.preferred_score,
                        required_matched: app.match_snapshot.matched_required_skills?.length || 0,
                        required_total: app.match_snapshot.job_required_skills?.length || 0,
                        preferred_matched: app.match_snapshot.matched_preferred_skills?.length || 0,
                        preferred_total: app.match_snapshot.job_preferred_skills?.length || 0,
                        matched_skills: (app.match_snapshot.matched_required_skills || []).concat(app.match_snapshot.matched_preferred_skills || []),
                        missing_skills: (app.match_snapshot.missing_required_skills || []).concat(app.match_snapshot.missing_preferred_skills || []),
                        missing_required_skills: app.match_snapshot.missing_required_skills || [],
                        missing_preferred_skills: app.match_snapshot.missing_preferred_skills || [],
                        semantic_matches: app.match_snapshot.semantic_matches || [],
                        has_low_match_warning: app.match_snapshot.has_low_match_warning,
                        low_match_warning: app.match_snapshot.low_match_warning,
                        resume_filename: app.match_snapshot.resume_filename,
                        isSnapshot: true,
                        snapshot_time: app.match_snapshot.created_at
                      })}
                      className="px-2.5 py-1 text-xs bg-indigo-50 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300 rounded-lg hover:bg-indigo-100 dark:hover:bg-indigo-900/50 transition-colors border border-indigo-200 dark:border-indigo-800"
                    >
                      Snapshot
                    </button>
                  )}
                  <button
                    onClick={() => navigate(`/placement/students/${app.student_id}`)}
                    className="px-3 py-1 text-xs bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
                  >
                    View
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Publish Modal in JobDetails */}
      {publishModal.isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-md w-full p-6 shadow-xl border border-gray-200 dark:border-gray-800">
            {publishModal.needsEmptySkillsConfirmation ? (
              <div>
                <div className="w-12 h-12 rounded-full bg-amber-100 dark:bg-amber-950/50 text-amber-600 dark:text-amber-400 flex items-center justify-center mb-4">
                  <AlertTriangle className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                  Publish Without Skills?
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
                  This job posting has zero required and zero preferred skills defined.
                </p>
                <div className="mt-3 p-3 bg-amber-50 dark:bg-amber-950/30 rounded-xl border border-amber-200 dark:border-amber-800 text-xs text-amber-800 dark:text-amber-300">
                  ⚠️ Candidate match scores will be marked as <strong>"Not calculated"</strong>.
                </div>
                <div className="mt-6 flex space-x-3">
                  <button
                    type="button"
                    disabled={publishModal.isPublishing}
                    onClick={() => handleConfirmPublish(true)}
                    className="flex-1 px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-sm font-medium transition-colors"
                  >
                    {publishModal.isPublishing ? 'Publishing...' : 'Yes, Publish Anyway'}
                  </button>
                  <button
                    type="button"
                    disabled={publishModal.isPublishing}
                    onClick={() => setPublishModal({ isOpen: false, isPublishing: false, needsEmptySkillsConfirmation: false })}
                    className="px-4 py-2 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg text-sm font-medium"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div>
                <div className="w-12 h-12 rounded-full bg-emerald-100 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mb-4">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                  Publish Job Posting
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
                  Are you sure you want to publish <span className="font-semibold text-gray-900 dark:text-white">"{selectedJob.title}"</span>?
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  This will transition its status from <strong>DRAFT</strong> to <strong>OPEN</strong>.
                </p>
                <div className="mt-6 flex space-x-3">
                  <button
                    type="button"
                    disabled={publishModal.isPublishing}
                    onClick={() => handleConfirmPublish(false)}
                    className="flex-1 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-medium transition-colors"
                  >
                    {publishModal.isPublishing ? 'Publishing...' : 'Publish Job'}
                  </button>
                  <button
                    type="button"
                    disabled={publishModal.isPublishing}
                    onClick={() => setPublishModal({ isOpen: false, isPublishing: false, needsEmptySkillsConfirmation: false })}
                    className="px-4 py-2 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg text-sm font-medium"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default JobDetails;