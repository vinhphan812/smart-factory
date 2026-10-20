/**
 * Root application component with routing and error handling
 */

import React, { useEffect, Component } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
<<<<<<< HEAD
import { AppLayout } from '../components/AppLayout';
import { GatewayWsProvider } from '../hooks/useGatewayWs';
=======
import { Sidebar } from '../layout/Sidebar';
import { Header } from '../layout/Header';
import { GatewayWsProvider } from '../hooks/useGatewayWs';
import { OverviewPage } from '../pages/OverviewPage';
>>>>>>> 6dcf5f0 (feat(dashboard): #149 implement design system, navigation shell, and 9-module overview)
import { TelemetryPage } from '../pages/TelemetryPage';
import { EventsPage } from '../pages/EventsPage';

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
<<<<<<< HEAD
          <AppLayout>
            <Routes>
              <Route path="/" element={<TelemetryPage />} />
              <Route path="/telemetry" element={<TelemetryPage />} />
              <Route path="/events" element={<EventsPage />} />
            </Routes>
          </AppLayout>
=======
          <div className="min-h-screen flex flex-col bg-[var(--color-bg-primary)]">
            {/* Skip to content link for accessibility */}
            <a
              href="#main-content"
              className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:bg-[var(--color-primary)] focus:text-white focus:px-4 focus:py-2 focus:rounded-lg focus:outline-none"
            >
              Skip to content
            </a>

            {/* Header */}
            <Header />

            <div className="flex-1 flex">
              {/* Sidebar with 9-module navigation */}
              <Sidebar />

              {/* Main Content */}
              <main
                id="main-content"
                className="flex-1 p-6 overflow-auto"
                role="main"
              >
                <Routes>
                  <Route path="/" element={<OverviewPage />} />
                  <Route path="/telemetry" element={<TelemetryPage />} />
                  <Route path="/events" element={<EventsPage />} />
                  {/* Module detail pages - placeholder routes */}
                  <Route path="/modules/:moduleId" element={<ModuleDetailPage />} />
                </Routes>
              </main>
            </div>
          </div>
>>>>>>> 6dcf5f0 (feat(dashboard): #149 implement design system, navigation shell, and 9-module overview)
        </GatewayWsProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

<<<<<<< HEAD
=======
// Placeholder module detail page
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

>>>>>>> 6dcf5f0 (feat(dashboard): #149 implement design system, navigation shell, and 9-module overview)
export default App;
