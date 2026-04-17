import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { appendOrderToken, resolveOrderAccessToken } from '../lib/orderAccess';

interface AnalysisEventItem {
  seq: number;
  event_type: 'node_start' | 'node_end' | 'tool_call' | 'tool_result' | 'clause_progress' | 'complete' | 'error';
  step: 'parsing' | 'analyzing' | 'generating' | null;
  message: string | null;
  payload_json: Record<string, unknown> | null;
  created_at: string;
}

interface OrderStatusResponse {
  order_id: string;
  payment_status: string;
  analysis_status: 'waiting' | 'queued' | 'processing' | 'completed' | 'failed';
  current_step: 'parsing' | 'analyzing' | 'generating' | null;
  progress_message: string | null;
  progress_seq: number;
  report_ready: boolean;
  error_code: string | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
}

type AnalysisStep = 'parsing' | 'analyzing' | 'generating';

const MAX_RECONNECT_ATTEMPTS = 3;
const BASE_RECONNECT_DELAY_MS = 1000;

const STEP_DEFS: { key: AnalysisStep }[] = [
  { key: 'parsing' },
  { key: 'analyzing' },
  { key: 'generating' },
];

export default function ReviewPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { t } = useTranslation();
  const accessToken = resolveOrderAccessToken(orderId ?? null, searchParams);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [analysisStatus, setAnalysisStatus] = useState<OrderStatusResponse['analysis_status']>('queued');
  const [currentStep, setCurrentStep] = useState<AnalysisStep>('parsing');
  const [activityEvents, setActivityEvents] = useState<AnalysisEventItem[]>([]);
  const [reconnecting, setReconnecting] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [analysisStartedAtMs, setAnalysisStartedAtMs] = useState<number | null>(null);
  const [totalClauses, setTotalClauses] = useState<number | null>(null);
  const [analyzedClauses, setAnalyzedClauses] = useState(0);
  const [analysisFinishedAtMs, setAnalysisFinishedAtMs] = useState<number | null>(null);
  const [transitioning, setTransitioning] = useState(false);

  const started = useRef(false);
  const reconnectAttempt = useRef(0);
  const streamAbortRef = useRef<AbortController | null>(null);
  const lastSeqRef = useRef(0);
  const completeTimeoutRef = useRef<number | null>(null);
  const previousStepRef = useRef<AnalysisStep>('parsing');

  const pushActivityEvent = useCallback((evt: AnalysisEventItem) => {
    setActivityEvents((prev) => {
      if (prev.some((item) => item.seq === evt.seq)) return prev;
      return [...prev, evt].slice(-6);
    });
  }, []);

  const resolveReviewError = useCallback((errorCode?: string | null, fallback?: string | null) => {
    if (errorCode === 'non_contract_document') {
      return t('errors.non_contract_document');
    }
    return fallback || t('errors.review_failed');
  }, [t]);

  const extractClauseNumber = useCallback((payload: Record<string, unknown> | null): string | null => {
    const clauseText = typeof payload?.clause === 'string' ? payload.clause : null;
    if (!clauseText) return null;
    const match = clauseText.match(/第\s*\d+\s*条/);
    return match?.[0]?.replace(/\s+/g, '') ?? null;
  }, []);

  const phaseMeta = useCallback((step: AnalysisStep) => {
    if (step === 'parsing') {
      return { title: t('review.phase_parsing_title'), desc: t('review.phase_parsing_desc') };
    }
    if (step === 'analyzing') {
      return { title: t('review.phase_analyzing_title'), desc: t('review.phase_analyzing_desc') };
    }
    return { title: t('review.phase_generating_title'), desc: t('review.phase_generating_desc') };
  }, [t]);

  const fetchOrderStatus = useCallback(async (): Promise<OrderStatusResponse> => {
    const res = await fetch(appendOrderToken(`/api/orders/${orderId}/status`, accessToken));
    if (!res.ok) throw new Error(t('errors.review_failed'));
    return res.json();
  }, [accessToken, orderId, t]);

  const requestAnalysisStart = useCallback(async () => {
    const res = await fetch('/api/analysis/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ order_id: orderId, access_token: accessToken }),
    });
    if (!res.ok && res.status !== 409) {
      if (res.status === 402) {
        navigate(`/payment/${orderId}`);
        return false;
      }
      throw new Error(t('errors.review_failed'));
    }
    return true;
  }, [accessToken, navigate, orderId, t]);

  const resolveEventMessage = useCallback((evt: AnalysisEventItem): string | null => {
    if (evt.event_type === 'node_start') {
      const node = typeof evt.payload_json?.node === 'string' ? evt.payload_json.node : null;
      if (node === 'parse_contract') return t('review.phase_parsing_desc');
      if (node === 'analyze_risks') return t('review.phase_analyzing_desc');
      if (node === 'generate_report') return t('review.phase_generating_desc');
    }

    if (evt.event_type === 'tool_call') {
      const tool = typeof evt.payload_json?.tool === 'string' ? evt.payload_json.tool : null;
      const clauseNumber = extractClauseNumber(evt.payload_json);
      if (tool === 'analyze_clause_risk') {
        return clauseNumber
          ? t('review.tool_analyzing_clause', { clause: clauseNumber })
          : t('review.tool_analyze_clause_risk');
      }
      if (tool === 'generate_suggestion') {
        return clauseNumber
          ? t('review.tool_suggesting_clause', { clause: clauseNumber })
          : t('review.tool_generate_suggestion');
      }
      return t('review.tool_processing_clause');
    }

    if (evt.event_type === 'tool_result') {
      const tool = typeof evt.payload_json?.tool === 'string' ? evt.payload_json.tool : null;
      if (tool === 'analyze_clause_risk') return t('review.tool_clause_analyzed');
      if (tool === 'generate_suggestion') return t('review.tool_suggestion_generated');
    }

    if (evt.event_type === 'complete') {
      return t('review.complete_title');
    }

    if (evt.event_type === 'error') {
      return evt.message || t('errors.review_failed');
    }

    return evt.message;
  }, [extractClauseNumber, t]);

  const applyStatusSnapshot = useCallback((status: OrderStatusResponse) => {
    setAnalysisStatus(status.analysis_status);
    if (status.current_step) {
      setCurrentStep(status.current_step);
    }
    if (status.started_at) {
      const parsedStart = Date.parse(status.started_at);
      if (!Number.isNaN(parsedStart)) {
        setAnalysisStartedAtMs(parsedStart);
        // Use finished_at to cap elapsed time so reopened pages don't
        // keep counting wall-clock time past analysis completion.
        if (status.finished_at) {
          const parsedEnd = Date.parse(status.finished_at);
          if (!Number.isNaN(parsedEnd)) {
            setAnalysisFinishedAtMs(parsedEnd);
            setElapsedSeconds(Math.max(0, Math.floor((parsedEnd - parsedStart) / 1000)));
            return;
          }
        }
        setElapsedSeconds(Math.max(0, Math.floor((Date.now() - parsedStart) / 1000)));
      }
    }
  }, []);

  const processEvent = useCallback((evt: AnalysisEventItem) => {
    if (evt.seq <= lastSeqRef.current) {
      return;
    }
    lastSeqRef.current = Math.max(lastSeqRef.current, evt.seq);
    const eventMessage = resolveEventMessage(evt);

    if (evt.step) {
      setCurrentStep(evt.step);
    }

    switch (evt.event_type) {
      case 'node_start':
        if (evt.payload_json?.node === 'analyze_risks') {
          setAnalyzedClauses(0);
        }
        if (eventMessage) pushActivityEvent(evt);
        break;
      case 'node_end':
        if (evt.payload_json?.node === 'parse_contract') {
          const nextTotal = evt.payload_json?.total_clauses;
          setTotalClauses(typeof nextTotal === 'number' ? nextTotal : null);
        }
        break;
      case 'clause_progress':
        if (typeof evt.payload_json?.analyzed === 'number') {
          setAnalyzedClauses(evt.payload_json.analyzed as number);
        }
        break;
      case 'tool_call':
        if (eventMessage) pushActivityEvent(evt);
        break;
      case 'tool_result':
        if (eventMessage) pushActivityEvent(evt);
        break;
      case 'complete':
        setAnalysisStatus('completed');
        if (analysisFinishedAtMs == null && evt.created_at) {
          const parsedEnd = Date.parse(evt.created_at);
          if (!Number.isNaN(parsedEnd)) setAnalysisFinishedAtMs(parsedEnd);
        }
        pushActivityEvent(evt);
        if (orderId) {
          completeTimeoutRef.current = window.setTimeout(() => {
            navigate(appendOrderToken(`/report/${orderId}`, accessToken));
          }, 1200);
        }
        break;
      case 'error':
        setAnalysisStatus('failed');
        setErrorCode(typeof evt.payload_json?.error_code === 'string' ? evt.payload_json.error_code : null);
        setError(resolveReviewError(
          typeof evt.payload_json?.error_code === 'string' ? evt.payload_json.error_code : null,
          eventMessage || t('errors.review_failed'),
        ));
        setLoading(false);
        break;
    }
  }, [accessToken, analysisFinishedAtMs, navigate, orderId, pushActivityEvent, resolveEventMessage, resolveReviewError, t]);

  const loadHistory = useCallback(async () => {
    const res = await fetch(appendOrderToken(`/api/orders/${orderId}/events?after_seq=0`, accessToken));
    if (!res.ok) throw new Error(t('errors.review_failed'));
    const data = await res.json();
    setActivityEvents([]);
    lastSeqRef.current = 0;
    for (const evt of data.events as AnalysisEventItem[]) {
      processEvent(evt);
    }
  }, [accessToken, orderId, processEvent, t]);

  const connectStream = useCallback(async (): Promise<'terminal' | 'disconnected'> => {
    const abortController = new AbortController();
    streamAbortRef.current = abortController;

    try {
      const res = await fetch(
        appendOrderToken(`/api/orders/${orderId}/stream?after_seq=${lastSeqRef.current}`, accessToken),
        {
        signal: abortController.signal,
        },
      );
      if (!res.ok) {
        throw new Error(`Stream failed: ${res.status}`);
      }

      const reader = res.body?.getReader();
      if (!reader) return 'disconnected';

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split('\n\n');
        buffer = chunks.pop() ?? '';

        for (const chunk of chunks) {
          const trimmed = chunk.trim();
          if (!trimmed || trimmed.startsWith(':')) continue;
          const dataLine = trimmed
            .split('\n')
            .find((line) => line.startsWith('data: '));
          if (!dataLine) continue;
          try {
            const evt = JSON.parse(dataLine.slice(6)) as AnalysisEventItem;
            processEvent(evt);
            if (evt.event_type === 'complete' || evt.event_type === 'error') {
              return 'terminal';
            }
          } catch {
            // ignore malformed event payload
          }
        }
      }

      return 'disconnected';
    } catch (errorValue) {
      if (errorValue instanceof DOMException && errorValue.name === 'AbortError') {
        return 'disconnected';
      }
      if (errorValue instanceof TypeError) {
        return 'disconnected';
      }
      throw errorValue;
    }
  }, [accessToken, orderId, processEvent]);

  const startStreamLoop = useCallback(async () => {
    reconnectAttempt.current = 0;

    while (true) {
      setReconnecting(reconnectAttempt.current > 0);
      const result = await connectStream();
      setReconnecting(false);

      if (result === 'terminal') {
        return;
      }

      reconnectAttempt.current += 1;
      if (reconnectAttempt.current > MAX_RECONNECT_ATTEMPTS) {
        setError(t('review.reconnect_failed'));
        setLoading(false);
        return;
      }

      const delay = BASE_RECONNECT_DELAY_MS * Math.pow(2, reconnectAttempt.current - 1);
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }, [connectStream, t]);

  const bootstrap = useCallback(async (retryFailed = false) => {
    if (!orderId) return;

    streamAbortRef.current?.abort();
    setLoading(true);
    setError('');
    setErrorCode(null);
    setActivityEvents([]);
    setElapsedSeconds(0);
    setAnalysisStartedAtMs(null);
    setAnalysisFinishedAtMs(null);
    setTotalClauses(null);
    setAnalyzedClauses(0);
    previousStepRef.current = 'parsing';

    let status = await fetchOrderStatus();

    if (status.payment_status !== 'paid' && status.payment_status !== 'captured') {
      navigate(`/payment/${orderId}`);
      return;
    }
    applyStatusSnapshot(status);

    if (status.report_ready && status.analysis_status === 'completed') {
      navigate(`/report/${orderId}`);
      return;
    }

    if (status.analysis_status === 'failed' && !retryFailed) {
      setLoading(false);
      setErrorCode(status.error_code);
      setError(resolveReviewError(status.error_code, status.error_message));
      return;
    }

    if (
      retryFailed ||
      status.analysis_status === 'waiting' ||
      status.analysis_status === 'queued' ||
      status.analysis_status === 'processing'
    ) {
      const startedOk = await requestAnalysisStart();
      if (!startedOk) return;
      status = await fetchOrderStatus();
      applyStatusSnapshot(status);
      if (status.analysis_status === 'failed') {
        setLoading(false);
        setErrorCode(status.error_code);
        setError(resolveReviewError(status.error_code, status.error_message));
        return;
      }
      if (status.report_ready && status.analysis_status === 'completed') {
        navigate(`/report/${orderId}`);
        return;
      }
    }

    await loadHistory();
    setLoading(true);
    await startStreamLoop();
  }, [applyStatusSnapshot, fetchOrderStatus, loadHistory, navigate, orderId, requestAnalysisStart, resolveReviewError, startStreamLoop, t]);

  const handleManualRetry = useCallback(() => {
    void bootstrap(true);
  }, [bootstrap]);

  const isNonContractError = errorCode === 'non_contract_document';

  useEffect(() => {
    if (started.current || !orderId) return;
    started.current = true;
    void bootstrap();

    return () => {
      streamAbortRef.current?.abort();
      if (completeTimeoutRef.current) {
        window.clearTimeout(completeTimeoutRef.current);
      }
    };
  }, [bootstrap, orderId]);

  useEffect(() => {
    if (!loading) return;

    // When the analysis has a known end time, freeze the elapsed display
    // so it reflects actual analysis duration, not wall-clock since start.
    if (analysisFinishedAtMs != null && analysisStartedAtMs != null) {
      setElapsedSeconds(Math.max(0, Math.floor((analysisFinishedAtMs - analysisStartedAtMs) / 1000)));
      return;
    }

    const timer = window.setInterval(() => {
      if (analysisStartedAtMs != null) {
        setElapsedSeconds(Math.max(0, Math.floor((Date.now() - analysisStartedAtMs) / 1000)));
        return;
      }
      setElapsedSeconds((current) => current + 1);
    }, 1000);

    return () => window.clearInterval(timer);
  }, [analysisStartedAtMs, analysisFinishedAtMs, loading]);

  useEffect(() => {
    if (previousStepRef.current === currentStep) {
      return;
    }
    previousStepRef.current = currentStep;
    setTransitioning(true);
    const timeout = window.setTimeout(() => {
      setTransitioning(false);
    }, 400);

    return () => window.clearTimeout(timeout);
  }, [currentStep]);

  const formatElapsed = useCallback((totalSeconds: number) => {
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }, []);

  const currentPhase = phaseMeta(currentStep);
  const currentStepIdx = STEP_DEFS.findIndex((item) => item.key === currentStep);
  const activityItems = activityEvents
    .map((evt) => ({ seq: evt.seq, text: resolveEventMessage(evt) }))
    .filter((item): item is { seq: number; text: string } => Boolean(item.text))
    .reduce<{ seq: number; text: string }[]>((acc, item) => {
      if (acc[acc.length - 1]?.text === item.text) return acc;
      acc.push(item);
      return acc;
    }, [])
    .slice(-4);

  const decorateCurrentActivity = useCallback((text: string, isCurrent: boolean) => {
    if (!isCurrent) return text;
    const base = text.replace(/(?:\.\.\.|…)+$/, '').trimEnd();
    const dots = '.'.repeat((elapsedSeconds % 3) + 1);
    return `${base}${dots}`;
  }, [elapsedSeconds]);

  return (
    <div className="page review-page">
      {(loading || error) && (
        <div className="analyzing-section">
          <div className="review-live-card">
            <div className={`review-stage-header ${transitioning ? 'transitioning' : ''}`}>
              <div className={`review-stage-icon stage-${error ? 'error' : analysisStatus === 'completed' ? 'completed' : currentStep}`} aria-hidden="true">
                <span />
              </div>
              <h2 className="review-stage-title">
                {error
                  ? (isNonContractError ? t('review.not_contract_title') : t('errors.review_failed'))
                  : analysisStatus === 'completed' ? t('review.complete_title') : currentPhase.title}
              </h2>
              <p className="review-stage-desc">
                {error
                  ? (isNonContractError ? t('review.not_contract_desc') : error)
                  : currentPhase.desc}
              </p>
            </div>

            <div className="review-progress">
              <div className="review-progress-track">
                {STEP_DEFS.map((step, idx) => {
                  let stepStatus: 'done' | 'active' | 'pending' | 'error' = 'pending';
                  if (analysisStatus === 'completed' || idx < currentStepIdx) stepStatus = 'done';
                  else if (idx === currentStepIdx) stepStatus = error ? 'error' : 'active';

                  return (
                    <div key={step.key} className={`review-progress-segment seg-${stepStatus}`}>
                      <div className="review-progress-fill" />
                    </div>
                  );
                })}
              </div>
              <div className="review-progress-labels">
                {STEP_DEFS.map((step, idx) => {
                  let stepStatus: 'done' | 'active' | 'pending' = 'pending';
                  if (analysisStatus === 'completed' || idx < currentStepIdx) stepStatus = 'done';
                  else if (idx === currentStepIdx) stepStatus = 'active';

                  const labelKey = `review.step_${step.key}_short` as const;
                  return (
                    <span key={step.key} className={`review-progress-label lbl-${stepStatus}`}>
                      {t(labelKey)}
                    </span>
                  );
                })}
              </div>
              {currentStep === 'analyzing' && totalClauses != null && (
                <div className="review-clause-progress">
                  {t('review.clause_progress', { current: Math.min(analyzedClauses, totalClauses), total: totalClauses })}
                </div>
              )}
            </div>

            {!error && reconnecting && (
              <div className="reconnecting-banner">
                <div className="spinner spinner-small" />
                <span>{t('review.reconnecting')}</span>
              </div>
            )}

            {!error && (
              <div className="review-activity">
                <div className="review-activity-line" aria-hidden="true" />
                <div className="review-activity-list">
                  {(activityItems.length > 0 ? activityItems : [{ seq: -1, text: currentPhase.desc }]).map((item, i, items) => (
                    <div
                      key={`${item.seq}-${i}`}
                      className={`review-activity-item ${i === items.length - 1 ? 'is-current' : ''}`}
                    >
                      <div className="review-activity-dot" />
                      <span className="review-activity-text">
                        {decorateCurrentActivity(item.text, i === items.length - 1)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="review-elapsed">
              <span>{t('review.elapsed', { time: formatElapsed(elapsedSeconds) })}</span>
            </div>

            {error && (
              <div className="review-error-body">
                {!isNonContractError && <p>{error}</p>}
                {isNonContractError ? (
                  <button
                    className="btn-primary btn-retry"
                    onClick={() => navigate('/')}
                  >
                    {t('nav.home')}
                  </button>
                ) : (
                  <button
                    className="btn-primary btn-retry"
                    onClick={handleManualRetry}
                  >
                    {t('review.retry')}
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
