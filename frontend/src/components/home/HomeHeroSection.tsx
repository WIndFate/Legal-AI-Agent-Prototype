import { useTranslation } from 'react-i18next';

import type { ExampleReport } from '../../data/exampleReports';
import { exampleRiskColor } from './utils';

interface HomeHeroSectionProps {
  preview: ExampleReport;
}

export default function HomeHeroSection({ preview }: HomeHeroSectionProps) {
  const { t } = useTranslation();

  return (
    <section className="hero-card hero-grid">
      <div className="hero-copy">
        <p className="section-kicker">{t('upload.hero_kicker')}</p>
        <h2 className="hero-title">{t('app.title')}</h2>
        <p className="hero-subtitle">{t('upload.hero_body')}</p>
        <div className="trust-strip">
          <span className="trust-pill">{t('upload.trust_privacy')}</span>
          <span className="trust-pill">{t('upload.trust_no_account')}</span>
          <span className="trust-pill">{t('upload.trust_payg')}</span>
        </div>
        <div className="hero-metrics">
          <div className="hero-metric">
            <span>{t('pricing.title')}</span>
            <strong>{t('pricing.dynamic_quote')}</strong>
          </div>
          <div className="hero-metric">
            <span>{t('report.title')}</span>
            <strong>24h</strong>
          </div>
          <div className="hero-metric">
            <span>{t('report.referenced_law')}</span>
            <strong>JP</strong>
          </div>
        </div>
      </div>

      <div className="hero-preview-card">
        <div className="hero-preview-head">
          <span className="hero-preview-label">{t('report.title')}</span>
          <span
            className="risk-badge hero-preview-badge"
            style={{ background: exampleRiskColor(preview.overall_risk) }}
          >
            {preview.overall_risk}
          </span>
        </div>
        <div className="hero-preview-body">
          {preview.clauses.slice(0, 2).map((clause, idx) => (
            <div key={clause.clause_number} className="hero-preview-item">
              <div className="hero-preview-row">
                <strong>{clause.clause_number}</strong>
                <span
                  className="risk-tag"
                  style={{ background: exampleRiskColor(clause.risk_level) }}
                >
                  {clause.risk_level}
                </span>
              </div>
              <p className="hero-preview-text">{t(`examples.${preview.id}_c${idx + 1}_reason`)}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
