import React, { useState } from 'react';
import { ChevronDown, ChevronUp, AlertCircle, CheckCircle, Clock } from 'lucide-react';

const ResumeSuggestions = ({ suggestions = [] }) => {
  const [expanded, setExpanded] = useState(true);

  const getPriorityColor = (priority) => {
    switch (priority?.toLowerCase()) {
      case 'high': return 'border-red-400 bg-red-50';
      case 'medium': return 'border-yellow-400 bg-yellow-50';
      case 'low': return 'border-blue-400 bg-blue-50';
      default: return 'border-gray-300 bg-gray-50';
    }
  };

  const getPriorityIcon = (priority) => {
    switch (priority?.toLowerCase()) {
      case 'high': return <AlertCircle className="w-5 h-5 text-red-500" />;
      case 'medium': return <Clock className="w-5 h-5 text-yellow-500" />;
      case 'low': return <CheckCircle className="w-5 h-5 text-blue-500" />;
      default: return <AlertCircle className="w-5 h-5 text-gray-500" />;
    }
  };

  const getPriorityLabel = (priority) => {
    switch (priority?.toLowerCase()) {
      case 'high': return 'High Priority';
      case 'medium': return 'Medium Priority';
      case 'low': return 'Low Priority';
      default: return 'Suggestion';
    }
  };

  if (!suggestions || suggestions.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="text-center py-8">
          <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-3" />
          <h3 className="text-lg font-semibold text-gray-800">No Suggestions Needed</h3>
          <p className="text-gray-500">Your resume looks great! Keep up the good work.</p>
        </div>
      </div>
    );
  }

  const highPriority = suggestions.filter(s => s.priority === 'high');
  const mediumPriority = suggestions.filter(s => s.priority === 'medium');
  const lowPriority = suggestions.filter(s => s.priority === 'low');

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <div 
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div>
          <h3 className="text-lg font-semibold text-gray-800">💡 Improvement Suggestions</h3>
          <p className="text-sm text-gray-500">
            {suggestions.length} suggestions to improve your resume
          </p>
        </div>
        {expanded ? (
          <ChevronUp className="w-5 h-5 text-gray-400" />
        ) : (
          <ChevronDown className="w-5 h-5 text-gray-400" />
        )}
      </div>

      {expanded && (
        <div className="mt-4 space-y-3">
          {/* High Priority */}
          {highPriority.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-red-600 mb-2 flex items-center gap-2">
                <AlertCircle className="w-4 h-4" />
                High Priority ({highPriority.length})
              </h4>
              {highPriority.map((suggestion, index) => (
                <SuggestionCard key={index} suggestion={suggestion} />
              ))}
            </div>
          )}

          {/* Medium Priority */}
          {mediumPriority.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-yellow-600 mb-2 flex items-center gap-2">
                <Clock className="w-4 h-4" />
                Medium Priority ({mediumPriority.length})
              </h4>
              {mediumPriority.map((suggestion, index) => (
                <SuggestionCard key={index} suggestion={suggestion} />
              ))}
            </div>
          )}

          {/* Low Priority */}
          {lowPriority.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-blue-600 mb-2 flex items-center gap-2">
                <CheckCircle className="w-4 h-4" />
                Low Priority ({lowPriority.length})
              </h4>
              {lowPriority.map((suggestion, index) => (
                <SuggestionCard key={index} suggestion={suggestion} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const SuggestionCard = ({ suggestion }) => {
  const getCategoryIcon = (category) => {
    const icons = {
      skills: '💻',
      education: '🎓',
      experience: '💼',
      projects: '🚀',
      certifications: '📜',
      format: '📋',
    };
    return icons[category?.toLowerCase()] || '💡';
  };

  return (
    <div className={`
      p-3 rounded-lg border-l-4 transition-all
      ${suggestion.priority === 'high' ? 'border-red-400 bg-red-50' :
        suggestion.priority === 'medium' ? 'border-yellow-400 bg-yellow-50' :
        'border-blue-400 bg-blue-50'}
    `}>
      <div className="flex items-start gap-3">
        <span className="text-lg">{getCategoryIcon(suggestion.category)}</span>
        <div className="flex-1">
          <p className="text-sm text-gray-800">{suggestion.message}</p>
          {suggestion.impact && (
            <p className="text-xs text-gray-500 mt-1">
              Impact: {suggestion.impact}
            </p>
          )}
          <div className="flex items-center gap-3 mt-1">
            <span className={`
              text-xs px-2 py-0.5 rounded-full font-medium
              ${suggestion.priority === 'high' ? 'bg-red-200 text-red-700' :
                suggestion.priority === 'medium' ? 'bg-yellow-200 text-yellow-700' :
                'bg-blue-200 text-blue-700'}
            `}>
              {suggestion.priority}
            </span>
            <span className="text-xs text-gray-400 capitalize">
              {suggestion.category}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ResumeSuggestions;