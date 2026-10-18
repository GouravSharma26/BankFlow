/**
 * BankFlow Reporting API Client.
 *
 * Implements typed requests to the FastAPI backend conforming to docs/dashboard_api_contract.md.
 * Provides deterministic synthetic fixtures when Demo Mode is explicitly enabled.
 * Never silently replaces real API connection errors with demo data.
 */

import {
  HealthResponse,
  OverviewResponse,
  DailyTrendItem,
  DepositWithdrawalItem,
  BranchChannelItem,
  TypeMixItem,
  QualitySummaryItem,
  BatchExecutionItem,
  QuarantineItem,
  PaginatedTransactionsResponse,
  TransactionFilters,
  DailyFilters,
  DepositWithdrawalFilters,
  BranchChannelFilters,
  QualityFilters,
  BatchesFilters,
  QuarantineFilters,
} from './types';

import {
  DEMO_HEALTH,
  DEMO_OVERVIEW,
  DEMO_DAILY,
  DEMO_DEPOSIT_WITHDRAWAL,
  DEMO_BRANCH_CHANNEL,
  DEMO_TYPE_MIX,
  DEMO_QUALITY,
  DEMO_BATCHES,
  DEMO_QUARANTINE,
  getDemoTransactionsResponse,
} from '../data/demoFixtures';

export class ApiError extends Error {
  public statusCode: number;
  public details?: unknown;

  constructor(message: string, statusCode: number = 0, details?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.details = details;
  }
}

export function getApiBaseUrl(): string {
  // Vite env variable or default local FastAPI server URL
  return import.meta.env.VITE_BANKFLOW_API_BASE_URL || 'http://localhost:8000';
}

function buildQueryString(params: Record<string, string | number | undefined | null>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      query.append(key, String(value));
    }
  }
  const qs = query.toString();
  return qs ? `?${qs}` : '';
}

