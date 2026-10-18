import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { Badge } from '../components/common/Badge';
import { MetricCard } from '../components/common/MetricCard';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { EmptyState } from '../components/common/EmptyState';
import { DemoBanner } from '../components/common/DemoBanner';
import { Sidebar } from '../components/layout/Sidebar';
import { DashboardProvider, useDashboard } from '../context/DashboardContext';
import { OverviewView } from '../components/overview/OverviewView';
import { AnalyticsView } from '../components/analytics/AnalyticsView';
import { QualityView } from '../components/quality/QualityView';
import { TransactionsView } from '../components/transactions/TransactionsView';
import { PipelineView } from '../components/pipeline/PipelineView';

// Helper component to test context values
const ContextTester: React.FC = () => {
  const { currentTab, setCurrentTab, isDemoMode, setDemoMode, selectedCurrency, setSelectedCurrency } = useDashboard();
  return (
    <div>
      <span data-testid="current-tab">{currentTab}</span>
      <span data-testid="is-demo">{String(isDemoMode)}</span>
      <span data-testid="selected-currency">{selectedCurrency}</span>
      <button onClick={() => setCurrentTab('pipeline')}>Go to Pipeline</button>
      <button onClick={() => setDemoMode(true)}>Enable Demo</button>
      <button onClick={() => setDemoMode(false)}>Disable Demo</button>
      <button onClick={() => setSelectedCurrency('EUR')}>Select EUR</button>
    </div>
  );
};

describe('Common Components', () => {
  describe('Badge', () => {
    it('renders text with success variant styling', () => {
      render(<Badge variant="success">Completed</Badge>);
      const badge = screen.getByText('Completed');
      expect(badge).toBeInTheDocument();
      expect(badge.className).toContain('text-emerald-700');
    });

    it('renders with dot indicator when dot is true', () => {
      render(<Badge variant="danger" dot>Failed</Badge>);
      const dot = screen.getByTestId('badge-dot');
      expect(dot).toBeInTheDocument();
    });
  });

  describe('MetricCard', () => {
    it('renders title, value, and currency pill', () => {
      render(
        <MetricCard
          title="Gross Transaction Amount"
          value="$124,500.00"
          currency="USD"
          subtitle="Non-balance gross volume"
        />
      );
      expect(screen.getByText('Gross Transaction Amount')).toBeInTheDocument();
      expect(screen.getByText('$124,500.00')).toBeInTheDocument();
      expect(screen.getByText('USD')).toBeInTheDocument();
      expect(screen.getByText('Non-balance gross volume')).toBeInTheDocument();
    });
  });

  describe('ErrorAlert', () => {
    it('renders error message, status code badge, and invokes onRetry', () => {
      const retryMock = vi.fn();
      render(
        <ErrorAlert
          title="API Network Error"
          message="Connection refused on port 8000"
          statusCode={503}
          onRetry={retryMock}
        />
      );

      expect(screen.getByText('API Network Error')).toBeInTheDocument();
      expect(screen.getByText('Connection refused on port 8000')).toBeInTheDocument();
      expect(screen.getByText('HTTP 503')).toBeInTheDocument();

      const retryButton = screen.getByRole('button', { name: /retry/i });
      fireEvent.click(retryButton);
      expect(retryMock).toHaveBeenCalledTimes(1);
    });
  });

  describe('EmptyState', () => {
    it('renders title, description, and handles reset action', () => {
      const resetMock = vi.fn();
      render(
        <EmptyState
          title="No Batches Found"
          message="No records matched status filter"
          onClearFilters={resetMock}
        />
      );

      expect(screen.getByText('No Batches Found')).toBeInTheDocument();
      expect(screen.getByText('No records matched status filter')).toBeInTheDocument();

      const resetBtn = screen.getByRole('button', { name: /reset all filters/i });
      fireEvent.click(resetBtn);
      expect(resetMock).toHaveBeenCalledTimes(1);
    });
  });
});

