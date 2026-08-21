import React from 'react'

const ExamDutyConflict = ({ conflicts, onClose, onResolve }) => {
  if (!conflicts || conflicts.length === 0) {
    return null
  }

  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
      <div className="flex justify-between items-center mb-3">
        <h3 className="text-lg font-semibold text-red-800">
          ⚠️ Duty Conflicts ({conflicts.length})
        </h3>
        <div className="flex gap-2">
          {onResolve && (
            <button
              onClick={onResolve}
              className="px-3 py-1 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700"
            >
              Resolve All
            </button>
          )}
          {onClose && (
            <button
              onClick={onClose}
              className="px-3 py-1 text-sm text-gray-600 hover:text-gray-800"
            >
              ✕ Close
            </button>
          )}
        </div>
      </div>

      <p className="text-sm text-red-700 mb-3">
        The following lecturers have overlapping exam duties:
      </p>

      <div className="space-y-3">
        {conflicts.map((conflict, index) => (
          <div key={index} className="bg-white border border-red-200 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <span className="font-medium text-red-800">{conflict.lecturer_name || `Lecturer ID: ${conflict.lecturer_id}`}</span>
              <span className="text-xs text-red-600">⚠️ Conflict</span>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="bg-red-50 p-2 rounded border border-red-100">
                <p className="text-xs text-gray-500">Current Duty</p>
                <p className="text-sm font-medium text-gray-800">{conflict.exam_name}</p>
                <p className="text-xs text-gray-600">
                  📅 {new Date(conflict.date).toLocaleDateString()} | ⏰ {conflict.start_time} - {conflict.end_time}
                </p>
              </div>
              
              <div className="bg-red-50 p-2 rounded border border-red-100">
                <p className="text-xs text-gray-500">Conflicting Duty</p>
                <p className="text-sm font-medium text-gray-800">{conflict.conflicting_exam}</p>
                <p className="text-xs text-gray-600">
                  📅 {new Date(conflict.conflicting_date || conflict.date).toLocaleDateString()} | ⏰ {conflict.conflicting_start_time || conflict.start_time} - {conflict.conflicting_end_time || conflict.end_time}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-3 text-xs text-red-600">
        💡 Tip: Update the duty schedule or reassign one of the duties to resolve conflicts.
      </div>
    </div>
  )
}

export default ExamDutyConflict