async function fetchFromApi<T>(endpoint: string, params: Record<string, string | number | undefined | null> = {}): Promise<T> {
  const baseUrl = getApiBaseUrl().replace(/\/+$/, '');
  const url = `${baseUrl}${endpoint}${buildQueryString(params)}`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });
  } catch (err) {
    const errorMsg = err instanceof Error ? err.message : 'Network request failed';
    throw new ApiError(
      `Unable to connect to BankFlow API at ${baseUrl}. Ensure backend is running ('python -m bankflow serve'). Details: ${errorMsg}`,
      0
    );
  }

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status} ${response.statusText}`;
    try {
      const errorJson = await response.json();
      if (errorJson && typeof errorJson === 'object' && 'detail' in errorJson) {
        errorDetail = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail);
      }
    } catch {
      // Ignore JSON parse errors on non-json error responses
    }
    throw new ApiError(errorDetail, response.status);
  }

  return response.json() as Promise<T>;
}

export const BankFlowApi = {
  async getHealth(isDemo: boolean = false): Promise<HealthResponse> {
    if (isDemo) {
      return Promise.resolve(DEMO_HEALTH);
    }
    return fetchFromApi<HealthResponse>('/api/v1/health');
  },

  async getOverview(currency?: string, isDemo: boolean = false): Promise<OverviewResponse> {
    if (isDemo) {
      if (!currency) return Promise.resolve(DEMO_OVERVIEW);
      const filtered = DEMO_OVERVIEW.metrics_by_currency.filter((m) => m.currency === currency);
      return Promise.resolve({
        ...DEMO_OVERVIEW,
        metrics_by_currency: filtered.length > 0 ? filtered : DEMO_OVERVIEW.metrics_by_currency,
      });
    }
    return fetchFromApi<OverviewResponse>('/api/v1/overview', { currency });
  },

  async getDaily(filters: DailyFilters = {}, isDemo: boolean = false): Promise<DailyTrendItem[]> {
    if (isDemo) {
      let data = [...DEMO_DAILY];
      if (filters.currency) {
        data = data.filter((d) => d.currency === filters.currency);
      }
      if (filters.limit) {
        data = data.slice(0, filters.limit);
      }
      return Promise.resolve(data);
    }
    return fetchFromApi<DailyTrendItem[]>('/api/v1/daily', {
      currency: filters.currency,
      start_date: filters.start_date,
      end_date: filters.end_date,
      limit: filters.limit,
    });
  },

  async getDepositWithdrawal(filters: DepositWithdrawalFilters = {}, isDemo: boolean = false): Promise<DepositWithdrawalItem[]> {
    if (isDemo) {
      let data = [...DEMO_DEPOSIT_WITHDRAWAL];
      if (filters.currency) {
        data = data.filter((d) => d.currency === filters.currency);
      }
      if (filters.limit) {
        data = data.slice(0, filters.limit);
      }
      return Promise.resolve(data);
    }
    return fetchFromApi<DepositWithdrawalItem[]>('/api/v1/deposit-withdrawal', {
      currency: filters.currency,
      start_date: filters.start_date,
      end_date: filters.end_date,
      limit: filters.limit,
    });
  },

  async getBranchChannel(filters: BranchChannelFilters = {}, isDemo: boolean = false): Promise<BranchChannelItem[]> {
    if (isDemo) {
      let data = [...DEMO_BRANCH_CHANNEL];
      if (filters.currency) {
        data = data.filter((d) => d.currency === filters.currency);
      }
      if (filters.channel) {
        data = data.filter((d) => d.channel === filters.channel);
      }
      if (filters.region) {
        data = data.filter((d) => d.region === filters.region);
      }
      if (filters.limit) {
        data = data.slice(0, filters.limit);
      }
      return Promise.resolve(data);
    }
    return fetchFromApi<BranchChannelItem[]>('/api/v1/branch-channel', {
      currency: filters.currency,
      channel: filters.channel,
      branch_id: filters.branch_id,
      region: filters.region,
      limit: filters.limit,
    });
  },

  async getTypeMix(currency?: string, isDemo: boolean = false): Promise<TypeMixItem[]> {
    if (isDemo) {
      let data = [...DEMO_TYPE_MIX];
      if (currency) {
        data = data.filter((d) => d.currency === currency);
      }
      return Promise.resolve(data);
    }
    return fetchFromApi<TypeMixItem[]>('/api/v1/type-mix', { currency });
  },

  async getQuality(filters: QualityFilters = {}, isDemo: boolean = false): Promise<QualitySummaryItem[]> {
    if (isDemo) {
      let data = [...DEMO_QUALITY];
      if (filters.severity && filters.severity !== 'ALL') {
        data = data.filter((d) => d.severity === filters.severity);
      }
      if (filters.disposition && filters.disposition !== 'ALL') {
        data = data.filter((d) => d.disposition === filters.disposition);
      }
      if (filters.limit) {
        data = data.slice(0, filters.limit);
      }
      return Promise.resolve(data);
    }
    return fetchFromApi<QualitySummaryItem[]>('/api/v1/quality', {
      severity: filters.severity === 'ALL' ? undefined : filters.severity,
      disposition: filters.disposition === 'ALL' ? undefined : filters.disposition,
      limit: filters.limit,
    });
  },

  async getBatches(filters: BatchesFilters = {}, isDemo: boolean = false): Promise<BatchExecutionItem[]> {
    if (isDemo) {
      let data = [...DEMO_BATCHES];
      if (filters.status && filters.status !== 'ALL') {
        data = data.filter((b) => b.status === filters.status);
      }
      if (filters.reconciliation_status && filters.reconciliation_status !== 'ALL') {
        data = data.filter((b) => b.reconciliation_status === filters.reconciliation_status);
      }
      if (filters.limit) {
        data = data.slice(0, filters.limit);
      }
      return Promise.resolve(data);
    }
    return fetchFromApi<BatchExecutionItem[]>('/api/v1/batches', {
      status: filters.status === 'ALL' ? undefined : filters.status,
      reconciliation_status: filters.reconciliation_status === 'ALL' ? undefined : filters.reconciliation_status,
      limit: filters.limit,
    });
  },

  async getQuarantine(filters: QuarantineFilters = {}, isDemo: boolean = false): Promise<QuarantineItem[]> {
    if (isDemo) {
      let data = [...DEMO_QUARANTINE];
      if (filters.batch_id) {
        data = data.filter((q) => q.batch_id === filters.batch_id);
      }
      if (filters.entity_type && filters.entity_type !== 'ALL') {
        data = data.filter((q) => q.entity_type === filters.entity_type);
      }
      if (filters.primary_rule_code) {
        data = data.filter((q) => q.primary_rule_code === filters.primary_rule_code);
      }
      if (filters.limit) {
        data = data.slice(0, filters.limit);
      }
      return Promise.resolve(data);
    }
    return fetchFromApi<QuarantineItem[]>('/api/v1/quarantine', {
      batch_id: filters.batch_id,
      entity_type: filters.entity_type === 'ALL' ? undefined : filters.entity_type,
      primary_rule_code: filters.primary_rule_code,
      limit: filters.limit,
    });
  },

  async getTransactions(filters: TransactionFilters = {}, isDemo: boolean = false): Promise<PaginatedTransactionsResponse> {
    if (isDemo) {
      return Promise.resolve(
        getDemoTransactionsResponse(
          filters.page || 1,
          filters.page_size || 25,
          filters.currency,
          filters.status,
          filters.transaction_type,
          filters.channel
        )
      );
    }
    return fetchFromApi<PaginatedTransactionsResponse>('/api/v1/transactions', {
      page: filters.page,
      page_size: filters.page_size,
      currency: filters.currency,
      status: filters.status === 'ALL' ? undefined : filters.status,
      transaction_type: filters.transaction_type === 'ALL' ? undefined : filters.transaction_type,
      channel: filters.channel === 'ALL' ? undefined : filters.channel,
      start_date: filters.start_date,
      end_date: filters.end_date,
      sort_by: filters.sort_by,
      sort_order: filters.sort_order,
    });
  },
};
