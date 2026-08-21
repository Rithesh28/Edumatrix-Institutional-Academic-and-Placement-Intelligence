import React, { useState } from 'react'

const ExamDutyList = ({ 
  duties, 
  loading, 
  onAction, 
  getStatusBadge, 
  emptyMessage,
  role = 'hod'
}) => {
  const [sortField, setSortField] = useState('date')
  const [sortDirection, setSortDirection] = useState('asc')
  const [filterStatus, setFilterStatus] = useState('all')
  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 10

  // Filter duties
  const filteredDuties = duties.filter(duty => {
    if (filterStatus === 'all') return true
    return duty.status === filterStatus
  })

  // Sort duties
  const sortedDuties = [...filteredDuties].sort((a, b) => {
    let aVal = a[sortField] || ''
    let bVal = b[sortField] || ''
    
    if (sortField === 'date') {
      aVal = new Date(aVal).getTime()
      bVal = new Date(bVal).getTime()
    }
    
    if (typeof aVal === 'string') {
      aVal = aVal.toLowerCase()
      bVal = bVal.toLowerCase()
    }
    
    if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1
    if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1
    return 0
  })

  // Pagination
  const totalPages = Math.ceil(sortedDuties.length / itemsPerPage)
  const startIndex = (currentPage - 1) * itemsPerPage
  const paginatedDuties = sortedDuties.slice(startIndex, startIndex + itemsPerPage)

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('asc')
    }
  }

  const getSortIcon = (field) => {
    if (sortField !== field) return '↕'
    return sortDirection === 'asc' ? '↑' : '↓'
  }

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="text-center py-10 text-gray-500">Loading duties...</div>
      </div>
    )
  }

  if (duties.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="text-center py-10 text-gray-500">{emptyMessage || 'No duties found'}</div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      {/* Header */}
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold text-gray-800">
          {role === 'hod' ? 'Uploaded Duties' : 'My Duties'}
        </h2>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">{duties.length} duties</span>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="text-sm border border-gray-300 rounded-lg px-3 py-1"
          >
            <option value="all">All Status</option>
            <option value="pending">Pending</option>
            <option value="confirmed">Confirmed</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200">
              <th 
                className="text-left py-2 px-3 font-medium text-gray-600 cursor-pointer hover:text-gray-800"
                onClick={() => handleSort('lecturer_name')}
              >
                Lecturer {getSortIcon('lecturer_name')}
              </th>
              <th 
                className="text-left py-2 px-3 font-medium text-gray-600 cursor-pointer hover:text-gray-800"
                onClick={() => handleSort('exam_name')}
              >
                Exam {getSortIcon('exam_name')}
              </th>
              <th 
                className="text-left py-2 px-3 font-medium text-gray-600 cursor-pointer hover:text-gray-800"
                onClick={() => handleSort('date')}
              >
                Date {getSortIcon('date')}
              </th>
              <th 
                className="text-left py-2 px-3 font-medium text-gray-600 cursor-pointer hover:text-gray-800"
                onClick={() => handleSort('start_time')}
              >
                Time {getSortIcon('start_time')}
              </th>
              <th className="text-left py-2 px-3 font-medium text-gray-600">Venue</th>
              <th className="text-left py-2 px-3 font-medium text-gray-600">Status</th>
              {role === 'hod' && (
                <th className="text-left py-2 px-3 font-medium text-gray-600">Actions</th>
              )}
            </tr>
          </thead>
          <tbody>
            {paginatedDuties.map((duty) => (
              <tr key={duty.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="py-2 px-3 text-gray-800">{duty.lecturer_name || 'Unknown'}</td>
                <td className="py-2 px-3 text-gray-800">{duty.exam_name}</td>
                <td className="py-2 px-3 text-gray-800">{new Date(duty.date).toLocaleDateString()}</td>
                <td className="py-2 px-3 text-gray-800">
                  {duty.start_time} - {duty.end_time}
                </td>
                <td className="py-2 px-3 text-gray-800">{duty.venue}</td>
                <td className="py-2 px-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getStatusBadge(duty.status)}`}>
                    {duty.status}
                  </span>
                </td>
                {role === 'hod' && (
                  <td className="py-2 px-3">
                    <div className="flex items-center gap-2">
                      {duty.status === 'pending' && (
                        <button
                          onClick={() => onAction(duty.id, 'confirm')}
                          className="text-xs text-green-600 hover:text-green-800"
                        >
                          ✅ Confirm
                        </button>
                      )}
                      <button
                        onClick={() => onAction(duty.id, 'delete')}
                        className="text-xs text-red-600 hover:text-red-800"
                      >
                        🗑️ Delete
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-between items-center mt-4 pt-4 border-t border-gray-200">
          <span className="text-sm text-gray-500">
            Showing {startIndex + 1} to {Math.min(startIndex + itemsPerPage, sortedDuties.length)} of {sortedDuties.length}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="px-3 py-1 text-sm border border-gray-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
            >
              Previous
            </button>
            <button
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="px-3 py-1 text-sm border border-gray-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default ExamDutyList