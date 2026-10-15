import React, { useEffect, useState, useMemo } from 'react'
import {
  BookOpen,
  Plus,
  Search,
  Filter,
  Edit,
  Trash2,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertTriangle,
  X,
  Layers,
  GraduationCap,
  Building,
  Calendar
} from 'lucide-react'
import { studyBuddyAPI } from '../../services/api'
import { useAuthStore } from '../../store/authStore'
import toast from 'react-hot-toast'

const DEPARTMENTS = ['CSE', 'AIML', 'ISE', 'ECE', 'MECH', 'CIVIL', 'EEE']
const SEMESTERS = [1, 2, 3, 4, 5, 6, 7, 8]

export default function AdminSubjects() {
  const { user } = useAuthStore()

  // Data state
  const [subjects, setSubjects] = useState([])
  const [loading, setLoading] = useState(false)

  // Filters
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedDept, setSelectedDept] = useState('')
  const [selectedSemester, setSelectedSemester] = useState('')
  const [selectedStatus, setSelectedStatus] = useState('')

  // Modals state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [editingSubject, setEditingSubject] = useState(null)
  const [deletingSubject, setDeletingSubject] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Form states
  const [formCode, setFormCode] = useState('')
  const [formName, setFormName] = useState('')
  const [formDept, setFormDept] = useState('CSE')
  const [formSemester, setFormSemester] = useState('1')
  const [formAcademicYear, setFormAcademicYear] = useState('2025-2026')
  const [formCurriculum, setFormCurriculum] = useState('R2021')
  const [formDescription, setFormDescription] = useState('')
  const [formIsActive, setFormIsActive] = useState(true)
  const [formError, setFormError] = useState('')

  useEffect(() => {
    fetchSubjects()
  }, [])

  const fetchSubjects = async () => {
    setLoading(true)
    try {
      // Admin lists all subjects (both active and inactive)
      const res = await studyBuddyAPI.getSubjects()
      setSubjects(res.data || [])
    } catch (err) {
      console.error('Failed to load subjects:', err)
      toast.error('Failed to load academic subjects.')
    } finally {
      setLoading(false)
    }
  }

  // Filtered subjects
  const filteredSubjects = useMemo(() => {
    return subjects.filter((sub) => {
      if (selectedDept && sub.department.toLowerCase() !== selectedDept.toLowerCase()) {
        return false
      }
      if (selectedSemester && String(sub.semester) !== String(selectedSemester)) {
        return false
      }
      if (selectedStatus !== '') {
        const isActiveFilter = selectedStatus === 'active'
        if (sub.is_active !== isActiveFilter) return false
      }
      if (searchTerm.trim()) {
        const q = searchTerm.toLowerCase().trim()
        const matchCode = (sub.code || '').toLowerCase().includes(q)
        const matchName = (sub.name || '').toLowerCase().includes(q)
        const matchDept = (sub.department || '').toLowerCase().includes(q)
        if (!matchCode && !matchName && !matchDept) return false
      }
      return true
    })
  }, [subjects, selectedDept, selectedSemester, selectedStatus, searchTerm])

  // Open Create Modal
  const handleOpenCreate = () => {
    setFormCode('')
    setFormName('')
    setFormDept('CSE')
    setFormSemester('1')
    setFormAcademicYear('2025-2026')
    setFormCurriculum('R2021')
    setFormDescription('')
    setFormIsActive(true)
    setFormError('')
    setIsCreateModalOpen(true)
  }

  // Open Edit Modal
  const handleOpenEdit = (subject) => {
    setEditingSubject(subject)
    setFormCode(subject.code || '')
    setFormName(subject.name || '')
    setFormDept(subject.department || 'CSE')
    setFormSemester(subject.semester ? String(subject.semester) : '1')
    setFormAcademicYear(subject.academic_year || '')
    setFormCurriculum(subject.curriculum_version || '')
    setFormDescription(subject.description || '')
    setFormIsActive(subject.is_active)
    setFormError('')
  }

  // Submit Create Subject
  const handleCreateSubmit = async (e) => {
    e.preventDefault()
    setFormError('')
    if (!formCode.trim()) {
      setFormError('Subject code is required.')
      return
    }
    if (!formName.trim()) {
      setFormError('Subject name is required.')
      return
    }
    if (!formDept.trim()) {
      setFormError('Department is required.')
      return
    }

    setIsSubmitting(true)
    try {
      const payload = {
        code: formCode.trim().toUpperCase(),
        name: formName.trim(),
        department: formDept.trim(),
        semester: formSemester ? parseInt(formSemester, 10) : null,
        academic_year: formAcademicYear.trim() || null,
        curriculum_version: formCurriculum.trim() || null,
        description: formDescription.trim() || null
      }
      await studyBuddyAPI.createSubject(payload)
      toast.success(`Subject ${payload.code} created successfully.`)
      setIsCreateModalOpen(false)
      fetchSubjects()
    } catch (err) {
      console.error('Failed to create subject:', err)
      const detail = err.response?.data?.detail || 'Failed to create subject.'
      setFormError(detail)
      toast.error(detail)
    } finally {
      setIsSubmitting(false)
    }
  }

  // Submit Edit Subject
  const handleEditSubmit = async (e) => {
    e.preventDefault()
    if (!editingSubject) return
    setFormError('')

    if (!formCode.trim()) {
      setFormError('Subject code is required.')
      return
    }
    if (!formName.trim()) {
      setFormError('Subject name is required.')
      return
    }

    setIsSubmitting(true)
    try {
      const payload = {
        code: formCode.trim().toUpperCase(),
        name: formName.trim(),
        department: formDept.trim(),
        semester: formSemester ? parseInt(formSemester, 10) : null,
        academic_year: formAcademicYear.trim() || null,
        curriculum_version: formCurriculum.trim() || null,
        description: formDescription.trim() || null,
        is_active: formIsActive
      }
      await studyBuddyAPI.updateSubject(editingSubject.id, payload)
      toast.success(`Subject ${payload.code} updated successfully.`)
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

  // Toggle Active/Inactive directly
  const handleToggleActive = async (subject) => {
    const newStatus = !subject.is_active
    try {
      await studyBuddyAPI.updateSubject(subject.id, { is_active: newStatus })
      toast.success(`Subject ${subject.code} ${newStatus ? 'activated' : 'deactivated'}.`)
      setSubjects((prev) =>
        prev.map((s) => (s.id === subject.id ? { ...s, is_active: newStatus } : s))
      )
    } catch (err) {
      console.error('Failed to update subject status:', err)
      toast.error('Failed to update subject status.')
    }
  }

  // Delete Subject
  const handleDeleteConfirm = async () => {
    if (!deletingSubject) return
    setIsSubmitting(true)
    try {
      await studyBuddyAPI.deleteSubject(deletingSubject.id)
      toast.success(`Subject ${deletingSubject.code} deleted successfully.`)
      setSubjects((prev) => prev.filter((s) => s.id !== deletingSubject.id))
      setDeletingSubject(null)
    } catch (err) {
      console.error('Failed to delete subject:', err)
      toast.error(err.response?.data?.detail || 'Failed to delete subject.')
    } finally {
      setIsSubmitting(false)
    }
  }

  // Statistics
  const stats = useMemo(() => {
    const total = subjects.length
    const active = subjects.filter((s) => s.is_active).length
    const inactive = total - active
    const depts = new Set(subjects.map((s) => s.department)).size
    return { total, active, inactive, depts }
  }, [subjects])

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="text-2xl">📚</span>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Academic Subjects</h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Manage institutional subject catalogue, department allocations, and semester mappings
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={fetchSubjects}
            disabled={loading}
            className="p-2.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 transition-colors cursor-pointer"
            title="Refresh subjects"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>

          <button
            id="create-subject-btn"
            onClick={handleOpenCreate}
            className="flex items-center space-x-2 px-4 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium shadow-sm transition-colors cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Create Subject</span>
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-gray-900 rounded-xl p-4 border border-gray-200 dark:border-gray-800 shadow-sm">
          <span className="text-xs text-gray-500 dark:text-gray-400 block">Total Subjects</span>
          <span className="text-2xl font-bold text-gray-900 dark:text-white">{stats.total}</span>
        </div>
        <div className="bg-white dark:bg-gray-900 rounded-xl p-4 border border-gray-200 dark:border-gray-800 shadow-sm">
          <span className="text-xs text-emerald-600 dark:text-emerald-400 block">Active Subjects</span>
          <span className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{stats.active}</span>
        </div>
        <div className="bg-white dark:bg-gray-900 rounded-xl p-4 border border-gray-200 dark:border-gray-800 shadow-sm">
          <span className="text-xs text-amber-600 dark:text-amber-400 block">Inactive Subjects</span>
          <span className="text-2xl font-bold text-amber-600 dark:text-amber-400">{stats.inactive}</span>
        </div>
        <div className="bg-white dark:bg-gray-900 rounded-xl p-4 border border-gray-200 dark:border-gray-800 shadow-sm">
          <span className="text-xs text-purple-600 dark:text-purple-400 block">Departments</span>
          <span className="text-2xl font-bold text-purple-600 dark:text-purple-400">{stats.depts}</span>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-white dark:bg-gray-900 rounded-xl p-4 border border-gray-200 dark:border-gray-800 shadow-sm flex flex-col md:flex-row items-center justify-between gap-3">
        <div className="relative w-full md:w-72">
          <Search className="w-4 h-4 absolute left-3 top-3 text-gray-400" />
          <input
            type="text"
            placeholder="Search by code, name, dept..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2.5 w-full md:w-auto">
          {/* Department Filter */}
          <select
            value={selectedDept}
            onChange={(e) => setSelectedDept(e.target.value)}
            className="px-3 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Departments</option>
            {DEPARTMENTS.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>

          {/* Semester Filter */}
          <select
            value={selectedSemester}
            onChange={(e) => setSelectedSemester(e.target.value)}
            className="px-3 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Semesters</option>
            {SEMESTERS.map((s) => (
              <option key={s} value={s}>
                Semester {s}
              </option>
            ))}
          </select>

          {/* Status Filter */}
          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="px-3 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Statuses</option>
            <option value="active">Active Only</option>
            <option value="inactive">Inactive Only</option>
          </select>
        </div>
      </div>

      {/* Subjects Table */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center">
            <RefreshCw className="w-8 h-8 animate-spin text-blue-500 mx-auto mb-3" />
            <p className="text-sm text-gray-500 dark:text-gray-400">Loading academic subjects...</p>
          </div>
        ) : filteredSubjects.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-12 h-12 bg-blue-50 dark:bg-blue-950/40 rounded-full flex items-center justify-center mx-auto mb-3 text-blue-600 dark:text-blue-400">
              <BookOpen className="w-6 h-6" />
            </div>
            <h3 className="text-base font-semibold text-gray-900 dark:text-white">
              {subjects.length === 0 ? 'No academic subjects in catalogue' : 'No matching subjects'}
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 max-w-md mx-auto">
              {subjects.length === 0
                ? 'The catalogue is currently clean. Create academic subjects to enable Course Materials upload and Study Buddy assistance.'
                : 'Try adjusting your search criteria or filters.'}
            </p>
            {subjects.length === 0 && (
              <button
                onClick={handleOpenCreate}
                className="mt-4 inline-flex items-center space-x-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium text-sm transition-colors cursor-pointer"
              >
                <Plus className="w-4 h-4" />
                <span>Create First Subject</span>
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-700 dark:text-gray-300">
              <thead className="bg-gray-50 dark:bg-gray-800/60 text-xs font-semibold uppercase text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-800">
                <tr>
                  <th className="px-5 py-3.5">Code & Name</th>
                  <th className="px-5 py-3.5">Department</th>
                  <th className="px-5 py-3.5">Semester</th>
                  <th className="px-5 py-3.5">Curriculum / Year</th>
                  <th className="px-5 py-3.5">Status</th>
                  <th className="px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {filteredSubjects.map((sub) => (
                  <tr
                    key={sub.id}
                    className="hover:bg-gray-50/60 dark:hover:bg-gray-800/40 transition-colors"
                  >
                    <td className="px-5 py-4">
                      <div className="font-semibold text-gray-900 dark:text-white flex items-center space-x-2">
                        <span className="font-mono text-blue-600 dark:text-blue-400">{sub.code}</span>
                        <span>•</span>
                        <span>{sub.name}</span>
                      </div>
                      {sub.description && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-1">
                          {sub.description}
                        </p>
                      )}
                    </td>
                    <td className="px-5 py-4">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                        {sub.department}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-50 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
                        Semester {sub.semester ?? '—'}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-xs text-gray-500 dark:text-gray-400">
                      <div>{sub.curriculum_version || '—'}</div>
                      <div className="text-[11px] text-gray-400">{sub.academic_year || ''}</div>
                    </td>
                    <td className="px-5 py-4">
                      <button
                        onClick={() => handleToggleActive(sub)}
                        className={`inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-colors cursor-pointer ${
                          sub.is_active
                            ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 hover:bg-emerald-100'
                            : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
                        }`}
                        title="Click to toggle activation"
                      >
                        {sub.is_active ? (
                          <>
                            <CheckCircle className="w-3 h-3 text-emerald-500" />
                            <span>Active</span>
                          </>
                        ) : (
                          <>
                            <XCircle className="w-3 h-3 text-gray-400" />
                            <span>Inactive</span>
                          </>
                        )}
                      </button>
                    </td>
                    <td className="px-5 py-4 text-right space-x-2">
                      <button
                        onClick={() => handleOpenEdit(sub)}
                        className="p-1.5 rounded-lg text-gray-500 dark:text-gray-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-950/40 transition-colors cursor-pointer"
                        title="Edit Subject"
                      >
                        <Edit className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => setDeletingSubject(sub)}
                        className="p-1.5 rounded-lg text-gray-500 dark:text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40 transition-colors cursor-pointer"
                        title="Delete Subject"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* CREATE MODAL */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-lg w-full border border-gray-200 dark:border-gray-800 shadow-xl overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-800">
              <h3 className="text-lg font-bold text-gray-900 dark:text-white flex items-center space-x-2">
                <BookOpen className="w-5 h-5 text-blue-600" />
                <span>Create Academic Subject</span>
              </h3>
              <button
                onClick={() => setIsCreateModalOpen(false)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="p-6 space-y-4">
              {formError && (
                <div className="bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 rounded-lg p-3 text-xs text-red-700 dark:text-red-300 flex items-center space-x-2">
                  <AlertTriangle className="w-4 h-4 text-red-500 shrink-0" />
                  <span>{formError}</span>
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold uppercase text-gray-600 dark:text-gray-300 mb-1">
                    Subject Code *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. CS601"
                    value={formCode}
                    onChange={(e) => setFormCode(e.target.value.toUpperCase())}
                    className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase text-gray-600 dark:text-gray-300 mb-1">
                    Department *
                  </label>
                  <select
                    value={formDept}
                    onChange={(e) => setFormDept(e.target.value)}
                    className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 font-medium"
                  >
                    {DEPARTMENTS.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase text-gray-600 dark:text-gray-300 mb-1">
                  Subject Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Compiler Design"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 font-medium"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold uppercase text-gray-600 dark:text-gray-300 mb-1">
                    Semester *
                  </label>
                  <select
                    value={formSemester}
                    onChange={(e) => setFormSemester(e.target.value)}
                    className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                  >
                    {SEMESTERS.map((s) => (
                      <option key={s} value={s}>
                        Sem {s}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase text-gray-600 dark:text-gray-300 mb-1">
                    Academic Year
                  </label>
                  <input
                    type="text"
                    placeholder="2025-2026"
                    value={formAcademicYear}
                    onChange={(e) => setFormAcademicYear(e.target.value)}
                    className="w-full px-3 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase text-gray-600 dark:text-gray-300 mb-1">
                    Curriculum
                  </label>
                  <input
                    type="text"
                    placeholder="R2021"
                    value={formCurriculum}
                    onChange={(e) => setFormCurriculum(e.target.value)}
                    className="w-full px-3 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase text-gray-600 dark:text-gray-300 mb-1">
                  Description / Objectives
                </label>
                <textarea
                  rows={3}
                  placeholder="Optional brief description of the course..."
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="flex items-center justify-end space-x-3 pt-4 border-t border-gray-200 dark:border-gray-800">
                <button
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-700 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold shadow-sm transition-colors cursor-pointer disabled:opacity-50 flex items-center space-x-2"
                >
                  {isSubmitting ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Creating...</span>
                    </>
                  ) : (
                    <span>Create Subject</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* EDIT MODAL */}
      {editingSubject && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-lg w-full border border-gray-200 dark:border-gray-800 shadow-xl overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-800">
              <h3 className="text-lg font-bold text-gray-900 dark:text-white flex items-center space-x-2">
                <Edit className="w-5 h-5 text-blue-600" />
                <span>Edit Subject ({editingSubject.code})</span>
              </h3>
              <button
                onClick={() => setEditingSubject(null)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleEditSubmit} className="p-6 space-y-4">
              {formError && (
                <div className="bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 rounded-lg p-3 text-xs text-red-700 dark:text-red-300 flex items-center space-x-2">
                  <AlertTriangle className="w-4 h-4 text-red-500 shrink-0" />
                  <span>{formError}</span>
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold uppercase text-gray-600 dark:text-gray-300 mb-1">
                    Subject Code *
                  </label>
                  <input
                    type="text"
                    required
                    value={formCode}
                    onChange={(e) => setFormCode(e.target.value.toUpperCase())}
                    className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase text-gray-600 dark:text-gray-300 mb-1">
                    Department *
                  </label>
                  <select
                    value={formDept}
                    onChange={(e) => setFormDept(e.target.value)}
                    className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 font-medium"
                  >
                    {DEPARTMENTS.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase text-gray-600 dark:text-gray-300 mb-1">
                  Subject Name *
                </label>
                <input
                  type="text"
                  required
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 font-medium"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold uppercase text-gray-600 dark:text-gray-300 mb-1">
                    Semester *
                  </label>
                  <select
                    value={formSemester}
                    onChange={(e) => setFormSemester(e.target.value)}
                    className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                  >
                    {SEMESTERS.map((s) => (
                      <option key={s} value={s}>
                        Sem {s}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase text-gray-600 dark:text-gray-300 mb-1">
                    Academic Year
                  </label>
                  <input
                    type="text"
                    value={formAcademicYear}
                    onChange={(e) => setFormAcademicYear(e.target.value)}
                    className="w-full px-3 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase text-gray-600 dark:text-gray-300 mb-1">
                    Curriculum
                  </label>
                  <input
                    type="text"
                    value={formCurriculum}
                    onChange={(e) => setFormCurriculum(e.target.value)}
                    className="w-full px-3 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase text-gray-600 dark:text-gray-300 mb-1">
                  Description
                </label>
                <textarea
                  rows={3}
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  className="w-full px-3.5 py-2 text-sm rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="flex items-center space-x-2 pt-1">
                <input
                  type="checkbox"
                  id="edit-is-active"
                  checked={formIsActive}
                  onChange={(e) => setFormIsActive(e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 w-4 h-4"
                />
                <label
                  htmlFor="edit-is-active"
                  className="text-sm font-medium text-gray-700 dark:text-gray-300 cursor-pointer"
                >
                  Active in Curriculum Catalogue (visible to faculty and eligible students)
                </label>
              </div>

              <div className="flex items-center justify-end space-x-3 pt-4 border-t border-gray-200 dark:border-gray-800">
                <button
                  type="button"
                  onClick={() => setEditingSubject(null)}
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-700 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold shadow-sm transition-colors cursor-pointer disabled:opacity-50 flex items-center space-x-2"
                >
                  {isSubmitting ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <span>Save Changes</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DELETE CONFIRMATION MODAL */}
      {deletingSubject && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-md w-full border border-gray-200 dark:border-gray-800 shadow-xl p-6 space-y-4">
            <div className="flex items-center space-x-3 text-red-600 dark:text-red-400">
              <div className="p-3 bg-red-50 dark:bg-red-950/40 rounded-full">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold text-gray-900 dark:text-white">Delete Subject</h3>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-300">
              Are you sure you want to delete <span className="font-semibold text-gray-900 dark:text-white">{deletingSubject.code} — {deletingSubject.name}</span>?
            </p>
            <p className="text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 p-3 rounded-lg border border-amber-200 dark:border-amber-900">
              This action will permanently delete the subject record and purge any associated vector indexing chunks and storage files.
            </p>
            <div className="flex items-center justify-end space-x-3 pt-2">
              <button
                type="button"
                onClick={() => setDeletingSubject(null)}
                disabled={isSubmitting}
                className="px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-700 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteConfirm}
                disabled={isSubmitting}
                className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm font-semibold shadow-sm transition-colors cursor-pointer disabled:opacity-50 flex items-center space-x-2"
              >
                {isSubmitting ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Deleting...</span>
                  </>
                ) : (
                  <span>Delete Subject</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
