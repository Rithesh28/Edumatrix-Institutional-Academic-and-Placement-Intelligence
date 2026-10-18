import React from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'

function AdminDashboard() {
  const { user } = useAuthStore()
  const navigate = useNavigate()

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Admin Dashboard</h1>
      <div className="bg-white dark:bg-gray-900 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-800">
        <p className="text-gray-700 dark:text-gray-200 font-semibold text-lg">Welcome, {user?.name}!</p>
        <p className="text-gray-500 dark:text-gray-400 mt-1">Role: Administrator • System Management</p>
        <p className="text-gray-500 dark:text-gray-400">Email: {user?.email}</p>
      </div>

      {/* Active Management Modules */}
      <div>
        <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3">Active Modules</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div 
            onClick={() => navigate('/admin/users')}
            className="bg-white dark:bg-gray-900 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-800 hover:shadow-md transition-shadow cursor-pointer border-l-4 border-l-blue-600"
          >
            <h3 className="font-semibold text-lg text-gray-900 dark:text-white mb-1 flex items-center justify-between">
              <span>👥 User Management</span>
              <span className="text-xs bg-green-100 dark:bg-green-900/60 text-green-700 dark:text-green-300 px-2 py-0.5 rounded-full font-normal">Active</span>
            </h3>
            <p className="text-gray-500 dark:text-gray-400 text-sm">Manage user accounts, institutional roles, and activation status.</p>
          </div>

          <div 
            onClick={() => navigate('/admin/logs')}
            className="bg-white dark:bg-gray-900 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-800 hover:shadow-md transition-shadow cursor-pointer border-l-4 border-l-purple-600"
          >
            <h3 className="font-semibold text-lg text-gray-900 dark:text-white mb-1 flex items-center justify-between">
              <span>📋 System Audit Logs</span>
              <span className="text-xs bg-green-100 dark:bg-green-900/60 text-green-700 dark:text-green-300 px-2 py-0.5 rounded-full font-normal">Active</span>
            </h3>
            <p className="text-gray-500 dark:text-gray-400 text-sm">Review immutable audit logs for administrative and security actions.</p>
          </div>

          <div 
            onClick={() => navigate('/placement/dashboard')}
            className="bg-white dark:bg-gray-900 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-800 hover:shadow-md transition-shadow cursor-pointer border-l-4 border-l-indigo-500"
          >
            <h3 className="font-semibold text-lg text-gray-900 dark:text-white mb-1 flex items-center justify-between">
              <span>💼 Placement Intelligence</span>
              <span className="text-xs bg-green-100 dark:bg-green-900/60 text-green-700 dark:text-green-300 px-2 py-0.5 rounded-full font-normal">Active</span>
            </h3>
            <p className="text-gray-500 dark:text-gray-400 text-sm">Monitor placement drives, companies, jobs, and shortlists.</p>
          </div>

          <div 
            onClick={() => navigate('/placement/resume-analyzer')}
            className="bg-white dark:bg-gray-900 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-800 hover:shadow-md transition-shadow cursor-pointer border-l-4 border-l-cyan-500"
          >
            <h3 className="font-semibold text-lg text-gray-900 dark:text-white mb-1 flex items-center justify-between">
              <span>📄 Resume Analyzer</span>
              <span className="text-xs bg-green-100 dark:bg-green-900/60 text-green-700 dark:text-green-300 px-2 py-0.5 rounded-full font-normal">Active</span>
            </h3>
            <p className="text-gray-500 dark:text-gray-400 text-sm">Analyze student resumes, inspect ATS scores, and review extracted skills.</p>
          </div>

          <div 
            onClick={() => navigate('/files')}
            className="bg-white dark:bg-gray-900 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-800 hover:shadow-md transition-shadow cursor-pointer border-l-4 border-l-emerald-500"
          >
            <h3 className="font-semibold text-lg text-gray-900 dark:text-white mb-1 flex items-center justify-between">
              <span>📁 Institutional Files</span>
              <span className="text-xs bg-green-100 dark:bg-green-900/60 text-green-700 dark:text-green-300 px-2 py-0.5 rounded-full font-normal">Active</span>
            </h3>
            <p className="text-gray-500 dark:text-gray-400 text-sm">Manage institutional files, search documents, and view storage metrics.</p>
          </div>
        </div>
      </div>

      {/* Planned Modules */}
      <div>
        <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3">System Roadmap</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-gray-50 dark:bg-gray-900/60 border border-gray-200 dark:border-gray-800 rounded-xl p-6">
            <h3 className="font-semibold text-lg text-gray-900 dark:text-white mb-2 flex items-center justify-between">
              <span>📊 Advanced Analytics</span>
              <span className="text-xs bg-amber-100 dark:bg-amber-900/60 text-amber-700 dark:text-amber-300 px-2 py-0.5 rounded-full font-normal">Planned (Phase 3)</span>
            </h3>
            <p className="text-gray-500 dark:text-gray-400 text-sm">Cross-department academic trends and institutional placement forecasting.</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default AdminDashboard