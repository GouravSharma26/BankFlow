import React, { useEffect, useState, useCallback } from 'react';
import {
  ShieldAlert,
  AlertTriangle,
  FileWarning,
  CheckCircle,
  Filter,
  RefreshCw,
  Archive,
  Layers,
} from 'lucide-react';
import { useDashboard } from '../../context/DashboardContext';
import { BankFlowApi, ApiError } from '../../services/api';
import { QualitySummaryItem, QuarantineItem } from '../../services/types';
import { Badge } from '../common/Badge';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { ErrorAlert } from '../common/ErrorAlert';
import { EmptyState } from '../common/EmptyState';

// Explanations for known BankFlow validation rule codes
const RULE_DESCRIPTIONS: Record<string, string> = {
  RULE_AMOUNT_NON_POSITIVE: 'Transaction amount must be strictly greater than 0.00; non-positive values rejected.',
  RULE_TRANSACTION_DATE_FUTURE: 'Transaction timestamp cannot be in the future relative to batch execution window.',
  RULE_ACCOUNT_NOT_FOUND: 'Referenced account ID does not exist in active dimension dim_account; foreign-key validation failure.',
  RULE_DUPLICATE_NATURAL_KEY: 'Transaction ID already ingested in an earlier batch; duplicate replay rejected for idempotency.',
  RULE_CURRENCY_UNKNOWN: 'Currency code is not recognized in supported ISO currencies list (USD, EUR, GBP).',
  RULE_CUSTOMER_NOT_FOUND: 'Customer ID does not match any known customer record.',
  RULE_ACCOUNT_CLOSED: 'Transaction attempted on an account marked closed or frozen in dimension record.',
};

