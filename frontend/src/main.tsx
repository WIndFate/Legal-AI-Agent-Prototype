import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';

import './i18n';
import './App.css';

import Layout from './components/Layout';
import HomePage from './pages/HomePage';
import PaymentPage from './pages/PaymentPage';
import ReviewPage from './pages/ReviewPage';
import ReportPage from './pages/ReportPage';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/payment/:orderId" element={<PaymentPage />} />
          <Route path="/review/:orderId" element={<ReviewPage />} />
          <Route path="/report/:orderId" element={<ReportPage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  </StrictMode>,
);
