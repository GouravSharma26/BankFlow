import React from 'react';
import {
  RefreshCw,
  Coins,
  Radio,
  Zap,
} from 'lucide-react';
import { useDashboard } from '../../context/DashboardContext';
import { Badge } from '../common/Badge';

interface HeaderProps {
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export const Header: React.FC<HeaderProps> = ({ onRefresh, isRefreshing = false }) => {
  const {
    selectedCurrency,
    setSelectedCurrency,
    availableCurrencies,
    isDemoMode,
    setDemoMode,
    apiHealth,
    healthLoading,
    healthError,
    refreshHealth,
    apiBaseUrl,
  } = useDashboard();

  const handleToggleMode = () => {
    const nextMode = !isDemoMode;
    setDemoMode(nextMode);
    refreshHealth();
    if (onRefresh) {
      onRefresh();
    }
  };

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-20 px-6 py-3.5 flex items-center justify-between shadow-xs">
      {/* Title & Context */}
      <div className="flex items-center space-x-3">
        <div>
          <h1 className="text-lg font-bold text-slate-900 tracking-tight leading-tight flex items-center gap-2">
            BankFlow Analytics
            <span className="text-[11px] font-semibold text-blue-700 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded-full">
              Warehouse Console
            </span>
          </h1>
          <p className="text-xs text-slate-500 hidden sm:block">
            Batch ETL & Dimensional Warehouse Intelligence
          </p>
        </div>
      </div>

      {/* Right Controls: Mode Toggle, Currency Selector, API Status, Refresh */}
      <div className="flex items-center space-x-3">
        {/* Currency Selector */}
        <div className="flex items-center space-x-1.5 bg-slate-50 border border-slate-200 px-2.5 py-1.5 rounded-lg">
          <Coins className="w-3.5 h-3.5 text-slate-500" />
          <label htmlFor="currency-select" className="text-xs font-medium text-slate-600 sr-only">
            Reporting Currency
          </label>
          <select
            id="currency-select"
            value={selectedCurrency}
            onChange={(e) => setSelectedCurrency(e.target.value)}
            className="text-xs font-semibold text-slate-800 bg-transparent border-none outline-hidden cursor-pointer pr-1"
            title="Filter financial analytics by currency"
          >
            {availableCurrencies.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        {/* Operating Mode Selector / Toggle */}
        <button
          onClick={handleToggleMode}
          className={`inline-flex items-center px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
            isDemoMode
              ? 'bg-amber-50 text-amber-900 border-amber-300 hover:bg-amber-100'
              : 'bg-emerald-50 text-emerald-900 border-emerald-300 hover:bg-emerald-100'
          }`}
          title={isDemoMode ? 'Click to switch to Connected Mode' : 'Click to preview with Demo Data'}
        >
          {isDemoMode ? (
            <>
              <Zap className="w-3.5 h-3.5 mr-1.5 text-amber-600" />
              <span>Demo Mode</span>
            </>
          ) : (
            <>
              <Radio className="w-3.5 h-3.5 mr-1.5 text-emerald-600 animate-pulse" />
              <span>Connected</span>
            </>
          )}
        </button>

        {/* API Health Badge */}
        {!isDemoMode && (
          <div
            className="hidden md:flex items-center text-xs"
            title={`API: ${apiBaseUrl} (${apiHealth?.database || 'disconnected'})`}
          >
            {apiHealth && apiHealth.status === 'healthy' ? (
              <Badge variant="success" size="sm" dot>
                API: Connected
              </Badge>
            ) : healthError ? (
              <Badge variant="danger" size="sm" dot>
                API: Offline
              </Badge>
            ) : (
              <Badge variant="neutral" size="sm" dot>
                {healthLoading ? 'Checking...' : 'API: Ready'}
              </Badge>
            )}
          </div>
        )}

        {/* Refresh Action */}
        <button
          onClick={() => {
            refreshHealth();
            if (onRefresh) onRefresh();
          }}
          disabled={isRefreshing}
          className="p-2 text-slate-600 hover:text-slate-900 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg transition-colors disabled:opacity-50"
          title="Refresh dashboard data"
          aria-label="Refresh data"
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-blue-600' : ''}`} />
        </button>
      </div>
    </header>
  );
};
