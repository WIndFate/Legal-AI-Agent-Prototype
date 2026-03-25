import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { exampleReports } from '../data/exampleReports';
import type { ExampleReport } from '../data/exampleReports';

type InputMode = 'text' | 'image' | 'pdf';

interface UploadResult {
  contract_text: string;
  estimated_tokens: number;
  page_estimate: number;
  price_tier: string;
  price_jpy: number;
  pii_warnings: Array<{ type: string; text: string; start: number; end: number }>;
}

export default function HomePage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();

  const [inputMode, setInputMode] = useState<InputMode>('text');
  const [textInput, setTextInput] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Payment form
  const [email, setEmail] = useState('');
  const [referralCode, setReferralCode] = useState('');
  const [paying, setPaying] = useState(false);

  const handleUpload = async () => {
    setLoading(true);
    setError('');
    setUploadResult(null);

    try {
      const formData = new FormData();
      formData.append('input_type', inputMode);

      if (inputMode === 'text') {
        formData.append('text', textInput);
      } else if (file) {
        formData.append('file', file);
      }

      const res = await fetch('/api/upload', { method: 'POST', body: formData });
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`);

      const data: UploadResult = await res.json();
      setUploadResult(data);
    } catch (e) {
      setError(t('errors.upload_failed'));
    } finally {
      setLoading(false);
    }
  };

  const handlePayment = async () => {
    if (!uploadResult || !email) return;
    setPaying(true);
    setError('');

    try {
      const res = await fetch('/api/payment/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          contract_text: uploadResult.contract_text,
          input_type: inputMode,
          estimated_tokens: uploadResult.estimated_tokens,
          price_tier: uploadResult.price_tier,
          price_jpy: uploadResult.price_jpy,
          target_language: i18n.language,
          referral_code: referralCode || undefined,
        }),
      });
      if (!res.ok) throw new Error(`Payment failed: ${res.status}`);

      const data = await res.json();
      if (data.komoju_session_url) {
        sessionStorage.setItem(`report-language:${data.order_id}`, i18n.language);
        // Redirect to KOMOJU payment page
        window.location.href = data.komoju_session_url;
      } else {
        sessionStorage.setItem(`report-language:${data.order_id}`, i18n.language);
        // Dev mode: skip payment, go directly to review
        navigate(`/review/${data.order_id}`);
      }
    } catch (e) {
      setError(t('errors.payment_failed'));
    } finally {
      setPaying(false);
    }
  };

  const tierLabel = (tier: string) => {
    const key = `pricing.tier_${tier}` as const;
    return t(key);
  };

  return (
    <div className="page home-page">
      <section className="hero-card">
        <p className="section-kicker">{t('upload.hero_kicker')}</p>
        <h2 className="hero-title">{t('app.title')}</h2>
        <p className="hero-subtitle">{t('upload.hero_body')}</p>
        <div className="trust-strip">
          <span className="trust-pill">{t('upload.trust_privacy')}</span>
          <span className="trust-pill">{t('upload.trust_no_account')}</span>
          <span className="trust-pill">{t('upload.trust_payg')}</span>
        </div>
      </section>

      <section className="flow-card">
        <p className="section-kicker">{t('upload.how_it_works')}</p>
        <div className="flow-steps">
          <div className="flow-step">
            <span className="flow-index">1</span>
            <div>
              <strong>{t('upload.flow_upload_title')}</strong>
              <p>{t('upload.flow_upload_desc')}</p>
            </div>
          </div>
          <div className="flow-step">
            <span className="flow-index">2</span>
            <div>
              <strong>{t('upload.flow_review_title')}</strong>
              <p>{t('upload.flow_review_desc')}</p>
            </div>
          </div>
          <div className="flow-step">
            <span className="flow-index">3</span>
            <div>
              <strong>{t('upload.flow_report_title')}</strong>
              <p>{t('upload.flow_report_desc')}</p>
            </div>
          </div>
        </div>
      </section>

      <ExamplesSection />

      <section className="upload-shell" id="upload-section">
      <h2>{t('upload.title')}</h2>

      {/* Input mode tabs */}
      <div className="input-tabs">
        <button
          className={`tab ${inputMode === 'image' ? 'active' : ''}`}
          onClick={() => setInputMode('image')}
        >
          📷 {t('upload.camera')}
        </button>
        <button
          className={`tab ${inputMode === 'pdf' ? 'active' : ''}`}
          onClick={() => setInputMode('pdf')}
        >
          📄 {t('upload.pdf')}
        </button>
        <button
          className={`tab ${inputMode === 'text' ? 'active' : ''}`}
          onClick={() => setInputMode('text')}
        >
          ✏️ {t('upload.paste')}
        </button>
      </div>

      {/* Input area */}
      <div className="upload-area">
        {inputMode === 'text' ? (
          <textarea
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            placeholder={t('upload.placeholder')}
            rows={12}
          />
        ) : (
          <div className="file-upload">
            <input
              type="file"
              accept={inputMode === 'image' ? 'image/*' : '.pdf'}
              capture={inputMode === 'image' ? 'environment' : undefined}
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
            {file && <p className="file-name">{file.name}</p>}
          </div>
        )}
      </div>

      <button
        className="btn-primary"
        onClick={handleUpload}
        disabled={loading || (inputMode === 'text' ? !textInput.trim() : !file)}
      >
        {loading ? '...' : t('upload.submit')}
      </button>

      {error && <div className="error-message">{error}</div>}

      {/* PII warnings */}
      {uploadResult && uploadResult.pii_warnings.length > 0 && (
        <div className="pii-warning">
          <p>{t('pii.warning')}</p>
          <ul>
            {uploadResult.pii_warnings.map((w, i) => (
              <li key={i}>
                {t(`pii.${w.type}`)}: <code>{w.text}</code>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Pricing estimate */}
      {uploadResult && uploadResult.price_jpy > 0 && (
        <div className="pricing-card polished-card">
          <h3>{t('pricing.title')}</h3>
          <div className="pricing-details pricing-summary-grid">
            <div className="pricing-summary-item">
              <span>{t('pricing.estimated_pages')}</span>
              <strong>{uploadResult.page_estimate}</strong>
            </div>
            <div className="pricing-summary-item">
              <span>{t('pricing.estimated_tokens')}</span>
              <strong>{uploadResult.estimated_tokens.toLocaleString()}</strong>
            </div>
            <div className="pricing-summary-item pricing-summary-item-wide">
              <span>{tierLabel(uploadResult.price_tier)}</span>
              <p className="price-amount">¥{uploadResult.price_jpy.toLocaleString()}</p>
            </div>
          </div>

          <div className="pricing-assurance">
            <div className="assurance-item">
              <strong>{t('pricing.assurance_privacy_title')}</strong>
              <p>{t('pricing.assurance_privacy_desc')}</p>
            </div>
            <div className="assurance-item">
              <strong>{t('pricing.assurance_delivery_title')}</strong>
              <p>{t('pricing.assurance_delivery_desc')}</p>
            </div>
          </div>

          {/* Payment form */}
          <div className="payment-form">
            <h3>{t('payment.title')}</h3>
            <label>
              {t('payment.email_label')}
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={t('payment.email_placeholder')}
              />
            </label>
            <label>
              {t('payment.referral_label')}
              <input
                type="text"
                value={referralCode}
                onChange={(e) => setReferralCode(e.target.value)}
                placeholder={t('payment.referral_placeholder')}
              />
            </label>
            <button
              className="btn-primary btn-pay"
              onClick={handlePayment}
              disabled={paying || !email}
            >
              {paying ? t('payment.processing') : t('payment.pay_button', { price: uploadResult.price_jpy.toLocaleString() })}
            </button>
            <p className="payment-note">{t('payment.secure_note')}</p>
          </div>
        </div>
      )}
      </section>
    </div>
  );
}

// Risk level color helper (shared with report pages)
function exampleRiskColor(level: string): string {
  if (level === '高') return '#dc2626';
  if (level === '中') return '#f59e0b';
  if (level === '低') return '#16a34a';
  return '#6b7280';
}

function exampleRiskBg(level: string): string {
  if (level === '高') return '#fef2f2';
  if (level === '中') return '#fffbeb';
  if (level === '低') return '#f0fdf4';
  return '#f9fafb';
}

type TabKey = 'rental' | 'employment' | 'parttime';

function ExamplesSection() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<TabKey>('rental');

  const tabs: { key: TabKey; label: string }[] = [
    { key: 'rental', label: t('examples.tab_rental') },
    { key: 'employment', label: t('examples.tab_employment') },
    { key: 'parttime', label: t('examples.tab_parttime') },
  ];

  const report: ExampleReport = exampleReports[activeTab];

  return (
    <section className="examples-section" id="examples">
      <p className="section-kicker">{t('examples.section_kicker')}</p>
      <h2>{t('examples.section_title')}</h2>
      <p className="examples-desc">{t('examples.section_desc')}</p>

      <div className="example-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            className={`tab ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="example-report-card">
        <div className="example-report-header">
          <span className="example-badge">{t('examples.badge')}</span>
          <h3>{t(`examples.${activeTab}_title`)}</h3>
          <p className="example-report-desc">{t(`examples.${activeTab}_desc`)}</p>
        </div>

        <div className="example-overall-risk">
          <span
            className="risk-badge"
            style={{ background: exampleRiskColor(report.overall_risk) }}
          >
            {t('report.overall_risk')}: {report.overall_risk}
          </span>
        </div>

        <div className="example-clause-list">
          {report.clauses.map((clause, idx) => (
            <div
              key={idx}
              className="example-clause-card"
              style={{
                borderLeftColor: exampleRiskColor(clause.risk_level),
                background: exampleRiskBg(clause.risk_level),
              }}
            >
              <div className="clause-header">
                <div className="clause-heading">
                  <strong>{clause.clause_number}</strong>
                </div>
                <span
                  className="risk-tag"
                  style={{ background: exampleRiskColor(clause.risk_level) }}
                >
                  {clause.risk_level}
                </span>
              </div>
              <div className="example-original-text">{clause.original_text}</div>
              <p className="risk-reason">{t(`examples.${report.id}_c${idx + 1}_reason`)}</p>
              <div className="suggestion">
                <strong>{t('report.suggestion')}:</strong>
                <p>{t(`examples.${report.id}_c${idx + 1}_suggestion`)}</p>
              </div>
              {clause.referenced_law && (
                <div className="reference">
                  <strong>{t('report.referenced_law')}:</strong>
                  <p>{clause.referenced_law}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <a href="#upload-section" className="btn-primary example-cta">
        {t('examples.cta')}
      </a>
    </section>
  );
}
