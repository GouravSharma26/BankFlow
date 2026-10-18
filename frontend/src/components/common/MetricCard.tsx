import React from 'react';
import clsx from 'clsx';
import { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  currency?: string;
  icon?: LucideIcon;
  iconColor?: string;
  iconBg?: string;
  badge?: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtitle,
  currency,
  icon: Icon,
  iconColor = 'text-blue-600',
  iconBg = 'bg-blue-50',
  badge,
  footer,
  className,
}) => {
  return (
    <div
      className={clsx(
        'bg-white rounded-xl border border-slate-200 p-5 shadow-sm hover:shadow transition-shadow',
        className
      )}
    >
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{title}</p>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-slate-900 tracking-tight font-sans">
              {value}
            </span>
            {currency && (
              <span className="text-xs font-semibold text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200">
                {currency}
              </span>
            )}
          </div>
        </div>

        {Icon && (
          <div className={clsx('p-2.5 rounded-lg flex items-center justify-center', iconBg)}>
            <Icon className={clsx('w-5 h-5', iconColor)} />
          </div>
        )}
      </div>

      {(subtitle || badge) && (
        <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
          <span>{subtitle}</span>
          {badge}
        </div>
      )}

      {footer && <div className="mt-2">{footer}</div>}
    </div>
  );
};
