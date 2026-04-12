import { useTranslation } from 'react-i18next';
import LegalSectionList from '../components/common/LegalSectionList';
import { OFFICIAL_PRIVACY_SECTIONS, getPrivacyCopy } from '../data/legalContent';
import styles from '../styles/legal.module.css';

export default function PrivacyPage() {
  const { t, i18n } = useTranslation();
  const copy = getPrivacyCopy(i18n.language);
  const isJapanese = i18n.language.startsWith('ja');
  const supportedList = t('privacy.supported_list', { returnObjects: true }) as string[];
  const notSupportedList = t('privacy.not_supported_list', { returnObjects: true }) as string[];

  return (
    <div className={`page ${styles.legalPage}`}>
      <h2>{t('privacy.page_title')}</h2>

      <div className={styles.summary}>
        <p>{t('privacy.summary')}</p>
      </div>

      <div className={styles.content}>
        <p className={styles.lastUpdated}>{t('privacy.last_updated', { date: '2026-03-29' })}</p>

        <section className={styles.flowCard}>
          <h3>{t('privacy.flow_title')}</h3>
          <ol className={styles.flowList}>
            <li>{t('privacy.flow_step_1')}</li>
            <li>{t('privacy.flow_step_2')}</li>
            <li>{t('privacy.flow_step_3')}</li>
            <li>{t('privacy.flow_step_4')}</li>
          </ol>
        </section>

        <div className={styles.scopeGrid}>
          <section className={styles.scopeCard}>
            <h3>{t('privacy.supported_title')}</h3>
            <ul>
              {supportedList.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>
          <section className={styles.scopeCard}>
            <h3>{t('privacy.not_supported_title')}</h3>
            <ul>
              {notSupportedList.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>
        </div>

        <section className={styles.noticeCard}>
          <h3>{copy.noticeTitle}</h3>
          <p>{copy.noticeBody}</p>
        </section>

        <LegalSectionList sections={copy.sections} />

        {!isJapanese && (
          <details className={styles.officialDetails}>
            <summary>{copy.officialToggleLabel}</summary>
            <div className={styles.officialContent}>
              <LegalSectionList sections={OFFICIAL_PRIVACY_SECTIONS} />
            </div>
          </details>
        )}
      </div>
    </div>
  );
}
