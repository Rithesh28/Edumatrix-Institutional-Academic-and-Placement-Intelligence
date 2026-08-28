import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { useAuthStore } from '../../store/authStore'
import toast from 'react-hot-toast'
import { API_URL } from '../../services/api'

const LecturerCirculars = () => {
  const { token } = useAuthStore()
  const [circulars, setCirculars] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [uploadingFile, setUploadingFile] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const [formData, setFormData] = useState({
    type: 'general',
    title: '',
    content: '',
    due_date: ''
  })

  const fetchCirculars = async () => {
    try {
      const response = await axios.get(`${API_URL}/circulars/`, {
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

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value })
  }

  // Handle file selection with instant auto-extraction of content, title, and dates
  const handleFileSelect = async (e) => {
    const file = e.target.files[0]
    if (!file) return

    const allowedExtensions = ['.pdf', '.jpg', '.jpeg', '.png', '.docx', '.doc', '.txt']
    const ext = '.' + file.name.split('.').pop().toLowerCase()
    
    if (!allowedExtensions.includes(ext)) {
      toast.error('Please upload PDF, Image (JPG/PNG), DOCX, or TXT file')
      return
    }

    if (file.size > 10 * 1024 * 1024) {
      toast.error('File size should be less than 10MB')
      return
    }

    setSelectedFile(file)
    setUploadingFile(true)
    const toastId = toast.loading(`Scanning & extracting text from ${file.name}...`)

    try {
      const uploadFormData = new FormData()
      uploadFormData.append('file', file)

      const response = await axios.post(
        `${API_URL}/upload/circular`,
        uploadFormData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
            Authorization: `Bearer ${token}`
          }
        }
      )

      if (response.data) {
        const { text, preview, suggested_title, suggested_due_date, suggested_type } = response.data
        
        setFormData(prev => ({
          ...prev,
          title: suggested_title || prev.title || file.name.replace(/\.[^.]+$/, '').replace(/_/g, ' '),
          content: text || preview || prev.content || '',
          due_date: suggested_due_date || prev.due_date || '',
          type: suggested_type || prev.type || 'general'
        }))

        toast.success('✨ Auto-filled content and deadline from file!', { id: toastId })
      }
    } catch (err) {
      console.warn('Auto-extraction fallback:', err)
      // Fallback: Just set the title from filename if auto-extraction failed
      setFormData(prev => ({
        ...prev,
        title: prev.title || file.name.replace(/\.[^.]+$/, '').replace(/_/g, ' ')
      }))
      toast.dismiss(toastId)
      toast.success(`File selected: ${file.name}`)
    } finally {
      setUploadingFile(false)
      e.target.value = ''
    }
  }

  // Submit circular with file
  const handleSubmit = async (e) => {
    e.preventDefault()
    
    try {
      if (selectedFile) {
        // Upload with file
        const uploadFormData = new FormData()
        uploadFormData.append('file', selectedFile)
        uploadFormData.append('type', formData.type || 'general')
        uploadFormData.append('title', formData.title.trim() || 'Untitled')
        uploadFormData.append('content', formData.content.trim() || 'No content')
        if (formData.due_date) {
          uploadFormData.append('due_date', formData.due_date)
        }

        toast.loading('Uploading circular with file...', { id: 'upload' })

        const response = await axios.post(
          `${API_URL}/circulars/upload`,
          uploadFormData,
          {
            headers: {
              'Content-Type': 'multipart/form-data',
              Authorization: `Bearer ${token}`
            }
          }
        )

        toast.dismiss('upload')

        if (response.status === 200) {
          toast.success('Circular with file posted successfully!')
          resetForm()
          fetchCirculars()
        }
      } else {
        // Text-only circular
        const submitData = {
          type: formData.type || 'general',
          title: formData.title.trim() || 'Untitled',
          content: formData.content.trim() || 'No content'
        }
        
        if (formData.due_date && formData.due_date.trim() !== '') {
          submitData.due_date = formData.due_date
        }

        toast.loading('Posting circular...', { id: 'post' })

        const response = await axios.post(
          `${API_URL}/circulars/`,
          submitData,
          {
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${token}`
            }
          }
        )

        toast.dismiss('post')

        if (response.status === 200) {
          toast.success('Circular posted successfully!')
          resetForm()
          fetchCirculars()
        }
      }
    } catch (error) {
      toast.dismiss('upload')
      toast.dismiss('post')
      console.error('Failed to save circular:', error)
      const errorMsg = error.response?.data?.detail || error.response?.data?.message || 'Failed to post circular'
      toast.error(errorMsg)
    }
  }

  const resetForm = () => {
    setShowForm(false)
    setSelectedFile(null)
    setEditingId(null)
    setFormData({ type: 'general', title: '', content: '', due_date: '' })
  }

  const handleEdit = (circ) => {
    setEditingId(circ.id)
    setFormData({
      type: circ.type,
      title: circ.title,
      content: circ.content,
      due_date: circ.due_date ? circ.due_date.slice(0, 16) : ''
    })
    setShowForm(true)
  }

  const handleDelete = async (id) => {
    if (window.confirm('Are you sure you want to delete this circular?')) {
      try {
        await axios.delete(`${API_URL}/circulars/${id}`, {
          headers: { Authorization: `Bearer ${token}` }
        })
        toast.success('Circular deleted successfully')
        fetchCirculars()
      } catch (error) {
        toast.error('Failed to delete circular')
      }
    }
  }

  // Handle file download
  const handleDownload = async (fileId, filename) => {
    if (!fileId) {
      toast.error('No file attached to download')
      return
    }

    try {
      const response = await axios.get(
        `${API_URL}/files/${fileId}/download`,
        {
          headers: { Authorization: `Bearer ${token}` },
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
      toast.success('File downloaded!')
    } catch (error) {
      toast.error('Failed to download file')
    }
  }

  // Handle file preview
  const handlePreview = (fileId) => {
    if (!fileId) return
    window.open(`${API_URL}/files/${fileId}/preview?token=${token}`, '_blank')
  }

  const renderFileAttachment = (circ) => {
    if (!circ.file_details) return null

    const fileDetails = circ.file_details
    const isPreviewable = fileDetails.mime_type?.startsWith('image/') || 
                          fileDetails.mime_type === 'application/pdf'

    return (
      <div className="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
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
            {isPreviewable && (
              <button
                onClick={() => handlePreview(circ.file_id)}
                className="px-3 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
              >
                👁️ Preview
              </button>
            )}
            <button
              onClick={() => handleDownload(circ.file_id, fileDetails.filename)}
              className="px-3 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200"
            >
              ⬇️ Download
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
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Manage Circulars</h1>
        <button
          onClick={() => {
            setShowForm(!showForm)
            if (!showForm) {
              setSelectedFile(null)
              setFormData({ type: 'general', title: '', content: '', due_date: '' })
            }
          }}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          {showForm ? 'Cancel' : '+ Post Circular'}
        </button>
      </div>

      {showForm && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">
            {editingId ? 'Edit Circular' : 'Post New Circular'}
          </h2>
          
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* File Upload Section */}
            <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Upload File (PDF, Image, DOCX, TXT - Optional)
              </label>
              <div className="flex items-center space-x-4">
                <input
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png,.docx,.doc,.txt"
                  onChange={handleFileSelect}
                  disabled={uploadingFile}
                  className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                />
                {uploadingFile && (
                  <div className="flex items-center space-x-2">
                    <div className="animate-spin rounded-full h-5 w-5 border-2 border-blue-600 border-t-transparent"></div>
                    <span className="text-sm text-gray-600">Processing...</span>
                  </div>
                )}
              </div>
              {selectedFile && (
                <div className="mt-2 text-sm text-green-600">
                  ✅ File selected: {selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)
                </div>
              )}
            </div>

            {/* Type Field */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
              <select
                name="type"
                value={formData.type}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="general">General</option>
                <option value="exam">Exam</option>
                <option value="assignment">Assignment</option>
              </select>
            </div>

            {/* Title Field */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
              <input
                type="text"
                name="title"
                value={formData.title}
                onChange={handleChange}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Enter circular title"
              />
            </div>

            {/* Content Field */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Content</label>
              <textarea
                name="content"
                value={formData.content}
                onChange={handleChange}
                rows="4"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Enter circular content"
              />
            </div>

            {/* Due Date Field */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Due Date (Optional)</label>
              <input
                type="datetime-local"
                name="due_date"
                value={formData.due_date}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Buttons */}
            <div className="flex space-x-2">
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                {editingId ? 'Update' : 'Post Circular'}
              </button>
              <button
                type="button"
                onClick={resetForm}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Circulars List */}
      <div className="space-y-4">
        {circulars.length === 0 ? (
          <p className="text-gray-500 text-center py-10">No circulars yet</p>
        ) : (
          circulars.map((circ) => (
            <div key={circ.id} className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <span className={`text-xs px-2 py-1 rounded-full ${
                    circ.type === 'exam' ? 'bg-red-100 text-red-700' :
                    circ.type === 'assignment' ? 'bg-yellow-100 text-yellow-700' :
                    'bg-blue-100 text-blue-700'
                  }`}>
                    {circ.type.toUpperCase()}
                  </span>
                  <h3 className="text-lg font-semibold text-gray-900 mt-2">{circ.title}</h3>
                  <p className="text-gray-600 mt-1 whitespace-pre-wrap">{circ.content}</p>
                  
                  {/* File Attachment */}
                  {renderFileAttachment(circ)}
                  
                  {circ.due_date && (
                    <p className="text-sm text-red-600 mt-2">Due: {new Date(circ.due_date).toLocaleDateString()}</p>
                  )}
                  <p className="text-xs text-gray-400 mt-2">
                    Posted: {new Date(circ.created_at).toLocaleString()}
                    {circ.lecturer_name && ` by ${circ.lecturer_name}`}
                  </p>
                </div>
                <div className="flex space-x-2 ml-4">
                  <button
                    onClick={() => handleEdit(circ)}
                    className="text-blue-600 hover:text-blue-800 text-sm"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(circ.id)}
                    className="text-red-600 hover:text-red-800 text-sm"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default LecturerCirculars