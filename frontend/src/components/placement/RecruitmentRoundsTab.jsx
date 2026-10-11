import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Layers,
  Plus,
  Calendar,
  CheckCircle2,
  Clock,
  Award,
  AlertCircle,
  FileSpreadsheet,
  Users,
  ShieldCheck,
  X,
  ExternalLink,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import { getRoundOutcomes } from '../../services/placementService';
import toast from 'react-hot-toast';

export default function RecruitmentRoundsTab({ jobId, jobTitle, companyName }) {
  const navigate = useNavigate();
  const {
    jobRounds,
    isRoundsLoading,
    fetchJobRounds,
    createJobRound,
  } = usePlacementStore();

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Form State
  const [roundNumber, setRoundNumber] = useState('');
  const [roundName, setRoundName] = useState('');
  const [roundType, setRoundType] = useState('assessment');
  const [isFinal, setIsFinal] = useState(false);
  const [roundDate, setRoundDate] = useState('');

  // Outcomes Inspection Modal
  const [selectedRoundOutcomes, setSelectedRoundOutcomes] = useState(null);
  const [isLoadingOutcomes, setIsLoadingOutcomes] = useState(false);
  const [outcomesList, setOutcomesList] = useState([]);

  useEffect(() => {
    if (jobId) {
      fetchJobRounds(jobId).catch((err) => {
        toast.error('Failed to load recruitment rounds for this job.');
      });
    }
  }, [jobId]);

  const openCreateModal = () => {
    // Automatically suggest next round number
    const maxRoundNum = jobRounds.length > 0 ? Math.max(...jobRounds.map((r) => r.round_number || 0)) : 0;
    setRoundNumber(String(maxRoundNum + 1));
    setRoundName('');
    setRoundType('assessment');
    setIsFinal(false);
    setRoundDate('');
    setShowCreateModal(true);
  };

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    const num = parseInt(roundNumber, 10);
    if (!num || num <= 0) {
      toast.error('Round number must be a positive integer greater than 0.');
      return;
    }
    if (!roundName.trim()) {
      toast.error('Please enter a round name.');
      return;
    }

    // Check for duplicate round number locally before submitting
    const duplicate = jobRounds.find((r) => r.round_number === num);
    if (duplicate) {
      toast.error(`Round ${num} already exists for this job ("${duplicate.name}").`);
      return;
    }

    setIsSubmitting(true);
    try {
      await createJobRound(jobId, {
        round_number: num,
        name: roundName.trim(),
        round_type: roundType,
        is_final: isFinal,
        round_date: roundDate ? new Date(roundDate).toISOString() : null,
      });
      toast.success(`Recruitment Round #${num} ("${roundName.trim()}") created successfully!`);
      setShowCreateModal(false);
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to create recruitment round.';
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleInspectOutcomes = async (round) => {
    setSelectedRoundOutcomes(round);
    setIsLoadingOutcomes(true);
    try {
      const outcomes = await getRoundOutcomes(round.id);
      setOutcomesList(outcomes);
    } catch (err) {
      toast.error('Failed to load candidate outcomes for this round.');
      setOutcomesList([]);
    } finally {
      setIsLoadingOutcomes(false);
    }
  };

  const getRoundTypeBadge = (type) => {
    switch (type?.toLowerCase()) {
      case 'assessment':
        return 'bg-blue-100 dark:bg-blue-950/60 text-blue-800 dark:text-blue-300 border-blue-200 dark:border-blue-800';
      case 'technical':
        return 'bg-purple-100 dark:bg-purple-950/60 text-purple-800 dark:text-purple-300 border-purple-200 dark:border-purple-800';
      case 'hr':
        return 'bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border-amber-200 dark:border-amber-800';
      case 'group_discussion':
        return 'bg-teal-100 dark:bg-teal-950/60 text-teal-800 dark:text-teal-300 border-teal-200 dark:border-teal-800';
      default:
        return 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-700';
    }
  };

  const getOutcomeBadge = (outcome) => {
    switch (outcome?.toLowerCase()) {
      case 'cleared':
        return 'bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800';
      case 'rejected':
        return 'bg-rose-100 dark:bg-rose-950/60 text-rose-800 dark:text-rose-300 border border-rose-200 dark:border-rose-800';
      case 'on_hold':
        return 'bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800';
      case 'absent':
        return 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700';
      case 'offered':
        return 'bg-indigo-100 dark:bg-indigo-950/60 text-indigo-800 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800';
      default:
        return 'bg-gray-100 text-gray-700';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header and Controls */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-5 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-xs">
        <div>
          <div className="flex items-center space-x-2">
            <Layers className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            <h2 className="text-lg font-bold text-gray-900 dark:text-white">
              Recruitment Rounds ({jobRounds.length})
            </h2>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Authoritative sequential round progression ladder for <strong>{jobTitle}</strong> at <strong>{companyName}</strong>.
          </p>
        </div>

        <button
          onClick={openCreateModal}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold flex items-center space-x-2 shadow-sm transition-colors cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>Add Recruitment Round</span>
        </button>
      </div>

      {/* Rounds List */}
      {isRoundsLoading && jobRounds.length === 0 ? (
        <div className="flex justify-center items-center h-48 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-indigo-600 border-t-transparent" />
        </div>
      ) : jobRounds.length === 0 ? (
        <div className="text-center py-12 bg-white dark:bg-gray-900 rounded-xl border border-dashed border-gray-200 dark:border-gray-800 p-6">
          <Layers className="w-10 h-10 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
            No Recruitment Rounds Defined
          </h3>
          <p className="text-xs text-gray-500 dark:text-gray-400 max-w-md mx-auto mt-1 mb-4">
            Define recruitment rounds (e.g. Assessment, Technical Interview, Final HR) to track candidate progression and confirm tabular result batches.
          </p>
          <button
            onClick={openCreateModal}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors cursor-pointer"
          >
            Create Round 1
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {jobRounds.map((round, idx) => (
            <div
              key={round.id}
              className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5 shadow-xs hover:border-indigo-300 dark:hover:border-indigo-700 transition-colors"
            >
              <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
                <div className="flex items-start space-x-3.5">
                  <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-100 dark:border-indigo-900 flex items-center justify-center shrink-0">
                    <span className="font-bold text-indigo-700 dark:text-indigo-300 text-sm">
                      #{round.round_number}
                    </span>
                  </div>

                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-bold text-gray-900 dark:text-white text-base">
                        {round.name}
                      </h3>
                      <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getRoundTypeBadge(round.round_type)}`}>
                        {round.round_type?.toUpperCase()}
                      </span>
                      {round.is_final && (
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 flex items-center gap-1">
                          <Award className="w-3.5 h-3.5" />
                          FINAL ROUND
                        </span>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-4 text-xs text-gray-500 dark:text-gray-400 mt-2">
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5 text-gray-400" />
                        {round.round_date
                          ? new Date(round.round_date).toLocaleDateString(undefined, {
                              year: 'numeric',
                              month: 'short',
                              day: 'numeric',
                            })
                          : 'Date TBD'}
                      </span>
                      <span className="flex items-center gap-1">
                        <Users className="w-3.5 h-3.5 text-gray-400" />
                        {round.outcomes_count !== undefined ? `${round.outcomes_count} Confirmed Outcomes` : 'Progression Ledger Active'}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2.5 self-end lg:self-center">
                  <button
                    onClick={() => handleInspectOutcomes(round)}
                    className="px-3.5 py-1.5 text-xs font-semibold bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 rounded-lg transition-colors cursor-pointer flex items-center gap-1.5"
                  >
                    <Users className="w-3.5 h-3.5" />
                    <span>View Outcomes</span>
                  </button>

                  <button
                    onClick={() =>
                      navigate(
                        `/placement/results?jobId=${jobId}&roundId=${round.id}&companyId=${round.company_id || ''}`
                      )
                    }
                    className="px-3.5 py-1.5 text-xs font-semibold bg-indigo-50 dark:bg-indigo-950/60 hover:bg-indigo-100 dark:hover:bg-indigo-900 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 rounded-lg transition-colors cursor-pointer flex items-center gap-1.5"
                  >
                    <FileSpreadsheet className="w-3.5 h-3.5" />
                    <span>Upload & Link Results</span>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Round Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-md w-full p-6 shadow-xl border border-gray-200 dark:border-gray-800">
            <div className="flex items-center justify-between pb-4 border-b border-gray-100 dark:border-gray-800">
              <div className="flex items-center space-x-2">
                <Layers className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                <h3 className="text-base font-bold text-gray-900 dark:text-white">
                  Add Recruitment Round
                </h3>
              </div>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="space-y-4 mt-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Round Number *
                </label>
                <input
                  type="number"
                  min="1"
                  required
                  value={roundNumber}
                  onChange={(e) => setRoundNumber(e.target.value)}
                  placeholder="e.g. 1"
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
                <p className="text-[11px] text-gray-400 mt-0.5">
                  Sequential position in the recruitment pipeline (e.g. 1, 2, 3).
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Round Name / Title *
                </label>
                <input
                  type="text"
                  maxLength={100}
                  required
                  value={roundName}
                  onChange={(e) => setRoundName(e.target.value)}
                  placeholder="e.g. Online Coding Assessment"
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                    Round Type
                  </label>
                  <select
                    value={roundType}
                    onChange={(e) => setRoundType(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  >
                    <option value="assessment">Assessment / Test</option>
                    <option value="technical">Technical Interview</option>
                    <option value="hr">HR Interview</option>
                    <option value="group_discussion">Group Discussion</option>
                    <option value="managerial">Managerial Round</option>
                    <option value="other">Other</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                    Round Date (Optional)
                  </label>
                  <input
                    type="date"
                    value={roundDate}
                    onChange={(e) => setRoundDate(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  >
                  </input>
                </div>
              </div>

              {/* Is Final Round Toggle */}
              <div className="p-3 bg-gray-50 dark:bg-gray-800/60 rounded-xl border border-gray-200 dark:border-gray-700/60">
                <label className="flex items-center space-x-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={isFinal}
                    onChange={(e) => setIsFinal(e.target.checked)}
                    className="w-4 h-4 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500"
                  />
                  <div>
                    <span className="text-xs font-semibold text-gray-900 dark:text-white">
                      Mark as Final Round
                    </span>
                    <p className="text-[11px] text-gray-500 dark:text-gray-400">
                      Candidates clearing this round are marked as SELECTED. In accordance with policy, verified offers are issued separately.
                    </p>
                  </div>
                </label>
              </div>

              <div className="pt-3 border-t border-gray-100 dark:border-gray-800 flex justify-end space-x-2.5">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg text-xs font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer flex items-center gap-1.5"
                >
                  {isSubmitting ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Creating...</span>
                    </>
                  ) : (
                    <span>Create Round</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Round Outcomes Inspection Modal */}
      {selectedRoundOutcomes && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-2xl w-full p-6 shadow-xl border border-gray-200 dark:border-gray-800 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between pb-4 border-b border-gray-100 dark:border-gray-800 shrink-0">
              <div>
                <h3 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
                  <span>Round #{selectedRoundOutcomes.round_number}: {selectedRoundOutcomes.name}</span>
                  {selectedRoundOutcomes.is_final && (
                    <span className="px-2 py-0.5 text-[10px] font-bold bg-emerald-100 text-emerald-800 rounded-full">
                      FINAL
                    </span>
                  )}
                </h3>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  Confirmed Candidate Outcomes in Progression Ledger
                </p>
              </div>
              <button
                onClick={() => setSelectedRoundOutcomes(null)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="overflow-y-auto flex-1 py-4">
              {isLoadingOutcomes ? (
                <div className="flex justify-center items-center h-32">
                  <div className="animate-spin rounded-full h-7 w-7 border-2 border-indigo-600 border-t-transparent" />
                </div>
              ) : outcomesList.length === 0 ? (
                <div className="text-center py-8 text-gray-500 text-xs">
                  No confirmed student outcomes recorded for this round yet.
                </div>
              ) : (
                <div className="space-y-2.5">
                  {outcomesList.map((item) => (
                    <div
                      key={item.id}
                      className="p-3 bg-gray-50 dark:bg-gray-800/60 rounded-xl border border-gray-200 dark:border-gray-700/60 flex items-center justify-between text-xs"
                    >
                      <div>
                        <p className="font-semibold text-gray-900 dark:text-white">
                          {item.student_name || `Student #${item.student_id}`}
                        </p>
                        <p className="text-[11px] text-gray-400">{item.student_email}</p>
                        {item.remarks && (
                          <p className="text-[11px] text-gray-500 italic mt-0.5">
                            Note: {item.remarks}
                          </p>
                        )}
                      </div>
                      <div className="flex items-center space-x-2">
                        {item.score !== null && item.score !== undefined && (
                          <span className="text-[11px] font-medium text-gray-500">
                            Score: {item.score}
                          </span>
                        )}
                        <span className={`px-2.5 py-0.5 rounded-full font-semibold ${getOutcomeBadge(item.outcome)}`}>
                          {item.outcome?.toUpperCase()}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="pt-3 border-t border-gray-100 dark:border-gray-800 flex justify-end shrink-0">
              <button
                onClick={() => setSelectedRoundOutcomes(null)}
                className="px-4 py-2 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg text-xs font-semibold"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
