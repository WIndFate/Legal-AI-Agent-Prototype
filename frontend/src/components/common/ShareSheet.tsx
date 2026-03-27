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
  const [referralLoading, setReferralLoading] = useState(false);
  const [referralData, setReferralData] = useState<{
    referral_code: string;
  } | null>(null);

  const supportsNativeShare = useMemo(() => typeof navigator !== 'undefined' && !!navigator.share, []);

  useEffect(() => {
    if (!open) return;

    setCopiedLink(false);

    const storageKey = `referral-share:${orderId}`;
    const cached = sessionStorage.getItem(storageKey);
    if (cached) {
      try {
        setReferralData(JSON.parse(cached));
        return;
      } catch {
        sessionStorage.removeItem(storageKey);
      }
    }

    const loadReferral = async () => {
      setReferralLoading(true);

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
        const compact = { referral_code: data.referral_code };
        setReferralData(compact);
        sessionStorage.setItem(storageKey, JSON.stringify(compact));
      } catch {
        setReferralData(null);
      } finally {
        setReferralLoading(false);
      }
    };

    void loadReferral();
  }, [open, orderId]);

  if (!open) return null;

  const finalShareUrl = (() => {
    try {
      const url = new URL(shareUrl, window.location.origin);
      if (referralData?.referral_code) {
        url.searchParams.set('ref', referralData.referral_code);
      }
      return url.toString();
    } catch {
      return shareUrl;
    }
  })();

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(finalShareUrl);
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 1800);
    } catch {
      setCopiedLink(false);
    }
  };

  const triggerNativeShare = async () => {
    if (!navigator.share) return;

    try {
      await navigator.share({
        title: t('report.title'),
        text: t('report.share_text'),
        url: finalShareUrl,
      });
    } catch {
      // ignore cancel
    }
  };

  return (
    <div className="dialog-backdrop" role="presentation" onClick={onClose}>
      <div
        className="dialog-shell share-dialog share-dialog-compact"
        role="dialog"
        aria-modal="true"
        aria-labelledby="share-dialog-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="share-dialog-header">
          <h2 id="share-dialog-title" className="dialog-title share-dialog-title-compact">
            {t('report.share')}
          </h2>
          <button type="button" className="dialog-close-btn" onClick={onClose} aria-label={t('share.close')}>
            <svg viewBox="0 0 20 20" focusable="false">
              <path d="M5 5l10 10M15 5L5 15" />
            </svg>
          </button>
        </div>

        <div className="share-inline-row">
          <div className="share-url-block share-url-block-compact">
            <span>{t('share.link_label')}</span>
            <strong>{referralLoading ? t('share.copy_link') : finalShareUrl}</strong>
          </div>
          <div className="share-icon-actions">
            <button
              type="button"
              className="share-icon-btn"
              onClick={() => void copyLink()}
              aria-label={copiedLink ? t('share.link_copied') : t('share.copy_link')}
              title={copiedLink ? t('share.link_copied') : t('share.copy_link')}
            >
              <span className="share-icon-btn-glyph" aria-hidden="true">
                {copiedLink ? (
                  <svg viewBox="0 0 20 20" focusable="false">
                    <path d="M4 10l4 4 8-8" />
                  </svg>
                ) : (
                  <svg viewBox="0 0 20 20" focusable="false">
                    <rect x="7" y="5" width="9" height="11" rx="2" />
                    <rect x="4" y="2" width="9" height="11" rx="2" />
                  </svg>
                )}
              </span>
              <span>{copiedLink ? t('share.link_copied') : t('share.copy_link')}</span>
            </button>
            {supportsNativeShare && (
              <button
                type="button"
                className="share-icon-btn"
                onClick={() => void triggerNativeShare()}
                aria-label={t('share.native_share')}
                title={t('share.native_share')}
              >
                <span className="share-icon-btn-glyph" aria-hidden="true">
                  <svg viewBox="0 0 20 20" focusable="false">
                    <path d="M10 4v8M7 7l3-3 3 3" />
                    <path d="M5 12v2a2 2 0 002 2h6a2 2 0 002-2v-2" />
                  </svg>
                </span>
                <span>{t('share.native_share')}</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
