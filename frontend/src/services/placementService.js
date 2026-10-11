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