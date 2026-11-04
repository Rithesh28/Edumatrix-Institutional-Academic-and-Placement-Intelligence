import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import { FileText, Bell, User, Sparkles, Briefcase, MessageSquare, BarChart3 } from 'lucide-react'
import AIChatAnalytics from '../../components/ai-chat-analytics'

function StudentDashboard() {
  const { user } = useAuthStore()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('overview')

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Student Dashboard</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Welcome back, {user?.name}! Manage your academic and placement profile.</p>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-100 dark:bg-indigo-900/40 rounded-lg">
              <MessageSquare className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">12</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">AI Chats</p>
            </div>
          </div>
        </div>
        <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-100 dark:bg-green-900/40 rounded-lg">
              <FileText className="w-5 h-5 text-green-600 dark:text-green-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">3</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Circulars</p>
            </div>
          </div>
        </div>
        <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-100 dark:bg-purple-900/40 rounded-lg">
              <Briefcase className="w-5 h-5 text-purple-600 dark:text-purple-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">5</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Job Alerts</p>
            </div>
          </div>
        </div>
        <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-orange-100 dark:bg-orange-900/40 rounded-lg">
              <Bell className="w-5 h-5 text-orange-600 dark:text-orange-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">2</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Notifications</p>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        <div
          onClick={() => navigate('/student/chat')}
          className="bg-gradient-to-br from-indigo-50 to-purple-50 dark:from-indigo-950/40 dark:to-purple-950/40 border border-indigo-200 dark:border-indigo-800/60 hover:border-indigo-400 dark:hover:border-indigo-600 p-5 rounded-xl shadow-sm hover:shadow-md transition-all cursor-pointer group"
        >
          <div className="w-10 h-10 bg-indigo-600 text-white rounded-lg flex items-center justify-center mb-3 group-hover:scale-110 transition-transform shadow-sm">
            <MessageSquare className="w-5 h-5" />
          </div>
          <h3 className="font-bold text-gray-900 dark:text-white text-base">AI Chat Assistant</h3>
          <p className="text-gray-500 dark:text-gray-400 text-xs mt-1">Get instant answers to your academic and placement queries.</p>
        </div>

        <div
          onClick={() => navigate('/student/chat')}
          className="bg-gradient-to-br from-blue-50 to-cyan-50 dark:from-blue-950/40 dark:to-cyan-950/40 border border-blue-200 dark:border-blue-800/60 hover:border-blue-400 dark:hover:border-blue-600 p-5 rounded-xl shadow-sm hover:shadow-md transition-all cursor-pointer group"
        >
          <div className="w-10 h-10 bg-blue-600 text-white rounded-lg flex items-center justify-center mb-3 group-hover:scale-110 transition-transform shadow-sm">
            <BarChart3 className="w-5 h-5" />
          </div>
          <h3 className="font-bold text-gray-900 dark:text-white text-base">AI Performance</h3>
          <p className="text-gray-500 dark:text-gray-400 text-xs mt-1">View AI Chat Analyzer metrics and performance analytics.</p>
        </div>

        <div
          onClick={() => navigate('/student/profile')}
          className="bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-950/40 dark:to-emerald-950/40 border border-green-200 dark:border-green-800/60 hover:border-green-400 dark:hover:border-green-600 p-5 rounded-xl shadow-sm hover:shadow-md transition-all cursor-pointer group"
        >
          <div className="w-10 h-10 bg-green-600 text-white rounded-lg flex items-center justify-center mb-3 group-hover:scale-110 transition-transform shadow-sm">
            <User className="w-5 h-5" />
          </div>
          <h3 className="font-bold text-gray-900 dark:text-white text-base">Update Profile</h3>
          <p className="text-gray-500 dark:text-gray-400 text-xs mt-1">Keep your academic and contact information up to date.</p>
        </div>
      </div>

      {/* AI Chat Analytics Section */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-indigo-600" />
              AI Chat Performance Analytics
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Real-time insights into AI Chat Analyzer performance and classification quality
            </p>
          </div>
        </div>
        <AIChatAnalytics />
      </div>
    </div>
  )
}

export default StudentDashboard
