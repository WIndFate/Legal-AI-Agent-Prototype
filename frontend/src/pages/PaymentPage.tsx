import { useEffect, useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

type PaymentStatus = 'checking' | 'success' | 'failed' | 'pending';

export default function PaymentPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [status, setStatus] = useState<PaymentStatus>('checking');

  useEffect(() => {
    if (!orderId) return;
    let cancelled = false;

    const checkStatus = async () => {
      try {
        // First check if report already exists (analysis already done)
        const reportRes = await fetch(`/api/report/${orderId}`);
        if (reportRes.ok) {
          setStatus('success');
          setTimeout(() => navigate(`/report/${orderId}`, { replace: true }), 1000);
          return;
        }

        // Check payment status via dedicated endpoint
        const payRes = await fetch(`/api/payment/status/${orderId}`);
        if (payRes.ok) {
          const data = await payRes.json();
          if (data.status === 'paid' || data.status === 'captured') {
            setStatus('success');
            setTimeout(() => navigate(`/review/${orderId}`, { replace: true }), 1500);
            return;
          }
          if (data.status === 'failed' || data.status === 'cancelled') {
            setStatus('failed');
            return;
          }
        }

        // Still waiting for payment confirmation.
        setStatus('pending');
        if (!cancelled) {
          setTimeout(checkStatus, 3000);
        }
      } catch {
        // Retry on network error
        if (!cancelled) {
          setStatus('pending');
          setTimeout(checkStatus, 3000);
        }
      }
    };

    // KOMOJU redirects back with session_id or we arrive via direct navigation
    const sessionId = searchParams.get('session_id');
    if (sessionId || true) {
      // Always check status regardless
      checkStatus();
    }

    return () => { cancelled = true; };
  }, [orderId, searchParams, navigate]);

  return (
    <div className="page payment-page">
      <div className="payment-status-card">
        {(status === 'checking' || status === 'pending') && (
          <div className="loading-state">
            <div className="spinner" />
            <p className="status-text">{t('payment.processing')}</p>
            <p className="status-subtext">{t('payment.waiting_note')}</p>
          </div>
        )}

        {status === 'success' && (
          <div className="success-state">
            <div className="check-icon">&#10003;</div>
            <p className="status-text">{t('review.analyzing')}</p>
            <p className="status-subtext">{t('payment.success_note')}</p>
          </div>
        )}

        {status === 'failed' && (
          <div className="error-state">
            <p className="error-message">{t('errors.payment_failed')}</p>
            <button className="btn-primary" onClick={() => navigate('/')}>
              {t('nav.home')}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
