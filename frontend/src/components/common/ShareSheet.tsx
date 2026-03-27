import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

interface ShareSheetProps {
  open: boolean;
  onClose: () => void;
  shareUrl: string;
  orderId: string;
}

export default function ShareSheet({ open, onClose, shareUrl, orderId }: ShareSheetProps) {
  const { t } = useTranslation();
  const [copiedLink, setCopiedLink] = useState(false);
  const [copiedReferral, setCopiedReferral] = useState(false);
  const [copiedOrder, setCopiedOrder] = useState(false);
  const [referralLoading, setReferralLoading] = useState(false);
  const [referralError, setReferralError] = useState('');
  const [referralData, setReferralData] = useState<{
    referral_code: string;
    referral_url: string;
    discount_jpy: number;
  } | null>(null);

  const supportsNativeShare = useMemo(() => typeof navigator !== 'undefined' && !!navigator.share, []);

  useEffect(() => {
    if (!open) return;

    setCopiedLink(false);
    setCopiedReferral(false);
    setCopiedOrder(false);
    setReferralData(null);

    const storageKey = `referral-share:${orderId}`;
    const cached = sessionStorage.getItem(storageKey);
    if (cached) {
      try {
        setReferralData(JSON.parse(cached));
        setReferralError('');
        return;
      } catch {
        sessionStorage.removeItem(storageKey);
      }
    }

    const loadReferral = async () => {
      setReferralLoading(true);
      setReferralError('');

      try {
        const res = await fetch('/api/referral/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ order_id: orderId }),
        });
        if (!res.ok) {
          throw new Error(`Referral failed: ${res.status}`);
        }
        const data = await res.json();
        setReferralData(data);
        sessionStorage.setItem(storageKey, JSON.stringify(data));
      } catch {
        setReferralData(null);
        setReferralError(t('share.referral_error'));
      } finally {
        setReferralLoading(false);
      }
    };

    void loadReferral();
  }, [open, orderId, t]);

  if (!open) return null;

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 1800);
    } catch {
      setCopiedLink(false);
    }
  };

  const copyReferral = async () => {
    if (!referralData) return;

    try {
      await navigator.clipboard.writeText(referralData.referral_url);
      setCopiedReferral(true);
      setTimeout(() => setCopiedReferral(false), 1800);
    } catch {
      setCopiedReferral(false);
    }
  };

  const copyOrder = async () => {
    try {
      await navigator.clipboard.writeText(orderId);
      setCopiedOrder(true);
      setTimeout(() => setCopiedOrder(false), 1800);
    } catch {
      setCopiedOrder(false);
    }
  };

  const triggerNativeShare = async (mode: 'report' | 'referral') => {
    if (!navigator.share) return;

    const targetUrl = mode === 'referral' ? referralData?.referral_url || shareUrl : shareUrl;
    const targetText = mode === 'referral' ? t('share.referral_desc') : t('report.share_text');

    try {
      await navigator.share({
        title: t('report.title'),
        text: targetText,
        url: targetUrl,
      });
    } catch {
      // ignore cancel
    }
  };

  return (
    <div className="dialog-backdrop" role="presentation" onClick={onClose}>
      <div
        className="dialog-shell share-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="share-dialog-title"
        onClick={(event) => event.stopPropagation()}
      >
        <button type="button" className="dialog-close-btn" onClick={onClose} aria-label={t('share.close')}>
          ×
        </button>
        <p className="section-kicker">{t('share.kicker')}</p>
        <h2 id="share-dialog-title" className="dialog-title">{t('share.title')}</h2>
        <p className="dialog-body">{t('share.description')}</p>

        <div className="share-preview-card">
          <div className="share-preview-header">
            <div>
              <span className="share-brand-mark" aria-hidden="true" />
              <strong>{t('app.title')}</strong>
            </div>
            <span className="share-preview-badge">{t('share.preview_badge')}</span>
          </div>
          <h3>{t('share.preview_title')}</h3>
          <p>{t('share.preview_desc')}</p>
          <div className="share-preview-points">
            <div>{t('share.point_fast')}</div>
            <div>{t('share.point_private')}</div>
            <div>{t('share.point_multilingual')}</div>
          </div>
        </div>

        <div className="share-url-block">
          <span>{t('share.link_label')}</span>
          <strong>{shareUrl}</strong>
        </div>

        <div className="referral-panel">
          <div className="referral-panel-header">
            <div>
              <span className="referral-panel-kicker">{t('share.referral_title')}</span>
              <strong>{t('share.referral_reward', { amount: referralData?.discount_jpy ?? 100 })}</strong>
            </div>
            {referralData?.referral_code && (
              <span className="referral-code-chip">{referralData.referral_code}</span>
            )}
          </div>
          <p className="referral-panel-desc">{t('share.referral_desc')}</p>

          {referralLoading && (
            <div className="referral-status">{t('share.referral_loading')}</div>
          )}

          {!referralLoading && referralError && (
            <div className="referral-status referral-status-error">
              <span>{referralError}</span>
            </div>
          )}

          {!referralLoading && referralData && (
            <>
              <div className="share-url-block share-url-block-compact">
                <span>{t('share.referral_link_label')}</span>
                <strong>{referralData.referral_url}</strong>
              </div>
              <div className="referral-meta-grid">
                <div className="referral-meta-card">
                  <span>{t('share.referral_code_label')}</span>
                  <strong>{referralData.referral_code}</strong>
                </div>
                <div className="referral-meta-card">
                  <span>{t('payment.referral_label')}</span>
                  <strong>{t('share.referral_reward', { amount: referralData.discount_jpy })}</strong>
                </div>
              </div>
            </>
          )}
        </div>

        <div className="dialog-action-stack">
          {referralData ? (
            <button type="button" className="btn-primary" onClick={() => void copyReferral()}>
              {copiedReferral ? t('share.referral_copied') : t('share.copy_referral')}
            </button>
          ) : (
            <button type="button" className="btn-primary" onClick={() => void copyLink()}>
              {copiedLink ? t('share.link_copied') : t('share.copy_link')}
            </button>
          )}
          {supportsNativeShare && referralData && (
            <button
              type="button"
              className="btn-share dialog-secondary-btn"
              onClick={() => void triggerNativeShare('referral')}
            >
              {t('share.native_share_referral')}
            </button>
          )}
          <button type="button" className="btn-share dialog-secondary-btn" onClick={() => void copyLink()}>
            {copiedLink ? t('share.link_copied') : t('share.copy_link')}
          </button>
          {supportsNativeShare && (
            <button type="button" className="btn-share dialog-secondary-btn" onClick={() => void triggerNativeShare('report')}>
              {t('share.native_share')}
            </button>
          )}
          <button type="button" className="btn-share dialog-secondary-btn" onClick={() => void copyOrder()}>
            {copiedOrder ? t('share.order_copied') : t('share.copy_order')}
          </button>
          <button type="button" className="dialog-link-btn" onClick={onClose}>
            {t('share.close')}
          </button>
        </div>
      </div>
    </div>
  );
}
