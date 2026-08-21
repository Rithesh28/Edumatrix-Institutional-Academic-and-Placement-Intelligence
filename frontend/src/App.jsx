import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import Login from './pages/Login'
import Register from './pages/Register'
import Landing from './pages/Landing'
import StudentDashboard from './pages/student/Dashboard'
import LecturerDashboard from './pages/lecturer/Dashboard'
import HODDashboard from './pages/hod/Dashboard'
import AdminDashboard from './pages/admin/Dashboard'
import StudentChat from './pages/student/Chat'
import LecturerChat from './pages/lecturer/Chat'
import StudentCirculars from './pages/student/Circulars'
import LecturerCirculars from './pages/lecturer/Circulars'
import HODCirculars from './pages/hod/Circulars'
import StudentProfile from './pages/student/Profile'
import ReminderList from './pages/reminders/ReminderList'
import HODExamDuties from './pages/hod/ExamDuties'
import LecturerExamDuties from './pages/lecturer/ExamDuties'
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

// 🔥 NEW: Resume Analyzer Import
import ResumeAnalyzer from './pages/placement/ResumeAnalyzer'

function App() {
  const { token, user } = useAuthStore()

  // Helper to get dashboard path
  const getDashboardPath = () => {
    if (!user?.role) return '/login'
    const role = String(user.role).toLowerCase()
    const roleMap = {
      'student': '/student/dashboard',
      'lecturer': '/lecturer/dashboard',
      'hod': '/hod/dashboard',
      'admin': '/admin/dashboard',
      'placement_officer': '/placement/dashboard'
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
        
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            {/* Student Routes */}
            <Route path="/student/dashboard" element={<StudentDashboard />} />
            <Route path="/student/chat" element={<StudentChat />} />
            <Route path="/student/circulars" element={<StudentCirculars />} />
            <Route path="/student/profile" element={<StudentProfile />} />
            <Route path="/student/reminders" element={<ReminderList />} />
            
            {/* Lecturer Routes */}
            <Route path="/lecturer/dashboard" element={<LecturerDashboard />} />
            <Route path="/lecturer/chat" element={<LecturerChat />} />
            <Route path="/lecturer/circulars" element={<LecturerCirculars />} />
            <Route path="/lecturer/exam-duties" element={<LecturerExamDuties />} />
            
            {/* HOD Routes */}
            <Route path="/hod/dashboard" element={<HODDashboard />} />
            <Route path="/hod/exam-duties" element={<HODExamDuties />} />
            <Route path="/hod/circulars" element={<HODCirculars />} />
            
            {/* Admin Routes */}
            <Route path="/admin/dashboard" element={<AdminDashboard />} />
            
            {/* File Management Routes */}
            <Route path="/files/*" element={<FileManager />} />
            <Route path="/files/upload" element={<FileUpload />} />
            <Route path="/files/search" element={<FileSearch />} />
            <Route path="/files/:fileId" element={<FileDetail />} />
            
            {/* Placement Routes */}
            <Route path="/placement/dashboard" element={<PlacementDashboard />} />
            <Route path="/placement/companies" element={<Companies />} />
            <Route path="/placement/companies/add" element={<CompanyForm />} />
            <Route path="/placement/companies/:id" element={<CompanyForm />} />
            <Route path="/placement/companies/:id/edit" element={<CompanyForm />} />
            <Route path="/placement/jobs" element={<Jobs />} />
            <Route path="/placement/jobs/post" element={<JobForm />} />
            <Route path="/placement/jobs/:id" element={<JobDetails />} />
            <Route path="/placement/jobs/:id/edit" element={<JobForm />} />
            <Route path="/placement/students" element={<Students />} />
            <Route path="/placement/students/:id" element={<PlacementStudentProfile />} />
            <Route path="/placement/shortlist" element={<Shortlist />} />
            <Route path="/placement/reports" element={<Reports />} />
            
            {/* 🔥 NEW: Resume Analyzer Route */}
            <Route path="/placement/resume-analyzer" element={<ResumeAnalyzer />} />
          </Route>
        </Route>
        
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  )
}

export default App