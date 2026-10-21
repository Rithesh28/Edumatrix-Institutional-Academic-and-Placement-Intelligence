import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText,
  Upload,
  Search,
  Filter,
  CheckCircle,
  AlertTriangle,
  Clock,
  Building2,
  Briefcase,
  Award,
  ChevronRight,
  Plus,
  X,
  FileSpreadsheet,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import { getJobRounds } from '../../services/placementService';
import toast from 'react-hot-toast';

const Results = () => {
  const navigate = useNavigate();
  const {
    resultBatches,
    isResultsLoading,
    fetchResultBatches,
    uploadResultDocument,
    companies,
    fetchCompanies,
    jobs,
    fetchJobPostings,
  } = usePlacementStore();

  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [showUploadModal, setShowUploadModal] = useState(false);

  // Upload Form State
  const [selectedCompanyId, setSelectedCompanyId] = useState('');
  const [selectedJobId, setSelectedJobId] = useState('');
  const [availableRounds, setAvailableRounds] = useState([]);
  const [selectedRoundId, setSelectedRoundId] = useState('');
  const [roundName, setRoundName] = useState('');
  const [roundType, setRoundType] = useState('assessment');
  const [isFinalRound, setIsFinalRound] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => {
    fetchResultBatches();
    fetchCompanies();
    fetchJobPostings();
  }, []);

  // Fetch available recruitment rounds when a job is selected
  useEffect(() => {
    if (selectedJobId) {
      getJobRounds(selectedJobId)
        .then((rounds) => {
          setAvailableRounds(rounds || []);
        })
        .catch(() => {
          setAvailableRounds([]);
        });
    } else {
      setAvailableRounds([]);
      setSelectedRoundId('');
    }
  }, [selectedJobId]);

  const handleRoundSelect = (roundId) => {
    setSelectedRoundId(roundId);
    if (!roundId) return;
    const r = availableRounds.find((round) => String(round.id) === String(roundId));
    if (r) {
      setRoundName(r.round_name);
      setRoundType(r.round_type);
      setIsFinalRound(Boolean(r.is_final));
    }
  };

  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (!selectedCompanyId) {
      toast.error('Please select a company.');
      return;
    }
    if (!roundName.trim()) {
      toast.error('Please enter a round name.');
      return;
    }
    if (!uploadFile) {
      toast.error('Please select a result file (.csv, .xlsx, .pdf).');
      return;
    }

    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', uploadFile);
      formData.append('company_id', selectedCompanyId);
      formData.append('round_name', roundName.trim());
      formData.append('round_type', roundType);
      formData.append('is_final_round', isFinalRound ? 'true' : 'false');
      if (selectedJobId) {
        formData.append('job_posting_id', selectedJobId);
      }
      if (selectedRoundId) {
        formData.append('round_id', selectedRoundId);
      }

      const createdBatch = await uploadResultDocument(formData);
      toast.success(`Result file processed: ${createdBatch.total_rows} candidates extracted.`);
      setShowUploadModal(false);
      // Reset form
      setSelectedCompanyId('');
      setSelectedJobId('');
      setSelectedRoundId('');
      setAvailableRounds([]);
      setRoundName('');
      setRoundType('assessment');
      setIsFinalRound(false);
      setUploadFile(null);
      // Navigate to detail
      navigate(`/placement/results/${createdBatch.id}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || 'Failed to process result file.');
    } finally {
      setIsUploading(false);
    }
  };

  const filteredBatches = resultBatches.filter((b) => {
    const matchesSearch =
      b.round_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      b.company_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      b.job_title?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || b.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const getStatusBadge = (status) => {
    switch (status) {
      case 'fully_confirmed':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300">
            <CheckCircle className="w-3 h-3 mr-1" /> Fully Confirmed
          </span>
        );
      case 'partially_confirmed':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 dark:bg-amber-950/70 dark:text-amber-300">
            <Clock className="w-3 h-3 mr-1" /> Partially Confirmed
          </span>
        );
      case 'in_review':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 dark:bg-blue-950/70 dark:text-blue-300">
            <Clock className="w-3 h-3 mr-1" /> In Review
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center space-x-2">
            <span>Recruitment Results & Shortlists</span>
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Upload company-provided result documents, extract candidate rows, verify student matches, and confirm round outcomes.
          </p>
        </div>

        <button
          onClick={() => setShowUploadModal(true)}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold flex items-center space-x-2 shadow-sm transition-colors cursor-pointer"
        >
          <Upload className="w-4 h-4" />
          <span>Upload Result Document</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row gap-4 bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-3 text-gray-400" />
          <input
            type="text"
            placeholder="Search by company, round, or job role..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-gray-200 dark:border-gray-700 rounded-lg text-sm bg-gray-50 dark:bg-gray-800/60 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        <div className="flex items-center space-x-2">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-2 text-sm bg-gray-50 dark:bg-gray-800/60 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="all">All Statuses</option>
            <option value="in_review">In Review</option>
            <option value="partially_confirmed">Partially Confirmed</option>
            <option value="fully_confirmed">Fully Confirmed</option>
          </select>
        </div>
      </div>

      {/* Result Batches List */}
      {isResultsLoading && resultBatches.length === 0 ? (
        <div className="flex justify-center items-center h-48 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-indigo-600 border-t-transparent"></div>
        </div>
      ) : filteredBatches.length === 0 ? (
        <div className="text-center py-16 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
          <FileSpreadsheet className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-gray-900 dark:text-white">No Result Batches Found</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto mt-1 mb-4">
            Upload candidate result spreadsheets (.xlsx, .csv) or PDF result sheets to begin reviewing and confirming drive outcomes.
          </p>
          <button
            onClick={() => setShowUploadModal(true)}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow-sm"
          >
            Upload First Result Document
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filteredBatches.map((batch) => (
            <div
              key={batch.id}
              onClick={() => navigate(`/placement/results/${batch.id}`)}
              className="bg-white dark:bg-gray-900 p-5 rounded-xl border border-gray-200 dark:border-gray-800 hover:border-indigo-400 dark:hover:border-indigo-600 hover:shadow-md transition-all cursor-pointer flex flex-col md:flex-row md:items-center justify-between gap-4"
            >
              <div className="space-y-2 flex-1">
                <div className="flex items-center space-x-3 flex-wrap gap-y-1">
                  <h3 className="text-base font-bold text-gray-900 dark:text-white hover:text-indigo-600 transition-colors">
                    {batch.round_name}
                  </h3>
                  {batch.round_id && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                      Round #{batch.round_number || batch.round_id}
                    </span>
                  )}
                  {getStatusBadge(batch.status)}
                  {batch.is_final_round ? (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-purple-100 text-purple-800 dark:bg-purple-950/70 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
                      <Award className="w-3 h-3 mr-1" /> Final Process Round
                    </span>
                  ) : (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                      Intermediate Round
                    </span>
                  )}
                </div>

                <div className="flex items-center space-x-4 text-xs text-gray-500 dark:text-gray-400 flex-wrap gap-y-1">
                  <span className="flex items-center">
                    <Building2 className="w-3.5 h-3.5 mr-1 text-gray-400" />
                    {batch.company_name || 'Company N/A'}
                  </span>
                  {batch.job_title && (
                    <span className="flex items-center">
                      <Briefcase className="w-3.5 h-3.5 mr-1 text-gray-400" />
                      {batch.job_title}
                    </span>
                  )}
                  <span className="flex items-center">
                    <FileText className="w-3.5 h-3.5 mr-1 text-gray-400" />
                    {batch.filename || 'Source Document'}
                  </span>
                  <span>Uploaded: {new Date(batch.created_at).toLocaleDateString()}</span>
                </div>
              </div>

              {/* Counts Badge */}
              <div className="flex items-center space-x-6">
                <div className="grid grid-cols-4 gap-3 text-center">
                  <div className="px-2.5 py-1 bg-gray-50 dark:bg-gray-800/60 rounded">
                    <div className="text-sm font-bold text-gray-900 dark:text-white">{batch.total_rows}</div>
                    <div className="text-[10px] text-gray-500 uppercase">Total</div>
                  </div>
                  <div className="px-2.5 py-1 bg-emerald-50 dark:bg-emerald-950/40 rounded">
                    <div className="text-sm font-bold text-emerald-600 dark:text-emerald-400">{batch.matched_count}</div>
                    <div className="text-[10px] text-emerald-600 dark:text-emerald-400 uppercase">Matched</div>
                  </div>
                  <div className="px-2.5 py-1 bg-amber-50 dark:bg-amber-950/40 rounded">
                    <div className="text-sm font-bold text-amber-600 dark:text-amber-400">{batch.ambiguous_count}</div>
                    <div className="text-[10px] text-amber-600 dark:text-amber-400 uppercase">Review</div>
                  </div>
                  <div className="px-2.5 py-1 bg-indigo-50 dark:bg-indigo-950/40 rounded">
                    <div className="text-sm font-bold text-indigo-600 dark:text-indigo-400">{batch.confirmed_count}</div>
                    <div className="text-[10px] text-indigo-600 dark:text-indigo-400 uppercase">Confirmed</div>
                  </div>
                </div>

                <ChevronRight className="w-5 h-5 text-gray-400" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Upload & Setup Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl border border-gray-200 dark:border-gray-800 max-w-lg w-full p-6 space-y-5 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">Upload Result Document</h3>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Supported formats: CSV, XLSX, XLS, PDF
                </p>
              </div>
              <button
                onClick={() => setShowUploadModal(false)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleUploadSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Company <span className="text-rose-500">*</span>
                </label>
                <select
                  required
                  value={selectedCompanyId}
                  onChange={(e) => {
                    setSelectedCompanyId(e.target.value);
                    setSelectedJobId('');
                    setSelectedRoundId('');
                  }}
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">Select Company</option>
                  {companies.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Job Role (Optional)
                </label>
                <select
                  value={selectedJobId}
                  onChange={(e) => {
                    setSelectedJobId(e.target.value);
                    setSelectedRoundId('');
                  }}
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">Link to Specific Job Posting (Optional)</option>
                  {jobs
                    .filter((j) => !selectedCompanyId || String(j.company_id) === String(selectedCompanyId))
                    .map((j) => (
                      <option key={j.id} value={j.id}>
                        {j.title} ({j.status})
                      </option>
                    ))}
                </select>
              </div>

              {/* Authoritative Round Selector when Job is selected */}
              {selectedJobId && availableRounds.length > 0 && (
                <div>
                  <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                    Select Recruitment Round (Recommended)
                  </label>
                  <select
                    value={selectedRoundId}
                    onChange={(e) => handleRoundSelect(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-indigo-200 dark:border-indigo-800 rounded-lg bg-indigo-50/50 dark:bg-indigo-950/30 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="">-- Create/specify round manually below --</option>
                    {availableRounds.map((r) => (
                      <option key={r.id} value={r.id}>
                        Round #{r.round_number}: {r.round_name} ({r.round_type}) {r.is_final ? '[FINAL ROUND]' : ''}
                      </option>
                    ))}
                  </select>
                  <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-1">
                    Selecting an existing round links candidate outcomes directly to this job's recruitment pipeline.
                  </p>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                    Round Name <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Round 1 Online Test"
                    value={roundName}
                    onChange={(e) => setRoundName(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                    Round Type
                  </label>
                  <select
                    value={roundType}
                    onChange={(e) => setRoundType(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="assessment">Online Assessment</option>
                    <option value="technical_interview">Technical Interview</option>
                    <option value="hr_interview">HR Interview</option>
                    <option value="group_discussion">Group Discussion</option>
                    <option value="final_offer">Final Selection & Offer</option>
                    <option value="other">Other</option>
                  </select>
                </div>
              </div>

              {/* Final Round Checkbox */}
              <div className="p-3 bg-purple-50 dark:bg-purple-950/30 rounded-lg border border-purple-200 dark:border-purple-800/50">
                <label className="flex items-start space-x-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={isFinalRound}
                    onChange={(e) => setIsFinalRound(e.target.checked)}
                    className="mt-1 rounded text-purple-600 focus:ring-purple-500"
                  />
                  <div>
                    <span className="text-xs font-bold text-purple-900 dark:text-purple-200">
                      Final Recruitment Selection Round
                    </span>
                    <p className="text-[11px] text-purple-700 dark:text-purple-300 mt-0.5">
                      Check if this round determines final process selections. Confirmed students will have their application status set to SELECTED. Note: Official verified offers with CTC and offer letter attachments are verified separately under Verified Offers.
                    </p>
                  </div>
                </label>
              </div>

              {/* File upload input */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Upload Result File (.csv, .xlsx, .pdf, .jpg, .png) <span className="text-rose-500">*</span>
                </label>
                <input
                  type="file"
                  required
                  accept=".csv,.xlsx,.xls,.pdf,.docx,.png,.jpg,.jpeg"
                  onChange={(e) => setUploadFile(e.target.files[0] || null)}
                  className="w-full text-xs text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 dark:file:bg-indigo-950/50 dark:file:text-indigo-300"
                />
              </div>

              <div className="flex justify-end space-x-3 pt-3">
                <button
                  type="button"
                  onClick={() => setShowUploadModal(false)}
                  className="px-4 py-2 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 rounded-lg text-xs font-semibold hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isUploading}
                  className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center space-x-2 transition-colors"
                >
                  {isUploading ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Extracting & Matching...</span>
                    </>
                  ) : (
                    <>
                      <Upload className="w-3.5 h-3.5" />
                      <span>Process Result Sheet</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Results;
