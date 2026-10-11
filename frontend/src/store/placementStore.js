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
  confirmExternalApplication,
  createShortlist,
  getShortlists,
  removeFromShortlist,
  matchStudentsForJob,
  getPlacementStats,
  publishJobPosting,
  parseJdText,
  uploadJdFile,
  checkStudentEligibility,
  getStudentPlacementStatus,
  getRecruitmentCirculars,
  getRecruitmentCircular,
  createRecruitmentCircular,
  updateRecruitmentCircular,
  publishRecruitmentCircular,
  archiveRecruitmentCircular,
  addCircularAttachment,
  removeCircularAttachment,
  linkCircularJobs,
  unlinkCircularJob,
  uploadResultFile,
  getResultBatches,
  getResultBatch,
  updateResultItemMatch,
  confirmResultBatch,
} from '../services/placementService';
import { useAuthStore } from './authStore';

const formatErrorMessage = (error) => {
  const detail = error.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => (typeof d === 'string' ? d : d.msg || JSON.stringify(d))).join(', ');
  }
  if (detail && typeof detail === 'object') {
    return detail.message || JSON.stringify(detail);
  }
  return error.message || 'An error occurred';
};

const usePlacementStore = create((set, get) => ({
  // Placement Officer & General State
  companies: [],
  jobs: [],
  applications: [],
  shortlists: [],
  stats: null,
  selectedCompany: null,
  selectedJob: null,
  isLoading: false,
  error: null,

  // Recruitment Circulars State
  circulars: [],
  selectedCircular: null,
  isCircularsLoading: false,
  circularsError: null,

  // Recruitment Results State (Stage 3.2)
  resultBatches: [],
  selectedResultBatch: null,
  isResultsLoading: false,
  resultsError: null,

  // Student-specific placement state (isolated from Officer screens)
  jobEligibility: null,
  eligibilityJobId: null,
  isEligibilityLoading: false,
  eligibilityError: null,

  myApplications: [],
  isMyApplicationsLoading: false,
  myApplicationsError: null,

  myPlacementStatus: null,
  isPlacementStatusLoading: false,
  placementStatusError: null,

  isSubmittingApplication: false,
  applicationSubmitError: null,

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
        const currentJobId = parseInt(id, 10);
        const updates = { selectedJob: job, isLoading: false };
        if (get().eligibilityJobId !== currentJobId) {
          updates.jobEligibility = null;
          updates.eligibilityJobId = null;
          updates.eligibilityError = null;
        }
        set(updates);
        return job;
    } catch (error) {
        set({ isLoading: false, error: formatErrorMessage(error) });
        throw error;
    }
  },

  setSelectedJob: (job) => {
    const currentJobId = job ? parseInt(job.id, 10) : null;
    const updates = { selectedJob: job };
    if (get().eligibilityJobId !== currentJobId) {
      updates.jobEligibility = null;
      updates.eligibilityJobId = null;
      updates.eligibilityError = null;
    }
    set(updates);
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

  publishJobPosting: async (id, confirmNoSkills = false) => {
    set({ isLoading: true, error: null });
    try {
      const job = await publishJobPosting(id, confirmNoSkills);
      set((state) => ({
        jobs: state.jobs.map((j) => (j.id === id ? job : j)),
        selectedJob: state.selectedJob?.id === id ? job : state.selectedJob,
        isLoading: false,
      }));
      return job;
    } catch (error) {
      set({ isLoading: false, error: error.response?.data?.detail || error.message });
      throw error;
    }
  },

  parseJdText: async (text) => {
    set({ isLoading: true, error: null });
    try {
      const parsed = await parseJdText(text);
      set({ isLoading: false });
      return parsed;
    } catch (error) {
      set({ isLoading: false, error: error.response?.data?.detail || error.message });
      throw error;
    }
  },

  uploadJdFile: async (file) => {
    set({ isLoading: true, error: null });
    try {
      const parsed = await uploadJdFile(file);
      set({ isLoading: false });
      return parsed;
    } catch (error) {
      set({ isLoading: false, error: error.response?.data?.detail || error.message });
      throw error;
    }
  },

  // ============================================
  // APPLICATION ACTIONS
  // ============================================

  createApplication: async (data) => {
    set({
      isSubmittingApplication: true,
      applicationSubmitError: null,
      isLoading: true,
      error: null,
    });
    try {
      // Strictly sanitize payload to only include job_posting_id and optional notes
      const jobPostingId = typeof data === 'number' || typeof data === 'string'
        ? parseInt(data, 10)
        : (data?.job_posting_id || data?.jobId || data?.id);

      if (!jobPostingId || isNaN(jobPostingId)) {
        throw new Error('A valid job_posting_id is required to submit an application');
      }

      const payload = {
        job_posting_id: parseInt(jobPostingId, 10),
      };
      if (data && typeof data === 'object' && data.notes && typeof data.notes === 'string') {
        payload.notes = data.notes.trim();
      }

      const application = await createApplication(payload);

      set((state) => {
        // Update officer-facing applications list
        const updatedApplications = [application, ...state.applications];

        // Update student-facing myApplications list without duplicates
        const updatedMyApplications = [
          application,
          ...state.myApplications.filter(
            (a) => a.job_posting_id !== application.job_posting_id && a.id !== application.id
          ),
        ];

        // Update placement status if already loaded
        let updatedStatus = state.myPlacementStatus;
        if (state.myPlacementStatus) {
          const prevApps = state.myPlacementStatus.applications || [];
          const filteredPrev = prevApps.filter(
            (a) => a.job_posting_id !== application.job_posting_id && a.id !== application.id
          );
          updatedStatus = {
            ...state.myPlacementStatus,
            total_applications: (state.myPlacementStatus.total_applications || 0) + 1,
            status: state.myPlacementStatus.status === 'not_applied' ? 'applied' : state.myPlacementStatus.status,
            applications: [application, ...filteredPrev],
          };
        }

        return {
          applications: updatedApplications,
          myApplications: updatedMyApplications,
          myPlacementStatus: updatedStatus,
          isSubmittingApplication: false,
          isLoading: false,
          applicationSubmitError: null,
          error: null,
        };
      });

      return application;
    } catch (error) {
      const errMsg = formatErrorMessage(error);
      set({
        isSubmittingApplication: false,
        applicationSubmitError: errMsg,
        isLoading: false,
        error: errMsg,
      });
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
      set({ isLoading: false, error: formatErrorMessage(error) });
      throw error;
    }
  },

  updateApplication: async (id, data) => {
    set({ isLoading: true, error: null });
    try {
      const application = await updateApplication(id, data);
      set((state) => ({
        applications: state.applications.map((a) => (a.id === id ? application : a)),
        myApplications: state.myApplications.map((a) => (a.id === id ? application : a)),
        isLoading: false,
      }));
      return application;
    } catch (error) {
      set({ isLoading: false, error: formatErrorMessage(error) });
      throw error;
    }
  },

  confirmExternalApplication: async (id) => {
    set({ isLoading: true, error: null });
    try {
      const application = await confirmExternalApplication(id);
      set((state) => ({
        applications: state.applications.map((a) => (a.id === id ? { ...a, ...application } : a)),
        myApplications: state.myApplications.map((a) => (a.id === id ? { ...a, ...application } : a)),
        isLoading: false,
      }));
      return application;
    } catch (error) {
      const errMsg = formatErrorMessage(error);
      set({ isLoading: false, error: errMsg });
      throw error;
    }
  },

  // ============================================
  // STUDENT PLACEMENT & ELIGIBILITY ACTIONS
  // ============================================

  checkJobEligibility: async (jobId, studentId = null) => {
    const parsedJobId = parseInt(jobId, 10);
    if (!parsedJobId || isNaN(parsedJobId)) {
      const errMsg = 'A valid jobId is required to check eligibility';
      set({ eligibilityError: errMsg, isEligibilityLoading: false });
      throw new Error(errMsg);
    }

    // Derive student identity from authStore if not explicitly provided
    const authUser = useAuthStore.getState().user;
    const currentStudentId = studentId || authUser?.id;

    if (!currentStudentId) {
      const errMsg = 'Student authentication is required to check eligibility';
      set({ eligibilityError: errMsg, isEligibilityLoading: false });
      throw new Error(errMsg);
    }

    // Reset previous eligibility and record active jobId to avoid stale data
    set({
      jobEligibility: null,
      eligibilityJobId: parsedJobId,
      isEligibilityLoading: true,
      eligibilityError: null,
    });

    try {
      const result = await checkStudentEligibility(parsedJobId, currentStudentId);

      // Ensure results are only committed if the user is still querying this job
      if (get().eligibilityJobId === parsedJobId) {
        set({
          jobEligibility: result,
          isEligibilityLoading: false,
          eligibilityError: null,
        });
      }
      return result;
    } catch (error) {
      const errMsg = formatErrorMessage(error);
      if (get().eligibilityJobId === parsedJobId) {
        set({
          isEligibilityLoading: false,
          eligibilityError: errMsg,
        });
      }
      throw error;
    }
  },

  clearJobEligibility: () => set({
    jobEligibility: null,
    eligibilityJobId: null,
    isEligibilityLoading: false,
    eligibilityError: null,
  }),

  fetchMyApplications: async (studentId = null) => {
    const authUser = useAuthStore.getState().user;
    const currentStudentId = studentId || authUser?.id;

    set({ isMyApplicationsLoading: true, myApplicationsError: null });
    try {
      const params = currentStudentId ? { student_id: currentStudentId } : {};
      const apps = await getApplications(params);
      set({
        myApplications: apps,
        isMyApplicationsLoading: false,
        myApplicationsError: null,
      });
      return apps;
    } catch (error) {
      const errMsg = formatErrorMessage(error);
      set({
        isMyApplicationsLoading: false,
        myApplicationsError: errMsg,
      });
      throw error;
    }
  },

  fetchMyPlacementStatus: async (studentId = null) => {
    const authUser = useAuthStore.getState().user;
    const currentStudentId = studentId || authUser?.id;

    if (!currentStudentId) {
      const errMsg = 'Student authentication is required to view placement status';
      set({ placementStatusError: errMsg, isPlacementStatusLoading: false });
      throw new Error(errMsg);
    }

    set({ isPlacementStatusLoading: true, placementStatusError: null });
    try {
      const statusData = await getStudentPlacementStatus(currentStudentId);
      set({
        myPlacementStatus: statusData,
        myApplications: statusData.applications && statusData.applications.length > 0
          ? statusData.applications
          : get().myApplications,
        isPlacementStatusLoading: false,
        placementStatusError: null,
      });
      return statusData;
    } catch (error) {
      const errMsg = formatErrorMessage(error);
      set({
        isPlacementStatusLoading: false,
        placementStatusError: errMsg,
      });
      throw error;
    }
  },

  clearStudentErrors: () => set({
    eligibilityError: null,
    myApplicationsError: null,
    placementStatusError: null,
    applicationSubmitError: null,
  }),

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
  // RECRUITMENT CIRCULARS ACTIONS
  // ============================================

  fetchCirculars: async (params = {}) => {
    set({ isCircularsLoading: true, circularsError: null });
    try {
      const circulars = await getRecruitmentCirculars(params);
      set({ circulars, isCircularsLoading: false });
      return circulars;
    } catch (error) {
      const errorMsg = formatErrorMessage(error);
      set({ isCircularsLoading: false, circularsError: errorMsg });
      throw error;
    }
  },

  fetchCircular: async (id) => {
    set({ isCircularsLoading: true, circularsError: null });
    try {
      const circular = await getRecruitmentCircular(id);
      set({ selectedCircular: circular, isCircularsLoading: false });
      return circular;
    } catch (error) {
      const errorMsg = formatErrorMessage(error);
      set({ isCircularsLoading: false, circularsError: errorMsg });
      throw error;
    }
  },

  createCircular: async (data) => {
    set({ isCircularsLoading: true, circularsError: null });
    try {
      const circular = await createRecruitmentCircular(data);
      set((state) => ({
        circulars: [circular, ...state.circulars],
        selectedCircular: circular,
        isCircularsLoading: false,
      }));
      return circular;
    } catch (error) {
      const errorMsg = formatErrorMessage(error);
      set({ isCircularsLoading: false, circularsError: errorMsg });
      throw error;
    }
  },

  updateCircular: async (id, data) => {
    set({ isCircularsLoading: true, circularsError: null });
    try {
      const updated = await updateRecruitmentCircular(id, data);
      set((state) => ({
        circulars: state.circulars.map((c) => (c.id === id ? updated : c)),
        selectedCircular: updated,
        isCircularsLoading: false,
      }));
      return updated;
    } catch (error) {
      const errorMsg = formatErrorMessage(error);
      set({ isCircularsLoading: false, circularsError: errorMsg });
      throw error;
    }
  },

  publishCircular: async (id, params = {}) => {
    set({ isCircularsLoading: true, circularsError: null });
    try {
      const response = await publishRecruitmentCircular(id, params);
      const publishedCircular = response.circular;
      set((state) => ({
        circulars: state.circulars.map((c) => (c.id === id ? publishedCircular : c)),
        selectedCircular: publishedCircular,
        isCircularsLoading: false,
      }));
      return response;
    } catch (error) {
      const errorMsg = formatErrorMessage(error);
      set({ isCircularsLoading: false, circularsError: errorMsg });
      throw error;
    }
  },

  archiveCircular: async (id) => {
    set({ isCircularsLoading: true, circularsError: null });
    try {
      const archived = await archiveRecruitmentCircular(id);
      set((state) => ({
        circulars: state.circulars.map((c) => (c.id === id ? archived : c)),
        selectedCircular: archived,
        isCircularsLoading: false,
      }));
      return archived;
    } catch (error) {
      const errorMsg = formatErrorMessage(error);
      set({ isCircularsLoading: false, circularsError: errorMsg });
      throw error;
    }
  },

  addCircularAttachment: async (circularId, data) => {
    set({ isCircularsLoading: true, circularsError: null });
    try {
      const updated = await addCircularAttachment(circularId, data);
      set((state) => ({
        circulars: state.circulars.map((c) => (c.id === circularId ? updated : c)),
        selectedCircular: updated,
        isCircularsLoading: false,
      }));
      return updated;
    } catch (error) {
      const errorMsg = formatErrorMessage(error);
      set({ isCircularsLoading: false, circularsError: errorMsg });
      throw error;
    }
  },

  removeCircularAttachment: async (circularId, attachmentId) => {
    set({ isCircularsLoading: true, circularsError: null });
    try {
      const updated = await removeCircularAttachment(circularId, attachmentId);
      set((state) => ({
        circulars: state.circulars.map((c) => (c.id === circularId ? updated : c)),
        selectedCircular: updated,
        isCircularsLoading: false,
      }));
      return updated;
    } catch (error) {
      const errorMsg = formatErrorMessage(error);
      set({ isCircularsLoading: false, circularsError: errorMsg });
      throw error;
    }
  },

  linkCircularJobs: async (circularId, data) => {
    set({ isCircularsLoading: true, circularsError: null });
    try {
      const updated = await linkCircularJobs(circularId, data);
      set((state) => ({
        circulars: state.circulars.map((c) => (c.id === circularId ? updated : c)),
        selectedCircular: updated,
        isCircularsLoading: false,
      }));
      return updated;
    } catch (error) {
      const errorMsg = formatErrorMessage(error);
      set({ isCircularsLoading: false, circularsError: errorMsg });
      throw error;
    }
  },

  unlinkCircularJob: async (circularId, jobPostingId) => {
    set({ isCircularsLoading: true, circularsError: null });
    try {
      const updated = await unlinkCircularJob(circularId, jobPostingId);
      set((state) => ({
        circulars: state.circulars.map((c) => (c.id === circularId ? updated : c)),
        selectedCircular: updated,
        isCircularsLoading: false,
      }));
      return updated;
    } catch (error) {
      const errorMsg = formatErrorMessage(error);
      set({ isCircularsLoading: false, circularsError: errorMsg });
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
  // RECRUITMENT RESULTS ACTIONS (STAGE 3.2)
  // ============================================

  fetchResultBatches: async (params = {}) => {
    set({ isResultsLoading: true, resultsError: null });
    try {
      const batches = await getResultBatches(params);
      set({ resultBatches: batches, isResultsLoading: false });
      return batches;
    } catch (error) {
      set({ isResultsLoading: false, resultsError: formatErrorMessage(error) });
      throw error;
    }
  },

  fetchResultBatch: async (id) => {
    set({ isResultsLoading: true, resultsError: null });
    try {
      const batch = await getResultBatch(id);
      set({ selectedResultBatch: batch, isResultsLoading: false });
      return batch;
    } catch (error) {
      set({ isResultsLoading: false, resultsError: formatErrorMessage(error) });
      throw error;
    }
  },

  uploadResultDocument: async (formData) => {
    set({ isResultsLoading: true, resultsError: null });
    try {
      const batch = await uploadResultFile(formData);
      set((state) => ({
        resultBatches: [batch, ...state.resultBatches],
        selectedResultBatch: batch,
        isResultsLoading: false,
      }));
      return batch;
    } catch (error) {
      set({ isResultsLoading: false, resultsError: formatErrorMessage(error) });
      throw error;
    }
  },

  updateCandidateMatch: async (itemId, data) => {
    set({ isResultsLoading: true, resultsError: null });
    try {
      const updatedBatch = await updateResultItemMatch(itemId, data);
      set((state) => ({
        selectedResultBatch: updatedBatch,
        resultBatches: state.resultBatches.map((b) => (b.id === updatedBatch.id ? updatedBatch : b)),
        isResultsLoading: false,
      }));
      return updatedBatch;
    } catch (error) {
      set({ isResultsLoading: false, resultsError: formatErrorMessage(error) });
      throw error;
    }
  },

  confirmBatchResults: async (batchId, data = {}) => {
    set({ isResultsLoading: true, resultsError: null });
    try {
      const result = await confirmResultBatch(batchId, data);
      // Refresh batch details
      const updatedBatch = await getResultBatch(batchId);
      set((state) => ({
        selectedResultBatch: updatedBatch,
        resultBatches: state.resultBatches.map((b) => (b.id === batchId ? updatedBatch : b)),
        isResultsLoading: false,
      }));
      return result;
    } catch (error) {
      set({ isResultsLoading: false, resultsError: formatErrorMessage(error) });
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

  clearError: () => set({ error: null, circularsError: null }),
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
    circulars: [],
    selectedCircular: null,
    isCircularsLoading: false,
    circularsError: null,
    jobEligibility: null,
    eligibilityJobId: null,
    isEligibilityLoading: false,
    eligibilityError: null,
    myApplications: [],
    isMyApplicationsLoading: false,
    myApplicationsError: null,
    myPlacementStatus: null,
    isPlacementStatusLoading: false,
    placementStatusError: null,
    isSubmittingApplication: false,
    applicationSubmitError: null,
    resultBatches: [],
    selectedResultBatch: null,
    isResultsLoading: false,
    resultsError: null,
  }),
}));

export default usePlacementStore;