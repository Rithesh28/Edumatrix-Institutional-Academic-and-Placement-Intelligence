import React from 'react';
import { CheckCircle, XCircle, AlertCircle } from 'lucide-react';

const EligibilityBadge = ({ isEligible, matchScore, size = 'md' }) => {
  const sizes = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-sm px-3 py-1',
    lg: 'text-base px-4 py-2',
  };

  const iconSizes = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5',
  };

  if (isEligible) {
    return (
      <span className={`inline-flex items-center space-x-1 bg-green-100 text-green-700 rounded-full ${sizes[size]}`}>
        <CheckCircle className={iconSizes[size]} />
        <span>Eligible</span>
        {matchScore !== undefined && (
          <span className="font-medium">({matchScore.toFixed(1)}%)</span>
        )}
      </span>
    );
  }

  return (
    <span className={`inline-flex items-center space-x-1 bg-red-100 text-red-700 rounded-full ${sizes[size]}`}>
      <XCircle className={iconSizes[size]} />
      <span>Not Eligible</span>
      {matchScore !== undefined && (
        <span className="font-medium">({matchScore.toFixed(1)}%)</span>
      )}
    </span>
  );
};

export default EligibilityBadge;