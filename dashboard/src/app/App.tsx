/**
 * Root application component with routing and error handling
 */

import React, { useEffect, Component } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { AppLayout } from '../components/AppLayout';
import { GatewayWsProvider } from '../hooks/useGatewayWs';
import { ProtectedRoute } from '../components/Auth';
import { LoginPage } from '../pages/LoginPage';
import { TelemetryPage } from '../pages/TelemetryPage';
import { EventsPage } from '../pages/EventsPage';
import { IncidentsPage, IncidentDetailPage } from '../pages/incidents';
import { OverviewPage } from '../pages/OverviewPage';
import { useAuth, AuthProvider } from '../store/authContext';

// Error Boundary class component
interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

class ErrorBoundary extends Component<{ children: React.ReactNode }, ErrorBoundaryState> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: undefined };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    console.error('Error caught by boundary:', error, errorInfo);
  }

  render(): React.ReactNode {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-900 text-gray-100">
          <div className="text-center p-8">
            <h1 className="text-2xl font-bold text-red-400 mb-4">Something went wrong</h1>
            <p className="text-gray-400 mb-4">{this.state.error?.message}</p>
            <button
              onClick={() => window.location.reload()}
              className="bg-[var(--color-primary)] hover:bg-[var(--color-primary-dark)] px-4 py-2 rounded font-medium"
            >
              Reload Page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

/**
 * App wrapper that checks for existing session on mount
 */
function AuthCheck({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, tokens, refreshSession } = useAuth();

  useEffect(() => {
    // Try to refresh session if tokens exist
    if (tokens?.refresh_token && !isAuthenticated) {
      refreshSession();
    }
  }, []);

  return <>{children}</>;
}

/**
 * AppLayout wrapper that uses Outlet for child routes
 */
function AppLayoutWithOutlet() {
  return (
    <AppLayout>
      <Outlet />
    </AppLayout>
  );
}

function App(): React.ReactElement {
  // Auto-connect to gateway on mount
  useEffect(() => {
    console.log('Smart Factory Dashboard initialized');
  }, []);

  return (
    <ErrorBoundary>
      <AuthProvider>
        <BrowserRouter>
          <GatewayWsProvider>
            <AuthCheck>
              <Routes>
                {/* Public routes */}
                <Route path="/login" element={<LoginPage />} />

                {/* Protected routes with layout */}
                <Route
                  path="/"
                  element={
                    <ProtectedRoute requiredPermission="dashboard:view">
                      <AppLayoutWithOutlet />
                    </ProtectedRoute>
                  }
                >
                  <Route index element={<OverviewPage />} />
                  <Route path="telemetry" element={<TelemetryPage />} />
                  <Route path="events" element={<EventsPage />} />
                  <Route path="incidents" element={<IncidentsPage />} />
                  <Route path="incidents/:incidentId" element={<IncidentDetailPage />} />
                  <Route path="modules/:moduleId" element={<ModuleDetailPage />} />
                </Route>

                {/* Fallback to login */}
                <Route path="*" element={<Navigate to="/login" replace />} />
              </Routes>
            </AuthCheck>
          </GatewayWsProvider>
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  );
}

// Placeholder module detail page (route target for the 9-module sidebar links)
function ModuleDetailPage() {
  return (
    <div className="max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">
        Module Detail
      </h1>
      <p className="text-[var(--color-text-muted)] mt-2">
        Module detail view coming soon...
      </p>
    </div>
  );
}

export default App;
