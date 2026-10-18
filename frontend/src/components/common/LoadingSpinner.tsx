import React from 'react';
import clsx from 'clsx';
import { Loader2 } from 'lucide-react';

interface LoadingSpinnerProps {
  label?: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  fullHeight?: boolean;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  label = 'Loading warehouse analytics...',
  size = 'md',
  className,
  fullHeight = false,
}) => {
  const iconSize = {
    sm: 'w-4 h-4',
    md: 'w-7 h-7',
    lg: 'w-10 h-10',
  }[size];

  return (
    <div
      className={clsx(
        'flex flex-col items-center justify-center text-slate-500',
        fullHeight ? 'min-h-[350px] h-full' : 'py-10',
        className
      )}
    >
      <Loader2 className={clsx('animate-spin text-blue-600 mb-2', iconSize)} />
      {label && <p className="text-xs font-medium text-slate-600 tracking-wide">{label}</p>}
    </div>
  );
};
