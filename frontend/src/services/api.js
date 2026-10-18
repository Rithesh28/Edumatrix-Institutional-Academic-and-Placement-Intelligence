import axios from 'axios'

export const API_URL = import.meta.env.VITE_API_URL || 'http://172.16.30.71:8000'

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor to add token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth-storage')
    if (token) {
      try {
        const parsed = JSON.parse(token)
        if (parsed.state?.token) {
          config.headers.Authorization = `Bearer ${parsed.state.token}`
        }
      } catch (e) {
        // Invalid JSON in localStorage
      }
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor to handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth-storage')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// ============================================
// CHAT API
// ============================================
export const chatAPI = {
  getConversations: () => api.get('/chat/conversations'),
  getMessages: (userId) => api.get(`/chat/messages/${userId}`),
  sendMessage: (receiver_id, content) => api.post('/chat/send', { receiver_id, content }),
  getAllUsers: () => api.get('/chat/users'),
  // AI Assistant — dedicated endpoint with full grounding metadata
  chatAI: (content) => api.post('/chat/ai', { content }),
}

// ============================================
// STUDY BUDDY RAG API
// ============================================
export const studyBuddyAPI = {
  getSubjects: (params = {}) => api.get('/study-buddy/subjects', { params }),
  createSubject: (payload) => api.post('/study-buddy/subjects', payload),
  updateSubject: (subjectId, payload) => api.put(`/study-buddy/subjects/${subjectId}`, payload),
  deleteSubject: (subjectId) => api.delete(`/study-buddy/subjects/${subjectId}`),
  getSyllabusDetail: (documentId) => api.get(`/study-buddy/syllabi/${documentId}`),
  askQuestion: (question, subjectId = null, sourceMode = 'syllabus', attachedDocumentId = null) => api.post('/study-buddy/chat', { question, subject_id: subjectId, source_mode: sourceMode, attached_document_id: attachedDocumentId }),
  searchSyllabus: (query, subjectId = null, sourceMode = 'syllabus') => api.get('/study-buddy/search', { params: { query, subject_id: subjectId, source_mode: sourceMode } }),
  generateSummary: (payload) => api.post('/study-buddy/summaries/generate', payload),
  generateQuiz: (payload) => api.post('/study-buddy/quizzes/generate', payload),
  submitQuiz: (attemptId, answers) => api.post(`/study-buddy/quizzes/attempts/${attemptId}/submit`, { answers }),
  getQuizAttempts: (subjectId = null) => api.get('/study-buddy/quizzes/attempts', { params: subjectId ? { subject_id: subjectId } : {} }),
  getQuizResult: (attemptId) => api.get(`/study-buddy/quizzes/attempts/${attemptId}`),
  // Step 4.5: Progress Dashboard & Adaptive Planner
  getDashboardProgress: () => api.get('/study-buddy/progress/dashboard'),
  createPlan: (payload) => api.post('/study-buddy/plans', payload),
  getPlans: (subjectId = null, status = null) => api.get('/study-buddy/plans', { params: { ...(subjectId ? { subject_id: subjectId } : {}), ...(status ? { status } : {}) } }),
  getPlanDetail: (planId) => api.get(`/study-buddy/plans/${planId}`),
  updatePlan: (planId, payload) => api.patch(`/study-buddy/plans/${planId}`, payload),
  updateTaskStatus: (planId, taskId, isCompleted) => api.patch(`/study-buddy/plans/${planId}/tasks/${taskId}`, { is_completed: isCompleted }),
  regeneratePlan: (planId) => api.post(`/study-buddy/plans/${planId}/regenerate`),
  // Step 4.6C & 4.6D: Lecture Notes Library & Secure Download
  getSubjectNotes: (subjectId, params = {}) => api.get(`/study-buddy/subjects/${subjectId}/notes`, { params }),
  getNoteDetail: (noteId) => api.get(`/study-buddy/notes/${noteId}`),
  uploadNote: (subjectId, formData, onUploadProgress) => api.post(`/study-buddy/subjects/${subjectId}/notes`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 0,
    onUploadProgress,
  }),
  updateNote: (noteId, payload) => api.patch(`/study-buddy/notes/${noteId}`, payload),
  deleteNote: (noteId) => api.delete(`/study-buddy/notes/${noteId}`),
  retryNoteProcessing: (noteId) => api.post(`/study-buddy/notes/${noteId}/retry`),
  downloadNote: (noteId, preview = false) => api.get(`/study-buddy/notes/${noteId}/download`, { params: preview ? { preview: true } : {}, responseType: 'blob' }),
  downloadNoteFile: (fileId) => api.get(`/files/${fileId}/download`, { responseType: 'blob' }),
  // Step 4.6H: Student Personal Study Documents
  getMyDocuments: (params = {}) => api.get('/study-buddy/my-documents', { params }),
  getMyDocumentDetail: (documentId) => api.get(`/study-buddy/my-documents/${documentId}`),
  uploadMyDocument: (formData, onUploadProgress) => api.post('/study-buddy/my-documents', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 0,
    onUploadProgress,
  }),
  updateMyDocument: (documentId, payload) => api.patch(`/study-buddy/my-documents/${documentId}`, payload),
  deleteMyDocument: (documentId) => api.delete(`/study-buddy/my-documents/${documentId}`),
  retryMyDocument: (documentId) => api.post(`/study-buddy/my-documents/${documentId}/retry`),
  downloadMyDocument: (documentId) => api.get(`/study-buddy/my-documents/${documentId}/download`, { responseType: 'blob' }),
}

