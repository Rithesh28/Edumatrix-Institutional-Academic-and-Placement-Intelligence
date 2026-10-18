import React, { useState, useEffect, useMemo, useRef } from 'react'
import { useAuthStore } from '../../store/authStore'
import { studyBuddyAPI } from '../../services/api'
import toast from 'react-hot-toast'
import {
  BookOpen,
  Upload,
  Search,
  Filter,
  FileText,
  Image as ImageIcon,
  FileSpreadsheet,
  Presentation,
  Download,
  Edit,
  Trash2,
  RefreshCw,
  CheckCircle,
  AlertTriangle,
  Clock,
  X,
  Layers,
  ChevronRight,
  Eye,
  EyeOff,
  Archive,
  Info,
  AlertCircle,
  FileCheck,
  FileClock,
  FileWarning,
  Plus
} from 'lucide-react'

// Constants matching backend Step 4.6B / 4.6B.1
export const MAX_FILE_SIZE_BYTES = 524288000 // 500 MiB (500 * 1024 * 1024)
export const ALLOWED_EXTENSIONS = ['.pdf', '.png', '.docx', '.pptx']
export const ALLOWED_MIME_TYPES = [
  'application/pdf',
  'image/png',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation'
]

export function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

export function formatDate(dateString) {
  if (!dateString) return '—'
  try {
    const date = new Date(dateString)
    return date.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return dateString
  }
}

export function getFileFormatInfo(filename) {
  const ext = (filename || '').split('.').pop().toLowerCase()
  switch (ext) {
    case 'pdf':
      return {
        label: 'PDF',
        color: 'text-red-600 bg-red-50 dark:bg-red-950/40 dark:text-red-400 border-red-200 dark:border-red-900',
        icon: FileText
      }
    case 'png':
      return {
        label: 'PNG',
        color: 'text-purple-600 bg-purple-50 dark:bg-purple-950/40 dark:text-purple-400 border-purple-200 dark:border-purple-900',
        icon: ImageIcon
      }
    case 'docx':
      return {
        label: 'DOCX',
        color: 'text-blue-600 bg-blue-50 dark:bg-blue-950/40 dark:text-blue-400 border-blue-200 dark:border-blue-900',
        icon: FileSpreadsheet
      }
    case 'pptx':
      return {
        label: 'PPTX',
        color: 'text-orange-600 bg-orange-50 dark:bg-orange-950/40 dark:text-orange-400 border-orange-200 dark:border-orange-900',
        icon: Presentation
      }
    default:
      return {
        label: ext.toUpperCase() || 'FILE',
        color: 'text-gray-600 bg-gray-50 dark:bg-gray-800 dark:text-gray-400 border-gray-200 dark:border-gray-700',
        icon: FileText
      }
  }
}

