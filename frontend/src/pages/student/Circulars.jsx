import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { useAuthStore } from '../../store/authStore'
import toast from 'react-hot-toast'

const StudentCirculars = () => {
  const { token } = useAuthStore()
  const [circulars, setCirculars] = useState([])
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState(false)
  const [previewing, setPreviewing] = useState(false)

  const fetchCirculars = async () => {
    try {
      const response = await axios.get('http://localhost:8000/circulars/', {
        headers: { Authorization: `Bearer ${token}` }
      })
      setCirculars(response.data)
    } catch (error) {
      console.error('Failed to fetch circulars:', error)
      toast.error('Failed to load circulars')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCirculars()
  }, [])

  // Handle preview - opens in new tab using blob URL
  const handlePreview = async (fileId, filename, mimeType) => {
    if (!fileId) {
      toast.error('No file attached to preview')
      return
    }

    setPreviewing(true)
    try {
      // Use download endpoint to get the file
      const response = await axios.get(
        `http://localhost:8000/files/${fileId}/download`,
        {
          headers: {
            Authorization: `Bearer ${token}`
          },
          responseType: 'blob'
        }
      )

      // Determine the correct MIME type
      const contentType = mimeType || response.headers['content-type'] || 'application/octet-stream'
      
      // Create blob and URL
      const blob = new Blob([response.data], { type: contentType })
      const url = window.URL.createObjectURL(blob)
      
      // Open in new tab
      const newWindow = window.open(url, '_blank')
      
      // If popup is blocked, show a message
      if (!newWindow) {
        toast.error('Popup blocked! Please allow popups for this site.')
        window.URL.revokeObjectURL(url)
        setPreviewing(false)
        return
      }
      
      // Clean up after a delay
      setTimeout(() => {
        window.URL.revokeObjectURL(url)
      }, 30000)
      
      toast.success('Preview opened in new tab!')
    } catch (error) {
      console.error('Preview failed:', error)
      if (error.response?.status === 401) {
        toast.error('Please login again')
      } else {
        toast.error('Failed to preview file')
      }
    } finally {
      setPreviewing(false)
    }
  }

  // Handle download
  const handleDownload = async (fileId, filename) => {
    if (!fileId) {
      toast.error('No file attached to download')
      return
    }

    setDownloading(true)
    try {
      const response = await axios.get(
        `http://localhost:8000/files/${fileId}/download`,
        {
          headers: {
            Authorization: `Bearer ${token}`
          },
          responseType: 'blob'
        }
      )

      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', filename || 'download')
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      
      toast.success('File downloaded successfully!')
    } catch (error) {
      console.error('Download failed:', error)
      if (error.response?.status === 401) {
        toast.error('Please login again')
      } else {
        toast.error('Failed to download file')
      }
    } finally {
      setDownloading(false)
    }
  }

  const renderFileAttachment = (circ) => {
    if (!circ.file_details) {
      return null
    }

    const fileDetails = circ.file_details
    const isPreviewable = true // Allow preview for all files

    return (
      <div className="mt-3 p-3 bg-green-50 rounded-lg border border-green-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="text-sm font-medium text-gray-700">
              📎 {fileDetails.filename || 'Attachment'}
            </span>
            <span className="text-xs text-gray-500">
              ({fileDetails.file_size ? Math.round(fileDetails.file_size / 1024) : 0} KB)
            </span>
          </div>
          <div className="flex items-center space-x-3">
            <button
              onClick={() => handlePreview(
                circ.file_id, 
                fileDetails.filename, 
                fileDetails.mime_type
              )}
              disabled={previewing}
              className="px-3 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 disabled:opacity-50"
            >
              {previewing ? '⏳ Loading...' : '👁️ Preview'}
            </button>
            <button
              onClick={() => handleDownload(circ.file_id, fileDetails.filename)}
              disabled={downloading}
              className="px-3 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200 disabled:opacity-50"
            >
              {downloading ? '⏳ Downloading...' : '⬇️ Download'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (loading) {
    return <div className="text-center py-10">Loading circulars...</div>
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">📢 Circulars</h1>

      <div className="space-y-4">
        {circulars.length === 0 ? (
          <p className="text-gray-500 text-center py-10">No circulars yet</p>
        ) : (
          circulars.map((circ) => (
            <div key={circ.id} className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
              <div className="flex items-start space-x-2">
                <span className={`text-xs px-2 py-1 rounded-full ${
                  circ.type === 'exam' ? 'bg-red-100 text-red-700' :
                  circ.type === 'assignment' ? 'bg-yellow-100 text-yellow-700' :
                  'bg-blue-100 text-blue-700'
                }`}>
                  {circ.type.toUpperCase()}
                </span>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-gray-900">{circ.title}</h3>
                  <p className="text-gray-600 mt-1 whitespace-pre-wrap">{circ.content}</p>
                  
                  {/* File Attachment */}
                  {renderFileAttachment(circ)}
                  
                  {circ.due_date && (
                    <p className="text-sm text-red-600 mt-2">
                      📅 Due: {new Date(circ.due_date).toLocaleDateString()}
                    </p>
                  )}
                  <p className="text-xs text-gray-400 mt-2">
                    Posted: {new Date(circ.created_at).toLocaleString()}
                    {circ.lecturer_name && ` by ${circ.lecturer_name}`}
                  </p>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default StudentCirculars