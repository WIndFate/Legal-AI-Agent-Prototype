import { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import ShareSheet from '../components/common/ShareSheet';
import { SUPPORTED_LANGUAGES } from '../i18n';

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

function languageLabel(code: string): string {
  return SUPPORTED_LANGUAGES.find((lang) => lang.code === code)?.name || code;
}

const REPORT_TIMEOUT_MS = 12_000;
const DEFAULT_FILTERS: RiskFilter[] = ['high', 'medium', 'low'];

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
  const [isOffline, setIsOffline] = useState(
    typeof navigator !== 'undefined' ? !navigator.onLine : false
  );

  const referralCode = searchParams.get('ref');

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
      const controller = new AbortController();
      const timer = window.setTimeout(() => controller.abort(), REPORT_TIMEOUT_MS);

      try {
        setLoading(true);
        setError('');
        setExpired(false);

        const res = await fetch(`/api/report/${orderId}`, { signal: controller.signal });
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
          expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
        };
        const savedOriginals = sessionStorage.getItem(`report-originals:${orderId}`);
        const originalByClause = savedOriginals ? JSON.parse(savedOriginals) as Record<string, string> : {};
        setData({
          ...json,
          report: {
            ...json.report,
            clause_analyses: json.report.clause_analyses.map((clause) => ({
              ...clause,
              original_text: clause.original_text || originalByClause[clause.clause_number] || '',
            })),
          },
        });

        const expires = new Date(json.expires_at).getTime();
        const diffHours = Math.max(0, Math.ceil((expires - Date.now()) / (1000 * 60 * 60)));
        setHoursLeft(diffHours);
      } catch {
        setError(i18n.t('report.network_error'));
      } finally {
        window.clearTimeout(timer);
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
    return (
      <div className="page report-page">
        <div className="soft-error-panel report-expired-panel">
          <p className="section-kicker">{t('report.expired_kicker')}</p>
          <h2>{t('report.expired_title')}</h2>
          <p className="dialog-body">{t('report.expired_body')}</p>
          <div className="soft-error-actions">
            <button
              className="btn-primary"
              onClick={() => navigate(referralCode ? `/?ref=${encodeURIComponent(referralCode)}` : '/')}
            >
              {t('report.expired_action')}
            </button>
          </div>
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
  const reportLanguageLabel = languageLabel(data.language);
  const filteredClauses = report.clause_analyses.filter((clause) => {
    const normalized = normalizeRiskLevel(clause.risk_level);
    return normalized ? selectedRisks.includes(normalized) : true;
  });

  return (
    <div className="page report-page">
      <ShareSheet
        open={shareOpen}
        onClose={() => setShareOpen(false)}
        shareUrl={`${window.location.origin}/report/${data.order_id}`}
        orderId={data.order_id}
      />
      {isOffline && (
        <div className="offline-banner report-offline-banner">
          <strong>{t('report.network_error')}</strong>
        </div>
      )}

      <div className="report-summary-shell report-header-bar">
        <div className="document-ribbon">
          <span>{t('report.title')}</span>
          <span>{reportLanguageLabel}</span>
        </div>
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

          <div className="report-hero-panel">
            <div className="report-hero-panel-top">
              <span className="report-status-chip">{t('report.overall_risk')}</span>
              <span
                className="risk-badge report-hero-badge"
                style={{ background: riskColor(report.overall_risk_level) }}
              >
                {report.overall_risk_level}
              </span>
            </div>
            <div className="report-hero-stats report-hero-stats-compact">
              <div className="report-hero-stat">
                <span>{t('report.clause_count')}</span>
                <strong>{report.total_clauses}</strong>
              </div>
              <div className="report-hero-stat">
                <span>{t('report.high_risk')}</span>
                <strong className="stat high">{report.high_risk_count}</strong>
              </div>
              <div className="report-hero-stat">
                <span>{t('report.medium_risk')}</span>
                <strong className="stat medium">{report.medium_risk_count}</strong>
              </div>
              <div className="report-hero-stat">
                <span>{t('report.low_risk')}</span>
                <strong className="stat low">{report.low_risk_count}</strong>
              </div>
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
        <div className="report-toolbar">
          <span
            className="risk-badge"
            style={{ background: riskColor(report.overall_risk_level) }}
          >
            {t('report.overall_risk')}: {report.overall_risk_level}
          </span>
          <button className="btn-primary btn-share report-share-trigger" onClick={() => setShareOpen(true)}>
            {t('report.share')}
          </button>
        </div>
        <div className="summary-metrics report-summary-metrics">
          <div className="summary-metric">
            <span>{t('report.clause_count')}</span>
            <strong>{report.total_clauses}</strong>
          </div>
          <div className="summary-metric">
            <span>{t('report.high_risk')}</span>
            <strong className="stat high">{report.high_risk_count}</strong>
          </div>
          <div className="summary-metric">
            <span>{t('report.medium_risk')}</span>
            <strong className="stat medium">{report.medium_risk_count}</strong>
          </div>
          <div className="summary-metric">
            <span>{t('report.low_risk')}</span>
            <strong className="stat low">{report.low_risk_count}</strong>
          </div>
        </div>
        <div className="report-filter-bar">
          <span className="report-filter-label">{t('report.filter_label')}</span>
          <div className="report-filter-chips">
            <button
              type="button"
              className={`report-filter-chip ${selectedRisks.length === DEFAULT_FILTERS.length ? 'report-filter-chip-active' : ''}`}
              onClick={() => setSelectedRisks(DEFAULT_FILTERS)}
            >
              {t('report.filter_all')}
            </button>
            <button
              type="button"
              className={`report-filter-chip ${selectedRisks.includes('high') ? 'report-filter-chip-active report-filter-chip-high' : ''}`}
              onClick={() => toggleRiskFilter('high')}
            >
              {t('report.high_risk')}
            </button>
            <button
              type="button"
              className={`report-filter-chip ${selectedRisks.includes('medium') ? 'report-filter-chip-active report-filter-chip-medium' : ''}`}
              onClick={() => toggleRiskFilter('medium')}
            >
              {t('report.medium_risk')}
            </button>
            <button
              type="button"
              className={`report-filter-chip ${selectedRisks.includes('low') ? 'report-filter-chip-active report-filter-chip-low' : ''}`}
              onClick={() => toggleRiskFilter('low')}
            >
              {t('report.low_risk')}
            </button>
          </div>
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
              <div className="clause-toolbar">
                {clause.original_text ? (
                  <button
                    type="button"
                    className={`inline-toggle-btn ${expandedClauses[clause.clause_number] ? 'inline-toggle-btn-active' : ''}`}
                    onClick={() => toggleClause(clause.clause_number)}
                  >
                    {expandedClauses[clause.clause_number]
                      ? t('report.hide_original_clause')
                      : t('report.show_original_clause')}
                  </button>
                ) : (
                  <span className="clause-toolbar-spacer" />
                )}
              </div>
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
    </div>
  );
}
