import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import resumeService from '../services/resumeService';

const resumeStore = (set, get) => ({
  // State
  resumes: [],
  currentResume: null,
  selectedResumeId: null,
  loading: false,
  error: null,
  filters: {
    status: '',
    minScore: '',
    maxScore: '',
    limit: 20,
    offset: 0,
  },
  total: 0,
  uploadProgress: 0,
  isUploading: false,

  // Actions
  setFilters: (filters) => set({ filters: { ...get().filters, ...filters } }),
  
  clearFilters: () => set({
    filters: {
      status: '',
      minScore: '',
      maxScore: '',
      limit: 20,
      offset: 0,
    }
  }),

  fetchResumes: async (params = {}) => {
    set({ loading: true, error: null });
    try {
      const filters = { ...get().filters, ...params };
      const response = await resumeService.getResumes(filters);
      set({
        resumes: response.resumes || [],
        total: response.total || 0,
        loading: false,
      });
      return response;
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  fetchResumeById: async (resumeId) => {
    set({ loading: true, error: null });
    try {
      const [resume, score] = await Promise.all([
        resumeService.getResume(resumeId),
        resumeService.getAtsScore(resumeId).catch(() => null)
      ]);
      set({
        currentResume: { ...resume, score },
        selectedResumeId: resumeId,
        loading: false,
      });
      return { resume, score };
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  uploadResume: async (file, studentId = null) => {
    set({ isUploading: true, uploadProgress: 0, error: null });
    try {
      // Simulate progress
      const progressInterval = setInterval(() => {
        set((state) => ({
          uploadProgress: Math.min(state.uploadProgress + 10, 90)
        }));
      }, 200);

      const result = await resumeService.uploadResume(file, studentId);
      
      clearInterval(progressInterval);
      set({ uploadProgress: 100, isUploading: false });
      
      // Refresh the list
      await get().fetchResumes();
      
      return result;
    } catch (error) {
      set({ error: error.message, isUploading: false, uploadProgress: 0 });
      throw error;
    }
  },

  updateResume: async (resumeId, data) => {
    set({ loading: true, error: null });
    try {
      const result = await resumeService.updateResume(resumeId, data);
      
      // Update current resume if it's the same
      if (get().selectedResumeId === resumeId) {
        set((state) => ({
          currentResume: { ...state.currentResume, ...result },
          loading: false,
        }));
      }
      
      // Refresh the list
      await get().fetchResumes();
      
      return result;
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  deleteResume: async (resumeId) => {
    set({ loading: true, error: null });
    try {
      await resumeService.deleteResume(resumeId);
      
      // Clear current resume if deleted
      if (get().selectedResumeId === resumeId) {
        set({
          currentResume: null,
          selectedResumeId: null,
        });
      }
      
      // Refresh the list
      await get().fetchResumes();
      set({ loading: false });
      
      return true;
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  selectResume: (resumeId) => {
    set({ selectedResumeId: resumeId });
    if (resumeId) {
      get().fetchResumeById(resumeId);
    } else {
      set({ currentResume: null });
    }
  },

  clearCurrentResume: () => {
    set({
      currentResume: null,
      selectedResumeId: null,
    });
  },

  reset: () => {
    set({
      resumes: [],
      currentResume: null,
      selectedResumeId: null,
      loading: false,
      error: null,
      total: 0,
      uploadProgress: 0,
      isUploading: false,
    });
  },

  // Computed values
  getResumeById: (resumeId) => {
    return get().resumes.find(r => r.id === resumeId);
  },

  getCompletedResumes: () => {
    return get().resumes.filter(r => r.status === 'completed');
  },

  getAverageScore: () => {
    const completed = get().getCompletedResumes();
    if (completed.length === 0) return 0;
    const total = completed.reduce((sum, r) => sum + (r.ats_score || 0), 0);
    return Math.round(total / completed.length);
  },

  getStats: () => {
    const resumes = get().resumes;
    return {
      total: resumes.length,
      completed: resumes.filter(r => r.status === 'completed').length,
      processing: resumes.filter(r => r.status === 'processing').length,
      pending: resumes.filter(r => r.status === 'pending').length,
      failed: resumes.filter(r => r.status === 'failed').length,
      averageScore: get().getAverageScore(),
    };
  },
});

// Create the store with persistence
export const useResumeStore = create(
  persist(
    resumeStore,
    {
      name: 'resume-storage',
      partialize: (state) => ({
        filters: state.filters,
        total: state.total,
      }),
    }
  )
);

// Export individual selectors for better performance
export const useResumes = () => useResumeStore((state) => state.resumes);
export const useCurrentResume = () => useResumeStore((state) => state.currentResume);
export const useSelectedResumeId = () => useResumeStore((state) => state.selectedResumeId);
export const useResumeLoading = () => useResumeStore((state) => state.loading);
export const useResumeError = () => useResumeStore((state) => state.error);
export const useResumeFilters = () => useResumeStore((state) => state.filters);
export const useResumeTotal = () => useResumeStore((state) => state.total);
export const useUploadProgress = () => useResumeStore((state) => state.uploadProgress);
export const useIsUploading = () => useResumeStore((state) => state.isUploading);
export const useResumeStats = () => useResumeStore((state) => state.getStats());

export default useResumeStore;