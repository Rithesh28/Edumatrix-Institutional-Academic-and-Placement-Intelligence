import { useState, useEffect, useCallback } from 'react'
import { useAuthStore } from '../store/authStore'
import { examDutyAPI } from '../services/api'
import toast from 'react-hot-toast'

export const useExamDuties = () => {
  const [duties, setDuties] = useState([])
  const [conflicts, setConflicts] = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const { token, user } = useAuthStore()

  // Fetch duties based on role
  const fetchDuties = useCallback(async () => {
    setLoading(true)
    setError(null)
    
    try {
      let response
      
      if (user?.role === 'hod' || user?.role === 'admin') {
        response = await examDutyAPI.getHODDuties()
      } else if (user?.role === 'lecturer') {
        response = await examDutyAPI.getMyDuties()
      } else {
        setDuties([])
        setLoading(false)
        return
      }
      
      setDuties(response.data || [])
      
      // Detect conflicts
      const foundConflicts = detectConflicts(response.data || [])
      setConflicts(foundConflicts)
      
    } catch (error) {
      console.error('Failed to fetch duties:', error)
      setError(error.response?.data?.detail || 'Failed to load duties')
      toast.error('Failed to load duties')
    } finally {
      setLoading(false)
    }
  }, [user?.role])

  // Detect conflicts in duties
  const detectConflicts = useCallback((dutyList) => {
    const dutyMap = {}
    const foundConflicts = []
    
    dutyList.forEach(duty => {
      const key = `${duty.lecturer_id}-${duty.date}`
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
    
    return foundConflicts
  }, [])

  // Upload exam duty file
  const uploadDuty = useCallback(async (file) => {
    setUploading(true)
    setError(null)
    
    try {
      const response = await examDutyAPI.upload(file)
      
      if (response.data) {
        toast.success(`✅ ${response.data.created || 0} duties created successfully`)
        
        // Refresh duties after upload
        await fetchDuties()
        
        return response.data
      }
    } catch (error) {
      console.error('Upload failed:', error)
      const errorMsg = error.response?.data?.detail || 'Failed to upload exam duties'
      setError(errorMsg)
      toast.error(errorMsg)
      throw error
    } finally {
      setUploading(false)
    }
  }, [fetchDuties])

  // Upload async with polling
  const uploadDutyAsync = useCallback(async (file) => {
    setUploading(true)
    setError(null)
    
    try {
      const response = await examDutyAPI.uploadAsync(file)
      const taskId = response.data.task_id
      
      // Poll for status
      let status = 'pending'
      let result = null
      
      while (status === 'pending' || status === 'processing') {
        const statusResponse = await examDutyAPI.getUploadStatus(taskId)
        status = statusResponse.data.status
        
        if (status === 'completed') {
          result = statusResponse.data.result
          toast.success(`✅ ${result.created || 0} duties created successfully`)
          await fetchDuties()
          return result
        } else if (status === 'failed') {
          throw new Error(statusResponse.data.message || 'Processing failed')
        }
        
        // Wait 2 seconds before polling again
        await new Promise(resolve => setTimeout(resolve, 2000))
      }
      
    } catch (error) {
      console.error('Async upload failed:', error)
      const errorMsg = error.response?.data?.detail || error.message || 'Failed to upload exam duties'
      setError(errorMsg)
      toast.error(errorMsg)
      throw error
    } finally {
      setUploading(false)
    }
  }, [fetchDuties])

  // Confirm a duty
  const confirmDuty = useCallback(async (dutyId) => {
    try {
      await examDutyAPI.confirm(dutyId)
      toast.success('Duty confirmed successfully')
      await fetchDuties()
      return true
    } catch (error) {
      console.error('Failed to confirm:', error)
      toast.error(error.response?.data?.detail || 'Failed to confirm duty')
      return false
    }
  }, [fetchDuties])

  // Update a duty
  const updateDuty = useCallback(async (dutyId, data) => {
    try {
      await examDutyAPI.update(dutyId, data)
      toast.success('Duty updated successfully')
      await fetchDuties()
      return true
    } catch (error) {
      console.error('Failed to update:', error)
      toast.error(error.response?.data?.detail || 'Failed to update duty')
      return false
    }
  }, [fetchDuties])

  // Delete a duty
  const deleteDuty = useCallback(async (dutyId) => {
    try {
      await examDutyAPI.delete(dutyId)
      toast.success('Duty deleted successfully')
      await fetchDuties()
      return true
    } catch (error) {
      console.error('Failed to delete:', error)
      toast.error(error.response?.data?.detail || 'Failed to delete duty')
      return false
    }
  }, [fetchDuties])

  // Get upcoming duties
  const getUpcoming = useCallback(async () => {
    try {
      const response = await examDutyAPI.getUpcoming()
      return response.data || []
    } catch (error) {
      console.error('Failed to get upcoming duties:', error)
      return []
    }
  }, [])

  // Get duty details
  const getDutyDetails = useCallback(async (dutyId) => {
    try {
      const response = await examDutyAPI.getDutyDetails(dutyId)
      return response.data
    } catch (error) {
      console.error('Failed to get duty details:', error)
      toast.error('Failed to load duty details')
      return null
    }
  }, [])

  // Get department duties (for HOD)
  const getDepartmentDuties = useCallback(async () => {
    try {
      const response = await examDutyAPI.getDepartmentDuties()
      return response.data || []
    } catch (error) {
      console.error('Failed to get department duties:', error)
      return []
    }
  }, [])

  // Refresh conflicts only
  const refreshConflicts = useCallback(() => {
    const foundConflicts = detectConflicts(duties)
    setConflicts(foundConflicts)
    return foundConflicts
  }, [duties, detectConflicts])

  // Initial fetch
  useEffect(() => {
    if (token && (user?.role === 'hod' || user?.role === 'lecturer' || user?.role === 'admin')) {
      fetchDuties()
    }
  }, [token, user?.role, fetchDuties])

  return {
    // State
    duties,
    conflicts,
    loading,
    uploading,
    error,
    
    // Fetch methods
    fetchDuties,
    refreshConflicts,
    getUpcoming,
    getDutyDetails,
    getDepartmentDuties,
    
    // Actions
    uploadDuty,
    uploadDutyAsync,
    confirmDuty,
    updateDuty,
    deleteDuty,
    
    // Utils
    hasConflicts: conflicts.length > 0,
    conflictCount: conflicts.length,
  }
}

export default useExamDuties