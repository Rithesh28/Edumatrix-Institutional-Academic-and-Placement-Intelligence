import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { useAuthStore } from '../../store/authStore'
import { API_URL } from '../../services/api'

const HODDashboard = () => {
  const navigate = useNavigate()
  const { token } = useAuthStore()
  const [stats, setStats] = useState({
    total: 0,
    pending: 0,
    confirmed: 0,
    completed: 0
  })

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await axios.get(`${API_URL}/exam-duties/hod`, {
          headers: { Authorization: `Bearer ${token}` }
        })
        const duties = response.data
        setStats({
          total: duties.length,
          pending: duties.filter(d => d.status === 'pending').length,
          confirmed: duties.filter(d => d.status === 'confirmed').length,
          completed: duties.filter(d => d.status === 'completed').length
        })
      } catch (error) {
        console.error('Failed to fetch stats:', error)
      }
    }
    fetchStats()
  }, [token])

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">HOD Dashboard</h1>
        <button
          onClick={() => navigate('/hod/exam-duties')}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors shadow-sm"
        >
          📤 Upload Exam Duties
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white dark:bg-gray-900 p-6 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800">
          <h3 className="text-lg font-semibold text-gray-700 dark:text-gray-300">Total Duties</h3>
          <p className="text-3xl font-bold text-blue-600 dark:text-blue-400 mt-2">{stats.total}</p>
        </div>
        <div className="bg-white dark:bg-gray-900 p-6 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800">
          <h3 className="text-lg font-semibold text-gray-700 dark:text-gray-300">Pending</h3>
          <p className="text-3xl font-bold text-yellow-600 dark:text-yellow-400 mt-2">{stats.pending}</p>
        </div>
        <div className="bg-white dark:bg-gray-900 p-6 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800">
          <h3 className="text-lg font-semibold text-gray-700 dark:text-gray-300">Confirmed</h3>
          <p className="text-3xl font-bold text-green-600 dark:text-green-400 mt-2">{stats.confirmed}</p>
        </div>
        <div className="bg-white dark:bg-gray-900 p-6 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800">
          <h3 className="text-lg font-semibold text-gray-700 dark:text-gray-300">Completed</h3>
          <p className="text-3xl font-bold text-purple-600 dark:text-purple-400 mt-2">{stats.completed}</p>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white dark:bg-gray-900 p-6 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800">
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white mb-2">📤 Exam Duties</h3>
          <p className="text-gray-500 dark:text-gray-400 text-sm mb-4">Upload and manage exam duty schedules</p>
          <button
            onClick={() => navigate('/hod/exam-duties')}
            className="w-full px-4 py-2 bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 rounded-lg hover:bg-blue-200 dark:hover:bg-blue-900/70 border border-transparent dark:border-blue-700/50 font-medium transition-colors cursor-pointer"
          >
            Manage Exam Duties
          </button>
        </div>

        <div className="bg-white dark:bg-gray-900 p-6 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800">
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white mb-2">📢 Circulars</h3>
          <p className="text-gray-500 dark:text-gray-400 text-sm mb-4">Post and manage department circulars</p>
          <button
            onClick={() => navigate('/hod/circulars')}
            className="w-full px-4 py-2 bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 rounded-lg hover:bg-green-200 dark:hover:bg-green-900/70 border border-transparent dark:border-green-700/50 font-medium transition-colors cursor-pointer"
          >
            Manage Circulars
          </button>
        </div>

        <div className="bg-white dark:bg-gray-900 p-6 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800">
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white mb-2">📁 File Manager</h3>
          <p className="text-gray-500 dark:text-gray-400 text-sm mb-4">Browse and manage department files</p>
          <button
            onClick={() => navigate('/files')}
            className="w-full px-4 py-2 bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 rounded-lg hover:bg-purple-200 dark:hover:bg-purple-900/70 border border-transparent dark:border-purple-700/50 font-medium transition-colors cursor-pointer"
          >
            Open File Manager
          </button>
        </div>
      </div>
    </div>
  )
}

export default HODDashboard