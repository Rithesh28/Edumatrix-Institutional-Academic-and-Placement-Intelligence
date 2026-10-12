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
  ChevronUp,
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
  Layers,
  Calendar,
  ExternalLink,
  Clock,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import { useAuthStore } from '../../store/authStore';
import toast from 'react-hot-toast';
import BulkDriveCleanupModal from './BulkDriveCleanupModal';

const CONFIRMATION_PHRASE = 'CONFIRM_PURGE_TEST_DATA';

const ManageTestData = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const {
    cleanupPreview,
    drivesCleanupPreview,
    isCleanupLoading,
    cleanupError,
    cleanupResult,
    fetchCleanupPreview,
    fetchDrivesCleanupPreview,
    runCleanup,
    clearCleanupResult,
    fetchCirculars,
  } = usePlacementStore();

  const isPrivileged =
    user?.role === 'placement_officer' ||
    user?.role === 'placement' ||
    user?.role === 'admin';

  // Active Scope Tab: 'companies' | 'drives'
  const [activeTab, setActiveTab] = useState('companies');

  // Company Cleanup State
  const [searchTerm, setSearchTerm] = useState('');
  const [safetyFilter, setSafetyFilter] = useState('all');
  const [selectedIds, setSelectedIds] = useState([]);
  const [expandedRowIds, setExpandedRowIds] = useState(new Set());
  const [archiveModalOpen, setArchiveModalOpen] = useState(false);
  const [purgeModalOpen, setPurgeModalOpen] = useState(false);
  const [confirmationInput, setConfirmationInput] = useState('');
  const [actionError, setActionError] = useState(null);

  // Drive Cleanup State
  const [drivesSearchTerm, setDrivesSearchTerm] = useState('');
  const [drivesSafetyFilter, setDrivesSafetyFilter] = useState('all');
  const [drivesStatusFilter, setDrivesStatusFilter] = useState('all');
  const [selectedDriveIds, setSelectedDriveIds] = useState([]);
  const [expandedDriveRowIds, setExpandedDriveRowIds] = useState(new Set());
  const [driveModalOpen, setDriveModalOpen] = useState(false);
  const [driveModalSelection, setDriveModalSelection] = useState([]);
  const [selectedOrphanedJobIds, setSelectedOrphanedJobIds] = useState([]);
  const [orphanPurgeConfirmOpen, setOrphanPurgeConfirmOpen] = useState(false);
  const [orphanConfirmInput, setOrphanConfirmInput] = useState('');

  // Initial load
  useEffect(() => {
    if (isPrivileged) {
      loadPreview();
    }
  }, [isPrivileged]);

  const loadPreview = async () => {
    try {
      setActionError(null);
      await Promise.allSettled([
        fetchCleanupPreview({ include_all_candidates: true }),
        fetchDrivesCleanupPreview({ include_all_candidates: true }),
      ]);
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to load cleanup preview';
      setActionError(msg);
      toast.error(msg);
    }
  };

  // Company Data & Filters
  const candidates = cleanupPreview?.candidates || [];
  const companySummary = cleanupPreview?.summary || {
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

  // Drive Data & Filters
  const drives = drivesCleanupPreview?.drives || [];
  const orphanedJobs = drivesCleanupPreview?.orphaned_jobs || [];
  const driveSummary = drivesCleanupPreview?.summary || {
    total_candidates_flagged: 0,
    total_drives_flagged: 0,
    total_drives_safe_to_purge: 0,
    total_drives_requires_archive: 0,
    total_drives_protected_genuine: 0,
    total_orphaned_jobs: 0,
    total_dependent_jobs: 0,
    total_dependent_circulars: 0,
    total_dependent_applications: 0,
    total_dependent_result_batches: 0,
    total_dependent_offers: 0,
    total_dependent_accepted_offers: 0,
    total_files_identified: 0,
    total_shared_files_preserved: 0,
  };

  const filteredDrives = useMemo(() => {
    return drives.filter((item) => {
      const matchesSearch =
        !drivesSearchTerm ||
        item.title?.toLowerCase().includes(drivesSearchTerm.toLowerCase()) ||
        item.company_name?.toLowerCase().includes(drivesSearchTerm.toLowerCase()) ||
        String(item.circular_id).includes(drivesSearchTerm);

      const matchesSafety =
        drivesSafetyFilter === 'all' || item.safety_classification === drivesSafetyFilter;

      const matchesStatus =
        drivesStatusFilter === 'all' || item.status?.toLowerCase() === drivesStatusFilter.toLowerCase();

      return matchesSearch && matchesSafety && matchesStatus;
    });
  }, [drives, drivesSearchTerm, drivesSafetyFilter, drivesStatusFilter]);

  const selectedDrives = useMemo(() => {
    return drives.filter((d) => selectedDriveIds.includes(d.circular_id));
  }, [drives, selectedDriveIds]);

  const selectedDriveSafetyBreakdown = useMemo(() => {
    const safe = selectedDrives.filter((d) => d.safety_classification === 'SAFE_TO_PURGE').length;
    const requiresArchive = selectedDrives.filter((d) => d.safety_classification === 'REQUIRES_ARCHIVE').length;
    const protectedCount = selectedDrives.filter((d) => d.safety_classification === 'PROTECTED_GENUINE').length;
    return { safe, requiresArchive, protectedCount };
  }, [selectedDrives]);

  // Company Selection Handlers
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

  // Drive Selection Handlers
  const handleToggleSelectDrive = (id) => {
    setSelectedDriveIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleSelectAllVisibleDrives = () => {
    const visibleIds = filteredDrives.map((d) => d.circular_id);
    const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedDriveIds.includes(id));
    if (allSelected) {
      setSelectedDriveIds((prev) => prev.filter((id) => !visibleIds.includes(id)));
    } else {
      setSelectedDriveIds((prev) => Array.from(new Set([...prev, ...visibleIds])));
    }
  };

  const handleSelectSafeDrivesOnly = () => {
    const safeIds = filteredDrives
      .filter((d) => d.safety_classification === 'SAFE_TO_PURGE')
      .map((d) => d.circular_id);
    setSelectedDriveIds(safeIds);
  };

  const toggleDriveRowExpand = (id) => {
    setExpandedDriveRowIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleOpenDriveModal = (circularIds) => {
    if (!circularIds || circularIds.length === 0) {
      toast.error('Select at least one recruitment drive to inspect.');
      return;
    }
    setDriveModalSelection(circularIds);
    setDriveModalOpen(true);
  };

  // Company Execution Handlers
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

  // Orphaned Roles Cleanup Handlers
  const handleToggleSelectOrphan = (id) => {
    setSelectedOrphanedJobIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleConfirmOrphanPurge = async () => {
    if (orphanConfirmInput.trim() !== CONFIRMATION_PHRASE) {
      setActionError(`Confirmation phrase must match "${CONFIRMATION_PHRASE}" exactly.`);
      return;
    }
    setActionError(null);
    try {
      const payload = {
        orphaned_job_ids: selectedOrphanedJobIds,
        mode: 'purge',
        confirmation_phrase: CONFIRMATION_PHRASE,
      };
      await runCleanup(payload);
      toast.success(`Successfully purged ${selectedOrphanedJobIds.length} orphaned test role(s).`);
      setOrphanPurgeConfirmOpen(false);
      setSelectedOrphanedJobIds([]);
      setOrphanConfirmInput('');
      await loadPreview();
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Orphaned role purge failed.';
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

  const getStatusBadge = (status) => {
    const s = (status || '').toLowerCase();
    switch (s) {
      case 'published':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
            Published
          </span>
        );
      case 'draft':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
            Draft
          </span>
        );
      case 'archived':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
            Archived
          </span>
        );
      case 'closed':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
            Closed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400">
            {status}
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
            Safe, preview-first administrative interface to inspect test candidate companies and recruitment drives, and execute archive or purge actions.
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

      {/* Scope Switcher Tabs */}
      <div className="flex border-b border-gray-200 dark:border-gray-800">
        <button
          type="button"
          onClick={() => setActiveTab('companies')}
          className={`flex items-center gap-2 py-3 px-5 text-sm font-semibold border-b-2 transition-all cursor-pointer ${
            activeTab === 'companies'
              ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400 bg-indigo-50/40 dark:bg-indigo-950/20 rounded-t-lg'
              : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
          }`}
        >
          <Building2 className="w-4 h-4" />
          <span>Candidate Companies</span>
          <span className={`text-xs px-2 py-0.5 rounded-full ${
            activeTab === 'companies'
              ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/60 dark:text-indigo-300 font-bold'
              : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
          }`}>
            {candidates.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('drives')}
          className={`flex items-center gap-2 py-3 px-5 text-sm font-semibold border-b-2 transition-all cursor-pointer ${
            activeTab === 'drives'
              ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400 bg-indigo-50/40 dark:bg-indigo-950/20 rounded-t-lg'
              : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>Recruitment Drives</span>
          <span className={`text-xs px-2 py-0.5 rounded-full ${
            activeTab === 'drives'
              ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/60 dark:text-indigo-300 font-bold'
              : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
          }`}>
            {drives.length}
          </span>
        </button>
      </div>

      {/* Mandatory Safety Notice Banner */}
      <div className="p-4 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-xl flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
        <div className="text-xs text-amber-800 dark:text-amber-200 space-y-1">
          <p className="font-semibold text-sm text-amber-900 dark:text-amber-100">
            Administrative Review Aid — Verification Required
          </p>
          <p>
            The test-pattern detector flags candidates using automated naming signals (e.g., timestamps, "test", "mock", "temp").
            <strong> A test-like name is an evaluation signal only, never an authorization to delete records.</strong>
          </p>
          <p className="text-amber-700 dark:text-amber-300">
            The backend strictly validates safety classifications in real time. Genuine student applications, confirmed progression outcomes, accepted offers, and shared files are protected from permanent deletion.
          </p>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: CANDIDATE COMPANIES                                               */}
      {/* ========================================================================= */}
      {activeTab === 'companies' && (
        <div className="space-y-6">
          {/* Aggregate Preview Metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            <div className="bg-white dark:bg-gray-900 p-3.5 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
              <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider block">
                Flagged Candidates
              </span>
              <p className="text-xl font-bold text-gray-900 dark:text-white mt-1">
                {companySummary.total_candidates_flagged}
              </p>
            </div>
            <div className="bg-white dark:bg-gray-900 p-3.5 rounded-xl border border-emerald-200 dark:border-emerald-800/60 shadow-sm">
              <span className="text-[11px] font-medium text-emerald-600 dark:text-emerald-400 uppercase tracking-wider block">
                Safe to Purge
              </span>
              <p className="text-xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
                {companySummary.total_safe_to_purge}
              </p>
            </div>
            <div className="bg-white dark:bg-gray-900 p-3.5 rounded-xl border border-amber-200 dark:border-amber-800/60 shadow-sm">
              <span className="text-[11px] font-medium text-amber-600 dark:text-amber-400 uppercase tracking-wider block">
                Requires Archive
              </span>
              <p className="text-xl font-bold text-amber-600 dark:text-amber-400 mt-1">
                {companySummary.total_requires_archive}
              </p>
            </div>
            <div className="bg-white dark:bg-gray-900 p-3.5 rounded-xl border border-red-200 dark:border-red-800/60 shadow-sm">
              <span className="text-[11px] font-medium text-red-600 dark:text-red-400 uppercase tracking-wider block">
                Protected Genuine
              </span>
              <p className="text-xl font-bold text-red-600 dark:text-red-400 mt-1">
                {companySummary.total_protected_genuine}
              </p>
            </div>
            <div className="bg-white dark:bg-gray-900 p-3.5 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
              <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider block">
                Dependent Jobs
              </span>
              <p className="text-xl font-bold text-gray-700 dark:text-gray-300 mt-1">
                {companySummary.total_dependent_jobs}
              </p>
            </div>
            <div className="bg-white dark:bg-gray-900 p-3.5 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
              <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider block">
                Dependent Drives
              </span>
              <p className="text-xl font-bold text-gray-700 dark:text-gray-300 mt-1">
                {companySummary.total_dependent_circulars}
              </p>
            </div>
            <div className="bg-white dark:bg-gray-900 p-3.5 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm col-span-2 sm:col-span-1">
              <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider block">
                Shared Files Preserved
              </span>
              <p className="text-xl font-bold text-blue-600 dark:text-blue-400 mt-1">
                {companySummary.total_shared_files_preserved}
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
                          className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                        />
                      </th>
                      <th className="py-3 px-4">Company</th>
                      <th className="py-3 px-4">Safety Status</th>
                      <th className="py-3 px-4">Dependencies Summary</th>
                      <th className="py-3 px-4">Protection Notes</th>
                      <th className="py-3 px-4 text-right">Details</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                    {filteredCandidates.map((candidate) => {
                      const isSelected = selectedIds.includes(candidate.company_id);
                      const isExpanded = expandedRowIds.has(candidate.company_id);
                      const dep = candidate.dependent_counts;

                      return (
                        <React.Fragment key={candidate.company_id}>
                          <tr
                            className={`hover:bg-gray-50/70 dark:hover:bg-gray-800/50 transition-colors ${
                              isSelected ? 'bg-indigo-50/40 dark:bg-indigo-950/20' : ''
                            }`}
                          >
                            <td className="py-3 px-4">
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={() => handleToggleSelect(candidate.company_id)}
                                className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                              />
                            </td>
                            <td className="py-3 px-4">
                              <div className="font-semibold text-gray-900 dark:text-white flex items-center gap-1.5">
                                <Building2 className="w-3.5 h-3.5 text-gray-400" />
                                <span>{candidate.company_name}</span>
                              </div>
                              <div className="text-[11px] text-gray-400 mt-0.5">
                                ID #{candidate.company_id} • Created {new Date(candidate.created_at).toLocaleDateString()}
                              </div>
                            </td>
                            <td className="py-3 px-4">
                              {getSafetyBadge(candidate.safety_classification)}
                            </td>
                            <td className="py-3 px-4">
                              <div className="flex flex-wrap gap-1.5 text-[11px]">
                                <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded font-medium text-gray-700 dark:text-gray-300" title="Job Postings">
                                  {dep.jobs_count} Jobs
                                </span>
                                <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded font-medium text-gray-700 dark:text-gray-300" title="Recruitment Circulars">
                                  {dep.circulars_count} Circulars
                                </span>
                                <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded font-medium text-gray-700 dark:text-gray-300" title="Student Applications">
                                  {dep.applications_count} Apps
                                </span>
                                {dep.offers_count > 0 && (
                                  <span className="px-2 py-0.5 bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300 rounded font-medium" title="Offers">
                                    {dep.offers_count} Offers ({dep.accepted_offers_count} Accepted)
                                  </span>
                                )}
                              </div>
                            </td>
                            <td className="py-3 px-4 max-w-xs">
                              {candidate.protection_reasons.length > 0 ? (
                                <p className="text-[11px] text-amber-700 dark:text-amber-400 line-clamp-1" title={candidate.protection_reasons.join(', ')}>
                                  {candidate.protection_reasons[0]}
                                  {candidate.protection_reasons.length > 1 && ` (+${candidate.protection_reasons.length - 1} more)`}
                                </p>
                              ) : (
                                <span className="text-[11px] text-emerald-600 dark:text-emerald-400">
                                  Pure test candidate, eligible for purge
                                </span>
                              )}
                            </td>
                            <td className="py-3 px-4 text-right">
                              <button
                                onClick={() => toggleRowExpand(candidate.company_id)}
                                className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded cursor-pointer"
                                title="Expand dependency details"
                              >
                                {isExpanded ? (
                                  <ChevronUp className="w-4 h-4" />
                                ) : (
                                  <ChevronDown className="w-4 h-4" />
                                )}
                              </button>
                            </td>
                          </tr>

                          {/* Expanded Dependency Inspection Row */}
                          {isExpanded && (
                            <tr className="bg-gray-50/60 dark:bg-gray-800/40">
                              <td colSpan={6} className="py-4 px-6 space-y-3">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                  {/* Candidate Flag Signals */}
                                  <div className="space-y-1.5">
                                    <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 block">
                                      Detection Signals
                                    </span>
                                    <ul className="list-disc pl-4 text-xs text-gray-600 dark:text-gray-300 space-y-0.5">
                                      {candidate.candidate_reasons.map((r, idx) => (
                                        <li key={idx}>{r}</li>
                                      ))}
                                    </ul>
                                  </div>

                                  {/* Detailed Protection Reasons */}
                                  <div className="space-y-1.5">
                                    <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 block">
                                      Safety Verification & Protection Rules
                                    </span>
                                    {candidate.protection_reasons.length > 0 ? (
                                      <ul className="list-disc pl-4 text-xs text-amber-700 dark:text-amber-400 space-y-0.5">
                                        {candidate.protection_reasons.map((r, idx) => (
                                          <li key={idx}>{r}</li>
                                        ))}
                                      </ul>
                                    ) : (
                                      <p className="text-xs text-emerald-600 dark:text-emerald-400">
                                        No genuine student records or accepted offers linked. Safe for permanent purge.
                                      </p>
                                    )}
                                  </div>
                                </div>

                                {/* Files & Shared Preservations */}
                                {dep.files_count > 0 && (
                                  <div className="pt-2 border-t border-gray-200 dark:border-gray-700 text-xs text-gray-600 dark:text-gray-300 flex items-center gap-4">
                                    <span className="flex items-center gap-1">
                                      <Paperclip className="w-3.5 h-3.5 text-gray-400" />
                                      {dep.files_count} total file references
                                    </span>
                                    {dep.shared_files_count > 0 && (
                                      <span className="text-blue-600 dark:text-blue-400 font-medium">
                                        🛡️ {dep.shared_files_count} shared files will be preserved
                                      </span>
                                    )}
                                  </div>
                                )}
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
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: RECRUITMENT DRIVES                                                */}
      {/* ========================================================================= */}
      {activeTab === 'drives' && (
        <div className="space-y-6">
          {/* Drives Aggregate Preview Metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            <div className="bg-white dark:bg-gray-900 p-3.5 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
              <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider block">
                Flagged Drives
              </span>
              <p className="text-xl font-bold text-gray-900 dark:text-white mt-1">
                {driveSummary.total_drives_flagged || drives.length}
              </p>
            </div>
            <div className="bg-white dark:bg-gray-900 p-3.5 rounded-xl border border-emerald-200 dark:border-emerald-800/60 shadow-sm">
              <span className="text-[11px] font-medium text-emerald-600 dark:text-emerald-400 uppercase tracking-wider block">
                Safe to Purge
              </span>
              <p className="text-xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
                {driveSummary.total_drives_safe_to_purge}
              </p>
            </div>
            <div className="bg-white dark:bg-gray-900 p-3.5 rounded-xl border border-amber-200 dark:border-amber-800/60 shadow-sm">
              <span className="text-[11px] font-medium text-amber-600 dark:text-amber-400 uppercase tracking-wider block">
                Requires Archive
              </span>
              <p className="text-xl font-bold text-amber-600 dark:text-amber-400 mt-1">
                {driveSummary.total_drives_requires_archive}
              </p>
            </div>
            <div className="bg-white dark:bg-gray-900 p-3.5 rounded-xl border border-red-200 dark:border-red-800/60 shadow-sm">
              <span className="text-[11px] font-medium text-red-600 dark:text-red-400 uppercase tracking-wider block">
                Protected Genuine
              </span>
              <p className="text-xl font-bold text-red-600 dark:text-red-400 mt-1">
                {driveSummary.total_drives_protected_genuine}
              </p>
            </div>
            <div className="bg-white dark:bg-gray-900 p-3.5 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
              <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider block">
                Dependent Roles
              </span>
              <p className="text-xl font-bold text-gray-700 dark:text-gray-300 mt-1">
                {driveSummary.total_dependent_jobs}
              </p>
            </div>
            <div className="bg-white dark:bg-gray-900 p-3.5 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
              <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider block">
                Dependent Apps
              </span>
              <p className="text-xl font-bold text-gray-700 dark:text-gray-300 mt-1">
                {driveSummary.total_dependent_applications}
              </p>
            </div>
            <div className="bg-white dark:bg-gray-900 p-3.5 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm col-span-2 sm:col-span-1">
              <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider block">
                Orphaned Roles
              </span>
              <p className="text-xl font-bold text-indigo-600 dark:text-indigo-400 mt-1">
                {driveSummary.total_orphaned_jobs || orphanedJobs.length}
              </p>
            </div>
          </div>

          {/* Action Toolbar */}
          <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm space-y-3">
            <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <span className="text-xs font-medium text-gray-700 dark:text-gray-300">
                  Selected: <strong className="text-indigo-600 dark:text-indigo-400">{selectedDriveIds.length}</strong> of {drives.length} drives
                </span>
                {selectedDriveIds.length > 0 && (
                  <div className="flex items-center gap-1.5 text-[11px] text-gray-500 dark:text-gray-400">
                    <span>(Safe: {selectedDriveSafetyBreakdown.safe},</span>
                    <span>Archive: {selectedDriveSafetyBreakdown.requiresArchive},</span>
                    <span>Protected: {selectedDriveSafetyBreakdown.protectedCount})</span>
                    <button
                      onClick={() => setSelectedDriveIds([])}
                      className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline ml-1 cursor-pointer"
                    >
                      Clear Selection
                    </button>
                  </div>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={handleSelectSafeDrivesOnly}
                  className="px-3 py-1.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:hover:bg-emerald-900/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                >
                  Select Safe to Purge ({driveSummary.total_drives_safe_to_purge})
                </button>

                <button
                  onClick={() => handleOpenDriveModal(selectedDriveIds)}
                  disabled={selectedDriveIds.length === 0}
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Layers className="w-3.5 h-3.5" />
                  <span>Preview & Clean Up ({selectedDriveIds.length})</span>
                </button>
              </div>
            </div>
          </div>

          {/* Search, Status and Safety Filters */}
          <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between bg-white dark:bg-gray-900 p-3.5 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search drive title, company, or ID..."
                value={drivesSearchTerm}
                onChange={(e) => setDrivesSearchTerm(e.target.value)}
                className="w-full pl-9 pr-4 py-1.5 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:text-white"
              />
            </div>

            <div className="flex items-center gap-2 overflow-x-auto">
              {/* Status Filter */}
              <select
                value={drivesStatusFilter}
                onChange={(e) => setDrivesStatusFilter(e.target.value)}
                className="px-2.5 py-1.5 bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-xs font-medium text-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="all">All Statuses</option>
                <option value="draft">Draft</option>
                <option value="published">Published</option>
                <option value="archived">Archived</option>
                <option value="closed">Closed</option>
              </select>

              {/* Safety Filter Tabs */}
              {[
                { id: 'all', label: 'All Safety' },
                { id: 'SAFE_TO_PURGE', label: 'Safe to Purge' },
                { id: 'REQUIRES_ARCHIVE', label: 'Requires Archive' },
                { id: 'PROTECTED_GENUINE', label: 'Protected Genuine' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setDrivesSafetyFilter(tab.id)}
                  className={`px-2.5 py-1.5 text-xs font-medium rounded-lg transition-colors cursor-pointer whitespace-nowrap ${
                    drivesSafetyFilter === tab.id
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Candidate Drives Table */}
          {isCleanupLoading && drives.length === 0 ? (
            <div className="p-12 text-center text-gray-500 dark:text-gray-400 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
              <div className="animate-spin w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full mx-auto mb-3" />
              <p className="text-sm">Evaluating recruitment drive cleanup candidates...</p>
            </div>
          ) : filteredDrives.length === 0 ? (
            <div className="p-12 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 text-center space-y-2">
              <Layers className="w-10 h-10 text-gray-400 mx-auto" />
              <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                No recruitment drive candidates found
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {drivesSearchTerm || drivesSafetyFilter !== 'all' || drivesStatusFilter !== 'all'
                  ? 'Try adjusting your search query or filter criteria.'
                  : 'No test-generated or flagged recruitment drives found.'}
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
                            filteredDrives.length > 0 &&
                            filteredDrives.every((d) => selectedDriveIds.includes(d.circular_id))
                          }
                          onChange={handleSelectAllVisibleDrives}
                          className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                        />
                      </th>
                      <th className="py-3 px-4">Recruitment Drive</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Safety Status</th>
                      <th className="py-3 px-4">Dependencies</th>
                      <th className="py-3 px-4">Protection Notes</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                    {filteredDrives.map((drive) => {
                      const isSelected = selectedDriveIds.includes(drive.circular_id);
                      const isExpanded = expandedDriveRowIds.has(drive.circular_id);
                      const dep = drive.dependent_counts;

                      return (
                        <React.Fragment key={drive.circular_id}>
                          <tr
                            className={`hover:bg-gray-50/70 dark:hover:bg-gray-800/50 transition-colors ${
                              isSelected ? 'bg-indigo-50/40 dark:bg-indigo-950/20' : ''
                            }`}
                          >
                            <td className="py-3 px-4">
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={() => handleToggleSelectDrive(drive.circular_id)}
                                className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                              />
                            </td>
                            <td className="py-3 px-4">
                              <div className="font-semibold text-gray-900 dark:text-white flex items-center gap-1.5">
                                <FileText className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                                <span>{drive.title}</span>
                              </div>
                              <div className="text-[11px] text-gray-400 mt-0.5 flex items-center gap-2">
                                <span className="flex items-center gap-1">
                                  <Building2 className="w-3 h-3" />
                                  {drive.company_name}
                                </span>
                                <span>• ID #{drive.circular_id}</span>
                                {drive.drive_date && (
                                  <span>• Drive: {new Date(drive.drive_date).toLocaleDateString()}</span>
                                )}
                              </div>
                            </td>
                            <td className="py-3 px-4">
                              {getStatusBadge(drive.status)}
                            </td>
                            <td className="py-3 px-4">
                              {getSafetyBadge(drive.safety_classification)}
                            </td>
                            <td className="py-3 px-4">
                              <div className="flex flex-wrap gap-1.5 text-[11px]">
                                <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded font-medium text-gray-700 dark:text-gray-300" title="Linked Roles">
                                  {dep.jobs_count} Roles
                                </span>
                                <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded font-medium text-gray-700 dark:text-gray-300" title="Applications">
                                  {dep.applications_count} Apps
                                </span>
                                {dep.offers_count > 0 && (
                                  <span className="px-2 py-0.5 bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300 rounded font-medium" title="Offers">
                                    {dep.offers_count} Offers
                                  </span>
                                )}
                                {dep.attachments_count > 0 && (
                                  <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded font-medium text-gray-700 dark:text-gray-300" title="Attachments">
                                    {dep.attachments_count} Files
                                  </span>
                                )}
                              </div>
                            </td>
                            <td className="py-3 px-4 max-w-xs">
                              {drive.protection_reasons.length > 0 ? (
                                <p className="text-[11px] text-amber-700 dark:text-amber-400 line-clamp-1" title={drive.protection_reasons.join(', ')}>
                                  {drive.protection_reasons[0]}
                                  {drive.protection_reasons.length > 1 && ` (+${drive.protection_reasons.length - 1} more)`}
                                </p>
                              ) : (
                                <span className="text-[11px] text-emerald-600 dark:text-emerald-400">
                                  Disposable test drive, safe to purge
                                </span>
                              )}
                            </td>
                            <td className="py-3 px-4 text-right">
                              <div className="flex items-center justify-end gap-1.5">
                                <button
                                  onClick={() => handleOpenDriveModal([drive.circular_id])}
                                  className="px-2.5 py-1 text-xs font-semibold text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300 hover:bg-indigo-50 dark:hover:bg-indigo-950/50 rounded transition-colors cursor-pointer"
                                  title="Inspect and clean up this drive"
                                >
                                  Inspect
                                </button>
                                <button
                                  onClick={() => toggleDriveRowExpand(drive.circular_id)}
                                  className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded cursor-pointer"
                                  title="Toggle details"
                                >
                                  {isExpanded ? (
                                    <ChevronUp className="w-4 h-4" />
                                  ) : (
                                    <ChevronDown className="w-4 h-4" />
                                  )}
                                </button>
                              </div>
                            </td>
                          </tr>

                          {/* Expanded Drive Details Row */}
                          {isExpanded && (
                            <tr className="bg-gray-50/60 dark:bg-gray-800/40">
                              <td colSpan={7} className="py-4 px-6 space-y-3">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                  {/* Flagging Signals */}
                                  <div className="space-y-1.5">
                                    <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 block">
                                      Candidate Detection Signals
                                    </span>
                                    <ul className="list-disc pl-4 text-xs text-gray-600 dark:text-gray-300 space-y-0.5">
                                      {drive.candidate_reasons.map((r, idx) => (
                                        <li key={idx}>{r}</li>
                                      ))}
                                    </ul>
                                  </div>

                                  {/* Protection Rules */}
                                  <div className="space-y-1.5">
                                    <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 block">
                                      Safety Verification & Protection Rules
                                    </span>
                                    {drive.protection_reasons.length > 0 ? (
                                      <ul className="list-disc pl-4 text-xs text-amber-700 dark:text-amber-400 space-y-0.5">
                                        {drive.protection_reasons.map((r, idx) => (
                                          <li key={idx}>{r}</li>
                                        ))}
                                      </ul>
                                    ) : (
                                      <p className="text-xs text-emerald-600 dark:text-emerald-400">
                                        Pure test recruitment drive. No accepted offers or genuine student dependencies.
                                      </p>
                                    )}
                                  </div>
                                </div>

                                {/* Linked Roles Breakdown */}
                                {(drive.exclusive_job_roles?.length > 0 || drive.shared_job_roles?.length > 0) && (
                                  <div className="pt-2 border-t border-gray-200 dark:border-gray-700 text-xs space-y-1.5">
                                    <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 block">
                                      Linked Roles Analysis
                                    </span>
                                    <div className="flex flex-wrap gap-2">
                                      {drive.exclusive_job_roles?.map((role, idx) => (
                                        <span key={idx} className="px-2 py-0.5 bg-emerald-50 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 rounded border border-emerald-200 dark:border-emerald-800 text-[11px]" title="Role exclusive to this drive (will be deleted on purge)">
                                          Exclusive: {role}
                                        </span>
                                      ))}
                                      {drive.shared_job_roles?.map((role, idx) => (
                                        <span key={idx} className="px-2 py-0.5 bg-blue-50 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300 rounded border border-blue-200 dark:border-blue-800 text-[11px]" title="Role shared with other drives (junction only will be unlinked)">
                                          Shared: {role} (Preserved)
                                        </span>
                                      ))}
                                    </div>
                                  </div>
                                )}

                                {/* Files Detail */}
                                {dep.files_count > 0 && (
                                  <div className="pt-2 border-t border-gray-200 dark:border-gray-700 text-xs text-gray-600 dark:text-gray-300 flex items-center gap-4">
                                    <span className="flex items-center gap-1">
                                      <Paperclip className="w-3.5 h-3.5 text-gray-400" />
                                      {dep.files_count} total file attachment(s)
                                    </span>
                                    {dep.shared_files_count > 0 && (
                                      <span className="text-blue-600 dark:text-blue-400 font-medium">
                                        🛡️ {dep.shared_files_count} shared file(s) preserved
                                      </span>
                                    )}
                                  </div>
                                )}
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

          {/* Orphaned Test Roles Section */}
          {orphanedJobs.length > 0 && (
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm overflow-hidden p-5 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 bg-indigo-100 dark:bg-indigo-950/80 text-indigo-600 dark:text-indigo-400 rounded-lg">
                    <Briefcase className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-gray-900 dark:text-white flex items-center gap-2">
                      <span>Orphaned Test Roles</span>
                      <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300">
                        {orphanedJobs.length}
                      </span>
                    </h3>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Job postings created for testing that are not linked to any recruitment circular.
                    </p>
                  </div>
                </div>

                {selectedOrphanedJobIds.length > 0 && (
                  <button
                    onClick={() => {
                      setActionError(null);
                      setOrphanConfirmInput('');
                      setOrphanPurgeConfirmOpen(true);
                    }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Purge Selected Roles ({selectedOrphanedJobIds.length})</span>
                  </button>
                )}
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-gray-600 dark:text-gray-300">
                  <thead className="bg-gray-50 dark:bg-gray-800/70 text-[11px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider border-b border-gray-200 dark:border-gray-800">
                    <tr>
                      <th className="py-2.5 px-4 w-10">
                        <input
                          type="checkbox"
                          checked={
                            orphanedJobs.length > 0 &&
                            orphanedJobs.every((j) => selectedOrphanedJobIds.includes(j.job_id))
                          }
                          onChange={() => {
                            const allIds = orphanedJobs.map((j) => j.job_id);
                            if (allIds.every((id) => selectedOrphanedJobIds.includes(id))) {
                              setSelectedOrphanedJobIds([]);
                            } else {
                              setSelectedOrphanedJobIds(allIds);
                            }
                          }}
                          className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                        />
                      </th>
                      <th className="py-2.5 px-4">Role Title</th>
                      <th className="py-2.5 px-4">Company</th>
                      <th className="py-2.5 px-4">Status</th>
                      <th className="py-2.5 px-4">Applications</th>
                      <th className="py-2.5 px-4">Safety Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                    {orphanedJobs.map((job) => (
                      <tr key={job.job_id} className="hover:bg-gray-50/70 dark:hover:bg-gray-800/50">
                        <td className="py-2.5 px-4">
                          <input
                            type="checkbox"
                            checked={selectedOrphanedJobIds.includes(job.job_id)}
                            onChange={() => handleToggleSelectOrphan(job.job_id)}
                            className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                          />
                        </td>
                        <td className="py-2.5 px-4 font-semibold text-gray-900 dark:text-white">
                          {job.title}
                        </td>
                        <td className="py-2.5 px-4 text-gray-500">
                          {job.company_name}
                        </td>
                        <td className="py-2.5 px-4">
                          {getStatusBadge(job.status)}
                        </td>
                        <td className="py-2.5 px-4">
                          {job.applications_count}
                        </td>
                        <td className="py-2.5 px-4">
                          {getSafetyBadge(job.safety_classification)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODALS & DIALOGS                                                          */}
      {/* ========================================================================= */}

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
                {cleanupResult.companies_processed !== undefined && (
                  <div>
                    <span className="text-gray-400">Companies Processed:</span>{' '}
                    <strong className="text-gray-900 dark:text-white">{cleanupResult.companies_processed}</strong>
                  </div>
                )}
                {cleanupResult.drives_processed !== undefined && (
                  <div>
                    <span className="text-gray-400">Drives Processed:</span>{' '}
                    <strong className="text-gray-900 dark:text-white">{cleanupResult.drives_processed}</strong>
                  </div>
                )}
                {cleanupResult.company_ids && cleanupResult.company_ids.length > 0 && (
                  <div className="col-span-2">
                    <span className="text-gray-400">Company IDs:</span>{' '}
                    <strong className="text-gray-900 dark:text-white">{cleanupResult.company_ids.join(', ')}</strong>
                  </div>
                )}
                {cleanupResult.circular_ids && cleanupResult.circular_ids.length > 0 && (
                  <div className="col-span-2">
                    <span className="text-gray-400">Circular IDs:</span>{' '}
                    <strong className="text-gray-900 dark:text-white">{cleanupResult.circular_ids.join(', ')}</strong>
                  </div>
                )}
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

      {/* Archive Confirmation Modal (Company Scope) */}
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
                disabled={isCleanupLoading || selectedIds.length === 0}
                className="px-5 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
              >
                {isCleanupLoading ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Archiving...</span>
                  </>
                ) : (
                  <span>Confirm Archive</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Purge Confirmation Modal (Company Scope) */}
      {purgeModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-lg w-full p-6 border border-gray-200 dark:border-gray-800 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-red-100 dark:bg-red-950/80 text-red-600 dark:text-red-400 rounded-xl">
                <Trash2 className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                  Confirm Permanent Purge
                </h3>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Permanent Removal of Candidate Records
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

      {/* Orphaned Roles Purge Confirmation Modal */}
      {orphanPurgeConfirmOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-lg w-full p-6 border border-gray-200 dark:border-gray-800 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-red-100 dark:bg-red-950/80 text-red-600 dark:text-red-400 rounded-xl">
                <Trash2 className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                  Purge Orphaned Test Roles
                </h3>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Permanently remove {selectedOrphanedJobIds.length} unattached test job postings
                </p>
              </div>
            </div>

            <div className="space-y-2 text-xs text-gray-600 dark:text-gray-300">
              <p>
                These roles have no active circulars attached and are safe to purge.
              </p>
              <div className="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-lg text-[11px] text-red-800 dark:text-red-300">
                <p className="font-semibold">⚠️ Irreversible Deletion:</p>
                <p>This action will permanently delete the selected job records and any test applications.</p>
              </div>

              <div className="space-y-1.5 pt-1">
                <label className="block text-xs font-semibold text-gray-900 dark:text-white">
                  Type <span className="font-mono bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-300 px-1 py-0.5 rounded">{CONFIRMATION_PHRASE}</span> to confirm:
                </label>
                <input
                  type="text"
                  value={orphanConfirmInput}
                  onChange={(e) => setOrphanConfirmInput(e.target.value)}
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
                onClick={() => setOrphanPurgeConfirmOpen(false)}
                disabled={isCleanupLoading}
                className="px-4 py-2 text-xs font-semibold text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmOrphanPurge}
                disabled={
                  isCleanupLoading ||
                  orphanConfirmInput.trim() !== CONFIRMATION_PHRASE ||
                  selectedOrphanedJobIds.length === 0
                }
                className="px-5 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
              >
                {isCleanupLoading ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Purging...</span>
                  </>
                ) : (
                  <span>Permanently Purge Roles</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Drive Cleanup Modal (Integrated Component) */}
      <BulkDriveCleanupModal
        isOpen={driveModalOpen}
        onClose={() => setDriveModalOpen(false)}
        selectedCircularIds={driveModalSelection}
        onSuccess={async () => {
          setSelectedDriveIds([]);
          await loadPreview();
          fetchCirculars();
        }}
      />
    </div>
  );
};

export default ManageTestData;
