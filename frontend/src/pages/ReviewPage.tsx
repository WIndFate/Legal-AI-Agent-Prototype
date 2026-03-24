import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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

interface ReviewReport {
  overall_risk_level: string;
  summary: string;
  clause_analyses: ClauseAnalysis[];
  high_risk_count: number;
  medium_risk_count: number;
  low_risk_count: number;
  total_clauses: number;
}

interface StreamEvent {
  type: 'node_start' | 'token' | 'tool_call' | 'tool_result' | 'complete' | 'error';
  node?: string;
  label?: string;
  text?: string;
  tool?: string;
  clause?: string;
  report?: ReviewReport;
  message?: string;
}

const TOOL_LABELS: Record<string, string> = {
  analyze_clause_risk: '正在检索相关法条与风险依据…',
  generate_suggestion: '正在生成更易理解的修改建议…',
};

type AnalysisStep = 'parsing' | 'analyzing' | 'generating';

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

// Step definitions for progress indicator
const STEP_DEFS: { key: AnalysisStep; nodeMatch: string }[] = [
  { key: 'parsing', nodeMatch: 'parse_contract' },
  { key: 'analyzing', nodeMatch: 'analyze_risks' },
  { key: 'generating', nodeMatch: 'generate_report' },
];

export default function ReviewPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();

  const [report, setReport] = useState<ReviewReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [currentStep, setCurrentStep] = useState<AnalysisStep>('parsing');
  const [logLines, setLogLines] = useState<string[]>([]);
  const [originalContractText, setOriginalContractText] = useState('');
  const started = useRef(false);

  const pushLog = (line: string) =>
    setLogLines((prev) => [...prev, line].slice(-5));

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    setOriginalContractText(sessionStorage.getItem(`contract-text:${orderId}`) || '');

    const startReview = async () => {
      try {
        const res = await fetch('/api/review/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ order_id: orderId }),
        });

        // If analysis already completed, fetch the stored report
        if (res.status === 409) {
          const reportRes = await fetch(`/api/report/${orderId}`);
          if (reportRes.ok) {
            const data = await reportRes.json();
            if (data.language) {
              void i18n.changeLanguage(data.language);
            }
            setReport(data.report || data);
          }
          setLoading(false);
          return;
        }

        if (!res.ok) {
          throw new Error(`Review failed: ${res.status}`);
        }

        // Parse SSE stream
        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            try {
              const evt: StreamEvent = JSON.parse(line.slice(6));

              switch (evt.type) {
                case 'node_start': {
                  if (evt.label) pushLog(evt.label);
                  // Update step indicator based on node name
                  const matchedStep = STEP_DEFS.find(
                    (s) => evt.node && evt.node.includes(s.nodeMatch)
                  );
                  if (matchedStep) setCurrentStep(matchedStep.key);
                  break;
                }
                case 'tool_call':
                  pushLog(TOOL_LABELS[evt.tool || ''] || '正在处理条款分析步骤…');
                  break;
                case 'tool_result':
                  if (evt.text) pushLog(evt.text);
                  break;
                case 'complete':
                  if (evt.report) {
                    setReport(evt.report);
                    setLoading(false);
                  }
                  break;
                case 'error':
                  setError(evt.message || t('errors.review_failed'));
                  setLoading(false);
                  break;
              }
            } catch {
              // Skip malformed SSE JSON
            }
          }
        }

        // If stream ended without complete event, stop loading
        setLoading(false);
      } catch (e) {
        setError(e instanceof Error ? e.message : t('errors.review_failed'));
        setLoading(false);
      }
    };

    startReview();
  }, [i18n, orderId, t]);

  // Determine step status for progress indicator
  const stepOrder: AnalysisStep[] = ['parsing', 'analyzing', 'generating'];
  const currentStepIdx = stepOrder.indexOf(currentStep);

  return (
    <div className="page review-page">
      {/* Streaming progress section */}
      {loading && (
        <div className="analyzing-section">
          <h2>{t('review.title')}</h2>

          {/* Step progress indicator */}
          <div className="step-progress">
            {STEP_DEFS.map((step, idx) => {
              let stepStatus: 'done' | 'active' | 'pending' = 'pending';
              if (idx < currentStepIdx) stepStatus = 'done';
              else if (idx === currentStepIdx) stepStatus = 'active';

              const labelKey = `review.step_${step.key}` as const;
              return (
                <div key={step.key} className={`step-item step-${stepStatus}`}>
                  <div className="step-circle">
                    {stepStatus === 'done' ? '\u2713' : idx + 1}
                  </div>
                  <span className="step-label">{t(labelKey)}</span>
                </div>
              );
            })}
          </div>

          {/* Spinner and live log */}
          <div className="stream-log">
            <div className="spinner" />
            <p className="analyzing-text">{t('review.analyzing')}</p>
            <div className="recent-log">
              {logLines.map((line, i) => (
                <p key={i} className="recent-log-line">{line}</p>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Error display */}
      {error && <div className="error-message">{error}</div>}

      {/* Report display */}
      {report && (
        <div className="report-section">
          <h2>{t('report.title')}</h2>

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
                仅在本设备当前会话中保留，便于与分析结果对照阅读；服务端完成分析后已删除原合同文本。
              </p>
              <pre className="original-contract-text">{originalContractText}</pre>
            </div>
          )}

          {/* Navigate to shareable report page */}
          <button
            className="btn-primary btn-share"
            onClick={() => navigate(`/report/${orderId}`)}
          >
            {t('report.share')}
          </button>
        </div>
      )}
    </div>
  );
}
