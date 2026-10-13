import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import Login from './pages/Login'
import Register from './pages/Register'
import Landing from './pages/Landing'
import Unauthorized from './pages/Unauthorized'
import StudentDashboard from './pages/student/Dashboard'
import LecturerDashboard from './pages/lecturer/Dashboard'
import HODDashboard from './pages/hod/Dashboard'
import AdminDashboard from './pages/admin/Dashboard'
import AdminUsers from './pages/admin/Users'
import AdminAuditLogs from './pages/admin/AuditLogs'
import StudentChat from './pages/student/Chat'
import StudentStudyBuddy from './pages/student/StudyBuddy'
import LecturerChat from './pages/lecturer/Chat'
import StudentCirculars from './pages/student/Circulars'
import LecturerCirculars from './pages/lecturer/Circulars'
import HODCirculars from './pages/hod/Circulars'
import StudentProfile from './pages/student/Profile'
import StudentJobs from './pages/student/Jobs'
import StudentJobDetails from './pages/student/JobDetails'
import StudentApplications from './pages/student/Applications'
import ReminderList from './pages/reminders/ReminderList'
import HODExamDuties from './pages/hod/ExamDuties'
import LecturerExamDuties from './pages/lecturer/ExamDuties'
import HODChat from './pages/hod/Chat'
import PlacementChat from './pages/placement/Chat'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import { Toaster } from 'react-hot-toast'

// File Management Imports
import FileManager from './pages/FileManager'
import FileUpload from './components/FileUpload'
import FileSearch from './components/FileSearch'
import FileDetail from './pages/FileDetail'

// Placement Imports
import PlacementDashboard from './pages/placement/Dashboard'
import Companies from './pages/placement/Companies'
import CompanyForm from './pages/placement/CompanyForm'
import Jobs from './pages/placement/Jobs'
import JobForm from './pages/placement/JobForm'
import JobDetails from './pages/placement/JobDetails'
import Students from './pages/placement/Students'
import PlacementStudentProfile from './pages/placement/StudentProfile'
import Shortlist from './pages/placement/Shortlist'
import Reports from './pages/placement/Reports'
import Circulars from './pages/placement/Circulars'
import CircularForm from './pages/placement/CircularForm'
import CircularDetails from './pages/placement/CircularDetails'
import StudentRecruitmentCircularDetails from './pages/student/RecruitmentCircularDetails'
import Results from './pages/placement/Results'
import ResultBatchDetails from './pages/placement/ResultBatchDetails'
import ManageTestData from './pages/placement/ManageTestData'

// Resume Analyzer Import
import ResumeAnalyzer from './pages/placement/ResumeAnalyzer'

