import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Building2,
  Plus,
  Search,
  Edit2,
  Trash2,
  ExternalLink,
  ArrowLeft,
  ListChecks,
  CheckSquare,
  Square,
  Database,
  CheckCircle2,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import { useAuthStore } from '../../store/authStore';
import toast from 'react-hot-toast';
import BulkCompanyCleanupModal from './BulkCompanyCleanupModal';

const Companies = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { companies, isLoading, fetchCompanies, deleteCompany } = usePlacementStore();

  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('active'); // 'active' | 'inactive' | 'all'
  const [isBulkMode, setIsBulkMode] = useState(false);
  const [selectedCompanyIds, setSelectedCompanyIds] = useState([]);
  const [bulkCleanupModalOpen, setBulkCleanupModalOpen] = useState(false);

  const isPrivileged =
    user?.role === 'placement_officer' ||
    user?.role === 'placement' ||
    user?.role === 'admin';

  useEffect(() => {
    fetchCompanies();
  }, [fetchCompanies]);

  const handleDelete = async (id, name) => {
    if (window.confirm(`Are you sure you want to delete "${name}"?`)) {
      try {
        await deleteCompany(id);
        toast.success('Company deleted successfully');
        // Remove from selection if selected
        setSelectedCompanyIds((prev) => prev.filter((item) => item !== id));
      } catch (error) {
        toast.error('Failed to delete company');
      }
    }
  };

  const metrics = useMemo(() => {
    const total = companies.length;
    const active = companies.filter((c) => Boolean(c.is_active)).length;
    const inactive = companies.filter((c) => !c.is_active).length;
    return { total, active, inactive };
  }, [companies]);

  const filteredCompanies = useMemo(() => {
    return companies.filter((c) => {
      const matchesSearch =
        !searchTerm ||
        c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        c.industry?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        c.location?.toLowerCase().includes(searchTerm.toLowerCase());

      const matchesStatus =
        statusFilter === 'all'
          ? true
          : statusFilter === 'active'
          ? Boolean(c.is_active)
          : !c.is_active;

      return matchesSearch && matchesStatus;
    });
  }, [companies, searchTerm, statusFilter]);

  // Bulk Selection Handlers
  const handleToggleSelectCompany = (id) => {
    setSelectedCompanyIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleSelectAllFiltered = () => {
    const visibleIds = filteredCompanies.map((c) => c.id);
    const allSelected =
      visibleIds.length > 0 && visibleIds.every((id) => selectedCompanyIds.includes(id));
    if (allSelected) {
      setSelectedCompanyIds((prev) => prev.filter((id) => !visibleIds.includes(id)));
    } else {
      setSelectedCompanyIds((prev) => Array.from(new Set([...prev, ...visibleIds])));
    }
  };

  const handleSelectByStatus = (isActive) => {
    const statusIds = filteredCompanies
      .filter((c) => Boolean(c.is_active) === isActive)
      .map((c) => c.id);
    setSelectedCompanyIds((prev) => Array.from(new Set([...prev, ...statusIds])));
  };

  const handleClearSelection = () => {
    setSelectedCompanyIds([]);
  };

  const handleCleanupSuccess = (result) => {
    fetchCompanies();
    // Clear processed IDs from selection
    const processedIds = result?.company_ids || [];
    if (processedIds.length > 0) {
      setSelectedCompanyIds((prev) => prev.filter((id) => !processedIds.includes(id)));
    } else {
      setSelectedCompanyIds([]);
    }
  };

  if (isLoading && companies.length === 0) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-indigo-600 border-t-transparent"></div>
      </div>
    );
  }

  const allFilteredSelected =
    filteredCompanies.length > 0 &&
    filteredCompanies.every((c) => selectedCompanyIds.includes(c.id));

  return (
    <div className="space-y-6 pb-12">
      {/* Back Button */}
      <button
        onClick={() => navigate('/placement/dashboard')}
        className="flex items-center space-x-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors cursor-pointer"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Dashboard</span>
      </button>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Building2 className="w-7 h-7 text-indigo-600 dark:text-indigo-400" />
            <span>Companies</span>
          </h1>
          <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
            Manage partner companies, recruiters, and corporate profiles
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Bulk Selection Toggle */}
          {isPrivileged && (
            <button
              onClick={() => {
                setIsBulkMode(!isBulkMode);
                if (isBulkMode) setSelectedCompanyIds([]);
              }}
              className={`inline-flex items-center gap-2 px-3.5 py-2.5 rounded-lg text-sm font-semibold shadow-xs transition-colors cursor-pointer border ${
                isBulkMode
                  ? 'bg-indigo-600 text-white border-indigo-600 dark:bg-indigo-500'
                  : 'bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 border-gray-200 dark:border-gray-700'
              }`}
              title="Toggle bulk company selection and cleanup"
            >
              <ListChecks className="w-4 h-4 text-indigo-500 dark:text-indigo-400" />
              <span>Bulk Manage Companies</span>
            </button>
          )}

          {/* Manage Test Data Link */}
          {isPrivileged && (
            <button
              onClick={() => navigate('/placement/manage-test-data')}
              className="inline-flex items-center gap-2 px-3.5 py-2.5 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-gray-700 rounded-lg text-sm font-semibold shadow-xs transition-colors cursor-pointer"
              title="Open full recruitment test-data management and inspection"
            >
              <Database className="w-4 h-4 text-amber-500" />
              <span>Manage Test Data</span>
            </button>
          )}

          <button
            onClick={() => navigate('/placement/companies/add')}
            className="px-4 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 flex items-center space-x-2 text-sm font-semibold shadow-xs transition-colors cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Add Company</span>
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <button
          onClick={() => setStatusFilter('all')}
          className={`p-4 rounded-xl border text-left transition-all cursor-pointer shadow-xs ${
            statusFilter === 'all'
              ? 'bg-indigo-50/70 dark:bg-indigo-950/40 border-indigo-300 dark:border-indigo-700 ring-2 ring-indigo-500/30'
              : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 hover:border-gray-300'
          }`}
        >
          <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
            Total Companies
          </span>
          <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
            {metrics.total}
          </p>
        </button>

        <button
          onClick={() => setStatusFilter('active')}
          className={`p-4 rounded-xl border text-left transition-all cursor-pointer shadow-xs ${
            statusFilter === 'active'
              ? 'bg-emerald-50/70 dark:bg-emerald-950/40 border-emerald-300 dark:border-emerald-700 ring-2 ring-emerald-500/30'
              : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 hover:border-gray-300'
          }`}
        >
          <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">
            Active Companies
          </span>
          <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
            {metrics.active}
          </p>
        </button>

        <button
          onClick={() => setStatusFilter('inactive')}
          className={`p-4 rounded-xl border text-left transition-all cursor-pointer shadow-xs ${
            statusFilter === 'inactive'
              ? 'bg-gray-100 dark:bg-gray-800 border-gray-400 dark:border-gray-600 ring-2 ring-gray-400/30'
              : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 hover:border-gray-300'
          }`}
        >
          <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
            Inactive / Archived
          </span>
          <p className="text-2xl font-bold text-gray-600 dark:text-gray-400 mt-1">
            {metrics.inactive}
          </p>
        </button>
      </div>

      {/* Filters and Search Bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800 shadow-xs">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search companies by name, industry, or location..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm text-gray-900 dark:text-white"
          />
        </div>

        {/* Status Filter Tabs */}
        <div className="flex items-center gap-1.5 overflow-x-auto shrink-0">
          <button
            onClick={() => setStatusFilter('active')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors cursor-pointer ${
              statusFilter === 'active'
                ? 'bg-emerald-600 text-white shadow-xs'
                : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
            }`}
          >
            Active ({metrics.active})
          </button>
          <button
            onClick={() => setStatusFilter('inactive')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors cursor-pointer ${
              statusFilter === 'inactive'
                ? 'bg-gray-700 text-white dark:bg-gray-600 shadow-xs'
                : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
            }`}
          >
            Inactive / Archived ({metrics.inactive})
          </button>
          <button
            onClick={() => setStatusFilter('all')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors cursor-pointer ${
              statusFilter === 'all'
                ? 'bg-indigo-600 text-white shadow-xs'
                : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
            }`}
          >
            All ({metrics.total})
          </button>
        </div>
      </div>

      {/* Bulk Management Toolbar */}
      {isBulkMode && (
        <div className="bg-indigo-50/80 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800 p-4 rounded-xl shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-3 animate-in fade-in slide-in-from-top-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-indigo-600 text-white flex items-center gap-1.5 shadow-2xs">
              <ListChecks className="w-3.5 h-3.5" />
              {selectedCompanyIds.length} company(ies) selected
            </span>
            <span className="text-xs text-gray-500 dark:text-gray-400">
              of {filteredCompanies.length} filtered
            </span>

            <div className="flex flex-wrap items-center gap-1.5 ml-2">
              <button
                onClick={handleSelectAllFiltered}
                className="px-2.5 py-1 text-xs font-medium rounded-lg bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-gray-700 cursor-pointer shadow-2xs"
              >
                {allFilteredSelected ? 'Deselect All Filtered' : 'Select All Filtered'}
              </button>
              <button
                onClick={() => handleSelectByStatus(true)}
                className="px-2.5 py-1 text-xs font-medium rounded-lg bg-emerald-100/70 dark:bg-emerald-950/60 hover:bg-emerald-200 text-emerald-800 dark:text-emerald-200 border border-emerald-200 dark:border-emerald-800 cursor-pointer"
              >
                + Active ({filteredCompanies.filter((c) => c.is_active).length})
              </button>
              <button
                onClick={() => handleSelectByStatus(false)}
                className="px-2.5 py-1 text-xs font-medium rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-700 cursor-pointer"
              >
                + Inactive ({filteredCompanies.filter((c) => !c.is_active).length})
              </button>
              {selectedCompanyIds.length > 0 && (
                <button
                  onClick={handleClearSelection}
                  className="px-2 py-1 text-xs font-medium text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 underline cursor-pointer ml-1"
                >
                  Clear Selection
                </button>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setBulkCleanupModalOpen(true)}
              disabled={selectedCompanyIds.length === 0}
              className="px-4 py-2 text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg shadow-xs transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Preview & Clean Up Selected Companies</span>
            </button>
          </div>
        </div>
      )}

      {/* Companies Grid */}
      {filteredCompanies.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-gray-200 dark:border-gray-800">
          <Building2 className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <p className="text-gray-500 dark:text-gray-400">No companies found</p>
          <button
            onClick={() => navigate('/placement/companies/add')}
            className="mt-2 text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300 text-sm font-medium"
          >
            Add your first company
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredCompanies.map((company) => {
            const isSelected = selectedCompanyIds.includes(company.id);

            return (
              <div
                key={company.id}
                onClick={() => {
                  if (isBulkMode) {
                    handleToggleSelectCompany(company.id);
                  }
                }}
                className={`bg-white dark:bg-gray-900 rounded-xl border p-5 transition-all shadow-xs ${
                  isBulkMode ? 'cursor-pointer hover:border-indigo-400' : 'hover:shadow-md'
                } ${
                  isSelected
                    ? 'ring-2 ring-indigo-500 border-indigo-500 bg-indigo-50/20 dark:bg-indigo-950/20'
                    : 'border-gray-200 dark:border-gray-800'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2.5 flex-1 min-w-0">
                    {/* Bulk Selection Checkbox */}
                    {isBulkMode && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleToggleSelectCompany(company.id);
                        }}
                        className="mt-0.5 text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 shrink-0 cursor-pointer"
                      >
                        {isSelected ? (
                          <CheckSquare className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                        ) : (
                          <Square className="w-5 h-5" />
                        )}
                      </button>
                    )}

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2">
                        <Building2 className="w-5 h-5 text-indigo-500 shrink-0" />
                        <h3 className="font-semibold text-gray-900 dark:text-white truncate">
                          {company.name}
                        </h3>
                      </div>
                      {company.industry && (
                        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 truncate">
                          {company.industry}
                        </p>
                      )}
                      {company.location && (
                        <p className="text-xs text-gray-400 mt-0.5 truncate">{company.location}</p>
                      )}
                      {company.website && (
                        <a
                          href={company.website}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline flex items-center space-x-1 mt-1 truncate"
                        >
                          <span className="truncate">{company.website}</span>
                          <ExternalLink className="w-3 h-3 shrink-0" />
                        </a>
                      )}
                      <div className="flex items-center space-x-2 mt-2">
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                            company.is_active
                              ? 'bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300'
                              : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'
                          }`}
                        >
                          {company.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex space-x-1 shrink-0">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/placement/companies/${company.id}/edit`);
                      }}
                      className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer"
                      title="Edit company"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(company.id, company.name);
                      }}
                      className="p-1.5 text-gray-400 hover:text-red-600 rounded-lg hover:bg-red-50 dark:hover:bg-red-950/40 cursor-pointer"
                      title="Delete company"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {company.contact_email && (
                  <p className="text-xs text-gray-400 mt-2 truncate">📧 {company.contact_email}</p>
                )}
                {company.contact_phone && (
                  <p className="text-xs text-gray-400 truncate">📞 {company.contact_phone}</p>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Bulk Company Cleanup Modal */}
      <BulkCompanyCleanupModal
        isOpen={bulkCleanupModalOpen}
        onClose={() => setBulkCleanupModalOpen(false)}
        selectedCompanyIds={selectedCompanyIds}
        onSuccess={handleCleanupSuccess}
      />
    </div>
  );
};

export default Companies;