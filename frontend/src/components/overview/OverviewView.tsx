import React, { useEffect, useState, useCallback } from 'react';
import {
  DollarSign,
  CheckCircle2,
  Users,
  CreditCard,
  ShieldAlert,
  Boxes,
  Calendar,
  Layers,
  ArrowRight,
} from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import { useDashboard } from '../../context/DashboardContext';
import { BankFlowApi, ApiError } from '../../services/api';
import { OverviewResponse, DailyTrendItem, BatchExecutionItem } from '../../services/types';
import { MetricCard } from '../common/MetricCard';
import { Badge } from '../common/Badge';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { ErrorAlert } from '../common/ErrorAlert';

export const OverviewView: React.FC = () => {
  const { selectedCurrency, isDemoMode, setAvailableCurrencies, setCurrentTab } = useDashboard();

  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [dailyData, setDailyData] = useState<DailyTrendItem[]>([]);
  const [recentBatches, setRecentBatches] = useState<BatchExecutionItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<ApiError | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ovRes, dailyRes, batchRes] = await Promise.all([
        BankFlowApi.getOverview(selectedCurrency, isDemoMode),
        BankFlowApi.getDaily({ currency: selectedCurrency, limit: 14 }, isDemoMode),
        BankFlowApi.getBatches({ limit: 5 }, isDemoMode),
      ]);

      setOverview(ovRes);
      setDailyData(dailyRes);
      setRecentBatches(batchRes);

      if (ovRes.currencies && ovRes.currencies.length > 0) {
        setAvailableCurrencies(ovRes.currencies);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err);
      } else {
        setError(new ApiError(err instanceof Error ? err.message : 'Failed to load overview data'));
      }
    } finally {
      setLoading(false);
    }
  }, [selectedCurrency, isDemoMode, setAvailableCurrencies]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loading) {
    return <LoadingSpinner label="Loading BankFlow overview and metrics..." fullHeight />;
  }

  if (error) {
    return (
      <ErrorAlert
        title="Failed to Load Overview Data"
        message={error.message}
        statusCode={error.statusCode}
        onRetry={loadData}
      />
    );
  }

  const currencyMetrics = overview?.metrics_by_currency.find(
    (m) => m.currency === selectedCurrency
  ) || overview?.metrics_by_currency[0];

  const formatAmount = (val?: string) => {
    if (!val) return '0.00';
    const num = parseFloat(val);
    return isNaN(num) ? val : num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  return (
    <div className="space-y-6">
      {/* Top Banner Context */}
      <div className="bg-gradient-to-r from-blue-900 via-navy-900 to-navy-950 text-white rounded-xl p-6 shadow-md border border-navy-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 mb-1">
            <span className="text-xs font-semibold uppercase tracking-wider text-blue-300">
              Executive Warehouse Briefing
            </span>
            <span className="text-navy-700">•</span>
            <span className="text-xs text-slate-300">Currency: {selectedCurrency}</span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-white">
            Portfolio Health & Ingestion Pipeline
          </h2>
          <p className="text-xs text-slate-300 mt-1 max-w-2xl">
            Real-time analytical reporting from the PostgreSQL dimensional warehouse. Transaction amounts represent gross positive event values. Grouped strictly by currency.
          </p>
        </div>

        {overview && (
          <div className="flex items-center space-x-3 bg-navy-950/60 p-3 rounded-lg border border-navy-800 text-xs">
            <Calendar className="w-4 h-4 text-blue-400" />
            <div>
              <p className="text-[10px] text-slate-400 uppercase font-mono">Date Horizon</p>
              <p className="font-semibold text-slate-200">
                {overview.earliest_date || 'N/A'} → {overview.latest_date || 'N/A'}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Gross Transaction Value"
          value={`$${formatAmount(currencyMetrics?.gross_transaction_amount)}`}
          currency={selectedCurrency}
          subtitle={`Completed: $${formatAmount(currencyMetrics?.completed_gross_amount)}`}
          icon={DollarSign}
          iconColor="text-blue-600"
          iconBg="bg-blue-50"
          badge={
            <Badge variant="brand" size="sm">
              Event Gross
            </Badge>
          }
        />

        <MetricCard
          title="Total Transactions"
          value={currencyMetrics?.total_transactions.toLocaleString() ?? '0'}
          currency={selectedCurrency}
          subtitle={`Completed: ${currencyMetrics?.completed_transactions.toLocaleString() ?? '0'}`}
          icon={CreditCard}
          iconColor="text-indigo-600"
          iconBg="bg-indigo-50"
          badge={
            <Badge variant="success" size="sm" dot>
              {currencyMetrics?.acceptance_rate_pct ?? '0.00'}% Valid
            </Badge>
          }
        />

        <MetricCard
          title="Acceptance Rate"
          value={`${currencyMetrics?.acceptance_rate_pct ?? '0.00'}%`}
          subtitle="Contract valid facts"
          icon={CheckCircle2}
          iconColor="text-emerald-600"
          iconBg="bg-emerald-50"
          badge={
            <Badge variant="success" size="sm">
              Conformed
            </Badge>
          }
        />

        <MetricCard
          title="Active Accounts & Customers"
          value={`${currencyMetrics?.active_accounts ?? 0} Acc`}
          currency={selectedCurrency}
          subtitle={`Servicing ${currencyMetrics?.active_customers ?? 0} distinct customers`}
          icon={Users}
          iconColor="text-cyan-600"
          iconBg="bg-cyan-50"
        />
      </div>

      {/* Monitoring & Quality Summary Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Total Batches
            </p>
            <p className="text-2xl font-bold text-slate-900 mt-1">
              {overview?.total_batches ?? 0}
            </p>
            <p className="text-xs text-slate-500 mt-1">Recorded in monitoring schema</p>
          </div>
          <div className="p-3 bg-slate-100 rounded-xl text-slate-600">
            <Boxes className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Latest Batch Status
            </p>
            <div className="mt-1">
              <Badge
                variant={
                  overview?.latest_batch_status === 'SUCCEEDED'
                    ? 'success'
                    : overview?.latest_batch_status === 'SUCCEEDED_WITH_REJECTIONS'
                    ? 'warning'
                    : 'danger'
                }
                size="md"
                dot
              >
                {overview?.latest_batch_status || 'NONE'}
              </Badge>
            </div>
            <p className="text-xs text-slate-500 mt-1">Atomic transaction load</p>
          </div>
          <div className="p-3 bg-blue-50 rounded-xl text-blue-600">
            <Layers className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Quarantine Inventory
            </p>
            <p className="text-2xl font-bold text-rose-700 mt-1">
              {overview?.total_quarantined_records ?? 0}
            </p>
            <p className="text-xs text-slate-500 mt-1">
              {overview?.total_quality_issues ?? 0} distinct issues flagged
            </p>
          </div>
          <div className="p-3 bg-rose-50 rounded-xl text-rose-600">
            <ShieldAlert className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Main Analytics Chart: Daily Activity Trend */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 pb-4 border-b border-slate-100 gap-2">
          <div>
            <h3 className="text-base font-bold text-slate-900 tracking-tight">
              Daily Transaction Activity & Value Trend
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Daily gross transaction volume and event counts in {selectedCurrency}
            </p>
          </div>

          <button
            onClick={() => setCurrentTab('analytics')}
            className="inline-flex items-center text-xs font-medium text-blue-600 hover:text-blue-800"
          >
            Deep Dive Analytics <ArrowRight className="w-3.5 h-3.5 ml-1" />
          </button>
        </div>

        {dailyData.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-500">
            No daily transactions recorded for {selectedCurrency}.
          </div>
        ) : (
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={dailyData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorAmount" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#2563eb" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#2563eb" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis
                  dataKey="reporting_date"
                  tick={{ fontSize: 11, fill: '#64748b' }}
                  tickLine={false}
                  axisLine={{ stroke: '#e2e8f0' }}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: '#64748b' }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(val) => `$${val}`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#ffffff',
                    borderColor: '#e2e8f0',
                    borderRadius: '8px',
                    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                    fontSize: '12px',
                  }}
                  formatter={(val: unknown) => [
                    `$${parseFloat(String(val) || '0').toLocaleString('en-US', { minimumFractionDigits: 2 })}`,
                    'Gross Value',
                  ]}
                  labelFormatter={(label) => `Date: ${label}`}
                />
                <Area
                  type="monotone"
                  dataKey="gross_transaction_amount"
                  stroke="#2563eb"
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#colorAmount)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Recent Pipeline Activity Section */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs">
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
          <div>
            <h3 className="text-base font-bold text-slate-900 tracking-tight">
              Recent Batch Ingestion & Reconciliation
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Latest batch executions from <code className="text-xs font-mono bg-slate-100 px-1 py-0.5 rounded">monitoring.etl_batch_runs</code>
            </p>
          </div>
          <button
            onClick={() => setCurrentTab('pipeline')}
            className="text-xs font-medium text-blue-600 hover:text-blue-800 inline-flex items-center"
          >
            View All Batches <ArrowRight className="w-3.5 h-3.5 ml-1" />
          </button>
        </div>

        {recentBatches.length === 0 ? (
          <p className="text-xs text-slate-500 py-4 text-center">No batch runs recorded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left text-slate-600">
              <thead className="bg-slate-50 text-slate-500 uppercase font-semibold text-[10px] tracking-wider border-b border-slate-200">
                <tr>
                  <th className="py-2.5 px-3">Batch ID</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Reconciliation</th>
                  <th className="py-2.5 px-3 text-right">Staged</th>
                  <th className="py-2.5 px-3 text-right">Valid</th>
                  <th className="py-2.5 px-3 text-right">Rejected</th>
                  <th className="py-2.5 px-3 text-right">Inserted</th>
                  <th className="py-2.5 px-3 text-right">Skipped</th>
                  <th className="py-2.5 px-3 text-right">Duration</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {recentBatches.map((b) => (
                  <tr key={b.batch_id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3 px-3 font-mono font-medium text-slate-900">
                      {b.batch_id}
                    </td>
                    <td className="py-3 px-3">
                      <Badge
                        variant={
                          b.status === 'SUCCEEDED'
                            ? 'success'
                            : b.status === 'SUCCEEDED_WITH_REJECTIONS'
                            ? 'warning'
                            : 'danger'
                        }
                        size="sm"
                        dot
                      >
                        {b.status}
                      </Badge>
                    </td>
                    <td className="py-3 px-3">
                      <Badge
                        variant={b.reconciliation_status === 'RECONCILED' ? 'success' : 'danger'}
                        size="sm"
                      >
                        {b.reconciliation_status || 'UNKNOWN'}
                      </Badge>
                    </td>
                    <td className="py-3 px-3 text-right font-mono">{b.records_staged}</td>
                    <td className="py-3 px-3 text-right font-mono text-emerald-700 font-semibold">
                      {b.records_valid}
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-rose-700 font-semibold">
                      {b.records_rejected}
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-blue-700 font-semibold">
                      {b.records_inserted}
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-slate-500">
                      {b.records_skipped}
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-slate-500">
                      {b.duration_seconds !== null ? `${b.duration_seconds.toFixed(2)}s` : 'N/A'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
