import React, { useState, useRef } from 'react'
import { useAuthStore } from '../store/authStore'
import axios from 'axios'
import toast from 'react-hot-toast'
import { API_URL } from '../services/api'

const ExamDutyUpload = ({ onSuccess, onError, loading, setLoading }) => {
  const [file, setFile] = useState(null)
  const [dragActive, setDragActive] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [parsePreview, setParsePreview] = useState(null)
  const [showPreview, setShowPreview] = useState(false)
  const fileInputRef = useRef(null)
  const { token } = useAuthStore()

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0]
      validateAndSetFile(droppedFile)
    }
  }

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0])
    }
  }

  const validateAndSetFile = (selectedFile) => {
    const validTypes = ['.pdf', '.jpg', '.jpeg', '.png', '.docx', '.doc']
    const ext = '.' + selectedFile.name.split('.').pop().toLowerCase()
    
    if (!validTypes.includes(ext)) {
      toast.error('Please upload a PDF, Image, or DOCX file')
      return
    }
    
    if (selectedFile.size > 5 * 1024 * 1024) {
      toast.error('File size must be less than 5MB')
      return
    }
    
    setFile(selectedFile)
    setParsePreview(null)
    setShowPreview(false)
  }

  const handleUpload = async () => {
    if (!file) {
      toast.error('Please select a file')
      return
    }

    setLoading(true)
    setUploadProgress(10)
    
    const formData = new FormData()
    formData.append('file', file)

    try {
      setUploadProgress(30)
      
      const response = await axios.post(`${API_URL}/exam-duties/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
          Authorization: `Bearer ${token}`
        },
        timeout: 60000,
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          setUploadProgress(Math.min(percentCompleted, 90))
        }
      })

      setUploadProgress(100)
      
      // ✅ FIX: Handle response correctly
      console.log('✅ Upload response:', response.data)
      
      // Check if we have data
      if (response.data) {
        const result = response.data
        
        // Show preview of extracted data
        if (result.duties && result.duties.length > 0) {
          setParsePreview({
            duties: result.duties,
            created: result.created || 0,
            skipped: result.skipped || 0,
            conflicts: result.conflicts || [],
            unmatched: result.unmatched_lecturers || []
          })
          setShowPreview(true)
          toast.success(`✅ Extracted ${result.created || 0} duties`)
        } else if (result.created > 0) {
          // Even if no duties in response, created count might be > 0
          toast.success(`✅ ${result.created} duties created successfully`)
        } else {
          toast.warning('No duties were extracted from the file')
        }
        
        // ✅ Call onSuccess with the data
        if (onSuccess) {
          onSuccess(result)
        }
      } else {
        toast.warning('No response data received')
      }
      
      // Reset file input
      setFile(null)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
      
    } catch (error) {
      console.error('❌ Upload failed:', error)
      console.error('❌ Error response:', error.response?.data)
      
      let errorMsg = 'Failed to upload exam duties'
      
      if (error.response?.data?.detail) {
        errorMsg = error.response.data.detail
      } else if (error.response?.data?.message) {
        errorMsg = error.response.data.message
      } else if (error.message) {
        errorMsg = error.message
      }
      
      toast.error(errorMsg)
      if (onError) {
        onError(errorMsg)
      }
    } finally {
      setLoading(false)
      setUploadProgress(0)
    }
  }

  const handleConfirmPreview = () => {
    setShowPreview(false)
    setParsePreview(null)
    toast.success('Duties saved successfully')
    // Refresh the list
    if (onSuccess) {
      onSuccess({ created: parsePreview?.created || 0 })
    }
  }

  const handleCancelPreview = () => {
    setShowPreview(false)
    setParsePreview(null)
    toast.info('Upload cancelled')
  }

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-6 mb-6 transition-colors">
      <h2 className="text-lg font-semibold text-gray-800 dark:text-white mb-4">Upload Exam Duty Schedule</h2>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        Upload a PDF, Image, or DOCX file containing the exam duty schedule.
        The system will automatically extract and assign duties to lecturers.
      </p>

      {/* Drag & Drop Zone */}
      <div
        className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
          dragActive 
            ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/30' 
            : 'border-gray-300 dark:border-gray-700 hover:border-gray-400 dark:hover:border-gray-600 bg-transparent dark:bg-gray-800/30'
        }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          id="file-input"
          type="file"
          accept=".pdf,.jpg,.jpeg,.png,.docx,.doc"
          onChange={handleFileChange}
          className="hidden"
        />
        
        <label htmlFor="file-input" className="cursor-pointer">
          <div className="flex flex-col items-center">
            <span className="text-4xl mb-2">📤</span>
            <p className="text-gray-600 dark:text-gray-300">
              {file ? (
                <span className="text-green-600 dark:text-green-400 font-medium">📎 {file.name}</span>
              ) : (
                <>
                  <span className="font-medium text-gray-800 dark:text-gray-200">Click to upload</span> or drag and drop
                </>
              )}
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              PDF, JPG, PNG, DOCX (Max 5MB)
            </p>
            {file && (
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                ({(file.size / 1024).toFixed(1)} KB)
              </p>
            )}
          </div>
        </label>
      </div>

      {/* Upload Progress */}
      {uploadProgress > 0 && uploadProgress < 100 && (
        <div className="mt-4">
          <div className="flex justify-between text-sm text-gray-600 dark:text-gray-300 mb-1">
            <span>{uploadProgress >= 90 ? '🤖 Extracting & processing schedule...' : 'Uploading file...'}</span>
            <span>{uploadProgress}%</span>
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-800 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      )}

      {/* Upload Button */}
      <div className="mt-4 flex items-center gap-4">
        <button
          onClick={handleUpload}
          disabled={loading || !file}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? 'Processing...' : 'Upload & Extract'}
        </button>
        {file && (
          <button
            onClick={() => {
              setFile(null)
              if (fileInputRef.current) {
                fileInputRef.current.value = ''
              }
            }}
            className="px-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
          >
            Remove
          </button>
        )}
      </div>

      {/* Parse Preview Modal */}
      {showPreview && parsePreview && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-auto p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-xl font-bold text-gray-900">📋 Extracted Duties Preview</h3>
              <button
                onClick={handleCancelPreview}
                className="text-gray-500 hover:text-gray-700"
              >
                ✕
              </button>
            </div>
            
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div className="bg-green-50 p-3 rounded-lg">
                <p className="text-sm text-green-700 font-medium">Created</p>
                <p className="text-2xl font-bold text-green-700">{parsePreview.created}</p>
              </div>
              <div className="bg-yellow-50 p-3 rounded-lg">
                <p className="text-sm text-yellow-700 font-medium">Skipped</p>
                <p className="text-2xl font-bold text-yellow-700">{parsePreview.skipped}</p>
              </div>
              <div className="bg-red-50 p-3 rounded-lg">
                <p className="text-sm text-red-700 font-medium">Conflicts</p>
                <p className="text-2xl font-bold text-red-700">{parsePreview.conflicts?.length || 0}</p>
              </div>
            </div>

            {parsePreview.unmatched && parsePreview.unmatched.length > 0 && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-4">
                <p className="text-sm font-medium text-yellow-700">⚠️ Unmatched Lecturers:</p>
                <p className="text-sm text-yellow-600">{parsePreview.unmatched.join(', ')}</p>
              </div>
            )}

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-2 px-3 font-medium text-gray-600">Lecturer</th>
                    <th className="text-left py-2 px-3 font-medium text-gray-600">Exam</th>
                    <th className="text-left py-2 px-3 font-medium text-gray-600">Date</th>
                    <th className="text-left py-2 px-3 font-medium text-gray-600">Time</th>
                    <th className="text-left py-2 px-3 font-medium text-gray-600">Venue</th>
                  </tr>
                </thead>
                <tbody>
                  {parsePreview.duties?.map((duty, index) => (
                    <tr key={index} className="border-b border-gray-100">
                      <td className="py-2 px-3 text-gray-800">{duty.lecturer_name || 'Unknown'}</td>
                      <td className="py-2 px-3 text-gray-800">{duty.exam_name}</td>
                      <td className="py-2 px-3 text-gray-800">{new Date(duty.date).toLocaleDateString()}</td>
                      <td className="py-2 px-3 text-gray-800">{duty.start_time} - {duty.end_time}</td>
                      <td className="py-2 px-3 text-gray-800">{duty.venue || 'TBD'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex justify-end gap-3 mt-4 pt-4 border-t border-gray-200">
              <button
                onClick={handleCancelPreview}
                className="px-4 py-2 text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmPreview}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
              >
                ✅ Confirm & Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ExamDutyUpload