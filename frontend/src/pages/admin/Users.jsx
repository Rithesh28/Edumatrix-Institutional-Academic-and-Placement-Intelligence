import React, { useEffect, useState } from 'react'
import { 
  Users as UsersIcon, 
  Search, 
  Filter, 
  Shield, 
  UserCheck, 
  UserX, 
  RefreshCw, 
  ChevronLeft, 
  ChevronRight,
  AlertTriangle
} from 'lucide-react'
import { adminService } from '../../services/adminService'
import { useAuthStore } from '../../store/authStore'
import toast from 'react-hot-toast'

const ROLES = [
  { value: 'student', label: 'Student', color: 'bg-blue-100 text-blue-700' },
  { value: 'lecturer', label: 'Lecturer', color: 'bg-emerald-100 text-emerald-700' },
  { value: 'hod', label: 'HOD', color: 'bg-purple-100 text-purple-700' },
  { value: 'placement_officer', label: 'Placement Officer', color: 'bg-amber-100 text-amber-700' },
  { value: 'admin', label: 'Admin', color: 'bg-red-100 text-red-700' },
]

function Users() {
  const { user: currentUser } = useAuthStore()
  const [users, setUsers] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [limit] = useState(15)
  const [isLoading, setIsLoading] = useState(false)

  // Filters
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedRole, setSelectedRole] = useState('')
  const [selectedStatus, setSelectedStatus] = useState('')

  // Confirmation Modals
  const [roleModalUser, setRoleModalUser] = useState(null)
  const [newRole, setNewRole] = useState('')
  const [statusModalUser, setStatusModalUser] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const fetchUsers = async () => {
    setIsLoading(true)
    try {
      const params = {
        page,
        limit,
        search: searchTerm.trim() || undefined,
        role: selectedRole || undefined,
        is_active: selectedStatus !== '' ? selectedStatus === 'active' : undefined,
      }
      const data = await adminService.getUsers(params)
      setUsers(data.items || [])
      setTotal(data.total || 0)
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to fetch users')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchUsers()
  }, [page, selectedRole, selectedStatus])

  const handleSearchSubmit = (e) => {
    e.preventDefault()
    setPage(1)
    fetchUsers()
  }

  const handleRoleChangeConfirm = async () => {
    if (!roleModalUser || !newRole) return
    setIsSubmitting(true)
    try {
      await adminService.updateUserRole(roleModalUser.id, newRole)
      toast.success(`Updated role for ${roleModalUser.name} to ${newRole}`)
      setRoleModalUser(null)
      fetchUsers()
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update user role')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleStatusToggleConfirm = async () => {
    if (!statusModalUser) return
    setIsSubmitting(true)
    try {
      const updatedStatus = !statusModalUser.is_active
      await adminService.updateUserStatus(statusModalUser.id, updatedStatus)
      toast.success(`Account ${updatedStatus ? 'activated' : 'deactivated'} for ${statusModalUser.name}`)
      setStatusModalUser(null)
      fetchUsers()
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update account status')
    } finally {
      setIsSubmitting(false)
    }
  }

  const getRoleBadge = (role) => {
    const found = ROLES.find(r => r.value === String(role).toLowerCase())
    return (
      <span className={`px-2.5 py-1 text-xs font-semibold rounded-full capitalize ${found?.color || 'bg-gray-100 text-gray-700'}`}>
        {found?.label || role}
      </span>
    )
  }

  const totalPages = Math.ceil(total / limit) || 1

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <UsersIcon className="w-7 h-7 text-blue-600 dark:text-blue-400" />
            <span>User Management</span>
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Manage institutional user accounts, access roles, and activation status.
          </p>
        </div>
        <button
          onClick={fetchUsers}
          className="px-3.5 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 flex items-center gap-2 font-medium shadow-sm transition-colors self-start sm:self-auto cursor-pointer"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filters Bar */}
      <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm flex flex-col md:flex-row items-center gap-4">
        <form onSubmit={handleSearchSubmit} className="flex-1 w-full relative">
          <input
            type="text"
            placeholder="Search by name or email..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
          <Search className="w-4 h-4 text-gray-400 dark:text-gray-500 absolute left-3.5 top-3" />
        </form>

        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          <select
            value={selectedRole}
            onChange={(e) => { setSelectedRole(e.target.value); setPage(1); }}
            className="px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Roles</option>
            {ROLES.map(r => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>

          <select
            value={selectedStatus}
            onChange={(e) => { setSelectedStatus(e.target.value); setPage(1); }}
            className="px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Statuses</option>
            <option value="active">Active Only</option>
            <option value="inactive">Inactive Only</option>
          </select>

          {(searchTerm || selectedRole || selectedStatus) && (
            <button
              onClick={() => {
                setSearchTerm('')
                setSelectedRole('')
                setSelectedStatus('')
                setPage(1)
              }}
              className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 font-medium px-2 py-1 cursor-pointer"
            >
              Reset Filters
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-50 dark:bg-gray-800/80 border-b border-gray-200 dark:border-gray-800 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                <th className="py-3.5 px-4">User</th>
                <th className="py-3.5 px-4">Role</th>
                <th className="py-3.5 px-4">Department</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4">Created</th>
                <th className="py-3.5 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-800 text-sm">
              {isLoading ? (
                <tr>
                  <td colSpan="6" className="text-center py-12">
                    <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-600 dark:border-blue-400 border-t-transparent mx-auto mb-2"></div>
                    <span className="text-gray-500 dark:text-gray-400 text-xs">Loading institutional users...</span>
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan="6" className="text-center py-12 text-gray-500 dark:text-gray-400">
                    <UsersIcon className="w-10 h-10 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
                    <p className="font-medium">No users found matching your criteria</p>
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Try modifying your search or filter settings</p>
                  </td>
                </tr>
              ) : (
                users.map((u) => {
                  const isCurrent = currentUser?.id === u.id
                  return (
                    <tr key={u.id} className="hover:bg-gray-50/80 dark:hover:bg-gray-800/50 transition-colors">
                      <td className="py-3.5 px-4">
                        <div className="flex items-center space-x-3">
                          <div className="w-9 h-9 rounded-full bg-blue-100 dark:bg-blue-900/60 text-blue-700 dark:text-blue-300 flex items-center justify-center font-bold text-sm">
                            {u.name?.charAt(0).toUpperCase() || 'U'}
                          </div>
                          <div>
                            <div className="font-semibold text-gray-900 dark:text-white flex items-center gap-1.5">
                              <span>{u.name}</span>
                              {isCurrent && (
                                <span className="text-[10px] bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 px-1.5 py-0.5 rounded font-medium border border-blue-200 dark:border-blue-800">
                                  You
                                </span>
                              )}
                            </div>
                            <div className="text-xs text-gray-500 dark:text-gray-400">{u.email}</div>
                          </div>
                        </div>
                      </td>
                      <td className="py-3.5 px-4">
                        {getRoleBadge(u.role)}
                      </td>
                      <td className="py-3.5 px-4 text-gray-600 dark:text-gray-300">
                        {u.department || 'General'}
                      </td>
                      <td className="py-3.5 px-4">
                        <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${u.is_active ? 'bg-green-100 dark:bg-green-950/60 text-green-700 dark:text-green-300' : 'bg-red-100 dark:bg-red-950/60 text-red-700 dark:text-red-300'}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${u.is_active ? 'bg-green-500' : 'bg-red-500'}`}></span>
                          {u.is_active ? 'Active' : 'Deactivated'}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-xs text-gray-500 dark:text-gray-400">
                        {u.created_at ? new Date(u.created_at).toLocaleDateString() : 'N/A'}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end space-x-2">
                          <button
                            onClick={() => {
                              setRoleModalUser(u)
                              setNewRole(u.role)
                            }}
                            className="px-2.5 py-1 text-xs border border-gray-300 dark:border-gray-700 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-200 font-medium transition-colors cursor-pointer"
                            title="Change Role"
                          >
                            Edit Role
                          </button>
                          <button
                            onClick={() => setStatusModalUser(u)}
                            disabled={isCurrent}
                            className={`p-1.5 rounded text-xs transition-colors cursor-pointer ${
                              isCurrent 
                                ? 'text-gray-300 dark:text-gray-600 cursor-not-allowed' 
                                : u.is_active 
                                  ? 'text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/50' 
                                  : 'text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-950/50'
                            }`}
                            title={isCurrent ? 'Cannot modify own status' : u.is_active ? 'Deactivate Account' : 'Activate Account'}
                          >
                            {u.is_active ? <UserX className="w-4 h-4" /> : <UserCheck className="w-4 h-4" />}
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="p-4 border-t border-gray-200 dark:border-gray-800 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-gray-500 dark:text-gray-400">
          <div>
            Showing <span className="font-semibold text-gray-700 dark:text-gray-200">{users.length > 0 ? (page - 1) * limit + 1 : 0}</span> to{' '}
            <span className="font-semibold text-gray-700 dark:text-gray-200">{Math.min(page * limit, total)}</span> of{' '}
            <span className="font-semibold text-gray-700 dark:text-gray-200">{total}</span> accounts
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setPage(p => Math.max(p - 1, 1))}
              disabled={page <= 1 || isLoading}
              className="p-1.5 border border-gray-300 dark:border-gray-700 rounded hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-2 font-medium">Page {page} of {totalPages}</span>
            <button
              onClick={() => setPage(p => Math.min(p + 1, totalPages))}
              disabled={page >= totalPages || isLoading}
              className="p-1.5 border border-gray-300 dark:border-gray-700 rounded hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Role Change Modal */}
      {roleModalUser && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-md w-full p-6 shadow-xl space-y-4 border border-gray-200 dark:border-gray-800">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900/60 text-blue-600 dark:text-blue-400 flex items-center justify-center">
                <Shield className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">Update User Role</h3>
                <p className="text-xs text-gray-500 dark:text-gray-400">{roleModalUser.name} ({roleModalUser.email})</p>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1.5">Select New Role</label>
              <select
                value={newRole}
                onChange={(e) => setNewRole(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500"
              >
                {ROLES.map(r => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </div>

            {currentUser?.id === roleModalUser.id && newRole !== 'admin' && (
              <div className="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-lg text-xs text-red-700 dark:text-red-300 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>You cannot remove your own admin privileges to avoid accidental lockout.</span>
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setRoleModalUser(null)}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleRoleChangeConfirm}
                disabled={isSubmitting || (currentUser?.id === roleModalUser.id && newRole !== 'admin')}
                className="px-4 py-2 text-sm font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 cursor-pointer"
              >
                {isSubmitting ? 'Updating...' : 'Save Role'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Status Toggle Modal */}
      {statusModalUser && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-md w-full p-6 shadow-xl space-y-4 border border-gray-200 dark:border-gray-800">
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center ${statusModalUser.is_active ? 'bg-red-100 dark:bg-red-950/60 text-red-600 dark:text-red-400' : 'bg-green-100 dark:bg-green-950/60 text-green-600 dark:text-green-400'}`}>
                {statusModalUser.is_active ? <UserX className="w-5 h-5" /> : <UserCheck className="w-5 h-5" />}
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                  {statusModalUser.is_active ? 'Deactivate Account' : 'Activate Account'}
                </h3>
                <p className="text-xs text-gray-500 dark:text-gray-400">{statusModalUser.name} ({statusModalUser.email})</p>
              </div>
            </div>

            <p className="text-sm text-gray-600 dark:text-gray-300">
              {statusModalUser.is_active 
                ? 'Are you sure you want to deactivate this account? The user will be unable to log in until reactivated.' 
                : 'Are you sure you want to activate this account? The user will regain system access.'}
            </p>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setStatusModalUser(null)}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleStatusToggleConfirm}
                disabled={isSubmitting}
                className={`px-4 py-2 text-sm font-semibold text-white rounded-lg disabled:opacity-50 cursor-pointer ${
                  statusModalUser.is_active ? 'bg-red-600 hover:bg-red-700' : 'bg-green-600 hover:bg-green-700'
                }`}
              >
                {isSubmitting ? 'Processing...' : statusModalUser.is_active ? 'Confirm Deactivate' : 'Confirm Activate'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Users
