import React, { useState } from 'react'

const ExamDutyCard = ({ duty, onConfirm, onCancel, onAddToCalendar, hasConflict }) => {
  const [expanded, setExpanded] = useState(false)

  const getStatusBadge = (status) => {
    const colors = {
      pending: 'bg-yellow-100 text-yellow-700',
      confirmed: 'bg-green-100 text-green-700',
      completed: 'bg-blue-100 text-blue-700',
      cancelled: 'bg-red-100 text-red-700'
    }
    return colors[status] || 'bg-gray-100 text-gray-700'
  }

  const getStatusText = (status) => {
    const texts = {
      pending: '⏳ Pending',
      confirmed: '✅ Confirmed',
      completed: '📌 Completed',
      cancelled: '❌ Cancelled'
    }
    return texts[status] || status
  }

  const getStatusIcon = (status) => {
    const icons = {
      pending: '⏳',
      confirmed: '✅',
      completed: '📌',
      cancelled: '❌'
    }
    return icons[status] || '📅'
  }

  return (
    <div className={`bg-white dark:bg-gray-900 rounded-lg shadow-sm border p-4 hover:shadow-md transition-all ${hasConflict ? 'border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/20' : 'border-gray-200 dark:border-gray-800'}`}>
      <div className="flex justify-between items-start">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span className="text-lg">{getStatusIcon(duty.status)}</span>
            <h3 className="font-semibold text-gray-900 dark:text-white">{duty.exam_name}</h3>
            <span className={`text-xs px-2 py-0.5 rounded-full ${getStatusBadge(duty.status)}`}>
              {getStatusText(duty.status)}
            </span>
            {hasConflict && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-300">
                ⚠️ Conflict
              </span>
            )}
            {duty.reminder_sent && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300">
                🔔 Reminder Sent
              </span>
            )}
          </div>
          
          <div className="space-y-1 text-sm">
            <p className="text-gray-600 dark:text-gray-300">
              <span className="font-medium text-gray-800 dark:text-gray-200">📅 Date:</span> {new Date(duty.date).toLocaleDateString('en-IN', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
            </p>
            <p className="text-gray-600 dark:text-gray-300">
              <span className="font-medium text-gray-800 dark:text-gray-200">⏰ Time:</span> {duty.start_time} - {duty.end_time}
            </p>
            {duty.venue && (
              <p className="text-gray-600 dark:text-gray-300">
                <span className="font-medium text-gray-800 dark:text-gray-200">📍 Venue:</span> {duty.venue}
              </p>
            )}
            {duty.hod_name && (
              <p className="text-gray-500 dark:text-gray-400 text-xs">
                <span className="font-medium">Uploaded by:</span> {duty.hod_name}
              </p>
            )}
            
            {/* Expandable Details */}
            {expanded && (
              <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-800">
                <p className="text-gray-600 dark:text-gray-300 text-xs">
                  <span className="font-medium">Department:</span> {duty.department}
                </p>
                <p className="text-gray-600 dark:text-gray-300 text-xs">
                  <span className="font-medium">Lecturer ID:</span> {duty.lecturer_id}
                </p>
                <p className="text-gray-600 dark:text-gray-300 text-xs">
                  <span className="font-medium">HOD ID:</span> {duty.hod_id}
                </p>
                <p className="text-gray-600 dark:text-gray-300 text-xs">
                  <span className="font-medium">Created:</span> {new Date(duty.created_at).toLocaleString()}
                </p>
                {duty.updated_at && (
                  <p className="text-gray-600 dark:text-gray-300 text-xs">
                    <span className="font-medium">Updated:</span> {new Date(duty.updated_at).toLocaleString()}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-2 ml-4">
          {/* Expand/Collapse Button */}
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-gray-500 hover:text-gray-700"
          >
            {expanded ? '▲ Less' : '▼ More'}
          </button>

          {/* Add to Calendar */}
          {onAddToCalendar && duty.status !== 'cancelled' && (
            <button
              onClick={() => onAddToCalendar(duty)}
              className="px-3 py-1 text-xs text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
            >
              📅 Add to Calendar
            </button>
          )}

          {/* Action Buttons */}
          {duty.status === 'pending' && (
            <>
              <button
                onClick={() => onConfirm(duty.id)}
                className="px-3 py-1 text-sm text-white bg-green-600 rounded-lg hover:bg-green-700 transition-colors"
              >
                ✅ Confirm
              </button>
              <button
                onClick={() => onCancel(duty.id)}
                className="px-3 py-1 text-sm text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors"
              >
                ❌ Cancel
              </button>
            </>
          )}
          
          {duty.status === 'confirmed' && (
            <span className="text-xs text-green-600 text-center">✓ Confirmed</span>
          )}
          
          {duty.status === 'completed' && (
            <span className="text-xs text-blue-600 text-center">✓ Completed</span>
          )}
          
          {duty.status === 'cancelled' && (
            <span className="text-xs text-red-600 text-center">✗ Cancelled</span>
          )}
        </div>
      </div>
    </div>
  )
}

export default ExamDutyCard