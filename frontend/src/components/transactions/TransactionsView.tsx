import React, { useEffect, useState, useCallback } from 'react';
import {
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  RefreshCw,
  CreditCard,
  Building,
  User,
  X,
} from 'lucide-react';
import { useDashboard } from '../../context/DashboardContext';
import { BankFlowApi, ApiError } from '../../services/api';
import { PaginatedTransactionsResponse } from '../../services/types';
import { Badge } from '../common/Badge';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { ErrorAlert } from '../common/ErrorAlert';
import { EmptyState } from '../common/EmptyState';

export const TransactionsView: React.FC = () => {
  const { selectedCurrency, setSelectedCurrency, availableCurrencies, isDemoMode } = useDashboard();

  // Filter states
  const [status, setStatus] = useState<string>('');
  const [transactionType, setTransactionType] = useState<string>('');
  const [channel, setChannel] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [sortBy, setSortBy] = useState<'transaction_timestamp' | 'amount' | 'transaction_id' | 'reporting_date'>('transaction_timestamp');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  // Pagination states
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(25);

  // Response states
  const [data, setData] = useState<PaginatedTransactionsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<ApiError | null>(null);

  const loadTransactions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await BankFlowApi.getTransactions(
        {
          page,
          page_size: pageSize,
          currency: selectedCurrency || undefined,
          status: status || undefined,
          transaction_type: transactionType || undefined,
          channel: channel || undefined,
          start_date: startDate || undefined,
          end_date: endDate || undefined,
          sort_by: sortBy,
          sort_order: sortOrder,
        },
        isDemoMode
      );
      setData(res);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err);
      } else {
        setError(new ApiError(err instanceof Error ? err.message : 'Failed to query transactions'));
      }
    } finally {
      setLoading(false);
    }
  }, [
    page,
    pageSize,
    selectedCurrency,
    status,
    transactionType,
    channel,
    startDate,
    endDate,
    sortBy,
    sortOrder,
    isDemoMode,
  ]);

  useEffect(() => {
    loadTransactions();
  }, [loadTransactions]);

  const handleResetFilters = () => {
    setStatus('');
    setTransactionType('');
    setChannel('');
    setStartDate('');
    setEndDate('');
    setSortBy('transaction_timestamp');
    setSortOrder('desc');
    setPage(1);
  };

  const hasActiveFilters = Boolean(status || transactionType || channel || startDate || endDate);

  const formatAmount = (val?: string) => {
    if (!val) return '0.00';
    const num = parseFloat(val);
    return isNaN(num) ? val : num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  const formatTimestamp = (ts?: string) => {
    if (!ts) return '—';
    try {
      return new Date(ts).toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return ts;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header and Filter Control Bar */}
      <div className="bg-white dark:bg-navy-900 rounded-xl p-5 border border-slate-200 dark:border-navy-800 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <CreditCard className="w-5 h-5 text-blue-500" />
              Transactions Explorer & Ledger
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Paginated query console backed by BankFlow dimensional warehouse table <code className="text-blue-500">fct_transaction</code>.
            </p>
          </div>

          <div className="flex items-center gap-2">
            {hasActiveFilters && (
              <button
                onClick={handleResetFilters}
                className="flex items-center gap-1 text-xs text-rose-600 hover:text-rose-700 dark:text-rose-400 px-2.5 py-1.5 rounded-lg border border-rose-200 dark:border-rose-900/50 hover:bg-rose-50 dark:hover:bg-rose-950/30 transition-colors"
              >
                <X className="w-3.5 h-3.5" />
                Clear Filters
              </button>
            )}
            <button
              onClick={loadTransactions}
              disabled={loading}
              className="p-2 rounded-lg bg-blue-50 dark:bg-navy-800 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-navy-700 transition-colors"
              title="Refresh transaction query"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Filter Controls Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 pt-2 border-t border-slate-100 dark:border-navy-800">
          {/* Currency */}
          <div>
            <label className="block text-2xs uppercase tracking-wider font-semibold text-slate-400 mb-1">Currency</label>
            <select
              value={selectedCurrency}
              onChange={(e) => {
                setSelectedCurrency(e.target.value);
                setPage(1);
              }}
              className="w-full bg-slate-50 dark:bg-navy-950 text-xs text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-navy-800 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {availableCurrencies.map((c) => (
                <option key={c} value={c} className="bg-white dark:bg-navy-900">
                  {c}
                </option>
              ))}
            </select>
          </div>

          {/* Status */}
          <div>
            <label className="block text-2xs uppercase tracking-wider font-semibold text-slate-400 mb-1">Status</label>
            <select
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
              }}
              className="w-full bg-slate-50 dark:bg-navy-950 text-xs text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-navy-800 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">All Statuses</option>
              <option value="COMPLETED">COMPLETED</option>
              <option value="PENDING">PENDING</option>
              <option value="FAILED">FAILED</option>
              <option value="REVERSED">REVERSED</option>
            </select>
          </div>

          {/* Type */}
          <div>
            <label className="block text-2xs uppercase tracking-wider font-semibold text-slate-400 mb-1">Type</label>
            <select
              value={transactionType}
              onChange={(e) => {
                setTransactionType(e.target.value);
                setPage(1);
              }}
              className="w-full bg-slate-50 dark:bg-navy-950 text-xs text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-navy-800 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">All Types</option>
              <option value="DEPOSIT">Deposit</option>
              <option value="WITHDRAWAL">Withdrawal</option>
              <option value="TRANSFER">Transfer</option>
              <option value="PAYMENT">Payment</option>
              <option value="FEE">Fee</option>
              <option value="REVERSAL">Reversal</option>
            </select>
          </div>

          {/* Channel */}
          <div>
            <label className="block text-2xs uppercase tracking-wider font-semibold text-slate-400 mb-1">Channel</label>
            <select
              value={channel}
              onChange={(e) => {
                setChannel(e.target.value);
                setPage(1);
              }}
              className="w-full bg-slate-50 dark:bg-navy-950 text-xs text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-navy-800 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">All Channels</option>
              <option value="BRANCH">Branch</option>
              <option value="ATM">ATM</option>
              <option value="ONLINE">Online</option>
              <option value="MOBILE">Mobile</option>
            </select>
          </div>

          {/* Sort By */}
          <div>
            <label className="block text-2xs uppercase tracking-wider font-semibold text-slate-400 mb-1">Sort By</label>
            <div className="flex items-center gap-1">
              <select
                value={sortBy}
                onChange={(e) => {
                  setSortBy(e.target.value as 'transaction_timestamp' | 'amount' | 'transaction_id' | 'reporting_date');
                  setPage(1);
                }}
                className="w-full bg-slate-50 dark:bg-navy-950 text-xs text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-navy-800 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="transaction_timestamp">Timestamp</option>
                <option value="amount">Amount</option>
                <option value="transaction_id">ID</option>
                <option value="reporting_date">Date</option>
              </select>
              <button
                onClick={() => {
                  setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
                  setPage(1);
                }}
                className="p-1.5 rounded-lg border border-slate-200 dark:border-navy-800 bg-slate-50 dark:bg-navy-950 text-slate-600 dark:text-slate-300 hover:bg-slate-100"
                title={`Sort order: ${sortOrder.toUpperCase()}`}
              >
                <ArrowUpDown className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Date Range Start */}
          <div>
            <label className="block text-2xs uppercase tracking-wider font-semibold text-slate-400 mb-1">From Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value);
                setPage(1);
              }}
              className="w-full bg-slate-50 dark:bg-navy-950 text-xs text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-navy-800 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      {/* Loading & Error States */}
      {loading && <LoadingSpinner label="Fetching paginated warehouse transactions..." />}

      {error && !loading && (
        <ErrorAlert
          title="Transaction Query Failed"
          message={error.message}
          statusCode={error.statusCode}
          onRetry={loadTransactions}
        />
      )}

      {/* Main Table */}
      {!loading && !error && data && (
        <div className="bg-white dark:bg-navy-900 rounded-xl border border-slate-200 dark:border-navy-800 shadow-sm overflow-hidden">
          {/* Table Header Bar with Counts */}
          <div className="p-4 border-b border-slate-200 dark:border-navy-800 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
            <span className="font-semibold text-slate-700 dark:text-slate-300">
              Showing <span className="text-blue-600 dark:text-blue-400 font-bold">{data.items.length}</span> of{' '}
              <span className="text-slate-900 dark:text-white font-bold">{data.total.toLocaleString()}</span> transactions
              {' '}(Currency: <span className="font-mono text-blue-500">{selectedCurrency}</span>)
            </span>

            {/* Page Size Selector */}
            <div className="flex items-center gap-2">
              <span className="text-slate-400">Rows per page:</span>
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setPage(1);
                }}
                className="bg-slate-50 dark:bg-navy-950 text-xs border border-slate-200 dark:border-navy-800 rounded px-2 py-1 text-slate-800 dark:text-slate-200 focus:outline-none"
              >
                <option value={10}>10</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </div>
          </div>

          {data.items.length === 0 ? (
            <div className="p-8">
              <EmptyState
                title="No Transactions Match Filters"
                message="Try adjusting your status, date range, or currency filters to locate transactions."
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200 dark:border-navy-800 text-slate-400 uppercase font-semibold">
                    <th className="py-3 px-3">Transaction ID</th>
                    <th className="py-3 px-3">Date & Timestamp</th>
                    <th className="py-3 px-3">Type & Family</th>
                    <th className="py-3 px-3">Channel</th>
                    <th className="py-3 px-3">Account / Customer</th>
                    <th className="py-3 px-3">Branch & Region</th>
                    <th className="py-3 px-3">Status</th>
                    <th className="py-3 px-3 text-right">Amount ({selectedCurrency})</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-navy-800 text-slate-600 dark:text-slate-300">
                  {data.items.map((txn) => {
                    const isCredit = txn.transaction_family === 'CREDIT';
                    return (
                      <tr key={txn.transaction_id} className="hover:bg-slate-50 dark:hover:bg-navy-800/40">
                        <td className="py-3 px-3">
                          <span className="font-mono font-bold text-blue-600 dark:text-blue-400">
                            {txn.transaction_id}
                          </span>
                          <span className="block text-2xs font-mono text-slate-400">{txn.source_system}</span>
                        </td>
                        <td className="py-3 px-3">
                          <div className="font-medium text-slate-800 dark:text-slate-200">
                            {txn.reporting_date}
                          </div>
                          <div className="text-2xs text-slate-400">
                            {formatTimestamp(txn.transaction_timestamp)}
                          </div>
                        </td>
                        <td className="py-3 px-3">
                          <div className="font-medium text-slate-900 dark:text-white">{txn.type_name}</div>
                          <div className="mt-0.5">
                            <Badge variant={isCredit ? 'success' : 'neutral'}>
                              {txn.transaction_family}
                            </Badge>
                          </div>
                        </td>
                        <td className="py-3 px-3">
                          <Badge
                            variant={
                              txn.channel === 'ONLINE'
                                ? 'brand'
                                : txn.channel === 'MOBILE'
                                ? 'info'
                                : txn.channel === 'ATM'
                                ? 'warning'
                                : 'neutral'
                            }
                          >
                            {txn.channel}
                          </Badge>
                        </td>
                        <td className="py-3 px-3">
                          <div className="font-mono font-medium text-slate-900 dark:text-white flex items-center gap-1">
                            <CreditCard className="w-3 h-3 text-slate-400" />
                            {txn.account_id}
                          </div>
                          <div className="font-mono text-2xs text-slate-400 flex items-center gap-1 mt-0.5">
                            <User className="w-3 h-3 text-slate-400" />
                            {txn.customer_id}
                          </div>
                        </td>
                        <td className="py-3 px-3">
                          <div className="font-medium text-slate-800 dark:text-slate-200 flex items-center gap-1">
                            <Building className="w-3 h-3 text-slate-400" />
                            {txn.branch_name}
                          </div>
                          <div className="text-2xs text-slate-400 font-mono">
                            {txn.branch_id} • {txn.region}
                          </div>
                        </td>
                        <td className="py-3 px-3">
                          <Badge
                            variant={
                              txn.status === 'COMPLETED'
                                ? 'success'
                                : txn.status === 'FAILED'
                                ? 'danger'
                                : txn.status === 'REVERSED'
                                ? 'warning'
                                : 'info'
                            }
                          >
                            {txn.status}
                          </Badge>
                        </td>
                        <td className="py-3 px-3 text-right">
                          <div
                            className={`font-mono font-bold text-sm ${
                              isCredit
                                ? 'text-emerald-600 dark:text-emerald-400'
                                : 'text-slate-900 dark:text-white'
                            }`}
                          >
                            {isCredit ? '+' : ''}
                            {formatAmount(txn.amount)}
                          </div>
                          <div className="text-2xs font-mono text-slate-400">{txn.currency}</div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination Controls Footer */}
          {data.total_pages > 1 && (
            <div className="p-4 border-t border-slate-200 dark:border-navy-800 flex items-center justify-between text-xs">
              <span className="text-slate-500 dark:text-slate-400">
                Page <span className="font-bold text-slate-900 dark:text-white">{data.page}</span> of{' '}
                <span className="font-bold text-slate-900 dark:text-white">{data.total_pages}</span>
              </span>

              <div className="flex items-center gap-1">
                {/* First Page */}
                <button
                  onClick={() => setPage(1)}
                  disabled={page <= 1}
                  className="p-1.5 rounded border border-slate-200 dark:border-navy-800 text-slate-600 dark:text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-50 dark:hover:bg-navy-800"
                  title="First Page"
                >
                  <ChevronsLeft className="w-4 h-4" />
                </button>

                {/* Previous Page */}
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="p-1.5 rounded border border-slate-200 dark:border-navy-800 text-slate-600 dark:text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-50 dark:hover:bg-navy-800"
                  title="Previous Page"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>

                {/* Page indicator pill */}
                <span className="px-3 py-1 font-semibold text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-navy-800 rounded">
                  {page}
                </span>

                {/* Next Page */}
                <button
                  onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                  disabled={page >= data.total_pages}
                  className="p-1.5 rounded border border-slate-200 dark:border-navy-800 text-slate-600 dark:text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-50 dark:hover:bg-navy-800"
                  title="Next Page"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>

                {/* Last Page */}
                <button
                  onClick={() => setPage(data.total_pages)}
                  disabled={page >= data.total_pages}
                  className="p-1.5 rounded border border-slate-200 dark:border-navy-800 text-slate-600 dark:text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-50 dark:hover:bg-navy-800"
                  title="Last Page"
                >
                  <ChevronsRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
