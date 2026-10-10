import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import ThemeToggle from '../components/ThemeToggle'
import toast from 'react-hot-toast'

function Login() {
  const navigate = useNavigate()
  const { login, token, user } = useAuthStore()
  const [loading, setLoading] = useState(false)
  const [formData, setFormData] = useState({
    email: '',
    password: ''
  })

  // Redirect if already logged in
  useEffect(() => {
    if (token && user) {
      const role = user.role?.toLowerCase();
      const roleMap = {
        'student': '/student/dashboard',
        'lecturer': '/lecturer/dashboard',
        'hod': '/hod/dashboard',
        'admin': '/admin/dashboard',
        'placement_officer': '/placement/dashboard'
      };
      const redirectPath = roleMap[role] || '/login';
      navigate(redirectPath, { replace: true });
    }
  }, [token, user, navigate]);

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    })
  }

  const getErrorMessage = (error) => {
    const detail = error.response?.data?.detail
    if (!detail) return error.message || 'Login failed'
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail.map(item => item.msg || JSON.stringify(item)).join(', ')
    }
    if (typeof detail === 'object') {
      return detail.msg || JSON.stringify(detail)
    }
    return String(detail)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    
    try {
      const response = await login(formData.email.trim(), formData.password)
      toast.success('Login successful!')
      
      // Get role from response
      const userData = response?.user || user;
      const role = userData?.role?.toLowerCase();
      const roleMap = {
        'student': '/student/dashboard',
        'lecturer': '/lecturer/dashboard',
        'hod': '/hod/dashboard',
        'admin': '/admin/dashboard',
        'placement_officer': '/placement/dashboard'
      };
      const redirectPath = roleMap[role] || '/login';
      
      // Navigate after a small delay to ensure state is updated
      setTimeout(() => {
        navigate(redirectPath, { replace: true });
      }, 100);
      
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 dark:from-gray-950 dark:via-gray-900 dark:to-indigo-950 p-4 relative transition-colors duration-200">
      {/* Top Header Theme Toggle */}
      <div className="absolute top-4 right-4 sm:top-6 sm:right-6 z-20">
        <ThemeToggle id="login-theme-toggle" />
      </div>

      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-xl border border-gray-100 dark:border-gray-800 w-full max-w-md p-8 relative transition-colors duration-200">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-blue-600 dark:text-blue-400">EduMatrix</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">AI-Powered College Platform</p>
        </div>
        
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Email Address
            </label>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              required
              className="w-full px-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors"
              placeholder="you@college.edu"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Password
            </label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
              className="w-full px-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors"
              placeholder="••••••••"
            />
          </div>
          
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg disabled:opacity-50 disabled:cursor-not-allowed shadow-sm transition-colors"
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>
        
        <p className="text-center text-gray-600 dark:text-gray-400 mt-6 text-sm">
          Don't have an account?{' '}
          <Link to="/register" className="text-blue-600 dark:text-blue-400 hover:underline font-medium">
            Register
          </Link>
        </p>
      </div>
    </div>
  )
}

export default Login