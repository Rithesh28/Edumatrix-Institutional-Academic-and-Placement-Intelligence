import React from 'react'
import { useAuthStore } from '../../store/authStore'

function LecturerDashboard() {
  const { user } = useAuthStore()

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-4">Lecturer Dashboard</h1>
      <div className="card">
        <p className="text-gray-600">Welcome, {user?.name}!</p>
        <p className="text-gray-500 mt-2">Role: Lecturer</p>
        <p className="text-gray-500">Email: {user?.email}</p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mt-6">
        <div className="card">
          <h3 className="font-semibold text-lg mb-2">📝 Circulars</h3>
          <p className="text-gray-500 text-sm">Post and manage announcements</p>
        </div>
        <div className="card">
          <h3 className="font-semibold text-lg mb-2">❓ Doubt Dashboard</h3>
          <p className="text-gray-500 text-sm">Review escalated student doubts</p>
        </div>
        <div className="card">
          <h3 className="font-semibold text-lg mb-2">📅 Exam Duties</h3>
          <p className="text-gray-500 text-sm">View and manage duty schedule</p>
        </div>
      </div>
    </div>
  )
}

export default LecturerDashboard