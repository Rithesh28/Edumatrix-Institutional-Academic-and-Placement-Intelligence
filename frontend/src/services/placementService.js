/**
 * Placement Service - API calls for placement management
 */

import api from './api';

// ============================================
// COMPANY ENDPOINTS
// ============================================

export const createCompany = async (data) => {
  const response = await api.post('/placement/companies', data);
  return response.data;
};

export const getCompanies = async (params = {}) => {
  const response = await api.get('/placement/companies', { params });
  return response.data;
};

export const getCompany = async (id) => {
  const response = await api.get(`/placement/companies/${id}`);
  return response.data;
};

export const updateCompany = async (id, data) => {
  const response = await api.put(`/placement/companies/${id}`, data);
  return response.data;
};

export const deleteCompany = async (id) => {
  const response = await api.delete(`/placement/companies/${id}`);
  return response.data;
};

// ============================================
// JOB POSTING ENDPOINTS
// ============================================

export const createJobPosting = async (data) => {
  const response = await api.post('/placement/jobs', data);
  return response.data;
};

export const getJobPostings = async (params = {}) => {
  const response = await api.get('/placement/jobs', { params });
  return response.data;
};

export const getJobPosting = async (id) => {
  const response = await api.get(`/placement/jobs/${id}`);
  return response.data;
};

export const updateJobPosting = async (id, data) => {
  const response = await api.put(`/placement/jobs/${id}`, data);
  return response.data;
};

export const deleteJobPosting = async (id) => {
  const response = await api.delete(`/placement/jobs/${id}`);
  return response.data;
};

export const publishJobPosting = async (id, confirmNoSkills = false) => {
  const response = await api.post(`/placement/jobs/${id}/publish`, null, {
    params: { confirm_no_skills: confirmNoSkills }
  });
  return response.data;
};

export const parseJdText = async (text) => {
  const response = await api.post('/placement/jobs/parse-jd', { text });
  return response.data;
};

