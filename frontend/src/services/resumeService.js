import api from './api';

const resumeService = {
  /**
   * Upload a resume file
   * @param {File} file - Resume file (PDF, DOCX, JPG, PNG)
   * @param {number} studentId - Student ID (optional for placement officers)
   */
  uploadResume: async (file, studentId = null) => {
    const formData = new FormData();
    formData.append('file', file);
    
    let url = '/resume/upload';
    if (studentId) {
      url += `?student_id=${studentId}`;
    }
    
    const response = await api.post(url, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  /**
   * Get all resumes with filters
   */
  getResumes: async (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.studentId) params.append('student_id', filters.studentId);
    if (filters.status) params.append('status', filters.status);
    if (filters.minScore) params.append('min_ats_score', filters.minScore);
    if (filters.maxScore) params.append('max_ats_score', filters.maxScore);
    if (filters.limit) params.append('limit', filters.limit);
    if (filters.offset) params.append('offset', filters.offset);
    
    const response = await api.get(`/resume/?${params.toString()}`);
    return response.data;
  },

  /**
   * Get resume by ID
   */
  getResume: async (resumeId) => {
    const response = await api.get(`/resume/${resumeId}`);
    return response.data;
  },

  /**
   * Get ATS score for a resume
   */
  getAtsScore: async (resumeId) => {
    const response = await api.get(`/resume/${resumeId}/score`);
    return response.data;
  },

  /**
   * Get suggestions for a resume
   */
  getSuggestions: async (resumeId) => {
    const response = await api.get(`/resume/${resumeId}/suggestions`);
    return response.data;
  },

  /**
   * Update resume data
   */
  updateResume: async (resumeId, data) => {
    const response = await api.patch(`/resume/${resumeId}`, data);
    return response.data;
  },

  /**
   * Delete resume
   */
  deleteResume: async (resumeId) => {
    const response = await api.delete(`/resume/${resumeId}`);
    return response.data;
  },

  /**
   * Compare multiple resumes
   */
  compareResumes: async (resumeIds) => {
    const response = await api.post('/resume/compare', resumeIds);
    return response.data;
  },

  /**
   * Export resume data
   */
  exportResume: async (resumeId, format = 'json') => {
    const response = await api.get(`/resume/${resumeId}/export?format=${format}`, {
      responseType: 'blob',
    });
    return response.data;
  },
};

export default resumeService;