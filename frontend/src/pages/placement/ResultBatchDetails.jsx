import React, { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  FileText,
  ArrowLeft,
  Building2,
  Briefcase,
  Award,
  CheckCircle,
  AlertTriangle,
  Clock,
  HelpCircle,
  Search,
  Filter,
  UserCheck,
  UserX,
  EyeOff,
  Check,
  X,
  ExternalLink,
  ChevronDown,
  Info,
  Send,
  RotateCcw,
  Layers,
  Download,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import { searchStudentsForMatching, getJobRounds } from '../../services/placementService';
import toast from 'react-hot-toast';

export default function ResultBatchDetails() {
  const { batchId } = useParams();
  const navigate = useNavigate();
  const {
    selectedResultBatch,
    isResultsLoading,
    fetchResultBatch,
    updateCandidateMatch,
    confirmBatchResults,
    linkBatchToRound,
  } = usePlacementStore();

  const [searchTerm, setSearchTerm] = useState('');
  const [filterState, setFilterState] = useState('all');
  const [selectedItemIds, setSelectedItemIds] = useState(new Set());

  // Manual Matching Modal State
  const [matchingItem, setMatchingItem] = useState(null);
  const [studentSearchQuery, setStudentSearchQuery] = useState('');
  const [studentSearchResults, setStudentSearchResults] = useState([]);
  const [isSearchingStudents, setIsSearchingStudents] = useState(false);
  const [matchNotes, setMatchNotes] = useState('');
  const [isSubmittingMatch, setIsSubmittingMatch] = useState(false);

  // Link Round Modal State
  const [jobRoundsForLinking, setJobRoundsForLinking] = useState([]);
  const [showLinkRoundModal, setShowLinkRoundModal] = useState(false);
  const [selectedLinkRoundId, setSelectedLinkRoundId] = useState('');
  const [isLinkingRound, setIsLinkingRound] = useState(false);

  // Confirmation Modal State
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [confirmNotes, setConfirmNotes] = useState('');
  const [isConfirming, setIsConfirming] = useState(false);

  useEffect(() => {
    if (batchId) {
      fetchResultBatch(batchId).catch((err) => {
        toast.error('Failed to load result batch details.');
      });
    }
  }, [batchId]);

  const batch = selectedResultBatch;
  const items = batch?.items || [];

  // Fetch job rounds when batch has job_posting_id
  useEffect(() => {
    if (batch?.job_posting_id) {
      getJobRounds(batch.job_posting_id)
        .then((rounds) => setJobRoundsForLinking(rounds || []))
        .catch(() => setJobRoundsForLinking([]));
    }
  }, [batch?.job_posting_id]);

  const handleExecuteLinkRound = async () => {
    if (!selectedLinkRoundId) {
      toast.error('Please select a recruitment round.');
      return;
    }
    setIsLinkingRound(true);
    try {
      await linkBatchToRound(batch.id, parseInt(selectedLinkRoundId));
      toast.success('Batch successfully linked to recruitment round.');
      setShowLinkRoundModal(false);
      fetchResultBatch(batchId);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to link batch to round.');
    } finally {
      setIsLinkingRound(false);
    }
  };

  // Filtered Items
  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      // Search filter
      const matchesSearch =
        !searchTerm ||
        item.extracted_usn?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.extracted_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.extracted_email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.matched_student?.full_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.matched_student?.usn?.toLowerCase().includes(searchTerm.toLowerCase());

      if (!matchesSearch) return false;

      // Status filter
      const status = (item.review_status || '').toLowerCase();
      if (filterState === 'all') return true;
      if (filterState === 'confirmed') return status === 'confirmed';
      if (filterState === 'ambiguous') return status === 'ambiguous';
      if (filterState === 'unmatched') return status === 'unresolved' || status === 'unmatched' || (!item.matched_student_id && status !== 'ignored');
      if (filterState === 'ignored') return status === 'ignored';
      if (filterState === 'ready') {
        return (
          status !== 'confirmed' &&
          status !== 'ignored' &&
          status !== 'ambiguous' &&
          Boolean(item.matched_student_id)
        );
      }
      return true;
    });
  }, [items, searchTerm, filterState]);

  // Checkbox Selection Logic
  const eligibleItems = useMemo(() => {
    return items.filter(
      (item) => {
        const status = (item.review_status || '').toLowerCase();
        return status !== 'confirmed' && status !== 'ignored' && status !== 'ambiguous' && Boolean(item.matched_student_id);
      }
    );
  }, [items]);

  const handleSelectAll = (e) => {
    if (e.target.checked) {
      const allEligibleIds = new Set(eligibleItems.map((item) => item.id));
      setSelectedItemIds(allEligibleIds);
    } else {
      setSelectedItemIds(new Set());
    }
  };

  const handleToggleSelect = (itemId) => {
    setSelectedItemIds((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) {
        next.delete(itemId);
      } else {
        next.add(itemId);
      }
      return next;
    });
  };

  // Student Search
  const handleStudentSearch = async (query) => {
    setStudentSearchQuery(query);
    if (!query || query.trim().length < 2) {
      setStudentSearchResults([]);
      return;
    }
    setIsSearchingStudents(true);
    try {
      const results = await searchStudentsForMatching(query.trim());
      setStudentSearchResults(results);
    } catch (err) {
      console.error(err);
      toast.error('Student search failed.');
    } finally {
      setIsSearchingStudents(false);
    }
  };

  const openMatchModal = (item) => {
    setMatchingItem(item);
    setStudentSearchQuery(item.extracted_name || item.extracted_usn || '');
    setMatchNotes('');
    handleStudentSearch(item.extracted_name || item.extracted_usn || '');
  };

  const closeMatchModal = () => {
    setMatchingItem(null);
    setStudentSearchQuery('');
    setStudentSearchResults([]);
    setMatchNotes('');
  };

  const handleAssignStudent = async (student) => {
    if (!matchingItem) return;
    setIsSubmittingMatch(true);
    try {
      await updateCandidateMatch(matchingItem.id, {
        student_id: student.id,
        review_status: 'matched',
        notes: matchNotes.trim() || `Manually assigned to ${student.full_name} (${student.usn})`,
      });
      toast.success(`Matched to ${student.full_name}`);
      closeMatchModal();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to update match.');
    } finally {
      setIsSubmittingMatch(false);
    }
  };

  const handleClearMatch = async (item) => {
    if ((item.review_status || '').toLowerCase() === 'confirmed') {
      toast.error('Cannot clear match on an already confirmed candidate.');
      return;
    }
    try {
      await updateCandidateMatch(item.id, {
        student_id: null,
        review_status: 'unresolved',
        notes: 'Match cleared by Placement Officer',
      });
      toast.success('Match cleared.');
      setSelectedItemIds((prev) => {
        const next = new Set(prev);
        next.delete(item.id);
        return next;
      });
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to clear match.');
    }
  };

  const handleToggleIgnore = async (item) => {
    const status = (item.review_status || '').toLowerCase();
    if (status === 'confirmed') {
      toast.error('Cannot ignore a confirmed record.');
      return;
    }
    const isCurrentlyIgnored = status === 'ignored';
    const newStatus = isCurrentlyIgnored ? (item.matched_student_id ? 'matched' : 'unresolved') : 'ignored';
    try {
      await updateCandidateMatch(item.id, {
        student_id: item.matched_student_id,
        review_status: newStatus,
        notes: newStatus === 'ignored' ? 'Ignored by officer' : 'Unignored by officer',
      });
      toast.success(newStatus === 'ignored' ? 'Record marked as ignored.' : 'Record restored.');
      if (newStatus === 'ignored') {
        setSelectedItemIds((prev) => {
          const next = new Set(prev);
          next.delete(item.id);
          return next;
        });
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to update ignore status.');
    }
  };

  // Confirmation Execution
  const handleConfirmSelected = async () => {
    if (selectedItemIds.size === 0) {
      toast.error('Please select at least one matched candidate to confirm.');
      return;
    }

    // Require all candidate identities to be resolved before confirmation
    const selectedItems = items.filter((item) => selectedItemIds.has(item.id));
    const unresolved = selectedItems.filter(
      (item) => !item.matched_student_id && item.review_status !== 'IGNORED'
    );
    if (unresolved.length > 0) {
      toast.error(
        `Cannot confirm ${unresolved.length} candidate(s) without student identity matches. Please assign students or mark them as ignored before confirming.`
      );
      return;
    }

    setIsConfirming(true);
    try {
      const payload = {
        item_ids: Array.from(selectedItemIds),
        notes: confirmNotes.trim() || undefined,
      };
      const res = await confirmBatchResults(batch.id, payload);
      toast.success(
        `Confirmation complete: ${res.confirmed_count} candidate(s) confirmed, ${res.notifications_sent} notification(s) sent.`
      );
      setShowConfirmModal(false);
      setConfirmNotes('');
      setSelectedItemIds(new Set());
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to confirm results.');
    } finally {
      setIsConfirming(false);
    }
  };

  if (isResultsLoading && !batch) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (!batch) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8 text-center">
        <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-2">Batch not found</h2>
        <button
          onClick={() => navigate('/placement/results')}
          className="inline-flex items-center text-indigo-600 hover:text-indigo-700"
        >
          <ArrowLeft className="w-4 h-4 mr-1" /> Back to Result Batches
        </button>
      </div>
    );
  }

  const isConfirmed = batch.status === 'CONFIRMED';
  const isPartiallyConfirmed = batch.status === 'PARTIALLY_CONFIRMED';

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Back button & Header */}
      <div>
        <button
          onClick={() => navigate('/placement/results')}
          className="inline-flex items-center text-sm font-medium text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 mb-4 transition-colors"
        >
          <ArrowLeft className="w-4 h-4 mr-1" /> Back to Result Batches
        </button>

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white dark:bg-gray-800 p-6 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
          <div className="space-y-1">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                {batch.round_name}
              </h1>
              {batch.round_id ? (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                  <Layers className="w-3.5 h-3.5 mr-1" />
                  Round #{batch.round_number || batch.round_id}
                </span>
              ) : batch.job_posting_id ? (
                <button
                  onClick={() => setShowLinkRoundModal(true)}
                  className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300 border border-amber-200 dark:border-amber-800 hover:bg-amber-100 cursor-pointer transition-colors"
                  title="Link this result batch to an authoritative Recruitment Round"
                >
                  <Layers className="w-3.5 h-3.5 mr-1" />
                  Link to Round
                </button>
              ) : null}
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium uppercase tracking-wide bg-indigo-50 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300">
                {batch.round_type}
              </span>
              {batch.is_final_round ? (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-50 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
                  <Award className="w-3.5 h-3.5 mr-1" /> Final Process Selection
                </span>
              ) : (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
                  Intermediate Round
                </span>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-4 text-sm text-gray-500 dark:text-gray-400 pt-1">
              <div className="flex items-center gap-1.5">
                <Building2 className="w-4 h-4 text-gray-400" />
                <span className="font-medium text-gray-700 dark:text-gray-300">
                  {batch.company_name}
                </span>
              </div>
              {batch.job_title && (
                <div className="flex items-center gap-1.5">
                  <Briefcase className="w-4 h-4 text-gray-400" />
                  <span>{batch.job_title}</span>
                </div>
              )}
              {batch.source_file && (
                <div className="flex items-center gap-1.5">
                  <FileText className="w-4 h-4 text-gray-400" />
                  <span>{batch.source_file.original_name}</span>
                  <a
                    href={`/api/v1/placement/results/batches/${batch.id}/download`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 ml-1 text-xs font-medium text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 dark:hover:text-indigo-300 underline"
                    title="Download original uploaded file"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Download
                  </a>
                </div>
              )}
              <div className="flex items-center gap-1.5">
                <Clock className="w-4 h-4 text-gray-400" />
                <span>Uploaded {new Date(batch.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span
              className={`inline-flex items-center px-3 py-1.5 rounded-full text-xs font-semibold ${
                batch.status === 'CONFIRMED'
                  ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300'
                  : batch.status === 'PARTIALLY_CONFIRMED'
                  ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-300'
                  : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-300'
              }`}
            >
              {batch.status.replace('_', ' ')}
            </span>

            {eligibleItems.length > 0 && (
              <button
                onClick={() => setShowConfirmModal(true)}
                disabled={selectedItemIds.size === 0}
                className="inline-flex items-center px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 dark:disabled:bg-gray-700 text-white rounded-lg text-sm font-medium shadow-sm transition-colors cursor-pointer"
              >
                <CheckCircle className="w-4 h-4 mr-1.5" />
                Confirm Selected ({selectedItemIds.size})
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-white dark:bg-gray-800 p-4 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Total Extracted</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">
            {batch.total_rows}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-800 p-4 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
          <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">
            Identified / Matched
          </p>
          <p className="text-2xl font-bold text-emerald-700 dark:text-emerald-300 mt-1">
            {batch.matched_count}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-800 p-4 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
          <p className="text-xs font-medium text-amber-600 dark:text-amber-400">
            Ambiguous / Review
          </p>
          <p className="text-2xl font-bold text-amber-700 dark:text-amber-300 mt-1">
            {batch.ambiguous_count}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-800 p-4 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
          <p className="text-xs font-medium text-blue-600 dark:text-blue-400">Confirmed</p>
          <p className="text-2xl font-bold text-blue-700 dark:text-blue-300 mt-1">
            {batch.confirmed_count}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-800 p-4 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Unmatched / Ignored</p>
          <p className="text-2xl font-bold text-gray-700 dark:text-gray-300 mt-1">
            {batch.total_rows - batch.matched_count - batch.ambiguous_count}
          </p>
        </div>
      </div>

      {/* Round Semantics Notice */}
      <div
        className={`p-4 rounded-xl border flex items-start gap-3 ${
          batch.is_final_round
            ? 'bg-purple-50 border-purple-200 text-purple-900 dark:bg-purple-950/30 dark:border-purple-800 dark:text-purple-200'
            : 'bg-blue-50 border-blue-200 text-blue-900 dark:bg-blue-950/30 dark:border-blue-800 dark:text-blue-200'
        }`}
      >
        <Info className="w-5 h-5 flex-shrink-0 mt-0.5" />
        <div className="text-sm">
          <p className="font-semibold">
            {batch.is_final_round
              ? 'Final Recruitment Selection Round'
              : 'Intermediate Recruitment Round'}
          </p>
          <p className="mt-0.5 opacity-90">
            {batch.is_final_round
              ? 'Confirming candidates with "SELECTED" in this final round updates their job application status to SELECTED (cleared all selection rounds). Note: Verified placement offers with CTC and offer letters are recorded separately in the Verified Offers tab.'
              : 'Confirming candidates in this round records chronological round outcomes and sends progression alerts. It will NOT alter institutional placement counts or create verified offers.'}
          </p>
        </div>
      </div>

      {/* Filter and Candidate Table */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden">
        {/* Table Toolbar */}
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex flex-col sm:flex-row gap-3 items-center justify-between">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search USN, name, email..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Filter className="w-4 h-4 text-gray-400" />
            <select
              value={filterState}
              onChange={(e) => setFilterState(e.target.value)}
              className="text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 py-1.5 px-3 focus:ring-2 focus:ring-indigo-500"
            >
              <option value="all">All Records ({items.length})</option>
              <option value="ready">Ready to Confirm ({eligibleItems.length})</option>
              <option value="confirmed">Confirmed ({batch.confirmed_count})</option>
              <option value="ambiguous">Ambiguous ({batch.ambiguous_count})</option>
              <option value="unmatched">Unmatched</option>
              <option value="ignored">Ignored</option>
            </select>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700 text-left text-sm">
            <thead className="bg-gray-50 dark:bg-gray-900/50 text-gray-600 dark:text-gray-300 font-semibold text-xs uppercase tracking-wider">
              <tr>
                <th scope="col" className="px-4 py-3 w-10">
                  <input
                    type="checkbox"
                    checked={
                      eligibleItems.length > 0 &&
                      eligibleItems.every((item) => selectedItemIds.has(item.id))
                    }
                    onChange={handleSelectAll}
                    disabled={eligibleItems.length === 0}
                    className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                  />
                </th>
                <th scope="col" className="px-4 py-3">
                  Row
                </th>
                <th scope="col" className="px-4 py-3">
                  Extracted Record
                </th>
                <th scope="col" className="px-4 py-3">
                  Result Status
                </th>
                <th scope="col" className="px-4 py-3">
                  Matched Student
                </th>
                <th scope="col" className="px-4 py-3">
                  Match Method & Confidence
                </th>
                <th scope="col" className="px-4 py-3">
                  Review State
                </th>
                <th scope="col" className="px-4 py-3 text-right">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700 bg-white dark:bg-gray-800">
              {filteredItems.length === 0 ? (
                <tr>
                  <td colSpan="8" className="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
                    No records match the current filter.
                  </td>
                </tr>
              ) : (
                filteredItems.map((item) => {
                  const status = (item.review_status || '').toLowerCase();
                  const isItemConfirmed = status === 'confirmed';
                  const isItemIgnored = status === 'ignored';
                  const isItemAmbiguous = status === 'ambiguous';
                  const canSelect =
                    !isItemConfirmed && !isItemIgnored && !isItemAmbiguous && Boolean(item.matched_student_id);

                  return (
                    <tr
                      key={item.id}
                      className={`hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors ${
                        isItemIgnored ? 'opacity-60 bg-gray-50/50 dark:bg-gray-900/20' : ''
                      }`}
                    >
                      {/* Checkbox */}
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          checked={selectedItemIds.has(item.id)}
                          onChange={() => handleToggleSelect(item.id)}
                          disabled={!canSelect}
                          className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 disabled:opacity-40"
                        />
                      </td>

                      {/* Row Index */}
                      <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400 font-mono">
                        #{item.source_row_index != null ? item.source_row_index + 1 : '—'}
                      </td>

                      {/* Extracted Record */}
                      <td className="px-4 py-3">
                        <div className="font-medium text-gray-900 dark:text-gray-100">
                          {item.extracted_name || '—'}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400 font-mono">
                          {item.extracted_usn || 'No USN'}
                        </div>
                        {item.extracted_email && (
                          <div className="text-xs text-gray-400 dark:text-gray-500">
                            {item.extracted_email}
                          </div>
                        )}
                      </td>

                      {/* Status */}
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold uppercase ${
                            item.normalized_status?.toLowerCase() === 'selected'
                              ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300'
                              : item.normalized_status?.toLowerCase() === 'shortlisted'
                              ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300'
                              : item.normalized_status?.toLowerCase() === 'rejected'
                              ? 'bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-300'
                              : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                          }`}
                        >
                          {item.normalized_status}
                        </span>
                        {item.raw_status && item.raw_status !== item.normalized_status && (
                          <div className="text-xs text-gray-400 mt-0.5">({item.raw_status})</div>
                        )}
                      </td>

                      {/* Matched Student */}
                      <td className="px-4 py-3">
                        {item.matched_student ? (
                          <div>
                            <div className="font-medium text-gray-900 dark:text-gray-100">
                              {item.matched_student.full_name}
                            </div>
                            <div className="text-xs text-gray-500 dark:text-gray-400 font-mono">
                              {item.matched_student.usn} • {item.matched_student.department || '—'}
                            </div>
                          </div>
                        ) : isItemAmbiguous ? (
                          <div className="text-amber-600 dark:text-amber-400 text-xs flex items-center gap-1">
                            <AlertTriangle className="w-3.5 h-3.5" />
                            <span>Ambiguous: multiple candidate matches</span>
                          </div>
                        ) : (
                          <span className="text-xs text-gray-400 italic">No student matched</span>
                        )}
                      </td>

                      {/* Match Confidence & Method */}
                      <td className="px-4 py-3">
                        {item.match_confidence != null ? (
                          <div className="space-y-1">
                            <div className="flex items-center gap-1.5">
                              <span
                                className={`inline-flex px-1.5 py-0.5 rounded text-xs font-mono font-medium ${
                                  item.match_confidence >= 0.95
                                    ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
                                    : item.match_confidence >= 0.7
                                    ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300'
                                    : 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300'
                                }`}
                              >
                                {Math.round(item.match_confidence * 100)}%
                              </span>
                              <span className="text-xs text-gray-500 dark:text-gray-400 capitalize">
                                {item.match_method?.replace(/_/g, ' ') || 'none'}
                              </span>
                            </div>
                          </div>
                        ) : (
                          <span className="text-xs text-gray-400">—</span>
                        )}
                      </td>

                      {/* Review State */}
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium uppercase ${
                            status === 'confirmed'
                              ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300'
                              : status === 'matched'
                              ? 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/50 dark:text-indigo-300'
                              : status === 'ambiguous'
                              ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-300'
                              : status === 'ignored'
                              ? 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
                              : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                          }`}
                        >
                          {item.review_status}
                        </span>
                      </td>

                      {/* Actions */}
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {!isItemConfirmed && (
                            <>
                              <button
                                onClick={() => openMatchModal(item)}
                                title="Assign / Search Student"
                                className="p-1 text-gray-500 hover:text-indigo-600 dark:text-gray-400 dark:hover:text-indigo-300 transition-colors"
                              >
                                <UserCheck className="w-4 h-4" />
                              </button>
                              {item.matched_student_id && (
                                <button
                                  onClick={() => handleClearMatch(item)}
                                  title="Clear Match"
                                  className="p-1 text-gray-500 hover:text-red-600 dark:text-gray-400 dark:hover:text-red-300 transition-colors"
                                >
                                  <UserX className="w-4 h-4" />
                                </button>
                              )}
                              <button
                                onClick={() => handleToggleIgnore(item)}
                                title={isItemIgnored ? 'Restore Record' : 'Ignore Record'}
                                className={`p-1 transition-colors ${
                                  isItemIgnored
                                    ? 'text-indigo-600 hover:text-indigo-700 dark:text-indigo-400'
                                    : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-200'
                                }`}
                              >
                                <EyeOff className="w-4 h-4" />
                              </button>
                            </>
                          )}
                          {isItemConfirmed && (
                            <span className="text-xs text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                              <Check className="w-3.5 h-3.5" /> Confirmed
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Manual Matching Modal */}
      {matchingItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white dark:bg-gray-800 rounded-2xl max-w-xl w-full p-6 shadow-xl border border-gray-200 dark:border-gray-700 space-y-4">
            <div className="flex items-center justify-between border-b border-gray-200 dark:border-gray-700 pb-3">
              <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                <UserCheck className="w-5 h-5 text-indigo-600" />
                Manual Student Matching
              </h3>
              <button
                onClick={closeMatchModal}
                className="text-gray-400 hover:text-gray-500 dark:hover:text-gray-300"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Extracted Record Card */}
            <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg text-xs space-y-1">
              <div className="font-semibold text-gray-700 dark:text-gray-300">
                Source Row Details:
              </div>
              <div>Name: <span className="font-medium text-gray-900 dark:text-gray-100">{matchingItem.extracted_name || '—'}</span></div>
              <div>USN: <span className="font-mono text-gray-900 dark:text-gray-100">{matchingItem.extracted_usn || '—'}</span></div>
              <div>Email: <span className="text-gray-900 dark:text-gray-100">{matchingItem.extracted_email || '—'}</span></div>
            </div>

            {/* Student Search Input */}
            <div className="space-y-2">
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
                Search Registered Students
              </label>
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search by USN or Name..."
                  value={studentSearchQuery}
                  onChange={(e) => handleStudentSearch(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>

            {/* Search Results List */}
            <div className="max-h-60 overflow-y-auto divide-y divide-gray-100 dark:divide-gray-700 border border-gray-200 dark:border-gray-700 rounded-lg">
              {isSearchingStudents ? (
                <div className="p-4 text-center text-sm text-gray-500">Searching students...</div>
              ) : studentSearchResults.length === 0 ? (
                <div className="p-4 text-center text-sm text-gray-500">
                  {studentSearchQuery.length < 2
                    ? 'Type at least 2 characters to search'
                    : 'No registered students found'}
                </div>
              ) : (
                studentSearchResults.map((student) => (
                  <div
                    key={student.id}
                    className="p-3 hover:bg-indigo-50/50 dark:hover:bg-indigo-950/30 flex items-center justify-between transition-colors"
                  >
                    <div>
                      <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                        {student.full_name}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400 font-mono">
                        {student.usn} • {student.department || 'General'}
                      </div>
                      <div className="text-xs text-gray-400">{student.email}</div>
                    </div>
                    <button
                      onClick={() => handleAssignStudent(student)}
                      disabled={isSubmittingMatch}
                      className="px-3 py-1.5 text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors"
                    >
                      Assign
                    </button>
                  </div>
                ))
              )}
            </div>

            {/* Officer Notes */}
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                Officer Review Notes (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. Identity corroborated via placement drive attendance list"
                value={matchNotes}
                onChange={(e) => setMatchNotes(e.target.value)}
                className="w-full px-3 py-1.5 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={closeMatchModal}
                className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Modal */}
      {showConfirmModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white dark:bg-gray-800 rounded-2xl max-w-lg w-full p-6 shadow-xl border border-gray-200 dark:border-gray-700 space-y-4">
            <div className="flex items-center justify-between border-b border-gray-200 dark:border-gray-700 pb-3">
              <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                <CheckCircle className="w-5 h-5 text-indigo-600" />
                Confirm Recruitment Results
              </h3>
              <button
                onClick={() => setShowConfirmModal(false)}
                className="text-gray-400 hover:text-gray-500 dark:hover:text-gray-300"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-sm text-gray-600 dark:text-gray-300">
              <p>
                You are about to confirm{' '}
                <strong className="text-gray-900 dark:text-gray-100 font-bold">
                  {selectedItemIds.size}
                </strong>{' '}
                candidate result record(s) for <strong>{batch.company_name}</strong> —{' '}
                <strong>{batch.round_name}</strong>.
              </p>

              {batch.round_id ? (
                <div className="p-2.5 bg-indigo-50/70 dark:bg-indigo-950/30 border border-indigo-200 dark:border-indigo-800 rounded-lg text-xs text-indigo-900 dark:text-indigo-200 flex items-center gap-2">
                  <Layers className="w-4 h-4 text-indigo-600 shrink-0" />
                  <span>
                    Linked to <strong>Round #{batch.round_number || batch.round_id}: {batch.round_name}</strong>. Outcomes will be written to student progression ledger.
                  </span>
                </div>
              ) : (
                <div className="p-2.5 bg-amber-50/70 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg text-xs text-amber-900 dark:text-amber-200 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                  <span>
                    This batch is unlinked. To maintain chronological round progression, link this batch to an authoritative round.
                  </span>
                </div>
              )}

              {batch.is_final_round ? (
                <div className="p-3 bg-purple-50 dark:bg-purple-950/40 border border-purple-200 dark:border-purple-800 rounded-lg text-purple-900 dark:text-purple-200 text-xs space-y-1">
                  <p className="font-bold text-purple-800 dark:text-purple-200">
                    Final Recruitment Selection Round:
                  </p>
                  <p>
                    Confirmed candidates with status <span className="font-semibold">SELECTED</span> will have their job application status set to <strong>SELECTED</strong> (cleared all selection rounds).
                  </p>
                  <p className="font-semibold text-amber-800 dark:text-amber-300 pt-1">
                    ⚠️ Policy Notice: Final process selection does NOT automatically issue or verify a placement offer. Formal offers must be inspected and verified in Verified Offers with verified CTC and offer letter attachment.
                  </p>
                </div>
              ) : (
                <div className="p-3 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded-lg text-blue-900 dark:text-blue-200 text-xs">
                  <strong>Intermediate Round:</strong> Confirmed candidates will have their round
                  outcomes recorded in their progression history. Institutional placement statistics remain unchanged.
                </div>
              )}

              <div>
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Confirmation Audit Notes (Optional)
                </label>
                <textarea
                  rows="2"
                  placeholder="e.g. Verified by campus drive coordinator"
                  value={confirmNotes}
                  onChange={(e) => setConfirmNotes(e.target.value)}
                  className="w-full px-3 py-1.5 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-3 border-t border-gray-200 dark:border-gray-700">
              <button
                type="button"
                onClick={() => setShowConfirmModal(false)}
                disabled={isConfirming}
                className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmSelected}
                disabled={isConfirming}
                className="inline-flex items-center px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium shadow-sm transition-colors cursor-pointer"
              >
                {isConfirming ? 'Processing...' : 'Confirm & Dispatch'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Link Round Modal */}
      {showLinkRoundModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-gray-200 dark:border-gray-700 pb-3">
              <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                <Layers className="w-5 h-5 text-indigo-600" />
                Link Batch to Recruitment Round
              </h3>
              <button
                onClick={() => setShowLinkRoundModal(false)}
                className="text-gray-400 hover:text-gray-500 dark:hover:text-gray-300"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-gray-600 dark:text-gray-300">
              Select an authoritative recruitment round defined for this job posting to associate with this result batch.
            </p>

            {jobRoundsForLinking.length === 0 ? (
              <div className="p-4 bg-gray-50 dark:bg-gray-900 rounded-lg text-center text-xs text-gray-500">
                No recruitment rounds found for this job posting yet. Create rounds under Job Details &gt; Recruitment Rounds first.
              </div>
            ) : (
              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Available Rounds <span className="text-rose-500">*</span>
                </label>
                <select
                  value={selectedLinkRoundId}
                  onChange={(e) => setSelectedLinkRoundId(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">-- Select Round --</option>
                  {jobRoundsForLinking.map((r) => (
                    <option key={r.id} value={r.id}>
                      Round #{r.round_number}: {r.round_name} ({r.round_type}) {r.is_final ? '[FINAL]' : ''}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="flex justify-end gap-3 pt-3 border-t border-gray-200 dark:border-gray-700">
              <button
                type="button"
                onClick={() => setShowLinkRoundModal(false)}
                disabled={isLinkingRound}
                className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleExecuteLinkRound}
                disabled={isLinkingRound || !selectedLinkRoundId}
                className="inline-flex items-center px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium shadow-sm transition-colors cursor-pointer"
              >
                {isLinkingRound ? 'Linking...' : 'Link to Round'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
