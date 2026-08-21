import React from 'react'
import { useAuthStore } from '../../store/authStore'

function AdminDashboard() {
  const { user } = useAuthStore()

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-4">Admin Dashboard</h1>
      <div className="card">
        <p className="text-gray-600">Welcome, {user?.name}!</p>
        <p className="text-gray-500 mt-2">Role: Administrator</p>
        <p className="text-gray-500">Email: {user?.email}</p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mt-6">
        <div className="card">
          <h3 className="font-semibold text-lg mb-2">👥 Users</h3>
          <p className="text-gray-500 text-sm">Manage students and lecturers</p>
        </div>
        <div className="card">
          <h3 className="font-semibold text-lg mb-2">📋 System Logs</h3>
          <p className="text-gray-500 text-sm">View application logs and activity</p>
        </div>
        <div className="card">
          <h3 className="font-semibold text-lg mb-2">📊 Analytics</h3>
          <p className="text-gray-500 text-sm">Platform usage statistics</p>
        </div>
      </div>
    </div>
  )
}

export default AdminDashboard