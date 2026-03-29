import { useTranslation } from 'react-i18next';

import type { ExampleReport } from '../../data/exampleReports';
import { exampleRiskColor } from './utils';
import styles from '../../styles/home.module.css';

interface HomeHeroSectionProps {
  preview: ExampleReport;
}

export default function HomeHeroSection({ preview }: HomeHeroSectionProps) {
  const { t } = useTranslation();

  return (
    <section className="hero-card hero-grid">
      <div className={styles.heroCopy}>
        <p className="section-kicker">{t('upload.hero_kicker')}</p>
        <h2 className={styles.heroTitle}>{t('upload.hero_title')}</h2>
        <p className={styles.heroBrand}>{t('app.title')}</p>
        <p className={styles.heroSubtitle}>{t('upload.hero_body')}</p>
        <div className={styles.heroActions}>
          <a href="#upload-section" className={styles.heroPrimaryAction}>
            {t('upload.submit')}
          </a>
          <a href="/examples" className={styles.heroSecondaryAction}>
            {t('nav.examples')}
          </a>
        </div>
        <div className={styles.trustStrip}>
          <span className={styles.trustPill}>{t('upload.trust_privacy')}</span>
          <span className={styles.trustPill}>{t('upload.trust_no_account')}</span>
          <span className={styles.trustPill}>{t('upload.trust_payg')}</span>
          <span className={styles.trustPill}>{t('upload.trust_supported_types')}</span>
        </div>
        <div className="hero-metrics">
          <div className="hero-metric">
            <span>{t('pricing.title')}</span>
            <strong>{t('pricing.length_based')}</strong>
          </div>
          <div className="hero-metric">
            <span>{t('report.title')}</span>
            <strong>72h</strong>
          </div>
          <div className="hero-metric">
            <span>{t('report.referenced_law')}</span>
            <strong>{t('report.japanese_original')}</strong>
          </div>
        </div>
      </div>

      <div className={styles.heroPreviewCard}>
        <div className={`hero-preview-head ${styles.heroPreviewHead}`}>
          <span className={styles.heroPreviewLabel}>{t('report.title')}</span>
          <span
            className={`risk-badge ${styles.heroPreviewBadge}`}
            style={{ background: exampleRiskColor(preview.overall_risk) }}
          >
            {preview.overall_risk}
          </span>
        </div>
        <div className={styles.heroPreviewBody}>
          {preview.clauses.slice(0, 2).map((clause, idx) => (
            <div
              key={clause.clause_number}
              className={`${styles.heroPreviewItem} ${idx > 0 ? styles.heroPreviewItemSecondary : ''}`}
            >
              <div className={`hero-preview-row ${styles.heroPreviewRow}`}>
                <strong className={styles.heroPreviewClause}>{clause.clause_number}</strong>
                <span
                  className={`risk-tag ${styles.heroPreviewRiskTag}`}
                  style={{ background: exampleRiskColor(clause.risk_level) }}
                >
                  {clause.risk_level}
                </span>
              </div>
              <p className={styles.heroPreviewText}>{t(`examples.${preview.id}_c${idx + 1}_reason`)}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
