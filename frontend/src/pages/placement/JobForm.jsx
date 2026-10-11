import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Briefcase,
  ArrowLeft,
  Plus,
  X,
  Search,
  Upload,
  FileText,
  Sparkles,
  Loader2,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Calendar,
  DollarSign,
  Layers,
  Award,
  Info,
  Clock,
  Building2,
  ShieldAlert,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import toast from 'react-hot-toast';

const JobForm = () => {
  const navigate = useNavigate();
  const { id } = useParams();
  const {
    createJobPosting,
    updateJobPosting,
    fetchJobPosting,
    selectedJob,
    fetchCompanies,
    companies,
    isLoading,
    parseJdText,
    uploadJdFile,
  } = usePlacementStore();

  const [formData, setFormData] = useState({
    company_id: '',
    title: '',
    description: '',
    required_skills: [],
    preferred_skills: [],
    experience_level: '',
    cgpa_criteria: '',
    branch_eligibility: [],
    location: '',
    salary_range: '',
    application_url: '',
    application_deadline: '',
    drive_date: '',
    status: 'draft',
  });

  const [skillInput, setSkillInput] = useState('');
  const [preferredSkillInput, setPreferredSkillInput] = useState('');
  const [branchInput, setBranchInput] = useState('');
  const [companySearch, setCompanySearch] = useState('');
  const [showCompanySuggestions, setShowCompanySuggestions] = useState(false);
  const [filteredCompanies, setFilteredCompanies] = useState([]);
  const [companyError, setCompanyError] = useState('');
  const searchRef = useRef(null);

  // JD Parser state
  const [isParsingJd, setIsParsingJd] = useState(false);
  const [jdParseMode, setJdParseMode] = useState('upload'); // 'upload' | 'text'
  const [jdRawText, setJdRawText] = useState('');
  const [jdSelectedFile, setJdSelectedFile] = useState(null);
  const [parsedResult, setParsedResult] = useState(null);
  const [showEvidence, setShowEvidence] = useState(false);
  const fileInputRef = useRef(null);

  const isEditing = !!id;

  // Fetch companies and job data
  useEffect(() => {
    fetchCompanies();
    if (isEditing) {
      fetchJobPosting(id);
    }
  }, [id]);

  // Set form data when editing
  useEffect(() => {
    if (selectedJob && isEditing) {
      const companyId = selectedJob.company_id || '';
      const companyName = selectedJob.company_name || '';

      let companyNameToUse = companyName;
      if (!companyNameToUse && companyId) {
        const foundCompany = companies.find((c) => c.id === companyId);
        companyNameToUse = foundCompany?.name || '';
      }

      setFormData({
        company_id: companyId,
        title: selectedJob.title || '',
        description: selectedJob.description || '',
        required_skills: selectedJob.required_skills || [],
        preferred_skills: selectedJob.preferred_skills || [],
        experience_level: selectedJob.experience_level || '',
        cgpa_criteria: selectedJob.cgpa_criteria !== null && selectedJob.cgpa_criteria !== undefined ? String(selectedJob.cgpa_criteria) : '',
        branch_eligibility: selectedJob.branch_eligibility || [],
        location: selectedJob.location || '',
        salary_range: selectedJob.salary_range || '',
        application_url: selectedJob.application_url || '',
        application_deadline: selectedJob.application_deadline ? selectedJob.application_deadline.slice(0, 16) : '',
        drive_date: selectedJob.drive_date ? selectedJob.drive_date.slice(0, 16) : '',
        status: selectedJob.status || 'draft',
      });

      setCompanySearch(companyNameToUse);
    }
  }, [selectedJob, isEditing, companies]);

  // Filter companies based on search
  useEffect(() => {
    if (companySearch.length > 0) {
      const filtered = companies.filter((c) =>
        c.name.toLowerCase().includes(companySearch.toLowerCase()) && c.is_active !== false
      );
      setFilteredCompanies(filtered);
      setShowCompanySuggestions(true);
    } else {
      setFilteredCompanies([]);
      setShowCompanySuggestions(false);
    }
  }, [companySearch, companies]);

  // Close suggestions on click outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (searchRef.current && !searchRef.current.contains(event.target)) {
        setShowCompanySuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleCompanySelect = (company) => {
    setFormData((prev) => ({ ...prev, company_id: company.id }));
    setCompanySearch(company.name);
    setShowCompanySuggestions(false);
    setCompanyError('');
  };

  const handleClearCompany = () => {
    setFormData((prev) => ({ ...prev, company_id: '' }));
    setCompanySearch('');
    setShowCompanySuggestions(false);
    setCompanyError('');
  };

  const handleAddSkill = () => {
    if (skillInput.trim() && !formData.required_skills.includes(skillInput.trim())) {
      setFormData((prev) => ({
        ...prev,
        required_skills: [...prev.required_skills, skillInput.trim()],
      }));
      setSkillInput('');
    }
  };

  const handleRemoveSkill = (skill) => {
    setFormData((prev) => ({
      ...prev,
      required_skills: prev.required_skills.filter((s) => s !== skill),
    }));
  };

  const handleAddPreferredSkill = () => {
    if (preferredSkillInput.trim() && !formData.preferred_skills.includes(preferredSkillInput.trim())) {
      setFormData((prev) => ({
        ...prev,
        preferred_skills: [...prev.preferred_skills, preferredSkillInput.trim()],
      }));
      setPreferredSkillInput('');
    }
  };

  const handleRemovePreferredSkill = (skill) => {
    setFormData((prev) => ({
      ...prev,
      preferred_skills: prev.preferred_skills.filter((s) => s !== skill),
    }));
  };

  const handleAddBranch = () => {
    if (branchInput.trim() && !formData.branch_eligibility.includes(branchInput.trim())) {
      setFormData((prev) => ({
        ...prev,
        branch_eligibility: [...prev.branch_eligibility, branchInput.trim()],
      }));
      setBranchInput('');
    }
  };

  const handleRemoveBranch = (branch) => {
    setFormData((prev) => ({
      ...prev,
      branch_eligibility: prev.branch_eligibility.filter((b) => b !== branch),
    }));
  };

  // Handle JD File & Text Parsing
  const handleParseJd = async () => {
    if (jdParseMode === 'upload' && !jdSelectedFile) {
      toast.error('Please select a JD document file (.pdf, .docx, .txt)');
      return;
    }
    if (jdParseMode === 'text' && !jdRawText.trim()) {
      toast.error('Please paste Job Description text to analyze');
      return;
    }

    setIsParsingJd(true);
    setParsedResult(null);

    try {
      let parsed = null;
      if (jdParseMode === 'upload') {
        parsed = await uploadJdFile(jdSelectedFile);
      } else {
        parsed = await parseJdText(jdRawText);
      }

      if (parsed) {
        setParsedResult(parsed);

        // Update form fields with extracted data
        setFormData((prev) => ({
          ...prev,
          title: parsed.title || prev.title,
          description: parsed.description || prev.description,
          required_skills: Array.from(new Set([...(parsed.required_skills || []), ...prev.required_skills])),
          preferred_skills: Array.from(new Set([...(parsed.preferred_skills || []), ...prev.preferred_skills])),
          experience_level: parsed.experience_level || prev.experience_level,
          cgpa_criteria: parsed.cgpa_criteria !== null && parsed.cgpa_criteria !== undefined ? String(parsed.cgpa_criteria) : prev.cgpa_criteria,
          branch_eligibility: parsed.branch_eligibility?.length ? parsed.branch_eligibility : prev.branch_eligibility,
          location: parsed.location || prev.location,
          salary_range: parsed.salary_range || prev.salary_range,
          application_deadline: parsed.application_deadline ? parsed.application_deadline.slice(0, 16) : prev.application_deadline,
          drive_date: parsed.drive_date ? parsed.drive_date.slice(0, 16) : prev.drive_date,
        }));

        // Try to match company name if found
        if (parsed.company_name && !formData.company_id) {
          const matchCo = companies.find((c) =>
            c.name.toLowerCase().includes(parsed.company_name.toLowerCase()) ||
            parsed.company_name.toLowerCase().includes(c.name.toLowerCase())
          );
          if (matchCo) {
            setFormData((prev) => ({ ...prev, company_id: matchCo.id }));
            setCompanySearch(matchCo.name);
          } else {
            setCompanySearch(parsed.company_name);
          }
        }

        const reqCount = parsed.required_skills?.length || 0;
        const prefCount = parsed.preferred_skills?.length || 0;
        toast.success(
          `Extracted ${reqCount} required & ${prefCount} preferred skills + requirements. Review fields and warnings below.`
        );
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || 'Failed to extract requirements from Job Description');
    } finally {
      setIsParsingJd(false);
    }
  };

  // Append rich extracted metadata into description for candidate clarity
  const handleAppendExtractedDetailsToDescription = () => {
    if (!parsedResult) return;
    let extraText = '\n\n--- ADDITIONAL REQUIREMENTS & DETAILS ---\n';

    if (parsedResult.academic_percentages) {
      const p = parsedResult.academic_percentages;
      const parts = [];
      if (p.tenth) parts.push(`10th: ${p.tenth}%`);
      if (p.twelfth) parts.push(`12th: ${p.twelfth}%`);
      if (p.diploma) parts.push(`Diploma: ${p.diploma}%`);
      if (p.degree) parts.push(`Graduation/Degree: ${p.degree}%`);
      if (parts.length > 0) extraText += `• Academic Percentages: ${parts.join(', ')}\n`;
    }

    if (parsedResult.backlog_criteria) {
      extraText += `• Backlog Criteria: ${parsedResult.backlog_criteria}\n`;
    }

    if (parsedResult.bond_details) {
      extraText += `• Service Agreement / Bond: ${parsedResult.bond_details}\n`;
    }

    if (parsedResult.work_mode) {
      extraText += `• Work Mode: ${parsedResult.work_mode}\n`;
    }

    if (parsedResult.selection_rounds?.length > 0) {
      extraText += `• Selection Process: ${parsedResult.selection_rounds.join(' → ')}\n`;
    }

    if (parsedResult.graduation_years?.length > 0) {
      extraText += `• Eligible Batches: ${parsedResult.graduation_years.join(', ')}\n`;
    }

    setFormData((prev) => ({
      ...prev,
      description: (prev.description || '') + extraText,
    }));
    toast.success('Appended additional extracted criteria to Job Description');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!formData.company_id) {
      setCompanyError('Please select a company');
      toast.error('Please select a company');
      return;
    }

    if (!formData.title.trim()) {
      toast.error('Please enter a job title');
      return;
    }

    try {
      const submitData = {
        ...formData,
        application_url: formData.application_url?.trim() || null,
        cgpa_criteria: formData.cgpa_criteria ? parseFloat(formData.cgpa_criteria) : null,
        required_skills: formData.required_skills || [],
        preferred_skills: formData.preferred_skills || [],
        branch_eligibility: formData.branch_eligibility || [],
      };

      if (isEditing) {
        await updateJobPosting(id, submitData);
        toast.success('Job updated successfully');
      } else {
        await createJobPosting(submitData);
        toast.success(`Job posted successfully as ${submitData.status.toUpperCase()}`);
      }
      navigate('/placement/jobs');
    } catch (error) {
      toast.error(error.message || 'Failed to save job');
    }
  };

  if (isLoading && isEditing) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-indigo-600 border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto pb-12">
      <button
        onClick={() => navigate('/placement/jobs')}
        className="flex items-center space-x-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white mb-6 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Jobs</span>
      </button>

      {/* Header */}
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800 p-6 mb-6">
        <div className="flex items-center space-x-3">
          <div className="p-3 bg-indigo-50 dark:bg-indigo-950/50 rounded-xl text-indigo-600 dark:text-indigo-400">
            <Briefcase className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">
              {isEditing ? 'Edit Job Posting' : 'Create Job Posting'}
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {isEditing
                ? 'Update job requirements, skills, and eligibility criteria'
                : 'Define job details manually or extract automatically from a Job Description document'}
            </p>
          </div>
        </div>
      </div>

      {/* Smart JD Parser Section */}
      <div className="bg-gradient-to-br from-indigo-50/60 via-purple-50/40 to-white dark:from-gray-900 dark:via-gray-900 dark:to-gray-800/80 rounded-xl shadow-sm border border-indigo-100 dark:border-gray-800 p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            <h3 className="font-semibold text-gray-900 dark:text-white">
              Smart JD Extractor (General-Purpose Pipeline)
            </h3>
          </div>
          <div className="flex rounded-lg bg-gray-200 dark:bg-gray-800 p-0.5 text-xs font-medium">
            <button
              type="button"
              onClick={() => setJdParseMode('upload')}
              className={`px-3 py-1.5 rounded-md transition-all ${
                jdParseMode === 'upload'
                  ? 'bg-white dark:bg-gray-700 text-indigo-600 dark:text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900'
              }`}
            >
              Upload Document (PDF/DOCX/TXT)
            </button>
            <button
              type="button"
              onClick={() => setJdParseMode('text')}
              className={`px-3 py-1.5 rounded-md transition-all ${
                jdParseMode === 'text'
                  ? 'bg-white dark:bg-gray-700 text-indigo-600 dark:text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900'
              }`}
            >
              Paste JD Text
            </button>
          </div>
        </div>

        <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
          Extracts company, designation, 80/20 skills, academic percentages, CGPA, staged compensation, deadlines, and bond requirements. Parsing populates the review interface below without publishing the job.
        </p>

        {jdParseMode === 'upload' ? (
          <div>
            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-gray-300 dark:border-gray-700 hover:border-indigo-500 dark:hover:border-indigo-400 rounded-xl p-5 text-center cursor-pointer transition-colors bg-white/70 dark:bg-gray-800/50"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.doc,.txt"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    setJdSelectedFile(e.target.files[0]);
                  }
                }}
              />
              <Upload className="w-8 h-8 text-indigo-600 dark:text-indigo-400 mx-auto mb-2" />
              {jdSelectedFile ? (
                <div>
                  <p className="text-sm font-semibold text-indigo-600 dark:text-indigo-400">
                    📎 {jdSelectedFile.name}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    {(jdSelectedFile.size / 1024).toFixed(1)} KB — Click to choose a different file
                  </p>
                </div>
              ) : (
                <div>
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Click to browse or drop Job Description file
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Supports PDF, DOCX, or TXT format (Preserves tables & paragraphs)
                  </p>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div>
            <textarea
              rows="5"
              value={jdRawText}
              onChange={(e) => setJdRawText(e.target.value)}
              placeholder="Paste raw Job Description text here (e.g. campus notices, corporate job postings, eligibility tables)..."
              className="w-full text-sm p-3 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            />
          </div>
        )}

        <div className="mt-4 flex items-center justify-between">
          <button
            type="button"
            disabled={isParsingJd}
            onClick={handleParseJd}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg flex items-center space-x-2 shadow-sm transition-colors cursor-pointer"
          >
            {isParsingJd ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Running Extraction Pipeline...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Extract Job Details</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* EXTRACTED INSIGHTS & REVIEW FLAGS CARD (When Extracted) */}
      {parsedResult && (
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800 p-6 mb-6">
          <div className="flex items-center justify-between pb-3 border-b border-gray-100 dark:border-gray-800 mb-4">
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
              <h3 className="text-base font-bold text-gray-900 dark:text-white">
                Extraction Review & Quality Analysis
              </h3>
            </div>
            <span className="text-xs text-gray-500 dark:text-gray-400">
              Processed {parsedResult.raw_text_length} characters
            </span>
          </div>

          {/* Actionable Review Flags / Warnings */}
          {parsedResult.review_flags?.length > 0 && (
            <div className="mb-5 p-4 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-xl">
              <div className="flex items-center space-x-2 text-amber-800 dark:text-amber-300 font-semibold text-xs mb-2">
                <AlertTriangle className="w-4 h-4" />
                <span>Items Requiring Officer Confirmation ({parsedResult.review_flags.length})</span>
              </div>
              <ul className="space-y-1 text-xs text-amber-700 dark:text-amber-400 list-disc list-inside">
                {parsedResult.review_flags.map((flag, idx) => (
                  <li key={idx} className="leading-relaxed">{flag}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Structured Intelligence Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
            {/* Academic Criteria Details */}
            <div className="p-3.5 bg-gray-50 dark:bg-gray-800/60 rounded-xl border border-gray-200 dark:border-gray-700/60 text-xs">
              <p className="font-semibold text-gray-900 dark:text-white flex items-center gap-1.5 mb-2">
                <Award className="w-4 h-4 text-indigo-500" />
                Academic Criteria
              </p>
              <div className="space-y-1 text-gray-600 dark:text-gray-300">
                <p>CGPA Cutoff: <strong className="text-gray-900 dark:text-white">{parsedResult.cgpa_criteria !== null ? `${parsedResult.cgpa_criteria}+` : 'None / Not Specified'}</strong></p>
                {parsedResult.academic_percentages?.degree && (
                  <p>Graduation %: <strong className="text-indigo-600 dark:text-indigo-400">{parsedResult.academic_percentages.degree}%</strong></p>
                )}
                {parsedResult.academic_percentages?.twelfth && (
                  <p>12th/PUC %: <strong>{parsedResult.academic_percentages.twelfth}%</strong></p>
                )}
                {parsedResult.academic_percentages?.tenth && (
                  <p>10th %: <strong>{parsedResult.academic_percentages.tenth}%</strong></p>
                )}
                {parsedResult.backlog_criteria && (
                  <p className="text-rose-600 dark:text-rose-400 font-medium">⚠️ {parsedResult.backlog_criteria}</p>
                )}
                {parsedResult.degree_eligibility?.length > 0 && (
                  <p>Degrees: {parsedResult.degree_eligibility.join(', ')}</p>
                )}
                {parsedResult.graduation_years?.length > 0 && (
                  <p>Eligible Batches: <strong>{parsedResult.graduation_years.join(', ')}</strong></p>
                )}
              </div>
            </div>

            {/* Compensation & Staged Progression */}
            <div className="p-3.5 bg-gray-50 dark:bg-gray-800/60 rounded-xl border border-gray-200 dark:border-gray-700/60 text-xs">
              <p className="font-semibold text-gray-900 dark:text-white flex items-center gap-1.5 mb-2">
                <DollarSign className="w-4 h-4 text-emerald-500" />
                Compensation Breakdown
              </p>
              <div className="space-y-1.5 text-gray-600 dark:text-gray-300">
                {parsedResult.compensation_details?.staged_compensation?.length > 0 ? (
                  <div>
                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 font-semibold uppercase">
                      Staged Offer
                    </span>
                    {parsedResult.compensation_details.staged_compensation.map((stage, i) => (
                      <p key={i} className="mt-1">
                        <strong>{stage.stage}:</strong> {stage.amount}
                      </p>
                    ))}
                  </div>
                ) : (
                  <p>Compensation: <strong>{parsedResult.salary_range || 'Not specified'}</strong></p>
                )}
                {parsedResult.job_type && (
                  <p className="mt-1">Employment Type: <strong>{parsedResult.job_type}</strong></p>
                )}
              </div>
            </div>

            {/* Workplace & Agreement */}
            <div className="p-3.5 bg-gray-50 dark:bg-gray-800/60 rounded-xl border border-gray-200 dark:border-gray-700/60 text-xs">
              <p className="font-semibold text-gray-900 dark:text-white flex items-center gap-1.5 mb-2">
                <Building2 className="w-4 h-4 text-purple-500" />
                Workplace & Selection
              </p>
              <div className="space-y-1 text-gray-600 dark:text-gray-300">
                <p>Location: <strong>{parsedResult.location || 'Not specified'}</strong></p>
                <p>Work Mode: <strong>{parsedResult.work_mode || 'Not specified'}</strong></p>
                {parsedResult.bond_details && (
                  <p className="text-amber-600 dark:text-amber-400 font-medium">📜 Bond: {parsedResult.bond_details}</p>
                )}
                {parsedResult.selection_rounds?.length > 0 && (
                  <p>Rounds: {parsedResult.selection_rounds.join(' → ')}</p>
                )}
                {parsedResult.certifications?.length > 0 && (
                  <p>Certifications: {parsedResult.certifications.join(', ')}</p>
                )}
              </div>
            </div>
          </div>

          {/* Quick Action: Append non-DB details to Description */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-gray-100 dark:border-gray-800 text-xs">
            <button
              type="button"
              onClick={handleAppendExtractedDetailsToDescription}
              className="px-3 py-1.5 bg-indigo-50 dark:bg-indigo-950/50 hover:bg-indigo-100 dark:hover:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300 rounded-lg font-medium transition-colors cursor-pointer flex items-center gap-1.5"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Append Academic & Bond Criteria to Job Description</span>
            </button>

            {/* Toggle Traceable Evidence */}
            {parsedResult.field_evidence && Object.keys(parsedResult.field_evidence).length > 0 && (
              <button
                type="button"
                onClick={() => setShowEvidence(!showEvidence)}
                className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 font-medium flex items-center gap-1 cursor-pointer"
              >
                <span>{showEvidence ? 'Hide' : 'Inspect'} Field Extraction Evidence ({Object.keys(parsedResult.field_evidence).length})</span>
                {showEvidence ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>
            )}
          </div>

          {/* Field Evidence Drawer */}
          {showEvidence && parsedResult.field_evidence && (
            <div className="mt-4 p-4 bg-gray-50 dark:bg-gray-800/40 rounded-xl border border-gray-200 dark:border-gray-700/60 space-y-2 text-xs">
              <p className="font-semibold text-gray-700 dark:text-gray-300 mb-2">
                Verbatim Document Evidence (Audit Traceability):
              </p>
              {Object.entries(parsedResult.field_evidence).map(([field, snippet]) => (
                <div key={field} className="flex flex-col sm:flex-row sm:items-start justify-between gap-1 border-b border-gray-100 dark:border-gray-700/40 pb-1.5 last:border-0">
                  <span className="font-mono text-indigo-600 dark:text-indigo-400 shrink-0 font-medium">{field}:</span>
                  <span className="text-gray-600 dark:text-gray-400 text-right sm:text-left italic">"{snippet}"</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Main Form */}
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800 p-6">
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Company Search/Auto-suggest */}
          <div ref={searchRef}>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Company *
            </label>
            <div className="relative">
              <input
                type="text"
                value={companySearch}
                onChange={(e) => setCompanySearch(e.target.value)}
                onFocus={() => {
                  if (companySearch.length > 0) {
                    setShowCompanySuggestions(true);
                  }
                }}
                className={`w-full px-3 py-2 pl-10 pr-10 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 ${
                  companyError ? 'border-red-500' : 'border-gray-300 dark:border-gray-700'
                }`}
                placeholder="Type to search company..."
              />
              <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
              {companySearch && (
                <button
                  type="button"
                  onClick={handleClearCompany}
                  className="absolute right-3 top-2.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            {companyError && <p className="mt-1 text-sm text-red-600">{companyError}</p>}

            {/* Suggestions Dropdown */}
            {showCompanySuggestions && (
              <div className="absolute z-10 w-full max-w-xl mt-1 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 max-h-60 overflow-y-auto">
                {filteredCompanies.length > 0 ? (
                  filteredCompanies.map((company) => (
                    <button
                      key={company.id}
                      type="button"
                      onClick={() => handleCompanySelect(company)}
                      className="w-full px-4 py-2.5 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 flex items-center justify-between border-b border-gray-100 dark:border-gray-700/50 last:border-0"
                    >
                      <span>{company.name}</span>
                      {company.industry && (
                        <span className="text-xs text-gray-400">{company.industry}</span>
                      )}
                    </button>
                  ))
                ) : (
                  <div className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                    No companies found.
                    <button
                      type="button"
                      onClick={() => navigate('/placement/companies/add')}
                      className="ml-2 text-indigo-600 dark:text-indigo-400 hover:underline font-medium"
                    >
                      Add new company
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Selected company badge */}
            {formData.company_id && (
              <div className="mt-2 inline-flex items-center px-2.5 py-1 bg-green-50 dark:bg-green-950/40 border border-green-200 dark:border-green-800 rounded-lg text-xs font-medium text-green-700 dark:text-green-300">
                ✅ Selected: {companySearch}
              </div>
            )}
          </div>

          {/* Job Title */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Job Title *
            </label>
            <input
              type="text"
              name="title"
              value={formData.title}
              onChange={handleChange}
              required
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              placeholder="e.g., Software Development Engineer - I"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Job Description
            </label>
            <textarea
              name="description"
              value={formData.description}
              onChange={handleChange}
              rows="5"
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent font-sans text-sm leading-relaxed"
              placeholder="Job responsibilities, company overview, qualifications, and special criteria..."
            />
          </div>

          {/* Required Skills (Weight: 80% in matching) */}
          <div className="p-4 bg-gray-50/70 dark:bg-gray-800/40 rounded-xl border border-gray-200 dark:border-gray-700/60">
            <div className="flex items-center justify-between mb-1">
              <label className="block text-sm font-medium text-gray-900 dark:text-white">
                Required Skills (Core)
              </label>
              <span className="text-xs text-indigo-600 dark:text-indigo-400 font-medium">
                80% Matching Weight
              </span>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
              Mandatory skills candidates must possess for this role.
            </p>
            <div className="flex space-x-2">
              <input
                type="text"
                value={skillInput}
                onChange={(e) => setSkillInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAddSkill();
                  }
                }}
                className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-indigo-500"
                placeholder="Add required skill (e.g., Python, SQL, React)"
              />
              <button
                type="button"
                onClick={handleAddSkill}
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
            <div className="flex flex-wrap gap-2 mt-3">
              {formData.required_skills.map((skill) => (
                <span
                  key={skill}
                  className="inline-flex items-center px-2.5 py-1 bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 rounded-full text-xs font-medium"
                >
                  {skill}
                  <button
                    type="button"
                    onClick={() => handleRemoveSkill(skill)}
                    className="ml-1.5 text-indigo-500 hover:text-indigo-700 dark:hover:text-indigo-200"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
              {formData.required_skills.length === 0 && (
                <span className="text-xs text-gray-400 italic">No required skills added yet</span>
              )}
            </div>
          </div>

          {/* Preferred Skills (Weight: 20% in matching) */}
          <div className="p-4 bg-gray-50/70 dark:bg-gray-800/40 rounded-xl border border-gray-200 dark:border-gray-700/60">
            <div className="flex items-center justify-between mb-1">
              <label className="block text-sm font-medium text-gray-900 dark:text-white">
                Preferred Skills (Bonus)
              </label>
              <span className="text-xs text-teal-600 dark:text-teal-400 font-medium">
                20% Matching Weight
              </span>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
              Nice-to-have secondary skills that boost candidate ranking.
            </p>
            <div className="flex space-x-2">
              <input
                type="text"
                value={preferredSkillInput}
                onChange={(e) => setPreferredSkillInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAddPreferredSkill();
                  }
                }}
                className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-teal-500"
                placeholder="Add preferred skill (e.g., Docker, AWS, GraphQL)"
              />
              <button
                type="button"
                onClick={handleAddPreferredSkill}
                className="px-4 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition-colors"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
            <div className="flex flex-wrap gap-2 mt-3">
              {formData.preferred_skills.map((skill) => (
                <span
                  key={skill}
                  className="inline-flex items-center px-2.5 py-1 bg-teal-100 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800 rounded-full text-xs font-medium"
                >
                  {skill}
                  <button
                    type="button"
                    onClick={() => handleRemovePreferredSkill(skill)}
                    className="ml-1.5 text-teal-500 hover:text-teal-700 dark:hover:text-teal-200"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
              {formData.preferred_skills.length === 0 && (
                <span className="text-xs text-gray-400 italic">No preferred skills added yet</span>
              )}
            </div>
          </div>

          {/* Experience & CGPA */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Experience Level
              </label>
              <select
                name="experience_level"
                value={formData.experience_level}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">Select</option>
                <option value="fresher">Fresher / Graduate Trainee</option>
                <option value="0-1">0-1 years</option>
                <option value="1-3">1-3 years</option>
                <option value="3-5">3-5 years</option>
                <option value="5+">5+ years</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Minimum CGPA Criteria (10-point scale)
              </label>
              <input
                type="number"
                name="cgpa_criteria"
                value={formData.cgpa_criteria}
                onChange={handleChange}
                step="0.1"
                min="0"
                max="10"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-indigo-500"
                placeholder="e.g., 7.5 (leave empty if no CGPA cutoff)"
              />
            </div>
          </div>

          {/* Eligible Branches */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Eligible Branches
            </label>
            <div className="flex space-x-2">
              <input
                type="text"
                value={branchInput}
                onChange={(e) => setBranchInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAddBranch();
                  }
                }}
                className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-indigo-500"
                placeholder="Add eligible branch (e.g., CSE, ECE, IT, AIML)"
              />
              <button
                type="button"
                onClick={handleAddBranch}
                className="px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
            <div className="flex flex-wrap gap-2 mt-2">
              {formData.branch_eligibility.map((branch) => (
                <span
                  key={branch}
                  className="inline-flex items-center px-2.5 py-1 bg-green-100 dark:bg-green-950/60 text-green-700 dark:text-green-300 border border-green-200 dark:border-green-800 rounded-full text-xs font-medium"
                >
                  {branch}
                  <button
                    type="button"
                    onClick={() => handleRemoveBranch(branch)}
                    className="ml-1 text-green-500 hover:text-green-700"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
              {formData.branch_eligibility.length === 0 && (
                <span className="text-xs text-gray-400 italic">Open to all branches (none restricted)</span>
              )}
            </div>
          </div>

          {/* Location & Salary */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Location
              </label>
              <input
                type="text"
                name="location"
                value={formData.location}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-indigo-500"
                placeholder="e.g., Bangalore, India (Hybrid)"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Salary / Compensation Package
              </label>
              <input
                type="text"
                name="salary_range"
                value={formData.salary_range}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-indigo-500"
                placeholder="e.g., ₹8 - ₹12 LPA or Stipend: ₹25,000/mo → CTC: ₹6.5 LPA"
              />
            </div>
          </div>

          {/* Official External Application URL */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Official Application URL <span className="text-xs font-normal text-gray-500 dark:text-gray-400">(Optional)</span>
            </label>
            <input
              type="url"
              name="application_url"
              value={formData.application_url}
              onChange={handleChange}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-indigo-500"
              placeholder="https://company.careers.com/apply/job-12345"
            />
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              Direct HTTP/HTTPS link where students apply on the company's official career website. Students will open this page to submit their external application before confirming on EduMatrix.
            </p>
          </div>

          {/* Deadlines */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Application / Registration Deadline
              </label>
              <input
                type="datetime-local"
                name="application_deadline"
                value={formData.application_deadline}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Placement Drive Date
              </label>
              <input
                type="datetime-local"
                name="drive_date"
                value={formData.drive_date}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          {/* Status Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Initial Status
            </label>
            <select
              name="status"
              value={formData.status}
              onChange={handleChange}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-indigo-500"
            >
              <option value="draft">Draft (Review first, publish when finalized)</option>
              <option value="open">Open (Immediately active for candidate matching)</option>
              <option value="closed">Closed</option>
            </select>
          </div>

          {/* Buttons */}
          <div className="flex space-x-3 pt-4 border-t border-gray-200 dark:border-gray-800">
            <button
              type="submit"
              className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg shadow-sm transition-colors cursor-pointer flex-1"
            >
              {isEditing ? 'Update Job Posting' : formData.status === 'draft' ? 'Save as Draft' : 'Post Job'}
            </button>
            <button
              type="button"
              onClick={() => navigate('/placement/jobs')}
              className="px-5 py-2.5 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg transition-colors cursor-pointer"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default JobForm;