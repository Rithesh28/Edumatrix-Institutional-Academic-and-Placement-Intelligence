import React, { useState, useEffect } from 'react';
import { Loader2, User, Mail, Phone, Briefcase, GraduationCap, Code, FolderOpen, Award } from 'lucide-react';
import resumeService from '../../services/resumeService';
import ResumeScoreCard from './ResumeScoreCard';
import ResumeSuggestions from './ResumeSuggestions';
import toast from 'react-hot-toast';

const ResumeDetail = ({ resumeId, onBack }) => {
  const [resume, setResume] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scoreData, setScoreData] = useState(null);

  useEffect(() => {
    if (resumeId) {
      fetchResumeDetails();
    }
  }, [resumeId]);

  const fetchResumeDetails = async () => {
    setLoading(true);
    try {
      const [resumeData, scoreData] = await Promise.all([
        resumeService.getResume(resumeId),
        resumeService.getAtsScore(resumeId).catch(() => null)
      ]);
      
      setResume(resumeData);
      setScoreData(scoreData);
    } catch (error) {
      console.error('Error fetching resume details:', error);
      toast.error('Failed to load resume details');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 text-indigo-600 animate-spin" />
      </div>
    );
  }

  if (!resume) {
    return (
      <div className="text-center py-20">
        <p className="text-gray-500">Resume not found</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Personal Info */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-gray-800">
            {resume.name || 'Unnamed Resume'}
          </h2>
          <span className={`px-3 py-1 rounded-full text-sm font-medium ${
            resume.status === 'completed' ? 'bg-green-100 text-green-800' :
            resume.status === 'processing' ? 'bg-yellow-100 text-yellow-800' :
            resume.status === 'pending' ? 'bg-blue-100 text-blue-800' :
            'bg-red-100 text-red-800'
          }`}>
            {resume.status || 'pending'}
          </span>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="flex items-center gap-3 text-gray-600">
            <User className="w-5 h-5 text-indigo-500" />
            <span>{resume.name || 'N/A'}</span>
          </div>
          {resume.email && (
            <div className="flex items-center gap-3 text-gray-600">
              <Mail className="w-5 h-5 text-indigo-500" />
              <span>{resume.email}</span>
            </div>
          )}
          {resume.phone && (
            <div className="flex items-center gap-3 text-gray-600">
              <Phone className="w-5 h-5 text-indigo-500" />
              <span>{resume.phone}</span>
            </div>
          )}
        </div>
      </div>

      {/* Score & Suggestions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <ResumeScoreCard 
            score={scoreData?.ats_score || resume.ats_score}
            breakdown={{
              skills: scoreData?.skill_match || 0,
              education: scoreData?.education_match || 0,
              experience: scoreData?.experience_match || 0,
              projects: scoreData?.project_match || 0,
              certifications: scoreData?.certification_match || 0,
              format: scoreData?.format_score || 0,
            }}
            suggestions={resume.suggestions || []}
          />
        </div>
        <div className="lg:col-span-1">
          <ResumeSuggestions suggestions={resume.suggestions || []} />
        </div>
      </div>

      {/* Detailed Sections */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Skills */}
        {resume.skills && resume.skills.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 className="font-semibold text-gray-800 mb-3 flex items-center gap-2">
              <Code className="w-5 h-5 text-indigo-500" />
              Skills ({resume.skills.length})
            </h3>
            <div className="flex flex-wrap gap-2">
              {resume.skills.map((skill, index) => (
                <span key={index} className="px-3 py-1 bg-indigo-50 text-indigo-700 rounded-full text-sm">
                  {skill}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Education */}
        {resume.education && resume.education.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 className="font-semibold text-gray-800 mb-3 flex items-center gap-2">
              <GraduationCap className="w-5 h-5 text-indigo-500" />
              Education
            </h3>
            {resume.education.map((edu, index) => (
              <div key={index} className="border-b border-gray-100 last:border-0 py-2">
                <p className="font-medium text-gray-800">
                  {edu.degree || 'N/A'}
                </p>
                {edu.institution && (
                  <p className="text-sm text-gray-500">{edu.institution}</p>
                )}
                {(edu.start_year || edu.end_year) && (
                  <p className="text-sm text-gray-400">
                    {edu.start_year} - {edu.end_year}
                  </p>
                )}
                {edu.cgpa && (
                  <p className="text-sm text-gray-500">CGPA: {edu.cgpa}</p>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Experience */}
        {resume.experience && resume.experience.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 className="font-semibold text-gray-800 mb-3 flex items-center gap-2">
              <Briefcase className="w-5 h-5 text-indigo-500" />
              Experience
            </h3>
            {resume.experience.map((exp, index) => (
              <div key={index} className="border-b border-gray-100 last:border-0 py-2">
                <p className="font-medium text-gray-800">{exp.title || 'N/A'}</p>
                {exp.company && (
                  <p className="text-sm text-gray-500">{exp.company}</p>
                )}
                {(exp.start_date || exp.end_date) && (
                  <p className="text-sm text-gray-400">
                    {exp.start_date} - {exp.end_date || 'Present'}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Projects */}
        {resume.projects && resume.projects.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 className="font-semibold text-gray-800 mb-3 flex items-center gap-2">
              <FolderOpen className="w-5 h-5 text-indigo-500" />
              Projects
            </h3>
            {resume.projects.map((project, index) => (
              <div key={index} className="border-b border-gray-100 last:border-0 py-2">
                <p className="font-medium text-gray-800">{project.name || 'N/A'}</p>
                {project.description && (
                  <p className="text-sm text-gray-500">{project.description}</p>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Certifications */}
        {resume.certifications && resume.certifications.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 className="font-semibold text-gray-800 mb-3 flex items-center gap-2">
              <Award className="w-5 h-5 text-indigo-500" />
              Certifications
            </h3>
            {resume.certifications.map((cert, index) => (
              <div key={index} className="border-b border-gray-100 last:border-0 py-2">
                <p className="font-medium text-gray-800">{cert.name || 'N/A'}</p>
                {cert.issuer && (
                  <p className="text-sm text-gray-500">{cert.issuer}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ResumeDetail;