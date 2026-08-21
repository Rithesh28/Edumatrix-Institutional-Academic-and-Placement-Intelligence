import api from './api';

const FILE_API = '/files';

// Get auth token
const getToken = () => {
  const token = localStorage.getItem('access_token');
  return token;
};

// Helper to get headers with auth
const getHeaders = () => ({
  'Authorization': `Bearer ${getToken()}`,
  'Content-Type': 'application/json',
});

// Upload a file
export const uploadFile = async (file, metadata = {}) => {
  const formData = new FormData();
  formData.append('file', file);
  
  // Add metadata as query params
  const params = new URLSearchParams();
  if (metadata.title) params.append('title', metadata.title);
  if (metadata.description) params.append('description', metadata.description);
  if (metadata.tags) params.append('tags', metadata.tags);
  if (metadata.department) params.append('department', metadata.department);
  if (metadata.file_type) params.append('file_type', metadata.file_type);

  const response = await api.post(`${FILE_API}/upload?${params.toString()}`, formData, {
    headers: {
      'Authorization': `Bearer ${getToken()}`,
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

// Get file details
export const getFile = async (fileId) => {
  const response = await api.get(`${FILE_API}/${fileId}`, {
    headers: getHeaders(),
  });
  return response.data;
};

// Download file
export const downloadFile = async (fileId) => {
  const response = await api.get(`${FILE_API}/${fileId}/download`, {
    headers: getHeaders(),
    responseType: 'blob',
  });
  return response;
};

// Preview file (opens in new tab)
export const previewFile = (fileId) => {
  return `${api.defaults.baseURL}${FILE_API}/${fileId}/preview?token=${getToken()}`;
};

// Semantic search
export const searchFiles = async (query, filters = {}) => {
  const payload = {
    query: query,
    limit: filters.limit || 20,
    offset: filters.offset || 0,
    ...(filters.file_type && { file_type: filters.file_type }),
    ...(filters.department && { department: filters.department }),
    ...(filters.date_from && { date_from: filters.date_from }),
    ...(filters.date_to && { date_to: filters.date_to }),
  };
  
  const response = await api.post(`${FILE_API}/search`, payload, {
    headers: getHeaders(),
  });
  return response.data;
};

// List files
export const listFiles = async (filters = {}) => {
  const params = new URLSearchParams();
  if (filters.file_type) params.append('file_type', filters.file_type);
  if (filters.limit) params.append('limit', filters.limit);
  if (filters.offset) params.append('offset', filters.offset);
  
  const response = await api.get(`${FILE_API}/?${params.toString()}`, {
    headers: getHeaders(),
  });
  return response.data;
};

// Update file metadata
export const updateFile = async (fileId, data) => {
  const response = await api.patch(`${FILE_API}/${fileId}`, data, {
    headers: getHeaders(),
  });
  return response.data;
};

// Delete file
export const deleteFile = async (fileId, permanent = false) => {
  const response = await api.delete(`${FILE_API}/${fileId}?permanent=${permanent}`, {
    headers: getHeaders(),
  });
  return response.data;
};

// Bulk delete files
export const bulkDeleteFiles = async (fileIds, permanent = false) => {
  const response = await api.post(`${FILE_API}/bulk-delete?permanent=${permanent}`, {
    file_ids: fileIds,
  }, {
    headers: getHeaders(),
  });
  return response.data;
};

// Get file statistics
export const getFileStats = async () => {
  const response = await api.get(`${FILE_API}/stats`, {
    headers: getHeaders(),
  });
  return response.data;
};

// Get file versions
export const getFileVersions = async (fileId) => {
  const response = await api.get(`${FILE_API}/${fileId}/versions`, {
    headers: getHeaders(),
  });
  return response.data;
};

// Restore version
export const restoreVersion = async (fileId, versionNumber) => {
  const response = await api.post(`${FILE_API}/${fileId}/versions/restore`, {
    version_number: versionNumber,
  }, {
    headers: getHeaders(),
  });
  return response.data;
};

// Get search suggestions
export const getSearchSuggestions = async (query) => {
  const response = await api.get(`${FILE_API}/search/suggestions?q=${encodeURIComponent(query)}&limit=5`, {
    headers: getHeaders(),
  });
  return response.data;
};

// Get recent files
export const getRecentFiles = async (limit = 10) => {
  const response = await api.get(`${FILE_API}/search/recent?limit=${limit}`, {
    headers: getHeaders(),
  });
  return response.data;
};