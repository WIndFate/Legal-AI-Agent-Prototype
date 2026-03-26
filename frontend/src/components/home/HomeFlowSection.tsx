import { useTranslation } from 'react-i18next';
import styles from '../../styles/home.module.css';

export default function HomeFlowSection() {
  const { t } = useTranslation();

  return (
    <section className="flow-card">
      <p className="section-kicker">{t('upload.how_it_works')}</p>
      <h2>{t('upload.how_it_works')}</h2>
      <div className={styles.flowSteps}>
        <div className={styles.flowStep}>
          <span className={styles.flowIndex}>1</span>
          <div>
            <strong>{t('upload.flow_upload_title')}</strong>
            <p>{t('upload.flow_upload_desc')}</p>
          </div>
        </div>
        <div className={styles.flowStep}>
          <span className={styles.flowIndex}>2</span>
          <div>
            <strong>{t('upload.flow_review_title')}</strong>
            <p>{t('upload.flow_review_desc')}</p>
          </div>
        </div>
        <div className={styles.flowStep}>
          <span className={styles.flowIndex}>3</span>
          <div>
            <strong>{t('upload.flow_report_title')}</strong>
            <p>{t('upload.flow_report_desc')}</p>
          </div>
        </div>
      </div>
    </section>
  );
}
