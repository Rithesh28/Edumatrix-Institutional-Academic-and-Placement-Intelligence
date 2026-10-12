import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Megaphone,
  Plus,
  Search,
  Eye,
  Edit2,
  Building2,
  Calendar,
  Clock,
  Briefcase,
  Paperclip,
  CheckCircle2,
  AlertCircle,
  Archive,
  GraduationCap,
  Sparkles,
  Database,
  Filter,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import { useAuthStore } from '../../store/authStore';
import toast from 'react-hot-toast';

const Circulars = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const {
    circulars,
    isCircularsLoading,
    circularsError,
    fetchCirculars,
    publishCircular,
    archiveCircular,
  } = usePlacementStore();

  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [companyFilter, setCompanyFilter] = useState('all');

  const isPrivileged =
    user?.role === 'placement_officer' ||
    user?.role === 'placement' ||
    user?.role === 'admin';

  // Publish confirmation modal state
  const [publishModal, setPublishModal] = useState({
    isOpen: false,
    circular: null,
    isPublishing: false,
    confirmNoSkills: false,
    errorMessage: null,
  });

  useEffect(() => {
    fetchCirculars();
  }, [fetchCirculars]);

  const companiesList = useMemo(() => {
    const names = circulars.map((c) => c.company_name).filter(Boolean);
    return Array.from(new Set(names)).sort();
  }, [circulars]);

  const filteredCirculars = useMemo(() => {
    return circulars.filter((circ) => {
      const matchesSearch =
        !searchTerm ||
        circ.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        circ.company_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        circ.summary?.toLowerCase().includes(searchTerm.toLowerCase());

      const matchesStatus =
        statusFilter === 'all' || circ.status?.toLowerCase() === statusFilter.toLowerCase();

      const matchesCompany =
        companyFilter === 'all' || circ.company_name === companyFilter;

      return matchesSearch && matchesStatus && matchesCompany;
    });
  }, [circulars, searchTerm, statusFilter, companyFilter]);

  const stats = useMemo(() => {
    const total = circulars.length;
    const published = circulars.filter((c) => c.status === 'published').length;
    const drafts = circulars.filter((c) => c.status === 'draft').length;
    const archived = circulars.filter((c) => c.status === 'archived').length;
    const linkedRoles = circulars.reduce(
      (acc, c) => acc + (c.linked_jobs_count || c.linked_jobs?.length || 0),
      0
    );
    const companies = new Set(circulars.map((c) => c.company_name).filter(Boolean)).size;
    return { total, published, drafts, archived, linkedRoles, companies };
  }, [circulars]);

  const handleOpenPublish = (circular) => {
    if (!circular.linked_jobs || circular.linked_jobs.length === 0) {
      toast.error('A circular must have at least one linked job before publishing.');
      return;
    }
    setPublishModal({
      isOpen: true,
      circular,
      isPublishing: false,
      confirmNoSkills: false,
      errorMessage: null,
    });
  };

  const handleConfirmPublish = async () => {
    const { circular, confirmNoSkills } = publishModal;
    setPublishModal((prev) => ({ ...prev, isPublishing: true, errorMessage: null }));

    try {
      const response = await publishCircular(circular.id, {
        confirm_no_skills: confirmNoSkills,
      });
      toast.success(response.message || 'Recruitment circular published successfully!');
      setPublishModal({
        isOpen: false,
        circular: null,
        isPublishing: false,
        confirmNoSkills: false,
        errorMessage: null,
      });
      fetchCirculars();
    } catch (error) {
      const msg = error.response?.data?.detail || error.message || 'Failed to publish circular.';
      if (msg.includes('confirm_no_skills=True')) {
        setPublishModal((prev) => ({
          ...prev,
          isPublishing: false,
          errorMessage: msg,
          showSkillBypass: true,
        }));
      } else {
        toast.error(msg);
        setPublishModal((prev) => ({ ...prev, isPublishing: false, errorMessage: msg }));
      }
    }
  };

  const handleArchive = async (id, title) => {
    if (window.confirm(`Are you sure you want to archive circular "${title}"?`)) {
      try {
        await archiveCircular(id);
        toast.success('Circular archived successfully.');
        fetchCirculars();
      } catch (error) {
        toast.error('Failed to archive circular.');
      }
    }
  };

  const getStatusBadge = (status) => {
    switch (status?.toLowerCase()) {
      case 'published':
        return (
          <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" /> Published
          </span>
        );
      case 'draft':
        return (
          <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300 border border-amber-200 dark:border-amber-800 flex items-center gap-1">
            <AlertCircle className="w-3 h-3" /> Draft
          </span>
        );
      case 'archived':
        return (
          <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300 border border-gray-200 dark:border-gray-700 flex items-center gap-1">
            <Archive className="w-3 h-3" /> Archived
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Megaphone className="w-7 h-7 text-indigo-600 dark:text-indigo-400" />
            <span>Recruitment Drives</span>
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Manage institutional recruitment drives, eligible branches, circular documents, and linked job postings.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {isPrivileged && (
            <button
              onClick={() => navigate('/placement/manage-test-data')}
              className="inline-flex items-center gap-2 px-3.5 py-2.5 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-gray-700 rounded-lg text-sm font-semibold shadow-sm transition-colors cursor-pointer"
              title="Inspect candidates for safe recruitment test data cleanup"
            >
              <Database className="w-4 h-4 text-amber-500" />
              <span>Manage Test Data</span>
            </button>
          )}

          <button
            onClick={() => navigate('/placement/circulars/new')}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold shadow-sm transition-colors cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Create Recruitment Drive</span>
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
            Total Drives
          </span>
          <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">{stats.total}</p>
        </div>
        <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
          <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">
            Published
          </span>
          <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
            {stats.published}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
          <span className="text-xs font-medium text-amber-600 dark:text-amber-400 uppercase tracking-wider">
            Drafts
          </span>
          <p className="text-2xl font-bold text-amber-600 dark:text-amber-400 mt-1">
            {stats.drafts}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
          <span className="text-xs font-medium text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">
            Linked Roles
          </span>
          <p className="text-2xl font-bold text-indigo-600 dark:text-indigo-400 mt-1">
            {stats.linkedRoles}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm col-span-2 sm:col-span-1">
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
            Companies
          </span>
          <p className="text-2xl font-bold text-gray-600 dark:text-gray-400 mt-1">{stats.companies}</p>
        </div>
      </div>

      {/* Filters and Search */}
      <div className="flex flex-col lg:flex-row gap-3 items-stretch lg:items-center justify-between bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search drives by title, company, or summary..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:text-white"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {companiesList.length > 0 && (
            <div className="flex items-center gap-1.5">
              <Filter className="w-3.5 h-3.5 text-gray-400 hidden sm:block" />
              <select
                value={companyFilter}
                onChange={(e) => setCompanyFilter(e.target.value)}
                className="px-2.5 py-1.5 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-xs font-medium text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
              >
                <option value="all">All Companies ({companiesList.length})</option>
                {companiesList.map((comp) => (
                  <option key={comp} value={comp}>
                    {comp}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="flex items-center gap-1 overflow-x-auto">
            {['all', 'draft', 'published', 'archived'].map((status) => (
              <button
                key={status}
                onClick={() => setStatusFilter(status)}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg capitalize transition-colors cursor-pointer ${
                  statusFilter === status
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                }`}
              >
                {status}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Circulars List */}
      {isCircularsLoading && circulars.length === 0 ? (
        <div className="p-12 text-center text-gray-500 dark:text-gray-400">
          <div className="animate-spin w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full mx-auto mb-3" />
          <p>Loading recruitment drives...</p>
        </div>
      ) : circularsError ? (
        <div className="p-6 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-xl text-center text-red-700 dark:text-red-300">
          <p>{circularsError}</p>
        </div>
      ) : filteredCirculars.length === 0 ? (
        <div className="p-12 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 text-center">
          <Megaphone className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-gray-900 dark:text-white">
            No recruitment drives found
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {searchTerm || statusFilter !== 'all' || companyFilter !== 'all'
              ? 'Try adjusting your search query or filters.'
              : 'Create your first company recruitment drive.'}
          </p>
          {!searchTerm && statusFilter === 'all' && companyFilter === 'all' && (
            <button
              onClick={() => navigate('/placement/circulars/new')}
              className="mt-4 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold cursor-pointer"
            >
              Create Recruitment Drive
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filteredCirculars.map((circ) => (
            <div
              key={circ.id}
              className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5 shadow-sm hover:border-indigo-300 dark:hover:border-indigo-700 transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
            >
              <div className="space-y-2 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3
                    onClick={() => navigate(`/placement/circulars/${circ.id}`)}
                    className="text-lg font-bold text-gray-900 dark:text-white hover:text-indigo-600 dark:hover:text-indigo-400 cursor-pointer"
                  >
                    {circ.title}
                  </h3>
                  {getStatusBadge(circ.status)}
                </div>

                <div className="flex flex-wrap items-center gap-y-1 gap-x-4 text-xs text-gray-500 dark:text-gray-400">
                  <span className="flex items-center gap-1 font-medium text-gray-700 dark:text-gray-300">
                    <Building2 className="w-3.5 h-3.5 text-indigo-500" />
                    {circ.company_name || 'Company'}
                  </span>

                  {circ.drive_date && (
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3.5 h-3.5 text-gray-400" />
                      Drive: {new Date(circ.drive_date).toLocaleDateString()}
                    </span>
                  )}

                  {circ.application_deadline && (
                    <span className="flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5 text-gray-400" />
                      Deadline: {new Date(circ.application_deadline).toLocaleDateString()}
                    </span>
                  )}

                  <span className="flex items-center gap-1">
                    <Briefcase className="w-3.5 h-3.5 text-gray-400" />
                    {circ.linked_jobs_count || circ.linked_jobs?.length || 0} linked role(s)
                  </span>

                  <span className="flex items-center gap-1">
                    <Paperclip className="w-3.5 h-3.5 text-gray-400" />
                    {circ.attachments_count || circ.attachments?.length || 0} attachment(s)
                  </span>
                </div>

                {circ.summary && (
                  <p className="text-xs text-gray-600 dark:text-gray-300 line-clamp-2">
                    {circ.summary}
                  </p>
                )}

                {circ.branch_eligibility && circ.branch_eligibility.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1 pt-1">
                    <span className="text-[11px] text-gray-400 flex items-center gap-0.5 mr-1">
                      <GraduationCap className="w-3 h-3" /> Branches:
                    </span>
                    {circ.branch_eligibility.map((branch, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 rounded text-[11px]"
                      >
                        {branch}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2 pt-2 md:pt-0 border-t md:border-t-0 border-gray-100 dark:border-gray-800 flex-shrink-0">
                <button
                  onClick={() => navigate(`/placement/circulars/${circ.id}`)}
                  className="px-3 py-1.5 text-xs font-semibold bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 rounded-lg flex items-center gap-1 cursor-pointer transition-colors"
                >
                  <Eye className="w-3.5 h-3.5" /> View
                </button>

                {circ.status === 'draft' && (
                  <>
                    <button
                      onClick={() => navigate(`/placement/circulars/${circ.id}/edit`)}
                      className="px-3 py-1.5 text-xs font-semibold bg-indigo-50 dark:bg-indigo-950/50 hover:bg-indigo-100 dark:hover:bg-indigo-900/60 text-indigo-700 dark:text-indigo-300 rounded-lg flex items-center gap-1 cursor-pointer transition-colors"
                    >
                      <Edit2 className="w-3.5 h-3.5" /> Edit
                    </button>
                    <button
                      onClick={() => handleOpenPublish(circ)}
                      className="px-3 py-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg flex items-center gap-1 cursor-pointer transition-colors shadow-sm"
                    >
                      <Sparkles className="w-3.5 h-3.5" /> Publish
                    </button>
                  </>
                )}

                {circ.status === 'published' && (
                  <button
                    onClick={() => handleArchive(circ.id, circ.title)}
                    className="px-3 py-1.5 text-xs font-semibold bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 rounded-lg flex items-center gap-1 cursor-pointer transition-colors"
                  >
                    <Archive className="w-3.5 h-3.5" /> Archive
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Publish Review Modal */}
      {publishModal.isOpen && publishModal.circular && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-lg w-full p-6 border border-gray-200 dark:border-gray-800 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-emerald-100 dark:bg-emerald-950/80 text-emerald-600 dark:text-emerald-400 rounded-xl">
                <Sparkles className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                  Publish Recruitment Circular
                </h3>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Review announcement and atomic job publication
                </p>
              </div>
            </div>

            <div className="bg-gray-50 dark:bg-gray-800/60 p-4 rounded-xl space-y-2 text-xs text-gray-700 dark:text-gray-300">
              <p>
                <strong className="text-gray-900 dark:text-white">Title:</strong>{' '}
                {publishModal.circular.title}
              </p>
              <p>
                <strong className="text-gray-900 dark:text-white">Company:</strong>{' '}
                {publishModal.circular.company_name}
              </p>
              <p>
                <strong className="text-gray-900 dark:text-white">Linked Roles:</strong>{' '}
                {publishModal.circular.linked_jobs?.length || 0} job posting(s)
              </p>
              <p>
                <strong className="text-gray-900 dark:text-white">Attachments:</strong>{' '}
                {publishModal.circular.attachments?.length || 0} document(s)
              </p>
            </div>

            <div className="p-3 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded-lg text-xs text-blue-800 dark:text-blue-300 space-y-1">
              <p className="font-semibold">⚡ Atomic Publication Behavior:</p>
              <ul className="list-disc pl-4 space-y-0.5">
                <li>Publishes the circular and activates all linked draft job roles in one transaction.</li>
                <li>Sends an aggregate announcement to eligible students.</li>
                <li>Suppresses individual job publication alerts to prevent notification spam.</li>
              </ul>
            </div>

            {publishModal.errorMessage && (
              <div className="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-lg text-xs text-red-700 dark:text-red-300">
                {publishModal.errorMessage}
              </div>
            )}

            {publishModal.showSkillBypass && (
              <label className="flex items-center gap-2 p-3 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-lg cursor-pointer">
                <input
                  type="checkbox"
                  checked={publishModal.confirmNoSkills}
                  onChange={(e) =>
                    setPublishModal((prev) => ({
                      ...prev,
                      confirmNoSkills: e.target.checked,
                    }))
                  }
                  className="rounded text-amber-600 focus:ring-amber-500"
                />
                <span className="text-xs text-amber-900 dark:text-amber-200">
                  Explicitly confirm publication of roles without skill requirements.
                </span>
              </label>
            )}

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() =>
                  setPublishModal({
                    isOpen: false,
                    circular: null,
                    isPublishing: false,
                    confirmNoSkills: false,
                    errorMessage: null,
                  })
                }
                disabled={publishModal.isPublishing}
                className="px-4 py-2 text-xs font-semibold text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmPublish}
                disabled={publishModal.isPublishing}
                className="px-5 py-2 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors cursor-pointer flex items-center gap-1.5 shadow-sm disabled:opacity-50"
              >
                {publishModal.isPublishing ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Publishing...</span>
                  </>
                ) : (
                  <span>Confirm & Publish</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Circulars;
