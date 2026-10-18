import React from 'react';
import { AlertTriangle, Power } from 'lucide-react';
import { useDashboard } from '../../context/DashboardContext';

export const DemoBanner: React.FC = () => {
  const { isDemoMode, setDemoMode, refreshHealth } = useDashboard();

  if (!isDemoMode) {
    return null;
  }

  return (
    <div
      className="bg-amber-500 text-amber-950 px-4 py-2 text-xs font-medium flex items-center justify-between border-b border-amber-600 shadow-sm"
      role="status"
      aria-label="Demo Data Mode Active"
    >
      <div className="flex items-center space-x-2">
        <span className="flex items-center justify-center bg-amber-900 text-amber-100 px-2 py-0.5 rounded font-bold uppercase tracking-wider text-[10px]">
          <AlertTriangle className="w-3 h-3 mr-1 text-amber-300" />
          DEMO DATA
        </span>
        <span className="font-semibold text-amber-950">
          Showing deterministic synthetic preview fixtures.
        </span>
        <span className="hidden md:inline text-amber-900">
          Metrics are generated client-side and not queried from your local PostgreSQL warehouse.
        </span>
      </div>

      <button
        onClick={() => {
          setDemoMode(false);
          refreshHealth();
        }}
        className="inline-flex items-center text-xs bg-amber-900 hover:bg-amber-950 text-amber-100 px-2.5 py-1 rounded font-medium transition-colors shadow-sm"
        title="Switch back to Connected Mode (Live API)"
      >
        <Power className="w-3 h-3 mr-1.5" />
        Connect to Live API
      </button>
    </div>
  );
};
