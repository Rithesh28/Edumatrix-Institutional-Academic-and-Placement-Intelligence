import React from 'react';

const StatsCard = ({ title, value, icon, color = 'blue', subtitle }) => {
  const colors = {
    blue: 'bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400',
    green: 'bg-green-50 dark:bg-green-950/60 text-green-600 dark:text-green-400',
    purple: 'bg-purple-50 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400',
    orange: 'bg-orange-50 dark:bg-orange-950/60 text-orange-600 dark:text-orange-400',
    red: 'bg-red-50 dark:bg-red-950/60 text-red-600 dark:text-red-400',
    indigo: 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400',
  };

  return (
    <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800 p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{title}</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">{value}</p>
          {subtitle && (
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">{subtitle}</p>
          )}
        </div>
        <div className={`p-3 rounded-full ${colors[color] || colors.blue}`}>
          {icon}
        </div>
      </div>
    </div>
  );
};

export default StatsCard;