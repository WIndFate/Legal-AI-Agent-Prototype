import { useState } from 'react';
import { useTranslation } from 'react-i18next';

interface OrderReminderDialogProps {
  open: boolean;
  orderId: string;
  title: string;
  description: string;
  primaryLabel: string;
  onPrimary: () => void;
  secondaryLabel?: string;
  onSecondary?: () => void;
}

export default function OrderReminderDialog({
  open,
  orderId,
  title,
  description,
  primaryLabel,
  onPrimary,
  secondaryLabel,
  onSecondary,
}: OrderReminderDialogProps) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  if (!open) return null;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(orderId);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="dialog-backdrop" role="presentation">
      <div className="dialog-shell order-dialog" role="dialog" aria-modal="true" aria-labelledby="order-dialog-title">
        <p className="section-kicker">{t('order.save_kicker')}</p>
        <h2 id="order-dialog-title" className="dialog-title">{title}</h2>
        <p className="dialog-body">{description}</p>

        <div className="order-reference-card">
          <span>{t('order.order_id')}</span>
          <strong>{orderId}</strong>
          <p>{t('order.screenshot_hint')}</p>
        </div>

        <div className="dialog-action-stack">
          <button type="button" className="btn-share dialog-secondary-btn" onClick={handleCopy}>
            {copied ? t('order.copied') : t('order.copy_id')}
          </button>
          <button type="button" className="btn-primary" onClick={onPrimary}>
            {primaryLabel}
          </button>
          {secondaryLabel && onSecondary && (
            <button type="button" className="dialog-link-btn" onClick={onSecondary}>
              {secondaryLabel}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
