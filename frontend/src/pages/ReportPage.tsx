import { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import ShareSheet, { type ReportSummary } from '../components/common/ShareSheet';
import { fetchWithRetry } from '../lib/fetchWithRetry';
interface ClauseAnalysis {
  clause_number: string;
  risk_level: string;
  risk_reason: string;
  suggestion: string;
  referenced_law: string;
  original_text?: string;
}

interface ReportData {
  order_id: string;
  report: {
    overall_risk_level: string;
    summary: string;
    clause_analyses: ClauseAnalysis[];
    high_risk_count: number;
    medium_risk_count: number;
    low_risk_count: number;
    total_clauses: number;
  };
  language: string;
  created_at: string;
  expires_at: string;
}

type RiskFilter = 'high' | 'medium' | 'low';

function riskColor(level: string): string {
  if (level === '高' || level === 'High' || level === '高リスク') return '#dc2626';
  if (level === '中' || level === 'Medium' || level === '中リスク') return '#f59e0b';
  if (level === '低' || level === 'Low' || level === '低リスク') return '#16a34a';
  return '#6b7280';
}

function riskBg(level: string): string {
  if (level === '高' || level === 'High' || level === '高リスク') return '#fef2f2';
  if (level === '中' || level === 'Medium' || level === '中リスク') return '#fffbeb';
  if (level === '低' || level === 'Low' || level === '低リスク') return '#f0fdf4';
  return '#f9fafb';
}

function normalizeRiskLevel(level: string): RiskFilter | null {
  if (level === '高' || level === 'High' || level === '高リスク') return 'high';
  if (level === '中' || level === 'Medium' || level === '中リスク') return 'medium';
  if (level === '低' || level === 'Low' || level === '低リスク') return 'low';
  return null;
}

function sortClausesByRisk(clauseAnalyses: ClauseAnalysis[]): ClauseAnalysis[] {
  const rank: Record<RiskFilter, number> = { high: 0, medium: 1, low: 2 };
  return [...clauseAnalyses].sort((left, right) => {
    const leftRisk = normalizeRiskLevel(left.risk_level);
    const rightRisk = normalizeRiskLevel(right.risk_level);
    const leftRank = leftRisk ? rank[leftRisk] : 3;
    const rightRank = rightRisk ? rank[rightRisk] : 3;

    if (leftRank !== rightRank) return leftRank - rightRank;
    return left.clause_number.localeCompare(right.clause_number, 'ja');
  });
}

const REPORT_TIMEOUT_MS = 12_000;
const DEFAULT_FILTERS: RiskFilter[] = ['high', 'medium', 'low'];
const REPORT_TTL_HOURS = 72;

export default function ReportPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { t, i18n } = useTranslation();

  const [data, setData] = useState<ReportData | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [hoursLeft, setHoursLeft] = useState(0);
  const [expandedClauses, setExpandedClauses] = useState<Record<string, boolean>>({});
  const [shareOpen, setShareOpen] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [expired, setExpired] = useState(false);
  const [selectedRisks, setSelectedRisks] = useState<RiskFilter[]>(DEFAULT_FILTERS);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [isOffline, setIsOffline] = useState(
    typeof navigator !== 'undefined' ? !navigator.onLine : false
  );

  const referralCode = searchParams.get('ref');

  const handleDownloadPdf = async () => {
    if (!data || typeof window === 'undefined' || downloadingPdf) return;

    try {
      setDownloadingPdf(true);
      const pdfUrl = `/api/report/${data.order_id}/pdf?download=1`;
      const link = document.createElement('a');
      link.href = pdfUrl;
      link.download = `contractguard-report-${data.order_id}.pdf`;
      link.rel = 'noopener';
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch {
      setError(i18n.t('report.network_error'));
    } finally {
      setDownloadingPdf(false);
    }
  };

  const toggleClause = (clauseNumber: string) => {
    setExpandedClauses((prev) => ({
      ...prev,
      [clauseNumber]: !prev[clauseNumber],
    }));
  };

  const toggleRiskFilter = (risk: RiskFilter) => {
    setSelectedRisks((prev) => (
      prev.includes(risk) ? prev.filter((item) => item !== risk) : [...prev, risk]
    ));
  };

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

  useEffect(() => {
    const fetchReport = async () => {
      try {
        setLoading(true);
        setError('');
        setExpired(false);

        const res = await fetchWithRetry(`/api/report/${orderId}`, undefined, {
          timeoutMs: REPORT_TIMEOUT_MS,
          retries: 2,
          retryDelayMs: 700,
        });
        if (res.status === 404) {
          setExpired(true);
          setError(i18n.t('errors.report_expired'));
          return;
        }
        if (!res.ok) throw new Error(`Failed: ${res.status}`);

        const raw = await res.json();
        const json: ReportData = raw.report ? raw : {
          order_id: orderId || '',
          report: raw,
          language: sessionStorage.getItem(`report-language:${orderId}`) || i18n.language,
          created_at: new Date().toISOString(),
          expires_at: new Date(Date.now() + REPORT_TTL_HOURS * 60 * 60 * 1000).toISOString(),
        };
        const savedOriginals = sessionStorage.getItem(`report-originals:${orderId}`);
        const originalByClause = savedOriginals ? JSON.parse(savedOriginals) as Record<string, string> : {};
        setData({
          ...json,
          report: {
            ...json.report,
            clause_analyses: sortClausesByRisk(json.report.clause_analyses.map((clause) => ({
              ...clause,
              original_text: clause.original_text || originalByClause[clause.clause_number] || '',
            }))),
          },
        });

        const expires = new Date(json.expires_at).getTime();
        const diffHours = Math.max(0, Math.ceil((expires - Date.now()) / (1000 * 60 * 60)));
        setHoursLeft(diffHours);
      } catch {
        setError(i18n.t('report.network_error'));
      } finally {
        setLoading(false);
      }
    };

    void fetchReport();
  }, [i18n, orderId, reloadKey]);

  useEffect(() => {
    if (!data?.expires_at) return;

    const interval = setInterval(() => {
      const expires = new Date(data.expires_at).getTime();
      const diffHours = Math.max(0, Math.ceil((expires - Date.now()) / (1000 * 60 * 60)));
      setHoursLeft(diffHours);

      if (diffHours <= 0) {
        setExpired(true);
        setError(i18n.t('errors.report_expired'));
        setData(null);
      }
    }, 60000);

    return () => clearInterval(interval);
  }, [data, i18n]);

  if (loading) {
    return (
      <div className="page report-page">
        <div className="loading-state report-loading-card">
          <div className="spinner" />
          <p className="status-text">{t('report.title')}</p>
          <p className="status-subtext">{t('payment.waiting_note')}</p>
          <div className="report-loading-skeleton">
            <span />
            <span />
            <span />
          </div>
        </div>
      </div>
    );
  }

  if (expired) {
    const refParam = referralCode ? `?ref=${encodeURIComponent(referralCode)}` : '';
    const uploadPath = `/${refParam}#upload-section`;
    const homePath = `/${refParam}`;
    return (
      <div className="page report-page">
        <div className="soft-error-panel report-expired-panel">
          <div className="report-expired-icon" aria-hidden="true">
            <svg width="56" height="64" viewBox="0 0 56 64" fill="none" xmlns="http://www.w3.org/2000/svg">
              {/* Shield outline */}
              <path d="M28 3L7 13v15c0 13 9 25 21 29 12-4 21-16 21-29V13L28 3Z"
                stroke="var(--brand-soft)" strokeWidth="2" fill="rgba(31,58,95,0.06)" strokeLinejoin="round" />
              {/* Clock circle */}
              <circle cx="28" cy="24" r="9" stroke="var(--brand)" strokeWidth="1.8" fill="var(--panel)" />
              {/* Clock hands */}
              <line x1="28" y1="24" x2="28" y2="18.5" stroke="var(--brand)" strokeWidth="1.8" strokeLinecap="round" />
              <line x1="28" y1="24" x2="32.5" y2="24" stroke="var(--brand)" strokeWidth="1.8" strokeLinecap="round" />
              {/* Checkmark badge — offset below clock */}
              <circle cx="28" cy="44" r="7" fill="var(--panel)" stroke="var(--success)" strokeWidth="1.6" />
              <path d="M24.5 44l2.5 2.5 5-5" stroke="var(--success)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" fill="none" />
            </svg>
          </div>
          <p className="section-kicker">{t('report.expired_kicker')}</p>
          <h2>{t('report.expired_title')}</h2>
          <p className="dialog-body">{t('report.expired_body')}</p>
          <div className="soft-error-actions">
            <button className="btn-primary" onClick={() => navigate(uploadPath)}>
              {t('report.expired_action')}
            </button>
          </div>
          <button className="report-expired-home-link" onClick={() => navigate(homePath)}>
            {t('report.expired_home_link')}
          </button>
          <hr className="report-expired-divider" />
          <p className="report-expired-trust">{t('report.expired_trust')}</p>
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="page report-page">
        <div className="error-state soft-error-panel">
          {isOffline && (
            <div className="offline-banner">
              <strong>{t('report.network_error')}</strong>
            </div>
          )}
          <p className="error-message">{error}</p>
          <div className="soft-error-actions">
            <button className="btn-primary" onClick={() => setReloadKey((value) => value + 1)}>
              {t('review.retry')}
            </button>
            <button className="btn-share dialog-secondary-btn" onClick={() => navigate('/lookup')}>
              {t('nav.lookup')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const report = data.report;

  // Build summary for ShareSheet card generation
  const topHighRisk = report.clause_analyses.find((c) => normalizeRiskLevel(c.risk_level) === 'high');
  const topFinding = topHighRisk?.risk_reason
    || report.clause_analyses.find((c) => normalizeRiskLevel(c.risk_level) === 'medium')?.risk_reason
    || '';
  const reportSummary: ReportSummary = {
    overallRisk: report.overall_risk_level,
    totalClauses: report.total_clauses,
    highCount: report.high_risk_count,
    mediumCount: report.medium_risk_count,
    lowCount: report.low_risk_count,
    topFinding,
    targetLanguage: data.language,
  };

  const filteredClauses = report.clause_analyses.filter((clause) => {
    const normalized = normalizeRiskLevel(clause.risk_level);
    return normalized ? selectedRisks.includes(normalized) : true;
  });

  const allFiltersActive = selectedRisks.length === DEFAULT_FILTERS.length;

  const metricCards: Array<{
    key: 'all' | RiskFilter;
    label: string;
    value: number;
    active: boolean;
    accent?: string;
    onClick: () => void;
  }> = [
    {
      key: 'all',
      label: t('report.clause_count'),
      value: report.total_clauses,
      active: allFiltersActive,
      onClick: () => setSelectedRisks(DEFAULT_FILTERS),
    },
    {
      key: 'high',
      label: t('report.high_risk'),
      value: report.high_risk_count,
      active: selectedRisks.includes('high'),
      accent: 'high',
      onClick: () => toggleRiskFilter('high'),
    },
    {
      key: 'medium',
      label: t('report.medium_risk'),
      value: report.medium_risk_count,
      active: selectedRisks.includes('medium'),
      accent: 'medium',
      onClick: () => toggleRiskFilter('medium'),
    },
    {
      key: 'low',
      label: t('report.low_risk'),
      value: report.low_risk_count,
      active: selectedRisks.includes('low'),
      accent: 'low',
      onClick: () => toggleRiskFilter('low'),
    },
  ];

  return (
    <div className="page report-page">
      <ShareSheet
        open={shareOpen}
        onClose={() => setShareOpen(false)}
        shareUrl={`${window.location.origin}/report/${data.order_id}`}
        orderId={data.order_id}
        reportSummary={reportSummary}
      />
      {isOffline && (
        <div className="offline-banner report-offline-banner">
          <strong>{t('report.network_error')}</strong>
        </div>
      )}

      <div className="report-summary-shell report-header-bar">
        <div className="report-hero-grid">
          <div className="report-hero-copy">
            <p className="section-kicker">{t('report.executive_kicker')}</p>
            <h2>{t('report.title')}</h2>
            <p className="summary">{report.summary}</p>
            {hoursLeft > 0 && (
              <p className="expiry-notice">
                {t('report.expires_in', { hours: hoursLeft })}
              </p>
            )}
          </div>

          <div className="report-hero-panel report-hero-panel-compact">
            <div className="report-hero-panel-top">
              <span
                className="risk-badge report-hero-badge"
                style={{ background: riskColor(report.overall_risk_level) }}
              >
                {t('report.overall_risk')}: {report.overall_risk_level}
              </span>
            </div>
            <div className="order-inline-card order-inline-card-report">
              <span>{t('order.order_id')}</span>
              <strong>{data.order_id}</strong>
              <p>{t('order.lookup_help_body')}</p>
            </div>
          </div>
        </div>
      </div>

      <div
        className="overall-risk-card"
        style={{
          borderColor: riskColor(report.overall_risk_level),
          background: riskBg(report.overall_risk_level),
        }}
      >
        <div className="report-filter-hint">
          <span className="report-filter-hint-icon" aria-hidden="true">
            <svg viewBox="0 0 20 20" focusable="false">
              <path d="M3 5.5h14M6.5 10h7M9 14.5h2" />
            </svg>
          </span>
          <p>{t('report.filter_hint')}</p>
        </div>
        <div className="summary-metrics report-summary-metrics report-summary-metrics-interactive">
          {metricCards.map((metric) => (
            <button
              key={metric.key}
              type="button"
              className={`summary-metric report-summary-metric-btn ${metric.active ? 'report-summary-metric-btn-active' : ''} ${metric.accent ? `report-summary-metric-btn-${metric.accent}` : ''}`}
              onClick={metric.onClick}
            >
              <span>{metric.label}</span>
              <strong className={metric.accent ? `stat ${metric.accent}` : ''}>{metric.value}</strong>
            </button>
          ))}
        </div>
      </div>

      {filteredClauses.length === 0 ? (
        <div className="report-actions report-empty-state">
          <p className="share-note">{t('report.filter_empty')}</p>
        </div>
      ) : (
        <div className="clause-list">
          {filteredClauses.map((clause, idx) => (
            <div
              key={`${clause.clause_number}-${idx}`}
              className={`clause-card ${expandedClauses[clause.clause_number] ? 'clause-card-expanded' : ''}`}
              style={{
                borderLeftColor: riskColor(clause.risk_level),
                background: riskBg(clause.risk_level),
              }}
            >
              <div className="clause-header">
                <div className="clause-heading">
                  <span className="clause-eyebrow">
                    {t('report.finding_label')} #{String(idx + 1).padStart(2, '0')}
                  </span>
                  <strong>{clause.clause_number}</strong>
                </div>
                <span
                  className="risk-tag"
                  style={{ background: riskColor(clause.risk_level) }}
                >
                  {clause.risk_level}
                </span>
              </div>
              <div className="clause-meta-row">
                <div className="clause-meta-item">
                  <span>{t('report.overall_risk')}</span>
                  <strong>{clause.risk_level}</strong>
                </div>
                <div className="clause-meta-item">
                  <span>{t('report.referenced_law')}</span>
                  <strong>{t('report.japanese_original')}</strong>
                </div>
              </div>
              {clause.original_text && (
                <div className="clause-toolbar">
                  <button
                    type="button"
                    className={`inline-toggle-btn ${expandedClauses[clause.clause_number] ? 'inline-toggle-btn-active' : ''}`}
                    onClick={() => toggleClause(clause.clause_number)}
                  >
                    {expandedClauses[clause.clause_number]
                      ? t('report.hide_original_clause')
                      : t('report.show_original_clause')}
                  </button>
                </div>
              )}
              <div className={`clause-content ${expandedClauses[clause.clause_number] && clause.original_text ? 'clause-content-split' : ''}`}>
                {expandedClauses[clause.clause_number] && clause.original_text && (
                  <div className="inline-original-panel">
                    <p className="inline-original-label">{t('report.original_clause_label')}</p>
                    <pre className="inline-original-text">{clause.original_text}</pre>
                    <p className="inline-original-note">{t('report.original_contract_shared_note')}</p>
                  </div>
                )}
                <div className="clause-analysis-panel">
                  <div className="analysis-block">
                    <p className="analysis-label">{t('report.assessment_label')}</p>
                    <p className="risk-reason">{clause.risk_reason}</p>
                  </div>
                  {clause.suggestion && (
                    <div className="suggestion analysis-block">
                      <p className="analysis-label">{t('report.suggestion_label')}</p>
                      <p>{clause.suggestion}</p>
                    </div>
                  )}
                  {clause.referenced_law && (
                    <div className="reference analysis-block">
                      <p className="analysis-label">{t('report.reference_label')}</p>
                      <p>{clause.referenced_law}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Share CTA card */}
      <div className="report-share-cta" onClick={() => setShareOpen(true)} role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter') setShareOpen(true); }}>
        <div className="report-share-cta-copy">
          <strong>{t('share.cta_title')}</strong>
          <p>{t('share.cta_desc', { amount: 100 })}</p>
        </div>
        <span className="report-share-cta-arrow" aria-hidden="true">
          <svg viewBox="0 0 20 20" focusable="false">
            <path d="M7 4l6 6-6 6" />
          </svg>
        </span>
      </div>

      <div className="report-actions report-actions-bottom">
        <button className="btn-share report-download-trigger" onClick={() => void handleDownloadPdf()} disabled={downloadingPdf}>
          <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
            <path d="M10 3.5v8m0 0 3-3m-3 3-3-3M4.5 13.5v1.25A1.75 1.75 0 0 0 6.25 16.5h7.5a1.75 1.75 0 0 0 1.75-1.75V13.5" />
          </svg>
          <span>{t('report.download_pdf')}</span>
        </button>
        <button className="btn-primary btn-share report-share-trigger" onClick={() => setShareOpen(true)}>
          <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
            <path d="M10.5 4.5a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm-4.75 3a2 2 0 1 0 1.13 3.65l6.24 3.12a2 2 0 1 0 .58-1.16L7.46 10a2.03 2.03 0 0 0 0-.99l6.24-3.11a2 2 0 1 0-.58-1.17L6.88 7.85A1.99 1.99 0 0 0 5.75 7.5Z" />
          </svg>
          <span>{t('report.share')}</span>
        </button>
      </div>
    </div>
  );
}
