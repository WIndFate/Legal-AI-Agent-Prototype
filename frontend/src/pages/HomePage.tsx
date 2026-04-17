import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';

import RevealSection from '../components/common/RevealSection';
import HomeFlowSection from '../components/home/HomeFlowSection';
import HomeHeroSection from '../components/home/HomeHeroSection';
import HomeUploadSection from '../components/home/HomeUploadSection';
import type { InputMode, UploadResult } from '../components/home/types';
import { exampleReports } from '../data/exampleReports';
import { storeOrderAccessToken } from '../lib/orderAccess';

function detectFileInputType(file: File): 'image' | 'pdf' {
  if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
    return 'pdf';
  }
  return 'image';
}

export default function HomePage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const heroPreview = exampleReports.rental;

  const [inputMode, setInputMode] = useState<InputMode>('file');
  const [textInput, setTextInput] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [resultReady, setResultReady] = useState(false);

  // Payment form
  const [email, setEmail] = useState('');
  const [referralCode, setReferralCode] = useState('');
  const [paying, setPaying] = useState(false);

  const handleUpload = async () => {
    // Pre-flight file size check (before network round-trip)
    if (inputMode === 'file' && file) {
      const maxMB = (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) ? 30 : 25;
      if (file.size > maxMB * 1024 * 1024) {
        setError(t('errors.upload_too_large', { max: maxMB }));
        return;
      }
    }
    // Pre-flight text length check
    if (inputMode === 'text' && textInput.length > 80_000) {
      setError(t('errors.upload_text_too_long'));
      return;
    }

    setLoading(true);
    setError('');
    setUploadResult(null);

    try {
      const formData = new FormData();
      if (inputMode === 'text') {
        formData.append('input_type', 'text');
        formData.append('text', textInput);
      } else if (file) {
        formData.append('input_type', detectFileInputType(file));
        formData.append('file', file);
      }

      const res = await fetch('/api/upload', { method: 'POST', body: formData });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        const code: string = body?.detail ?? '';
        const errorKey =
          code === 'upload_too_large' ? 'errors.upload_too_large' :
          code === 'upload_too_many_pages' ? 'errors.upload_too_many_pages' :
          code === 'upload_unsupported_type' ? 'errors.upload_unsupported_type' :
          code === 'upload_encrypted_pdf' ? 'errors.upload_encrypted_pdf' :
          code === 'upload_corrupt_pdf' ? 'errors.upload_corrupt_pdf' :
          code === 'upload_text_too_long' ? 'errors.upload_text_too_long' :
          code === 'upload_banned' ? 'errors.upload_banned' :
          code === 'upload_rate_limited' ? 'errors.upload_rate_limited' :
          code === 'google_vision_not_configured' ? 'errors.google_vision_not_configured' :
          code === 'google_vision_billing_disabled' ? 'errors.google_vision_billing_disabled' :
          code === 'google_vision_api_disabled' ? 'errors.google_vision_api_disabled' :
          code === 'google_vision_permission_denied' ? 'errors.google_vision_permission_denied' :
          code === 'google_vision_auth_failed' ? 'errors.google_vision_auth_failed' :
          code === 'google_vision_unavailable' ? 'errors.google_vision_unavailable' :
          code === 'daily_budget_exhausted' ? 'errors.daily_budget_exhausted' :
          'errors.upload_failed';
        // Pick the correct max size based on the actual file type being uploaded
        const isPdf = file
          ? file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
          : false;
        const maxMB = isPdf ? 30 : 25;
        setError(t(errorKey, { max: maxMB }));
        return;
      }

      const data: UploadResult = await res.json();
      setUploadResult(data);
      setResultReady(true);
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
          input_type: uploadResult.detected_input_type,
          estimated_tokens: uploadResult.estimated_tokens,
          price_jpy: uploadResult.price_jpy,
          quote_mode: uploadResult.quote_mode,
          estimate_source: uploadResult.estimate_source,
          quote_token: uploadResult.quote_token,
          target_language: i18n.language,
          referral_code: referralCode || undefined,
        }),
      });
      if (!res.ok) throw new Error(`Payment failed: ${res.status}`);

      const data = await res.json();
      storeOrderAccessToken(data.order_id, data.access_token);
      if (data.komoju_session_url) {
        sessionStorage.setItem(`report-language:${data.order_id}`, i18n.language);
        // Redirect to KOMOJU payment page
        window.location.href = data.komoju_session_url;
      } else {
        sessionStorage.setItem(`report-language:${data.order_id}`, i18n.language);
        // Dev mode: still show the payment-success handoff so users save the order ID first.
        // Owner token is already persisted in sessionStorage above; no need to append to URL.
        navigate(`/payment/${data.order_id}`);
      }
    } catch (e) {
      setError(t('errors.payment_failed'));
    } finally {
      setPaying(false);
    }
  };

  useEffect(() => {
    if (!uploadResult) return;

    const timer = window.setTimeout(() => {
      const target = document.getElementById('payment-panel');
      target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);

    const clearCue = window.setTimeout(() => setResultReady(false), 2600);
    return () => {
      window.clearTimeout(timer);
      window.clearTimeout(clearCue);
    };
  }, [uploadResult]);

  useEffect(() => {
    const referralFromQuery = searchParams.get('ref')?.trim();
    if (!referralFromQuery) return;
    setReferralCode((current) => current || referralFromQuery);
  }, [searchParams]);

  return (
    <div className="page home-page" id="top">
      <RevealSection delayMs={0} variant="hero" className="home-scene home-scene-hero">
        <HomeHeroSection preview={heroPreview} />
      </RevealSection>
      <RevealSection delayMs={80} variant="panel" className="home-scene home-scene-flow">
        <HomeFlowSection />
      </RevealSection>
      <RevealSection delayMs={120} variant="panel" className="home-scene home-scene-upload">
        <HomeUploadSection
          inputMode={inputMode}
          setInputMode={setInputMode}
          textInput={textInput}
          setTextInput={setTextInput}
          file={file}
          setFile={setFile}
          uploadResult={uploadResult}
          loading={loading}
          error={error}
          email={email}
          setEmail={setEmail}
          referralCode={referralCode}
          setReferralCode={setReferralCode}
          paying={paying}
          onUpload={handleUpload}
          onPayment={handlePayment}
          onReset={() => { setUploadResult(null); setResultReady(false); }}
          spotlightResult={resultReady}
        />
      </RevealSection>
    </div>
  );
}
