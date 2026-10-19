import React from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import UnifiedBell from './UnifiedBell'
import ThemeToggle from './ThemeToggle'
import toast from 'react-hot-toast'

function Layout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuthStore()

  const isItemActive = (itemPath) => {
    if (location.pathname === itemPath) return true
    if (itemPath !== '/' && location.pathname.startsWith(itemPath + '/')) return true
    return false
  }

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
        { name: 'Study Buddy', path: '/student/study-buddy', icon: '📚' },
        { name: 'Campus Jobs', path: '/student/jobs', icon: '💼' },
        { name: 'My Applications', path: '/student/applications', icon: '📋' },
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
        { name: 'Course Materials', path: '/lecturer/course-materials', icon: '📖' },
        { name: 'Chat', path: '/lecturer/chat', icon: '💬' },
        { name: 'Circulars', path: '/lecturer/circulars', icon: '📝' },
        { name: 'Exam Duties', path: '/lecturer/exam-duties', icon: '📅' },
      ]
    }
    if (role === 'hod') {
      return [
        { name: 'Dashboard', path: '/hod/dashboard', icon: '📊' },
        { name: 'Chat', path: '/hod/chat', icon: '💬' },
        { name: 'Exam Duties', path: '/hod/exam-duties', icon: '📅' },
        { name: 'Circulars', path: '/hod/circulars', icon: '📢' },
      ]
    }
    if (role === 'placement_officer' || role === 'placement') {
      return [
        { name: 'Dashboard', path: '/placement/dashboard', icon: '📊' },
        { name: 'Manage Companies', path: '/placement/companies', icon: '🏢' },
        { name: 'Manage Jobs', path: '/placement/jobs', icon: '💼' },
        { name: 'Recruitment Drives', path: '/placement/circulars', icon: '📢' },
        { name: 'Applications', path: '/placement/applications', icon: '📑' },
        { name: 'View Students', path: '/placement/students', icon: '👨‍🎓' },
        { name: 'Reports', path: '/placement/reports', icon: '📈' },
        { name: 'Chat', path: '/placement/chat', icon: '💬' },
      ]
    }
    if (role === 'admin') {
      return [
        { name: 'Dashboard', path: '/admin/dashboard', icon: '📊' },
        { name: 'Users', path: '/admin/users', icon: '👥' },
        { name: 'Subjects', path: '/admin/subjects', icon: '📚' },
        { name: 'Audit Logs', path: '/admin/logs', icon: '📋' },
        { name: 'Resume Analyzer', path: '/placement/resume-analyzer', icon: '📄' },
        { name: 'Placement', path: '/placement/dashboard', icon: '💼' },
        { name: 'Files', path: '/files', icon: '📁' },
      ]
    }
    return []
  }

  const navItems = getNavItems()

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100 transition-colors duration-200">
      {/* Navbar */}
      <nav className="bg-white dark:bg-gray-900 shadow-sm border-b border-gray-200 dark:border-gray-800 sticky top-0 z-50 transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <h1 
                className="text-xl font-bold text-blue-600 dark:text-blue-400 cursor-pointer" 
                onClick={() => navigate(getDashboardLink())}
              >
                EduMatrix
              </h1>
              <span className="ml-2 text-sm text-gray-500 dark:text-gray-400 capitalize bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded border border-transparent dark:border-gray-700">
                {user?.role}
              </span>
            </div>
            <div className="flex items-center space-x-2 sm:space-x-4">
              <UnifiedBell />
              <ThemeToggle id="navbar-theme-toggle" />
              <span className="text-gray-700 dark:text-gray-300 hidden md:block text-sm font-medium">Welcome, {user?.name}</span>
              <button
                onClick={handleLogout}
                className="px-3.5 py-1.5 sm:px-4 sm:py-2 text-xs sm:text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors flex-shrink-0"
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
          className="w-64 bg-white dark:bg-gray-900 shadow-sm min-h-screen border-r border-gray-200 dark:border-gray-800 fixed lg:relative z-40 transform -translate-x-full lg:translate-x-0 transition-transform duration-200 ease-in-out" 
          id="sidebar"
        >
          <nav className="mt-6 px-4 space-y-1">
            {navItems.map((item) => {
              const active = isItemActive(item.path);
              return (
                <button
                  key={item.path}
                  onClick={() => {
                    navigate(item.path);
                    if (window.innerWidth < 1024) {
                      document.getElementById('sidebar').classList.add('-translate-x-full');
                    }
                  }}
                  className={`w-full text-left px-4 py-2 rounded-lg transition-colors flex items-center space-x-3 cursor-pointer ${
                    active
                      ? 'bg-blue-50 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 font-semibold shadow-sm'
                      : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 font-medium'
                  }`}
                >
                  <span className="text-xl">{item.icon}</span>
                  <span>{item.name}</span>
                </button>
              );
            })}
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