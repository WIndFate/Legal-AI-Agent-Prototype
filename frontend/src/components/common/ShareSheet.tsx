import { useEffect, useMemo, useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { generateShareCard } from '../../lib/shareCard';

export interface ReportSummary {
  overallRisk: string;
  totalClauses: number;
  highCount: number;
  mediumCount: number;
  lowCount: number;
  topFinding: string;
  targetLanguage: string;
}

interface ShareSheetProps {
  open: boolean;
  onClose: () => void;
  shareUrl: string;
  orderId: string;
  reportSummary?: ReportSummary;
}

export default function ShareSheet({ open, onClose, shareUrl, orderId, reportSummary }: ShareSheetProps) {
  const { t } = useTranslation();
  const [copiedLink, setCopiedLink] = useState(false);
  const [referralLoading, setReferralLoading] = useState(false);
  const [referralData, setReferralData] = useState<{
    referral_code: string;
    discount_jpy: number;
  } | null>(null);
  const [cardGenerating, setCardGenerating] = useState(false);
  const [cardPreviewUrl, setCardPreviewUrl] = useState<string | null>(null);
  const cardBlobRef = useRef<Blob | null>(null);

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
        const compact = { referral_code: data.referral_code, discount_jpy: data.discount_jpy ?? 100 };
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

  // Generate card preview when referral data + report summary are ready
  useEffect(() => {
    if (!open || !reportSummary || !referralData) return;

    const buildCard = async () => {
      setCardGenerating(true);
      try {
        const siteUrl = window.location.origin.includes('localhost')
          ? 'https://contractguard.com'
          : window.location.origin;

        const blob = await generateShareCard({
          overallRisk: reportSummary.overallRisk,
          totalClauses: reportSummary.totalClauses,
          highCount: reportSummary.highCount,
          mediumCount: reportSummary.mediumCount,
          lowCount: reportSummary.lowCount,
          topFinding: reportSummary.topFinding,
          referralCode: referralData.referral_code,
          siteUrl,
          labels: {
            brandSubtitle: t('share.card_brand_subtitle'),
            overallRiskLabel: t('share.card_risk_label'),
            clauseStats: t('share.card_clause_stats', {
              total: reportSummary.totalClauses,
              high: reportSummary.highCount,
              medium: reportSummary.mediumCount,
              low: reportSummary.lowCount,
            }),
            incentiveText: t('share.incentive_banner', { amount: referralData.discount_jpy }),
            referralLabel: t('share.referral_code_label'),
          },
        });
        cardBlobRef.current = blob;
        setCardPreviewUrl(URL.createObjectURL(blob));
      } catch {
        cardBlobRef.current = null;
        setCardPreviewUrl(null);
      } finally {
        setCardGenerating(false);
      }
    };

    void buildCard();

    return () => {
      if (cardPreviewUrl) URL.revokeObjectURL(cardPreviewUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, reportSummary, referralData, t]);

  if (!open) return null;

  const discountAmount = referralData?.discount_jpy ?? 100;
  const riskSummaryText = reportSummary
    ? t('share.card_clause_stats', {
        total: reportSummary.totalClauses,
        high: reportSummary.highCount,
        medium: reportSummary.mediumCount,
        low: reportSummary.lowCount,
      })
    : null;

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

  const saveCard = async () => {
    if (!cardBlobRef.current) return;

    const file = new File([cardBlobRef.current], 'contractguard-report.png', { type: 'image/png' });

    // Try native share with file first (works on mobile)
    if (navigator.share) {
      try {
        await navigator.share({ files: [file] });
        return;
      } catch {
        // Fall through to download
      }
    }

    // Download fallback
    const url = URL.createObjectURL(cardBlobRef.current);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'contractguard-report.png';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(finalShareUrl);
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2000);
    } catch {
      setCopiedLink(false);
    }
  };

  const triggerNativeShare = async () => {
    if (!navigator.share) return;
    try {
      await navigator.share({
        title: 'ContractGuard',
        text: reportSummary
          ? t('share.card_text', { total: reportSummary.totalClauses, high: reportSummary.highCount })
          : undefined,
        url: finalShareUrl,
      });
    } catch {
      // ignore cancel
    }
  };

  return (
    <div className="dialog-backdrop" role="presentation" onClick={onClose}>
      <div
        className="dialog-shell share-dialog share-dialog-v2"
        role="dialog"
        aria-modal="true"
        aria-labelledby="share-dialog-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="share-v2-header">
          <div className="share-v2-heading">
            <span className="share-v2-kicker">{t('share.preview_badge')}</span>
            <h2 id="share-dialog-title" className="share-v2-title">
              {t('share.title')}
            </h2>
            <p className="share-v2-desc">{t('share.description')}</p>
          </div>
          <button type="button" className="share-v2-close" onClick={onClose} aria-label={t('share.close')}>
            <svg viewBox="0 0 20 20" focusable="false">
              <path d="M5 5l10 10M15 5L5 15" />
            </svg>
          </button>
        </div>

        <div className="share-v2-body">
          <div className="share-v2-hero">
            <div className="share-v2-hero-copy">
              <p className="share-v2-hero-title">{t('share.preview_title')}</p>
              <p className="share-v2-hero-text">{t('share.preview_desc')}</p>
            </div>
            <div className="share-v2-points">
              <span>{t('share.point_fast')}</span>
              <span>{t('share.point_private')}</span>
              <span>{t('share.point_multilingual')}</span>
            </div>
          </div>

          <div className="share-v2-meta-grid">
            <div className="share-v2-incentive">
              <div className="share-v2-incentive-amount">¥{discountAmount}</div>
              <div className="share-v2-incentive-text">
                <span>{t('share.incentive_banner', { amount: discountAmount })}</span>
                {referralLoading && !referralData ? (
                  <small>{t('share.referral_loading')}</small>
                ) : referralData ? (
                  <span className="share-v2-incentive-code">{referralData.referral_code}</span>
                ) : (
                  <small>{t('share.referral_error')}</small>
                )}
              </div>
            </div>

            <div className="share-v2-link-card">
              <span className="share-v2-link-label">{t('share.link_label')}</span>
              <p className="share-v2-link-value">{finalShareUrl}</p>
            </div>
          </div>

          {reportSummary && (
            <div className="share-v2-card-section">
              <div className="share-v2-card-copy">
                <div className="share-v2-card-copy-top">
                  <span className="share-v2-card-copy-badge">ContractGuard</span>
                  <p className="share-v2-card-copy-risk">{reportSummary.overallRisk}</p>
                </div>
                {riskSummaryText && <p className="share-v2-card-copy-stats">{riskSummaryText}</p>}
                <p className="share-v2-card-copy-note">{t('share.referral_reward', { amount: discountAmount })}</p>
              </div>
              <div className="share-v2-card-frame">
                {cardGenerating || referralLoading ? (
                  <div className="share-v2-card-loading">
                    <div className="spinner spinner-small" />
                  </div>
                ) : cardPreviewUrl ? (
                  <img
                    src={cardPreviewUrl}
                    alt={t('share.save_card_label')}
                    className="share-v2-card-img"
                  />
                ) : (
                  <div className="share-v2-card-fallback">
                    <p>{t('share.preview_title')}</p>
                    <span>{riskSummaryText || t('share.preview_desc')}</span>
                  </div>
                )}
              </div>
              <button
                type="button"
                className="share-v2-save-btn"
                onClick={() => void saveCard()}
                disabled={!cardBlobRef.current}
              >
                <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
                  <path d="M10 3v9m0 0l3.5-3.5M10 12L6.5 8.5" />
                  <path d="M4 14v1.5A1.5 1.5 0 005.5 17h9a1.5 1.5 0 001.5-1.5V14" />
                </svg>
                {t('share.save_card')}
              </button>
            </div>
          )}

          <div className="share-v2-actions">
            <button
              type="button"
              className={`share-v2-action-btn share-v2-action-copy${copiedLink ? ' is-copied' : ''}`}
              onClick={() => void copyLink()}
            >
              {copiedLink ? (
                <svg viewBox="0 0 20 20" focusable="false"><path d="M4 10l4 4 8-8" /></svg>
              ) : (
                <svg viewBox="0 0 20 20" focusable="false">
                  <path d="M13.5 6.5h1A1.5 1.5 0 0116 8v7a1.5 1.5 0 01-1.5 1.5h-7A1.5 1.5 0 016 15v-1" />
                  <rect x="4" y="3.5" width="9" height="10" rx="1.5" />
                </svg>
              )}
              <span>{copiedLink ? t('share.link_copied') : t('share.copy_link')}</span>
            </button>
            {supportsNativeShare && (
              <button
                type="button"
                className="share-v2-action-btn share-v2-action-native"
                onClick={() => void triggerNativeShare()}
              >
                <svg viewBox="0 0 20 20" focusable="false">
                  <path d="M10 3v9M7 6l3-3 3 3" />
                  <path d="M4 12v3a2 2 0 002 2h8a2 2 0 002-2v-3" />
                </svg>
                <span>{t('share.native_share')}</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
