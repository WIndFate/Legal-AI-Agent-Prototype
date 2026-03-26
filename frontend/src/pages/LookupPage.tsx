import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

export default function LookupPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [orderId, setOrderId] = useState('');
  const [statusText, setStatusText] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!orderId.trim()) return;

    const trimmed = orderId.trim();
    setLoading(true);
    setError('');
    setStatusText(t('order.lookup_checking'));

    try {
      const reportRes = await fetch(`/api/report/${trimmed}`);
      if (reportRes.ok) {
        setStatusText(t('order.lookup_found_report'));
        navigate(`/report/${trimmed}`);
        return;
      }

      const paymentRes = await fetch(`/api/payment/status/${trimmed}`);
      if (paymentRes.ok) {
        const data = await paymentRes.json();
        if (data.status === 'paid' || data.status === 'captured') {
          setStatusText(t('order.lookup_found_processing'));
          navigate(`/review/${trimmed}`);
          return;
        }

        if (data.status === 'pending') {
          setStatusText(t('order.lookup_found_payment'));
          navigate(`/payment/${trimmed}`);
          return;
        }
      }

      setError(t('order.lookup_not_found'));
      setStatusText('');
    } catch {
      setError(t('order.lookup_not_found'));
      setStatusText('');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page lookup-page">
      <div className="lookup-shell">
        <p className="section-kicker">{t('order.lookup_kicker')}</p>
        <h2>{t('order.lookup_title')}</h2>
        <p className="section-intro">{t('order.lookup_desc')}</p>

        <form className="lookup-form" onSubmit={handleSubmit}>
          <label className="lookup-label">
            {t('order.order_id')}
            <input
              className="lookup-input"
              value={orderId}
              onChange={(event) => setOrderId(event.target.value)}
              placeholder={t('order.lookup_placeholder')}
            />
          </label>
          <button type="submit" className="btn-primary" disabled={loading || !orderId.trim()}>
            {loading ? t('order.lookup_checking') : t('order.lookup_action')}
          </button>
        </form>

        {statusText && <div className="lookup-status">{statusText}</div>}
        {error && <div className="error-message">{error}</div>}

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
