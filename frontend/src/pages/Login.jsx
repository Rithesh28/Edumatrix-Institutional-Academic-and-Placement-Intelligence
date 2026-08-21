import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
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
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-blue-600">EduMatrix</h1>
          <p className="text-gray-600 mt-2">AI-Powered College Platform</p>
        </div>
        
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Email Address
            </label>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="you@college.edu"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Password
            </label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="••••••••"
            />
          </div>
          
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>
        
        <p className="text-center text-gray-600 mt-6">
          Don't have an account?{' '}
          <Link to="/register" className="text-blue-600 hover:underline font-medium">
            Register
          </Link>
        </p>
      </div>
    </div>
  )
}

export default Login