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
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import toast from 'react-hot-toast';

const CONFIRMATION_PHRASE = 'CONFIRM_PURGE_TEST_DATA';

const BulkDriveCleanupModal = ({
  isOpen,
  onClose,
  selectedCircularIds = [],
  onSuccess,
}) => {
  const {
    drivesCleanupPreview,
    isCleanupLoading,
    cleanupError,
    fetchDrivesCleanupPreview,
    runCleanup,
  } = usePlacementStore();

  const [expandedDriveIds, setExpandedDriveIds] = useState(new Set());
  const [purgeConfirmOpen, setPurgeConfirmOpen] = useState(false);
  const [confirmationInput, setConfirmationInput] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [modalError, setModalError] = useState(null);

  // Fetch preview whenever modal opens with circular IDs
  useEffect(() => {
    if (isOpen && selectedCircularIds.length > 0) {
      setModalError(null);
      setPurgeConfirmOpen(false);
      setConfirmationInput('');
      fetchDrivesCleanupPreview({ circular_ids: selectedCircularIds }).catch((err) => {
        const msg = err.response?.data?.detail || err.message || 'Failed to generate drives cleanup preview';
        setModalError(msg);
      });
    }
  }, [isOpen, selectedCircularIds, fetchDrivesCleanupPreview]);

  const drives = drivesCleanupPreview?.drives || [];
  const summary = drivesCleanupPreview?.summary || {
    total_drives_flagged: 0,
    total_drives_safe_to_purge: 0,
    total_drives_requires_archive: 0,
    total_drives_protected_genuine: 0,
    total_dependent_jobs: 0,
    total_dependent_applications: 0,
    total_dependent_result_batches: 0,
    total_dependent_offers: 0,
    total_dependent_accepted_offers: 0,
    total_files_identified: 0,
    total_shared_files_preserved: 0,
  };

  const hasProtected = useMemo(() => {
    return drives.some((d) => d.safety_classification === 'PROTECTED_GENUINE');
  }, [drives]);

  const hasRequiresArchive = useMemo(() => {
    return drives.some((d) => d.safety_classification === 'REQUIRES_ARCHIVE');
  }, [drives]);

  const canPurgeAll = useMemo(() => {
    return drives.length > 0 && drives.every((d) => d.safety_classification === 'SAFE_TO_PURGE');
  }, [drives]);

  const toggleExpandDrive = (id) => {
    setExpandedDriveIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleArchive = async () => {
    setIsSubmitting(true);
    setModalError(null);
    try {
      const result = await runCleanup({
        circular_ids: selectedCircularIds,
        mode: 'archive',
      });
      toast.success(result.message || 'Recruitment drives archived successfully!');
      if (onSuccess) onSuccess(result);
      onClose();
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to archive drives';
      setModalError(msg);
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handlePurge = async () => {
    if (confirmationInput !== CONFIRMATION_PHRASE) {
      toast.error(`Please type "${CONFIRMATION_PHRASE}" to confirm permanent purge.`);
      return;
    }

    setIsSubmitting(true);
    setModalError(null);
    try {
      const result = await runCleanup({
        circular_ids: selectedCircularIds,
        mode: 'purge',
        confirmation_phrase: CONFIRMATION_PHRASE,
      });
      toast.success(result.message || 'Test recruitment drives purged successfully!');
      if (onSuccess) onSuccess(result);
      onClose();
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to purge test drives';
      setModalError(msg);
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm overflow-y-auto">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-800 w-full max-w-4xl max-h-[92vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="p-5 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between bg-gray-50/50 dark:bg-gray-800/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-100 dark:bg-indigo-950/80 text-indigo-600 dark:text-indigo-400 flex items-center justify-center border border-indigo-200 dark:border-indigo-800">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
                <span>Bulk Manage Recruitment Drives</span>
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                  {selectedCircularIds.length} Selected
                </span>
              </h2>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                Preview-first inspection of dependencies, safety classifications, and protection rules.
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Error */}
        {modalError && (
          <div className="mx-5 mt-4 p-3.5 bg-red-50 dark:bg-red-950/50 border border-red-200 dark:border-red-800 rounded-xl text-xs text-red-700 dark:text-red-300 flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0 text-red-500" />
            <div>
              <p className="font-semibold">Operation Notice</p>
              <p className="mt-0.5">{modalError}</p>
            </div>
          </div>
        )}

        {/* Modal Body */}
        <div className="p-5 overflow-y-auto space-y-5 flex-1">
          {isCleanupLoading && !drivesCleanupPreview ? (
            <div className="py-16 text-center text-gray-500 dark:text-gray-400">
              <RefreshCw className="w-8 h-8 text-indigo-600 animate-spin mx-auto mb-3" />
              <p className="font-medium text-sm">Analyzing drive dependencies and safety constraints...</p>
              <p className="text-xs text-gray-400 mt-1">Inspecting jobs, applications, rounds, offers, and attachments.</p>
            </div>
          ) : drives.length === 0 ? (
            <div className="py-12 text-center text-gray-500 dark:text-gray-400">
              <AlertCircle className="w-10 h-10 text-gray-400 mx-auto mb-2" />
              <p className="font-medium">No drives loaded in preview.</p>
            </div>
          ) : (
            <>
              {/* Summary Metrics Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                <div className="p-3 bg-gray-50 dark:bg-gray-800/60 rounded-xl border border-gray-200 dark:border-gray-800">
                  <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider block">
                    Selected Drives
                  </span>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className="text-xl font-bold text-gray-900 dark:text-white">
                      {summary.total_drives_flagged || drives.length}
                    </span>
                    <span className="text-[11px] text-gray-500 dark:text-gray-400">
                      ({summary.total_dependent_jobs} roles)
                    </span>
                  </div>
                </div>

                <div className="p-3 bg-emerald-50/60 dark:bg-emerald-950/30 rounded-xl border border-emerald-200/80 dark:border-emerald-800/60">
                  <span className="text-[11px] font-medium text-emerald-700 dark:text-emerald-400 uppercase tracking-wider block flex items-center gap-1">
                    <ShieldCheck className="w-3.5 h-3.5" /> Safe to Purge
                  </span>
                  <p className="text-xl font-bold text-emerald-800 dark:text-emerald-300 mt-1">
                    {summary.total_drives_safe_to_purge}
                  </p>
                </div>

                <div className="p-3 bg-amber-50/60 dark:bg-amber-950/30 rounded-xl border border-amber-200/80 dark:border-amber-800/60">
                  <span className="text-[11px] font-medium text-amber-700 dark:text-amber-400 uppercase tracking-wider block flex items-center gap-1">
                    <ShieldAlert className="w-3.5 h-3.5" /> Requires Archive
                  </span>
                  <p className="text-xl font-bold text-amber-800 dark:text-amber-300 mt-1">
                    {summary.total_drives_requires_archive}
                  </p>
                </div>

                <div className="p-3 bg-red-50/60 dark:bg-red-950/30 rounded-xl border border-red-200/80 dark:border-red-800/60">
                  <span className="text-[11px] font-medium text-red-700 dark:text-red-400 uppercase tracking-wider block flex items-center gap-1">
                    <ShieldX className="w-3.5 h-3.5" /> Protected Genuine
                  </span>
                  <p className="text-xl font-bold text-red-800 dark:text-red-300 mt-1">
                    {summary.total_drives_protected_genuine}
                  </p>
                </div>
              </div>

              {/* Dependent Invariants Breakdown */}
              <div className="p-3.5 bg-gray-50 dark:bg-gray-800/40 rounded-xl border border-gray-200 dark:border-gray-800">
                <p className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">
                  Total Dependent Records Across Selection:
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs">
                  <div className="flex items-center gap-1.5 text-gray-600 dark:text-gray-400">
                    <Briefcase className="w-3.5 h-3.5 text-indigo-500" />
                    <span>{summary.total_dependent_jobs} Linked Role(s)</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-gray-600 dark:text-gray-400">
                    <Users className="w-3.5 h-3.5 text-blue-500" />
                    <span>{summary.total_dependent_applications} Application(s)</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-gray-600 dark:text-gray-400">
                    <FileText className="w-3.5 h-3.5 text-amber-500" />
                    <span>{summary.total_dependent_result_batches} Result Batch(es)</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-gray-600 dark:text-gray-400">
                    <Award className="w-3.5 h-3.5 text-purple-500" />
                    <span>
                      {summary.total_dependent_offers} Offer(s) ({summary.total_dependent_accepted_offers} Accepted)
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 text-gray-600 dark:text-gray-400">
                    <Paperclip className="w-3.5 h-3.5 text-emerald-500" />
                    <span>
                      {summary.total_files_identified} File(s) ({summary.total_shared_files_preserved} Shared Preserved)
                    </span>
                  </div>
                </div>
              </div>

              {/* Safety Policy Notice */}
              {hasProtected ? (
                <div className="p-3.5 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-xl text-xs text-red-800 dark:text-red-300 flex items-start gap-2.5">
                  <ShieldX className="w-4 h-4 text-red-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="font-semibold">Permanent Purge Strictly Blocked</p>
                    <p className="mt-0.5">
                      One or more selected drives contain accepted placement offers or genuine student activity.
                      Institutions must permanently retain genuine placement history.
                      You can use <strong>Safe Archive</strong> to deactivate eligible test drives without losing genuine audit records.
                    </p>
                  </div>
                </div>
              ) : hasRequiresArchive ? (
                <div className="p-3.5 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-xl text-xs text-amber-800 dark:text-amber-300 flex items-start gap-2.5">
                  <ShieldAlert className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="font-semibold">Active Recruitment Records Require Archive</p>
                    <p className="mt-0.5">
                      Selected drives contain active student applications, pending offers, or confirmed outcomes.
                      Permanent deletion is blocked to protect ongoing student evaluations.
                      Use <strong>Safe Archive</strong> to safely hide them from active drive lists.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="p-3.5 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-xl text-xs text-emerald-800 dark:text-emerald-300 flex items-start gap-2.5">
                  <ShieldCheck className="w-4 h-4 text-emerald-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="font-semibold">Safe for Bulk Purge</p>
                    <p className="mt-0.5">
                      All {drives.length} selected recruitment drives are disposable synthetic test records.
                      No genuine students, accepted offers, or shared institutional files will be affected.
                    </p>
                  </div>
                </div>
              )}

              {/* Drive Cards List */}
              <div className="space-y-2.5">
                <div className="flex items-center justify-between text-xs font-semibold text-gray-700 dark:text-gray-300 px-1">
                  <span>Selected Recruitment Drives Breakdown ({drives.length})</span>
                  <button
                    onClick={() => {
                      if (expandedDriveIds.size === drives.length) {
                        setExpandedDriveIds(new Set());
                      } else {
                        setExpandedDriveIds(new Set(drives.map((d) => d.circular_id)));
                      }
                    }}
                    className="text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer"
                  >
                    {expandedDriveIds.size === drives.length ? 'Collapse All' : 'Expand All'}
                  </button>
                </div>

                {drives.map((drive) => {
                  const isExpanded = expandedDriveIds.has(drive.circular_id);
                  const isSafe = drive.safety_classification === 'SAFE_TO_PURGE';
                  const isArchive = drive.safety_classification === 'REQUIRES_ARCHIVE';

                  return (
                    <div
                      key={drive.circular_id}
                      className="bg-white dark:bg-gray-800/80 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden shadow-sm"
                    >
                      <div
                        onClick={() => toggleExpandDrive(drive.circular_id)}
                        className="p-3.5 flex items-center justify-between gap-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                      >
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          {isSafe ? (
                            <span className="p-1 rounded-lg bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 flex-shrink-0">
                              <ShieldCheck className="w-4 h-4" />
                            </span>
                          ) : isArchive ? (
                            <span className="p-1 rounded-lg bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300 flex-shrink-0">
                              <ShieldAlert className="w-4 h-4" />
                            </span>
                          ) : (
                            <span className="p-1 rounded-lg bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-300 flex-shrink-0">
                              <ShieldX className="w-4 h-4" />
                            </span>
                          )}

                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <h4 className="text-sm font-bold text-gray-900 dark:text-white truncate">
                                {drive.title}
                              </h4>
                              <span className="text-[11px] font-semibold px-2 py-0.2 rounded-full uppercase bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">
                                {drive.status}
                              </span>
                            </div>
                            <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                              <span className="flex items-center gap-1 font-medium text-gray-700 dark:text-gray-300">
                                <Building2 className="w-3 h-3 text-indigo-500" />
                                {drive.company_name}
                              </span>
                              <span>ID: {drive.circular_id}</span>
                              {drive.drive_date && (
                                <span className="flex items-center gap-1">
                                  <Clock className="w-3 h-3 text-gray-400" />
                                  Drive: {new Date(drive.drive_date).toLocaleDateString()}
                                </span>
                              )}
                              <span>{drive.linked_job_ids?.length || 0} role(s)</span>
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-2 flex-shrink-0">
                          <span
                            className={`px-2 py-0.5 text-[11px] font-semibold rounded-full border ${
                              isSafe
                                ? 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
                                : isArchive
                                ? 'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800'
                                : 'bg-red-50 dark:bg-red-950/60 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800'
                            }`}
                          >
                            {drive.safety_classification.replace(/_/g, ' ')}
                          </span>
                          {isExpanded ? (
                            <ChevronUp className="w-4 h-4 text-gray-400" />
                          ) : (
                            <ChevronDown className="w-4 h-4 text-gray-400" />
                          )}
                        </div>
                      </div>

                      {/* Expanded Details */}
                      {isExpanded && (
                        <div className="px-4 pb-4 pt-2 border-t border-gray-100 dark:border-gray-800/80 bg-gray-50/50 dark:bg-gray-900/40 space-y-2 text-xs">
                          {/* Protection Reasons */}
                          {drive.protection_reasons?.length > 0 && (
                            <div className="space-y-1">
                              <span className="font-semibold text-gray-700 dark:text-gray-300">Protection Notes:</span>
                              <ul className="list-disc list-inside space-y-0.5 text-gray-600 dark:text-gray-400 pl-1">
                                {drive.protection_reasons.map((reason, idx) => (
                                  <li key={idx}>{reason}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {/* Linked Jobs */}
                          {drive.linked_job_titles?.length > 0 && (
                            <div className="space-y-1">
                              <span className="font-semibold text-gray-700 dark:text-gray-300">Linked Roles:</span>
                              <div className="flex flex-wrap gap-1.5">
                                {drive.linked_job_titles.map((title, idx) => (
                                  <span
                                    key={idx}
                                    className="px-2 py-0.5 rounded bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300"
                                  >
                                    {title}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Metric pills */}
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-[11px]">
                            <div className="p-2 bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700">
                              <span className="text-gray-500">Applications:</span>{' '}
                              <span className="font-semibold text-gray-900 dark:text-white">
                                {drive.dependent_counts?.applications_count || 0}
                              </span>
                            </div>
                            <div className="p-2 bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700">
                              <span className="text-gray-500">Rounds / Outcomes:</span>{' '}
                              <span className="font-semibold text-gray-900 dark:text-white">
                                {drive.dependent_counts?.rounds_count || 0} /{' '}
                                {drive.dependent_counts?.outcomes_count || 0}
                              </span>
                            </div>
                            <div className="p-2 bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700">
                              <span className="text-gray-500">Result Batches:</span>{' '}
                              <span className="font-semibold text-gray-900 dark:text-white">
                                {drive.dependent_counts?.result_batches_count || 0}
                              </span>
                            </div>
                            <div className="p-2 bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700">
                              <span className="text-gray-500">Offers (Accepted):</span>{' '}
                              <span className="font-semibold text-gray-900 dark:text-white">
                                {drive.dependent_counts?.offers_count || 0} (
                                {drive.dependent_counts?.accepted_offers_count || 0})
                              </span>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Confirmation Screen if Purge is clicked */}
              {purgeConfirmOpen && (
                <div className="p-4 bg-red-50 dark:bg-red-950/40 border border-red-300 dark:border-red-800 rounded-xl space-y-3">
                  <div className="flex items-start gap-2.5">
                    <AlertTriangle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <h4 className="text-sm font-bold text-red-900 dark:text-red-200">
                        Confirm Permanent Deletion of {drives.length} Drive(s)
                      </h4>
                      <p className="text-xs text-red-700 dark:text-red-300 mt-1">
                        This action cannot be undone. All linked test roles, rounds, batches, and unshared files will be transactionally removed.
                      </p>
                    </div>
                  </div>

                  <div className="space-y-1.5 pt-1">
                    <label className="text-xs font-semibold text-gray-700 dark:text-gray-300 block">
                      Type <code className="bg-red-100 dark:bg-red-900/60 px-1 py-0.5 rounded font-mono font-bold text-red-800 dark:text-red-200">{CONFIRMATION_PHRASE}</code> to confirm:
                    </label>
                    <input
                      type="text"
                      value={confirmationInput}
                      onChange={(e) => setConfirmationInput(e.target.value)}
                      placeholder={CONFIRMATION_PHRASE}
                      className="w-full px-3 py-2 text-xs font-mono bg-white dark:bg-gray-900 border border-red-300 dark:border-red-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 text-gray-900 dark:text-white"
                    />
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-gray-200 dark:border-gray-800 flex flex-wrap items-center justify-between gap-3 bg-gray-50/50 dark:bg-gray-800/50">
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="px-4 py-2 text-xs font-semibold text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors cursor-pointer"
          >
            Cancel
          </button>

          <div className="flex items-center gap-2">
            {/* Archive Button */}
            <button
              onClick={handleArchive}
              disabled={isSubmitting || drives.length === 0}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold bg-amber-500 hover:bg-amber-600 text-white rounded-lg transition-colors cursor-pointer disabled:opacity-50 shadow-sm"
              title="Archive selected drives without deleting placement history"
            >
              <Archive className="w-3.5 h-3.5" />
              <span>Safe Archive ({drives.length})</span>
            </button>

            {/* Purge Button */}
            {canPurgeAll && !purgeConfirmOpen && (
              <button
                onClick={() => setPurgeConfirmOpen(true)}
                disabled={isSubmitting}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors cursor-pointer shadow-sm"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Purge Test Drives ({drives.length})</span>
              </button>
            )}

            {purgeConfirmOpen && (
              <button
                onClick={handlePurge}
                disabled={isSubmitting || confirmationInput !== CONFIRMATION_PHRASE}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors cursor-pointer disabled:opacity-50 shadow-sm"
              >
                {isSubmitting ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Trash2 className="w-3.5 h-3.5" />
                )}
                <span>Execute Permanent Purge</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default BulkDriveCleanupModal;
