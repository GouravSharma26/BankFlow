import React, { useEffect, useState, useCallback } from 'react';
import {
  Layers,
  CheckCircle2,
  AlertOctagon,
  Clock,
  Filter,
  RefreshCw,
  FileCheck2,
  ChevronDown,
  ChevronUp,
  Database,
  ArrowRight,
} from 'lucide-react';
import { useDashboard } from '../../context/DashboardContext';
import { BankFlowApi, ApiError } from '../../services/api';
import { BatchExecutionItem } from '../../services/types';
import { Badge } from '../common/Badge';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { ErrorAlert } from '../common/ErrorAlert';
import { EmptyState } from '../common/EmptyState';

export const PipelineView: React.FC = () => {
  const { isDemoMode } = useDashboard();

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [reconFilter, setReconFilter] = useState<string>('');
  const [limit, setLimit] = useState<number>(25);

  // Data & UI states
  const [batches, setBatches] = useState<BatchExecutionItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [expandedBatchId, setExpandedBatchId] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await BankFlowApi.getBatches(
        {
          status: statusFilter || undefined,
          reconciliation_status: reconFilter || undefined,
          limit,
        },
        isDemoMode
      );
      setBatches(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err);
      } else {
        setError(new ApiError(err instanceof Error ? err.message : 'Failed to load batch execution history'));
      }
    } finally {
      setLoading(false);
    }
  }, [statusFilter, reconFilter, limit, isDemoMode]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Aggregate Metrics
  const totalBatches = batches.length;
  const succeededCount = batches.filter((b) => b.status === 'SUCCEEDED').length;
  const failedCount = batches.filter((b) => b.status === 'FAILED' || b.status === 'ROLLED_BACK').length;
  const reconciledCount = batches.filter((b) => b.reconciliation_status === 'RECONCILED').length;
  const totalExtracted = batches.reduce((acc, b) => acc + b.records_extracted, 0);
  const totalInserted = batches.reduce((acc, b) => acc + b.records_inserted, 0);
  const totalRejected = batches.reduce((acc, b) => acc + b.records_rejected, 0);

  const formatDate = (isoString?: string | null) => {
    if (!isoString) return '—';
    try {
      return new Date(isoString).toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  const toggleExpand = (batchId: string) => {
    setExpandedBatchId(expandedBatchId === batchId ? null : batchId);
  };

  return (
    <div className="space-y-6">
      {/* Pipeline Architecture Banner */}
      <div className="bg-slate-900 dark:bg-navy-900 text-white rounded-xl p-6 border border-navy-800 shadow-md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Layers className="w-6 h-6 text-blue-400" />
              <h2 className="text-xl font-bold">ETL Pipeline & Batch Reconciliation</h2>
            </div>
            <p className="text-xs text-slate-300 max-w-3xl">
              BankFlow enforces transactional staging, explicit row accounting, and automated reconciliation.
              Every batch verifies that extracted records balance against valid staged rows plus quarantined rejections
              before marking the batch succeeded.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-xs text-slate-400">Success Rate</div>
              <div className="text-lg font-bold text-emerald-400">
                {totalBatches > 0 ? ((succeededCount / totalBatches) * 100).toFixed(0) : '0'}%
              </div>
            </div>
            <div className="text-right border-l border-navy-700 pl-3">
              <div className="text-xs text-slate-400">Reconciled</div>
              <div className="text-lg font-bold text-blue-400">
                {totalBatches > 0 ? ((reconciledCount / totalBatches) * 100).toFixed(0) : '0'}%
              </div>
            </div>
          </div>
        </div>

        {/* Pipeline Ingestion Flow Diagram Pills */}
        <div className="mt-5 pt-4 border-t border-navy-800 flex flex-wrap items-center gap-2 text-xs text-slate-300">
          <span className="font-semibold text-slate-400">Ingestion Flow:</span>
          <span className="px-2.5 py-1 rounded bg-navy-950 border border-navy-700">1. CSV Extract</span>
          <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
          <span className="px-2.5 py-1 rounded bg-navy-950 border border-navy-700">2. Staging Validation</span>
          <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
          <span className="px-2.5 py-1 rounded bg-navy-950 border border-navy-700">3. Quarantine Rejections</span>
          <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
          <span className="px-2.5 py-1 rounded bg-navy-950 border border-navy-700">4. Dimensional Upsert</span>
          <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
          <span className="px-2.5 py-1 rounded bg-navy-950 border border-navy-700">5. Count & Value Reconciliation</span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-navy-900 p-5 rounded-xl border border-slate-200 dark:border-navy-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-medium">
            <span>Total Batches Tracked</span>
            <Layers className="w-4 h-4 text-blue-500" />
          </div>
          <div className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
            {totalBatches}
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            {succeededCount} succeeded, {failedCount} failed
          </p>
        </div>

        <div className="bg-white dark:bg-navy-900 p-5 rounded-xl border border-slate-200 dark:border-navy-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-medium">
            <span>Total Extracted Rows</span>
            <Database className="w-4 h-4 text-indigo-500" />
          </div>
          <div className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
            {totalExtracted.toLocaleString()}
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Extracted from synthetic CSV batches
          </p>
        </div>

        <div className="bg-white dark:bg-navy-900 p-5 rounded-xl border border-slate-200 dark:border-navy-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-medium">
            <span>Warehouse Inserted</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
            {totalInserted.toLocaleString()}
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Clean records committed to star schema
          </p>
        </div>

        <div className="bg-white dark:bg-navy-900 p-5 rounded-xl border border-slate-200 dark:border-navy-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-medium">
            <span>Quarantined & Rejections</span>
            <AlertOctagon className="w-4 h-4 text-rose-500" />
          </div>
          <div className="text-2xl font-bold text-rose-600 dark:text-rose-400 mt-1">
            {totalRejected.toLocaleString()}
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            {totalExtracted > 0 ? ((totalRejected / totalExtracted) * 100).toFixed(1) : '0.0'}% rejection rate
          </p>
        </div>
      </div>

      {/* Batch Execution History Table */}
      <div className="bg-white dark:bg-navy-900 rounded-xl p-6 border border-slate-200 dark:border-navy-800 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-5">
          <div>
            <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <FileCheck2 className="w-5 h-5 text-blue-500" />
              Batch Execution & Reconciliation Audit Trail
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Audit logs from <code className="text-blue-500">ops_batch_execution</code> tracking duration, row accounting, and reconciliation.
            </p>
          </div>

          {/* Filters */}
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-1.5 bg-slate-50 dark:bg-navy-950 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-navy-800">
              <Filter className="w-3.5 h-3.5 text-slate-400" />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-transparent text-xs text-slate-800 dark:text-slate-200 focus:outline-none cursor-pointer"
              >
                <option value="" className="bg-white dark:bg-navy-900">All Statuses</option>
                <option value="SUCCEEDED" className="bg-white dark:bg-navy-900">SUCCEEDED</option>
                <option value="FAILED" className="bg-white dark:bg-navy-900">FAILED</option>
                <option value="STARTED" className="bg-white dark:bg-navy-900">STARTED</option>
                <option value="ROLLED_BACK" className="bg-white dark:bg-navy-900">ROLLED_BACK</option>
              </select>
            </div>

            <div className="flex items-center gap-1.5 bg-slate-50 dark:bg-navy-950 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-navy-800">
              <select
                value={reconFilter}
                onChange={(e) => setReconFilter(e.target.value)}
                className="bg-transparent text-xs text-slate-800 dark:text-slate-200 focus:outline-none cursor-pointer"
              >
                <option value="" className="bg-white dark:bg-navy-900">All Reconciliation</option>
                <option value="RECONCILED" className="bg-white dark:bg-navy-900">RECONCILED</option>
                <option value="DISCREPANCY_DETECTED" className="bg-white dark:bg-navy-900">DISCREPANCY_DETECTED</option>
                <option value="UNRECONCILED" className="bg-white dark:bg-navy-900">UNRECONCILED</option>
              </select>
            </div>

            <div className="flex items-center gap-1.5 bg-slate-50 dark:bg-navy-950 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-navy-800">
              <span className="text-xs text-slate-400">Limit:</span>
              <select
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="bg-transparent text-xs text-slate-800 dark:text-slate-200 focus:outline-none cursor-pointer"
              >
                <option value={10} className="bg-white dark:bg-navy-900">10</option>
                <option value={25} className="bg-white dark:bg-navy-900">25</option>
                <option value={50} className="bg-white dark:bg-navy-900">50</option>
                <option value={100} className="bg-white dark:bg-navy-900">100</option>
              </select>
            </div>

            <button
              onClick={loadData}
              disabled={loading}
              className="p-1.5 rounded-lg bg-blue-50 dark:bg-navy-800 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-navy-700 transition-colors"
              title="Refresh batch history"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {loading && <LoadingSpinner label="Fetching pipeline batches and reconciliation metrics..." />}

        {error && !loading && (
          <ErrorAlert
            title="Batch Query Failed"
            message={error.message}
            statusCode={error.statusCode}
            onRetry={loadData}
          />
        )}

        {!loading && !error && batches.length === 0 && (
          <EmptyState
            title="No Batch Records Found"
            message="No pipeline batches match the selected status or reconciliation filter."
          />
        )}

        {!loading && !error && batches.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 dark:border-navy-800 text-slate-400 uppercase font-semibold">
                  <th className="py-3 px-3">Batch ID / Source</th>
                  <th className="py-3 px-3">Status</th>
                  <th className="py-3 px-3">Reconciliation</th>
                  <th className="py-3 px-3">Execution Time</th>
                  <th className="py-3 px-3 text-right">Extracted</th>
                  <th className="py-3 px-3 text-right">Valid</th>
                  <th className="py-3 px-3 text-right">Rejected</th>
                  <th className="py-3 px-3 text-right">Inserted</th>
                  <th className="py-3 px-3 text-right">Skipped</th>
                  <th className="py-3 px-3 text-center">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-navy-800 text-slate-600 dark:text-slate-300">
                {batches.map((batch) => {
                  const isExpanded = expandedBatchId === batch.batch_id;
                  const isSuccess = batch.status === 'SUCCEEDED';
                  const isFailed = batch.status === 'FAILED' || batch.status === 'ROLLED_BACK';

                  return (
                    <React.Fragment key={batch.batch_id}>
                      <tr
                        onClick={() => toggleExpand(batch.batch_id)}
                        className={`hover:bg-slate-50 dark:hover:bg-navy-800/40 cursor-pointer transition-colors ${
                          isExpanded ? 'bg-blue-50/50 dark:bg-navy-800/30' : ''
                        }`}
                      >
                        <td className="py-3 px-3">
                          <div className="font-mono font-bold text-slate-900 dark:text-white">
                            {batch.batch_id}
                          </div>
                          <div className="text-slate-400 text-xs flex items-center gap-1 mt-0.5">
                            <span className="font-mono">{batch.source_name}</span>
                          </div>
                        </td>
                        <td className="py-3 px-3">
                          <Badge variant={isSuccess ? 'success' : isFailed ? 'danger' : 'warning'}>
                            {batch.status}
                          </Badge>
                        </td>
                        <td className="py-3 px-3">
                          <Badge
                            variant={
                              batch.reconciliation_status === 'RECONCILED'
                                ? 'success'
                                : batch.reconciliation_status === 'DISCREPANCY_DETECTED'
                                ? 'danger'
                                : 'neutral'
                            }
                          >
                            {batch.reconciliation_status || 'PENDING'}
                          </Badge>
                        </td>
                        <td className="py-3 px-3">
                          <div className="font-medium text-slate-700 dark:text-slate-300">
                            {formatDate(batch.started_at)}
                          </div>
                          <div className="text-slate-400 text-xs flex items-center gap-1 mt-0.5">
                            <Clock className="w-3 h-3" />
                            {batch.duration_seconds !== null ? `${batch.duration_seconds.toFixed(2)}s` : 'running...'}
                          </div>
                        </td>
                        <td className="py-3 px-3 text-right font-medium">
                          {batch.records_extracted.toLocaleString()}
                        </td>
                        <td className="py-3 px-3 text-right text-emerald-600 dark:text-emerald-400 font-medium">
                          {batch.records_valid.toLocaleString()}
                        </td>
                        <td className="py-3 px-3 text-right font-bold text-rose-600 dark:text-rose-400">
                          {batch.records_rejected.toLocaleString()}
                          {batch.rejection_rate_pct && (
                            <span className="block text-2xs font-normal text-slate-400">
                              ({batch.rejection_rate_pct}%)
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-3 text-right font-semibold text-slate-900 dark:text-white">
                          {batch.records_inserted.toLocaleString()}
                        </td>
                        <td className="py-3 px-3 text-right font-mono text-slate-400">
                          {batch.records_skipped}
                        </td>
                        <td className="py-3 px-3 text-center">
                          <button
                            type="button"
                            className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                          >
                            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                          </button>
                        </td>
                      </tr>

                      {/* Expandable Details Drawer */}
                      {isExpanded && (
                        <tr className="bg-slate-50 dark:bg-navy-950/60 border-b border-slate-200 dark:border-navy-800">
                          <td colSpan={10} className="p-4">
                            <div className="space-y-3 max-w-4xl">
                              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                                Batch Audit & Accounting Breakdown
                              </h4>
                              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                                <div className="bg-white dark:bg-navy-900 p-2.5 rounded border border-slate-200 dark:border-navy-800">
                                  <div className="text-slate-400">Staged Rows</div>
                                  <div className="text-sm font-bold text-slate-900 dark:text-white">
                                    {batch.records_staged.toLocaleString()}
                                  </div>
                                </div>
                                <div className="bg-white dark:bg-navy-900 p-2.5 rounded border border-slate-200 dark:border-navy-800">
                                  <div className="text-slate-400">Updated Rows</div>
                                  <div className="text-sm font-bold text-slate-900 dark:text-white">
                                    {batch.records_updated.toLocaleString()}
                                  </div>
                                </div>
                                <div className="bg-white dark:bg-navy-900 p-2.5 rounded border border-slate-200 dark:border-navy-800">
                                  <div className="text-slate-400">Reconciliation Equality</div>
                                  <div className="text-sm font-bold text-emerald-600 dark:text-emerald-400">
                                    {batch.records_extracted === batch.records_valid + batch.records_rejected
                                      ? 'Balanced (Valid + Rejected = Extracted)'
                                      : 'Discrepancy Detected'}
                                  </div>
                                </div>
                                <div className="bg-white dark:bg-navy-900 p-2.5 rounded border border-slate-200 dark:border-navy-800">
                                  <div className="text-slate-400">Completed At</div>
                                  <div className="text-sm font-medium text-slate-900 dark:text-white">
                                    {formatDate(batch.completed_at)}
                                  </div>
                                </div>
                              </div>

                              {batch.error_summary && (
                                <div className="p-3 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 rounded-lg text-xs text-rose-800 dark:text-rose-300 font-mono">
                                  <div className="font-bold flex items-center gap-1 mb-1">
                                    <AlertOctagon className="w-3.5 h-3.5" />
                                    Batch Error Summary
                                  </div>
                                  {batch.error_summary}
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
