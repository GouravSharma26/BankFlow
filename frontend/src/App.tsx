import React from 'react';
import { DashboardProvider, useDashboard } from './context/DashboardContext';
import { Layout } from './components/layout/Layout';
import { OverviewView } from './components/overview/OverviewView';
import { AnalyticsView } from './components/analytics/AnalyticsView';
import { QualityView } from './components/quality/QualityView';
import { PipelineView } from './components/pipeline/PipelineView';
import { TransactionsView } from './components/transactions/TransactionsView';

const DashboardContent: React.FC = () => {
  const { currentTab } = useDashboard();

  return (
    <Layout>
      {currentTab === 'overview' && <OverviewView />}
      {currentTab === 'analytics' && <AnalyticsView />}
      {currentTab === 'quality' && <QualityView />}
      {currentTab === 'pipeline' && <PipelineView />}
      {currentTab === 'transactions' && <TransactionsView />}
    </Layout>
  );
};

export function App() {
  return (
    <DashboardProvider>
      <DashboardContent />
    </DashboardProvider>
  );
}

export default App;
