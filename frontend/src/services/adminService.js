import api from './api'

export const adminService = {
  getUsers: async (params = {}) => {
    const response = await api.get('/admin/users', { params })
    return response.data
  },

  getUserDetails: async (userId) => {
    const response = await api.get(`/admin/users/${userId}`)
    return response.data
  },

  updateUserRole: async (userId, role) => {
    const response = await api.patch(`/admin/users/${userId}/role`, { role })
    return response.data
  },

  updateUserStatus: async (userId, isActive) => {
    const response = await api.patch(`/admin/users/${userId}/status`, { is_active: isActive })
    return response.data
  },

  getAuditLogs: async (params = {}) => {
    const response = await api.get('/admin/logs', { params })
    return response.data
  },
}

export default adminService
