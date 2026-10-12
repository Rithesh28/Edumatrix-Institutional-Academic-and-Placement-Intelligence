import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  RefreshCw,
  Database,
  Trash2,
  Archive,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ShieldCheck,
  ShieldAlert,
  ShieldX,
  ChevronDown,
  ChevronRight,
  Search,
  Filter,
  Check,
  Building2,
  Briefcase,
  Users,
  Paperclip,
  Award,
  AlertCircle,
  FileText,
  Info,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import { useAuthStore } from '../../store/authStore';
import toast from 'react-hot-toast';

const CONFIRMATION_PHRASE = 'CONFIRM_PURGE_TEST_DATA';

const ManageTestData = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const {
    cleanupPreview,
    isCleanupLoading,
    cleanupError,
    cleanupResult,
    fetchCleanupPreview,
    runCleanup,
    clearCleanupResult,
    fetchCirculars,
  } = usePlacementStore();

  const isPrivileged =
    user?.role === 'placement_officer' ||
    user?.role === 'placement' ||
    user?.role === 'admin';

  // Local state
  const [searchTerm, setSearchTerm] = useState('');
  const [safetyFilter, setSafetyFilter] = useState('all');
  const [selectedIds, setSelectedIds] = useState([]);
  const [expandedRowIds, setExpandedRowIds] = useState(new Set());

  // Modal states
  const [archiveModalOpen, setArchiveModalOpen] = useState(false);
  const [purgeModalOpen, setPurgeModalOpen] = useState(false);
  const [confirmationInput, setConfirmationInput] = useState('');
  const [actionError, setActionError] = useState(null);

  // Initial load
  useEffect(() => {
    if (isPrivileged) {
      loadPreview();
    }
  }, [isPrivileged]);

  const loadPreview = async () => {
    try {
      setActionError(null);
      await fetchCleanupPreview({ include_all_candidates: true });
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to load cleanup preview';
      setActionError(msg);
      toast.error(msg);
    }
  };

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

  // Filter candidates
  const filteredCandidates = useMemo(() => {
    return candidates.filter((item) => {
      const matchesSearch =
        !searchTerm ||
        item.company_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        String(item.company_id).includes(searchTerm);

      const matchesSafety =
        safetyFilter === 'all' || item.safety_classification === safetyFilter;

      return matchesSearch && matchesSafety;
    });
  }, [candidates, searchTerm, safetyFilter]);

  // Selected companies details
  const selectedCompanies = useMemo(() => {
    return candidates.filter((c) => selectedIds.includes(c.company_id));
  }, [candidates, selectedIds]);

  const selectedSafetyBreakdown = useMemo(() => {
    const safe = selectedCompanies.filter((c) => c.safety_classification === 'SAFE_TO_PURGE').length;
    const requiresArchive = selectedCompanies.filter((c) => c.safety_classification === 'REQUIRES_ARCHIVE').length;
    const protectedCount = selectedCompanies.filter((c) => c.safety_classification === 'PROTECTED_GENUINE').length;
    return { safe, requiresArchive, protectedCount };
  }, [selectedCompanies]);

  const hasIneligibleForPurge = useMemo(() => {
    return selectedCompanies.some(
      (c) => c.safety_classification === 'REQUIRES_ARCHIVE' || c.safety_classification === 'PROTECTED_GENUINE'
    );
  }, [selectedCompanies]);

  // Selection handlers
  const handleToggleSelect = (id) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleSelectAllVisible = () => {
    const visibleIds = filteredCandidates.map((c) => c.company_id);
    const allSelected = visibleIds.every((id) => selectedIds.includes(id));
    if (allSelected) {
      setSelectedIds((prev) => prev.filter((id) => !visibleIds.includes(id)));
    } else {
      setSelectedIds((prev) => Array.from(new Set([...prev, ...visibleIds])));
    }
  };

  const toggleRowExpand = (id) => {
    setExpandedRowIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  // Execution Handlers
  const handleOpenArchive = () => {
    if (selectedIds.length === 0) {
      toast.error('Select at least one company to archive.');
      return;
    }
    setActionError(null);
    setArchiveModalOpen(true);
  };

  const handleConfirmArchive = async () => {
    setActionError(null);
    try {
      const payload = {
        company_ids: selectedIds,
        mode: 'archive',
      };
      await runCleanup(payload);
      toast.success(`Successfully archived ${selectedIds.length} candidate company(ies).`);
      setArchiveModalOpen(false);
      setSelectedIds([]);
      await loadPreview();
      fetchCirculars();
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Archive operation failed.';
      setActionError(msg);
      toast.error(msg);
    }
  };

  const handleOpenPurge = () => {
    if (selectedIds.length === 0) {
      toast.error('Select at least one company to purge.');
      return;
    }
    if (hasIneligibleForPurge) {
      toast.error('Cannot purge selected companies: Some require archival or are protected.');
      return;
    }
    setActionError(null);
    setConfirmationInput('');
    setPurgeModalOpen(true);
  };

  const handleConfirmPurge = async () => {
    if (confirmationInput.trim() !== CONFIRMATION_PHRASE) {
      setActionError(`Confirmation phrase must match "${CONFIRMATION_PHRASE}" exactly.`);
      return;
    }
    setActionError(null);
    try {
      const payload = {
        company_ids: selectedIds,
        mode: 'purge',
        confirmation_phrase: CONFIRMATION_PHRASE,
      };
      await runCleanup(payload);
      toast.success(`Successfully purged ${selectedIds.length} candidate company(ies).`);
      setPurgeModalOpen(false);
      setSelectedIds([]);
      setConfirmationInput('');
      await loadPreview();
      fetchCirculars();
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Purge operation failed.';
      setActionError(msg);
      toast.error(msg);
    }
  };

  const getSafetyBadge = (classification) => {
    switch (classification) {
      case 'SAFE_TO_PURGE':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
            <span>Safe to Purge</span>
          </span>
        );
      case 'REQUIRES_ARCHIVE':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-full bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
            <ShieldAlert className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
            <span>Requires Archive</span>
          </span>
        );
      case 'PROTECTED_GENUINE':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-800 dark:bg-red-950/80 dark:text-red-300 border border-red-200 dark:border-red-800">
            <ShieldX className="w-3.5 h-3.5 text-red-600 dark:text-red-400" />
            <span>Protected Genuine</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300">
            {classification}
          </span>
        );
    }
  };

  if (!isPrivileged) {
    return (
      <div className="p-8 text-center max-w-lg mx-auto">
        <div className="p-4 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-xl text-red-700 dark:text-red-300 space-y-3">
          <AlertTriangle className="w-8 h-8 text-red-600 mx-auto" />
          <h2 className="text-lg font-bold">Unauthorized Access</h2>
          <p className="text-xs">
            Only Placement Officers and Administrators are authorized to view or manage recruitment test data cleanup.
          </p>
          <button
            onClick={() => navigate('/placement/circulars')}
            className="mt-2 px-4 py-2 bg-red-600 text-white rounded-lg text-xs font-semibold"
          >
            Return to Recruitment Drives
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-16 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <button
            onClick={() => navigate('/placement/circulars')}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 mb-2 cursor-pointer transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Recruitment Drives</span>
          </button>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Database className="w-7 h-7 text-indigo-600 dark:text-indigo-400" />
            <span>Manage Test Data</span>
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Safe, preview-first administrative interface to inspect test candidate companies and execute archive or purge actions.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadPreview}
            disabled={isCleanupLoading}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-gray-700 rounded-lg text-xs font-semibold shadow-sm transition-colors cursor-pointer disabled:opacity-50"
            title="Refresh candidate preview from backend"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isCleanupLoading ? 'animate-spin text-indigo-600' : ''}`} />
            <span>Refresh Preview</span>
          </button>
        </div>
      </div>

      {/* Mandatory Safety Notice Banner */}
      <div className="p-4 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-xl flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
        <div className="text-xs text-amber-800 dark:text-amber-200 space-y-1">
          <p className="font-semibold text-sm text-amber-900 dark:text-amber-100">
            Administrative Review Aid — Verification Required
          </p>
          <p>
            The test-pattern detector flags candidate companies using automated naming signals (e.g., timestamps, "test", "mock", "temp").
            <strong> A test-like name is an evaluation signal only, never an authorization to delete records.</strong>
          </p>
          <p className="text-amber-700 dark:text-amber-300">
            The backend strictly validates safety classifications in real time. Genuine student applications, confirmed progression outcomes, accepted offers, and shared files are protected from permanent deletion.
          </p>
        </div>
      </div>

      {/* Aggregate Preview Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
        <div className="bg-white dark:bg-gray-900 p-3.5 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
          <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider block">
            Flagged Candidates
          </span>
          <p className="text-xl font-bold text-gray-900 dark:text-white mt-1">
            {summary.total_candidates_flagged}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-900 p-3.5 rounded-xl border border-emerald-200 dark:border-emerald-800/60 shadow-sm">
          <span className="text-[11px] font-medium text-emerald-600 dark:text-emerald-400 uppercase tracking-wider block">
            Safe to Purge
          </span>
          <p className="text-xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
            {summary.total_safe_to_purge}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-900 p-3.5 rounded-xl border border-amber-200 dark:border-amber-800/60 shadow-sm">
          <span className="text-[11px] font-medium text-amber-600 dark:text-amber-400 uppercase tracking-wider block">
            Requires Archive
          </span>
          <p className="text-xl font-bold text-amber-600 dark:text-amber-400 mt-1">
            {summary.total_requires_archive}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-900 p-3.5 rounded-xl border border-red-200 dark:border-red-800/60 shadow-sm">
          <span className="text-[11px] font-medium text-red-600 dark:text-red-400 uppercase tracking-wider block">
            Protected Genuine
          </span>
          <p className="text-xl font-bold text-red-600 dark:text-red-400 mt-1">
            {summary.total_protected_genuine}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-900 p-3.5 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
          <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider block">
            Dependent Jobs
          </span>
          <p className="text-xl font-bold text-gray-700 dark:text-gray-300 mt-1">
            {summary.total_dependent_jobs}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-900 p-3.5 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
          <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider block">
            Dependent Drives
          </span>
          <p className="text-xl font-bold text-gray-700 dark:text-gray-300 mt-1">
            {summary.total_dependent_circulars}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-900 p-3.5 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm col-span-2 sm:col-span-1">
          <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider block">
            Shared Files Preserved
          </span>
          <p className="text-xl font-bold text-blue-600 dark:text-blue-400 mt-1">
            {summary.total_shared_files_preserved}
          </p>
        </div>
      </div>

      {/* Action Toolbar */}
      <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm space-y-3">
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="text-xs font-medium text-gray-700 dark:text-gray-300">
              Selected: <strong className="text-indigo-600 dark:text-indigo-400">{selectedIds.length}</strong> of {candidates.length}
            </span>
            {selectedIds.length > 0 && (
              <div className="flex items-center gap-1.5 text-[11px] text-gray-500 dark:text-gray-400">
                <span>(Safe: {selectedSafetyBreakdown.safe},</span>
                <span>Archive: {selectedSafetyBreakdown.requiresArchive},</span>
                <span>Protected: {selectedSafetyBreakdown.protectedCount})</span>
                <button
                  onClick={() => setSelectedIds([])}
                  className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline ml-1 cursor-pointer"
                >
                  Clear Selection
                </button>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleOpenArchive}
              disabled={selectedIds.length === 0 || isCleanupLoading}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              title="Deactivate companies and archive dependent jobs and circulars"
            >
              <Archive className="w-3.5 h-3.5" />
              <span>Archive Selected ({selectedIds.length})</span>
            </button>

            <button
              onClick={handleOpenPurge}
              disabled={selectedIds.length === 0 || hasIneligibleForPurge || isCleanupLoading}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              title={
                hasIneligibleForPurge
                  ? 'Cannot purge: Selected companies include protected or archival-required records'
                  : 'Permanently purge selected test records'
              }
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Purge Selected ({selectedIds.length})</span>
            </button>
          </div>
        </div>

        {hasIneligibleForPurge && (
          <div className="p-2.5 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/80 rounded-lg text-xs text-amber-800 dark:text-amber-200 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-amber-600 flex-shrink-0" />
            <span>
              <strong>Purge blocked for current selection:</strong> One or more selected companies have genuine placement history (applications, confirmed outcomes, offers) or require archival. Uncheck them or use <strong>Archive Selected</strong> instead.
            </span>
          </div>
        )}
      </div>

      {/* Search and Safety Filter */}
      <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between bg-white dark:bg-gray-900 p-3.5 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search candidate company name or ID..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-1.5 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:text-white"
          />
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto">
          {[
            { id: 'all', label: 'All Candidates' },
            { id: 'SAFE_TO_PURGE', label: 'Safe to Purge' },
            { id: 'REQUIRES_ARCHIVE', label: 'Requires Archive' },
            { id: 'PROTECTED_GENUINE', label: 'Protected Genuine' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setSafetyFilter(tab.id)}
              className={`px-2.5 py-1.5 text-xs font-medium rounded-lg transition-colors cursor-pointer whitespace-nowrap ${
                safetyFilter === tab.id
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Candidate Companies Table */}
      {isCleanupLoading && candidates.length === 0 ? (
        <div className="p-12 text-center text-gray-500 dark:text-gray-400 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
          <div className="animate-spin w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full mx-auto mb-3" />
          <p className="text-sm">Evaluating recruitment cleanup candidates...</p>
        </div>
      ) : filteredCandidates.length === 0 ? (
        <div className="p-12 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 text-center space-y-2">
          <Database className="w-10 h-10 text-gray-400 mx-auto" />
          <h3 className="text-base font-semibold text-gray-900 dark:text-white">
            No cleanup candidates found
          </h3>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {searchTerm || safetyFilter !== 'all'
              ? 'Try adjusting your search query or filter criteria.'
              : 'No test-pattern companies or cleanup candidates detected in the system.'}
          </p>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-gray-600 dark:text-gray-300">
              <thead className="bg-gray-50 dark:bg-gray-800/70 text-[11px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider border-b border-gray-200 dark:border-gray-800">
                <tr>
                  <th className="py-3 px-4 w-10">
                    <input
                      type="checkbox"
                      checked={
                        filteredCandidates.length > 0 &&
                        filteredCandidates.every((c) => selectedIds.includes(c.company_id))
                      }
                      onChange={handleSelectAllVisible}
                      className="rounded text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                    />
                  </th>
                  <th className="py-3 px-3">Company</th>
                  <th className="py-3 px-3">Status</th>
                  <th className="py-3 px-3">Classification</th>
                  <th className="py-3 px-3">Dependencies</th>
                  <th className="py-3 px-3">Protection & Signal Reasons</th>
                  <th className="py-3 px-4 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {filteredCandidates.map((cand) => {
                  const isSelected = selectedIds.includes(cand.company_id);
                  const isExpanded = expandedRowIds.has(cand.company_id);
                  const counts = cand.dependent_counts;

                  return (
                    <React.Fragment key={cand.company_id}>
                      <tr
                        className={`hover:bg-gray-50/70 dark:hover:bg-gray-800/40 transition-colors ${
                          isSelected ? 'bg-indigo-50/40 dark:bg-indigo-950/20' : ''
                        }`}
                      >
                        <td className="py-3.5 px-4">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => handleToggleSelect(cand.company_id)}
                            className="rounded text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                          />
                        </td>
                        <td className="py-3.5 px-3">
                          <div className="font-semibold text-gray-900 dark:text-white flex items-center gap-1.5">
                            <Building2 className="w-3.5 h-3.5 text-indigo-500 flex-shrink-0" />
                            <span>{cand.company_name}</span>
                          </div>
                          <span className="text-[11px] text-gray-400">ID: #{cand.company_id}</span>
                        </td>
                        <td className="py-3.5 px-3">
                          {cand.is_active ? (
                            <span className="px-2 py-0.5 text-[11px] font-medium rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300">
                              Active
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 text-[11px] font-medium rounded-full bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300">
                              Inactive
                            </span>
                          )}
                        </td>
                        <td className="py-3.5 px-3">
                          {getSafetyBadge(cand.safety_classification)}
                        </td>
                        <td className="py-3.5 px-3">
                          <div className="flex flex-wrap gap-1.5 text-[11px]">
                            <span className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-gray-600 dark:text-gray-300" title="Job Postings">
                              💼 {counts.jobs_count}
                            </span>
                            <span className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-gray-600 dark:text-gray-300" title="Recruitment Drives">
                              📢 {counts.circulars_count}
                            </span>
                            <span className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-gray-600 dark:text-gray-300" title="Student Applications">
                              📋 {counts.applications_count}
                            </span>
                            {counts.offers_count > 0 && (
                              <span className="px-1.5 py-0.5 bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300 rounded font-medium" title="Offers">
                                🏆 {counts.offers_count} ({counts.accepted_offers_count} acc)
                              </span>
                            )}
                            {counts.files_count > 0 && (
                              <span className="px-1.5 py-0.5 bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300 rounded" title="Files">
                                📎 {counts.files_count}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-3.5 px-3">
                          <div className="space-y-1 max-w-xs">
                            {cand.protection_reasons && cand.protection_reasons.length > 0 ? (
                              <div className="flex flex-wrap gap-1">
                                {cand.protection_reasons.map((pr, idx) => (
                                  <span
                                    key={idx}
                                    className="px-1.5 py-0.5 bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 rounded text-[10px] font-medium leading-tight"
                                  >
                                    🛡️ {pr}
                                  </span>
                                ))}
                              </div>
                            ) : (
                              <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
                                No blocking dependencies
                              </span>
                            )}

                            {cand.flag_reasons && cand.flag_reasons.length > 0 && (
                              <div className="text-[10px] text-gray-400">
                                Signal: {cand.flag_reasons.join(', ')}
                              </div>
                            )}
                          </div>
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <button
                            onClick={() => toggleRowExpand(cand.company_id)}
                            className="inline-flex items-center gap-1 text-[11px] font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 cursor-pointer"
                          >
                            <span>{isExpanded ? 'Hide' : 'Inspect'}</span>
                            {isExpanded ? (
                              <ChevronDown className="w-3.5 h-3.5" />
                            ) : (
                              <ChevronRight className="w-3.5 h-3.5" />
                            )}
                          </button>
                        </td>
                      </tr>

                      {/* Expandable Breakdown Card */}
                      {isExpanded && (
                        <tr className="bg-gray-50/70 dark:bg-gray-800/50">
                          <td colSpan={7} className="p-4 border-t border-b border-gray-100 dark:border-gray-800">
                            <div className="space-y-3">
                              <h4 className="text-xs font-bold text-gray-900 dark:text-white flex items-center gap-1.5">
                                <Info className="w-3.5 h-3.5 text-indigo-500" />
                                <span>Detailed Dependency Breakdown for {cand.company_name}</span>
                              </h4>

                              <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-2.5 text-[11px]">
                                <div className="p-2 bg-white dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-700">
                                  <span className="text-gray-400 block">Job Postings:</span>
                                  <span className="font-semibold text-gray-800 dark:text-gray-200">{counts.jobs_count}</span>
                                </div>
                                <div className="p-2 bg-white dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-700">
                                  <span className="text-gray-400 block">Circulars:</span>
                                  <span className="font-semibold text-gray-800 dark:text-gray-200">{counts.circulars_count}</span>
                                </div>
                                <div className="p-2 bg-white dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-700">
                                  <span className="text-gray-400 block">Circular-Job Links:</span>
                                  <span className="font-semibold text-gray-800 dark:text-gray-200">{counts.circular_job_links_count}</span>
                                </div>
                                <div className="p-2 bg-white dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-700">
                                  <span className="text-gray-400 block">Applications:</span>
                                  <span className="font-semibold text-gray-800 dark:text-gray-200">{counts.applications_count}</span>
                                </div>
                                <div className="p-2 bg-white dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-700">
                                  <span className="text-gray-400 block">Shortlists:</span>
                                  <span className="font-semibold text-gray-800 dark:text-gray-200">{counts.shortlists_count}</span>
                                </div>
                                <div className="p-2 bg-white dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-700">
                                  <span className="text-gray-400 block">Recruitment Rounds:</span>
                                  <span className="font-semibold text-gray-800 dark:text-gray-200">{counts.rounds_count}</span>
                                </div>
                                <div className="p-2 bg-white dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-700">
                                  <span className="text-gray-400 block">Round Outcomes:</span>
                                  <span className="font-semibold text-gray-800 dark:text-gray-200">{counts.outcomes_count} (Confirmed: {counts.confirmed_outcomes_count})</span>
                                </div>
                                <div className="p-2 bg-white dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-700">
                                  <span className="text-gray-400 block">Result Batches:</span>
                                  <span className="font-semibold text-gray-800 dark:text-gray-200">{counts.result_batches_count}</span>
                                </div>
                                <div className="p-2 bg-white dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-700">
                                  <span className="text-gray-400 block">Result Items:</span>
                                  <span className="font-semibold text-gray-800 dark:text-gray-200">{counts.result_items_count} (Confirmed: {counts.confirmed_result_items_count})</span>
                                </div>
                                <div className="p-2 bg-white dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-700">
                                  <span className="text-gray-400 block">Placement Offers:</span>
                                  <span className="font-semibold text-gray-800 dark:text-gray-200">{counts.offers_count} (Accepted: {counts.accepted_offers_count})</span>
                                </div>
                                <div className="p-2 bg-white dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-700">
                                  <span className="text-gray-400 block">Attached Files:</span>
                                  <span className="font-semibold text-gray-800 dark:text-gray-200">{counts.files_count} (Shared Preserved: {counts.shared_files_count})</span>
                                </div>
                                <div className="p-2 bg-white dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-700">
                                  <span className="text-gray-400 block">Affected Students:</span>
                                  <span className="font-semibold text-gray-800 dark:text-gray-200">{cand.affected_student_count} unique student(s)</span>
                                </div>
                              </div>

                              {/* Warnings & Notes */}
                              <div className="space-y-1.5 pt-1 text-[11px]">
                                {counts.accepted_offers_count > 0 && (
                                  <div className="p-2 bg-red-100 dark:bg-red-950/60 border border-red-200 dark:border-red-800 rounded text-red-800 dark:text-red-200 font-medium">
                                    🔴 CRITICAL: Students have accepted verified offers through this company. Deletion is permanently blocked by institutional placement accounting rules.
                                  </div>
                                )}
                                {counts.active_offers_count > 0 && counts.accepted_offers_count === 0 && (
                                  <div className="p-2 bg-amber-100 dark:bg-amber-950/60 border border-amber-200 dark:border-amber-800 rounded text-amber-800 dark:text-amber-200 font-medium">
                                    🟠 Pending active verified placement offers exist for this company.
                                  </div>
                                )}
                                {counts.confirmed_outcomes_count > 0 && (
                                  <div className="p-2 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded text-amber-800 dark:text-amber-200">
                                    🟠 Confirmed round progression outcomes exist. Archiving preserves this recruitment history.
                                  </div>
                                )}
                                {counts.shared_files_count > 0 && (
                                  <div className="p-2 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded text-blue-800 dark:text-blue-200">
                                    ℹ️ {counts.shared_files_count} file(s) are shared with academic circulars or other records and will be preserved even if this recruitment record is purged.
                                  </div>
                                )}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Execution Result Modal */}
      {cleanupResult && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-lg w-full p-6 border border-gray-200 dark:border-gray-800 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-emerald-100 dark:bg-emerald-950/80 text-emerald-600 dark:text-emerald-400 rounded-xl">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                  Cleanup Execution Succeeded
                </h3>
                <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider font-semibold">
                  Mode: {cleanupResult.mode}
                </p>
              </div>
            </div>

            <div className="p-3.5 bg-gray-50 dark:bg-gray-800/60 rounded-xl text-xs space-y-2">
              <p className="text-gray-800 dark:text-gray-200 font-medium">
                {cleanupResult.message}
              </p>
              <div className="pt-2 border-t border-gray-200 dark:border-gray-700 grid grid-cols-2 gap-2 text-[11px]">
                <div>
                  <span className="text-gray-400">Processed Companies:</span>{' '}
                  <strong className="text-gray-900 dark:text-white">{cleanupResult.companies_processed}</strong>
                </div>
                <div>
                  <span className="text-gray-400">Company IDs:</span>{' '}
                  <strong className="text-gray-900 dark:text-white">{cleanupResult.company_ids?.join(', ')}</strong>
                </div>
                {cleanupResult.audit_log_id && (
                  <div className="col-span-2">
                    <span className="text-gray-400">Audit Log Recorded:</span>{' '}
                    <strong className="text-emerald-600 dark:text-emerald-400">Log #{cleanupResult.audit_log_id}</strong>
                  </div>
                )}
              </div>
            </div>

            {/* Affected Records Detail */}
            {cleanupResult.records_affected && Object.keys(cleanupResult.records_affected).length > 0 && (
              <div className="space-y-1.5">
                <span className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                  Actual Records Affected:
                </span>
                <div className="grid grid-cols-2 gap-1.5 text-[11px] max-h-36 overflow-y-auto">
                  {Object.entries(cleanupResult.records_affected).map(([key, val]) => (
                    <div
                      key={key}
                      className="p-1.5 bg-gray-100 dark:bg-gray-800 rounded flex justify-between items-center"
                    >
                      <span className="text-gray-500 dark:text-gray-400 capitalize">
                        {key.replace(/_/g, ' ')}:
                      </span>
                      <span className="font-bold text-gray-900 dark:text-white">{val}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex justify-end pt-2">
              <button
                onClick={clearCleanupResult}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Archive Confirmation Modal */}
      {archiveModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-lg w-full p-6 border border-gray-200 dark:border-gray-800 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-amber-100 dark:bg-amber-950/80 text-amber-600 dark:text-amber-400 rounded-xl">
                <Archive className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                  Confirm Company Archival
                </h3>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Safe Deactivation & Record Closure
                </p>
              </div>
            </div>

            <div className="text-xs text-gray-600 dark:text-gray-300 space-y-2">
              <p>
                You are about to archive <strong>{selectedIds.length}</strong> selected candidate company(ies):
              </p>
              <div className="max-h-28 overflow-y-auto p-2.5 bg-gray-50 dark:bg-gray-800 rounded-lg space-y-1">
                {selectedCompanies.map((c) => (
                  <div key={c.company_id} className="flex justify-between items-center text-[11px]">
                    <span className="font-semibold text-gray-900 dark:text-white">{c.company_name}</span>
                    <span className="text-gray-400">ID #{c.company_id}</span>
                  </div>
                ))}
              </div>
              <div className="p-3 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded-lg text-[11px] text-blue-800 dark:text-blue-300 space-y-1">
                <p className="font-semibold">⚡ Archive Operations:</p>
                <ul className="list-disc pl-4 space-y-0.5">
                  <li>Deactivates company records in the catalog.</li>
                  <li>Closes all open job postings under these companies.</li>
                  <li>Archives related recruitment circulars and result batches.</li>
                  <li>Preserves student application records, verified offers, and historical placement evidence.</li>
                </ul>
              </div>
            </div>

            {actionError && (
              <div className="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-lg text-xs text-red-700 dark:text-red-300">
                {actionError}
              </div>
            )}

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setArchiveModalOpen(false)}
                disabled={isCleanupLoading}
                className="px-4 py-2 text-xs font-semibold text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmArchive}
                disabled={isCleanupLoading}
                className="px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors cursor-pointer disabled:opacity-50 flex items-center gap-1.5"
              >
                {isCleanupLoading ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Archiving...</span>
                  </>
                ) : (
                  <span>Confirm & Archive</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Destructive Purge Confirmation Modal */}
      {purgeModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-lg w-full p-6 border border-red-200 dark:border-red-800 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-red-100 dark:bg-red-950/80 text-red-600 dark:text-red-400 rounded-xl">
                <Trash2 className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                  Permanently Purge Test Records
                </h3>
                <p className="text-xs text-red-600 dark:text-red-400 font-semibold">
                  DESTRUCTIVE & IRREVERSIBLE OPERATION
                </p>
              </div>
            </div>

            <div className="text-xs text-gray-600 dark:text-gray-300 space-y-2">
              <p>
                You are requesting permanent deletion for <strong>{selectedIds.length}</strong> company(ies) and all their associated test records:
              </p>
              <div className="max-h-28 overflow-y-auto p-2.5 bg-gray-50 dark:bg-gray-800 rounded-lg space-y-1">
                {selectedCompanies.map((c) => (
                  <div key={c.company_id} className="flex justify-between items-center text-[11px]">
                    <span className="font-semibold text-gray-900 dark:text-white">{c.company_name}</span>
                    <span className="text-emerald-600 dark:text-emerald-400 font-medium">Safe to Purge</span>
                  </div>
                ))}
              </div>

              <div className="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-lg text-[11px] text-red-800 dark:text-red-300 space-y-1">
                <p className="font-semibold">⚠️ Permanent Data Loss Warning:</p>
                <ul className="list-disc pl-4 space-y-0.5">
                  <li>Company records, job postings, circulars, and test applications will be permanently deleted.</li>
                  <li>Unshared recruitment attachment files will be deleted from object storage.</li>
                  <li>Shared documents (e.g. general institutional circulars) will be automatically preserved.</li>
                  <li>This action cannot be undone.</li>
                </ul>
              </div>

              <div className="space-y-1.5 pt-1">
                <label className="block text-xs font-semibold text-gray-900 dark:text-white">
                  Type <span className="font-mono bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-300 px-1 py-0.5 rounded">{CONFIRMATION_PHRASE}</span> to confirm:
                </label>
                <input
                  type="text"
                  value={confirmationInput}
                  onChange={(e) => setConfirmationInput(e.target.value)}
                  placeholder={CONFIRMATION_PHRASE}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-800 border border-red-300 dark:border-red-700 rounded-lg text-xs font-mono focus:outline-none focus:ring-2 focus:ring-red-500 dark:text-white"
                />
              </div>
            </div>

            {actionError && (
              <div className="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-lg text-xs text-red-700 dark:text-red-300">
                {actionError}
              </div>
            )}

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setPurgeModalOpen(false)}
                disabled={isCleanupLoading}
                className="px-4 py-2 text-xs font-semibold text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmPurge}
                disabled={
                  isCleanupLoading ||
                  confirmationInput.trim() !== CONFIRMATION_PHRASE ||
                  selectedIds.length === 0
                }
                className="px-5 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
              >
                {isCleanupLoading ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Purging...</span>
                  </>
                ) : (
                  <span>Permanently Purge Records</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ManageTestData;