export const QualityView: React.FC = () => {
  const { isDemoMode } = useDashboard();

  // Filters
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [dispositionFilter, setDispositionFilter] = useState<string>('');
  const [entityFilter, setEntityFilter] = useState<string>('');

  // Data states
  const [qualityItems, setQualityItems] = useState<QualitySummaryItem[]>([]);
  const [quarantineItems, setQuarantineItems] = useState<QuarantineItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<ApiError | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [qualityRes, quarantineRes] = await Promise.all([
        BankFlowApi.getQuality(
          {
            severity: severityFilter || undefined,
            disposition: dispositionFilter || undefined,
            limit: 50,
          },
          isDemoMode
        ),
        BankFlowApi.getQuarantine(
          {
            entity_type: entityFilter || undefined,
            limit: 50,
          },
          isDemoMode
        ),
      ]);

      setQualityItems(qualityRes);
      setQuarantineItems(quarantineRes);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err);
      } else {
        setError(new ApiError(err instanceof Error ? err.message : 'Failed to fetch data quality records'));
      }
    } finally {
      setLoading(false);
    }
  }, [severityFilter, dispositionFilter, entityFilter, isDemoMode]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Aggregate stats
  const totalIssues = qualityItems.reduce((acc, q) => acc + q.issue_count, 0);
  const totalAffectedRows = qualityItems.reduce((acc, q) => acc + q.affected_source_rows, 0);
  const totalQuarantinedRows = quarantineItems.reduce((acc, q) => acc + q.quarantined_rows, 0);
  const errorCount = qualityItems.filter((q) => q.severity === 'ERROR').length;

  const formatDate = (isoString?: string | null) => {
    if (!isoString) return '—';
    try {
      return new Date(isoString).toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="space-y-6">
      {/* Architectural Context Banner */}
      <div className="bg-slate-900 dark:bg-navy-900 text-white rounded-xl p-6 border border-navy-800 shadow-md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-6 h-6 text-amber-400" />
              <h2 className="text-xl font-bold">Data Quality & Quarantine Monitor</h2>
            </div>
            <p className="text-xs text-slate-300 max-w-3xl">
              BankFlow enforces strict transaction-level data contracts. Malformed or invalid rows are captured in the
              quarantine layer without silently discarding records. Valid transactions in the same batch continue safely to
              the dimensional warehouse.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs px-3 py-1.5 bg-navy-950 border border-navy-700 rounded-lg text-slate-300 font-mono">
              Rule Codes: {qualityItems.length}
            </span>
            <span className="text-xs px-3 py-1.5 bg-navy-950 border border-navy-700 rounded-lg text-slate-300 font-mono">
              Quarantined: {totalQuarantinedRows}
            </span>
          </div>
        </div>

        {/* Rejection Architecture Note */}
        <div className="mt-4 pt-4 border-t border-navy-800 grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-slate-400">
          <div className="flex items-start gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <strong className="text-slate-200">Row-Level Rejection:</strong> Individual defective events (e.g. non-positive
              amount, missing account FK) are quarantined to <code className="text-amber-300">stg_quarantined_record</code> with
              exact rule code and raw JSON payload.
            </div>
          </div>
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <strong className="text-slate-200">Batch-Level Failure:</strong> Fatal file corruptions or unhandled staging exceptions
              rollback the entire transaction block, marking batch status <code className="text-rose-300">FAILED</code> without partial ingestion.
            </div>
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-navy-900 p-5 rounded-xl border border-slate-200 dark:border-navy-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-medium">
            <span>Active Quality Rules</span>
            <AlertTriangle className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
            {qualityItems.length}
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            {errorCount} error-level severity rules triggered
          </p>
        </div>

        <div className="bg-white dark:bg-navy-900 p-5 rounded-xl border border-slate-200 dark:border-navy-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-medium">
            <span>Total Quality Defects</span>
            <FileWarning className="w-4 h-4 text-rose-500" />
          </div>
          <div className="text-2xl font-bold text-rose-600 dark:text-rose-400 mt-1">
            {totalIssues.toLocaleString()}
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Across {totalAffectedRows} affected raw source rows
          </p>
        </div>

        <div className="bg-white dark:bg-navy-900 p-5 rounded-xl border border-slate-200 dark:border-navy-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-medium">
            <span>Quarantined Records</span>
            <Archive className="w-4 h-4 text-blue-500" />
          </div>
          <div className="text-2xl font-bold text-blue-600 dark:text-blue-400 mt-1">
            {totalQuarantinedRows.toLocaleString()}
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Preserved with full raw payloads for audit
          </p>
        </div>

        <div className="bg-white dark:bg-navy-900 p-5 rounded-xl border border-slate-200 dark:border-navy-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-medium">
            <span>Quarantine Batches</span>
            <Layers className="w-4 h-4 text-purple-500" />
          </div>
          <div className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
            {quarantineItems.length}
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Batches with quarantined records
          </p>
        </div>
      </div>

      {/* Quality Issues Summary Table */}
      <div className="bg-white dark:bg-navy-900 rounded-xl p-6 border border-slate-200 dark:border-navy-800 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-5">
          <div>
            <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-amber-500" />
              Validation Rules & Defect Inventory
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Aggregated validation outcomes by rule code, severity, and quarantine disposition.
            </p>
          </div>

          {/* Table Filters */}
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-1.5 bg-slate-50 dark:bg-navy-950 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-navy-800">
              <Filter className="w-3.5 h-3.5 text-slate-400" />
              <select
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value)}
                className="bg-transparent text-xs text-slate-800 dark:text-slate-200 focus:outline-none cursor-pointer"
              >
                <option value="" className="bg-white dark:bg-navy-900">All Severities</option>
                <option value="ERROR" className="bg-white dark:bg-navy-900">ERROR</option>
                <option value="WARNING" className="bg-white dark:bg-navy-900">WARNING</option>
                <option value="INFO" className="bg-white dark:bg-navy-900">INFO</option>
              </select>
            </div>

            <div className="flex items-center gap-1.5 bg-slate-50 dark:bg-navy-950 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-navy-800">
              <select
                value={dispositionFilter}
                onChange={(e) => setDispositionFilter(e.target.value)}
                className="bg-transparent text-xs text-slate-800 dark:text-slate-200 focus:outline-none cursor-pointer"
              >
                <option value="" className="bg-white dark:bg-navy-900">All Dispositions</option>
                <option value="REJECTED" className="bg-white dark:bg-navy-900">REJECTED</option>
                <option value="ACCEPTED" className="bg-white dark:bg-navy-900">ACCEPTED</option>
                <option value="WARNED" className="bg-white dark:bg-navy-900">WARNED</option>
                <option value="SKIPPED" className="bg-white dark:bg-navy-900">SKIPPED</option>
              </select>
            </div>

            <button
              onClick={loadData}
              disabled={loading}
              className="p-1.5 rounded-lg bg-blue-50 dark:bg-navy-800 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-navy-700 transition-colors"
              title="Refresh quality data"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {loading && <LoadingSpinner label="Loading data quality validation rules..." />}

        {error && !loading && (
          <ErrorAlert
            title="Quality Query Failed"
            message={error.message}
            statusCode={error.statusCode}
            onRetry={loadData}
          />
        )}

        {!loading && !error && qualityItems.length === 0 && (
          <EmptyState
            title="No Quality Issues Found"
            message="Zero validation defects match your filter criteria. All checked rows conformed to rules."
          />
        )}

        {!loading && !error && qualityItems.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 dark:border-navy-800 text-slate-400 uppercase font-semibold">
                  <th className="py-3 px-3">Rule Code & Description</th>
                  <th className="py-3 px-3">Severity</th>
                  <th className="py-3 px-3">Disposition</th>
                  <th className="py-3 px-3 text-right">Total Defects</th>
                  <th className="py-3 px-3 text-right">Affected Rows</th>
                  <th className="py-3 px-3 text-right">Affected Batches</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-navy-800 text-slate-600 dark:text-slate-300">
                {qualityItems.map((rule) => {
                  const description = RULE_DESCRIPTIONS[rule.rule_code] || 'Custom validation check';
                  return (
                    <tr key={`${rule.rule_code}-${rule.severity}-${rule.disposition}`} className="hover:bg-slate-50 dark:hover:bg-navy-800/40">
                      <td className="py-3 px-3 max-w-md">
                        <div className="font-mono font-semibold text-slate-900 dark:text-white">
                          {rule.rule_code}
                        </div>
                        <div className="text-slate-500 dark:text-slate-400 text-xs mt-0.5">
                          {description}
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        <Badge
                          variant={
                            rule.severity === 'ERROR'
                              ? 'danger'
                              : rule.severity === 'WARNING'
                              ? 'warning'
                              : 'info'
                          }
                        >
                          {rule.severity}
                        </Badge>
                      </td>
                      <td className="py-3 px-3">
                        <Badge
                          variant={
                            rule.disposition === 'REJECTED'
                              ? 'danger'
                              : rule.disposition === 'ACCEPTED'
                              ? 'success'
                              : 'neutral'
                          }
                        >
                          {rule.disposition}
                        </Badge>
                      </td>
                      <td className="py-3 px-3 text-right font-bold text-rose-600 dark:text-rose-400">
                        {rule.issue_count.toLocaleString()}
                      </td>
                      <td className="py-3 px-3 text-right font-medium">
                        {rule.affected_source_rows.toLocaleString()}
                      </td>
                      <td className="py-3 px-3 text-right font-mono">
                        {rule.affected_batches}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Quarantine Inventory Table */}
      <div className="bg-white dark:bg-navy-900 rounded-xl p-6 border border-slate-200 dark:border-navy-800 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-5">
          <div>
            <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <Archive className="w-5 h-5 text-blue-500" />
              Quarantined Records Inventory
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Quarantined entity rows stored in <code className="text-blue-500">stg_quarantined_record</code> awaiting remediation or replay.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 bg-slate-50 dark:bg-navy-950 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-navy-800">
              <span className="text-xs text-slate-400">Entity:</span>
              <select
                value={entityFilter}
                onChange={(e) => setEntityFilter(e.target.value)}
                className="bg-transparent text-xs text-slate-800 dark:text-slate-200 focus:outline-none cursor-pointer"
              >
                <option value="" className="bg-white dark:bg-navy-900">All Entities</option>
                <option value="TRANSACTION" className="bg-white dark:bg-navy-900">TRANSACTION</option>
                <option value="ACCOUNT" className="bg-white dark:bg-navy-900">ACCOUNT</option>
                <option value="CUSTOMER" className="bg-white dark:bg-navy-900">CUSTOMER</option>
                <option value="BRANCH" className="bg-white dark:bg-navy-900">BRANCH</option>
              </select>
            </div>
          </div>
        </div>

        {quarantineItems.length === 0 ? (
          <EmptyState
            title="Quarantine Table Empty"
            message="No records are currently held in the quarantine staging layer for this filter."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 dark:border-navy-800 text-slate-400 uppercase font-semibold">
                  <th className="py-3 px-3">Batch ID</th>
                  <th className="py-3 px-3">Entity Type</th>
                  <th className="py-3 px-3">Primary Trigger Rule</th>
                  <th className="py-3 px-3 text-right">Quarantined Rows</th>
                  <th className="py-3 px-3 text-right">Recorded Issues</th>
                  <th className="py-3 px-3 text-right">First Quarantined</th>
                  <th className="py-3 px-3 text-right">Last Quarantined</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-navy-800 text-slate-600 dark:text-slate-300">
                {quarantineItems.map((q, idx) => (
                  <tr key={`${q.batch_id}-${q.entity_type}-${idx}`} className="hover:bg-slate-50 dark:hover:bg-navy-800/40">
                    <td className="py-3 px-3 font-mono font-medium text-blue-600 dark:text-blue-400">
                      {q.batch_id}
                    </td>
                    <td className="py-3 px-3">
                      <Badge variant="brand">{q.entity_type}</Badge>
                    </td>
                    <td className="py-3 px-3 font-mono text-slate-700 dark:text-slate-300">
                      {q.primary_rule_code || '—'}
                    </td>
                    <td className="py-3 px-3 text-right font-bold text-rose-600 dark:text-rose-400">
                      {q.quarantined_rows.toLocaleString()}
                    </td>
                    <td className="py-3 px-3 text-right font-medium">
                      {q.recorded_issue_count.toLocaleString()}
                    </td>
                    <td className="py-3 px-3 text-right text-slate-400">
                      {formatDate(q.first_quarantined_at)}
                    </td>
                    <td className="py-3 px-3 text-right text-slate-400">
                      {formatDate(q.last_quarantined_at)}
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
