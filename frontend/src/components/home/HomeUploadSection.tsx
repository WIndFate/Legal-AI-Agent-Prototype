import { useEffect, useId, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import clsx from 'clsx';

import type { InputMode, UploadResult } from './types';
import { SUPPORTED_LANGUAGES } from '../../i18n';
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
  const { t, i18n } = useTranslation();
  const fileInputId = useId();
  const [previewExpanded, setPreviewExpanded] = useState(false);
  const [languageConfirmed, setLanguageConfirmed] = useState(false);
  const hasOcrNotice = Boolean(uploadResult?.ocr_warnings?.length);
  const isLowOcrConfidence = uploadResult?.ocr_confidence === 'low';
  const isMediumOcrConfidence =
    uploadResult?.ocr_confidence === 'medium' || (uploadResult?.ocr_confidence == null && hasOcrNotice);
  const previewItems = uploadResult?.clause_preview ?? [];
  const visiblePreviewItems = previewExpanded ? previewItems : previewItems.slice(0, 5);
  const resolvedLanguage = i18n.resolvedLanguage ?? i18n.language;
  const currentLanguageLabel =
    SUPPORTED_LANGUAGES.find(({ code }) => code === resolvedLanguage)?.name ?? resolvedLanguage;

  useEffect(() => {
    setPreviewExpanded(false);
  }, [uploadResult]);

  useEffect(() => {
    setLanguageConfirmed(false);
  }, [uploadResult, resolvedLanguage]);

  return (
    <section className="upload-shell" id="upload-section">
      <div className="section-heading">
        <h2>{t('upload.title')}</h2>
        <p className="section-intro">{t('upload.hero_body')}</p>
      </div>

      <div className="intake-trust-grid">
        <div className="intake-trust-card">
          <span>{t('upload.trust_privacy')}</span>
          <strong>72h</strong>
          <p>{t('pricing.assurance_privacy_desc')}</p>
        </div>
        <div className="intake-trust-card">
          <span>{t('upload.trust_payg')}</span>
          <strong>{t('review.live_label')}</strong>
          <p>{t('pricing.assurance_delivery_desc')}</p>
        </div>
        <div className="intake-trust-card">
          <span>{t('report.referenced_law')}</span>
          <strong>{t('report.japanese_original')}</strong>
          <p>{t('report.comparison_hint')}</p>
        </div>
      </div>
      <div className={styles.privacyInline}>
        <span>{t('upload.privacy_inline')}</span>
        <Link to="/privacy" className={styles.privacyInlineLink}>
          {t('footer.privacy')}
        </Link>
      </div>

      <div className={styles.mobileUtilityGrid}>
        <Link to="/examples" className={styles.examplesEntryCard}>
          <span className={styles.examplesEntryIcon} aria-hidden="true" />
          <div className={styles.examplesEntryCopy}>
            <span>{t('examples.section_kicker')}</span>
            <strong>{t('examples.section_title')}</strong>
            <p>{t('examples.section_desc')}</p>
          </div>
          <span className={styles.examplesEntryLink}>{t('nav.examples')}</span>
        </Link>

        <Link to="/lookup" className={clsx(styles.examplesEntryCard, styles.lookupEntryCard)}>
          <span className={clsx(styles.examplesEntryIcon, styles.lookupEntryIcon)} aria-hidden="true" />
          <div className={styles.examplesEntryCopy}>
            <span>{t('order.lookup_kicker')}</span>
            <strong>{t('nav.lookup')}</strong>
            <p>{t('order.lookup_help_body')}</p>
          </div>
          <span className={styles.examplesEntryLink}>{t('order.lookup_action')}</span>
        </Link>
      </div>

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
            enterKeyHint="done"
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
        className={clsx('btn-primary', loading && styles.loadingActionButton)}
        onClick={() => void onUpload()}
        disabled={loading || (inputMode === 'text' ? !textInput.trim() : !file)}
      >
        <span className={styles.actionButtonContent}>
          <span
            className={clsx(styles.actionButtonIcon, loading && styles.actionButtonIconLoading)}
            aria-hidden="true"
          />
          <span>{loading ? t('upload.preview_loading_button') : t('upload.submit')}</span>
        </span>
      </button>

      {loading && (
        <div className={styles.previewLoadingCard} role="status" aria-live="polite">
          <span className={styles.previewLoadingSpinner} aria-hidden="true" />
          <div className={styles.previewLoadingCopy}>
            <strong>{t('upload.preview_loading_title')}</strong>
            <p>{t('upload.preview_loading_body')}</p>
          </div>
        </div>
      )}

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
          <div className={clsx('next-step-banner', styles.paymentBanner)}>
            <strong>{t('order.next_step_title')}</strong>
            <p>{t('order.next_step_body')}</p>
          </div>
          <div className="pricing-card-header">
            <div>
              <p className="section-kicker">{t('pricing.title')}</p>
              <h3>{t('pricing.length_based')}</h3>
            </div>
            <div className="pricing-price-lockup">
              <span>{t('pricing.price')}</span>
              <p className={styles.priceAmount}>¥{uploadResult.price_jpy.toLocaleString()}</p>
            </div>
          </div>
          {hasOcrNotice && (
            <div
              className={clsx(
                styles.ocrNotice,
                isLowOcrConfidence ? styles.ocrNoticeWarning : styles.ocrNoticeInfo,
              )}
              role="status"
            >
              <strong>{t(isLowOcrConfidence ? 'upload.ocr_notice_title' : 'upload.ocr_notice_info_title')}</strong>
              <ul>
                {uploadResult.ocr_warnings.map((warning) => (
                  <li key={warning}>{t(warning)}</li>
                ))}
              </ul>
              {isMediumOcrConfidence && uploadResult.ocr_confidence === 'medium' && (
                <p>{t('upload.ocr_post_payment_notice')}</p>
              )}
            </div>
          )}
          <div className={styles.pricingQuoteMeta}>
            <p>{t('pricing.length_based_desc')}</p>
            <span>{t('pricing.minimum_price', { price: 200 })}</span>
          </div>
          {uploadResult.quote_mode === 'exact' && previewItems.length > 0 && (
            <div className={styles.clausePreviewCard}>
              <div className={styles.clausePreviewHeader}>
                <strong>{t('upload.clause_preview_title', { count: uploadResult.clause_count ?? previewItems.length })}</strong>
                {previewItems.length > 5 && (
                  <button
                    type="button"
                    className={styles.clausePreviewToggle}
                    onClick={() => setPreviewExpanded((current) => !current)}
                  >
                    {previewExpanded
                      ? t('upload.clause_preview_collapse')
                      : t('upload.clause_preview_expand', { count: previewItems.length })}
                  </button>
                )}
              </div>
              <ul className={styles.clausePreviewList}>
                {visiblePreviewItems.map((item, index) => (
                  <li key={`${item.number}-${item.title}-${index}`} className={styles.clausePreviewItem}>
                    <span>{item.number}</span>
                    <strong>{item.title}</strong>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {uploadResult.quote_mode === 'estimated_pre_ocr' && (
            <div className={clsx(styles.clausePreviewCard, styles.clausePreviewPending)}>
              <strong>{t('upload.clause_preview_pending_title')}</strong>
              <p>{t('upload.clause_preview_unavailable')}</p>
            </div>
          )}
          <div className={styles.pricingHighlights} aria-label={t('payment.title')}>
            <div className={styles.pricingHighlight}>
              <strong>{t('payment.secure_note')}</strong>
            </div>
            <div className={styles.pricingHighlight}>
              <strong>{t('pricing.assurance_privacy_title')}</strong>
              <span>{t('pricing.assurance_privacy_desc')}</span>
            </div>
            <div className={styles.pricingHighlight}>
              <strong>{t('pricing.assurance_delivery_title')}</strong>
              <span>{t('pricing.assurance_delivery_desc')}</span>
            </div>
          </div>

          <div className={styles.paymentForm}>
            <h3>{t('payment.title')}</h3>
            <div className={styles.languageLockCard}>
              <div className={styles.languageLockHeader}>
                <strong>{t('payment.language_lock_title')}</strong>
                <span className={styles.languageLockBadge}>{currentLanguageLabel}</span>
              </div>
              <p>{t('payment.language_lock_body', { language: currentLanguageLabel })}</p>
              <label className={styles.languageLockConfirm}>
                <input
                  type="checkbox"
                  checked={languageConfirmed}
                  onChange={(e) => setLanguageConfirmed(e.target.checked)}
                />
                <span>{t('payment.language_lock_confirm')}</span>
              </label>
            </div>
            <label>
              {t('payment.email_label')}
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={t('payment.email_placeholder')}
                inputMode="email"
                autoComplete="email"
              />
            </label>
            <label>
              {t('payment.referral_label')}
              <input
                type="text"
                value={referralCode}
                onChange={(e) => setReferralCode(e.target.value)}
                placeholder={t('payment.referral_placeholder')}
                autoCapitalize="characters"
                autoCorrect="off"
                spellCheck={false}
              />
            </label>
            <button
              className="btn-primary btn-pay"
              onClick={() => void onPayment()}
              disabled={paying || !email || !languageConfirmed}
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
