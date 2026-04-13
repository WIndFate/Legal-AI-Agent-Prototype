import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import OrderReminderDialog from '../components/common/OrderReminderDialog';
import { fetchWithRetry } from '../lib/fetchWithRetry';

type PaymentStatus = 'checking' | 'success' | 'failed' | 'pending' | 'timeout';
type TerminalPaymentStatus = 'failed' | 'cancelled' | null;

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
  const [retryingPayment, setRetryingPayment] = useState(false);
  const [terminalPaymentStatus, setTerminalPaymentStatus] = useState<TerminalPaymentStatus>(null);
  const [retryError, setRetryError] = useState('');
  const [pendingElapsed, setPendingElapsed] = useState(0);

  const PENDING_HINT_DELAY_S = 30;

  // Track how long we've been in checking/pending state
  useEffect(() => {
    if (status !== 'checking' && status !== 'pending') {
      setPendingElapsed(0);
      return;
    }
    const start = Date.now();
    const timer = window.setInterval(() => {
      setPendingElapsed(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [status]);

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

  const handleRetryPayment = async () => {
    if (!orderId) return;
    setRetryingPayment(true);
    setRetryError('');

    try {
      const res = await fetchWithRetry(`/api/payment/${orderId}/retry`, {
        method: 'POST',
      }, {
        timeoutMs: 12_000,
        retries: 1,
        retryDelayMs: 700,
      });
      if (!res.ok) {
        let detail = '';
        try {
          const body = await res.json();
          if (typeof body.detail === 'string') {
            detail = body.detail;
          }
        } catch {
          detail = '';
        }
        if (res.status === 410) {
          throw new Error(t('payment.retry_contract_missing'));
        }
        if (res.status === 409) {
          if (detail === 'Payment already completed') {
            throw new Error(t('payment.retry_already_completed'));
          }
          throw new Error(t('payment.retry_unavailable'));
        }
        throw new Error(detail || t('payment.retry_failed'));
      }
      const data = await res.json();
      if (data.komoju_session_url) {
        window.location.href = data.komoju_session_url;
        return;
      }
      setStatus('checking');
      setPollNonce((value) => value + 1);
    } catch (error) {
      if (error instanceof Error && error.message) {
        setRetryError(error.message);
      } else {
        setRetryError(t('payment.retry_failed'));
      }
    } finally {
      setRetryingPayment(false);
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
        setTerminalPaymentStatus(null);
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
          setTerminalPaymentStatus(null);
          setStatus('success');
          setNextRoute(`/report/${orderId}`);
          setShowOrderPrompt(true);
          return;
        }

        if (data.payment_status === 'paid' || data.payment_status === 'captured') {
          setTerminalPaymentStatus(null);
          setStatus('success');
          setNextRoute(`/review/${orderId}`);
          setShowOrderPrompt(true);
          return;
        }
        if (data.payment_status === 'failed' || data.payment_status === 'cancelled') {
          setTerminalPaymentStatus(data.payment_status);
          setStatus('failed');
          return;
        }

        // Still waiting for payment confirmation.
        setTerminalPaymentStatus(null);
        setStatus('pending');
        if (!cancelled) {
          pollTimer = window.setTimeout(checkStatus, PAYMENT_POLL_INTERVAL_MS);
        }
      } catch {
        if (Date.now() >= pollDeadline) {
          setTerminalPaymentStatus(null);
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
        </div>

        <div className="payment-meta-strip">
          <span className="payment-meta-tag">{t('order.order_id')}: {orderId?.slice(0, 8)}</span>
          <span className="payment-meta-sep" aria-hidden="true">·</span>
          <span className="payment-meta-tag">{t('report.title')}: 72h</span>
          <span className="payment-meta-sep" aria-hidden="true">·</span>
          <span className="payment-meta-tag">{t('payment.secure_note')}</span>
        </div>

        {(status === 'checking' || status === 'pending') && (
          <div className="loading-state">
            <div className="spinner" />
            <p className="status-text">{t('payment.pending_title')}</p>
            <p className="status-subtext">{t('payment.pending_desc')}</p>
            {pendingElapsed >= PENDING_HINT_DELAY_S && (
              <div className="payment-pending-hint">
                <p className="payment-pending-hint-text">{t('payment.pending_hint')}</p>
                <button className="btn-primary" onClick={handleRetryPayment} disabled={retryingPayment}>
                  {retryingPayment ? t('payment.processing') : t('payment.retry_payment')}
                </button>
                {retryError && <p className="error-message">{retryError}</p>}
              </div>
            )}
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
              <button className="payment-link-button" onClick={handleCopyOrderId}>
                {copied ? t('order.copied') : t('order.copy_id')}
              </button>
            </div>
            <div className="payment-timeout-actions">
              <button className="btn-primary" onClick={handleRetryPayment} disabled={retryingPayment}>
                {retryingPayment ? t('payment.processing') : t('payment.retry_payment')}
              </button>
              <button className="btn-share" onClick={() => { setRetryError(''); setStatus('checking'); setPollNonce((value) => value + 1); }}>
                {t('payment.check_again')}
              </button>
            </div>
            <div className="payment-meta-links">
              <button className="payment-link-button" onClick={() => navigate('/lookup')}>
                {t('nav.lookup')}
              </button>
            </div>
            {retryError && <p className="error-message">{retryError}</p>}
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
            <p className="status-text">
              {terminalPaymentStatus === 'cancelled' ? t('payment.cancelled_title') : t('payment.failed_title')}
            </p>
            <p className="status-subtext">
              {terminalPaymentStatus === 'cancelled' ? t('payment.cancelled_desc') : t('payment.failed_desc')}
            </p>
            <div className="order-inline-card payment-timeout-order-card">
              <span>{t('order.order_id')}</span>
              <strong>{orderId}</strong>
              <p>{t('order.screenshot_hint')}</p>
              <button className="payment-link-button" onClick={handleCopyOrderId}>
                {copied ? t('order.copied') : t('order.copy_id')}
              </button>
            </div>
            <div className="payment-timeout-actions">
              <button className="btn-primary" onClick={handleRetryPayment} disabled={retryingPayment}>
                {retryingPayment ? t('payment.processing') : t('payment.retry_payment')}
              </button>
            </div>
            <div className="payment-meta-links">
              <button className="payment-link-button" onClick={() => navigate('/lookup')}>
                {t('nav.lookup')}
              </button>
            </div>
            {retryError && <p className="error-message">{retryError}</p>}
          </div>
        )}
      </div>
    </div>
  );
}
