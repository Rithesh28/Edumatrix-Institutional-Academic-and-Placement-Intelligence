import React, { useState } from 'react';
import {
  X,
  AlertTriangle,
  Trash2,
  ShieldCheck,
  ShieldAlert,
  CheckCircle2,
  Briefcase,
  Paperclip,
  Check,
  Building2,
  RefreshCw,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import toast from 'react-hot-toast';

const BulkJobDeleteModal = ({
  isOpen,
  onClose,
  selectedJobIds = [],
  jobs = [],
  onSuccess,
}) => {
  const { bulkDeleteJobs } = usePlacementStore();

  const [forceCloseProtected, setForceCloseProtected] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  if (!isOpen) return null;

  // Selected job items lookup
  const selectedJobs = selectedJobIds.map((id) => {
    const job = jobs.find((j) => j.id === id);
    return (
      job || {
        id,
        title: 'Job #' + id.slice(0, 8),
        company_name: 'Unknown Company',
        status: 'unknown',
      }
    );
  });

  const handleExecute = async () => {
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      const res = await bulkDeleteJobs(selectedJobIds, forceCloseProtected);
      setResult(res);
      toast.success(
        `Bulk operation complete: ${res.deleted_count} deleted, ${res.closed_count} closed, ${res.blocked_count} preserved.`
      );
      if (onSuccess) {
        onSuccess(res);
      }
    } catch (err) {
      const msg =
        err.response?.data?.detail || err.message || 'Bulk job deletion failed';
      setErrorMessage(typeof msg === 'string' ? msg : JSON.stringify(msg));
      toast.error('Failed to complete bulk job operation');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    setResult(null);
    setErrorMessage(null);
    setForceCloseProtected(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in">
      <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-2xl w-full max-h-[90vh] flex flex-col shadow-2xl border border-gray-200 dark:border-gray-800 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-gray-200 dark:border-gray-800 bg-gray-50/70 dark:bg-gray-800/50">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-rose-100 dark:bg-rose-950/60 rounded-xl text-rose-600 dark:text-rose-400">
              <Trash2 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-gray-900 dark:text-white">
                Bulk Job Deletion & Safe Cleanup
              </h2>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {selectedJobIds.length} job posting(s) selected for action
              </p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          {errorMessage && (
            <div className="p-4 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 rounded-xl text-sm text-rose-700 dark:text-rose-300 flex items-start space-x-3">
              <AlertTriangle className="w-5 h-5 text-rose-500 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Operation Error</p>
                <p className="text-xs mt-0.5">{errorMessage}</p>
              </div>
            </div>
          )}

          {!result ? (
            <>
              {/* Relationship Safety Notice */}
              <div className="p-4 bg-indigo-50/70 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800 rounded-xl">
                <div className="flex items-start space-x-3">
                  <ShieldCheck className="w-5 h-5 text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5" />
                  <div className="text-xs space-y-1">
                    <p className="font-bold text-indigo-900 dark:text-indigo-200">
                      EduMatrix Institutional Audit Safeguard
                    </p>
                    <p className="text-indigo-700 dark:text-indigo-300">
                      To protect recruitment history and student records, jobs
                      with existing <strong>student applications</strong> or{' '}
                      <strong>recruitment circulars</strong> are protected from
                      permanent deletion.
                    </p>
                    <ul className="list-disc pl-4 mt-1 text-indigo-700 dark:text-indigo-300 space-y-0.5">
                      <li>
                        Jobs with <strong>zero dependencies</strong> will be
                        permanently deleted along with their attachment links.
                      </li>
                      <li>
                        Jobs with existing applications/circulars will be
                        safely handled according to the toggle below.
                      </li>
                    </ul>
                  </div>
                </div>
              </div>

              {/* Mode Selection / Force Close Toggle */}
              <div className="p-4 bg-gray-50 dark:bg-gray-800/60 rounded-xl border border-gray-200 dark:border-gray-700 space-y-3">
                <label className="flex items-start space-x-3 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={forceCloseProtected}
                    onChange={(e) => setForceCloseProtected(e.target.checked)}
                    className="mt-1 h-4 w-4 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500 cursor-pointer"
                  />
                  <div>
                    <span className="text-sm font-semibold text-gray-900 dark:text-white">
                      Safely Close Protected Jobs (Recommended)
                    </span>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                      When checked, any job that cannot be deleted due to existing
                      student applications or circular links will be safely transitioned
                      to <strong>CLOSED</strong> status, stopping further applications while
                      completely preserving placement records.
                    </p>
                    {!forceCloseProtected && (
                      <p className="text-xs text-amber-600 dark:text-amber-400 mt-1 flex items-center gap-1">
                        <AlertTriangle className="w-3.5 h-3.5 inline" />
                        Unchecked: Protected jobs with applications will be skipped
                        and left unchanged.
                      </p>
                    )}
                  </div>
                </label>
              </div>

              {/* Selected Jobs Summary */}
              <div>
                <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                  Selected Postings ({selectedJobs.length})
                </h3>
                <div className="max-h-48 overflow-y-auto space-y-2 border border-gray-200 dark:border-gray-800 rounded-xl p-3 bg-white dark:bg-gray-900">
                  {selectedJobs.map((job) => (
                    <div
                      key={job.id}
                      className="flex items-center justify-between text-xs py-1.5 px-2 rounded-lg bg-gray-50 dark:bg-gray-800/50"
                    >
                      <div className="flex items-center space-x-2 truncate">
                        <Briefcase className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                        <span className="font-medium text-gray-900 dark:text-white truncate">
                          {job.title}
                        </span>
                        <span className="text-gray-400">•</span>
                        <span className="text-gray-500 dark:text-gray-400 truncate">
                          {job.company_name}
                        </span>
                      </div>
                      <div className="flex items-center space-x-2 shrink-0 ml-2">
                        {job.attachments?.length > 0 && (
                          <span className="inline-flex items-center gap-0.5 text-[11px] text-gray-400">
                            <Paperclip className="w-3 h-3" />
                            {job.attachments.length}
                          </span>
                        )}
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${
                            job.status === 'open'
                              ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300'
                              : job.status === 'draft'
                              ? 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300'
                              : 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
                          }`}
                        >
                          {job.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            /* Results Screen */
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="p-3 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-xl">
                  <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 uppercase">
                    Deleted
                  </span>
                  <p className="text-xl font-bold text-emerald-700 dark:text-emerald-300 mt-0.5">
                    {result.deleted_count}
                  </p>
                </div>
                <div className="p-3 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-xl">
                  <span className="text-xs font-semibold text-amber-600 dark:text-amber-400 uppercase">
                    Safely Closed
                  </span>
                  <p className="text-xl font-bold text-amber-700 dark:text-amber-300 mt-0.5">
                    {result.closed_count}
                  </p>
                </div>
                <div className="p-3 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl">
                  <span className="text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase">
                    Preserved / Blocked
                  </span>
                  <p className="text-xl font-bold text-gray-700 dark:text-gray-300 mt-0.5">
                    {result.blocked_count}
                  </p>
                </div>
              </div>

              {/* Individual Results Details */}
              <div>
                <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                  Execution Report
                </h4>
                <div className="max-h-56 overflow-y-auto space-y-1.5 border border-gray-200 dark:border-gray-800 rounded-xl p-3 bg-white dark:bg-gray-900">
                  {result.results?.map((item, idx) => {
                    const matchedJob = jobs.find((j) => j.id === item.id);
                    return (
                      <div
                        key={idx}
                        className="flex items-start justify-between text-xs p-2 rounded-lg bg-gray-50 dark:bg-gray-800/50"
                      >
                        <div className="truncate mr-2">
                          <p className="font-semibold text-gray-900 dark:text-white truncate">
                            {matchedJob?.title || `Job ID: ${item.id.slice(0, 8)}...`}
                          </p>
                          <p className="text-[11px] text-gray-500 dark:text-gray-400">
                            {item.message}
                          </p>
                        </div>
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase shrink-0 ${
                            item.status === 'deleted'
                              ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300'
                              : item.status === 'closed'
                              ? 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300'
                              : 'bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300'
                          }`}
                        >
                          {item.status}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-gray-200 dark:border-gray-800 bg-gray-50/70 dark:bg-gray-800/50 flex justify-end space-x-3">
          {!result ? (
            <>
              <button
                type="button"
                onClick={handleClose}
                disabled={isSubmitting}
                className="px-4 py-2 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-xl text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleExecute}
                disabled={isSubmitting || selectedJobIds.length === 0}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-semibold shadow-xs transition-colors cursor-pointer disabled:opacity-50 flex items-center space-x-1.5"
              >
                {isSubmitting ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Processing...</span>
                  </>
                ) : (
                  <>
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>
                      {forceCloseProtected
                        ? 'Delete or Close Selected Jobs'
                        : 'Delete Safe Jobs Only'}
                    </span>
                  </>
                )}
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={handleClose}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold shadow-xs transition-colors cursor-pointer"
            >
              Done & Refresh
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default BulkJobDeleteModal;
