import { useMemo, useState } from 'react';
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
  const [copiedOrder, setCopiedOrder] = useState(false);

  const supportsNativeShare = useMemo(() => typeof navigator !== 'undefined' && !!navigator.share, []);

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

  const copyOrder = async () => {
    try {
      await navigator.clipboard.writeText(orderId);
      setCopiedOrder(true);
      setTimeout(() => setCopiedOrder(false), 1800);
    } catch {
      setCopiedOrder(false);
    }
  };

  const triggerNativeShare = async () => {
    if (!navigator.share) return;

    try {
      await navigator.share({
        title: t('report.title'),
        text: t('report.share_text'),
        url: shareUrl,
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

        <div className="dialog-action-stack">
          <button type="button" className="btn-primary" onClick={copyLink}>
            {copiedLink ? t('share.link_copied') : t('share.copy_link')}
          </button>
          {supportsNativeShare && (
            <button type="button" className="btn-share dialog-secondary-btn" onClick={() => void triggerNativeShare()}>
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
