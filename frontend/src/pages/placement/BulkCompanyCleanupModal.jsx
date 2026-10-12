import React, { useEffect, useState, useMemo } from 'react';
import {
  X,
  AlertTriangle,
  Trash2,
  Archive,
  ShieldCheck,
  ShieldAlert,
  ShieldX,
  CheckCircle2,
  Briefcase,
  Users,
  FileText,
  Paperclip,
  Award,
  Building2,
  Layers,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  AlertCircle,
  Clock,
  Check,
  Megaphone,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import toast from 'react-hot-toast';

const CONFIRMATION_PHRASE = 'CONFIRM_PURGE_TEST_DATA';

const BulkCompanyCleanupModal = ({
  isOpen,
  onClose,
  selectedCompanyIds = [],
  onSuccess,
}) => {
  const {
    cleanupPreview,
    isCleanupLoading,
    cleanupError,
    fetchCleanupPreview,
    clearCleanupPreview,
    runCleanup,
  } = usePlacementStore();

  const [expandedCompanyIds, setExpandedCompanyIds] = useState(new Set());
  const [purgeConfirmOpen, setPurgeConfirmOpen] = useState(false);
  const [confirmationInput, setConfirmationInput] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [modalError, setModalError] = useState(null);

  // Fetch preview whenever modal opens with company IDs
  useEffect(() => {
    if (isOpen && selectedCompanyIds.length > 0) {
      setModalError(null);
      setPurgeConfirmOpen(false);
      setConfirmationInput('');
      fetchCleanupPreview({ company_ids: selectedCompanyIds, include_all_candidates: false }).catch((err) => {
        const msg = err.response?.data?.detail || err.message || 'Failed to generate company cleanup preview';
        setModalError(msg);
      });
    } else if (!isOpen) {
      clearCleanupPreview();
    }
  }, [isOpen, selectedCompanyIds, fetchCleanupPreview, clearCleanupPreview]);

  const candidates = cleanupPreview?.candidates || [];
  const summary = cleanupPreview?.summary || {
    total_candidates_flagged: 0,
    total_safe_to_purge: 0,
    total_requires_archive: 0,
    total_protected_genuine: 0,
    total_dependent_jobs: 0,
    total_dependent_circulars: 0,
    total_dependent_applications: 0,
    total_dependent_result_batches: 0,
    total_dependent_offers: 0,
    total_dependent_accepted_offers: 0,
    total_files_identified: 0,
    total_shared_files_preserved: 0,
  };

  const hasProtected = useMemo(() => {
    return candidates.some((c) => c.safety_classification === 'PROTECTED_GENUINE');
  }, [candidates]);

  const hasRequiresArchive = useMemo(() => {
    return candidates.some((c) => c.safety_classification === 'REQUIRES_ARCHIVE');
  }, [candidates]);

  const canPurgeAll = useMemo(() => {
    return (
      candidates.length > 0 &&
      candidates.every((c) => c.safety_classification === 'SAFE_TO_PURGE')
    );
  }, [candidates]);

  const toggleExpandCompany = (id) => {
    setExpandedCompanyIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleExecuteArchive = async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    setModalError(null);

    try {
      const result = await runCleanup({
        company_ids: selectedCompanyIds,
        mode: 'archive',
      });
      toast.success(
        result.message || `Successfully archived ${selectedCompanyIds.length} company(ies).`
      );
      if (onSuccess) onSuccess(result);
      onClose();
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to archive companies.';
      setModalError(msg);
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleExecutePurge = async () => {
    if (isSubmitting) return;
    if (confirmationInput.trim() !== CONFIRMATION_PHRASE) {
      setModalError(`Please type exact confirmation phrase: ${CONFIRMATION_PHRASE}`);
      return;
    }

    setIsSubmitting(true);
    setModalError(null);

    try {
      const result = await runCleanup({
        company_ids: selectedCompanyIds,
        mode: 'purge',
        confirmation_phrase: CONFIRMATION_PHRASE,
      });
      toast.success(
        result.message || `Successfully purged ${selectedCompanyIds.length} test company(ies).`
      );
      if (onSuccess) onSuccess(result);
      onClose();
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to purge companies.';
      setModalError(msg);
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-800 w-full max-w-4xl max-h-[92vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-800 bg-gray-50/80 dark:bg-gray-800/50">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-indigo-100 dark:bg-indigo-950/70 text-indigo-600 dark:text-indigo-400">
              <Building2 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
                <span>Bulk Company Cleanup Preview</span>
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300 font-semibold">
                  {selectedCompanyIds.length} Selected
                </span>
              </h2>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Preview dependencies, student records, linked recruitment drives, and safety classifications before executing cleanup.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded-lg hover:bg-gray-200/50 dark:hover:bg-gray-700 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {/* Loading State */}
          {isCleanupLoading && !cleanupPreview && (
            <div className="flex flex-col items-center justify-center py-16 space-y-3">
              <RefreshCw className="w-8 h-8 text-indigo-600 animate-spin" />
              <p className="text-sm font-medium text-gray-600 dark:text-gray-300">
                Analyzing company dependencies, recruitment drives, and student records...
              </p>
            </div>
          )}

          {/* Modal Error */}
          {modalError && (
            <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-sm flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="font-semibold">Safety or Execution Error</p>
                <p className="text-xs mt-1 leading-relaxed">{modalError}</p>
              </div>
            </div>
          )}

          {cleanupPreview && (
            <>
              {/* Summary Metrics Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-gray-50 dark:bg-gray-800/70 p-3.5 rounded-xl border border-gray-200 dark:border-gray-700/80">
                  <span className="text-[11px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Total Companies
                  </span>
                  <p className="text-xl font-bold text-gray-900 dark:text-white mt-0.5">
                    {candidates.length}
                  </p>
                  <span className="text-[11px] text-gray-400">Selected for cleanup</span>
                </div>

                <div className="bg-emerald-50 dark:bg-emerald-950/40 p-3.5 rounded-xl border border-emerald-200 dark:border-emerald-800/80">
                  <span className="text-[11px] font-semibold text-emerald-700 dark:text-emerald-400 uppercase tracking-wider flex items-center gap-1">
                    <ShieldCheck className="w-3.5 h-3.5" /> Safe to Purge
                  </span>
                  <p className="text-xl font-bold text-emerald-700 dark:text-emerald-300 mt-0.5">
                    {summary.total_safe_to_purge}
                  </p>
                  <span className="text-[11px] text-emerald-600/80 dark:text-emerald-400/70">
                    Disposable test companies
                  </span>
                </div>

                <div className="bg-amber-50 dark:bg-amber-950/40 p-3.5 rounded-xl border border-amber-200 dark:border-amber-800/80">
                  <span className="text-[11px] font-semibold text-amber-700 dark:text-amber-400 uppercase tracking-wider flex items-center gap-1">
                    <ShieldAlert className="w-3.5 h-3.5" /> Requires Archive
                  </span>
                  <p className="text-xl font-bold text-amber-700 dark:text-amber-300 mt-0.5">
                    {summary.total_requires_archive}
                  </p>
                  <span className="text-[11px] text-amber-600/80 dark:text-amber-400/70">
                    Retain history via archive
                  </span>
                </div>

                <div className="bg-rose-50 dark:bg-rose-950/40 p-3.5 rounded-xl border border-rose-200 dark:border-rose-800/80">
                  <span className="text-[11px] font-semibold text-rose-700 dark:text-rose-400 uppercase tracking-wider flex items-center gap-1">
                    <ShieldX className="w-3.5 h-3.5" /> Protected Genuine
                  </span>
                  <p className="text-xl font-bold text-rose-700 dark:text-rose-300 mt-0.5">
                    {summary.total_protected_genuine}
                  </p>
                  <span className="text-[11px] text-rose-600/80 dark:text-rose-400/70">
                    Permanent deletion blocked
                  </span>
                </div>
              </div>

              {/* Dependent Records Aggregate Stats */}
              <div className="bg-gray-50/70 dark:bg-gray-800/40 rounded-xl p-3.5 border border-gray-200 dark:border-gray-800">
                <h4 className="text-xs font-bold text-gray-700 dark:text-gray-300 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5 text-indigo-500" />
                  Aggregate Dependent Record Counts
                </h4>
                <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2.5 text-center">
                  <div className="p-2 bg-white dark:bg-gray-800 rounded-lg border border-gray-200/80 dark:border-gray-700/80 shadow-2xs">
                    <Briefcase className="w-3.5 h-3.5 text-indigo-500 mx-auto mb-1" />
                    <span className="text-xs font-bold text-gray-800 dark:text-gray-100">
                      {summary.total_dependent_jobs}
                    </span>
                    <p className="text-[10px] text-gray-500">Linked Jobs</p>
                  </div>
                  <div className="p-2 bg-white dark:bg-gray-800 rounded-lg border border-gray-200/80 dark:border-gray-700/80 shadow-2xs">
                    <Megaphone className="w-3.5 h-3.5 text-indigo-500 mx-auto mb-1" />
                    <span className="text-xs font-bold text-gray-800 dark:text-gray-100">
                      {summary.total_dependent_circulars}
                    </span>
                    <p className="text-[10px] text-gray-500">Recruitment Drives</p>
                  </div>
                  <div className="p-2 bg-white dark:bg-gray-800 rounded-lg border border-gray-200/80 dark:border-gray-700/80 shadow-2xs">
                    <Users className="w-3.5 h-3.5 text-blue-500 mx-auto mb-1" />
                    <span className="text-xs font-bold text-gray-800 dark:text-gray-100">
                      {summary.total_dependent_applications}
                    </span>
                    <p className="text-[10px] text-gray-500">Applications</p>
                  </div>
                  <div className="p-2 bg-white dark:bg-gray-800 rounded-lg border border-gray-200/80 dark:border-gray-700/80 shadow-2xs">
                    <FileText className="w-3.5 h-3.5 text-purple-500 mx-auto mb-1" />
                    <span className="text-xs font-bold text-gray-800 dark:text-gray-100">
                      {summary.total_dependent_result_batches}
                    </span>
                    <p className="text-[10px] text-gray-500">Result Batches</p>
                  </div>
                  <div className="p-2 bg-white dark:bg-gray-800 rounded-lg border border-gray-200/80 dark:border-gray-700/80 shadow-2xs">
                    <Award className="w-3.5 h-3.5 text-amber-500 mx-auto mb-1" />
                    <span className="text-xs font-bold text-gray-800 dark:text-gray-100">
                      {summary.total_dependent_offers}
                    </span>
                    <p className="text-[10px] text-gray-500">Verified Offers</p>
                  </div>
                  <div className="p-2 bg-white dark:bg-gray-800 rounded-lg border border-gray-200/80 dark:border-gray-700/80 shadow-2xs">
                    <Paperclip className="w-3.5 h-3.5 text-teal-500 mx-auto mb-1" />
                    <span className="text-xs font-bold text-gray-800 dark:text-gray-100">
                      {summary.total_files_identified}
                    </span>
                    <p className="text-[10px] text-gray-500">Storage Files</p>
                  </div>
                  <div className="p-2 bg-white dark:bg-gray-800 rounded-lg border border-gray-200/80 dark:border-gray-700/80 shadow-2xs">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-500 mx-auto mb-1" />
                    <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400">
                      {summary.total_shared_files_preserved}
                    </span>
                    <p className="text-[10px] text-gray-500">Preserved Shared</p>
                  </div>
                </div>
              </div>

              {/* Safety Alerts */}
              {hasProtected && (
                <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 flex items-start gap-3">
                  <ShieldX className="w-5 h-5 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
                  <div className="text-xs space-y-1 text-rose-800 dark:text-rose-200">
                    <p className="font-bold text-sm">Permanent Purge Is Blocked for Genuine Records</p>
                    <p>
                      One or more selected companies are classified as{' '}
                      <span className="font-bold">PROTECTED_GENUINE</span> because they have accepted placement offers or genuine student history.
                      EduMatrix strictly prevents permanent deletion of genuine institutional placement records.
                    </p>
                    <p className="font-medium text-rose-700 dark:text-rose-300">
                      👉 You can use <span className="underline font-bold">Safe Archive</span> to non-destructively deactivate companies and close roles without data loss, or deselect protected companies.
                    </p>
                  </div>
                </div>
              )}

              {!hasProtected && hasRequiresArchive && (
                <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 flex items-start gap-3">
                  <ShieldAlert className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                  <div className="text-xs space-y-1 text-amber-800 dark:text-amber-200">
                    <p className="font-bold text-sm">Archive Recommended for Dependent History</p>
                    <p>
                      One or more selected companies have active applications, confirmed round outcomes, or referenced roles that require historical retention.
                      Permanent purge is restricted. Please select <span className="font-bold">Safe Archive</span>.
                    </p>
                  </div>
                </div>
              )}

              {canPurgeAll && (
                <div className="p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 flex items-start gap-3">
                  <ShieldCheck className="w-5 h-5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                  <div className="text-xs space-y-0.5 text-emerald-800 dark:text-emerald-200">
                    <p className="font-bold text-sm">All Selected Companies Are Safe to Purge</p>
                    <p>
                      No accepted offers or genuine student records were detected. You may permanently purge disposable test data or non-destructively archive them.
                    </p>
                  </div>
                </div>
              )}

              {/* Per-Company Detail List */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-gray-700 dark:text-gray-300 uppercase tracking-wider">
                  Company Candidates Breakdown ({candidates.length})
                </h4>

                <div className="space-y-2.5">
                  {candidates.map((cand) => {
                    const isExpanded = expandedCompanyIds.has(cand.company_id);
                    const counts = cand.dependent_counts || {};
                    const breakdown = cand.records_breakdown || {};

                    return (
                      <div
                        key={cand.company_id}
                        className={`rounded-xl border transition-all ${
                          cand.safety_classification === 'PROTECTED_GENUINE'
                            ? 'bg-rose-50/20 dark:bg-rose-950/10 border-rose-200 dark:border-rose-900/60'
                            : cand.safety_classification === 'REQUIRES_ARCHIVE'
                            ? 'bg-amber-50/20 dark:bg-amber-950/10 border-amber-200 dark:border-amber-900/60'
                            : 'bg-white dark:bg-gray-800/80 border-gray-200 dark:border-gray-700/80'
                        }`}
                      >
                        {/* Company Card Header */}
                        <div
                          onClick={() => toggleExpandCompany(cand.company_id)}
                          className="px-4 py-3.5 flex items-center justify-between cursor-pointer select-none hover:bg-gray-50/60 dark:hover:bg-gray-750/50 rounded-xl"
                        >
                          <div className="flex items-center gap-3 min-w-0">
                            <Building2 className="w-4 h-4 text-indigo-500 shrink-0" />
                            <div className="min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-semibold text-sm text-gray-900 dark:text-white truncate">
                                  {cand.company_name}
                                </span>
                                <span className="text-[11px] px-1.5 py-0.5 rounded-md bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 font-mono">
                                  ID: {cand.company_id}
                                </span>
                                <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                                  cand.is_active
                                    ? 'bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300'
                                    : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                                }`}>
                                  {cand.is_active ? 'Active' : 'Inactive'}
                                </span>
                              </div>

                              {/* Signals / Flags */}
                              <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                                {cand.flag_reasons?.map((flag, idx) => (
                                  <span
                                    key={idx}
                                    className="text-[10px] px-1.5 py-0.2 rounded-md bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400"
                                  >
                                    🏷️ {flag}
                                  </span>
                                ))}
                              </div>
                            </div>
                          </div>

                          <div className="flex items-center gap-3 shrink-0">
                            {/* Classification Badge */}
                            {cand.safety_classification === 'SAFE_TO_PURGE' && (
                              <span className="px-2.5 py-1 text-xs font-bold rounded-lg bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 flex items-center gap-1">
                                <ShieldCheck className="w-3.5 h-3.5" /> Safe to Purge
                              </span>
                            )}
                            {cand.safety_classification === 'REQUIRES_ARCHIVE' && (
                              <span className="px-2.5 py-1 text-xs font-bold rounded-lg bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300 border border-amber-200 dark:border-amber-800 flex items-center gap-1">
                                <ShieldAlert className="w-3.5 h-3.5" /> Requires Archive
                              </span>
                            )}
                            {cand.safety_classification === 'PROTECTED_GENUINE' && (
                              <span className="px-2.5 py-1 text-xs font-bold rounded-lg bg-rose-100 text-rose-800 dark:bg-rose-950/80 dark:text-rose-300 border border-rose-200 dark:border-rose-800 flex items-center gap-1">
                                <ShieldX className="w-3.5 h-3.5" /> Protected Genuine
                              </span>
                            )}

                            {isExpanded ? (
                              <ChevronUp className="w-4 h-4 text-gray-400" />
                            ) : (
                              <ChevronDown className="w-4 h-4 text-gray-400" />
                            )}
                          </div>
                        </div>

                        {/* Expandable Details */}
                        {isExpanded && (
                          <div className="px-4 pb-4 pt-1 border-t border-gray-100 dark:border-gray-800 space-y-3.5 text-xs">
                            {/* Protection Reasons Notice */}
                            {cand.protection_reasons?.length > 0 && (
                              <div className="p-2.5 rounded-lg bg-amber-50/70 dark:bg-amber-950/30 border border-amber-200/70 dark:border-amber-800/60 text-amber-900 dark:text-amber-200 space-y-1">
                                <p className="font-bold flex items-center gap-1.5">
                                  <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
                                  Protection Notes & Safeguards:
                                </p>
                                <ul className="list-disc list-inside space-y-0.5 text-[11px] text-amber-800 dark:text-amber-300">
                                  {cand.protection_reasons.map((reason, rIdx) => (
                                    <li key={rIdx}>{reason}</li>
                                  ))}
                                </ul>
                              </div>
                            )}

                            {/* Linked Drives and Jobs */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                              {/* Linked Drives */}
                              <div className="p-2.5 bg-gray-50/80 dark:bg-gray-800/60 rounded-lg border border-gray-200/60 dark:border-gray-700/60">
                                <p className="font-semibold text-gray-800 dark:text-gray-200 flex items-center gap-1.5 mb-1">
                                  <Megaphone className="w-3.5 h-3.5 text-indigo-500" />
                                  Linked Recruitment Drives ({counts.circulars_count || 0})
                                </p>
                                {cand.linked_circular_titles?.length > 0 ? (
                                  <div className="flex flex-wrap gap-1 mt-1">
                                    {cand.linked_circular_titles.map((title, idx) => (
                                      <span
                                        key={idx}
                                        className="text-[10px] px-2 py-0.5 rounded-md bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-gray-600"
                                      >
                                        📢 {title}
                                      </span>
                                    ))}
                                  </div>
                                ) : (
                                  <p className="text-[11px] text-gray-400 italic">No recruitment drives linked</p>
                                )}
                              </div>

                              {/* Linked Job Postings */}
                              <div className="p-2.5 bg-gray-50/80 dark:bg-gray-800/60 rounded-lg border border-gray-200/60 dark:border-gray-700/60">
                                <p className="font-semibold text-gray-800 dark:text-gray-200 flex items-center gap-1.5 mb-1">
                                  <Briefcase className="w-3.5 h-3.5 text-indigo-500" />
                                  Job Roles ({counts.jobs_count || 0})
                                </p>
                                {cand.linked_job_titles?.length > 0 ? (
                                  <div className="flex flex-wrap gap-1 mt-1">
                                    {cand.linked_job_titles.map((title, idx) => (
                                      <span
                                        key={idx}
                                        className="text-[10px] px-2 py-0.5 rounded-md bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-gray-600"
                                      >
                                        💼 {title}
                                      </span>
                                    ))}
                                  </div>
                                ) : (
                                  <p className="text-[11px] text-gray-400 italic">No job postings created</p>
                                )}
                              </div>
                            </div>

                            {/* Detailed Records Grid */}
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                              <div className="p-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200/60 dark:border-gray-700/60">
                                <span className="text-gray-500">Applications:</span>{' '}
                                <span className="font-bold text-gray-800 dark:text-gray-100">
                                  {counts.applications_count || 0}
                                </span>
                                <span className="text-[10px] text-gray-400 block">
                                  {cand.affected_student_count || 0} unique students
                                </span>
                              </div>
                              <div className="p-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200/60 dark:border-gray-700/60">
                                <span className="text-gray-500">Rounds / Outcomes:</span>{' '}
                                <span className="font-bold text-gray-800 dark:text-gray-100">
                                  {counts.rounds_count || 0} / {counts.outcomes_count || 0}
                                </span>
                                <span className="text-[10px] text-gray-400 block">
                                  {counts.confirmed_outcomes_count || 0} confirmed
                                </span>
                              </div>
                              <div className="p-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200/60 dark:border-gray-700/60">
                                <span className="text-gray-500">Result Batches:</span>{' '}
                                <span className="font-bold text-gray-800 dark:text-gray-100">
                                  {counts.result_batches_count || 0} ({counts.result_items_count || 0} items)
                                </span>
                              </div>
                              <div className="p-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200/60 dark:border-gray-700/60">
                                <span className="text-gray-500">Verified Offers:</span>{' '}
                                <span className="font-bold text-gray-800 dark:text-gray-100">
                                  {counts.offers_count || 0}
                                </span>
                                <span className="text-[10px] text-gray-400 block">
                                  {counts.accepted_offers_count || 0} accepted
                                </span>
                              </div>
                            </div>

                            {/* Exact Records Simulation Table */}
                            <div className="p-2.5 rounded-lg bg-indigo-50/40 dark:bg-indigo-950/20 border border-indigo-200/50 dark:border-indigo-800/40">
                              <p className="font-bold text-indigo-950 dark:text-indigo-200 mb-1.5 flex items-center gap-1.5">
                                <Clock className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                                Action Simulation & Exact Records Affected:
                              </p>
                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
                                <div className="space-y-0.5 text-gray-600 dark:text-gray-300">
                                  <span className="font-semibold text-rose-700 dark:text-rose-400">If Purged Permanently:</span>
                                  <p>• {breakdown.companies_to_delete || 1} company record deleted</p>
                                  <p>• {breakdown.jobs_to_delete || 0} job posting(s) deleted</p>
                                  <p>• {breakdown.circulars_to_delete || 0} recruitment drive(s) deleted</p>
                                  <p>• {breakdown.applications_to_delete || 0} application(s) deleted</p>
                                  <p>• {breakdown.files_to_delete || 0} unshared storage file(s) removed</p>
                                  <p className="text-emerald-600 dark:text-emerald-400 font-medium">
                                    • {breakdown.shared_files_preserved || 0} shared file(s) safely preserved
                                  </p>
                                </div>
                                <div className="space-y-0.5 text-gray-600 dark:text-gray-300">
                                  <span className="font-semibold text-amber-700 dark:text-amber-400">If Archived Safely:</span>
                                  <p>• {breakdown.companies_to_archive || 1} company deactivated (is_active=False)</p>
                                  <p>• {breakdown.jobs_to_close || 0} job posting(s) closed</p>
                                  <p>• {breakdown.circulars_to_archive || 0} recruitment drive(s) archived</p>
                                  <p className="text-emerald-600 dark:text-emerald-400 font-medium">
                                    • All applications, offers, and files preserved 100%
                                  </p>
                                </div>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-800 bg-gray-50/80 dark:bg-gray-800/50 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 text-xs font-semibold rounded-lg bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600 transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
          </div>

          <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
            {/* Safe Archive Action */}
            <button
              onClick={handleExecuteArchive}
              disabled={isSubmitting || candidates.length === 0}
              className="flex-1 sm:flex-none inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-xs font-bold bg-amber-600 hover:bg-amber-700 text-white shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              title="Deactivate companies and close jobs without deleting any data"
            >
              <Archive className="w-4 h-4" />
              <span>Safe Archive ({selectedCompanyIds.length} Companies)</span>
            </button>

            {/* Permanent Purge Trigger */}
            <button
              onClick={() => setPurgeConfirmOpen(!purgeConfirmOpen)}
              disabled={isSubmitting || candidates.length === 0 || !canPurgeAll}
              className={`flex-1 sm:flex-none inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-xs font-bold transition-all shadow-sm ${
                canPurgeAll
                  ? 'bg-rose-600 hover:bg-rose-700 text-white cursor-pointer'
                  : 'bg-gray-200 dark:bg-gray-800 text-gray-400 dark:text-gray-500 cursor-not-allowed'
              }`}
              title={
                canPurgeAll
                  ? 'Permanently delete disposable test companies'
                  : 'Purge disabled because one or more companies have protected genuine records or require archival'
              }
            >
              <Trash2 className="w-4 h-4" />
              <span>Permanently Purge ({summary.total_safe_to_purge})</span>
            </button>
          </div>
        </div>

        {/* Purge Confirmation Drawer / Inline Section */}
        {purgeConfirmOpen && canPurgeAll && (
          <div className="px-6 py-4 border-t border-rose-200 dark:border-rose-900 bg-rose-50/90 dark:bg-rose-950/70 animate-in slide-in-from-bottom-2">
            <div className="max-w-xl mx-auto space-y-3">
              <div className="flex items-start gap-2.5">
                <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-sm font-bold text-rose-900 dark:text-rose-100">
                    Confirm Permanent Deletion of {selectedCompanyIds.length} Test Company(ies)
                  </h4>
                  <p className="text-xs text-rose-700 dark:text-rose-300 mt-0.5">
                    This action is destructive and will permanently purge the selected test companies, exclusive jobs, test recruitment drives, result batches, and unshared files.
                  </p>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-[11px] font-semibold text-rose-800 dark:text-rose-200 block">
                  To confirm, type{' '}
                  <span className="font-mono bg-rose-100 dark:bg-rose-900 px-1.5 py-0.5 rounded font-bold select-all text-rose-900 dark:text-rose-100">
                    {CONFIRMATION_PHRASE}
                  </span>{' '}
                  below:
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={confirmationInput}
                    onChange={(e) => setConfirmationInput(e.target.value)}
                    placeholder={CONFIRMATION_PHRASE}
                    className="flex-1 px-3 py-2 text-xs font-mono border border-rose-300 dark:border-rose-700 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-rose-500"
                  />
                  <button
                    onClick={handleExecutePurge}
                    disabled={isSubmitting || confirmationInput.trim() !== CONFIRMATION_PHRASE}
                    className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-bold disabled:opacity-40 disabled:cursor-not-allowed shadow-sm transition-all flex items-center gap-1.5 cursor-pointer"
                  >
                    {isSubmitting ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>Purging...</span>
                      </>
                    ) : (
                      <>
                        <Trash2 className="w-3.5 h-3.5" />
                        <span>Confirm Purge</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default BulkCompanyCleanupModal;
