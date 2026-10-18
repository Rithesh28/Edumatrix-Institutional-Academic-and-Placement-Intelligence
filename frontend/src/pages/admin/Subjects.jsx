import React, { useState, useEffect, useMemo } from 'react'
import {
  BookOpen,
  Plus,
  Search,
  Filter,
  Edit2,
  Trash2,
  Power,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  XCircle,
  FileText,
  Calendar,
  Layers,
  Building2,
  GraduationCap,
  X
} from 'lucide-react'
import { studyBuddyAPI } from '../../services/api'
import toast from 'react-hot-toast'

const DEPARTMENTS = ['AIML', 'CSE', 'ECE', 'MECH', 'CIVIL', 'IT', 'EEE']
const SEMESTERS = [1, 2, 3, 4, 5, 6, 7, 8]

export default function AdminSubjects() {
  const [subjects, setSubjects] = useState([])
  const [isLoading, setIsLoading] = useState(true)

  // Filters
  const [searchQuery, setSearchQuery] = useState('')
  const [departmentFilter, setDepartmentFilter] = useState('ALL')
  const [semesterFilter, setSemesterFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState('ALL')

  // Modals
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [editingSubject, setEditingSubject] = useState(null)
  const [deletingSubject, setDeletingSubject] = useState(null)
  const [togglingSubject, setTogglingSubject] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Form State
  const [formData, setFormData] = useState({
    code: '',
    name: '',
    department: 'AIML',
    semester: 1,
    curriculum_version: '2024-v1',
    academic_year: '2024-2025',
    is_active: true
  })
  const [formError, setFormError] = useState('')

  const fetchSubjects = async () => {
    setIsLoading(true)
    try {
      // Admin sees both active and inactive subjects
      const res = await studyBuddyAPI.getSubjects({ is_active: false })
      setSubjects(res.data || [])
    } catch (err) {
      console.error('Failed to fetch subjects:', err)
      toast.error('Failed to load academic subjects.')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchSubjects()
  }, [])

  // Filtered list
  const filteredSubjects = useMemo(() => {
    return subjects.filter((s) => {
      if (departmentFilter !== 'ALL' && s.department.toUpperCase() !== departmentFilter.toUpperCase()) {
        return false
      }
      if (semesterFilter !== 'ALL' && Number(s.semester) !== Number(semesterFilter)) {
        return false
      }
      if (statusFilter === 'ACTIVE' && !s.is_active) {
        return false
      }
      if (statusFilter === 'INACTIVE' && s.is_active) {
        return false
      }
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase().trim()
        const matchCode = s.code.toLowerCase().includes(query)
        const matchName = s.name.toLowerCase().includes(query)
        const matchDept = s.department.toLowerCase().includes(query)
        if (!matchCode && !matchName && !matchDept) return false
      }
      return true
    })
  }, [subjects, departmentFilter, semesterFilter, statusFilter, searchQuery])

  // Stats
  const stats = useMemo(() => {
    const total = subjects.length
    const active = subjects.filter((s) => s.is_active).length
    const inactive = total - active
    const totalNotes = subjects.reduce((acc, s) => acc + (s.lecture_notes_count || 0), 0)
    return { total, active, inactive, totalNotes }
  }, [subjects])

  // Form Handlers
  const handleOpenAddModal = () => {
    setFormData({
      code: '',
      name: '',
      department: departmentFilter !== 'ALL' ? departmentFilter : 'AIML',
      semester: semesterFilter !== 'ALL' ? Number(semesterFilter) : 1,
      curriculum_version: '2024-v1',
      academic_year: '2024-2025',
      is_active: true
    })
    setFormError('')
    setIsAddModalOpen(true)
  }

  const handleOpenEditModal = (subject) => {
    setEditingSubject(subject)
    setFormData({
      code: subject.code,
      name: subject.name,
      department: subject.department,
      semester: subject.semester,
      curriculum_version: subject.curriculum_version || '2024-v1',
      academic_year: subject.academic_year || '2024-2025',
      is_active: subject.is_active
    })
    setFormError('')
  }

  const handleCreateSubject = async (e) => {
    e.preventDefault()
    setFormError('')

    if (!formData.code.trim() || !formData.name.trim() || !formData.department.trim()) {
      setFormError('Subject code, name, and department are required.')
      return
    }

    setIsSubmitting(true)
    try {
      const payload = {
        code: formData.code.trim().toUpperCase(),
        name: formData.name.trim(),
        department: formData.department.trim().toUpperCase(),
        semester: Number(formData.semester),
        curriculum_version: formData.curriculum_version.trim() || '2024-v1',
        academic_year: formData.academic_year.trim() || undefined,
        is_active: Boolean(formData.is_active)
      }

      await studyBuddyAPI.createSubject(payload)
      toast.success(`Subject ${payload.code} created successfully!`)
      setIsAddModalOpen(false)
      fetchSubjects()
    } catch (err) {
      console.error('Failed to create subject:', err)
      const detail = err.response?.data?.detail || 'Failed to create subject. Please check for conflicting codes.'
      setFormError(detail)
      toast.error(detail)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleUpdateSubject = async (e) => {
    e.preventDefault()
    if (!editingSubject) return
    setFormError('')

    setIsSubmitting(true)
    try {
      const payload = {
        code: formData.code.trim().toUpperCase(),
        name: formData.name.trim(),
        department: formData.department.trim().toUpperCase(),
        semester: Number(formData.semester),
        curriculum_version: formData.curriculum_version.trim() || '2024-v1',
        academic_year: formData.academic_year.trim() || undefined,
        is_active: Boolean(formData.is_active)
      }

      await studyBuddyAPI.updateSubject(editingSubject.id, payload)
      toast.success(`Subject ${payload.code} updated successfully!`)
      setEditingSubject(null)
      fetchSubjects()
    } catch (err) {
      console.error('Failed to update subject:', err)
      const detail = err.response?.data?.detail || 'Failed to update subject.'
      setFormError(detail)
      toast.error(detail)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleToggleStatus = async (subject) => {
    setIsSubmitting(true)
    try {
      const updatedStatus = !subject.is_active
      await studyBuddyAPI.updateSubject(subject.id, { is_active: updatedStatus })
      toast.success(`Subject ${subject.code} ${updatedStatus ? 'activated' : 'deactivated'}.`)
      setTogglingSubject(null)
      fetchSubjects()
    } catch (err) {
      console.error('Failed to toggle subject status:', err)
      toast.error(err.response?.data?.detail || 'Failed to update subject status.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDeleteSubject = async () => {
    if (!deletingSubject) return
    setIsSubmitting(true)
    try {
      await studyBuddyAPI.deleteSubject(deletingSubject.id)
      toast.success(`Subject ${deletingSubject.code} deleted successfully.`)
      setDeletingSubject(null)
      fetchSubjects()
    } catch (err) {
      console.error('Failed to delete subject:', err)
      toast.error(err.response?.data?.detail || 'Failed to delete subject.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="text-2xl">📚</span>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Academic Subject Catalogue</h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Manage institutional subjects, department and semester curricula, and Study Buddy activation
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            id="refresh-subjects-btn"
            onClick={fetchSubjects}
            disabled={isLoading}
            className="p-2.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 transition-colors cursor-pointer"
            title="Refresh subjects"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>

          <button
            id="add-subject-btn"
            onClick={handleOpenAddModal}
            className="flex items-center space-x-2 px-4 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium shadow-sm transition-colors cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Add Subject</span>
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
          <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 block uppercase tracking-wider">
            Total Subjects
          </span>
          <span className="text-2xl font-bold text-gray-900 dark:text-white mt-1 block">
            {stats.total}
          </span>
        </div>
        <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
          <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 block uppercase tracking-wider">
            Active
          </span>
          <span className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1 block">
            {stats.active}
          </span>
        </div>
        <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
          <span className="text-xs font-semibold text-amber-600 dark:text-amber-400 block uppercase tracking-wider">
            Inactive
          </span>
          <span className="text-2xl font-bold text-amber-600 dark:text-amber-400 mt-1 block">
            {stats.inactive}
          </span>
        </div>
        <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
          <span className="text-xs font-semibold text-blue-600 dark:text-blue-400 block uppercase tracking-wider">
            Total Course Notes
          </span>
          <span className="text-2xl font-bold text-blue-600 dark:text-blue-400 mt-1 block">
            {stats.totalNotes}
          </span>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="bg-white dark:bg-gray-900 p-4 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Search */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-3 text-gray-400" />
            <input
              id="search-subjects-input"
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by code, title, or department..."
              className="w-full pl-9 pr-4 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Department Filter */}
          <div className="flex items-center space-x-2">
            <label className="text-xs font-semibold text-gray-500 dark:text-gray-400 shrink-0">
              Department:
            </label>
            <select
              id="dept-filter"
              value={departmentFilter}
              onChange={(e) => setDepartmentFilter(e.target.value)}
              className="px-3 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
            >
              <option value="ALL">All Departments</option>
              {DEPARTMENTS.map((dept) => (
                <option key={dept} value={dept}>
                  {dept}
                </option>
              ))}
            </select>
          </div>

          {/* Semester Filter */}
          <div className="flex items-center space-x-2">
            <label className="text-xs font-semibold text-gray-500 dark:text-gray-400 shrink-0">
              Semester:
            </label>
            <select
              id="semester-filter"
              value={semesterFilter}
              onChange={(e) => setSemesterFilter(e.target.value)}
              className="px-3 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
            >
              <option value="ALL">All Semesters</option>
              {SEMESTERS.map((sem) => (
                <option key={sem} value={sem}>
                  Sem {sem}
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div className="flex items-center space-x-2">
            <label className="text-xs font-semibold text-gray-500 dark:text-gray-400 shrink-0">
              Status:
            </label>
            <select
              id="status-filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
            >
              <option value="ALL">All Status</option>
              <option value="ACTIVE">Active Only</option>
              <option value="INACTIVE">Inactive Only</option>
            </select>
          </div>
        </div>
      </div>

      {/* Subjects List */}
      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 bg-gray-100 dark:bg-gray-800 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : filteredSubjects.length === 0 ? (
        <div className="bg-white dark:bg-gray-900 rounded-xl p-12 text-center border border-gray-200 dark:border-gray-800">
          <BookOpen className="w-12 h-12 text-gray-400 mx-auto mb-3" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">No Subjects Found</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 max-w-md mx-auto">
            {subjects.length === 0
              ? 'The academic subject catalogue is currently fresh and empty. Click "Add Subject" to create institutional subjects.'
              : 'No subjects match the selected filters or search terms.'}
          </p>
          {subjects.length === 0 && (
            <button
              onClick={handleOpenAddModal}
              className="mt-4 inline-flex items-center space-x-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span>Add First Subject</span>
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredSubjects.map((sub) => (
            <div
              key={sub.id}
              className={`bg-white dark:bg-gray-900 rounded-xl p-5 border shadow-sm transition-all hover:shadow-md flex flex-col justify-between ${
                sub.is_active
                  ? 'border-gray-200 dark:border-gray-800'
                  : 'border-amber-200 dark:border-amber-900/50 bg-amber-50/20 dark:bg-amber-950/10'
              }`}
            >
              <div>
                {/* Header row: Code + Status Badge */}
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="font-mono text-sm font-bold px-2.5 py-1 rounded-md bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-900">
                    {sub.code}
                  </span>
                  {sub.is_active ? (
                    <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                      <CheckCircle className="w-3 h-3" />
                      <span>Active</span>
                    </span>
                  ) : (
                    <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                      <XCircle className="w-3 h-3" />
                      <span>Inactive</span>
                    </span>
                  )}
                </div>

                {/* Name */}
                <h3 className="text-base font-bold text-gray-900 dark:text-white line-clamp-2 mb-3">
                  {sub.name}
                </h3>

                {/* Badges / Metadata */}
                <div className="flex flex-wrap items-center gap-2 text-xs mb-4">
                  <span className="px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 font-medium">
                    Dept: {sub.department}
                  </span>
                  <span className="px-2 py-0.5 rounded bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 font-medium border border-purple-200 dark:border-purple-800">
                    Sem {sub.semester}
                  </span>
                  <span className="px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400">
                    v{sub.curriculum_version || '2024-v1'}
                  </span>
                  {sub.academic_year && (
                    <span className="px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400">
                      {sub.academic_year}
                    </span>
                  )}
                </div>

                {/* Lecture Notes Count */}
                <div className="text-xs text-gray-500 dark:text-gray-400 flex items-center space-x-1.5 pb-3 border-b border-gray-100 dark:border-gray-800">
                  <FileText className="w-3.5 h-3.5" />
                  <span>{sub.lecture_notes_count || 0} Lecture Notes attached</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between gap-2 pt-3 mt-2">
                <button
                  id={`edit-subject-${sub.id}`}
                  onClick={() => handleOpenEditModal(sub)}
                  className="flex items-center space-x-1 text-xs font-medium px-2.5 py-1.5 rounded-lg border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                >
                  <Edit2 className="w-3.5 h-3.5 text-blue-500" />
                  <span>Edit</span>
                </button>

                <div className="flex items-center space-x-2">
                  <button
                    id={`toggle-subject-${sub.id}`}
                    onClick={() => setTogglingSubject(sub)}
                    className={`flex items-center space-x-1 text-xs font-medium px-2.5 py-1.5 rounded-lg border transition-colors ${
                      sub.is_active
                        ? 'border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-300 hover:bg-amber-50 dark:hover:bg-amber-950/30'
                        : 'border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-950/30'
                    }`}
                  >
                    <Power className="w-3.5 h-3.5" />
                    <span>{sub.is_active ? 'Deactivate' : 'Activate'}</span>
                  </button>

                  <button
                    id={`delete-subject-${sub.id}`}
                    onClick={() => setDeletingSubject(sub)}
                    className="p-1.5 text-gray-400 hover:text-red-600 dark:hover:text-red-400 rounded-lg hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
                    title="Delete Subject"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* Modal: Add Subject */}
      {/* --------------------------------------------------------------------- */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 max-w-lg w-full shadow-2xl overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Plus className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                <h2 className="text-lg font-bold text-gray-900 dark:text-white">Create Academic Subject</h2>
              </div>
              <button
                onClick={() => !isSubmitting && setIsAddModalOpen(false)}
                disabled={isSubmitting}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateSubject} className="p-6 space-y-4">
              {formError && (
                <div className="bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 rounded-xl p-3 text-xs text-red-700 dark:text-red-300 flex items-start space-x-2">
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-red-500" />
                  <span>{formError}</span>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 mb-1">
                    Subject Code *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. AIML601"
                    value={formData.code}
                    onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                    className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 mb-1">
                    Department *
                  </label>
                  <select
                    value={formData.department}
                    onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                    className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                  >
                    {DEPARTMENTS.map((dept) => (
                      <option key={dept} value={dept}>
                        {dept}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 mb-1">
                  Subject Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Neural Networks & Deep Learning"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 mb-1">
                    Semester *
                  </label>
                  <select
                    value={formData.semester}
                    onChange={(e) => setFormData({ ...formData, semester: Number(e.target.value) })}
                    className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                  >
                    {SEMESTERS.map((sem) => (
                      <option key={sem} value={sem}>
                        Sem {sem}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 mb-1">
                    Curriculum
                  </label>
                  <input
                    type="text"
                    value={formData.curriculum_version}
                    onChange={(e) => setFormData({ ...formData, curriculum_version: e.target.value })}
                    className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 mb-1">
                    Academic Year
                  </label>
                  <input
                    type="text"
                    value={formData.academic_year}
                    onChange={(e) => setFormData({ ...formData, academic_year: e.target.value })}
                    className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div className="flex items-center space-x-2 pt-2">
                <input
                  id="add-is-active"
                  type="checkbox"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <label htmlFor="add-is-active" className="text-sm text-gray-700 dark:text-gray-300 font-medium">
                  Active in Study Buddy & Course Materials
                </label>
              </div>

              <div className="flex items-center justify-end space-x-3 pt-4 border-t border-gray-100 dark:border-gray-800">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  disabled={isSubmitting}
                  className="px-4 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="flex items-center space-x-2 px-5 py-2 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium shadow-sm disabled:opacity-50"
                >
                  {isSubmitting && <RefreshCw className="w-4 h-4 animate-spin" />}
                  <span>Create Subject</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* Modal: Edit Subject */}
      {/* --------------------------------------------------------------------- */}
      {editingSubject && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 max-w-lg w-full shadow-2xl overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Edit2 className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                <h2 className="text-lg font-bold text-gray-900 dark:text-white">Edit Subject: {editingSubject.code}</h2>
              </div>
              <button
                onClick={() => !isSubmitting && setEditingSubject(null)}
                disabled={isSubmitting}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleUpdateSubject} className="p-6 space-y-4">
              {formError && (
                <div className="bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 rounded-xl p-3 text-xs text-red-700 dark:text-red-300 flex items-start space-x-2">
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-red-500" />
                  <span>{formError}</span>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 mb-1">
                    Subject Code *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.code}
                    onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                    className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 mb-1">
                    Department *
                  </label>
                  <select
                    value={formData.department}
                    onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                    className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                  >
                    {DEPARTMENTS.map((dept) => (
                      <option key={dept} value={dept}>
                        {dept}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 mb-1">
                  Subject Name *
                </label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 mb-1">
                    Semester *
                  </label>
                  <select
                    value={formData.semester}
                    onChange={(e) => setFormData({ ...formData, semester: Number(e.target.value) })}
                    className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                  >
                    {SEMESTERS.map((sem) => (
                      <option key={sem} value={sem}>
                        Sem {sem}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 mb-1">
                    Curriculum
                  </label>
                  <input
                    type="text"
                    value={formData.curriculum_version}
                    onChange={(e) => setFormData({ ...formData, curriculum_version: e.target.value })}
                    className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300 mb-1">
                    Academic Year
                  </label>
                  <input
                    type="text"
                    value={formData.academic_year}
                    onChange={(e) => setFormData({ ...formData, academic_year: e.target.value })}
                    className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div className="flex items-center space-x-2 pt-2">
                <input
                  id="edit-is-active"
                  type="checkbox"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <label htmlFor="edit-is-active" className="text-sm text-gray-700 dark:text-gray-300 font-medium">
                  Active in Study Buddy & Course Materials
                </label>
              </div>

              <div className="flex items-center justify-end space-x-3 pt-4 border-t border-gray-100 dark:border-gray-800">
                <button
                  type="button"
                  onClick={() => setEditingSubject(null)}
                  disabled={isSubmitting}
                  className="px-4 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="flex items-center space-x-2 px-5 py-2 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium shadow-sm disabled:opacity-50"
                >
                  {isSubmitting && <RefreshCw className="w-4 h-4 animate-spin" />}
                  <span>Save Changes</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* Modal: Confirm Status Toggle */}
      {/* --------------------------------------------------------------------- */}
      {togglingSubject && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 max-w-md w-full shadow-2xl p-6 space-y-4">
            <div className="flex items-center space-x-3">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                togglingSubject.is_active ? 'bg-amber-100 text-amber-600 dark:bg-amber-950/50 dark:text-amber-400' : 'bg-emerald-100 text-emerald-600 dark:bg-emerald-950/50 dark:text-emerald-400'
              }`}>
                <Power className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-gray-900 dark:text-white">
                  {togglingSubject.is_active ? 'Deactivate Subject' : 'Activate Subject'}
                </h3>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {togglingSubject.code} — {togglingSubject.name}
                </p>
              </div>
            </div>

            <p className="text-sm text-gray-600 dark:text-gray-300">
              {togglingSubject.is_active
                ? 'Deactivating this subject will hide it from lecturer uploads and student Study Buddy queries. Its indexed chunks in Qdrant will be deactivated safely.'
                : 'Activating this subject will restore it for lecturer uploads and student Study Buddy retrieval.'}
            </p>

            <div className="flex items-center justify-end space-x-3 pt-3 border-t border-gray-100 dark:border-gray-800">
              <button
                type="button"
                onClick={() => setTogglingSubject(null)}
                disabled={isSubmitting}
                className="px-4 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => handleToggleStatus(togglingSubject)}
                disabled={isSubmitting}
                className={`flex items-center space-x-2 px-4 py-2 text-sm rounded-lg font-medium text-white shadow-sm disabled:opacity-50 ${
                  togglingSubject.is_active ? 'bg-amber-600 hover:bg-amber-700' : 'bg-emerald-600 hover:bg-emerald-700'
                }`}
              >
                {isSubmitting && <RefreshCw className="w-4 h-4 animate-spin" />}
                <span>{togglingSubject.is_active ? 'Deactivate' : 'Activate'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* Modal: Confirm Delete */}
      {/* --------------------------------------------------------------------- */}
      {deletingSubject && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 max-w-md w-full shadow-2xl p-6 space-y-4">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-full bg-red-100 text-red-600 dark:bg-red-950/50 dark:text-red-400 flex items-center justify-center">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-gray-900 dark:text-white">Delete Subject</h3>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {deletingSubject.code} — {deletingSubject.name}
                </p>
              </div>
            </div>

            <div className="space-y-2 text-xs text-gray-600 dark:text-gray-300">
              <p>
                Are you sure you want to permanently delete this subject?
              </p>
              <ul className="list-disc list-inside space-y-1 text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-800/60 p-3 rounded-lg">
                <li>Associated syllabus documents and lecture notes will be removed.</li>
                <li>Indexed semantic vectors in Qdrant will be cleaned up.</li>
                <li>Stored note files in MinIO storage will be removed.</li>
                <li>Private student uploads will be preserved and unlinked.</li>
              </ul>
            </div>

            <div className="flex items-center justify-end space-x-3 pt-3 border-t border-gray-100 dark:border-gray-800">
              <button
                type="button"
                onClick={() => setDeletingSubject(null)}
                disabled={isSubmitting}
                className="px-4 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteSubject}
                disabled={isSubmitting}
                className="flex items-center space-x-2 px-4 py-2 text-sm rounded-lg bg-red-600 hover:bg-red-700 text-white font-medium shadow-sm disabled:opacity-50"
              >
                {isSubmitting && <RefreshCw className="w-4 h-4 animate-spin" />}
                <span>Delete Permanently</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
