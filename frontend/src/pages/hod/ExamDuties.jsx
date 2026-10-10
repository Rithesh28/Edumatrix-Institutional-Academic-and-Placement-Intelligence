import React, { useState, useEffect, useCallback } from 'react'
import { useAuthStore } from '../../store/authStore'
import axios from 'axios'
import toast from 'react-hot-toast'
import ExamDutyUpload from '../../components/ExamDutyUpload'
import ExamDutyCard from '../../components/ExamDutyCard'
import ExamDutyList from '../../components/ExamDutyList'
import ExamDutyConflict from '../../components/ExamDutyConflict'
import { API_URL } from '../../services/api'

const HODExamDuties = () => {
  const [loading, setLoading] = useState(false)
  const [duties, setDuties] = useState([])
  const [conflicts, setConflicts] = useState([])
  const [fetching, setFetching] = useState(true)
  const [showConflicts, setShowConflicts] = useState(false)
  const [uploadResult, setUploadResult] = useState(null)
  const [refreshTrigger, setRefreshTrigger] = useState(0) // ✅ Force re-render
  const { token } = useAuthStore()

  const fetchDuties = useCallback(async () => {
    if (!token) {
      console.log('No token available')
      setFetching(false)
      return
    }
    
    try {
      setFetching(true)
      console.log('🔍 Fetching duties from /exam-duties/hod...')
      const response = await axios.get(`${API_URL}/exam-duties/hod`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      console.log('✅ Duties fetched:', response.data.length)
      setDuties(response.data)
      checkConflicts(response.data)
    } catch (error) {
      console.error('❌ Failed to fetch duties:', error)
      if (error.response?.status === 401) {
        toast.error('Session expired. Please login again.')
      } else {
        toast.error('Failed to load duties')
      }
    } finally {
      setFetching(false)
    }
  }, [token])

  const checkConflicts = (dutyList) => {
    const dutyMap = {}
    const foundConflicts = []
    
    dutyList.forEach(duty => {
      const key = `${duty.lecturer_id}-${duty.date}`
      if (dutyMap[key]) {
        foundConflicts.push({
          duty_id: duty.id,
          lecturer_id: duty.lecturer_id,
          lecturer_name: duty.lecturer_name,
          date: duty.date,
          exam_name: duty.exam_name,
          start_time: duty.start_time,
          end_time: duty.end_time,
          conflicting_duty_id: dutyMap[key].id,
          conflicting_exam: dutyMap[key].exam_name,
          conflict_type: 'time_overlap'
        })
      } else {
        dutyMap[key] = duty
      }
    })
    
    setConflicts(foundConflicts)
  }

  // ✅ Fetch on mount AND when refreshTrigger changes
  useEffect(() => {
    fetchDuties()
  }, [fetchDuties, refreshTrigger])

  // ✅ Handle upload success
  const handleUploadSuccess = (result) => {
    console.log('✅ Upload success callback received:', result)
    setUploadResult(result)
    toast.success(`✅ ${result.created || 0} duties created successfully`)
    
    // ✅ Force refresh by updating trigger
    setRefreshTrigger(prev => prev + 1)
  }

  const handleUploadError = (error) => {
    toast.error(error || 'Failed to upload exam duties')
  }

  const handleDutyAction = async (dutyId, action) => {
    try {
      if (action === 'confirm') {
        await axios.put(
          `${API_URL}/exam-duties/${dutyId}/confirm`,
          {},
          { headers: { Authorization: `Bearer ${token}` } }
        )
        toast.success('Duty confirmed')
      } else if (action === 'delete') {
        if (!window.confirm('Are you sure you want to delete this duty?')) return
        await axios.delete(
          `${API_URL}/exam-duties/${dutyId}`,
          { headers: { Authorization: `Bearer ${token}` } }
        )
        toast.success('Duty deleted')
      }
      // ✅ Refresh after action
      setRefreshTrigger(prev => prev + 1)
    } catch (error) {
      console.error('Action failed:', error)
      toast.error(error.response?.data?.detail || 'Action failed')
    }
  }

  const getStatusBadge = (status) => {
    const colors = {
      pending: 'bg-yellow-100 text-yellow-700',
      confirmed: 'bg-green-100 text-green-700',
      completed: 'bg-blue-100 text-blue-700',
      cancelled: 'bg-red-100 text-red-700'
    }
    return colors[status] || 'bg-gray-100 text-gray-700'
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">Exam Duties</h1>

      {/* Upload Section */}
      <ExamDutyUpload
        onSuccess={handleUploadSuccess}
        onError={handleUploadError}
        loading={loading}
        setLoading={setLoading}
      />

      {/* Upload Result Summary */}
      {uploadResult && (
        <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-4 mb-6">
          <div className="flex items-center gap-4 flex-wrap">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Upload Result:</span>
            <span className="text-sm text-green-600 dark:text-green-400">✅ Created: {uploadResult.created || 0}</span>
            <span className="text-sm text-yellow-600 dark:text-yellow-400">⏭️ Skipped: {uploadResult.skipped || 0}</span>
            <span className="text-sm text-red-600 dark:text-red-400">⚠️ Conflicts: {uploadResult.conflicts?.length || 0}</span>
            <button
              onClick={() => setShowConflicts(true)}
              className="text-sm text-red-600 dark:text-red-400 hover:text-red-800 underline"
            >
              View Conflicts
            </button>
          </div>
        </div>
      )}

      {/* Conflicts Section */}
      {conflicts.length > 0 && showConflicts && (
        <div className="mb-6">
          <ExamDutyConflict
            conflicts={conflicts}
            onClose={() => setShowConflicts(false)}
            onResolve={() => {
              setShowConflicts(false)
              setRefreshTrigger(prev => prev + 1)
            }}
          />
        </div>
      )}

      {/* Conflicts Warning */}
      {conflicts.length > 0 && !showConflicts && (
        <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-6 flex items-center justify-between">
          <div>
            <span className="text-red-700 dark:text-red-300 font-medium">⚠️ {conflicts.length} conflicts detected</span>
            <span className="text-red-600 dark:text-red-400 text-sm ml-2">Some lecturers have overlapping duties</span>
          </div>
          <button
            onClick={() => setShowConflicts(true)}
            className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm"
          >
            View Conflicts
          </button>
        </div>
      )}

      {/* Duties List */}
      <ExamDutyList
        duties={duties}
        loading={fetching}
        onAction={handleDutyAction}
        getStatusBadge={getStatusBadge}
        emptyMessage="No duties uploaded yet"
        role="hod"
      />
    </div>
  )
}

export default HODExamDuties