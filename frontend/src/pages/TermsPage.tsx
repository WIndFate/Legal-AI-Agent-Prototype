import { useTranslation } from 'react-i18next';
import { OFFICIAL_TERMS_SECTIONS, getTermsCopy, type LegalSection } from '../data/legalContent';
import styles from '../styles/legal.module.css';

function LegalSectionList({ sections }: { sections: LegalSection[] }) {
  return (
    <>
      {sections.map((section) => (
        <section key={section.title} className={styles.legalSection}>
          <h3>{section.title}</h3>
          {section.blocks.map((block, index) =>
            block.type === 'paragraph' ? (
              <div key={`${section.title}-${index}`}>
                {block.content.map((paragraph) => (
                  <p key={paragraph}>{paragraph}</p>
                ))}
              </div>
            ) : (
              <ul key={`${section.title}-${index}`}>
                {block.content.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ),
          )}
        </section>
      ))}
    </>
  );
}

export default function TermsPage() {
  const { t, i18n } = useTranslation();
  const copy = getTermsCopy(i18n.language);
  const isJapanese = i18n.language.startsWith('ja');

  return (
    <div className={`page ${styles.legalPage}`}>
      <h2>{t('terms.page_title')}</h2>

      <div className={styles.summary}>
        <p>{t('terms.summary')}</p>
      </div>

      <div className={styles.content}>
        <p className={styles.lastUpdated}>{t('terms.last_updated', { date: '2026-03-25' })}</p>

        <section className={styles.noticeCard}>
          <h3>{copy.noticeTitle}</h3>
          <p>{copy.noticeBody}</p>
        </section>

        <LegalSectionList sections={copy.sections} />

        {!isJapanese && (
          <details className={styles.officialDetails}>
            <summary>{copy.officialToggleLabel}</summary>
            <div className={styles.officialContent}>
              <p className={styles.officialSummary}>{copy.officialSummary}</p>
              <LegalSectionList sections={OFFICIAL_TERMS_SECTIONS} />
            </div>
          </details>
        )}
      </div>
    </div>
  );
}
