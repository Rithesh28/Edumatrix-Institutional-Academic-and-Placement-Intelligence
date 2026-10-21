/**
 * Placement Service - API calls for placement management
 */

import api, { API_URL } from './api';

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

export const bulkDeleteCompanies = async (companyIds, mode = 'soft') => {
  const response = await api.post('/placement/companies/bulk-delete', {
    company_ids: companyIds,
    mode,
  });
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

export const bulkDeleteJobs = async (jobIds, force = false) => {
  const response = await api.post('/placement/jobs/bulk-delete', {
    job_ids: jobIds,
    force,
  });
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

export const uploadJdFiles = async (files) => {
  const formData = new FormData();
  if (Array.isArray(files)) {
    files.forEach((f) => formData.append('files', f));
  } else if (files) {
    formData.append('files', files);
  }
  const response = await api.post('/placement/jobs/upload-jd', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const uploadJdFile = async (file) => {
  return uploadJdFiles([file]);
};

export const getStoredAuthToken = () => {
  try {
    const auth = localStorage.getItem('auth-storage');
    if (auth) {
      const parsed = JSON.parse(auth);
      if (parsed.state?.token) return parsed.state.token;
    }
  } catch (_) {}
  return localStorage.getItem('token') || localStorage.getItem('access_token') || '';
};

export const downloadFileBlob = async (url, fallbackFilename) => {
  try {
    const response = await api.get(url, { responseType: 'blob' });
    
    // Check if the response is actually an error JSON returned as a blob
    const contentType = response.headers['content-type'] || '';
    if (contentType.includes('application/json')) {
      let errorMsg = 'Failed to download file';
      try {
        const text = await response.data.text();
        const json = JSON.parse(text);
        if (json.detail) errorMsg = json.detail;
      } catch (_) {}
      throw new Error(errorMsg);
    }

    if (!response.data || (response.data instanceof Blob && response.data.size === 0)) {
      throw new Error('Downloaded file is empty or missing from storage');
    }

    // Extract genuine filename from Content-Disposition header if available
    let downloadName = fallbackFilename;
    const disposition = response.headers['content-disposition'];
    if (disposition) {
      const utf8Match = disposition.match(/filename\*=UTF-8''([^;\n]*)/i);
      if (utf8Match && utf8Match[1]) {
        try {
          downloadName = decodeURIComponent(utf8Match[1]);
        } catch (_) {}
      } else {
        const standardMatch = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (standardMatch && standardMatch[1]) {
          downloadName = standardMatch[1].replace(/['"]/g, '').trim();
        }
      }
    }

    // Default clean filename fallback
    if (!downloadName || downloadName === 'Attached Document' || downloadName === 'download') {
      const ext = contentType.includes('pdf') ? '.pdf' : contentType.includes('jpeg') ? '.jpg' : contentType.includes('png') ? '.png' : '';
      downloadName = `document_${Date.now()}${ext}`;
    }

    const blob = new Blob([response.data], { type: contentType || 'application/octet-stream' });
    const blobUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = blobUrl;
    link.setAttribute('download', downloadName);
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => window.URL.revokeObjectURL(blobUrl), 2000);
    return downloadName;
  } catch (err) {
    let errorDetail = err.message || 'Authenticated download failed';
    if (err.response?.data instanceof Blob) {
      try {
        const text = await err.response.data.text();
        const json = JSON.parse(text);
        if (json.detail) errorDetail = json.detail;
      } catch (_) {}
    } else if (err.response?.data?.detail) {
      errorDetail = err.response.data.detail;
    }
    const cleanErr = new Error(errorDetail);
    cleanErr.status = err.response?.status;
    console.error('Authenticated download failed:', errorDetail);
    throw cleanErr;
  }
};

export const previewFileBlob = async (url) => {
  try {
    const response = await api.get(url, { responseType: 'blob' });
    const contentType = response.headers['content-type'] || '';

    // Check if response is error JSON disguised as blob
    if (contentType.includes('application/json')) {
      let errorMsg = 'Failed to preview file';
      try {
        const text = await response.data.text();
        const json = JSON.parse(text);
        if (json.detail) errorMsg = json.detail;
      } catch (_) {}
      throw new Error(errorMsg);
    }

    if (!response.data || (response.data instanceof Blob && response.data.size === 0)) {
      throw new Error('File content is empty or unavailable in storage');
    }

    // If file is not previewable in browser, trigger download instead
    const isPreviewable = (
      contentType.includes('pdf') ||
      contentType.startsWith('image/') ||
      contentType.startsWith('text/')
    );

    if (!isPreviewable) {
      return await downloadFileBlob(url);
    }

    const blob = new Blob([response.data], { type: contentType || 'application/pdf' });
    const blobUrl = window.URL.createObjectURL(blob);
    window.open(blobUrl, '_blank', 'noopener,noreferrer');
    setTimeout(() => window.URL.revokeObjectURL(blobUrl), 60000);
  } catch (err) {
    let errorDetail = err.message || 'Authenticated preview failed';
    if (err.response?.data instanceof Blob) {
      try {
        const text = await err.response.data.text();
        const json = JSON.parse(text);
        if (json.detail) errorDetail = json.detail;
      } catch (_) {}
    } else if (err.response?.data?.detail) {
      errorDetail = err.response.data.detail;
    }
    const cleanErr = new Error(errorDetail);
    cleanErr.status = err.response?.status;
    console.error('Authenticated preview failed:', errorDetail);
    throw cleanErr;
  }
};

export const downloadJobFileAuth = async (jobId, fileId, filename) => {
  return downloadFileBlob(`/placement/jobs/${jobId}/files/${fileId}/download`, filename);
};

export const previewJobFileAuth = async (jobId, fileId) => {
  return previewFileBlob(`/placement/jobs/${jobId}/files/${fileId}/preview`);
};

export const getJobFileDownloadUrl = (jobId, fileId) => {
  const token = getStoredAuthToken();
  const base = `${API_URL}/placement/jobs/${jobId}/files/${fileId}/download`;
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
};

export const getJobFilePreviewUrl = (jobId, fileId) => {
  const token = getStoredAuthToken();
  const base = `${API_URL}/placement/jobs/${jobId}/files/${fileId}/preview`;
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
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

export const getPlacementStats = async (params = {}) => {
  const response = await api.get('/placement/stats', { params });
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

export const downloadCircularAttachmentAuth = async (circularId, attachmentId, filename) => {
  return downloadFileBlob(`/placement/circulars/${circularId}/attachments/${attachmentId}/download`, filename);
};

export const previewCircularAttachmentAuth = async (circularId, attachmentId) => {
  return previewFileBlob(`/placement/circulars/${circularId}/attachments/${attachmentId}/preview`);
};

export const getCircularAttachmentDownloadUrl = (circularId, attachmentId) => {
  const token = getStoredAuthToken();
  const base = `${API_URL}/placement/circulars/${circularId}/attachments/${attachmentId}/download`;
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
};

export const getCircularAttachmentPreviewUrl = (circularId, attachmentId) => {
  const token = getStoredAuthToken();
  const base = `${API_URL}/placement/circulars/${circularId}/attachments/${attachmentId}/preview`;
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
};

export const parseShortlist = async (formData) => {
  const response = await api.post('/placement/circulars/parse-shortlist', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const createAndPostDrive = async (data) => {
  const response = await api.post('/placement/circulars/create-and-post-drive', data);
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

