import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import clsx from 'clsx';

import { exampleReports } from '../../data/exampleReports';
import type { ExampleReport } from '../../data/exampleReports';
import { exampleRiskBg, exampleRiskColor } from './utils';
import styles from '../../styles/examples.module.css';

type TabKey = 'rental' | 'employment' | 'parttime';
type ExampleRiskFilter = 'high' | 'medium' | 'low';

interface HomeExamplesSectionProps {
  standalone?: boolean;
}

export default function HomeExamplesSection({ standalone = false }: HomeExamplesSectionProps) {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<TabKey>('rental');
  const [selectedRisks, setSelectedRisks] = useState<ExampleRiskFilter[]>(['high', 'medium', 'low']);
  const reportCardRef = useRef<HTMLDivElement | null>(null);

  const tabs: { key: TabKey; label: string }[] = [
    { key: 'rental', label: t('examples.tab_rental') },
    { key: 'employment', label: t('examples.tab_employment') },
    { key: 'parttime', label: t('examples.tab_parttime') },
  ];

  const report: ExampleReport = exampleReports[activeTab];
  const filteredClauses = report.clauses.filter((clause) => {
    if (selectedRisks.length === 0) return false;
    if (clause.risk_level === '高') return selectedRisks.includes('high');
    if (clause.risk_level === '中') return selectedRisks.includes('medium');
    if (clause.risk_level === '低') return selectedRisks.includes('low');
    return true;
  });

  const toggleRiskFilter = (risk: ExampleRiskFilter) => {
    setSelectedRisks((prev) => (
      prev.includes(risk) ? prev.filter((item) => item !== risk) : [...prev, risk]
    ));
  };

  const allSelected = selectedRisks.length === 3;
  const filterMetrics = [
    {
      key: 'all' as const,
      label: t('report.clause_count'),
      value: report.clauses.length,
      active: allSelected,
      onClick: () => setSelectedRisks(['high', 'medium', 'low']),
    },
    {
      key: 'high' as const,
      label: t('report.high_risk'),
      value: report.clauses.filter((clause) => clause.risk_level === '高').length,
      active: selectedRisks.includes('high'),
      onClick: () => toggleRiskFilter('high'),
      accent: 'high',
    },
    {
      key: 'medium' as const,
      label: t('report.medium_risk'),
      value: report.clauses.filter((clause) => clause.risk_level === '中').length,
      active: selectedRisks.includes('medium'),
      onClick: () => toggleRiskFilter('medium'),
      accent: 'medium',
    },
    {
      key: 'low' as const,
      label: t('report.low_risk'),
      value: report.clauses.filter((clause) => clause.risk_level === '低').length,
      active: selectedRisks.includes('low'),
      onClick: () => toggleRiskFilter('low'),
      accent: 'low',
    },
  ];

  const handleTabChange = (tab: TabKey) => {
    setActiveTab(tab);
    setSelectedRisks(['high', 'medium', 'low']);

    if (!standalone || !window.matchMedia('(max-width: 767px)').matches) {
      return;
    }

    window.setTimeout(() => {
      reportCardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
  };

  return (
    <section
      className={clsx('examples-section', standalone && styles.standaloneSection)}
      id={standalone ? undefined : 'examples'}
    >
      <p className="section-kicker">{t('examples.section_kicker')}</p>
      <h2>{t('examples.section_title')}</h2>
      <p className={styles.desc}>{t('examples.section_desc')}</p>

      {standalone ? (
        <div className={styles.galleryLayout}>
          <div className={styles.curatedStrip}>
            <div className={styles.scenarioList}>
              {tabs.map((tab) => (
                <button
                  key={tab.key}
                  className={clsx(styles.scenarioCard, activeTab === tab.key && styles.scenarioCardActive)}
                  onClick={() => handleTabChange(tab.key)}
                >
                  <div className={styles.scenarioTopline}>
                    <span className={styles.scenarioIndex}>
                      {String(tabs.findIndex((item) => item.key === tab.key) + 1).padStart(2, '0')}
                    </span>
                    <span className={styles.scenarioEyebrow}>{t('examples.badge')}</span>
                  </div>
                  <strong>{t(`examples.${tab.key}_title`)}</strong>
                  <p>{t(`examples.${tab.key}_desc`)}</p>
                </button>
              ))}
            </div>
          </div>

          <div ref={reportCardRef} className={styles.reportCard}>
            <div className={styles.documentRibbon}>
              <span>{t('report.title')}</span>
              <span>{t('report.executive_kicker')}</span>
            </div>
            <div className={styles.reportHeader}>
              <div className={styles.reportHeaderTop}>
                <div>
                  <h3>{t(`examples.${activeTab}_title`)}</h3>
                  <p className={styles.reportLead}>{tabs.find((tab) => tab.key === activeTab)?.label}</p>
                </div>
                <span className={styles.reportStatus}>
                  {t('report.overall_risk')}: {report.overall_risk}
                </span>
              </div>
              <p className={styles.reportDesc}>{t(`examples.${activeTab}_desc`)}</p>
            </div>

            <div className={styles.overallRisk}>
              <div className={styles.overviewHeader}>
                <span
                  className="risk-badge"
                  style={{ background: exampleRiskColor(report.overall_risk) }}
                >
                  {t('report.overall_risk')}: {report.overall_risk}
                </span>
                <p className={styles.overviewNote}>{t('pricing.assurance_delivery_desc')}</p>
              </div>
              <div className={styles.filterHintRow}>
                <span className={styles.filterHintIcon} aria-hidden="true">
                  <svg viewBox="0 0 16 16">
                    <path d="M2 4h12M4.5 8h7M6.5 12h3" />
                  </svg>
                </span>
                <p>{t('report.filter_hint')}</p>
              </div>
              <div className={styles.reportFilterGrid}>
                {filterMetrics.map((metric) => (
                  <button
                    key={metric.key}
                    type="button"
                    className={clsx(
                      styles.reportFilterCard,
                      metric.active && styles.reportFilterCardActive,
                      metric.accent === 'high' && styles.reportFilterCardHigh,
                      metric.accent === 'medium' && styles.reportFilterCardMedium,
                      metric.accent === 'low' && styles.reportFilterCardLow,
                    )}
                    onClick={metric.onClick}
                  >
                    <span>{metric.label}</span>
                    <strong>{metric.value}</strong>
                  </button>
                ))}
              </div>
            </div>

            <div className={styles.clauseList}>
              {filteredClauses.length > 0 ? filteredClauses.map((clause, idx) => {
                const clauseIndex = report.clauses.findIndex((item) => item.clause_number === clause.clause_number) + 1;
                return (
                  <div
                    key={`${clause.clause_number}-${idx}`}
                    className={styles.clauseCard}
                    style={{
                      borderLeftColor: exampleRiskColor(clause.risk_level),
                      background: exampleRiskBg(clause.risk_level),
                    }}
                  >
                    <div className="clause-header">
                      <div className="clause-heading">
                        <span className="clause-eyebrow">{t('report.finding_label')}</span>
                        <strong>{clause.clause_number}</strong>
                      </div>
                      <span
                        className="risk-tag"
                        style={{ background: exampleRiskColor(clause.risk_level) }}
                      >
                        {clause.risk_level}
                      </span>
                    </div>
                    <div className={styles.clauseMetaRow}>
                      <div className={styles.clauseMetaCard}>
                        <span>{t('report.original_clause_label')}</span>
                        <strong>{t('report.comparison_title')}</strong>
                      </div>
                      <div className={styles.clauseMetaCard}>
                        <span>{t('report.referenced_law')}</span>
                        <strong>{t('report.japanese_original')}</strong>
                      </div>
                    </div>
                    <div className={styles.originalText}>{clause.original_text}</div>
                    <div className="analysis-block">
                      <span className="analysis-label">{t('report.assessment_label')}</span>
                      <p className="risk-reason">{t(`examples.${report.id}_c${clauseIndex}_reason`)}</p>
                    </div>
                    <div className="suggestion">
                      <span className="analysis-label">{t('report.suggestion_label')}</span>
                      <p>{t(`examples.${report.id}_c${clauseIndex}_suggestion`)}</p>
                    </div>
                    {clause.referenced_law && (
                      <div className="reference">
                        <span className="analysis-label">{t('report.reference_label')}</span>
                        <p>{clause.referenced_law}</p>
                      </div>
                    )}
                  </div>
                );
              }) : (
                <div className={styles.emptyState}>{t('report.filter_empty')}</div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <>
          <div className="example-tabs">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                className={clsx('tab', activeTab === tab.key && 'active')}
                onClick={() => handleTabChange(tab.key)}
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
                  <strong>{t('report.japanese_original')}</strong>
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
        </>
      )}

      <a href="/#upload-section" className={clsx('btn-primary', styles.cta)}>
        {t('examples.cta')}
      </a>
    </section>
  );
}
