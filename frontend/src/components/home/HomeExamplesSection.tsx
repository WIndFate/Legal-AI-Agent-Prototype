import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { exampleReports } from '../../data/exampleReports';
import type { ExampleReport } from '../../data/exampleReports';
import { exampleRiskBg, exampleRiskColor } from './utils';

type TabKey = 'rental' | 'employment' | 'parttime';

export default function HomeExamplesSection() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<TabKey>('rental');

  const tabs: { key: TabKey; label: string }[] = [
    { key: 'rental', label: t('examples.tab_rental') },
    { key: 'employment', label: t('examples.tab_employment') },
    { key: 'parttime', label: t('examples.tab_parttime') },
  ];

  const report: ExampleReport = exampleReports[activeTab];

  return (
    <section className="examples-section" id="examples">
      <p className="section-kicker">{t('examples.section_kicker')}</p>
      <h2>{t('examples.section_title')}</h2>
      <p className="examples-desc">{t('examples.section_desc')}</p>

      <div className="example-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            className={`tab ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="example-report-card">
        <div className="example-report-header">
          <span className="example-badge">{t('examples.badge')}</span>
          <h3>{t(`examples.${activeTab}_title`)}</h3>
          <p className="example-report-desc">{t(`examples.${activeTab}_desc`)}</p>
        </div>

        <div className="example-overall-risk">
          <span
            className="risk-badge"
            style={{ background: exampleRiskColor(report.overall_risk) }}
          >
            {t('report.overall_risk')}: {report.overall_risk}
          </span>
          <div className="example-meta-grid">
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

        <div className="example-clause-list">
          {report.clauses.map((clause, idx) => (
            <div
              key={idx}
              className="example-clause-card"
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
              <div className="example-original-text">{clause.original_text}</div>
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

      <a href="#upload-section" className="btn-primary example-cta">
        {t('examples.cta')}
      </a>
    </section>
  );
}
