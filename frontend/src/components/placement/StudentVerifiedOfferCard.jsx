import React, { useState } from 'react';
import {
  Award,
  Building2,
  Calendar,
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  FileText,
  Download,
  Check,
  X,
  Briefcase,
  Banknote,
  ShieldCheck,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import toast from 'react-hot-toast';

export default function StudentVerifiedOfferCard({ offer, onOfferUpdated }) {
  const { respondToOffer } = usePlacementStore();

  const [confirmModalAction, setConfirmModalAction] = useState(null); // 'accepted' | 'declined' | null
  const [remarks, setRemarks] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!offer) return null;

  const status = (offer.acceptance_status || offer.status || 'offered').toLowerCase();
  const isOfferedPending = status === 'offered';
  const isAccepted = status === 'accepted';
  const isDeclined = status === 'declined';
  const isRescinded = status === 'rescinded';

  const handleOpenConfirm = (decision) => {
    setConfirmModalAction(decision);
    setRemarks('');
  };

  const handleCloseConfirm = () => {
    if (isSubmitting) return;
    setConfirmModalAction(null);
    setRemarks('');
  };

  const handleConfirmSubmit = async (e) => {
    e.preventDefault();
    if (!confirmModalAction || isSubmitting) return;

    setIsSubmitting(true);
    try {
      await respondToOffer(offer.id, {
        decision: confirmModalAction,
        remarks: remarks.trim() || undefined,
      });

      toast.success(
        confirmModalAction === 'accepted'
          ? 'Offer accepted successfully! Your response has been recorded.'
          : 'Offer declined. Your response has been recorded.'
      );
      setConfirmModalAction(null);
      setRemarks('');
      if (onOfferUpdated) {
        onOfferUpdated();
      }
    } catch (err) {
      const errMsg =
        err.response?.data?.detail ||
        err.message ||
        'Failed to record offer response. Please try again.';
      toast.error(errMsg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatCTC = (ctc) => {
    if (ctc === null || ctc === undefined || ctc === '') return 'Undisclosed';
    const num = Number(ctc);
    return isNaN(num) ? String(ctc) : `₹${num.toLocaleString('en-IN')} LPA`;
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return null;
    try {
      const d = new Date(dateStr);
      return isNaN(d.getTime()) ? null : d.toLocaleDateString('en-IN', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      });
    } catch {
      return null;
    }
  };

  const formatDateTime = (dateStr) => {
    if (!dateStr) return null;
    try {
      const d = new Date(dateStr);
      return isNaN(d.getTime()) ? null : d.toLocaleString('en-IN', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return null;
    }
  };

  return (
    <div
      className={`rounded-2xl border transition-all p-5 shadow-xs ${
        isRescinded
          ? 'bg-gray-50/80 dark:bg-gray-900/60 border-gray-300 dark:border-gray-800 opacity-90'
          : isAccepted
          ? 'bg-white dark:bg-gray-900 border-emerald-300 dark:border-emerald-800/80'
          : isDeclined
          ? 'bg-white dark:bg-gray-900 border-rose-200 dark:border-rose-900/50'
          : 'bg-white dark:bg-gray-900 border-blue-200 dark:border-blue-800/60 shadow-sm'
      }`}
    >
      {/* Header: Company, Designation & Status Badge */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400">
              <Building2 className="w-4 h-4" />
            </span>
            <span className="font-semibold text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              {offer.company_name || 'Hiring Organization'}
            </span>
            <span className="text-gray-300 dark:text-gray-600">•</span>
            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 dark:text-emerald-400">
              <ShieldCheck className="w-3.5 h-3.5" />
              Verified Offer
            </span>
          </div>

          <h3 className="text-lg font-bold text-gray-900 dark:text-white">
            {offer.designation || offer.job_title || 'Software Professional'}
          </h3>

          {offer.job_title && offer.job_title !== offer.designation && (
            <p className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1">
              <Briefcase className="w-3.5 h-3.5 text-gray-400" />
              <span>Job Drive: {offer.job_title}</span>
            </p>
          )}
        </div>

        {/* Status Badge */}
        <div className="self-start">
          {isOfferedPending && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-100 dark:bg-amber-950/70 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-800">
              <Clock className="w-3.5 h-3.5" />
              <span>Pending Your Decision</span>
            </span>
          )}

          {isAccepted && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 dark:bg-emerald-950/70 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Offer Accepted</span>
            </span>
          )}

          {isDeclined && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-100 dark:bg-rose-950/70 text-rose-800 dark:text-rose-300 border border-rose-300 dark:border-rose-800">
              <XCircle className="w-3.5 h-3.5" />
              <span>Offer Declined</span>
            </span>
          )}

          {isRescinded && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-gray-200 dark:bg-gray-800 text-gray-800 dark:text-gray-300 border border-gray-300 dark:border-gray-700">
              <AlertTriangle className="w-3.5 h-3.5 text-rose-600 dark:text-rose-400" />
              <span>Offer Rescinded</span>
            </span>
          )}
        </div>
      </div>

      {/* Key Details Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 my-4">
        {/* Verified Compensation */}
        <div className="p-3 rounded-xl bg-gray-50 dark:bg-gray-800/60 border border-gray-100 dark:border-gray-800">
          <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider block">
            Verified CTC
          </span>
          <p className="text-base font-extrabold text-emerald-600 dark:text-emerald-400 mt-0.5 flex items-center gap-1">
            <Banknote className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            <span>{formatCTC(offer.ctc_lpa ?? offer.ctc)}</span>
          </p>
        </div>

        {/* Offer Issuance Date */}
        <div className="p-3 rounded-xl bg-gray-50 dark:bg-gray-800/60 border border-gray-100 dark:border-gray-800">
          <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider block">
            Offer Date
          </span>
          <p className="text-sm font-semibold text-gray-800 dark:text-gray-200 mt-1 flex items-center gap-1.5">
            <Calendar className="w-3.5 h-3.5 text-gray-400" />
            <span>{formatDate(offer.offer_date) || 'Recorded by Cell'}</span>
          </p>
        </div>

        {/* Student Response Date (when applicable) */}
        <div className="p-3 rounded-xl bg-gray-50 dark:bg-gray-800/60 border border-gray-100 dark:border-gray-800 col-span-2 sm:col-span-1">
          <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider block">
            Response Status
          </span>
          <p className="text-xs font-medium text-gray-700 dark:text-gray-300 mt-1">
            {offer.response_date
              ? `Responded: ${formatDateTime(offer.response_date)}`
              : isOfferedPending
              ? 'Awaiting your action'
              : 'Status recorded'}
          </p>
        </div>
      </div>

      {/* Rescission Advisory Banner (Safe display of rescinded status) */}
      {isRescinded && (
        <div className="mb-4 p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-xs text-rose-800 dark:text-rose-300 flex items-start gap-2.5">
          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <p className="font-bold">This offer has been rescinded.</p>
            <p className="text-rose-700 dark:text-rose-400">
              The employer or placement cell has formally withdrawn this verified offer. It is no longer active.
            </p>
            {(offer.reason || offer.rescission_reason) && (
              <p className="mt-1 text-[11px] bg-white/70 dark:bg-gray-900/60 p-2 rounded-lg border border-rose-200 dark:border-rose-900">
                <span className="font-semibold">Reason:</span> {offer.reason || offer.rescission_reason}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Offer Letter Attachment Link (Authorized Download) */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-gray-100 dark:border-gray-800 text-xs">
        <div>
          {offer.offer_letter_file_id ? (
            <a
              href={`/api/v1/files/${offer.offer_letter_file_id}/download`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-50 dark:bg-blue-950/60 hover:bg-blue-100 dark:hover:bg-blue-900/70 text-blue-700 dark:text-blue-300 font-semibold border border-blue-200 dark:border-blue-800 transition-colors"
              title="Download your authorized official offer letter document"
            >
              <FileText className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
              <span>Official Offer Letter</span>
              <Download className="w-3 h-3 text-blue-500" />
            </a>
          ) : (
            <span className="text-gray-400 dark:text-gray-500 flex items-center gap-1">
              <FileText className="w-3.5 h-3.5 text-gray-400" />
              <span>No digital document attachment attached</span>
            </span>
          )}
        </div>

        {/* Decision Actions for Pending Offers */}
        {isOfferedPending && (
          <div className="flex items-center gap-2 self-end sm:self-auto">
            <button
              onClick={() => handleOpenConfirm('declined')}
              disabled={isSubmitting}
              className="px-3.5 py-2 text-xs font-bold text-rose-700 dark:text-rose-300 bg-rose-50 hover:bg-rose-100 dark:bg-rose-950/50 dark:hover:bg-rose-900/60 border border-rose-300 dark:border-rose-800 rounded-xl transition-all cursor-pointer disabled:opacity-50 flex items-center gap-1.5"
            >
              <X className="w-3.5 h-3.5 text-rose-600" />
              <span>Decline Offer</span>
            </button>

            <button
              onClick={() => handleOpenConfirm('accepted')}
              disabled={isSubmitting}
              className="px-4 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 dark:bg-emerald-600 dark:hover:bg-emerald-500 rounded-xl shadow-xs transition-all cursor-pointer disabled:opacity-50 flex items-center gap-1.5"
            >
              <Check className="w-3.5 h-3.5" />
              <span>Accept Offer</span>
            </button>
          </div>
        )}

        {/* Accepted Confirmation Badge Info */}
        {isAccepted && (
          <div className="text-emerald-700 dark:text-emerald-400 text-xs font-medium flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            <span>You have accepted this verified placement offer.</span>
          </div>
        )}

        {/* Declined Information */}
        {isDeclined && (
          <div className="text-rose-600 dark:text-rose-400 text-xs font-medium flex items-center gap-1">
            <XCircle className="w-3.5 h-3.5 text-rose-600" />
            <span>You have declined this placement offer.</span>
          </div>
        )}
      </div>

      {/* Confirmation Modal */}
      {confirmModalAction && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="confirm-modal-title"
            className="bg-white dark:bg-gray-900 rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-gray-200 dark:border-gray-800 space-y-4"
          >
            {/* Modal Header */}
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div
                  className={`p-2.5 rounded-xl ${
                    confirmModalAction === 'accepted'
                      ? 'bg-emerald-100 dark:bg-emerald-950/70 text-emerald-600 dark:text-emerald-400'
                      : 'bg-rose-100 dark:bg-rose-950/70 text-rose-600 dark:text-rose-400'
                  }`}
                >
                  {confirmModalAction === 'accepted' ? (
                    <Award className="w-6 h-6" />
                  ) : (
                    <AlertTriangle className="w-6 h-6" />
                  )}
                </div>
                <div>
                  <h4
                    id="confirm-modal-title"
                    className="text-lg font-bold text-gray-900 dark:text-white"
                  >
                    {confirmModalAction === 'accepted'
                      ? 'Confirm Offer Acceptance'
                      : 'Confirm Declining Offer'}
                  </h4>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {offer.company_name} — {offer.designation}
                  </p>
                </div>
              </div>

              <button
                onClick={handleCloseConfirm}
                disabled={isSubmitting}
                className="p-1 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Explanation & Policy Notice */}
            <div
              className={`p-3.5 rounded-xl text-xs space-y-1.5 ${
                confirmModalAction === 'accepted'
                  ? 'bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-900 dark:text-emerald-300'
                  : 'bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-900 dark:text-rose-300'
              }`}
            >
              {confirmModalAction === 'accepted' ? (
                <>
                  <p className="font-bold">
                    You are accepting this verified offer with CTC of {formatCTC(offer.ctc_lpa ?? offer.ctc)}.
                  </p>
                  <p className="text-emerald-800 dark:text-emerald-400">
                    Accepting formalizes your intent with the Placement Cell and the employer. Your placement record will be updated in accordance with institutional accounting guidelines.
                  </p>
                </>
              ) : (
                <>
                  <p className="font-bold">
                    Are you sure you want to decline this verified offer?
                  </p>
                  <p className="text-rose-800 dark:text-rose-400">
                    Declining turns down this position. This decision is recorded immediately in the Placement ledger and cannot be reversed or accepted subsequently.
                  </p>
                </>
              )}
            </div>

            {/* Optional Remarks */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                Remarks or Comments (Optional)
              </label>
              <textarea
                value={remarks}
                onChange={(e) => setRemarks(e.target.value)}
                placeholder={
                  confirmModalAction === 'accepted'
                    ? 'Optional acceptance comments for Placement Officer...'
                    : 'Optional reason or note for declining...'
                }
                rows={3}
                disabled={isSubmitting}
                className="w-full text-xs p-3 rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:outline-none resize-none"
              />
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={handleCloseConfirm}
                disabled={isSubmitting}
                className="px-4 py-2 text-xs font-semibold text-gray-700 dark:text-gray-300 bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 rounded-xl transition-colors cursor-pointer"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={handleConfirmSubmit}
                disabled={isSubmitting}
                className={`px-5 py-2 text-xs font-bold text-white rounded-xl shadow-xs transition-all cursor-pointer flex items-center gap-1.5 ${
                  confirmModalAction === 'accepted'
                    ? 'bg-emerald-600 hover:bg-emerald-700'
                    : 'bg-rose-600 hover:bg-rose-700'
                }`}
              >
                {isSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>
                  {confirmModalAction === 'accepted'
                    ? isSubmitting
                      ? 'Accepting...'
                      : 'Confirm Acceptance'
                    : isSubmitting
                    ? 'Declining...'
                    : 'Confirm Decline'}
                </span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
