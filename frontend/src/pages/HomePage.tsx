import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import HomeExamplesSection from '../components/home/HomeExamplesSection';
import HomeFlowSection from '../components/home/HomeFlowSection';
import HomeHeroSection from '../components/home/HomeHeroSection';
import HomeUploadSection from '../components/home/HomeUploadSection';
import type { InputMode, UploadResult } from '../components/home/types';
import { exampleReports } from '../data/exampleReports';

export default function HomePage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const heroPreview = exampleReports.rental;

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
          page_estimate: uploadResult.page_estimate,
          price_tier: uploadResult.price_tier,
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
        // Dev mode: skip payment, go directly to review
        navigate(`/review/${data.order_id}`);
      }
    } catch (e) {
      setError(t('errors.payment_failed'));
    } finally {
      setPaying(false);
    }
  };

  return (
    <div className="page home-page" id="top">
      <HomeHeroSection preview={heroPreview} />
      <HomeFlowSection />
      <HomeExamplesSection />
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
      />
    </div>
  );
}
