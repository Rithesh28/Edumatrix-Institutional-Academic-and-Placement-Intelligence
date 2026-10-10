import React, { useState, useEffect } from 'react'
import { useAuthStore } from '../../store/authStore'
import axios from 'axios'
import toast from 'react-hot-toast'
import ExamDutyCard from '../../components/ExamDutyCard'
import ExamDutyConflict from '../../components/ExamDutyConflict'
import useExamDuties from '../../hooks/useExamDuties'
import { API_URL } from '../../services/api'

const LecturerExamDuties = () => {
  const [duties, setDuties] = useState([])
  const [conflicts, setConflicts] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [showConflicts, setShowConflicts] = useState(false)
  const { token } = useAuthStore()

  const fetchDuties = async () => {
    try {
      const response = await axios.get(`${API_URL}/exam-duties/me`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setDuties(response.data)
      
      // Check for conflicts (simple detection)
      const dutyMap = {}
      const foundConflicts = []
      
      response.data.forEach(duty => {
        const key = `${duty.date}`
        if (dutyMap[key]) {
          // Check if times overlap
          if (duty.start_time < dutyMap[key].end_time && duty.end_time > dutyMap[key].start_time) {
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
          }
        } else {
          dutyMap[key] = duty
        }
      })
      
      setConflicts(foundConflicts)
    } catch (error) {
      console.error('Failed to fetch duties:', error)
      toast.error('Failed to load duties')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDuties()
  }, [])

  const handleConfirm = async (dutyId) => {
    try {
      await axios.put(
        `${API_URL}/exam-duties/${dutyId}/confirm`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      )
      toast.success('Duty confirmed successfully')
      fetchDuties()
    } catch (error) {
      console.error('Failed to confirm:', error)
      toast.error('Failed to confirm duty')
    }
  }

  const handleCancel = async (dutyId) => {
    if (!window.confirm('Are you sure you want to cancel this duty?')) return
    try {
      await axios.put(
        `${API_URL}/exam-duties/${dutyId}/cancel`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      )
      toast.success('Duty cancelled')
      fetchDuties()
    } catch (error) {
      console.error('Failed to cancel:', error)
      toast.error('Failed to cancel duty')
    }
  }

  const handleAddToCalendar = (duty) => {
    const startDate = new Date(duty.date)
    const [hours, minutes] = duty.start_time.split(':')
    startDate.setHours(parseInt(hours), parseInt(minutes))
    
    const endDate = new Date(duty.date)
    const [endHours, endMinutes] = duty.end_time.split(':')
    endDate.setHours(parseInt(endHours), parseInt(endMinutes))
    
    const formatDate = (date) => {
      return date.toISOString().replace(/-|:|\.\d+/g, '')
    }
    
    const url = `https://calendar.google.com/calendar/r/eventedit?text=Exam Duty: ${duty.exam_name}&dates=${formatDate(startDate)}/${formatDate(endDate)}&details=Venue: ${duty.venue}&location=${duty.venue}`
    window.open(url, '_blank')
  }

  const getFilteredDuties = () => {
    if (filter === 'all') return duties
    return duties.filter(d => d.status === filter)
  }

  const getStats = () => {
    const total = duties.length
    const pending = duties.filter(d => d.status === 'pending').length
    const confirmed = duties.filter(d => d.status === 'confirmed').length
    const completed = duties.filter(d => d.status === 'completed').length
    return { total, pending, confirmed, completed }
  }

  const stats = getStats()
  const filteredDuties = getFilteredDuties()

  if (loading) {
    return <div className="text-center py-10 text-gray-500">Loading duties...</div>
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">My Exam Duties</h1>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <div className="bg-white dark:bg-gray-900 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800">
          <p className="text-sm text-gray-500 dark:text-gray-400">Total</p>
          <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{stats.total}</p>
        </div>
        <div className="bg-white dark:bg-gray-900 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800">
          <p className="text-sm text-gray-500 dark:text-gray-400">Pending</p>
          <p className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">{stats.pending}</p>
        </div>
        <div className="bg-white dark:bg-gray-900 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800">
          <p className="text-sm text-gray-500 dark:text-gray-400">Confirmed</p>
          <p className="text-2xl font-bold text-green-600 dark:text-green-400">{stats.confirmed}</p>
        </div>
        <div className="bg-white dark:bg-gray-900 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800">
          <p className="text-sm text-gray-500 dark:text-gray-400">Completed</p>
          <p className="text-2xl font-bold text-purple-600 dark:text-purple-400">{stats.completed}</p>
        </div>
      </div>

      {/* Conflicts Warning */}
      {conflicts.length > 0 && (
        <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-4 flex items-center justify-between">
          <div>
            <span className="text-red-700 dark:text-red-300 font-medium">⚠️ {conflicts.length} conflict{conflicts.length > 1 ? 's' : ''} detected</span>
            <span className="text-red-600 dark:text-red-400 text-sm ml-2">You have overlapping duties</span>
          </div>
          <button
            onClick={() => setShowConflicts(!showConflicts)}
            className="px-3 py-1 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm"
          >
            {showConflicts ? 'Hide' : 'View'}
          </button>
        </div>
      )}

      {/* Conflicts Section */}
      {showConflicts && conflicts.length > 0 && (
        <div className="mb-4">
          <ExamDutyConflict
            conflicts={conflicts}
            onClose={() => setShowConflicts(false)}
            onResolve={() => {
              setShowConflicts(false)
              fetchDuties()
            }}
          />
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-2 mb-4">
        {['all', 'pending', 'confirmed', 'completed', 'cancelled'].map((status) => (
          <button
            key={status}
            onClick={() => setFilter(status)}
            className={`px-3 py-1 text-sm rounded-lg transition-colors ${
              filter === status
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
            }`}
          >
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </button>
        ))}
      </div>

      {/* Duties List */}
      {filteredDuties.length === 0 ? (
        <div className="text-center py-10 text-gray-500">No duties found</div>
      ) : (
        <div className="space-y-3">
          {filteredDuties.map((duty) => (
            <ExamDutyCard
              key={duty.id}
              duty={duty}
              onConfirm={handleConfirm}
              onCancel={handleCancel}
              onAddToCalendar={handleAddToCalendar}
              hasConflict={conflicts.some(c => c.duty_id === duty.id || c.conflicting_duty_id === duty.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export default LecturerExamDuties