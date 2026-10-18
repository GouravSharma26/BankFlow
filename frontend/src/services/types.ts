/**
 * TypeScript types for the BankFlow Reporting API.
 * Strict match with docs/dashboard_api_contract.md and src/bankflow/api/schemas.py.
 */

export interface HealthResponse {
  status: 'healthy' | 'degraded';
  service: string;
  version: string;
  database: 'connected' | 'unavailable';
}

export interface OverviewCurrencySummary {
  currency: string;
  total_transactions: number;
  completed_transactions: number;
  gross_transaction_amount: string;
  completed_gross_amount: string;
  acceptance_rate_pct: string;
  active_accounts: number;
  active_customers: number;
}

export interface OverviewResponse {
  currencies: string[];
  earliest_date: string | null;
  latest_date: string | null;
  metrics_by_currency: OverviewCurrencySummary[];
  total_batches: number;
  latest_batch_status: string | null;
  total_quality_issues: number;
  total_quarantined_records: number;
}

export interface DailyTrendItem {
  date_key: number;
  reporting_date: string;
  year_number: number;
  month_number: number;
  month_name: string;
  day_name: string;
  is_weekend: boolean;
  currency: string;
  total_transaction_count: number;
  completed_transaction_count: number;
  pending_transaction_count: number;
  failed_transaction_count: number;
  reversed_transaction_count: number;
  active_accounts: number;
  active_customers: number;
  gross_transaction_amount: string;
  completed_gross_amount: string;
}

export interface DepositWithdrawalItem {
  date_key: number;
  reporting_date: string;
  currency: string;
  deposit_count: number;
  deposit_gross_amount: string;
  completed_deposit_count: number;
  completed_deposit_gross_amount: string;
  withdrawal_count: number;
  withdrawal_gross_amount: string;
  completed_withdrawal_count: number;
  completed_withdrawal_gross_amount: string;
  reversal_count: number;
  reversal_gross_amount: string;
  deposit_value_share_pct: string;
  withdrawal_value_share_pct: string;
}

export interface BranchChannelItem {
  region: string;
  branch_id: string;
  branch_name: string;
  channel: 'BRANCH' | 'ATM' | 'ONLINE' | 'MOBILE' | string;
  currency: string;
  total_transaction_count: number;
  completed_transaction_count: number;
  distinct_accounts: number;
  distinct_customers: number;
  gross_transaction_amount: string;
  completed_gross_amount: string;
}

export interface TypeMixItem {
  transaction_type_code: string;
  transaction_type_name: string;
  transaction_family: string;
  currency: string;
  total_transaction_count: number;
  completed_transaction_count: number;
  failed_transaction_count: number;
  pending_transaction_count: number;
  reversed_transaction_count: number;
  gross_transaction_amount: string;
  completed_gross_amount: string;
  event_share_pct: string;
  value_share_pct: string;
}

export interface QualitySummaryItem {
  rule_code: string;
  severity: 'ERROR' | 'WARNING' | 'INFO' | string;
  disposition: 'ACCEPTED' | 'REJECTED' | 'WARNED' | 'SKIPPED' | string;
  issue_count: number;
  affected_source_rows: number;
  affected_batches: number;
}

export interface BatchExecutionItem {
  batch_id: string;
  source_name: string;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  status: 'SUCCEEDED' | 'SUCCEEDED_WITH_REJECTIONS' | 'FAILED' | string;
  records_extracted: number;
  records_staged: number;
  records_valid: number;
  records_rejected: number;
  records_inserted: number;
  records_updated: number;
  records_skipped: number;
  rejection_rate_pct: string;
  reconciliation_status: 'RECONCILED' | 'UNRECONCILED' | 'DISCREPANCY_DETECTED' | null | string;
  error_summary: string | null;
}

export interface QuarantineItem {
  batch_id: string;
  entity_type: string;
  primary_rule_code: string;
  quarantined_rows: number;
  recorded_issue_count: number;
  first_quarantined_at: string | null;
  last_quarantined_at: string | null;
}

export interface TransactionDetailItem {
  transaction_id: string;
  source_system: string;
  account_id: string;
  customer_id: string;
  branch_id: string;
  branch_name: string;
  region: string;
  transaction_type: string;
  type_name: string;
  transaction_family: string;
  amount: string;
  currency: string;
  status: 'COMPLETED' | 'PENDING' | 'FAILED' | 'REVERSED' | string;
  channel: 'BRANCH' | 'ATM' | 'ONLINE' | 'MOBILE' | string;
  transaction_timestamp: string;
  reporting_date: string;
  batch_id: string;
  loaded_at: string | null;
}

export type TransactionItem = TransactionDetailItem;

export interface PaginatedTransactionsResponse {
  items: TransactionDetailItem[];
  total: number;
  total_count?: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface TransactionFilters {
  page?: number;
  page_size?: number;
  currency?: string;
  status?: string;
  transaction_type?: string;
  channel?: string;
  start_date?: string;
  end_date?: string;
  sort_by?: 'transaction_timestamp' | 'amount' | 'transaction_id' | 'reporting_date';
  sort_order?: 'asc' | 'desc';
}

export interface DailyFilters {
  currency?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
}

export interface DepositWithdrawalFilters {
  currency?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
}

export interface BranchChannelFilters {
  currency?: string;
  channel?: string;
  branch_id?: string;
  region?: string;
  limit?: number;
}

export interface QualityFilters {
  severity?: string;
  disposition?: string;
  limit?: number;
}

export interface BatchesFilters {
  status?: string;
  reconciliation_status?: string;
  limit?: number;
}

export interface QuarantineFilters {
  batch_id?: string;
  entity_type?: string;
  primary_rule_code?: string;
  limit?: number;
}
