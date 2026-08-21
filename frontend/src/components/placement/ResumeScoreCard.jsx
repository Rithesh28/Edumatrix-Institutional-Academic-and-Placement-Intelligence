import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

const ResumeScoreCard = ({ score, breakdown = {}, suggestions = [] }) => {
  const getScoreColor = (score) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getScoreBg = (score) => {
    if (score >= 80) return 'bg-green-100';
    if (score >= 60) return 'bg-yellow-100';
    return 'bg-red-100';
  };

  const getScoreEmoji = (score) => {
    if (score >= 80) return '🌟';
    if (score >= 60) return '📈';
    return '💪';
  };

  const categories = [
    { key: 'skills', label: 'Skills Match', icon: '💻' },
    { key: 'education', label: 'Education', icon: '🎓' },
    { key: 'experience', label: 'Experience', icon: '💼' },
    { key: 'projects', label: 'Projects', icon: '🚀' },
    { key: 'certifications', label: 'Certifications', icon: '📜' },
    { key: 'format', label: 'Resume Format', icon: '📋' },
  ];

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-800 mb-4">ATS Score</h3>
      
      {/* Main Score */}
      <div className="flex items-center gap-6 mb-6">
        <div className="relative">
          <div className="w-24 h-24">
            <svg className="w-24 h-24 transform -rotate-90">
              <circle
                className="text-gray-200"
                strokeWidth="6"
                stroke="currentColor"
                fill="transparent"
                r="36"
                cx="48"
                cy="48"
              />
              <circle
                className={getScoreColor(score || 0)}
                strokeWidth="6"
                strokeDasharray={226.19}
                strokeDashoffset={226.19 * (1 - (score || 0) / 100)}
                strokeLinecap="round"
                stroke="currentColor"
                fill="transparent"
                r="36"
                cx="48"
                cy="48"
              />
            </svg>
            <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 text-center">
              <span className={`text-2xl font-bold ${getScoreColor(score || 0)}`}>
                {Math.round(score || 0)}
              </span>
              <span className="text-xs text-gray-400 block">ATS Score</span>
            </div>
          </div>
        </div>
        
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-2xl">{getScoreEmoji(score || 0)}</span>
            <span className="font-medium text-gray-800">
              {score >= 80 ? 'Excellent Resume!' :
               score >= 60 ? 'Good Resume' :
               score >= 40 ? 'Needs Improvement' :
               'Requires Significant Work'}
            </span>
          </div>
          <p className="text-sm text-gray-500">
            {score >= 80 ? 'Your resume is well-structured and optimized for ATS systems.' :
             score >= 60 ? 'Your resume has good content but could be optimized further.' :
             'Review the suggestions below to improve your resume.'}
          </p>
        </div>
      </div>

      {/* Category Breakdown */}
      <div className="space-y-3">
        {categories.map((cat) => {
          const value = breakdown?.[cat.key] || 0;
          return (
            <div key={cat.key}>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">
                  {cat.icon} {cat.label}
                </span>
                <span className={`font-medium ${getScoreColor(value)}`}>
                  {Math.round(value)}%
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all duration-500 ${
                    value >= 80 ? 'bg-green-500' :
                    value >= 60 ? 'bg-yellow-500' :
                    'bg-red-500'
                  }`}
                  style={{ width: `${value}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Quick Stats */}
      {suggestions.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <div className="flex items-center gap-4 text-sm">
            <span className="text-gray-600">💡 Suggestions:</span>
            <span className="text-red-600 font-medium">
              {suggestions.filter(s => s.priority === 'high').length} High
            </span>
            <span className="text-yellow-600 font-medium">
              {suggestions.filter(s => s.priority === 'medium').length} Medium
            </span>
            <span className="text-blue-600 font-medium">
              {suggestions.filter(s => s.priority === 'low').length} Low
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default ResumeScoreCard;