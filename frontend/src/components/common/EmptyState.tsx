import React from 'react';
import { FilterX } from 'lucide-react';

export interface EmptyStateProps {
  title?: string;
  description?: string;
  message?: string;
  onClearFilters?: () => void;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = 'No records found',
  description,
  message,
  onClearFilters,
  className = '',
}) => {
  const displayText = message || description || 'No transaction or analytics data matched the specified filters or date range.';

  return (
    <div
      className={`flex flex-col items-center justify-center p-8 text-center bg-white dark:bg-navy-900 border border-slate-200 dark:border-navy-800 rounded-xl ${className}`}
    >
      <div className="p-3 bg-slate-100 dark:bg-navy-950 rounded-full text-slate-500 mb-3">
        <FilterX className="w-6 h-6" />
      </div>
      <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">{title}</h3>
      <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-sm">{displayText}</p>
      {onClearFilters && (
        <button
          onClick={onClearFilters}
          className="mt-4 px-3 py-1.5 text-xs font-medium text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-navy-800 border border-blue-200 dark:border-navy-700 rounded-lg hover:bg-blue-100 dark:hover:bg-navy-700 transition-colors"
        >
          Reset All Filters
        </button>
      )}
    </div>
  );
};
