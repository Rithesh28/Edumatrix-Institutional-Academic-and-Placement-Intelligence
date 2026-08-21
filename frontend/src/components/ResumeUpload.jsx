import React, { useState, useEffect, useRef } from 'react'
import { FileText, Upload, Trash2, Download, Eye, Award, CheckCircle, RefreshCw, X, Sparkles } from 'lucide-react'
import { resumeAPI } from '../services/api'
import toast from 'react-hot-toast'

const ResumeUpload = () => {
  const [resumes, setResumes] = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [activeResume, setActiveResume] = useState(null)
  const fileInputRef = useRef(null)

  const fetchResumes = async () => {
    setLoading(true)
    try {
      const response = await resumeAPI.getAll()
      const list = response.data?.resumes || (Array.isArray(response.data) ? response.data : [])
      setResumes(list)
    } catch (error) {
      console.error('Failed to fetch resumes:', error)
      toast.error('Failed to load resumes')
      setResumes([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchResumes()
  }, [])

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Check file type
    const allowedExtensions = ['.pdf', '.docx', '.doc', '.jpg', '.jpeg', '.png']
    const ext = '.' + file.name.split('.').pop().toLowerCase()

    if (!allowedExtensions.includes(ext)) {
      toast.error('Please upload PDF, DOCX, DOC, JPG, or PNG files only')
      return
    }

    // Check file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
      toast.error('File size should be less than 10MB')
      return
    }

    setUploading(true)
    try {
      await resumeAPI.upload(file)
      toast.success('🎉 Resume uploaded & analyzed with ATS scoring!')
      await fetchResumes()
    } catch (error) {
      console.error('Upload error:', error)
      toast.error(error.response?.data?.detail || 'Failed to upload resume')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this resume?')) return

    try {
      await resumeAPI.delete(id)
      setResumes(resumes.filter((r) => r.id !== id))
      toast.success('Resume deleted successfully')
      if (activeResume?.id === id) setActiveResume(null)
    } catch (error) {
      toast.error('Failed to delete resume')
    }
  }

  const handleExport = async (id, format = 'json') => {
    try {
      const response = await resumeAPI.export(id, format)
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `resume_${id}.${format}`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      toast.success(`Exported resume as ${format.toUpperCase()}`)
    } catch (error) {
      toast.error('Failed to export resume')
    }
  }

  const getScoreBadge = (score) => {
    if (score === null || score === undefined) return <span className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded-full font-medium">Pending</span>
    if (score >= 75) return <span className="px-2.5 py-1 text-xs bg-green-100 text-green-800 rounded-full font-bold">ATS {Math.round(score)}%</span>
    if (score >= 50) return <span className="px-2.5 py-1 text-xs bg-amber-100 text-amber-800 rounded-full font-bold">ATS {Math.round(score)}%</span>
    return <span className="px-2.5 py-1 text-xs bg-rose-100 text-rose-800 rounded-full font-bold">ATS {Math.round(score)}%</span>
  }

  return (
    <div className="space-y-6">
      {/* Header & Upload Box */}
      <div className="border-2 border-dashed border-indigo-200 hover:border-indigo-400 bg-indigo-50/40 rounded-xl p-6 text-center transition-all">
        <input
          ref={fileInputRef}
          type="file"
          id="profile-resume-input"
          accept=".pdf,.docx,.doc,.jpg,.jpeg,.png"
          onChange={handleUpload}
          disabled={uploading}
          className="hidden"
        />

        <label htmlFor="profile-resume-input" className="cursor-pointer flex flex-col items-center justify-center">
          <div className="w-12 h-12 bg-indigo-600 text-white rounded-full flex items-center justify-center mb-3 shadow-md">
            <Upload className="w-6 h-6" />
          </div>
          <p className="text-sm font-semibold text-gray-800">
            <span className="text-indigo-600 underline">Upload New Resume</span> or drag and drop
          </p>
          <p className="text-xs text-gray-500 mt-1">
            Supports PDF, DOCX, PNG, JPG (Max 10MB). Automatically analyzed for skills & ATS score.
          </p>
        </label>

        {uploading && (
          <div className="mt-4 flex items-center justify-center gap-2 text-sm text-indigo-600 font-medium">
            <RefreshCw className="w-4 h-4 animate-spin" />
            <span>Analyzing resume with AI parser...</span>
          </div>
        )}
      </div>

      {/* Resume List */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-base font-bold text-gray-900 flex items-center gap-2">
            <FileText className="w-5 h-5 text-indigo-600" />
            Uploaded Resumes ({resumes.length})
          </h3>
          <button
            onClick={fetchResumes}
            className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg text-xs flex items-center gap-1"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>

        {loading ? (
          <div className="text-center py-8 text-gray-500 text-sm">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-indigo-600" />
            Loading resumes...
          </div>
        ) : resumes.length === 0 ? (
          <div className="text-center py-8 bg-gray-50 rounded-xl border border-gray-200">
            <p className="text-gray-500 text-sm font-medium">No resumes uploaded yet.</p>
            <p className="text-xs text-gray-400 mt-1">Upload your resume to get instant ATS scores and placement visibility!</p>
          </div>
        ) : (
          <div className="space-y-3">
            {resumes.map((resume) => (
              <div
                key={resume.id}
                className="flex flex-col sm:flex-row sm:items-center justify-between p-4 bg-white border border-gray-200 rounded-xl hover:border-indigo-300 transition-all gap-3 shadow-sm"
              >
                <div className="flex items-start gap-3 flex-1 min-w-0">
                  <div className="w-10 h-10 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center flex-shrink-0">
                    <FileText className="w-5 h-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="font-semibold text-gray-900 truncate">
                        {resume.name || 'Student Resume'}
                      </p>
                      {getScoreBadge(resume.ats_score)}
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {resume.created_at ? new Date(resume.created_at).toLocaleDateString() : 'Recent'} • {resume.status || 'completed'}
                    </p>
                    {/* Skills pills */}
                    {Array.isArray(resume.skills) && resume.skills.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {resume.skills.slice(0, 4).map((s, idx) => (
                          <span key={idx} className="px-2 py-0.5 bg-gray-100 text-gray-700 text-[11px] rounded-md">
                            {typeof s === 'string' ? s : s.name || ''}
                          </span>
                        ))}
                        {resume.skills.length > 4 && (
                          <span className="text-[11px] text-gray-400 self-center">+{resume.skills.length - 4} more</span>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 self-end sm:self-center">
                  <button
                    onClick={() => setActiveResume(resume)}
                    className="px-3 py-1.5 text-xs font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-lg flex items-center gap-1"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    <span>View Analysis</span>
                  </button>
                  <button
                    onClick={() => handleExport(resume.id, 'json')}
                    className="p-1.5 text-emerald-600 hover:bg-emerald-50 rounded-lg"
                    title="Export JSON"
                  >
                    <Download className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(resume.id)}
                    className="p-1.5 text-rose-600 hover:bg-rose-50 rounded-lg"
                    title="Delete Resume"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Analysis Details Modal */}
      {activeResume && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[85vh] overflow-y-auto shadow-2xl border border-gray-200">
            <div className="sticky top-0 bg-white border-b border-gray-200 p-5 flex items-center justify-between z-10">
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-gray-900">📄 Resume Analysis</h3>
                {getScoreBadge(activeResume.ats_score)}
              </div>
              <button
                onClick={() => setActiveResume(null)}
                className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-full"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 space-y-4">
              {/* ATS Score Box */}
              <div className="bg-indigo-50 p-4 rounded-xl border border-indigo-100 flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold text-indigo-900 uppercase">Overall ATS Compatibility</p>
                  <p className="text-xs text-indigo-700 mt-0.5">Scored based on keyword coverage and structure.</p>
                </div>
                <div className="text-2xl font-black text-indigo-600 bg-white px-4 py-2 rounded-xl shadow-sm border border-indigo-200">
                  {Math.round(activeResume.ats_score || 0)}%
                </div>
              </div>

              {/* Skills */}
              <div>
                <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Award className="w-4 h-4 text-purple-600" />
                  Extracted Skills
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {Array.isArray(activeResume.skills) && activeResume.skills.length > 0 ? (
                    activeResume.skills.map((s, idx) => (
                      <span key={idx} className="px-2.5 py-1 bg-purple-50 border border-purple-200 text-purple-700 text-xs rounded-lg font-medium">
                        {typeof s === 'string' ? s : s.name || ''}
                      </span>
                    ))
                  ) : (
                    <p className="text-xs text-gray-400">No skills detected</p>
                  )}
                </div>
              </div>

              {/* Suggestions */}
              {Array.isArray(activeResume.suggestions) && activeResume.suggestions.length > 0 && (
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
                  <h4 className="text-xs font-bold text-amber-900 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4 text-amber-600" />
                    Improvement Tips
                  </h4>
                  <ul className="space-y-1 text-xs text-amber-900">
                    {activeResume.suggestions.map((sug, i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <span className="text-amber-500 font-bold">•</span>
                        <span>{typeof sug === 'string' ? sug : sug.message || JSON.stringify(sug)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 p-4 flex justify-end">
              <button
                onClick={() => setActiveResume(null)}
                className="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-800 rounded-lg text-xs font-semibold"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ResumeUpload