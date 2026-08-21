import { create } from 'zustand';
import {
  uploadFile,
  searchFiles,
  listFiles,
  getFile,
  downloadFile,
  deleteFile,
  updateFile,
  getFileStats,
  getRecentFiles,
  getSearchSuggestions,
} from '../services/fileService';

const useFileStore = create((set, get) => ({
  // State
  files: [],
  selectedFile: null,
  recentFiles: [],
  searchResults: [],
  searchQuery: '',
  stats: null,
  isLoading: false,
  error: null,
  totalFiles: 0,
  currentPage: 0,
  pageSize: 20,

  // Actions
  uploadFile: async (file, metadata) => {
    set({ isLoading: true, error: null });
    try {
      const result = await uploadFile(file, metadata);
      // Refresh files list after upload
      await get().listFiles();
      set({ isLoading: false });
      return result;
    } catch (error) {
      set({ 
        isLoading: false, 
        error: error.response?.data?.detail || error.message 
      });
      throw error;
    }
  },

  searchFiles: async (query, filters = {}) => {
    set({ isLoading: true, error: null, searchQuery: query });
    try {
      const result = await searchFiles(query, filters);
      set({
        searchResults: result.results || [],
        totalFiles: result.total || 0,
        isLoading: false,
      });
      return result;
    } catch (error) {
      set({ 
        isLoading: false, 
        error: error.response?.data?.detail || error.message 
      });
      throw error;
    }
  },

  listFiles: async (filters = {}) => {
    set({ isLoading: true, error: null });
    try {
      const result = await listFiles(filters);
      set({
        files: result || [],
        isLoading: false,
      });
      return result;
    } catch (error) {
      set({ 
        isLoading: false, 
        error: error.response?.data?.detail || error.message 
      });
      throw error;
    }
  },

  getFileDetails: async (fileId) => {
    set({ isLoading: true, error: null });
    try {
      const file = await getFile(fileId);
      set({ selectedFile: file, isLoading: false });
      return file;
    } catch (error) {
      set({ 
        isLoading: false, 
        error: error.response?.data?.detail || error.message 
      });
      throw error;
    }
  },

  downloadFile: async (fileId, filename) => {
    set({ isLoading: true, error: null });
    try {
      const response = await downloadFile(fileId);
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename || 'download');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      set({ isLoading: false });
    } catch (error) {
      set({ 
        isLoading: false, 
        error: error.response?.data?.detail || error.message 
      });
      throw error;
    }
  },

  deleteFile: async (fileId, permanent = false) => {
    set({ isLoading: true, error: null });
    try {
      await deleteFile(fileId, permanent);
      // Refresh list
      await get().listFiles();
      set({ isLoading: false });
    } catch (error) {
      set({ 
        isLoading: false, 
        error: error.response?.data?.detail || error.message 
      });
      throw error;
    }
  },

  updateFile: async (fileId, data) => {
    set({ isLoading: true, error: null });
    try {
      const updated = await updateFile(fileId, data);
      // Update selected file if it's the same
      const { selectedFile } = get();
      if (selectedFile && selectedFile.id === fileId) {
        set({ selectedFile: updated });
      }
      // Refresh list
      await get().listFiles();
      set({ isLoading: false });
      return updated;
    } catch (error) {
      set({ 
        isLoading: false, 
        error: error.response?.data?.detail || error.message 
      });
      throw error;
    }
  },

  getStats: async () => {
    set({ isLoading: true, error: null });
    try {
      const stats = await getFileStats();
      set({ stats, isLoading: false });
      return stats;
    } catch (error) {
      set({ 
        isLoading: false, 
        error: error.response?.data?.detail || error.message 
      });
      throw error;
    }
  },

  getRecentFiles: async (limit = 10) => {
    set({ isLoading: true, error: null });
    try {
      const files = await getRecentFiles(limit);
      set({ recentFiles: files, isLoading: false });
      return files;
    } catch (error) {
      set({ 
        isLoading: false, 
        error: error.response?.data?.detail || error.message 
      });
      throw error;
    }
  },

  getSuggestions: async (query) => {
    try {
      const result = await getSearchSuggestions(query);
      return result.suggestions || [];
    } catch (error) {
      console.error('Failed to get suggestions:', error);
      return [];
    }
  },

  clearSearch: () => {
    set({ searchResults: [], searchQuery: '', totalFiles: 0 });
  },

  clearError: () => {
    set({ error: null });
  },

  setPage: (page) => {
    set({ currentPage: page });
  },

  reset: () => {
    set({
      files: [],
      selectedFile: null,
      searchResults: [],
      searchQuery: '',
      stats: null,
      isLoading: false,
      error: null,
      totalFiles: 0,
      currentPage: 0,
    });
  },
}));

export default useFileStore;