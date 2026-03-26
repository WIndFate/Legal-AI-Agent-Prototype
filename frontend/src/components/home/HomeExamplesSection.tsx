import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import clsx from 'clsx';

import { exampleReports } from '../../data/exampleReports';
import type { ExampleReport } from '../../data/exampleReports';
import { exampleRiskBg, exampleRiskColor } from './utils';
import styles from '../../styles/examples.module.css';

type TabKey = 'rental' | 'employment' | 'parttime';

interface HomeExamplesSectionProps {
  standalone?: boolean;
}

export default function HomeExamplesSection({ standalone = false }: HomeExamplesSectionProps) {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<TabKey>('rental');

  const tabs: { key: TabKey; label: string }[] = [
    { key: 'rental', label: t('examples.tab_rental') },
    { key: 'employment', label: t('examples.tab_employment') },
    { key: 'parttime', label: t('examples.tab_parttime') },
  ];

  const report: ExampleReport = exampleReports[activeTab];

  return (
    <section
      className={clsx('examples-section', standalone && styles.standaloneSection)}
      id={standalone ? undefined : 'examples'}
    >
      <p className="section-kicker">{t('examples.section_kicker')}</p>
      <h2>{t('examples.section_title')}</h2>
      <p className={styles.desc}>{t('examples.section_desc')}</p>

      <div className="example-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            className={clsx('tab', activeTab === tab.key && 'active')}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className={styles.reportCard}>
        <div className={styles.reportHeader}>
          <span className={styles.badge}>{t('examples.badge')}</span>
          <h3>{t(`examples.${activeTab}_title`)}</h3>
          <p className={styles.reportDesc}>{t(`examples.${activeTab}_desc`)}</p>
        </div>

        <div className={styles.overallRisk}>
          <span
            className="risk-badge"
            style={{ background: exampleRiskColor(report.overall_risk) }}
          >
            {t('report.overall_risk')}: {report.overall_risk}
          </span>
          <div className={styles.metaGrid}>
            <div className="example-meta-item">
              <span>{t('report.clause_count')}</span>
              <strong>{report.clauses.length}</strong>
            </div>
            <div className="example-meta-item">
              <span>{t('report.referenced_law')}</span>
              <strong>JP</strong>
            </div>
          </div>
        </div>

        <div className={styles.clauseList}>
          {report.clauses.map((clause, idx) => (
            <div
              key={idx}
              className={styles.clauseCard}
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
              <div className={styles.originalText}>{clause.original_text}</div>
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

      <a href="/#upload-section" className={clsx('btn-primary', styles.cta)}>
        {t('examples.cta')}
      </a>
    </section>
  );
}
