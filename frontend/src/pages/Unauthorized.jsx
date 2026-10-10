import React from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { ShieldAlert, ArrowLeft, Home } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import ThemeToggle from '../components/ThemeToggle'

function Unauthorized() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useAuthStore()

  const getDashboardPath = () => {
    if (!user?.role) return '/login'
    const role = String(user.role).toLowerCase()
    const roleMap = {
      student: '/student/dashboard',
      lecturer: '/lecturer/dashboard',
      hod: '/hod/dashboard',
      admin: '/admin/dashboard',
      placement_officer: '/placement/dashboard',
    }
    return roleMap[role] || '/'
  }

  const roleName = user?.role ? String(user.role).replace('_', ' ') : 'Guest'

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center p-4 relative transition-colors duration-200">
      {/* Top Header Theme Toggle */}
      <div className="absolute top-4 right-4 sm:top-6 sm:right-6 z-20">
        <ThemeToggle id="unauthorized-theme-toggle" />
      </div>

      <div className="max-w-md w-full bg-white dark:bg-gray-900 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-800 p-8 text-center space-y-6 transition-colors duration-200">
        <div className="w-16 h-16 bg-red-100 dark:bg-red-950/50 text-red-600 dark:text-red-400 rounded-full flex items-center justify-center mx-auto shadow-inner border border-transparent dark:border-red-900/50">
          <ShieldAlert className="w-9 h-9" />
        </div>

        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Access Restricted</h1>
          <p className="text-gray-500 dark:text-gray-400 text-sm mt-2">
            You do not have the required role or authorization to access this page.
          </p>
        </div>

        <div className="bg-gray-50 dark:bg-gray-800/60 rounded-xl p-4 border border-gray-200 dark:border-gray-700 text-left text-xs space-y-2">
          <div className="flex justify-between items-center">
            <span className="text-gray-500 dark:text-gray-400 font-medium">Logged in as:</span>
            <span className="text-gray-800 dark:text-gray-200 font-semibold">{user?.email || 'N/A'}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-gray-500 font-medium">Assigned Role:</span>
            <span className="bg-red-50 text-red-700 font-semibold px-2 py-0.5 rounded capitalize">
              {roleName}
            </span>
          </div>
          {location.state?.from && (
            <div className="flex justify-between items-center pt-1 border-t border-gray-200">
              <span className="text-gray-500 font-medium">Attempted Path:</span>
              <span className="text-gray-700 font-mono truncate max-w-[200px]">
                {location.state.from.pathname}
              </span>
            </div>
          )}
        </div>

        <div className="flex flex-col sm:flex-row gap-3 pt-2">
          <button
            onClick={() => navigate(-1)}
            className="flex-1 px-4 py-2.5 border border-gray-300 text-gray-700 rounded-xl hover:bg-gray-100 font-medium text-sm flex items-center justify-center gap-2 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Go Back</span>
          </button>
          <button
            onClick={() => navigate(getDashboardPath())}
            className="flex-1 px-4 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 font-semibold text-sm flex items-center justify-center gap-2 shadow-sm transition-colors"
          >
            <Home className="w-4 h-4" />
            <span>My Dashboard</span>
          </button>
        </div>
      </div>
    </div>
  )
}

export default Unauthorized
