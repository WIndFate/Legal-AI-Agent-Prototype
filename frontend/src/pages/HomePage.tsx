import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';

import RevealSection from '../components/common/RevealSection';
import HomeFlowSection from '../components/home/HomeFlowSection';
import HomeHeroSection from '../components/home/HomeHeroSection';
import HomeUploadSection from '../components/home/HomeUploadSection';
import type { InputMode, UploadResult } from '../components/home/types';
import { exampleReports } from '../data/exampleReports';

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
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`);

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
          input_type:
            inputMode === 'text'
              ? 'text'
              : uploadResult.upload_mime_type === 'application/pdf'
                ? 'pdf'
                : 'image',
          estimated_tokens: uploadResult.estimated_tokens,
          price_jpy: uploadResult.price_jpy,
          quote_mode: uploadResult.quote_mode,
          estimate_source: uploadResult.estimate_source,
          upload_token: uploadResult.upload_token,
          upload_name: uploadResult.upload_name,
          upload_mime_type: uploadResult.upload_mime_type,
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
        // Dev mode: still show the payment-success handoff so users save the order ID first.
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
          spotlightResult={resultReady}
        />
      </RevealSection>
    </div>
  );
}