export const uploadJdFile = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await api.post('/placement/jobs/upload-jd', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

// ============================================
// APPLICATION ENDPOINTS
// ============================================

export const createApplication = async (data) => {
  const response = await api.post('/placement/applications', data);
  return response.data;
};

export const getApplications = async (params = {}) => {
  const response = await api.get('/placement/applications', { params });
  return response.data;
};

export const getApplication = async (id) => {
  const response = await api.get(`/placement/applications/${id}`);
  return response.data;
};

export const updateApplication = async (id, data) => {
  const response = await api.put(`/placement/applications/${id}`, data);
  return response.data;
};

export const confirmExternalApplication = async (id) => {
  const response = await api.post(`/placement/applications/${id}/confirm-external`);
  return response.data;
};

export const confirmExternalJobApplication = async (jobId) => {
  const response = await api.post(`/placement/jobs/${jobId}/confirm-external`);
  return response.data;
};

// ============================================
// SHORTLIST ENDPOINTS
// ============================================

export const createShortlist = async (data) => {
  const response = await api.post('/placement/shortlist', data);
  return response.data;
};

export const getShortlists = async (params = {}) => {
  const response = await api.get('/placement/shortlist', { params });
  return response.data;
};

export const removeFromShortlist = async (id) => {
  const response = await api.delete(`/placement/shortlist/${id}`);
  return response.data;
};

// ============================================
// STUDENT ENDPOINTS - ADDED
// ============================================

export const getStudents = async (params = {}) => {
  const response = await api.get('/placement/students', { params });
  return response.data;
};

export const getStudent = async (id) => {
  const response = await api.get(`/placement/students/${id}`);
  return response.data;
};

// ============================================
// MATCHING ENDPOINTS
// ============================================

export const matchStudentsForJob = async (data) => {
  const response = await api.post('/placement/match', data);
  return response.data;
};

export const checkStudentEligibility = async (jobId, studentId) => {
  const response = await api.get(`/placement/jobs/${jobId}/check-eligibility/${studentId}`);
  return response.data;
};

// ============================================
// STATISTICS ENDPOINTS
// ============================================

export const getPlacementStats = async () => {
  const response = await api.get('/placement/stats');
  return response.data;
};

export const getCompanyStats = async (companyId) => {
  const response = await api.get(`/placement/companies/${companyId}/stats`);
  return response.data;
};

export const getStudentPlacementStatus = async (studentId) => {
  const response = await api.get(`/placement/students/${studentId}/placement-status`);
  return response.data;
};

// ============================================
// RECRUITMENT CIRCULAR ENDPOINTS
// ============================================

export const getRecruitmentCirculars = async (params = {}) => {
  const response = await api.get('/placement/circulars', { params });
  return response.data;
};

export const getRecruitmentCircular = async (id) => {
  const response = await api.get(`/placement/circulars/${id}`);
  return response.data;
};

export const createRecruitmentCircular = async (data) => {
  const response = await api.post('/placement/circulars', data);
  return response.data;
};

export const updateRecruitmentCircular = async (id, data) => {
  const response = await api.put(`/placement/circulars/${id}`, data);
  return response.data;
};

export const publishRecruitmentCircular = async (id, params = {}) => {
  const response = await api.post(`/placement/circulars/${id}/publish`, null, { params });
  return response.data;
};

export const archiveRecruitmentCircular = async (id) => {
  const response = await api.post(`/placement/circulars/${id}/archive`);
  return response.data;
};

export const addCircularAttachment = async (circularId, data) => {
  const response = await api.post(`/placement/circulars/${circularId}/attachments`, data);
  return response.data;
};

export const removeCircularAttachment = async (circularId, attachmentId) => {
  const response = await api.delete(`/placement/circulars/${circularId}/attachments/${attachmentId}`);
  return response.data;
};

export const linkCircularJobs = async (circularId, data) => {
  const response = await api.post(`/placement/circulars/${circularId}/jobs`, data);
  return response.data;
};

export const unlinkCircularJob = async (circularId, jobPostingId) => {
  const response = await api.delete(`/placement/circulars/${circularId}/jobs/${jobPostingId}`);
  return response.data;
};

// ============================================
// RECRUITMENT RESULT ENDPOINTS (STAGE 3.2)
// ============================================

export const uploadResultFile = async (formData) => {
  const response = await api.post('/placement/results/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const getResultBatches = async (params = {}) => {
  const response = await api.get('/placement/results/batches', { params });
  return response.data;
};

export const getResultBatch = async (id) => {
  const response = await api.get(`/placement/results/batches/${id}`);
  return response.data;
};

export const updateResultItemMatch = async (itemId, data) => {
  const response = await api.put(`/placement/results/items/${itemId}/match`, data);
  return response.data;
};

export const confirmResultBatch = async (batchId, data = {}) => {
  const response = await api.post(`/placement/results/batches/${batchId}/confirm`, data);
  return response.data;
};

export const searchStudentsForMatching = async (query) => {
  const response = await api.get('/placement/results/students/search', {
    params: { q: query },
  });
  return response.data;
};

// ============================================
// RECRUITMENT ROUNDS & PROGRESSION ENDPOINTS (STAGE 3.3.5)
// ============================================

export const getJobRounds = async (jobId) => {
  const response = await api.get(`/placement/jobs/${jobId}/rounds`);
  return response.data;
};

export const createJobRound = async (jobId, data) => {
  const response = await api.post(`/placement/jobs/${jobId}/rounds`, data);
  return response.data;
};

export const getRoundDetails = async (roundId) => {
  const response = await api.get(`/placement/rounds/${roundId}`);
  return response.data;
};

export const getRoundOutcomes = async (roundId, params = {}) => {
  const response = await api.get(`/placement/rounds/${roundId}/outcomes`, { params });
  return response.data;
};

export const getStudentProgression = async (studentId, params = {}) => {
  const response = await api.get(`/placement/students/${studentId}/progression`, { params });
  return response.data;
};

export const correctRoundOutcome = async (outcomeId, data) => {
  const response = await api.post(`/placement/outcomes/${outcomeId}/correct`, data);
  return response.data;
};

export const linkBatchToRound = async (batchId, roundId) => {
  const response = await api.post(`/placement/results/batches/${batchId}/link-round`, null, {
    params: { round_id: roundId },
  });
  return response.data;
};

// ============================================
// VERIFIED PLACEMENT OFFER ENDPOINTS (STAGE 3.3.4 / 3.3.5)
// ============================================

export const getVerifiedOffers = async (params = {}) => {
  const response = await api.get('/placement/offers', { params });
  return response.data;
};

export const getOfferDetails = async (offerId) => {
  const response = await api.get(`/placement/offers/${offerId}`);
  return response.data;
};

export const createVerifiedOffer = async (data) => {
  const response = await api.post('/placement/offers', data);
  return response.data;
};

export const updateVerifiedOffer = async (offerId, data) => {
  const response = await api.put(`/placement/offers/${offerId}`, data);
  return response.data;
};

export const rescindVerifiedOffer = async (offerId, data) => {
  const response = await api.post(`/placement/offers/${offerId}/rescind`, data);
  return response.data;
};

export const getPlacementAccounting = async () => {
  const response = await api.get('/placement/accounting');
  return response.data;
};

// Student-Specific Offer Endpoints (Stage 3.3.6)
export const getMyOffers = async () => {
  const response = await api.get('/placement/offers/my-offers');
  return response.data;
};

export const respondToOffer = async (offerId, data) => {
  const response = await api.post(`/placement/offers/${offerId}/respond`, data);
  return response.data;
};

// Drive Placement Report (Stage 3.4.3)
export const getCircularDriveReport = async (circularId) => {
  const response = await api.get(`/placement/circulars/${circularId}/report`);
  return response.data;
};

// ============================================
// SAFE TEST DATA CLEANUP ENDPOINTS (STAGE 3.4.1 / 3.4.5)
// ============================================

export const getCleanupPreview = async (params = {}) => {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value.forEach((v) => searchParams.append(key, v));
    } else if (value !== undefined && value !== null) {
      searchParams.append(key, value);
    }
  });
  const response = await api.get('/placement/cleanup/preview', { params: searchParams });
  return response.data;
};

export const getDrivesCleanupPreview = async (params = {}) => {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value.forEach((v) => searchParams.append(key, v));
    } else if (value !== undefined && value !== null) {
      searchParams.append(key, value);
    }
  });
  const response = await api.get('/placement/cleanup/drives/preview', { params: searchParams });
  return response.data;
};

export const getJobsCleanupPreview = async (params = {}) => {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value.forEach((v) => searchParams.append(key, v));
    } else if (value !== undefined && value !== null) {
      searchParams.append(key, value);
    }
  });
  const response = await api.get('/placement/cleanup/jobs/preview', { params: searchParams });
  return response.data;
};

export const executeCleanup = async (data) => {
  const response = await api.post('/placement/cleanup/execute', data);
  return response.data;
};

