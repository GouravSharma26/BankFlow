import React, { useEffect, useState, useCallback } from 'react';
import {
  TrendingUp,
  ArrowDownRight,
  PieChart as PieIcon,
  Building2,
  Calendar,
  Filter,
  RefreshCw,
} from 'lucide-react';
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  BarChart,
} from 'recharts';
import { useDashboard } from '../../context/DashboardContext';
import { BankFlowApi, ApiError } from '../../services/api';
import {
  DailyTrendItem,
  DepositWithdrawalItem,
  BranchChannelItem,
  TypeMixItem,
} from '../../services/types';
import { Badge } from '../common/Badge';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { ErrorAlert } from '../common/ErrorAlert';
import { EmptyState } from '../common/EmptyState';

const TYPE_COLORS: Record<string, string> = {
  DEPOSIT: '#10b981', // emerald
  WITHDRAWAL: '#f59e0b', // amber
  TRANSFER: '#3b82f6', // blue
  PAYMENT: '#8b5cf6', // purple
  FEE: '#ef4444', // red
  REVERSAL: '#ec4899', // pink
};

export const AnalyticsView: React.FC = () => {
  const { selectedCurrency, setSelectedCurrency, availableCurrencies, isDemoMode } = useDashboard();

  // Filters
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [selectedChannel, setSelectedChannel] = useState<string>('');

  // Data states
  const [dailyData, setDailyData] = useState<DailyTrendItem[]>([]);
  const [depWithData, setDepWithData] = useState<DepositWithdrawalItem[]>([]);
  const [branchData, setBranchData] = useState<BranchChannelItem[]>([]);
  const [typeMixData, setTypeMixData] = useState<TypeMixItem[]>([]);

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<ApiError | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [dailyRes, depWithRes, branchRes, typeRes] = await Promise.all([
        BankFlowApi.getDaily(
          {
            currency: selectedCurrency,
            start_date: startDate || undefined,
            end_date: endDate || undefined,
            limit: 60,
          },
          isDemoMode
        ),
        BankFlowApi.getDepositWithdrawal(
          {
            currency: selectedCurrency,
            start_date: startDate || undefined,
            end_date: endDate || undefined,
            limit: 60,
          },
          isDemoMode
        ),
        BankFlowApi.getBranchChannel(
          {
            currency: selectedCurrency,
            channel: selectedChannel || undefined,
            limit: 50,
          },
          isDemoMode
        ),
        BankFlowApi.getTypeMix(selectedCurrency, isDemoMode),
      ]);

      setDailyData(dailyRes);
      setDepWithData(depWithRes);
      setBranchData(branchRes);
      setTypeMixData(typeRes);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err);
      } else {
        setError(new ApiError(err instanceof Error ? err.message : 'Failed to fetch analytics data'));
      }
    } finally {
      setLoading(false);
    }
  }, [selectedCurrency, startDate, endDate, selectedChannel, isDemoMode]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleResetFilters = () => {
    setStartDate('');
    setEndDate('');
    setSelectedChannel('');
  };

  const formatAmount = (val?: string | number) => {
    if (val === undefined || val === null) return '0.00';
    const num = typeof val === 'string' ? parseFloat(val) : val;
    return isNaN(num) ? String(val) : num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  // Aggregated totals for summary chips
  const totalVolume = dailyData.reduce((acc, d) => acc + d.total_transaction_count, 0);
  const totalGrossAmount = dailyData.reduce((acc, d) => acc + parseFloat(d.gross_transaction_amount || '0'), 0);
  const completedGrossAmount = dailyData.reduce((acc, d) => acc + parseFloat(d.completed_gross_amount || '0'), 0);

  // Pre-process chart data for ComposedChart (volume + gross value)
  const chartDailyData = dailyData.map((d) => ({
    date: d.reporting_date,
    dayName: d.day_name,
    volume: d.total_transaction_count,
    completedVolume: d.completed_transaction_count,
    grossAmount: parseFloat(d.gross_transaction_amount || '0'),
    completedAmount: parseFloat(d.completed_gross_amount || '0'),
  }));

  // Deposit vs withdrawal data for bar comparison
  const depWithChartData = depWithData.map((d) => ({
    date: d.reporting_date,
    depositCount: d.deposit_count,
    withdrawalCount: d.withdrawal_count,
    depositAmount: parseFloat(d.deposit_gross_amount || '0'),
    withdrawalAmount: parseFloat(d.withdrawal_gross_amount || '0'),
    depositShare: parseFloat(d.deposit_value_share_pct || '0'),
    withdrawalShare: parseFloat(d.withdrawal_value_share_pct || '0'),
  }));

  return (
    <div className="space-y-6">
      {/* Top Filter & Currency Control Bar */}
      <div className="bg-white dark:bg-navy-900 rounded-xl p-5 border border-slate-200 dark:border-navy-800 shadow-sm flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-blue-500" />
            Transaction Analytics & Trend Explorer
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Deep-dive into event distributions, currency volumes, deposit ratios, and channel metrics.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Currency Selector */}
          <div className="flex items-center gap-2 bg-slate-50 dark:bg-navy-950 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-navy-800">
            <span className="text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">Currency</span>
            <select
              value={selectedCurrency}
              onChange={(e) => setSelectedCurrency(e.target.value)}
              className="bg-transparent font-bold text-sm text-blue-600 dark:text-blue-400 focus:outline-none cursor-pointer"
            >
              {availableCurrencies.map((c) => (
                <option key={c} value={c} className="bg-white dark:bg-navy-900 text-slate-900 dark:text-white">
                  {c}
                </option>
              ))}
            </select>
          </div>

          {/* Date Range Start */}
          <div className="flex items-center gap-1.5 bg-slate-50 dark:bg-navy-950 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-navy-800">
            <Calendar className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-xs text-slate-400">From:</span>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="bg-transparent text-xs text-slate-800 dark:text-slate-200 focus:outline-none cursor-pointer"
            />
          </div>

          {/* Date Range End */}
          <div className="flex items-center gap-1.5 bg-slate-50 dark:bg-navy-950 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-navy-800">
            <Calendar className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-xs text-slate-400">To:</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="bg-transparent text-xs text-slate-800 dark:text-slate-200 focus:outline-none cursor-pointer"
            />
          </div>

          {/* Channel Filter */}
          <div className="flex items-center gap-1.5 bg-slate-50 dark:bg-navy-950 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-navy-800">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={selectedChannel}
              onChange={(e) => setSelectedChannel(e.target.value)}
              className="bg-transparent text-xs font-medium text-slate-800 dark:text-slate-200 focus:outline-none cursor-pointer"
            >
              <option value="" className="bg-white dark:bg-navy-900">All Channels</option>
              <option value="BRANCH" className="bg-white dark:bg-navy-900">Branch</option>
              <option value="ATM" className="bg-white dark:bg-navy-900">ATM</option>
              <option value="ONLINE" className="bg-white dark:bg-navy-900">Online</option>
              <option value="MOBILE" className="bg-white dark:bg-navy-900">Mobile</option>
            </select>
          </div>

          {/* Reset Filters */}
          {(startDate || endDate || selectedChannel) && (
            <button
              onClick={handleResetFilters}
              className="text-xs text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 underline"
            >
              Reset
            </button>
          )}

          {/* Refresh Action */}
          <button
            onClick={loadData}
            disabled={loading}
            className="p-2 rounded-lg bg-blue-50 dark:bg-navy-800 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-navy-700 transition-colors"
            title="Refresh analytics data"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Loading & Error States */}
      {loading && <LoadingSpinner label="Loading analytics and metric trends..." fullHeight />}

      {error && !loading && (
        <ErrorAlert
          title="Analytics Query Error"
          message={error.message}
          statusCode={error.statusCode}
          onRetry={loadData}
        />
      )}

      {!loading && !error && (
        <>
          {/* Summary Metric Chips */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white dark:bg-navy-900 p-4 rounded-xl border border-slate-200 dark:border-navy-800 shadow-sm">
              <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Total Filtered Volume</span>
              <div className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
                {totalVolume.toLocaleString()} <span className="text-xs font-normal text-slate-400">events</span>
              </div>
              <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Over {dailyData.length} active reporting days
              </div>
            </div>

            <div className="bg-white dark:bg-navy-900 p-4 rounded-xl border border-slate-200 dark:border-navy-800 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Gross Transaction Amount</span>
                <Badge variant="brand">{selectedCurrency}</Badge>
              </div>
              <div className="text-2xl font-bold text-blue-600 dark:text-blue-400 mt-1">
                {formatAmount(totalGrossAmount)}
              </div>
              <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Sum of raw event amounts (non-balance)
              </div>
            </div>

            <div className="bg-white dark:bg-navy-900 p-4 rounded-xl border border-slate-200 dark:border-navy-800 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Completed Gross Amount</span>
                <Badge variant="success">Completed</Badge>
              </div>
              <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
                {formatAmount(completedGrossAmount)}
              </div>
              <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Successfully settled transactions
              </div>
            </div>

            <div className="bg-white dark:bg-navy-900 p-4 rounded-xl border border-slate-200 dark:border-navy-800 shadow-sm">
              <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Completion Ratio</span>
              <div className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
                {totalGrossAmount > 0
                  ? ((completedGrossAmount / totalGrossAmount) * 100).toFixed(1)
                  : '0.0'}
                %
              </div>
              <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Completed vs total event value
              </div>
            </div>
          </div>

          {/* Section 1: Daily Trends Dual-Axis Chart */}
          <div className="bg-white dark:bg-navy-900 rounded-xl p-6 border border-slate-200 dark:border-navy-800 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                  Daily Volume & Gross Value Trends ({selectedCurrency})
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Left axis: Event volume (bars). Right axis: Gross transaction value in {selectedCurrency} (line).
                </p>
              </div>
              <div className="flex items-center gap-2 mt-2 sm:mt-0">
                <Badge variant="neutral">ISO {selectedCurrency}</Badge>
              </div>
            </div>

            {chartDailyData.length === 0 ? (
              <EmptyState title="No Daily Activity" message="No transactions recorded for the selected filters." />
            ) : (
              <div className="h-80 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chartDailyData} margin={{ top: 10, right: 30, left: 0, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.2} />
                    <XAxis
                      dataKey="date"
                      stroke="#94a3b8"
                      fontSize={11}
                      tickLine={false}
                      tickFormatter={(val) => val.slice(5)}
                    />
                    <YAxis
                      yAxisId="left"
                      stroke="#94a3b8"
                      fontSize={11}
                      tickLine={false}
                      label={{ value: 'Event Count', angle: -90, position: 'insideLeft', fill: '#94a3b8', fontSize: 10 }}
                    />
                    <YAxis
                      yAxisId="right"
                      orientation="right"
                      stroke="#3b82f6"
                      fontSize={11}
                      tickLine={false}
                      tickFormatter={(v) => `$${v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v}`}
                      label={{ value: `Gross (${selectedCurrency})`, angle: 90, position: 'insideRight', fill: '#3b82f6', fontSize: 10 }}
                    />
                    <Tooltip
                      content={({ active, payload, label }) => {
                        if (active && payload && payload.length) {
                          const data = payload[0].payload;
                          return (
                            <div className="bg-navy-950 text-white p-3 rounded-lg shadow-xl border border-navy-800 text-xs space-y-1">
                              <p className="font-bold text-slate-300">
                                {label} ({data.dayName})
                              </p>
                              <p className="text-blue-400">Total Volume: {data.volume} txns</p>
                              <p className="text-emerald-400">Completed Volume: {data.completedVolume} txns</p>
                              <p className="text-amber-400">
                                Gross Amount: {selectedCurrency} {formatAmount(data.grossAmount)}
                              </p>
                              <p className="text-indigo-400">
                                Completed Amount: {selectedCurrency} {formatAmount(data.completedAmount)}
                              </p>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Legend
                      verticalAlign="top"
                      height={36}
                      formatter={(val) => <span className="text-xs text-slate-600 dark:text-slate-300">{val}</span>}
                    />
                    <Bar
                      yAxisId="left"
                      dataKey="volume"
                      name="Total Transaction Volume"
                      fill="#3b82f6"
                      radius={[4, 4, 0, 0]}
                      maxBarSize={40}
                    />
                    <Line
                      yAxisId="right"
                      type="monotone"
                      dataKey="grossAmount"
                      name={`Gross Amount (${selectedCurrency})`}
                      stroke="#f59e0b"
                      strokeWidth={2.5}
                      dot={{ r: 3, fill: '#f59e0b' }}
                      activeDot={{ r: 6 }}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Section 2: Deposit vs Withdrawal Comparison */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white dark:bg-navy-900 rounded-xl p-6 border border-slate-200 dark:border-navy-800 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    <ArrowDownRight className="w-5 h-5 text-emerald-500" />
                    Deposit vs Withdrawal Value Share
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Gross event value split across cash inflow and outflow events.
                  </p>
                </div>
              </div>

              {depWithChartData.length === 0 ? (
                <EmptyState title="No Deposit/Withdrawal Records" message="No data for selected range." />
              ) : (
                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={depWithChartData} margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.2} />
                      <XAxis
                        dataKey="date"
                        stroke="#94a3b8"
                        fontSize={11}
                        tickLine={false}
                        tickFormatter={(val) => val.slice(5)}
                      />
                      <YAxis
                        stroke="#94a3b8"
                        fontSize={11}
                        tickLine={false}
                        tickFormatter={(v) => `${v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v}`}
                      />
                      <Tooltip
                        content={({ active, payload, label }) => {
                          if (active && payload && payload.length) {
                            const data = payload[0].payload;
                            return (
                              <div className="bg-navy-950 text-white p-3 rounded-lg shadow-xl border border-navy-800 text-xs space-y-1">
                                <p className="font-bold text-slate-300">{label}</p>
                                <p className="text-emerald-400">
                                  Deposits: {selectedCurrency} {formatAmount(data.depositAmount)} ({data.depositCount} txns)
                                </p>
                                <p className="text-amber-400">
                                  Withdrawals: {selectedCurrency} {formatAmount(data.withdrawalAmount)} ({data.withdrawalCount} txns)
                                </p>
                                <p className="text-slate-400">
                                  Deposit Value Share: {data.depositShare}%
                                </p>
                              </div>
                            );
                          }
                          return null;
                        }}
                      />
                      <Legend
                        verticalAlign="top"
                        height={36}
                        formatter={(val) => <span className="text-xs text-slate-600 dark:text-slate-300">{val}</span>}
                      />
                      <Bar
                        dataKey="depositAmount"
                        name={`Deposits (${selectedCurrency})`}
                        fill="#10b981"
                        radius={[4, 4, 0, 0]}
                        maxBarSize={30}
                      />
                      <Bar
                        dataKey="withdrawalAmount"
                        name={`Withdrawals (${selectedCurrency})`}
                        fill="#f59e0b"
                        radius={[4, 4, 0, 0]}
                        maxBarSize={30}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            {/* Section 3: Transaction Type Mix */}
            <div className="bg-white dark:bg-navy-900 rounded-xl p-6 border border-slate-200 dark:border-navy-800 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    <PieIcon className="w-5 h-5 text-purple-500" />
                    Transaction Type & Family Mix
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Distribution of volume and value across business transaction types.
                  </p>
                </div>
              </div>

              {typeMixData.length === 0 ? (
                <EmptyState title="No Type Mix Data" message="No breakdown available for this currency." />
              ) : (
                <div className="space-y-4">
                  {/* Type Mix Visual Distribution Bars */}
                  <div className="space-y-2">
                    {typeMixData.map((item) => {
                      const sharePct = parseFloat(item.value_share_pct || '0');
                      const color = TYPE_COLORS[item.transaction_type_code] || '#64748b';
                      return (
                        <div key={item.transaction_type_code} className="space-y-1">
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-medium text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                              <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
                              {item.transaction_type_name} ({item.transaction_family})
                            </span>
                            <span className="font-semibold text-slate-900 dark:text-white">
                              {selectedCurrency} {formatAmount(item.gross_transaction_amount)} ({sharePct}%)
                            </span>
                          </div>
                          <div className="w-full bg-slate-100 dark:bg-navy-950 rounded-full h-2 overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all duration-500"
                              style={{ width: `${Math.min(100, Math.max(2, sharePct))}%`, backgroundColor: color }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Summary Table */}
                  <div className="overflow-x-auto pt-2">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-slate-200 dark:border-navy-800 text-slate-400 font-semibold uppercase">
                          <th className="pb-2">Type</th>
                          <th className="pb-2">Family</th>
                          <th className="pb-2 text-right">Count</th>
                          <th className="pb-2 text-right">Event Share</th>
                          <th className="pb-2 text-right">Gross Value</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 dark:divide-navy-800 text-slate-600 dark:text-slate-300">
                        {typeMixData.map((row) => (
                          <tr key={row.transaction_type_code} className="hover:bg-slate-50 dark:hover:bg-navy-800/40">
                            <td className="py-2 font-medium">{row.transaction_type_name}</td>
                            <td className="py-2">
                              <Badge variant={row.transaction_family === 'CREDIT' ? 'success' : 'neutral'}>
                                {row.transaction_family}
                              </Badge>
                            </td>
                            <td className="py-2 text-right">{row.total_transaction_count.toLocaleString()}</td>
                            <td className="py-2 text-right font-medium">{row.event_share_pct}%</td>
                            <td className="py-2 text-right font-semibold text-slate-900 dark:text-white">
                              {selectedCurrency} {formatAmount(row.gross_transaction_amount)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Section 4: Branch and Channel Breakdown */}
          <div className="bg-white dark:bg-navy-900 rounded-xl p-6 border border-slate-200 dark:border-navy-800 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  <Building2 className="w-5 h-5 text-blue-500" />
                  Branch & Channel Performance Breakdown
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Event volume and gross settled activity categorized by operating region, branch, and channel.
                </p>
              </div>
              <div className="mt-2 sm:mt-0">
                <span className="text-xs text-slate-400">Showing {branchData.length} records</span>
              </div>
            </div>

            {branchData.length === 0 ? (
              <EmptyState title="No Branch Records Found" message="Try adjusting your channel or currency filter." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-200 dark:border-navy-800 text-slate-400 uppercase font-semibold">
                      <th className="py-3 px-3">Region</th>
                      <th className="py-3 px-3">Branch ID</th>
                      <th className="py-3 px-3">Branch Name</th>
                      <th className="py-3 px-3">Channel</th>
                      <th className="py-3 px-3 text-right">Transactions</th>
                      <th className="py-3 px-3 text-right">Completed</th>
                      <th className="py-3 px-3 text-right">Accounts</th>
                      <th className="py-3 px-3 text-right">Gross Amount</th>
                      <th className="py-3 px-3 text-right">Settled Amount</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-navy-800 text-slate-600 dark:text-slate-300">
                    {branchData.map((b, idx) => (
                      <tr key={`${b.branch_id}-${b.channel}-${idx}`} className="hover:bg-slate-50 dark:hover:bg-navy-800/40">
                        <td className="py-3 px-3 font-semibold text-slate-800 dark:text-slate-200">{b.region}</td>
                        <td className="py-3 px-3 font-mono text-slate-500">{b.branch_id}</td>
                        <td className="py-3 px-3 font-medium text-slate-900 dark:text-white">{b.branch_name}</td>
                        <td className="py-3 px-3">
                          <Badge
                            variant={
                              b.channel === 'ONLINE'
                                ? 'brand'
                                : b.channel === 'MOBILE'
                                ? 'info'
                                : b.channel === 'ATM'
                                ? 'warning'
                                : 'neutral'
                            }
                          >
                            {b.channel}
                          </Badge>
                        </td>
                        <td className="py-3 px-3 text-right font-medium">{b.total_transaction_count.toLocaleString()}</td>
                        <td className="py-3 px-3 text-right text-emerald-600 dark:text-emerald-400">
                          {b.completed_transaction_count.toLocaleString()}
                        </td>
                        <td className="py-3 px-3 text-right">{b.distinct_accounts.toLocaleString()}</td>
                        <td className="py-3 px-3 text-right font-semibold text-slate-900 dark:text-white">
                          {b.currency} {formatAmount(b.gross_transaction_amount)}
                        </td>
                        <td className="py-3 px-3 text-right font-medium text-emerald-600 dark:text-emerald-400">
                          {b.currency} {formatAmount(b.completed_gross_amount)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};