export default function LecturerCourseMaterials() {
  const { user, token } = useAuthStore()

  const SEMESTERS = [1, 2, 3, 4, 5, 6, 7, 8]

  // State
  const [subjects, setSubjects] = useState([])
  const [selectedSemester, setSelectedSemester] = useState('')
  const [selectedSubjectId, setSelectedSubjectId] = useState('')
  const [loadingSubjects, setLoadingSubjects] = useState(true)

  // Filter subjects strictly for the selected semester
  const availableSubjectsForSemester = useMemo(() => {
    if (!selectedSemester) return []
    return subjects.filter((s) => String(s.semester) === String(selectedSemester) && s.is_active)
  }, [subjects, selectedSemester])

  const handleSemesterChange = (newSemester) => {
    setSelectedSemester(newSemester)
    // Rule 3: Changing the semester clears the previous subject selection.
    setSelectedSubjectId('')
    setNotes([])
    setSyllabusDoc(null)
  }

  // Syllabus info (units/topics) for the selected subject
  const [syllabusDoc, setSyllabusDoc] = useState(null)
  const [loadingSyllabus, setLoadingSyllabus] = useState(false)

  // Notes state
  const [notes, setNotes] = useState([])
  const [loadingNotes, setLoadingNotes] = useState(false)
  const [notesError, setNotesError] = useState(null)

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [unitFilter, setUnitFilter] = useState('ALL')

  // Modals state
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false)
  const [editingNote, setEditingNote] = useState(null)
  const [deletingNote, setDeletingNote] = useState(null)
  const [retryingNoteId, setRetryingNoteId] = useState(null)
  const [publishingNoteId, setPublishingNoteId] = useState(null)

  // Upload modal form state
  const [uploadSubjectId, setUploadSubjectId] = useState('')
  const [uploadFile, setUploadFile] = useState(null)
  const [uploadTitle, setUploadTitle] = useState('')
  const [uploadDescription, setUploadDescription] = useState('')
  const [uploadUnitId, setUploadUnitId] = useState('')
  const [uploadTopicId, setUploadTopicId] = useState('')
  const [uploadValidationErr, setUploadValidationErr] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)

  // Edit modal form state
  const [editTitle, setEditTitle] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editUnitId, setEditUnitId] = useState('')
  const [editTopicId, setEditTopicId] = useState('')
  const [editStatus, setEditStatus] = useState('DRAFT')
  const [isSavingEdit, setIsSavingEdit] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

  // Add Subject Modal State (Part B)
  const [isAddSubjectModalOpen, setIsAddSubjectModalOpen] = useState(false)
  const [subjectFormData, setSubjectFormData] = useState({
    code: '',
    name: '',
    semester: '',
    curriculum_version: '2024.1',
    academic_year: '2026-2027',
    description: ''
  })
  const [isCreatingSubject, setIsCreatingSubject] = useState(false)
  const [subjectFormError, setSubjectFormError] = useState('')

  const fileInputRef = useRef(null)

  // 1. Fetch authorized subjects on mount
  useEffect(() => {
    fetchSubjects()
  }, [])

  const fetchSubjects = async (preserveSelection = false) => {
    setLoadingSubjects(true)
    try {
      const res = await studyBuddyAPI.getSubjects()
      const data = res.data || []
      setSubjects(data)
      if (data.length > 0 && !preserveSelection) {
        setSelectedSemester(String(data[0].semester))
        setSelectedSubjectId(String(data[0].id))
      }
    } catch (err) {
      console.error('Failed to load subjects:', err)
      toast.error('Failed to load authorized subjects.')
    } finally {
      setLoadingSubjects(false)
    }
  }

  const handleOpenAddSubjectModal = () => {
    setSubjectFormData({
      code: '',
      name: '',
      semester: selectedSemester || '1',
      curriculum_version: '2024.1',
      academic_year: '2026-2027',
      description: ''
    })
    setSubjectFormError('')
    setIsAddSubjectModalOpen(true)
  }

  const handleCreateSubject = async (e) => {
    e.preventDefault()
    setSubjectFormError('')

    const code = (subjectFormData.code || '').trim().toUpperCase()
    const name = (subjectFormData.name || '').trim()
    const sem = Number(subjectFormData.semester)

    if (!code || !name) {
      setSubjectFormError('Subject code and subject name are required.')
      return
    }

    if (!sem || sem < 1 || sem > 8) {
      setSubjectFormError('Please select a valid semester between 1 and 8.')
      return
    }

    setIsCreatingSubject(true)
    try {
      const payload = {
        code,
        name,
        department: user?.department || undefined,
        semester: sem,
        curriculum_version: (subjectFormData.curriculum_version || '').trim() || '2024.1',
        academic_year: (subjectFormData.academic_year || '').trim() || '2026-2027',
        description: (subjectFormData.description || '').trim() || undefined
      }

      const res = await studyBuddyAPI.createSubject(payload)
      const created = res.data
      toast.success(`Subject ${created.code} — ${created.name} created successfully!`)
      setIsAddSubjectModalOpen(false)

      // Refresh subjects and auto-select newly created subject
      await fetchSubjects(true)
      setSelectedSemester(String(created.semester))
      setSelectedSubjectId(String(created.id))
    } catch (err) {
      console.error('Failed to create subject:', err)
      const detail = err.response?.data?.detail || 'Failed to create subject.'
      setSubjectFormError(detail)
      toast.error(detail)
    } finally {
      setIsCreatingSubject(false)
    }
  }

  // Selected subject object
  const activeSubject = useMemo(() => {
    return subjects.find((s) => String(s.id) === String(selectedSubjectId)) || null
  }, [subjects, selectedSubjectId])

  // 2. Fetch published syllabus details for units & topics when subject changes
  useEffect(() => {
    if (!activeSubject) {
      setSyllabusDoc(null)
      return
    }

    if (activeSubject.published_document_id) {
      fetchSyllabusDetail(activeSubject.published_document_id)
    } else {
      setSyllabusDoc(null)
    }

    fetchNotes(activeSubject.id)
  }, [selectedSubjectId])

  const fetchSyllabusDetail = async (documentId) => {
    setLoadingSyllabus(true)
    try {
      const res = await studyBuddyAPI.getSyllabusDetail(documentId)
      setSyllabusDoc(res.data)
    } catch (err) {
      console.warn('No published syllabus details found:', err)
      setSyllabusDoc(null)
    } finally {
      setLoadingSyllabus(false)
    }
  }

  // 3. Fetch lecture notes for selected subject
  const fetchNotes = async (subjectId) => {
    if (!subjectId) return
    setLoadingNotes(true)
    setNotesError(null)

    try {
      const params = {}
      if (statusFilter && statusFilter !== 'ALL') {
        params.status = statusFilter
      }
      if (unitFilter && unitFilter !== 'ALL') {
        params.unit_id = Number(unitFilter)
      }
      if (searchQuery.trim()) {
        params.search = searchQuery.trim()
      }

      const res = await studyBuddyAPI.getSubjectNotes(subjectId, params)
      setNotes(res.data || [])
    } catch (err) {
      console.error('Failed to load lecture notes:', err)
      const detail = err.response?.data?.detail || 'Failed to load lecture notes for this subject.'
      setNotesError(detail)
      toast.error(detail)
    } finally {
      setLoadingNotes(false)
    }
  }

  // Trigger notes fetch on filter or search changes
  useEffect(() => {
    if (activeSubject?.id) {
      const timer = setTimeout(() => {
        fetchNotes(activeSubject.id)
      }, 250)
      return () => clearTimeout(timer)
    }
  }, [searchQuery, statusFilter, unitFilter])

  // Units list helper
  const availableUnits = useMemo(() => {
    return syllabusDoc?.units || []
  }, [syllabusDoc])

  // Topics list helper for upload modal
  const uploadTopics = useMemo(() => {
    if (!uploadUnitId) return []
    const u = availableUnits.find((unit) => String(unit.id) === String(uploadUnitId))
    return u?.topics || []
  }, [uploadUnitId, availableUnits])

  // Topics list helper for edit modal
  const editTopics = useMemo(() => {
    if (!editUnitId) return []
    const u = availableUnits.find((unit) => String(unit.id) === String(editUnitId))
    return u?.topics || []
  }, [editUnitId, availableUnits])

  // Unit lookup helper for note cards
  const getUnitTopicLabel = (unitId, topicId) => {
    if (!unitId && !topicId) return null
    let unitTitle = null
    let topicTitle = null

    if (availableUnits.length > 0) {
      const u = availableUnits.find((unit) => unit.id === unitId)
      if (u) {
        unitTitle = `Unit ${u.unit_number}: ${u.title}`
        if (topicId) {
          const t = u.topics?.find((topic) => topic.id === topicId)
          if (t) topicTitle = `Topic ${t.topic_number}: ${t.title}`
        }
      }
    }

    if (unitTitle && topicTitle) return `${unitTitle} • ${topicTitle}`
    if (unitTitle) return unitTitle
    if (unitId) return `Unit #${unitId}`
    return null
  }

  // ---------------------------------------------------------------------------
  // Upload Logic
  // ---------------------------------------------------------------------------
  const handleOpenUploadModal = () => {
    const defaultSubId = selectedSubjectId || (availableSubjectsForSemester.length > 0 ? String(availableSubjectsForSemester[0].id) : '')
    setUploadSubjectId(defaultSubId)
    setUploadFile(null)
    setUploadTitle('')
    setUploadDescription('')
    setUploadUnitId('')
    setUploadTopicId('')
    setUploadValidationErr('')
    setUploadProgress(0)
    setIsUploadModalOpen(true)
  }

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    setUploadValidationErr('')
    if (!file) {
      setUploadFile(null)
      return
    }

    // Client-side extension validation
    const ext = '.' + file.name.split('.').pop().toLowerCase()
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setUploadValidationErr(
        `Unsupported file type "${ext}". Allowed formats: PDF, PNG, DOCX, and PPTX.`
      )
      setUploadFile(null)
      return
    }

    // Client-side size validation (500 MiB)
    if (file.size > MAX_FILE_SIZE_BYTES) {
      const sizeMiB = (file.size / (1024 * 1024)).toFixed(1)
      setUploadValidationErr(
        `File exceeds 500 MiB limit (Selected: ${sizeMiB} MiB). Please select a smaller file.`
      )
      setUploadFile(null)
      return
    }

    setUploadFile(file)
    // Auto-populate title if empty
    if (!uploadTitle.trim()) {
      const rawName = file.name.substring(0, file.name.lastIndexOf('.')) || file.name
      setUploadTitle(rawName.replace(/[_-]/g, ' '))
    }
  }

  const handleUploadSubmit = async (e) => {
    e.preventDefault()
    setUploadValidationErr('')

    if (!uploadSubjectId) {
      setUploadValidationErr('Please select a subject.')
      return
    }

    if (!uploadFile) {
      setUploadValidationErr('Please choose a valid file to upload.')
      return
    }

    if (!uploadTitle.trim()) {
      setUploadValidationErr('Please provide a title for the lecture note.')
      return
    }

    // Prepare multipart FormData without reading file into memory
    const formData = new FormData()
    formData.append('file', uploadFile)
    formData.append('title', uploadTitle.trim())
    if (uploadDescription.trim()) {
      formData.append('description', uploadDescription.trim())
    }
    if (uploadUnitId) {
      formData.append('unit_id', uploadUnitId)
    }
    if (uploadTopicId) {
      formData.append('topic_id', uploadTopicId)
    }

    setIsUploading(true)
    setUploadProgress(0)

    try {
      const res = await studyBuddyAPI.uploadNote(
        uploadSubjectId,
        formData,
        (progressEvent) => {
          if (progressEvent.total) {
            const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
            setUploadProgress(percent)
          }
        }
      )

      toast.success('Lecture note uploaded successfully!')
      setIsUploadModalOpen(false)

      // Refresh list
      if (String(uploadSubjectId) === String(selectedSubjectId)) {
        fetchNotes(selectedSubjectId)
      } else {
        setSelectedSubjectId(String(uploadSubjectId))
      }
    } catch (err) {
      console.error('Upload failed:', err)
      const detail = err.response?.data?.detail || err.message || 'Upload failed.'
      setUploadValidationErr(detail)
      toast.error(`Upload error: ${detail}`)
    } finally {
      setIsUploading(false)
    }
  }

  // ---------------------------------------------------------------------------
  // Note Actions: Publish / Unpublish
  // ---------------------------------------------------------------------------
  const handleTogglePublish = async (note) => {
    if (note.processing_status !== 'EXTRACTED' && !note.is_published) {
      toast.error('Cannot publish note: text extraction must succeed before publication.')
      return
    }

    setPublishingNoteId(note.id)
    const newIsPublished = !note.is_published

    try {
      const payload = {
        is_published: newIsPublished,
        status: newIsPublished ? 'PUBLISHED' : 'DRAFT'
      }
      const res = await studyBuddyAPI.updateNote(note.id, payload)
      toast.success(newIsPublished ? 'Note published successfully!' : 'Note moved to drafts.')

      // Update local state directly
      setNotes((prev) =>
        prev.map((n) => (n.id === note.id ? { ...n, ...res.data } : n))
      )
    } catch (err) {
      console.error('Failed to toggle publication status:', err)
      const detail = err.response?.data?.detail || 'Failed to update publication status.'
      toast.error(detail)
    } finally {
      setPublishingNoteId(null)
    }
  }

  // ---------------------------------------------------------------------------
  // Note Actions: Retry Processing
  // ---------------------------------------------------------------------------
  const handleRetryProcessing = async (noteId) => {
    setRetryingNoteId(noteId)
    try {
      const res = await studyBuddyAPI.retryNoteProcessing(noteId)
      toast.success('Extraction retried successfully!')
      setNotes((prev) =>
        prev.map((n) => (n.id === noteId ? { ...n, ...res.data } : n))
      )
    } catch (err) {
      console.error('Failed to retry note processing:', err)
      const detail = err.response?.data?.detail || 'Failed to retry processing.'
      toast.error(detail)
    } finally {
      setRetryingNoteId(null)
    }
  }

  // ---------------------------------------------------------------------------
  // Note Actions: Edit Metadata
  // ---------------------------------------------------------------------------
  const handleOpenEditModal = (note) => {
    setEditingNote(note)
    setEditTitle(note.title || '')
    setEditDescription(note.description || '')
    setEditUnitId(note.unit_id ? String(note.unit_id) : '')
    setEditTopicId(note.topic_id ? String(note.topic_id) : '')
    setEditStatus(note.status || 'DRAFT')
  }

  const handleSaveEdit = async (e) => {
    e.preventDefault()
    if (!editingNote) return
    if (!editTitle.trim()) {
      toast.error('Title cannot be empty.')
      return
    }

    setIsSavingEdit(true)
    try {
      const payload = {
        title: editTitle.trim(),
        description: editDescription.trim() || null,
        unit_id: editUnitId ? Number(editUnitId) : null,
        topic_id: editTopicId ? Number(editTopicId) : null,
        status: editStatus
      }

      const res = await studyBuddyAPI.updateNote(editingNote.id, payload)
      toast.success('Note updated successfully!')
      setNotes((prev) =>
        prev.map((n) => (n.id === editingNote.id ? { ...n, ...res.data } : n))
      )
      setEditingNote(null)
    } catch (err) {
      console.error('Failed to update note:', err)
      const detail = err.response?.data?.detail || 'Failed to update note.'
      toast.error(detail)
    } finally {
      setIsSavingEdit(false)
    }
  }

  // ---------------------------------------------------------------------------
  // Note Actions: Delete
  // ---------------------------------------------------------------------------
  const handleConfirmDelete = async () => {
    if (!deletingNote) return
    setIsDeleting(true)
    try {
      await studyBuddyAPI.deleteNote(deletingNote.id)
      toast.success('Lecture note deleted successfully.')
      setNotes((prev) => prev.filter((n) => n.id !== deletingNote.id))
      setDeletingNote(null)
    } catch (err) {
      console.error('Failed to delete note:', err)
      const detail = err.response?.data?.detail || 'Failed to delete lecture note.'
      toast.error(detail)
    } finally {
      setIsDeleting(false)
    }
  }

  // ---------------------------------------------------------------------------
  // Note Actions: Download Original File
  // ---------------------------------------------------------------------------
  const handleDownloadNote = async (note) => {
    if (!note.file_id) {
      toast.error('No stored file attachment found for this note.')
      return
    }

    const toastId = toast.loading('Preparing download...')
    try {
      const res = await studyBuddyAPI.downloadNoteFile(note.file_id)
      const blob = new Blob([res.data], { type: note.mime_type || 'application/octet-stream' })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', note.original_filename || `${note.title}.pdf`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      toast.success('Download complete!', { id: toastId })
    } catch (err) {
      console.error('Download failed:', err)
      toast.error('Failed to download file. Please try again.', { id: toastId })
    }
  }

  // Statistics
  const stats = useMemo(() => {
    const total = notes.length
    const published = notes.filter((n) => n.is_published).length
    const extracted = notes.filter((n) => n.processing_status === 'EXTRACTED').length
    const failed = notes.filter((n) => n.processing_status === 'FAILED').length
    return { total, published, extracted, failed }
  }, [notes])

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="text-2xl">📖</span>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Course Materials</h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Manage, ingest, and publish lecture notes for Study Buddy library
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            id="refresh-notes-btn"
            onClick={() => activeSubject && fetchNotes(activeSubject.id)}
            disabled={loadingNotes || !activeSubject}
            className="p-2.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 transition-colors cursor-pointer"
            title="Refresh notes"
          >
            <RefreshCw className={`w-4 h-4 ${loadingNotes ? 'animate-spin' : ''}`} />
          </button>

          <button
            id="btn-open-add-subject"
            onClick={handleOpenAddSubjectModal}
            className="flex items-center space-x-2 px-3.5 py-2.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-750 font-medium text-sm shadow-sm transition-colors cursor-pointer"
            title="Add a new academic subject"
          >
            <Plus className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            <span>Add Subject</span>
          </button>

          <button
            id="upload-note-btn"
            onClick={handleOpenUploadModal}
            disabled={!activeSubject}
            className="flex items-center space-x-2 px-4 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium shadow-sm transition-colors disabled:opacity-50 cursor-pointer"
          >
            <Upload className="w-4 h-4" />
            <span>Upload Notes</span>
          </button>
        </div>
      </div>

      {/* Semester & Subject Selector & Scope Banner */}
      <div className="bg-white dark:bg-gray-900 rounded-xl p-5 border border-gray-200 dark:border-gray-800 shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex flex-col sm:flex-row sm:items-center gap-3 w-full md:w-auto">
            {/* Step 1: Semester Selector */}
            <div className="w-full sm:w-48">
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-1.5">
                1. Select Semester
              </label>
              <select
                id="semester-selector"
                value={selectedSemester}
                onChange={(e) => handleSemesterChange(e.target.value)}
                className="w-full px-3.5 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 font-medium text-sm transition-colors"
              >
                <option value="">-- Select Semester --</option>
                {SEMESTERS.map((sem) => (
                  <option key={sem} value={sem}>
                    Semester {sem}
                  </option>
                ))}
              </select>
            </div>

            {/* Step 2: Subject Selector (Filtered to active authorized subjects for selected semester) */}
            <div className="w-full sm:w-80">
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-1.5">
                2. Select Subject
              </label>
              {loadingSubjects ? (
                <div className="h-10 bg-gray-100 dark:bg-gray-800 rounded-lg animate-pulse" />
              ) : !selectedSemester ? (
                <div className="px-3.5 py-2 rounded-lg bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-400 text-sm">
                  Please select a semester first
                </div>
              ) : availableSubjectsForSemester.length === 0 ? (
                <div className="flex items-center justify-between gap-2 px-3.5 py-2 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-400 text-sm">
                  <span className="truncate">No active subjects for Sem {selectedSemester}</span>
                  <button
                    id="btn-add-subject-empty"
                    type="button"
                    onClick={handleOpenAddSubjectModal}
                    className="text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1 shrink-0 cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Add</span>
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-1.5">
                  <select
                    id="subject-selector"
                    value={selectedSubjectId}
                    onChange={(e) => setSelectedSubjectId(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 font-medium text-sm transition-colors"
                  >
                    <option value="">-- Select Subject --</option>
                    {availableSubjectsForSemester.map((sub) => (
                      <option key={sub.id} value={sub.id}>
                        {sub.code} — {sub.name}
                      </option>
                    ))}
                  </select>
                  <button
                    id="btn-quick-add-subject"
                    type="button"
                    onClick={handleOpenAddSubjectModal}
                    title="Add new subject"
                    className="p-2.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950/50 transition-colors shrink-0 cursor-pointer"
                  >
                    <Plus className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
          </div>

          {activeSubject && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-blue-50 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                Department: {activeSubject.department}
              </span>
              <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-purple-50 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
                Semester {activeSubject.semester}
              </span>
              {syllabusDoc ? (
                <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-md text-xs font-medium bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                  <FileCheck className="w-3.5 h-3.5" />
                  <span>Syllabus v{syllabusDoc.version} Linked ({availableUnits.length} Units)</span>
                </span>
              ) : (
                <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-md text-xs font-medium bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400">
                  <Info className="w-3.5 h-3.5" />
                  <span>No approved syllabus linked</span>
                </span>
              )}
            </div>
          )}
        </div>

        {/* Stats strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-gray-100 dark:border-gray-800">
          <div className="p-3 rounded-lg bg-gray-50 dark:bg-gray-800/60">
            <span className="text-xs text-gray-500 dark:text-gray-400 block">Total Notes</span>
            <span className="text-xl font-bold text-gray-900 dark:text-white">{stats.total}</span>
          </div>
          <div className="p-3 rounded-lg bg-emerald-50/60 dark:bg-emerald-950/20">
            <span className="text-xs text-emerald-700 dark:text-emerald-400 block">Published</span>
            <span className="text-xl font-bold text-emerald-700 dark:text-emerald-300">{stats.published}</span>
          </div>
          <div className="p-3 rounded-lg bg-blue-50/60 dark:bg-blue-950/20">
            <span className="text-xs text-blue-700 dark:text-blue-400 block">Extracted</span>
            <span className="text-xl font-bold text-blue-700 dark:text-blue-300">{stats.extracted}</span>
          </div>
          <div className="p-3 rounded-lg bg-amber-50/60 dark:bg-amber-950/20">
            <span className="text-xs text-amber-700 dark:text-amber-400 block">Failed / Pending</span>
            <span className="text-xl font-bold text-amber-700 dark:text-amber-300">{stats.failed}</span>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white dark:bg-gray-900 rounded-xl p-4 border border-gray-200 dark:border-gray-800 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 absolute left-3 top-3 text-gray-400" />
          <input
            id="notes-search-input"
            type="text"
            placeholder="Search notes by title..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 top-2.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2.5 w-full sm:w-auto">
          {/* Status Filter */}
          <div className="flex items-center space-x-1.5">
            <Filter className="w-3.5 h-3.5 text-gray-400" />
            <select
              id="notes-status-filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-xs px-2.5 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 font-medium focus:ring-2 focus:ring-blue-500"
            >
              <option value="ALL">All Statuses</option>
              <option value="DRAFT">Draft</option>
              <option value="PUBLISHED">Published</option>
              <option value="ARCHIVED">Archived</option>
            </select>
          </div>

          {/* Unit Filter */}
          {availableUnits.length > 0 && (
            <div className="flex items-center space-x-1.5">
              <Layers className="w-3.5 h-3.5 text-gray-400" />
              <select
                id="notes-unit-filter"
                value={unitFilter}
                onChange={(e) => setUnitFilter(e.target.value)}
                className="text-xs px-2.5 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 font-medium focus:ring-2 focus:ring-blue-500 max-w-[180px] truncate"
              >
                <option value="ALL">All Units</option>
                {availableUnits.map((u) => (
                  <option key={u.id} value={u.id}>
                    Unit {u.unit_number}: {u.title}
                  </option>
                ))}
              </select>
            </div>
          )}

          {(searchQuery || statusFilter !== 'ALL' || unitFilter !== 'ALL') && (
            <button
              onClick={() => {
                setSearchQuery('')
                setStatusFilter('ALL')
                setUnitFilter('ALL')
              }}
              className="text-xs text-blue-600 dark:text-blue-400 hover:underline px-1 py-1"
            >
              Reset filters
            </button>
          )}
        </div>
      </div>

      {/* Notes List / Empty / Loading State */}
      {!selectedSubjectId ? (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-dashed border-gray-300 dark:border-gray-800 p-12 text-center space-y-4">
          <div className="w-16 h-16 bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 rounded-full flex items-center justify-center mx-auto text-2xl">
            📖
          </div>
          <div className="space-y-1">
            <h3 className="font-semibold text-lg text-gray-900 dark:text-white">
              {!selectedSemester ? 'Select a Semester to Begin' : 'Select a Subject to View Course Materials'}
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
              {!selectedSemester
                ? 'Choose a semester above to filter and display active subjects authorized for your department.'
                : `Select one of the active subjects for Semester ${selectedSemester} above to view notes or upload materials.`}
            </p>
          </div>
        </div>
      ) : loadingNotes ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-28 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 animate-pulse p-5"
            />
          ))}
        </div>
      ) : notesError ? (
        <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900 rounded-xl p-8 text-center space-y-3">
          <AlertCircle className="w-10 h-10 text-red-500 mx-auto" />
          <h3 className="font-semibold text-gray-900 dark:text-white">Unable to load lecture notes</h3>
          <p className="text-sm text-red-600 dark:text-red-400 max-w-md mx-auto">{notesError}</p>
          <button
            onClick={() => activeSubject && fetchNotes(activeSubject.id)}
            className="px-4 py-2 text-xs font-medium rounded-lg bg-red-600 hover:bg-red-700 text-white transition-colors"
          >
            Try Again
          </button>
        </div>
      ) : notes.length === 0 ? (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-dashed border-gray-300 dark:border-gray-800 p-12 text-center space-y-4">
          <div className="w-16 h-16 bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 rounded-full flex items-center justify-center mx-auto text-2xl">
            📚
          </div>
          <div className="space-y-1">
            <h3 className="font-semibold text-lg text-gray-900 dark:text-white">
              No lecture notes found
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
              {searchQuery || statusFilter !== 'ALL' || unitFilter !== 'ALL'
                ? 'No notes match the current search or filters. Try adjusting them.'
                : 'Upload lecture slides, documents, or diagrams (PDF, PNG, DOCX, PPTX) to enrich your subject library.'}
            </p>
          </div>
          <button
            onClick={handleOpenUploadModal}
            disabled={!activeSubject}
            className="inline-flex items-center space-x-2 px-4 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition-colors cursor-pointer"
          >
            <Upload className="w-4 h-4" />
            <span>Upload First Note</span>
          </button>
        </div>
      ) : (
        <div className="space-y-3.5">
          {notes.map((note) => {
            const formatInfo = getFileFormatInfo(note.original_filename)
            const FormatIcon = formatInfo.icon
            const unitLabel = getUnitTopicLabel(note.unit_id, note.topic_id)

            // Guard: Can only publish if processing_status is EXTRACTED
            const canPublish = note.processing_status === 'EXTRACTED'
            const isRetrying = retryingNoteId === note.id
            const isPublishing = publishingNoteId === note.id

            return (
              <div
                key={note.id}
                className="bg-white dark:bg-gray-900 rounded-xl p-5 border border-gray-200 dark:border-gray-800 shadow-sm hover:border-gray-300 dark:hover:border-gray-700 transition-all space-y-3"
              >
                <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                  {/* Left: Icon & Info */}
                  <div className="flex items-start space-x-3.5 min-w-0 flex-1">
                    <div
                      className={`w-12 h-12 rounded-xl flex items-center justify-center border shrink-0 ${formatInfo.color}`}
                    >
                      <FormatIcon className="w-6 h-6" />
                    </div>

                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-semibold text-base text-gray-900 dark:text-white truncate">
                          {note.title}
                        </h3>

                        {/* Format badge */}
                        <span
                          className={`text-[11px] font-bold px-2 py-0.5 rounded border uppercase ${formatInfo.color}`}
                        >
                          {formatInfo.label}
                        </span>

                        {/* Publication Status Badge */}
                        {note.is_published ? (
                          <span className="inline-flex items-center space-x-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                            <Eye className="w-3 h-3" />
                            <span>Published</span>
                          </span>
                        ) : note.status === 'ARCHIVED' ? (
                          <span className="inline-flex items-center space-x-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                            <Archive className="w-3 h-3" />
                            <span>Archived</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center space-x-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-700">
                            <EyeOff className="w-3 h-3" />
                            <span>Draft</span>
                          </span>
                        )}

                        {/* Extraction Processing Status Badge */}
                        {note.processing_status === 'EXTRACTED' ? (
                          <span className="inline-flex items-center space-x-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                            <CheckCircle className="w-3 h-3 text-blue-500" />
                            <span>Text Extracted</span>
                          </span>
                        ) : note.processing_status === 'PROCESSING' ? (
                          <span className="inline-flex items-center space-x-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                            <RefreshCw className="w-3 h-3 animate-spin text-blue-500" />
                            <span>Extracting Text...</span>
                          </span>
                        ) : note.processing_status === 'FAILED' ? (
                          <span
                            title={note.extraction_error || 'Extraction failed'}
                            className="inline-flex items-center space-x-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-900 cursor-help"
                          >
                            <AlertTriangle className="w-3 h-3 text-red-500" />
                            <span>Extraction Failed</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center space-x-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-yellow-50 dark:bg-yellow-950/40 text-yellow-700 dark:text-yellow-400 border border-yellow-200 dark:border-yellow-900">
                            <Clock className="w-3 h-3" />
                            <span>Uploaded</span>
                          </span>
                        )}
                      </div>

                      {/* File Details Subtitle */}
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500 dark:text-gray-400">
                        <span className="font-mono text-gray-600 dark:text-gray-300 truncate max-w-xs">
                          {note.original_filename}
                        </span>
                        <span>•</span>
                        <span>{formatFileSize(note.file_size)}</span>
                        <span>•</span>
                        <span>Uploaded {formatDate(note.created_at)}</span>
                        {note.download_count > 0 && (
                          <>
                            <span>•</span>
                            <span>{note.download_count} downloads</span>
                          </>
                        )}
                      </div>

                      {/* Unit / Topic Provenance */}
                      {unitLabel && (
                        <div className="flex items-center space-x-1.5 text-xs text-blue-700 dark:text-blue-300 font-medium pt-0.5">
                          <Layers className="w-3.5 h-3.5" />
                          <span>{unitLabel}</span>
                        </div>
                      )}

                      {/* Description */}
                      {note.description && (
                        <p className="text-xs text-gray-600 dark:text-gray-300 pt-1 line-clamp-2">
                          {note.description}
                        </p>
                      )}

                      {/* Error banner if extraction failed */}
                      {note.processing_status === 'FAILED' && note.extraction_error && (
                        <div className="bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 rounded-lg p-2.5 text-xs text-red-700 dark:text-red-300 mt-2">
                          <span className="font-semibold">Reason:</span> {note.extraction_error}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Right: Actions Toolbar */}
                  <div className="flex flex-wrap items-center gap-1.5 self-end md:self-start shrink-0 pt-2 md:pt-0">
                    {/* Retry button (if failed or stuck uploaded) */}
                    {(note.processing_status === 'FAILED' ||
                      note.processing_status === 'UPLOADED') && (
                      <button
                        onClick={() => handleRetryProcessing(note.id)}
                        disabled={isRetrying}
                        className="px-2.5 py-1.5 rounded-lg border border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 hover:bg-amber-100 dark:hover:bg-amber-900/40 text-xs font-medium flex items-center space-x-1.5 transition-colors cursor-pointer disabled:opacity-50"
                        title="Retry text extraction"
                      >
                        <RefreshCw className={`w-3.5 h-3.5 ${isRetrying ? 'animate-spin' : ''}`} />
                        <span>{isRetrying ? 'Retrying...' : 'Retry'}</span>
                      </button>
                    )}

                    {/* Publish / Unpublish Toggle */}
                    <button
                      onClick={() => handleTogglePublish(note)}
                      disabled={isPublishing || (!note.is_published && !canPublish)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
                        note.is_published
                          ? 'border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                          : canPublish
                          ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                          : 'bg-gray-200 dark:bg-gray-800 text-gray-400 dark:text-gray-500'
                      }`}
                      title={
                        !note.is_published && !canPublish
                          ? 'Text extraction must complete successfully before publishing.'
                          : note.is_published
                          ? 'Unpublish and move to draft'
                          : 'Publish note to students'
                      }
                    >
                      {isPublishing ? (
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      ) : note.is_published ? (
                        <EyeOff className="w-3.5 h-3.5" />
                      ) : (
                        <Eye className="w-3.5 h-3.5" />
                      )}
                      <span>
                        {isPublishing
                          ? 'Updating...'
                          : note.is_published
                          ? 'Unpublish'
                          : 'Publish'}
                      </span>
                    </button>

                    {/* Download */}
                    {note.file_id && (
                      <button
                        onClick={() => handleDownloadNote(note)}
                        className="p-1.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors cursor-pointer"
                        title="Download original file"
                      >
                        <Download className="w-4 h-4" />
                      </button>
                    )}

                    {/* Edit Metadata */}
                    <button
                      onClick={() => handleOpenEditModal(note)}
                      className="p-1.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950/40 transition-colors cursor-pointer"
                      title="Edit note metadata"
                    >
                      <Edit className="w-4 h-4" />
                    </button>

                    {/* Delete */}
                    <button
                      onClick={() => setDeletingNote(note)}
                      className="p-1.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40 transition-colors cursor-pointer"
                      title="Delete note"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* Upload Note Modal */}
      {/* --------------------------------------------------------------------- */}
      {isUploadModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 max-w-xl w-full shadow-2xl overflow-hidden transition-all">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Upload className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                <h2 className="text-lg font-bold text-gray-900 dark:text-white">Upload Lecture Note</h2>
              </div>
              <button
                onClick={() => !isUploading && setIsUploadModalOpen(false)}
                disabled={isUploading}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Form */}
            <form onSubmit={handleUploadSubmit} className="p-6 space-y-4">
              {/* Validation error banner */}
              {uploadValidationErr && (
                <div className="bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 rounded-xl p-3.5 text-xs text-red-700 dark:text-red-300 flex items-start space-x-2">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-red-500" />
                  <span>{uploadValidationErr}</span>
                </div>
              )}

              {/* Target Semester & Subject selector in modal */}
              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-800/60 p-2.5 rounded-lg border border-gray-200 dark:border-gray-700">
                  <span>Target Semester: <strong className="text-gray-900 dark:text-white">Semester {selectedSemester || (activeSubject ? activeSubject.semester : '—')}</strong></span>
                  <span>Department: <strong className="text-gray-900 dark:text-white">{activeSubject?.department || user?.department || 'Authorized'}</strong></span>
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 mb-1.5">
                    Subject *
                  </label>
                  <select
                    value={uploadSubjectId}
                    onChange={(e) => setUploadSubjectId(e.target.value)}
                    disabled={isUploading || availableSubjectsForSemester.length === 0}
                    className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 font-medium"
                  >
                    <option value="">-- Select Subject --</option>
                    {availableSubjectsForSemester.map((sub) => (
                      <option key={sub.id} value={sub.id}>
                        {sub.code} — {sub.name} (Sem {sub.semester})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* File Dropzone / Picker */}
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 mb-1.5">
                  File Attachment (PDF, PNG, DOCX, PPTX — Up to 500 MiB) *
                </label>
                <div
                  onClick={() => !isUploading && fileInputRef.current?.click()}
                  className={`border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-colors ${
                    uploadFile
                      ? 'border-blue-500 bg-blue-50/50 dark:bg-blue-950/20'
                      : 'border-gray-300 dark:border-gray-700 hover:border-blue-400 bg-gray-50 dark:bg-gray-800/40'
                  }`}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.png,.docx,.pptx,application/pdf,image/png,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                  {uploadFile ? (
                    <div className="space-y-1">
                      <div className="inline-flex items-center space-x-2 text-sm font-semibold text-blue-700 dark:text-blue-300">
                        <FileCheck className="w-5 h-5 text-blue-600" />
                        <span className="truncate max-w-sm">{uploadFile.name}</span>
                      </div>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {formatFileSize(uploadFile.size)} • Click to choose a different file
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-1.5">
                      <Upload className="w-8 h-8 text-gray-400 mx-auto" />
                      <p className="text-sm font-medium text-gray-700 dark:text-gray-200">
                        Click to browse file from your device
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        Strictly bounded up to 500 MiB per file
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Title */}
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 mb-1.5">
                  Note Title *
                </label>
                <input
                  type="text"
                  required
                  maxLength={255}
                  value={uploadTitle}
                  onChange={(e) => setUploadTitle(e.target.value)}
                  placeholder="e.g. Unit 2: CPU Scheduling Algorithms Lecture Notes"
                  disabled={isUploading}
                  className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Description */}
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 mb-1.5">
                  Description (Optional)
                </label>
                <textarea
                  rows={2}
                  value={uploadDescription}
                  onChange={(e) => setUploadDescription(e.target.value)}
                  placeholder="Key concepts covered, recommended reading, tutorial problems..."
                  disabled={isUploading}
                  className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Unit & Topic Alignment */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 mb-1.5">
                    Syllabus Unit (Optional)
                  </label>
                  <select
                    value={uploadUnitId}
                    onChange={(e) => {
                      setUploadUnitId(e.target.value)
                      setUploadTopicId('')
                    }}
                    disabled={isUploading || availableUnits.length === 0}
                    className="w-full px-3 py-2 text-xs rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                  >
                    <option value="">No unit association</option>
                    {availableUnits.map((u) => (
                      <option key={u.id} value={u.id}>
                        Unit {u.unit_number}: {u.title}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 mb-1.5">
                    Topic (Optional)
                  </label>
                  <select
                    value={uploadTopicId}
                    onChange={(e) => setUploadTopicId(e.target.value)}
                    disabled={isUploading || uploadTopics.length === 0}
                    className="w-full px-3 py-2 text-xs rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                  >
                    <option value="">No topic association</option>
                    {uploadTopics.map((t) => (
                      <option key={t.id} value={t.id}>
                        Topic {t.topic_number}: {t.title}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Upload Progress Bar */}
              {isUploading && (
                <div className="space-y-1.5 pt-2">
                  <div className="flex justify-between text-xs font-medium text-gray-600 dark:text-gray-300">
                    <span>Uploading and streaming to storage...</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5 overflow-hidden">
                    <div
                      className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                  <p className="text-[11px] text-gray-500 dark:text-gray-400">
                    Background extraction starts automatically after file upload finishes.
                  </p>
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center justify-end space-x-3 pt-3 border-t border-gray-100 dark:border-gray-800">
                <button
                  type="button"
                  onClick={() => setIsUploadModalOpen(false)}
                  disabled={isUploading}
                  className="px-4 py-2 text-sm font-medium rounded-lg border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isUploading || !uploadFile}
                  className="flex items-center space-x-2 px-5 py-2 text-sm font-medium rounded-lg bg-blue-600 hover:bg-blue-700 text-white shadow-sm transition-colors disabled:opacity-50 cursor-pointer"
                >
                  {isUploading && <RefreshCw className="w-4 h-4 animate-spin" />}
                  <span>{isUploading ? 'Uploading Note...' : 'Upload Note'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* Edit Note Modal */}
      {/* --------------------------------------------------------------------- */}
      {editingNote && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 max-w-lg w-full shadow-2xl overflow-hidden transition-all">
            <div className="px-6 py-4 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Edit className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                <h2 className="text-lg font-bold text-gray-900 dark:text-white">Edit Lecture Note</h2>
              </div>
              <button
                onClick={() => !isSavingEdit && setEditingNote(null)}
                disabled={isSavingEdit}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveEdit} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 mb-1.5">
                  Title *
                </label>
                <input
                  type="text"
                  required
                  maxLength={255}
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  disabled={isSavingEdit}
                  className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 mb-1.5">
                  Description
                </label>
                <textarea
                  rows={2}
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  disabled={isSavingEdit}
                  className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 mb-1.5">
                    Syllabus Unit
                  </label>
                  <select
                    value={editUnitId}
                    onChange={(e) => {
                      setEditUnitId(e.target.value)
                      setEditTopicId('')
                    }}
                    disabled={isSavingEdit || availableUnits.length === 0}
                    className="w-full px-3 py-2 text-xs rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">No unit association</option>
                    {availableUnits.map((u) => (
                      <option key={u.id} value={u.id}>
                        Unit {u.unit_number}: {u.title}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 mb-1.5">
                    Topic
                  </label>
                  <select
                    value={editTopicId}
                    onChange={(e) => setEditTopicId(e.target.value)}
                    disabled={isSavingEdit || editTopics.length === 0}
                    className="w-full px-3 py-2 text-xs rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">No topic association</option>
                    {editTopics.map((t) => (
                      <option key={t.id} value={t.id}>
                        Topic {t.topic_number}: {t.title}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Status selection (Draft vs Archived) */}
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 mb-1.5">
                  Lifecycle Status
                </label>
                <select
                  value={editStatus}
                  onChange={(e) => setEditStatus(e.target.value)}
                  disabled={isSavingEdit}
                  className="w-full px-3 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                >
                  <option value="DRAFT">DRAFT</option>
                  <option value="ARCHIVED">ARCHIVED</option>
                  {editingNote.processing_status === 'EXTRACTED' && (
                    <option value="PUBLISHED">PUBLISHED</option>
                  )}
                </select>
                {editingNote.processing_status !== 'EXTRACTED' && (
                  <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-1">
                    Note cannot be set to PUBLISHED until text extraction completes successfully.
                  </p>
                )}
              </div>

              <div className="flex items-center justify-end space-x-3 pt-3 border-t border-gray-100 dark:border-gray-800">
                <button
                  type="button"
                  onClick={() => setEditingNote(null)}
                  disabled={isSavingEdit}
                  className="px-4 py-2 text-sm font-medium rounded-lg border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSavingEdit}
                  className="flex items-center space-x-2 px-5 py-2 text-sm font-medium rounded-lg bg-blue-600 hover:bg-blue-700 text-white shadow-sm transition-colors disabled:opacity-50 cursor-pointer"
                >
                  {isSavingEdit && <RefreshCw className="w-4 h-4 animate-spin" />}
                  <span>{isSavingEdit ? 'Saving...' : 'Save Changes'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* Delete Confirmation Dialog */}
      {/* --------------------------------------------------------------------- */}
      {deletingNote && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 max-w-md w-full shadow-2xl p-6 space-y-4">
            <div className="flex items-center space-x-3 text-red-600 dark:text-red-400">
              <div className="w-10 h-10 rounded-full bg-red-50 dark:bg-red-950/40 flex items-center justify-center shrink-0">
                <Trash2 className="w-5 h-5" />
              </div>
              <h3 className="text-lg font-bold text-gray-900 dark:text-white">Delete Lecture Note?</h3>
            </div>

            <p className="text-sm text-gray-600 dark:text-gray-300">
              Are you sure you want to permanently delete{' '}
              <strong className="text-gray-900 dark:text-white">"{deletingNote.title}"</strong>?
              This will remove the file from storage and revoke access for students. This action cannot be undone.
            </p>

            <div className="flex items-center justify-end space-x-3 pt-2">
              <button
                type="button"
                onClick={() => setDeletingNote(null)}
                disabled={isDeleting}
                className="px-4 py-2 text-sm font-medium rounded-lg border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                disabled={isDeleting}
                className="flex items-center space-x-2 px-5 py-2 text-sm font-medium rounded-lg bg-red-600 hover:bg-red-700 text-white shadow-sm transition-colors disabled:opacity-50 cursor-pointer"
              >
                {isDeleting && <RefreshCw className="w-4 h-4 animate-spin" />}
                <span>{isDeleting ? 'Deleting...' : 'Delete Permanently'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
      {/* --------------------------------------------------------------------- */}
      {/* Add Subject Modal (Part B)                                            */}
      {/* --------------------------------------------------------------------- */}
      {isAddSubjectModalOpen && (
        <div
          id="add-subject-modal"
          className="fixed inset-0 z-50 overflow-y-auto bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-150"
          role="dialog"
          aria-modal="true"
        >
          <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 max-w-lg w-full shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-gray-100 dark:border-gray-800 pb-3">
              <div className="flex items-center space-x-2">
                <div className="p-2 rounded-lg bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400">
                  <BookOpen className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-gray-900 dark:text-white">Add Academic Subject</h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Create a new subject for {user?.department || 'your department'}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsAddSubjectModalOpen(false)}
                className="p-1 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {subjectFormError && (
              <div className="p-3 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/60 text-xs text-red-700 dark:text-red-300 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{subjectFormError}</span>
              </div>
            )}

            <form onSubmit={handleCreateSubject} className="space-y-3.5">
              {/* Department (Read-only / Authorized Scope) */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Department
                </label>
                <input
                  type="text"
                  value={user?.department || 'AIML'}
                  disabled
                  className="w-full px-3.5 py-2 rounded-lg bg-gray-100 dark:bg-gray-800/60 border border-gray-300 dark:border-gray-700 text-gray-500 dark:text-gray-400 text-sm font-semibold cursor-not-allowed"
                />
                <p className="text-[11px] text-gray-400 mt-0.5">
                  Locked to your authorized faculty department.
                </p>
              </div>

              {/* Semester Selector */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Semester <span className="text-red-500">*</span>
                </label>
                <select
                  id="create-subject-semester"
                  value={subjectFormData.semester}
                  onChange={(e) => setSubjectFormData((prev) => ({ ...prev, semester: e.target.value }))}
                  required
                  className="w-full px-3.5 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white text-sm focus:ring-2 focus:ring-blue-500"
                >
                  {SEMESTERS.map((sem) => (
                    <option key={sem} value={sem}>
                      Semester {sem}
                    </option>
                  ))}
                </select>
              </div>

              {/* Subject Code */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Subject Code <span className="text-red-500">*</span>
                </label>
                <input
                  id="create-subject-code"
                  type="text"
                  placeholder="e.g., CS601, AIML602"
                  value={subjectFormData.code}
                  onChange={(e) => setSubjectFormData((prev) => ({ ...prev, code: e.target.value.toUpperCase() }))}
                  required
                  className="w-full px-3.5 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white text-sm uppercase focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Subject Name */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Subject Name <span className="text-red-500">*</span>
                </label>
                <input
                  id="create-subject-name"
                  type="text"
                  placeholder="e.g., Deep Learning Architecture"
                  value={subjectFormData.name}
                  onChange={(e) => setSubjectFormData((prev) => ({ ...prev, name: e.target.value }))}
                  required
                  className="w-full px-3.5 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white text-sm focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Curriculum Version & Academic Year */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                    Curriculum Version
                  </label>
                  <input
                    id="create-subject-curriculum"
                    type="text"
                    placeholder="2024.1"
                    value={subjectFormData.curriculum_version}
                    onChange={(e) => setSubjectFormData((prev) => ({ ...prev, curriculum_version: e.target.value }))}
                    className="w-full px-3.5 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white text-sm focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                    Academic Year
                  </label>
                  <input
                    id="create-subject-academic-year"
                    type="text"
                    placeholder="2026-2027"
                    value={subjectFormData.academic_year}
                    onChange={(e) => setSubjectFormData((prev) => ({ ...prev, academic_year: e.target.value }))}
                    className="w-full px-3.5 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white text-sm focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              {/* Description */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">
                  Description (Optional)
                </label>
                <textarea
                  id="create-subject-description"
                  rows={2}
                  placeholder="Brief course objectives..."
                  value={subjectFormData.description}
                  onChange={(e) => setSubjectFormData((prev) => ({ ...prev, description: e.target.value }))}
                  className="w-full px-3.5 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white text-sm focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="flex items-center justify-end space-x-3 pt-3 border-t border-gray-100 dark:border-gray-800">
                <button
                  type="button"
                  onClick={() => setIsAddSubjectModalOpen(false)}
                  disabled={isCreatingSubject}
                  className="px-4 py-2 text-sm font-medium rounded-lg border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors disabled:opacity-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  id="btn-submit-create-subject"
                  type="submit"
                  disabled={isCreatingSubject}
                  className="flex items-center space-x-2 px-5 py-2 text-sm font-semibold rounded-lg bg-blue-600 hover:bg-blue-700 text-white shadow-sm transition-colors disabled:opacity-50 cursor-pointer"
                >
                  {isCreatingSubject && <RefreshCw className="w-4 h-4 animate-spin" />}
                  <span>{isCreatingSubject ? 'Creating...' : 'Create Subject'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
