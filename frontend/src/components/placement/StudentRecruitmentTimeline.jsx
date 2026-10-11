import React, { useEffect, useMemo, useState } from 'react';
import {
  TrendingUp,
  Award,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  Building2,
  Calendar,
  Layers,
  ShieldCheck,
  X,
  Briefcase,
  Info,
  Check,
  Sparkles,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import toast from 'react-hot-toast';

export default function StudentRecruitmentTimeline({
  studentId,
  jobId = null,
  jobTitle = null,
  companyName = null,
  isOpen = true,
  onClose = null,
  inline = false,
}) {
  const {
    studentProgression,
    isProgressionLoading,
    fetchStudentProgression,
  } = usePlacementStore();

  const [isLoadingRounds, setIsLoadingRounds] = useState(false);

  useEffect(() => {
    if (studentId) {
      setIsLoadingRounds(true);
      fetchStudentProgression(studentId, jobId)
        .catch(() => {
          // Graceful handling of empty or unrecorded progression
        })
        .finally(() => {
          setIsLoadingRounds(false);
        });
    }
  }, [studentId, jobId, fetchStudentProgression]);

  // Filter progression items to the target job if specified, and sort in chronological/numerical order
  const filteredProgression = useMemo(() => {
    if (!Array.isArray(studentProgression)) return [];

    let items = studentProgression;
    if (jobId) {
      items = items.filter(
        (p) => String(p.job_posting_id) === String(jobId) || String(p.application_id) === String(jobId)
      );
    }

    return [...items].sort((a, b) => {
      if (a.round_number !== b.round_number) {
        return (a.round_number || 0) - (b.round_number || 0);
      }
      return (a.round_id || 0) - (b.round_id || 0);
    });
  }, [studentProgression, jobId]);

  const formatDate = (dateStr) => {
    if (!dateStr) return null;
    try {
      const d = new Date(dateStr);
      return isNaN(d.getTime())
        ? null
        : d.toLocaleDateString('en-IN', {
            day: 'numeric',
            month: 'short',
            year: 'numeric',
          });
    } catch {
      return null;
    }
  };

  const getOutcomeBadge = (outcome, isFinalRound) => {
    switch (outcome?.toLowerCase()) {
      case 'cleared':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 dark:bg-emerald-950/70 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>CLEARED</span>
          </span>
        );
      case 'selected':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-purple-100 dark:bg-purple-950/70 text-purple-800 dark:text-purple-300 border border-purple-300 dark:border-purple-800">
            <Sparkles className="w-3.5 h-3.5" />
            <span>PROCESS SELECTED</span>
          </span>
        );
      case 'rejected':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-100 dark:bg-rose-950/70 text-rose-800 dark:text-rose-300 border border-rose-300 dark:border-rose-800">
            <XCircle className="w-3.5 h-3.5" />
            <span>NOT CLEARED</span>
          </span>
        );
      case 'on_hold':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 dark:bg-amber-950/70 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-800">
            <Clock className="w-3.5 h-3.5" />
            <span>ON HOLD</span>
          </span>
        );
      case 'absent':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-700">
            <span>ABSENT</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-100 dark:bg-blue-950/70 text-blue-800 dark:text-blue-300 border border-blue-300 dark:border-blue-800">
            <Clock className="w-3.5 h-3.5" />
            <span>{outcome ? outcome.toUpperCase() : 'IN PROGRESS'}</span>
          </span>
        );
    }
  };

  const timelineContent = (
    <div className="space-y-4">
      {/* Header Info */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-gray-100 dark:border-gray-800">
        <div>
          <h3 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-purple-600 dark:text-purple-400" />
            <span>Recruitment Progression Timeline</span>
          </h3>
          {(jobTitle || companyName) && (
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 flex items-center gap-1">
              <Building2 className="w-3.5 h-3.5" />
              <span>
                {companyName ? `${companyName} — ` : ''}
                {jobTitle || 'Placement Drive'}
              </span>
            </p>
          )}
        </div>

        <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-purple-50 dark:bg-purple-950/60 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800 self-start sm:self-auto">
          {filteredProgression.length} Confirmed {filteredProgression.length === 1 ? 'Round' : 'Rounds'}
        </span>
      </div>

      {/* Disclaimers & Distinction Notice */}
      <div className="p-3 rounded-xl bg-blue-50/70 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800/60 text-xs text-blue-900 dark:text-blue-200 flex items-start gap-2.5">
        <Info className="w-4 h-4 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="font-semibold">Recruitment Milestones vs. Formal Offers</p>
          <p className="text-blue-700 dark:text-blue-300 leading-relaxed text-[11px]">
            Clearing process rounds indicates recruitment qualification. Final-round selection confirms completion of candidate evaluations, but does not substitute for a formal Placement Offer. Official verified employment offers appear separately once confirmed by the Placement Cell.
          </p>
        </div>
      </div>

      {/* Loading State */}
      {(isProgressionLoading || isLoadingRounds) && filteredProgression.length === 0 ? (
        <div className="space-y-3 py-6 animate-pulse">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex gap-4 items-start">
              <div className="w-8 h-8 rounded-full bg-gray-200 dark:bg-gray-800 flex-shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-gray-200 dark:bg-gray-800 rounded w-1/3" />
                <div className="h-3 bg-gray-100 dark:bg-gray-800 rounded w-1/2" />
              </div>
            </div>
          ))}
        </div>
      ) : filteredProgression.length === 0 ? (
        /* Empty State / Legacy Records */
        <div className="text-center py-10 bg-gray-50/70 dark:bg-gray-800/40 rounded-2xl border border-gray-200 dark:border-gray-800 p-6 space-y-2.5">
          <Layers className="w-10 h-10 text-gray-300 dark:text-gray-600 mx-auto" />
          <h4 className="text-sm font-bold text-gray-800 dark:text-gray-200">
            No Round Progression Outcomes Recorded Yet
          </h4>
          <p className="text-xs text-gray-500 dark:text-gray-400 max-w-sm mx-auto">
            Recruitment rounds and confirmed outcomes for this drive will appear here chronologically as interview results are confirmed by the Placement Cell.
          </p>
        </div>
      ) : (
        /* Chronological Timeline List */
        <div className="relative pl-6 sm:pl-8 space-y-6 before:absolute before:left-3 sm:before:left-4 before:top-2 before:bottom-2 before:w-0.5 before:bg-gray-200 dark:before:bg-gray-800">
          {filteredProgression.map((item, idx) => {
            const isCleared = item.outcome?.toLowerCase() === 'cleared';
            const isSelected = item.outcome?.toLowerCase() === 'selected';
            const isRejected = item.outcome?.toLowerCase() === 'rejected';
            const isOnHold = item.outcome?.toLowerCase() === 'on_hold';

            return (
              <div key={item.outcome_id || idx} className="relative group">
                {/* Timeline Icon Node */}
                <div
                  className={`absolute -left-6 sm:-left-8 top-1 w-6 h-6 sm:w-7 sm:h-7 rounded-full flex items-center justify-center border-2 bg-white dark:bg-gray-900 transition-all ${
                    isCleared || isSelected
                      ? 'border-emerald-500 text-emerald-600 dark:text-emerald-400 shadow-xs'
                      : isRejected
                      ? 'border-rose-500 text-rose-600 dark:text-rose-400'
                      : isOnHold
                      ? 'border-amber-500 text-amber-600 dark:text-amber-400'
                      : 'border-blue-400 text-blue-500 dark:text-blue-400'
                  }`}
                >
                  {isCleared ? (
                    <Check className="w-3.5 h-3.5 stroke-[3]" />
                  ) : isSelected ? (
                    <Sparkles className="w-3.5 h-3.5" />
                  ) : isRejected ? (
                    <X className="w-3.5 h-3.5 stroke-[3]" />
                  ) : isOnHold ? (
                    <Clock className="w-3.5 h-3.5" />
                  ) : (
                    <span className="text-[10px] font-bold">{item.round_number || idx + 1}</span>
                  )}
                </div>

                {/* Round Details Card */}
                <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 shadow-xs hover:border-gray-300 dark:hover:border-gray-700 transition-colors space-y-2.5">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          Round #{item.round_number}
                        </span>
                        <h4 className="text-sm font-bold text-gray-900 dark:text-white">
                          {item.round_name || `Round ${item.round_number}`}
                        </h4>
                        {item.is_final_round && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-extrabold bg-purple-100 dark:bg-purple-950/70 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800 uppercase">
                            Final Round
                          </span>
                        )}
                      </div>

                      <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500 dark:text-gray-400 mt-1">
                        {item.round_type && (
                          <span className="capitalize">
                            Type: <strong className="text-gray-700 dark:text-gray-300">{item.round_type}</strong>
                          </span>
                        )}
                        {item.round_date && (
                          <span className="flex items-center gap-1">
                            <Calendar className="w-3 h-3 text-gray-400" />
                            <span>Scheduled: {formatDate(item.round_date)}</span>
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Outcome Badge */}
                    <div className="self-start sm:self-auto">
                      {getOutcomeBadge(item.outcome, item.is_final_round)}
                    </div>
                  </div>

                  {/* Score & Confirmation Timestamp */}
                  <div className="pt-2 border-t border-gray-100 dark:border-gray-800 flex flex-wrap items-center justify-between gap-2 text-xs">
                    <div className="flex items-center gap-3">
                      {item.score !== null && item.score !== undefined && (
                        <span className="font-semibold text-gray-700 dark:text-gray-300">
                          Score: <span className="text-blue-600 dark:text-blue-400">{item.score}</span>
                        </span>
                      )}
                      {item.remarks && (
                        <span className="text-gray-500 dark:text-gray-400 italic truncate max-w-xs">
                          Notes: {item.remarks}
                        </span>
                      )}
                    </div>

                    {item.confirmed_at && (
                      <span className="text-[11px] text-gray-400 dark:text-gray-500">
                        Confirmed: {formatDate(item.confirmed_at)}
                      </span>
                    )}
                  </div>

                  {/* Final Round Selection Distinction Box */}
                  {isSelected && (
                    <div className="p-2.5 rounded-lg bg-purple-50 dark:bg-purple-950/40 border border-purple-200 dark:border-purple-800 text-[11px] text-purple-900 dark:text-purple-300 space-y-1">
                      <p className="font-bold flex items-center gap-1">
                        <Sparkles className="w-3.5 h-3.5 text-purple-600" />
                        <span>Process Selection Recorded</span>
                      </p>
                      <p className="text-purple-700 dark:text-purple-400">
                        You have successfully reached and cleared the final recruitment evaluation! Verified employment offers are extended separately by Placement Officers after verification.
                      </p>
                    </div>
                  )}

                  {/* Linked Verified Offer Callout (if an offer exists for this candidate) */}
                  {item.has_offer && (
                    <div className="p-2.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-[11px] text-emerald-900 dark:text-emerald-300 flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5">
                        <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                        <span className="font-bold">Verified Placement Offer Issued!</span>
                        {item.offer_ctc_lpa && (
                          <span className="text-emerald-700 dark:text-emerald-400">
                            • ₹{item.offer_ctc_lpa} LPA
                          </span>
                        )}
                      </div>
                      <span className="font-bold uppercase px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-900/60 text-emerald-800 dark:text-emerald-300 text-[10px]">
                        Status: {item.offer_status || 'OFFERED'}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );

  // If rendered inline (e.g. inside an accordion or tab):
  if (inline) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 p-5 shadow-xs">
        {timelineContent}
      </div>
    );
  }

  // Modal mode:
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="recruitment-timeline-title"
        className="bg-white dark:bg-gray-900 rounded-2xl max-w-2xl w-full p-6 shadow-2xl border border-gray-200 dark:border-gray-800 space-y-4 max-h-[90vh] overflow-y-auto"
      >
        <div className="flex items-center justify-between pb-2 border-b border-gray-100 dark:border-gray-800">
          <div className="flex items-center gap-2">
            <span className="p-2 rounded-xl bg-purple-100 dark:bg-purple-950/70 text-purple-600 dark:text-purple-400">
              <TrendingUp className="w-5 h-5" />
            </span>
            <h3 id="recruitment-timeline-title" className="text-lg font-bold text-gray-900 dark:text-white">
              Recruitment Process Timeline
            </h3>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {timelineContent}

        <div className="pt-3 border-t border-gray-100 dark:border-gray-800 flex justify-end">
          {onClose && (
            <button
              onClick={onClose}
              className="px-4 py-2 text-xs font-semibold bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-xl transition-colors cursor-pointer"
            >
              Close Timeline
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