// ============================================
// CIRCULARS API
// ============================================
export const circularAPI = {
  getAll: () => api.get('/circulars/'),
  getById: (id) => api.get(`/circulars/${id}`),
  getByType: (type) => api.get(`/circulars/type/${type}`),
  create: (data) => api.post('/circulars/', data),
  update: (id, data) => api.put(`/circulars/${id}`, data),
  delete: (id) => api.delete(`/circulars/${id}`),
}

// ============================================
// NOTIFICATIONS API
// ============================================
export const notificationAPI = {
  getAll: () => api.get('/notifications/'),
  getUnreadCount: () => api.get('/notifications/unread/count'),
  markAsRead: (id) => api.put(`/notifications/${id}/read`),
  markAllAsRead: () => api.put('/notifications/read-all'),
  delete: (id) => api.delete(`/notifications/${id}`),
}

// ============================================
// REMINDERS API (Part 1)
// ============================================
export const reminderAPI = {
  getAll: () => api.get('/reminders/'),
  getUnreadCount: () => api.get('/reminders/unread/count'),
  markAsRead: (id) => api.put(`/reminders/${id}/read`),
  markAllAsRead: () => api.put('/reminders/read-all'),
  delete: (id) => api.delete(`/reminders/${id}`),
  getStats: () => api.get('/reminders/stats'),
}

// ============================================
// PROFILE API (Part 2)
// ============================================
export const profileAPI = {
  getProfile: () => api.get('/profile/me'),
  updateProfile: (data) => api.put('/profile/me', data),
  uploadProfilePicture: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/profile/upload-picture', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  getSkills: () => api.get('/profile/skills'),
  addSkill: (data) => api.post('/profile/skills', data),
  updateSkill: (id, data) => api.put(`/profile/skills/${id}`, data),
  deleteSkill: (id) => api.delete(`/profile/skills/${id}`),
  getProjects: () => api.get('/profile/projects'),
  addProject: (data) => api.post('/profile/projects', data),
  updateProject: (id, data) => api.put(`/profile/projects/${id}`, data),
  deleteProject: (id) => api.delete(`/profile/projects/${id}`),
}

// ============================================
// CERTIFICATIONS API (Part 2)
// ============================================
export const certificationAPI = {
  getAll: () => api.get('/profile/certifications'),
  add: (data) => api.post('/profile/certifications', data),
  update: (id, data) => api.put(`/profile/certifications/${id}`, data),
  delete: (id) => api.delete(`/profile/certifications/${id}`),
}

// ============================================
// RESUME API (UPDATED - Full Resume Analyzer)
// ============================================
export const resumeAPI = {
  // Upload
  upload: (file, studentId = null) => {
    const formData = new FormData()
    formData.append('file', file)
    let url = '/resume/upload'
    if (studentId) {
      url += `?student_id=${studentId}`
    }
    return api.post(url, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  
  // Get all resumes with filters
  getAll: (filters = {}) => {
    const params = new URLSearchParams()
    if (filters.studentId) params.append('student_id', filters.studentId)
    if (filters.status) params.append('status', filters.status)
    if (filters.minScore) params.append('min_ats_score', filters.minScore)
    if (filters.maxScore) params.append('max_ats_score', filters.maxScore)
    if (filters.limit) params.append('limit', filters.limit)
    if (filters.offset) params.append('offset', filters.offset)
    return api.get(`/resume/?${params.toString()}`)
  },
  
  // Get single resume
  getById: (id) => api.get(`/resume/${id}`),
  
  // Get ATS score
  getAtsScore: (id) => api.get(`/resume/${id}/score`),
  
  // Get suggestions
  getSuggestions: (id) => api.get(`/resume/${id}/suggestions`),
  
  // Update resume
  update: (id, data) => api.patch(`/resume/${id}`, data),
  
  // Update status
  updateStatus: (id, status) => api.patch(`/resume/${id}/status`, { status }),
  
  // Delete resume
  delete: (id) => api.delete(`/resume/${id}`),
  
  // Compare resumes
  compare: (ids) => api.post('/resume/compare', ids),
  
  // Export resume
  export: (id, format = 'json') => api.get(`/resume/${id}/export?format=${format}`, {
    responseType: 'blob',
  }),
}

// ============================================
// EXAM DUTY API (UPDATED)
// ============================================
export const examDutyAPI = {
  // Upload
  upload: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/exam-duties/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  uploadAsync: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/exam-duties/upload/async', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  getUploadStatus: (taskId) => api.get(`/exam-duties/upload-status/${taskId}`),
  
  // Get duties
  getMyDuties: () => api.get('/exam-duties/me'),
  getHODDuties: () => api.get('/exam-duties/hod'),
  getDepartmentDuties: () => api.get('/exam-duties/department'),
  getDutyDetails: (id) => api.get(`/exam-duties/${id}`),
  getUpcoming: () => api.get('/exam-duties/upcoming'),
  
  // Actions
  confirm: (id) => api.put(`/exam-duties/${id}/confirm`),
  update: (id, data) => api.put(`/exam-duties/${id}`, data),
  delete: (id) => api.delete(`/exam-duties/${id}`),
}

export default api