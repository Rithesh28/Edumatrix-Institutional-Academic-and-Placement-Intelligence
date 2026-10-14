import React from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'

function LecturerDashboard() {
  const { user } = useAuthStore()
  const navigate = useNavigate()

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Lecturer Dashboard</h1>
      <div className="bg-white dark:bg-gray-900 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-800">
        <p className="text-gray-700 dark:text-gray-200 font-semibold text-lg">Welcome, {user?.name}!</p>
        <p className="text-gray-500 dark:text-gray-400 mt-1">Role: Lecturer • {user?.department || 'Department'}</p>
        <p className="text-gray-500 dark:text-gray-400">Email: {user?.email}</p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mt-6">
        <div 
          onClick={() => navigate('/lecturer/course-materials')}
          className="bg-white dark:bg-gray-900 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-800 hover:border-blue-500 dark:hover:border-blue-500 cursor-pointer transition-all hover:shadow-md"
        >
          <h3 className="font-semibold text-lg text-gray-900 dark:text-white mb-2">📖 Course Materials</h3>
          <p className="text-gray-500 dark:text-gray-400 text-sm">Upload, review, and publish lecture notes</p>
        </div>
        <div 
          onClick={() => navigate('/lecturer/circulars')}
          className="bg-white dark:bg-gray-900 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-800 hover:border-blue-500 dark:hover:border-blue-500 cursor-pointer transition-all hover:shadow-md"
        >
          <h3 className="font-semibold text-lg text-gray-900 dark:text-white mb-2">📝 Circulars</h3>
          <p className="text-gray-500 dark:text-gray-400 text-sm">Post and manage announcements</p>
        </div>
        <div 
          onClick={() => navigate('/lecturer/chat')}
          className="bg-white dark:bg-gray-900 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-800 hover:border-blue-500 dark:hover:border-blue-500 cursor-pointer transition-all hover:shadow-md"
        >
          <h3 className="font-semibold text-lg text-gray-900 dark:text-white mb-2">💬 Chat</h3>
          <p className="text-gray-500 dark:text-gray-400 text-sm">Message students and faculty</p>
        </div>
        <div 
          onClick={() => navigate('/lecturer/exam-duties')}
          className="bg-white dark:bg-gray-900 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-800 hover:border-blue-500 dark:hover:border-blue-500 cursor-pointer transition-all hover:shadow-md"
        >
          <h3 className="font-semibold text-lg text-gray-900 dark:text-white mb-2">📅 Exam Duties</h3>
          <p className="text-gray-500 dark:text-gray-400 text-sm">View and manage duty schedule</p>
        </div>
      </div>
    </div>
  )
}

export default LecturerDashboard