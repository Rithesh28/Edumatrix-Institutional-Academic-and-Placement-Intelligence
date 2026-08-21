import React from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import UnifiedBell from './UnifiedBell'
import toast from 'react-hot-toast'

function Layout() {
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()

  const handleLogout = () => {
    logout()
    toast.success('Logged out successfully')
    navigate('/login')
  }

  const getDashboardLink = () => {
    const role = user?.role?.toLowerCase() || ''
    if (role === 'student') return '/student/dashboard'
    if (role === 'lecturer') return '/lecturer/dashboard'
    if (role === 'hod') return '/hod/dashboard'
    if (role === 'placement_officer' || role === 'placement') return '/placement/dashboard'
    return '/admin/dashboard'
  }

  // Navigation items based on role
  const getNavItems = () => {
    const role = user?.role?.toLowerCase() || ''
    if (role === 'student') {
      return [
        { name: 'Dashboard', path: '/student/dashboard', icon: '📊' },
        { name: 'Chat', path: '/student/chat', icon: '💬' },
        { name: 'Circulars', path: '/student/circulars', icon: '📢' },
        { name: 'Resume Analyzer', path: '/placement/resume-analyzer', icon: '📄' },
        { name: 'Profile', path: '/student/profile', icon: '👤' },
        { name: 'Reminders', path: '/student/reminders', icon: '🔔' },
      ]
    }
    if (role === 'lecturer') {
      return [
        { name: 'Dashboard', path: '/lecturer/dashboard', icon: '📊' },
        { name: 'Chat', path: '/lecturer/chat', icon: '💬' },
        { name: 'Circulars', path: '/lecturer/circulars', icon: '📝' },
        { name: 'Exam Duties', path: '/lecturer/exam-duties', icon: '📅' },
      ]
    }
    if (role === 'hod') {
      return [
        { name: 'Dashboard', path: '/hod/dashboard', icon: '📊' },
        { name: 'Exam Duties', path: '/hod/exam-duties', icon: '📅' },
        { name: 'Circulars', path: '/hod/circulars', icon: '📢' },
      ]
    }
    if (role === 'placement_officer' || role === 'placement') {
      return [
        { name: 'Dashboard', path: '/placement/dashboard', icon: '📊' },
        { name: 'Resume Analyzer', path: '/placement/resume-analyzer', icon: '📄' },
        { name: 'Companies', path: '/placement/companies', icon: '🏢' },
        { name: 'Jobs', path: '/placement/jobs', icon: '💼' },
        { name: 'Students', path: '/placement/students', icon: '👨‍🎓' },
        { name: 'Shortlist', path: '/placement/shortlist', icon: '📋' },
        { name: 'Reports', path: '/placement/reports', icon: '📈' },
        { name: 'Files', path: '/files', icon: '📁' },
      ]
    }
    if (role === 'admin') {
      return [
        { name: 'Dashboard', path: '/admin/dashboard', icon: '📊' },
        { name: 'Resume Analyzer', path: '/placement/resume-analyzer', icon: '📄' },
        { name: 'Placement', path: '/placement/dashboard', icon: '💼' },
        { name: 'Users', path: '/admin/users', icon: '👥' },
        { name: 'Logs', path: '/admin/logs', icon: '📋' },
        { name: 'Files', path: '/files', icon: '📁' },
      ]
    }
    return []
  }

  const navItems = getNavItems()

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navbar */}
      <nav className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <h1 
                className="text-xl font-bold text-blue-600 cursor-pointer" 
                onClick={() => navigate(getDashboardLink())}
              >
                EduMatrix
              </h1>
              <span className="ml-2 text-sm text-gray-500 capitalize bg-gray-100 px-2 py-1 rounded">
                {user?.role}
              </span>
            </div>
            <div className="flex items-center space-x-4">
              <UnifiedBell />
              <span className="text-gray-700 hidden sm:block">Welcome, {user?.name}</span>
              <button
                onClick={handleLogout}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Sidebar + Main Content */}
      <div className="flex">
        {/* Sidebar */}
        <aside 
          className="w-64 bg-white shadow-sm min-h-screen border-r border-gray-200 fixed lg:relative z-40 transform -translate-x-full lg:translate-x-0 transition-transform duration-200 ease-in-out" 
          id="sidebar"
        >
          <nav className="mt-6 px-4 space-y-1">
            {navItems.map((item) => (
              <button
                key={item.path}
                onClick={() => {
                  navigate(item.path)
                  if (window.innerWidth < 1024) {
                    document.getElementById('sidebar').classList.add('-translate-x-full')
                  }
                }}
                className="w-full text-left px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors flex items-center space-x-3"
              >
                <span className="text-xl">{item.icon}</span>
                <span>{item.name}</span>
              </button>
            ))}
          </nav>
        </aside>

        {/* Mobile menu button */}
        <button
          onClick={() => {
            const sidebar = document.getElementById('sidebar')
            sidebar.classList.toggle('-translate-x-full')
          }}
          className="lg:hidden fixed bottom-4 left-4 z-50 bg-blue-600 text-white p-3 rounded-full shadow-lg"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        {/* Main Content */}
        <main className="flex-1 p-4 sm:p-6 lg:ml-0">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default Layout