import React from 'react';
import {
  LayoutDashboard,
  BarChart3,
  ShieldCheck,
  Activity,
  ReceiptText,
  Database,
  Layers,
} from 'lucide-react';
import { useDashboard, TabType } from '../../context/DashboardContext';

interface NavItem {
  id: TabType;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}

const navItems: NavItem[] = [
  {
    id: 'overview',
    label: 'Overview',
    description: 'Executive KPIs & activity',
    icon: LayoutDashboard,
  },
  {
    id: 'analytics',
    label: 'Transaction Analytics',
    description: 'Volume, mix & channel trends',
    icon: BarChart3,
  },
  {
    id: 'quality',
    label: 'Data Quality',
    description: 'Validation & quarantine inventory',
    icon: ShieldCheck,
  },
  {
    id: 'pipeline',
    label: 'Pipeline Monitoring',
    description: 'Batch health & reconciliation',
    icon: Activity,
  },
  {
    id: 'transactions',
    label: 'Transactions',
    description: 'Conformed dimensional facts',
    icon: ReceiptText,
  },
];

export const Sidebar: React.FC = () => {
  const { currentTab, setCurrentTab } = useDashboard();

  return (
    <aside className="w-64 bg-navy-950 text-slate-300 flex flex-col border-r border-navy-800 flex-shrink-0 select-none min-h-screen">
      {/* Brand Header */}
      <div className="p-5 border-b border-navy-800/80">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-700 via-blue-600 to-cyan-500 flex items-center justify-center text-white shadow-md shadow-blue-900/40">
            <Layers className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white tracking-tight flex items-center gap-1.5">
              BankFlow
              <span className="text-[10px] font-semibold text-blue-400 bg-blue-950/80 border border-blue-800/60 px-1.5 py-0.2 rounded">
                v0.1
              </span>
            </h2>
            <p className="text-[11px] text-slate-400 font-mono tracking-wider">
              DATA WAREHOUSE
            </p>
          </div>
        </div>
      </div>

      {/* Navigation List */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <p className="px-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">
          Analytics & Governance
        </p>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;

          return (
            <button
              key={item.id}
              onClick={() => setCurrentTab(item.id)}
              className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-left transition-all ${
                isActive
                  ? 'bg-blue-600 text-white font-medium shadow-sm shadow-blue-900/40'
                  : 'text-slate-300 hover:bg-navy-900 hover:text-white'
              }`}
            >
              <Icon
                className={`w-4 h-4 flex-shrink-0 ${
                  isActive ? 'text-white' : 'text-slate-400 group-hover:text-slate-200'
                }`}
              />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold leading-tight">{item.label}</p>
                <p
                  className={`text-[10px] truncate ${
                    isActive ? 'text-blue-100' : 'text-slate-500'
                  }`}
                >
                  {item.description}
                </p>
              </div>
            </button>
          );
        })}
      </nav>

      {/* Footer Architecture Notes */}
      <div className="p-4 border-t border-navy-800/80 bg-navy-900/50 space-y-3">
        <div className="space-y-1.5 text-[11px] text-slate-400">
          <div className="flex items-center space-x-2 text-slate-300 font-semibold">
            <Database className="w-3.5 h-3.5 text-blue-400" />
            <span>Architecture Specs</span>
          </div>
          <p className="text-[10px] text-slate-400 leading-relaxed font-sans">
            PostgreSQL 17 Star Schema<br />
            FastAPI Read-Only Reporting<br />
            Strict Currency Segregation
          </p>
        </div>

        <div className="pt-2 border-t border-navy-800 flex items-center justify-between text-[10px] text-slate-500 font-mono">
          <span>PORTFOLIO SIMULATION</span>
          <span className="text-emerald-400 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            SYNTHETIC
          </span>
        </div>
      </div>
    </aside>
  );
};
