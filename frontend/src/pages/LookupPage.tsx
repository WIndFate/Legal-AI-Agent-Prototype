import { FormEvent, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { fetchWithRetry } from '../lib/fetchWithRetry';

const LOOKUP_TIMEOUT_MS = 12_000;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export default function LookupPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [orderId, setOrderId] = useState('');
  const [statusText, setStatusText] = useState('');
  const [error, setError] = useState('');
  const [errorKind, setErrorKind] = useState<'validation' | 'not_found' | 'network' | null>(null);
  const [loading, setLoading] = useState(false);
  const [isOffline, setIsOffline] = useState(
    typeof navigator !== 'undefined' ? !navigator.onLine : false
  );

  useEffect(() => {
    const handleOnline = () => setIsOffline(false);
    const handleOffline = () => setIsOffline(true);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const lookupOrder = async () => {
    if (!orderId.trim()) return;
    const trimmed = orderId.trim();
    if (!UUID_PATTERN.test(trimmed)) {
      setError(t('order.lookup_invalid'));
      setErrorKind('validation');
      setStatusText('');
      return;
    }

    setLoading(true);
    setError('');
    setErrorKind(null);
    setStatusText(t('order.lookup_checking'));

    try {
      const statusRes = await fetchWithRetry(`/api/orders/${trimmed}/status`, undefined, {
        timeoutMs: LOOKUP_TIMEOUT_MS,
        retries: 2,
        retryDelayMs: 700,
      });
      if (!statusRes.ok) {
        if (statusRes.status === 404) {
          setError(t('order.lookup_not_found'));
          setErrorKind('not_found');
          setStatusText('');
          return;
        }
        throw new Error(`Lookup failed: ${statusRes.status}`);
      }

      const data = await statusRes.json();

      if (data.report_ready || data.analysis_status === 'completed') {
        setStatusText(t('order.lookup_found_report'));
        navigate(`/report/${trimmed}`);
        return;
      }

      if (data.analysis_status === 'failed' || data.analysis_status === 'queued' || data.analysis_status === 'processing') {
        setStatusText(t('order.lookup_found_processing'));
        navigate(`/review/${trimmed}`);
        return;
      }

      if (data.payment_status === 'paid' || data.payment_status === 'captured') {
        setStatusText(t('order.lookup_found_processing'));
        navigate(`/review/${trimmed}`);
        return;
      }

      if (data.payment_status === 'pending') {
        setStatusText(t('order.lookup_found_payment'));
        navigate(`/payment/${trimmed}`);
        return;
      }

      if (data.payment_status === 'failed' || data.payment_status === 'cancelled') {
        setStatusText(t('order.lookup_found_payment'));
        navigate(`/payment/${trimmed}`);
        return;
      }

      setError(t('order.lookup_not_found'));
      setErrorKind('not_found');
      setStatusText('');
    } catch {
      setError(t('order.lookup_network'));
      setErrorKind('network');
      setStatusText('');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await lookupOrder();
  };

  return (
    <div className="page lookup-page">
      <div className="lookup-shell">
        <p className="section-kicker">{t('order.lookup_kicker')}</p>
        <h2>{t('order.lookup_title')}</h2>
        <p className="section-intro">{t('order.lookup_desc')}</p>

        {isOffline && (
          <div className="offline-banner">
            <strong>{t('order.lookup_network')}</strong>
          </div>
        )}

        <form className="lookup-form" onSubmit={handleSubmit}>
          <label className="lookup-label">
            {t('order.order_id')}
            <input
              className="lookup-input"
              value={orderId}
              onChange={(event) => {
                setOrderId(event.target.value);
                if (error) {
                  setError('');
                  setErrorKind(null);
                }
              }}
              placeholder={t('order.lookup_placeholder')}
              inputMode="text"
              enterKeyHint="search"
              autoComplete="off"
              autoCapitalize="off"
              autoCorrect="off"
              spellCheck={false}
            />
          </label>
          <button type="submit" className="btn-primary" disabled={loading || !orderId.trim()}>
            {loading ? t('order.lookup_checking') : t('order.lookup_action')}
          </button>
        </form>

        {statusText && <div className="lookup-status">{statusText}</div>}
        {error && (
          <div className="lookup-feedback-panel">
            <p className="error-message">{error}</p>
            {errorKind === 'network' && (
              <div className="lookup-actions">
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => void lookupOrder()}
                  disabled={loading || !orderId.trim()}
                >
                  {t('review.retry')}
                </button>
              </div>
            )}
          </div>
        )}

        <div className="lookup-help-grid">
          <div className="lookup-help-card">
            <span>{t('order.lookup_help_title')}</span>
            <strong>{t('order.lookup_help_body')}</strong>
          </div>
          <div className="lookup-help-card">
            <span>{t('payment.title')}</span>
            <strong>{t('order.lookup_help_payment')}</strong>
          </div>
          <div className="lookup-help-card">
            <span>{t('report.title')}</span>
            <strong>{t('order.lookup_help_report')}</strong>
          </div>
        </div>
      </div>
    </div>
  );
}
