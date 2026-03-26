import { useTranslation } from 'react-i18next';

export default function HomeFlowSection() {
  const { t } = useTranslation();

  return (
    <section className="flow-card">
      <p className="section-kicker">{t('upload.how_it_works')}</p>
      <h2>{t('upload.how_it_works')}</h2>
      <div className="flow-steps">
        <div className="flow-step">
          <span className="flow-index">1</span>
          <div>
            <strong>{t('upload.flow_upload_title')}</strong>
            <p>{t('upload.flow_upload_desc')}</p>
          </div>
        </div>
        <div className="flow-step">
          <span className="flow-index">2</span>
          <div>
            <strong>{t('upload.flow_review_title')}</strong>
            <p>{t('upload.flow_review_desc')}</p>
          </div>
        </div>
        <div className="flow-step">
          <span className="flow-index">3</span>
          <div>
            <strong>{t('upload.flow_report_title')}</strong>
            <p>{t('upload.flow_report_desc')}</p>
          </div>
        </div>
      </div>
    </section>
  );
}
