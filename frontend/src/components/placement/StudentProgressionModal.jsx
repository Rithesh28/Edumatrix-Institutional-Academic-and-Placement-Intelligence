import React, { useState, useEffect } from 'react';
import {
  TrendingUp,
  Award,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  Layers,
  Building2,
  Calendar,
  X,
  Edit2,
  FileText,
  ShieldCheck,
  ChevronRight,
  Info,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import toast from 'react-hot-toast';

export default function StudentProgressionModal({
  isOpen = true,
  onClose,
  studentId,
  studentName,
  studentEmail,
  jobId = null,
}) {
  const {
    studentProgression,
    isProgressionLoading,
    fetchStudentProgression,
    correctRoundOutcome,
  } = usePlacementStore();

  const [correctingOutcome, setCorrectingOutcome] = useState(null);
  const [newOutcome, setNewOutcome] = useState('cleared');
  const [newScore, setNewScore] = useState('');
  const [correctionReason, setCorrectionReason] = useState('');
  const [isSubmittingCorrection, setIsSubmittingCorrection] = useState(false);

  useEffect(() => {
    if (isOpen && studentId) {
      fetchStudentProgression(studentId, jobId).catch((err) => {
        toast.error('Failed to load candidate progression.');
      });
    }
  }, [isOpen, studentId, jobId]);

  if (!isOpen) return null;

  const handleOpenCorrection = (item) => {
    setCorrectingOutcome(item);
    setNewOutcome(item.outcome || 'cleared');
    setNewScore(item.score !== null && item.score !== undefined ? String(item.score) : '');
    setCorrectionReason('');
  };

  const handleCorrectionSubmit = async (e) => {
    e.preventDefault();
    if (!correctingOutcome) return;
    if (!correctionReason.trim() || correctionReason.trim().length < 3) {
      toast.error('Please provide a substantive audit reason for correcting this outcome.');
      return;
    }

    setIsSubmittingCorrection(true);
    try {
      await correctRoundOutcome(correctingOutcome.outcome_id, {
        new_outcome: newOutcome,
        new_score: newScore ? parseFloat(newScore) : null,
        reason: correctionReason.trim(),
      });
      toast.success('Round outcome corrected and audited successfully.');
      setCorrectingOutcome(null);
      fetchStudentProgression(studentId, jobId);
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to correct outcome.';
      toast.error(msg);
    } finally {
      setIsSubmittingCorrection(false);
    }
  };

  const getOutcomeBadge = (outcome) => {
    switch (outcome?.toLowerCase()) {
      case 'cleared':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
            <CheckCircle2 className="w-3 h-3" />
            CLEARED
          </span>
        );
      case 'rejected':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 dark:bg-rose-950/60 text-rose-800 dark:text-rose-300 border border-rose-200 dark:border-rose-800">
            <XCircle className="w-3 h-3" />
            NOT SELECTED
          </span>
        );
      case 'on_hold':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
            <Clock className="w-3 h-3" />
            ON HOLD
          </span>
        );
      case 'absent':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
            ABSENT
          </span>
        );
      case 'offered':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 dark:bg-indigo-950/60 text-indigo-800 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
            OFFERED (LEGACY)
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-700">
            {outcome?.toUpperCase()}
          </span>
        );
    }
  };

  const getOfferStatusBadge = (status) => {
    switch (status?.toLowerCase()) {
      case 'accepted':
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border border-emerald-200">
            VERIFIED OFFER: ACCEPTED
          </span>
        );
      case 'offered':
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-200">
            VERIFIED OFFER: PENDING
          </span>
        );
      case 'declined':
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 dark:bg-rose-950/60 text-rose-800 dark:text-rose-300 border border-rose-200">
            VERIFIED OFFER: DECLINED
          </span>
        );
      case 'rescinded':
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200">
            VERIFIED OFFER: RESCINDED
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
      <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-2xl w-full p-6 shadow-xl border border-gray-200 dark:border-gray-800 max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-gray-100 dark:border-gray-800 shrink-0">
          <div>
            <div className="flex items-center space-x-2">
              <TrendingUp className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
              <h3 className="text-base font-bold text-gray-900 dark:text-white">
                Recruitment Progression History
              </h3>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              Candidate: <strong>{studentName || `Student #${studentId}`}</strong> ({studentEmail || 'N/A'})
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 p-1"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Policy distinction banner */}
        <div className="p-3 bg-indigo-50/60 dark:bg-indigo-950/30 rounded-xl border border-indigo-100 dark:border-indigo-900/50 text-xs text-indigo-900 dark:text-indigo-300 flex items-start gap-2 mt-3 mb-1 shrink-0">
          <Info className="w-4 h-4 text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5" />
          <span>
            <strong>Progression Lifecycle Policy:</strong> Sequential clearance records round advancement. Passing a final selection round marks a candidate as selected, but does NOT constitute an official verified offer until formal terms, CTC, and offer letters are verified under Verified Offers.
          </span>
        </div>

        {/* Timeline Content */}
        <div className="overflow-y-auto flex-1 py-4">
          {isProgressionLoading ? (
            <div className="flex justify-center items-center h-48">
              <div className="animate-spin rounded-full h-8 w-8 border-2 border-indigo-600 border-t-transparent" />
            </div>
          ) : studentProgression.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              <Layers className="w-10 h-10 mx-auto mb-2 text-gray-300 dark:text-gray-600" />
              <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                No Recruitment Progression Recorded
              </p>
              <p className="text-xs text-gray-400 mt-1">
                Candidate has not had confirmed outcomes recorded in any recruitment rounds yet.
              </p>
            </div>
          ) : (
            <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-3 before:bottom-3 before:w-0.5 before:bg-gray-200 dark:before:bg-gray-800">
              {studentProgression.map((item, idx) => (
                <div key={item.outcome_id} className="relative">
                  {/* Dot */}
                  <div className="absolute -left-6 top-1.5 w-4 h-4 rounded-full border-2 border-white dark:border-gray-900 bg-indigo-600 shadow-xs" />

                  <div className="p-4 bg-gray-50 dark:bg-gray-800/60 rounded-xl border border-gray-200 dark:border-gray-700/60 space-y-2.5">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-gray-900 dark:text-white text-sm">
                            Round #{item.round_number}: {item.round_name}
                          </span>
                          {item.is_final_round && (
                            <span className="px-2 py-0.2 rounded-full text-[10px] font-bold bg-purple-100 dark:bg-purple-950/60 text-purple-800 dark:text-purple-300 border border-purple-200">
                              FINAL ROUND
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1.5 mt-0.5">
                          <Building2 className="w-3.5 h-3.5" />
                          <span>{item.company_name} • {item.job_title}</span>
                        </p>
                      </div>

                      <div className="flex items-center gap-2 self-start sm:self-auto">
                        {getOutcomeBadge(item.outcome)}
                        <button
                          onClick={() => handleOpenCorrection(item)}
                          title="Correct outcome with audited reason"
                          className="p-1 text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    {/* Metadata & Offer Indicators */}
                    <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500 dark:text-gray-400 pt-2 border-t border-gray-200 dark:border-gray-700/40">
                      {item.score !== null && item.score !== undefined && (
                        <span>Score: <strong>{item.score}</strong></span>
                      )}
                      {item.confirmed_at && (
                        <span>Confirmed on: {new Date(item.confirmed_at).toLocaleDateString()}</span>
                      )}
                      {item.has_offer && (
                        <div className="flex items-center gap-1.5 ml-auto">
                          {getOfferStatusBadge(item.offer_status)}
                          {item.offer_ctc_lpa && (
                            <span className="font-semibold text-emerald-600 dark:text-emerald-400 text-xs">
                              {item.offer_ctc_lpa} LPA
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    {item.remarks && (
                      <p className="text-[11px] text-gray-500 italic bg-white dark:bg-gray-800 p-2 rounded-lg border border-gray-100 dark:border-gray-700">
                        Remarks: {item.remarks}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="pt-3 border-t border-gray-100 dark:border-gray-800 flex justify-end shrink-0">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg text-xs font-semibold"
          >
            Close
          </button>
        </div>
      </div>

      {/* Outcome Correction Modal */}
      {correctingOutcome && (
        <div className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-md w-full p-6 shadow-xl border border-gray-200 dark:border-gray-800">
            <div className="flex items-center justify-between pb-4 border-b border-gray-100 dark:border-gray-800">
              <div className="flex items-center space-x-2">
                <Edit2 className="w-5 h-5 text-indigo-600" />
                <h3 className="text-base font-bold text-gray-900 dark:text-white">
                  Correct Confirmed Outcome
                </h3>
              </div>
              <button
                onClick={() => setCorrectingOutcome(null)}
                className="text-gray-400 hover:text-gray-600 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCorrectionSubmit} className="space-y-4 mt-4">
              <div className="p-3 bg-amber-50 dark:bg-amber-950/30 rounded-xl border border-amber-200 dark:border-amber-800 text-xs text-amber-800 dark:text-amber-300">
                ⚠️ Authoritative round outcomes cannot be silently overwritten. An audited administrative rationale is strictly required.
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  New Outcome *
                </label>
                <select
                  value={newOutcome}
                  onChange={(e) => setNewOutcome(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                >
                  <option value="cleared">CLEARED (Passed Round)</option>
                  <option value="rejected">REJECTED (Not Selected)</option>
                  <option value="on_hold">ON_HOLD (Under Consideration)</option>
                  <option value="absent">ABSENT</option>
                  <option value="offered">OFFERED (Legacy compatibility)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Revised Score (Optional)
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={newScore}
                  onChange={(e) => setNewScore(e.target.value)}
                  placeholder="e.g. 85.5"
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Mandatory Audit Rationale *
                </label>
                <textarea
                  required
                  minLength={3}
                  rows={3}
                  value={correctionReason}
                  onChange={(e) => setCorrectionReason(e.target.value)}
                  placeholder="e.g. Discrepancy rectified: candidate completed technical re-evaluation approved by recruiter."
                  className="w-full px-3 py-2 text-xs border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
              </div>

              <div className="flex justify-end space-x-2.5 pt-2">
                <button
                  type="button"
                  onClick={() => setCorrectingOutcome(null)}
                  className="px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-lg text-xs font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingCorrection}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5"
                >
                  {isSubmittingCorrection ? 'Recording...' : 'Apply & Audit'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
