import { create } from 'zustand';
import {
  createCompany,
  getCompanies,
  getCompany,
  updateCompany,
  deleteCompany,
  createJobPosting,
  getJobPostings,
  getJobPosting,
  updateJobPosting,
  deleteJobPosting,
  createApplication,
  getApplications,
  updateApplication,
  createShortlist,
  getShortlists,
  removeFromShortlist,
  matchStudentsForJob,
  getPlacementStats,
} from '../services/placementService';

const usePlacementStore = create((set, get) => ({
  // State
  companies: [],
  jobs: [],
  applications: [],
  shortlists: [],
  stats: null,
  selectedCompany: null,
  selectedJob: null,
  isLoading: false,
  error: null,

  // ============================================
  // COMPANY ACTIONS
  // ============================================

  createCompany: async (data) => {
    set({ isLoading: true, error: null });
    try {
      const company = await createCompany(data);
      set((state) => ({
        companies: [company, ...state.companies],
        isLoading: false,
      }));
      return company;
    } catch (error) {
      set({ isLoading: false, error: error.response?.data?.detail || error.message });
      throw error;
    }
  },

  fetchCompanies: async (params = {}) => {
    set({ isLoading: true, error: null });
    try {
      const companies = await getCompanies(params);
      set({ companies, isLoading: false });
      return companies;
    } catch (error) {
      set({ isLoading: false, error: error.response?.data?.detail || error.message });
      throw error;
    }
  },

  fetchCompany: async (id) => {
    set({ isLoading: true, error: null });
    try {
      const company = await getCompany(id);
      set({ selectedCompany: company, isLoading: false });
      return company;
    } catch (error) {
      set({ isLoading: false, error: error.response?.data?.detail || error.message });
      throw error;
    }
  },

  updateCompany: async (id, data) => {
    set({ isLoading: true, error: null });
    try {
      const company = await updateCompany(id, data);
      set((state) => ({
        companies: state.companies.map((c) => (c.id === id ? company : c)),
        selectedCompany: company,
        isLoading: false,
      }));
      return company;
    } catch (error) {
      set({ isLoading: false, error: error.response?.data?.detail || error.message });
      throw error;
    }
  },

  deleteCompany: async (id) => {
    set({ isLoading: true, error: null });
    try {
      await deleteCompany(id);
      set((state) => ({
        companies: state.companies.filter((c) => c.id !== id),
        isLoading: false,
      }));
    } catch (error) {
      set({ isLoading: false, error: error.response?.data?.detail || error.message });
      throw error;
    }
  },

  // ============================================
  // JOB POSTING ACTIONS
  // ============================================

  createJobPosting: async (data) => {
    set({ isLoading: true, error: null });
    try {
      const job = await createJobPosting(data);
      set((state) => ({
        jobs: [job, ...state.jobs],
        isLoading: false,
      }));
      return job;
    } catch (error) {
      set({ isLoading: false, error: error.response?.data?.detail || error.message });
      throw error;
    }
  },

  fetchJobPostings: async (params = {}) => {
    set({ isLoading: true, error: null });
    try {
      const jobs = await getJobPostings(params);
      set({ jobs, isLoading: false });
      return jobs;
    } catch (error) {
      set({ isLoading: false, error: error.response?.data?.detail || error.message });
      throw error;
    }
  },

  fetchJobPosting: async (id) => {
    set({ isLoading: true, error: null });
    try {
        const job = await getJobPosting(id);
        // Ensure company_name is set from the response
        if (job && !job.company_name && job.company_id) {
        // If company_name is missing, try to get it from companies list
        const { companies } = get();
        const company = companies.find(c => c.id === job.company_id);
        if (company) {
            job.company_name = company.name;
        }
        }
        set({ selectedJob: job, isLoading: false });
        return job;
    } catch (error) {
        set({ isLoading: false, error: error.response?.data?.detail || error.message });
        throw error;
    }
  },

  updateJobPosting: async (id, data) => {
    set({ isLoading: true, error: null });
    try {
      const job = await updateJobPosting(id, data);
      set((state) => ({
        jobs: state.jobs.map((j) => (j.id === id ? job : j)),
        selectedJob: job,
        isLoading: false,
      }));
      return job;
    } catch (error) {
      set({ isLoading: false, error: error.response?.data?.detail || error.message });
      throw error;
    }
  },

  deleteJobPosting: async (id) => {
    set({ isLoading: true, error: null });
    try {
      await deleteJobPosting(id);
      set((state) => ({
        jobs: state.jobs.filter((j) => j.id !== id),
        isLoading: false,
      }));
    } catch (error) {
      set({ isLoading: false, error: error.response?.data?.detail || error.message });
      throw error;
    }
  },

  // ============================================
  // APPLICATION ACTIONS
  // ============================================

  createApplication: async (data) => {
    set({ isLoading: true, error: null });
    try {
      const application = await createApplication(data);
      set((state) => ({
        applications: [application, ...state.applications],
        isLoading: false,
      }));
      return application;
    } catch (error) {
      set({ isLoading: false, error: error.response?.data?.detail || error.message });
      throw error;
    }
  },

  fetchApplications: async (params = {}) => {
    set({ isLoading: true, error: null });
    try {
      const applications = await getApplications(params);
      set({ applications, isLoading: false });
      return applications;
    } catch (error) {
      set({ isLoading: false, error: error.response?.data?.detail || error.message });
      throw error;
    }
  },

  updateApplication: async (id, data) => {
    set({ isLoading: true, error: null });
    try {
      const application = await updateApplication(id, data);
      set((state) => ({
        applications: state.applications.map((a) => (a.id === id ? application : a)),
        isLoading: false,
      }));
      return application;
    } catch (error) {
      set({ isLoading: false, error: error.response?.data?.detail || error.message });
      throw error;
    }
  },

  // ============================================
  // SHORTLIST ACTIONS
  // ============================================

  createShortlist: async (data) => {
    set({ isLoading: true, error: null });
    try {
      const shortlist = await createShortlist(data);
      set((state) => ({
        shortlists: [shortlist, ...state.shortlists],
        isLoading: false,
      }));
      return shortlist;
    } catch (error) {
      set({ isLoading: false, error: error.response?.data?.detail || error.message });
      throw error;
    }
  },

  fetchShortlists: async (params = {}) => {
    set({ isLoading: true, error: null });
    try {
      const shortlists = await getShortlists(params);
      set({ shortlists, isLoading: false });
      return shortlists;
    } catch (error) {
      set({ isLoading: false, error: error.response?.data?.detail || error.message });
      throw error;
    }
  },

  removeFromShortlist: async (id) => {
    set({ isLoading: true, error: null });
    try {
      await removeFromShortlist(id);
      set((state) => ({
        shortlists: state.shortlists.filter((s) => s.id !== id),
        isLoading: false,
      }));
    } catch (error) {
      set({ isLoading: false, error: error.response?.data?.detail || error.message });
      throw error;
    }
  },

  // ============================================
  // MATCHING ACTIONS
  // ============================================

  matchStudents: async (data) => {
    set({ isLoading: true, error: null });
    try {
      const result = await matchStudentsForJob(data);
      set({ isLoading: false });
      return result;
    } catch (error) {
      set({ isLoading: false, error: error.response?.data?.detail || error.message });
      throw error;
    }
  },

  // ============================================
  // STATISTICS ACTIONS
  // ============================================

  fetchStats: async () => {
    set({ isLoading: true, error: null });
    try {
      const stats = await getPlacementStats();
      set({ stats, isLoading: false });
      return stats;
    } catch (error) {
      set({ isLoading: false, error: error.response?.data?.detail || error.message });
      throw error;
    }
  },

  // ============================================
  // UTILITY ACTIONS
  // ============================================

  clearError: () => set({ error: null }),
  reset: () => set({
    companies: [],
    jobs: [],
    applications: [],
    shortlists: [],
    stats: null,
    selectedCompany: null,
    selectedJob: null,
    isLoading: false,
    error: null,
  }),
}));

export default usePlacementStore;