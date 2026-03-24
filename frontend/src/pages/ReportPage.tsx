import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

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

export default function ReportPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const { t, i18n } = useTranslation();
  const [data, setData] = useState<ReportData | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [hoursLeft, setHoursLeft] = useState(0);
  const [originalContractText, setOriginalContractText] = useState('');

  useEffect(() => {
    const fetchReport = async () => {
      try {
        const res = await fetch(`/api/report/${orderId}`);
        if (res.status === 404) {
          setError(t('errors.report_expired'));
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
        setData(json);
        setOriginalContractText(sessionStorage.getItem(`contract-text:${orderId}`) || '');
        if (json.language) {
          void i18n.changeLanguage(json.language);
        }

        // Calculate initial hours remaining
        const expires = new Date(json.expires_at).getTime();
        const diffHours = Math.max(0, Math.ceil((expires - Date.now()) / (1000 * 60 * 60)));
        setHoursLeft(diffHours);
      } catch {
        setError(t('errors.not_found'));
      } finally {
        setLoading(false);
      }
    };
    fetchReport();
  }, [i18n, orderId, t]);

  // Update expiry countdown every minute
  useEffect(() => {
    if (!data?.expires_at) return;

    const interval = setInterval(() => {
      const expires = new Date(data.expires_at).getTime();
      const diffHours = Math.max(0, Math.ceil((expires - Date.now()) / (1000 * 60 * 60)));
      setHoursLeft(diffHours);

      if (diffHours <= 0) {
        setError(t('errors.report_expired'));
        setData(null);
      }
    }, 60000);

    return () => clearInterval(interval);
  }, [data, t]);

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

  return (
    <div className="page report-page">
      <div className="report-header-bar">
        <h2>{t('report.title')}</h2>
        <p className="report-language-note">
          本报告内容已按生成时选择的语言固定为 {data.language}。切换页面语言只影响界面文案，不会重新翻译已生成报告。
        </p>
        {hoursLeft > 0 && (
          <p className="expiry-notice">
            {t('report.expires_in', { hours: hoursLeft })}
          </p>
        )}
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
        <div className="risk-stats">
          <span className="stat high">
            {t('report.high_risk')}: {report.high_risk_count}
          </span>
          <span className="stat medium">
            {t('report.medium_risk')}: {report.medium_risk_count}
          </span>
          <span className="stat low">
            {t('report.low_risk')}: {report.low_risk_count}
          </span>
        </div>
      </div>

      {/* Clause cards */}
      <div className="clause-list">
        {report.clause_analyses.map((clause, idx) => (
          <div
            key={idx}
            className="clause-card"
            style={{
              borderLeftColor: riskColor(clause.risk_level),
              background: riskBg(clause.risk_level),
            }}
          >
            <div className="clause-header">
              <strong>{clause.clause_number}</strong>
              <span
                className="risk-tag"
                style={{ background: riskColor(clause.risk_level) }}
              >
                {clause.risk_level}
              </span>
            </div>
            <p className="risk-reason">{clause.risk_reason}</p>
            {clause.suggestion && (
              <div className="suggestion">
                <strong>{t('report.suggestion')}:</strong>
                <p>{clause.suggestion}</p>
              </div>
            )}
            {clause.referenced_law && (
              <div className="reference">
                <strong>{t('report.referenced_law')}:</strong>
                <p>{clause.referenced_law}</p>
              </div>
            )}
          </div>
        ))}
      </div>

      {originalContractText && (
        <div className="original-contract-card">
          <h3>原日文合同对照</h3>
          <p className="original-contract-note">
            仅在上传合同的同一设备当前会话中可见。若通过分享链接或邮件打开，出于隐私保护不会再显示原合同全文。
          </p>
          <pre className="original-contract-text">{originalContractText}</pre>
        </div>
      )}

      {/* Share button */}
      <button className="btn-primary btn-share" onClick={handleShare}>
        {t('report.share')}
      </button>
    </div>
  );
}
