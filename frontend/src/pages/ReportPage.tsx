import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { SUPPORTED_LANGUAGES } from '../i18n';

// Shared report types
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

// Risk level color helpers
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

function languageLabel(code: string): string {
  return SUPPORTED_LANGUAGES.find((lang) => lang.code === code)?.name || code;
}

export default function ReportPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const { t, i18n } = useTranslation();
  const [data, setData] = useState<ReportData | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [hoursLeft, setHoursLeft] = useState(0);
  const [expandedClauses, setExpandedClauses] = useState<Record<string, boolean>>({});

  const toggleClause = (clauseNumber: string) => {
    setExpandedClauses((prev) => ({
      ...prev,
      [clauseNumber]: !prev[clauseNumber],
    }));
  };

  useEffect(() => {
    const fetchReport = async () => {
      try {
        const res = await fetch(`/api/report/${orderId}`);
        if (res.status === 404) {
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

        // Calculate initial hours remaining
        const expires = new Date(json.expires_at).getTime();
        const diffHours = Math.max(0, Math.ceil((expires - Date.now()) / (1000 * 60 * 60)));
        setHoursLeft(diffHours);
      } catch {
        setError(i18n.t('errors.not_found'));
      } finally {
        setLoading(false);
      }
    };
    fetchReport();
  }, [i18n, orderId]);

  // Update expiry countdown every minute
  useEffect(() => {
    if (!data?.expires_at) return;

    const interval = setInterval(() => {
      const expires = new Date(data.expires_at).getTime();
      const diffHours = Math.max(0, Math.ceil((expires - Date.now()) / (1000 * 60 * 60)));
      setHoursLeft(diffHours);

      if (diffHours <= 0) {
        setError(i18n.t('errors.report_expired'));
        setData(null);
      }
    }, 60000);

    return () => clearInterval(interval);
  }, [data, i18n]);

  // Share handler with Web Share API fallback to clipboard
  const handleShare = async () => {
    const url = window.location.href;
    const text = t('report.share_text');

    if (navigator.share) {
      try {
        await navigator.share({ title: t('report.title'), text, url });
      } catch {
        // User cancelled share dialog
      }
    } else {
      // Fallback: copy link to clipboard
      try {
        await navigator.clipboard.writeText(url);
      } catch {
        // Clipboard API not available
      }
    }
  };

  if (loading) {
    return (
      <div className="page report-page">
        <div className="loading-state">
          <div className="spinner" />
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="page report-page">
        <div className="error-state">
          <p className="error-message">{error}</p>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const report = data.report;
  const reportLanguageLabel = languageLabel(data.language);

  return (
    <div className="page report-page">
      <div className="report-summary-shell report-header-bar">
        <div className="report-hero-grid">
          <div className="report-hero-copy">
            <p className="section-kicker">{t('report.executive_kicker')}</p>
            <h2>{t('report.title')}</h2>
            <p className="report-comparison-hint">{t('report.comparison_hint')}</p>
            <p className="report-language-note">
              {t('report.language_locked_note', { language: reportLanguageLabel })}
            </p>
            {hoursLeft > 0 && (
              <p className="expiry-notice">
                {t('report.expires_in', { hours: hoursLeft })}
              </p>
            )}
          </div>

          <div className="report-hero-panel">
            <span
              className="risk-badge report-hero-badge"
              style={{ background: riskColor(report.overall_risk_level) }}
            >
              {t('report.overall_risk')}: {report.overall_risk_level}
            </span>
            <div className="report-hero-stats">
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
            </div>
          </div>
        </div>
      </div>

      {/* Overall risk card */}
      <div
        className="overall-risk-card"
        style={{
          borderColor: riskColor(report.overall_risk_level),
          background: riskBg(report.overall_risk_level),
        }}
      >
        <span
          className="risk-badge"
          style={{ background: riskColor(report.overall_risk_level) }}
        >
          {t('report.overall_risk')}: {report.overall_risk_level}
        </span>
        <p className="summary">{report.summary}</p>
        <div className="summary-metrics">
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
      </div>

      {/* Clause cards */}
      <div className="clause-list">
        {report.clause_analyses.map((clause, idx) => (
          <div
            key={idx}
            className={`clause-card ${expandedClauses[clause.clause_number] ? 'clause-card-expanded' : ''}`}
            style={{
              borderLeftColor: riskColor(clause.risk_level),
              background: riskBg(clause.risk_level),
            }}
          >
            <div className="clause-header">
              <div className="clause-heading">
                <span className="clause-eyebrow">#{String(idx + 1).padStart(2, '0')}</span>
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
                <strong>JP</strong>
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
                  <p className="risk-reason">{clause.risk_reason}</p>
                </div>
                {clause.suggestion && (
                  <div className="suggestion analysis-block">
                    <p className="analysis-label">{t('report.suggestion')}</p>
                    <p>{clause.suggestion}</p>
                  </div>
                )}
                {clause.referenced_law && (
                  <div className="reference analysis-block">
                    <p className="analysis-label">{t('report.referenced_law')}</p>
                    <p>{clause.referenced_law}</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Share button */}
      <div className="report-actions">
        <button className="btn-primary btn-share" onClick={handleShare}>
          {t('report.share')}
        </button>
        <p className="share-note">{t('report.share_note')}</p>
      </div>
    </div>
  );
}
