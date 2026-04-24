import { Component, StrictMode, Suspense, lazy, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';

import './i18n';
import './styles/base.css';
import './styles/layout.css';
import './styles/home.css';
import './styles/review.css';
import './styles/report.css';
import './styles/responsive.css';
import './styles/ux.css';

import Layout from './components/Layout';

const HomePage = lazy(() => import('./pages/HomePage'));
const ExamplesPage = lazy(() => import('./pages/ExamplesPage'));
const PaymentPage = lazy(() => import('./pages/PaymentPage'));
const LookupPage = lazy(() => import('./pages/LookupPage'));
const ReviewPage = lazy(() => import('./pages/ReviewPage'));
const ReportPage = lazy(() => import('./pages/ReportPage'));
const PrivacyPage = lazy(() => import('./pages/PrivacyPage'));
const TermsPage = lazy(() => import('./pages/TermsPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));

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

function HashScrollHandler() {
  const location = useLocation();

  useEffect(() => {
    if (!location.hash) return;

    const targetId = location.hash.slice(1);
    let attempts = 0;

    const scrollToTarget = () => {
      const target = document.getElementById(targetId);
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
      }

      attempts += 1;
      if (attempts < 12) {
        window.setTimeout(scrollToTarget, 80);
      }
    };

    window.setTimeout(scrollToTarget, 0);
  }, [location.hash, location.pathname]);

  return null;
}

function RouteScrollReset() {
  const location = useLocation();

  useEffect(() => {
    if (location.hash) return;
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  }, [location.pathname, location.search, location.hash]);

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
      <RouteScrollReset />
      <HashScrollHandler />
      <Layout>
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/examples" element={<ExamplesPage />} />
            <Route path="/lookup" element={<LookupPage />} />
            <Route path="/payment/:orderId" element={<PaymentPage />} />
            <Route path="/review/:orderId" element={<ReviewPage />} />
            <Route path="/report/:orderId" element={<ReportPage />} />
            <Route path="/privacy" element={<PrivacyPage />} />
            <Route path="/terms" element={<TermsPage />} />
            <Route path="*" element={<NotFoundPage />} />
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
