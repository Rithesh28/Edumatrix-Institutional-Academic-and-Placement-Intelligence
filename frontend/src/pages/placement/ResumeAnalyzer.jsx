import React, { useEffect, useState, useRef } from 'react';
import { 
  FileText, 
  Upload, 
  Search, 
  Filter, 
  Eye, 
  Download, 
  Trash2, 
  RefreshCw, 
  CheckCircle2, 
  AlertCircle, 
  X, 
  Award, 
  Briefcase, 
  GraduationCap, 
  Sparkles, 
  TrendingUp, 
  Layers,
  Clock,
  User
} from 'lucide-react';
import { useResumeStore } from '../../store/resumeStore';
import { useAuthStore } from '../../store/authStore';
import toast from 'react-hot-toast';
import { API_URL } from '../../services/api';
import axios from 'axios';

const ResumeAnalyzer = () => {
  const {
    resumes,
    loading,
    filters,
    total,
    uploadProgress,
    isUploading,
    fetchResumes,
    uploadResume,
    deleteResume,
    setFilters,
    clearFilters,
  } = useResumeStore();

  const { token, user } = useAuthStore();
  const fileInputRef = useRef(null);

  // Local state
  const [selectedFile, setSelectedFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [activeResume, setActiveResume] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [students, setStudents] = useState([]);
  const [selectedStudentId, setSelectedStudentId] = useState('');

  useEffect(() => {
    fetchResumes();
    if (user?.role === 'placement_officer' || user?.role === 'admin') {
      fetchStudents();
    }
  }, []);

  const fetchStudents = async () => {
    try {
      const res = await axios.get(`${API_URL}/placement/students`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (Array.isArray(res.data)) {
        setStudents(res.data);
      }
    } catch (err) {
      console.log('Could not fetch students list for resume attribution:', err);
    }
  };

  // Drag & drop handlers
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelected = (file) => {
    const validExts = ['.pdf', '.docx', '.doc', '.png', '.jpg', '.jpeg'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!validExts.includes(ext)) {
      toast.error('Please upload a PDF, DOCX, or Image file');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      toast.error('File size must be under 10MB');
      return;
    }
    setSelectedFile(file);
  };

  const handleUploadSubmit = async () => {
    if (!selectedFile) {
      toast.error('Please choose a resume file to upload');
      return;
    }

    try {
      const studentId = selectedStudentId ? parseInt(selectedStudentId) : null;
      await uploadResume(selectedFile, studentId);
      toast.success('✅ Resume uploaded and analyzed successfully!');
      setSelectedFile(null);
      setSelectedStudentId('');
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (error) {
      console.error('Upload failed:', error);
      toast.error(error.response?.data?.detail || error.message || 'Failed to upload resume');
    }
  };

  const handleViewDetails = async (resumeId) => {
    setLoadingDetail(true);
    try {
      const res = await axios.get(`${API_URL}/resume/${resumeId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setActiveResume(res.data);
    } catch (error) {
      console.error('Error fetching resume details:', error);
      toast.error('Failed to load resume details');
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleDelete = async (resumeId) => {
    if (!window.confirm('Are you sure you want to delete this resume analysis?')) return;
    try {
      await deleteResume(resumeId);
      toast.success('Resume deleted');
      if (activeResume?.id === resumeId) setActiveResume(null);
    } catch (error) {
      toast.error('Failed to delete resume');
    }
  };

  const handleExport = async (resumeId, format = 'json') => {
    try {
      const res = await axios.get(`${API_URL}/resume/${resumeId}/export?format=${format}`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `resume_analysis_${resumeId}.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      toast.success(`Exported resume as ${format.toUpperCase()}`);
    } catch (error) {
      toast.error('Failed to export resume');
    }
  };

  const handleReanalyze = async (resumeId) => {
    try {
      toast.loading('Re-analyzing resume...', { id: `reanalyze-${resumeId}` });
      const res = await axios.post(`${API_URL}/resume/${resumeId}/reanalyze`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.data.success) {
        toast.success('✅ Resume re-analyzed successfully!', { id: `reanalyze-${resumeId}` });
        fetchResumes();
      } else {
        toast.error(res.data.message || 'Re-analysis failed', { id: `reanalyze-${resumeId}` });
      }
    } catch (error) {
      toast.error('Failed to re-analyze resume', { id: `reanalyze-${resumeId}` });
    }
  };

  const isStudent = user?.role?.toLowerCase() === 'student';

  // Filtered list
  const filteredResumes = resumes.filter(r => {
    const q = searchTerm.toLowerCase();
    const nameMatch = r.name?.toLowerCase().includes(q) || r.student_name?.toLowerCase().includes(q);
    const skillsMatch = Array.isArray(r.skills) && r.skills.some(s => s.toLowerCase().includes(q));
    return !searchTerm || nameMatch || skillsMatch;
  });

  // Calculate statistics
  const avgScore = resumes.length > 0
    ? Math.round(resumes.reduce((acc, r) => acc + (r.ats_score || 0), 0) / (resumes.filter(r => r.ats_score !== null).length || 1))
    : 0;

  const topScoring = resumes.filter(r => (r.ats_score || 0) >= 75).length;
  const needsWork = resumes.filter(r => r.ats_score !== null && r.ats_score < 50).length;

  const getScoreBadge = (score) => {
    if (score === null || score === undefined) return <span className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded-full font-medium">Pending</span>;
    if (score >= 75) return <span className="px-2.5 py-1 text-xs bg-green-100 text-green-800 rounded-full font-semibold">ATS {Math.round(score)}%</span>;
    if (score >= 50) return <span className="px-2.5 py-1 text-xs bg-amber-100 text-amber-800 rounded-full font-semibold">ATS {Math.round(score)}%</span>;
    return <span className="px-2.5 py-1 text-xs bg-rose-100 text-rose-800 rounded-full font-semibold">ATS {Math.round(score)}%</span>;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Sparkles className="w-7 h-7 text-purple-600" />
            {isStudent ? 'My Resume Analyzer & ATS Scorer' : 'Placement AI Resume Intelligence'}
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            {isStudent 
              ? 'Upload your resume to check your ATS compatibility score, extract detected skills, and view personalized improvement tips.'
              : 'Review and analyze student uploaded resumes, evaluate ATS readiness, and test new resumes.'}
          </p>
        </div>
        <button
          onClick={() => fetchResumes()}
          className="self-start sm:self-auto px-4 py-2 bg-white border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50 flex items-center gap-2 shadow-sm"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Total Resumes</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">{total || resumes.length}</p>
          </div>
          <div className="p-3 bg-purple-50 text-purple-600 rounded-xl">
            <FileText className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Avg. ATS Score</p>
            <p className="text-2xl font-bold text-indigo-600 mt-1">{avgScore}%</p>
          </div>
          <div className="p-3 bg-indigo-50 text-indigo-600 rounded-xl">
            <TrendingUp className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">High Match (≥75%)</p>
            <p className="text-2xl font-bold text-emerald-600 mt-1">{topScoring}</p>
          </div>
          <div className="p-3 bg-emerald-50 text-emerald-600 rounded-xl">
            <Award className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Needs Work (&lt;50%)</p>
            <p className="text-2xl font-bold text-rose-600 mt-1">{needsWork}</p>
          </div>
          <div className="p-3 bg-rose-50 text-rose-600 rounded-xl">
            <AlertCircle className="w-6 h-6" />
          </div>
        </div>
      </div>

      {/* Upload Box */}
      <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
        <h2 className="text-base font-semibold text-gray-900 mb-2 flex items-center gap-2">
          <Upload className="w-5 h-5 text-purple-600" />
          Upload & Analyze Resume
        </h2>
        <p className="text-sm text-gray-500 mb-4">
          Upload any student resume in PDF, DOCX, or Image format for real-time ATS scoring, NLP entity extraction, and actionable tips.
        </p>

        <div
          className={`border-2 border-dashed rounded-xl p-6 text-center transition-all ${
            dragActive ? 'border-purple-500 bg-purple-50' : 'border-gray-300 hover:border-purple-400 bg-gray-50/50'
          }`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <input
            ref={fileInputRef}
            type="file"
            id="resume-file-input"
            accept=".pdf,.docx,.doc,.png,.jpg,.jpeg"
            onChange={(e) => e.target.files?.[0] && handleFileSelected(e.target.files[0])}
            className="hidden"
          />

          <label htmlFor="resume-file-input" className="cursor-pointer flex flex-col items-center justify-center">
            <div className="w-12 h-12 bg-purple-100 text-purple-600 rounded-full flex items-center justify-center mb-3">
              <Upload className="w-6 h-6" />
            </div>
            {selectedFile ? (
              <div className="text-center">
                <p className="text-sm font-semibold text-purple-700">📎 {selectedFile.name}</p>
                <p className="text-xs text-gray-400 mt-1">{(selectedFile.size / 1024).toFixed(1)} KB</p>
              </div>
            ) : (
              <div>
                <p className="text-sm font-medium text-gray-700">
                  <span className="text-purple-600 font-semibold underline">Click to choose</span> or drag and drop resume here
                </p>
                <p className="text-xs text-gray-400 mt-1">Supports PDF, DOCX, JPG, PNG (Max 10MB)</p>
              </div>
            )}
          </label>
        </div>

        {/* Progress Bar */}
        {isUploading && (
          <div className="mt-4">
            <div className="flex justify-between text-xs text-gray-600 mb-1">
              <span>🤖 Extracting entities & calculating ATS score...</span>
              <span>{uploadProgress}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div className="bg-purple-600 h-2 rounded-full transition-all duration-300" style={{ width: `${uploadProgress}%` }} />
            </div>
          </div>
        )}

        {/* Upload Actions & Optional Student Selector */}
        <div className="mt-4 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          {students.length > 0 && (
            <div className="flex items-center gap-2 flex-1 max-w-md">
              <label className="text-xs text-gray-500 whitespace-nowrap">Assign to Student (Optional):</label>
              <select
                value={selectedStudentId}
                onChange={(e) => setSelectedStudentId(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-purple-500 focus:outline-none"
              >
                <option value="">-- General / Current User --</option>
                {students.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.department || 'Student'})
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="flex items-center gap-2 self-end">
            {selectedFile && (
              <button
                type="button"
                onClick={() => {
                  setSelectedFile(null);
                  if (fileInputRef.current) fileInputRef.current.value = '';
                }}
                className="px-3 py-2 text-sm text-gray-500 hover:text-gray-700"
              >
                Cancel
              </button>
            )}
            <button
              onClick={handleUploadSubmit}
              disabled={isUploading || !selectedFile}
              className="px-5 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 font-medium text-sm disabled:opacity-50 disabled:cursor-not-allowed shadow-sm transition-colors"
            >
              {isUploading ? 'Analyzing...' : 'Analyze Resume'}
            </button>
          </div>
        </div>
      </div>

      {/* Resumes List Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 transform -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search by student, name, or skill..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-purple-500 focus:outline-none"
            />
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`p-2 rounded-lg border text-sm flex items-center gap-1.5 transition-colors ${
                showFilters ? 'bg-purple-50 text-purple-700 border-purple-300' : 'text-gray-600 border-gray-300 hover:bg-gray-50'
              }`}
            >
              <Filter className="w-4 h-4" />
              <span>Filters</span>
            </button>
          </div>
        </div>

        {/* Filter Controls */}
        {showFilters && (
          <div className="mb-4 p-4 bg-gray-50 rounded-lg border border-gray-200 grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Status</label>
              <select
                value={filters.status}
                onChange={(e) => {
                  setFilters({ status: e.target.value });
                  fetchResumes();
                }}
                className="w-full text-sm border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-purple-500"
              >
                <option value="">All Statuses</option>
                <option value="completed">Completed</option>
                <option value="processing">Processing</option>
                <option value="pending">Pending</option>
                <option value="failed">Failed</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Min ATS Score</label>
              <input
                type="number"
                min="0"
                max="100"
                placeholder="e.g. 60"
                value={filters.minScore}
                onChange={(e) => {
                  setFilters({ minScore: e.target.value });
                  fetchResumes();
                }}
                className="w-full text-sm border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-purple-500"
              >
              </input>
            </div>
            <div className="flex items-end">
              <button
                onClick={() => {
                  clearFilters();
                  fetchResumes();
                }}
                className="w-full p-2 bg-gray-200 hover:bg-gray-300 rounded-lg text-sm font-medium text-gray-700"
              >
                Reset Filters
              </button>
            </div>
          </div>
        )}

        {/* List Content */}
        {loading ? (
          <div className="flex justify-center items-center py-12">
            <RefreshCw className="w-6 h-6 text-purple-600 animate-spin" />
            <span className="ml-2 text-sm text-gray-500">Loading resumes...</span>
          </div>
        ) : filteredResumes.length === 0 ? (
          <div className="text-center py-12">
            <FileText className="w-12 h-12 text-gray-300 mx-auto mb-2" />
            <p className="text-gray-500 font-medium">No resumes found</p>
            <p className="text-xs text-gray-400 mt-1">Upload a resume above to start AI analysis</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50 text-gray-500 text-left font-medium">
                <tr>
                  <th className="py-3 px-4">Candidate / Student</th>
                  <th className="py-3 px-4">Skills Highlight</th>
                  <th className="py-3 px-4">ATS Compatibility</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {filteredResumes.map((resume) => (
                  <tr key={resume.id} className="hover:bg-purple-50/40 transition-colors">
                    <td className="py-3.5 px-4">
                      <div className="font-medium text-gray-900">{resume.name || 'Unnamed Candidate'}</div>
                      <div className="text-xs text-gray-500">{resume.student_name || resume.email || `ID #${resume.student_id}`}</div>
                    </td>
                    <td className="py-3.5 px-4 max-w-xs truncate">
                      {Array.isArray(resume.skills) && resume.skills.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {resume.skills.slice(0, 3).map((skill, idx) => (
                            <span key={idx} className="bg-gray-100 text-gray-700 px-2 py-0.5 rounded text-xs">
                              {typeof skill === 'string' ? skill : skill.name || ''}
                            </span>
                          ))}
                          {resume.skills.length > 3 && (
                            <span className="text-xs text-gray-400">+{resume.skills.length - 3}</span>
                          )}
                        </div>
                      ) : (
                        <span className="text-gray-400 text-xs">None detected</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4">{getScoreBadge(resume.ats_score)}</td>
                    <td className="py-3.5 px-4">
                      <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${
                        resume.status === 'completed' ? 'bg-green-100 text-green-800' :
                        resume.status === 'processing' ? 'bg-amber-100 text-amber-800' :
                        'bg-red-100 text-red-800'
                      }`}>
                        {resume.status || 'pending'}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-gray-500 text-xs">
                      {resume.created_at ? new Date(resume.created_at).toLocaleDateString() : 'N/A'}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => handleReanalyze(resume.id)}
                          className="p-1.5 text-blue-600 hover:bg-blue-50 rounded-lg"
                          title="Re-analyze & Score ATS"
                        >
                          <RefreshCw className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleViewDetails(resume.id)}
                          className="p-1.5 text-purple-600 hover:bg-purple-50 rounded-lg"
                          title="View Full Analysis"
                        >
                          <Eye className="w-4 h-4" />
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
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Full Resume Details Modal */}
      {activeResume && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto shadow-2xl border border-gray-200">
            {/* Modal Header */}
            <div className="sticky top-0 bg-white border-b border-gray-200 p-6 flex items-center justify-between z-10">
              <div>
                <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                  <span>📄 {activeResume.name || 'Candidate Resume'}</span>
                  {getScoreBadge(activeResume.ats_score)}
                </h2>
                <p className="text-xs text-gray-500 mt-0.5">
                  {activeResume.email} • {activeResume.phone || 'No phone'}
                </p>
              </div>
              <button
                onClick={() => setActiveResume(null)}
                className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-full transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-6">
              {/* ATS Score & Score Breakdown */}
              <div className="bg-gradient-to-r from-purple-50 via-indigo-50 to-blue-50 p-5 rounded-xl border border-purple-100">
                <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
                  <div>
                    <h3 className="text-sm font-semibold text-purple-900 uppercase tracking-wider">Overall ATS Readiness</h3>
                    <p className="text-xs text-purple-700 mt-1">
                      Calculated using industry standard keyword density, semantic headings, and skill taxonomy.
                    </p>
                  </div>
                  <div className="text-center bg-white px-5 py-3 rounded-xl shadow-sm border border-purple-200">
                    <p className="text-3xl font-extrabold text-purple-600">{Math.round(activeResume.ats_score || 0)}%</p>
                    <p className="text-[10px] font-semibold uppercase text-gray-500 mt-0.5">
                      {(activeResume.ats_score || 0) >= 75 ? '🔥 Strong Match' : (activeResume.ats_score || 0) >= 50 ? '⚡ Average' : '⚠️ Needs Polish'}
                    </p>
                  </div>
                </div>
              </div>

              {/* Skills Found */}
              <div>
                <h4 className="text-sm font-bold text-gray-900 flex items-center gap-2 mb-2">
                  <Award className="w-4 h-4 text-purple-600" />
                  Extracted Technical & Domain Skills ({activeResume.skills?.length || 0})
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {activeResume.skills && activeResume.skills.length > 0 ? (
                    activeResume.skills.map((skill, i) => (
                      <span key={i} className="px-3 py-1 bg-purple-50 border border-purple-200 text-purple-700 text-xs rounded-lg font-medium">
                        {typeof skill === 'string' ? skill : skill.name || JSON.stringify(skill)}
                      </span>
                    ))
                  ) : (
                    <p className="text-xs text-gray-400">No skills recognized.</p>
                  )}
                </div>
              </div>

              {/* Suggestions & Recommendations */}
              {activeResume.suggestions && activeResume.suggestions.length > 0 && (
                <div className="bg-amber-50/70 border border-amber-200 rounded-xl p-4">
                  <h4 className="text-sm font-bold text-amber-900 flex items-center gap-2 mb-2">
                    <Sparkles className="w-4 h-4 text-amber-600" />
                    AI Resume Improvement Suggestions
                  </h4>
                  <ul className="space-y-1.5 text-xs text-amber-900">
                    {activeResume.suggestions.map((sug, i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <span className="text-amber-500 font-bold">•</span>
                        <span>{typeof sug === 'string' ? sug : sug.message || sug.suggestion || JSON.stringify(sug)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Education */}
              {activeResume.education && activeResume.education.length > 0 && (
                <div>
                  <h4 className="text-sm font-bold text-gray-900 flex items-center gap-2 mb-2">
                    <GraduationCap className="w-4 h-4 text-indigo-600" />
                    Education History
                  </h4>
                  <div className="space-y-2">
                    {activeResume.education.map((edu, idx) => (
                      <div key={idx} className="p-3 bg-gray-50 rounded-lg border border-gray-200 text-xs">
                        <p className="font-semibold text-gray-800">{edu.degree || edu.institution || 'Degree'}</p>
                        <p className="text-gray-500">{edu.institution || edu.branch || ''} {edu.year ? `(${edu.year})` : ''}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Experience / Projects */}
              {activeResume.experience && activeResume.experience.length > 0 && (
                <div>
                  <h4 className="text-sm font-bold text-gray-900 flex items-center gap-2 mb-2">
                    <Briefcase className="w-4 h-4 text-emerald-600" />
                    Work Experience & Internships
                  </h4>
                  <div className="space-y-2">
                    {activeResume.experience.map((exp, idx) => (
                      <div key={idx} className="p-3 bg-gray-50 rounded-lg border border-gray-200 text-xs">
                        <p className="font-semibold text-gray-800">{exp.title || exp.role || 'Experience'}</p>
                        <p className="text-gray-500">{exp.company || ''} {exp.duration ? `• ${exp.duration}` : ''}</p>
                        {exp.description && <p className="text-gray-600 mt-1">{exp.description}</p>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 p-4 flex justify-between items-center">
              <button
                onClick={() => handleExport(activeResume.id, 'json')}
                className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-xs font-semibold hover:bg-emerald-700 flex items-center gap-1.5"
              >
                <Download className="w-4 h-4" />
                <span>Export Analysis</span>
              </button>
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
  );
};

export default ResumeAnalyzer;