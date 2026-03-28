import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

interface AnalysisEventItem {
  seq: number;
  event_type: 'node_start' | 'tool_call' | 'tool_result' | 'complete' | 'error';
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
  const { t } = useTranslation();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [analysisStatus, setAnalysisStatus] = useState<OrderStatusResponse['analysis_status']>('queued');
  const [currentStep, setCurrentStep] = useState<AnalysisStep>('parsing');
  const [logLines, setLogLines] = useState<string[]>([]);
  const [phaseText, setPhaseText] = useState('');
  const [reconnecting, setReconnecting] = useState(false);

  const started = useRef(false);
  const reconnectAttempt = useRef(0);
  const streamAbortRef = useRef<AbortController | null>(null);
  const lastSeqRef = useRef(0);

  const pushLog = useCallback((line: string) => {
    if (!line.trim()) return;
    setLogLines((prev) => {
      if (prev[prev.length - 1] === line) return prev;
      return [...prev, line].slice(-6);
    });
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
    const res = await fetch(`/api/orders/${orderId}/status`);
    if (!res.ok) throw new Error(t('errors.review_failed'));
    return res.json();
  }, [orderId, t]);

  const requestAnalysisStart = useCallback(async () => {
    const res = await fetch('/api/analysis/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ order_id: orderId }),
    });
    if (!res.ok && res.status !== 409) {
      if (res.status === 402) {
        navigate(`/payment/${orderId}`);
        return false;
      }
      throw new Error(t('errors.review_failed'));
    }
    return true;
  }, [navigate, orderId, t]);

  const resolveEventMessage = useCallback((evt: AnalysisEventItem): string | null => {
    if (evt.event_type === 'node_start') {
      const node = typeof evt.payload_json?.node === 'string' ? evt.payload_json.node : null;
      if (node === 'parse_contract') return t('review.phase_parsing_desc');
      if (node === 'analyze_risks') return t('review.phase_analyzing_desc');
      if (node === 'generate_report') return t('review.phase_generating_desc');
    }

    if (evt.event_type === 'tool_call') {
      const tool = typeof evt.payload_json?.tool === 'string' ? evt.payload_json.tool : null;
      if (tool === 'analyze_clause_risk') return t('review.tool_analyze_clause_risk');
      if (tool === 'generate_suggestion') return t('review.tool_generate_suggestion');
      return t('review.tool_processing_clause');
    }

    if (evt.event_type === 'complete') {
      return t('review.phase_generating_desc');
    }

    if (evt.event_type === 'error') {
      return evt.message || t('errors.review_failed');
    }

    return evt.message;
  }, [t]);

  const applyStatusSnapshot = useCallback((status: OrderStatusResponse) => {
    setAnalysisStatus(status.analysis_status);
    if (status.current_step) {
      setCurrentStep(status.current_step);
      setPhaseText(phaseMeta(status.current_step).desc);
    } else if (status.progress_message) {
      setPhaseText(status.progress_message);
    }
  }, [phaseMeta]);

  const processEvent = useCallback((evt: AnalysisEventItem) => {
    lastSeqRef.current = Math.max(lastSeqRef.current, evt.seq);
    const eventMessage = resolveEventMessage(evt);

    if (evt.step) {
      setCurrentStep(evt.step);
      setPhaseText(eventMessage || phaseMeta(evt.step).desc);
    } else if (eventMessage) {
      setPhaseText(eventMessage);
    }

    switch (evt.event_type) {
      case 'node_start':
      case 'tool_call':
      case 'tool_result':
        if (eventMessage) pushLog(eventMessage);
        break;
      case 'complete':
        setAnalysisStatus('completed');
        if (orderId) {
          navigate(`/report/${orderId}`);
        }
        break;
      case 'error':
        setAnalysisStatus('failed');
        setError(eventMessage || t('errors.review_failed'));
        setLoading(false);
        break;
    }
  }, [navigate, orderId, phaseMeta, pushLog, resolveEventMessage, t]);

  const loadHistory = useCallback(async () => {
    const res = await fetch(`/api/orders/${orderId}/events?after_seq=0`);
    if (!res.ok) throw new Error(t('errors.review_failed'));
    const data = await res.json();
    setLogLines([]);
    lastSeqRef.current = 0;
    for (const evt of data.events as AnalysisEventItem[]) {
      processEvent(evt);
    }
  }, [orderId, processEvent, t]);

  const connectStream = useCallback(async (): Promise<'terminal' | 'disconnected'> => {
    const abortController = new AbortController();
    streamAbortRef.current = abortController;

    try {
      const res = await fetch(`/api/orders/${orderId}/stream?after_seq=${lastSeqRef.current}`, {
        signal: abortController.signal,
      });
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
  }, [orderId, processEvent]);

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
      setError(status.error_message || t('errors.review_failed'));
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
        setError(status.error_message || t('errors.review_failed'));
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
  }, [applyStatusSnapshot, fetchOrderStatus, loadHistory, navigate, orderId, requestAnalysisStart, startStreamLoop, t]);

  const handleManualRetry = useCallback(() => {
    void bootstrap(true);
  }, [bootstrap]);

  useEffect(() => {
    if (started.current || !orderId) return;
    started.current = true;
    void bootstrap();

    return () => {
      streamAbortRef.current?.abort();
    };
  }, [bootstrap, orderId]);

  const currentPhase = phaseMeta(currentStep);
  const currentStepIdx = STEP_DEFS.findIndex((item) => item.key === currentStep);

  return (
    <div className="page review-page">
      {loading && (
        <div className="analyzing-section">
          <div className="review-live-card">
            <div className="review-live-header">
              <div>
                <p className="section-kicker">{t('review.live_label')}</p>
                <h2>{currentPhase.title}</h2>
              </div>
              <div className="review-phase-panel">
                <span className="review-phase-chip">
                  {analysisStatus === 'queued' ? t('payment.processing') : t('review.analyzing')}
                </span>
                <div className="review-phase-stats">
                  <div className="review-phase-stat">
                    <span>{t('review.live_label')}</span>
                    <strong>{Math.max(currentStepIdx + 1, 1)}/3</strong>
                  </div>
                  <div className="review-phase-stat">
                    <span>{t('report.title')}</span>
                    <strong>{currentPhase.title}</strong>
                  </div>
                </div>
              </div>
            </div>

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

            {reconnecting && (
              <div className="reconnecting-banner">
                <div className="spinner spinner-small" />
                <span>{t('review.reconnecting')}</span>
              </div>
            )}

            <div className="stream-log polished-stream-log">
              <div className="spinner" />
              <div className="recent-log">
                {logLines.length > 0 ? (
                  logLines.map((line, i) => (
                    <p key={`${line}-${i}`} className="recent-log-line">{line}</p>
                  ))
                ) : (
                  <p className="recent-log-line">{phaseText || currentPhase.desc}</p>
                )}
              </div>
            </div>

            <div className="review-assurance-grid">
              <div className="review-assurance-card">
                <span>{t('upload.trust_privacy')}</span>
                <strong>72h</strong>
              </div>
              <div className="review-assurance-card">
                <span>{t('report.referenced_law')}</span>
                <strong>{t('report.japanese_original')}</strong>
              </div>
            </div>
          </div>
        </div>
      )}

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
    </div>
  );
}
