import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { BankFlowApi, ApiError, getApiBaseUrl } from '../services/api';
import { DEMO_HEALTH } from '../data/demoFixtures';

describe('BankFlowApi Client', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  describe('Demo Mode Fixtures', () => {
    it('returns DEMO_HEALTH fixture when isDemo is true', async () => {
      const health = await BankFlowApi.getHealth(true);
      expect(health).toEqual(DEMO_HEALTH);
      expect(health.status).toBe('healthy');
      expect(health.database).toBe('connected');
    });

    it('returns DEMO_OVERVIEW fixture for USD when isDemo is true', async () => {
      const overview = await BankFlowApi.getOverview('USD', true);
      expect(overview.currencies).toContain('USD');
      expect(overview.metrics_by_currency.length).toBeGreaterThan(0);
      const usdMetric = overview.metrics_by_currency.find((m) => m.currency === 'USD');
      expect(usdMetric).toBeDefined();
      expect(usdMetric?.gross_transaction_amount).toBeDefined();
    });

    it('returns filtered transactions in demo mode', async () => {
      const page1 = await BankFlowApi.getTransactions({ page: 1, page_size: 10, currency: 'USD' }, true);
      expect(page1.items.length).toBeLessThanOrEqual(10);
      expect(page1.total).toBeGreaterThan(0);
      expect(page1.items.every((item) => item.currency === 'USD')).toBe(true);
    });

    it('returns batch history in demo mode', async () => {
      const batches = await BankFlowApi.getBatches({ limit: 5 }, true);
      expect(batches.length).toBeGreaterThan(0);
      expect(batches[0].batch_id).toBeDefined();
      expect(batches[0].reconciliation_status).toBe('RECONCILED');
    });

    it('returns data quality summary in demo mode', async () => {
      const quality = await BankFlowApi.getQuality({ limit: 10 }, true);
      expect(quality.length).toBeGreaterThan(0);
      expect(quality[0].rule_code).toBeDefined();
      expect(quality[0].severity).toBeDefined();
    });
  });

  describe('Connected Mode API Requests', () => {
    it('calls fetch with proper URL and headers on health check', async () => {
      const mockResponse = {
        status: 'healthy',
        service: 'bankflow-reporting-api',
        version: '0.1.0',
        database: 'connected',
      };

      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      const result = await BankFlowApi.getHealth(false);
      expect(result).toEqual(mockResponse);
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/health'),
        expect.objectContaining({
          headers: expect.objectContaining({ Accept: 'application/json' }),
        })
      );
    });

    it('passes query parameters properly for daily endpoint', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [],
      } as Response);

      await BankFlowApi.getDaily(
        {
          currency: 'EUR',
          start_date: '2026-03-01',
          end_date: '2026-03-15',
          limit: 15,
        },
        false
      );

      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringMatching(/\/api\/v1\/daily\?currency=EUR&start_date=2026-03-01&end_date=2026-03-15&limit=15/),
        expect.anything()
      );
    });

    it('throws ApiError with status and message when server returns 4xx/5xx', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        json: async () => ({ detail: 'Batch not found' }),
      } as Response);

      await expect(BankFlowApi.getBatches({ status: 'NONEXISTENT' }, false)).rejects.toThrow(ApiError);
      try {
        await BankFlowApi.getBatches({ status: 'NONEXISTENT' }, false);
      } catch (err) {
        expect(err).toBeInstanceOf(ApiError);
        const apiErr = err as ApiError;
        expect(apiErr.statusCode).toBe(404);
        expect(apiErr.message).toContain('Batch not found');
      }
    });

    it('throws ApiError with statusCode 0 on connection/network failure without fallback to mock', async () => {
      globalThis.fetch = vi.fn().mockRejectedValue(new Error('Failed to fetch'));

      await expect(BankFlowApi.getOverview('USD', false)).rejects.toThrow(ApiError);
      try {
        await BankFlowApi.getOverview('USD', false);
      } catch (err) {
        expect(err).toBeInstanceOf(ApiError);
        const apiErr = err as ApiError;
        expect(apiErr.statusCode).toBe(0);
        expect(apiErr.message).toContain('Unable to connect to BankFlow API');
      }
    });
  });

  describe('getApiBaseUrl URL Resolution & Protection', () => {
    const originalEnv = import.meta.env.VITE_BANKFLOW_API_BASE_URL;

    afterEach(() => {
      import.meta.env.VITE_BANKFLOW_API_BASE_URL = originalEnv;
    });

    it('returns configured VITE_BANKFLOW_API_BASE_URL without trailing slashes', () => {
      import.meta.env.VITE_BANKFLOW_API_BASE_URL = 'https://bankflow-api.onrender.com///';
      expect(getApiBaseUrl()).toBe('https://bankflow-api.onrender.com');
    });

    it('returns http://localhost:8000 when hostname is localhost and env is empty', () => {
      delete import.meta.env.VITE_BANKFLOW_API_BASE_URL;
      expect(getApiBaseUrl()).toBe('http://localhost:8000');
    });

    it('returns empty string on public domain without env var to protect against querying visitor localhost', () => {
      delete import.meta.env.VITE_BANKFLOW_API_BASE_URL;
      const originalLocation = window.location;
      // Mock public hostname
      Object.defineProperty(window, 'location', {
        value: { hostname: 'bankflow-analytics.vercel.app' },
        writable: true,
      });

      expect(getApiBaseUrl()).toBe('');

      // Restore location
      Object.defineProperty(window, 'location', {
        value: originalLocation,
        writable: true,
      });
    });
  });
});
