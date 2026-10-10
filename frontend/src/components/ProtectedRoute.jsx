import React from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'

function ProtectedRoute({ allowedRoles, children }) {
  const { token, user } = useAuthStore()
  const location = useLocation()

  // 1. Unauthenticated -> Redirect to login
  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  // 2. Validate role if allowedRoles is specified
  if (allowedRoles && allowedRoles.length > 0) {
    const rawRole = user?.role || localStorage.getItem('userRole') || ''
    const currentRole = String(rawRole).toLowerCase()
    const normalizedAllowed = allowedRoles.map((r) => String(r).toLowerCase())

    if (!currentRole || !normalizedAllowed.includes(currentRole)) {
      // Authenticated but unauthorized for this role
      return <Navigate to="/unauthorized" state={{ from: location, requiredRoles: allowedRoles }} replace />
    }
  }

  return children ? children : <Outlet />
}

export default ProtectedRoute