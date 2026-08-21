import React from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import { FileText, Bell, User, Sparkles, Briefcase, MessageSquare } from 'lucide-react'

function StudentDashboard() {
  const { user } = useAuthStore()
  const navigate = useNavigate()

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Student Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">Welcome back, {user?.name}! Manage your academic and placement profile.</p>
        </div>
      </div>

      <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center space-x-4">
          <div className="w-12 h-12 rounded-xl bg-blue-600 text-white flex items-center justify-center text-xl font-bold">
            {user?.name?.charAt(0).toUpperCase() || 'S'}
          </div>
          <div>
            <h2 className="text-lg font-bold text-gray-900">{user?.name}</h2>
            <p className="text-xs text-gray-500">{user?.email} • {user?.department || 'Student'}</p>
          </div>
        </div>
        <button
          onClick={() => navigate('/student/profile')}
          className="px-4 py-2 bg-blue-50 text-blue-600 hover:bg-blue-100 rounded-lg text-sm font-semibold transition-colors flex items-center gap-1.5"
        >
          <User className="w-4 h-4" />
          <span>Edit Profile</span>
        </button>
      </div>
      
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        <div
          onClick={() => navigate('/placement/resume-analyzer')}
          className="bg-gradient-to-br from-purple-50 to-indigo-50 border border-purple-200 hover:border-purple-400 p-5 rounded-xl shadow-sm hover:shadow-md transition-all cursor-pointer group"
        >
          <div className="w-10 h-10 bg-purple-600 text-white rounded-lg flex items-center justify-center mb-3 group-hover:scale-110 transition-transform shadow-sm">
            <Sparkles className="w-5 h-5" />
          </div>
          <h3 className="font-bold text-gray-900 text-base">📄 AI Resume Analyzer</h3>
          <p className="text-gray-500 text-xs mt-1">Upload resume to get ATS compatibility score & skill breakdown.</p>
        </div>

        <div
          onClick={() => navigate('/student/profile')}
          className="bg-white border border-gray-200 hover:border-blue-300 p-5 rounded-xl shadow-sm hover:shadow-md transition-all cursor-pointer group"
        >
          <div className="w-10 h-10 bg-blue-100 text-blue-600 rounded-lg flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
            <User className="w-5 h-5" />
          </div>
          <h3 className="font-bold text-gray-900 text-base">👤 My Profile & Resumes</h3>
          <p className="text-gray-500 text-xs mt-1">Manage academic details, CGPA, skills, and certifications.</p>
        </div>

        <div
          onClick={() => navigate('/student/circulars')}
          className="bg-white border border-gray-200 hover:border-blue-300 p-5 rounded-xl shadow-sm hover:shadow-md transition-all cursor-pointer group"
        >
          <div className="w-10 h-10 bg-amber-100 text-amber-600 rounded-lg flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
            <Bell className="w-5 h-5" />
          </div>
          <h3 className="font-bold text-gray-900 text-base">📢 Circulars & Notices</h3>
          <p className="text-gray-500 text-xs mt-1">View exam schedules, assignments, and campus circulars.</p>
        </div>
      </div>
    </div>
  )
}

export default StudentDashboard