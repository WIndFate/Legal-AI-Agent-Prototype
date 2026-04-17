import { useEffect, useMemo, useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { generateShareCard } from '../../lib/shareCard';
import { buildShareUrl, ownerHeaders } from '../../lib/orderAccess';

export interface ReportSummary {
  overallRisk: string;
  totalClauses: number;
  highCount: number;
  mediumCount: number;
  lowCount: number;
  targetLanguage: string;
}

interface ShareSheetProps {
  open: boolean;
  onClose: () => void;
  orderId: string;
  accessToken: string | null;
  reportSummary?: ReportSummary;
}

export default function ShareSheet({ open, onClose, orderId, accessToken, reportSummary }: ShareSheetProps) {
  const { t } = useTranslation();
  const [copiedLink, setCopiedLink] = useState(false);
  const [referralLoading, setReferralLoading] = useState(false);
  // Share URL is derived from the server-minted share_token and is null until
  // the owner-authenticated `/share-link` call succeeds, so we never leak the
  // owner URL as a fallback.
  const [resolvedShareUrl, setResolvedShareUrl] = useState<string | null>(null);
  const [referralData, setReferralData] = useState<{
    referral_code: string;
    discount_jpy: number;
  } | null>(null);
  const [cardGenerating, setCardGenerating] = useState(false);
  const [cardPreviewUrl, setCardPreviewUrl] = useState<string | null>(null);
  const cardBlobRef = useRef<Blob | null>(null);

  const supportsNativeShare = useMemo(() => typeof navigator !== 'undefined' && !!navigator.share, []);
  const finalShareUrl = useMemo(() => {
    if (!resolvedShareUrl) return null;
    try {
      const url = new URL(resolvedShareUrl, window.location.origin);
      if (referralData?.referral_code) {
        url.searchParams.set('ref', referralData.referral_code);
      }
      return url.toString();
    } catch {
      return resolvedShareUrl;
    }
  }, [referralData?.referral_code, resolvedShareUrl]);

  useEffect(() => {
    if (!open) return;

    const { body, documentElement } = document;
    const previousBodyOverflow = body.style.overflow;
    const previousBodyTouchAction = body.style.touchAction;
    const previousHtmlOverflow = documentElement.style.overflow;

    body.style.overflow = 'hidden';
    body.style.touchAction = 'none';
    documentElement.style.overflow = 'hidden';

    return () => {
      body.style.overflow = previousBodyOverflow;
      body.style.touchAction = previousBodyTouchAction;
      documentElement.style.overflow = previousHtmlOverflow;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;

    setCopiedLink(false);
    setResolvedShareUrl(null);

    const loadShareLink = async () => {
      if (!accessToken) return;
      try {
        const res = await fetch(`/api/report/${orderId}/share-link`, {
          method: 'POST',
          headers: ownerHeaders(accessToken),
        });
        if (!res.ok) return;
        const data = await res.json();
        if (typeof data.share_token === 'string' && data.share_token) {
          setResolvedShareUrl(buildShareUrl(orderId, data.share_token));
        }
      } catch {
        setResolvedShareUrl(null);
      }
    };
    void loadShareLink();

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
          headers: {
            'Content-Type': 'application/json',
            ...ownerHeaders(accessToken),
          },
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
  }, [accessToken, open, orderId]);

  // Generate card preview when referral data + report summary are ready
  useEffect(() => {
    if (!open || !reportSummary || !referralData || !finalShareUrl) return;

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
          referralCode: referralData.referral_code,
          siteUrl,
          shareUrl: finalShareUrl,
          discountAmount: referralData.discount_jpy ?? 100,
          labels: {
            brandSubtitle: t('share.card_brand_subtitle'),
            overallRiskLabel: t('share.card_risk_label'),
            clauseStats: t('share.card_clause_stats', {
              total: reportSummary.totalClauses,
              high: reportSummary.highCount,
              medium: reportSummary.mediumCount,
              low: reportSummary.lowCount,
            }),
            incentiveText: t('share.incentive_banner', { amount: referralData.discount_jpy ?? 100 }),
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
  }, [finalShareUrl, open, reportSummary, referralData, t]);

  if (!open) return null;

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
    if (!finalShareUrl) return;
    try {
      await navigator.clipboard.writeText(finalShareUrl);
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2000);
    } catch {
      setCopiedLink(false);
    }
  };

  const triggerNativeShare = async () => {
    if (!navigator.share || !finalShareUrl) return;
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
        {/* ── Compact header ── */}
        <div className="share-v2-header">
          <div className="share-v2-header-text">
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
          {/* ── Card preview ── */}
          {reportSummary && (
            <div className="share-v2-card-section">
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
                ) : null}
              </div>
            </div>
          )}

          {/* ── Actions ── */}
          <div className="share-v2-actions">
            <button
              type="button"
              className="share-v2-action-btn share-v2-action-save share-v2-action-full"
              onClick={() => void saveCard()}
              disabled={!cardBlobRef.current}
            >
              <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
                <path d="M10 3v9m0 0l3.5-3.5M10 12L6.5 8.5" />
                <path d="M4 14v1.5A1.5 1.5 0 005.5 17h9a1.5 1.5 0 001.5-1.5V14" />
              </svg>
              <span>{t('share.save_card')}</span>
            </button>
            <button
              type="button"
              className={`share-v2-action-btn share-v2-action-copy${copiedLink ? ' is-copied' : ''}${!supportsNativeShare ? ' share-v2-action-full' : ''}`}
              onClick={() => void copyLink()}
              disabled={!finalShareUrl}
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
                disabled={!finalShareUrl}
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
