import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

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
        sessionStorage.setItem(`contract-text:${data.order_id}`, uploadResult.contract_text);
        // Redirect to KOMOJU payment page
        window.location.href = data.komoju_session_url;
      } else {
        sessionStorage.setItem(`report-language:${data.order_id}`, i18n.language);
        sessionStorage.setItem(`contract-text:${data.order_id}`, uploadResult.contract_text);
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
        <div className="pricing-card">
          <h3>{t('pricing.title')}</h3>
          <div className="pricing-details">
            <p>{t('pricing.estimated_pages')}: {uploadResult.page_estimate}</p>
            <p className="price-tier">{tierLabel(uploadResult.price_tier)}</p>
            <p className="price-amount">¥{uploadResult.price_jpy.toLocaleString()}</p>
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
          </div>
        </div>
      )}
    </div>
  );
}
