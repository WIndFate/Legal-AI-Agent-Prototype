import { Component, StrictMode, Suspense, lazy, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';

import './i18n';
import './App.css';

import Layout from './components/Layout';

const HomePage = lazy(() => import('./pages/HomePage'));
const PaymentPage = lazy(() => import('./pages/PaymentPage'));
const ReviewPage = lazy(() => import('./pages/ReviewPage'));
const ReportPage = lazy(() => import('./pages/ReportPage'));
const PrivacyPage = lazy(() => import('./pages/PrivacyPage'));
const TermsPage = lazy(() => import('./pages/TermsPage'));

function RouteFallback() {
  return (
    <div className="route-fallback">
      <div className="spinner" />
    </div>
  );
}

function AnalyticsBootstrap() {
  useEffect(() => {
    import('./analytics').then(({ bootstrapAnalytics }) => {
      void bootstrapAnalytics();
    });
  }, []);

  return null;
}

class AppErrorBoundary extends Component<{ children: React.ReactNode }, { hasError: boolean }> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  override render() {
    if (this.state.hasError) {
      return <p>An error occurred. Please refresh the page.</p>;
    }

    return this.props.children;
  }
}

function AppRoutes() {
  return (
    <BrowserRouter>
      <AnalyticsBootstrap />
      <Layout>
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/payment/:orderId" element={<PaymentPage />} />
            <Route path="/review/:orderId" element={<ReviewPage />} />
            <Route path="/report/:orderId" element={<ReportPage />} />
            <Route path="/privacy" element={<PrivacyPage />} />
            <Route path="/terms" element={<TermsPage />} />
          </Routes>
        </Suspense>
      </Layout>
    </BrowserRouter>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppErrorBoundary>
      <AppRoutes />
    </AppErrorBoundary>
  </StrictMode>,
);
