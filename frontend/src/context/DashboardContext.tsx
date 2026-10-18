import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { HealthResponse } from '../services/types';
import { BankFlowApi, getApiBaseUrl } from '../services/api';

export type TabType = 'overview' | 'analytics' | 'quality' | 'pipeline' | 'transactions';

interface DashboardContextType {
  currentTab: TabType;
  setCurrentTab: (tab: TabType) => void;
  selectedCurrency: string;
  setSelectedCurrency: (currency: string) => void;
  availableCurrencies: string[];
  setAvailableCurrencies: (currencies: string[]) => void;
  isDemoMode: boolean;
  setDemoMode: (enabled: boolean) => void;
  apiHealth: HealthResponse | null;
  healthLoading: boolean;
  healthError: string | null;
  refreshHealth: () => Promise<void>;
  apiBaseUrl: string;
}

const DashboardContext = createContext<DashboardContextType | undefined>(undefined);

export const DashboardProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [currentTab, setCurrentTab] = useState<TabType>('overview');
  const [selectedCurrency, setSelectedCurrency] = useState<string>('USD');
  const [availableCurrencies, setAvailableCurrencies] = useState<string[]>(['USD', 'EUR', 'GBP']);

  // Demo mode state: check env or localStorage
  const [isDemoMode, setIsDemoModeState] = useState<boolean>(() => {
    const envDemo = import.meta.env.VITE_DEMO_MODE;
    if (envDemo === 'true' || envDemo === true) return true;
    const stored = localStorage.getItem('bankflow_demo_mode');
    return stored === 'true';
  });

  const [apiHealth, setApiHealth] = useState<HealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(false);
  const [healthError, setHealthError] = useState<string | null>(null);

  const setDemoMode = useCallback((enabled: boolean) => {
    setIsDemoModeState(enabled);
    localStorage.setItem('bankflow_demo_mode', String(enabled));
  }, []);

  const refreshHealth = useCallback(async () => {
    setHealthLoading(true);
    setHealthError(null);
    try {
      const health = await BankFlowApi.getHealth(isDemoMode);
      setApiHealth(health);
      if (health.status !== 'healthy' || health.database !== 'connected') {
        setHealthError(`Service ${health.status}, Database ${health.database}`);
      }
    } catch (err) {
      setApiHealth(null);
      setHealthError(err instanceof Error ? err.message : 'Failed to reach API server');
    } finally {
      setHealthLoading(false);
    }
  }, [isDemoMode]);

  useEffect(() => {
    refreshHealth();
  }, [refreshHealth]);

  return (
    <DashboardContext.Provider
      value={{
        currentTab,
        setCurrentTab,
        selectedCurrency,
        setSelectedCurrency,
        availableCurrencies,
        setAvailableCurrencies,
        isDemoMode,
        setDemoMode,
        apiHealth,
        healthLoading,
        healthError,
        refreshHealth,
        apiBaseUrl: getApiBaseUrl(),
      }}
    >
      {children}
    </DashboardContext.Provider>
  );
};

export function useDashboard(): DashboardContextType {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error('useDashboard must be used within a DashboardProvider');
  }
  return context;
}