describe('Dashboard State and Navigation', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('provides default state and allows tab switching and currency changing', () => {
    render(
      <DashboardProvider>
        <ContextTester />
      </DashboardProvider>
    );

    expect(screen.getByTestId('current-tab')).toHaveTextContent('overview');
    expect(screen.getByTestId('selected-currency')).toHaveTextContent('USD');

    fireEvent.click(screen.getByText('Go to Pipeline'));
    expect(screen.getByTestId('current-tab')).toHaveTextContent('pipeline');

    fireEvent.click(screen.getByText('Select EUR'));
    expect(screen.getByTestId('selected-currency')).toHaveTextContent('EUR');
  });

  it('renders Sidebar with all 5 core navigation options and updates current tab', () => {
    render(
      <DashboardProvider>
        <div className="flex">
          <Sidebar />
          <ContextTester />
        </div>
      </DashboardProvider>
    );

    expect(screen.getByText('Overview')).toBeInTheDocument();
    expect(screen.getByText('Transaction Analytics')).toBeInTheDocument();
    expect(screen.getByText('Data Quality')).toBeInTheDocument();
    expect(screen.getByText('Pipeline Monitoring')).toBeInTheDocument();
    expect(screen.getByText('Transactions')).toBeInTheDocument();

    // Click 'Data Quality' navigation
    fireEvent.click(screen.getByText('Data Quality'));
    expect(screen.getByTestId('current-tab')).toHaveTextContent('quality');
  });

  it('renders DemoBanner when demo mode is active and allows disabling demo mode', () => {
    localStorage.setItem('bankflow_demo_mode', 'true');

    render(
      <DashboardProvider>
        <div>
          <DemoBanner />
          <ContextTester />
        </div>
      </DashboardProvider>
    );

    // Unambiguous persistent DEMO DATA MODE indicator
    expect(screen.getByText(/DEMO DATA/i)).toBeInTheDocument();
    expect(screen.getByText(/deterministic synthetic preview fixtures/i)).toBeInTheDocument();

    const switchBtn = screen.getByRole('button', { name: /connect to live api/i });
    fireEvent.click(switchBtn);

    expect(screen.getByTestId('is-demo')).toHaveTextContent('false');
  });
});

describe('Page Views in Demo Mode', () => {
  beforeEach(() => {
    localStorage.setItem('bankflow_demo_mode', 'true');
  });

  it('renders OverviewView with KPI cards and batch summary', async () => {
    render(
      <DashboardProvider>
        <OverviewView />
      </DashboardProvider>
    );

    // Wait for async load in demo mode
    await waitFor(() => {
      expect(screen.getByText('Total Transactions')).toBeInTheDocument();
    });

    expect(screen.getByText('Gross Transaction Value')).toBeInTheDocument();
    expect(screen.getByText('Acceptance Rate')).toBeInTheDocument();
    expect(screen.getByText('Active Accounts & Customers')).toBeInTheDocument();
    expect(screen.getByText('Latest Batch Status')).toBeInTheDocument();
    expect(screen.getByText('Quarantine Inventory')).toBeInTheDocument();
    expect(screen.getByText('Daily Transaction Activity & Value Trend')).toBeInTheDocument();
  });

  it('renders TransactionsView with paginated data and filters', async () => {
    render(
      <DashboardProvider>
        <TransactionsView />
      </DashboardProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/Transactions Explorer & Ledger/i)).toBeInTheDocument();
    });

    // Check table headers and rows rendered
    expect(screen.getByText('Transaction ID')).toBeInTheDocument();
    expect(screen.getByText('Date & Timestamp')).toBeInTheDocument();
    expect(screen.getByText('Type & Family')).toBeInTheDocument();
  });

  it('renders PipelineView with batch history and reconciliation badges', async () => {
    render(
      <DashboardProvider>
        <PipelineView />
      </DashboardProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/ETL Pipeline & Batch Reconciliation/i)).toBeInTheDocument();
    });

    expect(screen.getByText('Batch Execution & Reconciliation Audit Trail')).toBeInTheDocument();
    expect(screen.getByText('Extracted')).toBeInTheDocument();
    expect(screen.getByText('Warehouse Inserted')).toBeInTheDocument();
  });

  it('renders AnalyticsView with charts and breakdown tables', async () => {
    render(
      <DashboardProvider>
        <AnalyticsView />
      </DashboardProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/Transaction Analytics & Trend Explorer/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Daily Volume & Gross Value Trends/i)).toBeInTheDocument();
    expect(screen.getByText(/Deposit vs Withdrawal Value Share/i)).toBeInTheDocument();
    expect(screen.getByText(/Transaction Type & Family Mix/i)).toBeInTheDocument();
    expect(screen.getByText(/Branch & Channel Performance Breakdown/i)).toBeInTheDocument();
  });

  it('renders QualityView with rule defect inventory and quarantine table', async () => {
    render(
      <DashboardProvider>
        <QualityView />
      </DashboardProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/Data Quality & Quarantine Monitor/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Validation Rules & Defect Inventory/i)).toBeInTheDocument();
    expect(screen.getByText(/Quarantined Records Inventory/i)).toBeInTheDocument();
    expect(screen.getByText('Row-Level Rejection:')).toBeInTheDocument();
    expect(screen.getByText('Batch-Level Failure:')).toBeInTheDocument();
  });
});