function App() {
  const { token, user } = useAuthStore()

  // Helper to get dashboard path based on role
  const getDashboardPath = () => {
    if (!user?.role) return '/login'
    const role = String(user.role).toLowerCase()
    const roleMap = {
      student: '/student/dashboard',
      lecturer: '/lecturer/dashboard',
      hod: '/hod/dashboard',
      admin: '/admin/dashboard',
      placement_officer: '/placement/dashboard',
    }
    return roleMap[role] || '/student/dashboard'
  }

  const isLoggedIn = !!token && !!user

  return (
    <Router>
      <Toaster position="top-right" />
      <Routes>
        <Route path="/" element={
          isLoggedIn ? <Navigate to={getDashboardPath()} replace /> : <Landing />
        } />
        
        <Route path="/login" element={
          isLoggedIn ? <Navigate to={getDashboardPath()} replace /> : <Login />
        } />
        
        <Route path="/register" element={<Register />} />
        
        <Route path="/unauthorized" element={<Unauthorized />} />

        {/* Authenticated Root */}
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            
            {/* Student Chat (student only) */}
            <Route element={<ProtectedRoute allowedRoles={['student']} />}>
              <Route path="/student/chat" element={<StudentChat />} />
            </Route>

            {/* Student Routes (student, admin) */}
            <Route element={<ProtectedRoute allowedRoles={['student', 'admin']} />}>
              <Route path="/student/dashboard" element={<StudentDashboard />} />
              <Route path="/student/jobs" element={<StudentJobs />} />
              <Route path="/student/jobs/circulars/:id" element={<StudentRecruitmentCircularDetails />} />
              <Route path="/student/jobs/:id" element={<StudentJobDetails />} />
              <Route path="/student/applications" element={<StudentApplications />} />
              <Route path="/student/circulars" element={<StudentCirculars />} />
              <Route path="/student/profile" element={<StudentProfile />} />
              <Route path="/student/study-buddy" element={<StudentStudyBuddy />} />
              <Route path="/student/reminders" element={<ReminderList />} />
            </Route>

            {/* Lecturer Chat (lecturer only) */}
            <Route element={<ProtectedRoute allowedRoles={['lecturer']} />}>
              <Route path="/lecturer/chat" element={<LecturerChat />} />
            </Route>

            {/* Lecturer Routes (lecturer, admin) */}
            <Route element={<ProtectedRoute allowedRoles={['lecturer', 'admin']} />}>
              <Route path="/lecturer/dashboard" element={<LecturerDashboard />} />
              <Route path="/lecturer/circulars" element={<LecturerCirculars />} />
              <Route path="/lecturer/exam-duties" element={<LecturerExamDuties />} />
            </Route>

            {/* HOD Chat (hod only) */}
            <Route element={<ProtectedRoute allowedRoles={['hod']} />}>
              <Route path="/hod/chat" element={<HODChat />} />
            </Route>

            {/* HOD Routes (hod, admin) */}
            <Route element={<ProtectedRoute allowedRoles={['hod', 'admin']} />}>
              <Route path="/hod/dashboard" element={<HODDashboard />} />
              <Route path="/hod/exam-duties" element={<HODExamDuties />} />
              <Route path="/hod/circulars" element={<HODCirculars />} />
            </Route>

            {/* Admin Routes (admin only) */}
            <Route element={<ProtectedRoute allowedRoles={['admin']} />}>
              <Route path="/admin/dashboard" element={<AdminDashboard />} />
              <Route path="/admin/users" element={<AdminUsers />} />
              <Route path="/admin/logs" element={<AdminAuditLogs />} />
            </Route>

            {/* File Management Routes (all authenticated roles) */}
            <Route element={<ProtectedRoute allowedRoles={['admin', 'hod', 'lecturer', 'student', 'placement_officer']} />}>
              <Route path="/files/*" element={<FileManager />} />
              <Route path="/files/upload" element={<FileUpload />} />
              <Route path="/files/search" element={<FileSearch />} />
              <Route path="/files/:fileId" element={<FileDetail />} />
            </Route>

            {/* Placement Officer Chat (placement_officer only) */}
            <Route element={<ProtectedRoute allowedRoles={['placement_officer']} />}>
              <Route path="/placement/chat" element={<PlacementChat />} />
            </Route>

            {/* Placement Administration Routes (placement_officer, admin) */}
            <Route element={<ProtectedRoute allowedRoles={['placement_officer', 'admin']} />}>
              <Route path="/placement/dashboard" element={<PlacementDashboard />} />
              <Route path="/placement/companies" element={<Companies />} />
              <Route path="/placement/companies/add" element={<CompanyForm />} />
              <Route path="/placement/companies/:id" element={<CompanyForm />} />
              <Route path="/placement/companies/:id/edit" element={<CompanyForm />} />
              <Route path="/placement/jobs" element={<Jobs />} />
              <Route path="/placement/jobs/post" element={<JobForm />} />
              <Route path="/placement/jobs/:id" element={<JobDetails />} />
              <Route path="/placement/jobs/:id/edit" element={<JobForm />} />
              <Route path="/placement/circulars" element={<Circulars />} />
              <Route path="/placement/circulars/new" element={<CircularForm />} />
              <Route path="/placement/circulars/:id" element={<CircularDetails />} />
              <Route path="/placement/circulars/:id/edit" element={<CircularForm />} />
              <Route path="/placement/results" element={<Results />} />
              <Route path="/placement/results/:batchId" element={<ResultBatchDetails />} />
              <Route path="/placement/students" element={<Students />} />
              <Route path="/placement/students/:id" element={<PlacementStudentProfile />} />
              <Route path="/placement/shortlist" element={<Shortlist />} />
              <Route path="/placement/reports" element={<Reports />} />
              <Route path="/placement/manage-test-data" element={<ManageTestData />} />
              <Route path="/placement/files" element={<Navigate to="/files" replace />} />
            </Route>

            {/* Resume Analyzer Route (students, placement officers, admins) */}
            <Route element={<ProtectedRoute allowedRoles={['student', 'placement_officer', 'admin']} />}>
              <Route path="/placement/resume-analyzer" element={<ResumeAnalyzer />} />
            </Route>

          </Route>
        </Route>
        
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  )
}

export default App