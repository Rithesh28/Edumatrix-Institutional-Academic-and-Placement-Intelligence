import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Briefcase, ArrowLeft, Plus, X, Search } from 'lucide-react';
import usePlacementStore from '../../store/placementStore';
import toast from 'react-hot-toast';

const JobForm = () => {
  const navigate = useNavigate();
  const { id } = useParams();
  const { createJobPosting, updateJobPosting, fetchJobPosting, selectedJob, fetchCompanies, companies, isLoading } = usePlacementStore();
  const [formData, setFormData] = useState({
    company_id: '',
    title: '',
    description: '',
    required_skills: [],
    experience_level: '',
    cgpa_criteria: '',
    branch_eligibility: [],
    location: '',
    salary_range: '',
    application_deadline: '',
    drive_date: '',
    status: 'open',
  });
  const [skillInput, setSkillInput] = useState('');
  const [branchInput, setBranchInput] = useState('');
  const [companySearch, setCompanySearch] = useState('');
  const [showCompanySuggestions, setShowCompanySuggestions] = useState(false);
  const [filteredCompanies, setFilteredCompanies] = useState([]);
  const [companyError, setCompanyError] = useState('');
  const searchRef = useRef(null);

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
      
      // Find company name if not provided in response
      let companyNameToUse = companyName;
      if (!companyNameToUse && companyId) {
        const foundCompany = companies.find(c => c.id === companyId);
        companyNameToUse = foundCompany?.name || '';
      }

      setFormData({
        company_id: companyId,
        title: selectedJob.title || '',
        description: selectedJob.description || '',
        required_skills: selectedJob.required_skills || [],
        experience_level: selectedJob.experience_level || '',
        cgpa_criteria: selectedJob.cgpa_criteria || '',
        branch_eligibility: selectedJob.branch_eligibility || [],
        location: selectedJob.location || '',
        salary_range: selectedJob.salary_range || '',
        application_deadline: selectedJob.application_deadline ? selectedJob.application_deadline.slice(0, 16) : '',
        drive_date: selectedJob.drive_date ? selectedJob.drive_date.slice(0, 16) : '',
        status: selectedJob.status || 'open',
      });
      
      // Set company search value
      setCompanySearch(companyNameToUse);
    }
  }, [selectedJob, isEditing, companies]);

  // Filter companies based on search
  useEffect(() => {
    if (companySearch.length > 0) {
      const filtered = companies.filter(c => 
        c.name.toLowerCase().includes(companySearch.toLowerCase()) &&
        c.is_active !== false
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
        cgpa_criteria: formData.cgpa_criteria ? parseFloat(formData.cgpa_criteria) : null,
        required_skills: formData.required_skills || [],
        branch_eligibility: formData.branch_eligibility || [],
      };
      if (isEditing) {
        await updateJobPosting(id, submitData);
        toast.success('Job updated successfully');
      } else {
        await createJobPosting(submitData);
        toast.success('Job posted successfully');
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
    <div className="max-w-3xl mx-auto">
      <button
        onClick={() => navigate('/placement/jobs')}
        className="flex items-center space-x-2 text-gray-600 hover:text-gray-800 mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Jobs</span>
      </button>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center space-x-3 mb-6">
          <div className="p-2 bg-green-100 rounded-lg">
            <Briefcase className="w-6 h-6 text-green-600" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-gray-900">
              {isEditing ? 'Edit Job' : 'Post New Job'}
            </h2>
            <p className="text-sm text-gray-500">
              {isEditing ? 'Update job details' : 'Create a new job posting'}
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Company Search/Auto-suggest */}
          <div ref={searchRef}>
            <label className="block text-sm font-medium text-gray-700 mb-1">
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
                className={`w-full px-3 py-2 pl-10 pr-10 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent ${
                  companyError ? 'border-red-500' : 'border-gray-300'
                }`}
                placeholder="Type to search company..."
              />
              <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
              {companySearch && (
                <button
                  type="button"
                  onClick={handleClearCompany}
                  className="absolute right-3 top-2.5 text-gray-400 hover:text-gray-600"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
            
            {companyError && (
              <p className="mt-1 text-sm text-red-600">{companyError}</p>
            )}

            {/* Suggestions Dropdown */}
            {showCompanySuggestions && (
              <div className="absolute z-10 w-full mt-1 bg-white rounded-lg shadow-lg border border-gray-200 max-h-60 overflow-y-auto">
                {filteredCompanies.length > 0 ? (
                  filteredCompanies.map((company) => (
                    <button
                      key={company.id}
                      type="button"
                      onClick={() => handleCompanySelect(company)}
                      className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-indigo-50 flex items-center justify-between border-b border-gray-100 last:border-0"
                    >
                      <span>{company.name}</span>
                      {company.industry && (
                        <span className="text-xs text-gray-400">{company.industry}</span>
                      )}
                    </button>
                  ))
                ) : (
                  <div className="px-4 py-3 text-sm text-gray-500">
                    No companies found. 
                    <button
                      type="button"
                      onClick={() => navigate('/placement/companies/add')}
                      className="ml-2 text-indigo-600 hover:text-indigo-800 font-medium"
                    >
                      Add new company
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Selected company badge */}
            {formData.company_id && (
              <div className="mt-1 inline-flex items-center px-2 py-1 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">
                ✅ Selected: {companySearch}
              </div>
            )}
          </div>

          {/* Job Title */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Job Title *
            </label>
            <input
              type="text"
              name="title"
              value={formData.title}
              onChange={handleChange}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              placeholder="e.g., Software Engineer"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              name="description"
              value={formData.description}
              onChange={handleChange}
              rows="4"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              placeholder="Job description, responsibilities, requirements..."
            />
          </div>

          {/* Required Skills */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Required Skills
            </label>
            <div className="flex space-x-2">
              <input
                type="text"
                value={skillInput}
                onChange={(e) => setSkillInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleAddSkill()}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                placeholder="Add a skill (e.g., Python)"
              />
              <button
                type="button"
                onClick={handleAddSkill}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
            <div className="flex flex-wrap gap-2 mt-2">
              {formData.required_skills.map((skill) => (
                <span
                  key={skill}
                  className="inline-flex items-center px-2 py-1 bg-indigo-100 text-indigo-700 rounded-full text-sm"
                >
                  {skill}
                  <button
                    type="button"
                    onClick={() => handleRemoveSkill(skill)}
                    className="ml-1 text-indigo-500 hover:text-indigo-700"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          </div>

          {/* Experience & CGPA */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Experience Level
              </label>
              <select
                name="experience_level"
                value={formData.experience_level}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              >
                <option value="">Select</option>
                <option value="fresher">Fresher</option>
                <option value="0-1">0-1 years</option>
                <option value="1-3">1-3 years</option>
                <option value="3-5">3-5 years</option>
                <option value="5+">5+ years</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                CGPA Criteria
              </label>
              <input
                type="number"
                name="cgpa_criteria"
                value={formData.cgpa_criteria}
                onChange={handleChange}
                step="0.1"
                min="0"
                max="10"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                placeholder="e.g., 7.5"
              />
            </div>
          </div>

          {/* Eligible Branches */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Eligible Branches
            </label>
            <div className="flex space-x-2">
              <input
                type="text"
                value={branchInput}
                onChange={(e) => setBranchInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleAddBranch()}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                placeholder="Add a branch (e.g., CSE)"
              />
              <button
                type="button"
                onClick={handleAddBranch}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
            <div className="flex flex-wrap gap-2 mt-2">
              {formData.branch_eligibility.map((branch) => (
                <span
                  key={branch}
                  className="inline-flex items-center px-2 py-1 bg-green-100 text-green-700 rounded-full text-sm"
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
            </div>
          </div>

          {/* Location & Salary */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Location
              </label>
              <input
                type="text"
                name="location"
                value={formData.location}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                placeholder="City, State"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Salary Range
              </label>
              <input
                type="text"
                name="salary_range"
                value={formData.salary_range}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                placeholder="e.g., ₹8-12 LPA"
              />
            </div>
          </div>

          {/* Deadlines */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Application Deadline
              </label>
              <input
                type="datetime-local"
                name="application_deadline"
                value={formData.application_deadline}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Drive Date
              </label>
              <input
                type="datetime-local"
                name="drive_date"
                value={formData.drive_date}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>
          </div>

          {/* Status */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Status
            </label>
            <select
              name="status"
              value={formData.status}
              onChange={handleChange}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            >
              <option value="open">Open</option>
              <option value="draft">Draft</option>
              <option value="closed">Closed</option>
            </select>
          </div>

          {/* Buttons */}
          <div className="flex space-x-3 pt-4 border-t border-gray-200">
            <button
              type="submit"
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 flex-1"
            >
              {isEditing ? 'Update Job' : 'Post Job'}
            </button>
            <button
              type="button"
              onClick={() => navigate('/placement/jobs')}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
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