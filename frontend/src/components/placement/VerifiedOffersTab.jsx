import React, { useState, useEffect } from 'react';
import {
  Award,
  Plus,
  DollarSign,
  Calendar,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  FileText,
  User,
  X,
  ShieldAlert,
  Edit2,
  ExternalLink,
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import toast from 'react-hot-toast';

export default function VerifiedOffersTab({ jobId, jobTitle, companyName, applications = [] }) {
  const {
    verifiedOffers,
    isOffersLoading,
    fetchVerifiedOffers,
    createVerifiedOffer,
    updateVerifiedOffer,
    rescindVerifiedOffer,
  } = usePlacementStore();

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Create Form State
  const [selectedApplicationId, setSelectedApplicationId] = useState('');
  const [designation, setDesignation] = useState('');
  const [ctcLpa, setCtcLpa] = useState('');
  const [offerDate, setOfferDate] = useState('');
  const [offerLetterFileId, setOfferLetterFileId] = useState('');

  // Rescind Modal State
  const [rescindTarget, setRescindTarget] = useState(null);
  const [rescindReason, setRescindReason] = useState('');
  const [isRescinding, setIsRescinding] = useState(false);

  // Edit Terms Modal State
  const [editTarget, setEditTarget] = useState(null);
  const [editDesignation, setEditDesignation] = useState('');
  const [editCtcLpa, setEditCtcLpa] = useState('');
  const [editReason, setEditReason] = useState('');
  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    if (jobId) {
      fetchVerifiedOffers({ job_posting_id: jobId }).catch((err) => {
        toast.error('Failed to load verified placement offers.');
      });
    }
  }, [jobId]);

  // Offers that belong to this job posting
  const jobOffers = (verifiedOffers || []).filter((o) => o.job_posting_id === parseInt(jobId, 10));

  // Eligible applications: candidates who don't already have an offer for this job
  const existingOfferAppIds = new Set(jobOffers.map((o) => o.application_id));
  const availableApplications = (applications || []).filter(
    (app) => !existingOfferAppIds.has(app.id)
  );

  const openCreateModal = () => {
    setSelectedApplicationId(availableApplications[0]?.id ? String(availableApplications[0].id) : '');
    setDesignation(jobTitle || 'Associate Software Engineer');
    setCtcLpa('');
    setOfferDate(new Date().toISOString().split('T')[0]);
    setOfferLetterFileId('');
    setShowCreateModal(true);
  };

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    const appId = parseInt(selectedApplicationId, 10);
    if (!appId) {
      toast.error('Please select an applicant.');
      return;
    }
    const ctc = parseFloat(ctcLpa);
    if (isNaN(ctc) || ctc <= 0) {
      toast.error('Annual CTC must be a positive number greater than 0 LPA.');
      return;
    }
    if (!designation.trim()) {
      toast.error('Please enter the offered designation.');
      return;
    }

    setIsSubmitting(true);
    try {
      await createVerifiedOffer({
        application_id: appId,
        job_posting_id: parseInt(jobId, 10),
        designation: designation.trim(),
        ctc_lpa: ctc,
        offer_date: offerDate ? new Date(offerDate).toISOString() : null,
        offer_letter_file_id: offerLetterFileId.trim() || null,
      });
      toast.success('Verified placement offer issued successfully!');
      setShowCreateModal(false);
      fetchVerifiedOffers({ job_posting_id: jobId });
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to issue verified offer.';
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRescindSubmit = async (e) => {
    e.preventDefault();
    if (!rescindTarget) return;
    if (!rescindReason.trim() || rescindReason.trim().length < 3) {
      toast.error('Please provide a substantive administrative reason for rescinding this offer.');
      return;
    }

    setIsRescinding(true);
    try {
      await rescindVerifiedOffer(rescindTarget.id, {
        reason: rescindReason.trim(),
      });
      toast.success(`Offer #${rescindTarget.id} rescinded successfully.`);
      setRescindTarget(null);
      setRescindReason('');
      fetchVerifiedOffers({ job_posting_id: jobId });
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to rescind offer.';
      toast.error(msg);
    } finally {
      setIsRescinding(false);
    }
  };

  const openEditModal = (offer) => {
    setEditTarget(offer);
    setEditDesignation(offer.designation || '');
    setEditCtcLpa(offer.ctc_lpa !== null ? String(offer.ctc_lpa) : '');
    setEditReason('');
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!editTarget) return;
    const ctc = parseFloat(editCtcLpa);
    if (isNaN(ctc) || ctc <= 0) {
      toast.error('Annual CTC must be greater than 0 LPA.');
      return;
    }

    setIsEditing(true);
    try {
      await updateVerifiedOffer(editTarget.id, {
        designation: editDesignation.trim(),
        ctc_lpa: ctc,
        reason: editReason.trim() || 'Terms updated by Placement Officer',
      });
      toast.success('Offer terms updated successfully.');
      setEditTarget(null);
      fetchVerifiedOffers({ job_posting_id: jobId });
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to update offer.';
      toast.error(msg);
    } finally {
      setIsEditing(false);
    }
  };

  const getStatusBadge = (status) => {
    switch (status?.toLowerCase()) {
      case 'offered':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
            <Clock className="w-3.5 h-3.5" />
            PENDING RESPONSE
          </span>
        );
      case 'accepted':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
            <CheckCircle2 className="w-3.5 h-3.5" />
            ACCEPTED BY STUDENT
          </span>
        );
      case 'declined':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 dark:bg-rose-950/60 text-rose-800 dark:text-rose-300 border border-rose-200 dark:border-rose-800">
            <XCircle className="w-3.5 h-3.5" />
            DECLINED BY STUDENT
          </span>
        );
      case 'rescinded':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
            <AlertTriangle className="w-3.5 h-3.5" />
            RESCINDED
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-700">
            {status?.toUpperCase()}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-5 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-xs">
        <div>
          <div className="flex items-center space-x-2">
            <Award className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
            <h2 className="text-lg font-bold text-gray-900 dark:text-white">
              Verified Placement Offers ({jobOffers.length})
            </h2>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Institutional offer records verified by the Placement Officer. Offers remain distinct from interview round clearances.
          </p>
        </div>

        <button
          onClick={openCreateModal}
          disabled={availableApplications.length === 0}
          title={
            availableApplications.length === 0
              ? 'All current applicants already have an offer or no applicants submitted'
              : 'Issue verified offer'
          }
          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center space-x-2 shadow-sm transition-colors cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>Verify & Issue Offer</span>
        </button>
      </div>

      {/* Offers Cards / List */}
      {isOffersLoading && jobOffers.length === 0 ? (
        <div className="flex justify-center items-center h-48 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-emerald-600 border-t-transparent" />
        </div>
      ) : jobOffers.length === 0 ? (
        <div className="text-center py-12 bg-white dark:bg-gray-900 rounded-xl border border-dashed border-gray-200 dark:border-gray-800 p-6">
          <Award className="w-10 h-10 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
            No Verified Placement Offers Issued
          </h3>
          <p className="text-xs text-gray-500 dark:text-gray-400 max-w-md mx-auto mt-1 mb-4">
            Passing recruitment rounds marks candidates as SELECTED, but does not count as a verified institutional placement until an offer is formally verified.
          </p>
          {availableApplications.length > 0 && (
            <button
              onClick={openCreateModal}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors cursor-pointer"
            >
              Issue First Offer
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-3.5">
          {jobOffers.map((offer) => (
            <div
              key={offer.id}
              className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5 shadow-xs hover:border-emerald-300 dark:hover:border-emerald-700 transition-colors"
            >
              <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
                <div className="flex items-start space-x-3.5">
                  <div className="w-10 h-10 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-100 dark:border-emerald-900 flex items-center justify-center shrink-0">
                    <Award className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                  </div>

                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-bold text-gray-900 dark:text-white text-base">
                        {offer.student_name || `Student #${offer.student_id}`}
                      </h3>
                      {getStatusBadge(offer.acceptance_status)}
                    </div>

                    <p className="text-xs text-gray-600 dark:text-gray-300 mt-1">
                      Role: <strong className="text-gray-900 dark:text-white">{offer.designation || 'Not specified'}</strong> •{' '}
                      Compensation: <strong className="text-emerald-600 dark:text-emerald-400">{offer.ctc_lpa ? `${offer.ctc_lpa} LPA` : 'TBD'}</strong>
                    </p>

                    <div className="flex flex-wrap items-center gap-4 text-xs text-gray-500 dark:text-gray-400 mt-2">
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5 text-gray-400" />
                        Offer Date: {offer.offer_date ? new Date(offer.offer_date).toLocaleDateString() : 'N/A'}
                      </span>
                      {offer.response_date && (
                        <span className="flex items-center gap-1">
                          <Clock className="w-3.5 h-3.5 text-gray-400" />
                          Response Date: {new Date(offer.response_date).toLocaleDateString()}
                        </span>
                      )}
                      {offer.offer_letter_file_id && (
                        <a
                          href={`/api/v1/files/${offer.offer_letter_file_id}/download`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 text-indigo-600 dark:text-indigo-400 hover:underline font-medium"
                        >
                          <FileText className="w-3.5 h-3.5" />
                          <span>View Offer Letter</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2.5 self-end lg:self-center">
                  {offer.acceptance_status !== 'rescinded' && (
                    <>
                      <button
                        onClick={() => openEditModal(offer)}
                        className="px-3 py-1.5 text-xs font-semibold bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 rounded-lg transition-colors cursor-pointer flex items-center gap-1"
                      >
                        <Edit2 className="w-3 h-3" />
                        <span>Edit Terms</span>
                      </button>

                      <button
                        onClick={() => setRescindTarget(offer)}
                        className="px-3 py-1.5 text-xs font-semibold bg-rose-50 dark:bg-rose-950/50 hover:bg-rose-100 dark:hover:bg-rose-900 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800 rounded-lg transition-colors cursor-pointer flex items-center gap-1"
                      >
                        <ShieldAlert className="w-3 h-3" />
                        <span>Rescind Offer</span>
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Verified Offer Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-md w-full p-6 shadow-xl border border-gray-200 dark:border-gray-800">
            <div className="flex items-center justify-between pb-4 border-b border-gray-100 dark:border-gray-800">
              <div className="flex items-center space-x-2">
                <Award className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                <h3 className="text-base font-bold text-gray-900 dark:text-white">
                  Verify & Issue Placement Offer
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
                  Candidate / Application *
                </label>
                <select
                  required
                  value={selectedApplicationId}
                  onChange={(e) => setSelectedApplicationId(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                >
                  <option value="" disabled>Select a candidate</option>
                  {availableApplications.map((app) => (
                    <option key={app.id} value={app.id}>
                      {app.student_name} ({app.student_email}) — Status: {app.status?.toUpperCase()}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Designation / Role *
                </label>
                <input
                  type="text"
                  required
                  value={designation}
                  onChange={(e) => setDesignation(e.target.value)}
                  placeholder="e.g. Associate Software Engineer"
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                    CTC (LPA) *
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.1"
                    required
                    value={ctcLpa}
                    onChange={(e) => setCtcLpa(e.target.value)}
                    placeholder="e.g. 14.5"
                    className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                    Offer Date
                  </label>
                  <input
                    type="date"
                    value={offerDate}
                    onChange={(e) => setOfferDate(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Offer Letter File UUID (Optional)
                </label>
                <input
                  type="text"
                  value={offerLetterFileId}
                  onChange={(e) => setOfferLetterFileId(e.target.value)}
                  placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
                  className="w-full px-3 py-2 text-xs font-mono border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                />
                <p className="text-[11px] text-gray-400 mt-0.5">
                  Attached file from File Manager. Student will be granted access to download.
                </p>
              </div>

              <div className="p-3 bg-emerald-50/50 dark:bg-emerald-950/20 rounded-xl border border-emerald-100 dark:border-emerald-900/40 text-xs text-emerald-800 dark:text-emerald-300">
                ℹ️ The offer will be issued in <strong>OFFERED</strong> state. The candidate can securely review, accept, or decline from their student dashboard.
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
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer flex items-center gap-1.5"
                >
                  {isSubmitting ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Issuing...</span>
                    </>
                  ) : (
                    <span>Issue Verified Offer</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Rescind Offer Confirmation Modal */}
      {rescindTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-md w-full p-6 shadow-xl border border-gray-200 dark:border-gray-800">
            <div className="flex items-center space-x-3 text-rose-600 mb-3">
              <ShieldAlert className="w-6 h-6" />
              <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                Rescind Placement Offer #{rescindTarget.id}
              </h3>
            </div>

            <p className="text-xs text-gray-600 dark:text-gray-300">
              Are you sure you want to rescind the offer for <strong>{rescindTarget.student_name}</strong> ({rescindTarget.designation})?
            </p>

            <div className="mt-3 p-3 bg-rose-50 dark:bg-rose-950/30 rounded-xl border border-rose-200 dark:border-rose-800 text-xs text-rose-800 dark:text-rose-300">
              ⚠️ In accordance with placement accounting rules, rescinding will revoke the offer. If the student previously accepted this offer, their profile placement status will automatically revert if they have no other active accepted offers.
            </div>

            <form onSubmit={handleRescindSubmit} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Mandatory Audit Reason *
                </label>
                <textarea
                  required
                  minLength={3}
                  rows={3}
                  value={rescindReason}
                  onChange={(e) => setRescindReason(e.target.value)}
                  placeholder="e.g. Employer cancelled project head-count / Candidate failed eligibility verification."
                  className="w-full px-3 py-2 text-xs border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-rose-500 focus:outline-none"
                />
              </div>

              <div className="flex justify-end space-x-2.5">
                <button
                  type="button"
                  onClick={() => setRescindTarget(null)}
                  className="px-4 py-2 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg text-xs font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isRescinding}
                  className="px-4 py-2 bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer flex items-center gap-1.5"
                >
                  {isRescinding ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Rescinding...</span>
                    </>
                  ) : (
                    <span>Confirm Rescission</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Terms Modal */}
      {editTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-md w-full p-6 shadow-xl border border-gray-200 dark:border-gray-800">
            <div className="flex items-center justify-between pb-4 border-b border-gray-100 dark:border-gray-800">
              <h3 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
                <Edit2 className="w-4 h-4 text-indigo-600" />
                <span>Edit Offer Terms #{editTarget.id}</span>
              </h3>
              <button
                onClick={() => setEditTarget(null)}
                className="text-gray-400 hover:text-gray-600 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleEditSubmit} className="space-y-4 mt-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Designation
                </label>
                <input
                  type="text"
                  value={editDesignation}
                  onChange={(e) => setEditDesignation(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Annual CTC (LPA)
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0.1"
                  value={editCtcLpa}
                  onChange={(e) => setEditCtcLpa(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Mandatory Modification Audit Reason *
                </label>
                <textarea
                  required
                  rows={2}
                  value={editReason}
                  onChange={(e) => setEditReason(e.target.value)}
                  placeholder="e.g. Revised compensation based on updated company confirmation email."
                  className="w-full px-3 py-2 text-xs border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
              </div>

              <div className="flex justify-end space-x-2.5">
                <button
                  type="button"
                  onClick={() => setEditTarget(null)}
                  className="px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-lg text-xs font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isEditing}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5"
                >
                  {isEditing ? 'Saving...' : 'Save Terms'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
