import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import OrderReminderDialog from '../components/common/OrderReminderDialog';
import ShareSheet from '../components/common/ShareSheet';

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

type AnalysisStep = 'parsing' | 'analyzing' | 'generating';

// Maximum number of automatic reconnection attempts
const MAX_RECONNECT_ATTEMPTS = 3;
// Base delay for exponential backoff (ms)
const BASE_RECONNECT_DELAY_MS = 1000;
// Inactivity timeout: treat stream as dead if no data for this long (ms)
const STREAM_TIMEOUT_MS = 60_000;

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
  const { t } = useTranslation();

  const [report, setReport] = useState<ReviewReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [currentStep, setCurrentStep] = useState<AnalysisStep>('parsing');
  const [logLines, setLogLines] = useState<string[]>([]);
  const [expandedClauses, setExpandedClauses] = useState<Record<string, boolean>>({});
  const [phaseText, setPhaseText] = useState('');
  const [reconnecting, setReconnecting] = useState(false);
  const [showCompletionPrompt, setShowCompletionPrompt] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);

  // Refs to track reconnection state without causing re-renders
  const started = useRef(false);
  const reconnectAttempt = useRef(0);
  const timeoutTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  // Track the total number of SSE events processed so far for deduplication on reconnect
  const eventIndex = useRef(0);
  // Whether the stream completed or received a server-side error (no reconnect needed)
  const terminalReached = useRef(false);

  const toolLabel = useCallback((toolName?: string) => {
    if (toolName === 'analyze_clause_risk') return t('review.tool_analyze_clause_risk');
    if (toolName === 'generate_suggestion') return t('review.tool_generate_suggestion');
    return t('review.tool_processing_clause');
  }, [t]);

  const pushLog = useCallback((line: string) =>
    setLogLines((prev) => [...prev, line].slice(-5)), []);

  const toggleClause = (clauseNumber: string) => {
    setExpandedClauses((prev) => ({
      ...prev,
      [clauseNumber]: !prev[clauseNumber],
    }));
  };

  const phaseMeta = useCallback((step: AnalysisStep) => {
    if (step === 'parsing') {
      return { title: t('review.phase_parsing_title'), desc: t('review.phase_parsing_desc') };
    }
    if (step === 'analyzing') {
      return { title: t('review.phase_analyzing_title'), desc: t('review.phase_analyzing_desc') };
    }
    return { title: t('review.phase_generating_title'), desc: t('review.phase_generating_desc') };
  }, [t]);

  /** Clear the inactivity timeout timer */
  const clearStreamTimeout = useCallback(() => {
    if (timeoutTimer.current) {
      clearTimeout(timeoutTimer.current);
      timeoutTimer.current = null;
    }
  }, []);

  /**
   * Reset (or start) the inactivity timeout. If no data arrives within
   * STREAM_TIMEOUT_MS, the callback fires to trigger a reconnect attempt.
   */
  const resetStreamTimeout = useCallback((onTimeout: () => void) => {
    clearStreamTimeout();
    timeoutTimer.current = setTimeout(onTimeout, STREAM_TIMEOUT_MS);
  }, [clearStreamTimeout]);

  /**
   * Core SSE connection logic. Returns a promise that resolves when the
   * stream ends (either normally or due to disconnection).
   *
   * - On `complete` or `error` events the promise resolves with `'terminal'`
   *   meaning no reconnect is needed.
   * - On unexpected end-of-stream or timeout it resolves with `'disconnected'`.
   * - On 409 (already completed) it fetches the stored report and resolves `'terminal'`.
   */
  const connectSSE = useCallback(async (): Promise<'terminal' | 'disconnected'> => {
    const abortController = new AbortController();
    abortRef.current = abortController;

    // The number of events already processed before this connection attempt.
    // On reconnect the backend replays from the beginning, so we skip this many events.
    const skipCount = eventIndex.current;

    try {
      const res = await fetch('/api/review/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order_id: orderId }),
        signal: abortController.signal,
      });

      // If analysis already completed, fetch the stored report
      if (res.status === 409) {
        const reportRes = await fetch(`/api/report/${orderId}`);
        if (reportRes.ok) {
          const data = await reportRes.json();
          const savedOriginals = sessionStorage.getItem(`report-originals:${orderId}`);
          const originalByClause = savedOriginals ? JSON.parse(savedOriginals) as Record<string, string> : {};
          const persistedReport = data.report || data;
          setReport({
            ...persistedReport,
            clause_analyses: (persistedReport.clause_analyses || []).map((clause: ClauseAnalysis) => ({
              ...clause,
              original_text: originalByClause[clause.clause_number] || '',
            })),
          });
        }
        setLoading(false);
        return 'terminal';
      }

      if (!res.ok) {
        throw new Error(`Review failed: ${res.status}`);
      }

      // Parse SSE stream
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let localEventIdx = 0;

      // Set up inactivity timeout that will abort this connection
      const handleTimeout = () => {
        abortController.abort();
      };
      resetStreamTimeout(handleTimeout);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // Reset inactivity timer on every data chunk
        resetStreamTimeout(handleTimeout);

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;

          // Deduplicate: skip events already processed in a previous connection
          if (localEventIdx < skipCount) {
            localEventIdx++;
            eventIndex.current = Math.max(eventIndex.current, localEventIdx);
            continue;
          }
          localEventIdx++;
          eventIndex.current = Math.max(eventIndex.current, localEventIdx);

          try {
            const evt: StreamEvent = JSON.parse(line.slice(6));

            switch (evt.type) {
              case 'node_start': {
                if (evt.label) pushLog(evt.label);
                // Update step indicator based on node name
                const matchedStep = STEP_DEFS.find(
                  (s) => evt.node && evt.node.includes(s.nodeMatch)
                );
                if (matchedStep) {
                  setCurrentStep(matchedStep.key);
                  setPhaseText(phaseMeta(matchedStep.key).desc);
                }
                break;
              }
              case 'tool_call':
                {
                  const label = toolLabel(evt.tool);
                  pushLog(label);
                  setPhaseText(label);
                }
                break;
              case 'tool_result':
                if (evt.text) {
                  pushLog(evt.text);
                  setPhaseText(evt.text);
                }
                break;
              case 'complete':
                clearStreamTimeout();
                if (evt.report) {
                  const originalByClause = Object.fromEntries(
                    evt.report.clause_analyses
                      .filter((clause) => clause.original_text)
                      .map((clause) => [clause.clause_number, clause.original_text as string])
                  );
                  sessionStorage.setItem(`report-originals:${orderId}`, JSON.stringify(originalByClause));
                  setReport(evt.report);
                  setLoading(false);
                  setShowCompletionPrompt(true);
                }
                terminalReached.current = true;
                return 'terminal';
              case 'error':
                clearStreamTimeout();
                setError(evt.message || t('errors.review_failed'));
                setLoading(false);
                terminalReached.current = true;
                return 'terminal';
            }
          } catch {
            // Skip malformed SSE JSON
          }
        }
      }

      clearStreamTimeout();
      // Stream ended without a terminal event — treat as unexpected disconnection
      return 'disconnected';
    } catch (e) {
      clearStreamTimeout();
      // AbortError from timeout or manual abort — treat as disconnection
      if (e instanceof DOMException && e.name === 'AbortError') {
        return 'disconnected';
      }
      // Network error — also treat as disconnection for retry
      if (e instanceof TypeError) {
        return 'disconnected';
      }
      // Other unexpected errors — surface to user
      throw e;
    }
  }, [orderId, t, pushLog, toolLabel, phaseMeta, clearStreamTimeout, resetStreamTimeout]);

  /**
   * Initiate the SSE review stream with automatic reconnection.
   * On unexpected disconnection, retries with exponential backoff
   * up to MAX_RECONNECT_ATTEMPTS times.
   */
  const startReviewWithReconnect = useCallback(async () => {
    reconnectAttempt.current = 0;
    terminalReached.current = false;

    while (true) {
      try {
        setReconnecting(reconnectAttempt.current > 0);
        const result = await connectSSE();
        setReconnecting(false);

        if (result === 'terminal') {
          // Stream completed normally or server returned an error — done
          return;
        }

        // Disconnected unexpectedly — check if we can retry
        if (terminalReached.current) return;

        reconnectAttempt.current++;
        if (reconnectAttempt.current > MAX_RECONNECT_ATTEMPTS) {
          // Exhausted all retries — show error with manual retry option
          setError(t('review.reconnect_failed'));
          setLoading(false);
          return;
        }

        // Exponential backoff: 1s, 2s, 4s
        const delay = BASE_RECONNECT_DELAY_MS * Math.pow(2, reconnectAttempt.current - 1);
        await new Promise((resolve) => setTimeout(resolve, delay));
      } catch (e) {
        // Non-retryable error
        setError(e instanceof Error ? e.message : t('errors.review_failed'));
        setLoading(false);
        return;
      }
    }
  }, [connectSSE, t]);

  /** Manual retry handler — resets all state and starts fresh */
  const handleManualRetry = useCallback(() => {
    // Reset all relevant state
    setError('');
    setLoading(true);
    setReport(null);
    setCurrentStep('parsing');
    setLogLines([]);
    setPhaseText('');
    setReconnecting(false);
    reconnectAttempt.current = 0;
    eventIndex.current = 0;
    terminalReached.current = false;

    startReviewWithReconnect();
  }, [startReviewWithReconnect]);

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    startReviewWithReconnect();

    // Cleanup: abort any in-flight connection and clear timers on unmount
    return () => {
      clearStreamTimeout();
      if (abortRef.current) {
        abortRef.current.abort();
      }
    };
  }, [startReviewWithReconnect, clearStreamTimeout]);

  // Determine step status for progress indicator
  const stepOrder: AnalysisStep[] = ['parsing', 'analyzing', 'generating'];
  const currentStepIdx = stepOrder.indexOf(currentStep);
  const currentPhase = phaseMeta(currentStep);

  return (
    <div className="page review-page">
      {orderId && (
        <ShareSheet
          open={shareOpen}
          onClose={() => setShareOpen(false)}
          shareUrl={`${window.location.origin}/report/${orderId}`}
          orderId={orderId}
        />
      )}
      {orderId && (
        <OrderReminderDialog
          open={showCompletionPrompt}
          orderId={orderId}
          title={t('order.save_after_review_title')}
          description={t('order.save_after_review_desc')}
          primaryLabel={t('order.open_report')}
          onPrimary={() => navigate(`/report/${orderId}`)}
          secondaryLabel={t('share.close')}
          onSecondary={() => setShowCompletionPrompt(false)}
        />
      )}
      {/* Streaming progress section */}
      {loading && (
        <div className="analyzing-section">
          <div className="review-live-card">
            <div className="review-live-header">
              <div>
                <p className="section-kicker">{t('review.live_label')}</p>
                <h2>{currentPhase.title}</h2>
                <p className="review-phase-text">{phaseText || currentPhase.desc}</p>
              </div>
              <div className="review-phase-panel">
                <span className="review-phase-chip">{t('review.analyzing')}</span>
                <div className="review-phase-stats">
                  <div className="review-phase-stat">
                    <span>{t('review.live_label')}</span>
                    <strong>{currentStepIdx + 1}/3</strong>
                  </div>
                  <div className="review-phase-stat">
                    <span>{t('report.title')}</span>
                    <strong>{currentPhase.title}</strong>
                  </div>
                </div>
              </div>
            </div>

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

            {/* Reconnecting indicator */}
            {reconnecting && (
              <div className="reconnecting-banner">
                <div className="spinner spinner-small" />
                <span>{t('review.reconnecting')}</span>
              </div>
            )}

            {/* Spinner and live log */}
            <div className="stream-log polished-stream-log">
              <div className="spinner" />
              <p className="analyzing-text">{t('review.analyzing')}</p>
              <div className="recent-log">
                {logLines.map((line, i) => (
                  <p key={i} className="recent-log-line">{line}</p>
                ))}
              </div>
            </div>

            <div className="review-assurance-grid">
              <div className="review-assurance-card">
                <span>{t('upload.trust_privacy')}</span>
                <strong>24h</strong>
              </div>
              <div className="review-assurance-card">
                <span>{t('report.referenced_law')}</span>
                <strong>{t('report.japanese_original')}</strong>
              </div>
              <div className="review-assurance-card">
                <span>{t('payment.title')}</span>
                <strong>{t('review.live_label')}</strong>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Error display with optional manual retry button */}
      {error && (
        <div className="error-message">
          <p>{error}</p>
          <button
            className="btn-primary btn-retry"
            onClick={handleManualRetry}
          >
            {t('review.retry')}
          </button>
        </div>
      )}

      {/* Report display */}
      {report && (
        <div className="report-section">
          <div className="report-summary-shell">
            <p className="section-kicker">{t('report.executive_kicker')}</p>
            <h2>{t('report.title')}</h2>
            <p className="report-comparison-hint">{t('report.comparison_hint')}</p>
            {orderId && (
              <div className="order-inline-card order-inline-card-report">
                <span>{t('order.order_id')}</span>
                <strong>{orderId}</strong>
                <p>{t('order.lookup_help_body')}</p>
              </div>
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
                    <strong>{clause.clause_number}</strong>
                  </div>
                  <span
                    className="risk-tag"
                    style={{ background: riskColor(clause.risk_level) }}
                  >
                    {clause.risk_level}
                  </span>
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
                      <p className="inline-original-note">{t('report.original_contract_session_note')}</p>
                    </div>
                  )}
                  <div className="clause-analysis-panel">
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
                </div>
              </div>
            ))}
          </div>

          {/* Navigate to shareable report page */}
          <div className="report-actions">
            <button
              className="btn-primary btn-share"
              onClick={() => setShareOpen(true)}
            >
              {t('report.share')}
            </button>
            {orderId && (
              <button
                className="btn-share dialog-secondary-btn"
                onClick={() => navigate(`/report/${orderId}`)}
              >
                {t('order.open_report')}
              </button>
            )}
            <p className="share-note">{t('report.share_note')}</p>
          </div>
        </div>
      )}
    </div>
  );
}
