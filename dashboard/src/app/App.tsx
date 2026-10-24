/**
 * Root application component with routing and error handling
 */

import React, { useEffect, Component } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { AppLayout } from '../components/AppLayout';
import { GatewayWsProvider } from '../hooks/useGatewayWs';
import { AppRoutes } from './routes';

// Error Boundary class component
interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

class ErrorBoundary extends Component<{ children: React.ReactNode }, ErrorBoundaryState> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
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

function App(): React.ReactElement {
  // Auto-connect to gateway on mount
  useEffect(() => {
    console.log('Smart Factory Dashboard initialized');
  }, []);

  return (
    <ErrorBoundary>
      <BrowserRouter>
        <GatewayWsProvider>
          {/* Single application shell (AppLayout renders the design-system
              Header + Sidebar with 9-module navigation) hosting all routes. */}
          <AppLayout>
            <AppRoutes />
          </AppLayout>
        </GatewayWsProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;
