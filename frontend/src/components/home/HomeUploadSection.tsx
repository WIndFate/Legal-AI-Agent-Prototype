import { useId } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { useTranslation } from 'react-i18next';
import clsx from 'clsx';

import type { InputMode, UploadResult } from './types';
import styles from '../../styles/home.module.css';

interface HomeUploadSectionProps {
  inputMode: InputMode;
  setInputMode: Dispatch<SetStateAction<InputMode>>;
  textInput: string;
  setTextInput: Dispatch<SetStateAction<string>>;
  file: File | null;
  setFile: Dispatch<SetStateAction<File | null>>;
  uploadResult: UploadResult | null;
  loading: boolean;
  error: string;
  email: string;
  setEmail: Dispatch<SetStateAction<string>>;
  referralCode: string;
  setReferralCode: Dispatch<SetStateAction<string>>;
  paying: boolean;
  onUpload: () => Promise<void>;
  onPayment: () => Promise<void>;
  spotlightResult: boolean;
}

export default function HomeUploadSection({
  inputMode,
  setInputMode,
  textInput,
  setTextInput,
  file,
  setFile,
  uploadResult,
  loading,
  error,
  email,
  setEmail,
  referralCode,
  setReferralCode,
  paying,
  onUpload,
  onPayment,
  spotlightResult,
}: HomeUploadSectionProps) {
  const { t } = useTranslation();
  const fileInputId = useId();

  const tierLabel = (tier: string) => {
    const key = `pricing.tier_${tier}` as const;
    return t(key);
  };

  const quoteLabel =
    uploadResult?.quote_mode === 'estimated_pre_ocr'
      ? t('pricing.quote_estimated_label')
      : t('pricing.quote_exact_label');

  const quoteDescription =
    uploadResult?.quote_mode === 'estimated_pre_ocr'
      ? t('pricing.quote_estimated_desc')
      : t('pricing.quote_exact_desc');

  return (
    <section className="upload-shell" id="upload-section">
      <div className="section-heading">
        <h2>{t('upload.title')}</h2>
        <p className="section-intro">{t('upload.hero_body')}</p>
      </div>

      <div className="intake-trust-grid">
        <div className="intake-trust-card">
          <span>{t('upload.trust_privacy')}</span>
          <strong>24h</strong>
          <p>{t('pricing.assurance_privacy_desc')}</p>
        </div>
        <div className="intake-trust-card">
          <span>{t('upload.trust_payg')}</span>
          <strong>{t('review.live_label')}</strong>
          <p>{t('pricing.assurance_delivery_desc')}</p>
        </div>
        <div className="intake-trust-card">
          <span>{t('report.referenced_law')}</span>
          <strong>JP</strong>
          <p>{t('report.comparison_hint')}</p>
        </div>
      </div>

      <a href="/examples" className={styles.examplesEntryCard}>
        <span className={styles.examplesEntryIcon} aria-hidden="true" />
        <div className={styles.examplesEntryCopy}>
          <span>{t('examples.section_kicker')}</span>
          <strong>{t('examples.section_title')}</strong>
          <p>{t('examples.section_desc')}</p>
        </div>
        <span className={styles.examplesEntryLink}>{t('nav.examples')}</span>
      </a>

      <div className="input-tabs">
        <button
          className={clsx('tab', inputMode === 'file' && 'active')}
          onClick={() => setInputMode('file')}
        >
          {t('upload.file')}
        </button>
        <button
          className={clsx('tab', inputMode === 'text' && 'active')}
          onClick={() => setInputMode('text')}
        >
          {t('upload.paste')}
        </button>
      </div>

      <div className={styles.uploadArea}>
        {inputMode === 'text' ? (
          <textarea
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            placeholder={t('upload.placeholder')}
            rows={12}
          />
        ) : (
          <div className={styles.fileUpload}>
            <p className={styles.fileUploadTitle}>{t('upload.file')}</p>
            <p className={styles.fileUploadHint}>{t('upload.file_hint')}</p>
            <div className={styles.fileUploadActions}>
              <label htmlFor={fileInputId} className={styles.filePickerButton}>
                {t('upload.file')}
              </label>
              <span className={styles.filePickerCaption}>JPG / PNG / PDF</span>
            </div>
            <input
              id={fileInputId}
              className={styles.fileInput}
              type="file"
              accept="image/*,.pdf,application/pdf"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
            <div className={styles.formatPills}>
              <span className={styles.formatPill}>JPG</span>
              <span className={styles.formatPill}>PNG</span>
              <span className={styles.formatPill}>PDF</span>
            </div>
            {file && (
              <div className={styles.fileSummaryCard}>
                <span>{t('upload.file')}</span>
                <strong>{file.name}</strong>
              </div>
            )}
          </div>
        )}
      </div>

      <button
        className="btn-primary"
        onClick={() => void onUpload()}
        disabled={loading || (inputMode === 'text' ? !textInput.trim() : !file)}
      >
        {loading ? '...' : t('upload.submit')}
      </button>

      {error && <div className="error-message">{error}</div>}

      {uploadResult && uploadResult.pii_warnings.length > 0 && (
        <div className="pii-warning">
          <p>{t('pii.warning')}</p>
          <ul>
            {uploadResult.pii_warnings.map((warning, index) => (
              <li key={index}>
                {t(`pii.${warning.type}`)}: <code>{warning.text}</code>
              </li>
            ))}
          </ul>
        </div>
      )}

      {uploadResult && uploadResult.price_jpy > 0 && (
        <div
          id="payment-panel"
          className={clsx('pricing-card', 'polished-card', spotlightResult && 'spotlight-card')}
        >
          <div className="next-step-banner">
            <strong>{t('order.next_step_title')}</strong>
            <p>{t('order.next_step_body')}</p>
          </div>
          <div className="pricing-card-header">
            <div>
              <p className="section-kicker">{t('pricing.title')}</p>
              <h3>{tierLabel(uploadResult.price_tier)}</h3>
            </div>
            <div className="pricing-price-lockup">
              <span>{t('pricing.price')}</span>
              <p className={styles.priceAmount}>¥{uploadResult.price_jpy.toLocaleString()}</p>
            </div>
          </div>
          <div className={styles.pricingQuoteMeta}>
            <strong>{quoteLabel}</strong>
            <p>{quoteDescription}</p>
          </div>
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
              <span>{t('payment.title')}</span>
              <strong>{t('payment.secure_note')}</strong>
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

          <div className={styles.paymentForm}>
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
              onClick={() => void onPayment()}
              disabled={paying || !email}
            >
              {paying
                ? t('payment.processing')
                : t('payment.pay_button', { price: uploadResult.price_jpy.toLocaleString() })}
            </button>
            <p className="payment-note">{t('payment.secure_note')}</p>
          </div>
        </div>
      )}
    </section>
  );
}
