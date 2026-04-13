import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import OrderReminderDialog from '../components/common/OrderReminderDialog';
import { fetchWithRetry } from '../lib/fetchWithRetry';

type PaymentStatus = 'checking' | 'success' | 'failed' | 'pending' | 'timeout';

const PAYMENT_POLL_INTERVAL_MS = 3_000;
const PAYMENT_POLL_TIMEOUT_MS = 5 * 60 * 1_000;

export default function PaymentPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [status, setStatus] = useState<PaymentStatus>('checking');
  const [showOrderPrompt, setShowOrderPrompt] = useState(false);
  const [nextRoute, setNextRoute] = useState<string | null>(null);
  const [pollNonce, setPollNonce] = useState(0);
  const [copied, setCopied] = useState(false);

  const handleCopyOrderId = async () => {
    if (!orderId) return;
    try {
      await navigator.clipboard.writeText(orderId);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  };

  useEffect(() => {
    if (!orderId) return;
    let cancelled = false;
    let pollTimer: number | undefined;
    const pollDeadline = Date.now() + PAYMENT_POLL_TIMEOUT_MS;

    const checkStatus = async () => {
      if (cancelled) return;
      if (Date.now() >= pollDeadline) {
        setStatus('timeout');
        return;
      }

      try {
        const statusRes = await fetchWithRetry(`/api/orders/${orderId}/status`, undefined, {
          timeoutMs: 10_000,
          retries: 2,
          retryDelayMs: 700,
        });
        if (!statusRes.ok) {
          if (statusRes.status === 404) {
            setStatus('failed');
            return;
          }
          throw new Error(`Status failed: ${statusRes.status}`);
        }

        const data = await statusRes.json();
        if (data.report_ready || data.analysis_status === 'completed') {
          setStatus('success');
          setNextRoute(`/report/${orderId}`);
          setShowOrderPrompt(true);
          return;
        }

        if (data.payment_status === 'paid' || data.payment_status === 'captured') {
          setStatus('success');
          setNextRoute(`/review/${orderId}`);
          setShowOrderPrompt(true);
          return;
        }
        if (data.payment_status === 'failed' || data.payment_status === 'cancelled') {
          setStatus('failed');
          return;
        }

        // Still waiting for payment confirmation.
        setStatus('pending');
        if (!cancelled) {
          pollTimer = window.setTimeout(checkStatus, PAYMENT_POLL_INTERVAL_MS);
        }
      } catch {
        if (Date.now() >= pollDeadline) {
          setStatus('timeout');
          return;
        }

        // Retry on transient network error until timeout.
        if (!cancelled) {
          setStatus('pending');
          pollTimer = window.setTimeout(checkStatus, PAYMENT_POLL_INTERVAL_MS);
        }
      }
    };

    checkStatus();

    return () => {
      cancelled = true;
      if (pollTimer) {
        window.clearTimeout(pollTimer);
      }
    };
  }, [orderId, pollNonce]);

  return (
    <div className="page payment-page">
      {orderId && nextRoute && (
        <OrderReminderDialog
          open={showOrderPrompt}
          orderId={orderId}
          title={t('order.save_after_payment_title')}
          description={t('order.save_after_payment_desc')}
          primaryLabel={nextRoute.includes('/report/') ? t('order.open_report') : t('order.continue_review')}
          onPrimary={() => navigate(nextRoute, { replace: true })}
          secondaryLabel={t('share.close')}
          onSecondary={() => setShowOrderPrompt(false)}
        />
      )}
      <div className="payment-status-card">
        <div className="payment-status-header">
          <p className="section-kicker">{t('payment.title')}</p>
          <h2>{t('app.title')}</h2>
          <p className="status-subtext">{t('payment.waiting_note')}</p>
        </div>

        <div className="payment-summary-grid">
          <div className="payment-summary-item">
            <span>ID</span>
            <strong>{orderId?.slice(0, 8)}</strong>
          </div>
          <div className="payment-summary-item">
            <span>{t('report.title')}</span>
            <strong>72h</strong>
          </div>
          <div className="payment-summary-item payment-summary-item-wide">
            <span>{t('upload.trust_privacy')}</span>
            <strong>{t('payment.secure_note')}</strong>
          </div>
        </div>

        {(status === 'checking' || status === 'pending') && (
          <div className="loading-state">
            <div className="spinner" />
            <p className="status-text">{t('payment.processing')}</p>
            <p className="status-subtext">{t('payment.waiting_note')}</p>
            <button className="btn-share" onClick={() => navigate('/')}>
              {t('payment.cancel_waiting')}
            </button>
          </div>
        )}

        {status === 'timeout' && (
          <div className="error-state">
            <p className="status-text">{t('payment.timeout_title')}</p>
            <p className="status-subtext">{t('payment.timeout_desc')}</p>
            <div className="order-inline-card payment-timeout-order-card">
              <span>{t('order.order_id')}</span>
              <strong>{orderId}</strong>
              <p>{t('order.screenshot_hint')}</p>
            </div>
            <div className="payment-timeout-actions">
              <button className="btn-share" onClick={handleCopyOrderId}>
                {copied ? t('order.copied') : t('order.copy_id')}
              </button>
              <button className="btn-primary" onClick={() => { setStatus('checking'); setPollNonce((value) => value + 1); }}>
                {t('payment.check_again')}
              </button>
              <button className="btn-share" onClick={() => navigate('/lookup')}>
                {t('nav.lookup')}
              </button>
              <button className="payment-link-button" onClick={() => navigate('/')}>
                {t('nav.home')}
              </button>
            </div>
          </div>
        )}

        {status === 'success' && (
          <div className="success-state">
            <div className="check-icon">&#10003;</div>
            <p className="status-text">{t('payment.success_note')}</p>
            <p className="status-subtext">{t('order.save_after_payment_desc')}</p>
            <div className="order-inline-card">
              <span>{t('order.order_id')}</span>
              <strong>{orderId}</strong>
            </div>
            {nextRoute && (
              <button className="btn-primary" onClick={() => navigate(nextRoute, { replace: true })}>
                {nextRoute.includes('/report/') ? t('order.open_report') : t('order.continue_review')}
              </button>
            )}
          </div>
        )}

        {status === 'failed' && (
          <div className="error-state">
            <p className="error-message">{t('errors.payment_failed')}</p>
            <div className="order-inline-card payment-timeout-order-card">
              <span>{t('order.order_id')}</span>
              <strong>{orderId}</strong>
              <p>{t('order.screenshot_hint')}</p>
            </div>
            <div className="payment-timeout-actions">
              <button className="btn-share" onClick={handleCopyOrderId}>
                {copied ? t('order.copied') : t('order.copy_id')}
              </button>
              <button className="btn-share" onClick={() => navigate('/lookup')}>
                {t('nav.lookup')}
              </button>
              <button className="btn-primary" onClick={() => navigate('/')}>
                {t('nav.home')}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
